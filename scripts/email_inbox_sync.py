#!/usr/bin/env python3
"""Inbound client email -> Monica's notes. The email-blindness fix.

WHY (2026-08-09): three clients got burned by an inbox nobody reads
systematically. Fran's website feedback sat for 3 days. Jeff's screenshot
got acknowledged by someone who never opened it. Kenny's customer list got
a "great, we'll take it from here" with no retrieval. The mailbox
(contact@restorationai.io; setup@ is an alias into the same inbox) was only
scanned for setup@ traffic (email_intake.py) and registrar invites
(domain_access_email.py) — a client replying to ANY of our email threads was
invisible to Monica and to the daily digest.

This module closes the gap: every inbox message from a KNOWN CLIENT becomes
one marketing_ops_notes row (the table Monica reads before she messages
anyone), and every attachment is saved to the client's account documents in
Supabase Storage (branding/{company_id}/docs/). Non-client mail — vendors,
spam, Google notifications — is skipped silently.

Matching a sender to a client, strictest first:
  exact    sender email == a known contact email (profiles.email,
           companies.email, integration_settings.contacts[].email)
  domain   sender's domain == the domain those contact emails use
           (anyone@pauldavis.com matches the client whose contacts are
           @pauldavis.com) — free-mail domains (gmail, yahoo, ...) never
           count as a client domain.

READ-ONLY on the mailbox: never marks read, never labels, never replies.
email_intake.py's concierge-processed label workflow is untouched — the two
scanners are independent and idempotent side by side.

State (ops_kv):
  email-inbox-sync-cursor   ISO timestamp; list inbox mail after this
                            (first run: last 14 days)
  email-inbox-sync-seen     processed Gmail message ids, capped at 500

Runs inside client_ops_sync.run() daily (same independent try/except as the
setup ledger). CLI for manual runs:

    python3 scripts/email_inbox_sync.py --dry-run     # print, write nothing
    python3 scripts/email_inbox_sync.py               # live
    python3 scripts/email_inbox_sync.py --days 30     # widen first-run lookback

Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, GOOGLE_OAUTH_CLIENT_ID/SECRET,
GMAIL_TOKEN_JSON (CI) or ~/.config/rankai/gmail_token.json (ops Mac).
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import urllib.parse
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
import email_intake  # noqa: E402 — Gmail auth + API helpers (same mailbox)
from client_concierge import (  # noqa: E402
    DEPARTED_STATUSES, _sb, kv_get, kv_set, load_env,
)

CURSOR_KEY = "email-inbox-sync-cursor"
SEEN_KEY = "email-inbox-sync-seen"
# SECOND MAILBOX (Monica email evolution 2c, 2026-08-20): the sales-era
# contact@getrestorationai.com inbox — where Bobby's unanswered emails sat.
# Scanned with its own token/cursor/seen; skipped quietly when no token is
# minted yet, so the daily sweep never breaks on a missing credential.
GETREST_TOKEN_PATH = (Path.home() / ".config" / "rankai"
                      / "gmail_token_getrestorationai.json")
GETREST_CURSOR_KEY = "email-inbox-sync-cursor-getrest"
GETREST_SEEN_KEY = "email-inbox-sync-seen-getrest"
SEEN_CAP = 500
DEFAULT_LOOKBACK_DAYS = 14
SNIPPET_CHARS = 300
MAX_MESSAGES = 600          # runaway guard; daily volume is ~15 messages,
                            # so this only matters on a wide first backfill

# A free-mail domain shared by half the world identifies nobody. Only a
# company's OWN domain may match "anyone@that-domain".
FREEMAIL = {
    "gmail.com", "googlemail.com", "yahoo.com", "ymail.com", "rocketmail.com",
    "aol.com", "hotmail.com", "outlook.com", "live.com", "msn.com",
    "icloud.com", "me.com", "mac.com", "comcast.net", "att.net",
    "verizon.net", "sbcglobal.net", "bellsouth.net", "cox.net",
    "charter.net", "proton.me", "protonmail.com", "mail.com", "gmx.com",
    "earthlink.net", "hey.com", "zoho.com",
}
# Our own mail must never read as "a client emailed us".
OWN_DOMAINS = {"restorationai.io", "getrestorationai.com"}


# ------------------------------------------------------------ client index
def client_index() -> dict[str, dict]:
    """company_id -> {name, emails, domains} for every non-departed client.

    Emails: profiles.email + companies.email + integration_settings
    .contacts[].email. Domains: the domain part of those emails, minus
    free-mail providers (and never our own domains).
    """
    cos = _sb("GET", "/rest/v1/companies?select=id,name,status,email,"
              "integration_settings") or []
    profs = _sb("GET", "/rest/v1/profiles?select=company_id,email") or []
    by_cid: dict[str, set[str]] = {}
    for p in profs:
        if p.get("email") and p.get("company_id"):
            by_cid.setdefault(p["company_id"], set()).add(
                p["email"].lower().strip())
    index: dict[str, dict] = {}
    for co in cos:
        cid = co.get("id")
        if not cid or (co.get("status") or "").lower() in DEPARTED_STATUSES:
            continue
        emails = set(by_cid.get(cid) or set())
        if co.get("email"):
            emails.add(str(co["email"]).lower().strip())
        ints = co.get("integration_settings") or {}
        if isinstance(ints, str):
            try:
                import json as _json
                ints = _json.loads(ints)
            except Exception:  # noqa: BLE001
                ints = {}
        for c in (ints.get("contacts") or []):
            if isinstance(c, dict) and c.get("email"):
                emails.add(str(c["email"]).lower().strip())
        emails = {e for e in emails if "@" in e}
        domains = {e.split("@")[-1] for e in emails}
        domains -= FREEMAIL | OWN_DOMAINS
        index[cid] = {"name": co.get("name") or cid, "emails": emails,
                      "domains": domains}
    return index


def match_sender(sender: str, index: dict[str, dict],
                 to_field: str = "") -> list[str]:
    """Company ids this sender belongs to. Exact email beats domain; a
    domain shared by sister companies matches each (same-owner accounts share
    one contacts array — that is not real ambiguity)."""
    s = (sender or "").lower().strip()
    # Canary sender -> Test company, but ONLY on mail addressed to the
    # setup@ intake alias (email_intake's scope) — the same address also
    # sends our own GHL onboarding drip, which must never file notes.
    if (s in email_intake.CANARY_SENDERS
            and email_intake.INTAKE_ALIAS in (to_field or "").lower()):
        return [email_intake.CANARY_SENDERS[s]]
    if "@" not in s or s.split("@")[-1] in OWN_DOMAINS:
        return []
    exact = [cid for cid, ident in index.items() if s in ident["emails"]]
    if exact:
        return exact
    dom = s.split("@")[-1]
    return [cid for cid, ident in index.items() if dom in ident["domains"]]


# ------------------------------------------------------------ mail parsing
def _plaintext(payload: dict, parsed: dict) -> str:
    """Readable body text: text/plain parts first, HTML flattened as the
    fallback (some mailers ship HTML-only), quoted reply lines dropped."""
    text = "\n".join(parsed.get("text", []))
    if not text.strip():
        chunks: list[str] = []

        def walk(part: dict) -> None:
            body = part.get("body") or {}
            if "html" in (part.get("mimeType") or "") and body.get("data"):
                raw = base64.urlsafe_b64decode(body["data"]).decode(
                    errors="replace")
                raw = re.sub(r"(?is)<(style|script|head)[^>]*>.*?</\1>", " ", raw)
                chunks.append(re.sub(r"(?s)<[^>]+>", " ", raw))
            for child in part.get("parts") or []:
                walk(child)

        walk(payload)
        text = " ".join(chunks)
        text = re.sub(r"&nbsp;|&zwnj;|&#8203;", " ", text)
        text = text.replace("&amp;", "&").replace("&#39;", "'")
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith(">")]
    return re.sub(r"\s+", " ", " ".join(lines)).strip()


def _upload_doc(company_id: str, filename: str, data: bytes, mime: str) -> str:
    """Save one attachment to the client's account documents
    (branding/{company_id}/docs/ — the bucket the app and site pipeline
    read). x-upsert: re-saving a file a human already filed is harmless."""
    base = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    path = f"{company_id}/docs/{filename}"
    r = requests.post(
        f"{base}/storage/v1/object/branding/{urllib.parse.quote(path)}",
        data=data, timeout=120,
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": mime or "application/octet-stream",
                 "x-upsert": "true"})
    if r.status_code >= 400:
        raise RuntimeError(f"storage upload {path}: {r.status_code} "
                           f"{r.text[:200]}")
    return path


def _safe_filename(name: str) -> str:
    name = os.path.basename((name or "").strip()) or "attachment"
    return re.sub(r"[^\w .()\[\]&+-]+", "_", name)[:150]


# -------------------------------------------------------------------- sync
def _getrest_access_token() -> str | None:
    """Access token for the getrestorationai.com mailbox, or None when its
    refresh token hasn't been minted (gmail_auth_bootstrap.py) — the sweep
    then skips that mailbox without failing. Env GMAIL_TOKEN_JSON_GETREST
    (CI) beats the on-disk file (ops Mac), mirroring email_intake."""
    env_tok = os.environ.get("GMAIL_TOKEN_JSON_GETREST", "").strip()
    if env_tok:
        saved = json.loads(env_tok)
    elif GETREST_TOKEN_PATH.exists():
        saved = json.loads(GETREST_TOKEN_PATH.read_text())
    else:
        return None
    tok = email_intake._http(
        "https://oauth2.googleapis.com/token",
        data=urllib.parse.urlencode({
            "refresh_token": saved["refresh_token"],
            "client_id": os.environ["GOOGLE_OAUTH_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_OAUTH_CLIENT_SECRET"],
            "grant_type": "refresh_token"}).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    return tok.get("access_token")


def sync_inbox(dry_run: bool, cid_to_slug: dict | None = None) -> list[str]:
    """One pass over BOTH our mailboxes: new inbox mail from known clients
    -> one note each (plus attachments into their account documents).
    Returns '{slug}: ...' lines for the sweep log. Read-only on Gmail;
    idempotent via ops_kv."""
    out = _sync_one_mailbox("restorationai.io", email_intake.access_token(),
                            CURSOR_KEY, SEEN_KEY, dry_run, cid_to_slug)
    tok2 = None
    try:
        tok2 = _getrest_access_token()
    except Exception as e:  # noqa: BLE001 — one mailbox must not sink the other
        print(f"  ! getrestorationai token refresh failed: {str(e)[:100]}")
    if tok2:
        out += _sync_one_mailbox("getrestorationai.com", tok2,
                                 GETREST_CURSOR_KEY, GETREST_SEEN_KEY,
                                 dry_run, cid_to_slug)
    else:
        print("  (getrestorationai.com mailbox: no token — skipped; mint "
              "one with scripts/gmail_auth_bootstrap.py)")
    return out


def _sync_one_mailbox(mailbox: str, tok: str, cursor_key: str,
                      seen_key: str, dry_run: bool,
                      cid_to_slug: dict | None = None) -> list[str]:
    cid_to_slug = cid_to_slug or {}
    out: list[str] = []
    run_start = datetime.now(timezone.utc)

    cursor = kv_get(cursor_key)
    seen: list[str] = kv_get(seen_key) or []
    if cursor:
        since = datetime.fromisoformat(str(cursor).replace("Z", "+00:00"))
    else:
        since = run_start - timedelta(days=DEFAULT_LOOKBACK_DAYS)
    q = f"in:inbox after:{int(since.timestamp())}"

    stubs: list[dict] = []
    page = None
    while len(stubs) < MAX_MESSAGES:
        path = f"/messages?q={urllib.parse.quote(q)}&maxResults=100"
        if page:
            path += f"&pageToken={page}"
        listing = email_intake._g(tok, path)
        stubs += listing.get("messages") or []
        page = listing.get("nextPageToken")
        if not page:
            break
    fresh = [s for s in stubs if s["id"] not in set(seen)]
    print(f"email-inbox sync [{mailbox}] since "
          f"{since.strftime('%Y-%m-%d %H:%M')}Z: "
          f"{len(stubs)} inbox message(s), {len(fresh)} unprocessed"
          f"{' [DRY RUN]' if dry_run else ''}")

    index = client_index() if fresh else {}
    processed: list[str] = []
    filed = skipped = 0
    for stub in reversed(fresh):        # oldest first -> notes read in order
        try:
            m = email_intake._g(tok, f"/messages/{stub['id']}?format=full")
        except Exception as e:  # noqa: BLE001 — one bad fetch never ends the run
            print(f"  ! fetch {stub['id']} failed: {str(e)[:100]}")
            continue
        headers = {h["name"].lower(): h["value"]
                   for h in (m.get("payload") or {}).get("headers", [])}
        sender_m = re.search(r"[\w.+-]+@[\w.-]+", headers.get("from", ""))
        sender = sender_m.group(0).lower() if sender_m else "?"
        subject = headers.get("subject") or "(no subject)"
        try:
            when = parsedate_to_datetime(headers.get("date", "")).strftime(
                "%Y-%m-%d")
        except Exception:  # noqa: BLE001
            when = "unknown date"

        cids = match_sender(sender, index,
                            (headers.get("to", "") + " "
                             + headers.get("cc", "")))
        if not cids:
            skipped += 1
            processed.append(stub["id"])
            continue

        parsed: dict = {}
        email_intake._walk_parts(m.get("payload") or {}, parsed)
        snippet = _plaintext(m.get("payload") or {}, parsed)[:SNIPPET_CHARS]
        attachments = [a for a in parsed.get("attachments", [])
                       if a.get("attachmentId")]

        for cid in cids:
            slug = (cid_to_slug.get(cid)
                    or (index.get(cid) or {}).get("name") or cid)
            saved: list[str] = []
            for a in attachments:
                fname = _safe_filename(a.get("filename"))
                if dry_run:
                    saved.append(fname)
                    continue
                try:
                    blob = email_intake._g(
                        tok, f"/messages/{stub['id']}/attachments/"
                             f"{a['attachmentId']}")
                    data = base64.urlsafe_b64decode(blob["data"])
                    _upload_doc(cid, fname, data,
                                a.get("mimeType") or "")
                    saved.append(fname)
                except Exception as e:  # noqa: BLE001
                    print(f"  ! attachment {fname} for {slug}: {str(e)[:100]}")
            if saved:
                att = ", ".join(saved) + " (saved to their account documents)"
            elif attachments:
                att = "present but could not be saved — check the inbox"
            else:
                att = "none"
            note = (f"[CLIENT EMAIL] {sender} emailed {subject!r} on {when} "
                    f"(to our {mailbox} inbox): "
                    f"{snippet or '(no readable body)'} Attachments: {att}.")
            if dry_run:
                print(f"  WOULD file note -> {slug}: {note[:160]}")
            else:
                _sb("POST", "/rest/v1/marketing_ops_notes",
                    body={"company_id": cid, "body": note},
                    prefer="return=minimal")
            filed += 1
            out.append(f"{slug}: inbound email from {sender} "
                       f"({subject[:60]!r}, {when}) -> Monica's notes"
                       + (f", {len(saved)} attachment(s) saved" if saved else ""))
        processed.append(stub["id"])

    if not dry_run:
        seen = (seen + processed)[-SEEN_CAP:]
        kv_set(seen_key, seen)
        # Overlap the next window by an hour; the seen list absorbs the rerun.
        kv_set(cursor_key, (run_start - timedelta(hours=1)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"))
    print(f"email-inbox sync [{mailbox}]: {filed} note(s) filed, "
          f"{skipped} non-client message(s) skipped")
    return out


def main() -> int:
    global DEFAULT_LOOKBACK_DAYS
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true",
                    help="print what would be filed; write nothing")
    ap.add_argument("--days", type=int, default=DEFAULT_LOOKBACK_DAYS,
                    help="first-run lookback when no cursor exists")
    args = ap.parse_args()
    load_env()
    DEFAULT_LOOKBACK_DAYS = args.days
    try:
        from client_ops_sync import slug_map
        cid_to_slug = slug_map()
    except Exception:  # noqa: BLE001 — slugs are cosmetic here
        cid_to_slug = {}
    for ln in sync_inbox(args.dry_run, cid_to_slug):
        print("  " + ln)
    return 0


if __name__ == "__main__":
    sys.exit(main())
