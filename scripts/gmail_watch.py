#!/usr/bin/env python3
"""gmail_watch.py — client emails to contact@restorationai.io can never rot
unseen again (Santino 2026-09-01, the Fran Carlo case: 5 unread emails over
3 weeks, 4 asking about the same request, because Monica's loop reads GHL
conversations and never the Gmail inbox).

What it does, each run:
  1. Pull recent inbox messages (last LOOKBACK_DAYS) via the Gmail API.
  2. Match senders against KNOWN CLIENT identities: company email domains and
     every contact email in companies.integration_settings.contacts.
  3. For each matched INBOUND message that (a) we have not already noted and
     (b) has no outbound reply from us in the same thread SINCE it arrived,
     file ONE marketing_ops_notes row:
        [CLIENT-EMAIL] {Name} ({company}) emailed {age}h ago: "{subject}"
        — no reply from us yet. Snippet: ...
     The note is idempotent per message id (ops_kv gmail-seen ledger), shows
     in Ops Attention, and rides the existing notes→Monica bridge so the
     concierge loop finally sees email-first clients.

One-time setup (needs Santino's click):
    python3 scripts/gmail_watch.py --auth-url     # print consent URL
    python3 scripts/gmail_watch.py --auth CODE    # exchange code, save token
Token lands in ~/.rankai/gmail-token.json (gmail.readonly only — this
watcher can never send or delete mail).

Run:
    python3 scripts/gmail_watch.py                # one pass (cron: ops-sync)
    python3 scripts/gmail_watch.py --dry-run      # report, write nothing
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.parse
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:  # noqa: BLE001
    pass

SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
HDR = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"}
TOKEN_PATH = Path(os.environ.get("GMAIL_TOKEN_PATH",
                                 Path.home() / ".rankai" / "gmail-token.json"))
SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
LOOKBACK_DAYS = 4
# generic mailbox domains never identify a client by domain alone
_FREEMAIL = {"gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "aol.com",
             "icloud.com", "me.com", "msn.com", "live.com", "comcast.net"}


def _oauth_client() -> dict:
    cid = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
    secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
    if cid and secret:
        return {"client_id": cid, "client_secret": secret}
    from gsc_setup import OAUTH_CLIENT_PATH  # same installed-app client as GSC
    cfg = json.load(open(OAUTH_CLIENT_PATH))
    cfg = cfg.get("installed") or cfg.get("web") or cfg
    return {"client_id": cfg["client_id"], "client_secret": cfg["client_secret"]}


_REDIRECT = "http://localhost:8765"


def auth_url() -> str:
    # Google retired the urn:ietf:wg:oauth:2.0:oob copy-paste flow (Santino hit
    # its error page 2026-09-01); desktop clients now use a loopback redirect.
    c = _oauth_client()
    return ("https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": c["client_id"],
        "redirect_uri": _REDIRECT,
        "response_type": "code", "scope": SCOPE,
        "access_type": "offline", "prompt": "select_account consent",
        "login_hint": "contact@restorationai.io"}))


def auth_exchange(code: str) -> None:
    c = _oauth_client()
    r = requests.post("https://oauth2.googleapis.com/token", data={
        **c, "code": code.strip(),
        "redirect_uri": _REDIRECT,
        "grant_type": "authorization_code"}, timeout=30)
    r.raise_for_status()
    tok = r.json()
    if "refresh_token" not in tok:
        sys.exit("no refresh_token returned — re-run --auth-url (prompt=consent)")
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(json.dumps({"refresh_token": tok["refresh_token"]}))
    print(f"saved {TOKEN_PATH}")


def auth_local() -> None:
    """One-shot local flow: open the consent URL, catch the redirect on
    localhost:8765, exchange, save. Santino just clicks Allow."""
    import http.server
    import threading
    import webbrowser
    code_box: dict = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            code_box["code"] = (qs.get("code") or [""])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h2>Gmail watcher authorized. You can close this tab.</h2>")

        def log_message(self, *a):  # noqa: D102
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 8765), H)
    threading.Thread(target=srv.handle_request, daemon=True).start()
    url = auth_url()
    print("opening browser for consent:", url)
    webbrowser.open(url)
    import time
    for _ in range(1800):
        if code_box.get("code"):
            break
        time.sleep(1)
    srv.server_close()
    if not code_box.get("code"):
        sys.exit("timed out waiting for consent (5 min)")
    auth_exchange(code_box["code"])


def access_token() -> str:
    env_tok = os.environ.get("GMAIL_AGENCY_TOKEN_JSON", "").strip()
    rt = (json.loads(env_tok)["refresh_token"] if env_tok
          else json.load(open(TOKEN_PATH))["refresh_token"])
    c = _oauth_client()
    r = requests.post("https://oauth2.googleapis.com/token", data={
        **c, "refresh_token": rt, "grant_type": "refresh_token"}, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


# ---------------------------------------------------------------- identities
def client_identities() -> dict:
    """{email_or_domain: (company_id, company_name, contact_name)}"""
    out: dict = {}
    cos = requests.get(
        f"{SB_URL}/rest/v1/companies?select=id,name,email,status,integration_settings",
        headers=HDR, timeout=30).json()
    for co in cos:
        if str(co.get("status") or "").strip().lower() in (
                "inactive", "suspended", "paused", "churned", "archived"):
            continue
        cid, name = co["id"], (co.get("name") or "").strip()
        emails = [(co.get("email") or "", "")]
        for c in (co.get("integration_settings") or {}).get("contacts", []) or []:
            emails.append((c.get("email") or "",
                           f"{c.get('first_name') or ''} {c.get('last_name') or ''}".strip()))
        for em, who in emails:
            em = em.strip().lower()
            if not em or "@" not in em:
                continue
            out[em] = (cid, name, who)
            dom = em.split("@", 1)[1]
            if dom not in _FREEMAIL:
                out.setdefault(dom, (cid, name, ""))
    return out


# ------------------------------------------------------------------- watcher
def _seen() -> set:
    r = requests.get(f"{SB_URL}/rest/v1/ops_kv?k=eq.gmail-watch-seen&select=v",
                     headers=HDR, timeout=30)
    rows = r.json() if r.ok else []
    return set((rows[0]["v"] or {}).get("ids", [])) if rows else set()


def _save_seen(ids: set) -> None:
    requests.post(f"{SB_URL}/rest/v1/ops_kv?on_conflict=k",
                  headers=HDR | {"Prefer": "resolution=merge-duplicates,return=minimal",
                                 "Content-Type": "application/json"},
                  json={"k": "gmail-watch-seen", "v": {"ids": sorted(ids)[-2000:]}},
                  timeout=30)


def _g(path: str, at: str, **params) -> dict:
    r = requests.get(f"https://gmail.googleapis.com/gmail/v1/users/me/{path}",
                     headers={"Authorization": f"Bearer {at}"},
                     params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def run(dry: bool) -> int:
    at = access_token()
    idmap = client_identities()
    seen = _seen()
    q = f"in:inbox newer_than:{LOOKBACK_DAYS}d -from:me"
    msgs = _g("messages", at, q=q, maxResults=100).get("messages", []) or []
    new_notes = 0
    for stub in msgs:
        mid = stub["id"]
        if mid in seen:
            continue
        m = _g(f"messages/{mid}", at, format="metadata",
               metadataHeaders=["From", "Subject", "Date"])
        hdrs = {h["name"].lower(): h["value"]
                for h in m.get("payload", {}).get("headers", [])}
        sender = (re.search(r"<([^>]+)>", hdrs.get("from", ""))
                  or re.search(r"(\S+@\S+)", hdrs.get("from", "")))
        sender = (sender.group(1) if sender else "").strip().lower()
        if not sender:
            seen.add(mid)
            continue
        hit = idmap.get(sender) or idmap.get(sender.split("@", 1)[1] if "@" in sender else "")
        if not hit:
            seen.add(mid)
            continue
        cid, company, who = hit
        # replied since? any message in the thread FROM us newer than this one
        thread = _g(f"threads/{m['threadId']}", at, format="metadata",
                    metadataHeaders=["From"])
        replied = any(
            "restorationai.io" in json.dumps(
                [h["value"] for h in t.get("payload", {}).get("headers", [])
                 if h["name"].lower() == "from"]).lower()
            and int(t.get("internalDate", 0)) > int(m.get("internalDate", 0))
            for t in thread.get("messages", []))
        seen.add(mid)
        if replied:
            continue
        age_h = round((dt.datetime.now(dt.timezone.utc).timestamp()
                       - int(m.get("internalDate", 0)) / 1000) / 3600)
        subject = (hdrs.get("subject") or "(no subject)")[:120]
        snippet = (m.get("snippet") or "")[:200]
        label = who or sender
        body = (f"[CLIENT-EMAIL] {label} ({company}) emailed contact@ {age_h}h ago: "
                f"\"{subject}\" — no reply from us yet. Snippet: {snippet}")
        print(("  would file: " if dry else "  filed: ") + body[:140])
        if not dry:
            requests.post(f"{SB_URL}/rest/v1/marketing_ops_notes",
                          headers=HDR | {"Prefer": "return=minimal",
                                         "Content-Type": "application/json"},
                          json={"company_id": cid, "status": "open", "body": body},
                          timeout=30)
        new_notes += 1
    if not dry:
        _save_seen(seen)
    print(f"gmail-watch: {len(msgs)} inbox msgs scanned, {new_notes} unanswered client email(s) noted")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--auth-url", action="store_true")
    ap.add_argument("--auth", metavar="CODE")
    ap.add_argument("--auth-local", action="store_true",
                    help="open browser, catch redirect on localhost:8765, save token")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if args.auth_local:
        auth_local()
        return 0
    if args.auth_url:
        print(auth_url())
        return 0
    if args.auth:
        auth_exchange(args.auth)
        return 0
    sys.path.insert(0, str(ROOT / "scripts"))
    return run(args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
