#!/usr/bin/env python3
"""
Rank AI — Google Ads Provisioning Worker (BUILD path)

The deterministic counterpart to ads_sync.py. Where ads_sync READS Google Ads ->
Supabase, this worker BUILDS a contractor's ads from a job queued by the app:

  marketing_ads_jobs (status='queued')  ->  this worker  ->  campaigns/LPs/tracking
                                                              (all PAUSED)
                                          ->  status='needs_review'
  marketing_ads_jobs (job_type='go_live') -> enable campaigns -> status='live'

It reuses the PROVEN scripts/ads_manager.py commands (same code an operator runs in
the terminal) plus scripts/build_site.py sync-deploy. Per-client Google Ads auth is
read from user_integrations (exactly like ads_sync.py); Twilio subaccount creds from
company_phone_setup. The worker writes ONLY marketing_* tables.

Design: deterministic. On any failure a job is marked status='failed' with the error,
and stops — it never improvises against a live, money-spending ad account. A human (or
an on-demand Claude session) reviews the failure and fixes the root cause in code.

Run modes:
  python3 scripts/ads_provision.py --once      # process one queued job then exit (cron)
  python3 scripts/ads_provision.py --loop       # poll forever (worker service)

Required env:
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
  GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET, GOOGLE_ADS_DEVELOPER_TOKEN
  GITHUB_PERSONAL_ACCESS_TOKEN, ANTHROPIC_API_KEY, GOOGLE_AI_API_KEY (LP imagery, optional)
  GIT_AUTHOR/COMMITTER identity configured in the deploy environment
"""

import os
import sys
import json
import time
import base64
import urllib.request
import urllib.parse
import urllib.error
import subprocess
import logging
import argparse
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent  # where this worker's code lives
# WORK_ROOT is the checkout used for file generation + git ops. Locally it's the
# repo itself; on Railway it's a fresh full clone (see ensure_work_repo) so that
# `git subtree split/push` has real history + push credentials.
WORK_ROOT = REPO_ROOT
SCRIPTS = WORK_ROOT / "scripts"
CLIENTS = WORK_ROOT / "clients"
SITES = WORK_ROOT / "sites"


def set_work_root(path):
    global WORK_ROOT, SCRIPTS, CLIENTS, SITES
    WORK_ROOT = Path(path)
    SCRIPTS = WORK_ROOT / "scripts"
    CLIENTS = WORK_ROOT / "clients"
    SITES = WORK_ROOT / "sites"


def cloud_mode():
    return os.environ.get("ADS_WORKER_CLONE") == "1"


def ensure_work_repo():
    """In cloud mode (ADS_WORKER_CLONE=1) clone the monorepo fresh so git deploys
    work in a runtime container that has no .git. A no-op locally."""
    if not cloud_mode():
        return
    pat = os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN")
    if not pat:
        raise RuntimeError("ADS_WORKER_CLONE=1 but GITHUB_PERSONAL_ACCESS_TOKEN is not set")
    repo = os.environ.get("ADS_WORKER_REPO", "restorationai/Rank-AI-Pipeline")
    work = Path(os.environ.get("ADS_WORKER_WORKDIR", "/tmp/rank-ai-work"))
    url = f"https://x-access-token:{pat}@github.com/{repo}.git"
    if (work / ".git").exists():
        subprocess.run(["git", "-C", str(work), "fetch", "origin", "main"], check=True)
        subprocess.run(["git", "-C", str(work), "reset", "--hard", "origin/main"], check=True)
    else:
        work.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", url, str(work)], check=True)  # full clone — subtree needs history
    # Git identity for the worker's commits
    subprocess.run(["git", "-C", str(work), "config", "user.email", "ads-worker@restorationai.io"], check=False)
    subprocess.run(["git", "-C", str(work), "config", "user.name", "Rank AI Ads Worker"], check=False)
    set_work_root(work)
    log.info(f"Worker repo ready at {work}")

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s - %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S")
log = logging.getLogger("ads_provision")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
OAUTH_CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
OAUTH_CLIENT_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")

for _name, _val in [("SUPABASE_URL", SUPABASE_URL), ("SUPABASE_SERVICE_ROLE_KEY", SUPABASE_KEY)]:
    if not _val:
        log.error(f"Missing required env var: {_name}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Supabase REST helpers (service-role)
# ---------------------------------------------------------------------------
def _sb(method, path, body=None, prefer=None):
    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
               "Content-Type": "application/json"}
    if prefer:
        headers["Prefer"] = prefer
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}", data=data,
                                 headers=headers, method=method)
    with urllib.request.urlopen(req) as resp:
        raw = resp.read().decode()
        return json.loads(raw) if raw else None


def sb_get(path):
    return _sb("GET", path)


def sb_patch(path, body):
    return _sb("PATCH", path, body, prefer="return=representation")


def sb_post(path, body):
    return _sb("POST", path, body, prefer="return=representation")


def update_job(job_id, **fields):
    fields["updated_at"] = "now()"
    # PostgREST can't take now() as a value literal; drop it and let DB default/trigger handle, or send ISO.
    fields.pop("updated_at", None)
    try:
        sb_patch(f"marketing_ads_jobs?id=eq.{job_id}", fields)
    except Exception as e:
        log.warning(f"Failed to update job {job_id}: {e}")


def set_phase(job_id, phase, progress):
    log.info(f"  [{progress}%] {phase}")
    update_job(job_id, phase=phase, progress=progress)


# ---------------------------------------------------------------------------
# Client resolution + per-client auth shim
# ---------------------------------------------------------------------------
def resolve_client(company_id):
    """Return dict with slug, refresh_token, customer_id, login_customer_id, domain,
    twilio_subaccount_sid/auth_token. Raises if anything required is missing."""
    sites = sb_get(f"marketing_sites?company_id=eq.{urllib.parse.quote(company_id)}"
                   f"&select=rank_ai_slug,domain")
    if not sites:
        raise RuntimeError(f"No marketing_sites row for company {company_id}")
    slug = sites[0]["rank_ai_slug"]

    integ = sb_get(f"user_integrations?client_id=eq.{urllib.parse.quote(company_id)}"
                   f"&provider=eq.google_ads&select=connection_metadata,status")
    if not integ:
        raise RuntimeError(f"No google_ads integration for company {company_id} — client must connect Google Ads")
    meta = integ[0].get("connection_metadata") or {}
    refresh_token = meta.get("refresh_token")
    customer_id = meta.get("selected_ads_customer_id")
    login_customer_id = meta.get("login_customer_id") or customer_id
    if not refresh_token or not customer_id:
        raise RuntimeError(f"Integration for {company_id} missing refresh_token or customer_id")

    twilio = sb_get(f"company_phone_setup?id=eq.{urllib.parse.quote(company_id)}"
                    f"&select=twilio_subaccount_sid,twilio_auth_token")
    tw = twilio[0] if twilio else {}

    return {
        "company_id": company_id,
        "slug": slug,
        "domain": sites[0].get("domain", ""),
        "refresh_token": refresh_token,
        "customer_id": str(customer_id).replace("-", ""),
        "login_customer_id": str(login_customer_id).replace("-", ""),
        "twilio_sid": tw.get("twilio_subaccount_sid"),
        "twilio_token": tw.get("twilio_auth_token"),
    }


def write_auth_shim(ctx):
    """Materialize the local creds ads_manager.py expects, from the DB-sourced OAuth.
    This lets the worker reuse the exact proven CLI commands unchanged."""
    if not OAUTH_CLIENT_ID or not OAUTH_CLIENT_SECRET:
        raise RuntimeError("GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET not set")
    slug = ctx["slug"]
    tok_path = CLIENTS / slug / ".ads-token.json"
    tok_path.parent.mkdir(parents=True, exist_ok=True)
    tok_path.write_text(json.dumps({
        "client_id": OAUTH_CLIENT_ID,
        "client_secret": OAUTH_CLIENT_SECRET,
        "refresh_token": ctx["refresh_token"],
        "token": None,
        "scopes": ["https://www.googleapis.com/auth/adwords"],
    }))
    # Ensure the client record carries the customer id ads_manager reads.
    rec_path = CLIENTS / f"{slug}.json"
    if rec_path.exists():
        rec = json.loads(rec_path.read_text())
        rec.setdefault("brand", {})["google_ads_customer_id"] = ctx["customer_id"]
        rec_path.write_text(json.dumps(rec, indent=2))


def client_env(ctx):
    """Env for ads_manager subprocesses — per-client login (MCC or self)."""
    env = dict(os.environ)
    env["GOOGLE_ADS_MCC_CUSTOMER_ID"] = ctx["login_customer_id"]
    return env


def run_cmd(args, env=None, cwd=None):
    """Run a pipeline command; raise with captured output on failure."""
    res = subprocess.run([sys.executable, "-u"] + args, cwd=str(cwd or WORK_ROOT),
                         env=env or os.environ.copy(), capture_output=True, text=True)
    if res.returncode != 0:
        tail = (res.stdout or "")[-1500:] + "\n" + (res.stderr or "")[-1500:]
        raise RuntimeError(f"Command failed ({' '.join(args[:3])}…): {tail}")
    return res.stdout


def am(ctx, *cmd_args):
    """Invoke scripts/ads_manager.py <cmd_args> with this client's auth env."""
    return run_cmd([str(SCRIPTS / "ads_manager.py")] + list(cmd_args), env=client_env(ctx))


# ---------------------------------------------------------------------------
# Phase helpers that aren't ads_manager commands
# ---------------------------------------------------------------------------
def load_structure(slug):
    p = CLIENTS / slug / "ads-structure.json"
    return json.loads(p.read_text()) if p.exists() else {"campaigns": {}, "ad_groups": {}}


def gen_lp_manifest(ctx, services):
    """Build the /lp/ manifest (config-driven body content). One page per
    service×city + service×intent. Champion variant v2."""
    sys.path.insert(0, str(SCRIPTS))
    import ads_manager as M
    slug = ctx["slug"]
    plan = json.loads((CLIENTS / slug / "plan-input.json").read_text())
    cfg = M.load_industry_config(plan.get("template", "general"))
    body_cfg = cfg.get("lp_body_content", {})
    areas = plan.get("service_areas", [])
    domain = ctx["domain"]

    HERO = {"city": "Trusted Cleanup & Recovery Experts — Available Day or Night",
            "cost": "Upfront Pricing · Free On-Site Estimate · No Hidden Fees",
            "company": "IICRC Certified · Licensed & Insured · Local Experts",
            "free-estimate": "Free On-Site Assessment · No Obligation",
            "insurance": "We Bill Your Insurer Directly · All Major Carriers Accepted",
            "removal": "Certified Removal · Professionally Documented"}
    HERO.update({"near-me": HERO["city"], "emergency": HERO["city"]})
    H1 = {"near-me": "{s} Near You", "emergency": "Emergency {s}", "cost": "{s} Cost",
          "company": "{s} Company", "free-estimate": "Free {s} Estimate",
          "insurance": "{s} Insurance Claims", "removal": "{s} Removal"}
    INTENTS = ["near-me", "emergency", "cost", "company", "free-estimate", "insurance", "removal"]

    def body(intent, label):
        src = body_cfg.get("city" if intent in ("near-me", "emergency") else intent) or body_cfg.get("city", {})
        sub = lambda x: (x or "").replace("{service}", label)
        return {"heading": sub(src.get("heading", "")), "intro": sub(src.get("intro", "")),
                "bullets": [sub(b) for b in src.get("bullets", [])],
                "callout": sub(src.get("callout", ""))}

    # optional imagery (only if files exist)
    img_dir = SITES / slug / "public" / "images" / "lp"
    images = {}
    for key, fname in [("heroImageUrl", "hero-flood-clean.png"), ("featureImageUrl", "feature-van.png"),
                       ("supportImageUrl", "support-airmover.png"), ("closingImageUrl", "closing-restored.png")]:
        if (img_dir / fname).exists():
            images[key] = f"/images/lp/{fname}"

    manifest = []
    for s in services:
        sslug = s["slug"] if isinstance(s, dict) else s
        label = M.get_service_label(sslug, cfg)
        for a in areas:
            city, st = a.get("city", ""), a.get("state", "")
            manifest.append({"slug": f"{sslug}-{a.get('slug')}", "variant": "v2", "serviceLabel": label,
                             "city": city, "state": st, "intent": "city",
                             "h1": f"{label} in {city}, {st}",
                             "metaTitle": f"{label} in {city}, {st} | 24/7 Emergency Response",
                             "metaDescription": f"Fast, licensed {label.lower()} in {city}, {st}. 24/7 response, insurance billing, free assessment. Call now.",
                             "heroSubtitle": HERO["city"], **images, "bodyContent": body("city", label)})
        for intent in INTENTS:
            h1 = H1[intent].format(s=label)
            manifest.append({"slug": f"{sslug}-{intent}", "variant": "v2", "serviceLabel": label,
                             "city": None, "state": None, "intent": intent, "h1": h1,
                             "metaTitle": f"{h1} | {HERO[intent]}"[:80],
                             "metaDescription": f"{h1} — licensed, IICRC-certified, 24/7 response across the metro. Call now."[:155],
                             "heroSubtitle": HERO[intent], **images, "bodyContent": body(intent, label)})

    out = SITES / slug / "src" / "data" / "lp-manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2))
    log.info(f"  wrote {len(manifest)} LP manifest entries")
    return manifest


def patch_brand(slug, fields):
    """Insert key:value lines into brand.ts after phoneRaw (idempotent)."""
    bp = SITES / slug / "src" / "lib" / "brand.ts"
    text = bp.read_text()
    lines = []
    for k, v in fields.items():
        if f"{k}:" in text:
            continue  # already present
        lines.append(f'  {k}: "{v}",')
    if not lines:
        return
    anchor = [l for l in text.splitlines() if "phoneRaw:" in l]
    if not anchor:
        raise RuntimeError("brand.ts has no phoneRaw anchor")
    text = text.replace(anchor[0], anchor[0] + "\n" + "\n".join(lines), 1)
    bp.write_text(text)


def provision_twilio(ctx, forward_to, area_codes, record):
    """Idempotent: reuse the recorded number if present, else search+buy a local
    number in the client's subaccount and point its voice webhook at the site fn."""
    slug = ctx["slug"]
    ct_path = CLIENTS / slug / "ads" / "call-tracking.json"
    if ct_path.exists():
        existing = json.loads(ct_path.read_text())
        log.info(f"  reusing tracking number {existing.get('tracking_number')}")
        return existing
    sid, token = ctx["twilio_sid"], ctx["twilio_token"]
    if not sid or not token:
        raise RuntimeError("No Twilio subaccount creds in company_phone_setup")
    auth = base64.b64encode(f"{sid}:{token}".encode()).decode()

    def tw(method, path, data=None):
        body = urllib.parse.urlencode(data).encode() if data else None
        req = urllib.request.Request(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/{path}",
                                     data=body, headers={"Authorization": f"Basic {auth}"}, method=method)
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read().decode())

    chosen = None
    for ac in area_codes:
        res = tw("GET", f"AvailablePhoneNumbers/US/Local.json?{urllib.parse.urlencode({'AreaCode': ac, 'VoiceEnabled': 'true'})}")
        nums = res.get("available_phone_numbers", [])
        if nums:
            chosen = nums[0]["phone_number"]
            break
    if not chosen:
        raise RuntimeError(f"No available numbers in area codes {area_codes}")

    bought = tw("POST", "IncomingPhoneNumbers.json", {
        "PhoneNumber": chosen, "VoiceUrl": f"https://{ctx['domain']}/twilio/voice",
        "VoiceMethod": "POST", "FriendlyName": f"{slug} · LP tracking (Google Ads)"})

    # Write the Cloudflare Pages voice function
    fn = SITES / slug / "functions" / "twilio" / "voice.ts"
    fn.parent.mkdir(parents=True, exist_ok=True)
    # Supabase Edge Function that logs the call + recording into marketing_ads_calls.
    status_cb = os.environ.get("ADS_TWILIO_STATUS_CALLBACK",
                              "https://nyscciinkhlutvqkgyvq.supabase.co/functions/v1/twilio-status-callback")
    fn.write_text(
        f'// Twilio Voice webhook — forwards the tracking number to the business line.\n'
        f'// Generated by ads_provision.py.{" RECORDING ON — add a WA two-party-consent caller notice before production." if record else ""}\n'
        f'const FORWARD_TO = "{forward_to}";\n'
        f'const RECORD = {"true" if record else "false"};\n'
        f'const STATUS_CALLBACK = "{status_cb}";\n'
        f'const handler: PagesFunction = () => {{\n'
        f'  const rec = RECORD\n'
        f'    ? ` record="record-from-answer" recordingStatusCallback="${{STATUS_CALLBACK}}"` +\n'
        f'      ` recordingStatusCallbackEvent="completed" recordingStatusCallbackMethod="POST"`\n'
        f'    : "";\n'
        f'  const twiml = `<?xml version="1.0" encoding="UTF-8"?>` +\n'
        f'    `<Response><Dial${{rec}} answerOnBridge="true"><Number>{forward_to}</Number></Dial></Response>`;\n'
        f'  return new Response(twiml, {{ headers: {{ "Content-Type": "text/xml" }} }});\n'
        f'}};\n'
        f'export const onRequestPost = handler;\nexport const onRequestGet = handler;\n')

    ct = {"subaccount_sid": sid, "tracking_number": bought["phone_number"],
          "tracking_number_sid": bought["sid"], "forward_to": forward_to,
          "voice_webhook_url": f"https://{ctx['domain']}/twilio/voice", "recording": record}
    ct_path.parent.mkdir(parents=True, exist_ok=True)
    ct_path.write_text(json.dumps(ct, indent=2))
    log.info(f"  provisioned tracking number {bought['phone_number']}")
    return ct


def git_deploy(ctx, message):
    """Commit the generated site/client files, then subtree-push to the per-client
    repo (→ Cloudflare build). In cloud mode also push the monorepo so the generated
    source (manifest, brand.ts, voice.ts) persists beyond the ephemeral clone."""
    slug = ctx["slug"]
    root = str(WORK_ROOT)
    subprocess.run(["git", "add", f"sites/{slug}", f"clients/{slug}"], cwd=root, check=False)
    # commit returns non-zero if nothing changed — that's fine
    subprocess.run(["git", "commit", "-q", "-m", message], cwd=root, check=False)
    if cloud_mode():
        # sync with origin, then persist the generated source upstream
        subprocess.run(["git", "pull", "--rebase", "--autostash", "origin", "main"], cwd=root, check=True)
        subprocess.run(["git", "push", "origin", "main"], cwd=root, check=True)
    # subtree-split + force-push sites/{slug} → the per-client deploy repo (Cloudflare builds it)
    run_cmd([str(SCRIPTS / "build_site.py"), "sync-deploy", "--slug", slug,
             "--branch", "main", "--allow-dirty"])


# ---------------------------------------------------------------------------
# Job handlers
# ---------------------------------------------------------------------------
def run_full_launch(job, ctx):
    payload = job.get("payload") or {}
    slug = ctx["slug"]
    job_id = job["id"]
    services = payload.get("services") or []
    service_slugs = ",".join(s["slug"] if isinstance(s, dict) else s for s in services)
    if not service_slugs:
        raise RuntimeError("payload.services is empty")
    camp = payload.get("campaign", {})
    daily_budget = camp.get("daily_budget", 50)
    lead_value = camp.get("lead_value", 300)
    ct = payload.get("call_tracking", {})

    write_auth_shim(ctx)

    # Phase 1 — campaign structure + RSAs + budgets
    set_phase(job_id, "Phase 1 · Campaigns", 15)
    am(ctx, "scaffold", "--slug", slug, "--services", service_slugs)
    am(ctx, "backfill-rsas", "--slug", slug)
    struct = load_structure(slug)
    for ckey, c in struct.get("campaigns", {}).items():
        am(ctx, "set-budget", "--slug", slug, "--campaign", c["resource_name"],
           "--daily-budget", str(daily_budget))

    # Phase 2 — angle RSAs
    set_phase(job_id, "Phase 2 · RSAs", 30)
    am(ctx, "angle-rsas", "--slug", slug)

    # Phase 3 — negatives
    set_phase(job_id, "Phase 3 · Negatives", 40)
    am(ctx, "apply-negatives", "--slug", slug)

    # Phase 4 — landing pages
    set_phase(job_id, "Phase 4 · Landing pages", 60)
    gen_lp_manifest(ctx, services)
    git_deploy(ctx, f"feat({slug}): ad landing pages [automated launch]")
    am(ctx, "update-final-urls", "--slug", slug)

    # Phase 5 — click-to-call conversion
    set_phase(job_id, "Phase 5 · Conversion tracking", 78)
    am(ctx, "create-conversion", "--slug", slug, "--value", str(lead_value))
    conv = json.loads((CLIENTS / slug / "ads" / "conversion.json").read_text())
    patch_brand(slug, {"gadsId": conv["gads_id"], "gadsCallConversionLabel": conv["conversion_label"]})

    # Phase 6 — Twilio call tracking
    set_phase(job_id, "Phase 6 · Call tracking", 90)
    forward_to = ct.get("forward_to")
    if forward_to:
        # local-looking area codes near the client (fallback chain)
        plan = json.loads((CLIENTS / slug / "plan-input.json").read_text())
        ac = []
        for a in plan.get("service_areas", []):
            pass  # area-code inference is region-specific; use the provided list or business AC
        area_codes = payload.get("area_codes") or ["253", "206", "425", "360"]
        tw = provision_twilio(ctx, forward_to, area_codes, ct.get("recording_enabled", True))
        patch_brand(slug, {"adsTrackingPhone": _fmt(tw["tracking_number"]),
                            "adsTrackingPhoneRaw": tw["tracking_number"]})
        sb_post("marketing_ads_call_tracking", {
            "company_id": ctx["company_id"], "rank_ai_slug": slug,
            "phone_number": tw["tracking_number"], "forward_to": forward_to,
            "forward_type": ct.get("forward_type", "pstn"),
            "recording_enabled": ct.get("recording_enabled", True), "source": "google_ads",
            "voice_webhook_url": tw["voice_webhook_url"],
            "gads_conversion_label": conv["conversion_label"], "status": "active"})

    git_deploy(ctx, f"feat({slug}): wire conversion + call tracking [automated launch]")

    set_phase(job_id, "Built — awaiting review", 100)
    update_job(job_id, status="needs_review",
               result={"campaigns": len(struct.get("campaigns", {})),
                       "ad_groups": len(struct.get("ad_groups", {})),
                       "tracking_number": (ct.get("forward_to") and tw.get("tracking_number")) or None,
                       "conversion_label": conv["conversion_label"]})
    log.info(f"Job {job_id} ({slug}) built — needs_review (all PAUSED)")


def run_go_live(job, ctx):
    """Enable all paused campaigns for the client, mark the launch job live."""
    slug = ctx["slug"]
    struct = load_structure(slug)
    for ckey, c in struct.get("campaigns", {}).items():
        am(ctx, "enable", "--slug", slug, "--resource", c["resource_name"])
    parent = (job.get("payload") or {}).get("launch_job_id") or job.get("parent_job_id")
    if parent:
        update_job(parent, status="live")
    update_job(job["id"], status="live", phase="Campaigns enabled", progress=100)
    log.info(f"Job {job['id']} ({slug}) — campaigns ENABLED, live")


def _fmt(e164):
    d = e164.lstrip("+")
    if len(d) == 11 and d.startswith("1"):
        d = d[1:]
    return f"({d[:3]}) {d[3:6]}-{d[6:]}" if len(d) == 10 else e164


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def claim_next_job():
    jobs = sb_get("marketing_ads_jobs?status=eq.queued&order=created_at.asc&limit=1"
                  "&select=id,company_id,rank_ai_slug,job_type,payload,parent_job_id")
    if not jobs:
        return None
    job = jobs[0]
    # optimistic claim
    sb_patch(f"marketing_ads_jobs?id=eq.{job['id']}&status=eq.queued",
             {"status": "running", "progress": 5})
    return job


def process_one():
    job = claim_next_job()
    if not job:
        return False
    job_id = job["id"]
    log.info(f"Processing job {job_id} type={job.get('job_type')} company={job.get('company_id')}")
    try:
        ensure_work_repo()  # cloud: fresh clone w/ history+creds for git deploys; no-op locally
        ctx = resolve_client(job["company_id"])
        if job.get("job_type") == "go_live":
            run_go_live(job, ctx)
        else:
            run_full_launch(job, ctx)
    except Exception as e:
        log.error(f"Job {job_id} FAILED: {e}")
        update_job(job_id, status="failed", error=str(e)[:4000])
        log.error(traceback.format_exc())
    return True


def main():
    ap = argparse.ArgumentParser(description="Rank AI — Google Ads provisioning worker")
    ap.add_argument("--once", action="store_true", help="process one queued job then exit (cron)")
    ap.add_argument("--loop", action="store_true", help="poll forever (worker service)")
    ap.add_argument("--interval", type=int, default=30, help="poll seconds in --loop mode")
    args = ap.parse_args()

    if args.loop:
        log.info("ads_provision worker started (loop mode)")
        while True:
            try:
                worked = process_one()
            except Exception as e:
                log.error(f"poll error: {e}")
                worked = False
            if not worked:
                time.sleep(args.interval)
    else:
        log.info("ads_provision worker — single pass")
        did = process_one()
        log.info("No queued jobs." if not did else "Done.")


if __name__ == "__main__":
    main()
