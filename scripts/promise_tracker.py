#!/usr/bin/env python3
"""Promise tracker: every promise OUR team makes to a client, owned and due.

Phase 1 of the follow-through system ("never lose a call or a promise",
Santino 2026-09-29). Full write-up: docs/FOLLOW-THROUGH-SYSTEM.md.

WHY. On 2026-09-20 Santino told Michael Katofsky on the onboarding call that
we would get back to him with GBP name options "in a day or so". Nothing
tracked it: Fathom's summary compressed it away, the extractor only read the
summary, and Monica's own one-slot promise memory does not see calls. Seven
days later the promise was still open while Monica kept nudging Michael for a
customer list that was not due for weeks.

WHAT IT DOES
  extract  every processed Fathom call: a Claude pass (claude-sonnet-5) over
           the FULL transcript lists what Santino / Levi / "we" promised the
           client, with the verbatim quote, the transcript timestamp, an
           owner and a due date derived from the words.
  texts    once a day: the same pass over HUMAN outbound SMS/email (GHL rows
           carrying a userId and no marketplace appId = Santino typed it).
  close    a commitment closes (status done + evidence) when a later
           outbound message to that client (Monica's or a human's) or a
           marketing_work_log entry clearly delivers it. A cheap Claude
           yes/no (claude-haiku-4-5), only re-asked when something new
           landed since the last check.
  remind   digest PROMISES section (client_ops_sync), one ops ping to
           Santino when a santino/dev promise is due within 24h and one when
           it goes overdue (quiet hours respected by flush_ops_pings), and,
           ONLY with PROMISES_MONICA_AUTOSEND=1, a [FOR MONICA] directive
           when a monica-owned promise comes due. Unset = notify only.
  hold     client_concierge.promise_hold: while a client holds an overdue
           open commitment, Monica sends no client-owed nudges.

Table: public.client_commitments (docs/migrations/2026-09-29_client_commitments.sql)
State: ops_kv `promise-tracker-state` (text-scan watermarks, close-check
       cursors, ping stamps).

Commands:
    run [--send]                       close + remind, per client (hourly)
    close [--send] [--company ID]      close pass only (no reminders)
    scan-texts [--send] [--days N]     human SMS/email pass (daily)
    backfill [--days 21] [--out F]     calls + texts for the last N days
    backfill --send --apply-file F     write exactly what a dry run saved
    list [--all]                       open promises, overdue first
    set <id> done|cancelled|open [--evidence TEXT]
Default is dry-run everywhere; --send writes.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
from datetime import date, datetime, time as dtime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

sys.path.insert(0, str(Path(__file__).parent))
import client_concierge as cc  # noqa: E402
from client_concierge import _sb, anthropic_json, kv_get, kv_set, load_env  # noqa: E402

TABLE = "/rest/v1/client_commitments"
STATE_KEY = "promise-tracker-state"
MODEL_EXTRACT = os.environ.get("PROMISES_EXTRACT_MODEL", "claude-sonnet-5")
MODEL_CHECK = os.environ.get("PROMISES_CHECK_MODEL", "claude-haiku-4-5")
OUR_TEAM = "Santino Velci (owner), Levi Candiff (sales), Monica (our assistant)"
DUE_HOUR = 17          # a promise is due by 5pm client-local on its due day


def autosend_enabled() -> bool:
    return os.environ.get("PROMISES_MONICA_AUTOSEND", "").strip() == "1"


# ------------------------------------------------------------------ due dates
def add_business_days(d: date, n: int) -> date:
    while n > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d


def due_from_kind(kind: str, said_local: datetime,
                  explicit: str | None = None) -> datetime:
    """Local due datetime from the words used (Santino's rules, 09-29):
    "a day or so" / "tomorrow" = +1 business day; "couple of days" = +2;
    "this week" = Friday; "next week" = next Friday; a stated date wins;
    nothing stated = +2 business days."""
    d0 = said_local.date()
    kind = (kind or "none").lower()
    if kind == "date" and explicit:
        try:
            d = date.fromisoformat(str(explicit)[:10])
            if d >= d0:
                return datetime.combine(d, dtime(DUE_HOUR), said_local.tzinfo)
        except ValueError:
            pass
        kind = "none"
    if kind == "today":
        d = d0 if said_local.hour < DUE_HOUR - 1 else add_business_days(d0, 1)
    elif kind in ("tomorrow", "day_or_so"):
        d = add_business_days(d0, 1)
    elif kind == "couple_days":
        d = add_business_days(d0, 2)
    elif kind == "this_week":
        # Friday of this week (said on a weekend: the coming Friday)
        d = d0 + timedelta(days=(4 - d0.weekday()) % 7)
    elif kind == "next_week":
        # Friday of next week (said on a weekend, "next week" is the coming one)
        d = d0 + timedelta(days=(4 - d0.weekday()) % 7
                           + (0 if d0.weekday() >= 5 else 7))
    else:
        d = add_business_days(d0, 2)
    return datetime.combine(d, dtime(DUE_HOUR), said_local.tzinfo)


def client_tz(company: dict) -> ZoneInfo:
    try:
        tz, _src = cc.resolve_timezone(company, None)
        return ZoneInfo(tz)
    except Exception:  # noqa: BLE001
        return ZoneInfo(cc.DEFAULT_TZ)


# ------------------------------------------------------------------ extraction
EXTRACT_SYSTEM = f"""\
You read a conversation between our agency and one of its clients (a
restoration contractor) and list every PROMISE OUR SIDE MADE TO THE CLIENT.

Our side: {OUR_TEAM}, or anyone speaking for us as "we"/"I"/"our team".

A promise is a commitment by us to DO, SEND, DECIDE, FIND OUT or FOLLOW UP on
something for this client: "I'll send you the name options tomorrow", "we'll
get back to you in a day or so", "I'll check with Google and let you know",
"we'll have the site live by Friday", "I'll text you the link after the call".

NOT promises:
- anything the CLIENT will do (their homework);
- things done live during the conversation;
- vague ongoing intentions with no deliverable ("we'll keep optimizing");
- restating what our service includes in general, pitches, hypotheticals;
- scheduling the next meeting itself (a booked call is tracked elsewhere).

For each promise:
- what: imperative, concrete, understandable without the source ("Send
  Michael 3 GBP name options with search volumes").
- quote: the closest VERBATIM words from the source. Never invent.
- at: the transcript timestamp (HH:MM:SS) or the message timestamp given.
- source_id: for messages, the [id] of the message that made the promise;
  for a call, "".
- owner: "monica" = pure communication we can send from information we
  already hold (a link, an answer we know, options already researched, a
  confirmation); "dev" = build/ops work (site, listings, GBP content,
  tracking numbers, reports, setup); "santino" = a decision, research,
  judgment, pricing, a call, anything needing Santino personally.
- due_kind: the time words used for THIS promise, exactly one of
  "today", "tomorrow", "day_or_so", "couple_days", "this_week",
  "next_week", "date", "none".
- due_date: YYYY-MM-DD only when due_kind is "date" (resolve relative dates
  like "Monday" against the given start date), else "".
- confidence: "high" when it is plainly a commitment, "medium" when it is
  a likely commitment, "low" otherwise.
One entry per distinct promise; merge repeats of the same promise.

Return ONLY JSON:
{{"promises": [{{"what": str, "quote": str, "at": str, "source_id": str,
  "owner": "monica"|"santino"|"dev", "due_kind": str, "due_date": str,
  "confidence": "high"|"medium"|"low"}}]}}"""


def _extract(company: dict, header: str, body: str) -> list[dict]:
    out = None
    for attempt in (1, 2):
        try:
            out = anthropic_json(
                EXTRACT_SYSTEM,
                f"Client: {company.get('name')}\n{header}\n\n{body}",
                max_tokens=8000, model=MODEL_EXTRACT, timeout=300)
            break
        except (ValueError, requests.RequestException) as e:
            # malformed JSON / a slow long-transcript read: one retry
            if attempt == 2:
                raise
            print(f"    extraction retry ({str(e)[:70]})")
    keep = []
    for p in out.get("promises") or []:
        if not isinstance(p, dict) or not str(p.get("what") or "").strip():
            continue
        if str(p.get("confidence") or "").lower() == "low":
            continue
        owner = str(p.get("owner") or "santino").lower()
        p["owner"] = owner if owner in ("monica", "santino", "dev") else "santino"
        keep.append(p)
    return keep


def _offset_at(start: datetime, ts: str) -> datetime:
    try:
        h, m, s = (int(x) for x in str(ts).split(":")[:3])
        return start + timedelta(hours=h, minutes=m, seconds=s)
    except (ValueError, TypeError):
        return start


def extract_call(company: dict, m: dict, segments: list[dict]) -> list[dict]:
    """Rows (not yet written) for one Fathom call's full transcript."""
    rid = str(m.get("recording_id"))
    start = datetime.fromisoformat(str(m.get("recording_start_time")
                                       or m.get("created_at")).replace("Z", "+00:00"))
    tz = client_tz(company)
    lines = [f"[{s.get('timestamp') or ''}] "
             f"{(s.get('speaker') or {}).get('display_name') or '?'}: "
             f"{s.get('text') or ''}" for s in segments]
    body = "\n".join(lines)
    if not body.strip():
        return []
    local = start.astimezone(tz)
    header = (f"Source: recorded call {m.get('title')!r}, started "
              f"{local:%A %Y-%m-%d %H:%M} client-local time ({tz.key}).\n"
              "Transcript (timestamps are offsets from the call start):")
    rows = []
    for p in _extract(company, header, body[:180000]):
        said = _offset_at(start, p.get("at"))
        due = due_from_kind(p.get("due_kind"), said.astimezone(tz),
                            p.get("due_date"))
        rows.append({"company_id": company["id"], "source": "call",
                     "source_ref": f"fathom:{rid}",
                     "said_at": said.isoformat(),
                     "quote": str(p.get("quote") or "")[:800],
                     "what": str(p.get("what")).strip()[:400],
                     "owner": p["owner"],
                     "due_at": due.astimezone(timezone.utc).isoformat()})
    return rows


def extract_texts(company: dict, msgs: list[dict], context: list[dict]
                  ) -> list[dict]:
    """Rows for human outbound SMS/email. msgs = the human messages to
    judge; context = the surrounding thread (both sides, oldest first)."""
    if not msgs:
        return []
    tz = client_tz(company)
    ids = {m["id"] for m in msgs}
    lines = []
    for m in context:
        who = ("us-human" if m["id"] in ids else
               "client" if m["direction"] == "in" else "us")
        mark = f"[{m['id']}] " if m["id"] in ids else ""
        lines.append(f"{mark}{m['when'].astimezone(tz):%a %Y-%m-%d %H:%M} "
                     f"{who} ({m['channel']}): {m['body'][:700]}")
    header = ("Source: the client's text/email thread (client-local times, "
              f"{tz.key}). Judge ONLY lines marked with an [id] (typed by "
              "Santino); other lines are context.")
    by_id = {m["id"]: m for m in msgs}
    rows = []
    for p in _extract(company, header, "\n".join(lines)):
        src = by_id.get(str(p.get("source_id") or "").strip("[] "))
        if not src:
            continue
        due = due_from_kind(p.get("due_kind"), src["when"].astimezone(tz),
                            p.get("due_date"))
        rows.append({"company_id": company["id"],
                     "source": "email" if src["channel"] == "email" else "sms",
                     "source_ref": f"ghl:{src['id']}",
                     "said_at": src["when"].isoformat(),
                     "quote": str(p.get("quote") or "")[:800],
                     "what": str(p.get("what")).strip()[:400],
                     "owner": p["owner"],
                     "due_at": due.astimezone(timezone.utc).isoformat()})
    return rows


def already_extracted(company_id: str, source_ref: str) -> bool:
    rows = _sb("GET", f"{TABLE}?company_id=eq.{company_id}&source_ref=eq."
               + urllib.parse.quote(source_ref) + "&select=id&limit=1") or []
    return bool(rows)


def write_rows(rows: list[dict], dry_run: bool) -> int:
    if not rows:
        return 0
    if dry_run:
        return len(rows)
    # PostgREST bulk inserts need identical keys on every object
    keys = ("company_id", "source", "source_ref", "said_at", "quote", "what",
            "owner", "due_at", "status", "evidence", "closed_at")
    rows = [{k: r.get(k, "open" if k == "status" else None) for k in keys}
            for r in rows]
    _sb("POST", f"{TABLE}?on_conflict=company_id,source_ref,what", rows,
        prefer="resolution=ignore-duplicates,return=minimal")
    return len(rows)


def record_call(company: dict, m: dict, dry_run: bool,
                segments: list[dict] | None = None,
                force: bool = False) -> list[dict]:
    """fathom_sync's hook: extract + store the promises of one processed
    call. Once per recording (the table is the ledger); fail-open upstream."""
    rid = str(m.get("recording_id"))
    if not force and already_extracted(company["id"], f"fathom:{rid}"):
        print("    promises: already extracted for this call")
        return []
    segs = segments
    if not segs:
        from fathom_sync import fathom_transcript
        segs = fathom_transcript(rid, api_key=m.get("_api_key"))
    rows = extract_call(company, m, segs)
    for r in rows:
        print(f"    promise [{r['owner']}] due {r['due_at'][:16]}: "
              f"{r['what'][:90]}")
    write_rows(rows, dry_run)
    if not rows:
        print("    promises: none made on this call")
    return rows


# ------------------------------------------------------------------ roster
def client_roster() -> list[dict]:
    """Rank AI clients we message (per-client fan-out unit)."""
    import call_match
    out = []
    for e in call_match.load_roster(_sb):
        co = e["company"]
        if not call_match.is_minable(e) or cc.company_inactive(co):
            continue
        out.append(co)
    return out


def contact_ids(company: dict) -> list[str]:
    ints = company.get("integration_settings") or {}
    if isinstance(ints, str):
        try:
            ints = json.loads(ints)
        except ValueError:
            ints = {}
    ids = [c.get("ghl_contact_id") for c in (ints.get("contacts") or [])
           if isinstance(c, dict) and c.get("ghl_contact_id")]
    if ints.get("ghl_contact_id"):
        ids.append(ints["ghl_contact_id"])
    return list(dict.fromkeys(ids))


def thread(company: dict, max_msgs: int = 120) -> list[dict]:
    """Every contact's messages merged, oldest first."""
    seen, out = set(), []
    for gid in contact_ids(company):
        for m in cc.fetch_history(gid, max_msgs=max_msgs):
            if m["id"] in seen:
                continue
            seen.add(m["id"])
            out.append(m)
    out.sort(key=lambda m: m["when"])
    return out


def human_outbound(msgs: list[dict]) -> list[dict]:
    return [m for m in msgs if m["direction"] == "out" and m.get("user_id")
            and m["channel"] in ("sms", "email")
            and len(str(m.get("body") or "")) >= 12]


# ------------------------------------------------------------------ texts
def scan_texts(company: dict, since: datetime, dry_run: bool,
               msgs: list[dict] | None = None) -> list[dict]:
    msgs = msgs if msgs is not None else thread(company)
    new = [m for m in human_outbound(msgs) if m["when"] > since]
    if not new:
        return []
    fresh = []
    for m in new:
        if not already_extracted(company["id"], f"ghl:{m['id']}"):
            fresh.append(m)
    if not fresh:
        return []
    first = min(m["when"] for m in fresh)
    context = [m for m in msgs if m["when"] >= first - timedelta(days=2)][-80:]
    rows = extract_texts(company, fresh, context)
    write_rows(rows, dry_run)
    return rows


# ------------------------------------------------------------------ closing
CLOSE_SYSTEM = """\
You check whether an agency DELIVERED one specific promise it made to a
client. You get the promise and everything that happened AFTER it: our
outbound messages to the client and our internal work log.
delivered = true ONLY when something below clearly does what was promised
(sends the thing, gives the answer, reports the work done, or tells the
client the decision). NOT delivery: a holding line ("still working on it",
"I'll get you that"), a message saying the work is in progress or coming
soon, a message about a different topic, a partial delivery. When unsure,
delivered = false: a wrongly closed promise is worse than an open one.
Return ONLY JSON: {"delivered": bool, "evidence": "<the line that proves it,
with its timestamp, or empty>"}"""


def work_log_since(company_id: str, since: str) -> list[dict]:
    try:
        return _sb("GET", "/rest/v1/marketing_work_log?company_id=eq."
                   + company_id + "&ts=gt." + urllib.parse.quote(since)
                   + "&select=ts,category,action,detail&order=ts.asc"
                   "&limit=60") or []
    except Exception:  # noqa: BLE001
        return []


def check_delivered(c: dict, outbound: list[dict], log: list[dict]
                    ) -> tuple[bool, str]:
    lines = [f"{m['when']:%Y-%m-%d %H:%M} UTC "
             f"{'Santino' if m.get('user_id') else 'Monica/auto'} "
             f"({m['channel']}): {m['body'][:600]}" for m in outbound]
    lines += [f"{str(w.get('ts'))[:16]} work log [{w.get('category')}/"
              f"{w.get('action')}]: {str(w.get('detail'))[:300]}" for w in log]
    if not lines:
        return False, ""
    out = anthropic_json(
        CLOSE_SYSTEM,
        f"PROMISE (made {str(c.get('said_at'))[:16]} UTC): {c.get('what')}\n"
        f"Their words: \"{c.get('quote')}\"\n\nAFTER IT:\n" + "\n".join(lines),
        max_tokens=600, model=MODEL_CHECK)
    return bool(out.get("delivered")), str(out.get("evidence") or "")[:500]


def open_commitments(company_id: str | None = None) -> list[dict]:
    q = f"{TABLE}?status=eq.open&select=*&order=due_at.asc"
    if company_id:
        q += f"&company_id=eq.{company_id}"
    return _sb("GET", q) or []


def close_for_client(company: dict, opens: list[dict], state: dict,
                     dry_run: bool, msgs: list[dict] | None = None,
                     force: bool = False) -> list[tuple[dict, str]]:
    """Close what a later message / work-log entry delivered. Only re-asks
    the model when something new landed since the last check."""
    if not opens:
        return []
    msgs = msgs if msgs is not None else thread(company)
    cursors = state.setdefault("close_cursor", {})
    closed = []
    for c in opens:
        said = datetime.fromisoformat(str(c["said_at"]).replace("Z", "+00:00"))
        outbound = [m for m in msgs if m["direction"] == "out"
                    and m["when"] > said and m["channel"] in ("sms", "email")]
        log = work_log_since(c["company_id"], said.isoformat())
        sig = f"{len(outbound)}:{len(log)}:" + (
            outbound[-1]["id"] if outbound else "")
        if not force and cursors.get(c["id"]) == sig:
            continue
        try:
            ok, ev = check_delivered(c, outbound[-25:], log[-30:])
        except Exception as e:  # noqa: BLE001 — one check never stops the run
            print(f"    ! close check failed ({str(e)[:80]})")
            continue
        cursors[c["id"]] = sig
        if not ok:
            continue
        closed.append((c, ev))
        print(f"    DONE: {c['what'][:80]}  <- {ev[:110]}")
        if not dry_run:
            _sb("PATCH", f"{TABLE}?id=eq.{c['id']}",
                {"status": "done", "evidence": ev or "delivered (auto-check)",
                 "closed_at": datetime.now(timezone.utc).isoformat()},
                prefer="return=minimal")
    return closed


# ------------------------------------------------------------------ reminders
def _due(c: dict) -> datetime:
    return datetime.fromisoformat(str(c["due_at"]).replace("Z", "+00:00"))


def remind(companies: dict, opens: list[dict], state: dict,
           dry_run: bool) -> int:
    """Ops pings for santino/dev (and monica while autosend is off) items:
    once when due within 24h, once when overdue. Monica directives only with
    PROMISES_MONICA_AUTOSEND=1."""
    now = datetime.now(timezone.utc)
    soon = state.setdefault("pinged_soon", {})
    late = state.setdefault("pinged_overdue", {})
    directed = state.setdefault("monica_directed", {})
    by_client: dict[str, list[str]] = {}
    n = 0
    for c in opens:
        co = companies.get(c["company_id"]) or {"id": c["company_id"],
                                               "name": c["company_id"]}
        due = _due(c)
        if c["owner"] == "monica" and autosend_enabled():
            if due <= now and c["id"] not in directed:
                body = ("[FOR MONICA] PROMISE DUE: on "
                        f"{str(c['said_at'])[:10]} we told them: "
                        f"\"{str(c.get('quote'))[:300]}\"\nDeliver it now: "
                        f"{c['what']}\nOnly send what we actually hold; if "
                        "something is missing, say it is coming and hand it "
                        "to Santino. (promise_tracker, commitment "
                        f"{c['id'][:8]})")
                print(f"  directive -> Monica: {co.get('name')}: {c['what'][:70]}")
                if not dry_run:
                    _sb("POST", "/rest/v1/marketing_ops_notes",
                        {"company_id": c["company_id"], "body": body})
                    directed[c["id"]] = now.isoformat()
                n += 1
            continue
        if due <= now and c["id"] not in late:
            late[c["id"]] = now.isoformat()
            soon.setdefault(c["id"], now.isoformat())
            if now - due > timedelta(hours=72):
                # overdue long before we first saw it (backfill, or a call
                # mined late): the digest carries it, the phone does not
                continue
            line = f"OVERDUE since {due:%m/%d}: {c['what'][:110]}"
        elif now < due <= now + timedelta(hours=24) and c["id"] not in soon:
            line = f"due {due:%m/%d %H:%M} UTC: {c['what'][:110]}"
            soon[c["id"]] = now.isoformat()
        else:
            continue
        by_client.setdefault(co.get("name") or c["company_id"], []).append(
            f"[{c['owner']}] {line}")
    for name, lines in by_client.items():
        reason = "PROMISE " + (" | ".join(lines[:3])
                               + (f" (+{len(lines) - 3} more)" if len(lines) > 3 else ""))
        cc._OPS_PINGS.append((name, reason))
        n += 1
        print(f"  ops ping: {name}: {reason[:150]}")
    if by_client:
        cc.flush_ops_pings(dry_run)
    return n


# ------------------------------------------------------------------ digest
def digest_sections(now: datetime | None = None) -> dict:
    """{overdue, today, tomorrow: [{client, what, quote, owner, due}]},
    today/tomorrow judged in each client's own timezone. Fail-open."""
    now = now or datetime.now(timezone.utc)
    out = {"overdue": [], "today": [], "tomorrow": [], "holds": []}
    try:
        opens = open_commitments()
        cos = cc.fetch_companies(sorted({c["company_id"] for c in opens})) \
            if opens else {}
    except Exception as e:  # noqa: BLE001
        out["error"] = str(e)[:120]
        return out
    for c in opens:
        co = cos.get(c["company_id"]) or {}
        tz = client_tz(co) if co else ZoneInfo(cc.DEFAULT_TZ)
        due = _due(c)
        d_local, n_local = due.astimezone(tz).date(), now.astimezone(tz).date()
        row = {"client": co.get("name") or c["company_id"],
               "what": c["what"], "quote": c.get("quote") or "",
               "owner": c["owner"], "due": due.astimezone(tz),
               "source": c["source"], "id": c["id"]}
        if due <= now:
            out["overdue"].append(row)
        elif d_local == n_local:
            out["today"].append(row)
        elif d_local == n_local + timedelta(days=1) or (
                n_local.weekday() == 4 and d_local == n_local + timedelta(days=3)):
            out["tomorrow"].append(row)
    for k in ("overdue", "today", "tomorrow"):       # grouped per client
        out[k].sort(key=lambda r: (r["client"], r["due"]))
    hold_owners = {o.strip() for o in os.environ.get(
        "PROMISES_HOLD_OWNERS", "monica,santino").split(",")}
    hold_since = datetime.fromisoformat(os.environ.get(
        "PROMISES_HOLD_SINCE", "2026-09-29T00:00:00+00:00"))
    said = {c["id"]: c.get("said_at") for c in opens}
    out["holds"] = sorted({
        r["client"] for r in out["overdue"] if r["owner"] in hold_owners
        and said.get(r["id"]) and datetime.fromisoformat(
            str(said[r["id"]]).replace("Z", "+00:00")) >= hold_since})
    return out


def digest_markdown(sec: dict) -> list[str]:
    if not any(sec.get(k) for k in ("overdue", "today", "tomorrow")):
        return []
    lines = ["## PROMISES (what we owe clients)"]
    for key, label in (("overdue", "OVERDUE"), ("today", "Due today"),
                       ("tomorrow", "Due tomorrow")):
        if sec.get(key):
            lines.append(f"### {label}")
            for r in sec[key]:
                lines.append(f"- **{r['client']}** [{r['owner']}] {r['what']} "
                             f"(due {r['due']:%a %m/%d %-I%p}): \"{r['quote'][:160]}\"")
    if sec.get("holds"):
        lines.append("_Monica is holding client-owed nudges for: "
                     + ", ".join(sec["holds"]) + " until these are delivered._")
    return lines + [""]


def digest_html(sec: dict, esc) -> str:
    if not any(sec.get(k) for k in ("overdue", "today", "tomorrow")):
        return ""
    colors = {"overdue": "#b91c1c", "today": "#b45309", "tomorrow": "#1d4ed8"}
    parts = ['<div style="border:2px solid #b91c1c;border-radius:8px;'
             'padding:8px 12px;margin:8px 0 16px">'
             '<h3 style="margin:4px 0;color:#b91c1c">PROMISES: what we owe '
             'clients</h3>']
    for key, label in (("overdue", "OVERDUE"), ("today", "Due today"),
                       ("tomorrow", "Due tomorrow")):
        if not sec.get(key):
            continue
        parts.append(f'<p style="margin:8px 0 2px;font-weight:700;color:'
                     f'{colors[key]}">{label} ({len(sec[key])})</p>'
                     '<ul style="margin:2px 0">')
        for r in sec[key]:
            parts.append(
                f'<li><b>{esc(r["client"])}</b> <span style="color:#64748b">'
                f'[{esc(r["owner"])}] due {r["due"]:%a %m/%d %-I%p}</span><br>'
                f'{esc(r["what"])}<br><i style="color:#475569">"'
                f'{esc(r["quote"][:200])}"</i></li>')
        parts.append("</ul>")
    if sec.get("holds"):
        parts.append('<p style="font-size:12px;color:#64748b">Monica is '
                     'holding client-owed nudges for: '
                     + esc(", ".join(sec["holds"])) + '.</p>')
    parts.append("</div>")
    return "".join(parts)


# ------------------------------------------------------------------ commands
def load_state() -> dict:
    return kv_get(STATE_KEY) or {}


def save_state(state: dict, dry_run: bool) -> None:
    if not dry_run:
        kv_set(STATE_KEY, state)


def cmd_run(args) -> int:
    """Hourly: close + remind, one client at a time, fail-open."""
    dry_run = not args.send
    state = load_state()
    opens = open_commitments()
    cids = sorted({c["company_id"] for c in opens})
    companies = cc.fetch_companies(cids) if cids else {}
    print(f"promise tracker: {len(opens)} open across {len(cids)} client(s)"
          + (" [DRY RUN]" if dry_run else ""))
    for cid in cids:
        co = companies.get(cid)
        if not co:
            continue
        print(f"\n--- {co.get('name')}")
        try:
            done = close_for_client(co, [c for c in opens if c["company_id"] == cid],
                                    state, dry_run)
            done_ids = {c["id"] for c, _ in done}
            opens = [c for c in opens if c["id"] not in done_ids]
        except Exception as e:  # noqa: BLE001 — per client, fail-open
            print(f"  ! close pass failed: {str(e)[:120]}")
    try:
        remind(companies, opens, state, dry_run)
    except Exception as e:  # noqa: BLE001
        print(f"  ! reminders failed: {str(e)[:120]}")
    live = {c["id"] for c in opens}
    for k in ("close_cursor", "pinged_soon", "pinged_overdue", "monica_directed"):
        state[k] = {i: v for i, v in (state.get(k) or {}).items() if i in live}
    save_state(state, dry_run)
    return 0


def cmd_close(args) -> int:
    """Close pass only (no reminders): what later messages / the work log
    already delivered."""
    dry_run = not args.send
    state = load_state()
    opens = open_commitments()
    if args.company:
        opens = [c for c in opens if c["company_id"] in args.company]
    cids = sorted({c["company_id"] for c in opens})
    companies = cc.fetch_companies(cids) if cids else {}
    for cid in cids:
        co = companies.get(cid)
        if not co:
            continue
        print(f"\n--- {co.get('name')}")
        try:
            close_for_client(co, [c for c in opens if c["company_id"] == cid],
                             state, dry_run, force=args.force)
        except Exception as e:  # noqa: BLE001
            print(f"  ! close pass failed: {str(e)[:120]}")
    save_state(state, dry_run)
    return 0


def cmd_scan_texts(args) -> int:
    dry_run = not args.send
    state = load_state()
    marks = state.setdefault("text_scan", {})
    now = datetime.now(timezone.utc)
    total = 0
    for co in client_roster():
        since_s = marks.get(co["id"])
        since = (datetime.fromisoformat(since_s) if since_s and not args.days
                 else now - timedelta(days=args.days or 1))
        try:
            rows = scan_texts(co, since, dry_run)
        except Exception as e:  # noqa: BLE001 — per client, fail-open
            print(f"  ! {co.get('name')}: {str(e)[:120]}")
            continue
        for r in rows:
            print(f"  {co.get('name')}: [{r['owner']}] due {r['due_at'][:10]} "
                  f"{r['what'][:90]}  <- \"{r['quote'][:80]}\"")
        total += len(rows)
        marks[co["id"]] = now.isoformat()
    print(f"\n{total} promise(s) found in human texts"
          + (" [DRY RUN]" if dry_run else ""))
    save_state(state, dry_run)
    return 0


def cmd_backfill(args) -> int:
    """Calls + human texts for the last N days, then an auto-close pass.
    Prints the full table. --send writes."""
    import call_match
    import fathom_sync as fs
    dry_run = not args.send
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=args.days)
    state = load_state()
    if args.apply_file:
        # apply EXACTLY what a reviewed dry run printed (extraction is a
        # model call; re-running it would not reproduce the same list)
        saved = json.loads(Path(args.apply_file).read_text())
        return _backfill_write(saved, now, state, dry_run)
    roster = call_match.load_roster(_sb)
    by_key = {e["key"]: e for e in roster}
    fstate = fs.load_state()
    found: list[tuple[dict, dict]] = []      # (company, row)
    if not args.texts_only:
        meetings = fs.fathom_meetings(since=since.strftime("%Y-%m-%dT%H:%M:%SZ"))
        for m in reversed(meetings):
            rid = str(m.get("recording_id"))
            key = (fstate.get("processed") or {}).get(rid)
            if args.rid and rid not in args.rid:
                continue
            entry = by_key.get(key)
            if not entry:
                # unmatched in the sync state: the new matcher gets a go
                entry, _why = fs.match_for_backfill(m, roster)
            if not entry or not call_match.is_minable(entry):
                continue
            co = entry["company"]
            print(f"\n--- call {fs.meeting_when(m)} {m.get('title')!r} -> "
                  f"{entry['key']}")
            try:
                if already_extracted(co["id"], f"fathom:{rid}") and not args.force:
                    print("    already in the table")
                    continue
                segs = fs.fathom_transcript(rid, api_key=m.get("_api_key"))
                rows = extract_call(co, m, segs)
            except Exception as e:  # noqa: BLE001
                print(f"    ! extraction failed: {str(e)[:120]}")
                continue
            for r in rows:
                found.append((co, r))
                print(f"    [{r['owner']}] due {r['due_at'][:10]}: {r['what'][:100]}")
    threads: dict[str, list[dict]] = {}

    def thread_of(co: dict) -> list[dict]:
        if co["id"] not in threads:
            threads[co["id"]] = thread(co, max_msgs=150)
        return threads[co["id"]]
    if not args.calls_only:
        for co in client_roster():
            if args.company and co["id"] not in args.company:
                continue
            try:
                msgs = thread_of(co)
                rows = scan_texts(co, since, dry_run=True, msgs=msgs)
            except Exception as e:  # noqa: BLE001
                print(f"  ! texts {co.get('name')}: {str(e)[:120]}")
                continue
            for r in rows:
                found.append((co, r))
                print(f"  text {co.get('name')}: [{r['owner']}] "
                      f"{r['what'][:100]}")
    # auto-close each found promise against what came after it
    status: dict[int, tuple[str, str]] = {}
    per_client: dict[str, list[int]] = {}
    for i, (co, r) in enumerate(found):
        per_client.setdefault(co["id"], []).append(i)
    for cid, idxs in per_client.items():
        co = found[idxs[0]][0]
        try:
            msgs = thread_of(co)
        except Exception:  # noqa: BLE001
            msgs = []
        for i in idxs:
            r = dict(found[i][1], id=f"new-{i}")
            said = datetime.fromisoformat(r["said_at"])
            outbound = [m for m in msgs if m["direction"] == "out"
                        and m["when"] > said and m["channel"] in ("sms", "email")]
            try:
                ok, ev = check_delivered(r, outbound[-25:],
                                         work_log_since(cid, said.isoformat())[-30:])
            except Exception as e:  # noqa: BLE001
                ok, ev = False, f"(check failed: {str(e)[:60]})"
            status[i] = ("done" if ok else "open", ev)
    print("\n" + "=" * 100)
    print(f"BACKFILL: {len(found)} promise(s), last {args.days} days"
          + (" [DRY RUN]" if dry_run else ""))
    for i, (co, r) in enumerate(found):
        st, ev = status.get(i, ("open", ""))
        late = " OVERDUE" if st == "open" and datetime.fromisoformat(
            r["due_at"]) < now else ""
        print(f"- {co.get('name')[:28]:28} | {r['source']:5} | "
              f"{r['said_at'][:10]} | due {r['due_at'][:10]} | "
              f"{r['owner']:7} | {st.upper()}{late}\n    what: {r['what'][:150]}"
              f"\n    said: \"{r['quote'][:180]}\""
              + (f"\n    evidence: {ev[:160]}" if st == "done" else ""))
    rows = []
    for i, (co, r) in enumerate(found):
        st, ev = status.get(i, ("open", ""))
        row = dict(r)
        if st == "done":
            row.update(status="done", evidence=ev or "delivered (backfill check)",
                       closed_at=now.isoformat())
        rows.append(row)
    if args.out:
        Path(args.out).write_text(json.dumps(rows, indent=1, default=str))
        print(f"saved {len(rows)} row(s) to {args.out} (apply with "
              f"backfill --send --apply-file {args.out})")
    return _backfill_write(rows, now, state, dry_run)


def _backfill_write(rows: list[dict], now: datetime, state: dict,
                    dry_run: bool) -> int:
    if dry_run:
        return 0
    # one ignore-duplicates upsert per client keeps a bad row from sinking all
    for cid in sorted({r["company_id"] for r in rows}):
        batch = [r for r in rows if r["company_id"] == cid]
        try:
            write_rows(batch, dry_run=False)
        except Exception as e:  # noqa: BLE001
            print(f"  ! write failed for {cid}: {str(e)[:120]}")
    marks = state.setdefault("text_scan", {})
    for co in client_roster():
        marks.setdefault(co["id"], now.isoformat())
    save_state(state, dry_run=False)
    print(f"wrote {len(rows)} row(s) to client_commitments")
    return 0


def cmd_list(args) -> int:
    q = f"{TABLE}?select=*&order=due_at.asc"
    if not args.all:
        q += "&status=eq.open"
    rows = _sb("GET", q) or []
    cos = cc.fetch_companies(sorted({r["company_id"] for r in rows})) if rows else {}
    now = datetime.now(timezone.utc)
    for r in rows:
        late = "OVERDUE " if r["status"] == "open" and _due(r) < now else ""
        print(f"{r['id'][:8]} {late}{r['status']:9} due {str(r['due_at'])[:16]} "
              f"[{r['owner']}] {(cos.get(r['company_id']) or {}).get('name', r['company_id'])}: "
              f"{r['what'][:90]}")
    print(f"{len(rows)} row(s)")
    return 0


def cmd_set(args) -> int:
    # uuid columns take no LIKE in PostgREST: match the prefix client-side
    rows = [r for r in (_sb("GET", f"{TABLE}?select=id,what") or [])
            if str(r["id"]).startswith(args.id)]
    if len(rows) != 1:
        print(f"need exactly one match for {args.id!r}, got {len(rows)}")
        return 1
    patch = {"status": args.status,
             "closed_at": (None if args.status == "open"
                           else datetime.now(timezone.utc).isoformat())}
    if args.evidence:
        patch["evidence"] = args.evidence
    _sb("PATCH", f"{TABLE}?id=eq.{rows[0]['id']}", patch, prefer="return=minimal")
    print(f"{rows[0]['id'][:8]} -> {args.status}: {rows[0]['what'][:80]}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("run")
    p.add_argument("--send", action="store_true")
    p = sub.add_parser("close")
    p.add_argument("--send", action="store_true")
    p.add_argument("--company", action="append", default=[])
    p.add_argument("--force", action="store_true",
                   help="re-check even when nothing new landed")
    p = sub.add_parser("scan-texts")
    p.add_argument("--send", action="store_true")
    p.add_argument("--days", type=int, default=0,
                   help="ignore watermarks and scan the last N days")
    p = sub.add_parser("backfill")
    p.add_argument("--send", action="store_true")
    p.add_argument("--days", type=int, default=21)
    p.add_argument("--rid", action="append", default=[])
    p.add_argument("--company", action="append", default=[])
    p.add_argument("--calls-only", action="store_true")
    p.add_argument("--texts-only", action="store_true")
    p.add_argument("--force", action="store_true")
    p.add_argument("--out", default="", help="save the reviewed rows (JSON)")
    p.add_argument("--apply-file", default="",
                   help="with --send: write exactly the rows a dry run saved")
    p = sub.add_parser("list")
    p.add_argument("--all", action="store_true")
    p = sub.add_parser("set")
    p.add_argument("id")
    p.add_argument("status", choices=["done", "cancelled", "open"])
    p.add_argument("--evidence", default="")
    args = ap.parse_args()
    load_env()
    return {"run": cmd_run, "close": cmd_close, "scan-texts": cmd_scan_texts,
            "backfill": cmd_backfill, "list": cmd_list,
            "set": cmd_set}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
