#!/usr/bin/env python3
"""feedback_router.py — client feedback becomes WORK, automatically.

THE STRUCTURAL GAP (Santino 2026-08-05). On the night of 08-04 Greg Arianoff
sent four screenshots of our own service images back with PPE corrections
("Biohazard would be in full suit sealed zipper and hood on."), and Jerrott
Gray said the Reign preview was "not ready to go live", wanted it "dark moody
and expensive looking", and asked why the service area did not include Dallas.
Monica received both, classified both, and replied to both. The actual WORK
happened only because Santino read the thread himself and asked for it. There
was no path from "the client said something actionable" to "queued, executed,
verified, client told".

This module is that path. It sits between the concierge's inbound classifier
(which now emits a `client_feedback` block — see CLASSIFY_SYSTEM) and the
nightly dev agent's [DEV] inbox (scripts/dev_inbox.py, .github/workflows/
dev-agent.yml), and it decides three things:

  1. Is this feedback WORK ON OUR SIDE?  (vs. a question, vs. an ask of them)
  2. Can a machine safely do it TONIGHT, unsupervised?  -> [DEV]
     ...or does Santino have to look at it first?      -> [TODO-PROPOSED]
  3. When it lands, who tells the client?  -> the [FROM SANTINO] directive
     that dev_inbox.py files on `done`, so Monica closes the loop in her own
     voice with the link.

DESIGN NOTES

* The risk gate is a PURE FUNCTION (`risk_verdict`) with no network calls, so
  `python3 scripts/feedback_router.py selftest` can replay real client messages
  offline in a second. Both 08-04 cases are in the regression set.
* Auto-run is deliberately narrow. Pixels and paint auto-run; WORDS do not.
  A client dictating copy, facts, claims or pricing onto a LIVE production site
  is exactly the failure mode that gets an agency sued, so those always stop at
  Santino's Approve button. Ambiguity resolves toward the human.
* The queued note carries an ORIGIN trailer (`ORIGIN: client-feedback | ...`).
  That is what survives the app's Approve button (which rewrites the tag but
  keeps the body) and what dev_inbox.py reads to close the loop back to the
  client. Everything else in the note is written for a human to read.
* Fail-open by contract, like work_log: routing must never break the 5-minute
  inbound poll. Every entry point swallows its own exceptions.

CLI:
  python3 scripts/feedback_router.py selftest          # offline, no keys
  python3 scripts/feedback_router.py replay            # the two 08-04 cases
  python3 scripts/feedback_router.py queue --slug X --category imagery \\
      --what "..." --quote "..." [--where "..."] [--who Greg] [--dry-run]
  python3 scripts/feedback_router.py list [--slug X]   # queued feedback tasks
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

# ---------------------------------------------------------------- categories
# What kind of work the feedback implies. The key is what the classifier
# returns; the tuple is (human label, auto-runnable at all, the tool that does
# it). "auto-runnable at all" is the FIRST gate — anything False can only ever
# become a [TODO-PROPOSED], no matter how confident the classifier is.
CATEGORIES: dict[str, tuple[str, bool, str]] = {
    "imagery":      ("site imagery", True,
                     "image-style-guide.md + gen_site_images.py --redo"),
    "design":       ("look and feel", True,
                     "plan-input brand block + build_site.resolve_tokens"),
    "brand":        ("brand assets", True,
                     "brand colours / logo / livery in the style guide"),
    "service_area": ("service areas", True,
                     "plan-input service_areas + plan_site + build_site add-pages"),
    "copy":         ("site copy", False,
                     "rendered markdown under sites/{slug}/src/content"),
    "facts":        ("business facts on the site", False,
                     "plan-input brand block (the truth table)"),
    "rejection":    ("preview rejected", False, "depends on what they meant"),
    "other":        ("unclassified", False, "n/a"),
}

AUTO_CATEGORIES = {k for k, (_, ok, _) in CATEGORIES.items() if ok}

# Why each never-auto category stops at Santino, in words that make sense on
# his phone at 11pm. This text is what the [TODO-PROPOSED] card shows him.
_NEVER_AUTO_WHY: dict[str, str] = {
    "copy":      ("changing the words on a client's site is the agency's "
                  "liability, not a machine's"),
    "facts":     ("a business fact has to be confirmed true by a human "
                  "before it goes on their site"),
    "rejection": ("they turned it down without saying what to change, so "
                  "somebody has to ask them what they meant"),
    "other":     ("no category with a known safe procedure fits this"),
}

# ---------------------------------------------------------------- risk regexes
# Words that must NEVER auto-execute regardless of category or confidence.
# Money and contracts are Santino's, always.
#
# Every alternative is boundary-anchored on BOTH ends. The first draft was
# not, and `fee` swallowed "the over all FEEl to be dark moody" — Jerrott's
# theme request would have gone to Santino's approve queue as a billing
# matter. Prefix matching is how a safety regex quietly becomes a blocker.
_MONEY_RE = re.compile(
    r"\b(?:pric(?:e|es|ing)|cost|costs|invoice[sd]?|bill|bills|billing|"
    r"billed|charge[ds]?|charging|refund[sed]*|contract[s]?|retainer|"
    r"payment[s]?|paid|discount[s]?|rates?|fees?)\b|\$\s?\d", re.I)
# ("quote" is deliberately absent: on a restoration site "request a quote" is
#  a CTA, not money talk, and it would block every form change.)

# Claims are the one thing a client can ASK for that we still may not publish
# without checking: certifications, 24/7, licences, response times, awards,
# "family owned", years in business, star ratings. claims_lint.py exists
# because a client-flavoured claim shipped once already (davis-construction,
# 2026-07). A machine may not be the one that decides a claim is true.
_CLAIM_RE = re.compile(
    r"\b(?:24[\s/-]?7|24 hours|iicrc|certif\w*|licen[cs]\w*|bonded|insured|"
    r"accredit\w*|award\w*|guarantee\w*|warrant\w*|family[\s-]?owned|"
    r"veteran[\s-]?owned|woman[\s-]?owned|est\.?\s?\d{4}|since \d{4}|"
    r"\d+\+?\s*(?:years|yrs)|response time|minutes? or less|"
    r"\d\.\d\s*star|best in|number one|top[\s-]rated)\b"
    r"|#\s?1\b", re.I)

# Destructive intent — removing pages/cities/services from a site that is
# already indexed. Additive work is cheap to reverse; deletions are not.
_REMOVAL_RE = re.compile(
    r"\b(?:remove|delete|take (?:it |them |that )?down|get rid of|drop|"
    r"unpublish|pull (?:it|them|that) (?:off|down))\b", re.I)

# Reads like a complaint about US, not a correction of the work. Corrections
# ("the yellow needs to match the logo") are the normal, healthy case and must
# NOT trip this — only dissatisfaction with the relationship does.
_COMPLAINT_RE = re.compile(
    r"\b(?:cancel(?:ling|ing|lation)?|refund|unhappy|disappointed|frustrat\w*|"
    r"unacceptable|waste of (?:time|money)|not what (?:i|we) (?:paid|signed)|"
    r"lawyer|attorney|dispute|fed up|last (?:chance|straw)|"
    r"(?:this|it) is (?:terrible|awful|horrible|garbage|trash))\b", re.I)

# Legal/regulated surfaces a machine never edits on its own.
_LEGAL_RE = re.compile(
    r"\b(?:privacy policy|terms of service|terms and conditions|disclaimer|"
    r"ada|accessibility statement|gdpr|ccpa|hipaa)\b", re.I)


# ---------------------------------------------------------------- the gate
def risk_verdict(fb: dict, *, site_live: bool, has_site: bool) -> tuple[str, str]:
    """The whole auto-vs-human decision, as one pure function.

    Returns ("auto", why) or ("propose", why). Never raises, never calls out.

    fb keys (all optional except category/what/quote):
      category   one of CATEGORIES
      what       the change, in our words
      where      which page / asset / section, or "site-wide"
      quote      the client's verbatim words
      confidence "high" | "medium" | "low"
      complaint  bool — the classifier's read that a human is needed

    site_live  the client's apex is cut over (marketing_sites.apex_live)
    has_site   we have a sites/{slug} subtree to change at all
    """
    cat = str(fb.get("category") or "other").strip().lower()
    what = str(fb.get("what") or "").strip()
    quote = str(fb.get("quote") or "").strip()
    conf = str(fb.get("confidence") or "low").strip().lower()
    blob = f"{quote}\n{what}\n{fb.get('where') or ''}"

    if not has_site:
        return "propose", ("no site subtree on file for this client, so there "
                           "is nothing a build agent can change")
    if not what:
        return "propose", "the classifier could not say what they want changed"
    if cat not in CATEGORIES:
        return "propose", f"unknown feedback category {cat!r}"

    # --- absolute stops, ahead of everything else -------------------------
    if fb.get("complaint") or _COMPLAINT_RE.search(blob):
        return "propose", ("reads as a complaint about our service, not a "
                           "correction, so a human answers it first")
    if _MONEY_RE.search(blob):
        return "propose", "touches pricing, billing or the contract"
    if _CLAIM_RE.search(blob):
        return "propose", ("would put a certification, availability, licence "
                           "or superlative claim on the site, and only a "
                           "human may certify a claim is true")
    if _LEGAL_RE.search(blob):
        return "propose", "touches a legal or policy page"

    # --- category-level stops --------------------------------------------
    if cat not in AUTO_CATEGORIES:
        return "propose", _NEVER_AUTO_WHY.get(cat, _NEVER_AUTO_WHY["other"])
    if conf != "high":
        return "propose", f"classifier confidence was {conf}, not high"

    # --- live-production stops -------------------------------------------
    if site_live:
        if _REMOVAL_RE.search(blob):
            return "propose", ("asks to remove something from a LIVE site, "
                               "and deletions on an indexed site are not "
                               "reversible on their own")
    return "auto", (f"{CATEGORIES[cat][0]} change, stated plainly, on a "
                    f"{'live' if site_live else 'preview'} site")


def is_actionable(fb: dict) -> bool:
    """Is this a feedback block worth routing at all? (Shape check only —
    the classifier decides meaning, this rejects malformed rows.)"""
    return bool(str(fb.get("quote") or "").strip()
                and str(fb.get("what") or "").strip())


# ---------------------------------------------------------------- note bodies
ORIGIN_MARK = "ORIGIN: client-feedback"
_ORIGIN_RE = re.compile(r"ORIGIN:\s*client-feedback([^\n]*)", re.I)
# Fallback when the trailer is gone but the note is plainly ours: the header
# line carries the same three facts in prose. Verified 2026-08-05 that the
# app's Approve button preserves the whole body (OpsAttention.tsx does
# `[DEV] ${detail}` on body-minus-tag), so this is insurance against a hand
# edit or a future app change, not a known break.
_HEADER_RE = re.compile(
    r"CLIENT FEEDBACK\s*\(([^)]*)\)\s*from\s+(.+?)\s+at\s+(.+?),\s*"
    r"(\d{4}-\d{2}-\d{2})", re.I)


def parse_origin(body: str) -> dict | None:
    """Read the ORIGIN trailer back off a [DEV] / [TODO-PROPOSED] note.

    This is the hinge of the whole loop: the app's Approve button rewrites the
    tag but keeps the body, so the trailer is what survives from queue-time to
    done-time and tells `dev_inbox.py done` there is a client to tell.
    Returns None for notes that did not come from a client."""
    body = body or ""
    out: dict[str, str] = {}
    m = _ORIGIN_RE.search(body)
    if m:
        out["origin"] = "client-feedback"
        for part in m.group(1).split("|"):
            part = part.strip()
            if "=" in part:
                k, v = part.split("=", 1)
                out[k.strip()] = v.strip()
    else:
        h = _HEADER_RE.search(body)
        if not h:
            return None
        out = {"origin": "client-feedback", "who": h.group(2).strip(),
               "company": h.group(3).strip()}
        for key, (label, _, _) in CATEGORIES.items():
            if label.lower() == h.group(1).strip().lower():
                out["cat"] = key
                break
    # The client's verbatim words live on their own labelled line.
    q = re.search(r'THEY SAID:\s*"(.+?)"\s*$', body, re.M | re.S)
    if q:
        out["quote"] = q.group(1).strip()
    return out


def compose_task_note(fb: dict, *, tag: str, company_name: str, slug: str,
                      who: str, site_live: bool, site_url: str | None,
                      verdict_why: str, when: str) -> str:
    """The queued note. Written for a human to read at a glance and for the
    dev agent to execute from, with one machine-readable trailer."""
    cat = str(fb.get("category") or "other").lower()
    label, _, tool = CATEGORIES.get(cat, CATEGORIES["other"])
    where = str(fb.get("where") or "").strip() or "not specified"
    lines = [
        f"{tag} CLIENT FEEDBACK ({label}) from {who} at {company_name}, "
        f"{when[:10]}:",
        str(fb.get("what") or "").strip(),
        f"WHERE: {where}",
        f'THEY SAID: "{str(fb.get("quote") or "").strip()}"',
        f"SITE: sites/{slug} — {'LIVE production' if site_live else 'preview/staging'}"
        + (f" ({site_url})" if site_url else ""),
        f"LIKELY TOOL: {tool}",
    ]
    if tag == "[DEV]":
        lines.append("WHEN DONE: dev_inbox.py done files the [FROM SANTINO] "
                     "note automatically, so Monica tells them it is fixed "
                     "with the link. Do not text the client yourself.")
    else:
        lines.append(f"WHY THIS NEEDS YOUR OK: {verdict_why}. Approve and it "
                     "becomes a [DEV] task on tonight's run; dismiss and "
                     "nothing happens.")
    lines.append(
        f"{ORIGIN_MARK} | who={who} | cat={cat} | conf="
        f"{str(fb.get('confidence') or 'low').lower()} | slug={slug}"
        + (" | live=1" if site_live else ""))
    return "\n".join(lines)


def compose_done_directive(origin: dict, summary: str,
                           link: str | None) -> str:
    """The [FROM SANTINO] note filed when the work lands — the fourth step of
    the loop, and the one we had been doing by hand all night.

    [FROM SANTINO] is a directive tag (client_concierge._DIRECTIVE_TAGS): it
    outranks the cadence cooldown and the nudge cap, so Monica delivers it on
    the next pass instead of waiting for a nudge slot. The wording models the
    Reign message Santino wrote himself: what changed, one line, take a look."""
    who = origin.get("who") or "the client"
    # Their own sentence usually ends in a period; wrapping it in quotes and
    # then adding ours reads as a typo ('...hood on.".').
    quote = (origin.get("quote") or "").strip().rstrip(".!, ")
    body = [
        f"[FROM SANTINO] {who} asked us to change this: "
        + (f'"{quote[:180]}". ' if quote else "")
        + "It is DONE now.",
        f"Tell them in one short line what changed ({summary[:220]}) and that "
        "they can take another look.",
    ]
    if link:
        body.append(f"Include this link: {link}")
    body.append("Past tense is correct here, the work is recorded. Do not ask "
                "them anything else in this message, no other item rides "
                "along.")
    return "\n".join(body)


# ---------------------------------------------------------------- supabase
def _sb(*a, **kw):
    from client_ops_sync import _sb as sb  # lazy: selftest needs no env
    return sb(*a, **kw)


def site_status(company_id: str, slug: str | None) -> tuple[bool, bool, str | None]:
    """(has_site, site_live, url) for a client.

    has_site  = a sites/{slug} subtree exists in the monorepo
    site_live = marketing_sites.apex_live, i.e. the real domain is cut over,
                so a deploy to main reaches the public internet
    url       = the best link to hand the client (apex when live, else preview)
    """
    has_site = bool(slug and (ROOT / "sites" / slug).exists())
    live, url = False, None
    try:
        rows = _sb("GET", "/rest/v1/marketing_sites?company_id=eq."
                   f"{company_id}&select=cloudflare_pages_url,domain,apex_live"
                   "&limit=1", prefer="return=representation") or []
        row = rows[0] if rows else {}
        apex = str(row.get("domain") or "").strip()
        if row.get("apex_live") and apex:
            live = True
            url = apex if apex.startswith("http") else f"https://{apex}"
        else:
            u = str(row.get("cloudflare_pages_url") or "").strip()
            url = u if u.startswith("http") else None
    except Exception as e:  # noqa: BLE001 — unknown state routes to the human
        print(f"  [feedback] marketing_sites lookup failed: {str(e)[:90]}")
    return has_site, live, url


def _recent_notes(company_id: str, days: int = 21) -> list[dict]:
    # "Z", not isoformat()'s "+00:00": a bare + in a PostgREST query string is
    # decoded as a space and the whole filter 400s. The dedupe check then
    # fails open and the same task is filed twice (caught in the 08-05 canary
    # run, which queued Greg's sewage fix two nights in a row).
    since = (datetime.now(timezone.utc) - timedelta(days=days)
             ).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        return _sb("GET", "/rest/v1/marketing_ops_notes?company_id=eq."
                   f"{company_id}&created_at=gte.{since}"
                   "&select=id,body,status,created_at&limit=300",
                   prefer="return=representation") or []
    except Exception as e:  # noqa: BLE001
        # Fails OPEN (returns []), so a lookup outage means a possible
        # duplicate task, never a lost one. Loud, because a silent dedupe
        # failure looks exactly like a working dedupe until it doesn't.
        print(f"  [feedback] WARNING: dedupe lookup failed, duplicates are "
              f"possible this pass: {str(e)[:200]}")
        return []


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower())


def already_queued(company_id: str, quote: str) -> str | None:
    """Has this exact feedback already been filed? The 5-minute poll, the
    webhook and a re-run of the same batch must not stack three copies of the
    same task (and a client who repeats themselves must not either).

    Matching is on a normalised 40-char window of their own words, checked
    against BOTH open and resolved notes from the last three weeks — a task
    the dev agent already finished must not be re-queued by a later poll."""
    needle = _norm(quote)[:40].strip()
    if len(needle) < 12:
        return None
    for n in _recent_notes(company_id):
        b = n.get("body") or ""
        if ORIGIN_MARK not in b:
            continue
        if needle in _norm(b):
            return str(n.get("id"))
    return None


# ---------------------------------------------------------------- the router
def route_feedback(company: dict, feedback: list[dict], *, who: str,
                   when: str | None = None, dry_run: bool = False,
                   escalate=None, limit: int = 4) -> list[dict]:
    """Turn a classifier `client_feedback` block into queued work.

    One note per feedback item: [DEV] when the gate says auto (the nightly
    dev agent picks it up without anyone clicking), [TODO-PROPOSED] when it
    says propose (Santino's Approve button turns it into [DEV]).

    FAIL-OPEN: any exception is printed and swallowed. Losing a queued task is
    recoverable (the client will say it again, and the escalation digest still
    carries the message); breaking the inbound poll is not.

    Returns a list of {"tag", "why", "note_id", "category"} for the caller to
    print / test against."""
    out: list[dict] = []
    cid = company.get("id")
    if not cid or not feedback:
        return out
    when = when or datetime.now(timezone.utc).isoformat()
    try:
        from client_concierge import company_slug
        slug = company_slug(cid)
    except Exception:  # noqa: BLE001
        slug = None
    has_site, live, url = site_status(cid, slug)

    # An inbound TEXT is a burst of corrections, not a backlog, so the default
    # cap stays 4. A recorded MEETING legitimately carries more (HomeLyft
    # asked for nine things on 2026-08-04), so fathom_sync raises it — the cap
    # is about the plausibility of the SOURCE, not a limit on client asks.
    for fb in feedback[:max(1, limit)]:
        try:
            if not is_actionable(fb):
                print(f"  [feedback] skipped a malformed block: {str(fb)[:90]}")
                continue
            quote = str(fb.get("quote") or "").strip()
            dupe = already_queued(cid, quote)
            if dupe:
                print(f"  [feedback] already queued as note {str(dupe)[:8]} — "
                      f"not filing again ({quote[:50]!r})")
                continue
            verdict, why = risk_verdict(fb, site_live=live, has_site=has_site)
            tag = "[DEV]" if verdict == "auto" else "[TODO-PROPOSED]"
            body = compose_task_note(
                fb, tag=tag, company_name=company.get("name") or "the client",
                slug=slug or "?", who=who, site_live=live, site_url=url,
                verdict_why=why, when=when)
            print(f"  [feedback] {verdict.upper()} ({fb.get('category')}): "
                  f"{str(fb.get('what'))[:70]!r} — {why}")
            if dry_run:
                print("    [dry-run] would file:\n      "
                      + body.replace("\n", "\n      "))
                out.append({"tag": tag, "why": why, "note_id": None,
                            "category": fb.get("category")})
                continue
            row = _sb("POST", "/rest/v1/marketing_ops_notes",
                      {"company_id": cid, "body": body, "status": "open",
                       "author": "monica"},
                      prefer="return=representation")
            note_id = (row or [{}])[0].get("id") if isinstance(row, list) else None
            print(f"    filed {tag} note {str(note_id)[:8]}"
                  + (" — runs on tonight's dev-agent pass"
                     if tag == "[DEV]" else " — waiting on your approve"))
            # The ledger line that makes this show up as RESPONSIVENESS in
            # their monthly report (work_report groups category "site").
            try:
                from work_log import work_log
                work_log(cid, "site", "client-feedback-queued",
                         f"{who} asked for a change to their website and it "
                         f"went into the build queue the same day: "
                         f"{str(fb.get('what'))[:120]}",
                         evidence={"quote": quote[:300],
                                   "category": fb.get("category"),
                                   "where": fb.get("where"),
                                   "verdict": verdict, "why": why,
                                   "note_id": note_id, "slug": slug,
                                   "site_live": live},
                         actor="monica",
                         source="feedback_router.route_feedback")
            except Exception as e:  # noqa: BLE001
                print(f"    [work-log] warn: {str(e)[:90]}")
            if tag == "[TODO-PROPOSED]" and escalate:
                try:
                    escalate(f"{who} asked for site work we did NOT auto-run: "
                             f"{str(fb.get('what'))[:120]} ({why}). Approve it "
                             "in Today and tonight's dev agent does it.")
                except Exception:  # noqa: BLE001
                    pass
            out.append({"tag": tag, "why": why, "note_id": note_id,
                        "category": fb.get("category")})
        except Exception as e:  # noqa: BLE001 — never break the poll
            print(f"  [feedback] routing failed ({str(e)[:120]}) — the "
                  "message still reached the escalation digest")
    return out


# ---------------------------------------------------------------- selftest
# Offline regression cases for the gate. No network, no keys. Both real 08-04
# messages are replays, quoted verbatim from the commits that fixed them by
# hand (f9791388 Greg/PuroClean, 86e935b3 + 02f85dc8 Jerrott/Reign).
REPLAYS: list[tuple[str, dict, bool, str]] = [
    # (label, feedback block, site_live, expected verdict)
    ("Greg / PuroClean — PPE wrong in the service images",
     {"category": "imagery",
      "what": "regenerate the biohazard, sewage and mold service images with "
              "full sealed suits zipped to the throat and hoods up, and fix "
              "the distorted water-damage tech",
      "where": "service card images: biohazard, sewage, mold, water damage",
      "quote": "Biohazard would be in full suit sealed zipper and hood on. "
               "Sewage same as Biohazard full suit zipped up, wearing the "
               "suit around waist is frowned upon. This guy is distorted.",
      "confidence": "high", "complaint": False},
     True, "auto"),
    ("Greg / PuroClean — 'you went overboard' is a correction, not a complaint",
     {"category": "imagery",
      "what": "loosen the uniform rule so PPE matches the scene instead of "
              "one blanket rule",
      "where": "service card images",
      "quote": "I think you went overboard with the uniform requirements and AI",
      "confidence": "high", "complaint": False},
     True, "auto"),
    ("Jerrott / Reign — dark and moody, black vehicles",
     {"category": "design",
      "what": "make the whole site dark, moody and premium, and make the "
              "company vehicles black",
      "where": "site-wide theme and every vehicle image",
      "quote": "Id like the over all feel to be dark moody and expensive "
               "looking. The company vehicles need to be black.",
      "confidence": "high", "complaint": False},
     False, "auto"),
    ("Jerrott / Reign — service area missing Dallas",
     {"category": "service_area",
      "what": "add Dallas and the other major metro cities to the service area",
      "where": "service-area pages",
      "quote": "Is there a reason the service area dosnt include dallas and "
               "other major areas?",
      "confidence": "high", "complaint": False},
     False, "auto"),
    ("Jerrott / Reign — brand yellow must match the logo",
     {"category": "brand",
      "what": "resample the brand yellow from his logo file and make the "
              "vehicle decals consistent across every image",
      "where": "brand primary colour + vehicle livery",
      "quote": "The yellow need to to match the logo color and the company "
               "vehicle decals need to match from photo to photo.",
      "confidence": "high", "complaint": False},
     False, "auto"),
    ("Jerrott / Reign — bare rejection with no specifics",
     {"category": "rejection",
      "what": "the preview was rejected, find out what to change",
      "where": "the whole preview",
      "quote": "Viewed it and it is not ready to go live.",
      "confidence": "high", "complaint": False},
     False, "propose"),
    # --- the stops -------------------------------------------------------
    ("copy change on a LIVE site",
     {"category": "copy", "what": "reword the homepage headline",
      "where": "homepage hero", "quote": "Can you change the headline to say "
      "water damage specialists instead", "confidence": "high"},
     True, "propose"),
    ("copy change on a PREVIEW site is still a human's call",
     {"category": "copy", "what": "reword the homepage headline",
      "where": "homepage hero", "quote": "Change the headline please",
      "confidence": "high"},
     False, "propose"),
    ("client dictates a claim",
     {"category": "design", "what": "add a 24/7 badge to the hero",
      "where": "hero", "quote": "Put 24/7 emergency service in the header",
      "confidence": "high"},
     False, "propose"),
    ("client dictates a certification",
     {"category": "brand", "what": "add the IICRC badge to the footer",
      "where": "footer", "quote": "We want the IICRC certified logo on there",
      "confidence": "high"},
     False, "propose"),
    ("pricing on the site",
     {"category": "copy", "what": "publish the new service pricing",
      "where": "services page", "quote": "Update the pricing to $299 minimum",
      "confidence": "high"},
     False, "propose"),
    ("an actual complaint",
     {"category": "design", "what": "make the site look better",
      "where": "site-wide",
      "quote": "Honestly I am really unhappy with this, I am thinking about "
               "cancelling", "confidence": "high"},
     False, "propose"),
    ("classifier was unsure",
     {"category": "imagery", "what": "maybe change the hero photo",
      "where": "homepage", "quote": "the picture is a bit odd",
      "confidence": "medium"},
     False, "propose"),
    ("removal from a LIVE site",
     {"category": "service_area",
      "what": "remove the Henderson and Boulder City pages",
      "where": "service-area pages",
      "quote": "Take down the Henderson and Boulder City pages, we dont go "
               "there anymore", "confidence": "high"},
     True, "propose"),
    ("removal from a PREVIEW site is cheap and reversible",
     {"category": "service_area",
      "what": "remove the Henderson page before we launch",
      "where": "service-area pages",
      "quote": "Drop the Henderson page before this goes live",
      "confidence": "high"},
     False, "auto"),
    ("legal page",
     {"category": "copy", "what": "update the privacy policy",
      "where": "privacy policy", "quote": "Our privacy policy needs updating",
      "confidence": "high"},
     False, "propose"),
    ("no site to change yet",
     {"category": "imagery", "what": "change the hero image",
      "where": "homepage", "quote": "the hero image should be a house",
      "confidence": "high"},
     False, "propose"),   # forced by has_site=False below
]


def _selftest() -> int:
    fails = 0
    print("risk gate:")
    for label, fb, live, want in REPLAYS:
        has_site = "no site" not in label
        got, why = risk_verdict(fb, site_live=live, has_site=has_site)
        ok = got == want
        fails += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} {got:<7} (want {want:<7}) "
              f"{label}\n         {why}")

    print("\nmalformed blocks are dropped, not queued:")
    for fb in ({"category": "imagery", "quote": "", "what": "x"},
               {"category": "imagery", "quote": "y", "what": ""},
               {}):
        ok = not is_actionable(fb)
        fails += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} {str(fb)[:60]}")

    print("\nORIGIN trailer survives a round trip (the Approve-button hinge):")
    fb = REPLAYS[0][1]
    dev = compose_task_note(fb, tag="[DEV]", company_name="PuroClean East LV",
                            slug="puroclean-east-las-vegas", who="Greg",
                            site_live=True, site_url="https://x.test",
                            verdict_why="ok", when="2026-08-05T00:00:00Z")
    prop = compose_task_note(fb, tag="[TODO-PROPOSED]",
                             company_name="PuroClean East LV",
                             slug="puroclean-east-las-vegas", who="Greg",
                             site_live=True, site_url=None,
                             verdict_why="claims", when="2026-08-05T00:00:00Z")
    # The app's Approve button rewrites the tag and keeps the body.
    approved = prop.replace("[TODO-PROPOSED]", "[DEV]", 1)
    for label, body in (("queued [DEV]", dev), ("approved proposal", approved)):
        o = parse_origin(body)
        ok = bool(o and o.get("who") == "Greg" and o.get("cat") == "imagery"
                  and "sealed zipper" in (o.get("quote") or ""))
        fails += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} {label}: {o}")
    ok = parse_origin("[DEV] rebuild the hero section") is None
    fails += not ok
    print(f"  {'ok  ' if ok else 'FAIL'} a hand-written [DEV] note has no "
          "origin (no client to notify)")
    # Trailer stripped by hand: the header line still identifies the client.
    stripped = "\n".join(l for l in dev.splitlines()
                         if not l.startswith(ORIGIN_MARK))
    o = parse_origin(stripped)
    ok = bool(o and o.get("who") == "Greg" and o.get("cat") == "imagery"
              and "sealed zipper" in (o.get("quote") or ""))
    fails += not ok
    print(f"  {'ok  ' if ok else 'FAIL'} trailer stripped, header fallback: {o}")

    print("\ndev-agent inbox sees a task, not a JSON blob:")
    task = dev[len("[DEV]"):].strip()
    ok = ("THEY SAID:" in task and "LIKELY TOOL:" in task
          and "SITE: sites/puroclean-east-las-vegas — LIVE production" in task)
    fails += not ok
    print(f"  {'ok  ' if ok else 'FAIL'} {task.splitlines()[0][:78]}")

    print("\nclose-the-loop directive:")
    d = compose_done_directive(parse_origin(dev), "PPE fixed on the four "
                               "service images", "https://x.test")
    ok = (d.startswith("[FROM SANTINO]") and "Greg" in d
          and "https://x.test" in d and "—" not in d and "–" not in d)
    fails += not ok
    print(f"  {'ok  ' if ok else 'FAIL'} {d[:100]!r}")

    print(f"\n{'ALL GREEN' if not fails else str(fails) + ' FAILURE(S)'}")
    return 1 if fails else 0


def _replay() -> int:
    """The two real 08-04 cases, end to end through the gate, printed as the
    notes that WOULD have been filed had the loop existed that night."""
    cases = [
        ("Greg Arianoff", "PuroClean East Las Vegas",
         "puroclean-east-las-vegas", True, REPLAYS[0][1]),
        ("Jerrott Gray", "Reign Restoration", "reign-restoration", False,
         REPLAYS[2][1]),
        ("Jerrott Gray", "Reign Restoration", "reign-restoration", False,
         REPLAYS[3][1]),
    ]
    for who, name, slug, live, fb in cases:
        v, why = risk_verdict(fb, site_live=live,
                              has_site=(ROOT / "sites" / slug).exists())
        tag = "[DEV]" if v == "auto" else "[TODO-PROPOSED]"
        print("=" * 72)
        print(compose_task_note(fb, tag=tag, company_name=name, slug=slug,
                                who=who, site_live=live, site_url=None,
                                verdict_why=why,
                                when="2026-08-05T00:00:00Z"))
        print("-" * 72)
        print(compose_done_directive(
            parse_origin(compose_task_note(
                fb, tag=tag, company_name=name, slug=slug, who=who,
                site_live=live, site_url=None, verdict_why=why,
                when="2026-08-05T00:00:00Z")),
            "the change they asked for", "https://preview.example"))
    return 0


def _cmd_queue(a) -> int:
    from client_concierge import load_env
    load_env()
    from work_log import company_id_for_slug
    cid = company_id_for_slug(a.slug)
    if not cid:
        print(f"ERROR: no company_id for slug {a.slug!r}", file=sys.stderr)
        return 1
    company = {"id": cid, "name": a.company or a.slug}
    res = route_feedback(company,
                         [{"category": a.category, "what": a.what,
                           "where": a.where, "quote": a.quote,
                           "confidence": a.confidence,
                           "complaint": a.complaint}],
                         who=a.who, dry_run=a.dry_run)
    return 0 if res else 1


def _cmd_list(a) -> int:
    from client_concierge import load_env
    load_env()
    from client_ops_sync import slug_map
    smap = slug_map()
    rows = _sb("GET", "/rest/v1/marketing_ops_notes?status=eq.open"
               "&select=id,company_id,body,created_at&order=created_at.asc"
               "&limit=500", prefer="return=representation") or []
    n = 0
    for r in rows:
        o = parse_origin(r.get("body") or "")
        if not o:
            continue
        slug = smap.get(r.get("company_id"))
        if a.slug and slug != a.slug:
            continue
        n += 1
        tag = (r["body"].split(" ", 1)[0] or "?")
        print(f"{str(r['id'])[:8]}  {tag:<16} {slug or '?':<28} "
              f"{r['created_at'][:16]}  {o.get('cat')}  "
              f"{r['body'].splitlines()[1][:70] if len(r['body'].splitlines()) > 1 else ''}")
    print(f"\n{n} open client-feedback task(s)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("selftest")
    sub.add_parser("replay")
    q = sub.add_parser("queue")
    q.add_argument("--slug", required=True)
    q.add_argument("--company", default="")
    q.add_argument("--category", required=True, choices=sorted(CATEGORIES))
    q.add_argument("--what", required=True)
    q.add_argument("--quote", required=True)
    q.add_argument("--where", default="")
    q.add_argument("--who", default="the client")
    q.add_argument("--confidence", default="high",
                   choices=["high", "medium", "low"])
    q.add_argument("--complaint", action="store_true")
    q.add_argument("--dry-run", action="store_true")
    l = sub.add_parser("list")
    l.add_argument("--slug", default="")
    a = ap.parse_args()
    if a.cmd == "selftest":
        return _selftest()
    if a.cmd == "replay":
        return _replay()
    if a.cmd == "queue":
        return _cmd_queue(a)
    return _cmd_list(a)


if __name__ == "__main__":
    sys.exit(main())
