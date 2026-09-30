#!/usr/bin/env python3
"""site_regression_watch.py — LIVE WATCHER for silent site regressions
(Santino 2026-09-29: "We definitely don't want these sites getting reverted
after we make changes ... we need to add a watcher either way").

The deploy guard (scripts/deploy_guard.py) stops a bad push; this watches
what visitors actually get, so a regression from ANY path (a guard override,
a CDN/asset change, a template edit that slipped through) still surfaces.

Per active client with a live (cut-over) domain, fetch the homepage,
/services/ and a sample of service pages and fingerprint:
  nav        header nav labels (Case Studies included)
  sections   homepage <h2> headings (digits normalised)
  videos     distinct embedded video ids (+ <video> tags)
  logo       header logo <img> src/class/width/height
  images     service imagery: distinct srcs, distinct CONTENT (edge ETag),
             and how many use the template fallback /images/services.webp
  pages      URL count from the live sitemap

Stored in ops_kv site-fingerprint/{slug} = {baseline, last, regression}.
Each run diffs against the baseline:
  REGRESSION  a nav item or homepage section disappears, videos drop,
              fallback images increase, distinct images drop, logo
              classes/size change, or pages drop more than 5%
              -> ONE company-less [PIPELINE ALERT] card per site
                 (pipeline_watchdog refresh-in-place pattern) naming the
                 Cloudflare production deploy(s) since the last good
                 fingerprint, + one SMS when the card is new.
  otherwise   the baseline silently becomes the current fingerprint
              (improvements are absorbed; a cleared regression auto-resolves
              its card).
Accepting a deliberate change: resolve the card in the app (the next run
adopts the current page as the baseline) or run --accept SLUG.

CLIENT PINS (Santino 2026-09-30: client-requested changes must be
"implemented ... and maintained"). The fingerprint above only knows what the
site looked like yesterday; it cannot know that Angie asked for East Niles to
go or that Kenny's About text is his exact words. clients/{slug}/client-pins.json
records each VERIFIED client-requested state as an absolute assertion:

  {"pins": [{"id": "east-niles-removed",
             "request": "Angie 09-29: take East Niles off the service areas",
             "url": "/service-areas/",
             "forbid": ["East Niles"],          # visible text must NOT contain
             "forbid_re": ["\\d+ Google reviews"], # visible-text regexes that must not match
             "require": ["Bakersfield"],        # visible text MUST contain
             "order": ["Bakersfield", "Arvin"], # first occurrences in this order
             "html_require": ["h-32 md:h-40"],  # raw-HTML regexes that must match
             "html_forbid": [...],              # raw-HTML regexes that must not
             "status": 301,                     # exact HTTP status (no redirect follow)
             "location": "/service-areas/",     # Location header must contain
             "sha256": "..."}]}                 # exact bytes (image/asset URLs)

Every pin is checked on every run (nightly + after every deploy lane). A
broken pin is a REGRESSION like any other (same card, same SMS) and is never
absorbed into a baseline: resolving the card does not silence it. To retire a
pin (the client asked for something new), edit or delete it in the file.
Sites with a pins file are watched even when clients/{slug}.json has no
cut_over_at (Arch, Veterans, TDI and DryCor serve their own domains without it).

CLI:
  --list              JSON slug list for the workflow matrix
  --slug S            watch one site (the per-client matrix job)
  --all               every site, serially (local convenience)
  --seed              store the current fingerprint as the baseline
  --accept S          adopt the current fingerprint for S, close its card
  --pins [S]          check client pins only (all pinned sites, or S), no writes
  --dry-run           fingerprint + diff, no writes
"""
from __future__ import annotations

import argparse
import hashlib
import html as htmllib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")
if not os.environ.get("SUPABASE_URL"):
    load_dotenv(Path.home() / "Desktop/mywebsitecode/rank-ai/.env")

DEAD_SLUGS = {"mcc-restoration", "mold-solutionz"}
UA = "Mozilla/5.0 (compatible; RankAI-SiteWatch/1.0; +https://restorationai.io)"
FALLBACK_IMG = "/images/services.webp"
SAMPLE_SERVICE_PAGES = 6
MAX_ETAGS = 40
PAGE_DROP = 0.05
NOW = datetime.now(timezone.utc)


# ---------------------------------------------------------------- plumbing
def _sb(method: str, path: str, body=None, prefer: str = "return=minimal"):
    url = os.environ["SUPABASE_URL"].rstrip("/") + path
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    r = requests.request(method, url, json=body, timeout=30, headers={
        "apikey": key, "Authorization": f"Bearer {key}",
        "Content-Type": "application/json", "Prefer": prefer})
    r.raise_for_status()
    return r.json() if r.content else None


def kv_get(k: str) -> dict:
    rows = _sb("GET", f"/rest/v1/ops_kv?k=eq.{k}&select=v",
               prefer="return=representation") or []
    return (rows[0].get("v") if rows else None) or {}


def kv_put(k: str, v: dict) -> None:
    _sb("POST", "/rest/v1/ops_kv?on_conflict=k", {"k": k, "v": v},
        prefer="resolution=merge-duplicates,return=minimal")


def _get(url: str, timeout: int = 25) -> tuple[int, str, str]:
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=timeout,
                         allow_redirects=True)
        return r.status_code, r.text, r.url
    except requests.RequestException:
        return 0, "", url


def _text(fragment: str) -> str:
    t = re.sub(r"<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", htmllib.unescape(t)).strip()


def _record(slug: str) -> dict:
    p = ROOT / "clients" / f"{slug}.json"
    try:
        return json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


# ---------------------------------------------------------------- targets
def targets() -> list[tuple[str, str]]:
    """Active clients whose own domain serves our site (cut over)."""
    active = None
    try:
        from client_ops_sync import slug_map
        cos = _sb("GET", "/rest/v1/companies?select=id,status",
                  prefer="return=representation") or []
        ok = {c["id"] for c in cos if str(c.get("status") or "").lower() == "active"}
        active = {s for cid, s in slug_map().items() if cid in ok}
    except Exception as e:  # noqa: BLE001 — fall back to the repo records
        print(f"(app status unavailable, using repo records: {str(e)[:80]})")
    out = []
    for p in sorted((ROOT / "clients").glob("*.json")):
        slug = p.stem
        if slug == "company_map" or slug in DEAD_SLUGS:
            continue
        d = _record(slug)
        if not d.get("domain") or not (d.get("cut_over_at") or load_pins(slug)):
            continue
        if not (ROOT / "sites" / slug).exists():
            continue
        if active is not None and slug not in active:
            continue
        out.append((slug, d["domain"].strip().lower()))
    return out


# ---------------------------------------------------------------- client pins
def load_pins(slug: str) -> list[dict]:
    p = ROOT / "clients" / slug / "client-pins.json"
    try:
        return [x for x in (json.loads(p.read_text()).get("pins") or [])
                if isinstance(x, dict) and x.get("url")]
    except (OSError, json.JSONDecodeError, AttributeError):
        return []


_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"',
                         "–": "-", "—": "-", " ": " "})


def visible_text(html: str) -> str:
    """What a visitor reads: tags, scripts, styles and JSON-LD stripped,
    entities decoded, quotes/dashes/whitespace normalised."""
    t = re.sub(r"<(script|style|noscript|template)\b.*?</\1>", " ", html, flags=re.S | re.I)
    t = re.sub(r"<!--.*?-->", " ", t, flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", htmllib.unescape(t).translate(_QUOTES)).strip()


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.translate(_QUOTES)).strip()


def check_pin(origin: str, pin: dict, cache: dict) -> str | None:
    """None when the client-requested state holds, else a short failure."""
    url = urljoin(origin + "/", pin["url"].lstrip("/")) if not pin["url"].startswith("http") else pin["url"]
    want_status = pin.get("status")
    key = (url, bool(want_status and want_status != 200))
    if key not in cache:
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=30,
                             allow_redirects=not key[1])
            cache[key] = (r.status_code, r.content, r.headers.get("location", ""))
        except requests.RequestException as e:
            cache[key] = (0, b"", str(e)[:60])
    st, raw, loc = cache[key]
    if st == 0:
        return None          # unreachable is the homepage check's job, not a pin break
    if want_status and st != want_status:
        return f"{pin['url']} HTTP {st} (want {want_status})"
    if not want_status and st != 200:
        return f"{pin['url']} HTTP {st}"
    if pin.get("location") and pin["location"] not in loc:
        return f"{pin['url']} redirects to '{loc}' (want '{pin['location']}')"
    if pin.get("sha256"):
        got = hashlib.sha256(raw).hexdigest()
        if got != pin["sha256"]:
            return f"{pin['url']} content changed (sha256 {got[:12]}, want {pin['sha256'][:12]})"
    html = raw.decode("utf-8", "replace")
    if any(k in pin for k in ("require", "forbid", "forbid_re", "order")):
        text = visible_text(html)
        low = text.lower()
        miss = [s for s in pin.get("require") or [] if _norm(s).lower() not in low]
        if miss:
            return f"{pin['url']} lost required text: " + "; ".join(f"'{m[:70]}'" for m in miss[:3])
        bad = [s for s in pin.get("forbid") or [] if _norm(s).lower() in low]
        bad += [m.group(0) for rx in pin.get("forbid_re") or []
                for m in [re.search(rx, text, re.I)] if m]
        if bad:
            return f"{pin['url']} shows forbidden text again: " + "; ".join(f"'{b[:70]}'" for b in bad[:3])
        order = [_norm(s).lower() for s in pin.get("order") or []]
        if order:
            idx = [low.find(s) for s in order]
            if -1 in idx or idx != sorted(idx):
                return f"{pin['url']} order broken (want {' < '.join(pin['order'])})"
    for rx in pin.get("html_require") or []:
        if not re.search(rx, html, re.I | re.S):
            return f"{pin['url']} lost markup /{rx[:60]}/"
    for rx in pin.get("html_forbid") or []:
        if re.search(rx, html, re.I | re.S):
            return f"{pin['url']} has forbidden markup /{rx[:60]}/ again"
    return None


def check_pins(slug: str, domain: str) -> list[str]:
    pins = load_pins(slug)
    if not pins:
        return []
    origin = f"https://{domain}"
    cache: dict = {}
    out = []
    for pin in pins:
        why = check_pin(origin, pin, cache)
        if why:
            out.append(f"client pin '{pin.get('id', '?')}' ({pin.get('request', '')[:90]}) "
                       f"broken: {why}")
    return out


# ---------------------------------------------------------------- parsing
def _split(html: str) -> tuple[str, str]:
    m = re.search(r"<header\b.*?</header>", html, re.S | re.I)
    header = m.group(0) if m else ""
    body = re.sub(r"<header\b.*?</header>|<footer\b.*?</footer>", " ", html,
                  flags=re.S | re.I)
    return header, body


def nav_labels(header: str) -> list[str]:
    labels = set()
    for nav in re.findall(r"<nav\b.*?</nav>", header, re.S | re.I):
        for a in re.findall(r"<a\b[^>]*>(.*?)</a>", nav, re.S | re.I):
            t = _text(a)
            if t and len(re.sub(r"\D", "", t)) < 7:      # skip phone links
                labels.add(t.lower())
    return sorted(labels)


def section_heads(body: str) -> list[str]:
    heads = []
    for h in re.findall(r"<h2\b[^>]*>(.*?)</h2>", body, re.S | re.I):
        t = re.sub(r"\d+", "#", _text(h).lower())
        if t and t not in heads:
            heads.append(t)
    return heads


def video_ids(body: str) -> list[str]:
    ids = set()
    for pat in (r'data-video-id="([\w-]{6,})"',
                r"i\.ytimg\.com/vi/([\w-]{6,})/",
                r"youtube(?:-nocookie)?\.com/embed/([\w-]{6,})",
                r"youtu\.be/([\w-]{6,})",
                r'videoid="([\w-]{6,})"',
                r"player\.vimeo\.com/video/(\d+)"):
        ids.update(re.findall(pat, body, re.I))
    for i, tag in enumerate(re.findall(r"<video\b[^>]*>", body, re.I)):
        src = re.search(r'src="([^"]+)"', tag)
        ids.add("video:" + (src.group(1) if src else str(i)))
    return sorted(ids)


def logo_of(header: str) -> dict | None:
    for tag in re.findall(r"<img\b[^>]*>", header, re.I):
        if "logo" in tag.lower():
            attr = {k: v for k, v in re.findall(r'(\w[\w-]*)="([^"]*)"', tag)}
            return {"src": attr.get("src", ""), "class": attr.get("class", ""),
                    "width": attr.get("width", ""), "height": attr.get("height", "")}
    return None


def img_srcs(body: str) -> list[str]:
    out = []
    for tag in re.findall(r"<img\b[^>]*>", body, re.I):
        m = re.search(r'\ssrc="([^"]+)"', tag)
        if not m:
            continue
        src = m.group(1)
        if "logo" in src.lower() or src.startswith("data:") or "ytimg.com" in src:
            continue
        out.append(src)
    return out


def service_links(body: str) -> list[str]:
    return sorted(set(re.findall(r'href="(/services/[a-z0-9-]+/)"', body)))


def sitemap_count(origin: str) -> int | None:
    for path in ("/sitemap-index.xml", "/sitemap.xml"):
        st, xml, _ = _get(origin + path)
        if st != 200 or "<loc>" not in xml:
            continue
        locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml)
        if "<sitemapindex" in xml:
            n = 0
            for child in locs:
                c_st, c_xml, _ = _get(child)
                if c_st != 200:
                    return None      # partial count would read as a drop
                n += len(re.findall(r"<loc>", c_xml))
            return n
        return len(locs)
    return None


def etag(url: str) -> str | None:
    try:
        r = requests.head(url, headers={"User-Agent": UA}, timeout=15,
                          allow_redirects=True)
        if r.status_code != 200:
            return None
        return (r.headers.get("etag") or "").strip('W/"') or None
    except requests.RequestException:
        return None


# ---------------------------------------------------------------- fingerprint
def fingerprint(slug: str, domain: str) -> dict | None:
    origin = f"https://{domain}"
    st, home, final = _get(origin + "/")
    if st != 200 or len(home) < 2000:
        print(f"  {slug}: homepage unreachable (HTTP {st}); skipped")
        return None
    origin = f"{urlparse(final).scheme}://{urlparse(final).netloc}"
    header, body = _split(home)
    fp = {"at": NOW.isoformat(), "domain": domain,
          "nav": nav_labels(header), "sections": section_heads(body),
          "videos": video_ids(body), "logo": logo_of(header),
          "images": None, "pages": sitemap_count(origin)}

    s_st, services, _ = _get(origin + "/services/")
    if s_st == 200:
        _, s_body = _split(services)
        srcs = img_srcs(s_body)
        links = service_links(s_body)
        if links:
            step = max(1, len(links) // SAMPLE_SERVICE_PAGES)
            for path in links[::step][:SAMPLE_SERVICE_PAGES]:
                p_st, page, _ = _get(origin + path)
                if p_st == 200:
                    srcs += img_srcs(_split(page)[1])[:3]
        distinct = sorted(set(srcs))
        tags = {}
        for src in distinct[:MAX_ETAGS]:
            tags[src] = etag(urljoin(origin + "/", src)) or src
        fp["images"] = {
            "total": len(srcs),
            "fallback": sum(1 for s in srcs if s.split("?")[0].endswith(FALLBACK_IMG)),
            "distinct_srcs": len(distinct),
            "distinct_content": len(set(tags.values())),
            "etags": tags,
        }
    fp["deploy"] = latest_deploys(slug, 1)[:1]
    return fp


# ---------------------------------------------------------------- deploys
def latest_deploys(slug: str, n: int = 25) -> list[dict]:
    tok = (os.environ.get("CLOUDFLARE_PAGES_API_TOKEN")
           or os.environ.get("CLOUDFLARE_API_TOKEN")
           or os.environ.get("CLOUDFLARE_R2_API_TOKEN") or "")
    acct = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
    if not tok or not acct:
        return []
    proj = (_record(slug).get("build") or {}).get("pages_project") or f"rankai-{slug}"
    try:
        r = requests.get(
            f"https://api.cloudflare.com/client/v4/accounts/{acct}/pages/projects/"
            f"{proj}/deployments?env=production&per_page={n}",
            headers={"Authorization": f"Bearer {tok}"}, timeout=30)
        rows = r.json().get("result") or [] if r.ok else []
    except (requests.RequestException, ValueError):
        return []
    out = []
    for d in rows:
        meta = (d.get("deployment_trigger") or {}).get("metadata") or {}
        out.append({"id": d.get("id", "")[:8], "at": d.get("created_on", "")[:19],
                    "commit": (meta.get("commit_hash") or "")[:9],
                    "message": (meta.get("commit_message") or "").splitlines()[0][:90]
                    if meta.get("commit_message") else "",
                    "status": (d.get("latest_stage") or {}).get("status")})
    return out


def suspect_deploys(slug: str, baseline: dict) -> str:
    since = ((baseline.get("deploy") or [{}])[0] or {}).get("at") or baseline.get("at", "")[:19]
    ds = [d for d in latest_deploys(slug) if d["at"] > since and d["status"] == "success"]
    if not ds:
        return "no production deploy since the last good fingerprint"
    first = ds[-1]
    more = f" (+{len(ds) - 1} later, latest {ds[0]['commit']})" if len(ds) > 1 else ""
    return (f"introduced by deploy {first['commit']} '{first['message']}' at "
            f"{first['at']}Z{more}")


# ---------------------------------------------------------------- diff
def compare(base: dict, cur: dict) -> list[str]:
    regs = []
    gone = [x for x in base.get("nav") or [] if x not in (cur.get("nav") or [])]
    if gone and cur.get("nav"):
        regs.append("nav item(s) gone: " + ", ".join(gone))
    gone = [x for x in base.get("sections") or [] if x not in (cur.get("sections") or [])]
    if gone:
        regs.append("homepage section(s) gone: " + ", ".join(f"'{g}'" for g in gone[:6]))
    bv, cv = base.get("videos") or [], cur.get("videos") or []
    if len(cv) < len(bv):
        regs.append(f"homepage videos {len(bv)} -> {len(cv)}")
    bl, cl = base.get("logo"), cur.get("logo")
    if bl and not cl:
        regs.append("header logo image gone")
    elif bl and cl:
        diffs = [k for k in ("class", "width", "height") if bl.get(k) != cl.get(k)]
        if diffs:
            regs.append("logo " + "; ".join(f"{k} '{bl.get(k)}' -> '{cl.get(k)}'" for k in diffs))
    bi, ci = base.get("images"), cur.get("images")
    if bi and ci:
        if ci["fallback"] > bi["fallback"]:
            regs.append(f"service images on the {FALLBACK_IMG} fallback "
                        f"{bi['fallback']} -> {ci['fallback']}")
        if ci["distinct_srcs"] < bi["distinct_srcs"]:
            regs.append(f"distinct service images {bi['distinct_srcs']} -> {ci['distinct_srcs']}")
        elif ci["distinct_content"] < bi["distinct_content"]:
            regs.append(f"distinct service image CONTENT {bi['distinct_content']} -> "
                        f"{ci['distinct_content']} (duplicates)")
    bp, cp = base.get("pages"), cur.get("pages")
    if bp and cp is not None and cp < bp * (1 - PAGE_DROP):
        regs.append(f"sitemap pages {bp} -> {cp} (-{round(100 * (bp - cp) / bp)}%)")
    return regs


def merge(base: dict, cur: dict) -> dict:
    """New baseline = current, keeping the old value for any metric this run
    could not measure (a timed-out /services/ must not erase it)."""
    out = dict(cur)
    for k in ("images", "pages", "logo"):
        if out.get(k) is None and base.get(k) is not None:
            out[k] = base[k]
    return out


# ---------------------------------------------------------------- alerts
def _issue_head(slug: str) -> str:
    return f"site regression: {slug}"


def _card_key(slug: str) -> str:
    from pipeline_watchdog import alert_key
    return alert_key(_issue_head(slug) + " — x")


def _human_resolved(slug: str) -> bool:
    """Was this site's open regression card resolved by a person (= accept)?"""
    try:
        seen = kv_get(_card_key(slug))
        nid = seen.get("note_id")
        if not nid or seen.get("auto_cleared"):
            return False
        rows = _sb("GET", f"/rest/v1/marketing_ops_notes?id=eq.{nid}&select=status",
                   prefer="return=representation") or []
        return bool(rows) and rows[0].get("status") == "resolved"
    except Exception:  # noqa: BLE001
        return False


def _reconcile(slug: str, issue: str | None) -> None:
    from pipeline_watchdog import reconcile_notes, text_santino
    fresh = reconcile_notes([issue] if issue else [], scope=_card_key(slug))
    text_santino(fresh)


# ---------------------------------------------------------------- run
def _pin_key(slug: str) -> str:
    from pipeline_watchdog import alert_key
    return alert_key(f"client request reverted: {slug} — x")


def run_pins(slug: str, domain: str, *, dry: bool = False) -> list[str]:
    """Check clients/{slug}/client-pins.json against the live site. Its own
    card (separate from the fingerprint card), so accepting a design change
    never silences a reverted client request."""
    pins = load_pins(slug)
    if not pins:
        return []
    broken = check_pins(slug, domain)
    for b in broken:
        print(f"  {slug}: PIN BROKEN {b}")
    if not broken:
        print(f"  {slug}: {len(pins)} client pin(s) hold")
    if dry:
        return broken
    issue = None
    try:
        prev = kv_get(f"site-pins/{slug}")
    except Exception:  # noqa: BLE001
        prev = {}
    ok_at = NOW.isoformat() if not broken else (prev.get("ok_at") or "")
    if broken:
        since = {"at": (prev.get("ok_at") or NOW.isoformat())[:19]}
        issue = (f"client request reverted: {slug} — live {domain} no longer shows "
                 f"{len(broken)} change(s) the client asked for and we told them were done: "
                 + " | ".join(broken)
                 + f". {suspect_deploys(slug, since)}. Re-apply it "
                 f"(the request + URL are in clients/{slug}/client-pins.json) and redeploy; "
                 "only edit the pin if the client has since asked for something different.")
    try:
        kv_put(f"site-pins/{slug}", {"at": NOW.isoformat(), "ok_at": ok_at,
                                     "pins": len(pins), "broken": broken})
        from pipeline_watchdog import reconcile_notes, text_santino
        text_santino(reconcile_notes([issue] if issue else [], scope=_pin_key(slug)))
    except Exception as e:  # noqa: BLE001 — alerting must not kill the fingerprint run
        print(f"  {slug}: pin alert not filed ({str(e)[:120]})")
    return broken


def run_slug(slug: str, domain: str, *, seed: bool = False, accept: bool = False,
             dry: bool = False) -> str:
    key = f"site-fingerprint/{slug}"
    pin_broken = run_pins(slug, domain, dry=dry)
    cur = fingerprint(slug, domain)
    if cur is None:
        return "pins-broken" if pin_broken else "unreachable"
    rec = {} if dry and seed else kv_get(key)
    summary = (f"nav={len(cur['nav'])} sections={len(cur['sections'])} "
               f"videos={len(cur['videos'])} logo={'y' if cur['logo'] else 'n'} "
               f"imgs={json.dumps({k: v for k, v in (cur['images'] or {}).items() if k != 'etags'})} "
               f"pages={cur['pages']}")
    if seed or accept or not rec.get("baseline"):
        why = "seed" if seed or not rec.get("baseline") else "accept"
        if not dry:
            kv_put(key, {"baseline": cur, "baseline_at": NOW.isoformat(),
                         "last": cur, "last_at": NOW.isoformat(), "regression": None,
                         "baseline_why": why})
            if rec.get("regression"):
                _reconcile(slug, None)
        print(f"  {slug}: baseline {'would be ' if dry else ''}stored ({why}) {summary}")
        return why
    base = rec["baseline"]
    if rec.get("regression") and _human_resolved(slug):
        if not dry:
            kv_put(key, {**rec, "baseline": cur, "baseline_at": NOW.isoformat(),
                         "last": cur, "last_at": NOW.isoformat(), "regression": None,
                         "baseline_why": "card resolved by a person"})
        print(f"  {slug}: regression card was resolved by a person; current page adopted")
        return "accepted"
    regs = compare(base, cur)
    if regs:
        prev = rec.get("regression") or {}
        deploy = prev.get("deploy") if prev.get("items") == regs else suspect_deploys(slug, base)
        issue = (f"{_issue_head(slug)} — live {domain} lost what it had at "
                 f"{str(rec.get('baseline_at', ''))[:16]}Z: " + "; ".join(regs)
                 + f". {deploy}. If this was deliberate, resolve this card (the "
                 "next run adopts the current page as the new baseline).")
        print(f"  {slug}: REGRESSION " + " | ".join(regs) + f" [{deploy}]")
        if not dry:
            kv_put(key, {**rec, "last": cur, "last_at": NOW.isoformat(),
                         "regression": {"since": prev.get("since") or NOW.isoformat(),
                                        "items": regs, "deploy": deploy, "issue": issue}})
            _reconcile(slug, issue)
        return "regression"
    if not dry:
        kv_put(key, {**rec, "baseline": merge(base, cur), "baseline_at": NOW.isoformat(),
                     "last": cur, "last_at": NOW.isoformat(), "regression": None})
        if rec.get("regression"):
            _reconcile(slug, None)
    print(f"  {slug}: ok {summary}")
    return "ok"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--slug")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--seed", action="store_true")
    ap.add_argument("--accept", metavar="SLUG")
    ap.add_argument("--pins", nargs="?", const="*", metavar="SLUG")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.pins:
        slugs = ([a.pins] if a.pins != "*" else
                 sorted(p.parent.name for p in (ROOT / "clients").glob("*/client-pins.json")))
        bad = 0
        for s in slugs:
            dom = (_record(s).get("domain") or "").strip().lower()
            if dom:
                bad += len(run_pins(s, dom, dry=True))
        print(f"client pins: {bad} broken across {len(slugs)} site(s)")
        return 1 if bad else 0
    tg = targets()
    if a.list:
        print(json.dumps([s for s, _ in tg]))
        return 0
    doms = dict(tg)
    if a.accept:
        d = doms.get(a.accept) or (_record(a.accept).get("domain") or "")
        run_slug(a.accept, d, accept=True, dry=a.dry_run)
        return 0
    todo = tg if a.all else [(a.slug, doms.get(a.slug) or _record(a.slug).get("domain"))] if a.slug else []
    if not todo:
        ap.error("--slug, --all, --list or --accept")
    tally: dict[str, int] = {}
    for slug, dom in todo:
        if not dom:
            print(f"  {slug}: no live domain; skipped")
            continue
        try:
            v = run_slug(slug, dom, seed=a.seed, dry=a.dry_run)
        except Exception as e:  # noqa: BLE001 — one site never kills the sweep
            print(f"  {slug}: ERROR {str(e)[:160]}")
            v = "error"
        tally[v] = tally.get(v, 0) + 1
    print(f"site regression watch: {tally}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
