#!/usr/bin/env python3
"""Email intake — the email half of the Concierge (contact@ + setup@).

v2 (Santino 2026-09-05, "just like Monica does via SMS"): polls the WHOLE
contact@restorationai.io inbox, not just setup@-addressed mail. Any message
whose sender matches a known client contact is processed: attachments are
CLASSIFIED (coi / license / ein_doc / logo / photos / customer_list / other)
and FILED into the client's branding/{cid}/docs bucket (the same shelf every
other pipeline reads — the toll-free EIN scanner, site builds, LSA prep),
with duplicate detection so a re-sent file becomes "already on file" instead
of a second copy. Then Monica REPLIES in-thread from contact@ — short, plain,
no em dashes, never promising a call — unless a human already answered the
thread. Unknown senders to setup@ still escalate; unknown senders to
contact@ (vendor mail, newsletters) are labeled and skipped silently.

Processed messages get the Gmail label `concierge-processed` — that label IS
the cursor, so re-runs never double-process and nothing depends on local
state. The broad sweep only looks 3 days back, so history never backfills.

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

    port = 5173  # /connect/google/callback on this port is a
    # registered redirect URI of the shared OAuth client (the app dev origin)
    redirect = f"http://localhost:{port}/connect/google/callback"
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
    env_tok = os.environ.get("GMAIL_TOKEN_JSON", "").strip()
    if env_tok:
        saved = json.loads(env_tok)
    elif TOKEN_PATH.exists():
        saved = json.loads(TOKEN_PATH.read_text())
    else:
        sys.exit(f"No GMAIL_TOKEN_JSON env and no token at {TOKEN_PATH} — "
                 "run: email_intake.py auth")
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


def _storage_put(path: str, data: bytes, mime: str,
                 bucket: str = "email-intake") -> None:
    """Upload to a private Supabase Storage bucket (survives ephemeral worker
    containers; humans grab files from the Supabase dashboard)."""
    import requests as _req
    base = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    r = _req.post(f"{base}/storage/v1/object/{bucket}/{path}",
                  data=data, timeout=60,
                  headers={"Authorization": f"Bearer {key}",
                           "Content-Type": mime, "x-upsert": "true"})
    if r.status_code >= 400:
        raise RuntimeError(f"storage upload {path}: {r.status_code} {r.text[:200]}")


def _storage_names(prefix: str, bucket: str = "branding") -> set[str]:
    """Existing object names under a prefix — the duplicate check."""
    import requests as _req
    base = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    try:
        r = _req.post(f"{base}/storage/v1/object/list/{bucket}",
                      json={"prefix": prefix, "limit": 200}, timeout=30,
                      headers={"Authorization": f"Bearer {key}"})
        return {o.get("name", "") for o in (r.json() or [])} if r.ok else set()
    except Exception:  # noqa: BLE001 — dup check must never block filing
        return set()


DOC_KINDS = {"coi", "license", "ein_doc", "brand_guide", "customer_list", "other_doc"}

CLASSIFY_DOC_SYSTEM = """You classify a business email attachment for a
marketing agency's filing system. Given the filename, email subject and body,
answer as JSON: {"kind": one of coi|license|ein_doc|logo|photos|customer_list|
brand_guide|other_doc, "summary": "<8 words max>"}. coi = certificate of
insurance. ein_doc = IRS letter / W-9 / anything showing the federal EIN.
customer_list = spreadsheet/CSV of customers or contacts. Reply with JSON
only."""

REPLY_SYSTEM = """You are Monica, the operations coordinator at Restoration
AI, replying by EMAIL to a client of the agency. Write a short plain-text
reply (2-5 sentences). Rules, all hard:
- Never use an em dash anywhere.
- Address the client by the first name given.
- If files were filed, confirm receipt naturally and say what happens next
  ONLY if the context states a next step. Never invent status or promises.
- If they re-sent a file we already have, thank them and confirm it is
  already on file; that IS worth a short reply.
- Never say Santino will call them. If something needs Santino, say you will
  pass it along to him.
- Never claim a site/campaign launched unless the context says so.
- If the email asks a question the context does not answer, acknowledge it
  and say you are checking rather than guessing.
- Sign off as:\nMonica\nRestoration AI
Reply as JSON only: {"reply": "<the email body>"} or {"reply": null} if no
reply is appropriate (pure FYI mail needing nothing)."""


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


def _file_attachments(tok: str, msg_id: str, parsed: dict, company_id: str,
                      subject: str, body_text: str, dry_run: bool):
    """Classify + file one message's attachments; returns (saved, filed_notes).
    Shared by the live poll and the lookback sweep."""
    saved, filed_notes = [], []
    atts = [a for a in parsed.get("attachments", []) if a.get("attachmentId")]
    existing = _storage_names(f"{company_id}/docs") if atts else set()
    for a in atts:
        blob = _g(tok, f"/messages/{msg_id}/attachments/{a['attachmentId']}")
        data = base64.urlsafe_b64decode(blob["data"])
        fname = a["filename"]
        low = fname.lower()
        if (low in ("image.png", "image001.png", "image002.png")
                or low.startswith("outlook-") or low.endswith(".ics")):
            continue  # signature imagery / calendar invites, never documents
        try:
            klass = anthropic_json(
                CLASSIFY_DOC_SYSTEM,
                f"Filename: {fname}\nSubject: {subject}\n"
                f"Body excerpt:\n{body_text[:800]}")
        except Exception:  # noqa: BLE001
            klass = {}
        kind = (klass.get("kind") or "other_doc").strip()
        if fname in existing:
            filed_notes.append(f"{fname} (already on file — no action)")
            print(f"    attachment: {fname} [{kind}] DUPLICATE — already "
                  "in branding docs")
            saved.append(fname)
            continue
        if not dry_run:
            if kind in DOC_KINDS:
                _storage_put(f"{company_id}/docs/{fname}", data,
                             a.get("mimeType") or "application/octet-stream",
                             bucket="branding")
            # everything (docs included) also lands in the raw email-intake
            # bucket as the untouched original
            _storage_put(f"{company_id}/{msg_id}/{fname}", data,
                         a.get("mimeType") or "application/octet-stream")
        saved.append(fname)
        filed_notes.append(f"{fname} ({kind.replace('_', ' ')})")
        print(f"    attachment: {fname} [{kind}]"
              + ("" if dry_run else
                 (f" -> branding/{company_id}/docs/" if kind in DOC_KINDS
                  else f" -> email-intake/{company_id}/{msg_id}/")))
    return saved, filed_notes


_CLAIM_RE = re.compile(
    r"\b(sent|emailed|e-mailed|forwarded|attached|shared)\b[^.!?]{0,60}"
    r"\b(email|over|already|before|last week|last month|earlier|to you)\b"
    r"|\balready (sent|emailed|shared|provided)\b", re.I)

CLAIM_SYSTEM = """A client of a marketing agency wrote the message below. Does
it claim they ALREADY sent the agency something by email in the PAST (not a
promise to send later, and not this same message's own attachments)? Reply as
JSON only: {"claim": true|false, "keywords": ["<1-3 search words for what
they sent, e.g. COI, insurance, license, customer list>"]}"""


def email_lookback(company_id: str, company: dict, keywords: list[str],
                   dry_run: bool) -> list[str]:
    """Search the mailbox HISTORY (180 days) for mail from this client's known
    addresses, run every hit through the same filing + EIN capture as live
    mail, and return human-readable notes of what was found. The 'I already
    sent it' reflex (Fran Carlo 2026-08-28: EIN + licenses sat 8 days in a
    thread while the pipeline prepared to re-ask)."""
    tok = access_token()
    addrs = [(c.get("email") or "").strip() for c in
             ((company.get("integration_settings") or {}).get("contacts")) or []]
    addrs = [a for a in addrs if a]
    if not addrs:
        return []
    frm = "{" + " ".join(f"from:{a}" for a in addrs) + "}"
    kw = " ".join(keywords[:3])
    found_notes: list[str] = []
    seen: set[str] = set()
    for q in ([f"{frm} newer_than:180d {kw}"] if kw else []) +              [f"{frm} newer_than:180d has:attachment"]:
        stubs = _g(tok, f"/messages?q={urllib.parse.quote(q)}&maxResults=5"
                   ).get("messages", []) or []
        for stub in stubs:
            if stub["id"] in seen:
                continue
            seen.add(stub["id"])
            m = _g(tok, f"/messages/{stub['id']}?format=full")
            hdrs = {h["name"].lower(): h["value"]
                    for h in m.get("payload", {}).get("headers", [])}
            subj = hdrs.get("subject", "(no subject)")
            parsed: dict = {}
            _walk_parts(m.get("payload", {}), parsed)
            body = "\n".join(parsed.get("text", []))[:4000]
            print(f"    lookback hit: {subj!r} ({hdrs.get('date', '')[:16]})")
            saved, notes = _file_attachments(tok, stub["id"], parsed,
                                             company_id, subj, body, dry_run)
            try:
                _capture_ein_from_email(company_id, subj, body, dry_run)
            except Exception:  # noqa: BLE001
                pass
            if notes:
                found_notes.append(f"email {subj!r}: {'; '.join(notes)}")
        if found_notes:
            break  # keyword pass found it — skip the broad pass
    return found_notes


def _gmail_vision(tok: str, msg_id: str, parsed: dict) -> list[dict]:
    """Image attachments (screenshots, photos) as vision blocks so the email
    brain SEES them the way SMS Monica does (Santino 2026-09-05). Inline
    Gmail images arrive as cid: attachments, so the parts walk covers both."""
    out: list[dict] = []
    for a in parsed.get("attachments", []):
        if len(out) >= 4:
            break
        if not (a.get("mimeType") or "").startswith("image/"):
            continue
        low = (a.get("filename") or "").lower()
        if low.startswith("outlook-") or low in ("image001.png", "image002.png"):
            continue  # signature imagery
        if not a.get("attachmentId"):
            continue
        try:
            blob = _g(tok, f"/messages/{msg_id}/attachments/{a['attachmentId']}")
            data = base64.urlsafe_b64decode(blob["data"])
            if len(data) < 8000:
                continue  # pixels / logos
            from io import BytesIO
            from PIL import Image
            img = Image.open(BytesIO(data)).convert("RGB")
            w, h = img.size
            if max(w, h) > 1568:
                sc = 1568 / max(w, h)
                img = img.resize((round(w * sc), round(h * sc)))
            buf = BytesIO()
            img.save(buf, "JPEG", quality=80)
            out.append({"media_type": "image/jpeg",
                        "data": base64.b64encode(buf.getvalue()).decode()})
        except Exception:  # noqa: BLE001
            continue
    return out


def _capture_ein_from_email(cid: str, subject: str, body: str,
                            dry_run: bool) -> None:
    """EIN in an email body dual-stores into company_phone_setup + companies
    (Fran Carlo 2026-08-28: EIN 04-3553992 sat unread in a thread while the
    toll-free pipeline was about to ask him for it). Unlike the SMS path this
    does NOT require an EIN-ASK marker — a client emailing their EIN is
    always deliberate. Only fires when nothing is stored yet."""
    import requests as _req
    m = re.search(r"\b(\d{2})-?(\d{7})\b", body)
    if not m:
        return
    context = (subject + " " + body).lower()
    if "ein" not in context and "tax id" not in context and "employer id" not in context:
        return  # a bare 9-digit pattern without EIN wording could be anything
    ein = f"{m.group(1)}-{m.group(2)}"
    base = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    hdr = {"apikey": key, "Authorization": f"Bearer {key}"}
    cur = _req.get(f"{base}/rest/v1/company_phone_setup?id=eq.{cid}"
                   "&select=business_ein", headers=hdr, timeout=20).json()
    if cur and cur[0].get("business_ein"):
        return  # already on file — never overwrite
    print(f"    EIN captured from email body: {ein}"
          + (" [dry-run]" if dry_run else " -> dual-stored"))
    if dry_run:
        return
    _req.patch(f"{base}/rest/v1/company_phone_setup?id=eq.{cid}",
               json={"business_ein": ein}, timeout=20,
               headers={**hdr, "Prefer": "return=minimal"})
    _req.patch(f"{base}/rest/v1/companies?id=eq.{cid}&ein=is.null",
               json={"ein": ein}, timeout=20,
               headers={**hdr, "Prefer": "return=minimal"})


def cmd_poll(args) -> int:
    dry_run = not args.send
    tok = access_token()
    label_id = ensure_label(tok)
    # Two sweeps: setup@-addressed mail keeps its strict handling (unknown
    # senders escalate), and a broad 3-day inbox sweep catches client mail
    # sent straight to contact@ (Sarha's COI 2026-08-23 arrived mid-thread
    # and sat unprocessed for two weeks). newer_than caps backfill.
    q_setup = f"to:{INTAKE_ALIAS} -label:{PROCESSED_LABEL}"
    q_broad = (f"in:inbox -label:{PROCESSED_LABEL} newer_than:3d "
               "-from:me -category:promotions -category:social")
    setup_ids = {m["id"] for m in _g(
        tok, f"/messages?q={urllib.parse.quote(q_setup)}&maxResults=20"
    ).get("messages", []) or []}
    broad_ids = [m["id"] for m in _g(
        tok, f"/messages?q={urllib.parse.quote(q_broad)}&maxResults=40"
    ).get("messages", []) or []]
    msgs = [{"id": i} for i in list(setup_ids) +
            [b for b in broad_ids if b not in setup_ids]]
    print(f"email intake poll: {len(msgs)} unprocessed message(s) "
          f"({len(setup_ids)} setup@, {len(msgs) - len(setup_ids)} broad)"
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
        result: dict = {}

        match = sender_to_company(sender, companies)
        if not match:
            if stub["id"] in setup_ids:
                reason = (f"email to {INTAKE_ALIAS} from unrecognized sender "
                          f"{sender} ({subject!r}) — needs a human to identify "
                          "the client")
                append_escalation({"id": "?", "name": sender}, None, reason,
                                  dry_run, ping=True)
                if not dry_run:
                    _g_post(tok, f"/messages/{stub['id']}/modify",
                            {"addLabelIds": [label_id]})
            else:
                # contact@ gets vendor mail, receipts, newsletters — not
                # client traffic. Skip WITHOUT labeling: tomorrow's contact
                # sync may make this sender known while it is still in the
                # 3-day window.
                print("    (not a known client contact — skipped)")
            continue
        company_id, company = match
        print(f"    matched -> {company.get('name')} ({company_id})")
        try:
            _capture_ein_from_email(company_id, subject, body_text, dry_run)
        except Exception as e:  # noqa: BLE001
            print(f"    (ein capture errored: {str(e)[:80]})")

        # "I already sent it" -> search the mailbox history and file what we
        # find, so the reply can say "found it" instead of re-asking.
        lookback_notes: list[str] = []
        if _CLAIM_RE.search(body_text or ""):
            try:
                verdict = anthropic_json(CLAIM_SYSTEM, body_text[:1200])
            except Exception:  # noqa: BLE001
                verdict = {}
            if verdict.get("claim"):
                print("    claim detected: they say they already emailed it — "
                      "searching history")
                lookback_notes = email_lookback(
                    company_id, company, verdict.get("keywords") or [], dry_run)

        # attachments: classify and file into branding/{cid}/docs — the shelf
        # the EIN scanner, site builds and LSA prep already read. Duplicates
        # (same filename already on the shelf) are recognized, not re-filed.
        saved, filed_notes = _file_attachments(
            tok, stub["id"], parsed, company_id, subject, body_text, dry_run)
        vision = _gmail_vision(tok, stub["id"], parsed)
        if vision:
            print(f"    [vision] {len(vision)} image(s) will ride the analysis")

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
            result = anthropic_json(CLASSIFY_SYSTEM, user, images=vision or None)
            for hit in result.get("matches", []) or []:
                print(f"    ANSWER item {hit['item_id'][:8]} = {hit['value']!r}")
                apply_answer(hit["item_id"], hit["value"], dry_run)
            if result.get("escalate"):
                # Notification policy 2026-08-02: text Santino only when the
                # email is angry or only he can answer it; routine ambiguous
                # email reaches him via the morning digest.
                append_escalation(company,
                                  {"channel": "email", "id": stub["id"],
                                   "body": f"{subject}: {body_text[:300]}"},
                                  result.get("escalate_reason") or "ambiguous email",
                                  dry_run,
                                  ping=(bool(result.get("needs_santino"))
                                        or result.get("sentiment") == "negative"))
            if saved and not (result.get("matches") or []):
                # v2: docs are auto-filed now, so this is a digest FYI, not a
                # ping — Santino only gets pinged for photos/logos needing
                # placement judgment.
                needs_hand = any("logo" in n or "photos" in n for n in filed_notes)
                append_escalation(company, None,
                                  f"email attachments auto-filed: "
                                  f"{', '.join(filed_notes)}",
                                  dry_run, ping=needs_hand)

        # ---- Monica replies in-thread (2026-09-05) --------------------------
        # Guards, in order: a human (or Monica) already answered after this
        # message -> silent; classifier flagged Santino-only -> silent (the
        # escalation carries it); otherwise draft a short reply and send it
        # from contact@ on the same thread.
        if not result.get("needs_santino"):
            thread = _g(tok, f"/threads/{m['threadId']}?format=metadata")
            answered = False
            for tm in thread.get("messages", []) or []:
                if (int(tm.get("internalDate", 0)) > int(m.get("internalDate", 0))
                        and "SENT" in (tm.get("labelIds") or [])):
                    answered = True
            if answered:
                print("    reply: thread already answered — staying quiet")
            else:
                # First name: the matching contact, else the owner/primary
                # contact, else a neutral greeting. NEVER the company name —
                # the 2026-09-05 shakedown emailed Sarha as "Hi Air," off
                # "Air Care Restoration".
                first = "there"
                contacts = ((company.get("integration_settings") or {})
                            .get("contacts")) or []
                for c in contacts:
                    if (c.get("email") or "").lower() == sender.lower() and c.get("name"):
                        first = c["name"].split()[0]
                        break
                else:
                    for c in contacts:
                        if c.get("name") and (c.get("primary") or
                                              "owner" in str(c.get("role", "")).lower()):
                            first = c["name"].split()[0]
                            break
                ctx = (f"Client first name: {first}\n"
                       f"Their email subject: {subject}\n"
                       f"Their email body:\n{body_text[:1500]}\n"
                       + (f"\nWe just filed these attachments: "
                          f"{'; '.join(filed_notes)}\n" if filed_notes else "")
                       + (f"\nThey said they had emailed something before; we "
                          f"searched and found + filed: "
                          f"{' | '.join(lookback_notes)}\n" if lookback_notes
                          else "")
                       + (f"\nAnswers we recorded from this email: "
                          + "; ".join(str(h.get("value"))[:60] for h in
                                      (result.get("matches") or []))
                          if result.get("matches") else ""))
                try:
                    draft = anthropic_json(REPLY_SYSTEM, ctx, images=vision or None)
                except Exception as e:  # noqa: BLE001
                    draft = {}
                    print(f"    reply: draft failed ({str(e)[:80]})")
                body_reply = (draft or {}).get("reply")
                if body_reply:
                    body_reply = body_reply.replace("\u2014", "-").replace("—", "-")
                    print(f"    reply -> {sender}:\n      "
                          + body_reply.replace("\n", "\n      "))
                    if not dry_run:
                        import email.mime.text as _emt
                        mime = _emt.MIMEText(body_reply)
                        mime["To"] = sender
                        mime["From"] = "contact@restorationai.io"
                        mime["Subject"] = (subject if subject.lower().startswith("re:")
                                           else f"Re: {subject}")
                        if headers.get("message-id"):
                            mime["In-Reply-To"] = headers["message-id"]
                            mime["References"] = headers["message-id"]
                        raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
                        _g_post(tok, "/messages/send",
                                {"raw": raw, "threadId": m["threadId"]})
                        try:
                            _sb_log_reply(company_id, sender, subject, body_reply)
                        except Exception:  # noqa: BLE001
                            pass
                else:
                    print("    reply: nothing to say (FYI mail)")

        if not dry_run:
            _g_post(tok, f"/messages/{stub['id']}/modify",
                    {"addLabelIds": [label_id]})

    flush_ops_pings(dry_run)
    return 0


def _sb_log_reply(cid: str, to: str, subject: str, body: str) -> None:
    """Activity-feed line so every auto-reply is visible in the app."""
    import requests as _req
    base = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    _req.post(f"{base}/rest/v1/marketing_work_log", timeout=20,
              headers={"apikey": key, "Authorization": f"Bearer {key}",
                       "Prefer": "return=minimal"},
              json={"company_id": cid, "actor": "monica",
                    "category": "concierge", "action": "email-reply",
                    "detail": f"Replied by email to {to} re {subject!r}.",
                    "evidence": {"body": body[:500]}})


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
    lb = sub.add_parser("lookback", help="search mailbox history for a client's past mail and file it")
    lb.add_argument("--company-id", required=True)
    lb.add_argument("--keywords", default="", help="space-separated search hints (COI, license...)")
    lb.add_argument("--send", action="store_true")
    args = ap.parse_args()
    load_env()
    if args.cmd == "lookback":
        cos = fetch_companies()
        co = cos.get(args.company_id) or {"id": args.company_id}
        notes = email_lookback(args.company_id, co,
                               args.keywords.split(), not args.send)
        print("\n".join(notes) if notes else "(nothing found)")
        return 0
    return {"auth": cmd_auth, "poll": cmd_poll,
            "install-cron": cmd_install_cron}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
