#!/usr/bin/env python3
"""gbp_site_media.py -- the website -> Google Business Profile PHOTO parity lane
(Santino 2026-09-28), plus the site-asset mirror the app's GBP Profile Planner
drafts from.

Two jobs, one per-client unit:

  manifest   Publish what the client's BUILT site holds to ops_kv
             'site-assets/{company_id}' (a derived mirror; the repo site stays
             canonical). The planner edge function cannot read the repo, so
             this is how it gets:
               services[]  service pages: name, slug, meta_description, intro
                           paragraph, live URL (grounding for GBP service
                           descriptions)
               images[]    hero, team, services hub, per-service cards,
                           before/after, logo: live site URL, a Google-ready
                           JPG mirror (Business Profile media accepts JPG/PNG,
                           never WebP), sha1, size, role, GBP category, and
                           ai_generated (true unless clients/{slug}/
                           photo-manifest.json records a REAL photo in that
                           slot; photo_harvest.py is the provenance source)
               allowed_claims / cities   the claims_lint truth table and the
                           plan-input city pool (same inputs gbp.py's
                           service_descriptions uses)
  push       Add website images to the client's GBP over time. ONLY when
               (a) the site answers on its real domain (HTTP probe, not flags)
               (b) the GBP is verified (metadata.hasVoiceOfMerchant)
             At most --cap (default 3, env GBP_SITE_PHOTOS_WEEKLY_CAP) new
             photos per rolling 7 days. Order: real photos before AI images,
             then hero, service cards, team, before/after, services hub. Logos
             never ride this lane (cover/logo are the planner's call). Every
             push is recorded in ops_kv 'gbp-site-media/{company_id}' (sha1 +
             URL) so nothing is uploaded twice; the planner's push_media writes
             the same ledger.

WRITE GATE: push is a dry run unless BOTH --apply is passed AND env
GBP_SITE_PHOTOS_WRITE is 1/true. CI passes --apply; the env flag stays unset
(report mode) until the owner confirms. Fail-open everywhere: a client that
errors is reported and skipped, never kills the run.

Per-client by design (LAW 09-19): `list-due` emits the roster as JSON and the
workflow runs one process per client with its own timeout.

Usage:
  python3 scripts/gbp_site_media.py manifest --slug dry-bros-water-fire-restoration
  python3 scripts/gbp_site_media.py push --slug kenneth-w-talbot-jr          # dry run
  python3 scripts/gbp_site_media.py run --slug X --apply                      # manifest + push
  python3 scripts/gbp_site_media.py list-due
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

import requests  # noqa: E402
import gbp  # noqa: E402  company_id_for, get_access_token, _clients, log_change, _desc_allowed_claims, _city_pool

GBP_V4 = "https://mybusiness.googleapis.com/v4"
VER_API = "https://mybusinessverifications.googleapis.com/v1"
SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
BUCKET = "branding"
UA = "Mozilla/5.0 (RankAI site-media parity; +https://restorationai.io)"
DEFAULT_CAP = 3
ROLE_RANK = {"hero": 0, "service": 1, "team": 2, "before_after": 3, "services_hub": 4, "crew": 2, "other": 5}
ROLE_CATEGORY = {"hero": "EXTERIOR", "service": "AT_WORK", "team": "TEAMS", "crew": "TEAMS",
                 "before_after": "AT_WORK", "services_hub": "ADDITIONAL", "logo": "LOGO", "other": "ADDITIONAL"}
AI_NAME_HINT = re.compile(r"(^|[-_.])(ai|gen|generated|gemini|nanobanana)([-_.]|$)", re.I)
VARIANT = re.compile(r"-(480|768|1200)w\.\w+$")


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(d: datetime | None = None) -> str:
    return (d or now()).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------- #
# Supabase helpers
# --------------------------------------------------------------------------- #
def _h(extra: dict | None = None) -> dict:
    return {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "application/json", **(extra or {})}


def kv_get(k: str):
    r = requests.get(f"{SB_URL}/rest/v1/ops_kv?k=eq.{requests.utils.quote(k, safe='')}&select=v",
                     headers=_h(), timeout=20)
    r.raise_for_status()
    rows = r.json()
    return rows[0]["v"] if rows else None


def kv_put(k: str, v) -> None:
    r = requests.post(f"{SB_URL}/rest/v1/ops_kv?on_conflict=k", headers=_h({"Prefer": "resolution=merge-duplicates"}),
                      json={"k": k, "v": v, "updated_at": iso()}, timeout=30)
    r.raise_for_status()


def site_row(cid: str) -> dict:
    r = requests.get(f"{SB_URL}/rest/v1/marketing_sites?company_id=eq.{cid}&select=domain,apex_live",
                     headers=_h(), timeout=20)
    r.raise_for_status()
    rows = r.json()
    return rows[0] if rows else {}


def company_plan(cid: str) -> dict:
    r = requests.get(f"{SB_URL}/rest/v1/companies?id=eq.{cid}&select=plan:integration_settings->gbp_plan",
                     headers=_h(), timeout=20)
    r.raise_for_status()
    rows = r.json()
    return (rows[0].get("plan") or {}) if rows else {}


def storage_upload(path: str, data: bytes, ctype: str) -> str:
    r = requests.post(f"{SB_URL}/storage/v1/object/{BUCKET}/{path}",
                      headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": ctype,
                               "x-upsert": "true", "cache-control": "31536000"},
                      data=data, timeout=60)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"storage upload {r.status_code}: {r.text[:160]}")
    return f"{SB_URL}/storage/v1/object/public/{BUCKET}/{path}"


# --------------------------------------------------------------------------- #
# probes
# --------------------------------------------------------------------------- #
def probe_site(domain: str) -> tuple[bool, str]:
    """Live = the REAL domain answers 200 with HTML on its own host (not flags)."""
    if not domain:
        return False, "no domain on marketing_sites"
    try:
        r = requests.get(f"https://{domain}/", headers={"User-Agent": UA}, timeout=20, allow_redirects=True)
    except Exception as e:  # noqa: BLE001
        return False, f"probe error: {str(e)[:80]}"
    host = requests.utils.urlparse(r.url).hostname or ""
    if r.status_code != 200:
        return False, f"HTTP {r.status_code}"
    if not host.replace("www.", "").endswith(domain.replace("www.", "")):
        return False, f"redirected off-domain to {host}"
    if "text/html" not in r.headers.get("content-type", ""):
        return False, "not HTML"
    return True, f"200 on {host}"


def probe_image(url: str) -> tuple[bool, str]:
    try:
        r = requests.head(url, headers={"User-Agent": UA}, timeout=15, allow_redirects=True)
        if r.status_code == 405:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=20, stream=True)
    except Exception as e:  # noqa: BLE001
        return False, f"error {str(e)[:60]}"
    ct = r.headers.get("content-type", "")
    return (r.status_code == 200 and ct.startswith("image/")), f"{r.status_code} {ct}"


# --------------------------------------------------------------------------- #
# manifest
# --------------------------------------------------------------------------- #
def _frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end < 0:
        return {}, text
    fm: dict = {}
    for line in text[3:end].splitlines():
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$", line)
        if not m:
            continue
        v = m.group(2).strip()
        if v.startswith('"') and v.endswith('"'):
            try:
                v = json.loads(v)
            except json.JSONDecodeError:
                v = v.strip('"')
        fm[m.group(1)] = v
    return fm, text[end + 4:]


def site_services(slug: str, domain: str) -> list[dict]:
    d = ROOT / "sites" / slug / "src" / "content" / "services"
    out = []
    for md in sorted(d.glob("*.md")) if d.exists() else []:
        fm, body = _frontmatter(md.read_text(encoding="utf-8"))
        para = next((p.strip() for p in body.split("\n\n")
                     if p.strip() and not p.strip().startswith(("#", "-", "*", "!", "|", "<", "1."))), "")
        svc_slug = str(fm.get("service_slug") or md.stem)
        out.append({
            "slug": svc_slug,
            "name": str(fm.get("service_display") or fm.get("h1") or md.stem.replace("-", " ").title()),
            "h1": str(fm.get("h1") or ""),
            "meta_description": str(fm.get("meta_description") or ""),
            "intro": re.sub(r"\s+", " ", para)[:600],
            "url": f"https://{domain}/services/{svc_slug}/" if domain else "",
        })
    return out


def real_slots(slug: str) -> dict[str, dict]:
    """{'/images/hero-bg.webp': slot} for every slot photo_harvest filled with a REAL photo."""
    p = ROOT / "clients" / slug / "photo-manifest.json"
    try:
        m = json.loads(p.read_text()) if p.exists() else {}
    except json.JSONDecodeError:
        return {}
    out = {}
    for v in (m.get("slots") or {}).values():
        if isinstance(v, dict) and v.get("file") and v.get("asset"):
            out[v["file"]] = v
    return out


def _role(rel: str) -> tuple[str, str | None]:
    name = rel.split("/")[-1]
    stem = name.rsplit(".", 1)[0]
    if rel.startswith("services/"):
        return "service", stem
    if rel.startswith("before-after/"):
        return "before_after", stem
    if stem == "hero-bg":
        return "hero", None
    if stem in ("team",):
        return "team", None
    if stem in ("crew",):
        return "crew", None
    if stem == "services":
        return "services_hub", None
    if stem == "logo":
        return "logo", None
    return "other", None


def collect_images(slug: str) -> list[Path]:
    img = ROOT / "sites" / slug / "public" / "images"
    if not img.exists():
        return []
    picks: list[Path] = []
    for f in sorted(img.iterdir()):
        if f.is_file() and f.suffix.lower() in (".webp", ".png", ".jpg", ".jpeg") and not VARIANT.search(f.name):
            if f.stem in ("hero-bg", "team", "crew", "services", "logo"):
                if f.stem == "logo" and f.suffix.lower() != ".png" and (img / "logo.png").exists():
                    continue
                picks.append(f)
    for sub in ("services", "before-after"):
        d = img / sub
        if not d.is_dir():
            continue
        seen: set[str] = set()
        # before/after ship as .png + .webp: prefer the PNG (Google-acceptable as-is)
        for f in sorted(d.iterdir(), key=lambda x: (x.stem, x.suffix.lower() != ".png")):
            if not f.is_file() or VARIANT.search(f.name) or f.suffix.lower() not in (".webp", ".png", ".jpg", ".jpeg"):
                continue
            if f.stem in seen:
                continue
            seen.add(f.stem)
            picks.append(f)
    return picks


def _caption(role: str, svc: str | None, services: list[dict], brand: str, city: str) -> str:
    names = {s["slug"]: s["name"] for s in services}
    if role == "service" and svc:
        return f"{names.get(svc, svc.replace('-', ' ').title())} by {brand}{f' in {city}' if city else ''}"
    if role == "before_after" and svc:
        kind, _, phase = svc.rpartition("-")
        return f"{kind.replace('-', ' ').title()} restoration, {phase}" if kind else svc.replace("-", " ")
    return {"hero": f"{brand}{f', serving {city}' if city else ''}", "team": f"The {brand} team",
            "crew": f"The {brand} crew", "services_hub": f"{brand} restoration services",
            "logo": f"{brand} logo"}.get(role, brand)


def gbp_ready(cid: str, f: Path, site_url: str, live: bool) -> tuple[str | None, int, int, str]:
    """Return (google_fetchable_url, width, height, sha1). JPG/PNG that are live
    on the site are used as-is; WebP is converted once to a JPG mirror in
    storage (branding/{cid}/site-assets/gbp-ready/), content-addressed so a
    re-run never re-uploads."""
    from PIL import Image
    raw = f.read_bytes()
    sha = hashlib.sha1(raw).hexdigest()[:16]
    im = Image.open(io.BytesIO(raw))
    w, h = im.size
    if min(w, h) < 250:
        return None, w, h, sha
    if f.suffix.lower() in (".png", ".jpg", ".jpeg") and live and 10_000 <= len(raw) <= 5_000_000:
        return site_url, w, h, sha
    if not live:
        return None, w, h, sha
    path = f"{cid}/site-assets/gbp-ready/{f.stem}-{sha[:8]}.jpg"
    public = f"{SB_URL}/storage/v1/object/public/{BUCKET}/{path}"
    try:
        if requests.head(public, timeout=10).status_code == 200:
            return public, w, h, sha
    except Exception:  # noqa: BLE001
        pass
    rgb = im.convert("RGB")
    if max(w, h) > 2400:
        rgb.thumbnail((2400, 2400))
    buf = io.BytesIO()
    rgb.save(buf, "JPEG", quality=88, optimize=True, progressive=True)
    return storage_upload(path, buf.getvalue(), "image/jpeg"), w, h, sha


def build_manifest(slug: str) -> dict:
    cid = gbp.company_id_for(slug)
    if not cid:
        raise SystemExit(f"{slug}: no company_id")
    site = site_row(cid)
    domain = (site.get("domain") or "").strip().lower().replace("https://", "").strip("/")
    live, why = probe_site(domain)
    pi_path = ROOT / "clients" / slug / "plan-input.json"
    pi = json.loads(pi_path.read_text()) if pi_path.exists() else {}
    brand = (pi.get("brand") or {}).get("display_name") or slug
    primary_city, others = gbp._city_pool(pi.get("service_areas") or [])
    services = site_services(slug, domain)
    reals = real_slots(slug)
    images = []
    for f in collect_images(slug):
        rel = f.relative_to(ROOT / "sites" / slug / "public" / "images").as_posix()
        role, svc = _role(rel)
        site_url = f"https://{domain}/images/{rel}" if domain else ""
        img_live, img_why = probe_image(site_url) if (live and site_url) else (False, "site not live")
        real = reals.get(f"/images/{rel}")
        ai = role != "logo" and not real
        if AI_NAME_HINT.search(f.stem):
            ai = True
        try:
            gurl, w, h, sha = gbp_ready(cid, f, site_url, img_live)
        except Exception as e:  # noqa: BLE001 -- one bad image never kills the manifest
            print(f"    ! {rel}: {str(e)[:120]}")
            continue
        images.append({
            "key": rel, "role": role, "service_slug": svc, "site_url": site_url, "live": img_live,
            "live_detail": img_why, "gbp_url": gurl, "width": w, "height": h, "sha1": sha,
            "ai_generated": ai, "provenance": (f"real photo ({real.get('source')}: {real.get('subject', '')})"
                                               if real else ("brand logo" if role == "logo" else "AI-generated site image")),
            "category": ROLE_CATEGORY.get(role, "ADDITIONAL"),
            "caption": _caption(role, svc, services, brand, primary_city),
        })
    truth_claims: list[str] = []
    try:
        import claims_lint
        truth_claims = gbp._desc_allowed_claims(claims_lint.load_truth(slug))
    except Exception as e:  # noqa: BLE001
        print(f"    ! claims truth unavailable: {str(e)[:80]}")
    return {
        "slug": slug, "company_id": cid, "domain": domain, "site_live": live, "site_probe": why,
        "brand": brand, "primary_city": primary_city, "cities": [c for c in [primary_city] + others if c],
        "state": next((a.get("state") for a in (pi.get("service_areas") or []) if a.get("state")), ""),
        "services": services, "images": images, "allowed_claims": truth_claims,
        "generated_at": iso(), "generator": "scripts/gbp_site_media.py manifest",
    }


def cmd_manifest(slug: str) -> dict:
    m = build_manifest(slug)
    kv_put(f"site-assets/{m['company_id']}", m)
    live_imgs = [i for i in m["images"] if i["live"]]
    print(f"  manifest {slug}: site {'LIVE' if m['site_live'] else 'NOT live'} ({m['site_probe']}), "
          f"{len(m['services'])} service pages, {len(m['images'])} images ({len(live_imgs)} live, "
          f"{sum(1 for i in m['images'] if i['ai_generated'])} AI), claims={m['allowed_claims']}"
          f" -> ops_kv site-assets/{m['company_id']}")
    return m


# --------------------------------------------------------------------------- #
# push lane
# --------------------------------------------------------------------------- #
def _gget(url: str, tok: str) -> dict:
    r = requests.get(url, headers={"Authorization": f"Bearer {tok}"}, timeout=30)
    r.raise_for_status()
    return r.json()


def locate(slug: str, cid: str) -> tuple[str | None, str | None, dict | None, str]:
    """(token, account_name, location, detail). Location by the client's
    place_id (same rule as gbp.find_location: never guess on a falsy id),
    else the planner's google_location."""
    tok = gbp.get_access_token(cid)
    if not tok:
        return None, None, None, "no business.manage token"
    pi_path = ROOT / "clients" / slug / "plan-input.json"
    place = ((json.loads(pi_path.read_text()) if pi_path.exists() else {}).get("brand") or {}).get("place_id") \
        or gbp._place_id_from_connection(cid)
    want_loc = (company_plan(cid) or {}).get("google_location")
    for acct in _gget(f"{gbp.ACCT_API}/accounts", tok).get("accounts", []):
        page = ""
        for _ in range(5):
            data = _gget(f"{gbp.INFO_API}/{acct['name']}/locations?readMask=name,title,metadata"
                         f"&pageSize=100{'&pageToken=' + page if page else ''}", tok)
            for loc in data.get("locations", []):
                md = loc.get("metadata") or {}
                if (place and md.get("placeId") == place and not md.get("duplicateLocation")) \
                        or (want_loc and loc["name"] == want_loc):
                    return tok, acct["name"], loc, "found"
            page = data.get("nextPageToken") or ""
            if not page:
                break
    return tok, None, None, f"no location for place_id {place or '-'} / plan {want_loc or '-'}"


def push_one(tok: str, acct: str, loc_name: str, img: dict) -> dict:
    locid = loc_name.split("/")[-1]
    body = {"mediaFormat": "PHOTO", "locationAssociation": {"category": img["category"]},
            "sourceUrl": img["gbp_url"], "description": img.get("caption", "")[:250]}
    r = requests.post(f"{GBP_V4}/{acct}/locations/{locid}/media", json=body,
                      headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}, timeout=60)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
    return r.json()


def cmd_push(slug: str, apply: bool, cap: int, real_only: bool, manifest: dict | None = None) -> str:
    cid = gbp.company_id_for(slug)
    if not cid:
        return f"{slug}: skip (no company_id)"
    write_env = str(os.environ.get("GBP_SITE_PHOTOS_WRITE", "")).lower() in ("1", "true", "yes")
    write = apply and write_env
    mode = "WRITE" if write else ("DRY (GBP_SITE_PHOTOS_WRITE not set)" if apply else "DRY")
    m = manifest or kv_get(f"site-assets/{cid}")
    if not m:
        return f"{slug}: skip (no site-assets manifest; run `manifest` first)"
    ledger = kv_get(f"gbp-site-media/{cid}") or {"pushed": []}
    report: dict = {"at": iso(), "mode": mode, "cap": cap, "gates": {}, "candidates": [], "pushed": [], "errors": []}

    # Gate (a): the real domain answers (fresh probe, never a flag)
    live, why = probe_site(m.get("domain", ""))
    report["gates"]["site_live"] = {"ok": live, "detail": why}
    # Gate (b): GBP verified
    tok = acct = None
    loc = None
    try:
        tok, acct, loc, detail = locate(slug, cid)
        verified = bool(loc and (loc.get("metadata") or {}).get("hasVoiceOfMerchant"))
        report["gates"]["gbp_verified"] = {"ok": verified, "detail": f"{loc['name']} ({loc.get('title')})" if loc else detail}
    except Exception as e:  # noqa: BLE001
        report["gates"]["gbp_verified"] = {"ok": False, "detail": f"lookup failed: {str(e)[:100]}"}

    pushed = ledger.get("pushed") or []
    have = {p.get("sha1") for p in pushed} | {p.get("site_url") for p in pushed}
    week_ago = now() - timedelta(days=7)
    recent = [p for p in pushed if p.get("by") == "lane" and p.get("at", "") >= iso(week_ago)]
    room = max(0, cap - len(recent))
    cands = [i for i in m.get("images", []) if i.get("live") and i.get("gbp_url") and i.get("role") != "logo"
             and i.get("sha1") not in have and i.get("site_url") not in have
             and not (real_only and i.get("ai_generated"))]
    cands.sort(key=lambda i: (bool(i.get("ai_generated")), ROLE_RANK.get(i.get("role"), 9), i.get("key")))
    batch = cands[:room]
    report["candidates"] = [{"key": i["key"], "role": i["role"], "ai": i["ai_generated"], "category": i["category"]}
                            for i in cands[:10]]
    report["remaining"] = len(cands)
    report["room_this_week"] = room

    gates_ok = all(g["ok"] for g in report["gates"].values())
    lines = [f"  [{slug}] {mode}: site {'LIVE' if live else 'not live'} ({why}); GBP "
             f"{'verified' if report['gates']['gbp_verified']['ok'] else 'NOT verified'} "
             f"({report['gates']['gbp_verified']['detail']}); {len(cands)} unpushed site image(s), "
             f"{len(recent)}/{cap} used this week"]
    if not gates_ok:
        lines.append("    gates closed: nothing would be pushed")
    for i in batch:
        tag = "AI" if i["ai_generated"] else "real"
        if not gates_ok:
            lines.append(f"    next up once gates open [{i['category']}/{tag}] {i['key']}")
            continue
        if not write:
            lines.append(f"    would push [{i['category']}/{tag}] {i['key']} <- {i['gbp_url']}")
            continue
        try:
            res = push_one(tok, acct, loc["name"], i)
            rec = {"sha1": i["sha1"], "site_url": i["site_url"], "source_url": i["gbp_url"], "key": i["key"],
                   "category": i["category"], "ai_generated": i["ai_generated"], "media_name": res.get("name"),
                   "at": iso(), "by": "lane"}
            pushed.append(rec)
            report["pushed"].append(rec)
            lines.append(f"    pushed [{i['category']}/{tag}] {i['key']} -> {res.get('name')}")
        except Exception as e:  # noqa: BLE001 -- fail-open per image
            report["errors"].append({"key": i["key"], "error": str(e)[:200]})
            lines.append(f"    FAILED {i['key']}: {str(e)[:160]}")
    ledger["pushed"] = pushed
    ledger["last_run"] = report
    try:
        kv_put(f"gbp-site-media/{cid}", ledger)
    except Exception as e:  # noqa: BLE001
        lines.append(f"    ! ledger write failed: {str(e)[:100]}")
    if report["pushed"]:
        n = len(report["pushed"])
        gbp.log_change(cid, "photo", f"{n} website photo{'s' if n != 1 else ''} added to the Google listing",
                       actor="automation", meta={"count": n, "keys": [p["key"] for p in report["pushed"]]})
    return "\n".join(lines)


def list_due() -> list[str]:
    import contextlib
    with contextlib.redirect_stdout(sys.stderr):   # the status gate prints; stdout stays pure JSON
        slugs = gbp._clients(SimpleNamespace(all=True, slug=None))
    return [s for s in slugs if (ROOT / "sites" / s / "public" / "images").is_dir()]


def main() -> int:
    ap = argparse.ArgumentParser(description="Website images -> GBP photo parity lane (+ planner site-asset mirror)")
    ap.add_argument("cmd", choices=["manifest", "push", "run", "list-due"])
    ap.add_argument("--slug")
    ap.add_argument("--apply", action="store_true", help="allow writes (still needs env GBP_SITE_PHOTOS_WRITE=1)")
    ap.add_argument("--cap", type=int, default=int(os.environ.get("GBP_SITE_PHOTOS_WEEKLY_CAP") or DEFAULT_CAP))
    ap.add_argument("--real-only", action="store_true", help="never push AI-generated site images")
    args = ap.parse_args()
    if args.cmd == "list-due":
        print(json.dumps(list_due()))
        return 0
    if not args.slug:
        ap.error("--slug is required (per-client unit; use list-due for the roster)")
    try:
        m = cmd_manifest(args.slug) if args.cmd in ("manifest", "run") else None
        if args.cmd in ("push", "run"):
            print(cmd_push(args.slug, args.apply, args.cap, args.real_only, m))
    except SystemExit as e:
        print(f"  [{args.slug}] skip: {e}")
    except Exception as e:  # noqa: BLE001 -- fail-open: one client never breaks the loop
        print(f"  [{args.slug}] ERROR (non-fatal): {str(e)[:200]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
