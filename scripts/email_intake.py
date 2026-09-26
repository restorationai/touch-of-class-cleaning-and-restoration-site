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
    CLASSIFY_SYSTEM, _sb, anthropic_json, append_escalation, apply_answer,
    fetch_companies, flush_ops_pings, gather_items, load_env, load_meeting_intel,
)

TOKEN_PATH = Path.home() / ".config" / "rankai" / "gmail_token.json"
GETREST_TOKEN_PATH = (Path.home() / ".config" / "rankai"
                      / "gmail_token_getrestorationai.json")
INTAKE_ALIAS = "setup@restorationai.io"
# Both agency mailboxes get the full intake + Monica-reply treatment
# (2026-09-11: Angie's site-change email to the getrest inbox was ingested
# but never answered because only the .io mailbox was polled). Replies go
# out from whichever address the client wrote to.
ACCOUNTS = {
    "main": {"env": "GMAIL_TOKEN_JSON", "path": TOKEN_PATH,
             "addr": "contact@restorationai.io", "setup_alias": INTAKE_ALIAS},
    "getrest": {"env": "GMAIL_TOKEN_JSON_GETREST", "path": GETREST_TOKEN_PATH,
                "addr": "contact@getrestorationai.com", "setup_alias": None},
}
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


def access_token(account: str = "main") -> str:
    acc = ACCOUNTS[account]
    env_tok = os.environ.get(acc["env"], "").strip()
    if env_tok:
        saved = json.loads(env_tok)
    elif acc["path"].exists():
        saved = json.loads(acc["path"].read_text())
    else:
        raise RuntimeError(f"no {acc['env']} env and no token at {acc['path']}"
                           " — run: email_intake.py auth")
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

# Emailed IMAGES get vision routing (Jaziel/RX 2026-09-24: 8 staff photos
# classified from FILENAME ONLY; 'photos' had no destination so a correct
# classification was a black hole and the error fallback shelved them in
# docs/ where no team-photo consumer looks). Kind -> branding/ prefix.
IMG_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".heic")
IMG_ROUTES = {
    "team_photo": "team",
    "job_photo": "job-photos/inbox",
    "logo": "brand",
    "document_scan": "docs",        # a photographed certificate/form
    "other_image": "job-photos/inbox",  # visible-to-humans default, never docs
}
CLASSIFY_IMG_SYSTEM = """You classify an image a client emailed to their
marketing agency. Look at the image itself. Reply JSON only:
{"kind": one of team_photo|job_photo|logo|document_scan|other_image,
 "summary": "<8 words max>"}.
team_photo = people/headshots/staff/crew portraits or group shots.
job_photo = work sites, damage, equipment, trucks, finished jobs.
logo = a logo or brand graphic. document_scan = a photographed or scanned
document/certificate/form."""


def _classify_email_image(data: bytes, mime: str, fname: str,
                          subject: str) -> str:
    """Vision-classify an emailed image; fail-safe to other_image (which
    routes somewhere a human LOOKS, never the docs shelf)."""
    try:
        import base64 as _b64
        blocks = [{"media_type": mime if mime.startswith("image/")
                   else "image/jpeg",
                   "data": _b64.b64encode(data).decode()}]
        k = anthropic_json(
            CLASSIFY_IMG_SYSTEM,
            f"Filename: {fname}\nEmail subject: {subject}",
            max_tokens=200, images=blocks)
        kind = (k.get("kind") or "").strip()
        return kind if kind in IMG_ROUTES else "other_image"
    except Exception:  # noqa: BLE001
        return "other_image"

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
- SCHEDULING (Rob Showalter 2026-09-14, all hard): you cannot see anyone's
  calendar from this path. If the client proposes call or meeting times or
  asks to schedule anything, NEVER accept, pick, or confirm a time and
  never say a time "works". Say you are passing the times to Santino, who
  will confirm the exact time. Exception: if the thread history shows OUR
  side already confirmed one specific time, re-affirm exactly that time and
  nothing else.
- Read the thread history before replying. If a later message in the
  thread (from either side) already resolved what this email asks, do not
  contradict it or answer again; at most confirm the resolution.
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


_DOC_TEXT_EXTS = (".docx", ".pdf", ".txt")

FEEDBACK_DOC_SYSTEM = """A client of a restoration-marketing agency emailed
this document. Decide whether it contains ACTIONABLE FEEDBACK or
INSTRUCTIONS for the agency (website revisions, copy changes, business-fact
corrections, service changes, requests). Reply as JSON only:
{"is_actionable": bool,
 "groups": [{"title": "<short task title>",
             "detail": "<the client's items for this group, verbatim-ish,
                        compressed>",
             "needs_confirmation": bool}],
 "summary": "<one sentence>"}
Group related items (aim for 2-6 groups, not one per line). Mark
needs_confirmation=true for anything ambiguous, legally sensitive
(licensing, service claims), or touching phone numbers/tracking. A brochure,
contract, COI, invoice, or data file is NOT actionable feedback."""


def _doc_text(fname: str, data: bytes) -> str:
    """Plain text from a docx/pdf/txt attachment; '' when unreadable."""
    low = fname.lower()
    try:
        if low.endswith(".docx"):
            import io
            import zipfile
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                xml = z.read("word/document.xml").decode("utf-8", "ignore")
            xml = re.sub(r"</w:p>", "\n", xml)
            return re.sub(r"<[^>]+>", "", xml).strip()
        if low.endswith(".pdf"):
            import io
            from pypdf import PdfReader
            return "\n".join((pg.extract_text() or "")
                             for pg in PdfReader(io.BytesIO(data)).pages
                             ).strip()
        if low.endswith(".txt"):
            return data.decode("utf-8", "ignore").strip()
    except Exception as e:  # noqa: BLE001
        print(f"    doc-text extract failed for {fname}: {str(e)[:80]}")
    return ""


def _doc_image_count(fname: str, data: bytes) -> int:
    """Embedded images in a docx (word/media/*) or pdf (/Image XObjects).
    Cheap heuristic for the Phase 2.3 screenshot-heavy watcher."""
    low = fname.lower()
    try:
        if low.endswith(".docx"):
            import io
            import zipfile
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                return sum(1 for n in z.namelist()
                           if n.startswith("word/media/"))
        if low.endswith(".pdf"):
            return data.count(b"/Subtype /Image") + data.count(
                b"/Subtype/Image")
    except Exception:  # noqa: BLE001
        pass
    return 0


def _route_doc_feedback(company_id: str, company_name: str, sender: str,
                        fname: str, text: str, dry_run: bool) -> int:
    """Will Clark 2026-09-22: his 14-item website-review .docx was stored
    and acked but its CONTENT never reached the feedback pipeline — a human
    agent had to read it and file the dev tasks by hand. Docs now route
    through the same [TODO-PROPOSED] gate as texted feedback: notes are
    filed, Santino's proposal digest announces them, his Approve click is
    still what makes them [DEV]. Returns the number of groups filed."""
    if len(text) < 200:
        return 0
    try:
        verdict = anthropic_json(
            FEEDBACK_DOC_SYSTEM,
            f"Company: {company_name}\nFrom: {sender}\n"
            f"Filename: {fname}\n\nDocument text:\n{text[:12000]}")
    except Exception as e:  # noqa: BLE001
        print(f"    feedback-doc classify failed: {str(e)[:80]}")
        return 0
    if not verdict.get("is_actionable"):
        return 0
    groups = [g for g in (verdict.get("groups") or [])
              if str(g.get("title") or "").strip()][:8]
    today = datetime.now(timezone.utc).date().isoformat()
    for g in groups:
        confirm = ("CONFIRM WITH CLIENT/SANTINO FIRST: "
                   if g.get("needs_confirmation") else "")
        body = (f"[TODO-PROPOSED] CLIENT FEEDBACK (emailed doc {fname}) "
                f"from {sender} at {company_name}, {today}: "
                f"{confirm}{g['title']} — "
                f"{str(g.get('detail') or '').strip()[:900]}")
        if not dry_run:
            _sb("POST", "/rest/v1/marketing_ops_notes", {
                "company_id": company_id, "author": "monica",
                "status": "open", "body": body},
                prefer="return=minimal")
        print(f"    feedback-doc: filed group — {g['title'][:60]}"
              + (" [needs confirmation]"
                 if g.get("needs_confirmation") else ""))
    return len(groups)


def _file_attachments(tok: str, msg_id: str, parsed: dict, company_id: str,
                      subject: str, body_text: str, dry_run: bool,
                      company_name: str = "", sender: str = ""):
    """Classify + file one message's attachments; returns (saved, filed_notes).
    Shared by the live poll and the lookback sweep."""
    saved, filed_notes = [], []
    atts = [a for a in parsed.get("attachments", []) if a.get("attachmentId")]
    _names_cache: dict[str, set] = {}

    def _existing(dest_prefix: str) -> set:
        if dest_prefix not in _names_cache:
            _names_cache[dest_prefix] = _storage_names(
                f"{company_id}/{dest_prefix}")
        return _names_cache[dest_prefix]
    existing = _existing("docs") if atts else set()
    for a in atts:
        blob = _g(tok, f"/messages/{msg_id}/attachments/{a['attachmentId']}")
        data = base64.urlsafe_b64decode(blob["data"])
        fname = a["filename"]
        # STORAGE-SAFE NAME (narestco 2026-09-25: an em dash in "...Widget
        # — Developer...pdf" made Supabase reject the key as InvalidKey
        # and the RuntimeError killed the WHOLE 40-message poll). Keys are
        # ASCII-slugged; the pretty original stays in the note text.
        import re as _re
        _stem, _dot, _ext = fname.rpartition(".")
        _safe = _re.sub(r"[^A-Za-z0-9._-]+", "-", (_stem or fname)).strip("-.")
        fname = (_safe or "attachment") + ((_dot + _ext) if _dot else "")
        low = fname.lower()
        if (low in ("image.png", "image001.png", "image002.png")
                or low.startswith("outlook-") or low.endswith(".ics")):
            continue  # signature imagery / calendar invites, never documents
        mime = a.get("mimeType") or "application/octet-stream"
        is_image = (mime.startswith("image/") or low.endswith(IMG_EXTS))
        if is_image:
            kind = _classify_email_image(data, mime, fname, subject)
            dest = IMG_ROUTES[kind]
        else:
            try:
                klass = anthropic_json(
                    CLASSIFY_DOC_SYSTEM,
                    f"Filename: {fname}\nSubject: {subject}\n"
                    f"Body excerpt:\n{body_text[:800]}")
            except Exception:  # noqa: BLE001
                klass = {}
            kind = (klass.get("kind") or "other_doc").strip()
            dest = "docs" if kind in DOC_KINDS else None
        if fname in (_existing(dest) if dest else existing):
            filed_notes.append(f"{fname} (already on file — no action)")
            print(f"    attachment: {fname} [{kind}] DUPLICATE — already "
                  f"in branding/{dest or 'docs'}")
            saved.append(fname)
            continue
        if not dry_run:
            if dest:
                _storage_put(f"{company_id}/{dest}/{fname}", data, mime,
                             bucket="branding")
            # everything (docs included) also lands in the raw email-intake
            # bucket as the untouched original
            _storage_put(f"{company_id}/{msg_id}/{fname}", data,
                         a.get("mimeType") or "application/octet-stream")
        saved.append(fname)
        filed_notes.append(f"{fname} ({kind.replace('_', ' ')})")
        # PHASE 1 (Will Clark 2026-09-22): document CONTENT rides the
        # feedback pipeline, not just the filing shelf.
        if fname.lower().endswith(_DOC_TEXT_EXTS):
            _txt = _doc_text(fname, data)
            if _txt:
                _n = _route_doc_feedback(
                    company_id, company_name or company_id,
                    sender or "the client", fname, _txt, dry_run)
                if _n:
                    filed_notes.append(
                        f"{fname}: logged {_n} action group(s) for the "
                        "team from its contents")
            # PHASE 2.3 WATCHER: a screenshot-heavy doc (lots of embedded
            # images, little text) can't be routed by text alone — flag it
            # loudly; this firing is the signal to BUILD image extraction.
            _imgs = _doc_image_count(fname, data)
            if _imgs >= 3 and len(_txt) < 500:
                _note = (f"[PHASE-2.3 TRIGGER] {fname} from "
                         f"{sender or 'client'} carries {_imgs} embedded "
                         f"image(s) with only {len(_txt)} chars of text — "
                         "doc image extraction is NOT built yet, so its "
                         "visual feedback was NOT auto-routed. Review the "
                         "doc by eye AND tell Claude to build Phase 2.3.")
                if not dry_run:
                    _sb("POST", "/rest/v1/marketing_ops_notes", {
                        "company_id": company_id, "author": "monica",
                        "status": "open", "body": _note},
                        prefer="return=minimal")
                print(f"    {_note[:110]}")
        # DBA EMAIL DOOR (2026-09-26): while the rename waits on a DBA,
        # every emailed pdf/image also runs the rename-verify flow.
        try:
            _dv = _dba_email_bridge(company_id, company_name or company_id,
                                    sender or "", fname, data, mime,
                                    dry_run)
            if _dv:
                filed_notes.append(f"{fname}: DBA lane -> {_dv}")
        except Exception as _e:  # noqa: BLE001 — bridge never blocks filing
            print(f"    dba-bridge error: {str(_e)[:90]}")
        print(f"    attachment: {fname} [{kind}]"
              + ("" if dry_run else
                 (f" -> branding/{company_id}/{dest}/" if dest
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
            saved, notes = _file_attachments(
                tok, stub["id"], parsed, company_id, subj, body, dry_run,
                company_name=(company or {}).get("name") or "",
                sender=(hdrs.get("from") or "")[:80])
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
    companies: dict | None = None
    for account in ACCOUNTS:
        try:
            tok = access_token(account)
        except Exception as e:  # noqa: BLE001 — one mailbox down must not block the other
            print(f"({account} mailbox skipped: {str(e)[:120]})")
            continue
        companies = _poll_mailbox(tok, account, dry_run, companies)
    # 3b: send any queued done-notifications for email-origin feedback
    try:
        n = process_email_reply_queue(dry_run)
        if n:
            print(f"[reply-queue] {n} done-notification(s) "
                  + ("would send" if dry_run else "sent"))
    except Exception as e:  # noqa: BLE001 — never blocks the poll
        print(f"[reply-queue] warn: {str(e)[:100]}")
    flush_ops_pings(dry_run)
    return 0


def _poll_mailbox(tok: str, account: str, dry_run: bool,
                  companies: dict | None) -> dict | None:
    label_id = ensure_label(tok)
    # Two sweeps: setup@-addressed mail keeps its strict handling (unknown
    # senders escalate), and a broad 3-day inbox sweep catches client mail
    # sent straight to contact@ (Sarha's COI 2026-08-23 arrived mid-thread
    # and sat unprocessed for two weeks). newer_than caps backfill.
    alias = ACCOUNTS[account]["setup_alias"]
    q_broad = (f"in:inbox -label:{PROCESSED_LABEL} newer_than:3d "
               "-from:me -category:promotions -category:social")
    setup_ids: set = set()
    if alias:
        q_setup = f"to:{alias} -label:{PROCESSED_LABEL}"
        setup_ids = {m["id"] for m in _g(
            tok, f"/messages?q={urllib.parse.quote(q_setup)}&maxResults=20"
        ).get("messages", []) or []}
    broad_ids = [m["id"] for m in _g(
        tok, f"/messages?q={urllib.parse.quote(q_broad)}&maxResults=40"
    ).get("messages", []) or []]
    msgs = [{"id": i} for i in list(setup_ids) +
            [b for b in broad_ids if b not in setup_ids]]
    # Backstop (Fran Carlo 2026-09-02: his reply predated this system's
    # deploy and sat unanswered 3 days): matched client mail that is TOO OLD
    # for an auto-reply but never got processed pings Santino instead of
    # rotting quietly. Labeled after the ping so it fires once.
    q_stale = (f"in:inbox -label:{PROCESSED_LABEL} older_than:2d newer_than:14d "
               "-from:me -category:promotions -category:social")
    stale_ids = [m["id"] for m in _g(
        tok, f"/messages?q={urllib.parse.quote(q_stale)}&maxResults=30"
    ).get("messages", []) or []]
    print(f"email intake poll [{account}]: {len(msgs)} unprocessed message(s) "
          f"({len(setup_ids)} setup@, {len(msgs) - len(setup_ids)} broad)"
          f"{' [DRY RUN]' if dry_run else ''}")
    if not msgs:
        return companies

    companies = companies or fetch_companies()
    for sid in stale_ids:
        try:
            sm = _g(tok, f"/messages/{sid}?format=metadata")
            shdr = {h["name"].lower(): h["value"]
                    for h in sm.get("payload", {}).get("headers", [])}
            ssender = re.search(r"[\w.+-]+@[\w.-]+", shdr.get("from", ""))
            ssender = ssender.group(0) if ssender else "?"
            smatch = sender_to_company(ssender, companies)
            if not smatch:
                continue
            _, sco = smatch
            append_escalation(sco, None,
                              f"STALE CLIENT EMAIL never processed: from {ssender}, "
                              f"subject {shdr.get('subject', '(none)')!r}, "
                              f"date {shdr.get('date', '?')[:22]} — needs a human "
                              "reply (too old for an auto-reply)",
                              dry_run, ping=True)
            if not dry_run:
                _g_post(tok, f"/messages/{sid}/modify", {"addLabelIds": [label_id]})
        except Exception as e:  # noqa: BLE001
            print(f"  (stale sweep error: {str(e)[:80]})")
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
            tok, stub["id"], parsed, company_id, subject, body_text, dry_run,
            company_name=(company or {}).get("name") or "",
            sender=sender)
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
            # EMAILED CHANGE REQUESTS DISPATCH LIKE TEXTS (Angie/All Pro
            # 2026-09-11: her homepage fix list arrived by email and only
            # became a note — the dev-agent routing lived solely in the SMS
            # path). Same router, same auto-vs-propose gates.
            fbs = result.get("client_feedback") or []
            if fbs:
                try:
                    from client_concierge import append_escalation as _esc
                    from feedback_router import route_feedback
                    routed = route_feedback(
                        company, fbs, who=sender,
                        when=datetime.now(timezone.utc).isoformat(),
                        dry_run=dry_run,
                        origin_channel="email",
                        email_ref={"acct": account,
                                   "eth": m.get("threadId") or "",
                                   "eto": sender},
                        escalate=lambda r: _esc(company, None, r, dry_run,
                                                ping=False))
                    if routed:
                        print(f"    [feedback] {len(routed)} emailed change "
                              "request(s) routed to the build lane")
                except Exception as e:  # noqa: BLE001 — never kills the poll
                    print(f"    [feedback] router unavailable ({str(e)[:80]})")
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
                site_facts = ""
                try:
                    import requests as _rq
                    _srow = _rq.get(
                        os.environ["SUPABASE_URL"].rstrip("/")
                        + f"/rest/v1/marketing_sites?company_id=eq.{company_id}"
                        "&select=apex_live,domain,cloudflare_pages_url&limit=1",
                        headers={"apikey": os.environ["SUPABASE_SERVICE_ROLE_KEY"],
                                 "Authorization": "Bearer "
                                 + os.environ["SUPABASE_SERVICE_ROLE_KEY"]},
                        timeout=15).json()
                    if _srow:
                        _sr = _srow[0]
                        if _sr.get("apex_live") and _sr.get("domain"):
                            site_facts = (f"\nSite facts: their new website IS LIVE at "
                                          f"https://{_sr['domain']}/\n")
                        elif _sr.get("cloudflare_pages_url"):
                            _pv = _sr["cloudflare_pages_url"].replace(
                                "https://", "https://staging.")
                            site_facts = ("\nSite facts: the new website is NOT live yet; "
                                          f"the preview link to share is {_pv} ; their "
                                          "current domain still shows their OLD site until "
                                          "launch.\n")
                except Exception:  # noqa: BLE001
                    pass
                # Thread history rides the draft (Rob Showalter 2026-09-14:
                # "9 am pls" was answered blind with "Got it, 9 am works"
                # eleven seconds after our own email in the SAME thread had
                # locked 6:15pm — the composer saw only the newest inbound).
                # Metadata snippets are enough to keep her consistent.
                hist_lines = []
                for tm in sorted(thread.get("messages", []) or [],
                                 key=lambda t: int(t.get("internalDate", 0)))[-6:]:
                    th = {x["name"]: x["value"] for x in
                          (tm.get("payload", {}).get("headers") or [])}
                    who = ("us" if "SENT" in (tm.get("labelIds") or [])
                           else (th.get("From") or "them"))
                    hist_lines.append(f"- {who}: {(tm.get('snippet') or '')[:160]}")
                ctx = (site_facts + f"Client first name: {first}\n"
                       + ("Thread history, oldest first (stay consistent "
                          "with what our side already said):\n"
                          + "\n".join(hist_lines) + "\n\n" if hist_lines else "")
                       + f"Their email subject: {subject}\n"
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
                        mime["From"] = ACCOUNTS[account]["addr"]
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

    return companies


def process_email_reply_queue(dry_run: bool) -> int:
    """3b (2026-09-13): send the done-notifications dev_inbox queued for
    EMAIL-origin feedback — threaded under the client's own conversation,
    from the mailbox they wrote to. Runs on every intake pass; rows are
    deleted only after a successful send."""
    from client_ops_sync import _sb
    rows = _sb("GET", "/rest/v1/ops_kv?k=like.email-reply-queue:*"
               "&select=k,v") or []
    if not rows:
        return 0
    sent = 0
    toks: dict[str, str] = {}
    for row in rows:
        v = row.get("v") or {}
        acct = v.get("acct") if v.get("acct") in ACCOUNTS else "main"
        try:
            tok = toks.setdefault(acct, access_token(acct))
        except Exception as e:  # noqa: BLE001
            print(f"  [reply-queue] token unavailable for {acct} "
                  f"({str(e)[:60]}) — row stays queued")
            continue
        eth = v.get("eth")
        thread = _g(tok, f"/threads/{eth}?format=metadata"
                    "&metadataHeaders=Subject&metadataHeaders=Message-ID")             if eth else {}
        msgs = (thread or {}).get("messages") or []
        hd = {}
        if msgs:
            hd = {h["name"].lower(): h["value"] for h in
                  (msgs[-1].get("payload") or {}).get("headers", [])}
        subject = hd.get("subject") or "Your website update"
        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"
        to_raw = v.get("eto") or ""
        mto = re.search(r"<([^>]+)>", to_raw)
        to_addr = mto.group(1) if mto else to_raw.strip()
        if not to_addr or "@" not in to_addr:
            print(f"  [reply-queue] no recipient on {row['k']} — dropping")
            if not dry_run:
                _sb("DELETE", f"/rest/v1/ops_kv?k=eq.{row['k']}")
            continue
        first = (v.get("who") or "").split("<")[0].strip().split()
        first = (first[0].title() if first and "@" not in first[0]
                 else "there")
        summary = str(v.get("summary") or
                      "the update you asked for is in").strip().rstrip(".")
        summary = summary[0].upper() + summary[1:] if summary else summary
        link_line = (f" You can take a look here: {v['link']}"
                     if v.get("link") else "")
        body = (f"Hi {first},\n\n{summary}.{link_line}\n\n"
                "Take a look when you get a chance and let us know if "
                "anything else needs adjusting.\n")
        body = body.replace("\u2014", ", ").replace("\u2013", "-")
        print(f"  [reply-queue] -> {to_addr} ({acct}): {summary[:70]}")
        if dry_run:
            sent += 1
            continue
        import email.mime.text as _emt
        mime = _emt.MIMEText(body)
        mime["To"] = to_addr
        mime["From"] = ACCOUNTS[acct]["addr"]
        mime["Subject"] = subject
        if hd.get("message-id"):
            mime["In-Reply-To"] = hd["message-id"]
            mime["References"] = hd["message-id"]
        raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
        payload = {"raw": raw}
        if eth:
            payload["threadId"] = eth
        _g_post(tok, "/messages/send", payload)
        try:
            _sb_log_reply(v.get("cid") or "", to_addr, subject, body)
        except Exception:  # noqa: BLE001
            pass
        _sb("DELETE", f"/rest/v1/ops_kv?k=eq.{row['k']}")
        sent += 1
    return sent


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




def _dba_email_bridge(company_id: str, company_name: str, sender: str,
                      fname: str, data: bytes, mime: str,
                      dry_run: bool) -> str | None:
    """EMAIL DOOR for the DBA lane (Santino 2026-09-26, Will Clark case:
    his LARA receipt was correctly filed to docs/ but the rename sat
    silent for 3 days and Monica asked him for photos instead — the
    texted and hub doors reach the verify machinery, contact@ email never
    did). While a company's rename stage is awaiting_dba, every emailed
    pdf/image runs the SAME flow the texted lane uses:
      certificate + exact match -> stage advances (dba_verified)
      receipt / kin paperwork  -> the what-arrived-what's-still-owed
                                  reply (Jim/CRW 09-21 behavior) + a
                                  context note on the conversation
      mismatch                 -> _dba_apply's escalation
    Returns the verdict string or None when not applicable."""
    low = fname.lower()
    is_pdf = mime == "application/pdf" or low.endswith(".pdf")
    if not (is_pdf or mime.startswith("image/") or low.endswith(IMG_EXTS)):
        return None
    try:
        import client_concierge as cc
    except Exception as e:  # noqa: BLE001
        print(f"    dba-bridge: concierge unavailable ({str(e)[:60]})")
        return None
    try:
        pend = cc._rename_state(company_id)
    except Exception:  # noqa: BLE001
        return None
    if not pend or str(pend.get("stage")) != "awaiting_dba":
        return None
    cands = cc._rename_candidates(company_id)
    chosen = cc._dba_chosen_name(pend, cands)
    if not chosen:
        return None
    rows = _sb("GET", f"/rest/v1/companies?id=eq.{company_id}"
               "&select=id,name,state") or []
    company = rows[0] if rows else {"id": company_id, "name": company_name}
    import base64 as _b64
    media = "application/pdf" if is_pdf else mime
    images = [{"media_type": media, "data": _b64.b64encode(data).decode()}]
    doc = cc._dba_extract(company, images)
    if not doc:
        print(f"    dba-bridge: {fname} not readable as DBA paperwork")
        return None
    # Reply rides the client's normal Monica thread; need a real contact.
    contact = None
    try:
        g = cc._ghl("GET", "/contacts/", params={
            "locationId": cc._loc(), "query": sender, "limit": 3}) or {}
        for c in g.get("contacts") or []:
            if c.get("phone"):
                contact = c
                break
    except Exception:  # noqa: BLE001
        pass
    state: dict = {}
    if not doc.get("is_dba_document"):
        kind = str(doc.get("document_kind") or "dba-related paperwork")
        note = (f"{fname}: {kind} arrived by EMAIL from {sender} — "
                "recorded, certificate still owed")
        pend.setdefault("notes", []).append(note)
        cc._rename_save(company_id, pend, dry_run)
        if contact is not None:
            cc._dba_related_reply(company, contact, doc,
                                  "the emailed document", state, dry_run,
                                  pend)
        else:
            print("    dba-bridge: no texting contact found — note filed, "
                  "no auto-reply")
        return "related"
    doc_url = f"{company_id}/docs/{fname}"
    if contact is None:
        print("    dba-bridge: certificate detected but no texting "
              "contact — escalating without auto-reply")
    verdict = cc._dba_apply(company, contact or {}, chosen, doc, doc_url,
                            "an emailed filing", state, dry_run)
    if verdict == "match":
        pend["stage"] = "dba_verified"
        cc._rename_save(company_id, pend, dry_run)
    return verdict


def cmd_dba_check(args) -> int:
    """Manual/catch-up runner: feed an ALREADY-STORED branding doc through
    the DBA email bridge. Dry-run by default (prints Monica's would-be
    reply); --send delivers it."""
    key = f"{args.company}/{args.file.lstrip('/')}"
    import urllib.parse as _up
    _sk = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    url = (os.environ["SUPABASE_URL"].rstrip("/")
           + f"/storage/v1/object/branding/{_up.quote(key)}")
    req = urllib.request.Request(url, headers={
        "apikey": _sk, "Authorization": f"Bearer {_sk}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    mime = "application/pdf" if key.lower().endswith(".pdf") else "image/jpeg"
    fname = key.rsplit("/", 1)[-1]
    v = _dba_email_bridge(args.company, args.company, args.sender or "",
                          fname, data, mime, dry_run=not args.send)
    print(f"dba-check verdict: {v}")
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
    dc = sub.add_parser("dba-check", help="run a stored branding doc through the DBA bridge (dry-run default)")
    dc.add_argument("--company", required=True)
    dc.add_argument("--file", required=True, help="path under branding/{company}/, e.g. docs/x.pdf")
    dc.add_argument("--sender", default="")
    dc.add_argument("--send", action="store_true")
    dc.set_defaults(func=cmd_dba_check)
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
            "dba-check": cmd_dba_check,
            "install-cron": cmd_install_cron}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
