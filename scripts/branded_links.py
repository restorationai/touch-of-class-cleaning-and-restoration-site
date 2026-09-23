#!/usr/bin/env python3
"""branded_links.py — client-domain short links (n8n Phase 3, 2026-09-21).

Carrier filters score the link domain in an SMS against the sender's
registered business; agency-domain links in a client's dispatch texts are
a mismatch signal. For every client with a LIVE site on our Cloudflare,
this provisions a zone-level dynamic redirect:

    https://{client-domain}/s/{code}  --302-->  https://app.restorationai.io/s/{code}

(the exact behavior restorationai.io/s/ has today; the app resolves the
code). The visible domain in the message becomes the client's own.

After the rule verifies live, companies.integration_settings.
branded_link_host = {domain} is stamped — that stamp is the ONLY thing
the n8n mint sites trust when composing a branded URL, so a client
whose rule is missing or broken keeps the restorationai.io fallback.

Idempotent; run per-client or fleet-wide:
    python3 scripts/branded_links.py provision            # every live client
    python3 scripts/branded_links.py provision --slug X   # one client
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

import os  # noqa: E402
from client_ops_sync import _sb  # noqa: E402

# Rulesets write needs the broader token; CLOUDFLARE_R2_API_TOKEN is
# Pages/R2-scoped and 403s on rulesets (verified 2026-09-21).
CF_TOKEN = os.environ["CLOUDFLARE_API_TOKEN"]
RULE_DESC = "branded short links -> app resolver"
PHASE = "http_request_dynamic_redirect"
TARGET = "https://app.restorationai.io"


def _cf(path: str, method: str = "GET", body: dict | None = None) -> dict:
    req = urllib.request.Request(
        f"https://api.cloudflare.com/client/v4{path}", method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {CF_TOKEN}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def live_clients() -> list[tuple[str, str]]:
    out = []
    for p in sorted((ROOT / "clients").glob("*.json")):
        if p.stem == "company_map":
            continue
        try:
            d = json.loads(p.read_text())
        except Exception:  # noqa: BLE001
            continue
        if (d.get("cut_over_at") or d.get("build_status") == "cut_over"
                or (d.get("apex_cutover") or {}).get("done")):
            if d.get("domain"):
                out.append((p.stem, d["domain"]))
    return out


def ensure_rule(domain: str) -> str:
    """Idempotently append the /s/ redirect to the zone. Returns status."""
    zones = _cf(f"/zones?name={domain}")["result"]
    if not zones:
        return "NO-ZONE"
    zid = zones[0]["id"]
    try:
        ep = _cf(f"/zones/{zid}/rulesets/phases/{PHASE}/entrypoint")
        rules = (ep.get("result") or {}).get("rules") or []
    except urllib.error.HTTPError:
        rules = []          # phase entrypoint does not exist yet
    if any(r.get("description") == RULE_DESC for r in rules):
        return "ALREADY"
    rules.append({
        "action": "redirect",
        "expression": 'starts_with(http.request.uri.path, "/s/")',
        "description": RULE_DESC,
        "action_parameters": {"from_value": {
            "status_code": 302,
            "target_url": {"expression":
                           f'concat("{TARGET}", http.request.uri.path)'},
            "preserve_query_string": True}},
    })
    _cf(f"/zones/{zid}/rulesets/phases/{PHASE}/entrypoint", "PUT",
        {"rules": rules})
    return "CREATED"


def verify(domain: str) -> bool:
    req = urllib.request.Request(f"https://{domain}/s/__probe",
                                 method="HEAD")
    try:
        urllib.request.urlopen(req, timeout=20)
    except urllib.error.HTTPError as e:
        return (e.code in (301, 302)
                or e.headers.get("Location", "").startswith(TARGET))
    except Exception:  # noqa: BLE001
        return False
    return False        # a 200 means Pages served it — rule not active


def _verify_redirect(domain: str) -> bool:
    """urllib follows redirects; probe without following."""
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):  # noqa: ANN002, ANN003
            return None
    opener = urllib.request.build_opener(NoRedirect)
    try:
        opener.open(f"https://{domain}/s/__probe", timeout=20)
    except urllib.error.HTTPError as e:
        return e.code in (301, 302) and str(
            e.headers.get("Location", "")).startswith(TARGET)
    except Exception:  # noqa: BLE001
        return False
    return False


def stamp(slug: str, domain: str, apply: bool,
          healthy: bool = True) -> None:
    """healthy=True stamps the domain; healthy=False REMOVES the stamp so
    the master sender quietly falls back to restorationai.io links until
    the rule answers again (a stale stamp = dead links in dispatch texts)."""
    cmap = json.loads((ROOT / "clients" / "company_map.json").read_text())
    cid = cmap.get(slug)
    if not cid:
        print(f"  {slug}: no company id — stamp skipped")
        return
    rows = _sb("GET", f"/rest/v1/companies?id=eq.{cid}"
               "&select=integration_settings") or []
    ints = (rows[0].get("integration_settings") if rows else {}) or {}
    if not healthy:
        # DISS 2026-09-23: one transient probe flap un-stamped a perfectly
        # healthy zone and two dispatch texts went out with fallback links.
        # Require TWO consecutive failed probes before pulling the stamp —
        # a real outage persists; a network hiccup doesn't.
        fails = int(ints.get("branded_link_probe_fails") or 0) + 1
        ints["branded_link_probe_fails"] = fails
        if ints.get("branded_link_host") and fails >= 2 and apply:
            ints.pop("branded_link_host", None)
            _sb("PATCH", f"/rest/v1/companies?id=eq.{cid}",
                {"integration_settings": ints})
            print(f"  {slug}: probe failed twice — stamp REMOVED, links "
                  "fall back to restorationai.io")
        elif apply:
            _sb("PATCH", f"/rest/v1/companies?id=eq.{cid}",
                {"integration_settings": ints})
            print(f"  {slug}: probe failed (strike {fails}/2) — stamp kept")
        return
    if ints.get("branded_link_probe_fails"):
        ints.pop("branded_link_probe_fails", None)
        if ints.get("branded_link_host") == domain and apply:
            _sb("PATCH", f"/rest/v1/companies?id=eq.{cid}",
                {"integration_settings": ints})
            return
    if ints.get("branded_link_host") == domain:
        return
    ints["branded_link_host"] = domain
    if apply:
        _sb("PATCH", f"/rest/v1/companies?id=eq.{cid}",
            {"integration_settings": ints})
        print(f"  {slug}: branded_link_host stamped -> {domain}")


def cmd_provision(args) -> int:
    targets = live_clients()
    if args.slug:
        targets = [t for t in targets if t[0] == args.slug]
        if not targets:
            sys.exit(f"{args.slug} is not a live-site client")
    fails = 0
    for slug, domain in targets:
        try:
            status = ensure_rule(domain)
        except Exception as e:  # noqa: BLE001
            print(f"  {slug} ({domain}): rule FAILED {str(e)[:80]}")
            fails += 1
            continue
        time.sleep(3 if status == "CREATED" else 0)
        ok = _verify_redirect(domain)
        print(f"  {slug} ({domain}): rule {status}, probe "
              f"{'302-OK' if ok else 'NOT REDIRECTING'}")
        if ok:
            stamp(slug, domain, apply=not args.dry_run)
        else:
            stamp(slug, domain, apply=not args.dry_run, healthy=False)
            fails += 1
    print(f"done: {len(targets)} client(s), {fails} failure(s)")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("provision")
    p.add_argument("--slug")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(fn=cmd_provision)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
