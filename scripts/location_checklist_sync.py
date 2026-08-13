#!/usr/bin/env python3
"""location_checklist_sync.py — the launch checklist's client asks (second-office
program, Santino 2026-08-13: "each step is both a task and a record").

Every company_locations row that is not yet 'live' carries a launch checklist
in its `checklist` jsonb column (written by the app's LocationsPanel; shape in
app-work migration 20260813200000): dba -> address -> gbp_created ->
verification -> live -> site_pages -> citations -> hub, each step an object
with a `done` flag plus that step's facts.

Three of those steps can only move when the CLIENT does something:

  dba           send a photo of the DBA filing for the new location
  address       what's the registered address? a lease or utility bill helps
  verification  complete Google's video/postcard verification (owner-only)

This script walks every non-live location and seeds ONE idempotent
marketing_action_plan `client_input` ask per location — for the EARLIEST
undone step that needs client input — via client_ops_sync.insert_plan_row
(find-or-create by action_key, pinned, title refreshed in place). Steps that
are our work (gbp_created, site_pages, citations, hub) never generate an ask;
because asks only fire when a client step is the earliest UNDONE step,
"verification only after gbp_created" falls out naturally, and a belt-and-
braces guard enforces it anyway.

One ask at a time per location: seeding step N retires the open asks for
every other client step of that location, and a step completing retires its
own ask on the next sweep — the same seed-key retire pattern setup_ledger
uses (PATCH status=planned -> resolved by action_key). Monica picks the asks
up natively from marketing_action_plan; nothing here touches
client_concierge.py.

Column-derived truth so we never ask for what we already hold: a row with a
street address counts as address-done even if nobody ticked the box, a row
with a gbp_location_id counts as gbp_created-done, status 'live' counts as
live-done.

STATE REGISTRY WATCHER (2026-08-13, Santino-approved: a pending state filing
must never be missed by human error). Any location whose dba step is NOT done
but shows a filing in flight (filed_at or a filing photo recorded, or a watch
already open) gets a nightly check of that state's PUBLIC business registry.
Watch state lives on the step itself: checklist.dba.watch =
{state, query, last_checked, last_result, status, seen}. On a NEW
active/approved record matching the query:

  * dba is marked done with the exact registered name(s), file number and
    approval date pulled from the registry; doc_url becomes the registry
    record URL (the client's filing photo moves to photo_url, never lost);
  * one marketing_work_log line ("Sioux City expansion: Iowa approved the
    registration") so the monthly summary picks it up for free;
  * one [FOR MONICA] marketing_ops_notes directive telling the client the
    good news (plain words, no ask), deduped forever by a per-location marker;
  * if none of the approved names carry the location's city (no
    "... of Sioux City" trade name), ONE decision card via insert_plan_row:
    corporate name as-is vs. filing the trade name first.

Per-state fetchers live in REGISTRY_FETCHERS — adding a state is one small
function returning normalized records. Iowa (the first): sos.iowa.gov's
Business Entities Search is a public ASP.NET form; a plain GET for the
VIEWSTATE + a form POST returns the results table server-side (verified
2026-08-13 — reCAPTCHA is loaded on the page but not enforced on the POST).
If a state ever blocks server-side fetching, the watch records
status 'needs-browser-agent' instead of failing the sweep.

Usage:
    python3 scripts/location_checklist_sync.py             # real run
    python3 scripts/location_checklist_sync.py --dry-run   # print only

Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (rank-ai/.env or CI secrets).
Runs daily from .github/workflows/client-ops-sync.yml.
"""
from __future__ import annotations

import argparse
import html as html_lib
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))

from client_ops_sync import _sb, action_key, insert_plan_row, load_env, slug_map
from work_log import work_log

# The full sequence, in launch order (mirrors the app's CHECKLIST_STEPS).
STEP_ORDER = ["dba", "address", "gbp_created", "verification", "live",
              "site_pages", "citations", "hub"]
# The steps only the client can move.
CLIENT_STEPS = ("dba", "address", "verification")


def _step_done(row: dict, step: str) -> bool:
    """Checklist truth first, then cheap column-derived truth."""
    st = ((row.get("checklist") or {}).get(step)) or {}
    if st.get("done"):
        return True
    if step == "address" and (row.get("address") or "").strip():
        return True
    if step == "gbp_created" and (row.get("gbp_location_id") or st.get("location_id")):
        return True
    if step == "live" and row.get("status") == "live":
        return True
    return False


# ================================================================ registry
# State registry watcher. One small fetcher per state; each takes the search
# query and returns (records, results_url) where every record is
# {file_number, name, status, type, legal_name, detail_url}. A state that
# cannot be read server-side raises RegistryBlocked — recorded on the watch
# as status 'needs-browser-agent', never a crash.

# A real browser UA: state sites 403 the default python-requests UA.
REGISTRY_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
               "AppleWebKit/537.36 (KHTML, like Gecko) "
               "Chrome/126.0.0.0 Safari/537.36")
IA_SEARCH_URL = "https://sos.iowa.gov/search/business/search.aspx"
STATE_NAMES = {"IA": "Iowa"}
# Legal-suffix noise stripped when deriving a default query from the company
# name; the query is deliberately BROAD (first two significant words) so a
# city-suffixed trade name ("Crew Restoration & Construction of Sioux City")
# still matches a "Crew Restoration" search. Override any time by editing
# checklist.dba.watch.query in the app or via SQL.
_QUERY_STOPWORDS = {"llc", "inc", "corp", "co", "ltd", "company",
                    "incorporated", "corporation", "the"}


class RegistryBlocked(Exception):
    """The registry refused a server-side read (CAPTCHA wall, login gate,
    layout change). The watch records 'needs-browser-agent' and moves on."""


def _strip_tags(fragment: str) -> str:
    return html_lib.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()


def _registry_search_ia(query: str) -> tuple[list[dict], str]:
    """Iowa SoS Business Entities Search (sos.iowa.gov — the PUBLIC search;
    filings.sos.iowa.gov Fast Track is login-walled). Classic ASP.NET
    WebForms: GET the form for __VIEWSTATE/__EVENTVALIDATION, POST the name
    search, parse the results table (Business No. | Name | Status | Type |
    Legal Name, one summary.aspx detail link per row). Verified working
    server-side 2026-08-13; reCAPTCHA's api.js is on the page but the POST
    is not enforced."""
    s = requests.Session()
    s.headers["User-Agent"] = REGISTRY_UA
    r = s.get(IA_SEARCH_URL, timeout=30)
    r.raise_for_status()

    def field(name: str) -> str:
        m = re.search(r'name="%s"[^>]*value="([^"]*)"' % re.escape(name), r.text)
        return m.group(1) if m else ""

    if not (field("__VIEWSTATE") and field("__EVENTVALIDATION")):
        raise RegistryBlocked("search form did not render (no VIEWSTATE) — "
                              "layout change or a CAPTCHA/login wall")
    r2 = s.post(IA_SEARCH_URL, timeout=30, data={
        "__VIEWSTATE": field("__VIEWSTATE"),
        "__VIEWSTATEGENERATOR": field("__VIEWSTATEGENERATOR"),
        "__EVENTVALIDATION": field("__EVENTVALIDATION"),
        "ctl00$ContentPlaceHolder$searchRadio": "searchName",
        "ctl00$ContentPlaceHolder$txtName": query,
        "ctl00$ContentPlaceHolder$hidSearchType": "name",
        "btnNumber": "",
    })
    r2.raise_for_status()
    m = re.search(r'<article id="mainArticle">(.*?)</article>', r2.text, re.S)
    if not m:
        raise RegistryBlocked("results page missing its article — blocked "
                              "or redesigned")
    records: list[dict] = []
    for rowm in re.finditer(r"<tr[^>]*>\s*(<td.*?)</tr>", m.group(1), re.S):
        cells = [_strip_tags(c) for c in
                 re.findall(r"<td[^>]*>(.*?)</td>", rowm.group(1), re.S)]
        if len(cells) < 5 or not cells[0].isdigit():
            continue  # header/footer rows
        link = re.search(r'href="(summary\.aspx\?q=[^"]+)"', rowm.group(1))
        records.append({
            "file_number": cells[0], "name": cells[1], "status": cells[2],
            "type": cells[3], "legal_name": cells[4],
            "detail_url": urljoin(IA_SEARCH_URL,
                                  html_lib.unescape(link.group(1))) if link else None,
        })
    return records, r2.url


def _registry_detail_ia(detail_url: str) -> dict:
    """Best-effort facts from an Iowa summary page: the filing date and every
    ACTIVE registered name (legal + fictitious/trade). Never raises — the
    results row already holds enough to act on."""
    out: dict = {}
    try:
        r = requests.get(detail_url, timeout=30,
                         headers={"User-Agent": REGISTRY_UA})
        r.raise_for_status()
        art = re.search(r'<article id="mainArticle">(.*?)</article>',
                        r.text, re.S)
        body = art.group(1) if art else r.text
        # Filing Date sits between its header row and the Chapter section;
        # values arrive as m/d/yyyy h:mm — the LAST date in the segment is
        # the filing date (order: Expiration | Effective | Filing).
        seg = re.search(r"Filing Date(.*?)(?:Chapter|Names)", body, re.S)
        if seg:
            dates = re.findall(r"(\d{1,2})/(\d{1,2})/(\d{4})", seg.group(1))
            if dates:
                mo, dy, yr = dates[-1]
                out["approved_at"] = f"{yr}-{int(mo):02d}-{int(dy):02d}"
        # Names table: rows of Type | Status | Modified | Name.
        names_seg = re.search(r">Names<(.*?)(?:Registered Agent|$)", body, re.S)
        if names_seg:
            names = []
            for rowm in re.finditer(r"<tr[^>]*>\s*(<td.*?)</tr>",
                                    names_seg.group(1), re.S):
                cells = [_strip_tags(c) for c in
                         re.findall(r"<td[^>]*>(.*?)</td>", rowm.group(1), re.S)]
                if len(cells) >= 4 and cells[1].lower() == "active" and cells[3]:
                    names.append(cells[3])
            if names:
                out["names"] = names
    except Exception as e:  # noqa: BLE001 — detail is a bonus, never a blocker
        print(f"    (registry detail fetch failed, using the results row: "
              f"{str(e)[:80]})")
    return out


# state code -> fetcher(query) -> (records, results_url). Add a state by
# adding one function above and one line here.
REGISTRY_FETCHERS = {"IA": _registry_search_ia}


def _default_registry_query(company_name: str) -> str:
    """Broad-on-purpose default: the first two significant words of the
    company name ('Crew Restoration & Construction' -> 'Crew Restoration'),
    so trade-name variants still match. checklist.dba.watch.query overrides."""
    words = [w for w in re.findall(r"[A-Za-z']+", company_name or "")
             if w.lower() not in _QUERY_STOPWORDS]
    return " ".join(words[:2]) or (company_name or "").strip()


def _record_matches(query: str, rec: dict) -> bool:
    """Every query word must appear in the record's registered or legal name
    — the state search is fuzzy-ish, so re-verify before acting."""
    hay = f"{rec.get('name', '')} {rec.get('legal_name', '')}".lower()
    return all(w in hay for w in query.lower().split())


def _patch_checklist(loc_id: str, checklist: dict, dry_run: bool) -> None:
    if dry_run:
        return
    _sb("PATCH", f"/rest/v1/company_locations?id=eq.{loc_id}",
        {"checklist": checklist,
         "updated_at": datetime.now(timezone.utc).isoformat()})


def _goodnews_note(cid: str, loc_id: str, label: str, state_name: str,
                   names: list[str], dry_run: bool) -> bool:
    """ONE [FOR MONICA] directive per location, ever (deduped across every
    status by the ref marker — resolving it must not re-file it). Plain
    English, no em dashes, share the news, ask for nothing."""
    # Parens stay out of the ilike pattern (PostgREST reserves them).
    token = f"loc-{loc_id}-dba-approved"
    marker = f"(ref {token})"
    existing = _sb("GET", "/rest/v1/marketing_ops_notes"
                   f"?company_id=eq.{cid}&body=ilike.*{token}*&select=id",
                   prefer="return=representation") or []
    if existing:
        return False
    registered = " and ".join(f'"{n}"' for n in names[:3]) or "the new name"
    body = (f"[FOR MONICA] Good news to pass along: {state_name} has approved "
            f"the business registration for the new {label} office. It is now "
            f"officially registered as {registered}. MONICA: tell the client "
            "the good news in plain words and congratulate them on the new "
            "location. This is a share, not an ask. Do not ask them for "
            f"anything in this message. {marker}")
    if dry_run:
        print(f"    [dry-run] would file [FOR MONICA] good-news note {marker}")
        return True
    _sb("POST", "/rest/v1/marketing_ops_notes", [{"company_id": cid, "body": body}])
    return True


def _watch_registry(row: dict, slug: str | None, company_name: str,
                    dry_run: bool) -> None:
    """Nightly registry check for one location. Mutates row['checklist'] in
    memory when the state approves, so the SAME sweep's ask-seeding sees dba
    as done and retires the open ask. Never raises: a registry problem is
    recorded on the watch, not thrown at the sweep."""
    cid, loc_id = row["company_id"], row["id"]
    label = (row.get("label") or row.get("city") or "the new location").strip()
    checklist = row.get("checklist") or {}
    dba = dict(checklist.get("dba") or {})
    if _step_done(row, "dba"):
        return
    watch = dict(dba.get("watch") or {})
    # A watch starts only once a filing is actually in flight (a filing date
    # or the filing photo recorded, or a watch already open) — a bare planned
    # location has nothing to watch; the dba ask owns that conversation.
    if not (dba.get("filed_at") or dba.get("doc_url") or watch):
        return
    state = (watch.get("state") or row.get("state") or "").strip().upper()
    if state not in REGISTRY_FETCHERS:
        print(f"  {label}: dba filing pending but no registry fetcher for "
              f"state {state or '?'} — add one to REGISTRY_FETCHERS")
        return
    query = (watch.get("query") or "").strip() or _default_registry_query(company_name)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    watch.update({"state": state, "query": query, "last_checked": now})

    try:
        records, results_url = REGISTRY_FETCHERS[state](query)
    except (RegistryBlocked, requests.RequestException) as e:
        watch.update({"status": "needs-browser-agent",
                      "last_result": f"fetch blocked: {str(e)[:160]}"})
        dba["watch"] = watch
        checklist["dba"] = dba
        row["checklist"] = checklist
        _patch_checklist(loc_id, checklist, dry_run)
        print(f"  {label}: registry watch ({state} '{query}') BLOCKED — "
              f"needs-browser-agent recorded: {str(e)[:120]}")
        return

    matches = [r for r in records if _record_matches(query, r)]
    active = [r for r in matches
              if (r.get("status") or "").strip().lower() == "active"]
    seen = set(watch.get("seen") or [])
    new_active = [r for r in active if r["file_number"] not in seen]
    watch["seen"] = sorted({r["file_number"] for r in matches} | seen)

    if not new_active:
        watch.update({"status": "watching",
                      "last_result": f"{len(records)} record(s), "
                                     f"{len(active)} active match(es), nothing new"})
        dba["watch"] = watch
        checklist["dba"] = dba
        row["checklist"] = checklist
        _patch_checklist(loc_id, checklist, dry_run)
        print(f"  {label}: registry watch ({state} '{query}') — "
              f"{watch['last_result']}")
        return

    # ---- the state approved the filing ---------------------------------
    state_name = STATE_NAMES.get(state, state)
    names: list[str] = []
    approved_at = None
    detail_url = None
    for rec in new_active:
        detail_url = detail_url or rec.get("detail_url")
        detail = _registry_detail_ia(rec["detail_url"]) if (
            state == "IA" and rec.get("detail_url")) else {}
        approved_at = approved_at or detail.get("approved_at")
        for n in detail.get("names") or [rec["name"], rec["legal_name"]]:
            if n and n not in names:
                names.append(n)
    approved_at = approved_at or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    file_numbers = [r["file_number"] for r in new_active]
    registry_url = detail_url or results_url
    city = (row.get("city") or label).strip().lower()
    city_named = [n for n in names if city and city in n.lower()]

    # The client's filing photo keeps living on the step — doc_url becomes
    # the registry record, the photo moves to photo_url.
    old_doc = dba.get("doc_url")
    if old_doc and "sos." not in old_doc and not dba.get("photo_url"):
        dba["photo_url"] = old_doc
    watch.update({"status": "approved",
                  "last_result": f"approved: {names[0]} (file {file_numbers[0]})"})
    dba.update({
        "done": True,
        "name": (city_named or names)[0],
        "names": names,
        "file_number": file_numbers[0],
        "approved_at": approved_at,
        "doc_url": registry_url,
        "watch": watch,
    })
    checklist["dba"] = dba
    row["checklist"] = checklist
    _patch_checklist(loc_id, checklist, dry_run)
    print(f"  {label}: {state_name} APPROVED the registration — "
          f"{', '.join(names)} (file {', '.join(file_numbers)})")

    # The record every other surface reads: monthly summary via work_log,
    # the client via Monica, the naming decision via the plan board.
    if not dry_run:
        work_log(cid, "setup", "location-step-done",
                 f"{label} expansion: {state_name} approved the registration "
                 f"({names[0]}, file {file_numbers[0]})",
                 evidence={"location_id": loc_id, "step": "dba",
                           "file_numbers": file_numbers, "names": names,
                           "registry_url": registry_url},
                 actor="system", source="location_checklist_sync registry watcher")
    else:
        print("    [dry-run] would write marketing_work_log line "
              f"('{label} expansion: {state_name} approved the registration')")
    _goodnews_note(cid, loc_id, label, state_name, names, dry_run)

    if not city_named:
        # Approved, but only under the corporate name — the Google listing
        # naming question is now live and it is a human call.
        loc_label = row.get("label") or city.title()
        insert_plan_row(
            cid, slug, f"loc-{loc_id}-listing-name",
            title=f"DECISION: {loc_label} listing name — corporate name "
                  f"as-is, or file the {state_name} trade name first",
            rationale=(
                f"{state_name} approved the registration for the {loc_label} "
                f"office, but only under {names[0]!r} — none of the approved "
                f"names carry the city. Option A, corporate name as-is: the "
                "Google Business Profile can be created today and the name "
                "matches the state record exactly, but the listing cannot "
                "legitimately carry the city (Google treats added geo terms "
                "as keyword stuffing when they are not part of the real-world "
                "name) and renaming later can trigger re-verification. "
                f"Option B, file the {state_name} trade name first "
                f"(e.g. '{names[0]} of {loc_label}'): the listing then "
                "carries the city legitimately and matches how locals "
                "search, but it adds a state filing fee plus processing time "
                "and pushes the GBP creation date out. Registry record: "
                f"{registry_url}"),
            action_type="gbp_fix", target=f"gbp:{slug}" if slug else None,
            impact="high", effort="low", dry_run=dry_run)


def _retire(cid: str, seed: str, dry_run: bool) -> None:
    """Same pattern as setup_ledger: an open ask resolves itself when its
    step no longer needs the client (or another step's ask takes the slot)."""
    if dry_run:
        return
    _sb("PATCH", "/rest/v1/marketing_action_plan"
        f"?company_id=eq.{cid}&action_key=eq.{action_key(cid, seed)}"
        "&status=eq.planned", {"status": "resolved"})


def _ask_for(step: str, label: str) -> tuple[str, str]:
    """(title, rationale) for one client step. Client-facing wording rules:
    plain words, no em dashes, one question."""
    if step == "dba":
        return (
            f"ASK CLIENT: send a photo of the DBA filing for the new "
            f"{label} location",
            f"They are opening a second office in {label} and the first "
            "record we need on file is the DBA (doing-business-as) "
            "registration for the new location. MONICA: one plain question. "
            "If they have already filed it, a photo of the stamped filing "
            "texted back is perfect. If they have not filed yet, ask what "
            "name they plan to register it under so we can line everything "
            "up (Google listing, website pages, directories) to match it "
            "exactly.")
    if step == "address":
        return (
            f"ASK CLIENT: what's the registered address for the new "
            f"{label} location? A lease or utility bill photo helps",
            f"Their DBA for the {label} office is recorded and the next "
            "thing Google requires for the new listing is a real street "
            "address. MONICA: ask what's the registered address for the new "
            "location, and mention that a photo of a lease or utility bill "
            "helps because Google's verification usually asks for proof the "
            "business operates there. A texted photo is fine. Until we have "
            "the address in writing we cannot create the Google listing.")
    return (
        f"ASK CLIENT: complete Google's verification for the new {label} "
        "listing",
        f"The Google Business Profile for their {label} office exists but "
        "Google will only show it once the OWNER completes verification "
        "(usually a short video walkthrough or a mailed postcard code). We "
        "cannot do this step for them. MONICA: ask them to finish the "
        "verification Google is prompting for on the new listing and to "
        "tell us which method Google offered, so we know when to expect it "
        "to go live.")


def sync_location(row: dict, slug: str | None, dry_run: bool) -> str | None:
    """Seed/keep the one open ask for this location. Returns the step asked
    for (or None when no client step is the earliest undone one)."""
    cid, loc_id = row["company_id"], row["id"]
    label = (row.get("label") or row.get("city") or "the new location").strip()

    earliest = next((s for s in STEP_ORDER if not _step_done(row, s)), None)
    ask_step = earliest if earliest in CLIENT_STEPS else None
    # Belt and braces: never ask for verification before the profile exists.
    if ask_step == "verification" and not _step_done(row, "gbp_created"):
        ask_step = None

    # One ask at a time per location + auto-retire on completion.
    for s in CLIENT_STEPS:
        if s != ask_step:
            _retire(cid, f"loc-{loc_id}-{s}", dry_run)

    if not ask_step:
        print(f"  {label} ({slug or cid}): no client ask "
              f"(earliest undone: {earliest or 'none, all steps done'})")
        return None

    title, rationale = _ask_for(ask_step, label)
    created = insert_plan_row(
        cid, slug, f"loc-{loc_id}-{ask_step}",
        title=title, rationale=rationale,
        action_type="client_input", target=None,
        impact="high", effort="low", dry_run=dry_run)
    print(f"  {label} ({slug or cid}): {ask_step} ask "
          f"{'seeded' if created else 'already open'}")
    return ask_step


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true",
                    help="print what would happen; write nothing")
    args = ap.parse_args()
    load_env()

    rows = _sb("GET", "/rest/v1/company_locations?status=neq.live&select=*"
               "&order=company_id", prefer="return=representation") or []
    if not rows:
        print("No non-live locations — nothing to do.")
        return 0

    smap = slug_map()
    cids = sorted({r["company_id"] for r in rows})
    names = {c["id"]: c.get("name") or "" for c in
             _sb("GET", "/rest/v1/companies"
                 f"?id=in.({','.join(cids)})&select=id,name",
                 prefer="return=representation") or []}
    print(f"{len(rows)} non-live location(s):")
    for row in rows:
        slug = smap.get(row["company_id"])
        # Registry watch FIRST: an approval flips dba in memory, so the ask
        # pass below retires the now-answered dba ask in the same sweep.
        _watch_registry(row, slug, names.get(row["company_id"], ""),
                        args.dry_run)
        sync_location(row, slug, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
