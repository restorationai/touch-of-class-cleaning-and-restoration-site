#!/usr/bin/env python3
"""Email intake for setup@restorationai.io — the email half of the Concierge.

Polls the contact@restorationai.io Gmail inbox (setup@ is an alias that
delivers there) for new messages addressed to setup@, matches the sender to a
client, classifies the body against that client's open onboarding items with
the SAME classifier the SMS concierge uses, records answers into
client_intake_items, saves attachments, and escalates anything ambiguous
(which also fires the ops-ping SMS to Santino's cell).

Processed messages get the Gmail label `concierge-processed` — that label IS
the cursor, so re-runs never double-process and nothing depends on local
state. No outbound email is sent in v1; confirmations still ride the SMS
concierge.

Commands:
    auth            one-time OAuth consent for contact@restorationai.io
                    (opens browser; stores refresh token at
                    ~/.config/rankai/gmail_token.json — NEVER in the repo)
    poll [--send]   process new setup@ mail. Default is dry-run (prints what
                    it would record); --send writes + labels + ops-pings.
    install-cron    launchd job: poll --send every 5 minutes (M-F 6-20 PT
                    gating is NOT applied — email can be read any time; only
                    outbound client messaging is business-hours gated).

Env (same .env as the concierge): GOOGLE_OAUTH_CLIENT_ID/SECRET,
SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, ANTHROPIC_API_KEY, GHL_* (ops-ping).
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from client_concierge import (  # noqa: E402
    CLASSIFY_SYSTEM, anthropic_json, append_escalation, apply_answer,
    fetch_companies, flush_ops_pings, gather_items, load_env, load_meeting_intel,
)

TOKEN_PATH = Path.home() / ".config" / "rankai" / "gmail_token.json"
INTAKE_ALIAS = "setup@restorationai.io"
PROCESSED_LABEL = "concierge-processed"
GMAIL = "https://gmail.googleapis.com/gmail/v1/users/me"
SCOPE = "https://www.googleapis.com/auth/gmail.modify"
ATTACH_DIR = Path(__file__).parent.parent / "clients" / "_ops" / "email-intake"

# The canary/test sender maps to the Test company, same as the SMS canary.
CANARY_SENDERS = {"contact@getrestorationai.com": "CO-1782880883337"}


# ------------------------------------------------------------------ OAuth
def _http(url: str, data: bytes | None = None, headers: dict | None = None,
          method: str | None = None) -> dict:
    req = urllib.request.Request(url, data=data, headers=headers or {},
                                 method=method)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode() or "{}")


def cmd_auth(_args) -> int:
    cid = os.environ["GOOGLE_OAUTH_CLIENT_ID"]
    secret = os.environ["GOOGLE_OAUTH_CLIENT_SECRET"]
    import http.server
    import socketserver
    import webbrowser

    port = 8765
    redirect = f"http://localhost:{port}/"
    auth_url = ("https://accounts.google.com/o/oauth2/v2/auth?"
                + urllib.parse.urlencode({
                    "client_id": cid, "redirect_uri": redirect,
                    "response_type": "code", "scope": SCOPE,
                    "access_type": "offline", "prompt": "consent",
                    "login_hint": "contact@restorationai.io"}))
    code_holder: dict = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            code_holder["code"] = (q.get("code") or [""])[0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Done - you can close this tab.")

        def log_message(self, *a):  # silence request logging
            pass

    print(f"Opening browser for consent (sign in as contact@restorationai.io)...\n{auth_url}\n")
    webbrowser.open(auth_url)
    with socketserver.TCPServer(("", port), H) as httpd:
        while not code_holder.get("code"):
            httpd.handle_request()
    tok = _http("https://oauth2.googleapis.com/token",
                data=urllib.parse.urlencode({
                    "code": code_holder["code"], "client_id": cid,
                    "client_secret": secret, "redirect_uri": redirect,
                    "grant_type": "authorization_code"}).encode(),
                headers={"Content-Type": "application/x-www-form-urlencoded"})
    if "refresh_token" not in tok:
        print(f"ERROR: no refresh_token in response: {tok}", file=sys.stderr)
        return 1
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(json.dumps(tok))
    TOKEN_PATH.chmod(0o600)
    print(f"Refresh token stored at {TOKEN_PATH}. Run: email_intake.py poll")
    return 0


def access_token() -> str:
    if not TOKEN_PATH.exists():
        sys.exit(f"No Gmail token at {TOKEN_PATH} — run: email_intake.py auth")
    saved = json.loads(TOKEN_PATH.read_text())
    tok = _http("https://oauth2.googleapis.com/token",
                data=urllib.parse.urlencode({
                    "refresh_token": saved["refresh_token"],
                    "client_id": os.environ["GOOGLE_OAUTH_CLIENT_ID"],
                    "client_secret": os.environ["GOOGLE_OAUTH_CLIENT_SECRET"],
                    "grant_type": "refresh_token"}).encode(),
                headers={"Content-Type": "application/x-www-form-urlencoded"})
    return tok["access_token"]


def _g(tok: str, path: str, **kw) -> dict:
    return _http(f"{GMAIL}{path}", headers={"Authorization": f"Bearer {tok}"}, **kw)


def _g_post(tok: str, path: str, body: dict) -> dict:
    return _http(f"{GMAIL}{path}", data=json.dumps(body).encode(),
                 headers={"Authorization": f"Bearer {tok}",
                          "Content-Type": "application/json"})


# ------------------------------------------------------------------ poll
def ensure_label(tok: str) -> str:
    labels = _g(tok, "/labels").get("labels", [])
    for l in labels:
        if l["name"] == PROCESSED_LABEL:
            return l["id"]
    made = _g_post(tok, "/labels", {"name": PROCESSED_LABEL,
                                    "labelListVisibility": "labelShow",
                                    "messageListVisibility": "show"})
    return made["id"]


def _walk_parts(part: dict, out: dict) -> None:
    mime = part.get("mimeType", "")
    body = part.get("body", {})
    if mime == "text/plain" and body.get("data"):
        out.setdefault("text", []).append(
            base64.urlsafe_b64decode(body["data"]).decode(errors="replace"))
    if part.get("filename") and (body.get("attachmentId") or body.get("data")):
        out.setdefault("attachments", []).append(
            {"filename": part["filename"], "attachmentId": body.get("attachmentId"),
             "mimeType": mime})
    for p in part.get("parts", []) or []:
        _walk_parts(p, out)


def sender_to_company(sender_email: str, companies: dict) -> tuple[str, dict] | None:
    s = sender_email.lower().strip()
    if s in CANARY_SENDERS:
        cid = CANARY_SENDERS[s]
        return cid, companies.get(cid, {"id": cid, "name": "Test company (canary)"})
    for cid, co in companies.items():
        contacts = ((co.get("integration_settings") or {}).get("contacts")) or []
        for c in contacts:
            if (c.get("email") or "").lower().strip() == s:
                return cid, co
    return None


def cmd_poll(args) -> int:
    dry_run = not args.send
    tok = access_token()
    label_id = ensure_label(tok)
    q = f"to:{INTAKE_ALIAS} -label:{PROCESSED_LABEL}"
    msgs = _g(tok, f"/messages?q={urllib.parse.quote(q)}&maxResults=20").get(
        "messages", []) or []
    print(f"email intake poll: {len(msgs)} unprocessed message(s)"
          f"{' [DRY RUN]' if dry_run else ''}")
    if not msgs:
        return 0

    companies = fetch_companies()
    for stub in msgs:
        m = _g(tok, f"/messages/{stub['id']}?format=full")
        headers = {h["name"].lower(): h["value"]
                   for h in m.get("payload", {}).get("headers", [])}
        sender = re.search(r"[\w.+-]+@[\w.-]+", headers.get("from", ""))
        sender = sender.group(0) if sender else "?"
        subject = headers.get("subject", "(no subject)")
        parsed: dict = {}
        _walk_parts(m.get("payload", {}), parsed)
        body_text = "\n".join(parsed.get("text", []))[:4000].strip()
        print(f"\n--- {subject!r} from {sender}")

        match = sender_to_company(sender, companies)
        if not match:
            reason = (f"email to {INTAKE_ALIAS} from unrecognized sender "
                      f"{sender} ({subject!r}) — needs a human to identify "
                      "the client")
            append_escalation({"id": "?", "name": sender}, None, reason, dry_run)
            if not dry_run:
                _g_post(tok, f"/messages/{stub['id']}/modify",
                        {"addLabelIds": [label_id]})
            continue
        company_id, company = match
        print(f"    matched -> {company.get('name')} ({company_id})")

        # attachments: save locally so a human (or the site pipeline) can use
        # them; the classifier is told they exist.
        saved = []
        for a in parsed.get("attachments", []):
            if not a.get("attachmentId"):
                continue
            blob = _g(tok, f"/messages/{stub['id']}/attachments/{a['attachmentId']}")
            dest = ATTACH_DIR / company_id / stub["id"]
            if not dry_run:
                dest.mkdir(parents=True, exist_ok=True)
                (dest / a["filename"]).write_bytes(
                    base64.urlsafe_b64decode(blob["data"]))
            saved.append(a["filename"])
            print(f"    attachment: {a['filename']}"
                  + ("" if dry_run else f" -> {dest}"))

        items = gather_items(company_id)
        if not items and not saved:
            print("    no open items and no attachments — labeling only")
        else:
            intel = load_meeting_intel(company) or ""
            user = (f"Client: {company.get('name')}\nChannel: email\n"
                    f"Subject: {subject}\n"
                    + (f"Attachments included: {', '.join(saved)}\n" if saved else "")
                    + ("\nMeeting intel:\n" + intel + "\n" if intel else "")
                    + "\nOpen items:\n"
                    + "\n".join(f"- id={i['id']} [{i.get('kind', 'intake')}] "
                                f"{i.get('question') or i.get('title')}"
                                for i in items)
                    + f"\n\nClient email body:\n{body_text}")
            result = anthropic_json(CLASSIFY_SYSTEM, user)
            for hit in result.get("matches", []) or []:
                print(f"    ANSWER item {hit['item_id'][:8]} = {hit['value']!r}")
                apply_answer(hit["item_id"], hit["value"], dry_run)
            if result.get("escalate"):
                append_escalation(company,
                                  {"channel": "email", "id": stub["id"],
                                   "body": f"{subject}: {body_text[:300]}"},
                                  result.get("escalate_reason") or "ambiguous email",
                                  dry_run)
            if saved and not (result.get("matches") or []):
                append_escalation(company, None,
                                  f"email attachments saved ({', '.join(saved)}) "
                                  "— need a human to file them (logo/photos/docs)",
                                  dry_run)

        if not dry_run:
            _g_post(tok, f"/messages/{stub['id']}/modify",
                    {"addLabelIds": [label_id]})

    flush_ops_pings(dry_run)
    return 0


# ------------------------------------------------------------------ cron
PLIST = Path.home() / "Library/LaunchAgents/io.restorationai.email-intake.plist"


def cmd_install_cron(_args) -> int:
    script = Path(__file__).resolve()
    PLIST.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>io.restorationai.email-intake</string>
  <key>ProgramArguments</key><array>
    <string>/usr/bin/python3</string>
    <string>{script}</string>
    <string>poll</string>
    <string>--send</string>
  </array>
  <key>StartInterval</key><integer>300</integer>
  <key>StandardOutPath</key><string>/tmp/email-intake.log</string>
  <key>StandardErrorPath</key><string>/tmp/email-intake.log</string>
</dict></plist>
""")
    os.system(f"launchctl unload {PLIST} 2>/dev/null; launchctl load {PLIST}")
    print(f"launchd job installed ({PLIST}) — polls every 5 min, logs to "
          "/tmp/email-intake.log")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("auth", help="one-time OAuth consent")
    pp = sub.add_parser("poll", help="process new setup@ mail")
    pp.add_argument("--send", action="store_true",
                    help="really record/label/ping (default: dry run)")
    sub.add_parser("install-cron", help="launchd every 5 min")
    args = ap.parse_args()
    load_env()
    return {"auth": cmd_auth, "poll": cmd_poll,
            "install-cron": cmd_install_cron}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
