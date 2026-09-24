#!/usr/bin/env python3
"""
gbp_face_audit.py — GBP FRONT-FACE CONVERSION AUDIT (the "what a caller sees" lens).

Ranking work is wasted if the Google panel itself kills the call: Davis
Construction's panel shows 4 junk Street-View user photos (grass / a park) and
nothing else — nobody calls that. This script audits and fixes the FRONT-FACING
profile for every client with a CONNECTED GBP (user_integrations google row with
connection_metadata.selected_location_id):

  1. FETCH  — location (categories, serviceItems, profile.description, hours) via
     the Business Information API + photo inventory via the v4 media API
     (owner media w/ per-category counts + COVER/PROFILE detection, customer
     media count — the junk-photo surface).
  2. SCORE  — conversion-lens 0-100: owner photos >=10, cover set, logo set,
     description >=250 chars, GBP services cover the site's services, primary
     category matches the client's vertical, hours set.
  3. AUTO-FIX (with --apply, else printed):
       PHOTOS      — owner count < 10 -> upload real site assets from
                     sites/{slug}/public/images (team/crew/gallery/work/
                     before-after first, per-service images last), converted
                     webp->JPEG and uploaded via the v4 bytes flow. Capped at
                     --max-photos per run; sha1 provenance in
                     clients/{slug}/gbp-face-state.json so reruns never re-upload.
       DESCRIPTION — missing/thin -> generate from plan-input brand truth
                     (claims-gated: no invented certs/years) and PATCH it.
       SERVICES    — site services missing from the GBP -> gbp.add_services
                     (names only, never pricing).
       CATEGORIES  — NEVER auto-changed (ranking-sensitive). Mismatch -> an
                     action-plan recommendation instead.
  4. ACTION PLAN — everything not auto-fixable becomes a marketing_action_plan
     row (action_key namespace 'gbpface:', deduped on re-run, pinned=false,
     assigned_system manual): junk customer photos to report to Google, primary
     category recommendations, missing logo/cover needing a brand file.

Usage:
  python3 scripts/gbp_face_audit.py                      # dry-run, all connected clients
  python3 scripts/gbp_face_audit.py --slug narestco
  python3 scripts/gbp_face_audit.py --apply --slug narestco
  python3 scripts/gbp_face_audit.py --apply --max-photos 10

Env (rank-ai/.env or CI): SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY,
GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET, ANTHROPIC_API_KEY
(description generation only). Monthly cadence via gbp-maintenance.yml.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import gbp  # noqa: E402 — auth, Supabase REST, reconcile/add_services, _anthropic_json

GBP_V4 = "https://mybusiness.googleapis.com/v4"
GBP_UPLOAD = "https://mybusiness.googleapis.com/upload/v1/media"

MIN_OWNER_PHOTOS = 10
MIN_DESC_CHARS = 250
BREADTH_TARGET = 60   # long-tail service count of a well-built profile (fleet norm)
MAX_DESC_CHARS = 740  # GBP hard limit is 750; leave headroom
MIN_PHOTO_PX = 250    # Google's minimum photo dimension
MIN_PHOTO_BYTES = 10_240

# Conversion-lens vertical -> acceptable PRIMARY categories (normalized lower).
# Anything else => recommend (never auto-change) the flip, e.g. FireDEX's
# "Contractor" -> "Water damage restoration service".
EXPECTED_PRIMARY = {
    "restoration": {"water damage restoration service", "fire damage restoration service"},
    "plumbing": {"plumber", "plumbing service"},
    "construction": {"general contractor", "construction company"},
}

# Photo asset priority inside sites/{slug}/public/images — real people/work
# first, per-service imagery last. Responsive -480w/-768w/-1200w variants and
# the logo/lp assets are excluded.
ASSET_TIERS = [
    ("root-people", ["team", "crew", "office", "truck", "van"]),
    ("gallery", None), ("work", None), ("before-after", None), ("services", None),
]
IMG_EXTS = (".webp", ".jpg", ".jpeg", ".png")


# --------------------------------------------------------------------------- #
# enumeration — companies with a selected GBP location
# --------------------------------------------------------------------------- #
def google_integrations() -> dict[str, dict]:
    """company_id -> connection_metadata for every provider=google row."""
    rows = gbp._sb("user_integrations?provider=eq.google&select=client_id,connection_metadata")
    return {r["client_id"]: (r.get("connection_metadata") or {}) for r in rows}


def slug_company_pairs() -> list[tuple[str, str]]:
    cmap = json.loads((ROOT / "clients" / "company_map.json").read_text())
    return [(slug, cid) for slug, cid in cmap.items()]


# --------------------------------------------------------------------------- #
# fetch — location + media inventory
# --------------------------------------------------------------------------- #
def fetch_location(token: str, location_name: str) -> dict:
    url = (f"{gbp.INFO_API}/{location_name}?readMask=name,title,categories,"
           "storefrontAddress,regularHours,profile,serviceItems,metadata,websiteUri,"
           "serviceArea")
    return gbp._g(url, token)


def media_account_for(token: str, location_id: str) -> str | None:
    """The v4 media endpoints need an account parent; find one that can see
    this location's media."""
    for acct in gbp._g(f"{gbp.ACCT_API}/accounts", token).get("accounts", []):
        r = requests.get(f"{GBP_V4}/{acct['name']}/locations/{location_id}/media?pageSize=1",
                         headers={"Authorization": f"Bearer {token}"})
        if r.ok:
            return acct["name"]
    return None


def fetch_media(token: str, acct: str, location_id: str) -> dict:
    """Owner media inventory (all pages) + customer media count."""
    base = f"{GBP_V4}/{acct}/locations/{location_id}/media"
    items, page_token = [], None
    while True:
        url = base + "?pageSize=100" + (f"&pageToken={page_token}" if page_token else "")
        r = requests.get(url, headers={"Authorization": f"Bearer {token}"})
        r.raise_for_status()
        data = r.json()
        items.extend(data.get("mediaItems", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    cats: dict[str, int] = {}
    for it in items:
        c = (it.get("locationAssociation") or {}).get("category") or "UNKNOWN"
        cats[c] = cats.get(c, 0) + 1
    rc = requests.get(base + "/customers?pageSize=1",
                      headers={"Authorization": f"Bearer {token}"})
    customer_count = rc.json().get("totalMediaItemCount", 0) if rc.ok else None
    # Cover-photo candidates for the app's picker (googleusercontent URLs
    # accept a =sNNNN size suffix; strip any existing one first). Landscape
    # photos only — GBP covers are 16:9 and reject portrait crops badly.
    candidates = []
    for it in items:
        cat = (it.get("locationAssociation") or {}).get("category") or "UNKNOWN"
        if cat in ("COVER", "PROFILE", "LOGO"):
            continue
        raw = it.get("googleUrl") or it.get("thumbnailUrl") or ""
        if "googleusercontent" not in raw:
            continue
        dim = it.get("dimensions") or {}
        w, h = dim.get("widthPixels") or 0, dim.get("heightPixels") or 0
        if w and h and w <= h:
            continue
        base_url = raw.split("=")[0]
        candidates.append({"name": it.get("name"), "category": cat,
                           "thumb": base_url + "=s640",
                           "full": base_url + "=s2560"})
        if len(candidates) >= 24:
            break
    return {
        "owner_count": len(items),
        "owner_by_category": cats,
        "has_cover": bool(cats.get("COVER")),
        "has_logo": bool(cats.get("PROFILE") or cats.get("LOGO")),
        "customer_count": customer_count,
        "photo_candidates": candidates,
    }


def profile_snapshot(slug: str, loc: dict, media: dict) -> dict:
    g = gbp.summarize(loc)
    site = gbp.site_services(slug)
    client = json.loads((ROOT / "clients" / f"{slug}.json").read_text())
    vertical = client.get("vertical", "")
    # Listing-declared service-area towns (Igler adoption 2026-07-17): tells
    # Google how far from the pin the business deserves calls. Compared against
    # the plan's service_areas; read-only for now (set comes after one cycle).
    sa_places = [pi.get("placeName") or pi.get("name") or ""
                 for pi in ((loc.get("serviceArea") or {}).get("places") or {}).get("placeInfos", [])]
    plan_areas = []
    try:
        pi_path = ROOT / "clients" / slug / "plan-input.json"
        if pi_path.exists():
            plan_areas = [a.get("label") or a.get("name") or str(a)
                          for a in json.loads(pi_path.read_text()).get("service_areas", [])]
    except Exception:
        pass
    # Score v2 inputs (2026-09-24): review volume + keyworded-name state.
    review_count, name_applied = 0, False
    try:
        cmap = json.loads((ROOT / "clients" / "company_map.json").read_text())
        cid = cmap.get(slug)
        if cid:
            prow = gbp._sb("marketing_gbp_profiles?company_id=eq." + cid
                           + "&select=review_count")
            review_count = int((prow or [{}])[0].get("review_count") or 0)
            applied = gbp._sb("marketing_gbp_suggestions?company_id=eq." + cid
                              + "&item_type=eq.name&status=eq.applied"
                              "&select=item&limit=1")
            name_applied = bool(applied)
    except Exception as e:  # noqa: BLE001 — score v2 inputs never kill audit
        print(f"    (score-v2 inputs warn: {str(e)[:70]})")
    return {
        "slug": slug, "title": g["title"], "vertical": vertical,
        "primary_category": g["primary_category"],
        "additional_categories": g["additional_categories"],
        "gbp_services": g["services"], "site_services": site,
        "description_len": g["description_len"], "has_hours": g["has_hours"],
        "service_area_places": sa_places,
        "plan_service_areas": plan_areas,
        "review_count": review_count, "name_applied": name_applied,
        **media,
    }


# --------------------------------------------------------------------------- #
# score — the conversion lens
# --------------------------------------------------------------------------- #
def score_profile(p: dict) -> dict:
    """Score v2 (Santino 2026-09-24, Coastal case: a 100 at 29 reviews with
    no keyworded name meant "fields filled", not "nothing left"). v1 was
    pure profile completeness; v2 folds in the three levers that were
    invisible: review volume, the rename opportunity, service breadth.
    100 now means genuinely nothing left that we know how to improve.

    Weights (sum 100): media 30 (photos 15/cover 7/logo 8), description 10,
    category 15, hours 5, services-parity 10, service-breadth 10,
    reviews 12, keyworded-name 8."""
    parts: dict[str, float] = {}
    parts["photos"] = round(min((p["owner_count"] or 0) / MIN_OWNER_PHOTOS, 1.0) * 15, 1)
    parts["cover"] = 7.0 if p["has_cover"] else 0.0
    parts["logo"] = 8.0 if p["has_logo"] else 0.0
    dl = p["description_len"]
    parts["description"] = 10.0 if dl >= MIN_DESC_CHARS else (5.0 if dl > 0 else 0.0)
    n_site = max(len(p["site_services"]), 1)
    parts["services"] = round(min(len(p["gbp_services"]) / n_site, 1.0) * 10, 1)
    # Breadth: services rank for their exact wording, so long-tail coverage
    # is a ranking lever beyond site parity. BREADTH_TARGET is the fleet
    # norm for a well-built profile, not a Google limit.
    parts["service_breadth"] = round(
        min(len(p["gbp_services"]) / BREADTH_TARGET, 1.0) * 10, 1)
    expected = EXPECTED_PRIMARY.get(p["vertical"], set())
    cat_ok = (p["primary_category"] or "").strip().lower() in expected if expected else True
    parts["category"] = 15.0 if cat_ok else 0.0
    parts["hours"] = 5.0 if p["has_hours"] else 0.0
    # Review volume: what callers see next to the name. Tiered — the
    # review campaign is the lever that lifts it.
    rc = p.get("review_count") or 0
    parts["reviews"] = 12.0 if rc >= 50 else (6.0 if rc >= 20 else 0.0)
    # Keyworded name: the strongest single ranking field (house law
    # 2026-09-10). Full points only when an applied name row exists;
    # candidates pending or dismissed = the opportunity is still on the
    # table and the listing is not fully optimized.
    parts["keyworded_name"] = 8.0 if p.get("name_applied") else 0.0
    return {"total": round(sum(parts.values()), 1), "parts": parts, "category_ok": cat_ok}


# --------------------------------------------------------------------------- #
# auto-fix: photos (bytes upload; sha1 provenance so reruns never re-upload)
# --------------------------------------------------------------------------- #
def state_path(slug: str) -> Path:
    return ROOT / "clients" / slug / "gbp-face-state.json"


def load_state(slug: str) -> dict:
    p = state_path(slug)
    if p.exists():
        return json.loads(p.read_text())
    return {"uploaded": {}}


def save_state(slug: str, state: dict) -> None:
    p = state_path(slug)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2) + "\n")


def _is_variant(name: str) -> bool:
    stem = Path(name).stem
    return stem.endswith(("-480w", "-768w", "-1200w")) or stem.startswith(("logo", "favicon", "icon"))


def candidate_photos(slug: str) -> list[Path]:
    """Real site assets in conversion priority order (people/work > gallery >
    before-after > per-service), base variants only, deduped by stem so the
    .webp and .png of the same shot don't both upload."""
    img_dir = ROOT / "sites" / slug / "public" / "images"
    if not img_dir.exists():
        return []
    out: list[Path] = []
    seen_stems: set[str] = set()

    def add(p: Path) -> None:
        if p.suffix.lower() not in IMG_EXTS or _is_variant(p.name):
            return
        if p.stem in seen_stems:
            return
        seen_stems.add(p.stem)
        out.append(p)

    for tier, roots in ASSET_TIERS:
        if roots is not None:  # root-level people/work shots
            for f in sorted(img_dir.iterdir()):
                if f.is_file() and any(f.stem.startswith(r) for r in roots):
                    add(f)
        else:
            d = img_dir / tier
            if d.is_dir():
                for f in sorted(d.iterdir()):
                    if f.is_file():
                        add(f)
    return out


def to_jpeg(path: Path) -> bytes | None:
    """webp/png -> JPEG bytes meeting Google's minimums, or None if unusable."""
    from PIL import Image
    try:
        im = Image.open(path)
        if min(im.size) < MIN_PHOTO_PX:
            return None
        buf = io.BytesIO()
        im.convert("RGB").save(buf, "JPEG", quality=88)
        data = buf.getvalue()
        return data if len(data) >= MIN_PHOTO_BYTES else None
    except Exception:
        return None


def live_image_url(slug: str, path: Path) -> str | None:
    """Public URL of a sites/{slug}/public/... asset on the client's live site."""
    rec = json.loads((ROOT / "clients" / f"{slug}.json").read_text())
    origin = (rec.get("deploy_url") or "").rstrip("/")
    if not origin:
        return None
    public_dir = ROOT / "sites" / slug / "public"
    try:
        rel = path.relative_to(public_dir)
    except ValueError:
        return None
    return f"{origin}/{rel.as_posix()}"


def upload_photo_source_url(token: str, acct: str, location_id: str, url: str,
                            category: str = "ADDITIONAL") -> str:
    """v4 sourceUrl flow (the path gbp_photos.py has proven in prod). Returns the
    created media resource name."""
    r = requests.post(f"{GBP_V4}/{acct}/locations/{location_id}/media",
                      headers={"Authorization": f"Bearer {token}",
                               "Content-Type": "application/json"},
                      json={"mediaFormat": "PHOTO",
                            "locationAssociation": {"category": category},
                            "sourceUrl": url})
    if r.status_code not in (200, 201):
        raise RuntimeError(f"sourceUrl create HTTP {r.status_code}: {r.text[:200]}")
    return r.json().get("name", url)


def upload_photo_bytes(token: str, acct: str, location_id: str, jpeg: bytes,
                       category: str = "ADDITIONAL") -> str:
    """v4 bytes flow: startUpload -> PUT bytes -> create media item. Returns the
    created media resource name. (Fallback — some locations 500 on dataRef
    creates, so sourceUrl is tried first.)"""
    hdr = {"Authorization": f"Bearer {token}"}
    r = requests.post(f"{GBP_V4}/{acct}/locations/{location_id}/media:startUpload",
                      headers={**hdr, "Content-Type": "application/json"}, json={})
    r.raise_for_status()
    ref = r.json()["resourceName"]
    r2 = requests.post(f"{GBP_UPLOAD}/{ref}?upload_type=media",
                       headers={**hdr, "Content-Type": "image/jpeg"}, data=jpeg)
    r2.raise_for_status()
    r3 = requests.post(f"{GBP_V4}/{acct}/locations/{location_id}/media",
                       headers={**hdr, "Content-Type": "application/json"},
                       json={"mediaFormat": "PHOTO",
                             "locationAssociation": {"category": category},
                             "dataRef": {"resourceName": ref}})
    if r3.status_code not in (200, 201):
        raise RuntimeError(f"media create HTTP {r3.status_code}: {r3.text[:200]}")
    return r3.json().get("name", ref)


def set_cover_photo(slug: str, company_id: str, meta: dict, photo_url: str) -> None:
    """One-click cover: upload photo_url as the location's COVER photo, then
    re-audit the client so the app's score card reflects it. Google may take
    a few minutes to swap the panel image (and can reject images under
    480x270 — the picker only offers landscape owner photos)."""
    location_name = meta["selected_location_id"]
    location_id = location_name.split("/")[-1]
    token = gbp.get_access_token(company_id)
    if not token:
        raise RuntimeError(f"{slug}: token refresh failed")
    acct = media_account_for(token, location_id)
    if not acct:
        raise RuntimeError(f"{slug}: no v4 media account access")
    try:
        name = upload_photo_source_url(token, acct, location_id, photo_url,
                                       category="COVER")
    except RuntimeError:
        jpeg = requests.get(photo_url, timeout=60)
        jpeg.raise_for_status()
        name = upload_photo_bytes(token, acct, location_id, jpeg.content,
                                  category="COVER")
    print(f"  {slug}: cover photo set ({name})")
    # CHANGE-LOG (Santino 2026-08-12: he set Go Green's cover from the app
    # and it never reached marketing_gbp_changes — every client-visible GBP
    # change must land there; it feeds the Monthly Summary). Best-effort,
    # never blocks the change itself.
    try:
        sb_url = os.environ["SUPABASE_URL"].rstrip("/")
        sb_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        requests.post(
            f"{sb_url}/rest/v1/marketing_gbp_changes",
            headers={"apikey": sb_key, "Authorization": f"Bearer {sb_key}",
                     "Content-Type": "application/json"},
            json={"company_id": company_id,
                  "change_type": "profile_cover_photo",
                  "summary": "New cover photo set on the Google listing",
                  "actor": "app",
                  "meta": {"media_name": name, "photo_url": photo_url[:300]}},
            timeout=20).raise_for_status()
    except Exception as e:  # noqa: BLE001
        print(f"  [log] cover change-log failed (non-blocking): {str(e)[:80]}")


def r2_hosted_jpeg(slug: str, path: Path, jpeg: bytes) -> str | None:
    """Host a JPEG conversion on the client's R2 bucket (webp is rejected by the
    GBP sourceUrl fetcher) and return its public URL."""
    rec = json.loads((ROOT / "clients" / f"{slug}.json").read_text())
    r2 = rec.get("r2") or {}
    bucket, public = r2.get("bucket"), (r2.get("public_url") or "").rstrip("/")
    if not (bucket and public):
        return None
    import image_utils
    key = f"gbp-face/{path.stem}.jpg"
    if not image_utils.upload_bytes_to_r2(bucket, key, jpeg, content_type="image/jpeg"):
        return None
    return f"{public}/{key}"


def fix_photos(slug: str, token: str, acct: str, location_id: str,
               owner_count: int, max_photos: int, apply: bool) -> list[str]:
    notes: list[str] = []
    needed = max(0, MIN_OWNER_PHOTOS - owner_count)
    if needed == 0:
        return notes
    goal = min(needed, max_photos)
    state = load_state(slug)
    done = 0
    for p in candidate_photos(slug):
        if done >= goal:
            break
        digest = hashlib.sha1(p.read_bytes()).hexdigest()
        if digest in state["uploaded"]:
            continue
        rel = str(p.relative_to(ROOT))
        if not apply:
            notes.append(f"photos: WOULD upload {rel}")
            done += 1
            continue
        errors: list[str] = []
        media_name = None
        is_webp = p.suffix.lower() == ".webp"
        # 1) sourceUrl straight off the live site (the path gbp_photos.py proved).
        #    Google's fetcher rejects webp, so only jpg/png go direct.
        url = live_image_url(slug, p)
        if url and not is_webp:
            try:
                media_name = upload_photo_source_url(token, acct, location_id, url)
            except Exception as e:  # noqa: BLE001
                errors.append(str(e)[:110])
        # 2) JPEG conversion hosted on the client's R2 bucket -> sourceUrl.
        if media_name is None:
            jpeg = to_jpeg(p)
            if jpeg is None:
                notes.append(f"photos: skip {rel} (below {MIN_PHOTO_PX}px/{MIN_PHOTO_BYTES}B minimum)")
                continue
            r2_url = r2_hosted_jpeg(slug, p, jpeg)
            if r2_url:
                try:
                    media_name = upload_photo_source_url(token, acct, location_id, r2_url)
                except Exception as e:  # noqa: BLE001
                    errors.append(str(e)[:110])
            # 3) last resort: v4 bytes flow (some locations 500 on dataRef creates).
            if media_name is None:
                try:
                    media_name = upload_photo_bytes(token, acct, location_id, jpeg)
                except Exception as e:  # noqa: BLE001 — one bad photo must not stop the batch
                    errors.append(str(e)[:110])
        if media_name is None:
            notes.append(f"photos: FAILED {rel} ({'; '.join(errors)})")
            continue
        state["uploaded"][digest] = {
            "file": rel, "media_name": media_name,
            "at": datetime.now(timezone.utc).isoformat()}
        save_state(slug, state)  # save per-upload: a later failure never loses provenance
        notes.append(f"photos: uploaded {rel} -> {media_name}")
        done += 1
    if done < goal:
        notes.append(f"photos: {goal - done} of {goal} needed upload(s) unfilled "
                     "(assets exhausted or failing)")
    return notes


# --------------------------------------------------------------------------- #
# auto-fix: description (claims-gated) + services
# --------------------------------------------------------------------------- #
def generate_description(slug: str) -> str | None:
    pi = json.loads((ROOT / "clients" / slug / "plan-input.json").read_text())
    brand, areas = pi.get("brand", {}), pi.get("service_areas", [])
    cities = [a.get("city") for a in areas if a.get("city")][:6]
    truth = {
        "business_name": brand.get("display_name"),
        "phone": brand.get("phone"),
        "services": gbp.site_services(slug)[:14],
        "cities": cities,
        "certifications": brand.get("certifications") or [],
        "license_numbers": brand.get("license_numbers") or [],
        "founded_year": brand.get("founded_year"),
        "hours": brand.get("hours"),
    }
    system = (
        "You write Google Business Profile descriptions for local home-service "
        "businesses. CLAIMS-GATED: use ONLY the facts provided — never invent "
        "certifications, years in business, awards, guarantees, response times, or "
        "insurance claims that are not in the data. Null/empty fields must simply be "
        "omitted. No phone numbers, URLs, or ALL-CAPS. Plain confident prose, "
        "customer-benefit led, naming the core services and service area.")
    user = (f"Write one GBP business description, 400-{MAX_DESC_CHARS} characters, for this "
            f"business. Return STRICT JSON only: {{\"description\": str}}.\n\nFACTS:\n"
            + json.dumps(truth, indent=2))
    try:
        desc = (gbp._anthropic_json(system, user).get("description") or "").strip()
    except Exception as e:  # noqa: BLE001
        print(f"     description generation failed: {str(e)[:140]}")
        return None
    return desc[:MAX_DESC_CHARS] if len(desc) >= 100 else None


def set_description(token: str, location_name: str, text: str) -> None:
    r = requests.patch(f"{gbp.INFO_API}/{location_name}?updateMask=profile.description",
                       headers={"Authorization": f"Bearer {token}",
                                "Content-Type": "application/json"},
                       json={"profile": {"description": text}})
    if not r.ok:
        raise RuntimeError(f"description PATCH HTTP {r.status_code}: {r.text[:200]}")


def fix_description(slug: str, token: str, location_name: str,
                    desc_len: int, apply: bool) -> list[str]:
    if desc_len >= MIN_DESC_CHARS:
        return []
    if not apply:
        return [f"description: WOULD generate + set (currently {desc_len} chars)"]
    text = generate_description(slug)
    if not text:
        return ["description: generation produced nothing usable — left unchanged"]
    set_description(token, location_name, text)
    return [f"description: set ({len(text)} chars): {text[:90]}..."]


def fix_services(slug: str, apply: bool) -> list[str]:
    rec = gbp.reconcile(slug)
    missing = rec.get("site_without_gbp") or []
    if not missing:
        return []
    if not apply:
        return [f"services: WOULD add {len(missing)} -> {missing}"]
    return ["services: " + gbp.add_services(slug, missing)]


# --------------------------------------------------------------------------- #
# action plan (namespace gbpface:, deduped, pinned=false, manual)
# --------------------------------------------------------------------------- #
def action_key(action_type: str, target: str, dedupe: str) -> str:
    return "gbpface:" + hashlib.sha1(f"{action_type}|{target}|{dedupe}".encode()).hexdigest()[:16]


def plan_items(p: dict, score: dict) -> list[dict]:
    slug, title = p["slug"], p["title"] or p["slug"]
    items: list[dict] = []
    if (p["customer_count"] or 0) > 0:
        items.append({
            "dedupe": "junk-customer-photos", "priority": 1, "impact": "high",
            "title": f"Review {p['customer_count']} customer-uploaded Google photos, report junk to Google",
            "rationale": (f"GBP front-face audit: '{title}' has {p['customer_count']} customer/"
                          f"user-uploaded photos vs {p['owner_count']} owner photos. Junk user "
                          "uploads (Street View grabs, grass/park shots — the Davis Construction "
                          "failure mode) sit on the Google panel and kill call conversion "
                          "regardless of ranking. The API cannot delete them: open the listing's "
                          "photo gallery, and for each off-topic photo use 'Report a problem' to "
                          "request removal, then keep owner photos flowing so they dominate.")})
    if not score["category_ok"]:
        expected = ", ".join(sorted(EXPECTED_PRIMARY.get(p["vertical"], set()))) or p["vertical"]
        items.append({
            "dedupe": "primary-category", "priority": 1, "impact": "high",
            "title": f"Recommend primary GBP category change: '{p['primary_category']}' -> {expected}",
            "rationale": (f"GBP front-face audit: primary category '{p['primary_category']}' does "
                          f"not match the client's vertical ({p['vertical']}; expected one of: "
                          f"{expected}). Primary category is the single strongest local-pack "
                          "signal AND the label shown on the panel. NEVER auto-changed "
                          "(ranking-sensitive) — review and apply manually in the GBP dashboard, "
                          "ideally in a low-traffic window, and watch the geo-grid after.")})
    sa_n, plan_n = len(p.get("service_area_places") or []), len(p.get("plan_service_areas") or [])
    if plan_n and sa_n < min(plan_n, 10):
        items.append({
            "dedupe": "service-area-thin", "priority": 2, "impact": "medium",
            "title": f"GBP service areas thin: {sa_n} towns listed vs {plan_n} in the plan",
            "rationale": (f"GBP front-face audit: '{title}' declares only {sa_n} service-area "
                          f"place(s) on the listing while the site plan targets {plan_n} areas. "
                          "The listing's service-area list tells Google how far from the pin the "
                          "business deserves calls (rule of thumb: everything within ~2h drive, "
                          "Google caps at 20). Add the plan's top towns/counties in the GBP "
                          "dashboard (Edit profile > Location and areas). Listing currently has: "
                          + (", ".join(p["service_area_places"]) or "none") + ".")})
    if not p["has_logo"]:
        items.append({
            "dedupe": "logo-missing", "priority": 2, "impact": "medium",
            "title": "Upload GBP logo (profile photo), needs the brand file",
            "rationale": (f"GBP front-face audit: '{title}' has no logo/profile photo. The logo "
                          "renders next to the business name on the panel, in Maps and on review "
                          "replies — its absence reads as unestablished. Upload the brand logo "
                          f"(sites/{slug}/public/images/logo.* if present, sized >=250x250, "
                          "ideally square PNG on white) via the GBP dashboard Photos > Logo.")})
    if not p["has_cover"]:
        items.append({
            "dedupe": "cover-missing", "priority": 2, "impact": "medium",
            "title": "Set GBP cover photo, pick the strongest real work/team shot",
            "rationale": (f"GBP front-face audit: '{title}' has no COVER photo, so Google chooses "
                          "what tops the panel (often a user upload — the junk-photo failure "
                          "mode). Set a strong, real, landscape work/team shot as the cover in "
                          "the GBP dashboard Photos > Cover. Cover selection is a preference "
                          "signal Google usually honors.")})
    return items


def upsert_plan_items(company_id: str, slug: str, items: list[dict], apply: bool) -> int:
    if not items:
        return 0
    existing_rows = gbp._sb(f"marketing_action_plan?company_id=eq.{company_id}&select=action_key")
    existing = {r.get("action_key") for r in existing_rows}
    now = datetime.now(timezone.utc).isoformat()
    inserts = []
    for it in items:
        key = action_key("gbp_face_fix", slug, it["dedupe"])
        if key in existing:
            continue
        inserts.append({
            "company_id": company_id, "rank_ai_slug": slug,
            "action_type": "gbp_face_fix", "assigned_system": "manual",
            "title": it["title"], "rationale": it["rationale"],
            "target": f"gbp:{slug}", "impact": it["impact"], "effort": "low",
            "status": "planned", "pinned": False, "priority": it["priority"],
            "action_key": key, "source_run_at": now,
        })
    if not apply:
        for row in inserts:
            print(f"     [dry-run] would insert plan row: {row['title'][:90]}")
        return len(inserts)
    if inserts:
        requests.post(f"{gbp.SB_URL}/rest/v1/marketing_action_plan",
                      headers={"apikey": gbp.SB_KEY, "Authorization": f"Bearer {gbp.SB_KEY}",
                               "Content-Type": "application/json", "Prefer": "return=minimal"},
                      data=json.dumps(inserts)).raise_for_status()
    return len(inserts)


# --------------------------------------------------------------------------- #
# persist — marketing_gbp_face_audit (the app's GBP Face Score card reads this)
# --------------------------------------------------------------------------- #
def autofix_actions(fixes: list[str]) -> list[str]:
    """Safe actions available, derived from what the fixers themselves decided
    (dry-run 'WOULD ...' or apply-mode success notes) so the app's 1-click
    button never promises work --apply wouldn't actually do. Never categories."""
    actions: list[str] = []

    def hit(action: str) -> None:
        if action not in actions:
            actions.append(action)

    for f in fixes:
        if f.startswith("photos:") and ("WOULD upload" in f or "uploaded" in f):
            hit("upload_photos")
        elif f.startswith("description:") and ("WOULD" in f or f.startswith("description: set")):
            hit("set_description")
        elif f.startswith("services:") and ("WOULD add" in f or "added" in f):
            hit("add_services")
    return actions


def persist_audit(company_id: str, p: dict, score: dict,
                  items: list[dict], applied: bool) -> None:
    """Upsert the score row. Dry-run also writes — scores are read-only facts;
    last_applied_at is only touched when --apply actually ran fixes."""
    expected = sorted(EXPECTED_PRIMARY.get(p["vertical"], set()))
    row = {
        "company_id": company_id,
        "rank_ai_slug": p["slug"],
        "score": score["total"],
        "components": {
            "photos": {"owner_count": p["owner_count"], "cover": p["has_cover"],
                       "logo": p["has_logo"], "customer_count": p["customer_count"],
                       "candidates": p.get("photo_candidates") or [],
                       "score": score["parts"]["photos"],
                       "cover_score": score["parts"]["cover"],
                       "logo_score": score["parts"]["logo"]},
            "description": {"chars": p["description_len"], "min_chars": MIN_DESC_CHARS,
                            "score": score["parts"]["description"]},
            "services": {"gbp_count": len(p["gbp_services"]),
                         "site_count": len(p["site_services"]),
                         "score": score["parts"]["services"]},
            "category": {"primary": p["primary_category"], "expected": expected,
                         "match": score["category_ok"], "score": score["parts"]["category"]},
            "hours": {"set": p["has_hours"], "score": score["parts"]["hours"]},
            # Multi-GBP: one entry per managed listing (primary first) so the
            # app renders a score card per listing. Single-listing clients get
            # a one-entry list — same shape everywhere.
            "locations": [location_summary(p)] + (p.get("extra_locations") or []),
        },
        "flags": [{"key": it["dedupe"], "impact": it["impact"], "title": it["title"]}
                  for it in items],
        "autofixable": autofix_actions(p.get("fixes") or []),
        "audited_at": datetime.now(timezone.utc).isoformat(),
    }
    if applied:
        row["last_applied_at"] = row["audited_at"]
    try:
        gbp._sb_upsert("marketing_gbp_face_audit", [row], on_conflict="company_id")
    except Exception as e:  # noqa: BLE001 — persistence must never abort the audit
        print(f"     persist failed: {str(e)[:140]}")


# --------------------------------------------------------------------------- #
# per-client run
# --------------------------------------------------------------------------- #
def audit_client(slug: str, company_id: str, meta: dict, apply: bool,
                 max_photos: int, location: dict = None,
                 persist: bool = True, run_fixes: bool = True) -> dict | None:
    """Audit one location. Multi-GBP: `location` overrides the primary
    (selected_location_id); secondary listings run audit-only (run_fixes=False,
    persist=False) and are folded into the primary's row by audit_company."""
    location_name = (location or {}).get("location_id") or meta["selected_location_id"]
    location_id = location_name.split("/")[-1]
    token = gbp.get_access_token(company_id)
    if not token:
        print(f"  {slug}: SKIP — google row exists but token refresh failed")
        return None
    loc = fetch_location(token, location_name)
    acct = media_account_for(token, location_id)
    media = fetch_media(token, acct, location_id) if acct else {
        "owner_count": 0, "owner_by_category": {}, "has_cover": False,
        "has_logo": False, "customer_count": None}
    p = profile_snapshot(slug, loc, media)
    score = score_profile(p)
    p["score"] = score

    print(f"\n## {slug} — {p['title']}   SCORE {score['total']}/100")
    print(f"   parts: {score['parts']}")
    print(f"   photos: {p['owner_count']} owner ({p['owner_by_category']}) | "
          f"{p['customer_count']} customer | cover={p['has_cover']} logo={p['has_logo']}")
    print(f"   category: {p['primary_category']} ({'OK' if score['category_ok'] else 'MISMATCH'})"
          f" | services {len(p['gbp_services'])} GBP vs {len(p['site_services'])} site"
          f" | description {p['description_len']} chars | hours={p['has_hours']}")

    fixes: list[str] = []
    if run_fixes:
        if acct:
            fixes += fix_photos(slug, token, acct, location_id, p["owner_count"], max_photos, apply)
        else:
            fixes.append("photos: no v4 media account access — photo fix skipped")
        fixes += fix_description(slug, token, location_name, p["description_len"], apply)
        fixes += fix_services(slug, apply)
        for f in fixes:
            print(f"   -> {f}")
        if not fixes:
            print("   -> no auto-fixes needed")
        # CHANGE-LOG (2026-08-12, same gap as set_cover_photo): applied fixes
        # must reach marketing_gbp_changes or they never show in the client's
        # Monthly Summary. One plain row per applied fix line; dry runs and
        # WOULD/skipped lines never log.
        if apply:
            _CHANGE_LINES = {
                "photos": ("profile_photos",
                           "New photos uploaded to the Google listing"),
                "description": ("profile_description",
                                "Business description updated on the Google listing"),
                "services": ("service_add",
                             "Services added to the Google listing"),
            }
            for f in fixes:
                kind = f.split(":", 1)[0].strip()
                low = f.lower()
                if kind not in _CHANGE_LINES or "would" in low or "skipped" in low \
                        or "left unchanged" in low or "no v4" in low:
                    continue
                ctype, summary = _CHANGE_LINES[kind]
                try:
                    sb_url = os.environ["SUPABASE_URL"].rstrip("/")
                    sb_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
                    requests.post(
                        f"{sb_url}/rest/v1/marketing_gbp_changes",
                        headers={"apikey": sb_key,
                                 "Authorization": f"Bearer {sb_key}",
                                 "Content-Type": "application/json"},
                        json={"company_id": company_id, "change_type": ctype,
                              "summary": summary, "actor": "optimizer",
                              "meta": {"detail": f[:300]}},
                        timeout=20).raise_for_status()
                except Exception as e:  # noqa: BLE001
                    print(f"   [log] change-log failed (non-blocking): {str(e)[:80]}")
    items = plan_items(p, score)
    if location and (location.get("title") or "").strip():
        # Secondary listing: tag plan items so they don't collide with the
        # primary's dedupe keys and read unambiguously in the app.
        loc_tag = location["title"].strip()
        for it in items:
            it["dedupe"] = f"{it['dedupe']}:{location_name.split('/')[-1]}"
            it["title"] = f"[{loc_tag}] {it['title']}"
    n = upsert_plan_items(company_id, slug, items, apply)
    if n and apply:
        print(f"   -> {n} action-plan row(s) inserted (gbpface:)")
    p["fixes"] = fixes
    p["location_name"] = location_name
    p["location_title"] = (location or {}).get("title") or p.get("title") or ""
    p["items"] = items
    if persist:
        persist_audit(company_id, p, score, items, applied=apply)
    return p


def location_summary(p: dict) -> dict:
    """Compact per-listing entry for components.locations (multi-GBP UI)."""
    s = p["score"]
    return {
        "location_id": p.get("location_name"),
        "title": p.get("location_title") or p.get("title"),
        "score": s["total"], "parts": s["parts"],
        "owner_count": p["owner_count"], "customer_count": p["customer_count"],
        "cover": p["has_cover"], "logo": p["has_logo"],
        "description_chars": p["description_len"],
        "services_count": len(p["gbp_services"]),
        "primary_category": p["primary_category"],
        "category_ok": s["category_ok"], "hours": p["has_hours"],
    }


def audit_company(slug: str, cid: str, meta: dict, apply: bool,
                  max_photos: int) -> dict | None:
    """Audit every managed listing for a company (multi-GBP Phase 1).

    Primary = selected_locations[0] (or the legacy selected_location_id):
    full audit + auto-fixes + persisted row. Secondaries: audit-only (no
    writes to Google), folded into the primary row's components.locations so
    the app renders one score card per listing without schema changes."""
    locs = [l for l in (meta.get("selected_locations") or [])
            if isinstance(l, dict) and l.get("location_id")]
    if not locs:
        locs = [{"location_id": meta["selected_location_id"],
                 "title": meta.get("selected_location_title") or ""}]
    primary = audit_client(slug, cid, meta, apply, max_photos,
                           location=locs[0], persist=False, run_fixes=True)
    if not primary:
        return None
    extras = []
    for loc in locs[1:]:
        try:
            p = audit_client(slug, cid, meta, apply, max_photos,
                             location=loc, persist=False, run_fixes=False)
            if p:
                extras.append(p)
        except Exception as e:  # noqa: BLE001 — one listing never kills the run
            print(f"  {slug}: secondary listing {loc.get('title') or loc['location_id']} "
                  f"ERROR ({str(e)[:120]}) — skipped")
    primary["extra_locations"] = [location_summary(p) for p in extras]
    persist_audit(cid, primary, primary["score"], primary["items"], applied=apply)
    return primary


def main() -> int:
    ap = argparse.ArgumentParser(description="GBP front-face conversion audit + fix")
    ap.add_argument("--slug", help="one client only")
    ap.add_argument("--apply", action="store_true",
                    help="execute fixes + insert plan rows (default: dry-run)")
    ap.add_argument("--max-photos", type=int, default=10,
                    help="max photo uploads per client per run (default 10)")
    ap.add_argument("--set-cover", metavar="URL",
                    help="set this photo as the COVER for --slug, then re-audit")
    args = ap.parse_args()

    integrations = google_integrations()

    if args.set_cover:
        if not args.slug:
            ap.error("--set-cover requires --slug")
        pairs = dict(slug_company_pairs())
        cid = pairs.get(args.slug)
        meta = integrations.get(cid) if cid else None
        if not meta or not meta.get("selected_location_id"):
            print(f"  {args.slug}: no connected GBP location")
            return 1
        set_cover_photo(args.slug, cid, meta, args.set_cover)
        audit_company(args.slug, cid, meta, apply=False, max_photos=0)
        return 0

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"=== GBP front-face audit [{mode}] ===")
    results = []
    for slug, cid in slug_company_pairs():
        if args.slug and slug != args.slug:
            continue
        meta = integrations.get(cid)
        if meta is None:
            print(f"  {slug}: SKIP — no Google integration connected (run the connect flow)")
            continue
        if not meta.get("selected_location_id"):
            print(f"  {slug}: SKIP — Google connected but no GBP location selected "
                  "(0 locations on the account, or selection pending)")
            continue
        try:
            r = audit_company(slug, cid, meta, args.apply, args.max_photos)
            if r:
                results.append(r)
        except Exception as e:  # one client must never abort a scheduled run
            print(f"  {slug}: ERROR ({type(e).__name__}: {str(e)[:200]}) — skipped")

    if results:
        print(f"\n{'SLUG':<34}{'SCORE':>6}  {'PHOTOS':>7}  {'CUST':>5}  "
              f"{'COVER':>6}  {'LOGO':>5}  {'DESC':>5}  {'SVCS':>9}  CATEGORY")
        for p in results:
            print(f"{p['slug']:<34}{p['score']['total']:>6}  {p['owner_count']:>7}  "
                  f"{str(p['customer_count']):>5}  {str(p['has_cover']):>6}  "
                  f"{str(p['has_logo']):>5}  {p['description_len']:>5}  "
                  f"{len(p['gbp_services']):>3}/{len(p['site_services']):<3}    "
                  f"{p['primary_category']}{'  <- MISMATCH' if not p['score']['category_ok'] else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
