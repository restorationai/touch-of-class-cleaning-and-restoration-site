#!/usr/bin/env python3
"""silence_watch.py — every automation proves it is still producing, daily.

WHY THIS EXISTS. Three times now we have shipped something, wired it, and
found out weeks later that it had been silently doing nothing:

  * gbp_admin_invite (2026-08-04) — built, correct, and never scheduled. Reign
    connected Google on 08-03 and no invite was ever sent.
  * lsa_ask_guard (2026-08-05) — running on every compose pass, but the
    Railway worker holds no Google Ads credentials, so it returned "no
    opinion" every single time and Jaziel was asked for access we already had.
  * the client-feedback loop (2026-08-05) — this one was actually ALIVE, and
    was declared dead anyway, because an inbox listing checked two minutes
    before the write looked exactly like a pipeline that never ran.

All three are the same bug in the OBSERVER, not the code: a system that
produces nothing looks identical to a system with nothing to do. This job
makes those two states different.

THE RULE, per system:

    inputs == 0                      -> quiet (green). Nothing to do is fine.
    inputs > 0, never produced       -> RED "never" — the gbp_admin_invite
                                        shape: built, wired, never once ran.
    inputs > 0, last output too old  -> RED "silent" — it used to work.
    otherwise                        -> green.

INPUTS come from the system's own heartbeat (scripts/heartbeat.py) or from
the state its trigger writes; OUTPUTS are read from the SHARED TRUTH — the
board, the ledger tables, the artifacts other people can see. Never from the
same self-report as the inputs: a system that stamps a heartbeat and writes
nothing must still be caught.

A RED files ONE [TODO-SANTINO] card per system per UTC day (ops_kv
`silence-watch-state`), so a week-long stall is a week of one card a day, not
a flood. The card carries the exact command to check with. Systems whose
probe itself fails are held as "unknown" and only carded when unknown two
runs running — a flaky lookup is not an outage, but a lookup that never
recovers is.

Scheduling: ops_scheduler DAILY_JOBS ("silence-watch", 15:20 UTC), after the
fathom meeting watchdog (15:10) which owns the deeper per-meeting check.

CLI:
  python3 scripts/silence_watch.py check            # dry run, prints the table
  python3 scripts/silence_watch.py check --send     # files cards for REDs
  python3 scripts/silence_watch.py status           # the table only, never files
  python3 scripts/silence_watch.py check --json     # machine-readable
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

NOW = datetime.now(timezone.utc)
WATCH_KEY = "silence-watch-state"
# How far apart two "unknown" readings must be to count as two strikes. The
# worker re-runs its whole daily roster after every deploy, and a deploy
# switchover can leave two containers alive for a moment — on 2026-08-05 two
# passes landed in the SAME SECOND and carded a system that had been unknown
# once. Consecutive has to mean "on a later pass", not "twice, somehow".
UNKNOWN_CONFIRM_HOURS = 6


def _sb(*a, **kw):
    from client_ops_sync import _sb as sb
    return sb(*a, **kw)


def _iso(dt_) -> str:
    return dt_.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse(ts) -> datetime | None:
    if not ts:
        return None
    try:
        d = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _age_days(ts) -> float | None:
    d = _parse(ts)
    return None if d is None else (NOW - d).total_seconds() / 86400


def _rows(path: str) -> list[dict]:
    return _sb("GET", path, prefer="return=representation") or []


def _newest(path: str, field: str) -> str | None:
    rows = _rows(f"{path}&select={field}&order={field}.desc&limit=1")
    return rows[0].get(field) if rows else None


def _count(path: str) -> int:
    """Row count via a bounded fetch — these tables are small and this keeps
    one code path for every probe."""
    return len(_rows(path + "&select=id&limit=2000"))


def _active_clients() -> list[str]:
    out = []
    for f in sorted((ROOT / "clients").glob("*.json")):
        if f.name == "company_map.json":
            continue
        try:
            c = json.loads(f.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if str(c.get("status") or "").lower() in ("active", "preview", "onboarding"):
            out.append(f.stem)
    return out


def _hb_window(system: str, days: float) -> tuple[int, int, str | None]:
    """(inputs, outputs, last_run_at) from a heartbeat's runs inside the
    window. Runs are the record of what the code SAW, which is the only
    honest source for "were there inputs"."""
    from heartbeat import read
    hb = read(system)
    if not hb:
        return -1, -1, None            # -1 = no heartbeat at all yet
    cut = NOW - timedelta(days=days)
    ins = outs = 0
    for r in (hb.get("runs") or []):
        d = _parse(r.get("at"))
        if d and d >= cut:
            ins += int(r.get("inputs") or 0)
            outs += int(r.get("outputs") or 0)
    return ins, outs, hb.get("last_run_at")


# --------------------------------------------------------------- the probes
# Each returns (inputs, inputs_desc, last_output_iso_or_None, output_desc).
# Raising is allowed: the caller turns it into "unknown", never into green.

def probe_feedback_queue(days: float):
    """Client texts that carried a correction -> queued build work."""
    seen, blocks, _last = _hb_window("inbound-classify", days)
    since = _iso(NOW - timedelta(days=days))
    notes = _rows("/rest/v1/marketing_ops_notes?created_at=gte." + since
                  + "&select=id,body,created_at&order=created_at.desc&limit=500")
    filed = [n for n in notes
             if "ORIGIN: client-feedback" in (n.get("body") or "")]
    last = filed[0]["created_at"] if filed else _newest(
        "/rest/v1/marketing_ops_notes?body=like.*ORIGIN:%20client-feedback*",
        "created_at")
    if blocks < 0:
        # No heartbeat at all. NOT "quiet": either nothing has classified a
        # single inbound message since deploy (Monica's inbound path is down)
        # or the stamping itself is broken. Both are worth a card, and the
        # unknown-twice rule keeps the first pass after a deploy silent.
        return -1, ("the classify heartbeat has never been recorded — either "
                    "no inbound message has been classified since deploy, or "
                    "the stamping is broken"), last, \
            f"{len(filed)} card(s) in {days:g}d"
    return blocks, (f"{blocks} feedback block(s) found in {seen} classified "
                    f"message(s)"), last, f"{len(filed)} card(s) in {days:g}d"


def probe_meeting_sync(days: float):
    """Fathom meetings -> board work (fathom_sync owns the per-meeting check;
    this one only asks whether the pipeline is running and producing)."""
    from heartbeat import read  # noqa: F401  (kept for symmetry/imports)
    rows = _rows("/rest/v1/ops_kv?k=eq.fathom-sync-heartbeat&select=v")
    hb = (rows[0].get("v") or {}) if rows else {}
    if not hb:
        return 1, "fathom sync has no heartbeat at all", None, "never ran"
    cut = NOW - timedelta(days=days)
    meetings = sum(int(r.get("meetings") or 0) for r in (hb.get("runs") or [])
                   if (_parse(r.get("at")) or NOW) >= cut)
    return meetings, (f"{meetings} meeting(s) processed in {days:g}d "
                      f"(last run {str(hb.get('last_run_at'))[:16]})"), \
        hb.get("last_work_at"), "last card filed"


def probe_gbp_invites(_days: float):
    """Agency manager access on client GBPs — the one that was manual-only."""
    rows = _rows("/rest/v1/ops_kv?k=eq.gbp-manager-access&select=v")
    memo = (rows[0].get("v") or {}) if rows else {}
    checked = [v.get("checked_at") for v in memo.values()
               if isinstance(v, dict) and v.get("checked_at")]
    clients = _active_clients()
    return len(clients), f"{len(clients)} active client(s) to hold access on", \
        (max(checked) if checked else None), \
        f"{len(memo)} client(s) in the access memo"


def probe_citation_queue(days: float):
    """authority_targets -> get_listed rows (monthly Railway cron)."""
    clients = _active_clients()
    since = _iso(NOW - timedelta(days=days))
    n = _count("/rest/v1/marketing_action_plan?action_type=eq.get_listed"
               f"&created_at=gte.{since}")
    return len(clients), f"{len(clients)} active client(s)", \
        _newest("/rest/v1/marketing_action_plan?action_type=eq.get_listed",
                "created_at"), f"{n} target(s) queued in {days:g}d"


def probe_geogrid(days: float):
    """Bi-weekly map-rank scans (1st + 15th, Railway geogrid-cron)."""
    configured = [s for s in _active_clients()
                  if (ROOT / "clients" / s / "geogrid-keywords.txt").exists()
                  and (ROOT / "clients" / s / "geogrid-cities.json").exists()]
    since = _iso(NOW - timedelta(days=days))
    n = _count(f"/rest/v1/marketing_geogrid_scans?scanned_at=gte.{since}")
    return len(configured), f"{len(configured)} client(s) configured for " \
        "geo-grid", _newest("/rest/v1/marketing_geogrid_scans?id=not.is.null",
                            "scanned_at"), f"{n} scan(s) in {days:g}d"


def probe_bing_sweep(days: float):
    """Nightly browser-agent sweep (launchd 21:30 local, Santino's Mac)."""
    clients = _active_clients()
    since = _iso(NOW - timedelta(days=days))
    n = _count(f"/rest/v1/browser_agent_actions?created_at=gte.{since}")
    return len(clients), f"{len(clients)} active client(s) in the sweep " \
        "roster", _newest("/rest/v1/browser_agent_actions?id=not.is.null",
                          "created_at"), f"{n} action(s) in {days:g}d"


def probe_review_dispatcher(days: float):
    """Review reactivation drip — pending invitations must keep going out."""
    due = _count("/rest/v1/review_requests?status=eq.pending&next_send_at=lte."
                 + _iso(NOW))
    return due, f"{due} invitation(s) past their send time", \
        _newest("/rest/v1/review_requests?last_sent_at=not.is.null",
                "last_sent_at"), "last invitation sent"


def probe_dev_agent(days: float):
    """The nightly agent that DRAINS the feedback queue. A queue that fills
    and never empties is the same silence one step downstream."""
    since = _iso(NOW - timedelta(days=days))
    notes = _rows("/rest/v1/marketing_ops_notes?status=eq.open"
                  "&select=id,body,created_at&order=created_at.asc&limit=1000")
    devs = [n for n in notes if (n.get("body") or "").startswith("[DEV]")]
    waiting = [n for n in devs if (_age_days(n["created_at"]) or 0) > 1]
    done = _rows("/rest/v1/marketing_ops_notes?created_at=gte." + since
                 + "&select=id,body,created_at&order=created_at.desc&limit=500")
    outs = [n for n in done
            if (n.get("body") or "").startswith(
                ("[TODO-SANTINO] Review: dev agent",
                 "[TODO-SANTINO] Dev agent NEEDS INPUT"))]
    return len(waiting), (f"{len(devs)} open [DEV] task(s), {len(waiting)} "
                          "older than a day"), \
        (outs[0]["created_at"] if outs else None), \
        f"{len(outs)} task(s) closed out in {days:g}d"


# --------------------------------------------------------------- the roster
# quiet_days = how long this system may legitimately produce nothing WHILE it
# has inputs. Set from the schedule, with headroom for one missed run.
SYSTEMS: list[dict] = [
    {"key": "feedback-queue", "label": "client feedback -> build queue",
     "probe": probe_feedback_queue, "window": 3, "quiet_days": 2,
     "why": "a client texts a correction and it becomes queued work the same "
            "day; when this dies their words go nowhere and only Santino "
            "reading the thread catches it",
     "fix": "python3 scripts/feedback_router.py status   (then check the "
            "Railway API logs for [feedback] lines on /concierge-inbound)"},
    {"key": "meeting-sync", "label": "meetings -> board work",
     "probe": probe_meeting_sync, "window": 4, "quiet_days": 3,
     "why": "calls are where clients ask for the most, and the extraction is "
            "the only thing that turns them into cards",
     "fix": "python3 scripts/fathom_sync.py status && "
            "python3 scripts/fathom_sync.py watch"},
    {"key": "gbp-invites", "label": "GBP manager access",
     "probe": probe_gbp_invites, "window": 3, "quiet_days": 3,
     "why": "no manager access means no Bing listing and no profile "
            "management; this ran manual-only for three days in August and "
            "nobody could tell",
     "fix": "python3 scripts/gbp_admin_invite.py --dry-run"},
    {"key": "citation-queue", "label": "citation / get-listed targets",
     "probe": probe_citation_queue, "window": 40, "quiet_days": 40,
     "why": "the monthly authority cron is the only thing filling the "
            "get-listed queue the team works from",
     "fix": "python3 scripts/authority_targets.py --all --write --mode all "
            "(Railway service authority-cron, 1st of month)"},
    {"key": "geogrid", "label": "geo-grid map-rank scans",
     "probe": probe_geogrid, "window": 20, "quiet_days": 20,
     "why": "the map-rank grid is what the client dashboard shows for local "
            "rankings; a missed pair of runs leaves it frozen",
     "fix": "python3 scripts/geogrid_cron.py   (Railway service "
            "geogrid-cron, 08:00 UTC on the 1st and 15th)"},
    {"key": "bing-sweep", "label": "nightly Bing / browser-agent sweep",
     "probe": probe_bing_sweep, "window": 3, "quiet_days": 3,
     "why": "the sweep is what advances Bing Places listings and catches "
            "status changes; it runs on Santino's Mac, so a sleeping laptop "
            "stops it with no other symptom",
     "fix": "python3 -m browser_agent.sweep   (launchd "
            "io.rankai.browser-agent-sweep, 21:30 local)"},
    {"key": "review-dispatcher", "label": "review reactivation dispatcher",
     "probe": probe_review_dispatcher, "window": 2, "quiet_days": 1,
     "why": "invitations sitting past their send time are reviews we are not "
            "collecting, and the backlog hides the stall",
     "fix": "check the n8n review dispatcher workflow + "
            "review_requests.next_send_at"},
    {"key": "dev-agent", "label": "nightly dev agent (drains the queue)",
     "probe": probe_dev_agent, "window": 3, "quiet_days": 2,
     "why": "queued client work that never executes is worse than never "
            "queuing it: we told them it was handled",
     "fix": "gh run list --workflow dev-agent.yml   (nightly 09:07 UTC) && "
            "python3 scripts/dev_inbox.py list"},
]


def evaluate(system: dict) -> dict:
    """One system's verdict. Never raises."""
    out = {"key": system["key"], "label": system["label"],
           "state": "unknown", "inputs": None, "inputs_desc": "",
           "last_output": None, "output_desc": "", "age_days": None,
           "why": system["why"], "fix": system["fix"],
           "quiet_days": system["quiet_days"]}
    try:
        inputs, idesc, last, odesc = system["probe"](system["window"])
    except Exception as e:  # noqa: BLE001 — unknown, never green
        out["inputs_desc"] = f"probe failed: {str(e)[:140]}"
        return out
    age = _age_days(last)
    out.update({"inputs": inputs, "inputs_desc": idesc, "last_output": last,
                "output_desc": odesc, "age_days": age})
    if inputs is not None and inputs < 0:
        # A probe that cannot even tell whether there were inputs is unknown,
        # never green — "we lost the ability to see this" is its own outage.
        out["state"] = "unknown"
    elif not inputs:
        out["state"] = "quiet"
    elif last is None:
        out["state"] = "never"
    elif age is not None and age > system["quiet_days"]:
        out["state"] = "silent"
    else:
        out["state"] = "green"
    return out


def _fleet_company_id() -> str | None:
    """Where a fleet-level card lands: there is no agency row, so it goes on
    a stable long-standing client rather than nowhere at all (same choice
    fathom_sync.watch makes)."""
    try:
        from client_ops_sync import slug_map
        smap = slug_map()
    except Exception:  # noqa: BLE001
        return None
    for want in ("restorationxpress", "narestco"):
        for cid, slug in smap.items():
            if slug == want:
                return cid
    return next(iter(smap), None)


def compose_card(v: dict) -> str:
    head = ("has produced NOTHING, ever" if v["state"] == "never"
            else f"has produced nothing for {v['age_days']:.1f} days")
    lines = [
        f"[TODO-SANTINO] SILENT SYSTEM: {v['label']} {head}, while its inputs "
        "are live.",
        f"INPUTS: {v['inputs_desc']}",
        f"OUTPUT: {v['output_desc']}"
        + (f" — last one {str(v['last_output'])[:16]}" if v["last_output"]
           else " — none on record"),
        f"WHY IT MATTERS: {v['why']}",
        f"CHECK IT WITH: {v['fix']}",
        f"Expected to produce something at least every {v['quiet_days']} day(s).",
        f"ORIGIN: silence-watch | system={v['key']} | state={v['state']}",
    ]
    return "\n".join(lines)


def cmd_check(args) -> int:
    dry_run = not args.send
    verdicts = [evaluate(s) for s in SYSTEMS]
    if args.json:
        print(json.dumps(verdicts, indent=1, default=str))
    else:
        mark = {"green": "ok  ", "quiet": "idle", "silent": "DEAD",
                "never": "DEAD", "unknown": "??? "}
        print(f"silence watch — {NOW.strftime('%Y-%m-%d %H:%M UTC')}")
        for v in verdicts:
            age = ("never" if v["last_output"] is None
                   else f"{v['age_days']:.1f}d ago")
            print(f"  {mark[v['state']]} {v['label']:<38} "
                  f"{v['state']:<7} out:{age:<10} {v['inputs_desc'][:60]}")

    state = {}
    try:
        rows = _rows(f"/rest/v1/ops_kv?k=eq.{WATCH_KEY}&select=v")
        state = (rows[0].get("v") or {}) if rows else {}
    except Exception as e:  # noqa: BLE001
        print(f"  [watch] state read failed ({str(e)[:90]}) — cards may repeat")
    today = NOW.strftime("%Y-%m-%d")
    company_id = None
    fired = 0
    for v in verdicts:
        prev = state.get(v["key"]) or {}
        alarm = v["state"] in ("silent", "never")
        if v["state"] == "unknown":
            # Two unknowns A PASS APART is itself an outage: we have lost the
            # ability to tell. One is a flaky lookup, and two in the same
            # minute are one duplicate run (see UNKNOWN_CONFIRM_HOURS).
            prev_at = _parse(prev.get("at"))
            gap = None if prev_at is None else (
                (NOW - prev_at).total_seconds() / 3600)
            alarm = (prev.get("state") == "unknown" and gap is not None
                     and gap >= UNKNOWN_CONFIRM_HOURS)
            if alarm:
                v["output_desc"] = ("the check itself cannot read this "
                                    "system's output twice running — "
                                    + v["inputs_desc"])
        state[v["key"]] = {"state": v["state"], "at": _iso(NOW),
                           "last_card_on": prev.get("last_card_on")}
        if not alarm:
            continue
        if prev.get("last_card_on") == today:
            print(f"  [watch] {v['key']}: already carded today")
            continue
        body = compose_card(v)
        if dry_run:
            print(f"  [dry-run] would file:\n    "
                  + body.replace("\n", "\n    "))
            fired += 1
            continue
        company_id = company_id or _fleet_company_id()
        if not company_id:
            print(f"  [watch] {v['key']}: no company to file against")
            continue
        try:
            _sb("POST", "/rest/v1/marketing_ops_notes",
                {"company_id": company_id, "body": body, "status": "open",
                 "author": "silence-watch"}, prefer="return=minimal")
            state[v["key"]]["last_card_on"] = today
            fired += 1
            print(f"  CARD FILED: {v['label']} is {v['state']}")
        except Exception as e:  # noqa: BLE001
            print(f"  [watch] {v['key']}: card insert failed {str(e)[:110]}")
    if not dry_run:
        try:
            _sb("POST", "/rest/v1/ops_kv?on_conflict=k",
                {"k": WATCH_KEY, "v": state, "updated_at": _iso(NOW)},
                prefer="resolution=merge-duplicates,return=minimal")
        except Exception as e:  # noqa: BLE001
            print(f"  [watch] state write failed: {str(e)[:110]}")
    reds = [v for v in verdicts if v["state"] in ("silent", "never")]
    print(f"\n{len(reds)} silent system(s), {fired} card(s) "
          f"{'that would be filed' if dry_run else 'filed'}")
    # The watchdog's own proof of life — systems_pulse checks for it, because
    # a dead watchdog reports everything as fine by saying nothing at all.
    try:
        from heartbeat import stamp
        stamp("silence-watch", inputs=len(verdicts), outputs=len(reds),
              dry_run=dry_run,
              red=",".join(v["key"] for v in reds) or None)
    except Exception as e:  # noqa: BLE001
        print(f"  [watch] heartbeat warn: {str(e)[:90]}")
    return 0


def main() -> int:
    try:
        from client_concierge import load_env
        load_env()
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd")
    for name in ("check", "status"):
        p = sub.add_parser(name)
        p.add_argument("--send", action="store_true",
                       help="file cards for RED systems (check only)")
        p.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.cmd == "status":
        a.send = False
    elif a.cmd is None:
        a = ap.parse_args(["check"])
    return cmd_check(a)


if __name__ == "__main__":
    sys.exit(main())
