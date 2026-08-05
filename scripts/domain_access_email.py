#!/usr/bin/env python3
"""Registrar delegate-invite verification from the agency inbox.

WHY (Santino 2026-08-05): the Ops Attention button said "Delegate access
confirmed ✓ (invite landed at setup@)" — a claim nobody had checked. Crew
Restoration got clicked and NO such email ever existed, so the ledger went
green, Monica stopped asking Kyle, and the one person who can unblock the
launch was never asked again. A button must not be able to assert a fact
about an inbox we can actually read.

This module reads it. contact@restorationai.io is the real mailbox
(setup@restorationai.io is an alias that delivers there), and
scripts/email_intake.py already holds a server-side Gmail OAuth refresh
token for it — GMAIL_TOKEN_JSON in CI/worker envs, ~/.config/rankai/
gmail_token.json on the ops Mac. We reuse THAT auth (no new credential, no
Claude-side connector dependency), search every registrar invitation ever
sent to the mailbox, and match each one to a client.

What counts as a verified invite:
  sender domain is a known registrar  AND  the subject/body reads like an
  access invitation ("Account Access Invite", "invited you to access",
  "delegate access", ...). Google Business Profile "invited you to manage"
  mail is NOT a registrar invite and never matches (google.com is not in
  the registrar table).

Matching an invite to a client — GoDaddy's invite carries the inviter's
NAME and a customer number but NOT the domain, so name matching is the
primary signal and the domain (when a registrar does include it) is the
strongest:
  domain        the invite body names a domain we hold for that client  1.0
  name_exact    inviter first+last == a known contact/owner name        0.9
  name_email    last name matches + first name matches an email local   0.7
  first_only    only the first name matches — AMBIGUOUS, never auto     0.4
Auto-advance requires >= AUTO_CONFIDENCE and a UNIQUE client at that tier;
anything ambiguous is surfaced for a human instead of guessed.

CLI:
    python3 scripts/domain_access_email.py scan          # every invite + its match
    python3 scripts/domain_access_email.py check --slug crew-restoration-construction
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import urllib.parse
from datetime import timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLIENTS_DIR = ROOT / "clients"
sys.path.insert(0, str(Path(__file__).parent))

AUTO_CONFIDENCE = 0.7

# Sender domain -> registrar label. Only mail FROM these hosts can ever be a
# registrar invite; everything else (Google Business Profile "invited you to
# manage", Google Ads manager invites, ...) is structurally excluded.
REGISTRAR_SENDERS = {
    "godaddy.com": "godaddy", "secureserver.net": "godaddy",
    "namecheap.com": "namecheap",
    "bluehost.com": "bluehost", "hostmonster.com": "bluehost",
    "hostgator.com": "hostgator", "websitewelcome.com": "hostgator",
    "squarespace.com": "squarespace",
    "wix.com": "wix",
    "networksolutions.com": "networksolutions", "register.com": "networksolutions",
    "name.com": "name.com",
    "enom.com": "enom",
    "hover.com": "hover",
    "dreamhost.com": "dreamhost",
    "ionos.com": "ionos", "ionos.de": "ionos", "1and1.com": "ionos",
    "hostinger.com": "hostinger",
    "porkbun.com": "porkbun",
    "domain.com": "domain.com", "web.com": "web.com",
    "moniker.com": "moniker",
    "inmotionhosting.com": "inmotion",
    "cloudflare.com": "cloudflare", "notify.cloudflare.com": "cloudflare",
    "wordpress.com": "wordpress", "automattic.com": "wordpress",
    "shopify.com": "shopify",
}

# Access-invitation language. Deliberately narrow: a registrar's marketing
# blast or "update your nameservers" notice must never read as an invite.
INVITE_RE = re.compile(
    r"account\s+access\s+invite"
    r"|invit(?:e|ed|es|ation)\s+(?:you|to)\s+(?:to\s+)?(?:access|manage)"
    r"|you'?(?:ve|ve)?\s*(?:have\s+)?been\s+invited"
    r"|invitation\s+to\s+(?:access|manage)"
    r"|delegat\w*\s+access"
    r"|grant(?:ed)?\s+(?:you\s+)?access"
    r"|added\s+you\s+(?:as|to)\b"
    r"|you\s+now\s+have\s+access",
    re.I)

# Domains that appear in every registrar email and mean nothing about which
# client the invite belongs to.
_NOISE_DOMAINS = {
    "restorationai.io", "getrestorationai.com", "godaddy.com", "namecheap.com",
    "google.com", "gmail.com", "cloudflare.com", "squarespace.com", "wix.com",
    "bluehost.com", "hostgator.com", "secureserver.net", "example.com",
    "sendgrid.net", "amazonaws.com", "microsoft.com", "apple.com",
}
_DOMAIN_RE = re.compile(r"\b([a-z0-9][a-z0-9-]{1,62}(?:\.[a-z0-9-]{2,})+)\b", re.I)
_TLD_OK = {"com", "net", "org", "co", "us", "io", "biz", "info", "pro", "services"}


# ------------------------------------------------------------------ gmail
def _gmail_token() -> tuple[str | None, str]:
    """(access_token, error). Never raises — a mailbox we cannot read must
    degrade to 'unknown', never to a false verdict."""
    try:
        import email_intake
    except Exception as e:  # noqa: BLE001
        return None, f"email_intake import failed: {str(e)[:120]}"
    have_env = bool(os.environ.get("GMAIL_TOKEN_JSON", "").strip())
    if not have_env and not email_intake.TOKEN_PATH.exists():
        return None, ("no Gmail credential: set the GMAIL_TOKEN_JSON secret "
                      "(server-side) or run scripts/email_intake.py auth")
    if not (os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
            and os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")):
        return None, "GOOGLE_OAUTH_CLIENT_ID/SECRET missing"
    try:
        return email_intake.access_token(), ""
    except SystemExit as e:  # access_token sys.exits when unconfigured
        return None, f"gmail auth unavailable: {str(e)[:120]}"
    except Exception as e:  # noqa: BLE001
        return None, f"gmail auth failed: {str(e)[:120]}"


def _visible_text(payload: dict) -> str:
    """Flatten a Gmail payload to readable text (registrar invites are
    HTML-only — GoDaddy ships no text/plain part at all)."""
    chunks: list[str] = []

    def walk(part: dict) -> None:
        body = part.get("body") or {}
        data = body.get("data")
        if data:
            try:
                raw = base64.urlsafe_b64decode(data).decode(errors="replace")
            except Exception:  # noqa: BLE001
                raw = ""
            if "html" in (part.get("mimeType") or ""):
                raw = re.sub(r"(?is)<(style|script|head)[^>]*>.*?</\1>", " ", raw)
                raw = re.sub(r"(?s)<[^>]+>", " ", raw)
            chunks.append(raw)
        for child in part.get("parts") or []:
            walk(child)

    walk(payload)
    text = " ".join(chunks)
    text = re.sub(r"&nbsp;|&zwnj;|&#8203;|‌|​", " ", text)
    text = text.replace("&amp;", "&").replace("&#39;", "'").replace("&rsquo;", "'")
    return re.sub(r"\s+", " ", text).strip()


def _inviter_name(from_header: str, text: str) -> str:
    """The human who sent the invite. GoDaddy puts them in the From display
    name ('Jack Bispo via GoDaddy'); other registrars put them in the body
    ('Curt Eddy has invited you...')."""
    disp = re.sub(r"<[^>]*>", "", from_header or "").strip().strip('"').strip()
    disp = re.sub(r"\s+via\s+\w[\w .-]*$", "", disp, flags=re.I).strip()
    generic = {"", "godaddy", "namecheap", "support", "no reply", "noreply",
               "donotreply", "do not reply", "customer care", "wix", "bluehost",
               "cloudflare", "team", "notifications"}
    if disp.lower() not in generic and re.search(r"[A-Za-z]{2,}\s+[A-Za-z]{2,}", disp):
        return disp
    m = re.search(r"([A-Z][\w'.-]+(?:\s+[A-Z][\w'.-]+){0,2})\s+(?:has\s+)?"
                  r"invit(?:ed|es)\s+you", text or "")
    if m:
        return m.group(1).strip()
    return disp


def _domains_in(text: str) -> set[str]:
    out: set[str] = set()
    for m in _DOMAIN_RE.finditer(text or ""):
        d = m.group(1).lower().strip(".")
        if d.startswith("www."):
            d = d[4:]
        if d in _NOISE_DOMAINS or d.split(".")[-1] not in _TLD_OK:
            continue
        if len(d.split(".")[0]) < 3:
            continue
        out.add(d)
    return out


def fetch_invites(lookback_days: int = 500, limit: int = 100
                  ) -> tuple[list[dict], bool, str]:
    """(invites, scan_ok, error). scan_ok=False means we could not read the
    mailbox — callers must treat every verdict as UNKNOWN, never as absent."""
    import email_intake
    tok, err = _gmail_token()
    if not tok:
        return [], False, err
    senders = " OR ".join(f"from:{d}" for d in sorted(set(REGISTRAR_SENDERS)))
    q = f"({senders}) newer_than:{lookback_days}d"
    try:
        listing = email_intake._g(
            tok, f"/messages?q={urllib.parse.quote(q)}&maxResults={limit}")
    except Exception as e:  # noqa: BLE001
        return [], False, f"gmail search failed: {str(e)[:150]}"
    invites: list[dict] = []
    for stub in listing.get("messages") or []:
        try:
            msg = email_intake._g(tok, f"/messages/{stub['id']}?format=full")
        except Exception:  # noqa: BLE001
            continue
        headers = {h["name"].lower(): h["value"]
                   for h in (msg.get("payload") or {}).get("headers", [])}
        from_h = headers.get("from", "")
        addr = (re.search(r"[\w.+-]+@[\w.-]+", from_h) or [""])
        addr = addr.group(0).lower() if hasattr(addr, "group") else ""
        host = addr.split("@")[-1]
        registrar = next((lab for dom, lab in REGISTRAR_SENDERS.items()
                          if host == dom or host.endswith("." + dom)), None)
        if not registrar:
            continue
        subject = headers.get("subject", "")
        text = _visible_text(msg.get("payload") or {})
        if not (INVITE_RE.search(subject) or INVITE_RE.search(text[:4000])):
            continue
        try:
            when = parsedate_to_datetime(headers.get("date", "")).astimezone(
                timezone.utc).isoformat()
        except Exception:  # noqa: BLE001
            when = ""
        cust = re.search(r"Customer\s+Number[:\s]+(\d{5,})", text, re.I)
        invites.append({
            "message_id": stub["id"],
            "thread_id": msg.get("threadId"),
            "registrar": registrar,
            "from": from_h,
            "from_email": addr,
            "to": headers.get("to", ""),
            "subject": subject,
            "date": when,
            "inviter": _inviter_name(from_h, text),
            "customer_number": cust.group(1) if cust else None,
            "domains": sorted(_domains_in(text)),
            "gmail_url": f"https://mail.google.com/mail/u/0/#all/{stub['id']}",
        })
    invites.sort(key=lambda i: i.get("date") or "", reverse=True)
    return invites, True, ""


# ------------------------------------------------------- identity matching
def _norm_name(s: str) -> str:
    return re.sub(r"[^a-z ]+", " ", (s or "").lower()).strip()


def _name_tokens(s: str) -> list[str]:
    return [t for t in _norm_name(s).split() if len(t) > 1]


def _client_record(slug: str) -> dict:
    p = CLIENTS_DIR / f"{slug}.json"
    try:
        return json.loads(p.read_text()) if p.exists() else {}
    except (json.JSONDecodeError, OSError):
        return {}


def identity_index(companies: list[dict], cid_to_slug: dict,
                   site_info: dict | None = None) -> dict:
    """cid -> the names/emails/domains that identify that client's people.

    Sources, richest first: integration_settings.contacts (first_name/
    last_name/email — the GHL backfill), companies.management_contacts,
    companies.account_owner_name, transfer_*_name, clients/{slug}.json
    contact, plus every domain we associate with the client.
    """
    site_info = site_info or {}
    index: dict[str, dict] = {}
    for co in companies:
        cid = co.get("id")
        if not cid:
            continue
        names: set[str] = set()
        emails: set[str] = set()
        ints = co.get("integration_settings") or {}
        if isinstance(ints, str):
            try:
                ints = json.loads(ints)
            except json.JSONDecodeError:
                ints = {}
        for c in (ints.get("contacts") or []):
            if not isinstance(c, dict):
                continue
            full = f"{c.get('first_name') or ''} {c.get('last_name') or ''}".strip()
            if full:
                names.add(_norm_name(full))
            if c.get("name"):
                names.add(_norm_name(c["name"]))
            if c.get("email"):
                emails.add(str(c["email"]).lower().strip())
        for c in (co.get("management_contacts") or []):
            if isinstance(c, dict):
                if c.get("name"):
                    names.add(_norm_name(c["name"]))
                if c.get("email"):
                    emails.add(str(c["email"]).lower().strip())
        for key in ("account_owner_name", "transfer_1_name", "transfer_2_name",
                    "transfer_3_name"):
            if co.get(key):
                names.add(_norm_name(co[key]))
        if co.get("email"):
            emails.add(str(co["email"]).lower().strip())
        slug = cid_to_slug.get(cid)
        rec = _client_record(slug) if slug else {}
        contact = rec.get("contact")
        if isinstance(contact, dict):
            if contact.get("name"):
                names.add(_norm_name(contact["name"]))
            if contact.get("email"):
                emails.add(str(contact["email"]).lower().strip())
        elif isinstance(contact, str) and "@" in contact:
            emails.add(contact.lower().strip())
        info = site_info.get(cid) or {}
        if isinstance(info, str):          # legacy: bare domain string
            info = {"domain": info}
        domains: set[str] = set()
        for d in (rec.get("domain"), co.get("website"), info.get("domain")):
            d = re.sub(r"^https?://", "", str(d or "")).strip("/ ").lower()
            if d.startswith("www."):
                d = d[4:]
            if d and "." in d:
                domains.add(d.split("/")[0])
        locals_ = {e.split("@")[0].lower() for e in emails if "@" in e}
        index[cid] = {
            "name": co.get("name") or slug or cid,
            "slug": slug,
            "names": {n for n in names if n},
            "emails": emails,
            "email_locals": locals_,
            # every token appearing in an email local part (jack.bispo, kyle_e)
            "local_tokens": {t for lo in locals_
                             for t in re.split(r"[._-]+", lo) if len(t) > 2},
            "domains": domains,
            # Known/guessed registrar — an invite from a DIFFERENT company
            # cannot be this client's (Jack Bispo owns both All Pro and
            # ProRestoration; his GoDaddy invite can only be the All Pro
            # domain, because prorestorationca.com sits at Moniker).
            "registrar": (info.get("registrar")
                          or info.get("registrar_guess") or ""),
        }
    return index


def match_invite(inv: dict, index: dict) -> list[dict]:
    """Every candidate client for one invite, best confidence first."""
    inviter = _norm_name(inv.get("inviter") or "")
    tokens = _name_tokens(inviter)
    first, last = (tokens[0] if tokens else ""), (tokens[-1] if len(tokens) > 1 else "")
    inv_domains = {d.lower() for d in inv.get("domains") or []}
    out: list[dict] = []
    for cid, ident in index.items():
        conf, why = 0.0, ""
        if ident["registrar"] and inv.get("registrar") \
                and ident["registrar"] != inv["registrar"] \
                and not (inv_domains & ident["domains"]):
            continue   # wrong company holds this client's domain
        if inv_domains & ident["domains"]:
            conf, why = 1.0, ("invite names " +
                              ", ".join(sorted(inv_domains & ident["domains"])))
        elif inviter and inviter in ident["names"]:
            conf, why = 0.9, f"inviter name matches contact '{inv.get('inviter')}'"
        elif last and any(last in _name_tokens(n) and first in _name_tokens(n)
                          for n in ident["names"]):
            conf, why = 0.9, f"inviter name matches contact '{inv.get('inviter')}'"
        elif last and first and (
                any(last in _name_tokens(n) for n in ident["names"])
                or last in ident["local_tokens"]):
            if first in ident["local_tokens"] or any(
                    first in _name_tokens(n) for n in ident["names"]):
                conf, why = 0.7, (f"'{inv.get('inviter')}' matches this "
                                  "client's contact name + email")
        elif first and first in ident["local_tokens"]:
            conf, why = 0.4, (f"only the first name '{first}' matches an email "
                              "on this account — ambiguous")
        if conf:
            out.append({"company_id": cid, "name": ident["name"],
                        "slug": ident["slug"], "confidence": conf, "why": why})
    out.sort(key=lambda c: -c["confidence"])
    return out


def invites_by_company(companies: list[dict], cid_to_slug: dict,
                       site_info: dict | None = None,
                       lookback_days: int = 500) -> tuple[dict, bool, str, list]:
    """(cid -> [verified invite, ...], scan_ok, error, ambiguous list).

    Only matches at or above AUTO_CONFIDENCE that are UNIQUE at their tier
    land in the per-company map; everything else is returned as ambiguous so
    a human decides instead of the ledger guessing.
    """
    invites, scan_ok, err = fetch_invites(lookback_days=lookback_days)
    if not scan_ok:
        return {}, False, err, []
    index = identity_index(companies, cid_to_slug, site_info)
    matched: dict[str, list[dict]] = {}
    ambiguous: list[dict] = []
    for inv in invites:
        cands = match_invite(inv, index)
        strong = [c for c in cands if c["confidence"] >= AUTO_CONFIDENCE]
        top = [c for c in strong if c["confidence"] == strong[0]["confidence"]] \
            if strong else []
        # Several companies owned by the SAME person (Jack Bispo owns both
        # All Pro and ProRestoration, one shared contacts array) is not real
        # ambiguity: one GoDaddy account access covers whichever of his
        # domains lives there, so the invite counts for each of them.
        same_owner = len(top) > 1 and len({
            frozenset(index[c["company_id"]]["emails"]) for c in top}) == 1
        if len(top) == 1 or same_owner:
            for cand in top:
                rec = dict(inv)
                rec["match"] = dict(cand)
                if same_owner:
                    rec["match"]["why"] += (" (same owner as "
                                            + str(len(top) - 1)
                                            + " sister account(s))")
                matched.setdefault(cand["company_id"], []).append(rec)
        else:
            ambiguous.append({"invite": inv, "candidates": cands[:4]})
    return matched, True, "", ambiguous


# ------------------------------------------------------------------- CLI
def _load_ops():
    from client_ops_sync import _sb, slug_map
    cos = _sb("GET", "/rest/v1/companies?status=ilike.active&select=id,name,"
              "website,email,account_owner_name,management_contacts,"
              "transfer_1_name,integration_settings",
              prefer="return=representation") or []
    sites = _sb("GET", "/rest/v1/marketing_sites?select=company_id,domain,"
                "domain_registrar,domain_registrar_guess",
                prefer="return=representation") or []
    return cos, slug_map(), {s["company_id"]: {
        "domain": s.get("domain"), "registrar": s.get("domain_registrar"),
        "registrar_guess": s.get("domain_registrar_guess")} for s in sites}


def cmd_scan(args) -> int:
    cos, cid_to_slug, site_domains = _load_ops()
    matched, ok, err, ambiguous = invites_by_company(
        cos, cid_to_slug, site_domains, lookback_days=args.days)
    if not ok:
        print(f"MAILBOX UNREADABLE — {err}")
        return 2
    n = sum(len(v) for v in matched.values())
    print(f"registrar invitations found: {n + len(ambiguous)} "
          f"({n} matched to a client, {len(ambiguous)} ambiguous)\n")
    for cid, invs in sorted(matched.items(), key=lambda kv: kv[1][0]["match"]["name"]):
        for inv in invs:
            print(f"  {inv['match']['name']} ({inv['match']['slug'] or cid})")
            print(f"    {inv['registrar']} invite from {inv['inviter']!r} "
                  f"on {inv['date'][:10]} -> {inv['to']}")
            print(f"    confidence {inv['match']['confidence']}: {inv['match']['why']}")
    for a in ambiguous:
        inv = a["invite"]
        print(f"  [AMBIGUOUS] {inv['registrar']} invite from {inv['inviter']!r} "
              f"on {inv['date'][:10]}")
        for c in a["candidates"]:
            print(f"      maybe {c['name']} ({c['confidence']}) — {c['why']}")
        if not a["candidates"]:
            print("      no candidate client at all")
    return 0


def cmd_check(args) -> int:
    cos, cid_to_slug, site_domains = _load_ops()
    cid = next((c for c, s in cid_to_slug.items() if s == args.slug), args.slug)
    matched, ok, err, _ = invites_by_company(cos, cid_to_slug, site_domains,
                                             lookback_days=args.days)
    if not ok:
        print(f"MAILBOX UNREADABLE — {err}")
        return 2
    invs = matched.get(cid) or []
    if not invs:
        print(f"{args.slug}: NO registrar access invitation has ever arrived "
              "for this client.")
        return 1
    for inv in invs:
        print(f"{args.slug}: {inv['registrar']} invite from {inv['inviter']!r} "
              f"on {inv['date'][:10]} ({inv['match']['why']})")
    return 0


def main() -> int:
    from client_concierge import load_env
    load_env()
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan", help="every registrar invite + its client match")
    s.add_argument("--days", type=int, default=500)
    s.set_defaults(fn=cmd_scan)
    c = sub.add_parser("check", help="does THIS client have a real invite?")
    c.add_argument("--slug", required=True)
    c.add_argument("--days", type=int, default=500)
    c.set_defaults(fn=cmd_check)
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
