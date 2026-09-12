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
* Auto-run covers pixels, paint AND WORDS (Santino 2026-08-08 — previously
  words were excluded). Rewording at the OWNER'S request is overseen by the
  person who matters most, and the AI wrote the copy in the first place. What
  still stops at his Approve button, after the 2026-08-08 widening: business
  facts, unclassified feedback, a bare rejection, deletions from an indexed
  site, complaints about our service, and legal pages. CLAIMS AND RATES NO
  LONGER STOP — the client is the source of truth about their own
  certifications, hours and prices, and claims_lint checks the BUILT site
  against their truth table, which is a better test than a keyword match on a
  text message. Ambiguity still resolves toward the human.
* The queued note carries an ORIGIN trailer (`ORIGIN: client-feedback | ...`).
  That is what survives the app's Approve button (which rewrites the tag but
  keeps the body) and what dev_inbox.py reads to close the loop back to the
  client. Everything else in the note is written for a human to read.
* Fail-open by contract, like work_log: routing must never break the 5-minute
  inbound poll. Every entry point swallows its own exceptions.
* SILENCE IS REPORTED, not inferred (2026-08-05). Every pass stamps a
  heartbeat (scripts/heartbeat.py) with what it saw and what it filed, so
  "no tasks in the inbox" and "the router is dead" are different, checkable
  states — `feedback_router.py status` answers it in one command, and
  scripts/silence_watch.py cards the gap daily. This module was declared dead
  on the day it started working because an inbox listing was checked two
  minutes before the write landed, and nothing could say otherwise.

CLI:
  python3 scripts/feedback_router.py selftest          # offline, no keys
  python3 scripts/feedback_router.py replay            # the two 08-04 cases
  python3 scripts/feedback_router.py status            # is the loop ALIVE?
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
    # COPY IS AUTO NOW (Santino 2026-08-08, on Greg asking to change "free
    # estimate" to "free assessment"): "it's fine to reword something if the
    # client asks, because the client will be checking. It almost is being
    # overseen by a human, who is the client himself. In fact the entire AI
    # writes the website in the first place."
    #
    # That is the right reading. The old rule treated every wording change as
    # agency liability, but the liability case is about a MACHINE DECIDING to
    # reword something. Applying the exact words the owner asked for is a
    # different act, and the owner is the authority on their own site's words.
    #
    # The risk regexes below still override: money, claims, removals,
    # complaints and legal pages stop at Santino no matter who asked. Those
    # are about truth and contracts, not phrasing.
    "copy":         ("site copy", True,
                     "rendered markdown under sites/{slug}/src/content"),
    # FACTS AND LEGAL RUN TOO (Santino 2026-08-09). "Business facts does not
    # need my approval." The owner is the authority on his own founding year,
    # address and hours, exactly as he is on his own certifications.
    "facts":        ("business facts on the site", True,
                     "plan-input brand block (the truth table)"),
    # A bare rejection still cannot auto-run, but NOT because it needs
    # Santino: there is genuinely nothing to execute. Santino 2026-08-09:
    # "why not just have Monica ask, 'Is there anything specific you'd like us
    # to do, or would you like our team to just handle it?'" That is a
    # CONVERSATION, so it routes to Monica rather than to his approve queue.
    "rejection":    ("preview rejected", False, "depends on what they meant"),
    "other":        ("unclassified", False, "n/a"),
}

AUTO_CATEGORIES = {k for k, (_, ok, _) in CATEGORIES.items() if ok}

# Why each never-auto category stops at Santino, in words that make sense on
# his phone at 11pm. This text is what the [TODO-PROPOSED] card shows him.
_NEVER_AUTO_WHY: dict[str, str] = {
    "facts":     ("a business fact has to be confirmed true by a human "
                  "before it goes on their site"),
    "rejection": ("they turned it down without saying what to change, so "
                  "Monica asks them: anything specific you want, or shall our "
                  "team just handle it? If they say handle it, she does"),
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

# NOTE (2026-08-08): _CLAIM_RE no longer gates client-requested changes — see
# risk_verdict. It is kept because other callers and claims_lint reason about
# the same vocabulary. Historical rationale below.
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
    # CLAIMS AND RATES NO LONGER STOP A CLIENT-REQUESTED CHANGE (Santino
    # 2026-08-08): "even if a word smuggles in something like 24-7 or IICRC
    # certified or talks about rates, we still want that to run itself without
    # going through me."
    #
    # The reasoning that makes this safe rather than reckless: the client is
    # the source of truth about their own certifications, hours and pricing.
    # Us refusing to publish "IICRC certified" for a firm that IS IICRC
    # certified was never protecting anyone; it just made the owner wait.
    #
    # The real backstop is downstream and stays: claims_lint runs at BUILD
    # time against the client's truth table, so a claim we have no evidence
    # for still fails there rather than shipping. That is a check against the
    # record, which is a better test than a keyword match on a text message.
    if _MONEY_RE.search(blob) and cat not in AUTO_CATEGORIES:
        return "propose", "touches pricing, billing or the contract"
    # PHONE NUMBERS NEVER AUTO-RUN (Frontline/Jared 2026-09-12: a mobile
    # LAYOUT complaint mentioning "phone number" auto-ran as display work
    # and the site's DNI tracking number was cemented over — attribution
    # silently lost). Any change whose words touch a phone number goes to a
    # human: the displayed number is usually a TRACKING line by design, and
    # Monica's script is to explain that first, not to swap it.
    if re.search(r"\bphone\s*(number|#)?\b|\bcall(?:ing)? number\b|"
                 r"\(\d{3}\)\s*\d{3}[- ]?\d{4}|\b\d{3}[-.]\d{3}[-.]\d{4}\b",
                 blob, re.I):
        return "propose", ("mentions a phone number — displayed numbers are "
                           "DNI tracking lines by design; a human confirms "
                           "before anything touches them")
    # LEGAL PAGES NO LONGER STOP (Santino 2026-08-09): "if somebody says to
    # update our privacy policy, Monica just needs to tell them to provide what
    # they want it updated to." The client supplies the wording; we apply it.
    # We are not drafting policy, we are typing what their lawyer wrote.
    if False and _LEGAL_RE.search(blob):
        return "propose", "touches a legal or policy page"

    # --- category-level stops --------------------------------------------
    if cat not in AUTO_CATEGORIES:
        return "propose", _NEVER_AUTO_WHY.get(cat, _NEVER_AUTO_WHY["other"])
    # BULLISH AUTO-RUN (Santino 2026-08-09, HomeLyft postmortem: Terry's
    # verbatim headline swap sat 5 days as a proposal): medium confidence
    # runs too. Only genuine uncertainty stops — "low" means the classifier
    # could not really tell what they want, so a human still reads it. The
    # risk regexes above (money, claims, removals, complaints) still stop
    # everything regardless of confidence.
    if conf not in ("high", "medium"):
        return "propose", f"classifier confidence was {conf} — genuinely unclear what they want"

    # --- live-production stops -------------------------------------------
    if site_live:
        # REMOVALS AUTO-RUN NOW (Santino 2026-08-10, HomeLyft's six-town
        # removal waited four days on his approval: "it should be executed
        # automatically"). The danger was never the deletion, it was deleting
        # an indexed URL without a redirect — so the redirect became a hard
        # execution requirement in dev_agent.md instead of a human gate here.
        if _REMOVAL_RE.search(blob):
            pass  # falls through to the normal category/confidence gates
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


_NOTES_PAGE = 500


def _recent_notes(company_id: str, days: int = 21) -> list[dict]:
    # "Z", not isoformat()'s "+00:00": a bare + in a PostgREST query string is
    # decoded as a space and the whole filter 400s. The dedupe check then
    # fails open and the same task is filed twice (caught in the 08-05 canary
    # run, which queued Greg's sewage fix two nights in a row).
    #
    # ORDERED, and loud when the page fills (2026-08-05). An unordered LIMIT
    # is the server's choice of rows, so a client with a busy three weeks
    # could have its NEWEST notes fall off the page — and a dedupe that
    # cannot see the note it should match files a duplicate, silently.
    since = (datetime.now(timezone.utc) - timedelta(days=days)
             ).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        rows = _sb("GET", "/rest/v1/marketing_ops_notes?company_id=eq."
                   f"{company_id}&created_at=gte.{since}"
                   "&select=id,body,status,created_at"
                   f"&order=created_at.desc&limit={_NOTES_PAGE}",
                   prefer="return=representation") or []
        if len(rows) >= _NOTES_PAGE:
            print(f"  [feedback] WARNING: {company_id} has {_NOTES_PAGE}+ notes "
                  f"in {days}d — the dedupe window is truncated, raise "
                  "_NOTES_PAGE")
        return rows
    except Exception as e:  # noqa: BLE001
        # Fails OPEN (returns []), so a lookup outage means a possible
        # duplicate task, never a lost one. Loud, because a silent dedupe
        # failure looks exactly like a working dedupe until it doesn't.
        print(f"  [feedback] WARNING: dedupe lookup failed, duplicates are "
              f"possible this pass: {str(e)[:200]}")
        return []


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower())


# Every marker that means "this note is queued work off something a client
# said" — the feedback trailer AND fathom_sync's meeting-commitment trailer.
# Dedupe has to see both: the ops lane checked its cards against the feedback
# mark only, which no ops card ever carries, so the check could never match
# and meeting commitments were never actually deduped (2026-08-05).
ORIGIN_MARKS = (ORIGIN_MARK, "ORIGIN: meeting-commitment")


def ask_key(quote: str, what: str | None = None) -> tuple[str, str]:
    """The identity of an ask: (their words window, our change window).

    Both are normalised 40-char windows. `what` is the load-bearing half —
    see note_matches_ask."""
    return _norm(quote)[:40].strip(), _norm(what or "")[:40].strip()


def note_matches_ask(body: str, qn: str, wn: str) -> bool:
    """Is `body` already the card for this ask? Pure, so the selftest can
    replay it offline.

    THE CHANGE IS THE IDENTITY, NOT THE QUOTE (2026-08-05). Matching on the
    quote alone was wrong in both directions:

      * ONE message routinely carries SEVERAL asks. Jerrott's 08-05 text
        produced three, and DISS's call produced three ops cards off one
        compound Fathom action item. When two items share a quote, the first
        one filed made the rest look "already queued" and they were dropped
        without a trace — losing a client's request, the worst failure this
        module has.
      * A client who re-words the same complaint ("the gold still isn't
        right") gets a second card, which is fine: a duplicate card is
        visible and costs one dismissal, a dropped request costs the client.

    So when we know what we intend to change, THAT window alone decides: two
    cards are the same card when they do the same thing. The client saying it
    twice in different words hits the same `what` and is correctly suppressed;
    two different changes never collide just because one quote covered both.
    Quote-only matching survives for callers with no `what` (and for cards
    filed before this trailer existed)."""
    nb = _norm(body)
    if len(wn) >= 12:
        return wn in nb
    return len(qn) >= 12 and qn in nb


def already_queued(company_id: str, quote: str,
                   what: str | None = None) -> str | None:
    """Has this exact ask already been filed? The 5-minute poll, the webhook,
    a re-run of the same batch and a re-mined meeting must not stack copies of
    one task (and a client who repeats themselves must not either).

    Checked against BOTH open and resolved notes from the last three weeks —
    a task the dev agent already finished must not be re-queued by a later
    poll — and against every ORIGIN marker, not just this module's."""
    qn, wn = ask_key(quote, what)
    if len(qn) < 12 and len(wn) < 12:
        return None
    for n in _recent_notes(company_id):
        b = n.get("body") or ""
        if not any(mk in b for mk in ORIGIN_MARKS):
            continue
        if note_matches_ask(b, qn, wn):
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
    dupes = 0
    errors: list[str] = []
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
    #
    # THE CAP NOW ANNOUNCES ITSELF (2026-08-05). It used to slice the list and
    # say nothing, so a client who asked for six things got four and no one
    # anywhere learned that two had been thrown away. A cap is a safety valve
    # against a hallucinating classifier, not a licence to lose a request.
    if len(feedback) > max(1, limit):
        dropped = feedback[max(1, limit):]
        msg = (f"{who} sent {len(feedback)} separate change requests in one "
               f"message and only the first {max(1, limit)} were queued. NOT "
               "queued: "
               + "; ".join(str(f.get("what"))[:90] for f in dropped)[:400])
        print(f"  [feedback] OVER CAP: {msg}")
        if escalate:
            try:
                escalate(msg)
            except Exception:  # noqa: BLE001
                pass
    for fb in feedback[:max(1, limit)]:
        try:
            if not is_actionable(fb):
                print(f"  [feedback] skipped a malformed block: {str(fb)[:90]}")
                continue
            quote = str(fb.get("quote") or "").strip()
            dupe = already_queued(cid, quote, str(fb.get("what") or ""))
            if dupe:
                dupes += 1
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
            errors.append(str(e)[:120])
            print(f"  [feedback] routing failed ({str(e)[:120]}) — the "
                  "message still reached the escalation digest")
    # PROOF OF LIFE (2026-08-05). Without this, "no tasks in the inbox" and
    # "the router is dead" are the same observation — which is exactly how an
    # inbox check two minutes ahead of the write got read as a total failure.
    # scripts/silence_watch.py compares inputs against outputs and cards the
    # gap; `feedback_router.py status` prints it on demand.
    try:
        from heartbeat import stamp
        stamp("feedback-router", inputs=len(feedback), outputs=len(out),
              dry_run=dry_run, dupes=dupes, company=company.get("name"),
              error="; ".join(errors)[:200] or None)
    except Exception as e:  # noqa: BLE001
        print(f"  [feedback] heartbeat warn: {str(e)[:90]}")
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
    # COPY IS AUTO SINCE 2026-08-08. These two used to assert the opposite;
    # the assertions moved, the risk cases below did NOT. The owner asking for
    # different words is not the failure mode the gate exists for.
    ("owner-requested reword on a LIVE site now runs",
     {"category": "copy", "what": "reword the homepage headline",
      "where": "homepage hero", "quote": "Can you change the headline to say "
      "water damage specialists instead", "confidence": "high"},
     True, "auto"),
    ("owner-requested reword on a PREVIEW site runs",
     {"category": "copy", "what": "reword the homepage headline",
      "where": "homepage hero", "quote": "Change the headline please",
      "confidence": "high"},
     False, "auto"),
    # CLAIMS AND RATES RUN TOO (Santino 2026-08-08). These five asserted the
    # opposite until today. The client is the source of truth about their own
    # certifications, hours and prices, and claims_lint still checks the built
    # site against their truth table, so an unevidenced claim fails there
    # rather than shipping. A keyword match on a text message was never the
    # thing keeping us honest.
    ("a reword carrying a claim runs",
     {"category": "copy", "what": "reword the hero line",
      "where": "hero", "quote": "Change it to say 24/7 emergency response",
      "confidence": "high"},
     True, "auto"),
    ("a reword about rates runs",
     {"category": "copy", "what": "reword the pricing note",
      "where": "services", "quote": "Change the wording about our rates",
      "confidence": "high"},
     True, "auto"),
    ("client dictates a claim",
     {"category": "design", "what": "add a 24/7 badge to the hero",
      "where": "hero", "quote": "Put 24/7 emergency service in the header",
      "confidence": "high"},
     False, "auto"),
    ("client dictates a certification",
     {"category": "brand", "what": "add the IICRC badge to the footer",
      "where": "footer", "quote": "We want the IICRC certified logo on there",
      "confidence": "high"},
     False, "auto"),
    ("pricing on the site",
     {"category": "copy", "what": "publish the new service pricing",
      "where": "services page", "quote": "Update the pricing to $299 minimum",
      "confidence": "high"},
     False, "auto"),
    ("an actual complaint",
     {"category": "design", "what": "make the site look better",
      "where": "site-wide",
      "quote": "Honestly I am really unhappy with this, I am thinking about "
               "cancelling", "confidence": "high"},
     False, "propose"),
    # Policy flip 2026-08-10 (Santino, HomeLyft postmortem): medium
    # confidence now RUNS; only "low" (genuinely unclear) proposes.
    ("classifier was unsure (medium runs now)",
     {"category": "imagery", "what": "maybe change the hero photo",
      "where": "homepage", "quote": "the picture is a bit odd",
      "confidence": "medium"},
     False, "auto"),
    ("classifier genuinely lost still proposes",
     {"category": "imagery", "what": "something about photos maybe",
      "where": "", "quote": "hm not sure about these",
      "confidence": "low"},
     False, "propose"),
    # Policy flip 2026-08-10: client-requested removals auto-run; the
    # mandatory-301 execution rules moved into dev_agent.md.
    ("removal from a LIVE site (client-requested, runs with redirects)",
     {"category": "service_area",
      "what": "remove the Henderson and Boulder City pages",
      "where": "service-area pages",
      "quote": "Take down the Henderson and Boulder City pages, we dont go "
               "there anymore", "confidence": "high"},
     True, "auto"),
    ("removal from a PREVIEW site is cheap and reversible",
     {"category": "service_area",
      "what": "remove the Henderson page before we launch",
      "where": "service-area pages",
      "quote": "Drop the Henderson page before this goes live",
      "confidence": "high"},
     False, "auto"),
    # Santino 2026-08-09: legal pages run too. Monica asks them for the wording
    # they want; we apply it. We are typing what their lawyer wrote, not
    # drafting policy.
    ("legal page runs once the client supplies the wording",
     {"category": "copy", "what": "update the privacy policy",
      "where": "privacy policy", "quote": "Our privacy policy needs updating",
      "confidence": "high"},
     False, "auto"),
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

    print("\ndedupe keys on the CHANGE, not the quote alone:")
    # The 08-05 shape: one text, three asks. The classifier can hand back the
    # same verbatim line for more than one of them (fathom's compound action
    # items always do — DISS filed three ops cards off one quote). Under
    # quote-only matching, asks 2 and 3 were dropped as "already queued".
    shared = "Logos on company vehicles need to match."
    filed = compose_task_note(
        {"category": "brand", "what": "resample the brand gold from the logo",
         "where": "site-wide", "quote": shared, "confidence": "high"},
        tag="[DEV]", company_name="Reign", slug="reign-restoration",
        who="Jerrott", site_live=False, site_url=None, verdict_why="ok",
        when="2026-08-05T00:00:00Z")
    dedupe_cases = [
        ("the SAME ask again is suppressed", shared,
         "resample the brand gold from the logo", True),
        ("a DIFFERENT ask sharing the quote still files", shared,
         "flip the mirrored van decal in the hero image", False),
        ("a re-worded quote for the same change is suppressed",
         "the golds still dont match", "resample the brand gold from the logo",
         True),
        ("an unrelated ask files", "the phone number is wrong",
         "update the phone number in the header", False),
    ]
    for label, q, w, want in dedupe_cases:
        qn, wn = ask_key(q, w)
        got = note_matches_ask(filed, qn, wn)
        ok = got == want
        fails += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} match={got!s:<5} (want {want!s:<5}) "
              f"{label}")
    # Legacy / quote-only callers keep the old behaviour.
    qn, wn = ask_key(shared, None)
    ok = note_matches_ask(filed, qn, wn)
    fails += not ok
    print(f"  {'ok  ' if ok else 'FAIL'} quote-only matching still works when "
          "the caller has no `what`")
    # A meeting-commitment card is dedupe-visible too (it never was before).
    ok = "ORIGIN: meeting-commitment" in ORIGIN_MARKS and ORIGIN_MARK in ORIGIN_MARKS
    fails += not ok
    print(f"  {'ok  ' if ok else 'FAIL'} both origin markers are in scope: "
          f"{ORIGIN_MARKS}")

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


def _cmd_status(_a) -> int:
    """Is the loop ALIVE? (2026-08-05: an empty inbox was read as a dead
    pipeline because nothing could answer this.) Inputs seen vs work filed."""
    from client_concierge import load_env
    load_env()
    from heartbeat import age_hours, read
    for system, label in (("inbound-classify", "concierge inbound (classify)"),
                          ("feedback-router", "feedback router (queue)")):
        hb = read(system)
        if not hb:
            print(f"{label}: NO HEARTBEAT YET — nothing has run since this "
                  "was deployed")
            continue
        t = hb.get("totals") or {}
        run_age = age_hours(hb.get("last_run_at"))
        out_age = age_hours(hb.get("last_output_at"))
        print(f"{label}:")
        print(f"  last ran      {str(hb.get('last_run_at'))[:16]}"
              + (f"  ({run_age:.1f}h ago)" if run_age is not None else ""))
        print(f"  last produced {str(hb.get('last_output_at'))[:16]}"
              + (f"  ({out_age:.1f}h ago)" if out_age is not None else
                 "  (never)"))
        print(f"  lifetime      {t.get('runs', 0)} run(s), "
              f"{t.get('inputs', 0)} input(s), {t.get('outputs', 0)} output(s)"
              + (f", last error: {str(hb.get('last_error'))[:70]}"
                 if hb.get("last_error") else ""))
        for r in (hb.get("runs") or [])[-5:]:
            print(f"    {str(r.get('at'))[:16]}  in={r.get('inputs')} "
                  f"out={r.get('outputs')}"
                  + (f" dupes={r['dupes']}" if r.get("dupes") else "")
                  + (f" {r.get('company')}" if r.get("company") else "")
                  + (f"  ERROR {str(r['error'])[:60]}" if r.get("error") else ""))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("selftest")
    sub.add_parser("replay")
    sub.add_parser("status")
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
    if a.cmd == "status":
        return _cmd_status(a)
    if a.cmd == "queue":
        return _cmd_queue(a)
    return _cmd_list(a)


if __name__ == "__main__":
    sys.exit(main())
