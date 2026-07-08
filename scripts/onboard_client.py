#!/usr/bin/env python3
"""
Rank AI client onboarding.

Two-phase provisioning:
  init       Create Cloudflare zone, output NS records, save partial client record.
             Run this BEFORE the client/registrar updates nameservers.
  provision  Verify zone is active, create R2 bucket, bind images.<domain> custom
             domain, smoke-test, finalize client record. Run this AFTER nameservers
             have propagated.

Other subcommands:
  status     Show current state of a client.
  list       List all known clients.

Environment:
  CLOUDFLARE_API_TOKEN     Required. Token must have Zone:Edit (DNS, zone settings).
  CLOUDFLARE_R2_API_TOKEN  Optional. Account-scoped token with R2 Storage:Edit. If set,
                           used for R2 bucket + custom-domain calls. Falls back to
                           CLOUDFLARE_API_TOKEN when unset (e.g., when a single token
                           holds both scopes).
  CLOUDFLARE_ACCOUNT_ID    Required.

Both tokens can be passed as flags (--token, --r2-token, --account-id) instead of env.

Idempotency: safe to re-run any subcommand. State is read from clients/{slug}.json.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verticals  # noqa: E402 — vertical registry (dirs under templates/)

REPO_ROOT = Path(__file__).resolve().parent.parent
CLIENTS_DIR = REPO_ROOT / "clients"
CF_API_BASE = "https://api.cloudflare.com/client/v4"

# ----------------------------------------------------------------------------
# Cloudflare API helper
# ----------------------------------------------------------------------------


class CloudflareError(Exception):
    pass


def cf_api(method: str, path: str, token: str, body: dict | None = None) -> dict:
    """Call Cloudflare API. Raises CloudflareError on non-2xx with full error context."""
    url = f"{CF_API_BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            err_body = json.loads(e.read().decode())
        except Exception:
            err_body = {"raw": e.read().decode(errors="replace") if hasattr(e, "read") else str(e)}
        raise CloudflareError(
            f"{method} {path} -> HTTP {e.code}: {json.dumps(err_body, indent=2)}"
        )
    except urllib.error.URLError as e:
        raise CloudflareError(f"{method} {path} -> network error: {e}")

    if not payload.get("success", False):
        raise CloudflareError(
            f"{method} {path} -> API returned success=false:\n{json.dumps(payload.get('errors'), indent=2)}"
        )
    return payload


# ----------------------------------------------------------------------------
# Client record persistence
# ----------------------------------------------------------------------------


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def client_path(slug: str) -> Path:
    return CLIENTS_DIR / f"{slug}.json"


def load_client(slug: str) -> dict | None:
    p = client_path(slug)
    if not p.exists():
        return None
    return json.loads(p.read_text())


def save_client(client: dict) -> None:
    CLIENTS_DIR.mkdir(parents=True, exist_ok=True)
    client["updated_at"] = now_iso()
    client_path(client["slug"]).write_text(json.dumps(client, indent=2) + "\n")


def derive_slug(domain: str) -> str:
    """narestco.com -> narestco. acme-plumbing.co.uk -> acme-plumbing."""
    bare = domain.lower().strip()
    bare = re.sub(r"^https?://", "", bare)
    bare = bare.rstrip("/")
    bare = re.sub(r"^www\.", "", bare)
    # Take leftmost label as slug seed
    slug = bare.split(".")[0]
    slug = re.sub(r"[^a-z0-9-]", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:32]


def normalize_domain(domain: str) -> str:
    bare = domain.lower().strip()
    bare = re.sub(r"^https?://", "", bare)
    bare = bare.rstrip("/")
    bare = re.sub(r"^www\.", "", bare)
    return bare


# ----------------------------------------------------------------------------
# Subcommand: init  (Phase 1 — zone creation, NS handoff)
# ----------------------------------------------------------------------------


def cmd_init(args) -> int:
    token, account_id = require_creds(args)
    domain = normalize_domain(args.domain)
    slug = args.slug or derive_slug(domain)

    if not args.tier:
        args.tier = "standard"
    if args.tier not in ("standard", "premium", "budget"):
        die(f"--tier must be standard|premium|budget, got: {args.tier}")

    image_policy = {
        "standard": "pro_hero_flash_inline",
        "premium": "pro_all",
        "budget": "flash_all",
    }[args.tier]

    existing = load_client(slug)
    if existing and not args.force:
        print(f"Client {slug!r} already exists at {client_path(slug)}.")
        print(f"Status: {existing.get('status')}")
        print("Re-run with --force to overwrite, or use 'provision' to continue.")
        return 1

    if args.vertical not in verticals.known_verticals():
        die(f"--vertical must be one of: {', '.join(verticals.known_verticals())} "
            f"(dirs under templates/), got: {args.vertical}")

    print(f"==> Initializing client: {args.name}")
    print(f"    slug:     {slug}")
    print(f"    domain:   {domain}")
    print(f"    tier:     {args.tier} (image_policy={image_policy})")
    print(f"    vertical: {args.vertical}")
    print()

    # Step 1: Check if zone already exists in this account
    print("[1/2] Checking Cloudflare for existing zone...")
    zones = cf_api("GET", f"/zones?name={domain}", token)
    zone = None
    if zones["result"]:
        zone = zones["result"][0]
        print(f"      Zone exists: id={zone['id']} status={zone['status']}")
    else:
        # Step 2: Create zone
        print("[2/2] Creating Cloudflare zone...")
        created = cf_api(
            "POST",
            "/zones",
            token,
            {"name": domain, "account": {"id": account_id}, "type": "full"},
        )
        zone = created["result"]
        print(f"      Created zone id={zone['id']}")

    name_servers = zone.get("name_servers") or []
    status = zone.get("status", "pending")

    client = existing or {}
    client.update(
        {
            "slug": slug,
            "display_name": args.name,
            "domain": domain,
            "tier": args.tier,
            "vertical": args.vertical,
            "image_policy": image_policy,
            "contact": args.contact,
            "zone": {
                "id": zone["id"],
                "name": zone["name"],
                "status": status,
                "name_servers": name_servers,
                "created_on": zone.get("created_on"),
            },
            "r2": {"bucket": f"rankai-{slug}", "custom_domain": f"images.{domain}"},
            "status": "ns_active" if status == "active" else "pending_ns",
            "created_at": (existing or {}).get("created_at") or now_iso(),
        }
    )
    save_client(client)
    print()
    print(f"==> Saved client record: {client_path(slug)}")
    print()

    # Output Phase A instructions
    if status == "active":
        print("==> Zone is already ACTIVE. You can run provision now:")
        print(f"    {sys.argv[0]} provision --slug {slug}")
        return 0

    print("==> NEXT STEP — Update nameservers at the registrar")
    print("─" * 70)
    print(f"    At the domain registrar (GoDaddy, Namecheap, etc.) for {domain},")
    print("    replace the current nameservers with these two:")
    print()
    for ns in name_servers:
        print(f"        {ns}")
    print()
    print("    Propagation usually takes 5–60 minutes. Re-run:")
    print(f"        {sys.argv[0]} status --slug {slug}")
    print("    until status is 'ns_active', then run:")
    print(f"        {sys.argv[0]} provision --slug {slug}")
    print("─" * 70)
    return 0


# ----------------------------------------------------------------------------
# Subcommand: provision  (Phase 2 — R2 + custom domain)
# ----------------------------------------------------------------------------


def cmd_provision(args) -> int:
    token, account_id = require_creds(args)
    r2_tok = r2_token(args)
    client = load_client(args.slug)
    if not client:
        die(f"No client record at {client_path(args.slug)}. Run init first.")

    slug = client["slug"]
    domain = client["domain"]
    zone_id = client["zone"]["id"]
    bucket = client["r2"]["bucket"]
    custom_domain = client["r2"]["custom_domain"]

    print(f"==> Provisioning {slug} ({domain})")
    if r2_tok != token:
        print("    (Using separate R2 token for R2 + custom-domain calls.)")
    print()

    # Step 1: Verify zone is active
    print("[1/5] Verifying Cloudflare zone status...")
    zone = cf_api("GET", f"/zones/{zone_id}", token)["result"]
    client["zone"]["status"] = zone["status"]
    if zone["status"] != "active":
        save_client(client)
        die(
            f"Zone status is {zone['status']!r}, not 'active'. Nameservers may not have "
            f"propagated yet. Cloudflare expects:\n  "
            + "\n  ".join(client["zone"]["name_servers"])
            + "\nRe-run provision when status flips to active."
        )
    print(f"      Zone {zone_id} is active.")

    # Step 2: Create R2 bucket
    print(f"[2/5] Creating R2 bucket {bucket!r}...")
    try:
        cf_api(
            "POST",
            f"/accounts/{account_id}/r2/buckets",
            r2_tok,
            {"name": bucket},
        )
        print(f"      Bucket created.")
    except CloudflareError as e:
        if "10004" in str(e) or "already exists" in str(e).lower():
            print(f"      Bucket already exists, skipping.")
        else:
            raise

    # Step 3: Bind custom domain
    print(f"[3/5] Binding custom domain {custom_domain!r} to bucket...")
    try:
        cf_api(
            "POST",
            f"/accounts/{account_id}/r2/buckets/{bucket}/domains/custom",
            r2_tok,
            {
                "domain": custom_domain,
                "zoneId": zone_id,
                "enabled": True,
                "minTLS": "1.2",
            },
        )
        print(f"      Custom domain bound.")
    except CloudflareError as e:
        if "already" in str(e).lower() or "10119" in str(e):
            print(f"      Custom domain already bound, skipping.")
        else:
            raise

    # Step 4: Wait for DNS + TLS
    print(f"[4/5] Waiting for TLS + DNS propagation on https://{custom_domain}/ ...")
    public_url = f"https://{custom_domain}"
    health_url = f"{public_url}/_health.txt"
    deadline = time.time() + 180
    last_err = None
    while time.time() < deadline:
        try:
            req = urllib.request.Request(public_url, method="HEAD")
            urllib.request.urlopen(req, timeout=5)
            print(f"      DNS+TLS ready.")
            break
        except urllib.error.HTTPError as e:
            # 4xx means DNS+TLS work; bucket is empty/no public objects, that's fine
            if 400 <= e.code < 500:
                print(f"      DNS+TLS ready (HTTP {e.code} from empty bucket).")
                break
            last_err = e
        except Exception as e:
            last_err = e
        time.sleep(5)
    else:
        die(f"Timed out waiting for {custom_domain}. Last error: {last_err}")

    # Step 5: Smoke test — write/read/delete a tiny health object
    print(f"[5/5] Smoke test — uploading and fetching {health_url} ...")
    health_content = f"rank-ai onboarding health check\nslug: {slug}\nat: {now_iso()}\n"
    # Note: R2 object PUT via API requires multipart or S3-compatible. We'll defer this
    # to manual verification or a follow-up using rclone/wrangler. For the script's first
    # version, we treat the HEAD success above as "good enough" smoke.
    print(f"      (Object PUT/GET smoke test deferred to manual or wrangler; HEAD proves the binding.)")

    # Finalize record
    client["r2"]["public_url"] = public_url
    client["r2"]["provisioned_at"] = now_iso()
    client["status"] = "active"
    save_client(client)

    print()
    print("==> Provision complete.")
    print(f"    Bucket:       {bucket}")
    print(f"    Public URL:   {public_url}/")
    print(f"    Image policy: {client['image_policy']}")
    print(f"    Record:       {client_path(slug)}")
    print()
    print("    Manual smoke (one-liner):")
    print(f"      curl -X PUT -H 'Content-Type: text/plain' --data 'hello' \\")
    print(f"        https://{account_id}.r2.cloudflarestorage.com/{bucket}/_health.txt \\")
    print(f"        # then: curl {public_url}/_health.txt")

    # Seed the Get-Listed baseline into the Action Plan (non-fatal). A brand-new
    # client gets the core directories now; the monthly authority cron enriches it
    # with AI-cited directories + link-gap once scan data exists.
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from authority_targets import build as build_get_listed
        print("\n[+] Seeding Get-Listed baseline into the Action Plan...")
        build_get_listed(slug, write=True)
    except Exception as e:
        sys.stderr.write(f"    (Get-Listed baseline skipped: {str(e)[:160]})\n")

    # Register the branded photo-upload link in Cloudflare KV (non-fatal), so
    # restorationai.io/gbpphotos/<slug> works immediately with no Worker redeploy.
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from upload_links_sync import main as sync_upload_links
        print("\n[+] Registering photo-upload link (Cloudflare KV)...")
        sync_upload_links()
    except Exception as e:
        sys.stderr.write(f"    (Upload-link KV sync skipped: {str(e)[:160]})\n")
    return 0


# ----------------------------------------------------------------------------
# Subcommand: status
# ----------------------------------------------------------------------------


def cmd_status(args) -> int:
    token, _ = require_creds(args, account_required=False)
    client = load_client(args.slug)
    if not client:
        die(f"No client record at {client_path(args.slug)}.")

    # Refresh zone status from Cloudflare
    zone = cf_api("GET", f"/zones/{client['zone']['id']}", token)["result"]
    client["zone"]["status"] = zone["status"]
    if client["status"] == "pending_ns" and zone["status"] == "active":
        client["status"] = "ns_active"
    save_client(client)

    print(json.dumps(client, indent=2))
    return 0


# ----------------------------------------------------------------------------
# Subcommand: list
# ----------------------------------------------------------------------------


# ----------------------------------------------------------------------------
# Subcommand: mirror-dns  (mirror records from an exported BIND zone file)
# ----------------------------------------------------------------------------

# Record names/types we never carry over to Cloudflare.
SKIP_NAMES = {"_domainconnect", "_cf-custom-hostname", "_cf-custom-hostname.www"}
SKIP_TYPES = {"SOA", "NS"}


def _strip_zone_comment(raw: str) -> str:
    """Strip a BIND `;` comment, but only when the `;` is OUTSIDE quotes.
    TXT rdata legitimately contains semicolons (DMARC/DKIM: "v=DMARC1; p=...");
    the old `raw.split(";", 1)` truncated those records mid-string."""
    in_quotes = False
    for i, ch in enumerate(raw):
        if ch == '"':
            in_quotes = not in_quotes
        elif ch == ";" and not in_quotes:
            return raw[:i]
    return raw


def parse_zonefile(path: Path, origin_hint: str | None = None) -> list[dict]:
    """Minimal BIND zone parser for GoDaddy/cPanel-style exports.
    Supports A, AAAA, CNAME, MX, TXT, SRV. Not a full RFC 1035 implementation.
    """
    origin = (origin_hint or "").rstrip(".") + "." if origin_hint else None
    records: list[dict] = []
    current_default_ttl = 3600
    for raw in path.read_text().splitlines():
        line = _strip_zone_comment(raw).strip()
        if not line:
            continue
        if line.startswith("$ORIGIN"):
            origin = line.split()[1].rstrip(".") + "."
            continue
        if line.startswith("$TTL"):
            current_default_ttl = int(line.split()[1])
            continue
        # SOA records often span multiple lines via parens; skip them.
        if " SOA " in line or line.endswith("SOA"):
            # consume until closing paren
            if "(" in line and ")" not in line:
                # would need lookahead; for GoDaddy export, the SOA line opens paren
                continue
            continue
        parts = line.split(None, 4)
        # Expected: <name> <ttl> IN <type> <data...>
        if len(parts) < 5:
            continue
        name, ttl, class_, rtype, rdata = parts
        if class_ != "IN":
            continue
        try:
            ttl_int = int(ttl)
        except ValueError:
            ttl_int = current_default_ttl
        records.append(
            {
                "name": name,
                "ttl": ttl_int,
                "type": rtype.upper(),
                "rdata": rdata.strip(),
            }
        )
    # Drop multi-line SOA continuations like "2026030500", "28800", etc.
    records = [r for r in records if r["type"] in {"A", "AAAA", "CNAME", "MX", "TXT", "SRV", "NS", "SOA"}]
    return records


def fqdn(name: str, zone: str) -> str:
    """Convert a zone-relative name to FQDN. `@` -> zone; bare label -> label.zone.
    Also handles BIND-style trailing `@` like `_sip._tls.@` -> `_sip._tls.<zone>`.
    """
    if name == "@":
        return zone
    if name.endswith("."):
        return name.rstrip(".")
    if name.endswith(".@"):
        return f"{name[:-2]}.{zone}"
    return f"{name}.{zone}"


def to_cf_payload(rec: dict, zone: str) -> dict | None:
    """Translate a parsed BIND record into a Cloudflare DNS record POST body."""
    rtype = rec["type"]
    name = fqdn(rec["name"], zone)
    ttl = rec["ttl"]
    data = rec["rdata"]

    if rtype in {"A", "AAAA"}:
        return {"type": rtype, "name": name, "content": data, "ttl": ttl, "proxied": False}
    if rtype == "CNAME":
        target = data.rstrip(".")
        if target == "@":
            target = zone
        return {"type": "CNAME", "name": name, "content": target, "ttl": ttl, "proxied": False}
    if rtype == "TXT":
        # Strip surrounding quotes if present; Cloudflare will re-quote.
        txt = data
        if txt.startswith('"') and txt.endswith('"'):
            txt = txt[1:-1]
        return {"type": "TXT", "name": name, "content": txt, "ttl": ttl}
    if rtype == "MX":
        # "<priority> <target>"
        prio, target = data.split(None, 1)
        return {
            "type": "MX",
            "name": name,
            "content": target.rstrip("."),
            "priority": int(prio),
            "ttl": ttl,
        }
    if rtype == "SRV":
        # "<priority> <weight> <port> <target>"
        prio, weight, port, target = data.split()
        # Cloudflare SRV records: name is the service label
        return {
            "type": "SRV",
            "name": name,
            "data": {
                "priority": int(prio),
                "weight": int(weight),
                "port": int(port),
                "target": target.rstrip("."),
            },
            "ttl": ttl,
        }
    return None


def cmd_mirror_dns(args) -> int:
    token, _ = require_creds(args, account_required=False)
    client = load_client(args.slug)
    if not client:
        die(f"No client record at {client_path(args.slug)}. Run init first.")

    zone_id = client["zone"]["id"]
    zone_name = client["zone"]["name"]

    zonefile = Path(args.from_zonefile).expanduser()
    if not zonefile.exists():
        die(f"Zone file not found: {zonefile}")

    raw_records = parse_zonefile(zonefile, origin_hint=zone_name)
    print(f"==> Parsed {len(raw_records)} records from {zonefile}")
    print()

    # Existing Cloudflare records (to dedupe)
    existing = cf_api("GET", f"/zones/{zone_id}/dns_records?per_page=200", token)["result"]
    existing_keys = {(r["type"], r["name"], r.get("content", "")) for r in existing}

    added, skipped, failed = [], [], []
    for rec in raw_records:
        # Filter rules
        if rec["type"] in SKIP_TYPES:
            skipped.append((rec, "type in skip-list (Cloudflare manages SOA/NS)"))
            continue
        if rec["name"] in SKIP_NAMES:
            skipped.append((rec, "name in skip-list (stale/GoDaddy-only record)"))
            continue
        payload = to_cf_payload(rec, zone_name)
        if not payload:
            skipped.append((rec, f"unsupported record type {rec['type']}"))
            continue

        # Dedupe key — for SRV the content is in `data`, so use name+type+data target
        if rec["type"] == "SRV":
            target = payload["data"]["target"]
            key = ("SRV", payload["name"], target)
        else:
            key = (payload["type"], payload["name"], payload.get("content", ""))
        if key in existing_keys:
            skipped.append((rec, "already exists in Cloudflare"))
            continue

        label = f"{payload['type']:6} {payload['name']:42}"
        if args.dry_run:
            print(f"  [DRY-RUN] would add: {label} -> {json.dumps(payload, ensure_ascii=False)[:80]}")
            added.append(rec)
            continue
        try:
            cf_api("POST", f"/zones/{zone_id}/dns_records", token, payload)
            print(f"  [OK]      added:    {label} -> {payload.get('content') or payload.get('data')}")
            added.append(rec)
        except CloudflareError as e:
            print(f"  [FAIL]    failed:   {label} :: {e}")
            failed.append((rec, str(e)))

    print()
    print(f"==> Summary: added={len(added)} skipped={len(skipped)} failed={len(failed)}")
    if skipped:
        print()
        print("Skipped records:")
        for rec, reason in skipped:
            print(f"  - {rec['type']:6} {rec['name']:42} :: {reason}")
    if failed:
        print()
        print("Failures (re-run to retry; idempotent):")
        for rec, err in failed:
            print(f"  - {rec['type']:6} {rec['name']:42} :: {err}")
        return 2
    return 0


# ----------------------------------------------------------------------------
# Subcommand: verify-dns  (query Cloudflare's NS directly to confirm mirror)
# ----------------------------------------------------------------------------


def cmd_verify_dns(args) -> int:
    import subprocess

    client = load_client(args.slug)
    if not client:
        die(f"No client record at {client_path(args.slug)}.")

    zone_name = client["zone"]["name"]
    ns = client["zone"]["name_servers"][0]

    print(f"==> Verifying DNS against Cloudflare NS: {ns}")
    print(f"    (This works BEFORE you flip the registrar nameservers, because")
    print(f"     we query Cloudflare directly rather than going through DNS hierarchy.)")
    print()

    queries = [
        ("A", zone_name),
        ("A", f"www.{zone_name}"),
        ("A", f"admin.{zone_name}"),
        ("A", f"mail.{zone_name}"),
        ("CNAME", f"autodiscover.{zone_name}"),
        ("CNAME", f"sip.{zone_name}"),
        ("CNAME", f"lyncdiscover.{zone_name}"),
        ("CNAME", f"msoid.{zone_name}"),
        ("CNAME", f"email.{zone_name}"),
        ("MX", zone_name),
        ("TXT", zone_name),
        ("SRV", f"_sip._tls.{zone_name}"),
        ("SRV", f"_sipfederationtls._tcp.{zone_name}"),
    ]
    failures = 0
    for rtype, name in queries:
        out = subprocess.run(
            ["dig", f"@{ns}", "+short", "+time=5", "+tries=1", name, rtype],
            capture_output=True, text=True, timeout=10,
        )
        result = out.stdout.strip()
        ok = bool(result)
        marker = "✓" if ok else "✗"
        if not ok:
            failures += 1
        first_line = (result.splitlines()[0] if result else "(no answer)")[:80]
        print(f"  {marker} {rtype:6} {name:38} -> {first_line}")

    print()
    if failures:
        print(f"==> {failures} queries returned no answer. Investigate before flipping NS at registrar.")
        return 1
    print("==> All queries returned answers. Safe to flip nameservers at GoDaddy.")
    return 0


# ----------------------------------------------------------------------------
# Subcommand: list
# ----------------------------------------------------------------------------


def cmd_list(args) -> int:
    if not CLIENTS_DIR.exists():
        print("(no clients yet)")
        return 0
    rows = []
    for f in sorted(CLIENTS_DIR.glob("*.json")):
        c = json.loads(f.read_text())
        rows.append((c["slug"], c["domain"], c.get("tier", "?"), c.get("status", "?")))
    if not rows:
        print("(no clients yet)")
        return 0
    w = max(len(r[0]) for r in rows)
    print(f"{'SLUG':<{w}}  DOMAIN                            TIER       STATUS")
    for slug, domain, tier, status in rows:
        print(f"{slug:<{w}}  {domain:<32}  {tier:<9}  {status}")
    return 0


# ----------------------------------------------------------------------------
# CLI plumbing
# ----------------------------------------------------------------------------


def die(msg: str, code: int = 1) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def require_creds(args, account_required: bool = True) -> tuple[str, str | None]:
    token = args.token or os.environ.get("CLOUDFLARE_API_TOKEN")
    account_id = args.account_id or os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    if not token:
        die("Missing CLOUDFLARE_API_TOKEN (env) or --token flag.")
    if account_required and not account_id:
        die("Missing CLOUDFLARE_ACCOUNT_ID (env) or --account-id flag.")
    return token, account_id


def r2_token(args) -> str:
    """R2-scoped token. Falls back to the zone token when not separately provided."""
    return (
        getattr(args, "r2_token", None)
        or os.environ.get("CLOUDFLARE_R2_API_TOKEN")
        or args.token
        or os.environ.get("CLOUDFLARE_API_TOKEN")
        or ""
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="onboard_client",
        description="Rank AI client onboarding (Cloudflare zone + R2 + custom domain).",
    )
    p.add_argument("--token", help="Cloudflare API token (or set CLOUDFLARE_API_TOKEN)")
    p.add_argument(
        "--r2-token",
        dest="r2_token",
        help="Separate R2-scoped token (or set CLOUDFLARE_R2_API_TOKEN). Falls back to --token.",
    )
    p.add_argument(
        "--account-id", help="Cloudflare account ID (or set CLOUDFLARE_ACCOUNT_ID)"
    )

    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("init", help="Phase 1: create zone, output NS for registrar update")
    pi.add_argument("--name", required=True, help='Display name, e.g. "Acme Plumbing"')
    pi.add_argument("--domain", required=True, help="Root domain, e.g. acme.com")
    pi.add_argument("--tier", choices=["standard", "premium", "budget"], default="standard")
    pi.add_argument("--vertical", required=True, choices=verticals.known_verticals(),
                    help="Industry vertical — selects templates/{vertical}/ for the whole "
                         "pipeline (prompts, archetypes, catalogs). REQUIRED so a "
                         "construction/plumbing/HVAC client can never silently receive "
                         "restoration templates (davis incident).")
    pi.add_argument("--contact", default=None, help="Contact email (optional)")
    pi.add_argument("--slug", default=None, help="Override derived slug (optional)")
    pi.add_argument("--force", action="store_true", help="Overwrite existing record")
    pi.set_defaults(func=cmd_init)

    pp = sub.add_parser(
        "provision",
        help="Phase 2: create R2 bucket, bind custom domain, smoke-test (run after NS active)",
    )
    pp.add_argument("--slug", required=True)
    pp.set_defaults(func=cmd_provision)

    ps = sub.add_parser("status", help="Show current state of a client")
    ps.add_argument("--slug", required=True)
    ps.set_defaults(func=cmd_status)

    pm = sub.add_parser(
        "mirror-dns",
        help="Mirror DNS records from an exported BIND zone file into Cloudflare (run before NS flip at registrar)",
    )
    pm.add_argument("--slug", required=True)
    pm.add_argument(
        "--from-zonefile",
        required=True,
        help="Path to exported BIND zone file (e.g., ~/Downloads/example.com.txt)",
    )
    pm.add_argument(
        "--dry-run", action="store_true", help="Preview what would be added without writing"
    )
    pm.set_defaults(func=cmd_mirror_dns)

    pv = sub.add_parser(
        "verify-dns",
        help="Query Cloudflare's NS directly to confirm records resolve (run before NS flip)",
    )
    pv.add_argument("--slug", required=True)
    pv.set_defaults(func=cmd_verify_dns)

    pl = sub.add_parser("list", help="List all known clients")
    pl.set_defaults(func=cmd_list)

    return p


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
