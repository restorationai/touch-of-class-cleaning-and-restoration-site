"""
Rank AI FastAPI service — Phase 3.

Exposes HTTP endpoints so the React app (app.restorationai.io) can trigger
on-demand pipeline runs and read job status.

Authentication: Bearer token (API_SECRET_KEY env var).
Deployed on Railway from the rank-ai monorepo.
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT / "scripts"))  # so we can import the geogrid pipeline

import re
import threading
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from supabase import create_client

from api.runner import create_and_run_job, COMPANY_MAP

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

app = FastAPI(title="Rank AI API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://app.restorationai.io",
        "https://rank.restorationai.io",   # free-audit lead form
        "http://localhost:5173",
        "http://localhost:4321",           # sales page astro dev
        "http://localhost:4322",           # landing-page astro dev
    ],
    allow_origin_regex=r"https://[a-z0-9-]+\.rank-ai-landing-page\.pages\.dev",  # Pages previews
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

API_SECRET = os.environ.get("API_SECRET_KEY", "")
bearer = HTTPBearer()


def auth(creds: HTTPAuthorizationCredentials = Depends(bearer)):
    if not API_SECRET or creds.credentials != API_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")


def sb():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


SYSTEM_LABELS = {
    1: "Keyword Research (S1)",
    2: "Write Post (S2)",
    3: "Onsite Audit (S3)",
    4: "Refresh Recommender (S4)",
    "gbp_face": "GBP Face Fix",
    "gbp_set_cover": "GBP Set Cover Photo",
}

# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class RunJobRequest(BaseModel):
    slug: str
    system: int | str  # 1, 2, 3, 4 — or "gbp_face" (GBP front-face audit + safe
                       # auto-fixes) / "gbp_set_cover" (needs photo_url)
    photo_url: str | None = None  # gbp_set_cover: the photo to set as COVER


class CompleteJobRequest(BaseModel):
    status: str   # "completed" or "failed"
    log: str = ""
    error: str = ""


class GeogridScanRequest(BaseModel):
    company_id: str        # = companies.id (TEXT), the app's join key
    keyword: str
    city_label: str        # must match a label in clients/{slug}/geogrid-cities.json

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok", "service": "rank-ai-api"}


@app.get("/status", dependencies=[Depends(auth)])
def status():
    """Return all active clients and their last-run timestamps from marketing_sites."""
    rows = (
        sb().table("marketing_sites")
        .select("rank_ai_slug,domain,build_status,last_audit_verdict,s1_last_run_at,s2_last_run_at,s3_last_run_at,s4_last_run_at")
        .in_("rank_ai_slug", list(COMPANY_MAP.keys()))
        .execute()
    )
    return {"clients": rows.data}


# ---------------------------------------------------------------------------
# Domains: in-app search + purchase (GoDaddy PAT), phantom-domain pipeline.
# Purchase = availability re-check -> Cloudflare zone created FIRST (so the
# domain is born pointing at our infrastructure) -> GoDaddy buy with CF
# nameservers -> marketing_sites row updated. We absorb the cost (Santino,
# 2026-07-21); premium domains blocked by the price cap.
# ---------------------------------------------------------------------------

GODADDY_API = "https://api.godaddy.com"
DOMAIN_PRICE_CAP_USD = 50.0
REGISTRANT = {
    "nameFirst": os.environ.get("DOMAIN_REG_FIRST", "Santino"),
    "nameLast": os.environ.get("DOMAIN_REG_LAST", "Velci"),
    "email": os.environ.get("DOMAIN_REG_EMAIL", "contact@getrestorationai.com"),
    "phone": os.environ.get("DOMAIN_REG_PHONE", "+1.8053293449"),
    "addressMailing": {
        "address1": os.environ.get("DOMAIN_REG_ADDR", "30 N Gould Street Ste R"),
        "city": os.environ.get("DOMAIN_REG_CITY", "Sheridan"),
        "state": os.environ.get("DOMAIN_REG_STATE", "Wyoming"),
        "postalCode": os.environ.get("DOMAIN_REG_ZIP", "82801"),
        "country": "US",
    },
}


def _gd(method: str, path: str, body=None, timeout=60):
    req = urllib.request.Request(
        GODADDY_API + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": "Bearer " + os.environ["GODADDY_PAT"],
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        return json.loads(raw) if raw else {}


def _cf_zone(domain: str):
    """Create (or fetch) the Cloudflare zone; returns (zone_id, nameservers)."""
    tok = os.environ["CLOUDFLARE_API_TOKEN"]
    acct = os.environ["CLOUDFLARE_ACCOUNT_ID"]
    hdrs = {"Authorization": "Bearer " + tok, "Content-Type": "application/json"}
    req = urllib.request.Request("https://api.cloudflare.com/client/v4/zones",
        method="POST", headers=hdrs,
        data=json.dumps({"name": domain, "account": {"id": acct}, "type": "full"}).encode())
    try:
        d = json.loads(urllib.request.urlopen(req, timeout=60).read())
        z = d["result"]
        return z["id"], z.get("name_servers") or []
    except urllib.error.HTTPError as e:
        err = json.loads(e.read())
        if any(x.get("code") == 1061 for x in err.get("errors", [])):  # already exists
            q = urllib.request.Request(
                "https://api.cloudflare.com/client/v4/zones?name=" + domain, headers=hdrs)
            d = json.loads(urllib.request.urlopen(q, timeout=30).read())
            z = (d.get("result") or [{}])[0]
            return z.get("id"), z.get("name_servers") or []
        raise


class DomainSearchRequest(BaseModel):
    query: str


@app.post("/domains/search", dependencies=[Depends(auth)])
def domains_search(req: DomainSearchRequest):
    """Availability + price for the query (and GoDaddy suggestions)."""
    q = re.sub(r"[^a-z0-9.-]", "", req.query.lower().strip())
    if not q:
        raise HTTPException(status_code=400, detail="Enter a domain to search.")
    candidates = [q if "." in q else q + ".com"]
    try:
        sug = _gd("GET", "/v1/domains/suggest?query={}&limit=8&waitMs=800".format(
            urllib.parse.quote(q)))
        candidates += [s["domain"] for s in sug if s.get("domain")][:8]
    except Exception:
        pass
    seen, out = set(), []
    for dom in candidates:
        if dom in seen:
            continue
        seen.add(dom)
        try:
            a = _gd("GET", "/v1/domains/available?domain=" + urllib.parse.quote(dom))
            out.append({"domain": dom, "available": bool(a.get("available")),
                        "price_usd": round((a.get("price") or 0) / 1e6, 2),
                        "definitive": a.get("definitive", False)})
        except Exception:
            continue
        if len(out) >= 6:
            break
    return {"results": out, "price_cap_usd": DOMAIN_PRICE_CAP_USD}


class DomainPurchaseRequest(BaseModel):
    domain: str
    company_id: str = ""


@app.post("/domains/purchase", dependencies=[Depends(auth)])
def domains_purchase(req: DomainPurchaseRequest):
    """Buy the domain on our GoDaddy account, born on Cloudflare nameservers."""
    dom = re.sub(r"[^a-z0-9.-]", "", req.domain.lower().strip())
    if "." not in dom:
        raise HTTPException(status_code=400, detail="Full domain required, e.g. example.com")
    a = _gd("GET", "/v1/domains/available?domain=" + urllib.parse.quote(dom))
    price = round((a.get("price") or 0) / 1e6, 2)
    if not a.get("available"):
        raise HTTPException(status_code=409, detail="{} is no longer available.".format(dom))
    if price > DOMAIN_PRICE_CAP_USD:
        raise HTTPException(status_code=400,
                            detail="{} costs ${:.2f} — over the ${:.0f} auto-purchase cap. "
                                   "Check with Santino first.".format(dom, price, DOMAIN_PRICE_CAP_USD))
    tld = dom.split(".")[-1]
    ag = _gd("GET", "/v1/domains/agreements?tlds={}&privacy=false".format(tld))
    keys = [x["agreementKey"] for x in ag] or ["DNRA"]

    zone_id, ns = _cf_zone(dom)
    body = {
        "domain": dom,
        "consent": {"agreementKeys": keys, "agreedBy": "45.29.84.10",
                    "agreedAt": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")},
        "period": 1, "privacy": False, "renewAuto": True,
        "contactAdmin": REGISTRANT, "contactBilling": REGISTRANT,
        "contactRegistrant": REGISTRANT, "contactTech": REGISTRANT,
    }
    if ns:
        body["nameServers"] = ns
    try:
        order = _gd("POST", "/v1/domains/purchase", body)
    except urllib.error.HTTPError as e:
        raise HTTPException(status_code=502,
                            detail="GoDaddy rejected the purchase: " + e.read().decode()[:300])

    if req.company_id:
        try:
            sb().table("marketing_sites").update(
                {"domain": dom, "cf_zone_id": zone_id}
            ).eq("company_id", req.company_id).execute()
        except Exception:
            pass
    return {"status": "purchased", "domain": dom, "price_usd": price,
            "order_id": order.get("orderId"), "cf_zone_id": zone_id,
            "nameservers": ns}


# ---------------------------------------------------------------------------
# Site builds: brief helpers + push-button build (Isaac/RestorationXpress is
# the pilot — everything through the app, nothing manual).
# ---------------------------------------------------------------------------

class DomainAttachRequest(BaseModel):
    company_id: str
    domain: str


@app.post("/domains/attach", dependencies=[Depends(auth)])
def domains_attach(req: DomainAttachRequest):
    """Client already OWNS a domain (Isaac case): record it on the site row
    and pre-create the Cloudflare zone so go-live is just a nameserver
    change at their registrar. No purchase, no DNS changes on their side."""
    dom = re.sub(r"[^a-z0-9.-]", "", req.domain.lower().strip()
                 .replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0])
    if "." not in dom or len(dom) < 4:
        raise HTTPException(status_code=400, detail="Enter a full domain, e.g. example.com")
    zone_id, ns = None, []
    try:
        zone_id, ns = _cf_zone(dom)
    except Exception:
        pass  # zone can be created at cutover; recording the domain still works
    upd = {"domain": dom}
    if zone_id:
        upd["cf_zone_id"] = zone_id
    r = sb().table("marketing_sites").update(upd).eq("company_id", req.company_id).execute()
    if not r.data:
        raise HTTPException(status_code=400, detail="No site record for this company (not bootstrapped yet).")
    return {"status": "attached", "domain": dom, "cf_zone_id": zone_id,
            "nameservers": ns,
            "note": "Existing site untouched; cutover happens at go-live."}


class SiteBriefColorsRequest(BaseModel):
    company_id: str


@app.post("/site-brief/extract-colors", dependencies=[Depends(auth)])
def site_brief_extract_colors(req: SiteBriefColorsRequest):
    """Fetch the client's CURRENT website and return its dominant brand
    colors ("use the same green as my site" without hex-code archaeology)."""
    rows = sb().table("companies").select("website").eq("id", req.company_id).execute()
    site = (rows.data[0].get("website") if rows.data else "") or ""
    # Hosts MUST be lowercased: "Www.RestorationXpress.com" stored verbatim
    # breaks TLS SNI on some servers (found live 2026-07-22).
    host = site.strip().lower().replace("https://", "").replace("http://", "").split("/")[0]
    if not host:
        raise HTTPException(status_code=400, detail="No website on file for this company.")
    ua = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
          "Accept": "text/html,application/xhtml+xml"}

    def fetch(u, t=20):
        try:
            r = urllib.request.Request(u, headers=ua)
            return urllib.request.urlopen(r, timeout=t).read().decode("utf-8", "ignore")
        except Exception:
            return ""

    bare = host[4:] if host.startswith("www.") else host
    html_text, site = "", ""
    for cand in ("https://" + host, "https://www." + bare, "https://" + bare,
                 "http://" + bare):
        html_text = fetch(cand)
        if html_text:
            site = cand
            break
    if not html_text:
        raise HTTPException(status_code=502,
                            detail="Couldn't fetch {} — their site may block bots; set colors manually.".format(bare))
    # Brand colors rarely sit in the HTML itself — WordPress and friends
    # compile the owner's chosen palette into dynamic/child/custom/uploads
    # stylesheets, while generic theme CSS carries decorative palettes that
    # are pure noise. Weight sources accordingly (found live: the greens of
    # restorationxpress.com were 109x in enfold_child.css, 1x in the HTML).
    sheets = []
    for tag in re.findall(r"<link[^>]+>", html_text):
        m = re.search(r'href=["\']([^"\']+)', tag)
        if "stylesheet" in tag and m:
            u = urllib.parse.urljoin(site + "/", m.group(1))
            if bare in urllib.parse.urlparse(u).netloc:
                sheets.append(u)

    def weight(u):
        return 5 if re.search(r"dynamic|custom|child|uploads", u, re.I) else 1

    sheets.sort(key=lambda u: -weight(u))
    corpora = [(html_text, 3)] + [(fetch(u, t=8), weight(u)) for u in sheets[:10]]

    counts: dict = {}
    for text, w in corpora:
        for m in re.findall(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b", text):
            h = m.lower()
            if len(h) == 3:
                h = "".join(c * 2 for c in h)
            counts[h] = counts.get(h, 0) + w
        for m in re.findall(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", text):
            r0, g0, b0 = (min(int(x), 255) for x in m)
            k = "{:02x}{:02x}{:02x}".format(r0, g0, b0)
            counts[k] = counts.get(k, 0) + w

    def rgb(h):
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    def is_gray(h):
        r0, g0, b0 = rgb(h)
        if max(r0, g0, b0) - min(r0, g0, b0) < 26:
            return True                       # gray family
        return (r0 + g0 + b0) > 705 or (r0 + g0 + b0) < 45  # near white/black

    # Brand colors are frequent AND saturated — score by both, then merge
    # near-duplicate shades so three greens don't crowd out the row.
    def score(h, n):
        r0, g0, b0 = rgb(h)
        mx, mn = max(r0, g0, b0), min(r0, g0, b0)
        sat = (mx - mn) / mx if mx else 0
        return n * (0.5 + sat)

    ranked = sorted(((h, n) for h, n in counts.items() if not is_gray(h)),
                    key=lambda x: -score(*x))
    picked = []
    for h, n in ranked:
        r0, g0, b0 = rgb(h)
        if any(abs(r0 - pr) + abs(g0 - pg) + abs(b0 - pb) < 90
               for pr, pg, pb in (rgb(x[0]) for x in picked)):
            continue
        picked.append((h, n))
        if len(picked) >= 6:
            break
    return {"website": site,
            "colors": [{"hex": "#" + h, "count": n} for h, n in picked]}


@app.post("/site-brief/extract-colors-from-logo", dependencies=[Depends(auth)])
def site_brief_extract_colors_from_logo(req: SiteBriefColorsRequest):
    """Brand colors from the client's UPLOADED LOGO — for clients with no
    website (Go Green: domain purchased, logo uploaded, no site to scrape).
    Reads the newest branding/{cid}/brand/ image and returns dominant
    saturated colors, same shape as extract-colors."""
    import io as _io

    from PIL import Image as _Img

    sb_url = os.environ["SUPABASE_URL"].rstrip("/")
    sb_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    hdrs = {"apikey": sb_key, "Authorization": "Bearer " + sb_key,
            "Content-Type": "application/json"}
    lst = urllib.request.Request(
        sb_url + "/storage/v1/object/list/branding", method="POST",
        data=json.dumps({"prefix": req.company_id + "/brand", "limit": 100,
                         "sortBy": {"column": "created_at", "order": "desc"}}).encode(),
        headers=hdrs)
    try:
        objs = json.loads(urllib.request.urlopen(lst, timeout=30).read())
    except Exception:
        objs = []
    imgs = [o for o in objs if o.get("id") and any(
        str(o.get("name", "")).lower().endswith(x)
        for x in (".png", ".jpg", ".jpeg", ".webp", ".svg"))]
    if not imgs:
        raise HTTPException(status_code=404,
                            detail="No logo on file yet — have them send it via the hub (Send Us Files, Logo).")
    key = req.company_id + "/brand/" + imgs[0]["name"]
    raw = urllib.request.urlopen(urllib.request.Request(
        sb_url + "/storage/v1/object/branding/" + urllib.parse.quote(key),
        headers=hdrs), timeout=60).read()
    from collections import Counter
    if imgs[0]["name"].lower().endswith(".svg"):
        # SVGs (Kyle/Crew3r 2026-07-25) carry their palette as literal color
        # tokens — PIL can't rasterize them, but we don't need it to. Pull
        # every hex/rgb() token, weight by occurrence, reuse the same
        # gray-filter + dedupe pipeline below.
        import re as _re
        txt = raw.decode("utf-8", "ignore")
        tokens = []
        for h in _re.findall(r"#([0-9a-fA-F]{6})\b", txt):
            tokens.append(tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)))
        for h in _re.findall(r"#([0-9a-fA-F]{3})\b", txt):
            tokens.append(tuple(int(c * 2, 16) for c in h))
        for m in _re.findall(r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", txt):
            tokens.append(tuple(min(int(v), 255) for v in m))
        if not tokens:
            raise HTTPException(status_code=422,
                                detail="The SVG logo has no literal colors (image-embedded or CSS-classed) — set colors manually.")
        counts = Counter(tokens)
    else:
        img = _Img.open(_io.BytesIO(raw)).convert("RGB").resize((96, 96))
        counts = Counter(img.getdata())

    def is_gray(c):
        r0, g0, b0 = c
        return (max(c) - min(c) < 26) or sum(c) > 705 or sum(c) < 45

    def score(c, n):
        mx, mn = max(c), min(c)
        return n * (0.5 + ((mx - mn) / mx if mx else 0))

    ranked = sorted(((c, n) for c, n in counts.items() if not is_gray(c)),
                    key=lambda x: -score(*x))
    picked = []
    for c, n in ranked:
        if any(sum(abs(a - b) for a, b in zip(c, pc)) < 90 for pc, _ in picked):
            continue
        picked.append((c, n))
        if len(picked) >= 6:
            break
    return {"source": imgs[0]["name"],
            "colors": [{"hex": "#{:02x}{:02x}{:02x}".format(*c), "count": n}
                       for c, n in picked]}


class SiteBuildRequest(BaseModel):
    company_id: str


@app.post("/site-build", dependencies=[Depends(auth)])
def site_build(req: SiteBuildRequest):
    """Queue a full site build (plan -> scaffold -> render -> staging preview)
    on GitHub Actions. Validates the brief; long work never runs on this
    server (a redeploy would kill it)."""
    site_rows = sb().table("marketing_sites").select(
        "rank_ai_slug,domain,build_status").eq("company_id", req.company_id).execute()
    if not site_rows.data:
        raise HTTPException(status_code=400,
                            detail="Client isn't bootstrapped yet — no site record. The 2-hour automation will create it, or run the bootstrap.")
    site = site_rows.data[0]
    slug, domain = site.get("rank_ai_slug"), site.get("domain") or ""
    if not slug:
        raise HTTPException(status_code=400, detail="No Rank AI slug on the site record.")
    if domain.endswith(".invalid") or not domain:
        raise HTTPException(status_code=400,
                            detail="No real domain yet — buy or set one in the Domain Purchase card first.")
    if site.get("build_status") in ("queued", "building"):
        raise HTTPException(status_code=409, detail="A build is already {}.".format(site["build_status"]))

    co = sb().table("companies").select("integration_settings").eq("id", req.company_id).execute()
    ints = (co.data[0].get("integration_settings") if co.data else None) or {}
    brand = ints.get("brand") or {}
    brief = ints.get("site_brief") or {}
    missing = []
    if not brand.get("primary_color"):
        missing.append("primary brand color")
    if not (brief.get("cities") or []):
        missing.append("at least one build city")
    if missing:
        raise HTTPException(status_code=400,
                            detail="Brief incomplete: add " + " and ".join(missing) + ", then save.")

    gh_pat = os.environ.get("GH_PAT", "")
    if not gh_pat:
        raise HTTPException(status_code=500, detail="GH_PAT not configured on the API service.")
    disp = urllib.request.Request(
        "https://api.github.com/repos/restorationai/Rank-AI-Pipeline/actions/workflows/site-build.yml/dispatches",
        method="POST",
        data=json.dumps({"ref": "main", "inputs": {"slug": slug}}).encode(),
        headers={"Authorization": "Bearer " + gh_pat,
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "rank-ai-api"})
    try:
        urllib.request.urlopen(disp, timeout=30)
    except urllib.error.HTTPError as e:
        raise HTTPException(status_code=502,
                            detail="GitHub dispatch failed: " + e.read().decode()[:200])
    sb().table("marketing_sites").update({"build_status": "queued"}).eq(
        "company_id", req.company_id).execute()
    return {"status": "queued", "slug": slug,
            "note": "Plan + render + staging preview takes 1-3 hours; "
                    "watch build_status and the ops email for the preview link."}


@app.post("/jobs/run", dependencies=[Depends(auth)])
def run_job(req: RunJobRequest):
    """Trigger a system run for a client. Returns job_id immediately; runs in background."""
    if req.slug not in COMPANY_MAP:
        raise HTTPException(status_code=404, detail=f"Unknown slug: {req.slug}")
    if req.system not in (1, 2, 3, 4, "gbp_face", "gbp_set_cover"):
        raise HTTPException(status_code=400,
                            detail="system must be 1, 2, 3, 4, 'gbp_face', or 'gbp_set_cover'")
    if req.system == "gbp_set_cover" and not (req.photo_url or "").startswith("https://"):
        raise HTTPException(status_code=400, detail="gbp_set_cover requires an https photo_url")

    job_id = create_and_run_job(req.slug, req.system, photo_url=req.photo_url)

    return {
        "job_id":  job_id,
        "slug":    req.slug,
        "system":  req.system,
        "label":   SYSTEM_LABELS[req.system],
        "status":  "queued",
        "note":    "Poll GET /jobs/{job_id} for status updates.",
    }


@app.get("/jobs/{job_id}", dependencies=[Depends(auth)])
def get_job(job_id: str):
    """Get the current status of a job."""
    rows = (
        sb().table("marketing_jobs")
        .select("id,type,status,params,result,error,queued_at,started_at,completed_at")
        .eq("id", job_id)
        .execute()
    )
    if not rows.data:
        raise HTTPException(status_code=404, detail="Job not found")
    return rows.data[0]


@app.post("/jobs/{job_id}/complete", dependencies=[Depends(auth)])
def complete_job(job_id: str, req: CompleteJobRequest):
    """
    Callback endpoint for GitHub Actions to mark agent-driven jobs (S1, S3) done.
    The on-demand.yml workflow calls this after claude -p finishes.
    """
    rows = sb().table("marketing_jobs").select("params").eq("id", job_id).execute()
    if not rows.data:
        raise HTTPException(status_code=404, detail="Job not found")

    slug = rows.data[0]["params"].get("slug")
    update = {
        "status":       req.status,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "log":          req.log[-8000:] if req.log else None,
        "error":        req.error or None,
    }
    sb().table("marketing_jobs").update(update).eq("id", job_id).execute()

    # Sync Supabase after agent-driven job completes
    if req.status == "completed" and slug:
        import subprocess
        subprocess.Popen(
            ["python3", str(ROOT / "scripts" / "supabase_sync.py"), "--slug", slug],
            cwd=str(ROOT),
        )

    return {"ok": True}


# ---------------------------------------------------------------------------
# Geo-grid: on-demand local-map-rankings scan (one keyword + one city)
# ---------------------------------------------------------------------------

# Reverse of COMPANY_MAP — the app sends company_id; the pipeline keys off slug.
SLUG_BY_COMPANY = {cid: slug for slug, cid in COMPANY_MAP.items()}


def _resolve_city(slug: str, city_label: str) -> dict:
    """Find {label,lat,lng} for a city_label in the client's geogrid-cities.json."""
    f = ROOT / "clients" / slug / "geogrid-cities.json"
    if not f.exists():
        raise HTTPException(status_code=404, detail=f"No geogrid-cities.json for {slug}")
    for c in json.loads(f.read_text()):
        if c.get("label") == city_label:
            return c
    raise HTTPException(status_code=404, detail=f"city_label '{city_label}' not configured for {slug}")


@app.post("/geogrid/scan", dependencies=[Depends(auth)])
def geogrid_scan(req: GeogridScanRequest):
    """Run ONE keyword×city geo-grid scan, store it, return the new scan row.

    Server-enforced rate limit: at most 1 scan per (company_id, keyword, city_label)
    per UTC day — re-scanning the same cell same-day returns 429 with the existing
    row (the dashboard should just show that one). Scans are ~10-60s; this blocks
    until the row + points + PNG are written. The app refreshes the card from the
    returned row (or via realtime subscribe to marketing_geogrid_scans).
    """
    slug = SLUG_BY_COMPANY.get(req.company_id)
    if not slug:
        raise HTTPException(status_code=404, detail=f"Unknown company_id: {req.company_id}")
    city = _resolve_city(slug, req.city_label)

    client = sb()
    # Rate limit: any scan for this cell since UTC midnight?
    today = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00+00:00")
    existing = (
        client.table("marketing_geogrid_scans")
        .select("id,avg_rank,pct_in_top3,found_points,total_points,image_url,scanned_at")
        .eq("company_id", req.company_id).eq("keyword", req.keyword)
        .eq("city_label", req.city_label).gte("scanned_at", today)
        .order("scanned_at", desc=True).limit(1).execute()
    )
    if existing.data:
        raise HTTPException(
            status_code=429,
            detail={"message": "Already scanned today (1/keyword/city/day).",
                    "scan": existing.data[0]},
        )

    # Lazy import — keeps PIL/requests out of the cold-start path for other routes.
    from geogrid_store import scan_and_store
    row = scan_and_store(client, slug, req.keyword, city)
    return {
        "id":           row["id"],
        "company_id":   req.company_id,
        "keyword":      req.keyword,
        "city_label":   req.city_label,
        "avg_rank":     row.get("avg_rank"),
        "pct_in_top3":  row.get("pct_in_top3"),
        "found_points": row.get("found_points"),
        "total_points": row.get("total_points"),
        "image_url":    row.get("image_url"),
        "cost_usd":     row.get("cost_usd"),
        "scanned_at":   row.get("scanned_at"),
    }


# ---------------------------------------------------------------------------
# Free-audit lead magnet (rank.restorationai.io) — PUBLIC endpoints.
# Jobs are tracked in marketing_jobs (type='lead_audit', company_id NULL);
# rate limits are derived from the same table so they survive restarts.
# ---------------------------------------------------------------------------

LEAD_AUDIT_DAILY_CAP = 10       # global per UTC day
LEAD_AUDIT_IP_CAP = 3           # per IP per UTC day
LEAD_AUDIT_DOMAIN_CAP = 2       # per target domain per UTC day
LEAD_LOOKUP_DAILY_CAP = 60      # global business-name lookups per UTC day
LEAD_LOOKUP_IP_CAP = 15         # per IP per UTC day

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$")


class LeadAuditRequest(BaseModel):
    # Path A (classic): website + contact info.
    # Path B (stepper): business_name + place_id/cid (+ optional domain) + contact info.
    website: str = ""
    name: str = ""
    email: str
    phone: str
    business_name: str = ""
    place_id: str = ""
    cid: str = ""
    domain: str = ""
    # Sales-funnel mode (e.g. OpDigital application → GHL webhook): the lead is
    # NOT emailed; the report + teaser image land on their GHL contact and the
    # team gets an ops ping. Requires the shared secret.
    source: str = ""
    secret: str = ""


def _lead_norm_domain(url: str) -> str:
    d = re.sub(r"^https?://", "", (url or "").strip().lower()).split("/")[0].split("?")[0]
    return d.replace("www.", "")


def _lead_count_today(client, col_json: str = None, value: str = None) -> int:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00+00:00")
    q = (client.table("marketing_jobs").select("id", count="exact")
         .eq("type", "lead_audit").gte("queued_at", today))
    if col_json:
        q = q.eq(f"params->>{col_json}", value)
    return q.execute().count or 0


# --- DataForSEO business lookup (name -> candidate GBP listings) ------------

DFS_LISTINGS = "https://api.dataforseo.com/v3/business_data/business_listings/search/live"
DFS_MAPS_LIVE = "https://api.dataforseo.com/v3/serp/google/maps/live/advanced"


def _dfs_post(url: str, body: list, timeout: int = 60) -> list:
    """POST one DataForSEO live task; return result items (or [])."""
    import base64
    import urllib.request
    import geogrid_scan as gs  # scripts/ on sys.path; load_dfs_creds handles env/~/.claude.json
    u, p = gs.load_dfs_creds()
    auth = base64.b64encode("{}:{}".format(u, p).encode()).decode()
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": "Basic " + auth, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read())
    task = (d.get("tasks") or [{}])[0]
    if task.get("status_code") and int(task["status_code"]) >= 40000:
        raise RuntimeError(task.get("status_message") or "DataForSEO task error")
    result = (task.get("result") or [{}])[0] or {}
    return result.get("items") or []


def _listing_row(it: dict) -> dict:
    rd = it.get("rating") or {}
    dom = (it.get("domain") or "").replace("www.", "") or None
    return {
        "title": it.get("title"),
        "address": it.get("address"),
        "rating": rd.get("value"),
        "reviews": rd.get("votes_count"),
        "place_id": it.get("place_id"),
        "cid": str(it.get("cid")) if it.get("cid") is not None else None,
        "domain": dom,
        "url": it.get("url"),
    }


def _name_score(a: str, b: str) -> float:
    import difflib
    a, b = (a or "").lower().strip(), (b or "").lower().strip()
    if not a or not b:
        return 0.0
    if a in b or b in a:
        return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def lookup_business(q: str, limit: int = 3) -> list:
    """US-wide GBP candidate search: business_listings first, Maps SERP fallback."""
    items = []
    try:
        items = _dfs_post(DFS_LISTINGS, [{"title": q[:200], "limit": 20}])
    except Exception:
        items = []
    rows = [it for it in items if isinstance(it, dict) and it.get("title")]
    if not rows:
        try:
            items = _dfs_post(DFS_MAPS_LIVE, [{"keyword": q[:200], "location_code": 2840,
                                               "language_code": "en", "device": "desktop"}])
            rows = [it for it in items if isinstance(it, dict) and it.get("title")]
        except Exception:
            rows = []
    scored = sorted(
        (( _name_score(q, it.get("title")), (it.get("rating") or {}).get("votes_count") or 0, i, it)
         for i, it in enumerate(rows)),
        key=lambda t: (-t[0], -t[1], t[2]))
    out, seen = [], set()
    for score, _votes, _i, it in scored:
        if score < 0.35:
            continue
        key = it.get("place_id") or it.get("cid") or it.get("title")
        if key in seen:
            continue
        seen.add(key)
        out.append(_listing_row(it))
        if len(out) >= limit:
            break
    return out


def _listing_by_id(place_id: str = "", cid: str = ""):
    """Fetch one listing by place_id/cid (used to resolve a missing domain)."""
    filters = None
    if place_id:
        filters = ["place_id", "=", place_id]
    elif cid:
        try:
            filters = ["cid", "=", int(cid)]
        except ValueError:
            filters = ["cid", "=", cid]
    if not filters:
        return None
    try:
        items = _dfs_post(DFS_LISTINGS, [{"filters": [filters], "limit": 1}])
        for it in items:
            if isinstance(it, dict) and it.get("title"):
                return _listing_row(it)
    except Exception:
        pass
    return None


@app.get("/lead-audit/business-lookup")
def lead_business_lookup(q: str, request: Request):
    """Public: up to 3 GBP candidates for a business name (stepper step 1)."""
    q = (q or "").strip()
    if len(q) < 3 or len(q) > 120:
        raise HTTPException(status_code=400, detail="Please enter your business name (3-120 characters).")

    ip = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "") or "").split(",")[0].strip()
    client = sb()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00+00:00")

    def _lookup_count(ip_val=None):
        query = (client.table("marketing_jobs").select("id", count="exact")
                 .eq("type", "lead_lookup").gte("queued_at", today))
        if ip_val:
            query = query.eq("params->>ip", ip_val)
        return query.execute().count or 0

    if _lookup_count() >= LEAD_LOOKUP_DAILY_CAP:
        raise HTTPException(status_code=429, detail="We've hit today's lookup limit — please try again tomorrow.")
    if ip and _lookup_count(ip) >= LEAD_LOOKUP_IP_CAP:
        raise HTTPException(status_code=429, detail="Too many searches from this connection today.")

    matches = lookup_business(q)
    client.table("marketing_jobs").insert({
        "type": "lead_lookup", "status": "completed",
        "params": {"q": q, "ip": ip, "source": "rank.restorationai.io"},
        "result": {"count": len(matches)},
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }).execute()
    return {"query": q, "matches": matches}


def _run_lead_audit_job(job_id: str, req: "LeadAuditRequest"):
    client = sb()
    client.table("marketing_jobs").update(
        {"status": "running", "started_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", job_id).execute()
    try:
        import lead_audit  # scripts/ is on sys.path (see header)
        sales = bool(req.source)
        res = lead_audit.run_audit(req.website or req.domain, req.name, req.email, req.phone,
                                   audit_id=job_id.replace("-", "")[:12],
                                   business_name=req.business_name or None,
                                   place_id=req.place_id or None,
                                   cid=req.cid or None,
                                   email_mode="internal" if sales else "all",
                                   sales_mode=sales)
        client.table("marketing_jobs").update({
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "result": res,
        }).eq("id", job_id).execute()
    except Exception as e:  # noqa: BLE001 — job must always terminate with a status
        client.table("marketing_jobs").update({
            "status": "failed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "error": str(e)[:500],
        }).eq("id", job_id).execute()
        # A silently failed lead audit = a hot lead with no report (Chris
        # Morrow sat unnoticed ~20h, 2026-07-23). Always tell the team.
        # lead_audit raises SiteDownError ONLY when the lead's site is
        # genuinely unreachable (NXDOMAIN / nothing on 443+80) — checked by
        # name so a failed `import lead_audit` can't break this handler.
        _notify_lead_audit_failure(job_id, req, str(e)[:300],
                                   site_down=e.__class__.__name__ == "SiteDownError")


def _notify_lead_audit_failure(job_id: str, req: "LeadAuditRequest", error: str,
                               site_down: bool = False):
    """Best-effort team email — the job status row remains the record.

    Funnel leads also get ONE mutually-exclusive GHL tag so the nurture
    workflow can branch (ungated merges sent 'graded .' + invalid media to
    Isaac Gomez, 2026-08-01):
      - "website down"  ← site_down=True: the site is GENUINELY unreachable
        (lead_audit.SiteDownError: NXDOMAIN / nothing on 443+80). Safe for
        the workflow's "your site isn't even up" message.
      - "audit failed"  ← everything else (crawler blocked but site up,
        parse errors, our-side timeouts). The workflow must send NOTHING
        lead-facing on this tag — silence beats falsely telling a lead
        with a working site that it is down.
    """
    if req.source:
        try:
            import lead_audit  # scripts/ is on sys.path
            contact_id = None
            for q in (req.email, req.phone):
                if not q:
                    continue
                res = lead_audit._ghl("GET", "/contacts/", params={"query": q})
                if res.get("contacts"):
                    contact_id = res["contacts"][0]["id"]
                    break
            if contact_id:
                tag = "website down" if site_down else "audit failed"
                lead_audit._ghl("POST", "/contacts/{}/tags".format(contact_id),
                                params={}, body={"tags": [tag]})
        except Exception:
            pass  # tagging is best-effort; the email below still alerts the team
    try:
        sg = os.environ.get("SENDGRID_API_KEY", "")
        if not sg:
            return
        body = json.dumps({
            "personalizations": [{"to": [{"email": "contact@restorationai.io"}]}],
            "from": {"email": "contact@restorationai.io"},
            "subject": "[Rank AI] Lead audit FAILED: {} ({})".format(
                req.name or req.business_name or "unknown", req.email),
            "content": [{"type": "text/plain", "value":
                "Lead audit job {} failed.\n\nLead: {} <{}> {}\n"
                "Website: {}\nBusiness: {}\nError: {}\n"
                "Classification: {}\n\n"
                "The lead got NO report — follow up or re-run manually.".format(
                    job_id, req.name, req.email, req.phone,
                    req.website or req.domain, req.business_name, error,
                    "WEBSITE DOWN (lead tagged 'website down')" if site_down
                    else "audit failed (site may be fine — lead tagged 'audit failed')")}]})
        urllib.request.urlopen(urllib.request.Request(
            "https://api.sendgrid.com/v3/mail/send", method="POST",
            data=body.encode(),
            headers={"Authorization": "Bearer " + sg,
                     "Content-Type": "application/json"}), timeout=20)
    except Exception:
        pass  # notification is best-effort


def _recover_orphaned_lead_audits():
    """Boot-time crash recovery (Santino 2026-07-30): a Railway deploy kills
    in-flight audit threads, leaving jobs stuck 'queued'/'running' forever —
    a hot lead with no report and no alert (Andrew Gomez, 2026-07-28). On
    startup: retry each orphan once; on the second orphaning, mark failed and
    send the existing failure email so a human follows up."""
    import time as _t
    _t.sleep(10)  # let the app finish booting before burning CPU on audits
    try:
        client = sb()
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
        rows = (client.table("marketing_jobs").select("id, params, status")
                .eq("type", "lead_audit").in_("status", ["queued", "running"])
                .gte("created_at", cutoff).execute().data) or []
    except Exception as e:  # noqa: BLE001
        print("[lead-audit recovery] scan failed:", str(e)[:150])
        return
    for row in rows:
        p = row.get("params") or {}
        attempts = int(p.get("attempts") or 0)
        req = LeadAuditRequest(
            website=p.get("domain") or "", domain=p.get("domain") or "",
            name=p.get("name") or "", email=p.get("email") or "",
            phone=p.get("phone") or "",
            business_name=p.get("business_name") or "",
            place_id=p.get("place_id") or "", cid=p.get("cid") or "",
            source="funnel-recovery" if p.get("sales") else "", secret="")
        if attempts >= 1:
            print(f"[lead-audit recovery] {row['id']}: died twice — marking failed")
            try:
                client.table("marketing_jobs").update({
                    "status": "failed",
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "error": "orphaned by deploy twice — needs manual re-run",
                }).eq("id", row["id"]).execute()
            except Exception:
                pass
            _notify_lead_audit_failure(row["id"], req,
                                       "audit thread killed by deploys twice")
            continue
        print(f"[lead-audit recovery] {row['id']}: re-running (attempt 2)")
        try:
            p["attempts"] = attempts + 1
            client.table("marketing_jobs").update(
                {"params": p, "status": "queued"}).eq("id", row["id"]).execute()
        except Exception:
            pass
        threading.Thread(target=_run_lead_audit_job,
                         args=(row["id"], req), daemon=True).start()


@app.on_event("startup")
def _lead_audit_recovery_on_boot():
    threading.Thread(target=_recover_orphaned_lead_audits, daemon=True).start()


@app.post("/lead-audit")
def create_lead_audit(req: LeadAuditRequest, request: Request):
    """Public: queue a free visibility audit.

    Accepts either {website, ...} (classic) or {business_name, place_id/cid,
    domain?, ...} (stepper). When the stepper gives no domain, we resolve it
    from the chosen listing's website field via DataForSEO."""
    domain = _lead_norm_domain(req.website or req.domain)
    if not re.match(r"^[a-z0-9.-]+\.[a-z]{2,}$", domain) and (req.place_id or req.cid):
        listing = _listing_by_id(req.place_id, req.cid)
        if listing and (listing.get("domain") or listing.get("url")):
            domain = _lead_norm_domain(listing.get("domain") or listing.get("url"))
            req.domain = domain
    if not re.match(r"^[a-z0-9.-]+\.[a-z]{2,}$", domain):
        raise HTTPException(status_code=400,
                            detail="We couldn't find a website for that business — please enter your website, e.g. yourcompany.com")
    req.domain = req.domain or domain
    if not EMAIL_RE.match(req.email or ""):
        raise HTTPException(status_code=400, detail="Please enter a valid email address.")
    if len(re.sub(r"\D", "", req.phone or "")) < 10:
        raise HTTPException(status_code=400, detail="Please enter a valid phone number.")

    # Sales-funnel calls must present the shared secret (set in Railway env);
    # a bad secret is treated as a normal public request (source stripped).
    if req.source:
        expected = os.environ.get("LEAD_AUDIT_FUNNEL_SECRET", "")
        if not (expected and req.secret == expected):
            req.source = ""

    ip = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "") or "").split(",")[0].strip()
    client = sb()
    trusted = bool(req.source)  # secret already validated above
    if not trusted and _lead_count_today(client) >= LEAD_AUDIT_DAILY_CAP:
        raise HTTPException(status_code=429, detail="We've hit today's audit limit — please try again tomorrow, or email contact@restorationai.io.")
    if not trusted and ip and _lead_count_today(client, "ip", ip) >= LEAD_AUDIT_IP_CAP:
        raise HTTPException(status_code=429, detail="Too many audits from this connection today.")
    if _lead_count_today(client, "domain", domain) >= LEAD_AUDIT_DOMAIN_CAP:
        raise HTTPException(status_code=429, detail="We've already run audits for this website today — check your inbox.")

    row = client.table("marketing_jobs").insert({
        "type": "lead_audit", "status": "queued",  # triggered_by is a UUID col — leave null
        "params": {"domain": domain, "name": req.name, "email": req.email,
                   "phone": req.phone, "ip": ip, "source": "rank.restorationai.io",
                   "business_name": req.business_name or None,
                   "place_id": req.place_id or None, "cid": req.cid or None,
                   # sales flag + attempt counter drive boot-time crash recovery
                   "sales": bool(req.source), "attempts": 0},
    }).execute()
    job_id = row.data[0]["id"]

    threading.Thread(target=_run_lead_audit_job, args=(job_id, req), daemon=True).start()
    return {"audit_id": job_id, "status": "queued",
            "note": "Your audit is running — it takes about 5 minutes. We'll email the report to you. "
                    "You can also poll GET /lead-audit/{audit_id}."}


class KickoffPrepRequest(BaseModel):
    contact_id: str
    secret: str = ""
    appointment_time: str = ""   # optional human phrase, e.g. "tomorrow at 5"


class BootstrapNowRequest(BaseModel):
    company_id: str = ""
    secret: str


@app.post("/bootstrap-now")
def bootstrap_now(req: BootstrapNowRequest):
    """Fired by the signup-alert edge fn the moment an account is created
    (Santino 2026-07-26: tabs full by FIRST login). Dispatches the bootstrap
    workflow, whose bootstrap-only pass now runs the whole day-one blitz:
    client files + geo-grid baseline + AI-search baseline + GBP/ads first
    syncs + optimizer. The 2-hourly schedule stays as the backstop."""
    expected = (os.environ.get("KICKOFF_PREP_SECRET")
                or os.environ.get("LEAD_AUDIT_FUNNEL_SECRET", ""))
    if not (expected and req.secret == expected):
        raise HTTPException(status_code=403, detail="bad secret")
    gh_pat = os.environ.get("GH_PAT", "")
    if not gh_pat:
        raise HTTPException(status_code=500, detail="GH_PAT not configured")
    disp = urllib.request.Request(
        "https://api.github.com/repos/restorationai/Rank-AI-Pipeline/actions/"
        "workflows/bootstrap-new-clients.yml/dispatches",
        method="POST",
        data=json.dumps({"ref": "main"}).encode(),
        headers={"Authorization": "Bearer " + gh_pat,
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "rank-ai-api"})
    try:
        urllib.request.urlopen(disp, timeout=30)
    except urllib.error.HTTPError as e:
        raise HTTPException(status_code=502,
                            detail=f"workflow dispatch failed: {e.code}")
    return {"status": "dispatched"}


class GbpFirstSyncRequest(BaseModel):
    company_id: str
    secret: str


# ---------------------------------------------------------------------------
# Call tracking (Santino 2026-07-28): per-client Twilio numbers for GBP +
# website. Straight-through connect (NO whisper to the business — standing
# rule). Recording everywhere EXCEPT it requires the short caller disclosure
# in all-party consent states; the disclosure plays only there.
# ---------------------------------------------------------------------------

ALL_PARTY_STATES = {"CA", "FL", "WA", "PA", "IL", "MA", "CT", "MD", "MT",
                    "NH", "NV", "OR", "DE"}


def _state_abbrev(state: str) -> str:
    s = (state or "").strip().upper()
    if len(s) == 2:
        return s
    names = {"CALIFORNIA": "CA", "FLORIDA": "FL", "WASHINGTON": "WA",
             "PENNSYLVANIA": "PA", "ILLINOIS": "IL", "MASSACHUSETTS": "MA",
             "CONNECTICUT": "CT", "MARYLAND": "MD", "MONTANA": "MT",
             "NEW HAMPSHIRE": "NH", "NEVADA": "NV", "OREGON": "OR",
             "DELAWARE": "DE"}
    return names.get(s, s[:2])


@app.post("/call-tracking/twiml/{company_id}/{source}")
async def call_tracking_twiml(company_id: str, source: str, request: Request):
    """Twilio Voice webhook: answer, (disclose where required), record, and
    dial straight through to the client's real line."""
    form = await request.form()
    call_sid = str(form.get("CallSid") or "")
    from_num = str(form.get("From") or "")
    to_num = str(form.get("To") or "")
    co = sb().table("companies").select("phone,state,integration_settings") \
        .eq("id", company_id).limit(1).execute().data
    if not co:
        raise HTTPException(status_code=404, detail="unknown company")
    real = re.sub(r"[^\d+]", "", co[0].get("phone") or "")
    if real and not real.startswith("+"):
        real = "+1" + real.lstrip("1")
    if not real:
        raise HTTPException(status_code=500, detail="company has no phone")
    disclose = _state_abbrev(co[0].get("state") or "") in ALL_PARTY_STATES
    try:
        if call_sid:
            sb().table("marketing_tracked_calls").upsert({
                "company_id": company_id, "source": source,
                "tracking_number": to_num, "from_number": from_num,
                "to_number": real, "call_sid": call_sid, "status": "ringing",
            }, on_conflict="call_sid").execute()
    except Exception as e:  # noqa: BLE001 — logging must never break the call
        print("[call-tracking] log failed:", str(e)[:120])
    base = "https://rank-ai-api-production.up.railway.app"
    say = ('<Say voice="Polly.Joanna">This call may be recorded.</Say>'
           if disclose else "")
    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?><Response>' + say +
        f'<Dial record="record-from-answer-dual" answerOnBridge="true"'
        f' recordingStatusCallback="{base}/call-tracking/recording/{company_id}"'
        f' action="{base}/call-tracking/status/{company_id}" method="POST">'
        f'{real}</Dial></Response>')
    from fastapi.responses import Response as _Resp
    return _Resp(content=twiml, media_type="application/xml")


@app.post("/call-tracking/status/{company_id}")
async def call_tracking_status(company_id: str, request: Request):
    form = await request.form()
    call_sid = str(form.get("CallSid") or "")
    if call_sid:
        try:
            sb().table("marketing_tracked_calls").update({
                "status": str(form.get("DialCallStatus") or form.get("CallStatus") or ""),
                "duration_seconds": int(form.get("DialCallDuration") or 0),
            }).eq("call_sid", call_sid).execute()
        except Exception as e:  # noqa: BLE001
            print("[call-tracking] status update failed:", str(e)[:120])
    from fastapi.responses import Response as _Resp
    return _Resp(content='<?xml version="1.0" encoding="UTF-8"?><Response/>',
                 media_type="application/xml")


@app.post("/call-tracking/recording/{company_id}")
async def call_tracking_recording(company_id: str, request: Request):
    form = await request.form()
    call_sid = str(form.get("CallSid") or "")
    url = str(form.get("RecordingUrl") or "")
    if call_sid and url:
        try:
            sb().table("marketing_tracked_calls").update(
                {"recording_url": url + ".mp3"}).eq("call_sid", call_sid).execute()
        except Exception as e:  # noqa: BLE001
            print("[call-tracking] recording update failed:", str(e)[:120])
    return {"ok": True}


@app.post("/case-study/{slug}")
async def case_study_intake(slug: str, request: Request):
    """Client-submitted case studies (Kyle/Crew 2026-07-28: they send a
    transcript or write-up to a webhook and it becomes a case-study blog
    post). Accepts JSON ({title?, text|transcript|body, ...}) or raw text.
    Queues a marketing_content_items row for the content engine's
    case-study lane + drops an ops note so it shows in Ops Attention.
    Auth: ?secret= PER-CLIENT derived token (safe to hand to the client's
    Zapier/GHL — grants nothing beyond this client's case-study intake).
    HMAC(CONNECT_LINK_SIGNING_SECRET, 'case-study:'+slug)[:20], no table
    needed. The master ops secret also works for internal use."""
    import hashlib as _hl
    import hmac as _hm
    master = (os.environ.get("KICKOFF_PREP_SECRET")
              or os.environ.get("LEAD_AUDIT_FUNNEL_SECRET", ""))
    sign = os.environ.get("CONNECT_LINK_SIGNING_SECRET", "")
    derived = (_hm.new(sign.encode(), f"case-study:{slug}".encode(),
                       _hl.sha256).hexdigest()[:20] if sign else None)
    got = request.query_params.get("secret", "")
    if not (got and (got == master or (derived and got == derived))):
        raise HTTPException(status_code=403, detail="bad secret")
    raw = await request.body()
    title, text = None, ""
    try:
        payload = json.loads(raw.decode("utf-8", "replace"))
        if isinstance(payload, dict):
            title = (payload.get("title") or "").strip() or None
            text = str(payload.get("text") or payload.get("transcript")
                       or payload.get("body") or payload.get("message") or "")
            if not text:
                text = json.dumps(payload)[:20000]
        else:
            text = str(payload)
    except (json.JSONDecodeError, UnicodeDecodeError):
        text = raw.decode("utf-8", "replace")
    text = text.strip()[:50000]
    if len(text) < 40:
        raise HTTPException(status_code=400, detail="send the case study text/transcript in the body")
    croot = Path(__file__).resolve().parent.parent / "clients"
    cmap = croot / "company_map.json"
    cid = None
    if cmap.exists():
        cid = json.loads(cmap.read_text()).get(slug)
    if not cid:
        cj = croot / f"{slug}.json"
        if cj.exists():
            cid = json.loads(cj.read_text()).get("company_id")
    if not cid:
        raise HTTPException(status_code=404, detail="unknown client slug")
    from datetime import datetime as _dt, timezone as _tz
    now = _dt.now(_tz.utc).isoformat()
    item_title = title or f"Case study submitted {now[:10]}"
    client_ = sb()
    client_.table("marketing_content_items").insert({
        "company_id": cid, "type": "blog", "status": "queued",
        "title": item_title, "intent": "case_study", "priority": 1,
        "queued_at": now,
        "notes": ("CLIENT-SUBMITTED CASE STUDY (webhook). Write this as the "
                  "case-study format: real job story, what happened, what the "
                  "crew did, outcome. Use ONLY facts from the raw material in "
                  "script_text; never invent addresses, names, or dollar "
                  "amounts. Anonymize the homeowner unless explicitly named "
                  "with permission."),
        "script_text": text,
    }).execute()
    client_.table("marketing_ops_notes").insert({
        "company_id": cid,
        "body": f"Client sent a case study via webhook: \"{item_title}\" — "
                "queued for the content engine (review before it publishes).",
        "author": "webhook",
    }).execute()
    return {"status": "queued", "slug": slug, "title": item_title, "chars": len(text)}


@app.post("/gbp-first-sync")
def gbp_first_sync(req: GbpFirstSyncRequest):
    """Fired by the Google-connect edge functions the moment a client's GBP
    connects (Santino 2026-07-26: 'as soon as someone connects, run it').
    Spawns gbp.sync in a thread so the Locations tab populates in minutes —
    profile row + v4 reviews + GBP photo import. The nightly ops-sync
    first-sync pass stays as the backstop (connect-before-bootstrap, redeploy
    killing the thread, etc.)."""
    expected = (os.environ.get("KICKOFF_PREP_SECRET")
                or os.environ.get("LEAD_AUDIT_FUNNEL_SECRET", ""))
    if not (expected and req.secret == expected):
        raise HTTPException(status_code=403, detail="bad secret")
    croot = Path(__file__).resolve().parent.parent / "clients"
    slug = None
    cmap = croot / "company_map.json"
    if cmap.exists():
        slug = next((s for s, cid in json.loads(cmap.read_text()).items()
                     if cid == req.company_id), None)
    if not slug:
        for f in croot.glob("*.json"):
            if f.name == "company_map.json":
                continue
            try:
                if json.loads(f.read_text()).get("company_id") == req.company_id:
                    slug = f.stem
                    break
            except (json.JSONDecodeError, OSError):
                continue
    if not slug:
        return {"status": "skipped",
                "note": "not bootstrapped yet — nightly ops sync will run the first sync"}
    rows = sb().table("marketing_gbp_profiles").select("company_id") \
        .eq("company_id", req.company_id).execute()
    if rows.data:
        return {"status": "skipped", "note": "already synced"}

    def _run(s=slug):
        # Full day-one blitz (Santino 2026-07-26: Kyle's follow-up call hit
        # empty tabs): sync -> AI optimizer suggestions -> face-score audit.
        # Each step best-effort; nightly ops-sync backstops all of them.
        try:
            import gbp  # scripts/ is on sys.path
            print("[gbp-first-sync]", gbp.sync(s))
        except Exception as e:  # noqa: BLE001 — backstopped nightly
            print("[gbp-first-sync] sync failed:", s, str(e)[:200])
            return
        try:
            import gbp
            r = gbp.optimize(s)
            print("[gbp-first-sync] optimize:", s, r.get("summary") or r.get("error"))
        except Exception as e:  # noqa: BLE001
            print("[gbp-first-sync] optimize failed:", s, str(e)[:200])
        try:
            import subprocess
            import sys as _sys
            root = Path(__file__).resolve().parent.parent
            r = subprocess.run([_sys.executable, str(root / "scripts" / "gbp_face_audit.py"),
                                "--slug", s, "--apply"],
                               capture_output=True, text=True, timeout=900)
            tail = (r.stdout or r.stderr or "").strip().splitlines()
            print("[gbp-first-sync] face-audit:", s, tail[-1][:120] if tail else "no output")
        except Exception as e:  # noqa: BLE001
            print("[gbp-first-sync] face-audit failed:", s, str(e)[:200])
        # Photos tab must populate on day one too (RX 2026-07-28: connected
        # with 40 GBP photos, app said "no job photos yet")
        try:
            r = gbp.import_gbp_media(s)
            print("[gbp-first-sync] media-import:", r[:120])
        except Exception as e:  # noqa: BLE001
            print("[gbp-first-sync] media-import failed:", s, str(e)[:200])

    threading.Thread(target=_run, daemon=True).start()
    return {"status": "queued", "slug": slug}


# ---------------------------------------------------------------------------
# Concierge instant inbound (Monica)
# ---------------------------------------------------------------------------
# Per-contact locks: GHL retries webhooks and clients double-text; one
# in-flight run per contact in this process keeps the thread readable and
# stops duplicate replies (cross-process dedupe is the concierge's
# handled-ids ledger in ops_kv).
_CONCIERGE_LOCKS: dict = {}
_CONCIERGE_LOCKS_GUARD = threading.Lock()


def _concierge_lock(contact_id: str) -> threading.Lock:
    with _CONCIERGE_LOCKS_GUARD:
        return _CONCIERGE_LOCKS.setdefault(contact_id, threading.Lock())


def _extract_contact_id(body: dict) -> str:
    """Liberal parse: GHL workflow webhooks vary by trigger and custom-data
    mapping — accept contact_id / contactId at the top level, nested under
    contact / customData, or flattened as 'contact.id'."""
    for key in ("contact_id", "contactId"):
        v = body.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    for parent in ("contact", "customData", "custom_data"):
        sub = body.get(parent)
        if isinstance(sub, dict):
            for key in ("contact_id", "contactId", "id"):
                v = sub.get(key)
                if isinstance(v, str) and v.strip():
                    return v.strip()
    for k, v in body.items():
        if (isinstance(v, str) and v.strip() and
                k.lower().replace(".", "_").replace("-", "_")
                in ("contact_id", "ghl_contact_id")):
            return v.strip()
    return ""


@app.post("/concierge-inbound")
async def concierge_inbound(request: Request):
    """GHL webhook: a client just replied (SMS/email) — instant Monica.

    Replaces waiting on the 5-min poll + hourly compose: classifies + acts
    on the new message(s) for this ONE contact, then runs an immediate
    compose so a warranted reply goes out now. All concierge gates apply
    (business hours, canary allowlist, human-defer, PAUSE switch; the
    client-waiting bypass covers the cooldown since the client just spoke).

    Auth: shared secret in the x-concierge-secret header, ?secret= query
    param, or a "secret" field in the JSON body — checked against
    CONCIERGE_WEBHOOK_SECRET (falls back to LEAD_AUDIT_FUNNEL_SECRET).
    Payload: liberal — any JSON carrying the GHL contact id (contact_id /
    contactId / contact.id / customData.contact_id / ?contact_id= query).
    Unknown contacts return "ignored": Monica only ever engages contacts
    she is already tracking, so the GHL workflow can fire on EVERY inbound
    message with no tag filter."""
    expected = (os.environ.get("CONCIERGE_WEBHOOK_SECRET")
                or os.environ.get("LEAD_AUDIT_FUNNEL_SECRET", ""))
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}
    secret = (request.headers.get("x-concierge-secret")
              or request.query_params.get("secret")
              or str(body.get("secret") or ""))
    if not (expected and secret == expected):
        raise HTTPException(status_code=403, detail="bad secret")
    contact_id = (_extract_contact_id(body)
                  or request.query_params.get("contact_id", "").strip())
    if not contact_id or len(contact_id) < 8:
        raise HTTPException(status_code=400,
                            detail="contact_id not found in payload")

    def _run():
        lock = _concierge_lock(contact_id)
        with lock:
            try:
                import client_concierge  # scripts/ is on sys.path (see header)
                client_concierge.load_env()
                out = client_concierge.webhook_inbound(contact_id, do_send=True)
                print(f"[concierge-inbound] {contact_id}: {out}")
            except Exception as e:  # noqa: BLE001 — webhook thread must not die loudly
                print("[concierge-inbound] failed:", str(e)[:300])

    threading.Thread(target=_run, daemon=True).start()
    return {"status": "queued", "contact_id": contact_id,
            "note": "Instant inbound started; any reply obeys business "
                    "hours, the canary allowlist and cadence gates."}


@app.post("/kickoff-prep")
def kickoff_prep_endpoint(req: KickoffPrepRequest):
    """Fired by the GHL 'kickoff booked' workflow webhook. Spawns a thread
    that polls Fathom for the just-finished sales demo with this contact,
    extracts what Santino asked them to have ready, and sends ONE friendly
    SMS + email (deduped via the kickoff-prep-sent contact tag)."""
    expected = (os.environ.get("KICKOFF_PREP_SECRET")
                or os.environ.get("LEAD_AUDIT_FUNNEL_SECRET", ""))
    if not (expected and req.secret == expected):
        raise HTTPException(status_code=403, detail="bad secret")
    if not req.contact_id or len(req.contact_id) < 8:
        raise HTTPException(status_code=400, detail="contact_id required")
    import kickoff_prep  # scripts/ is on sys.path (see header)
    threading.Thread(target=kickoff_prep.run, args=(req.contact_id,),
                     kwargs={"appt_time": req.appointment_time},
                     daemon=True).start()
    return {"status": "queued",
            "note": "Polling Fathom for the demo transcript; the reminder "
                    "sends once it lands. Dedupe tag: kickoff-prep-sent."}


@app.post("/kickoff-recap")
def kickoff_recap_endpoint(req: KickoffPrepRequest):
    """Fired by the GHL workflow when a KICKOFF appointment is marked
    completed. Polls Fathom for the recording and sends ONE recap of what was
    agreed (dedupe tag kickoff-recap-sent). GHL sometimes auto-completes
    appointments that never happened — if no recording matches, nothing is
    sent (the no-show rule, Santino 2026-07-25)."""
    expected = (os.environ.get("KICKOFF_PREP_SECRET")
                or os.environ.get("LEAD_AUDIT_FUNNEL_SECRET", ""))
    if not (expected and req.secret == expected):
        raise HTTPException(status_code=403, detail="bad secret")
    if not req.contact_id or len(req.contact_id) < 8:
        raise HTTPException(status_code=400, detail="contact_id required")
    import kickoff_recap  # scripts/ is on sys.path (see header)
    threading.Thread(target=kickoff_recap.run, args=(req.contact_id,),
                     daemon=True).start()
    return {"status": "queued",
            "note": "Polling Fathom for the kickoff recording; the recap sends "
                    "once it lands. No recording = no message (no-show rule). "
                    "Dedupe tag: kickoff-recap-sent."}


@app.get("/lead-audit/{audit_id}")
def get_lead_audit(audit_id: str):
    """Public: audit status. Returns only status + report URL (no contact info)."""
    rows = (sb().table("marketing_jobs")
            .select("id,type,status,result,queued_at,completed_at")
            .eq("id", audit_id).eq("type", "lead_audit").execute())
    if not rows.data:
        raise HTTPException(status_code=404, detail="Audit not found")
    j = rows.data[0]
    result = j.get("result") or {}
    return {"audit_id": j["id"], "status": j["status"],
            "report_url": result.get("report_url"),
            "grade": result.get("grade"),
            "queued_at": j["queued_at"], "completed_at": j["completed_at"]}


@app.get("/jobs", dependencies=[Depends(auth)])
def list_jobs(slug: str = None, limit: int = 20):
    """List recent jobs, optionally filtered by client slug."""
    query = (
        sb().table("marketing_jobs")
        .select("id,company_id,type,status,params,queued_at,completed_at,error")
        .order("queued_at", desc=True)
        .limit(limit)
    )
    if slug and slug in COMPANY_MAP:
        query = query.eq("company_id", COMPANY_MAP[slug])

    rows = query.execute()
    return {"jobs": rows.data}
