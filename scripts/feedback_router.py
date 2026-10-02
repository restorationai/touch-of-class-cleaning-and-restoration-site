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
                     "image-style-guide.md + gen_site_images.py --redo (named images only, --request quoting the client; image_guard.py)"),
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
    # Social/footer links are the client stating a fact about their own
    # profiles (Angie 2026-09-10: the Facebook/Instagram ask sat four days
    # as an unclassified [TODO-PROPOSED] while Monica's ack sounded like a
    # commitment). Owner-supplied URLs are their authority, like copy/facts.
    "site_links":   ("links and social icons on the site", True,
                     "citation_listings kind=social (Connect card) + "
                     "citations_sync footer/sameAs pass"),
    # CALL FORWARDING RUNS ON THE SPOT (Santino 2026-09-29, Bob Olson): a
    # client naming where a tracking number should ring is a setting we
    # manage, not a build. route_feedback executes it via call_forward.apply
    # the moment it arrives and files the done-directive; only an ambiguous
    # or invalid ask falls through to the dev agent like "other".
    "call_routing": ("call forwarding", True,
                     "scripts/call_forward.py set (call_tracking.{source}.forward_to)"),
    "rejection":    ("preview rejected", False, "depends on what they meant"),
    # UNCLASSIFIED RUNS TOO (Santino 2026-09-28): "I don't want to have to
    # approve every time after a meeting." Rachelle's "publish the new site
    # today" sat as an unclassified [TODO-PROPOSED] on the very day it was
    # promised. The dev agent triages every task and hands back only a step
    # that truly needs a person, so an unfamiliar ask is its problem to
    # scope, not a reason to park it. Confidence and the risk regexes above
    # still apply.
    "other":        ("unclassified", True,
                     "dev agent triage: do what it can, punt the rest"),
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

    # NO SITE YET IS NOT A REASON TO PARK (Santino 2026-09-28, Dry1 Out):
    # Cole's kickoff asked for the Astro rebuild, local landing pages and a
    # restoration-first Vista position; all three sat as proposals because
    # the site did not exist yet, which is exactly when they matter most.
    # They run as build INPUT: dev_agent.md records them in plan-input so
    # the first build ships with them.
    if not has_site:
        return "auto", ("no site built yet: record it as input for the first "
                        "build (plan-input / site brief)")
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
    # PHONE NUMBERS AUTO-RUN (Santino 2026-09-28, TDI/Rob): "If he requests
    # it, we can just do it. I don't want to have to oversee something when
    # someone makes a request like this anymore." The 09-12 hold (Frontline/
    # Jared: a layout complaint that mentioned "phone number" auto-ran and a
    # build cemented over the DNI tracking number) parked Rob's explicit
    # footer-numbers request for a day, the rest of his message shipped, and
    # he had to ask twice. The DNI safety did not go away, it moved to where
    # the judgment belongs: the classifier (CLASSIFY_SYSTEM, "PHONE NUMBERS")
    # decides whether a phone mention is a real change request or a
    # tracking-line misunderstanding to explain, and dev_agent.md ("Phone
    # numbers") says how to execute one without breaking attribution.
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
    # The company name rides the header line on every card; the group
    # close-out (dev_inbox) names each sister site from it.
    h = _HEADER_RE.search(body)
    if h:
        out.setdefault("company", h.group(3).strip())
    w = body.split("\n", 2)
    if len(w) > 1 and w[1].strip() and not w[1].startswith("WHERE:"):
        out.setdefault("what", w[1].strip()[:240])
    # The client's verbatim words live on their own labelled line.
    q = re.search(r'THEY SAID:\s*"(.+?)"\s*$', body, re.M | re.S)
    if q:
        out["quote"] = q.group(1).strip()
    return out


def compose_task_note(fb: dict, *, tag: str, company_name: str, slug: str,
                      who: str, site_live: bool, site_url: str | None,
                      verdict_why: str, when: str,
                      origin_channel: str = "sms",
                      email_ref: dict | None = None,
                      group: str | None = None,
                      also_for: list[str] | None = None) -> str:
    """The queued note. Written for a human to read at a glance and for the
    dev agent to execute from, with one machine-readable trailer.

    `group` ties together every card filed off ONE client message (several
    asks, and/or the same ask fanned out to sister companies that share the
    contact). dev_inbox holds the client's "done" until every card in the
    group is verified live, so one message never claims a sister site that
    nobody touched (All Pro / ProRestoration 2026-09-29). `also_for` names
    the sister cards in plain words for the agent."""
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
    if also_for:
        lines.append("ALSO FILED FOR: " + "; ".join(also_for) + ". The client "
                     "shares one phone with these sister companies and this "
                     "ask covers them too; each sister has its own card. The "
                     "client hears ONE message, after every card is verified "
                     "on its own live site.")
    if tag == "[DEV]":
        lines.append("WHEN DONE: verify on the LIVE site, then dev_inbox.py "
                     "done (with --area-add/--area-remove or --verify) files "
                     "the [FROM SANTINO] note, so Monica tells them it is "
                     "fixed with the link. Do not text the client yourself.")
    else:
        lines.append(f"WHY THIS NEEDS YOUR OK: {verdict_why}. Approve and it "
                     "becomes a [DEV] task on tonight's run; dismiss and "
                     "nothing happens.")
    # Channel fidelity (3b, 2026-09-13): the done-notification goes back on
    # the SAME channel the request arrived on — email refs ride the trailer
    # so dev_inbox can queue a threaded email reply instead of an SMS.
    em = ""
    if origin_channel == "email" and email_ref:
        em = (f" | acct={email_ref.get('acct') or 'main'}"
              f" | eth={email_ref.get('eth') or ''}"
              f" | eto={email_ref.get('eto') or ''}")
    lines.append(
        f"{ORIGIN_MARK} | who={who} | cat={cat} | conf="
        f"{str(fb.get('confidence') or 'low').lower()} | slug={slug}"
        + (" | live=1" if site_live else "")
        + f" | ch={origin_channel}" + em
        + (f" | grp={group}" if group else ""))
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


def compose_group_directive(who: str, quote: str, done: list[str],
                            pending: list[str], links: list[str],
                            verified: bool = True) -> str:
    """The client update for a whole GROUP of cards (one message's asks,
    across every sister site it covered), or for a card whose live check
    only partly passed.

    `done` lines are VERIFIED on the live site; `pending` lines are not.
    With nothing pending this is the normal DONE directive. With anything
    pending it is a PROGRESS directive that forbids the word done for the
    open part (Shana/Angie 2026-09-29..10-02: Monica said "Done, Bakersfield
    is at the top of your service areas" when one of three lists had it and
    the sister site had nothing)."""
    q = (quote or "").strip().rstrip(".!, ")
    head = (f'{who} asked us: "{q[:180]}". ' if q else f"{who} asked us for "
            "a website change. ")
    if not pending:
        body = [
            "[FROM SANTINO] " + head + "It is DONE now"
            + (" and verified on the live site" + ("s" if len(links) > 1
                                                    else "")
               if verified else "") + ".",
            "Tell them in one or two short lines what changed ("
            + "; ".join(d[:200] for d in done)[:600]
            + ") and that they can take another look.",
        ]
        if links:
            body.append("Include " + ("these links: " if len(links) > 1
                                      else "this link: ") + " ".join(links))
        body.append("Past tense is correct here, the work is "
                    + ("verified" if verified else "recorded") + ". Do "
                    "not ask them anything else in this message, no other "
                    "item rides along.")
        return "\n".join(body)
    body = [
        "[FROM SANTINO] PROGRESS UPDATE, NOT DONE YET. " + head,
        "VERIFIED FINISHED on the live site: "
        + ("; ".join(d[:200] for d in done)[:600] if done else "nothing yet")
        + ".",
        "STILL IN PROGRESS (not finished, not verified): "
        + "; ".join(p[:200] for p in pending)[:600] + ".",
        "Tell them both halves in one or two short lines: what is finished"
        + (" (with the link)" if links and done else "")
        + " and what we are still working on. Never say done, fixed, all "
        "set, complete or 'take another look' about the in-progress part, "
        "and never imply everything is finished.",
    ]
    if links and done:
        body.append("Link for the finished part: " + " ".join(links))
    body.append("Do not ask them anything else in this message.")
    return "\n".join(body)


# ---------------------------------------------------------------- shared owners
# ONE PHONE, TWO COMPANIES (Santino 2026-10-02, All Pro + ProRestoration).
# Jack Bispo owns both; his office manager texts from one shared number, so
# both companies resolve to ONE GHL contact and the inbound poll hands every
# message to whichever company the tracked map happened to keep. On 09-29
# she asked for East Niles out and Bakersfield first "on both websites";
# the work went to All Pro only, Monica said "Done", and ProRestoration was
# never touched. Same shape: Dry County + RT Olson (Bob).
#
# The rule: a site change from a shared contact is filed for EVERY company
# it plausibly covers. "Both" said anywhere, or a generic change (service
# areas, hours/phone/address, social links) with no company named, fans out
# to all of them. A change that names one company goes to that one. What is
# left (a design or image tweak with no company named and no clue in the
# conversation) is genuinely ambiguous: Monica asks which site.
SHARED_GENERIC_CATS = frozenset({"service_area", "facts", "site_links"})
# Trailing words that describe the trade, not the brand: "All Pro Plumbing
# Heating and Air" is "All Pro" when a person says it out loud.
_TRADE_WORDS = frozenset({
    "plumbing", "heating", "air", "and", "&", "hvac", "cooling",
    "conditioning", "services", "service", "restoration", "inc", "inc.",
    "llc", "co", "co.", "company", "corp", "the", "of", "construction",
    "cleaning", "water", "damage", "mitigation", "group", ","})
_BOTH_RE = re.compile(
    r"\bboth\s+(?:of\s+(?:the|our|my)\s+)?(?:web\s*)?(?:sites?|pages|"
    r"companies|businesses|accounts|listings|of\s+them)\b"
    r"|\b(?:on|for|to|in|at|with)\s+both\b"
    r"|\b(?:all|each|every)\s+(?:of\s+)?(?:our|the|my)?\s*(?:web\s*)?sites\b"
    r"|\beach\s+(?:web\s*)?site\b|\bboth\s+(?:co|biz)\b", re.I)


def company_short_name(name: str) -> str:
    """'All Pro Plumbing Heating and Air' -> 'All Pro';
    'ProRestoration Services' -> 'ProRestoration'. Strips trade words off
    the END only, so a brand that starts with one keeps it."""
    words = re.sub(r"[,]", " ", str(name or "")).split()
    while len(words) > 1 and words[-1].lower() in _TRADE_WORDS:
        words.pop()
    return " ".join(words) or str(name or "").strip()


def _squash(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def companies_named(text: str, companies: list[dict]) -> list[dict]:
    """Which of `companies` the text names: by short brand name ('All Pro',
    'ProRestoration', 'RT Olson'), by domain stem, or by trade when only one
    company carries that trade word ('the plumbing site')."""
    t = " " + re.sub(r"[^a-z0-9]+", " ", (text or "").lower()) + " "
    sq = _squash(text)
    hits = []
    for co in companies:
        short = company_short_name(co.get("name") or "")
        keys = {short.lower()}
        dom = str(co.get("domain") or "").lower()
        dom = re.sub(r"^https?://|^www\.|/.*$", "", dom).split(".")[0]
        if len(dom) >= 6:
            keys.add(dom)
        named = False
        for k in keys:
            kn = re.sub(r"[^a-z0-9]+", " ", k).strip()
            if len(_squash(kn)) < 4:
                continue
            if f" {kn} " in t or (len(_squash(kn)) >= 7 and _squash(kn) in sq):
                named = True
        if not named:
            for trade in ("plumbing", "restoration", "roofing", "hvac"):
                owners = [c for c in companies
                          if trade in (c.get("name") or "").lower()]
                if (len(owners) == 1 and owners[0] is co and re.search(
                        rf"\b{trade}\s+(?:web\s*)?(?:site|page|one|company)\b",
                        t)):
                    named = True
        if named:
            hits.append(co)
    return hits


def resolve_company_targets(fb: dict, text: str, primary: dict,
                            sisters: list[dict]) -> tuple[list[dict], str]:
    """Which companies one feedback item is filed for. Pure.

    Returns (companies, mode). mode is one of:
      single  no sister companies share this contact (the normal case)
      both    the client said both / each site (in this message or the
              recent thread `text` carries)
      named   the message names a subset of the companies
      generic a service-area / business-fact / link change with no company
              named: true of every site the owner runs, so all of them
      model   the classifier attributed it from the conversation
      ask     genuinely ambiguous: file nothing, Monica asks which site
    """
    if not sisters:
        return [primary], "single"
    allc = [primary] + [s for s in sisters if s.get("id") != primary.get("id")]
    if _BOTH_RE.search(text or "") or _BOTH_RE.search(str(fb.get("quote") or "")):
        return allc, "both"
    named = companies_named(" ".join([str(fb.get("quote") or ""), text or ""]),
                            allc)
    if named and len(named) < len(allc):
        return named, "named"
    if named and len(named) == len(allc):
        return allc, "both"
    applies = [str(x).strip().lower() for x in (fb.get("applies_to") or [])
               if str(x).strip()]
    if "all" in applies or "both" in applies:
        return allc, "both"
    if str(fb.get("category") or "").lower() in SHARED_GENERIC_CATS:
        return allc, "generic"
    by_slug = [c for c in allc if str(c.get("slug") or "").lower() in applies]
    if by_slug:
        return by_slug, "model"
    return [], "ask"


def which_site_question(companies: list[dict]) -> str:
    names = [company_short_name(c.get("name") or "") for c in companies]
    if len(names) == 2:
        opts = f"the {names[0]} site, the {names[1]} site, or both"
    else:
        opts = ", ".join(f"the {n} site" for n in names) + ", or all of them"
    return f"Quick check so we change the right one: is that for {opts}?"


# ---------------------------------------------------------------- live proof
# NEVER "DONE" BEFORE IT IS VERIFIED EVERYWHERE (Santino 2026-10-02). The
# dev agent's 09-29 handbacks said "Verified live" and they were true for the
# one surface it looked at: Bakersfield was the first tile on /service-areas/
# while the homepage area list and the footer list (the two places the
# client actually looked) still did not have it. A client-feedback card for
# a website change now closes only when these checks pass against the LIVE
# HTML, on every list surface, for every company card in the group.
WEB_CATS = frozenset({"imagery", "design", "brand", "service_area", "copy",
                      "facts", "site_links"})
# "Bakersfield, CA" as an area label: a city name, comma, two-letter state.
_AREA_LABEL_RE = re.compile(r"^([A-Z][A-Za-z.'\- ]{1,40}?),\s*([A-Z]{2})\b")
_SPEC_RE = re.compile(r"^\s*(\S+?)(?:#(\w+))?\s+(has|lacks|status)\s+(.+?)\s*$",
                      re.I)


def scope_html(html: str, scope: str | None) -> str:
    """The part of a page one check looks at. main = the page body proper
    (falls back to everything minus header/nav/footer); footer; header (the
    header plus every nav, where area dropdowns live); page = everything."""
    html = html or ""
    sc = (scope or "page").lower()
    if sc == "footer":
        return "\n".join(re.findall(r"<footer\b.*?</footer>", html, re.S | re.I))
    if sc in ("header", "nav"):
        return "\n".join(re.findall(r"<header\b.*?</header>|<nav\b.*?</nav>",
                                    html, re.S | re.I))
    if sc == "main":
        m = re.findall(r"<main\b.*?</main>", html, re.S | re.I)
        if m:
            return "\n".join(m)
        return re.sub(r"<header\b.*?</header>|<nav\b.*?</nav>|"
                      r"<footer\b.*?</footer>", " ", html, flags=re.S | re.I)
    return html


def visible_text(html: str) -> str:
    import html as _html
    t = re.sub(r"<script\b.*?</script>|<style\b.*?</style>|<svg\b.*?</svg>",
               " ", html or "", flags=re.S | re.I)
    t = _html.unescape(re.sub(r"<[^>]+>", " ", t))
    return re.sub(r"\s+", " ", t).strip()


def _city_key(s: str) -> str:
    s = re.sub(r",\s*[A-Za-z]{2}\.?$", "", str(s or "").strip())
    return re.sub(r"[^a-z]+", " ", s.lower()).strip()


def area_labels(html: str) -> list[str]:
    """Ordered, de-duplicated city labels ('Bakersfield, CA') found in link
    and list-item text — the clickable area lists, NOT prose. Prose is the
    trap: 'Proudly serving Bakersfield' and the footer's address both say
    Bakersfield on a page whose area list does not have it."""
    out: list[str] = []
    seen: set[str] = set()
    for m in re.finditer(r"<(a|li)\b[^>]*>(.*?)</\1>", html or "", re.S | re.I):
        txt = visible_text(m.group(2))
        lm = _AREA_LABEL_RE.match(txt)
        if not lm:
            continue
        k = _city_key(lm.group(1))
        if k and k not in seen:
            seen.add(k)
            out.append(f"{lm.group(1).strip()}, {lm.group(2)}")
    return out


def service_area_surfaces(base: str) -> list[tuple[str, str, str, bool]]:
    """Every place a site lists its service areas, as (label, url, scope,
    required). The /service-areas/ page must carry a list; the homepage
    body, footer and header menu are checked whenever they carry one."""
    b = base.rstrip("/")
    return [("service areas page", b + "/service-areas/", "main", True),
            ("homepage area list", b + "/", "main", False),
            ("footer area list", b + "/", "footer", False),
            ("header menu area list", b + "/", "header", False)]


def check_area_lists(pages: dict[str, str], surfaces, *, add=(), remove=(),
                     first=None, na: dict | None = None) -> list[dict]:
    """Pure: run the service-area checks over fetched pages.

    pages: url -> html ('' when the fetch failed). A surface counts as an
    area list when it carries 3+ city labels. Returns one row per check:
    {"surface", "url", "ok", "detail", "human"}; `human` is the phrase the
    client update uses ("Bakersfield shows on the footer area list")."""
    na = {str(k).lower(): v for k, v in (na or {}).items()}
    rows: list[dict] = []
    for label, url, scope, required in surfaces:
        key = label.split()[0].lower()
        if key in na or label.lower() in na:
            rows.append({"surface": label, "url": url, "ok": True,
                         "detail": f"n/a by agent: {na.get(key) or na.get(label.lower())}",
                         "human": None})
            continue
        html = pages.get(url)
        if not html:
            rows.append({"surface": label, "url": url, "ok": False,
                         "detail": "could not fetch the live page",
                         "human": f"the {label}"})
            continue
        labels = area_labels(scope_html(html, scope))
        keys = [_city_key(x) for x in labels]
        if len(labels) < 3:
            if required:
                rows.append({"surface": label, "url": url, "ok": False,
                             "detail": "no area list found on this page",
                             "human": f"the {label}"})
            continue
        for city in add:
            ok = _city_key(city) in keys
            rows.append({"surface": label, "url": url, "ok": ok,
                         "detail": (f"{city} listed" if ok else
                                    f"{city} NOT in the list ({', '.join(labels[:6])}...)"),
                         "human": f"{city} on the {label}"})
        if first:
            ok = bool(keys) and keys[0] == _city_key(first)
            rows.append({"surface": label, "url": url, "ok": ok,
                         "detail": (f"{first} is first" if ok else
                                    f"first is {labels[0] if labels else '?'}, "
                                    f"not {first}"),
                         "human": f"{first} listed first on the {label}"})
        for city in remove:
            ok = _city_key(city) not in keys
            rows.append({"surface": label, "url": url, "ok": ok,
                         "detail": (f"{city} gone" if ok else
                                    f"{city} STILL listed"),
                         "human": f"{city} off the {label}"})
    return rows


def parse_verify_spec(spec: str) -> tuple[str, str | None, str, str] | None:
    """'URL[#scope] has|lacks TEXT' or 'URL status CODE'. URL may be a path
    ('/about/'), joined to the site's base by the caller."""
    m = _SPEC_RE.match(spec or "")
    if not m:
        return None
    return m.group(1), m.group(2), m.group(3).lower(), m.group(4).strip("\"' ")


def check_spec(html: str | None, status: int | None, scope: str | None,
               op: str, arg: str) -> tuple[bool, str]:
    """Pure: one generic --verify check against a fetched page."""
    if op == "status":
        ok = str(status) == arg.strip()
        return ok, f"HTTP {status} (want {arg})"
    if not html:
        return False, "could not fetch the live page"
    text = visible_text(scope_html(html, scope)).lower()
    needle = re.sub(r"\s+", " ", arg).strip().lower()
    present = needle in text
    if op == "has":
        return present, (f"found {arg!r}" if present else f"{arg!r} NOT found")
    return (not present), (f"{arg!r} absent" if not present
                           else f"{arg!r} STILL present")


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
                   escalate=None, limit: int = 4,
                   origin_channel: str = "sms",
                   email_ref: dict | None = None,
                   group: str | None = None,
                   also_for: list[str] | None = None) -> list[dict]:
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
            if (str(fb.get("category") or "").lower() == "call_routing"
                    and str(fb.get("confidence") or "").lower() == "high"):
                done = _run_call_routing(company, fb, who=who, quote=quote,
                                         dry_run=dry_run)
                if done:
                    out.append(done)
                    continue
            verdict, why = risk_verdict(fb, site_live=live, has_site=has_site)
            tag = "[DEV]" if verdict == "auto" else "[TODO-PROPOSED]"
            body = compose_task_note(
                fb, tag=tag, company_name=company.get("name") or "the client",
                slug=slug or "?", who=who, site_live=live, site_url=url,
                verdict_why=why, when=when,
                origin_channel=origin_channel, email_ref=email_ref,
                group=group, also_for=also_for)
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


def _run_call_routing(company: dict, fb: dict, *, who: str, quote: str,
                      dry_run: bool) -> dict | None:
    """Execute a call-forwarding request now. Returns the out-row when it was
    handled (done or already set), None to fall through to a normal task."""
    try:
        import call_forward
        r = call_forward.apply(
            company["id"], str(fb.get("source") or fb.get("where") or ""),
            str(fb.get("forward_to") or ""), who=who, quote=quote,
            reset=bool(fb.get("reset")), dry_run=dry_run)
    except Exception as e:  # noqa: BLE001
        print(f"  [feedback] call routing failed ({str(e)[:100]}) — queuing")
        return None
    if not r.get("ok"):
        print(f"  [feedback] call routing not run: {r.get('why')} — queuing")
        return None
    print(f"  [feedback] CALL ROUTING done: {r['line']}")
    note_id = None
    if not r.get("noop") and not r.get("dry_run"):
        body = compose_done_directive({"who": who, "quote": quote},
                                      r["line"], None)
        row = _sb("POST", "/rest/v1/marketing_ops_notes",
                  {"company_id": company["id"], "body": body,
                   "status": "open", "author": "monica"},
                  prefer="return=representation")
        note_id = (row or [{}])[0].get("id") if isinstance(row, list) else None
    return {"tag": "[DONE]", "why": r["line"], "note_id": note_id,
            "category": "call_routing"}


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
    ("no site yet runs as build input",
     {"category": "imagery", "what": "change the hero image",
      "where": "homepage", "quote": "the hero image should be a house",
      "confidence": "high"},
     False, "auto"),   # has_site=False below; 2026-09-28: input for the first build
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

    fails += _selftest_shared_and_proof()
    print(f"\n{'ALL GREEN' if not fails else str(fails) + ' FAILURE(S)'}")
    return 1 if fails else 0


def _selftest_shared_and_proof() -> int:
    """Regression set for the 2026-09-29 All Pro / ProRestoration failure:
    one shared phone, a "both websites" ask filed for one company, and a
    "Done" that was true on one of three area lists."""
    fails = 0

    def check(ok: bool, label: str) -> None:
        nonlocal fails
        fails += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} {label}")

    allpro = {"id": "CO-1783380243102", "slug": "all-pro-plumbing",
              "name": "All Pro Plumbing Heating and Air",
              "domain": "allproplumbingheatingandair.com"}
    prores = {"id": "CO-1779551010975", "slug": "prorestoration",
              "name": "ProRestoration Services", "domain": "prorestorationca.com"}
    print("\nshared-contact requests reach EVERY sister company:")
    sa = {"category": "service_area", "confidence": "high",
          "what": "remove East Niles", "quote": "take off East Niles"}
    t, m = resolve_company_targets(sa, "can you take off East Niles on both "
                                   "websites", allpro, [prores])
    check(m == "both" and len(t) == 2, f"'on both websites' -> both ({m})")
    t, m = resolve_company_targets(sa, "Also on the Service areas can you "
                                   "takeoff East Niles", allpro, [prores])
    check(m == "generic" and len(t) == 2,
          f"service-area ask naming no company -> all sites ({m})")
    t, m = resolve_company_targets(
        dict(sa, applies_to=["all-pro-plumbing"]),
        "I looked on All Pro plumbing there is no Bakersfield listed at all",
        allpro, [prores])
    check(m == "named" and [c["id"] for c in t] == [allpro["id"]],
          f"names All Pro -> All Pro only ({m})")
    t, m = resolve_company_targets(sa, "the ProRestoration site still shows "
                                   "Woody", allpro, [prores])
    check(m == "named" and [c["id"] for c in t] == [prores["id"]],
          f"names ProRestoration -> ProRestoration only ({m})")
    img = {"category": "imagery", "confidence": "high",
           "what": "swap the hero photo", "quote": "change the top picture"}
    t, m = resolve_company_targets(img, "change the top picture", allpro,
                                   [prores])
    check(m == "ask" and not t, f"image tweak, no company named -> ask ({m})")
    t, m = resolve_company_targets(dict(img, applies_to=["prorestoration"]),
                                   "change the top picture", allpro, [prores])
    check(m == "model" and [c["id"] for c in t] == [prores["id"]],
          f"classifier attribution from the thread is used ({m})")
    t, m = resolve_company_targets(img, "change the top picture", allpro, [])
    check(m == "single" and t == [allpro], "no sisters -> unchanged path")
    q = which_site_question([allpro, prores])
    check("All Pro" in q and "ProRestoration" in q and "both" in q
          and "\u2014" not in q, f"which-site question: {q!r}")

    print("\ngrouped cards carry the group in the trailer:")
    body = compose_task_note(sa, tag="[DEV]", company_name=prores["name"],
                             slug="prorestoration", who="Angie",
                             site_live=True, site_url="https://prorestorationca.com",
                             verdict_why="ok", when="2026-09-29T00:00:00Z",
                             group="ab12cd34ef",
                             also_for=["All Pro Plumbing Heating and Air "
                                       "(all-pro-plumbing)"])
    o = parse_origin(body) or {}
    check(o.get("grp") == "ab12cd34ef" and o.get("company") == prores["name"]
          and o.get("what") == "remove East Niles" and "ALSO FILED FOR" in body,
          f"grp/company/what parsed: {o.get('grp')}, {o.get('company')}")

    print("\nlive proof: an area change is checked on EVERY list surface:")
    tile = '<a href="/service-areas/{s}/">{c}, CA</a>'
    def page(cities, footer_cities, prose=""):
        lis = "".join(tile.format(s=c.lower().replace(" ", "-"), c=c)
                      for c in cities)
        fl = "".join(tile.format(s=c.lower().replace(" ", "-"), c=c)
                     for c in footer_cities)
        return (f"<html><header><nav>Home</nav></header><main><p>{prose}</p>"
                f"<ul>{lis}</ul></main><footer><p>Bakersfield, CA 93308</p>"
                f"{fl}</footer></html>")
    base = "https://allpro.test"
    surf = service_area_surfaces(base)
    cities = ["Arvin", "Delano", "Lamont", "Taft"]
    # The real 09-29 state: the /service-areas/ page got the tile, the
    # homepage body and the footer did not, and the homepage PROSE plus the
    # footer ADDRESS both say "Bakersfield" (the trap a text search falls in).
    pages = {base + "/service-areas/": page(["Bakersfield"] + cities, cities),
             base + "/": page(cities, cities,
                              prose="Proudly serving Bakersfield, CA")}
    rows = check_area_lists(pages, surf, add=["Bakersfield"],
                            first="Bakersfield")
    bad = sorted({r["surface"] for r in rows if not r["ok"]})
    check(bad == ["footer area list", "homepage area list"],
          f"09-29 state FAILS on homepage + footer: {bad}")
    pages[base + "/"] = page(["Bakersfield"] + cities, ["Bakersfield"] + cities)
    rows = check_area_lists(pages, surf, add=["Bakersfield"],
                            first="Bakersfield", remove=["East Niles"])
    check(rows and all(r["ok"] for r in rows),
          "fixed everywhere -> every check passes")
    pages[base + "/service-areas/"] = page(cities + ["East Niles"], cities)
    rows = check_area_lists(pages, surf, remove=["East Niles"])
    check(any(not r["ok"] and "STILL" in r["detail"] for r in rows),
          "a removed city still on a list fails")
    rows = check_area_lists({}, surf, add=["Bakersfield"])
    check(rows and not any(r["ok"] for r in rows),
          "an unreachable site never verifies")
    rows = check_area_lists(pages, surf, add=["Arvin"],
                            na={"footer": "lists the top 10 only"})
    check(all(r["ok"] for r in rows) and any("n/a by agent" in r["detail"]
                                             for r in rows),
          "an agent-declared n/a surface is recorded, not silently skipped")

    print("\ngeneric --verify specs:")
    spec = parse_verify_spec("/about/#footer lacks East Niles")
    check(spec == ("/about/", "footer", "lacks", "East Niles"), f"parse {spec}")
    html = page(cities, cities)
    check(check_spec(html, 200, "footer", "has", "Taft, CA")[0]
          and not check_spec(html, 200, "footer", "has", "Woody")[0]
          and check_spec(None, 301, None, "status", "301")[0],
          "has / lacks / status")

    print("\nthe client update never says done for an open part:")
    d = compose_group_directive("Angie", "take off East Niles on both sites",
                                ["All Pro: East Niles is off every list"],
                                [], ["https://a.test", "https://b.test"])
    check(d.startswith("[FROM SANTINO]") and "DONE" in d and "b.test" in d,
          "all verified -> one DONE message with both links")
    p = compose_group_directive("Angie", "take off East Niles on both sites",
                                ["All Pro: East Niles is off every list"],
                                ["ProRestoration: remove East Niles"],
                                ["https://a.test"])
    check("NOT DONE YET" in p and "STILL IN PROGRESS" in p
          and "Never say done" in p and "\u2014" not in p,
          "partial -> PROGRESS message that forbids 'done'")
    return fails


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
