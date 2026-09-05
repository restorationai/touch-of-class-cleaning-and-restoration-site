#!/usr/bin/env python3
"""cutover_execute.py — the ONE-CLICK CUTOVER.

Pointing a client's real domain at our build used to be a hand-run ritual
(TRG and All Pro were "email-safe NS cutovers" done by hand: attach the
Cloudflare zone, copy every DNS record so their EMAIL doesn't die, attach the
Pages custom domains, stamp domain + cut_over_at, register GSC, verify from
outside). This script is that ritual as an idempotent, phased job the app can
trigger via the Railway API (api/runner.py system "cutover").

Commands:
    run --slug X [--apply]
        Execute the cutover phases in order. DRY-RUN BY DEFAULT: without
        --apply nothing is created, written to Cloudflare/Supabase, or
        stamped (the DNS snapshot file is still captured — it is read-only
        knowledge about the world and reviewing it is the point of a dry
        run). Every phase is fail-soft-REPORTED; an --apply run refuses to
        proceed past a failed CRITICAL phase, while a dry run keeps
        evaluating read-only checks so the whole picture prints at once.

        Phases:
          1. PRE-FLIGHT      real domain known; cutover_prep fresh (else
                             auto harvest+map --apply); site pushed to main;
                             brand.ts/astro.config carry the real domain
                             (heals via record-stamp + redeploy on --apply —
                             the sync-deploy rehydration guard does the fix).
          2. ZONE + EMAIL    find/create the CF zone; capture authoritative
                             DNS from OUTSIDE via DoH (MX, SPF, DKIM selector
                             guesses, DMARC) + whatever already sits in the
                             zone -> clients/{slug}/cutover/dns-snapshot.json;
                             ensure MX/SPF/DKIM/DMARC exist in the zone.
                             NEVER deletes a record.
          3. NS CHECK        DoH (never local dig — the LAN intercepts port
                             53): domain NS must equal the zone's assigned
                             Cloudflare pair, else "waiting on nameserver
                             transfer" + the exact pair, and stop. This is
                             the state the app button polls.
          4. ATTACH          Pages custom domains apex + www on the client's
                             Pages project + the CNAME records Pages needs.
                             Apex/www ADDRESS records (A/AAAA/CNAME at those
                             two names only) are repointed at the Pages
                             project — that IS the cutover; email records are
                             protected by a type+name allowlist and the full
                             pre-change zone lives in the snapshot.
          5. STAMP+REGISTER  write domain into clients/{slug}.json +
                             marketing_sites; gsc_register.py --domain;
                             IndexNow ping (both fail-soft).
          6. VERIFY OUTSIDE  DoH-resolve the apex, curl --resolve those IPs:
                             /llms.txt FIRST LINE must equal
                             sites/{slug}/public/llms.txt (identity, not
                             vibes) and the live HTML must not contain
                             "https://None". Only then cut_over_at is
                             stamped and marketing_sites.apex_live goes true
                             (supabase_sync derives apex_live from
                             cut_over_at, so the stamp itself waits for this
                             phase — stamping it in phase 5 would let the
                             nightly sync flip apex_live on an unverified
                             launch).
          7. BASELINE        clients/{slug}/cutover/baseline.json —
                             DataForSEO backlinks_summary (ONE paid call:
                             rank/backlinks/referring domains) + citations
                             found-count from user_integrations
                             provider=citations nap_audit. The before/after
                             benchmark. Skipped if already captured.

    provision --slug X [--apply]
        Phases 2+3 ONLY: find/create the Cloudflare zone, snapshot + copy
        email DNS, and report the zone's assigned nameserver pair — WITHOUT
        the site-readiness pre-flight (pushed_main / brand.ts hydration).
        For clients whose build is still staging-only: the NS pair only
        exists once the zone does, and provisioning early lets the client
        start the registrar transfer while the site is finished. DRY-RUN BY
        DEFAULT like run. The full `run` still gates the actual launch
        (attach/stamp/verify) on its pre-flight. Exit codes: 0 = NS already
        point at our zone, 3 = provisioned + waiting on transfer (the
        expected end-state), 2 = failed.

    status --slug X
        Machine-readable JSON of phase readiness (prep/email/ns/attach/
        verify) on stdout — the app's readiness panel renders this. Safe,
        read-only, no paid calls, NEVER creates the zone. Carries a
        top-level ns object — {required: [pair]|null, current: [DoH
        observation]|null, zone_exists: bool} — so the app can always show
        WHICH nameservers the client must set (required is null until the
        zone exists).

Exit codes for run: 0 = all critical phases passed (site verified LIVE),
3 = stopped waiting on nameserver transfer (the expected mid-state),
2 = a critical phase failed. Re-running is safe — every phase is idempotent.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

import cutover_harvest as ch  # import, don't edit (301 maps + prep stamps)
from work_log import company_id_for_slug, work_log  # noqa: E402

CF_API = "https://api.cloudflare.com/client/v4"
DOH = "https://dns.google/resolve"  # port-53 is intercepted on this LAN; DoH is the outside view
DOH_TYPES = {"A": 1, "NS": 2, "CNAME": 5, "MX": 15, "TXT": 16, "AAAA": 28}
# DKIM selector guesses: google/default/k1 per the runbook, plus the
# Microsoft 365 pair — harmless extra queries, catches Outlook-hosted email.
DKIM_SELECTORS = ("default", "google", "k1", "selector1", "selector2")
UA = {"User-Agent": "Mozilla/5.0 (compatible; RankAI-cutover; +https://restorationai.io)"}
CURL_TIMEOUT = 25


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# small clients: Cloudflare / DoH / Supabase REST
# ---------------------------------------------------------------------------

def cf_token(pages: bool = False) -> str:
    """Zone/DNS work uses CLOUDFLARE_API_TOKEN (gsc_register's var); Pages
    calls prefer the dedicated Pages token, same fallback chain as
    build_site.cf_creds()."""
    if pages:
        return (os.environ.get("CLOUDFLARE_PAGES_API_TOKEN")
                or os.environ.get("CLOUDFLARE_R2_API_TOKEN")
                or os.environ.get("CLOUDFLARE_API_TOKEN") or "")
    return os.environ.get("CLOUDFLARE_API_TOKEN", "")


def cf(method: str, path: str, body: dict | None = None, *,
       pages: bool = False, timeout: int = 30) -> dict:
    r = requests.request(
        method, CF_API + path, timeout=timeout,
        data=json.dumps(body) if body is not None else None,
        headers={"Authorization": "Bearer " + cf_token(pages=pages),
                 "Content-Type": "application/json"})
    try:
        d = r.json()
    except ValueError:
        raise RuntimeError(f"CF {method} {path} -> HTTP {r.status_code} (non-JSON)")
    if not d.get("success", False):
        raise RuntimeError(f"CF {method} {path} -> HTTP {r.status_code}: "
                           f"{json.dumps(d.get('errors'))[:300]}")
    return d


def doh(name: str, rtype: str) -> list[str]:
    """Authoritative answer data for one record type, from outside the LAN."""
    r = requests.get(DOH, params={"name": name, "type": rtype},
                     timeout=15, headers=UA)
    r.raise_for_status()
    want = DOH_TYPES[rtype]
    return [a.get("data", "") for a in (r.json().get("Answer") or [])
            if a.get("type") == want]


def txt_join(data: str) -> str:
    """DoH TXT data arrives quoted, sometimes in chunks: "a" "b" -> ab."""
    parts = re.findall(r'"([^"]*)"', data)
    return "".join(parts) if parts else data.strip('"')


def strip_dot(s: str) -> str:
    return s.rstrip(".").lower()


def _supa() -> tuple[str, str]:
    return ((os.environ.get("SUPABASE_URL") or "").rstrip("/"),
            os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or "")


def sb_get(path: str) -> list:
    url, key = _supa()
    if not (url and key):
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY unset")
    r = requests.get(url + path, timeout=20,
                     headers={"apikey": key, "Authorization": f"Bearer {key}"})
    r.raise_for_status()
    return r.json()


def sb_post(path: str, body: dict) -> None:
    url, key = _supa()
    if not (url and key):
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY unset")
    r = requests.post(url + path, json=body, timeout=20,
                      headers={"apikey": key, "Authorization": f"Bearer {key}",
                               "Content-Type": "application/json",
                               "Prefer": "return=minimal"})
    if r.status_code not in (200, 201, 204):
        raise RuntimeError(f"supabase POST {path} -> {r.status_code} {r.text[:200]}")


def sb_patch(path: str, body: dict) -> None:
    url, key = _supa()
    if not (url and key):
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY unset")
    r = requests.patch(url + path, json=body, timeout=20,
                       headers={"apikey": key, "Authorization": f"Bearer {key}",
                                "Content-Type": "application/json",
                                "Prefer": "return=minimal"})
    if r.status_code not in (200, 204):
        raise RuntimeError(f"supabase PATCH {path} -> {r.status_code} {r.text[:200]}")


def _pinned_fetch_py(domain: str, ip: str, path: str) -> tuple[int, str]:
    """curl --resolve without curl: raw TLS to the pinned IP with SNI set to
    the domain (Railway's Nixpacks image doesn't guarantee a curl binary)."""
    import socket
    import ssl
    ctx = ssl.create_default_context()
    with socket.create_connection((ip, 443), timeout=CURL_TIMEOUT) as sock:
        with ctx.wrap_socket(sock, server_hostname=domain) as tls:
            tls.sendall((f"GET {path} HTTP/1.1\r\nHost: {domain}\r\n"
                         f"User-Agent: {UA['User-Agent']}\r\n"
                         "Accept: */*\r\nConnection: close\r\n\r\n").encode())
            raw = b""
            while len(raw) < 2_000_000:
                chunk = tls.recv(65536)
                if not chunk:
                    break
                raw += chunk
    head, _, body = raw.partition(b"\r\n\r\n")
    lines = head.decode("latin-1").splitlines()
    code = int(lines[0].split()[1]) if lines and len(lines[0].split()) > 1 else 0
    if any(l.lower() == "transfer-encoding: chunked" for l in lines):
        out, rest = b"", body
        while rest:
            size_line, _, rest = rest.partition(b"\r\n")
            try:
                n = int(size_line.strip() or b"0", 16)
            except ValueError:
                break
            if n == 0:
                break
            out += rest[:n]
            rest = rest[n + 2:]
        body = out
    return code, body.decode("utf-8", "replace")


def curl_resolve(domain: str, ip: str, path: str) -> tuple[int, str]:
    """HTTPS fetch pinned to a specific IP (the outside-verification trick:
    DNS answers come from DoH, the request goes straight at that answer)."""
    try:
        out = subprocess.run(
            ["curl", "-sS", "--max-time", str(CURL_TIMEOUT), "-w", "\n%{http_code}",
             "--resolve", f"{domain}:443:{ip}", f"https://{domain}{path}"],
            capture_output=True, text=True, timeout=CURL_TIMEOUT + 10)
    except FileNotFoundError:
        try:
            return _pinned_fetch_py(domain, ip, path)
        except Exception:
            return 0, ""
    body, _, code = out.stdout.rpartition("\n")
    try:
        return int(code or 0), body
    except ValueError:
        return 0, body


# ---------------------------------------------------------------------------
# shared lookups
# ---------------------------------------------------------------------------

def resolve_domain_soft(slug: str) -> str | None:
    """record domain > cutover_prep domain (same precedence as
    cutover_harvest.resolve_domain, but returns None instead of exiting)."""
    rec = ch.client_record(slug)
    for cand in (rec.get("domain"), (rec.get("cutover_prep") or {}).get("domain")):
        if cand and not str(cand).endswith(".invalid") and str(cand).lower() != "none":
            return ch.norm_domain(str(cand))
    return None


def nudge_zone_activation(zone: dict | None) -> bool:
    """NS correct at the registry but the zone still `pending` -> ask
    Cloudflare to re-verify NOW instead of on its lazy schedule (Arch launch
    2026-09-05: Santino's transfer was done, readiness stayed red for hours,
    and the fix was one activation_check call). Returns True when the zone
    reports active afterwards. Harmless to repeat, changes no config."""
    if not zone or zone.get("status") == "active":
        return bool(zone and zone.get("status") == "active")
    try:
        cf("PUT", f"/zones/{zone['id']}/activation_check")
    except Exception:  # noqa: BLE001 — rate-limited repeats etc.; never fatal
        pass
    import time as _t
    for _ in range(3):
        _t.sleep(4)
        try:
            z = cf("GET", f"/zones/{zone['id']}").get("result") or {}
            if z.get("status") == "active":
                return True
        except Exception:  # noqa: BLE001
            break
    return False


def find_zone(domain: str) -> dict | None:
    res = cf("GET", f"/zones?name={domain}").get("result") or []
    return res[0] if res else None


def zone_records(zone_id: str) -> list[dict]:
    recs, page = [], 1
    while page <= 5:
        d = cf("GET", f"/zones/{zone_id}/dns_records?per_page=500&page={page}")
        batch = d.get("result") or []
        recs.extend(batch)
        if len(batch) < 500:
            break
        page += 1
    return recs


def pages_project_name(rec: dict, slug: str) -> str:
    return (rec.get("build") or {}).get("pages_project") or f"rankai-{slug}"


def pages_domains(project: str) -> list[str] | None:
    acct = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
    try:
        d = cf("GET", f"/accounts/{acct}/pages/projects/{project}/domains", pages=True)
    except RuntimeError as e:
        if "404" in str(e):
            return None  # project itself missing
        raise
    return [r.get("name", "") for r in (d.get("result") or [])]


def local_llms_first_line(slug: str) -> str:
    p = ROOT / "sites" / slug / "public" / "llms.txt"
    if not p.exists():
        return ""
    for line in p.read_text().splitlines():
        if line.strip():
            return line.strip()
    return ""


def snapshot_path(slug: str) -> Path:
    return ROOT / "clients" / slug / "cutover" / "dns-snapshot.json"


def baseline_path(slug: str) -> Path:
    return ROOT / "clients" / slug / "cutover" / "baseline.json"


# ---------------------------------------------------------------------------
# phase engine
# ---------------------------------------------------------------------------

class Phase:
    def __init__(self, name: str, critical: bool = True):
        self.name = name
        self.critical = critical
        self.ok = True
        self.notes: list[str] = []
        self.waiting_on_ns = False

    def note(self, msg: str) -> None:
        self.notes.append(msg)

    def fail(self, msg: str) -> None:
        self.ok = False
        self.notes.append("FAIL: " + msg)


# ---- phase 1: pre-flight ---------------------------------------------------

def phase_preflight(slug: str, apply: bool) -> tuple[Phase, str | None]:
    ph = Phase("PRE-FLIGHT")
    rec = ch.client_record(slug)
    domain = resolve_domain_soft(slug)
    if not domain:
        ph.fail("no real domain on clients/{slug}.json (domain and "
                "cutover_prep.domain both empty/.invalid) — attach one first")
        return ph, None
    src = "clients/{}.json domain".format(slug) if rec.get("domain") else "cutover_prep"
    ph.note(f"domain: {domain} (from {src})")

    # cutover_prep freshness (301 map staged before the old site dies)
    prep = rec.get("cutover_prep") or {}
    age = ch._prep_age_days(prep)
    if age is None or age > ch.STALE_DAYS:
        if apply:
            ph.note(f"cutover_prep {'missing' if age is None else f'{age:.0f}d stale'} "
                    "— auto-running cutover_harvest harvest+map --apply")
            try:
                ch.cmd_harvest(slug, domain)
                ch.cmd_map(slug, apply=True, commit=True)
                rec = ch.client_record(slug)  # reload — map stamps cutover_prep
                ph.note("harvest+map complete")
            except SystemExit as e:
                ph.fail(f"auto harvest+map aborted: {e}")
            except Exception as e:
                ph.fail(f"auto harvest+map failed: {str(e)[:160]}")
        else:
            ph.fail(f"cutover_prep {'missing' if age is None else f'{age:.0f} days stale'} "
                    "(would auto-run cutover_harvest harvest + map --apply)")
    else:
        ph.note(f"cutover_prep fresh: harvested {age:.1f}d ago, "
                f"{prep.get('url_count')} URLs, {prep.get('redirects_added')} redirects staged")

    # deployed to main
    build = rec.get("build") or {}
    if build.get("last_pushed_main_at"):
        ph.note(f"deployed to main: {build['last_pushed_main_at']}")
    else:
        ph.fail("site never pushed to main (build.last_pushed_main_at missing) — "
                "run build_site.py sync-deploy --branch main first"
                + ("" if build.get("last_pushed_staging_at") else " (no staging push either)"))

    # rehydration check: brand.ts + astro.config carry the real domain
    site_dir = ROOT / "sites" / slug
    stale_files = []
    for rel in ("src/lib/brand.ts", "astro.config.mjs"):
        p = site_dir / rel
        if not p.exists():
            ph.fail(f"sites/{slug}/{rel} missing — site not scaffolded?")
            continue
        body = p.read_text()
        if "https://None" in body or f"https://{domain}" not in body:
            stale_files.append(rel)
    if stale_files:
        if apply and ph.ok:
            # the rehydration guard heals on deploy, but only when the record
            # carries the domain — stamp it if needed, redeploy, re-check.
            ph.note("redeploying main so the sync-deploy rehydration guard heals "
                    + ", ".join(stale_files))
            if rec.get("domain") != domain:
                rec["domain"] = domain
                rec["updated_at"] = now_iso()
                ch.save_client_record(slug, rec)
                ph.note("domain stamped on the client record (guard reads it at deploy)")
            r = subprocess.run(
                ["python3", str(ROOT / "scripts" / "build_site.py"), "sync-deploy",
                 "--slug", slug, "--branch", "main", "--allow-dirty"],
                cwd=str(ROOT), capture_output=True, text=True, timeout=900)
            if r.returncode != 0:
                ph.fail("heal-redeploy failed: " + (r.stdout + r.stderr)[-300:])
            else:
                still = [rel for rel in stale_files
                         if "https://None" in (site_dir / rel).read_text()
                         or f"https://{domain}" not in (site_dir / rel).read_text()]
                if still:
                    ph.fail("still stale after heal-redeploy: " + ", ".join(still))
                else:
                    ph.note("healed + redeployed — brand.ts/astro.config now carry the domain")
        else:
            ph.fail("stale domain in " + ", ".join(stale_files) +
                    " (https://None or wrong domain) — the rehydration guard heals on "
                    "sync-deploy once the record carries the domain"
                    + ("" if apply else "; --apply stamps the record and redeploys main"))
    elif not stale_files:
        ph.note("brand.ts + astro.config carry https://" + domain)
    return ph, domain


# ---- phase 2: zone + email safety -------------------------------------------

def capture_outside_dns(domain: str) -> tuple[dict, int]:
    """DoH capture of everything email needs. Returns (capture, error_count)."""
    errors = 0
    cap: dict = {"ns": [], "mx": [], "apex_txt": [], "dmarc_txt": [],
                 "dkim": {}, "apex_a": [], "apex_cname": [], "www_cname": []}

    def q(name, rtype):
        nonlocal errors
        try:
            return doh(name, rtype)
        except Exception:
            errors += 1
            return []

    cap["ns"] = sorted(strip_dot(d) for d in q(domain, "NS"))
    for d in q(domain, "MX"):
        parts = d.split()
        if len(parts) >= 2:
            cap["mx"].append({"priority": int(parts[0]) if parts[0].isdigit() else 10,
                              "exchange": strip_dot(parts[1])})
    cap["apex_txt"] = [txt_join(d) for d in q(domain, "TXT")]
    cap["dmarc_txt"] = [txt_join(d) for d in q(f"_dmarc.{domain}", "TXT")]
    for sel in DKIM_SELECTORS:
        name = f"{sel}._domainkey.{domain}"
        txt = [txt_join(d) for d in q(name, "TXT")]
        cname = [strip_dot(d) for d in q(name, "CNAME")]
        # a CNAMEd selector answers the TXT query with the target's TXT too —
        # prefer recording the CNAME (that's the record to recreate)
        if cname:
            cap["dkim"][sel] = {"cname": cname}
        elif txt:
            cap["dkim"][sel] = {"txt": txt}
    cap["apex_a"] = [d for d in q(domain, "A")]
    cap["apex_cname"] = [strip_dot(d) for d in q(domain, "CNAME")]
    cap["www_cname"] = [strip_dot(d) for d in q(f"www.{domain}", "CNAME")]
    return cap, errors


def email_records_needed(domain: str, outside: dict, zrecs: list[dict]) -> list[dict]:
    """Records (create payloads) missing from the CF zone that the outside
    world says exist. NEVER produces deletions."""
    def zone_has(rtype: str, name: str, content_pred) -> bool:
        for r in zrecs:
            if r.get("type") != rtype or strip_dot(r.get("name", "")) != strip_dot(name):
                continue
            if content_pred(str(r.get("content", "")).strip().strip('"')):
                return True
        return False

    todo: list[dict] = []
    for mx in outside["mx"]:
        if not zone_has("MX", domain, lambda c, mx=mx: strip_dot(c) == mx["exchange"]):
            todo.append({"type": "MX", "name": domain, "content": mx["exchange"],
                         "priority": mx["priority"], "ttl": 1})
    # every apex TXT rides along (SPF is the critical one; verification TXTs
    # are free to preserve and deleting nothing is the contract)
    for t in outside["apex_txt"]:
        if not zone_has("TXT", domain, lambda c, t=t: c == t):
            todo.append({"type": "TXT", "name": domain, "content": t, "ttl": 1})
    for t in outside["dmarc_txt"]:
        if not zone_has("TXT", f"_dmarc.{domain}", lambda c, t=t: c == t):
            todo.append({"type": "TXT", "name": f"_dmarc.{domain}", "content": t, "ttl": 1})
    for sel, d in outside["dkim"].items():
        name = f"{sel}._domainkey.{domain}"
        for cn in d.get("cname", []):
            if not zone_has("CNAME", name, lambda c, cn=cn: strip_dot(c) == cn):
                todo.append({"type": "CNAME", "name": name, "content": cn,
                             "ttl": 1, "proxied": False})
        for t in d.get("txt", []):
            if not zone_has("TXT", name, lambda c, t=t: c == t):
                todo.append({"type": "TXT", "name": name, "content": t, "ttl": 1})
    return todo


def phase_zone_email(slug: str, domain: str, apply: bool) -> tuple[Phase, dict | None]:
    ph = Phase("ZONE + EMAIL SAFETY")
    zone = None
    try:
        zone = find_zone(domain)
    except Exception as e:
        ph.fail(f"Cloudflare zone lookup failed: {str(e)[:160]}")
        return ph, None

    if zone:
        ph.note(f"zone exists: {zone['id']} (status {zone.get('status')})")
    elif apply:
        try:
            acct = os.environ["CLOUDFLARE_ACCOUNT_ID"]
            zone = cf("POST", "/zones", {"name": domain, "account": {"id": acct},
                                         "type": "full"})["result"]
            ph.note(f"zone CREATED: {zone['id']} — assigned NS "
                    + ", ".join(zone.get("name_servers") or []))
        except Exception as e:
            ph.fail(f"zone create failed: {str(e)[:200]}")
            return ph, None
    else:
        ph.note("no Cloudflare zone yet (would create one)")

    # capture the world BEFORE flipping anything
    outside, doh_errors = capture_outside_dns(domain)
    zrecs: list[dict] = []
    if zone:
        try:
            zrecs = zone_records(zone["id"])
        except Exception as e:
            ph.note(f"zone record listing failed ({str(e)[:120]}) — snapshot has DoH only")
    snap = {"domain": domain, "captured_at": now_iso(),
            "authoritative": outside,
            "cf_zone": {"zone_id": zone.get("id") if zone else None,
                        "name_servers": (zone or {}).get("name_servers") or [],
                        "records": [{k: r.get(k) for k in
                                     ("id", "type", "name", "content", "priority", "proxied")}
                                    for r in zrecs]}}
    sp = snapshot_path(slug)
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(json.dumps(snap, indent=1) + "\n")
    ph.note(f"snapshot written: {sp.relative_to(ROOT)} "
            f"(MX {len(outside['mx'])}, apex TXT {len(outside['apex_txt'])}, "
            f"DKIM selectors {sorted(outside['dkim']) or 'none'}, "
            f"DMARC {'yes' if outside['dmarc_txt'] else 'no'})")

    if doh_errors >= 4 and not outside["mx"] and not outside["apex_txt"]:
        ph.fail("DoH capture mostly failed — refusing to certify email safety blind")
        return ph, zone
    if not outside["mx"]:
        ph.note("no MX on authoritative DNS — domain carries no email; nothing to preserve")

    todo = email_records_needed(domain, outside, zrecs)
    if not todo:
        ph.note("CF zone already holds every email record the outside world serves")
    elif apply and zone:
        created = failed = 0
        for payload in todo:
            try:
                cf("POST", f"/zones/{zone['id']}/dns_records", payload)
                created += 1
                ph.note(f"created {payload['type']} {payload['name']} -> "
                        f"{str(payload['content'])[:60]}")
            except Exception as e:
                failed += 1
                ph.fail(f"create {payload['type']} {payload['name']} failed: {str(e)[:140]}")
        ph.note(f"email records: {created} created, {failed} failed, 0 deleted (never)")
    else:
        for payload in todo:
            ph.note(f"WOULD create {payload['type']} {payload['name']} -> "
                    f"{str(payload['content'])[:60]}")
    return ph, zone


# ---- phase 3: nameserver gate ------------------------------------------------

def phase_ns(domain: str, zone: dict | None) -> Phase:
    ph = Phase("NS CHECK")
    expected = sorted(strip_dot(n) for n in ((zone or {}).get("name_servers") or []))
    try:
        current = sorted(strip_dot(d) for d in doh(domain, "NS"))
    except Exception as e:
        ph.fail(f"DoH NS lookup failed: {str(e)[:140]}")
        return ph
    ph.note(f"current NS: {', '.join(current) or '(none)'}")
    if not expected:
        ph.fail("zone has no assigned Cloudflare nameservers yet (zone not created) — "
                "run with --apply to create it and get the pair the client must set")
        ph.waiting_on_ns = True
        return ph
    ph.note(f"required NS: {', '.join(expected)}")
    if current == expected:
        ph.note("nameservers point at our Cloudflare zone")
        if (zone or {}).get("status") != "active":
            if nudge_zone_activation(zone):
                ph.note("zone was pending — activation re-check flipped it ACTIVE")
            else:
                ph.note("zone still pending on Cloudflare's side — activation "
                        "re-check triggered; safe to continue (NS verified)")
    else:
        ph.fail("waiting on nameserver transfer — the client must set exactly: "
                + ", ".join(expected))
        ph.waiting_on_ns = True
    return ph


# ---- phase 4: attach Pages ----------------------------------------------------

def phase_attach(slug: str, domain: str, zone: dict | None, rec: dict, apply: bool) -> Phase:
    ph = Phase("ATTACH PAGES")
    project = pages_project_name(rec, slug)
    acct = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
    try:
        existing = pages_domains(project)
    except Exception as e:
        ph.fail(f"Pages domain listing failed: {str(e)[:160]}")
        return ph
    if existing is None:
        ph.fail(f"Pages project {project} not found — was the site scaffolded?")
        return ph
    ph.note(f"Pages project: {project} (custom domains now: {existing or 'none'})")

    for name in (domain, f"www.{domain}"):
        if name in existing:
            ph.note(f"{name} already attached")
        elif apply:
            try:
                cf("POST", f"/accounts/{acct}/pages/projects/{project}/domains",
                   {"name": name}, pages=True)
                ph.note(f"attached {name}")
            except Exception as e:
                ph.fail(f"attach {name} failed: {str(e)[:160]}")
        else:
            ph.note(f"WOULD attach {name}")

    # DNS records Pages needs: apex + www CNAME -> {project}.pages.dev,
    # proxied. Only ADDRESS records at exactly these two names are touched;
    # replacing them is the cutover itself (full pre-state in the snapshot).
    if not zone:
        ph.note("no zone yet — DNS records evaluated on --apply after zone creation"
                if not apply else "")
        if apply:
            ph.fail("no zone to write Pages DNS records into")
        else:
            ph.note(f"WOULD ensure CNAME {domain} + www.{domain} -> {project}.pages.dev (proxied)")
        return ph
    target = f"{project}.pages.dev"
    try:
        zrecs = zone_records(zone["id"])
    except Exception as e:
        ph.fail(f"zone record listing failed: {str(e)[:140]}")
        return ph
    for name in (domain, f"www.{domain}"):
        addr = [r for r in zrecs if strip_dot(r.get("name", "")) == name
                and r.get("type") in ("A", "AAAA", "CNAME")]
        good = [r for r in addr if r.get("type") == "CNAME"
                and strip_dot(str(r.get("content", ""))) == target]
        if good:
            ph.note(f"{name} CNAME -> {target} already in place")
            continue
        payload = {"type": "CNAME", "name": name, "content": target,
                   "ttl": 1, "proxied": True}
        if not apply:
            ph.note(f"WOULD point {name} -> {target}"
                    + (f" (replacing {len(addr)} old address record(s): "
                       + ", ".join(f"{r['type']} {r['content']}" for r in addr[:4]) + ")"
                       if addr else ""))
            continue
        try:
            if addr:
                cf("PUT", f"/zones/{zone['id']}/dns_records/{addr[0]['id']}", payload)
                ph.note(f"repointed {name}: {addr[0]['type']} {addr[0]['content']} "
                        f"-> CNAME {target}")
                for extra in addr[1:]:
                    cf("DELETE", f"/zones/{zone['id']}/dns_records/{extra['id']}")
                    ph.note(f"removed surplus address record at {name}: "
                            f"{extra['type']} {extra['content']} (preserved in snapshot)")
            else:
                cf("POST", f"/zones/{zone['id']}/dns_records", payload)
                ph.note(f"created CNAME {name} -> {target} (proxied)")
        except Exception as e:
            ph.fail(f"DNS for {name} failed: {str(e)[:160]}")
    return ph


# ---- phase 5: stamp + register -------------------------------------------------

def phase_stamp(slug: str, domain: str, zone: dict | None, apply: bool) -> Phase:
    ph = Phase("STAMP + REGISTER", critical=True)
    if not apply:
        ph.note(f"WOULD stamp domain={domain} on clients/{slug}.json + marketing_sites, "
                "run gsc_register.py --domain, IndexNow ping")
        return ph
    rec = ch.client_record(slug)
    rec["domain"] = domain
    if zone:
        rec["zone"] = {"id": zone.get("id"), "name": zone.get("name"),
                       "status": zone.get("status"),
                       "name_servers": zone.get("name_servers") or []}
    # legacy origin: where the apex pointed before us (snapshot capture)
    try:
        snap = json.loads(snapshot_path(slug).read_text())
        legacy = (snap["authoritative"].get("apex_cname") or
                  snap["authoritative"].get("apex_a") or [])
        if legacy:
            rec.setdefault("apex_cutover", {})["legacy_origin"] = legacy[0]
    except Exception:
        pass
    rec["updated_at"] = now_iso()
    ch.save_client_record(slug, rec)
    ph.note(f"clients/{slug}.json: domain stamped"
            " (cut_over_at waits for outside verification)")
    try:
        body = {"domain": domain}
        if zone:
            body["cf_zone_id"] = zone.get("id")
        sb_patch(f"/rest/v1/marketing_sites?rank_ai_slug=eq.{slug}", body)
        ph.note("marketing_sites: domain" + (" + cf_zone_id" if zone else "") + " updated")
    except Exception as e:
        ph.fail(f"marketing_sites update failed: {str(e)[:160]}")

    # GSC + IndexNow are fail-soft: DNS propagation can lag; re-runs re-try.
    r = subprocess.run(["python3", str(ROOT / "scripts" / "gsc_register.py"),
                        "--domain", domain],
                       cwd=str(ROOT), capture_output=True, text=True, timeout=600)
    tail = (r.stdout + r.stderr).strip().splitlines()[-3:]
    ph.note(("gsc_register OK: " if r.returncode == 0 else "gsc_register (non-fatal) rc="
             + str(r.returncode) + ": ") + " | ".join(tail))
    r = subprocess.run(["python3", str(ROOT / "scripts" / "build_site.py"),
                        "indexnow", "--slug", slug],
                       cwd=str(ROOT), capture_output=True, text=True, timeout=600)
    tail = (r.stdout + r.stderr).strip().splitlines()[-2:]
    ph.note("indexnow: " + " | ".join(tail))
    return ph


# ---- phase 6: outside verification ---------------------------------------------

def phase_verify(slug: str, domain: str, apply: bool) -> Phase:
    ph = Phase("OUTSIDE VERIFICATION")
    want = local_llms_first_line(slug)
    if not want:
        ph.fail(f"sites/{slug}/public/llms.txt missing — nothing to verify identity against")
        return ph
    try:
        ips = doh(domain, "A")
    except Exception as e:
        ph.fail(f"DoH A lookup failed: {str(e)[:140]}")
        return ph
    if not ips:
        ph.fail("apex resolves to no A records from outside")
        return ph
    ph.note(f"apex A (DoH): {', '.join(ips[:4])}")

    got_line, ok_ip = "", None
    for ip in ips[:3]:
        code, body = curl_resolve(domain, ip, "/llms.txt")
        if code == 200 and body.strip():
            got_line = next((l.strip() for l in body.splitlines() if l.strip()), "")
            ok_ip = ip
            break
    if not ok_ip:
        ph.fail("llms.txt unreachable over HTTPS at the DoH-resolved IPs")
        return ph
    if got_line != want:
        ph.fail(f"llms.txt identity mismatch — live first line {got_line[:60]!r} != "
                f"repo {want[:60]!r} (this is not our build yet)")
        return ph
    ph.note(f"llms.txt identity check passed via {ok_ip} ({want[:50]!r})")

    code, html = curl_resolve(domain, ok_ip, "/")
    if code != 200:
        ph.fail(f"homepage HTTP {code} at {ok_ip}")
        return ph
    if "https://None" in html:
        ph.fail('live HTML still contains "https://None" — rehydration incomplete; '
                "redeploy main and re-run")
        return ph
    ph.note('homepage 200, no "https://None" in live HTML')

    if apply:
        rec = ch.client_record(slug)
        stamp = now_iso()
        rec["cut_over_at"] = rec.get("cut_over_at") or stamp
        # setdefault must run before the read: Python evaluates the right
        # side first, so the one-liner KeyError'd on first-time cutovers.
        apex = rec.setdefault("apex_cutover", {})
        apex["completed_at"] = apex.get("completed_at") or stamp
        rec["updated_at"] = stamp
        ch.save_client_record(slug, rec)
        try:
            sb_patch(f"/rest/v1/marketing_sites?rank_ai_slug=eq.{slug}",
                     {"apex_live": True, "apex_completed_at": rec["cut_over_at"],
                      "domain": domain})
            ph.note(f"LIVE: cut_over_at stamped + marketing_sites.apex_live=true")
        except Exception as e:
            ph.fail(f"apex_live update failed: {str(e)[:160]}")
        work_log(company_id_for_slug(slug), "site", "apex-cutover",
                 f"Website launched on the client's own domain (https://{domain}/) "
                 "with email records preserved and the launch verified from outside.",
                 evidence={"slug": slug, "domain": domain, "verified_ip": ok_ip},
                 source="cutover_execute.py")
        # Launch text to the client (Santino 2026-09-04, after the CRW
        # app-button cutover): Monica delivers it with every guard intact;
        # the [FROM SANTINO] directive tag makes it land same-day instead of
        # waiting out cooldowns. Best-effort — a note failure must never
        # fail a completed cutover.
        try:
            sb_post("/rest/v1/marketing_ops_notes", {
                "company_id": company_id_for_slug(slug),
                "body": ("[FROM SANTINO] Text the client this, word for "
                         "word: Big news! Your new website is officially "
                         f"live on your domain at https://{domain}/ Take a "
                         "look when you get a chance and let me know what "
                         "you think. Google will start picking it up over "
                         "the next few days and we handle all of that for "
                         "you.")})
            ph.note("launch text queued for Monica")
        except Exception as e:  # noqa: BLE001
            ph.fail(f"launch-text note failed (cutover itself is DONE): "
                    f"{str(e)[:120]}")
    else:
        ph.note("(dry run — would stamp cut_over_at + apex_live now)")
    return ph


# ---- phase 7: baseline ----------------------------------------------------------

def dfs_backlinks_summary(domain: str) -> dict | None:
    creds = ch.load_dfs_creds_soft()
    if not creds:
        return None
    import base64
    auth = base64.b64encode(f"{creds[0]}:{creds[1]}".encode()).decode()
    r = requests.post("https://api.dataforseo.com/v3/backlinks/summary/live",
                      data=json.dumps([{"target": domain, "include_subdomains": True}]),
                      timeout=90,
                      headers={"Authorization": "Basic " + auth,
                               "Content-Type": "application/json"})
    task = (r.json().get("tasks") or [{}])[0]
    if task.get("status_code") != 20000:
        raise RuntimeError(f"DFS {task.get('status_code')} {task.get('status_message')}")
    item = ((task.get("result") or [{}])[0] or {})
    return {"rank": item.get("rank"), "backlinks": item.get("backlinks"),
            "referring_domains": item.get("referring_domains"),
            "referring_main_domains": item.get("referring_main_domains"),
            "broken_backlinks": item.get("broken_backlinks"),
            "first_seen": item.get("first_seen"),
            "cost_usd": float(task.get("cost") or 0)}


def citations_counts(slug: str) -> dict | None:
    cid = company_id_for_slug(slug)
    if not cid:
        return None
    rows = sb_get("/rest/v1/user_integrations?provider=eq.citations"
                  f"&client_id=eq.{cid}&select=connection_metadata")
    for r in rows or []:
        nap = ((r.get("connection_metadata") or {}).get("nap_audit") or {})
        if nap:
            st = [str((v or {}).get("status") or "") for v in nap.values()]
            return {"found": st.count("found"),
                    "discrepancy": st.count("discrepancy"),
                    "missing": st.count("missing"),
                    "platforms_audited": len(st)}
    return None


def phase_baseline(slug: str, domain: str, apply: bool) -> Phase:
    ph = Phase("BASELINE", critical=False)
    bp = baseline_path(slug)
    if bp.exists():
        try:
            if (json.loads(bp.read_text()).get("backlinks") or {}).get("backlinks") is not None:
                ph.note(f"baseline already captured ({bp.relative_to(ROOT)}) — not re-buying")
                return ph
        except Exception:
            pass
    if not apply:
        ph.note("WOULD capture DataForSEO backlinks_summary (one paid call: "
                "rank/backlinks/referring domains) + citations found-count "
                f"-> {bp.relative_to(ROOT)}")
        return ph
    out = {"domain": domain, "captured_at": now_iso(),
           "backlinks": None, "citations": None}
    try:
        out["backlinks"] = dfs_backlinks_summary(domain)
        if out["backlinks"]:
            b = out["backlinks"]
            ph.note(f"backlinks_summary: rank {b['rank']}, {b['backlinks']} backlinks, "
                    f"{b['referring_domains']} referring domains "
                    f"(${b['cost_usd']:.4f})")
        else:
            ph.note("no DataForSEO creds — backlinks baseline skipped")
    except Exception as e:
        ph.fail(f"backlinks baseline failed: {str(e)[:160]}")
    try:
        out["citations"] = citations_counts(slug)
        ph.note("citations: " + (json.dumps(out["citations"])
                                 if out["citations"] else "no nap_audit on file yet"))
    except Exception as e:
        ph.note(f"citations count failed (non-fatal): {str(e)[:120]}")
    bp.parent.mkdir(parents=True, exist_ok=True)
    bp.write_text(json.dumps(out, indent=1) + "\n")
    ph.note(f"wrote {bp.relative_to(ROOT)}")
    return ph


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------

def commit_artifacts(slug: str) -> None:
    """Persist stamps + snapshots back to the monorepo (Railway containers are
    ephemeral; an uncommitted cut_over_at would be REVERTED by the next
    supabase_sync from a fresh checkout). Same pull-rebase-push dance as
    content_writer.commit_and_sync. Fail-soft: a push failure is loud but
    never un-launches a verified site."""
    files = [f"clients/{slug}.json", f"clients/{slug}/cutover"]
    try:
        subprocess.run(["git", "add", *files], cwd=ROOT, check=True,
                       capture_output=True, text=True)
        r = subprocess.run(
            ["git", "commit", "-m",
             f"cutover: {slug} one-click cutover artifacts [automated]\n\n"
             "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>",
             "--", *files],
            cwd=ROOT, capture_output=True, text=True)
        if r.returncode != 0:
            if "nothing to commit" in (r.stdout + r.stderr).lower():
                print("  commit: nothing new")
                return
            print(f"  commit failed (non-fatal): {(r.stdout + r.stderr)[-200:]}")
            return
        from repo_git_guard import safe_sync
        print("  committed + pushed" if safe_sync(ROOT, actor="cutover_execute")
              else "  committed locally (sync deferred — see guard message)")
    except Exception as e:
        print(f"  commit/push failed (non-fatal): {str(e)[:160]}")


def cmd_run(slug: str, apply: bool) -> int:
    mode = "APPLY" if apply else "DRY RUN"
    print(f"== ONE-CLICK CUTOVER {slug} — {mode} ==")
    phases: list[Phase] = []
    stopped_at: Phase | None = None
    waiting_ns = False

    def report(ph: Phase, idx: int) -> None:
        state = "ok" if ph.ok else ("STOP" if ph.critical else "warn")
        print(f"[{idx}/7] {ph.name:<22} {state}")
        for n in ph.notes:
            print(f"       - {n}")

    ph1, domain = phase_preflight(slug, apply)
    phases.append(ph1)
    report(ph1, 1)
    if not ph1.ok and apply:
        stopped_at = ph1
    if not domain:
        print("\nno domain — nothing further can even be evaluated")
        return 2

    zone = None
    if stopped_at is None:
        ph2, zone = phase_zone_email(slug, domain, apply and stopped_at is None)
        phases.append(ph2)
        report(ph2, 2)
        if not ph2.ok and apply:
            stopped_at = ph2
    if stopped_at is None or not apply:
        ph3 = phase_ns(domain, zone)
        phases.append(ph3)
        report(ph3, 3)
        waiting_ns = ph3.waiting_on_ns
        if not ph3.ok and apply and stopped_at is None:
            stopped_at = ph3
    rec = ch.client_record(slug)
    if stopped_at is None or not apply:
        ph4 = phase_attach(slug, domain, zone, rec, apply and stopped_at is None)
        phases.append(ph4)
        report(ph4, 4)
        if not ph4.ok and apply and stopped_at is None:
            stopped_at = ph4
    if stopped_at is None or not apply:
        ph5 = phase_stamp(slug, domain, zone, apply and stopped_at is None)
        phases.append(ph5)
        report(ph5, 5)
        if not ph5.ok and apply and stopped_at is None:
            stopped_at = ph5
    if stopped_at is None or not apply:
        ph6 = phase_verify(slug, domain, apply and stopped_at is None)
        phases.append(ph6)
        report(ph6, 6)
        if not ph6.ok and apply and stopped_at is None:
            stopped_at = ph6
    if stopped_at is None or not apply:
        ph7 = phase_baseline(slug, domain, apply and stopped_at is None)
        phases.append(ph7)
        report(ph7, 7)

    if apply:
        commit_artifacts(slug)

    failed = [p for p in phases if not p.ok]
    print()
    if not failed:
        print(f"== CUTOVER COMPLETE — https://{domain}/ verified LIVE from outside ==")
        return 0
    # "waiting on NS" is only the headline when it is the ONLY blocker before
    # the gate — a failed pre-flight or email phase must not hide behind it.
    if waiting_ns and all(p.ok for p in phases if p.name in ("PRE-FLIGHT", "ZONE + EMAIL SAFETY")):
        expected = ", ".join((zone or {}).get("name_servers") or []) or "(create zone first)"
        print(f"== WAITING ON NAMESERVER TRANSFER — client must set: {expected} ==")
        print("   re-run after the registrar change propagates; every phase is idempotent")
        return 3
    if apply and stopped_at:
        print(f"== STOPPED at {stopped_at.name} (critical) — later phases not attempted ==")
    else:
        print(f"== {len(failed)} phase(s) not ready: "
              + ", ".join(p.name for p in failed) + " ==")
    return 2


# ---------------------------------------------------------------------------
# provision — phases 2+3 only (zone + email snapshot + NS report)
# ---------------------------------------------------------------------------

def cmd_provision(slug: str, apply: bool) -> int:
    """Provision the domain WITHOUT the site-readiness pre-flight.

    Built for the Air Care case (2026-08-17): the build is staging-only —
    pushed_main is unmet so `run --apply` rightly refuses at PRE-FLIGHT —
    but the Cloudflare zone must exist before there IS a nameserver pair to
    hand the client, and the email snapshot should be captured while the OLD
    site's DNS still serves. This executes exactly phases 2 (zone + email
    safety) and 3 (NS gate) and reports the assigned pair. It never
    attaches, stamps, or verifies — the full `run` owns those behind its
    pre-flight."""
    mode = "APPLY" if apply else "DRY RUN"
    print(f"== PROVISION {slug} (zone + email snapshot + NS report) — {mode} ==")
    domain = resolve_domain_soft(slug)
    if not domain:
        print(f"no real domain on clients/{slug}.json (domain and "
              "cutover_prep.domain both empty/.invalid) — attach one first")
        return 2
    print(f"domain: {domain}")

    # informational only — the 301 harvest belongs to run's pre-flight, but
    # it must happen while the old site still serves, so say so out loud.
    prep = ch.client_record(slug).get("cutover_prep") or {}
    age = ch._prep_age_days(prep)
    if age is None or age > ch.STALE_DAYS:
        print(f"  note: cutover_prep {'missing' if age is None else f'{age:.0f}d stale'}"
              " — capture the 301 harvest while the old site still serves"
              " (cutover_harvest harvest + map --apply, or the full run)")
    else:
        print(f"  cutover_prep fresh: harvested {age:.1f}d ago, "
              f"{prep.get('url_count')} URLs, {prep.get('redirects_added')} redirects staged")

    def report(ph: Phase, idx: int) -> None:
        print(f"[{idx}/2] {ph.name:<22} {'ok' if ph.ok else 'STOP'}")
        for n in ph.notes:
            print(f"       - {n}")

    ph2, zone = phase_zone_email(slug, domain, apply)
    report(ph2, 1)
    if not ph2.ok and apply:
        commit_artifacts(slug)  # the snapshot is knowledge worth keeping
        print("\n== STOPPED at ZONE + EMAIL SAFETY — fix and re-run (idempotent) ==")
        return 2

    ph3 = phase_ns(domain, zone)
    report(ph3, 2)
    if apply:
        commit_artifacts(slug)

    pair = ", ".join((zone or {}).get("name_servers") or [])
    if ph3.waiting_on_ns:
        print(f"\n== PROVISIONED — WAITING ON NAMESERVER TRANSFER — client must set: "
              f"{pair or '(no zone yet — re-run with --apply to create it)'} ==")
        print("   launch itself stays behind the full run's site-readiness pre-flight")
        return 3
    if not ph3.ok or not ph2.ok:
        print("\n== provision not clean — see notes above; re-run is safe ==")
        return 2
    print(f"\n== PROVISIONED — nameservers already point at our zone ({pair}) ==")
    print("   next: the full `run --apply` (pre-flight + attach + verify)")
    return 0


# ---------------------------------------------------------------------------
# status — the JSON the app's readiness panel polls
# ---------------------------------------------------------------------------

def cmd_status(slug: str) -> int:
    out: dict = {"slug": slug, "checked_at": now_iso(), "domain": None,
                 "apex_live": False, "cut_over_at": None,
                 "ns": {"required": None, "current": None, "zone_exists": False},
                 "phases": {}, "next_action": "prep_incomplete"}
    try:
        rec = ch.client_record(slug)
    except SystemExit:
        out["error"] = f"no client record for {slug}"
        print(json.dumps(out, indent=1))
        return 1
    domain = resolve_domain_soft(slug)
    out["domain"] = domain
    out["cut_over_at"] = rec.get("cut_over_at")
    ph: dict = out["phases"]

    # prep
    prep = rec.get("cutover_prep") or {}
    age = ch._prep_age_days(prep)
    build = rec.get("build") or {}
    hydrated = None
    if domain:
        bt = ROOT / "sites" / slug / "src" / "lib" / "brand.ts"
        ac = ROOT / "sites" / slug / "astro.config.mjs"
        try:
            hydrated = all(p.exists() and "https://None" not in p.read_text()
                           and f"https://{domain}" in p.read_text() for p in (bt, ac))
        except OSError:
            hydrated = False
    prep_ready = bool(domain and age is not None and age <= ch.STALE_DAYS
                      and build.get("last_pushed_main_at") and hydrated)
    ph["prep"] = {
        "ready": prep_ready,
        "domain_known": bool(domain),
        "harvest_age_days": round(age, 1) if age is not None else None,
        "redirects_staged": prep.get("redirects_added"),
        "pushed_main": bool(build.get("last_pushed_main_at")),
        "domain_hydrated": hydrated,
        "detail": ("ready" if prep_ready else
                   "no real domain" if not domain else
                   "301 harvest missing/stale" if age is None or age > ch.STALE_DAYS else
                   "site not pushed to main" if not build.get("last_pushed_main_at") else
                   "brand.ts/astro.config still carry a stale domain (launch heals + redeploys)"),
    }

    zone = None
    if domain:
        try:
            zone = find_zone(domain)
        except Exception as e:
            ph["email"] = {"ready": False, "detail": f"zone lookup failed: {str(e)[:120]}"}
    expected_ns = sorted(strip_dot(n) for n in ((zone or {}).get("name_servers") or []))

    # email: snapshot captured + zone holds MX when the outside world has MX
    if "email" not in ph:
        snap_p = snapshot_path(slug)
        snap = None
        if snap_p.exists():
            try:
                snap = json.loads(snap_p.read_text())
            except ValueError:
                snap = None
        if not domain:
            ph["email"] = {"ready": False, "detail": "no domain"}
        elif not snap:
            ph["email"] = {"ready": False,
                           "detail": "DNS snapshot not captured yet (launch captures it)"}
        else:
            outside_mx = (snap.get("authoritative") or {}).get("mx") or []
            if not zone:
                ph["email"] = {"ready": False, "snapshot": True,
                               "detail": "no Cloudflare zone yet (launch creates it)"}
            elif not outside_mx:
                ph["email"] = {"ready": True, "snapshot": True, "mx_count": 0,
                               "detail": "no MX anywhere — domain carries no email"}
            else:
                try:
                    zmx = [r for r in zone_records(zone["id"])
                           if r.get("type") == "MX"
                           and strip_dot(r.get("name", "")) == domain]
                    ph["email"] = {"ready": len(zmx) > 0, "snapshot": True,
                                   "mx_count": len(zmx),
                                   "detail": (f"{len(zmx)} MX record(s) staged in zone"
                                              if zmx else "MX records not yet in zone")}
                except Exception as e:
                    ph["email"] = {"ready": False,
                                   "detail": f"zone records unreadable: {str(e)[:120]}"}

    # ns
    current_ns: list[str] = []
    if domain:
        try:
            current_ns = sorted(strip_dot(d) for d in doh(domain, "NS"))
        except Exception:
            pass
    ns_ready = bool(expected_ns) and current_ns == expected_ns
    if ns_ready and zone and zone.get("status") != "active":
        # self-heal: the transfer is done, Cloudflare just hasn't noticed —
        # nudge it so the app's green arrives without a human in the loop
        if nudge_zone_activation(zone):
            zone["status"] = "active"
    # Top-level nameserver facts for the app's reference block (Santino
    # 2026-08-17: "Check launch readiness" never showed WHICH nameservers the
    # client must set). `required` is the zone's ASSIGNED pair — it only
    # exists once the zone does; status stays strictly read-only, so a
    # missing zone reports null here and `run --apply` / `provision --apply`
    # are what create it.
    out["ns"] = {"required": expected_ns or None,
                 "current": current_ns or None,
                 "zone_exists": bool(zone)}
    ph["ns"] = {"ready": ns_ready, "expected_ns": expected_ns or None,
                "current_ns": current_ns or None,
                "detail": ("nameservers point at our zone" if ns_ready else
                           "zone not created yet — launch creates it and reports the pair"
                           if not expected_ns else
                           "waiting on nameserver transfer")}

    # attach
    project = pages_project_name(rec, slug)
    if domain:
        try:
            names = pages_domains(project)
            if names is None:
                ph["attach"] = {"ready": False, "project": project,
                                "detail": f"Pages project {project} not found"}
            else:
                have = {n for n in names}
                ready = domain in have and f"www.{domain}" in have
                ph["attach"] = {"ready": ready, "project": project,
                                "attached": sorted(have) or None,
                                "detail": ("apex + www attached" if ready
                                           else "custom domains not attached yet")}
        except Exception as e:
            ph["attach"] = {"ready": False, "project": project,
                            "detail": f"Pages lookup failed: {str(e)[:120]}"}
    else:
        ph["attach"] = {"ready": False, "detail": "no domain"}

    # verify (the /llms.txt identity probe — same convention as the ledger)
    if domain:
        serving = ch.probe_domain(domain, slug)
        live = serving == "OURS"
        ph["verify"] = {"ready": live, "serving": serving,
                        "detail": ("live site is our build (llms.txt identity match)"
                                   if live else f"domain currently serves: {serving}")}
        out["apex_live"] = bool(rec.get("cut_over_at")) and live
    else:
        ph["verify"] = {"ready": False, "detail": "no domain"}

    if ph["verify"]["ready"] and out["cut_over_at"]:
        out["next_action"] = "live"
    elif not prep_ready:
        out["next_action"] = "prep_incomplete"
    elif not expected_ns:
        out["next_action"] = "provision"          # launch creates zone + shows NS pair
    elif not ns_ready:
        out["next_action"] = "waiting_on_nameservers"
    else:
        out["next_action"] = "run_cutover"

    print(json.dumps(out, indent=1))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("run", help="execute the cutover phases (dry-run default)")
    pr.add_argument("--slug", required=True)
    pr.add_argument("--apply", action="store_true",
                    help="actually create/attach/stamp (default: report only)")
    pp = sub.add_parser("provision",
                        help="phases 2+3 only: zone + email snapshot + NS "
                             "report, no site-readiness pre-flight")
    pp.add_argument("--slug", required=True)
    pp.add_argument("--apply", action="store_true",
                    help="actually create the zone + copy email records")
    ps = sub.add_parser("status", help="JSON phase readiness for the app")
    ps.add_argument("--slug", required=True)
    args = ap.parse_args()
    if args.cmd == "run":
        return cmd_run(args.slug, args.apply)
    if args.cmd == "provision":
        return cmd_provision(args.slug, args.apply)
    return cmd_status(args.slug)


if __name__ == "__main__":
    sys.exit(main())
