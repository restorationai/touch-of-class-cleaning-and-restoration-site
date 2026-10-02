#!/usr/bin/env python3
"""Dev-agent inbox — the approved [DEV] work queue (Santino 2026-07-30).

The nightly dev agent (a headless Claude Code run, .github/workflows/
dev-agent.yml) uses this to read its inbox and close out finished tasks.
[DEV] notes are created by: Santino's note composer (Site build tag), the
Fathom call listener's approved proposals, ad-hoc ops work, and — since
2026-08-05 — the concierge itself, when a client's own message says
something we built is wrong (scripts/feedback_router.py).

CLOSING THE LOOP (2026-08-05). A client-originated task is not finished when
the deploy is green. It is finished when the CLIENT knows. `done` therefore
files two things for a client-feedback task instead of one:
  * the usual [TODO-SANTINO] Review row, so Santino eyeballs the result, and
  * a [FROM SANTINO] directive telling Monica to text them that it is fixed,
    with the link — the message we had been writing by hand all night
    ("Made it dark and moody with black vehicles, take another look").
[FROM SANTINO] is a directive tag in client_concierge, so it bypasses the
cadence cooldown and goes out on the next pass instead of waiting for a
nudge slot. Both halves also land in marketing_work_log, so the client's
monthly report shows the request, the work and the reply as one story.

MONTHLY SUMMARY LINE (2026-08-11). Every `done` also lands one row in
marketing_work_log, which scripts/monthly_summary.py compiles into the
client's Monthly Summary tab in the app. The row's detail is the
`--client-line` when given — a sentence written FOR THE CLIENT (no file
names, no tool names, no jargon) — else a mechanically cleaned version of
the technical summary. Pass --client-line every time; the fallback is a
net, not a voice.

Commands:
    list                    open [DEV] notes as JSON (id, company_id, slug,
                            task, origin) — `origin` is non-null when the
                            task came from a client's own words
    count                   just the number (workflow gate — skip run when 0)
    done --id X --summary "what was done" [--client-line "plain sentence"]
                            [--link URL] [--no-notify]
                            resolve the note + file the [TODO-SANTINO] review
                            row + one client-readable marketing_work_log line;
                            for client-feedback tasks also file the
                            [FROM SANTINO] note that tells the client
    punt --id X --reason "why it could not be done safely"
                            resolve the note + file a question row instead
                            (a waiting client is named in the row; anything
                            already VERIFIED in its group goes to the client
                            as a progress update, never as "done")

LIVE PROOF BEFORE "DONE" (Santino 2026-10-02, All Pro / ProRestoration).
A client-feedback card for a website change (cat in WEB_CATS) closes ONLY
when its live checks pass. `done` fetches the LIVE site and checks:
    --area-add CITY / --area-remove CITY / --area-first CITY   (repeatable)
        service-area changes, checked on EVERY area list: the
        /service-areas/ page, the homepage list, the footer list and a
        header menu list when present. Required for cat=service_area.
    --verify "URL[#main|#footer|#header] has|lacks TEXT" / "URL status 301"
        generic checks (URL may be a path). At least one is required for
        every other website category.
    --surface-na "footer=lists the top 10 only"   (rare, recorded verbatim)
On ANY failure nothing is resolved and nobody is told anything: the card
stays open, its body records the check results, and the command exits 3.
Fix it and re-run, or punt (which tells the client what IS verified and
what is still in progress). Cards filed off one message share a `grp=`;
the client hears ONE message, after the last open card in the group
closes, naming what is verified and (if anything was punted) what is not.
"""
from __future__ import annotations

import argparse
import json
import os
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
from feedback_router import (WEB_CATS, check_area_lists,  # noqa: E402
                             check_spec, company_short_name,
                             compose_done_directive, compose_group_directive,
                             parse_origin, parse_verify_spec,
                             service_area_surfaces, site_status)


INBOX_PAGE = 1000


def _bucket_of(company_id: str) -> int:
    """Stable client->bucket assignment for parallel agent runs (Santino
    2026-09-03 scale-up). md5 so the split survives restarts and every
    client's tasks always land in the SAME bucket — two agents never touch
    the same client's files in the same run."""
    import hashlib as _hl
    buckets = max(1, int(os.environ.get("DEV_BUCKETS", "1") or 1))
    if buckets == 1:
        return 0
    return int(_hl.md5((company_id or "").encode()).hexdigest(), 16) % buckets


def open_devs() -> list[dict]:
    # EXPLICIT page + a loud warning when it fills (2026-08-05). The query
    # had no limit, so it inherited PostgREST's server cap — and with
    # created_at.asc the rows that fall off the end are the NEWEST ones, i.e.
    # a client's just-queued task would go missing from the inbox while
    # sitting perfectly well in the table. "Queued but invisible" is the same
    # failure as "never queued" to everyone downstream.
    # Server-side [DEV] prefix filter (2026-09-17): without it this page held
    # the oldest 1000 open notes of ANY tag, and once the never-resolved
    # non-[DEV] backlog crossed 1000 rows every new [DEV] note (sorted last
    # under created_at.asc) fell off the end — the inbox read count=0 for two
    # days while Rob's 09-15 site asks sat queued. %5B/%5D = URL-encoded [].
    notes = _sb("GET", "/rest/v1/marketing_ops_notes?status=eq.open"
                "&body=like.%5BDEV%5D*"
                "&select=id,company_id,body,created_at"
                f"&order=created_at.asc&limit={INBOX_PAGE}") or []
    if len(notes) >= INBOX_PAGE:
        print(f"WARNING: {INBOX_PAGE}+ open ops notes — the inbox page is "
              "full and the newest tasks may be cut off. Raise INBOX_PAGE.",
              file=sys.stderr)
    smap = slug_map()
    out = []
    my_bucket = int(os.environ.get("DEV_BUCKET", "0") or 0)
    buckets = max(1, int(os.environ.get("DEV_BUCKETS", "1") or 1))
    for n in notes:
        if not n["body"].startswith("[DEV]"):
            continue
        if buckets > 1 and _bucket_of(n["company_id"] or "") != my_bucket:
            continue
        out.append({"id": n["id"], "company_id": n["company_id"],
                    "slug": smap.get(n["company_id"]),
                    "task": n["body"][len("[DEV]"):].strip(),
                    "origin": parse_origin(n["body"]),
                    "created_at": n["created_at"]})
    return out


def _note(company_id: str, body: str) -> None:
    _sb("POST", "/rest/v1/marketing_ops_notes",
        {"company_id": company_id, "body": body})


def _handback_on_file(company_id: str, kind: str, task_text: str) -> bool:
    """True when an OPEN handback row of this kind already quotes the same
    task text for this client (2026-09-29: the dev agent drained 4 identical
    [SERVICE RIPPLE] re-files and filed 4 identical review / NEEDS INPUT
    rows each, ~200 of Santino's 981 open TODOs). One row per task text."""
    try:
        rows = _sb("GET", "/rest/v1/marketing_ops_notes?status=eq.open"
                   f"&company_id=eq.{company_id}&body=like.{quote(kind + '*')}"
                   "&select=body&limit=500") or []
    except Exception:  # noqa: BLE001 - dedupe is best-effort
        return False
    needle = f"(task was: {task_text})"
    return any(needle in (r.get("body") or "") for r in rows)


_CODE_FILE_RE = re.compile(
    r"\b(?:sites|scripts|clients|src|templates|workers)/[\w./-]+"
    r"|\b[\w-]+\.(?:py|ts|tsx|js|mjs|json|md|astro|yml|sql)\b")


def _plainify(text: str) -> str:
    """Fallback client-readable cleanup for an engineer-written summary:
    strip code ticks, file paths, bracket tags, URLs and em dashes. A real
    --client-line always beats this."""
    t = re.sub(r"`+", "", str(text or ""))
    t = re.sub(r"\[[A-Z][A-Z -]*\]", "", t)
    t = _CODE_FILE_RE.sub("", t)
    t = re.sub(r"https?://\S+", "", t)
    t = re.sub(r"\s*[—–]\s*", ", ", t)
    t = re.sub(r"\s{2,}", " ", t).strip(" ,;:")
    return t[:180]


def _log(company_id: str, action: str, detail: str, evidence: dict) -> None:
    """Ledger line, fail-open — bookkeeping never blocks the close-out."""
    try:
        from work_log import work_log
        work_log(company_id, "site", action, detail, evidence=evidence,
                 actor="dev-agent", source="dev_inbox.py")
    except Exception as e:  # noqa: BLE001
        print(f"  [work-log] warn: {str(e)[:90]}")


def close_the_loop(company_id: str, origin: dict, summary: str,
                   link: str | None, directive: str | None = None,
                   action: str = "client-feedback-notified") -> None:
    """File the [FROM SANTINO] note that sends the client their answer.

    Best-effort by design: the work is already done and already reviewable,
    so a failure here must not fail the task close-out. It prints loudly
    instead, and the [TODO-SANTINO] row (filed either way) is the backstop."""
    try:
        slug = origin.get("slug")
        if not link:
            _, _, link = site_status(company_id, slug)
        who = origin.get("who") or "the client"
        # CHANNEL FIDELITY (3b, 2026-09-13, the Angie rule): a request that
        # arrived by EMAIL gets its "it's done" on the SAME email thread,
        # from the same mailbox — not a text. The reply is queued in ops_kv;
        # email_intake (which holds the Gmail tokens) sends it on its next
        # pass, threaded under the original conversation.
        if origin.get("ch") == "email" and origin.get("eth"):
            from datetime import datetime, timezone
            key = (f"email-reply-queue:{company_id}:"
                   f"{int(datetime.now(timezone.utc).timestamp())}")
            _sb("POST", "/rest/v1/ops_kv?on_conflict=k",
                {"k": key, "v": {
                    "cid": company_id,
                    "acct": origin.get("acct") or "main",
                    "eth": origin.get("eth"),
                    "eto": origin.get("eto") or "",
                    "who": who, "summary": summary, "link": link,
                    "queued_at": datetime.now(timezone.utc).isoformat()}},
                prefer="resolution=merge-duplicates")
            print(f"loop closed: EMAIL reply queued — {who} hears it on "
                  "their own thread on the next mail pass")
        else:
            body = directive or compose_done_directive(origin, summary, link)
            _note(company_id, body)
            print(f"loop closed: [FROM SANTINO] filed — Monica tells {who} "
                  + ("what is verified and what is still in progress"
                     if "NOT DONE YET" in body else "it is done")
                  + (f" with {link}" if link else ""))
        _log(company_id, action,
             (f"Told {who} which parts of their website change are finished "
              f"and which are still in progress: {summary[:140]}"
              if action != "client-feedback-notified" else
              f"Told {who} their website change was done: {summary[:140]}"),
             {"who": who, "quote": (origin.get("quote") or "")[:300],
              "link": link, "category": origin.get("cat")})
    except Exception as e:  # noqa: BLE001
        print(f"WARNING: could not file the client notification ({e}). The "
              "review row is filed, so tell them by hand.", file=sys.stderr)


# ---------------------------------------------------------------- live proof
_UA = "Mozilla/5.0 (RankAI dev_inbox live-check)"


def _http_get(url: str, follow: bool = True) -> tuple[int | None, str]:
    """(status, html) for a LIVE url, cache-busted so a stale edge copy can
    never pass a check. Never raises."""
    import urllib.error
    import urllib.request
    import time as _t
    sep = "&" if "?" in url else "?"
    full = f"{url}{sep}_lc={int(_t.time())}"

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):  # noqa: D401
            return None
    opener = (urllib.request.build_opener() if follow
              else urllib.request.build_opener(_NoRedirect))
    try:
        req = urllib.request.Request(full, headers={
            "User-Agent": _UA, "Cache-Control": "no-cache"})
        with opener.open(req, timeout=25) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:  # noqa: BLE001
        print(f"  [live-check] fetch failed {url}: {str(e)[:90]}")
        return None, ""


def _abs(base: str, url: str) -> str:
    if url.startswith("http"):
        return url
    return base.rstrip("/") + "/" + url.lstrip("/")


def live_checks(base: str, *, area_add=(), area_remove=(), area_first=None,
                verify=(), surface_na=()) -> list[dict]:
    """Run every requested check against the LIVE site. Each row:
    {surface, url, ok, detail, human}."""
    rows: list[dict] = []
    na = {}
    for item in surface_na or ():
        k, _, why = str(item).partition("=")
        na[k.strip().lower()] = why.strip() or "declared n/a"
    if area_add or area_remove or area_first:
        surfaces = service_area_surfaces(base)
        pages = {}
        for _, url, _, _ in surfaces:
            if url not in pages:
                pages[url] = _http_get(url)[1]
        rows += check_area_lists(pages, surfaces, add=list(area_add),
                                 remove=list(area_remove), first=area_first,
                                 na=na)
    for spec in verify or ():
        parsed = parse_verify_spec(spec)
        if not parsed:
            rows.append({"surface": spec, "url": "", "ok": False,
                         "detail": "unparseable --verify spec (use 'URL[#scope] "
                                   "has|lacks TEXT' or 'URL status CODE')",
                         "human": None})
            continue
        url, scope, op, arg = parsed
        url = _abs(base, url)
        status, html = _http_get(url, follow=(op != "status"))
        ok, detail = check_spec(html, status, scope, op, arg)
        rows.append({"surface": f"{url}{'#' + scope if scope else ''}",
                     "url": url, "ok": ok, "detail": detail,
                     "human": f"{arg} {'on' if op == 'has' else 'off'} "
                              f"{url.split('://', 1)[-1]}"
                     if op != "status" else None})
    return rows


_CHECK_BLOCK_RE = re.compile(r"\nLIVE CHECK [^\n]*(?:\n  [^\n]*)*", re.M)


def _record_checks(note: dict, rows: list[dict], verdict: str) -> str:
    """Replace the card's LIVE CHECK block with this run's results (one
    block, newest wins) and return the new body."""
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%MZ")
    block = (f"\nLIVE CHECK {stamp}: {verdict}\n"
             + "\n".join(f"  {'OK  ' if r['ok'] else 'FAIL'} {r['surface']}: "
                         f"{r['detail'][:140]}" for r in rows))
    body = _CHECK_BLOCK_RE.sub("", note["body"]) + block
    _sb("PATCH", f"/rest/v1/marketing_ops_notes?id=eq.{note['id']}",
        {"body": body})
    note["body"] = body
    return body


def _append_marker(note: dict, line: str) -> None:
    body = note["body"].rstrip() + "\n" + line
    _sb("PATCH", f"/rest/v1/marketing_ops_notes?id=eq.{note['id']}",
        {"body": body})
    note["body"] = body


def _group_notes(grp: str) -> list[dict]:
    """Every card filed off the same client message (any company)."""
    try:
        return _sb("GET", "/rest/v1/marketing_ops_notes?body=like."
                   + quote(f"*grp={grp}*")
                   + "&select=id,company_id,body,status,created_at"
                   "&order=created_at.asc&limit=50") or []
    except Exception as e:  # noqa: BLE001
        print(f"  [group] lookup failed ({str(e)[:90]}) — treating as single")
        return []


_VERIFIED_RE = re.compile(r"^DONE-VERIFIED [^|]*\| (.*?) \| link=(\S*)", re.M)


def _short(origin: dict | None, fallback: str = "") -> str:
    return company_short_name((origin or {}).get("company") or fallback)


def notify_group(note: dict, origin: dict, *, punted: bool = False) -> str:
    """Tell the client about a group once nothing in it is still being
    worked tonight. Returns what happened (for the review row)."""
    grp = origin.get("grp")
    members = _group_notes(grp) if grp else []
    if not any(m["id"] == note["id"] for m in members):
        members.append(note)
    # A sibling the agent can still finish keeps the message on hold: the
    # client hears ONE truthful message, not "done" for half the ask.
    waiting = [m for m in members if m["id"] != note["id"]
               and m.get("status") == "open"
               and (m.get("body") or "").startswith("[DEV]")]
    if waiting:
        names = ", ".join(sorted({_short(parse_origin(m["body"]), "?")
                                  for m in waiting}))
        print(f"client update HELD: {len(waiting)} card(s) in this request "
              f"are still open ({names}); the last one to close sends ONE "
              "message covering all of them")
        return "held until the rest of the request is verified"
    multi = len({m.get("company_id") for m in members}) > 1
    done, pending, links, told = [], [], [], []
    for m in members:
        b = m.get("body") or ""
        if "\nCLIENT-TOLD-DONE" in b:
            continue
        o = parse_origin(b) or {}
        tag = (_short(o) + ": ") if multi else ""
        v = _VERIFIED_RE.search(b)
        if v:
            done.append(tag + v.group(1).strip())
            if v.group(2) and v.group(2) not in links:
                links.append(v.group(2))
            told.append(m)
        else:
            pending.append(tag + (o.get("what") or "the rest of the request"))
    if not done:
        print("client update: nothing verified yet, nothing to tell")
        return "nothing verified, client not told"
    directive = compose_group_directive(
        origin.get("who") or "the client", origin.get("quote") or "",
        done, pending, links,
        verified=all("LIVE CHECK" in (m.get("body") or "") for m in told))
    # `summary` is what an EMAIL-channel reply says verbatim (email_intake
    # has no LLM pass), so it never quotes our internal task wording.
    summary = "; ".join(done)[:300] + (
        ". We are still finishing the rest of this request and will let you "
        "know as soon as that part is live too" if pending else "")
    close_the_loop(note["company_id"], origin, summary,
                   links[0] if links else None, directive=directive,
                   action=("client-feedback-progress" if pending
                           else "client-feedback-notified"))
    for m in told:
        _append_marker(m, "CLIENT-TOLD-DONE "
                       + datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    return ("client told what is verified and what is still in progress"
            if pending else "client told it is done (verified live)")


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    sub.add_parser("count")
    pd = sub.add_parser("done")
    pd.add_argument("--id", required=True)
    pd.add_argument("--summary", required=True)
    pd.add_argument("--client-line", default="",
                    help="the same fact in words the CLIENT reads in their "
                         "monthly summary: no file names, no jargon, no "
                         "internal tool names (falls back to a cleaned "
                         "version of --summary)")
    pd.add_argument("--link", default="",
                    help="the URL to hand the client (defaults to the site's "
                         "current apex or preview URL)")
    pd.add_argument("--no-notify", action="store_true",
                    help="skip the client notification — use ONLY when the "
                         "change is not yet visible to them")
    # LIVE PROOF (2026-10-02): required for client-feedback website cards.
    pd.add_argument("--area-add", action="append", default=[],
                    metavar="CITY", help="city that must now be on EVERY "
                    "live area list (repeatable)")
    pd.add_argument("--area-remove", action="append", default=[],
                    metavar="CITY", help="city that must be gone from EVERY "
                    "live area list (repeatable)")
    pd.add_argument("--area-first", default=None, metavar="CITY",
                    help="city that must be FIRST on every live area list")
    pd.add_argument("--verify", action="append", default=[], metavar="SPEC",
                    help="'URL[#main|#footer|#header] has|lacks TEXT' or "
                         "'URL status CODE' (repeatable; URL may be a path)")
    pd.add_argument("--surface-na", action="append", default=[],
                    metavar="SURFACE=WHY", help="declare an area-list surface "
                    "not applicable, e.g. 'footer=lists the top 10 only' "
                    "(recorded on the card and in Santino's review row)")
    pd.add_argument("--base", default="",
                    help="site base URL to verify against (defaults to the "
                         "live apex, else the preview URL on file)")
    pp = sub.add_parser("punt")
    pp.add_argument("--id", required=True)
    pp.add_argument("--reason", required=True)
    a = ap.parse_args()

    if a.cmd == "list":
        print(json.dumps(open_devs(), indent=1))
        return 0
    if a.cmd == "count":
        print(len(open_devs()))
        return 0

    rows = _sb("GET", f"/rest/v1/marketing_ops_notes?id=eq.{a.id}"
               "&select=id,company_id,body,status") or []
    if not rows:
        print(f"ERROR: note {a.id} not found", file=sys.stderr)
        return 1
    note = rows[0]
    origin = parse_origin(note["body"])
    task_text = note["body"][:120]
    cat = str((origin or {}).get("cat") or "other").lower()
    base = ""
    proof_line = ""
    # NEVER "DONE" BEFORE IT IS VERIFIED EVERYWHERE (Santino 2026-10-02).
    # The card is checked against the LIVE site BEFORE anything is resolved;
    # a failure leaves it open and tells nobody anything.
    # Checks the agent passes always run (a meeting card is cat=other but
    # may still be a site change); WEB_CATS cards cannot close without them.
    has_area = a.cmd == "done" and bool(a.area_add or a.area_remove
                                        or a.area_first)
    has_checks = a.cmd == "done" and (has_area or bool(a.verify))
    needs_proof = (a.cmd == "done" and bool(origin) and not a.no_notify
                   and (cat in WEB_CATS or has_checks))
    if needs_proof:
        if cat == "service_area" and not has_area:
            print("REFUSED: a service-area card closes only with live proof "
                  "on every area list. Re-run with --area-add / "
                  "--area-remove / --area-first CITY (the card stays open).",
                  file=sys.stderr)
            return 2
        if not has_area and not a.verify:
            print("REFUSED: a client-feedback website card closes only with "
                  "live proof. Re-run with --verify 'URL[#scope] has|lacks "
                  "TEXT' for every page/list the change appears on (the "
                  "card stays open).", file=sys.stderr)
            return 2
        base = a.base.strip()
        if not base:
            _, _, base = site_status(note["company_id"], origin.get("slug"))
        if not base:
            print("REFUSED: no live or preview URL on file to verify against; "
                  "pass --base URL (the card stays open).", file=sys.stderr)
            return 2
        checks = live_checks(base, area_add=a.area_add,
                             area_remove=a.area_remove,
                             area_first=a.area_first, verify=a.verify,
                             surface_na=a.surface_na)
        failed = [r for r in checks if not r["ok"]]
        for r in checks:
            print(f"  {'OK  ' if r['ok'] else 'FAIL'} {r['surface']}: "
                  f"{r['detail'][:120]}")
        if not checks or failed:
            _record_checks(note, checks, "FAILED, card stays open, client "
                           "NOT told")
            print(f"LIVE CHECK FAILED on {len(failed) or 'all'} check(s) at "
                  f"{base}. Nothing resolved and the client was told nothing. "
                  "Fix every failing surface (deploy, wait for it to go live) "
                  "and re-run done, or punt with what is still open.",
                  file=sys.stderr)
            return 3
        _record_checks(note, checks, "PASSED")
        nas = [r["detail"] for r in checks if "n/a by agent" in r["detail"]]
        proof_line = (f" Live-verified at {base} ({len(checks)} checks"
                      + (f"; {'; '.join(nas)}" if nas else "") + ").")

    now = datetime.now(timezone.utc).isoformat()
    _sb("PATCH", f"/rest/v1/marketing_ops_notes?id=eq.{a.id}",
        {"status": "resolved", "resolved_at": now})
    note["status"] = "resolved"
    if a.cmd == "done" and not origin and _handback_on_file(
            note["company_id"], "[TODO-SANTINO] Review: dev agent finished",
            task_text):
        print("resolved (identical review row already open, not re-filed)")
    elif a.cmd == "done":
        client_line = a.client_line.strip() or _plainify(a.summary)
        outcome = ""
        if origin and not a.no_notify:
            if needs_proof or origin.get("grp"):
                link = a.link.strip() or (
                    base.rstrip("/") + "/service-areas/"
                    if base and cat == "service_area" else base) or ""
                if not link:
                    _, _, link = site_status(note["company_id"],
                                             origin.get("slug"))
                _append_marker(note, "DONE-VERIFIED "
                               + now[:10] + " | "
                               + client_line.replace("|", ",")[:220]
                               + f" | link={link or ''}")
                outcome = notify_group(note, origin)
            else:
                close_the_loop(note["company_id"], origin, client_line,
                               a.link.strip() or None)
                outcome = "client told it is done"
        _note(note["company_id"],
              f"[TODO-SANTINO] Review: dev agent finished — {a.summary}"
              f"{proof_line} "
              f"(task was: {note['body'][:120]}) Hit Done after you eyeball it."
              + (f" CLIENT WAITING: {origin.get('who')} asked for this; "
                 f"{outcome or 'client NOT notified (--no-notify)'}."
                 if origin else ""))
        print("resolved + review row filed")
        # One client-readable ledger line per completed task — this is what
        # the app's Monthly Summary tab shows the client (monthly_summary.py
        # prefers evidence.client_line over the technical detail).
        if origin:
            _log(note["company_id"], "client-feedback-done",
                 f"Made the website change {origin.get('who') or 'the client'} "
                 f"asked for: {client_line[:140]}",
                 {"quote": (origin.get("quote") or "")[:300],
                  "category": origin.get("cat"), "note_id": a.id,
                  "summary": a.summary[:200], "client_line": client_line,
                  "live_verified": bool(needs_proof)})
            if a.no_notify:
                print("client notification SKIPPED (--no-notify) — the "
                      "review row still names them as waiting")
        else:
            _log(note["company_id"], "dev-task-done",
                 f"Website work completed: {client_line[:150]}",
                 {"note_id": a.id, "summary": a.summary[:200],
                  "client_line": client_line})
    elif _handback_on_file(note["company_id"],
                           "[TODO-SANTINO] Dev agent NEEDS INPUT", task_text):
        print("resolved (identical NEEDS INPUT row already open, not re-filed)")
    else:
        # A punted card in a multi-card request: whatever the rest of the
        # request already VERIFIED goes to the client as a progress update
        # (never "done"), and this card is named as still in progress.
        told = ""
        if origin and origin.get("grp"):
            told = notify_group(note, origin, punted=True)
        _note(note["company_id"],
              f"[TODO-SANTINO] Dev agent NEEDS INPUT: {a.reason} "
              f"(task was: {note['body'][:120]})"
              + (f" A CLIENT IS WAITING ON THIS: {origin.get('who')} said "
                 f"\"{(origin.get('quote') or '')[:120]}\" — "
                 + (f"{told}." if told and "told" in told and "not told"
                    not in told else "they have not been told anything yet.")
                 if origin else ""))
        print("resolved + needs-input row filed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
