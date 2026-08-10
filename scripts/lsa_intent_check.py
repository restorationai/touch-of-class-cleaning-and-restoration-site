#!/usr/bin/env python3
"""lsa_intent_check.py - mine STORED call material for LSA intent (Santino 2026-08-09).

Step 2 of 3 in the LSA-intent flow:

  1. DETECT (lsa_detect.py, exists): finds clients whose LSA campaigns are
     already live and stamps integration_settings.lsa.
  2. TRANSCRIPT CHECK (THIS script): for active Rank AI clients with no
     recorded lsa_intent and no ENABLED LSA campaign, scan what we already
     have on file from their calls (clients/{slug}/calls/*.md, ops-journal.md,
     intel/*.md, clients/_ops/meeting-intel/{slug}.md, marketing_ops_notes
     rows). If the client clearly stated want / don't-want / later, record
     integration_settings.lsa_intent with the quote as evidence, so Monica
     never asks a question the client already answered on a call.
     Never calls the Fathom API - stored material only.
  3. ASK (client_ops_sync checklist-lsa-intent, exists): Monica asks the
     client conversationally - but only for clients steps 1-2 left unset,
     and only after a human approves the [TODO-PROPOSED] note this script
     files ("LSA intent unknown"). Intent questions stay human-approved.

Safe to re-run (idempotent): skips any company that already has lsa_intent
(dict or legacy string), an ENABLED lsa.campaign_status, or a previously
filed "LSA intent unknown" note (any status - a dismissed note is a human
decision, not something to re-litigate). Recording writes follow the
read-modify-write pattern from lsa_detect.py / client_ops_sync.py: fresh GET
of integration_settings, mutate ONLY lsa_intent, PATCH the whole object -
sibling keys are never clobbered. The written dict carries the new shape
{decision, source, evidence, recorded_at} PLUS an "answer" mirror of
decision (and decided_at), because setup_ledger.py and client_concierge.py
both read li.get("answer") - without the mirror a recorded "yes" would never
surface the LSA-setup card.

False-positive guards:
  - a signal only counts when the surrounding text ties it to a call
    (call files / meeting intel are inherently calls; journals and ops
    notes need call language in the window);
  - files whose header covers MULTIPLE companies (e.g. all-pro-plumbing's
    meeting intel spans All Pro + ProRestoration, both Jack Bispo's) only
    count when the evidence line names THIS client - otherwise the signal
    is ambiguous and becomes the human-approved note instead;
  - conflicting signals (yes and no both found) also fall back to the note.

Usage: python3 scripts/lsa_intent_check.py [--dry-run]
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from client_ops_sync import _sb, slug_map  # noqa: E402

CLIENTS = ROOT / "clients"
MEETING_INTEL = CLIENTS / "_ops" / "meeting-intel"
NOTE_MARKER = "LSA intent unknown for"
WINDOW = 170  # chars of context each side of a mention

MENTION_RE = re.compile(
    r"\b(?:lsa|local\s+services?\s+ads?|google\s+guaranteed|google\s+screened)\b",
    re.I)
# Order matters: NO is checked before YES so "not interested" never reads as
# "interested in". LATER before YES so "revisit after launch" stays "later".
NO_RE = re.compile(
    r"(?:doesn'?t\s+want|does\s+not\s+want|don'?t\s+want|not\s+interested|"
    r"no\s+interest|declined|said\s+no|\bno\s+to\s+(?:lsa|local)|passed?\s+on|"
    r"opt(?:ed)?\s+out|never\s+wants?)", re.I)
LATER_RE = re.compile(
    r"(?:\blater\b|revisit|not\s+(?:right\s+)?now|not\s+yet|hold\s+off|"
    r"circle\s+back|wait\s+until|down\s+the\s+road|"
    r"next\s+(?:month|quarter|year))", re.I)
YES_RE = re.compile(
    r"(?:said\s+yes|yes\s+to\s+(?:lsa|local)|wants?\s+(?:lsa|local|it|them|this|to\s+do)|"
    r"interested\s+in|sign(?:ed)?\s+up|go(?:ing)?\s+ahead|let'?s\s+do|"
    r"commit(?:ted|ment)|launch|activate\b|turn(?:ing)?\s+(?:it\s+)?on|"
    r"background\s+check\s+\w*\s*(?:started|begun|underway|completed)|"
    r"verification\s+(?:submitted|resubmitted|in\s+progress|underway)|"
    r"begin\s+now)", re.I)
# Ties a window to an actual conversation with the client.
CALLISH_RE = re.compile(
    r"(?:\bcall\b|kick-?off|meeting|they\s+said|he\s+said|she\s+said|"
    r"told\s+us|on\s+the\s+phone|fathom|commitment)", re.I)
STOP = {"llc", "inc", "restoration", "construction", "services", "service",
        "the", "of", "and", "co", "company", "24/7", "247"}


def _tokens(name: str) -> set:
    return {t for t in re.findall(r"[a-z0-9]+", (name or "").lower())
            if t not in STOP and len(t) > 2}


def _ints(co: dict) -> dict:
    ints = co.get("integration_settings") or {}
    if isinstance(ints, str):
        try:
            ints = json.loads(ints)
        except Exception:
            ints = {}
    return ints


def _squash(text: str) -> str:
    return " ".join((text or "").split())


def gather_material(slug: str | None, cid: str) -> list[tuple[str, str, bool]]:
    """(source_label, text, is_call_material) for everything stored on file."""
    items: list[tuple[str, str, bool]] = []
    if slug:
        d = CLIENTS / slug
        for f in sorted(d.glob("calls/*.md")):
            items.append((f"calls/{f.name}", f.read_text(errors="ignore"), True))
        oj = d / "ops-journal.md"
        if oj.exists():
            items.append(("ops-journal.md", oj.read_text(errors="ignore"), False))
        for f in sorted(d.glob("intel/**/*.md")):
            items.append((f"intel/{f.name}", f.read_text(errors="ignore"), False))
        mi = MEETING_INTEL / f"{slug}.md"
        if mi.exists():
            items.append((f"meeting-intel/{slug}.md",
                          mi.read_text(errors="ignore"), True))
    notes = _sb("GET", f"/rest/v1/marketing_ops_notes?company_id=eq.{cid}"
                "&select=body,status,created_at&order=created_at.asc") or []
    for n in notes:
        body = n.get("body") or ""
        if NOTE_MARKER in body:
            continue  # never scan our own filed note
        items.append((f"ops-note {str(n.get('created_at') or '')[:10]}",
                      body, False))
    return items


def other_company_in_header(header: str, target_name: str,
                            all_names: list[str]) -> str | None:
    """Name of ANOTHER company the file header covers, if any.

    A token only implicates another company when it is len>=5 AND not part
    of the target's own name - otherwise "All Pro Plumbing" in a header
    would implicate every other plumbing company on the roster.
    """
    low = header.lower()
    target_toks = _tokens(target_name)
    for name in all_names:
        if name == target_name:
            continue
        for t in _tokens(name):
            if (len(t) >= 5 and t not in target_toks
                    and re.search(rf"\b{re.escape(t)}\b", low)):
                return name
    return None


def scan(items: list[tuple[str, str, bool]], target_name: str,
         all_names: list[str]) -> list[dict]:
    hits = []
    want = _tokens(target_name)
    for label, text, is_call in items:
        header = text.splitlines()[0] if text else ""
        shared_with = (other_company_in_header(header, target_name, all_names)
                       if not label.startswith("ops-note") else None)
        for m in MENTION_RE.finditer(text):
            w = _squash(text[max(0, m.start() - WINDOW):m.end() + WINDOW])
            if NO_RE.search(w):
                sig = "no"
            elif LATER_RE.search(w):
                sig = "later"
            elif YES_RE.search(w):
                sig = "yes"
            else:
                sig = None
            attributed = bool(is_call or CALLISH_RE.search(w))
            # The window may spill into NEIGHBORING bullets that do name the
            # client (that is how All Pro's shared intel file first slipped
            # through) - so the names-this-client test is scoped to the
            # mention's OWN line, not the window.
            ls = text.rfind("\n", 0, m.start()) + 1
            le = text.find("\n", m.end())
            line = _squash(text[ls:le if le != -1 else len(text)]).lower()
            names_target = any(re.search(rf"\b{re.escape(t)}\b", line)
                               for t in want)
            ambiguous = bool(shared_with) and not names_target
            hits.append({"source": label, "signal": sig, "window": w,
                         "attributed": attributed, "ambiguous": ambiguous,
                         "shared_with": shared_with,
                         # wider slice used ONLY for the stored evidence
                         # quote, so a client's words near the window edge
                         # don't get clipped mid-quote
                         "ev_window": _squash(
                             text[max(0, m.start() - 300):m.end() + 300])})
    return hits


def record_intent(cid: str, decision: str, evidence: str, dry: bool) -> bool:
    """Read-modify-write on integration_settings, touching ONLY lsa_intent."""
    rows = _sb("GET", f"/rest/v1/companies?id=eq.{cid}"
               "&select=integration_settings") or []
    if not rows:
        return False
    ints = _ints(rows[0])
    if ints.get("lsa_intent"):
        print("    skip write: lsa_intent appeared since the scan started")
        return False
    now = datetime.now(timezone.utc).isoformat()
    ints["lsa_intent"] = {
        "decision": decision, "source": "call",
        "evidence": evidence[:200], "recorded_at": now,
        # compat mirrors: setup_ledger + client_concierge read answer/decided_at
        "answer": decision, "decided_at": now,
        "recorded_by": "lsa_intent_check",
    }
    if not dry:
        _sb("PATCH", f"/rest/v1/companies?id=eq.{cid}",
            {"integration_settings": ints})
    return True


def existing_note(cid: str) -> dict | None:
    rows = _sb("GET", f"/rest/v1/marketing_ops_notes?company_id=eq.{cid}"
               f"&body=like.{quote('*' + NOTE_MARKER + '*', safe='*')}"
               "&select=id,status,created_at") or []
    return rows[0] if rows else None


def file_note(cid: str, name: str, dry: bool) -> bool:
    body = (f"[TODO-PROPOSED] {NOTE_MARKER} {name} - no stated answer in "
            "stored call material. Approve to have Monica ask.")
    if not dry:
        _sb("POST", "/rest/v1/marketing_ops_notes",
            {"company_id": cid, "body": body})
    return True


def main() -> int:
    dry = "--dry-run" in sys.argv
    cos = _sb("GET", "/rest/v1/companies?status=ilike.active"
              "&select=id,name,plan,integration_settings") or []
    all_names = [c.get("name") or "" for c in cos]
    smap = slug_map()
    recorded, noted, skipped = 0, 0, 0

    for co in cos:
        name = (co.get("name") or "").strip()
        if (co.get("plan") or "").strip().lower() != "rank ai":
            continue
        if re.search(r"\btest\b", name, re.I):
            continue
        ints = _ints(co)
        if ints.get("lsa_intent"):
            continue  # already answered (dict or legacy string) - step done
        if ((ints.get("lsa") or {}).get("campaign_status")) == "ENABLED":
            continue  # LSA already live - intent is moot
        cid = co["id"]
        slug = smap.get(cid)
        print(f"\n== {name} ({cid}, slug={slug or '?'})")

        items = gather_material(slug, cid)
        print(f"   material: {len(items)} source(s): "
              + (", ".join(lbl for lbl, _, _ in items) or "none"))
        hits = scan(items, name, all_names)
        for h in hits:
            flags = "".join([
                f" [{h['signal'] or 'no-signal'}]",
                "" if h["attributed"] else " [not-call-attributed]",
                f" [shared file w/ {h['shared_with']}, ambiguous]"
                if h["ambiguous"] else ""])
            print(f"   - {h['source']}{flags}: \"{h['window'][:200]}\"")

        solid = [h for h in hits
                 if h["signal"] and h["attributed"] and not h["ambiguous"]]
        decisions = {h["signal"] for h in solid}
        if len(decisions) == 1:
            decision = decisions.pop()
            # Best evidence = the window closest to the client's own words,
            # not merely the first regex hit - and the 200-char trim must
            # keep the quote, not cut it off (head-first trimming lost Roy's
            # THEY SAID quote on the first live run).
            def _ev_score(h: dict) -> int:
                w = h["window"].lower()
                return (3 * bool(re.search(r"they said|said yes|he said|she said", w))
                        + 2 * ('"' in h["window"])
                        + 1 * ("commitment" in w))
            sq = max(solid, key=_ev_score)["ev_window"]
            m_ = re.search(r"they said|said yes|he said|she said", sq, re.I)
            ev = sq[max(0, m_.start() - 40):m_.start() + 160] if m_ else sq[:200]
            print(f"   VERDICT: {decision.upper()} - recording lsa_intent"
                  + (" (dry-run: not written)" if dry else ""))
            if record_intent(cid, decision, ev, dry):
                recorded += 1
            continue
        why = ("conflicting signals" if decisions else
               "LSA mentioned but no clear stated answer" if hits else
               "no LSA mention in stored call material")
        prior = existing_note(cid)
        if prior:
            print(f"   VERDICT: unknown ({why}) - note already filed "
                  f"{str(prior.get('created_at') or '')[:10]} "
                  f"[{prior.get('status')}], skipping")
            skipped += 1
            continue
        print(f"   VERDICT: unknown ({why}) - filing [TODO-PROPOSED] note"
              + (" (dry-run: not written)" if dry else ""))
        if file_note(cid, name, dry):
            noted += 1

    print(f"\nDone{' (dry-run, nothing written)' if dry else ''}: "
          f"{recorded} intent(s) recorded, {noted} note(s) filed, "
          f"{skipped} already-noted skip(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
