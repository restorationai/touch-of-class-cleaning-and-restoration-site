#!/usr/bin/env python3
"""backfill_sept_2026_work.py — one-shot: September 2026 client work that ran
before its system logged to the Reports tab (Santino 2026-09-29: "any work
we're doing for any client ... gets documented in the reports tab as work").

Writes the SAME rows the now-fixed systems write going forward, dated at the
real event time, each tagged evidence/meta {"backfill": "2026-09-29", ...}:

  marketing_work_log
    lsa-lead-feedback     ops_kv lsa-lead-review:{cid}:{lead} verdicts Google accepted
    award-added           git: brand.ts `awards:` names that appeared
    ai-answers-added      git: llms.txt gained the AI-answers block
    ai-answers-refresh    git: llms.txt AI-answers block changed (one per client-day)
    pages-rendered        git: "render sweep:" commits, files that gained rendered: true
    services-added-to-site  marketing_ops_notes "[SERVICE RIPPLE] slug: added ..."
    favicon-logo          git: favicon.svg switched from a text glyph to the logo
    review-snippets-sync  git: brand.ts gbpReviewCount/gbpReviews changed in [automated] commits
    office-scout          ops_kv office-scout:{cid}
    location-scout        marketing_location_scout current shortlist (scanned_at)
  marketing_gbp_changes
    review_reply          GitHub Actions logs: review_responder "N replied" lines
    profile_service_areas GitHub Actions logs: gbp_parity "GBP serviceArea -> updated"

Idempotent: a candidate is skipped when a row with the same company, action /
change_type and UTC day already exists. Dry run by default.

  python3 scripts/oneshots/backfill_sept_2026_work.py                 # dry run
  python3 scripts/oneshots/backfill_sept_2026_work.py --apply
  --ghlogs DIR   filtered Actions log lines (review replies + parity areas);
                 see fetch notes at the bottom of this file
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import client_ops_sync as cos  # noqa: E402

cos.load_env()
from client_ops_sync import _sb  # noqa: E402
from work_log import company_id_for_slug  # noqa: E402
import ai_answers  # noqa: E402
import lsa_lead_review as llr  # noqa: E402
import render_sweep  # noqa: E402

SINCE, UNTIL = "2026-09-01", "2026-10-01"
TAG = "2026-09-29"
BEGIN, END = ai_answers.BEGIN, ai_answers.END


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True,
                          text=True, timeout=300).stdout


def show(rev: str, path: str) -> str:
    r = subprocess.run(["git", "-C", str(ROOT), "show", f"{rev}:{path}"],
                       capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


def commits(*paths: str, grep: str | None = None, extra: tuple = ()) -> list[tuple[str, str, str]]:
    """(sha, iso date, subject) oldest first, touching paths in September."""
    args = ["log", "--reverse", "--pretty=%H|%aI|%s", f"--since={SINCE}T00:00:00Z",
            f"--until={UNTIL}T00:00:00Z", *extra]
    if grep:
        args += [f"--grep={grep}"]
    out = []
    for row in git(*args, "--", *paths).splitlines():
        sha, when, subj = row.split("|", 2)
        out.append((sha, when, subj))
    return out


def touched_slugs(sha: str, pattern: str) -> set[str]:
    rx = re.compile(pattern)
    return {m.group(1) for f in git("show", "--name-only", "--format=", sha).splitlines()
            if (m := rx.match(f))}


def utc(ts: str) -> str:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()


# --------------------------------------------------------------- candidates
WL: list[dict] = []     # marketing_work_log rows
GC: list[dict] = []     # marketing_gbp_changes rows


def wl(cid, category, action, detail, ts, evidence, source):
    if cid:
        WL.append({"company_id": cid, "category": category, "action": action,
                   "detail": detail, "ts": utc(ts), "actor": "automation",
                   "source": f"{source} (backfill)",
                   "evidence": {**(evidence or {}), "backfill": TAG}})


def gc(cid, change_type, summary, ts, meta):
    if cid:
        GC.append({"company_id": cid, "change_type": change_type, "summary": summary[:300],
                   "changed_at": utc(ts), "actor": "automation",
                   "meta": {**(meta or {}), "backfill": TAG}})


def lsa_feedback() -> None:
    rows = _sb("GET", "/rest/v1/ops_kv?k=like.lsa-lead-review:CO-*&select=k,v") or []
    groups: dict[tuple, list] = defaultdict(list)
    for r in rows:
        k, v = r["k"], r["v"] or {}
        if k.count(":") != 2 or not llr.sent_ok(v.get("credit_decision")):
            continue
        when = v.get("reviewed_at") or ""
        if not (SINCE <= when[:10] < UNTIL):
            continue
        groups[(k.split(":")[1], when[:10])].append(v)
    for (cid, _day), vs in sorted(groups.items()):
        good = sum(1 for v in vs if v.get("verdict") == "good")
        bad = [v for v in vs if v.get("verdict") == "bad"]
        credits = sum(1 for v in vs if str(v.get("credit_decision")).startswith("SUCCESS"))
        wl(cid, "ads", "lsa-lead-feedback",
           llr.work_line(good, len(bad), credits, [v.get("dissatisfied_reason") for v in bad]),
           max(v["reviewed_at"] for v in vs),
           {"good": good, "bad": len(bad), "credits": credits,
            "from": "ops_kv lsa-lead-review verdicts"}, "lsa_lead_review.py")


def _block(text: str) -> str | None:
    m = re.search(re.escape(BEGIN) + r".*?" + re.escape(END), text, re.S)
    return m.group(0) if m else None


def _awards(text: str) -> dict:
    m = re.search(r"^\s*awards:\s*(\[.*?\])\s+as\b", text, re.M)
    try:
        return {a["name"]: a for a in json.loads(m.group(1)) if a.get("name")} if m else {}
    except (json.JSONDecodeError, AttributeError):
        return {}


def ai_answers_and_awards() -> None:
    refresh_days: set = set()
    for sha, when, _ in commits("sites/*/public/llms.txt"):
        for slug in touched_slugs(sha, r"sites/([^/]+)/public/llms\.txt$"):
            p = f"sites/{slug}/public/llms.txt"
            before, after = _block(show(f"{sha}^", p)), _block(show(sha, p))
            if not after or before == after:
                continue
            cid = company_id_for_slug(slug)
            if not before:
                wl(cid, "site", "ai-answers-added",
                   "Added a direct-answers section to your website for AI assistants "
                   "(ChatGPT, Google AI Overviews and others), answering \"who is the best "
                   "company near me\" questions with your real reviews, credentials and "
                   "phone number.", when, {"commit": sha[:10]}, "ai_answers.py")
            elif (slug, when[:10]) not in refresh_days:
                refresh_days.add((slug, when[:10]))
                wl(cid, "site", "ai-answers-refresh",
                   "Your website's answers for AI assistants were refreshed with your "
                   "latest reviews and credentials.", when, {"commit": sha[:10]},
                   "ai_answers.py")
    for sha, when, _ in commits("sites/*/src/lib/brand.ts", extra=("-G", "awards: \\[")):
        for slug in touched_slugs(sha, r"sites/([^/]+)/src/lib/brand\.ts$"):
            p = f"sites/{slug}/src/lib/brand.ts"
            before, after = _awards(show(f"{sha}^", p)), _awards(show(sha, p))
            for name, a in after.items():
                if name not in before:
                    wl(company_id_for_slug(slug), "site", "award-added",
                       f"Your award is now featured on your website: {ai_answers.award_label(a)}. "
                       "It leads your trust badges, homepage description and the "
                       "search-engine data Google and AI assistants read.",
                       when, {"award": a, "commit": sha[:10]}, "ai_answers.py")


def render_sweeps() -> None:
    for sha, when, subj in commits("sites", grep="^render sweep:"):
        m = re.match(r"render sweep: (\S+) pending pages", subj)
        if not m:
            continue
        slug = m.group(1)
        diff = git("show", "--format=", "--unified=0", sha, "--", f"sites/{slug}/src/content")
        rendered, cur = set(), None
        for ln in diff.splitlines():
            if ln.startswith("+++ b/"):
                cur = ln[6:].split(f"sites/{slug}/src/content/", 1)[-1]
            elif cur and re.match(r"^\+rendered:\s*true\b", ln):
                rendered.add(cur)
        if not rendered:
            continue
        # live at the time = the site had ALREADY been pushed to its
        # production branch (render_sweep's own rule): the first commit where
        # clients/{slug}.json carried build.last_pushed_main_at.
        first = git("log", "--reverse", "--pretty=%aI", "-S", '"last_pushed_main_at"',
                    "--", f"clients/{slug}.json").split()
        live = bool(first) and utc(first[0]) <= utc(when)
        wl(company_id_for_slug(slug), "site", "pages-rendered",
           render_sweep.pages_line(rendered, live), when,
           {"pages": sorted(rendered)[:200], "commit": sha[:10]}, "render_sweep.py")


def service_ripple() -> None:
    for r in _sb("GET", "/rest/v1/marketing_ops_notes?author=eq.service_ripple"
                 f"&created_at=gte.{SINCE}&created_at=lt.{UNTIL}"
                 "&body=like.%5BSERVICE%20RIPPLE%5D*&select=company_id,created_at,body") or []:
        m = re.match(r"\[SERVICE RIPPLE\] \S+: added (.+?) from the truth table", r["body"] or "")
        if not m:
            continue
        labels = [s.strip().replace("-", " ") for s in m.group(1).split(",")]
        wl(r["company_id"], "site", "services-added-to-site",
           f"Your website is growing to cover more of the services you offer: "
           f"{', '.join(labels)}. The new pages are being written and go live over "
           "the next few nights.", r["created_at"], {"services": labels}, "service_ripple.py")


def favicons() -> None:
    for sha, when, _ in commits("sites/*/public/favicon.svg"):
        for slug in touched_slugs(sha, r"sites/([^/]+)/public/favicon\.svg$"):
            p = f"sites/{slug}/public/favicon.svg"
            if "<text" in show(f"{sha}^", p) and "data:image/png;base64" in show(sha, p):
                wl(company_id_for_slug(slug), "site", "favicon-logo",
                   "Your logo is now the icon on your website's browser tab and phone "
                   "home-screen shortcut.", when, {"commit": sha[:10]}, "favicon_sync.py")


def review_snippets() -> None:
    days: set = set()
    rx = re.compile(r'gbpReviewCount:\s*"([^"]*)"')
    for sha, when, subj in commits("sites/*/src/lib/brand.ts",
                                   extra=("-G", r"gbpReviewCount|gbpReviews")):
        if "[automated]" not in subj or not subj.startswith("chore:"):
            continue
        for slug in touched_slugs(sha, r"sites/([^/]+)/src/lib/brand\.ts$"):
            if (slug, when[:10]) in days:
                continue
            p = f"sites/{slug}/src/lib/brand.ts"
            b, a = show(f"{sha}^", p), show(sha, p)
            rb, ra = rx.search(b), rx.search(a)
            snip_b = re.search(r"gbpReviews:\s*\[.*?\]", b, re.S)
            snip_a = re.search(r"gbpReviews:\s*\[.*?\]", a, re.S)
            if (rb and ra and rb.group(1) != ra.group(1)) or \
                    ((snip_b and snip_b.group(0)) != (snip_a and snip_a.group(0))):
                days.add((slug, when[:10]))
                wl(company_id_for_slug(slug), "site", "review-snippets-sync",
                   "Your website's Google star rating, review count and newest review "
                   "quotes kept in sync with your Google profile.", when,
                   {"commit": sha[:10], "count": ra.group(1) if ra else None},
                   "sync_brand_reviews.py")


def scouts() -> None:
    for r in _sb("GET", "/rest/v1/ops_kv?k=like.office-scout:CO-*&select=k,v") or []:
        v = r["v"] or {}
        gen = v.get("generated_at") or ""
        if not (SINCE <= gen[:10] < UNTIL):
            continue
        towns = [t.get("town") for t in v.get("towns") or [] if t.get("town")]
        n = sum(len(t.get("options") or []) for t in v.get("towns") or [])
        if n:
            wl(v.get("company_id") or r["k"].split(":", 1)[1], "research", "office-scout",
               f"Office search delivered in your app: {n} rentable space{'s' if n != 1 else ''} "
               f"rated for a second Google listing in {', '.join(towns[:5])}, with the best "
               "contact to call for each.", gen, {"towns": towns, "options": n},
               "office_scout.py")
    per: dict[str, list] = defaultdict(list)
    for r in _sb("GET", "/rest/v1/marketing_location_scout"
                 f"?scanned_at=gte.{SINCE}&select=company_id,seat_city,scanned_at") or []:
        per[r["company_id"]].append(r)
    for cid, rs in per.items():
        wl(cid, "research", "location-scout",
           "Second-location research refreshed in your app: the best nearby towns for "
           "another Google listing, ranked by local demand and reach.",
           max(r["scanned_at"] for r in rs), {"towns": [r["seat_city"] for r in rs]},
           "location_scout.py")


def from_action_logs(logdir: Path) -> None:
    """Review replies + parity service-area writes from filtered Actions logs
    (one file per run: tab-separated `job<TAB>step<TAB>timestamp message`)."""
    ts_rx = re.compile(r"^(\d{4}-\d{2}-\d{2}T[\d:.]+Z) (.*)$")
    seen_reply: set = set()
    for f in sorted(logdir.glob("*.txt")):
        posts: dict[str, list] = defaultdict(list)
        summaries: list[tuple] = []
        cur_slug, adds, drops = None, [], []
        for raw in f.read_text(errors="ignore").splitlines():
            msg = raw.split("\t")[-1]
            m = ts_rx.match(msg)
            if not m:
                continue
            ts, body = m.groups()
            if (pm := re.match(r"\s*\[([a-z0-9-]+)\] (\d)★ (.*?): POST ->", body)):
                posts[pm.group(1)].append(f"{(pm.group(3).split() or ['a customer'])[0]} "
                                          f"({pm.group(2)} stars)")
            elif (sm := re.match(r"([a-z0-9-]+): (\d+) replied,", body)):
                summaries.append((sm.group(1), int(sm.group(2)), ts))
            elif (hm := re.match(r"== ([a-z0-9-]+)$", body)):
                cur_slug, adds, drops = hm.group(1), [], []
            elif body.strip().startswith("add: "):
                adds = [re.sub(r"\s*\([\d.]+mi\)$", "", c).strip()
                        for c in body.strip()[5:].split(", ")]
            elif body.strip().startswith("drop (too far): "):
                drops = [c.strip() for c in body.strip()[16:].split(", ")]
            elif "GBP serviceArea -> updated" in body and cur_slug:
                # 09-18 RX wipe: that pre-guard write (no read-back) erased
                # RestorationXpress's areas; never report it as work.
                if cur_slug == "restorationxpress" and "verified" not in body:
                    continue
                nm = re.search(r"updated \((\d+) places", body)
                bits = []
                if adds:
                    bits.append("added " + ", ".join(adds[:8]))
                if drops:
                    bits.append("replaced farther areas " + ", ".join(drops[:6]))
                gc(company_id_for_slug(cur_slug), "profile_service_areas",
                   "Service areas on your Google listing updated to your closest "
                   f"{nm.group(1) if nm else 20} cities"
                   + (f" ({'; '.join(bits)})" if bits else "") + ".", ts,
                   {"added": adds, "dropped": drops, "source": "gbp_parity.py",
                    "run": f.stem})
        for slug, n, ts in summaries:
            if not n or (slug, ts[:10]) in seen_reply:
                continue
            seen_reply.add((slug, ts[:10]))
            names = posts.get(slug, [])[:n]
            gc(company_id_for_slug(slug), "review_reply",
               f"Replied to {n} new Google review{'s' if n != 1 else ''} on your profile"
               + (f": {', '.join(names[:6])}" + (" and more" if n > 6 else "") if names else "")
               + ".", ts, {"replies": n, "source": "review_responder.py", "run": f.stem})


# --------------------------------------------------------------- write
def existing(table: str, day_col: str, key_col: str) -> set:
    out, off = set(), 0
    while True:
        rows = _sb("GET", f"/rest/v1/{table}?{day_col}=gte.{SINCE}&{day_col}=lt.{UNTIL}"
                   f"&select=company_id,{key_col},{day_col}&limit=1000&offset={off}") or []
        out |= {(r["company_id"], r[key_col], (r[day_col] or "")[:10]) for r in rows}
        if len(rows) < 1000:
            return out
        off += 1000


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--ghlogs", help="dir of filtered Actions log lines (*.txt)")
    a = ap.parse_args()
    for fn in (lsa_feedback, ai_answers_and_awards, render_sweeps, service_ripple,
               favicons, review_snippets, scouts):
        try:
            fn()
        except Exception as e:  # noqa: BLE001 — one source never kills the rest
            print(f"[warn] {fn.__name__}: {str(e)[:160]}")
    if a.ghlogs:
        from_action_logs(Path(a.ghlogs))

    have_wl = existing("marketing_work_log", "ts", "action")
    have_gc = existing("marketing_gbp_changes", "changed_at", "change_type")
    new_wl = [r for r in WL if (r["company_id"], r["action"], r["ts"][:10]) not in have_wl]
    new_gc = [r for r in GC if (r["company_id"], r["change_type"], r["changed_at"][:10]) not in have_gc]
    # one per key within this batch too
    seen, uniq_wl = set(), []
    for r in new_wl:
        k = (r["company_id"], r["action"], r["ts"][:10], r["detail"])
        if k not in seen:
            seen.add(k)
            uniq_wl.append(r)
    seen, uniq_gc = set(), []
    for r in new_gc:
        k = (r["company_id"], r["change_type"], r["changed_at"][:10])
        if k not in seen:
            seen.add(k)
            uniq_gc.append(r)

    cnt = defaultdict(int)
    for r in uniq_wl:
        cnt[f"work_log/{r['action']}"] += 1
    for r in uniq_gc:
        cnt[f"gbp_changes/{r['change_type']}"] += 1
    print(json.dumps(dict(sorted(cnt.items())), indent=1))
    print(f"candidates: {len(WL)} work_log, {len(GC)} gbp_changes; new after dedupe: "
          f"{len(uniq_wl)} + {len(uniq_gc)}")
    for r in (uniq_wl + uniq_gc)[:400]:
        print(f"  {(r.get('ts') or r.get('changed_at'))[:10]} {r['company_id']} "
              f"{r.get('action') or r.get('change_type')}: "
              f"{(r.get('detail') or r.get('summary'))[:130]}")
    if not a.apply:
        print("[dry run] re-run with --apply to write")
        return 0
    for i in range(0, len(uniq_wl), 200):
        _sb("POST", "/rest/v1/marketing_work_log", uniq_wl[i:i + 200], prefer="return=minimal")
    for i in range(0, len(uniq_gc), 200):
        _sb("POST", "/rest/v1/marketing_gbp_changes", uniq_gc[i:i + 200], prefer="return=minimal")
    print(f"wrote {len(uniq_wl)} work_log + {len(uniq_gc)} gbp_changes rows (tagged backfill {TAG})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# Actions log fetch used for --ghlogs (2026-09-29): for every September run of
# weekly-maintenance, gbp-posts-midweek and client-ops-sync:
#   gh run view <id> --log | grep -E '★ .*: POST ->|Z [a-z0-9-]+: [0-9]+ replied|
#       Z == [a-z0-9-]+$|GBP serviceArea -> |    add: |    drop \(too far\): '
