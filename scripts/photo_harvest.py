#!/usr/bin/env python3
"""photo_harvest.py — REAL-PHOTO-FIRST site imagery (Santino, 2026-08-05).

The premise, in Santino's words: *we generate AI images while clients already
have real photos.* Every client with a claimed Google Business Profile has a
photo library on it — vans, crews, equipment, before/afters — and most also have
a pre-existing or franchise website full of the same. A real photograph of the
client's own van beats any generation outright, and it is the only thing that
categorically cannot produce an invented phone number, a garbled wordmark, a
six-fingered technician or a Tyvek suit worn like a jacket. The whole van-decal /
PPE / distortion saga (Reign, Greg Arianoff, 2026-08-04/05) was a fight to make a
generator reproduce something we could simply have downloaded.

Nothing here replaces generation — it *demotes* it to what it was always good
for: filling genuine gaps.

Four phases, each runnable alone:

  audit    fleet inventory — GBP media count (live v4), what has landed in the
           branding bucket, what the pre-existing/franchise site offers, how many
           assets are triaged, and whether the shipped site images are real or
           generated. Read-only; costs nothing but GBP quota.

  harvest  pull the client's own photos into storage:
             GBP     -> gbp.import_gbp_media (branding/{cid}/job-photos/posted/,
                        gbp-{mediaKey}.jpg — the existing, working path; this is
                        also the GBP post rotation, so we do not disturb it)
             website -> branding/{cid}/site-assets/web/ (a NEW prefix that
                        gbp_post.py and gbp_photos.py never read, so franchise
                        imagery can never be re-uploaded to the client's own GBP)
           Deduped by content SHA-1 across BOTH sources, so the same van photo
           that sits on the GBP and the franchise page is stored once. EXIF is
           read before any re-encode and kept in the manifest (capture date, GPS
           when the phone left it on) — that is what makes these usable as
           case-study evidence, not just decoration.

  triage   Claude vision classifies every harvested asset: fleet / crew /
           equipment / before_after / job_progress / building / graphic /
           unusable, plus a 0-100 fitness score per site slot (hero, team,
           services) and per service page. Written to
           clients/{slug}/photo-manifest.json — git-tracked, so a classification
           is reviewable in a diff and never silently changes.

  apply    installs the winning real photos as sites/{slug}/public/images/
           hero-bg.webp / team.webp / services.webp / services/{slug}.webp,
           with -480/-768/-1200w variants and an image-meta.json entry, exactly
           as gen_site_images.py would have. Records provenance in the manifest
           so the next run knows a slot is real and leaves it alone.

gen_site_images.py consults the manifest FIRST and skips any slot a real photo
already fills, so `apply` then `--services` is the standing order of operations.

Usage:
  python3 scripts/photo_harvest.py audit --all
  python3 scripts/photo_harvest.py harvest --slug puroclean-east-las-vegas
  python3 scripts/photo_harvest.py triage  --slug puroclean-east-las-vegas
  python3 scripts/photo_harvest.py apply   --slug puroclean-east-las-vegas
  python3 scripts/photo_harvest.py run     --all        # harvest + triage
Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, ANTHROPIC_API_KEY,
     GOOGLE_OAUTH_CLIENT_ID/SECRET (for the GBP half).
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import urllib.robotparser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

import requests  # noqa: E402
from PIL import Image  # noqa: E402

import gbp  # noqa: E402  — company_id_for, get_access_token, find_location, _g, _sb

SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
ANTHROPIC_API = "https://api.anthropic.com/v1/messages"
VISION_MODEL = os.environ.get("PHOTO_TRIAGE_MODEL", "claude-sonnet-4-6")

BUCKET = "branding"
WEB_PREFIX = "site-assets/web"        # never read by gbp_post / gbp_photos
GBP_PREFIX = "job-photos/posted"      # where import_gbp_media already lands

# A restoration marketing site is a wide-format medium; anything smaller than
# this cannot carry a hero without upscaling artifacts that look worse than a
# generation. Deliberately generous for the smaller slots — a 900px crew photo
# beats an invented one at 1400px.
MIN_W = {"hero": 1100, "team": 700, "services": 700, "service": 700}
# Score a slot must clear for a real photo to displace a generation. Set from
# the PuroClean pass: 70 keeps marketing cards and phone-snapshots out of the
# hero while letting a genuine fleet lineup through on the first try.
MIN_SCORE = {"hero": 70, "team": 68, "services": 62, "service": 60}

UA = ("Mozilla/5.0 (compatible; RankAIBot/1.0; +https://restorationai.io/bot) "
      "photo-harvest")

# Categories the triage may return. `graphic` and `unusable` are never installed
# on a site; `graphic` is kept anyway because a client's own marketing card is
# still useful evidence of their livery/colours for the generator's references.
CATEGORIES = ["fleet", "crew", "equipment", "before_after", "job_progress",
              "building", "graphic", "unusable"]


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #
def _sb_headers(ct: str | None = "application/json") -> dict:
    h = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"}
    if ct:
        h["Content-Type"] = ct
    return h


def _storage_list(cid: str, sub: str) -> list[dict]:
    r = requests.post(f"{SB_URL}/storage/v1/object/list/{BUCKET}",
                      headers=_sb_headers(),
                      json={"prefix": f"{cid}/{sub}", "limit": 1000}, timeout=40)
    try:
        j = r.json()
    except Exception:
        return []
    return [f for f in j if isinstance(f, dict) and f.get("id")] if isinstance(j, list) else []


def _public_url(cid: str, sub: str, name: str) -> str:
    return f"{SB_URL}/storage/v1/object/public/{BUCKET}/{cid}/{sub}/{name}"


def _storage_put(cid: str, sub: str, name: str, data: bytes, mime: str) -> bool:
    r = requests.post(f"{SB_URL}/storage/v1/object/{BUCKET}/{cid}/{sub}/{name}",
                      headers=_sb_headers(mime), data=data, timeout=90)
    return r.status_code in (200, 201)


def slugs_from_args(args) -> list[str]:
    cmap = json.loads((ROOT / "clients" / "company_map.json").read_text())
    if getattr(args, "slug", None):
        return [s.strip() for s in args.slug.split(",") if s.strip()]
    return list(cmap.keys())


def manifest_path(slug: str) -> Path:
    return ROOT / "clients" / slug / "photo-manifest.json"


def load_manifest(slug: str) -> dict:
    p = manifest_path(slug)
    if not p.exists():
        return {"slug": slug, "assets": {}, "slots": {}}
    try:
        m = json.loads(p.read_text())
    except json.JSONDecodeError:
        return {"slug": slug, "assets": {}, "slots": {}}
    m.setdefault("assets", {})
    m.setdefault("slots", {})
    return m


def save_manifest(slug: str, m: dict) -> None:
    p = manifest_path(slug)
    p.parent.mkdir(parents=True, exist_ok=True)
    m["assets"] = dict(sorted(m["assets"].items()))
    p.write_text(json.dumps(m, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def _http_get(url: str, timeout: int = 60) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# EXIF — read BEFORE any re-encode; this is the case-study raw material
# --------------------------------------------------------------------------- #
def read_exif(data: bytes) -> dict:
    """Capture date + GPS when the camera left them on. Google strips most EXIF
    from googleusercontent renditions, so this mostly pays off on web-harvested
    and crew-uploaded originals — which is exactly where a real job date matters
    (a before/after pair dated four days apart IS the case study)."""
    out: dict = {}
    try:
        im = Image.open(io.BytesIO(data))
        exif = getattr(im, "_getexif", lambda: None)()
        if not exif:
            return out
        from PIL.ExifTags import TAGS, GPSTAGS
        tags = {TAGS.get(k, k): v for k, v in exif.items()}
        for key in ("DateTimeOriginal", "DateTimeDigitized", "DateTime"):
            if tags.get(key):
                out["taken_at"] = str(tags[key])
                break
        if tags.get("Make") or tags.get("Model"):
            out["camera"] = " ".join(
                str(tags.get(k, "")).strip() for k in ("Make", "Model")).strip()
        gps_raw = tags.get("GPSInfo")
        if isinstance(gps_raw, dict):
            g = {GPSTAGS.get(k, k): v for k, v in gps_raw.items()}

            def _dms(v, ref):
                try:
                    d, m, s = [float(x) for x in v]
                except Exception:
                    return None
                dec = d + m / 60 + s / 3600
                return -dec if ref in ("S", "W") else dec
            lat = _dms(g.get("GPSLatitude"), g.get("GPSLatitudeRef"))
            lng = _dms(g.get("GPSLongitude"), g.get("GPSLongitudeRef"))
            if lat is not None and lng is not None:
                out["gps"] = {"lat": round(lat, 6), "lng": round(lng, 6)}
    except Exception:
        pass
    return out


def image_dims(data: bytes) -> tuple[int, int]:
    try:
        im = Image.open(io.BytesIO(data))
        return im.width, im.height
    except Exception:
        return 0, 0


# --------------------------------------------------------------------------- #
# HARVEST — the client's own pre-existing / franchise website
# --------------------------------------------------------------------------- #
def _own_domains(slug: str, cid: str | None) -> set[str]:
    """Hosts we must never harvest FROM — they are our own output. Harvesting
    the Rank AI site we built would feed generated images straight back into the
    'real photo' pool and launder them as real.

    The apex is ours ONLY once apex_live is true. Before cutover the client's own
    domain still serves their old site — RestorationXpress sat on IONOS
    WordPress at restorationxpress.com for weeks after we had a build — and that
    old site is precisely what we want to harvest. Excluding the apex outright
    (the first cut of this function) silently blanked the existing-site column
    for every pre-cutover client."""
    hosts: set[str] = set()
    pages_host = None
    rec = ROOT / "clients" / f"{slug}.json"
    if rec.exists():
        try:
            d = json.loads(rec.read_text())
            pages_host = (d.get("build") or {}).get("pages_project")
        except Exception:
            pass
    if pages_host:
        hosts.add(f"{pages_host}.pages.dev")
    if cid:
        try:
            for row in gbp._sb(f"marketing_sites?company_id=eq.{cid}"
                               "&select=domain,apex_live,cloudflare_pages_url,"
                               "r2_public_url"):
                for key in ("cloudflare_pages_url", "r2_public_url"):
                    v = row.get(key)
                    if v:
                        h = urllib.parse.urlparse(
                            v if "//" in str(v) else "//" + str(v)).netloc.lower()
                        hosts.add(h.replace("www.", ""))
                if row.get("apex_live") and row.get("domain"):
                    hosts.add(str(row["domain"]).lower().replace("www.", ""))
        except Exception:
            pass
    hosts.discard("")
    return hosts


def existing_site_url(slug: str, cid: str | None) -> str | None:
    """The client's PRE-EXISTING site: whatever companies.website or the GBP
    websiteUri points at, as long as it is not a host we built. PuroClean is the
    canonical case — their GBP points at the franchise location page
    puroclean.com/las-vegas-nv-puroclean-east-las-vegas, which is full of real
    vans and real crew, and is emphatically not ours."""
    if not cid:
        return None
    cands: list[str] = []
    try:
        for row in gbp._sb(f"companies?id=eq.{cid}&select=website"):
            if row.get("website"):
                cands.append(str(row["website"]))
        for row in gbp._sb(f"marketing_gbp_profiles?company_id=eq.{cid}&select=website"):
            if row.get("website"):
                cands.append(str(row["website"]))
    except Exception:
        return None
    own = _own_domains(slug, cid)
    for raw in cands:
        u = raw.strip()
        if not u:
            continue
        if not u.startswith("http"):
            u = "https://" + u.lstrip("/")
        u = u.split("?")[0].rstrip("/")
        host = urllib.parse.urlparse(u).netloc.lower().replace("www.", "")
        if not host or host in own:
            continue
        return u
    return None


_ROBOTS_CACHE: dict[str, urllib.robotparser.RobotFileParser | None] = {}


def robots_ok(url: str) -> bool:
    """These are the client's own photographs of the client's own business,
    harvested for the client's own site — but a crawler that ignores robots.txt
    is a crawler that gets us blocked, so we honour it anyway."""
    parts = urllib.parse.urlparse(url)
    base = f"{parts.scheme}://{parts.netloc}"
    if base not in _ROBOTS_CACHE:
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(base + "/robots.txt")
        try:
            body = _http_get(base + "/robots.txt", timeout=20)
            if body is None:
                _ROBOTS_CACHE[base] = None          # unreachable: allow
            else:
                rp.parse(body.decode("utf-8", "ignore").splitlines())
                _ROBOTS_CACHE[base] = rp
        except Exception:
            _ROBOTS_CACHE[base] = None
    rp = _ROBOTS_CACHE[base]
    return True if rp is None else rp.can_fetch(UA, url)


_IMG_RE = re.compile(r"""<img[^>]+?(?:data-src|data-lazy-src|src)=["']([^"']+)["']""", re.I)
_SRCSET_RE = re.compile(r"""(?:srcset|data-srcset)=["']([^"']+)["']""", re.I)
_OG_RE = re.compile(r"""<meta[^>]+property=["']og:image["'][^>]+content=["']([^"']+)["']""", re.I)
_BG_RE = re.compile(r"""background-image\s*:\s*url\((['"]?)([^)'"]+)\1\)""", re.I)
_LINK_RE = re.compile(r"""<a[^>]+href=["']([^"'#]+)["']""", re.I)

# Chrome/CMS furniture that is never a photograph of the business.
_JUNK_RE = re.compile(
    r"(logo|icon|favicon|sprite|placeholder|avatar|badge|spinner|loading|"
    r"pixel|1x1|blank|arrow|chevron|bullet|divider|pattern|bg-texture|"
    r"facebook|twitter|instagram|linkedin|youtube|yelp|bbb|google-?play|"
    r"app-?store|star|rating|flag)", re.I)


def original_image_url(url: str) -> str:
    """Strip a CDN's on-the-fly resize so we fetch the ORIGINAL upload.

    Wix (and Squarespace, and every builder that ships responsive images) serves
    a transformed derivative at the src the page actually references. DISS
    Restoration's homepage yielded 48 image candidates and not one survived the
    600px gate, because every one of them was a 147x98 blurred AVIF placeholder:

      .../media/{id}~mv2.jpg/v1/fill/w_147,h_98,...,blur_2,enc_avif,.../{id}~mv2.jpg

    The client's actual photograph is the path before /v1/. Reading the tiny
    derivative and concluding "this client has no usable photos" is exactly the
    wrong answer — they have plenty, behind one path segment."""
    # Wix / wixstatic: everything from /v1/ onward is the transform
    m = re.match(r"^(https?://static\.wixstatic\.com/media/[^/]+)/v1/", url)
    if m:
        return m.group(1)
    # Squarespace: ?format=NNNw controls the rendition; drop it for the original
    if "squarespace-cdn.com" in url:
        return url.split("?")[0]
    # WordPress: name-1024x585.jpg is a generated size, name.jpg is the upload
    m = re.match(r"^(.*)-\d{3,4}x\d{3,4}(\.(?:jpe?g|png|webp))$", url, re.I)
    if m and "/wp-content/uploads/" in url:
        return m.group(1) + m.group(2)
    return url


def _abs(base: str, u: str) -> str | None:
    if not u or u.startswith("data:"):
        return None
    try:
        return urllib.parse.urljoin(base, u.strip())
    except Exception:
        return None


def _widest_from_srcset(srcset: str) -> str | None:
    best, best_w = None, -1
    for part in srcset.split(","):
        bits = part.strip().split()
        if not bits:
            continue
        w = 0
        if len(bits) > 1 and bits[1].endswith("w"):
            try:
                w = int(bits[1][:-1])
            except ValueError:
                w = 0
        if w >= best_w:
            best, best_w = bits[0], w
    return best


def crawl_site_images(start_url: str, *, max_pages: int = 10,
                      max_images: int = 60) -> list[tuple[str, str]]:
    """Breadth-first over the start page and same-host links beneath its path,
    returning (image_url, found_on_page). Path-scoped on purpose: on a franchise
    domain the location page's subtree is the franchisee's own content, while
    the corporate root is 4,000 other franchisees' photos."""
    # Resolve redirects FIRST and take host+scope from where we actually land.
    # PuroClean's company record says puroclean.com/eastlasvegas, a vanity
    # redirect to /las-vegas-nv-puroclean-east-las-vegas/ — scoping to the
    # pre-redirect path would have matched no internal link at all.
    try:
        rr = requests.get(start_url, headers={"User-Agent": UA}, timeout=45,
                          allow_redirects=True)
        if rr.url:
            start_url = rr.url.split("?")[0]
    except Exception:
        pass
    parts = urllib.parse.urlparse(start_url)
    host = parts.netloc.lower()
    scope = parts.path.rstrip("/")
    seen_pages: set[str] = set()
    queue = [start_url]
    found: dict[str, str] = {}
    while queue and len(seen_pages) < max_pages and len(found) < max_images:
        page = queue.pop(0)
        if page in seen_pages:
            continue
        seen_pages.add(page)
        if not robots_ok(page):
            print(f"    robots.txt disallows {page} — skipped")
            continue
        body = _http_get(page, timeout=45)
        if not body:
            continue
        html = body.decode("utf-8", "ignore")
        cands: list[str] = []
        cands += _IMG_RE.findall(html)
        cands += _OG_RE.findall(html)
        cands += [m[1] for m in _BG_RE.findall(html)]
        for ss in _SRCSET_RE.findall(html):
            w = _widest_from_srcset(ss)
            if w:
                cands.append(w)
        for c in cands:
            u = _abs(page, c)
            if not u:
                continue
            if not re.search(r"\.(jpe?g|png|webp)(\?|$)", u, re.I):
                continue
            if _JUNK_RE.search(urllib.parse.urlparse(u).path):
                continue
            u = original_image_url(u.split("?")[0])
            found.setdefault(u, page)
            if len(found) >= max_images:
                break
        # only follow links that stay on-host and under the start path
        for href in _LINK_RE.findall(html):
            nxt = _abs(page, href)
            if not nxt:
                continue
            p2 = urllib.parse.urlparse(nxt)
            if p2.netloc.lower() != host:
                continue
            if scope and not p2.path.rstrip("/").startswith(scope):
                continue
            nxt = nxt.split("?")[0]
            if nxt not in seen_pages and len(queue) < max_pages * 3:
                queue.append(nxt)
        time.sleep(0.4)  # polite
    return sorted(found.items())


def harvest_website(slug: str, cid: str, *, cap: int = 40,
                    dry_run: bool = False) -> tuple[int, str]:
    url = existing_site_url(slug, cid)
    if not url:
        return 0, "no pre-existing site on record"
    print(f"    source: {url}")
    pairs = crawl_site_images(url)
    if not pairs:
        return 0, f"{url}: no candidate images"
    existing = {f["name"] for f in _storage_list(cid, f"{WEB_PREFIX}/")}
    have_sha = {n.split("-", 1)[1].split(".")[0] for n in existing if "-" in n}
    saved = 0
    for img_url, page in pairs:
        if saved >= cap:
            break
        data = _http_get(img_url)
        if not data or len(data) < 20_000:      # <20KB is furniture, not a photo
            continue
        w, h = image_dims(data)
        if w < 600 or h < 400:
            continue
        sha = hashlib.sha1(data).hexdigest()[:16]
        if sha in have_sha:
            continue
        ext = ".png" if data[:4] == b"\x89PNG" else ".jpg"
        name = f"web-{sha}{ext}"
        if dry_run:
            print(f"    [dry-run] {img_url} ({w}x{h}, {len(data)//1024}KB) -> {name}")
            saved += 1
            have_sha.add(sha)
            continue
        mime = "image/png" if ext == ".png" else "image/jpeg"
        if _storage_put(cid, WEB_PREFIX, name, data, mime):
            saved += 1
            have_sha.add(sha)
            # stash provenance immediately — the URL it came from is the only
            # proof later that this is the client's photo and not stock
            m = load_manifest(slug)
            m["assets"].setdefault(f"web:{sha}", {})
            m["assets"][f"web:{sha}"].update({
                "source": "website", "storage": f"{WEB_PREFIX}/{name}",
                "url": _public_url(cid, WEB_PREFIX, name),
                "origin_url": img_url, "found_on": page,
                "width": w, "height": h, "bytes": len(data), "sha1": sha,
                "exif": read_exif(data),
            })
            save_manifest(slug, m)
    return saved, f"{url} ({len(pairs)} candidates)"


def register_gbp_assets(slug: str, cid: str) -> int:
    """Fold whatever is already in the branding bucket into the manifest.
    Separated from the GBP import itself so a repo checkout can be re-synced
    with storage without spending GBP API quota.

    Two prefixes, both real client photography:
      job-photos/posted/  the GBP library import (import_gbp_media) plus
                          anything gbp_photos.py has already pushed up
      job-photos/         the crew-hub upload inbox — photos a technician took
                          on a job this week and sent from their phone via
                          restorationai.io/gbpphotos/{slug}. The most authentic
                          source we have, and the one carrying real EXIF (Google
                          strips it from its own renditions), so it is also the
                          only source that can date and place a case study.
    """
    m = load_manifest(slug)
    n_new = 0
    for prefix, src in ((GBP_PREFIX, "gbp"), ("job-photos", "crew")):
        for f in _storage_list(cid, f"{prefix}/"):
            name = f["name"]
            if not name.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                continue
            base = re.sub(r"^r\d+_", "", name)       # rotation-renamed copies
            key = f"{src}:{base.rsplit('.', 1)[0]}"
            other = f"{'crew' if src == 'gbp' else 'gbp'}:{base.rsplit('.', 1)[0]}"
            url = _public_url(cid, prefix, name)
            # The same filename moves job-photos/ -> job-photos/posted/ when
            # gbp_photos.py drains it up to the listing. That is one photo, not
            # two — and the old entry's URL is now a 404, so re-point it instead
            # of skipping. Keeping the classification costs nothing and the
            # alternative is a manifest full of dead links to photos we did
            # successfully harvest.
            if other in m["assets"]:
                m["assets"][other].update(
                    {"storage": f"{prefix}/{name}", "url": url, "source": src})
                continue
            if key in m["assets"] and m["assets"][key].get("width"):
                m["assets"][key].update({"storage": f"{prefix}/{name}", "url": url})
                continue
            data = _http_get(url)
            if not data:
                continue
            w, h = image_dims(data)
            if not w:
                continue
            m["assets"][key] = {**m["assets"].get(key, {}), **{
                "source": src, "storage": f"{prefix}/{name}", "url": url,
                "width": w, "height": h, "bytes": len(data),
                "sha1": hashlib.sha1(data).hexdigest()[:16],
                "exif": read_exif(data),
            }}
            n_new += 1
            # Checkpoint: registering a 200-photo library (ProRestoration) is
            # 200 downloads, and saving only at the end meant a run killed
            # part-way threw away every byte it had fetched and showed no
            # progress while it did so.
            if n_new % 25 == 0:
                save_manifest(slug, m)
                print(f"    registered {n_new} asset(s)...", flush=True)
    # cross-source dedupe: the same van shot on the GBP and the franchise page
    by_sha: dict[str, str] = {}
    for k, a in sorted(m["assets"].items()):
        sha = a.get("sha1")
        if not sha:
            continue
        if sha in by_sha and by_sha[sha] != k:
            a["duplicate_of"] = by_sha[sha]
        else:
            by_sha[sha] = k
            a.pop("duplicate_of", None)
    save_manifest(slug, m)
    return n_new


def cmd_harvest(args) -> int:
    for slug in slugs_from_args(args):
        cid = gbp.company_id_for(slug)
        print(f"\n=== harvest {slug} ({cid}) ===")
        if not cid:
            print("  no company_id — skipped")
            continue
        if not args.web_only:
            try:
                print("  GBP: " + gbp.import_gbp_media(slug, cap=args.cap))
            except Exception as e:
                print(f"  GBP: ERROR {str(e)[:140]}")
        n = register_gbp_assets(slug, cid)
        print(f"  manifest: +{n} GBP asset(s) registered")
        if not args.gbp_only:
            try:
                got, note = harvest_website(slug, cid, cap=args.cap,
                                            dry_run=args.dry_run)
                print(f"  web: {got} image(s) from {note}")
            except Exception as e:
                print(f"  web: ERROR {str(e)[:140]}")
    return 0


# --------------------------------------------------------------------------- #
# TRIAGE — Claude vision
# --------------------------------------------------------------------------- #
TRIAGE_SYSTEM = """You are the image editor for a restoration-company website \
build. You are shown photographs a contractor has published on their own Google \
Business Profile or website. Your job is to say what each one IS and whether it \
can carry a slot on a professional marketing site.

Return ONLY a JSON array, one object per image, in the order shown:
{"i":<index>,"category":"fleet|crew|equipment|before_after|job_progress|building|graphic|unusable",
 "subject":"<max 12 words, literal description>",
 "quality":<0-100 sharpness/exposure/composition/professionalism>,
 "slots":{"hero":<0-100>,"team":<0-100>,"services":<0-100>},
 "service_slugs":[<0-3 slugs, VERBATIM from the client's service list below>],
 "flags":["text_overlay","watermark","phone_number","logo_card","screenshot",
          "stock_photo","low_res","blurry","people_faces","competitor_brand",
          "graphic_content","indoor_clutter"],
 "reason":"<max 20 words>"}

FLAGS ARE ABOUT WHAT WAS ADDED IN AN EDITOR, NOT WHAT WAS IN FRONT OF THE LENS.
Text that physically exists in the scene — a phone number printed on a van
wrap, a logo on a polo shirt, a sign over a shop door, lettering on an
equipment case — is real signage. It is DESIRABLE and must NOT be flagged as
text_overlay, phone_number, watermark or logo_card. Those four flags mean the
image was composited or captioned afterwards: a phone number typed across the
middle, a "Before / After" caption bar, a tiled repeating watermark, a logo
lockup pasted into a corner over the photo. Getting this wrong throws away the
client's best real photographs, which is the whole point of the exercise.

stock_photo means: licensed library imagery, an AI-generated or composited
marketing render, or a corporate/franchise promo scene that is not this
location's own crew and own vehicles. Flag it when the image is too polished,
too generic or too obviously art-directed to be a working contractor's photo.

Category rules:
- fleet: the company's service vans/trucks are the subject.
- crew: identifiable people in company uniform, working or posed as a team.
- equipment: air movers, dehumidifiers, air scrubbers, hoses, racks of gear.
- before_after: a single image showing two states side by side or labelled.
- job_progress: damage or work in progress, no clear crew/van subject.
- building: office, shop, warehouse exterior/interior with no job activity.
- graphic: ANY image that is primarily a designed marketing card, logo lockup,
  collage with overlaid text, phone number or "Before/After" labels burnt in.
  A photo with a small corner watermark is NOT graphic; a phone number across
  the middle IS.
- unusable: blurry, dark, screenshotted, obviously licensed stock, tiny, an
  event/conference/party photo, or anything unrelated to the trade.

Slot scoring:
- hero: wide, calm, photogenic, ideally the fleet or an exterior arrival scene,
  with clean space where a headline could overlay. Portrait crops, burnt-in text
  and cluttered interiors score under 30.
- team: the crew visible as people. A group shot in uniform scores 85+. A single
  technician mid-task scores 55-70. No people scores 0.
- services: a technician or equipment mid-task that reads as "this is the work".

service_slugs is a CLOSED vocabulary: copy strings verbatim from the client's
service list in the user message and return [] when none of them fit. Invented
slugs are silently discarded — an unconstrained first pass produced
"structural-drying", "flood-cleanup" and "water-extraction" for a client whose
site has five service pages, none of them named that, so not one real photo
reached a service card.

Be strict. A marketing collage is never a hero. Score honestly; a site with
three good real photos and everything else generated beats a site of mediocre
real photos."""


def client_service_slugs(slug: str) -> list[str]:
    """The service pages this client actually has — the closed vocabulary the
    triage is allowed to tag against. Prefers the built site (authoritative) and
    falls back to plan-input for clients whose site is not scaffolded yet."""
    out: list[str] = []
    svc_dir = ROOT / "sites" / slug / "src" / "content" / "services"
    if svc_dir.is_dir():
        for md in sorted(svc_dir.glob("*.md")):
            m = re.search(r"""^service_slug:\s*['"]?([^'"\n]+?)['"]?\s*$""",
                          md.read_text(encoding="utf-8"), re.M)
            out.append((m.group(1) if m else md.stem).strip())
    if not out:
        pi = ROOT / "clients" / slug / "plan-input.json"
        if pi.exists():
            try:
                for s in json.loads(pi.read_text()).get("services") or []:
                    out.append(s if isinstance(s, str) else str(s.get("slug", "")))
            except Exception:
                pass
    return [s for s in dict.fromkeys(out) if s]


def _vision_call(items: list[tuple[int, bytes]], context: str) -> list[dict]:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise SystemExit("ANTHROPIC_API_KEY missing (rank-ai/.env)")
    content: list[dict] = [{"type": "text", "text": context}]
    for idx, data in items:
        content.append({"type": "text", "text": f"Image {idx}:"})
        content.append({"type": "image", "source": {
            "type": "base64", "media_type": "image/jpeg",
            "data": base64.b64encode(data).decode()}})
    body = {"model": VISION_MODEL, "max_tokens": 4000,
            "system": TRIAGE_SYSTEM,
            "messages": [{"role": "user", "content": content}]}
    last = ""
    for attempt in range(4):
        r = requests.post(ANTHROPIC_API, timeout=180,
                          headers={"x-api-key": key,
                                   "anthropic-version": "2023-06-01",
                                   "content-type": "application/json"},
                          data=json.dumps(body))
        if r.status_code == 200:
            txt = "".join(b.get("text", "") for b in r.json().get("content", []))
            mm = re.search(r"\[.*\]", txt, re.S)
            if mm:
                try:
                    return json.loads(mm.group(0))
                except json.JSONDecodeError:
                    last = txt[:200]
        else:
            last = f"HTTP {r.status_code}: {r.text[:200]}"
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"vision call failed: {last}")


def _thumb(data: bytes, edge: int = 720) -> bytes:
    im = Image.open(io.BytesIO(data)).convert("RGB")
    im.thumbnail((edge, edge), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=80)
    return buf.getvalue()


def triage(slug: str, *, batch: int = 6, limit: int = 0,
           force: bool = False) -> str:
    m = load_manifest(slug)
    assets = m["assets"]
    todo = [k for k, a in sorted(assets.items())
            if a.get("url") and not a.get("duplicate_of")
            and (force or not a.get("category"))]
    if limit:
        todo = todo[:limit]
    if not todo:
        return f"{slug}: nothing to triage ({len(assets)} asset(s) known)"
    brand = {}
    pi = ROOT / "clients" / slug / "plan-input.json"
    if pi.exists():
        brand = json.loads(pi.read_text()).get("brand", {})
    svc_vocab = client_service_slugs(slug)
    ctx = (f"Company: {brand.get('display_name', slug)}. "
           f"Trade: property damage restoration / remediation.\n"
           f"The client's service list (the ONLY values service_slugs may "
           f"contain): {', '.join(svc_vocab) if svc_vocab else '(none — return [])'}\n"
           f"Classify each image below.")
    done = 0
    for i in range(0, len(todo), batch):
        chunk = todo[i:i + batch]
        payload: list[tuple[int, bytes]] = []
        idx_key: dict[int, str] = {}
        for n, k in enumerate(chunk):
            data = _http_get(assets[k]["url"])
            if not data:
                continue
            try:
                payload.append((n, _thumb(data)))
            except Exception:
                continue
            idx_key[n] = k
        if not payload:
            continue
        try:
            res = _vision_call(payload, ctx)
        except Exception as e:
            print(f"    batch {i//batch}: {str(e)[:140]}")
            continue
        for row in res:
            k = idx_key.get(row.get("i", -1))
            if not k:
                continue
            a = assets[k]
            cat = row.get("category")
            a["category"] = cat if cat in CATEGORIES else "unusable"
            a["subject"] = str(row.get("subject", ""))[:120]
            a["quality"] = int(row.get("quality") or 0)
            slots = row.get("slots") or {}
            a["slots"] = {s: int(slots.get(s) or 0) for s in ("hero", "team", "services")}
            # closed vocabulary enforced HERE too — the prompt asks, this makes
            # sure, so an off-list slug can never sit in the manifest looking
            # like a match that will never fire
            a["service_slugs"] = [str(s) for s in (row.get("service_slugs") or [])
                                  if str(s) in svc_vocab][:6]
            a["flags"] = [str(f) for f in (row.get("flags") or [])][:10]
            a["reason"] = str(row.get("reason", ""))[:160]
            a["triaged_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            a["triage_model"] = VISION_MODEL
            done += 1
        save_manifest(slug, m)
        print(f"    triaged {min(i+batch, len(todo))}/{len(todo)}", flush=True)
    m["triaged_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    save_manifest(slug, m)
    return f"{slug}: {done} asset(s) classified ({len(assets)} total)"


def cmd_triage(args) -> int:
    for slug in slugs_from_args(args):
        cid = gbp.company_id_for(slug)
        if cid and not manifest_path(slug).exists():
            register_gbp_assets(slug, cid)
        print("  " + triage(slug, batch=args.batch, limit=args.limit,
                            force=args.force))
    return 0


# --------------------------------------------------------------------------- #
# SELECT + APPLY — real photos take the slot, generation fills what is left
# --------------------------------------------------------------------------- #
# Flags that disqualify an asset from a marketing slot no matter how it scored.
# `logo_card`/`text_overlay`/`phone_number` are the ones that matter most: a
# client's own marketing collage carries a burnt-in phone number, and shipping
# that as a hero repeats the exact defect (an invented number on the van) that
# real photos were supposed to eliminate.
HARD_FLAGS = {"screenshot", "stock_photo", "blurry", "low_res",
              "competitor_brand", "graphic_content"}
SLOT_BLOCK_FLAGS = {
    "hero": {"text_overlay", "watermark", "phone_number", "logo_card"},
    "team": {"logo_card", "phone_number"},
    "services": {"logo_card", "phone_number"},
    "service": {"logo_card", "phone_number"},
}
SLOT_CATEGORIES = {
    "hero": {"fleet", "building", "job_progress", "crew"},
    "team": {"crew"},
    "services": {"crew", "equipment", "job_progress"},
    "service": {"crew", "equipment", "job_progress", "before_after"},
}


def eligible(a: dict, slot: str, *, service_slug: str | None = None) -> int:
    """Score an asset for a slot, or 0 if it fails a gate. This is the whole
    'prefer real over generated' policy in one function — deliberately, so it
    can be read and argued with in one screen."""
    if a.get("duplicate_of") or not a.get("category"):
        return 0
    if a["category"] in ("graphic", "unusable"):
        return 0
    if a["category"] not in SLOT_CATEGORIES[slot]:
        return 0
    flags = set(a.get("flags") or [])
    if flags & HARD_FLAGS:
        return 0
    if flags & SLOT_BLOCK_FLAGS[slot]:
        return 0
    w, h = a.get("width") or 0, a.get("height") or 0
    if w < MIN_W[slot]:
        return 0
    if slot == "hero" and (h == 0 or w / h < 1.25):
        return 0                      # a portrait crop cannot be a 16:9 hero
    key = "services" if slot in ("services", "service") else slot
    score = int((a.get("slots") or {}).get(key) or 0)
    if score < MIN_SCORE[slot]:
        return 0
    if service_slug:
        tags = a.get("service_slugs") or []
        if service_slug not in tags:
            return 0
        # The triage lists service_slugs in RELEVANCE order, so tags[0] is what
        # the photo is actually OF and the rest are "could also illustrate".
        # Scoring every match the same made the per-service cards fall out in
        # alphabetical order of the service, not photographic fit: Reign's
        # storm card grabbed a flooded living room (water first, storm second)
        # simply because "storm" sorts before "water", and the water card was
        # left with a collapsed ceiling. A primary match is worth far more than
        # a generic services score, so weight it that way.
        score += 20 if tags[0] == service_slug else 5
    # a sharper, bigger original wins ties
    return score * 1000 + min(int(a.get("quality") or 0), 100) * 10 + min(w // 400, 9)


def pick(manifest: dict, slot: str, *, service_slug: str | None = None,
         used: set[str] | None = None) -> tuple[str, dict] | None:
    used = used or set()
    best, best_s = None, 0
    for k, a in manifest["assets"].items():
        if k in used:
            continue
        s = eligible(a, slot, service_slug=service_slug)
        if s > best_s:
            best, best_s = (k, a), s
    return best


# Where to keep the frame when a real photo has to lose height to reach the
# slot's aspect. 0 = keep the top, 1 = keep the bottom. Category-driven because
# the subject's position in frame is a property of the subject: vehicles and
# equipment sit on the ground in the lower half, faces sit in the upper half.
# The first PuroClean pass used a flat 0.35 and guillotined the wheels off a
# three-van fleet lineup — the single best photograph the client owns.
CROP_BIAS = {"fleet": 0.62, "equipment": 0.58, "building": 0.45,
             "job_progress": 0.5, "before_after": 0.5, "crew": 0.32}


def _install(data: bytes, dest: Path, *, target_ratio: float | None = None,
             crop_bias: float = 0.4) -> tuple[int, int]:
    """Write a real photograph into the site as WebP, cropping only when the
    slot demands an aspect the original does not have. Never upscales — the
    MIN_W gate already guarantees enough pixels."""
    from resize_images import VARIANT_WIDTHS, variant_bytes, variant_path
    im = Image.open(io.BytesIO(data)).convert("RGB")
    if target_ratio:
        r = im.width / im.height
        if r > target_ratio + 0.02:
            new_w = int(im.height * target_ratio)
            x = (im.width - new_w) // 2
            im = im.crop((x, 0, x + new_w, im.height))
        elif r < target_ratio - 0.02:
            new_h = int(im.width / target_ratio)
            y = int((im.height - new_h) * max(0.0, min(1.0, crop_bias)))
            im = im.crop((0, y, im.width, y + new_h))
    if im.width > 2000:
        im = im.resize((2000, round(im.height * 2000 / im.width)), Image.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, "WEBP", quality=86)
    for w in VARIANT_WIDTHS:
        if w < im.width:
            variant_path(dest, w).write_bytes(variant_bytes(im, w))
    return im.width, im.height


def rewrite_alt(slug: str, image_path: str, subject: str) -> list[str]:
    """Point the alt text at the photo that is actually there now.

    The templates hardcode an alt written for the image we INTENDED to generate
    — PuroClean's read "technician loading a branded service van" while the file
    became nine staff at a branded step-and-repeat. Swapping the pixels and
    leaving the description is worse than either alone: it is a wrong answer to
    a screen reader and a wrong signal to Google. The triage already produced a
    literal one-line description of every asset, so the correct alt is sitting
    right there in the manifest.

    Returns the files changed. Only touches lines that pair imageSrc/src with
    THIS image, so a site whose alt was hand-written for a different slot is
    left alone."""
    changed: list[str] = []
    pages = ROOT / "sites" / slug / "src" / "pages"
    if not pages.is_dir() or not subject:
        return changed
    # The subject is model output going into an Astro template literal, so strip
    # anything that could close the literal or open an interpolation. Without
    # this a description containing a backtick silently breaks the build.
    safe = re.sub(r"[`${}\\<>\"]", "", subject).strip().rstrip(". ")
    if not safe:
        return changed
    # keep the house convention (brand name in the alt) without an em dash
    txt_alt = safe + ", ${brand.displayName}"
    for f in sorted(pages.rglob("*.astro")):
        src = f.read_text(encoding="utf-8")
        out_lines, hit = [], False
        for line in src.split("\n"):
            if image_path in line and re.search(r"\b(imageAlt|alt)=", line):
                new = re.sub(r"(\b(?:imageAlt|alt)=)(\{`[^`]*`\}|\{[^}]*\}|\"[^\"]*\")",
                             lambda m: m.group(1) + "{`" + txt_alt + "`}", line, count=1)
                if new != line:
                    hit = True
                    line = new
            out_lines.append(line)
        if hit:
            f.write_text("\n".join(out_lines), encoding="utf-8")
            changed.append(str(f.relative_to(ROOT)))
    return changed


def apply_real_photos(slug: str, *, dry_run: bool = False,
                      slots: list[str] | None = None,
                      force: bool = False, only_missing: bool = False,
                      crop_bias: dict[str, float] | None = None) -> str:
    """only_missing=True fills GAPS only — a slot whose file does not exist yet.
    That is the mode gen_site_images runs in: on a brand-new site it means the
    real photo lands before a single generation, and on a site that already
    shipped generated imagery it means nothing changes underfoot during an
    unrelated build. Swapping a live generated hero for a real one is a
    deliberate act (`photo_harvest.py apply`), not a side effect."""
    m = load_manifest(slug)
    if not m["assets"]:
        return f"{slug}: no harvested assets — run harvest first"
    site = ROOT / "sites" / slug
    if not site.is_dir():
        return f"{slug}: no sites/{slug} — nothing to apply to"
    img_dir = site / "public" / "images"
    meta_path = site / "src" / "data" / "image-meta.json"
    try:
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    except json.JSONDecodeError:
        meta = {}

    want = slots or ["hero", "team", "services"]
    targets = {"hero": ("hero-bg.webp", 16 / 9),
               "team": ("team.webp", 3 / 2),
               "services": ("services.webp", 3 / 2)}
    used = {v.get("asset") for v in m["slots"].values() if isinstance(v, dict)}
    used.discard(None)
    applied, skipped = [], []
    for slot in want:
        fname, ratio = targets[slot]
        dest = img_dir / fname
        prev = m["slots"].get(slot) or {}
        if prev.get("asset") and not force and dest.exists():
            # "already applied" counts ONLY when the file is really on disk
            # (2026-08-19, rt-olson: the manifest said hero/team/services were
            # filled while public/images/ had none of them — every later run
            # skipped on the manifest's word and the site shipped a 404 hero).
            skipped.append(f"{slot}=real:{prev['asset']} (already)")
            continue
        if prev.get("asset") and not dest.exists():
            print(f"    {slot}: manifest says applied but {fname} is missing "
                  "on disk — re-applying")
        got = pick(m, slot, used=used)
        if only_missing and dest.exists():
            if got:
                skipped.append(f"{slot}=generated image in place; real candidate "
                               f"{got[0]} available -> `photo_harvest.py apply "
                               f"--slug {slug}` to swap")
            continue
        if not got:
            skipped.append(f"{slot}=no qualifying real photo -> generation keeps it")
            continue
        key, a = got
        if dry_run:
            applied.append(f"{slot} <- {key} ({a.get('category')}, "
                           f"{a.get('slots', {}).get(slot if slot != 'services' else 'services')}, "
                           f"{a['width']}x{a['height']}) {a.get('subject','')}")
            used.add(key)
            continue
        data = _http_get(a["url"])
        if not data:
            skipped.append(f"{slot}=download failed for {key}")
            continue
        w, h = _install(data, dest, target_ratio=ratio,
                        crop_bias=(crop_bias or {}).get(
                            slot, CROP_BIAS.get(a.get("category"), 0.4)))
        from resize_images import VARIANT_WIDTHS
        meta[f"/images/{fname}"] = {"width": w, "height": h,
                                    "variants": [x for x in VARIANT_WIDTHS if x < w]}
        m["slots"][slot] = {
            "asset": key, "source": a.get("source"),
            "origin_url": a.get("origin_url") or a.get("url"),
            "category": a.get("category"), "subject": a.get("subject"),
            "installed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "file": f"/images/{fname}",
            **({"crop_bias": (crop_bias or {})[slot]}
               if slot in (crop_bias or {}) else {}),
        }
        used.add(key)
        applied.append(f"{slot} <- {key} ({a.get('category')}) {w}x{h}")
        for f in rewrite_alt(slug, f"/images/{fname}", a.get("subject", "")):
            applied.append(f"    alt rewritten in {f}")

    if not dry_run:
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(json.dumps(dict(sorted(meta.items())), indent=2) + "\n",
                             encoding="utf-8")
        save_manifest(slug, m)
    head = "[dry-run] " if dry_run else ""
    return (f"{slug}: {head}{len(applied)} slot(s) filled with REAL photos"
            + ("\n      " + "\n      ".join(applied) if applied else "")
            + ("\n      skip: " + "; ".join(skipped) if skipped else ""))


def apply_service_photos(slug: str, *, dry_run: bool = False,
                         force: bool = False) -> str:
    """Per-service cards. Far more conservative than the three brand slots: a
    service card must be a photo the triage tied to THAT service by name, or the
    generator (which at least renders the right equipment for the right job)
    stays in charge.

    force=True is the CLIENT-CORRECTION path, the mirror of gen_site_images'
    --redo: a shipped generated card is normally never overwritten, but when
    the client has looked at it and rejected it, "never overwrite" is defending
    the wrong thing. Jerrott Gray, 2026-08-05, on the fire and mold cards:
    "Photos of employees ... need to have there PPE worn corectly ... please
    make photos looks realistic and not AI slop." His own photographs are the
    answer to both halves of that sentence."""
    m = load_manifest(slug)
    site = ROOT / "sites" / slug
    svc_dir = site / "src" / "content" / "services"
    if not svc_dir.is_dir():
        return f"{slug}: no src/content/services/"
    img_dir = site / "public" / "images" / "services"
    meta_path = site / "src" / "data" / "image-meta.json"
    try:
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    except json.JSONDecodeError:
        meta = {}
    used = {v.get("asset") for v in m["slots"].values() if isinstance(v, dict)}
    used.discard(None)
    applied = []
    for md in sorted(svc_dir.glob("*.md")):
        text = md.read_text(encoding="utf-8")
        mm = re.search(r"""^service_slug:\s*['"]?([^'"\n]+?)['"]?\s*$""", text, re.M)
        svc = (mm.group(1).strip() if mm else md.stem)
        dest = img_dir / f"{svc}.webp"
        slot_key = f"service:{svc}"
        held = (m["slots"].get(slot_key) or {}).get("asset")
        if held and not force:
            continue        # a real photo already holds this card
        if dest.exists() and not held and not force:
            continue        # generated image already shipped — never overwrite
        if held:
            used.discard(held)   # re-pickable when --force re-runs the choice
        got = pick(m, "service", service_slug=svc, used=used)
        if not got:
            continue
        key, a = got
        if dry_run:
            applied.append(f"{svc} <- {key} ({a.get('category')}) {a.get('subject','')}")
            used.add(key)
            continue
        data = _http_get(a["url"])
        if not data:
            continue
        w, h = _install(data, dest, target_ratio=3 / 2,
                        crop_bias=CROP_BIAS.get(a.get("category"), 0.4))
        from resize_images import VARIANT_WIDTHS
        meta[f"/images/services/{svc}.webp"] = {
            "width": w, "height": h,
            "variants": [x for x in VARIANT_WIDTHS if x < w]}
        m["slots"][slot_key] = {
            "asset": key, "source": a.get("source"), "category": a.get("category"),
            "subject": a.get("subject"), "file": f"/images/services/{svc}.webp",
            "installed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        used.add(key)
        applied.append(f"{svc} <- {key} ({a.get('category')}) {w}x{h}")
    if not dry_run and applied:
        meta_path.write_text(json.dumps(dict(sorted(meta.items())), indent=2) + "\n",
                             encoding="utf-8")
        save_manifest(slug, m)
    return (f"{slug}: {'[dry-run] ' if dry_run else ''}{len(applied)} service card(s) "
            f"from real photos" + ("\n      " + "\n      ".join(applied) if applied else ""))


def _parse_crop_bias(spec: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for part in (spec or "").split(","):
        part = part.strip()
        if not part:
            continue
        slot, _, val = part.partition("=")
        try:
            out[slot.strip()] = max(0.0, min(1.0, float(val)))
        except ValueError:
            print(f"  ignoring bad --crop-bias term {part!r}")
    return out


def cmd_apply(args) -> int:
    bias = _parse_crop_bias(getattr(args, "crop_bias", ""))
    want = [s.strip() for s in (getattr(args, "slots", "") or "").split(",")
            if s.strip()]
    for slug in slugs_from_args(args):
        if want == ["none"]:
            print(f"  {slug}: brand slots untouched (--slots none)")
        else:
            print("  " + apply_real_photos(slug, dry_run=args.dry_run,
                                           force=args.force,
                                           slots=want or None, crop_bias=bias))
        if args.services:
            print("  " + apply_service_photos(slug, dry_run=args.dry_run,
                                              force=args.force))
    return 0


# --------------------------------------------------------------------------- #
# AUDIT
# --------------------------------------------------------------------------- #
def gbp_media_count(slug: str) -> tuple[int, str]:
    """Live count of PHOTO media on the client's listing. Returns (-1, reason)
    when we simply cannot see the listing — an honest 'unknown' rather than a
    zero that would read as 'this client has no photos'."""
    cid = gbp.company_id_for(slug)
    if not cid:
        return -1, "no company_id"
    try:
        token = gbp.get_access_token(cid)
    except Exception as e:
        return -1, f"token error {str(e)[:40]}"
    if not token:
        return -1, "not connected"
    try:
        pi = ROOT / "clients" / slug / "plan-input.json"
        brand = json.loads(pi.read_text()).get("brand", {}) if pi.exists() else {}
        place = brand.get("place_id") or gbp._place_id_from_connection(cid)
        loc = gbp.find_location(token, place or "")
        if not loc:
            return -1, "no GBP location"
        acct = gbp._g(f"{gbp.ACCT_API}/accounts", token)["accounts"][0]["name"]
        total, page, n = 0, None, 0
        while True:
            d = gbp._g(f"https://mybusiness.googleapis.com/v4/{acct}/{loc['name']}/media"
                       + (f"?pageToken={page}" if page else ""), token)
            for it in d.get("mediaItems", []):
                if it.get("mediaFormat") == "PHOTO":
                    total += 1
            page = d.get("nextPageToken")
            n += 1
            if not page or n > 12:
                break
        return total, "ok"
    except Exception as e:
        return -1, str(e)[:50]


def site_image_state(slug: str) -> str:
    m = load_manifest(slug)
    img = ROOT / "sites" / slug / "public" / "images"
    if not img.is_dir():
        return "no-site"
    real = sum(1 for s in ("hero", "team", "services")
               if (m["slots"].get(s) or {}).get("asset"))
    gen = sum(1 for f in ("hero-bg.webp", "team.webp", "services.webp")
              if (img / f).exists())
    return f"{real} real / {gen} shipped"


def cmd_audit(args) -> int:
    rows = []
    for slug in slugs_from_args(args):
        cid = gbp.company_id_for(slug)
        m = load_manifest(slug)
        assets = m["assets"]
        stored_gbp = len(_storage_list(cid, f"{GBP_PREFIX}/")) if cid else 0
        stored_web = len(_storage_list(cid, f"{WEB_PREFIX}/")) if cid else 0
        live, note = (gbp_media_count(slug) if args.live else (-1, "skipped"))
        site_url = existing_site_url(slug, cid) if cid else None
        triaged = sum(1 for a in assets.values() if a.get("category"))
        usable = sum(1 for a in assets.values()
                     if a.get("category") not in (None, "graphic", "unusable"))
        best = {s: (pick(m, s) or (None, {}))[0] for s in ("hero", "team", "services")}
        covered = sum(1 for v in best.values() if v)
        rows.append({
            "slug": slug, "gbp_live": live, "gbp_note": note,
            "stored_gbp": stored_gbp, "stored_web": stored_web,
            "existing_site": site_url, "triaged": triaged, "usable": usable,
            "slots_coverable": covered, "site": site_image_state(slug),
        })
    hdr = (f"{'client':<34}{'GBP':>5}{'stor':>6}{'web':>5}{'triaged':>9}"
           f"{'usable':>8}{'slots':>7}  {'site img':<16} existing site")
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        live = "?" if r["gbp_live"] < 0 else str(r["gbp_live"])
        print(f"{r['slug']:<34}{live:>5}{r['stored_gbp']:>6}{r['stored_web']:>5}"
              f"{r['triaged']:>9}{r['usable']:>8}{r['slots_coverable']:>6}/3  "
              f"{r['site']:<16} {r['existing_site'] or '-'}")
    tot_u = sum(r["usable"] for r in rows)
    full = sum(1 for r in rows if r["slots_coverable"] == 3)
    part = sum(1 for r in rows if 0 < r["slots_coverable"] < 3)
    print(f"\n{len(rows)} clients | {tot_u} usable real photos | "
          f"{full} can fill all 3 brand slots from real photos, "
          f"{part} partially, {len(rows)-full-part} need generation for all 3")
    if args.json:
        Path(args.json).write_text(json.dumps(rows, indent=2) + "\n")
        print(f"wrote {args.json}")
    return 0


def cmd_run(args) -> int:
    """Standing pass: harvest anything new, triage anything unclassified. Safe to
    run nightly — both halves are incremental and no-op when nothing changed.

    Every step is caught per client: on a scheduled --all run one client's
    expired token or unreachable old website must never take the other 21 down
    with it. Output is flushed per line so a run that dies mid-fleet still says
    where it got to — the first fleet pass buffered ~20 minutes of progress into
    a pipe and lost all of it."""
    for slug in slugs_from_args(args):
        try:
            cid = gbp.company_id_for(slug)
        except Exception as e:
            print(f"\n=== {slug} === company_id lookup failed: {str(e)[:120]}",
                  flush=True)
            continue
        if not cid:
            continue
        print(f"\n=== {slug} ===", flush=True)
        try:
            print("  GBP: " + gbp.import_gbp_media(slug, cap=args.cap), flush=True)
        except Exception as e:
            print(f"  GBP: ERROR {str(e)[:120]}", flush=True)
        try:
            n = register_gbp_assets(slug, cid)
            print(f"  manifest: +{n} new", flush=True)
        except Exception as e:
            print(f"  manifest: ERROR {str(e)[:120]}", flush=True)
        if not args.gbp_only:
            try:
                got, note = harvest_website(slug, cid, cap=args.cap)
                print(f"  web: {got} from {note}", flush=True)
            except Exception as e:
                print(f"  web: ERROR {str(e)[:120]}", flush=True)
        try:
            print("  " + triage(slug, batch=args.batch, limit=args.limit), flush=True)
        except Exception as e:
            print(f"  triage: ERROR {str(e)[:120]}", flush=True)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--slug", help="one slug, or comma-separated list")
        p.add_argument("--all", action="store_true", help="every client")

    a = sub.add_parser("audit"); common(a)
    a.add_argument("--live", action="store_true",
                   help="query the GBP media API for a live photo count (slow)")
    a.add_argument("--json", help="also write the inventory to this path")
    a.set_defaults(fn=cmd_audit)

    h = sub.add_parser("harvest"); common(h)
    h.add_argument("--cap", type=int, default=40)
    h.add_argument("--gbp-only", action="store_true")
    h.add_argument("--web-only", action="store_true")
    h.add_argument("--dry-run", action="store_true")
    h.set_defaults(fn=cmd_harvest)

    t = sub.add_parser("triage"); common(t)
    t.add_argument("--batch", type=int, default=6)
    t.add_argument("--limit", type=int, default=0)
    t.add_argument("--force", action="store_true", help="re-classify everything")
    t.set_defaults(fn=cmd_triage)

    ap2 = sub.add_parser("apply"); common(ap2)
    ap2.add_argument("--dry-run", action="store_true")
    ap2.add_argument("--services", action="store_true",
                     help="also fill per-service cards from real photos")
    ap2.add_argument("--force", action="store_true",
                     help="re-pick slots that already hold a real photo")
    ap2.add_argument("--slots", default="", metavar="hero,team,services|none",
                     help="limit which BRAND slots are (re)filled; 'none' "
                          "touches only the --services cards, which is what a "
                          "second --force pass wants once the three brand "
                          "slots are already right")
    ap2.add_argument("--crop-bias", default="", metavar="SLOT=F[,SLOT=F]",
                     help="override where the crop keeps the frame for a slot "
                          "(0=top, 1=bottom), e.g. team=0.95. CROP_BIAS is "
                          "keyed by CATEGORY because that is right on average, "
                          "but a subject can sit anywhere in a phone portrait "
                          "— Reign's crew shot puts both technicians in the "
                          "bottom third of a 1920x2560 frame, where the 0.32 "
                          "crew default cuts them in half")
    ap2.set_defaults(fn=cmd_apply)

    r = sub.add_parser("run"); common(r)
    r.add_argument("--cap", type=int, default=40)
    r.add_argument("--batch", type=int, default=6)
    # Bounded vision spend per client per run — `run` is what the daily and
    # weekly crons call, and an unbounded classify over a 200-photo library
    # (ProRestoration) is neither predictable nor necessary. Untriaged assets
    # simply carry to the next run; the pass is incremental and resumable, so a
    # backlog drains over successive nights instead of in one unbounded burst.
    # Pass --limit 0 for an unbounded manual backfill.
    r.add_argument("--limit", type=int, default=120)
    r.add_argument("--gbp-only", action="store_true")
    r.set_defaults(fn=cmd_run)

    args = ap.parse_args()
    if not getattr(args, "slug", None) and not getattr(args, "all", False):
        ap.error("pass --slug <slug> or --all")
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
