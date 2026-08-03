#!/usr/bin/env python3
"""Setup ledger — the overseer (Santino 2026-07-28: "no client should ever get
left behind"). For every ACTIVE client on the Rank AI plan (other plans are
deliberately ignored), derive the setup state from the systems themselves —
never from someone having marked a box — and route every gap:

  us_owed      -> Santino's attention list (nightly ops email + app
                  SuperadminDashboard reads marketing_setup_ledger)
  client_owed  -> Monica already owns these via the checklist/ask passes;
                  the ledger just aggregates counts for the app + the
                  escalation ladder
  auto         -> the ledger FIXES it itself (GSC registration + IndexNow
                  for live sites)

Items:
  site-built      preview site exists in sites/{slug} (CRITICAL when the
                  kickoff call is within 3 days or already past)
  site-live       the client's real domain serves our site; if WE control
                  the zone and the site is built but not live, the detail
                  says LAUNCH NOW (own-domain policy, PuroClean 2026-07-28)
  domain-access   built + domain known + zone not ours + not live ->
                  client-owed registrar-access ask
  gsc-indexnow    live site registered in Search Console + IndexNow-pinged
                  (auto-heals: runs gsc_register + indexnow once, marks done)
  google-connected  reflects user_integrations state (ask pass owns nudges)
  client-asks     open client_input count + no-reply streak (ladder input)

Run:  python3 scripts/setup_ledger.py [--dry-run]
Wired into client_ops_sync's nightly pass via ensure_ledger().
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CLIENTS_DIR = ROOT / "clients"
SITES_DIR = ROOT / "sites"
sys.path.insert(0, str(ROOT / "scripts"))

from client_ops_sync import _sb, slug_map  # noqa: E402


def _norm_domain(d: str | None) -> str:
    d = (d or "").strip().lower()
    d = re.sub(r"^https?://", "", d).strip("/ ")
    return d[4:] if d.startswith("www.") else d


def _client_record(slug: str) -> dict:
    p = CLIENTS_DIR / f"{slug}.json"
    try:
        return json.loads(p.read_text()) if p.exists() else {}
    except json.JSONDecodeError:
        return {}


def _our_zones() -> dict[str, str]:
    """{domain: zone_status} for zones on our Cloudflare account. status
    'active' = NS actually point at us (launchable); 'pending' = zone created
    but the registrar cutover hasn't happened (crew3r 2026-07-28)."""
    tok = os.environ.get("CLOUDFLARE_API_TOKEN")
    if not tok:
        return {}
    out: dict[str, str] = {}
    page = 1
    try:
        while True:
            r = requests.get("https://api.cloudflare.com/client/v4/zones",
                             headers={"Authorization": f"Bearer {tok}"},
                             params={"per_page": 50, "page": page}, timeout=30)
            body = r.json()
            for z in body.get("result") or []:
                out[z["name"].lower()] = z.get("status") or "?"
            if page >= (body.get("result_info") or {}).get("total_pages", 1):
                break
            page += 1
    except Exception:
        pass
    return out


# ---- domain-access state machine (Santino 2026-08-03) ----------------------
# none -> promised -> delegate_granted | creds_provided -> ns_live
# State lives on marketing_sites (domain_access_status + registrar/email/
# timestamps). Writers: the app's Site tab "Provide Domain Access" card sets
# promised (client claim) and creds_provided (encrypted creds via the
# domain-access edge fn); THIS ledger sets delegate_granted (executing the
# Ops Attention "Delegate access confirmed" click, marketing_ops_notes
# pattern like APPROVE-PHONE-SWAP) and ns_live (the existing Cloudflare
# zone check — zone active == NS point at us).
_DA_STATES = ("none", "promised", "delegate_granted", "creds_provided", "ns_live")

# NS-suffix -> registrar guess, precomputed here (not an edge fn) so the app
# dropdown can pre-select without a live lookup. Suffix match on `dig NS`.
_REGISTRAR_NS = {
    "domaincontrol.com": "godaddy",
    "registrar-servers.com": "namecheap",
    "ionos.com": "ionos", "ionos.de": "ionos", "ui-dns.com": "ionos",
    "ui-dns.de": "ionos", "ui-dns.org": "ionos", "ui-dns.biz": "ionos",
    "bluehost.com": "bluehost",
    "hostgator.com": "hostgator", "websitewelcome.com": "hostgator",
    "squarespacedns.com": "squarespace", "googledomains.com": "squarespace",
    "wixdns.net": "wix",
    "cloudflare.com": "cloudflare",
    "worldnic.com": "networksolutions", "register.com": "networksolutions",
    "name-services.com": "enom", "enom.com": "enom",
    "hover.com": "hover",
    "dreamhost.com": "dreamhost",
    "wordpress.com": "wordpress",
    "dns-parking.com": "hostinger", "hostinger.com": "hostinger",
    "inmotionhosting.com": "inmotion",
    # observed in our own client fleet (2026-08-03 backfill)
    "monikerdns.net": "moniker",              # prorestorationca.com
    "hostmonster.com": "bluehost",            # QCI — HostMonster = Bluehost family,
                                              # matches portal-creds "bluehost:{slug}"
}


def _registrar_guess(domain: str) -> str | None:
    """Guess the registrar from the domain's live NS records (dig)."""
    try:
        out = subprocess.run(["dig", "+short", "NS", domain],
                             capture_output=True, text=True, timeout=20).stdout
    except Exception:
        return None
    for line in out.splitlines():
        ns = line.strip().rstrip(".").lower()
        if ".awsdns-" in ns:   # Route53 suffixes vary by TLD (.com/.net/.co.uk)
            return "route53"
        for suffix, reg in _REGISTRAR_NS.items():
            if ns.endswith(suffix):
                return reg
    return None


def _domain_access_row(cid: str) -> dict | None:
    """The marketing_sites domain-access columns for this company (or None
    when no marketing_sites row exists yet — nothing to track)."""
    try:
        rows = _sb("GET", f"/rest/v1/marketing_sites?company_id=eq.{cid}"
                   "&select=id,domain_access_status,domain_registrar,"
                   "domain_registrar_guess,domain_account_email,"
                   "domain_access_domain,domain_access_promised_at,"
                   "domain_access_granted_at,domain_ns_live_at&limit=1",
                   prefer="return=representation") or []
        return rows[0] if rows else None
    except Exception:
        return None


# Human-readable ledger detail per state (the app renders this verbatim).
def _da_detail(status: str, domain: str, da: dict) -> str | None:
    reg = da.get("domain_registrar") or da.get("domain_registrar_guess") or "?"
    email = da.get("domain_account_email") or "unknown account email"
    if status == "none":
        return ("We can't launch their site until we can get into their "
                "domain registrar. Monica is asking; the app's Site tab also "
                "shows them a 'Provide Domain Access' card "
                f"(registrar guess: {reg}).")
    if status == "promised":
        return ("Client SAYS access was provided "
                f"(registrar {reg}, account {email}) — a claim, not evidence. "
                "Check the setup@restorationai.io inbox for the delegate "
                "invite, then hit 'Delegate access confirmed' below. Monica "
                "is on a gentle verify nudge meanwhile.")
    if status == "delegate_granted":
        return ("Delegate access CONFIRMED — nothing more from the client. "
                f"Run the NS cutover for {domain} (browser_agent "
                "domain_connect playbook, email-safe rule applies).")
    if status == "creds_provided":
        return ("Client submitted registrar credentials through the encrypted "
                "path. Run scripts/domain_creds_sync.py on the ops Mac to "
                "decrypt them into the browser agent's portal-creds, then do "
                f"the NS cutover for {domain} (email-safe rule applies).")
    return None


def _site_serves_us(domain: str, brand_name: str) -> bool:
    """True only when the domain serves OUR build. Brand-name matching is
    useless here — the client's OLD site obviously contains their name
    (crew3r.com false-positived) — so require our own markers."""
    del brand_name
    try:
        r = requests.get(f"https://{domain}/", timeout=20,
                         headers={"User-Agent": "Mozilla/5.0 (rank-ai ledger)"})
        if r.status_code != 200:
            return False
        # every Astro build links /_astro/ asset bundles; old WP sites never do
        return "/_astro/" in r.text or "/images/logo" in r.text
    except Exception:
        return False


def _upcoming_kickoff(ints: dict) -> str | None:
    """ISO start time of a future kickoff appointment, else None."""
    gcid = ints.get("ghl_contact_id")
    key = os.environ.get("GHL_API_KEY")
    if not (gcid and key):
        return None
    try:
        r = requests.get(
            f"https://services.leadconnectorhq.com/contacts/{gcid}/appointments",
            headers={"Authorization": f"Bearer {key}", "Version": "2021-07-28",
                     "User-Agent": "Mozilla/5.0 (rank-ai ops)"}, timeout=20)
        for ev in r.json().get("events") or []:
            if "kickoff" not in (ev.get("title") or "").lower():
                continue
            try:
                t = datetime.strptime(ev.get("startTime", "")[:19], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
            if t > datetime.now() - timedelta(hours=12):
                return ev.get("startTime")
    except Exception:
        pass
    return None


# ---- citations-build per-platform status (Santino 2026-08-02) --------------
# The app renders the "Create listings we own" card as a checklist straight
# from evidence.platform_status (title stays untouched for backward compat):
#   live              -> checked/strikethrough (NAP audit found the listing)
#   submitted_pending -> half-state (browser agent completed the create/submit
#                        but the directory hasn't published it / the audit
#                        hasn't re-found it yet)
#   todo              -> empty checkbox
# Porch stays excluded (self-serve pro signup killed upstream, 2026-08-02).
_US_CREATE_PLATFORMS = ("bing_places", "apple_maps", "bbb", "expertise",
                        "houzz", "homeguide")
_PS_LABEL = {"live": "live",
             "submitted_pending": "created — pending publish",
             "todo": "not started"}
# browser_agent_actions outcomes that mean "the create actually went through"
# (recon_done / review_needed / deferred_* / needs_* never count).
_SUBMITTED_OUTCOMES = ("done", "done_public", "exists", "already_exists")


def _bing_sweep_rows() -> list[dict]:
    """Agency-account Bing sweep rows (company_id NULL). The 2026-08-01 GBP
    import ran as ONE batch on the agency Google account, so per-client
    attribution lives only in the row detail ('...FF, ProRestoration, RX,
    NaRestCo, Home Pride[published]')."""
    try:
        return _sb("GET", "/rest/v1/browser_agent_actions"
                   "?playbook=eq.bing-places&company_id=is.null&live=is.true"
                   "&outcome=in.(done,done_public,exists,already_exists,"
                   "live_write_unintended)&select=detail,meta",
                   prefer="return=representation") or []
    except Exception:
        return []


def _sweep_mentions_client(sweep_rows: list[dict], name: str, slug: str) -> bool:
    """True when a batch sweep row's detail/meta names this client — by slug,
    leading name words, or initials (the batch log abbreviates: FF = Flood
    Fixers, RX = RestorationXpress)."""
    name = (name or "").strip()
    words = [w for w in re.split(r"[^A-Za-z0-9]+", name) if w]
    parts: list[str] = []
    for w in words:  # CamelCase-aware: "RestorationXpress" -> Restoration, Xpress
        parts += re.findall(r"[A-Z][a-z0-9]*|[A-Z]+(?![a-z])", w) or [w]
    initials = "".join(p[0].upper() for p in parts if p)
    prefix2 = " ".join(words[:2]).lower()
    for r_ in sweep_rows:
        text = f"{r_.get('detail') or ''} {json.dumps(r_.get('meta') or {})}"
        low = text.lower()
        if slug and len(slug) >= 4 and slug in low:
            return True
        if len(prefix2) >= 8 and prefix2 in low:
            return True
        if len(initials) >= 2 and re.search(rf"\b{initials}\b", text):
            return True
    return False


def _agent_submitted_platforms(cid: str, name: str, slug: str,
                               bing_sweep: list[dict]) -> set[str]:
    """us-create platforms where browser_agent_actions shows a completed
    create/submit for this company (action names look like 'houzz-create',
    'create-listing' under a platform playbook, ...). Bing additionally
    counts when the agency-account batch sweep touched this client."""
    subs: set[str] = set()
    try:
        acts = _sb("GET", f"/rest/v1/browser_agent_actions?company_id=eq.{cid}"
                   "&live=is.true&select=playbook,action,outcome",
                   prefer="return=representation") or []
    except Exception:
        acts = []
    for a in acts:
        if (a.get("outcome") or "") not in _SUBMITTED_OUTCOMES:
            continue
        blob = f"{a.get('playbook') or ''} {a.get('action') or ''}".lower()
        for plat in _US_CREATE_PLATFORMS:
            if plat.split("_")[0] in blob:  # bing / apple / bbb / houzz / ...
                subs.add(plat)
    if "bing_places" not in subs and _sweep_mentions_client(bing_sweep, name, slug):
        subs.add("bing_places")
    return subs


def _upsert(rows: list[dict], dry_run: bool) -> None:
    """Upsert ledger rows, stamping done_at ONLY on the open->done TRANSITION.

    done_at (added 2026-08-02) is the milestone timestamp work_report.py
    renders ("Your website went live on ..."). The nightly sweep re-stamps
    updated_at on EVERY pass — that is exactly the bug that made flip times
    unrecoverable — so done_at must be: preserved verbatim while a row stays
    done, set to now() only when it transitions into done, cleared when a
    row reopens. If the pre-read of current state fails, ship WITHOUT
    done_at (never risk overwriting a real flip time with a guess)."""
    if not rows or dry_run:
        return
    now = datetime.now(timezone.utc).isoformat()
    try:
        cur: dict[tuple[str, str], dict] = {}
        for cid in {r["company_id"] for r in rows}:
            keys = ",".join(sorted({r["item_key"] for r in rows
                                    if r["company_id"] == cid}))
            for c in _sb("GET", "/rest/v1/marketing_setup_ledger"
                         f"?company_id=eq.{cid}&item_key=in.({keys})"
                         "&select=item_key,status,done_at",
                         prefer="return=representation") or []:
                cur[(cid, c["item_key"])] = c
        for r in rows:
            prev = cur.get((r["company_id"], r["item_key"])) or {}
            if r.get("status") == "done":
                # already done with a stamp -> keep it (write-back of the
                # same value, never a re-stamp); fresh transition -> now()
                r["done_at"] = (prev.get("done_at")
                                if prev.get("status") == "done"
                                and prev.get("done_at") else now)
            else:
                r["done_at"] = None  # reopened -> the old milestone is void
    except Exception:
        # PostgREST bulk upsert needs uniform keys — drop done_at everywhere
        for r in rows:
            r.pop("done_at", None)
    for r in rows:
        r["updated_at"] = now
    _sb("POST", "/rest/v1/marketing_setup_ledger?on_conflict=company_id,item_key",
        rows, prefer="resolution=merge-duplicates")


def _gsc_heal(domain: str, slug: str) -> str:
    """Idempotent GSC registration + IndexNow for a live domain."""
    msgs = []
    try:
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "gsc_register.py"),
                            "--domain", domain], capture_output=True, text=True, timeout=300)
        msgs.append("gsc:" + ("ok" if "VERIFIED" in (r.stdout + r.stderr) or "already" in
                              (r.stdout + r.stderr).lower() else "check"))
    except Exception as e:
        msgs.append(f"gsc:err {str(e)[:40]}")
    try:
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_site.py"),
                            "indexnow", "--slug", slug], capture_output=True, text=True, timeout=180)
        msgs.append("indexnow:" + ("ok" if "202" in r.stdout or "200" in r.stdout else "check"))
    except Exception as e:
        msgs.append(f"indexnow:err {str(e)[:40]}")
    return " ".join(msgs)


def _check_doc_uploads(cid: str, name: str, dry_run: bool) -> None:
    """Client hub document uploads -> a [TODO-SANTINO] note that persists in
    Today until dismissed (Santino 2026-07-31: Curt's Home Pride insurance
    PDF sat unseen in storage for a day because nothing announced it).
    Seen-state lives in ops_kv 'docs-seen' so each file alerts exactly once."""
    sb_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    r = requests.post(f"{os.environ['SUPABASE_URL']}/storage/v1/object/list/branding",
                      headers={"apikey": sb_key, "Authorization": f"Bearer {sb_key}",
                               "Content-Type": "application/json"},
                      json={"prefix": f"{cid}/docs/", "limit": 100}, timeout=30)
    if not r.ok:
        return
    paths: list[str] = []
    for folder in [f.get("name") for f in r.json() if f.get("name")]:
        rf = requests.post(f"{os.environ['SUPABASE_URL']}/storage/v1/object/list/branding",
                           headers={"apikey": sb_key, "Authorization": f"Bearer {sb_key}",
                                    "Content-Type": "application/json"},
                           json={"prefix": f"{cid}/docs/{folder}/", "limit": 100}, timeout=30)
        if rf.ok:
            paths += [f"{folder}/{f['name']}" for f in rf.json() if f.get("name")]
    if not paths:
        return
    seen_rows = _sb("GET", "/rest/v1/ops_kv?k=eq.docs-seen&select=v") or []
    seen = set((seen_rows[0].get("v") or []) if seen_rows else [])
    new = [p for p in paths if f"{cid}/{p}" not in seen]
    if not new:
        return
    # De-duplicate retry uploads of the same document (timestamp prefixes vary)
    base = sorted({re.sub(r"^\d+-", "", p.split("/")[-1]) for p in new})
    if not dry_run:
        _sb("POST", "/rest/v1/marketing_ops_notes", [{
            "company_id": cid,
            "body": f"[TODO-SANTINO] {name} uploaded {len(base)} document(s) via "
                    f"their hub link: {', '.join(base)[:200]} — stored under "
                    f"docs/{new[0].split('/')[0]}. Review and use it, then hit Done."}])
        seen.update(f"{cid}/{p}" for p in new)
        _sb("POST", "/rest/v1/ops_kv?on_conflict=k",
            {"k": "docs-seen", "v": sorted(seen)},
            prefer="resolution=merge-duplicates,return=minimal")
    print(f"  [{cid}] new client document upload(s): {', '.join(base)[:120]}")


def ensure_ledger(dry_run: bool, cid_to_slug: dict | None = None) -> list[str]:
    """Evaluate the ledger for every Active Rank AI client. Returns attention
    lines (us-owed gaps) for the nightly ops email."""
    cid_to_slug = cid_to_slug or slug_map()
    zones = _our_zones()
    cos = _sb("GET", "/rest/v1/companies?status=ilike.active&plan=eq.Rank%20AI"
              "&select=id,name,website,services,integration_settings",
              prefer="return=representation") or []
    attention: list[str] = []
    # per-run auto-heal budget: 2 geo-grid re-scans (DFS cost) + 3 media
    # imports + 3 tracking-number provisions + 3 GBP phone swaps
    _HEALS = {"geogrid": 2, "media": 3, "calltrack": 3, "swap": 3, "citations": 2}
    bing_sweep = _bing_sweep_rows()  # fetched once; reused per client

    for co in cos:
        cid = co["id"]
        slug = cid_to_slug.get(cid)
        if not slug:
            attention.append(f"(no slug) {co.get('name')}: not in slug map — bootstrap missing")
            continue
        ints = co.get("integration_settings") or {}
        if isinstance(ints, str):
            try:
                ints = json.loads(ints)
            except json.JSONDecodeError:
                ints = {}
        rows: list[dict] = []

        # ---- site-built --------------------------------------------------
        built = (SITES_DIR / slug / "src").exists()
        kickoff = None if built else _upcoming_kickoff(ints)
        detail = None
        if not built:
            detail = "No preview site exists."
            if kickoff:
                try:
                    days = (datetime.strptime(kickoff[:19], "%Y-%m-%d %H:%M:%S")
                            - datetime.now()).days
                    if days <= 3:
                        detail = (f"CRITICAL: kickoff {kickoff} is {max(days, 0)} day(s) away "
                                  "and NO preview site exists — build it before the call.")
                except ValueError:
                    pass
        rows.append({"company_id": cid, "item_key": "site-built", "kind": "us_owed",
                     "status": "done" if built else "open",
                     "title": "Preview site built",
                     "detail": detail,
                     "evidence": {"kickoff": kickoff, "site_dir": built}})
        if not built:
            attention.append(f"{slug}: SITE NOT BUILT" + (f" — {detail}" if detail and "CRITICAL" in detail else ""))

        # ---- site-live / domain-access ------------------------------------
        domain = _norm_domain(_client_record(slug).get("domain") or co.get("website"))
        live = False
        if domain and built:
            live = _site_serves_us(domain, co.get("name") or "")
        zstat = zones.get(domain, "") if domain else ""
        ours = zstat == "active"
        if not domain:
            rows.append({"company_id": cid, "item_key": "site-live", "kind": "us_owed",
                         "status": "blocked", "title": "Live on real domain",
                         "detail": "This client has no domain yet. Decide: buy one for them "
                         "(we launch the same day) or get access to one they already own.",
                         "evidence": {}})
            if built:
                attention.append(f"{slug}: site built, NO DOMAIN on file — decide buy vs client's registrar")
        else:
            d2 = None
            if not live and built:
                if ours:
                    d2 = ("Their domain is fully under our control — nothing is blocking "
                          "us from launching this site right now.")
                elif zstat == "pending":
                    d2 = ("Almost there: the domain is staged on our Cloudflare, but the "
                          "final switch happens at their registrar (GoDaddy etc.) — we "
                          "need their login or delegate access to flip it.")
                else:
                    d2 = ("Their domain lives in the client's own registrar account — we "
                          "need access to point it at the new site.")
            rows.append({"company_id": cid, "item_key": "site-live", "kind": "us_owed",
                         "status": "done" if live else ("open" if built else "blocked"),
                         "title": "Live on real domain", "detail": d2,
                         "evidence": {"domain": domain, "zone_status": zstat or "none"}})
            if built and not live:
                attention.append(f"{slug}: built but NOT LIVE on {domain} — "
                                 + ("LAUNCH NOW (zone active)" if ours else
                                    ("NS cutover pending (zone ready)" if zstat == "pending"
                                     else "needs domain access")))
            # ---- domain-access STATE MACHINE (2026-08-03) -------------------
            # none -> promised -> delegate_granted | creds_provided -> ns_live
            gap_open = bool(built and domain and not ours and not live)
            da = _domain_access_row(cid) or {}
            da_status = da.get("domain_access_status") or "none"
            try:
                patch: dict = {}
                if (ours or live) and da:
                    # ns_live auto-detect — the zone check we already run IS
                    # the evidence; no click, no claim, just the NS truth.
                    if da_status != "ns_live":
                        patch["domain_access_status"] = "ns_live"
                        patch["domain_ns_live_at"] = datetime.now(
                            timezone.utc).isoformat()
                        da_status = "ns_live"
                        attention.append(f"{slug}: domain access -> ns_live "
                                         "(zone active / site serves us)")
                elif gap_open and da:
                    # precompute the registrar guess for the app's dropdown
                    if (da.get("domain_access_domain") != domain
                            or not da.get("domain_registrar_guess")):
                        patch["domain_access_domain"] = domain
                        guess = _registrar_guess(domain)
                        if guess:
                            patch["domain_registrar_guess"] = guess
                    # Ops Attention "Delegate access confirmed" click executor
                    # (marketing_ops_notes pattern, same as APPROVE-PHONE-SWAP:
                    # no note -> nothing happens, ever).
                    if da_status not in ("delegate_granted", "ns_live"):
                        confirms = _sb(
                            "GET", "/rest/v1/marketing_ops_notes"
                            f"?company_id=eq.{cid}&status=eq.open"
                            "&body=like.*%5BDELEGATE-ACCESS-CONFIRMED%5D*"
                            "&select=id", prefer="return=representation") or []
                        if confirms and not dry_run:
                            patch["domain_access_status"] = "delegate_granted"
                            patch["domain_access_granted_at"] = datetime.now(
                                timezone.utc).isoformat()
                            da_status = "delegate_granted"
                            for cn in confirms:
                                _sb("PATCH", "/rest/v1/marketing_ops_notes"
                                    f"?id=eq.{cn['id']}",
                                    {"status": "resolved",
                                     "resolved_at": datetime.now(
                                         timezone.utc).isoformat()})
                            attention.append(f"{slug}: delegate access "
                                             "CONFIRMED (Ops Attention click) "
                                             "— ready for the NS cutover")
                if patch and da and not dry_run:
                    _sb("PATCH", f"/rest/v1/marketing_sites?id=eq.{da['id']}",
                        patch)
            except Exception as e:  # noqa: BLE001 — state upkeep must never kill the ledger
                attention.append(f"{slug}: domain-access state update failed "
                                 f"({str(e)[:80]})")
            # Ledger card renders FROM the state. none/promised = the client
            # owes us; delegate_granted/creds_provided = access is in hand and
            # the cutover is OUR move (us_owed, red).
            rows.append({"company_id": cid, "item_key": "domain-access",
                         "kind": ("us_owed" if da_status in
                                  ("delegate_granted", "creds_provided")
                                  else "client_owed"),
                         "status": "open" if gap_open else "done",
                         "title": {"none": "Registrar / domain access",
                                   "promised": "Domain access: client says it's "
                                               "provided — verify",
                                   "delegate_granted": "Domain access in hand "
                                                       "(delegate) — cut over NS",
                                   "creds_provided": "Domain access in hand "
                                                     "(credentials) — cut over NS",
                                   "ns_live": "Registrar / domain access",
                                   }.get(da_status, "Registrar / domain access"),
                         "detail": None if not gap_open else
                         _da_detail(da_status, domain, da),
                         "evidence": {"domain": domain,
                                      "zone_status": zstat or "none",
                                      "access_status": da_status,
                                      "registrar": da.get("domain_registrar"),
                                      "registrar_guess": da.get("domain_registrar_guess"),
                                      "account_email": da.get("domain_account_email")}})
            if gap_open and da_status in ("delegate_granted", "creds_provided"):
                attention.append(
                    f"{slug}: domain access in hand ({da_status}) — run the "
                    f"NS cutover for {domain}")
            # Monica actually asks via marketing_action_plan (gather_items),
            # NOT this ledger table — before 2026-08-03 the domain-access
            # ledger card claimed "Monica is asking them" while no
            # client_input row existed, so the ask never ranked anywhere
            # (Mold Solutionz: site built, cutover pending, and Andrea's
            # next draft led with the customer list). Seeding is now STATE-
            # GATED: none -> the rank-1 access ask; promised -> a verify
            # nudge ("did the invite go to setup@?"); any access-in-hand or
            # closed state -> both rows retired, Monica stops asking. Titles
            # contain "domain" so the concierge's ask_rank keeps them at
            # launch-blocker priority (1).
            try:
                from client_ops_sync import action_key, insert_plan_row
                seed = f"domain-access-{slug}"
                seed_verify = f"domain-verify-{slug}"

                def _retire_ask(key_seed: str) -> None:
                    if dry_run:
                        return
                    _sb("PATCH", "/rest/v1/marketing_action_plan"
                        f"?company_id=eq.{cid}"
                        f"&action_key=eq.{action_key(cid, key_seed)}"
                        "&status=eq.planned", {"status": "resolved"})

                if gap_open and da_status == "none":
                    _retire_ask(seed_verify)
                    if insert_plan_row(
                            cid, slug, seed,
                            title=f"ASK CLIENT: domain access — point {domain} "
                                  "at the finished site",
                            rationale=(
                                f"Their new website is BUILT and ready to go live on "
                                f"{domain}; the only thing missing is the final switch "
                                "at the place where they bought the domain (GoDaddy or "
                                "similar). MONICA: plain words only, never say "
                                "'registrar' or 'nameservers'. ONE question: where did "
                                "they buy the domain / where do they log in to manage "
                                "it? Then recommend a quick 15-minute call to do the "
                                "switch together on their phone or computer — we drive, "
                                "they just sign in; the current site keeps working the "
                                "whole time. This outranks every other ask, including "
                                "the customer list — the site cannot launch without it."),
                            action_type="client_input", target=domain,
                            impact="high", effort="low", dry_run=dry_run):
                        attention.append(f"{slug}: seeded Monica ask — domain "
                                         f"access for {domain}")
                elif gap_open and da_status == "promised":
                    _retire_ask(seed)
                    if insert_plan_row(
                            cid, slug, seed_verify,
                            title="ASK CLIENT: domain access follow-up — did "
                                  "the invite reach setup@restorationai.io?",
                            rationale=(
                                "The client SAYS they already provided access to "
                                f"the place that manages {domain}, but nothing has "
                                "landed on our side yet. MONICA: this is a gentle "
                                "verification, not a re-ask — never re-explain the "
                                "whole thing. ONE question on normal cooldown: did "
                                "the access invite go to setup@restorationai.io? "
                                "If they used a different email or aren't sure, "
                                "offer a quick 15-minute call to do it together. "
                                "Thank them for already acting on it."),
                            action_type="client_input", target=domain,
                            impact="high", effort="low", dry_run=dry_run):
                        attention.append(f"{slug}: seeded Monica VERIFY nudge — "
                                         f"domain access claimed for {domain}")
                else:
                    # gap closed, or access already in hand — stop asking
                    _retire_ask(seed)
                    _retire_ask(seed_verify)
            except Exception as e:  # noqa: BLE001 — seeding must never kill the ledger
                attention.append(f"{slug}: domain-access ask seeding failed "
                                 f"({str(e)[:80]})")

        # ---- gsc-indexnow (auto-heal once per live site) -------------------
        if live:
            existing = _sb("GET", "/rest/v1/marketing_setup_ledger"
                           f"?company_id=eq.{cid}&item_key=eq.gsc-indexnow&select=status",
                           prefer="return=representation") or []
            if not existing or existing[0].get("status") != "done":
                note = "dry-run" if dry_run else _gsc_heal(domain, slug)
                rows.append({"company_id": cid, "item_key": "gsc-indexnow", "kind": "auto",
                             "status": "done" if not dry_run else "open",
                             "title": "Search Console + IndexNow",
                             "detail": note, "evidence": {"domain": domain}})
                attention.append(f"{slug}: gsc/indexnow auto-heal -> {note}")

        # ---- google-connected (reflect only) -------------------------------
        gi = _sb("GET", f"/rest/v1/user_integrations?client_id=eq.{cid}"
                 "&provider=eq.google&select=id", prefer="return=representation") or []
        rows.append({"company_id": cid, "item_key": "google-connected", "kind": "client_owed",
                     "status": "done" if gi else "open",
                     "title": "Google connected" if gi else "Google NOT connected",
                     "detail": None if gi else
                     "The client hasn't connected their Google account yet, so we can't "
                     "manage their Business Profile, reviews, or rankings. Monica is "
                     "automatically texting them this link until it's done: "
                     f"https://restorationai.io/connect/{slug}",
                     "evidence": {}})

        # ---- gbp-verified (Voice of Merchant) --------------------------------
        # Why (2026-08-01): "connected" != "verified". QCI + Paul Davis sat
        # invisible to Bing's GBP import (and most GBP features) because their
        # listings are unverified, and nothing surfaced it as its own card —
        # QCI's verification video was even rejected 07-30. Go Green's
        # suspension also shows here (complyWithGuidelines). Distinct card so
        # verification gaps never hide inside the citations rollup.
        try:
            if gi:
                import gbp as _gbp
                _tok = _gbp.get_access_token(cid)
                _place = _gbp._place_id_from_connection(cid)
                _loc = _gbp.find_location(_tok, _place) if _tok and _place else None
                if _tok and _loc:
                    _ln = _loc["name"] if _loc["name"].startswith("locations/") \
                        else "locations/" + _loc["name"].split("locations/")[-1]
                    _vr = requests.get(
                        "https://mybusinessverifications.googleapis.com/v1/"
                        f"{_ln}/VoiceOfMerchantState",
                        headers={"Authorization": f"Bearer {_tok}"}, timeout=30)
                    if _vr.ok:
                        vom = _vr.json()
                        if vom.get("hasVoiceOfMerchant"):
                            rows.append({"company_id": cid, "item_key": "gbp-verified",
                                         "kind": "auto", "status": "done",
                                         "title": "Google Business Profile verified",
                                         "detail": None, "evidence": {}})
                        elif "complyWithGuidelines" in vom:
                            _why = (vom["complyWithGuidelines"] or {}).get(
                                "recommendationReason", "SUSPENDED")
                            rows.append({"company_id": cid, "item_key": "gbp-verified",
                                         "kind": "us_owed", "status": "open",
                                         "title": "GBP SUSPENDED — reinstatement "
                                                  "appeal needed",
                                         "detail": "Google disabled the listing "
                                                   f"({_why}). It is NOT publicly "
                                                   "visible; posts/photos/reviews all "
                                                   "blocked until reinstated. Appeal at "
                                                   "support.google.com/business — get "
                                                   "Google's suspension email from the "
                                                   "client first (date + violation).",
                                         "evidence": {"reason": _why}})
                            attention.append(f"{slug}: GBP SUSPENDED ({_why}) — "
                                             "reinstatement appeal needed")
                        else:
                            _pend = bool((vom.get("verify") or {})
                                         .get("hasPendingVerification"))
                            rows.append({"company_id": cid, "item_key": "gbp-verified",
                                         "kind": "client_owed", "status": "open",
                                         "title": "GBP NOT verified"
                                                  + (" — verification pending review"
                                                     if _pend else ""),
                                         "detail": "Google hasn't verified the listing, "
                                                   "so it's invisible on Maps and to "
                                                   "Bing's import. The OWNER completes "
                                                   "verification (usually a video walk-"
                                                   "through) at business.google.com — "
                                                   "Monica can walk them through it."
                                                   + (" A verification is already "
                                                      "submitted and awaiting Google."
                                                      if _pend else ""),
                                         "evidence": {"pending": _pend}})
        except Exception:
            pass

        # ---- client-asks aggregate (ladder input) ---------------------------
        asks = _sb("GET", "/rest/v1/marketing_action_plan"
                   f"?company_id=eq.{cid}&action_type=eq.client_input&status=eq.planned"
                   "&select=action_key,title", prefer="return=representation") or []
        ask_titles = [re.sub(r"^ASK (CLIENT: )?", "", (a.get("title") or "").strip())
                      for a in asks]
        rows.append({"company_id": cid, "item_key": "client-asks", "kind": "client_owed",
                     "status": "open" if asks else "done",
                     "title": (f"Waiting on {len(asks)} thing(s) from the client"
                               if asks else "Nothing outstanding from the client"),
                     "detail": ("They've stopped answering texts on this many items — "
                                "Monica's next message proposes a 15-minute call to knock "
                                "them all out at once, with a checklist picture attached."
                                if len(asks) >= 4 else None),
                     "evidence": {"count": len(asks), "titles": ask_titles[:10]}})
        if len(asks) >= 4:
            attention.append(f"{slug}: {len(asks)} open client asks — propose a setup call (ladder)")

        # ---- DATA FRESHNESS (Santino 2026-07-28: "I don't want to have to
        # always check every day"). The tabs must stay alive on their own:
        #   geo-grid   newest scan > 8 days old, imageless, or city config
        #              drifted (1 city configured vs 4+ service areas) ->
        #              AUTO re-scan (capped per run); config drift -> attention
        #   photos     google connected but no imported GBP media -> AUTO import
        # Heals are capped so one bad night can't burn budget.
        try:
            if (CLIENTS_DIR / slug / "geogrid-cities.json").exists():
                gg_cities = json.loads(
                    (CLIENTS_DIR / slug / "geogrid-cities.json").read_text())
                n_areas = len(json.loads((CLIENTS_DIR / slug / "plan-input.json")
                                         .read_text()).get("service_areas") or []) \
                    if (CLIENTS_DIR / slug / "plan-input.json").exists() else 0
                newest = _sb("GET", "/rest/v1/marketing_geogrid_scans"
                             f"?company_id=eq.{cid}&select=scanned_at,image_url"
                             "&order=scanned_at.desc&limit=1",
                             prefer="return=representation") or []
                age_days = 999
                has_img = False
                if newest:
                    try:
                        age_days = (datetime.now(timezone.utc) - datetime.fromisoformat(
                            newest[0]["scanned_at"].replace("Z", "+00:00"))).days
                    except (ValueError, KeyError):
                        pass
                    has_img = bool(newest[0].get("image_url"))
                drift = len(gg_cities) <= 1 and n_areas >= 4
                stale = age_days > 8 or not has_img
                if drift:
                    attention.append(f"{slug}: geo-grid config drift — {len(gg_cities)} "
                                     f"city configured vs {n_areas} service areas (reseed the ring)")
                if stale and not drift and not dry_run and _HEALS["geogrid"] > 0:
                    _HEALS["geogrid"] -= 1
                    subprocess.Popen([sys.executable,
                                      str(ROOT / "scripts" / "geogrid_cron.py"),
                                      "--slug", slug])
                    attention.append(f"{slug}: geo-grid stale ({age_days}d"
                                     + ("" if has_img else ", no image") + ") — re-scan started")
                rows_fresh = {"company_id": cid, "item_key": "data-fresh", "kind": "auto",
                              "status": "open" if (stale or drift) else "done",
                              "title": "Rankings data fresh",
                              "detail": (f"Newest map scan is {age_days} day(s) old"
                                         + ("" if has_img else " and has no map image")
                                         + ("; city ring needs reseeding" if drift else "")
                                         if (stale or drift) else None),
                              "evidence": {"age_days": age_days, "image": has_img,
                                           "cities": len(gg_cities), "areas": n_areas}}
                _upsert([rows_fresh], dry_run)
        except Exception:
            pass
        try:
            gi_google = bool(gi)
            if gi_google and not dry_run and _HEALS["media"] > 0:
                sb_url = os.environ["SUPABASE_URL"].rstrip("/")
                sb_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
                r = requests.post(f"{sb_url}/storage/v1/object/list/branding",
                                  headers={"apikey": sb_key,
                                           "Authorization": f"Bearer {sb_key}"},
                                  json={"prefix": f"{cid}/job-photos/posted/",
                                        "limit": 3}, timeout=30)
                have_media = any(isinstance(f, dict) and f.get("id") for f in (r.json() or []))
                if not have_media:
                    _HEALS["media"] -= 1
                    subprocess.run([sys.executable, str(ROOT / "scripts" / "gbp.py"),
                                    "media-import", "--slug", slug],
                                   capture_output=True, text=True, timeout=600)
                    attention.append(f"{slug}: GBP photo library imported (Photos tab was empty)")
        except Exception:
            pass

        # ---- CALL TRACKING (Santino 2026-07-28: "fully automated... least
        # amount of human touch"). Auto-provisions a county-local tracking
        # number (gbp source) for every Rank AI client that lacks one, capped
        # per run. The GBP phone SWAP auto-runs only when AUTO_PHONE_SWAP=1
        # (flipped on once the pilot numbers pass Santino's test call);
        # until then the swap stays one command: gbp.py set-phone --slug X.
        try:
            ct = (ints.get("call_tracking") or {})
            has_number = bool((ct.get("gbp") or {}).get("number"))
            if not has_number and not dry_run and _HEALS.get("calltrack", 0) > 0:
                _HEALS["calltrack"] -= 1
                r = subprocess.run([sys.executable,
                                    str(ROOT / "scripts" / "call_tracking.py"),
                                    "provision", "--slug", slug, "--source", "gbp"],
                                   capture_output=True, text=True, timeout=120)
                line = (r.stdout or r.stderr or "").strip().splitlines()[-1:]
                attention.append(f"{slug}: call tracking -> {line[0][:110] if line else 'no output'}")
                has_number = "provisioned" in (line[0] if line else "")
            # The GBP phone SWAP is NEVER automatic (Santino 2026-07-28: "a
            # human overseeing and confirming the push live for every single
            # client"). The human clicks "Approve phone swap" on the client's
            # Ops Attention card, which drops an [APPROVE-PHONE-SWAP] ops
            # note; this executor performs the swap on the next pass and
            # resolves the note. No approval note -> nothing happens, ever.
            swapped = bool((ct.get("gbp") or {}).get("gbp_swapped_at"))
            if has_number and not swapped:
                approvals = _sb("GET", "/rest/v1/marketing_ops_notes"
                                f"?company_id=eq.{cid}&status=eq.open"
                                "&body=like.*%5BAPPROVE-PHONE-SWAP%5D*&select=id",
                                prefer="return=representation") or []
                if approvals and not dry_run:
                    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "gbp.py"),
                                        "set-phone", "--slug", slug],
                                       capture_output=True, text=True, timeout=300)
                    line = (r.stdout or r.stderr or "").strip().splitlines()[-1:]
                    ok = bool(line and "->" in line[0])
                    if ok:
                        co2 = _sb("GET", f"/rest/v1/companies?id=eq.{cid}"
                                  "&select=integration_settings",
                                  prefer="return=representation") or [{}]
                        i2 = co2[0].get("integration_settings") or {}
                        if isinstance(i2, str):
                            i2 = json.loads(i2)
                        i2.setdefault("call_tracking", {}).setdefault("gbp", {})[
                            "gbp_swapped_at"] = datetime.now(timezone.utc).isoformat()
                        _sb("PATCH", f"/rest/v1/companies?id=eq.{cid}",
                            {"integration_settings": i2})
                        for ap in approvals:
                            _sb("PATCH", f"/rest/v1/marketing_ops_notes?id=eq.{ap['id']}",
                                {"status": "resolved",
                                 "resolved_at": datetime.now(timezone.utc).isoformat()})
                        swapped = True
                    attention.append(f"{slug}: APPROVED phone swap executed -> "
                                     f"{line[0][:100] if line else 'no output'}")
                else:
                    attention.append(f"{slug}: tracking number "
                                     f"{ct.get('gbp', {}).get('number', '?')} ready — "
                                     "awaiting your 'Approve phone swap' click in Ops Attention")
            rows.append({"company_id": cid, "item_key": "call-tracking", "kind": "auto",
                         "status": "done" if has_number else "open",
                         "title": ("Call tracking live: " + ct.get("gbp", {}).get("number", "")
                                   if has_number else "Call tracking number pending"),
                         "detail": None if has_number else
                         "A county-local tracking number gets provisioned automatically "
                         "on the next ops pass.",
                         "evidence": {"gbp_number": ct.get("gbp", {}).get("number"),
                                      "swapped": swapped}})
        except Exception:
            pass

        # ---- CITATIONS discovery/NAP audit (Santino 2026-07-28, priority):
        # auto-discovers each client's directory listings, prepopulates the
        # Connect tab slots, and flags phone discrepancies. Re-audits monthly.
        try:
            cit = _sb("GET", f"/rest/v1/user_integrations?client_id=eq.{cid}"
                      "&provider=eq.citations&select=connection_metadata",
                      prefer="return=representation") or []
            napa = ((cit[0].get("connection_metadata") or {}).get("nap_audit")
                    if cit else None) or {}
            newest_chk = max((v.get("checked_at") or "" for v in napa.values()),
                             default="")
            stale_c = True
            if newest_chk:
                try:
                    stale_c = (datetime.now(timezone.utc) - datetime.fromisoformat(
                        newest_chk.replace("Z", "+00:00"))).days > 30
                except ValueError:
                    pass
            if stale_c and not dry_run and _HEALS.get("citations", 0) > 0:
                _HEALS["citations"] -= 1
                r = subprocess.run([sys.executable,
                                    str(ROOT / "scripts" / "citations_audit.py"),
                                    "--slug", slug],
                                   capture_output=True, text=True, timeout=600)
                tail_ = (r.stdout or r.stderr or "").strip().splitlines()[-1:]
                attention.append(f"{slug}: citations audit -> {tail_[0][:110] if tail_ else 'no output'}")
                cit = _sb("GET", f"/rest/v1/user_integrations?client_id=eq.{cid}"
                          "&provider=eq.citations&select=connection_metadata",
                          prefer="return=representation") or []
                napa = ((cit[0].get("connection_metadata") or {}).get("nap_audit")
                        if cit else None) or {}
            n_found = sum(1 for v in napa.values()
                          if v.get("status") in ("found", "discrepancy"))
            n_disc = sum(1 for v in napa.values() if v.get("status") == "discrepancy")
            # A missing HomeAdvisor is not a gap — there's no free listing to
            # create (paid lead-gen only). Existing ones still get NAP-checked.
            n_missing = sum(1 for k, v in napa.items()
                            if v.get("status") == "missing" and k != "homeadvisor")
            if napa:
                # Split the missing listings by who can create them:
                #   us    — Bing Places (imports from their GBP, which we hold),
                #           Apple Maps (Business Connect agency claim), BBB (form)
                #   client — platforms that require the OWNER's identity / phone
                #           verification (Thumbtack, Angi free claim), plus
                #           Facebook (personal account) and Yelp claiming.
                # HomeAdvisor is EXCLUDED (Santino 2026-07-31): no free listing
                # exists — it's ~$300/yr membership + $15-100/lead. Never send
                # a client to sign up there as a "citation". Angi stays because
                # the basic profile claim is free (Angi Ads/Leads are not — the
                # claim ask must never morph into an Ads signup).
                _missing = {k for k, v in napa.items() if v.get("status") == "missing"}
                _lbl = {"bing_places": "Bing Places", "apple_maps": "Apple Maps",
                        "bbb": "BBB", "thumbtack": "Thumbtack",
                        "angi": "Angi (free claim only — never Angi Ads/Leads)",
                        "facebook": "Facebook", "yelp": "Yelp",
                        "expertise": "Expertise.com application",
                        "houzz": "Houzz", "porch": "Porch",
                        "homeguide": "HomeGuide", "nextdoor": "Nextdoor",
                        "yellowpages": "YellowPages"}
                # Split mirrors the app's owner badges: us = no owner identity
                # needed; client = owner claim / phone verification required.
                # Porch removed from us_create 2026-08-02: recon found Porch
                # killed self-serve pro signup entirely (insurance pivot; all
                # signup URLs 404, listing requires contacting Pro Support) —
                # a card must never demand an impossible action. Presence on
                # Porch is still AUDITED; legacy listings just can't be built.
                us_create = [_lbl[k] for k in ("bing_places", "apple_maps", "bbb",
                                               "expertise", "houzz", "homeguide")
                             if k in _missing]
                client_create = [_lbl[k] for k in ("yelp", "facebook", "thumbtack",
                                                   "angi", "nextdoor", "yellowpages")
                                 if k in _missing]
                # Per-platform checklist state (Santino 2026-08-02): the app
                # renders citations-build from evidence.platform_status.
                agent_subs = _agent_submitted_platforms(
                    cid, co.get("name") or "", slug, bing_sweep)
                platform_status = {}
                for plat in _US_CREATE_PLATFORMS:
                    _pst = (napa.get(plat) or {}).get("status")
                    if _pst in ("found", "discrepancy"):
                        # a discrepancy listing still EXISTS — never re-create;
                        # the wrong phone is tracked on the citations card
                        _state = "live"
                    elif plat in agent_subs:
                        _state = "submitted_pending"
                    else:
                        _state = "todo"
                    platform_status[plat] = {"status": _state,
                                             "label": _PS_LABEL[_state]}
                if dry_run:
                    print(f"  [citations-build] {slug}: " + ", ".join(
                        f"{k}={v['status']}" for k, v in platform_status.items()))
                rows.append({"company_id": cid, "item_key": "citations", "kind": "client_owed",
                             "status": "open" if (n_disc or client_create) else "done",
                             "title": f"Directory listings: {n_found} found, "
                                      f"{n_disc} wrong phone, {n_missing} missing",
                             "detail": ((f"Client-owed creates (owner identity required): "
                                         f"{', '.join(client_create)}. " if client_create else "")
                                        + ("Discrepancies get fixed against the Business "
                                           "Information card. " if n_disc else "")) or None,
                             "evidence": {"found": n_found, "discrepancies": n_disc,
                                          "missing": n_missing,
                                          "client_creates": client_create}})
                if us_create:
                    # Santino 2026-08-01 (corrected): these STAY visible until
                    # actually finished — the browser agent works them and marks
                    # each done only after verified completion, so a human can
                    # always see what's outstanding and catch breakage.
                    rows.append({"company_id": cid, "item_key": "citations-build",
                                 "kind": "us_owed", "status": "open",
                                 "title": f"Create listings we own: {', '.join(us_create)}",
                                 "detail": "Bing Places imports straight from their GBP "
                                           "(we hold access); Apple Maps via Business "
                                           "Connect agency claim; BBB via their request "
                                           "form. Always the Business Information card "
                                           "NAP with the REAL phone number. The browser "
                                           "agent works these; done = verified complete.",
                                 "evidence": {"platforms": us_create,
                                              "queued_for_agent": True,
                                              "platform_status": platform_status}})
                else:
                    rows.append({"company_id": cid, "item_key": "citations-build",
                                 "kind": "us_owed", "status": "done",
                                 "title": "Listings we can create ourselves: all present",
                                 "detail": None,
                                 "evidence": {"platform_status": platform_status}})
                if n_disc:
                    attention.append(f"{slug}: {n_disc} directory listing(s) show a WRONG "
                                     "phone — fix against the canonical card")
        except Exception:
            pass

        # ---- LSA follow-THROUGH (Santino 2026-07-30): a "Yes, wants LSA"
        # click in Ops Attention must surface the setup work, not vanish.
        # Santino runs LSA setup personally — us_owed, never a Monica ask.
        try:
            li = (ints.get("lsa_intent") or {}) if isinstance(ints, dict) else {}
            if not isinstance(li, dict):
                li = {}   # legacy plain-string lsa_intent (e.g. Crew) — no dict fields to read
            lsa_done = bool((ints.get("lsa") or {}).get("setup_done")
                            or (ints.get("lsa") or {}).get("customer_id"))
            if li.get("answer") == "yes" and not lsa_done:
                rows.append({"company_id": cid, "item_key": "lsa-setup",
                             "kind": "us_owed", "status": "open",
                             "title": "Wants Local Services Ads — setup not started",
                             "detail": "Santino runs this conversation personally "
                                       f"(marked YES {str(li.get('decided_at') or '')[:10]}). "
                                       "Mark integration_settings.lsa.setup_done when live.",
                             "evidence": {"decided_at": li.get("decided_at")}})
            elif li.get("answer") == "yes" and lsa_done:
                rows.append({"company_id": cid, "item_key": "lsa-setup",
                             "kind": "us_owed", "status": "done",
                             "title": "Local Services Ads: set up",
                             "detail": None, "evidence": {}})
        except Exception:
            pass

        # ---- Client hub document uploads -> Today (persists until Done)
        try:
            _check_doc_uploads(cid, co.get("name") or slug, dry_run)
        except Exception:
            pass

        # ---- Open AI-optimization recommendations (Santino 2026-07-30):
        # "open unanswered optimization recommendations should count as a
        # to-do needed by us." Every open suggestion the optimizer parked
        # (services/categories/pages/description/hours) stays on OUR board
        # until it's applied or dismissed in Locations -> AI optimization.
        # KEEP verdicts are informational ("looks good"), not to-dos.
        try:
            sugs = _sb("GET", f"/rest/v1/marketing_gbp_suggestions?company_id=eq.{cid}"
                       "&status=eq.open&verdict=neq.KEEP&select=item_type") or []
            if sugs:
                by_type = Counter(s.get("item_type") or "?" for s in sugs)
                breakdown = ", ".join(f"{n} {t}" for t, n in sorted(by_type.items()))
                rows.append({"company_id": cid, "item_key": "gbp-suggestions",
                             "kind": "us_owed", "status": "open",
                             "title": f"{len(sugs)} AI optimization recommendation"
                                      f"{'s' if len(sugs) != 1 else ''} awaiting your call",
                             "detail": f"Locations -> AI optimization ({breakdown}). "
                                       "Apply or dismiss each — open recommendations "
                                       "are our to-do, not background noise.",
                             "evidence": {"open": len(sugs), "by_type": dict(by_type)}})
            else:
                rows.append({"company_id": cid, "item_key": "gbp-suggestions",
                             "kind": "us_owed", "status": "done",
                             "title": "AI optimization: no open recommendations",
                             "detail": None, "evidence": {}})
        except Exception:
            pass

        # ---- Site imagery completeness (2026-07-31): per-service images
        # were manual agent work, so unfinished sites shipped with every
        # service card on the shared services.webp fallback (Coastal: all 12).
        # Complete = image on disk AND registered in image-meta.json —
        # serviceImage() only resolves registered images, so an unregistered
        # file still renders the fallback.
        try:
            svc_dir = SITES_DIR / slug / "src" / "content" / "services"
            if built and svc_dir.is_dir():
                stems = sorted(p.stem for p in svc_dir.glob("*.md"))
                simg_dir = SITES_DIR / slug / "public" / "images" / "services"
                meta_p = SITES_DIR / slug / "src" / "data" / "image-meta.json"
                try:
                    smeta = json.loads(meta_p.read_text()) if meta_p.exists() else {}
                except json.JSONDecodeError:
                    smeta = {}
                s_missing = [s for s in stems
                             if not ((simg_dir / f"{s}.webp").exists()
                                     and f"/images/services/{s}.webp" in smeta)]
                if s_missing:
                    rows.append({"company_id": cid, "item_key": "site-imagery",
                                 "kind": "us_owed", "status": "open",
                                 "title": f"Service imagery incomplete: {len(s_missing)} "
                                          f"of {len(stems)} service cards on the shared "
                                          "fallback image",
                                 "detail": "Generate + register with: python3 scripts/"
                                           f"gen_site_images.py --slug {slug} --services "
                                           "(writes the base webp, the 480/768/1200w "
                                           "variants and image-meta.json), then redeploy "
                                           "the site.",
                                 "evidence": {"total": len(stems),
                                              "missing": s_missing}})
                    attention.append(f"{slug}: {len(s_missing)}/{len(stems)} service "
                                     "cards on the fallback image — run the imagery "
                                     "finisher")
                elif stems:
                    rows.append({"company_id": cid, "item_key": "site-imagery",
                                 "kind": "us_owed", "status": "done",
                                 "title": f"Service imagery complete: "
                                          f"{len(stems)} services",
                                 "detail": None, "evidence": {"total": len(stems)}})
        except Exception:
            pass

        _upsert(rows, dry_run)

    return attention


def ensure_auto_site_build(dry_run: bool, cid_to_slug: dict | None = None,
                           cap: int = 4) -> list[str]:
    """Auto-build preview sites — site builds never wait on approval (Santino
    2026-07-28: "I definitely don't want site builds to be backlogged just
    because I haven't said yes or no"). For Active Rank AI clients with NO
    sites/{slug}: seed/enrich plan-input from the truth table (services +
    company contact block, the manual Mold Solutionz steps mechanized), then
    plan -> scaffold -> render. Cap 1 per run (render cost/time). Imagery is
    NOT auto-generated — the attention line flags the built site for the
    hero/photo pass. Disable with AUTO_SITE_BUILD=0."""
    if os.environ.get("AUTO_SITE_BUILD", "1") == "0":
        return ["auto-build disabled (AUTO_SITE_BUILD=0)"]
    cid_to_slug = cid_to_slug or slug_map()
    cos = _sb("GET", "/rest/v1/companies?status=ilike.active&plan=eq.Rank%20AI"
              "&select=id,name,phone,email,address,city,state,postal_code,services,"
              "integration_settings,service_areas",
              prefer="return=representation") or []
    out: list[str] = []
    built = 0
    for co in cos:
        if built >= cap:
            break
        cid, slug = co["id"], cid_to_slug.get(co["id"])
        if not slug or (SITES_DIR / slug / "src").exists():
            continue
        services = [s for s in (co.get("services") or []) if s]
        if not services:
            out.append(f"{slug}: cannot auto-build — no confirmed services in truth table")
            continue
        pi_path = CLIENTS_DIR / slug / "plan-input.json"
        if not pi_path.exists():
            out.append(f"{slug}: cannot auto-build — no plan-input.json (bootstrap missing)")
            continue
        if dry_run:
            out.append(f"{slug}: WOULD auto-build preview site ({len(services)} services)")
            built += 1
            continue
        try:
            pi = json.loads(pi_path.read_text())
            # map confirmed service names -> catalog slugs (simple normalize)
            import verticals
            cat = json.loads(Path(verticals.resolve_template(slug, "services.json")).read_text())
            by_norm = {re.sub(r"[^a-z]", "", s["display_name"].lower()): s["slug"]
                       for s in cat["services"]}
            cat_words = {s2["slug"]: set(re.findall(r"[a-z]+", s2["display_name"].lower()))
                         for s2 in cat["services"]}
            svc_slugs = []
            for s in services:
                key = re.sub(r"[^a-z]", "", s.lower())
                hit = by_norm.get(key) or next(
                    (v for k, v in by_norm.items() if key[:12] and key[:12] in k), None)
                if not hit:
                    # word-overlap fallback: "Biohazard & Trauma Cleanup" ->
                    # biohazard-cleanup even though the exact key differs
                    words = set(re.findall(r"[a-z]+", s.lower())) - {"and", "services", "service"}
                    best, score = None, 0.0
                    for cslug, cw in cat_words.items():
                        ov = len(words & cw) / max(len(words | cw), 1)
                        if ov > score:
                            best, score = cslug, ov
                    if score >= 0.5:
                        hit = best
                if hit and hit not in svc_slugs:
                    svc_slugs.append(hit)
            if not svc_slugs:
                out.append(f"{slug}: cannot auto-build — no services mapped to catalog")
                continue
            pi["services"] = svc_slugs
            # Areas: geogrid city ring (bootstrap seeds it) + company state,
            # else the company's own city (QCI 2026-07-28: plan generate died
            # on 'At least one service area is required')
            if not (pi.get("service_areas") or []):
                areas = []
                st = (co.get("state") or "").strip()
                # FIRST: the app's Site Build brief — the cities a human
                # explicitly picked (QCI 2026-07-29: brief had 8 cities, the
                # auto-build shipped 1 because it never read the brief).
                ints_b = co.get("integration_settings") or {}
                if isinstance(ints_b, str):
                    try:
                        ints_b = json.loads(ints_b)
                    except json.JSONDecodeError:
                        ints_b = {}
                for c_ in (ints_b.get("site_brief") or {}).get("cities") or []:
                    city = (c_.get("label") or "").strip()
                    cst = (c_.get("state") or st).strip()
                    if city:
                        areas.append({
                            "city": city, "state": cst,
                            "slug": re.sub(r"[^a-z0-9]+", "-",
                                           f"{city} {cst}".lower()).strip("-"),
                            **({"primary": True} if not areas else {})})
                # SECOND: the onboarding wizard's territory picker writes
                # companies.service_areas (county + cities) — the AI Dispatcher
                # reads it, but the site build never did (Coastal + QCI both
                # shipped with a fraction of their cities, 2026-07-30).
                if not areas:
                    _ST_ABBR = {"alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
                                "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
                                "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
                                "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
                                "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
                                "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
                                "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
                                "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
                                "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
                                "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
                                "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
                                "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
                                "wisconsin": "WI", "wyoming": "WY"}
                    sa_raw = co.get("service_areas")
                    if isinstance(sa_raw, str):
                        try:
                            sa_raw = json.loads(sa_raw)
                        except json.JSONDecodeError:
                            sa_raw = []
                    for terr in sa_raw or []:
                        tst = (terr.get("state") or st or "").strip()
                        tst = _ST_ABBR.get(tst.lower(), tst[:2].upper() if len(tst) > 2 else tst.upper())
                        for city in terr.get("cities") or []:
                            city = str(city).strip()
                            # campus/base entries aren't ranking targets
                            if not city or len(city) > 40 or "university" in city.lower():
                                continue
                            city = re.sub(r"\s*\(.*\)$", "", city)  # "El Paso de Robles (Paso Robles)"
                            areas.append({
                                "city": city, "state": tst,
                                "slug": re.sub(r"[^a-z0-9]+", "-",
                                               f"{city} {tst}".lower()).strip("-"),
                                **({"primary": True} if not areas else {})})
                gg = CLIENTS_DIR / slug / "geogrid-cities.json"
                if not areas and gg.exists():
                    try:
                        for c_ in json.loads(gg.read_text()):
                            city = (c_.get("city") or c_.get("label") or "").strip()
                            if city:
                                areas.append({
                                    "city": city, "state": st,
                                    "slug": re.sub(r"[^a-z0-9]+", "-",
                                                   f"{city} {st}".lower()).strip("-"),
                                    **({"primary": True} if not areas else {})})
                    except json.JSONDecodeError:
                        pass
                if not areas and (co.get("city") or "").strip():
                    city = co["city"].strip()
                    areas = [{"city": city, "state": st,
                              "slug": re.sub(r"[^a-z0-9]+", "-",
                                             f"{city} {st}".lower()).strip("-"),
                              "primary": True}]
                if not areas:
                    out.append(f"{slug}: cannot auto-build — no cities anywhere in the truth table")
                    continue
                pi["service_areas"] = areas
            pi.setdefault("template", "restoration")
            pi.setdefault("blog_seed_count", 8)
            b = pi.setdefault("brand", {})
            b.setdefault("display_name", (co.get("name") or slug).strip())
            b.setdefault("phone", co.get("phone") or "")
            b.setdefault("email", co.get("email") or "")
            b.setdefault("street_address", co.get("address") or "")
            b.setdefault("city", co.get("city") or "")
            b.setdefault("state", co.get("state") or "")
            b.setdefault("postal_code", co.get("postal_code") or "")
            # Honor the theme the client picked in the wizard (Go Green shipped
            # dark+red against an explicit "light" intake, 2026-07-28). The
            # primary color stays the scaffold default until a human brand pass
            # — auto-extracting from branding uploads is unsafe (they're often
            # photos, not clean logo files).
            ints_ = co.get("integration_settings") or {}
            if isinstance(ints_, str):
                try:
                    ints_ = json.loads(ints_)
                except json.JSONDecodeError:
                    ints_ = {}
            theme_pick = ((ints_.get("site_brief") or {}).get("theme")
                          or ints_.get("theme") or "").strip().lower()
            if theme_pick == "light":
                b.setdefault("theme", "light")
            # Wizard licensing -> brand truth table + trust badges (Coastal's
            # IICRC sat recorded-but-unused, 2026-07-30). Only VERIFIED claims.
            lic = ints_.get("licensing") or {}
            certs = [c.strip().upper() for c in
                     str(lic.get("certifications") or "").split(",") if c.strip()]
            if certs and "certifications" not in b:
                names = {"IICRC": "IICRC Certified Firm",
                         "WTR": "WRT (Water Damage Restoration Technician)",
                         "WRT": "WRT (Water Damage Restoration Technician)",
                         "ASD": "ASD (Applied Structural Drying)",
                         "AMRT": "AMRT (Applied Microbial Remediation)",
                         "FSRT": "FSRT (Fire & Smoke Restoration)"}
                # ARRAY, not a joined string — the scaffold casts this into
                # brand.ts as string[] verbatim, and a string crashed
                # HomeLyft's whole build on .some() (2026-08-01).
                b["certifications"] = [names.get(c, c) for c in certs]
            if lic.get("license_number") and "license_numbers" not in b:
                b["license_numbers"] = [str(lic["license_number"])]
            badges = []
            if any(c.startswith("IICRC") for c in certs):
                badges.append("IICRC Certified Firm")
            if lic.get("insured"):
                badges.append("Licensed & Insured")
            badges += ["24/7 Emergency Service", "Locally Owned & Operated"]
            b.setdefault("trust_badges", badges)
            # Primary area = the company's own city when it's in the list
            # (Vandenberg Village outranked Santa Maria purely by wizard
            # ordering, 2026-07-30).
            home_city = (co.get("city") or "").strip().lower()
            sa_list = pi.get("service_areas") or []
            if home_city and sa_list and not any(
                    a.get("primary") and a.get("city", "").strip().lower() == home_city
                    for a in sa_list):
                hit = next((a for a in sa_list
                            if a.get("city", "").strip().lower() == home_city), None)
                if hit:
                    for a in sa_list:
                        a.pop("primary", None)
                    hit["primary"] = True
            pi_path.write_text(json.dumps(pi, indent=1) + "\n")
            for cmdline, tmo in [
                ([sys.executable, str(ROOT / "scripts" / "plan_site.py"),
                  "generate", "--slug", slug], 300),
                ([sys.executable, str(ROOT / "scripts" / "build_site.py"),
                  "scaffold", "--slug", slug], 900),
                ([sys.executable, str(ROOT / "scripts" / "build_site.py"),
                  "render", "--slug", slug, "--workers", "4", "--push"], 5400),
            ]:
                r = subprocess.run(cmdline, capture_output=True, text=True, timeout=tmo)
                if r.returncode != 0:
                    tail = (r.stderr or r.stdout or "").strip().splitlines()[-1:]
                    raise RuntimeError(f"{cmdline[2]} failed: {tail}")
            # scaffold/render leave a nested .git in the site dir — committing
            # it to the monorepo creates an empty gitlink (2026-07-28)
            nested = SITES_DIR / slug / ".git"
            if nested.exists():
                import shutil
                shutil.rmtree(nested, ignore_errors=True)
            built += 1
            # WRITE-BACK (2026-08-03, second occurrence: HomeLyft 08-01, Reign
            # 08-03): builds that run OUTSIDE the site-build CI never patched
            # marketing_sites, so the app's Site tab stayed blank. Mirror
            # site-build.yml's "Mark preview ready" step: flip the row to
            # preview_ready + staging URL, and seed Monica's preview-feedback
            # plan row so the client gets shown their new site.
            preview = f"https://staging.rankai-{slug}.pages.dev"
            try:
                rec_ = json.loads((CLIENTS_DIR / f"{slug}.json").read_text())
                # upsert, not PATCH: a missing row would make PATCH a silent
                # 0-row no-op and the tab would stay blank anyway
                _sb("POST", "/rest/v1/marketing_sites?on_conflict=rank_ai_slug",
                    {"rank_ai_slug": slug, "company_id": cid,
                     "build_status": "preview_ready",
                     "cloudflare_pages_url": preview,
                     "github_repo": (rec_.get("build") or {}).get("github_repo"),
                     "plan_status": rec_.get("plan_status"),
                     "plan_template": (rec_.get("plan") or {}).get("template"),
                     "plan_url_count": (rec_.get("plan") or {}).get("url_count"),
                     "plan_generated_at": (rec_.get("plan") or {}).get("generated_at"),
                     "scaffolded_at": (rec_.get("build") or {}).get("scaffolded_at"),
                     "last_pushed_staging_at": (rec_.get("build") or {}).get("last_rendered_at"),
                     "updated_at": rec_.get("updated_at")},
                    prefer="resolution=merge-duplicates,return=minimal")
                fb_row = {"company_id": cid, "rank_ai_slug": slug,
                          "action_key": f"site-preview-feedback-{slug}",
                          "action_type": "client_input", "status": "planned",
                          "priority": 1, "impact": "high", "effort": "low",
                          "title": "Take a look at your new website preview and "
                                   "tell us your thoughts",
                          "target": preview,
                          "rationale": "New site build finished at " + preview +
                                       " — share the link with the client, ask what "
                                       "they think, and collect any change requests."}
                # manual dedupe (table has no unique constraint on action_key)
                dup_ = _sb("GET", "/rest/v1/marketing_action_plan"
                           f"?company_id=eq.{cid}&action_key=eq.{fb_row['action_key']}"
                           "&select=id", prefer="return=representation") or []
                if not dup_:
                    _sb("POST", "/rest/v1/marketing_action_plan", [fb_row])
            except Exception as e_:
                out.append(f"{slug}: built OK but marketing_sites write-back "
                           f"FAILED — {str(e_)[:120]} (app Site tab will look "
                           "blank until patched by hand)")
            has_brand_asset = False
            try:
                sb_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
                sb_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
                r_ = requests.post(f"{sb_url}/storage/v1/object/list/branding",
                                   headers={"Authorization": f"Bearer {sb_key}",
                                            "apikey": sb_key,
                                            "Content-Type": "application/json"},
                                   json={"prefix": f"{cid}/brand/", "limit": 5},
                                   timeout=20)
                has_brand_asset = r_.status_code == 200 and bool(r_.json())
            except Exception:
                pass
            out.append(f"{slug}: AUTO-BUILT preview site ({len(svc_slugs)} services) — "
                       "NEEDS imagery pass (hero + per-service) + human once-over"
                       + (f"; client brand upload EXISTS (branding/{cid}/brand) — "
                          "use it for logo + palette" if has_brand_asset else
                          "; no brand upload yet — ask for their logo"))
        except Exception as e:
            out.append(f"{slug}: auto-build FAILED — {str(e)[:140]}")
    return out


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass
    print(f"==> Setup ledger ({'dry-run' if dry else 'live'})")
    for line in ensure_ledger(dry):
        print("  ATTENTION:", line)
