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
import time
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

from fastapi import FastAPI, HTTPException, Depends, Request, BackgroundTasks
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
    "cutover": "One-Click Domain Cutover",
    "cutover_provision": "Cutover Provision (zone + email records)",
    "site_push_main": "Push Site to Production",
    "ads_account_create": "Create Google Ads Account",
}

# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class RunJobRequest(BaseModel):
    slug: str
    system: int | str  # 1, 2, 3, 4 — or "gbp_face" (GBP front-face audit + safe
                       # auto-fixes) / "gbp_set_cover" (needs photo_url) /
                       # "cutover" / "ads_account_create" (LSA board button)
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


@app.get("/report/{company_id}/{fname}")
def client_report(company_id: str, fname: str):
    """Serve a client's monthly results page (client_report.py writes them to
    the client-reports bucket). Supabase's public storage endpoint refuses to
    render HTML (text/plain + nosniff, XSS policy), so this is the report's
    real front door. Auth model = the unguessable token baked into the
    filename, same as the crew-hub upload links."""
    if not re.fullmatch(r"CO-\d{6,16}", company_id) \
            or not re.fullmatch(r"20\d{2}-\d{2}-[0-9a-f]{8,16}\.html", fname):
        raise HTTPException(status_code=404, detail="Not found")
    sb = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    import requests as _rq
    r = _rq.get(f"{sb}/storage/v1/object/client-reports/{company_id}/{fname}",
                headers={"apikey": key, "Authorization": f"Bearer {key}"},
                timeout=20)
    if not r.ok:
        raise HTTPException(status_code=404, detail="Not found")
    from fastapi.responses import HTMLResponse
    return HTMLResponse(r.text)


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
    if req.system not in (1, 2, 3, 4, "gbp_face", "gbp_set_cover", "cutover",
                          "cutover_provision", "site_push_main", "ads_account_create"):
        raise HTTPException(status_code=400,
                            detail="system must be 1, 2, 3, 4, 'gbp_face', 'gbp_set_cover', "
                                   "'cutover', 'cutover_provision', or 'ads_account_create'")
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


@app.get("/jobs-active", dependencies=[Depends(auth)])
def get_active_job(slug: str):
    """Latest queued/running launch-class job for a slug (2026-09-18: a page
    reload mid-push lost the 'Pushing' state — the panel resumes polling
    from this on mount instead of going blind)."""
    rows = (sb().table("marketing_jobs")
            .select("id,type,status,queued_at")
            .in_("type", ["site_push_main", "cutover", "cutover_provision"])
            .in_("status", ["queued", "running"])
            .order("queued_at", desc=True).limit(10).execute()).data or []
    for r in rows:
        # params carries the slug; cheap post-filter (few rows ever active)
        full = (sb().table("marketing_jobs").select("params")
                .eq("id", r["id"]).limit(1).execute()).data
        if full and str((full[0].get("params") or {}).get("slug")) == slug:
            return {"job": r}
    return {"job": None}


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
# One-click cutover: phase readiness for the app's launch panel. Read-only
# and fast enough to run inline (DoH + a few Cloudflare GETs + the llms.txt
# probe) — the mutating counterpart is POST /jobs/run {system: "cutover"},
# which follows gbp_set_cover's subprocess-job pattern in api/runner.py.
# ---------------------------------------------------------------------------

@app.get("/cutover/status", dependencies=[Depends(auth)])
def cutover_status(slug: str):
    if slug not in COMPANY_MAP:
        raise HTTPException(status_code=404, detail=f"Unknown slug: {slug}")
    import subprocess
    try:
        result = subprocess.run(
            ["python3", str(ROOT / "scripts" / "cutover_execute.py"),
             "status", "--slug", slug],
            cwd=str(ROOT), capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="cutover status timed out")
    try:
        return json.loads(result.stdout)
    except ValueError:
        raise HTTPException(
            status_code=502,
            detail="cutover status failed: "
                   + (result.stderr or result.stdout or "no output")[-300:])


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
    # Known GHL contact (staff-booked appointments hand us the id outright).
    # When set, delivery/tagging address this contact directly instead of
    # re-searching by email/phone — which silently missed contacts with no
    # phone and could hit the wrong duplicate.
    ghl_contact_id: str = ""


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


# Job ids with a live audit thread in THIS process. The periodic stale sweep
# skips these so a slow-but-alive audit is never double-run.
_LEAD_AUDIT_LIVE: set = set()
LEAD_AUDIT_STALE_MIN = 60        # queued/running this long with no live thread = orphan
LEAD_AUDIT_SWEEP_SEC = 900       # periodic stale sweep interval


def _run_lead_audit_job(job_id: str, req: "LeadAuditRequest"):
    _LEAD_AUDIT_LIVE.add(job_id)
    try:
        _run_lead_audit_job_inner(job_id, req)
    finally:
        _LEAD_AUDIT_LIVE.discard(job_id)


def _run_lead_audit_job_inner(job_id: str, req: "LeadAuditRequest"):
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
                                   sales_mode=sales,
                                   ghl_contact_id=req.ghl_contact_id or None)
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
    card_url = None
    if req.source:
        try:
            import lead_audit  # scripts/ is on sys.path
            # Staff-booked appointments hand us the contact id outright; only
            # fall back to searching when we were not given one.
            contact_id = req.ghl_contact_id or None
            for q in (() if contact_id else (req.email, req.phone)):
                if not q:
                    continue
                res = lead_audit._ghl("GET", "/contacts/", params={"query": q})
                if res.get("contacts"):
                    contact_id = res["contacts"][0]["id"]
                    break
            # Invisibility card: the failed branch's SMS merges the SAME
            # audit_teaser_image_url field the success path fills, so a failed
            # run still needs valid, personalized media (empty merges = broken
            # MMS). The card sells the finding itself: a mock search-results
            # frame with the lead's business marked "Not found". Name comes
            # from the form (business/company beats person), then the GHL
            # contact's companyName. No name at all = no card (never generic).
            card_name = (req.business_name or "").strip()
            person = (req.name or "").strip()
            if contact_id and not card_name:
                try:
                    c = (lead_audit._ghl("GET", "/contacts/{}".format(contact_id),
                                         params={}) or {}).get("contact") or {}
                    card_name = (c.get("companyName") or "").strip()
                    person = person or " ".join(
                        p for p in (c.get("firstName"), c.get("lastName")) if p).strip()
                except Exception:
                    pass
            card_name = card_name or person
            if card_name:
                try:
                    png = lead_audit.render_invisibility_card(card_name)
                    key = "{}/{}/invisible.png".format(
                        lead_audit.PREFIX, job_id.replace("-", "")[:12])
                    if lead_audit.r2_put(lead_audit.BUCKET, key, png, "image/png"):
                        card_url = "{}/{}".format(lead_audit.PUBLIC_BASE, key)
                except Exception:
                    card_url = None
            if contact_id:
                tag = "website down" if site_down else "audit failed"
                lead_audit._ghl("POST", "/contacts/{}/tags".format(contact_id),
                                params={}, body={"tags": [tag]})
                # The GHL workflow branches its messaging on the audit_status
                # custom field — write 'failed' so the field is never left
                # empty on ANY outcome (empty merges sent Virgil Santa an SMS
                # with blank fields, 2026-08-14). The invisibility card rides
                # along in audit_teaser_image_url so the failed-branch SMS
                # always has valid media.
                try:
                    ids = lead_audit._ghl_custom_field_ids()
                    cf = []
                    if ids.get("audit_status"):
                        cf.append({"id": ids["audit_status"],
                                   "field_value": "failed"})
                    if card_url and ids.get("audit_teaser_image_url"):
                        cf.append({"id": ids["audit_teaser_image_url"],
                                   "field_value": card_url})
                    if cf:
                        lead_audit._ghl(
                            "PUT", "/contacts/{}".format(contact_id), params={},
                            body={"customFields": cf})
                except Exception:
                    pass
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
                "The lead got NO report — follow up or re-run manually.{}".format(
                    job_id, req.name, req.email, req.phone,
                    req.website or req.domain, req.business_name, error,
                    "WEBSITE DOWN (lead tagged 'website down')" if site_down
                    else "audit failed (site may be fine — lead tagged 'audit failed')",
                    "\nInvisibility card (on the contact's teaser field): " + card_url
                    if card_url else "")}]})
        urllib.request.urlopen(urllib.request.Request(
            "https://api.sendgrid.com/v3/mail/send", method="POST",
            data=body.encode(),
            headers={"Authorization": "Bearer " + sg,
                     "Content-Type": "application/json"}), timeout=20)
    except Exception:
        pass  # notification is best-effort


def _recover_orphaned_lead_audits(stale_minutes: int = 0):
    """Crash recovery (Santino 2026-07-30): a Railway deploy kills in-flight
    audit threads, leaving jobs stuck 'queued'/'running' forever — a hot lead
    with no report and no alert (Andrew Gomez, 2026-07-28). Retry each orphan
    once (params.attempts); on the second orphaning, mark failed and send the
    existing failure email so a human follows up.

    stale_minutes=0 (boot): no thread survives a restart, so every open job
    is an orphan. stale_minutes>0 (periodic sweep): only jobs older than that
    with no live thread in this process.

    2026-09-29 (Silvano Conejo sat 'running' 7 days): this scan filtered on
    marketing_jobs.created_at, a column that does not exist, so it 400'd on
    every boot and recovered nothing. The table's timestamp is queued_at."""
    try:
        client = sb()
        now = datetime.now(timezone.utc)
        cutoff = (now - timedelta(hours=48)).isoformat()
        rows = (client.table("marketing_jobs")
                .select("id, params, status, queued_at, started_at")
                .eq("type", "lead_audit").in_("status", ["queued", "running"])
                .gte("queued_at", cutoff).execute().data) or []
    except Exception as e:  # noqa: BLE001
        print("[lead-audit recovery] scan failed:", str(e)[:150])
        return
    for row in rows:
        if row["id"] in _LEAD_AUDIT_LIVE:
            continue
        if stale_minutes:
            ts = row.get("started_at") or row.get("queued_at")
            try:
                age = now - datetime.fromisoformat(ts)
            except Exception:  # noqa: BLE001
                continue
            if age < timedelta(minutes=stale_minutes):
                continue
        p = row.get("params") or {}
        attempts = int(p.get("attempts") or 0)
        req = LeadAuditRequest(
            website=p.get("domain") or "", domain=p.get("domain") or "",
            name=p.get("name") or "", email=p.get("email") or "",
            phone=p.get("phone") or "",
            business_name=p.get("business_name") or "",
            place_id=p.get("place_id") or "", cid=p.get("cid") or "",
            source="funnel-recovery" if p.get("sales") else "", secret="",
            ghl_contact_id=p.get("ghl_contact_id") or "")
        if attempts >= 1:
            print(f"[lead-audit recovery] {row['id']}: orphaned twice, marking failed")
            try:
                client.table("marketing_jobs").update({
                    "status": "failed",
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "error": "orphaned twice (deploy restart or stale >{}m); needs manual re-run".format(LEAD_AUDIT_STALE_MIN),
                }).eq("id", row["id"]).execute()
            except Exception:
                pass
            _notify_lead_audit_failure(row["id"], req,
                                       "audit thread orphaned twice (deploy restart or stale)")
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


def _lead_audit_recovery_loop():
    """Boot sweep, then a stale-job sweep every LEAD_AUDIT_SWEEP_SEC (catches
    threads that die without a restart, and any boot sweep that failed)."""
    time.sleep(10)  # let the app finish booting before burning CPU on audits
    try:
        _recover_orphaned_lead_audits()
    except Exception as e:  # noqa: BLE001
        print("[lead-audit recovery] boot sweep error:", str(e)[:150])
    while True:
        time.sleep(LEAD_AUDIT_SWEEP_SEC)
        try:
            _recover_orphaned_lead_audits(stale_minutes=LEAD_AUDIT_STALE_MIN)
        except Exception as e:  # noqa: BLE001 — the loop must never die
            print("[lead-audit recovery] sweep error:", str(e)[:150])


@app.on_event("startup")
def _lead_audit_recovery_on_boot():
    threading.Thread(target=_lead_audit_recovery_loop, daemon=True).start()


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
                   "ghl_contact_id": req.ghl_contact_id or None,
                   # sales flag + attempt counter drive boot-time crash recovery
                   "sales": bool(req.source), "attempts": 0},
    }).execute()
    job_id = row.data[0]["id"]

    threading.Thread(target=_run_lead_audit_job, args=(job_id, req), daemon=True).start()
    return {"audit_id": job_id, "status": "queued",
            "note": "Your audit is running — it takes about 5 minutes. We'll email the report to you. "
                    "You can also poll GET /lead-audit/{audit_id}."}


# --- Staff-booked appointment → same audit, straight from GHL ---------------
#
# /lead-audit is fired by the OpDigital application FORM, where the lead types
# their own website. When a team member books a reignite/sales call in GHL
# there is no form: the contact already exists, so the webhook hands us the
# contact and we read the website off the record. Hernany Da Silva
# (2026-08-04) proved the gap — his appointment fired the nurture SMS with
# empty merge fields ("It came back graded .") because no audit ever ran.

GHL_APPT_MAX_PER_DOMAIN_DAY = 3   # secret-gated path; the dedupe below is the real guard
GHL_APPT_RECENT_DAYS = 30         # a fresh audit already on the contact = don't burn another


def _mf(v) -> str:
    """Clean one GHL merge-field value. An unrendered merge field arrives
    literally ('{{contact.website}}') — that is emptiness, not a website."""
    s = str(v if v is not None else "").strip()
    if not s or "{{" in s or s.lower() in ("null", "none", "undefined", "false"):
        return ""
    return s


# Subtrees of a GHL payload that carry SOMEBODY ELSE's identity — the
# calendar's email, the booking user's name. Flattening them would hand the
# audit sales@… instead of the lead's address, so they are never read.
GHL_FOREIGN_SUBTREES = {"calendar", "user", "assigneduser", "assignedto", "assigned_to",
                        "workflow", "location", "account", "agency", "createdby"}


def _ghl_scalars(node, out=None, depth: int = 0) -> dict:
    """Flatten a GHL webhook body to {lowercased_leaf_key: value}.

    GHL posts a big nested payload (contact / appointment / calendar /
    customData, plus a customFields list) — take the fields we need and ignore
    the rest, so a raw payload works with no hand-mapping. Scalars at each
    level are claimed before recursing and the first writer of a key wins, so
    callers seed the contact subtree first to give it top priority."""
    if out is None:
        out = {}
    if depth > 4 or not isinstance(node, dict):
        return out
    for k, v in node.items():
        if isinstance(v, (str, int, float)) and not isinstance(v, bool):
            key = str(k).strip().lower().split(".")[-1]
            if key and key not in out and _mf(v):
                out[key] = _mf(v)
    for k, v in node.items():
        if str(k).strip().lower() in GHL_FOREIGN_SUBTREES:
            continue
        if isinstance(v, dict):
            _ghl_scalars(v, out, depth + 1)
        elif isinstance(v, list):
            for item in v:
                if not isinstance(item, dict):
                    continue
                # customFields entries: {key|fieldKey|name|id, value|field_value}
                fk = str(item.get("key") or item.get("fieldKey") or item.get("name")
                         or "").strip().lower().split(".")[-1]
                val = item.get("value", item.get("field_value", item.get("fieldValue")))
                if fk and fk not in out and isinstance(val, (str, int, float)) \
                        and not isinstance(val, bool) and _mf(val):
                    out[fk] = _mf(val)
                # Deliberately NOT recursing into list items: a customFields
                # entry's own keys ('id', 'value', 'name') would otherwise
                # claim generic slots and a field label could become the
                # lead's name.
    return out


def _first(d: dict, *keys) -> str:
    for k in keys:
        v = _mf(d.get(k))
        if v:
            return v
    return ""


def _host_resolves(host: str) -> bool:
    import socket
    for h in (host, "www." + host):
        try:
            socket.getaddrinfo(h, None)
            return True
        except Exception:
            continue
    return False


@app.post("/lead-audit/ghl-appointment")
async def lead_audit_ghl_appointment(request: Request):
    """GHL 'Send Webhook' action on an appointment booking → the same audit.

    Tolerant by design: accepts the raw GHL payload (or a hand-written JSON
    body of merge fields) and picks out contact id / website / name / email /
    phone, ignoring everything else. The secret may ride in the body, the
    X-Rank-AI-Secret header, or ?secret=. Always answers 200 with a status so
    GHL never retry-storms a booking."""
    raw = await request.body()
    payload = {}
    try:
        payload = json.loads(raw.decode() or "{}")
    except Exception:
        try:  # some GHL setups post form-encoded
            payload = dict(urllib.parse.parse_qsl(raw.decode()))
        except Exception:
            payload = {}
    if not isinstance(payload, dict):
        payload = {}
    # Seed from the contact subtree first so the LEAD's email/phone/website win
    # over anything with the same key elsewhere in the payload.
    flat = {}
    if isinstance(payload.get("contact"), dict):
        _ghl_scalars(payload["contact"], flat)
    _ghl_scalars(payload, flat)

    expected = os.environ.get("LEAD_AUDIT_FUNNEL_SECRET", "")
    supplied = (_mf(request.headers.get("X-Rank-AI-Secret"))
                or _mf(request.query_params.get("secret"))
                or _first(flat, "secret", "rank_ai_secret"))
    if not (expected and supplied == expected):
        raise HTTPException(status_code=403, detail="bad secret")

    contact_id = (_first(flat, "ghl_contact_id", "contact_id", "contactid")
                  or _mf((payload.get("contact") or {}).get("id")
                         if isinstance(payload.get("contact"), dict) else ""))
    website = _first(flat, "website", "business_website", "website_info", "domain")
    email = _first(flat, "email")
    phone = _first(flat, "phone")
    name = (_first(flat, "full_name", "fullname", "name")
            or " ".join(x for x in (_first(flat, "first_name", "firstname"),
                                    _first(flat, "last_name", "lastname")) if x))
    business_name = _first(flat, "business_name", "companyname", "company_name", "company")
    source = _first(flat, "source") or "ghl-appointment"

    # The contact record is the authority — merge fields can arrive blank.
    contact = {}
    if contact_id:
        try:
            import lead_audit
            got = lead_audit._ghl("GET", "/contacts/{}".format(contact_id)) or {}
            contact = got.get("contact") or got or {}
        except Exception as e:  # noqa: BLE001
            print("[ghl-appointment] contact fetch failed:", str(e)[:150])
    if contact:
        cf = {}
        try:
            import lead_audit
            ids = lead_audit._ghl_custom_field_ids()
            by_id = {v: k for k, v in ids.items() if v}
            for f in (contact.get("customFields") or []):
                key = by_id.get(f.get("id")) or str(f.get("id") or "")
                cf[key] = _mf(f.get("value", f.get("field_value", f.get("fieldValue"))))
        except Exception:
            cf = {}
        # The live record outranks the payload: merge fields go stale, arrive
        # unrendered, or (calendar/user subtrees) describe the wrong person.
        website = (_mf(contact.get("website")) or cf.get("business_website", "")
                   or cf.get("website_info", "") or website)
        email = _mf(contact.get("email")) or email
        phone = _mf(contact.get("phone")) or phone
        name = " ".join(x for x in (_mf(contact.get("firstName")),
                                    _mf(contact.get("lastName"))) if x) or name
        business_name = _mf(contact.get("companyName")) or business_name
        # Already audited recently? Don't burn a second one on a re-booking.
        force = _first(flat, "force").lower() in ("1", "true", "yes")
        if not force and cf.get("audit_grade") and cf.get("audit_teaser_image_url"):
            dom_have = _lead_norm_domain(website)
            try:
                since = (datetime.now(timezone.utc)
                         - timedelta(days=GHL_APPT_RECENT_DAYS)).isoformat()
                prior = (sb().table("marketing_jobs").select("id", count="exact")
                         .eq("type", "lead_audit").eq("status", "completed")
                         .eq("params->>domain", dom_have)
                         .gte("queued_at", since).execute().count or 0)
            except Exception:
                prior = 0
            if prior:
                return {"status": "already_audited", "contact_id": contact_id,
                        "grade": cf.get("audit_grade"),
                        "report_url": cf.get("audit_report_url"),
                        "teaser_url": cf.get("audit_teaser_image_url"),
                        "note": "fields already populated and a completed audit for {} is "
                                "on file within {}d — send force:true to re-run".format(
                                    dom_have, GHL_APPT_RECENT_DAYS)}

    # Website resolution: contact field first, then the Google listing (Path B).
    # A typo'd website is the same problem as a missing one — Monique Curchy's
    # contact carried 'ww.rapidreliefrestoration.net' (2026-08-05), so a
    # non-resolving host also falls through to the listing lookup.
    domain = _lead_norm_domain(website)
    valid = bool(re.match(r"^[a-z0-9.-]+\.[a-z]{2,}$", domain)) and _host_resolves(domain)
    place_id = cid_val = ""
    if not valid and business_name:
        try:
            for cand in lookup_business(business_name, limit=3):
                cand_dom = _lead_norm_domain(cand.get("domain") or cand.get("url") or "")
                if re.match(r"^[a-z0-9.-]+\.[a-z]{2,}$", cand_dom) and _host_resolves(cand_dom):
                    domain, valid = cand_dom, True
                    place_id = cand.get("place_id") or ""
                    cid_val = cand.get("cid") or ""
                    break
        except Exception as e:  # noqa: BLE001
            print("[ghl-appointment] business lookup failed:", str(e)[:150])

    req = LeadAuditRequest(
        website=domain, domain=domain, name=name, email=email or "", phone=phone or "",
        business_name=business_name, place_id=place_id, cid=str(cid_val or ""),
        source=source, secret=expected, ghl_contact_id=contact_id)

    if not valid:
        # Never fail silently: tag the contact so the nurture workflow's guard
        # holds the SMS, and email the team so a human can supply the website.
        try:
            if contact_id:
                import lead_audit
                lead_audit._ghl("POST", "/contacts/{}/tags".format(contact_id), params={},
                                body={"tags": ["audit failed", "audit needs website"]})
        except Exception:
            pass
        _notify_lead_audit_failure(
            "ghl-appointment (no job queued)", req,
            "no usable website on the GHL contact ({}) and no Google listing match for '{}' "
            "— add the website to the contact and re-fire".format(
                website or "empty", business_name or "unknown"))
        return {"status": "no_website", "contact_id": contact_id,
                "website_seen": website, "business_name": business_name,
                "note": "contact tagged 'audit needs website' + team emailed"}

    client = sb()
    if _lead_count_today(client, "domain", domain) >= GHL_APPT_MAX_PER_DOMAIN_DAY:
        return {"status": "rate_limited", "domain": domain,
                "note": "already ran {} audits for this domain today".format(
                    GHL_APPT_MAX_PER_DOMAIN_DAY)}

    row = client.table("marketing_jobs").insert({
        "type": "lead_audit", "status": "queued",
        "params": {"domain": domain, "name": name, "email": email, "phone": phone,
                   "ip": "", "source": source, "business_name": business_name or None,
                   "place_id": place_id or None, "cid": str(cid_val) or None,
                   "ghl_contact_id": contact_id or None,
                   "sales": True, "attempts": 0},
    }).execute()
    job_id = row.data[0]["id"]
    threading.Thread(target=_run_lead_audit_job, args=(job_id, req), daemon=True).start()
    return {"status": "queued", "audit_id": job_id, "domain": domain,
            "contact_id": contact_id,
            "note": "audit running (~5 min); grade + teaser + cities land on the contact"}


# --- Booking backstop: a booked sales call must never reach call day unaudited
#
# Proven gap (Virgil Santa, 2026-08-14): leads can BOOK a sales call through
# paths that fire neither /lead-audit (the funnel form) nor
# /lead-audit/ghl-appointment (the staff-booked webhook), so they reach call
# day with empty audit fields and the nurture messaging misfires. Poll-based
# by design — zero GoHighLevel configuration: a pg_cron job ('booking-
# backstop', every 30 min) hits this endpoint, which scans the sales
# calendars' next 72h of appointments and queues the standard lead audit for
# any contact that has none. Audits are client-message-free (sales mode
# writes GHL custom fields + a note; the nurture workflow reacting to the
# fields appearing is the point).

BACKSTOP_WINDOW_HOURS = 72
BACKSTOP_RETRY_DAYS = 7            # one audit attempt per contact per week
BACKSTOP_KV_KEY = "booking-backstop"   # ops_kv ledger {contact_id: attempted_at}
BACKSTOP_KV_PRUNE_DAYS = 45
BACKSTOP_FOLLOWUP_CALENDAR = "uZ7whcPD6NFDqcSu0hCf"  # existing clients — never audit

# Calendar triage by name (discovered 2026-08-17). The funnel books demo /
# strategy calendars; kickoff, follow-up, support, go-live and hiring
# calendars serve people who already signed (or aren't prospects at all).
BACKSTOP_CAL_INCLUDE = ("guarantee", "strategy call", "strategy session", "demo")
BACKSTOP_CAL_EXCLUDE = ("follow up", "follow-up", "kickoff", "kick off", "kick-off",
                        "support", "go-live", "golive", "go live", "integration",
                        "hiring", "onboarding")

_BACKSTOP_LOCK = threading.Lock()   # 30-min cadence never overlaps a slow scan


def _backstop_client_contact_ids() -> set:
    """Every GHL contact id linked to a CURRENT client (companies.
    integration_settings top-level ghl_contact_id + each contacts[] entry's
    own id). One cheap fetch per run — booked CLIENTS must never be audited
    like prospects."""
    ids = set()
    try:
        rows = (sb().table("companies").select("id,integration_settings")
                .execute().data or [])
    except Exception as e:  # noqa: BLE001
        print("[booking-backstop] companies fetch failed:", str(e)[:150])
        return ids
    for r in rows:
        s = r.get("integration_settings") or {}
        if s.get("ghl_contact_id"):
            ids.add(s["ghl_contact_id"])
        for c in (s.get("contacts") or []):
            if isinstance(c, dict) and c.get("ghl_contact_id"):
                ids.add(c["ghl_contact_id"])
    return ids


@app.post("/booking-backstop")
def booking_backstop(request: Request):
    """Scan upcoming sales appointments; queue the standard lead audit for any
    contact with no audit on file. Auth: X-Rank-AI-Secret header or ?secret=
    against LEAD_AUDIT_FUNNEL_SECRET (same contract as /lead-audit/
    ghl-appointment). ?dry_run=1 reports what would be queued without queuing."""
    expected = os.environ.get("LEAD_AUDIT_FUNNEL_SECRET", "")
    supplied = (_mf(request.headers.get("X-Rank-AI-Secret"))
                or _mf(request.query_params.get("secret")))
    if not (expected and supplied == expected):
        raise HTTPException(status_code=403, detail="bad secret")
    dry_run = (request.query_params.get("dry_run") or "").lower() in ("1", "true", "yes")
    if not _BACKSTOP_LOCK.acquire(blocking=False):
        return {"status": "already_running"}
    try:
        return _booking_backstop_run(dry_run)
    finally:
        _BACKSTOP_LOCK.release()


def _booking_backstop_run(dry_run: bool) -> dict:
    import lead_audit  # scripts/ is on sys.path (see header)

    now = datetime.now(timezone.utc)
    horizon = now + timedelta(hours=BACKSTOP_WINDOW_HOURS)

    # 1. Discover calendars; select the sales-facing ones by name.
    selected, excluded_cals = [], []
    for c in (lead_audit._ghl("GET", "/calendars/") or {}).get("calendars") or []:
        cal_id, cal_name = c.get("id") or "", (c.get("name") or "").strip()
        low = cal_name.lower()
        why = None
        if cal_id == BACKSTOP_FOLLOWUP_CALENDAR:
            why = "client follow-up calendar"
        elif not c.get("isActive", True):
            why = "inactive"
        elif (c.get("calendarType") or "") == "personal":
            why = "personal calendar"
        elif any(t in low for t in BACKSTOP_CAL_EXCLUDE):
            why = "post-sale/internal name"
        elif not any(t in low for t in BACKSTOP_CAL_INCLUDE):
            why = "not sales-facing"
        if why:
            excluded_cals.append({"id": cal_id, "name": cal_name, "why": why})
        else:
            selected.append({"id": cal_id, "name": cal_name})

    # 2. Upcoming appointments in the window (the API leaks events outside
    # the requested range, so re-filter by start time here).
    start_ms, end_ms = int(now.timestamp() * 1000), int(horizon.timestamp() * 1000)
    appts = []
    for cal in selected:
        try:
            evs = (lead_audit._ghl("GET", "/calendars/events",
                                   params={"calendarId": cal["id"],
                                           "startTime": start_ms, "endTime": end_ms})
                   or {}).get("events") or []
        except Exception as e:  # noqa: BLE001
            print("[booking-backstop] events fetch failed for {} ({}): {}".format(
                cal["name"], cal["id"], str(e)[:120]))
            continue
        for ev in evs:
            if ev.get("deleted") or not ev.get("contactId"):
                continue
            if (ev.get("appointmentStatus") or "").lower() in ("cancelled", "noshow", "invalid"):
                continue
            try:
                st = datetime.fromisoformat(ev.get("startTime") or "")
                if st.tzinfo is None:
                    st = st.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            if not (now <= st <= horizon):
                continue
            appts.append({"ev": ev, "cal": cal, "start": st})
    appts.sort(key=lambda a: a["start"])  # nearest call gets its audit first

    client_ids = _backstop_client_contact_ids()

    # 3. Dedupe ledger: one attempt per contact per BACKSTOP_RETRY_DAYS.
    kv = {}
    try:
        rows = sb().table("ops_kv").select("v").eq("k", BACKSTOP_KV_KEY).execute().data
        kv = dict((rows[0].get("v") if rows else None) or {})
    except Exception as e:  # noqa: BLE001
        print("[booking-backstop] ops_kv read failed:", str(e)[:150])

    field_by_id = {}
    try:
        field_by_id = {v: k for k, v in lead_audit._ghl_custom_field_ids().items() if v}
    except Exception as e:  # noqa: BLE001
        print("[booking-backstop] custom-field map failed:", str(e)[:150])

    freemail = set(lead_audit._FREE_MAIL) | {"proton.me", "pm.me", "protonmail.com",
                                             "googlemail.com", "ymail.com"}

    # 4. Per contact: skip clients / already-audited / recent attempts, then
    # queue the exact same job the funnel form queues (sales mode: fields +
    # teaser land on the GHL contact, no lead-facing email).
    contacts_out, seen = [], set()
    queued = 0
    kv_dirty = False
    for a in appts:
        contact_id = a["ev"]["contactId"]
        if contact_id in seen:
            continue
        seen.add(contact_id)
        row = {"contact_id": contact_id, "start": a["start"].isoformat(),
               "calendar": a["cal"]["name"], "title": (a["ev"].get("title") or "")[:80]}
        contacts_out.append(row)
        if contact_id in client_ids:
            row["action"] = "skip: existing client"
            continue
        prev = kv.get(contact_id)
        if prev:
            try:
                if now - datetime.fromisoformat(prev) < timedelta(days=BACKSTOP_RETRY_DAYS):
                    row["action"] = "skip: attempted {}".format(prev)
                    continue
            except ValueError:
                pass
        try:
            got = lead_audit._ghl("GET", "/contacts/{}".format(contact_id)) or {}
            contact = got.get("contact") or got or {}
        except Exception as e:  # noqa: BLE001
            row["action"] = "skip: contact fetch failed ({})".format(str(e)[:80])
            continue
        cf = {}
        for f in (contact.get("customFields") or []):
            key = field_by_id.get(f.get("id"))
            if key:
                cf[key] = _mf(f.get("value", f.get("field_value", f.get("fieldValue"))))
        if cf.get("audit_status") or cf.get("audit_report_url"):
            row["action"] = "skip: audit already on file (status={}, report={})".format(
                cf.get("audit_status") or "-", "yes" if cf.get("audit_report_url") else "no")
            continue

        email = _mf(contact.get("email"))
        website = (_mf(contact.get("website")) or cf.get("business_website", "")
                   or cf.get("website_info", ""))
        domain = _lead_norm_domain(website)
        if not re.match(r"^[a-z0-9.-]+\.[a-z]{2,}$", domain):
            edom = email.rsplit("@", 1)[-1].lower() if "@" in email else ""
            if edom and edom not in freemail and re.match(r"^[a-z0-9.-]+\.[a-z]{2,}$", edom):
                domain = edom
            else:
                # NEVER fabricate a plausible domain from the company name — a
                # lookalike .com can be a real stranger's live site and would
                # produce a WRONG report. The RFC 2606 reserved `.invalid`
                # sentinel routes lead_audit onto its honest no-website
                # degraded path (listing/form profiling, degraded_no_website).
                domain = "no-website.invalid"
        row["domain"] = domain
        if domain != "no-website.invalid" and \
                _lead_count_today(sb(), "domain", domain) >= GHL_APPT_MAX_PER_DOMAIN_DAY:
            row["action"] = "skip: {} audits for this domain today".format(GHL_APPT_MAX_PER_DOMAIN_DAY)
            continue
        name = " ".join(x for x in (_mf(contact.get("firstName")),
                                    _mf(contact.get("lastName"))) if x)
        business_name = _mf(contact.get("companyName"))
        if dry_run:
            row["action"] = "would queue audit"
            continue

        req = LeadAuditRequest(
            website=domain, domain=domain, name=name, email=email, phone=_mf(contact.get("phone")),
            business_name=business_name, source="booking-backstop",
            secret=os.environ.get("LEAD_AUDIT_FUNNEL_SECRET", ""), ghl_contact_id=contact_id)
        jrow = sb().table("marketing_jobs").insert({
            "type": "lead_audit", "status": "queued",
            "params": {"domain": domain, "name": name, "email": email, "phone": req.phone,
                       "ip": "", "source": "booking-backstop",
                       "business_name": business_name or None,
                       "place_id": None, "cid": None,
                       "ghl_contact_id": contact_id,
                       "sales": True, "attempts": 0},
        }).execute()
        job_id = jrow.data[0]["id"]
        threading.Thread(target=_run_lead_audit_job, args=(job_id, req), daemon=True).start()
        kv[contact_id] = now.isoformat()
        kv_dirty = True
        queued += 1
        row["action"] = "queued audit {}".format(job_id)

    # Prune + persist the ledger (marketing_work_log needs a company_id, which
    # lead audits don't have — the print line + this response ARE the log).
    stale = [k for k, v in kv.items()
             if not isinstance(v, str)
             or (now - datetime.fromisoformat(v)) > timedelta(days=BACKSTOP_KV_PRUNE_DAYS)]
    if kv_dirty or stale:
        for k in stale:
            kv.pop(k, None)
        try:
            sb().table("ops_kv").upsert(
                {"k": BACKSTOP_KV_KEY, "v": kv, "updated_at": now.isoformat()},
                on_conflict="k").execute()
        except Exception as e:  # noqa: BLE001
            print("[booking-backstop] ops_kv write failed:", str(e)[:150])

    actions = [r.get("action", "") for r in contacts_out]
    print("[booking-backstop] {}: {} cal selected / {} excluded; {} appts in {}h; "
          "{} contacts -> {} queued, {} client-skips, {} already-audited, {} deduped".format(
              "DRY RUN" if dry_run else "live", len(selected), len(excluded_cals),
              len(appts), BACKSTOP_WINDOW_HOURS, len(contacts_out), queued,
              sum(1 for x in actions if "existing client" in x),
              sum(1 for x in actions if "already on file" in x),
              sum(1 for x in actions if x.startswith("skip: attempted"))))
    return {"status": "ok", "dry_run": dry_run,
            "calendars": {"selected": selected, "excluded": excluded_cals},
            "appointments_scanned": len(appts),
            "contacts": contacts_out, "queued": queued}


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


# Short-TTL cache for the twiml route's company lookup: every second of
# webhook latency is dead air for a live caller (Jack Bispo 2026-08-30), and
# routing config changes rarely. 120s keeps config edits near-instant while
# repeat calls skip the DB round-trip entirely.
_TWIML_CO_CACHE: dict[str, tuple[float, list]] = {}


# ---- SPAM SHIELD (E1+E2, Santino 2026-09-18, the RestorationXpress
# forensics: 74 spam calls, all on the GBP line, dozens of rotating 561
# numbers at machine-length durations — the number is scraped from the
# Google listing by lead-gen farms).
#   E1: numbers call-intel classified as spam land in ops_kv
#       'spam-blocklist'; a repeat caller never rings the client again.
#   E2: FIRST-TIME callers get a Twilio Lookup line-type check with a
#       Nomorobo spam score when the add-on is installed; high-risk goes
#       to the same dead end. Verdicts cache in 'spam-lookup-cache' so a
#       number is looked up once, ever. Lookup is capped at 1.5s — on any
#       error or timeout the call goes THROUGH (a real customer must never
#       be blocked by our plumbing).
_SPAM_KV_CACHE: dict = {}


def _spam_blocklist() -> dict:
    hit = _SPAM_KV_CACHE.get("bl")
    if hit and (time.time() - hit[0]) < 120:
        return hit[1]
    try:
        rows = sb().table("ops_kv").select("v").eq("k", "spam-blocklist")             .limit(1).execute().data
        bl = (rows[0]["v"] if rows else {}) or {}
    except Exception:
        bl = (hit[1] if hit else {})
    _SPAM_KV_CACHE["bl"] = (time.time(), bl)
    return bl


def _spam_prefix_blocks() -> dict:
    """Active NPA-NXX blocks (Santino approved 2026-09-24): call_intel
    writes a prefix here when 3+ DISTINCT numbers from it are classified
    spam within 7 days. Entries expire (until) — a farm moves on, the
    prefix comes back. 120s-cached like the blocklist."""
    hit = _SPAM_KV_CACHE.get("pb")
    if hit and (time.time() - hit[0]) < 120:
        return hit[1]
    try:
        rows = sb().table("ops_kv").select("v").eq(
            "k", "spam-prefix-blocks").limit(1).execute().data
        pb = (rows[0]["v"] if rows else {}) or {}
    except Exception:  # noqa: BLE001
        pb = (hit[1] if hit else {})
    _SPAM_KV_CACHE["pb"] = (time.time(), pb)
    return pb


def _is_known_contact(from_num: str) -> bool:
    """True when the caller matches a CRM contact — prefix blocks must
    never dead-end a real customer who shares an area-code prefix with a
    spam farm. Fails open (unknown lookup error -> treated as known)."""
    digits = "".join(ch for ch in from_num if ch.isdigit())[-10:]
    if len(digits) < 10:
        return False
    ck = "crm:" + digits
    hit = _SPAM_KV_CACHE.get(ck)
    if hit is not None:
        return hit
    try:
        rows = sb().table("contacts").select("id").ilike(
            "phone", f"%{digits[:3]}%{digits[3:6]}%{digits[6:]}%"
        ).limit(1).execute().data
        known = bool(rows)
    except Exception:  # noqa: BLE001
        known = True    # cannot verify -> do not block
    _SPAM_KV_CACHE[ck] = known
    return known


def _spam_lookup_verdict(from_num: str) -> str:
    """'block' | 'allow'. Cached per number forever; fails open."""
    try:
        rows = sb().table("ops_kv").select("v").eq("k", "spam-lookup-cache")             .limit(1).execute().data
        cache = (rows[0]["v"] if rows else {}) or {}
    except Exception:
        cache = {}
    if from_num in cache:
        return cache[from_num].get("verdict", "allow")
    verdict, why = "allow", ""
    try:
        import requests as _rq
        _sid = os.environ.get("TWILIO_MASTER_ACCOUNT_SID", "")
        _tok = os.environ.get("TWILIO_MASTER_AUTH_TOKEN", "")
        if _sid and _tok and from_num.startswith("+"):
            r = _rq.get(
                f"https://lookups.twilio.com/v1/PhoneNumbers/{from_num}",
                params={"AddOns": "nomorobo_spamscore"},
                auth=(_sid, _tok), timeout=1.5)
            if r.status_code == 200:
                add = ((r.json().get("add_ons") or {}).get("results") or {})                     .get("nomorobo_spamscore") or {}
                score = ((add.get("result") or {}).get("score"))
                if add.get("status") == "successful" and score == 1:
                    verdict, why = "block", "nomorobo score 1"
    except Exception:
        pass  # fail open, always
    try:
        cache[from_num] = {"verdict": verdict, "why": why,
                           "at": datetime.now(timezone.utc).isoformat()}
        sb().table("ops_kv").upsert({"k": "spam-lookup-cache", "v": cache},
                                    on_conflict="k").execute()
    except Exception:
        pass
    return verdict



def _db_safe_source(source: str) -> str:
    """marketing_tracked_calls.source has a CHECK constraint that predates
    the newer DNI sources (Bobby/RT Olson 2026-09-23: 44 meta_ads calls
    forwarded fine and EVERY log insert bounced 23514, silently). Until the
    constraint is widened in the dashboard, map unknowns to their nearest
    allowed family so calls are never invisible: meta_ads -> facebook
    (same platform), metro_<area> -> website (metro numbers are site DNI).
    Remove this once the constraint is dropped."""
    allowed = {"gbp", "website", "google_ads", "facebook", "instagram",
               "bing", "yelp", "chatgpt", "gemini"}
    if source in allowed:
        return source
    if source == "meta_ads":
        return "facebook"
    return "website"

_CODE_WORDS = re.compile(
    r"(?i)\b(verification|verify|passcode|one[- ]time|security code|"
    r"confirmation code|login code|sign[- ]in code|your code|code is|otp|pin)\b")
_CODE_NUM = re.compile(r"(?<!\d)(\d{4,8})(?!\d)")


def _verification_code(from_num: str, body: str) -> str | None:
    """Return the one-time code if this inbound text is a platform
    verification message, else None. Requires BOTH a machine sender
    (short code, toll-free, or alphanumeric id) AND code language + a 4-8
    digit number, so an ordinary customer text is never swallowed."""
    digits = re.sub(r"\D", "", from_num or "")
    machine = (len(digits) <= 6 or not digits
               or digits[-10:-7] in ("800", "833", "844", "855", "866",
                                     "877", "888"))
    if not machine or not _CODE_WORDS.search(body or ""):
        return None
    m = _CODE_NUM.search(body or "")
    return m.group(1) if m else None


@app.post("/call-tracking/sms/{company_id}/{source}")
async def call_tracking_sms(company_id: str, source: str, request: Request):
    """Twilio SMS webhook for DNI tracking numbers (Rita Look 2026-09-18:
    she texted Tony's GBP tracking line and the message died — sms_url was
    empty on every tracking number, fleet-wide). Logs the inbound and
    forwards it to the owner's cell from the agency's approved HydroZ
    toll-free, labeled with which line it came in on. Never errors back at
    Twilio: a webhook 500 would make Twilio retry-spam."""
    form = await request.form()
    from_num = str(form.get("From") or "")
    to_num = str(form.get("To") or "")
    body = str(form.get("Body") or "").strip()
    try:
        sb().table("messages").insert({
            "company_id": company_id, "direction": "inbound",
            "content": body, "status": "received",
            "source": f"tracking-{source}",
            "sender_id": from_num, "message_type": "sms",
        }).execute()
    except Exception as e:  # noqa: BLE001
        print("[tracking-sms] log failed:", str(e)[:120])
    # VERIFICATION-CODE CATCHER (Santino 2026-09-27): platforms we sign
    # clients up on can text their one-time codes to OUR Twilio numbers.
    # Those must be captured for the Mini (ops_kv verification-codes:{cid})
    # and must NOT be forwarded to the owner as a "customer texted you".
    # Real customer texts are untouched. Log-only in `messages` either way.
    code = _verification_code(from_num, body)
    if code:
        try:
            k = f"verification-codes:{company_id}"
            rows = sb().table("ops_kv").select("v").eq("k", k).execute().data
            items = ((rows[0].get("v") if rows else None) or {}).get("codes", [])
            items = (items + [{
                "code": code, "from": from_num, "to": to_num,
                "body": body[:300], "source": source,
                "at": datetime.now(timezone.utc).isoformat()}])[-20:]
            sb().table("ops_kv").upsert({"k": k, "v": {"codes": items}},
                                        on_conflict="k").execute()
            print(f"[tracking-sms] verification code captured for "
                  f"{company_id} from {from_num} (not forwarded)")
        except Exception as e:  # noqa: BLE001
            print("[tracking-sms] code capture failed:", str(e)[:150])
        from fastapi.responses import Response as _Resp
        return _Resp(content="<Response/>", media_type="application/xml")
    try:
        co = (sb().table("companies")
              .select("phone,integration_settings,name")
              .eq("id", company_id).limit(1).execute().data or [{}])[0]
        ints = co.get("integration_settings") or {}
        if isinstance(ints, str):
            ints = json.loads(ints or "{}")
        owner = (ints.get("owner_cell") or co.get("phone") or "")
        owner = "+1" + re.sub(r"\D", "", owner)[-10:] if owner else ""
        if owner and body:
            import requests as _rq
            label = {"gbp": "Google Business", "google_ads": "Google Ads",
                     "website": "website", "bing": "Bing", "yelp": "Yelp",
                     "gemini": "Gemini", "chatgpt": "ChatGPT"}.get(
                         source, source)
            note = (f"A customer texted your {label} tracking line "
                    f"({to_num}). From {from_num}:\n\n{body}\n\n"
                    "You can reply to them directly at their number.")
            _rq.post(
                "https://api.twilio.com/2010-04-01/Accounts/"
                "AC7fda75e56b54d75ca02b31082c42142b/Messages.json",
                auth=(os.environ["TWILIO_MASTER_ACCOUNT_SID"],
                      os.environ["TWILIO_MASTER_AUTH_TOKEN"]),
                data={"To": owner, "From": "+18337271056", "Body": note},
                timeout=30)
    except Exception as e:  # noqa: BLE001
        print("[tracking-sms] forward failed:", str(e)[:150])
    from fastapi.responses import Response as _Resp
    return _Resp(content="<Response/>", media_type="application/xml")


@app.post("/call-tracking/twiml/{company_id}/{source}")
async def call_tracking_twiml(company_id: str, source: str, request: Request,
                              background_tasks: BackgroundTasks):
    """Twilio Voice webhook: answer, (disclose where required), record, and
    dial straight through to the client's real line."""
    form = await request.form()
    call_sid = str(form.get("CallSid") or "")
    from_num = str(form.get("From") or "")
    to_num = str(form.get("To") or "")
    # SPAM SHIELD gate: repeat offenders (E1) and lookup-flagged robocallers
    # (E2) get a polite dead end and a logged row — they never ring the
    # client, and the app counts them as "blocked".
    _bl = _spam_blocklist()
    _blocked_reason = None
    _stir = str(form.get("StirVerstat") or "")
    if from_num and from_num in _bl:
        _blocked_reason = "blocklist"
    # PREFIX VELOCITY (2026-09-24): a farm rotating numbers inside one
    # NPA-NXX. Known CRM contacts are exempt; entries expire on their own.
    if _blocked_reason is None and from_num:
        _pb = _spam_prefix_blocks().get(from_num[:8])
        if _pb:
            try:
                _live = datetime.fromisoformat(
                    str(_pb.get("until"))) > datetime.now(timezone.utc)
            except (ValueError, TypeError):
                _live = False
            if _live and not _is_known_contact(from_num):
                _blocked_reason = "prefix-velocity"
    # SHAKEN/STIR (2026-09-24): an outright failed attestation is a spoofed
    # CLI — carriers vouch for A; 'TN-Validation-Failed' means the caller
    # provably does NOT own the number it is showing. CRM exempt, like all
    # first-contact blocks.
    if (_blocked_reason is None and from_num
            # Twilio sends the grade suffix ("TN-Validation-Failed-A/B/C"),
            # so the old exact match never fired once (found 2026-10-02).
            and _stir.startswith("TN-Validation-Failed")
            and not _is_known_contact(from_num)):
        _blocked_reason = "stir-failed"
    if _blocked_reason is None and from_num             and os.environ.get("SPAM_LOOKUP_ENABLED") == "1":
        _seen_hit = _SPAM_KV_CACHE.get("seen:" + from_num)
        if not _seen_hit:
            _SPAM_KV_CACHE["seen:" + from_num] = True
            if _spam_lookup_verdict(from_num) == "block":
                _blocked_reason = "lookup"
    if _blocked_reason:
        def _log_blocked():
            try:
                if call_sid:
                    sb().table("marketing_tracked_calls").upsert({
                        "company_id": company_id,
                        "source": _db_safe_source(source),
                        "tracking_number": to_num, "from_number": from_num,
                        "call_sid": call_sid, "status": "blocked_spam",
                        "analysis": {"outcome": "spam",
                                     "blocked": _blocked_reason,
                                     "stir": _stir or None},
                    }, on_conflict="call_sid").execute()
            except Exception as e:  # noqa: BLE001
                print("[spam-shield] log failed:", str(e)[:120])
        background_tasks.add_task(_log_blocked)
        from fastapi.responses import Response as _Resp
        return _Resp(content=(
            '<?xml version="1.0" encoding="UTF-8"?><Response>'
            '<Say voice="Polly.Joanna">This number does not accept '
            'solicitation calls. If you are a customer, please call back '
            'from your primary phone.</Say><Hangup/></Response>'),
            media_type="application/xml")

    _hit = _TWIML_CO_CACHE.get(company_id)
    if _hit and (time.time() - _hit[0]) < 120:
        co = _hit[1]
    else:
        co = sb().table("companies").select("phone,state,integration_settings") \
            .eq("id", company_id).limit(1).execute().data
        _TWIML_CO_CACHE[company_id] = (time.time(), co)
    if not co:
        raise HTTPException(status_code=404, detail="unknown company")
    _ints = co[0].get("integration_settings") or {}
    if isinstance(_ints, str):
        try:
            _ints = json.loads(_ints)
        except Exception:
            _ints = {}
    _ct = (_ints.get("call_tracking") or {}).get(source) or {}

    # PER-CLIENT FORWARD TARGET (Santino 2026-08-07, RestorationXpress).
    # Default is companies.phone, but Roy's site number rings a multi-level IP
    # phone menu; he asked for the tracked line to reach Isaac's cell directly.
    # forward_to on the call_tracking entry overrides, so one client's routing
    # never becomes everyone's.
    real = re.sub(r"[^\d+]", "", _ct.get("forward_to") or co[0].get("phone") or "")
    if real and not real.startswith("+"):
        real = "+1" + real.lstrip("1")
    if not real:
        raise HTTPException(status_code=500, detail="company has no phone")
    disclose = _state_abbrev(co[0].get("state") or "") in ALL_PARTY_STATES

    # WHISPER — OFF BY DEFAULT, AND THAT STAYS THE RULE.
    # The standing policy is no whisper: calls connect straight through, because
    # a whisper delays the bridge and an owner who is used to picking up hears
    # dead air. Roy asked for one explicitly on his 2026-08-04 follow-up call so
    # Isaac can tell a campaign lead from a normal call and screen out ones he
    # would otherwise pay for. That is a per-client OPT-IN written on the
    # call_tracking entry (whisper: "Call from Restoration AI"), never a default,
    # and it is spoken only to the ANSWERING party via the Number verb's `url`,
    # so the caller never hears it.
    _whisper = str(_ct.get("whisper") or "").strip()

    # Log AFTER the response goes back to Twilio — the upsert used to sit on
    # the caller's critical path and every ms here is dead air (Jack Bispo
    # 2026-08-30). BackgroundTasks runs it the moment the TwiML is sent.
    def _log_ringing():
        try:
            if call_sid:
                sb().table("marketing_tracked_calls").upsert({
                    "company_id": company_id,
                    "source": _db_safe_source(source),
                    "tracking_number": to_num, "from_number": from_num,
                    "to_number": real, "call_sid": call_sid, "status": "ringing",
                }, on_conflict="call_sid").execute()
        except Exception as e:  # noqa: BLE001 — logging must never break the call
            print("[call-tracking] log failed:", str(e)[:120])
        # STIR/SHAKEN evidence for EVERY call (2026-10-02, Tony/Coastal spam
        # study): the "Google listing verification" robocalls rotate local
        # VoIP/landline numbers, and line type + carrier overlap real callers
        # (insurance agents, property managers), so the next block rule must
        # be evidence-based. Kept in ops_kv (call_intel rewrites `analysis`).
        try:
            if call_sid:
                sb().table("ops_kv").upsert({
                    "k": f"call-stir:{call_sid}",
                    "v": {"stir": _stir or None, "from": from_num,
                          "company_id": company_id, "source": source,
                          "at": datetime.now(timezone.utc).isoformat()},
                }, on_conflict="k").execute()
        except Exception as e:  # noqa: BLE001
            print("[call-tracking] stir log failed:", str(e)[:120])
    background_tasks.add_task(_log_ringing)
    base = "https://rank-ai-api-production.up.railway.app"
    say = ('<Say voice="Polly.Joanna">This call may be recorded.</Say>'
           if disclose else "")
    if _whisper:
        _wurl = (f"{base}/call-tracking/whisper?text="
                 + urllib.parse.quote(_whisper[:120]))
        _dial_target = f'<Number url="{_wurl}">{real}</Number>'
    else:
        _dial_target = real
    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?><Response>' + say +
        f'<Dial record="record-from-answer-dual" answerOnBridge="true"'
        f' recordingStatusCallback="{base}/call-tracking/recording/{company_id}"'
        f' action="{base}/call-tracking/status/{company_id}" method="POST">'
        f'{_dial_target}</Dial></Response>')
    from fastapi.responses import Response as _Resp
    return _Resp(content=twiml, media_type="application/xml")


@app.api_route("/call-tracking/whisper", methods=["GET", "POST"])
async def call_tracking_whisper(text: str = "Call from Restoration AI"):
    """Spoken to the ANSWERING party only, before the legs bridge.

    Twilio fetches this from the <Number url="..."> attribute, so the caller
    hears ringing throughout and never hears this. Opt-in per client — see the
    whisper note in call_tracking_twiml.
    """
    from fastapi.responses import Response as _Resp
    safe = (text or "")[:120].replace("&", "and").replace("<", "").replace(">", "")
    return _Resp(
        content=('<?xml version="1.0" encoding="UTF-8"?><Response>'
                 f'<Say voice="Polly.Joanna">{safe}</Say></Response>'),
        media_type="application/xml")


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
        # Call intel (2026-09-10): kick the transcribe+analyze workflow so the
        # drawer fills within ~a minute of hangup; the 30-min cron backstops.
        gh_pat = os.environ.get("GH_PAT")
        if gh_pat:
            try:
                import requests
                requests.post(
                    "https://api.github.com/repos/restorationai/Rank-AI-Pipeline/"
                    "actions/workflows/call-intel.yml/dispatches",
                    headers={"Authorization": f"Bearer {gh_pat}",
                             "Accept": "application/vnd.github+json"},
                    json={"ref": "main"}, timeout=15)
            except Exception as e:  # noqa: BLE001
                print("[call-tracking] intel dispatch failed:", str(e)[:100])
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


def _invite_agency_manager(company_id: str, slug: str) -> None:
    """Add contact@restorationai.io as a MANAGER on the client's GBP — and
    accept the invitation — the moment they connect Google.

    Santino 2026-08-04: the invite used to be a manual script run (once, on
    08-01), so Reign connected on 08-03 and simply never got one, which is
    exactly why Reign had no Bing listing. Bing Places imports only the
    listings the agency account directly manages, so this is the first domino
    of the whole citations lane and it belongs in the connect moment, not in a
    human's memory. Idempotent — an existing manager/invite is a no-op. The
    daily ops pass (client_ops_sync.ensure_gbp_manager_access) is the
    backstop."""
    try:
        from gbp_admin_invite import ensure_agency_manager
        results, attention = ensure_agency_manager(
            dry_run=False, only_company_ids=[company_id])
        state = (results.get(slug) or {}).get("state", "?")
        print(f"[gbp-first-sync] manager-access: {slug} -> {state}")
        for a in attention:
            print(f"[gbp-first-sync] manager-access ATTENTION: {a}")
    except Exception as e:  # noqa: BLE001 — never break the connect flow
        print("[gbp-first-sync] manager-access failed:", slug, str(e)[:200])


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
        # Already synced, but the manager invite is a SEPARATE fact and may
        # still be missing (Reign 2026-08-03: connected, synced, never
        # invited, therefore never on Bing). Fire just that half.
        threading.Thread(target=_invite_agency_manager,
                         args=(req.company_id, slug), daemon=True).start()
        return {"status": "queued", "slug": slug, "note": "already synced — "
                "agency manager invite only"}

    def _run(s=slug):
        # Full day-one blitz (Santino 2026-07-26: Kyle's follow-up call hit
        # empty tabs): sync -> AI optimizer suggestions -> face-score audit.
        # Each step best-effort; nightly ops-sync backstops all of them.
        # Manager access goes FIRST — it is the only step whose absence is
        # invisible (no empty tab, just a client who never reaches Bing).
        _invite_agency_manager(req.company_id, s)
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


@app.post("/upload-event")
async def upload_event_endpoint(request: Request):
    """Branding-bucket upload sweep -> Monica thank-you texts (Monica email
    evolution 2e, 2026-08-20 — the Robert's-logo class: uploads landed
    silently). Fed by pg_cron job 'upload-event-sweep' every 10 min with
    the storage objects created in the last ~11 minutes; every call also
    retries hours-gated pending bursts, so a night upload gets its thanks
    in the morning. Empty batches are a fast no-op unless pendings exist.

    Auth: X-Rank-AI-Secret header or ?secret= against
    LEAD_AUDIT_FUNNEL_SECRET (same contract as /booking-backstop).
    Payload: {"objects": [{"name": "CO-.../job-photos/x.jpg", ...}, ...]}
    or a bare JSON array."""
    expected = os.environ.get("LEAD_AUDIT_FUNNEL_SECRET", "")
    supplied = (_mf(request.headers.get("X-Rank-AI-Secret"))
                or _mf(request.query_params.get("secret")))
    if not (expected and supplied == expected):
        raise HTTPException(status_code=403, detail="bad secret")
    try:
        body = await request.json()
    except Exception:
        body = {}
    objects = body if isinstance(body, list) else \
        (body.get("objects") if isinstance(body, dict) else None) or []

    def _run():
        try:
            import client_concierge  # scripts/ is on sys.path (see header)
            client_concierge.load_env()
            out = client_concierge.upload_event(objects, do_send=True)
            if out.get("acked") or out.get("held") or out.get("dropped"):
                print(f"[upload-event] {out} ({len(objects)} object(s) in)")
        except Exception as e:  # noqa: BLE001 — sweep thread must not die loudly
            print("[upload-event] failed:", str(e)[:300])

    threading.Thread(target=_run, daemon=True).start()
    return {"status": "queued", "objects": len(objects)}


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


class ConciergePreviewRequest(BaseModel):
    company_id: str
    secret: str = ""


@app.post("/concierge-preview")
def concierge_preview(req: ConciergePreviewRequest):
    """Preview Monica's NEXT message for one company (Santino 2026-08-03:
    messages generate on the spot at send time, so the app's "Preview next
    message" button runs the same compose in dry-run here). Read-only: no
    state writes, no escalations, nothing sent. Returns {draft, subject,
    channel, gate, company, items}; `gate` says why a real send would be
    held right now (cooldown / business hours / human-defer), null when it
    would go out. Slow by nature (~15-60s: GHL history + a Claude call).
    Auth: shared secret checked against CONCIERGE_WEBHOOK_SECRET (falls
    back to LEAD_AUDIT_FUNNEL_SECRET) — same contract as /concierge-inbound."""
    expected = (os.environ.get("CONCIERGE_WEBHOOK_SECRET")
                or os.environ.get("LEAD_AUDIT_FUNNEL_SECRET", ""))
    if not (expected and req.secret == expected):
        raise HTTPException(status_code=403, detail="bad secret")
    if not req.company_id.startswith("CO-"):
        raise HTTPException(status_code=400, detail="company_id must be a CO-… id")
    try:
        import client_concierge  # scripts/ is on sys.path (see header)
        client_concierge.load_env()
        out = client_concierge.preview_compose(req.company_id)
    except Exception as e:  # noqa: BLE001 — surface, never 500 with a stack
        raise HTTPException(status_code=502,
                            detail="preview failed: " + str(e)[:300])
    if out.get("error"):
        raise HTTPException(status_code=404, detail=out["error"])
    return out


@app.post("/concierge-send-now")
def concierge_send_now(req: ConciergePreviewRequest):
    """One explicit human click on the previewed draft = send it (Santino
    2026-08-03, after using the Crew preview: "Send now"). Boss-directive
    semantics: cooldown + nudge cap bypassed (the click IS the
    authorization, like a [FROM SANTINO] note); business hours NOT
    hard-blocked — the response carries local_time/in_business_hours so the
    UI confirms first. Hard safety gates KEPT: canary allowlist, CRM DND
    (with SMS->email fallback), grounding guard, and the duplicate guard (a
    second immediate click recomposes near-identical copy and is refused).
    Flows through the normal send path — work_log outreach line, sent-ids
    ledger, awaiting/commitment + directive bookkeeping — so downstream
    sees a real Monica send. Auth: same contract as /concierge-preview.
    Serialized per company via the concierge locks (double-click safe)."""
    expected = (os.environ.get("CONCIERGE_WEBHOOK_SECRET")
                or os.environ.get("LEAD_AUDIT_FUNNEL_SECRET", ""))
    if not (expected and req.secret == expected):
        raise HTTPException(status_code=403, detail="bad secret")
    if not req.company_id.startswith("CO-"):
        raise HTTPException(status_code=400, detail="company_id must be a CO-… id")
    lock = _concierge_lock("send-now:" + req.company_id)
    try:
        with lock:
            import client_concierge  # scripts/ is on sys.path (see header)
            client_concierge.load_env()
            out = client_concierge.send_now(req.company_id)
    except Exception as e:  # noqa: BLE001 — surface, never 500 with a stack
        raise HTTPException(status_code=502,
                            detail="send-now failed: " + str(e)[:300])
    return out


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


@app.post("/voice-ai/take-message")
async def voice_ai_take_message(request: Request):
    """Called mid-call by the GHL Voice AI agent on the agency's own inbound
    toll-free (+18556484464) when it could not put the caller through.

    Exists because of the 2026-08-05 Jerrott Gray incident: the agent said
    "transferring you now" twice, had no CALL_TRANSFER action configured at
    all, and simply looped until a two-day-old client hung up. The transfer
    is now real, but a transfer can still legitimately fail (Santino does not
    pick up), and the ONE thing that must never happen again is a caller
    being left with a promise nobody kept. So: the agent takes a message and
    this endpoint puts it on Santino's cell within seconds.

    Deliberately NOT routed through client_concierge.send_message: that path
    is gated on CONCIERGE_PAUSED and the canary allowlist, both of which are
    client-facing safety rails. A caller who could not reach a human is an
    ops page to Santino's own phone and must survive the concierge being
    paused. It posts straight to GHL instead, to Santino's own contact only.

    Auth: shared secret via ?secret=, the x-voice-secret header, or an
    Authorization header (GHL Custom Actions send authenticationValue there),
    checked against VOICE_AI_WEBHOOK_SECRET, then CONCIERGE_WEBHOOK_SECRET,
    then LEAD_AUDIT_FUNNEL_SECRET.

    Body: liberal — caller_name / callback_number / message in any casing.
    It has to be liberal, because GHL's own API currently CANNOT store the
    Custom Action `parameters` array: POST/PUT /voice-ai/actions returns
    400 "Maximum call stack size exceeded" for any non-empty `parameters` or
    `headers` list (verified 2026-08-05 against every field combination).
    So the action is registered with no declared parameters and GHL may well
    post an empty body. When it does, we fall back to identifying the caller
    from GHL's own conversation history and still page Santino, because an
    alert that names the wrong caller is recoverable and silence is not.
    Every raw body is logged so the first live call pins down the real shape.
    """
    expected = (os.environ.get("VOICE_AI_WEBHOOK_SECRET")
                or os.environ.get("CONCIERGE_WEBHOOK_SECRET")
                or os.environ.get("LEAD_AUDIT_FUNNEL_SECRET", ""))
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}
    auth_hdr = (request.headers.get("authorization") or "")
    supplied = (request.query_params.get("secret")
                or request.headers.get("x-voice-secret")
                or auth_hdr.replace("Bearer ", "").strip()
                or str(body.get("secret") or ""))
    if not (expected and supplied == expected):
        raise HTTPException(status_code=403, detail="bad secret")

    print("[voice-ai/take-message] raw body:", json.dumps(body)[:1000])

    flat: dict = {}

    def _flatten(obj, depth: int = 0) -> None:
        if depth > 4 or not isinstance(obj, dict):
            return
        for k, v in obj.items():
            if isinstance(v, dict):
                _flatten(v, depth + 1)
            elif v not in (None, "", [], {}):
                flat.setdefault(str(k).lower().replace("-", "_"), str(v).strip())

    _flatten(body)

    def _pick(*names: str) -> str:
        for n in names:
            if flat.get(n):
                return flat[n]
        return ""

    caller = _pick("caller_name", "callername", "full_name", "name")
    callback = _pick("callback_number", "callbacknumber", "from", "from_number",
                     "phone", "number")
    note = _pick("message", "message_content", "reason", "summary", "notes")
    urgent = _pick("urgent", "is_urgent").lower() in ("1", "true", "yes")

    import client_concierge  # scripts/ is on sys.path (see header)
    client_concierge.load_env()

    # GHL cannot declare the action's parameters (see docstring), so an empty
    # body is the expected case, not an error. Identify the caller from the
    # most recent inbound call on this location instead of paging Santino
    # with nothing he can act on.
    if not (caller or callback):
        try:
            found = client_concierge._ghl(
                "GET", "/conversations/search",
                params={"locationId": os.environ["GHL_LOCATION_ID"],
                        "sort": "desc", "sortBy": "last_message_date",
                        "limit": 5}) or {}
            for conv in (found.get("conversations") or []):
                cid = conv.get("contactId")
                if not cid:
                    continue
                caller = (conv.get("fullName") or conv.get("contactName")
                          or caller)
                callback = (conv.get("phone") or callback)
                break
        except Exception as e:  # noqa: BLE001 — best effort only
            print("[voice-ai/take-message] caller lookup failed:", str(e)[:200])

    lines = ["URGENT MISSED CALL on the front desk line." if urgent
             else "MISSED CALL on the front desk line.",
             "",
             f"Name: {caller or 'not given'}",
             f"Callback: {callback or 'not given'}"]
    if note:
        lines += ["", note]
    lines += ["", "They called +18556484464, the front desk could not reach "
                  "you, and it took a message. Full transcript is on the "
                  "call in GHL."]
    text = "\n".join(lines)

    try:
        contact_id = getattr(client_concierge, "OPS_PING_CONTACT_ID", "")
        payload = {"type": "SMS", "contactId": contact_id, "message": text}
        from_number = os.environ.get("CONCIERGE_FROM_NUMBER", "").strip()
        if from_number:
            payload["fromNumber"] = from_number
        client_concierge._ghl("POST", "/conversations/messages", body=payload)
    except Exception as e:  # noqa: BLE001 — the caller must never hear a stack
        print("[voice-ai/take-message] SMS failed:", str(e)[:300])
        return {"status": "logged",
                "spoken": "I have your message and I am getting it to Santino."}
    return {"status": "sent",
            "spoken": "I have your message and Santino has it on his phone now."}


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
