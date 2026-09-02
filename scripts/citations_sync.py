#!/usr/bin/env python3
"""Citations -> site schema.org sameAs reconciliation (nightly).

Every client site declares its directory/citation profiles (Yelp, BBB, Angi,
Apple Maps, Bing Places, Houzz, Nextdoor, ...) as `sameAs` URLs in its
JSON-LD. Citations trickle in for weeks after a site launches, so this script
keeps brand.ts's sameAsUrls in sync with the source of truth automatically:

  source of truth   user_integrations provider='citations'
                    connection_metadata.nap_audit — written by
                    citations_audit.py (monthly re-audit via setup_ledger).
                    A listing counts as LIVE when status is 'found' or
                    'discrepancy' (a discrepancy listing still EXISTS — the
                    wrong phone is tracked on the citations card, but the
                    profile is the client's and belongs in sameAs).
  also included     the client's own GBP maps URL (nap_audit.google_listing,
                    fallback clients/{slug}.json gbp.listing_url) and the
                    operator-recorded socials in plan-input brand.same_as_urls.
  injection point   sites/{slug}/src/lib/brand.ts `sameAsUrls: [...]` — the
                    schema renderer (src/lib/schema.ts) already emits
                    `sameAs: brand.sameAsUrls` on both the LocalBusiness and
                    Organization nodes, so a brand.ts edit is the whole change.

Ownership split (so hand-edits survive): entries on the MANAGED directory
domains below are ours to add/remove from the audit result; anything else in
the current sameAsUrls (socials, hand additions) is preserved verbatim, as is
any plan-input same_as_urls entry regardless of domain.

Entity-identity guards (sameAs asserts "this URL is the same entity" — a
wrong URL is worse than a missing one):
  * post/permalink URLs are never profiles (the audit's SERP pass sometimes
    lands on ANOTHER page's post that mentions the client — narestco's
    facebook slot held a sasserrestoration.com post, firedex's the FireDex
    gear manufacturer, 2026-08-11) -> skipped.
  * name-bearing URLs (>=3 alpha path tokens) must pass the same name-token
    guard citations_audit uses; opaque IDs (yelp hashes, bing ypid, apple
    place-id, numeric facebook pages) pass through — they were name-guarded
    against the SERP title at audit time.

Deploy policy: sites already live on main (client record build.
last_pushed_main_at set) get the brand.ts change COMMITTED (subtree split
ships committed history only — an uncommitted edit would not ride the push)
and then `build_site.py sync-deploy --branch main`. Preview-only sites just
get the source edit left in the tree; the nightly workflow's commit step
(or the next deploy) carries it. Idempotent: no set-difference = no write,
no commit, no deploy, quiet line.

Usage: citations_sync.py                 # all eligible clients
       citations_sync.py --slug narestco
       citations_sync.py --dry-run       # report, write nothing
       citations_sync.py --no-deploy     # edit + commit, skip sync-deploy
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from client_ops_sync import _sb, slug_map  # noqa: E402
from citations_audit import PLATFORMS, _guard_ok, _name_tokens  # noqa: E402

# Directory domains WE manage in sameAs (add when the audit says live, drop
# when it says gone). Facebook is deliberately absent: it doubles as a
# plan-input social, and a flaky "missing" must never strip the client's real
# page — facebook entries are only ever ADDED (with the post-URL guard).
_MANAGED_DOMAINS = {
    "yelp.com", "bbb.org", "angi.com", "homeadvisor.com", "thumbtack.com",
    "maps.apple.com", "expertise.com", "nextdoor.com", "houzz.com",
    "porch.com", "homeguide.com", "yellowpages.com",
}

_SAME_AS_RE = re.compile(
    r"^(\s*sameAsUrls:\s*)(\[[^\n]*\])( as string\[\],)\s*$", re.M)

# A post/permalink is never a profile page; houzz 'bo~t_' URLs are category
# BROWSE pages (profiles end '-pf~{id}').
_POST_BITS = ("/posts/", "/photos/", "/videos/", "/reel", "/watch",
              "/permalink", "/story.php", "bo~t_")

# Leading business-name stopwords when deriving the brand token.
_NAME_STOP = {"the", "and", "of", "inc", "llc", "corp", "company"}

# Skip statuses where we should not touch the site at all.
_SKIP_STATUS = {"paused", "cancelled", "canceled", "churned", "inactive", "archived", "suspended"}

_STATE_NAMES = {
    "alabama": "al", "alaska": "ak", "arizona": "az", "arkansas": "ar",
    "california": "ca", "colorado": "co", "connecticut": "ct",
    "delaware": "de", "florida": "fl", "georgia": "ga", "hawaii": "hi",
    "idaho": "id", "illinois": "il", "indiana": "in", "iowa": "ia",
    "kansas": "ks", "kentucky": "ky", "louisiana": "la", "maine": "me",
    "maryland": "md", "massachusetts": "ma", "michigan": "mi",
    "minnesota": "mn", "mississippi": "ms", "missouri": "mo",
    "montana": "mt", "nebraska": "ne", "nevada": "nv",
    "new hampshire": "nh", "new jersey": "nj", "new mexico": "nm",
    "new york": "ny", "north carolina": "nc", "north dakota": "nd",
    "ohio": "oh", "oklahoma": "ok", "oregon": "or", "pennsylvania": "pa",
    "rhode island": "ri", "south carolina": "sc", "south dakota": "sd",
    "tennessee": "tn", "texas": "tx", "utah": "ut", "vermont": "vt",
    "virginia": "va", "washington": "wa", "west virginia": "wv",
    "wisconsin": "wi", "wyoming": "wy", "district of columbia": "dc",
}
_STATES = set(_STATE_NAMES.values())


def _state_code(state: str) -> str:
    """Companies rows hold either the code ('CA') or the full name
    ('South Dakota') — normalize to the lowercase code, '' if unparseable."""
    s = (state or "").strip().lower()
    if s in _STATES:
        return s
    return _STATE_NAMES.get(s, "")


def _url_states(path: str) -> set:
    """Explicit state codes a directory URL declares: whole path segments
    (/tx/, /us/wa/) and city-state segment suffixes (oceanside-ca,
    henderson-nv-1). Slug-internal words never match — only full segments."""
    out: set = set()
    for seg in path.lower().split("/"):
        if not seg:
            continue
        if seg in _STATES:
            out.add(seg)
        m = re.search(r"-([a-z]{2})(?:-\d+)?$", seg)
        if m and m.group(1) in _STATES:
            out.add(m.group(1))
    return out


def _host(url: str) -> str:
    h = urlsplit(url).netloc.lower()
    for pre in ("www.", "m."):
        if h.startswith(pre):
            h = h[len(pre):]
    return h


def _norm(url: str):
    """Identity key for dedupe/compare. Google Maps URLs come in several
    shapes (google.com/maps?cid=X vs maps.google.com/maps?cid=X) — the cid IS
    the identity. Everything else: host (mobile-stripped) + path + query,
    scheme-insensitive."""
    p = urlsplit(url.strip())
    host = _host(url)
    q = parse_qs(p.query)
    if "google." in host and q.get("cid"):
        return ("gmaps", q["cid"][0])
    return (host, p.path.rstrip("/").lower(), p.query.lower())


def _is_managed(url: str) -> bool:
    host = _host(url)
    if any(host == d or host.endswith("." + d) for d in _MANAGED_DOMAINS):
        return True
    path = urlsplit(url).path
    if host.endswith("bing.com") and path.startswith("/maps"):
        return True  # Bing Places
    if ("google." in host or host == "maps.app.goo.gl") \
            and ("maps" in path or "cid=" in urlsplit(url).query):
        return True  # GBP maps URL
    return False


def _brand_token(name: str) -> str:
    """First significant word of the business name — the brand ('coastal',
    'onestop', 'puroclean'). A name-bearing directory URL for the client
    virtually always carries it; a same-industry competitor's does not
    (all-pro's houzz slot held 'onestop-pro-plumbing...', 2026-08-11)."""
    for t in re.findall(r"[a-z0-9]+", (name or "").lower()):
        if len(t) >= 3 and t not in _NAME_STOP:
            return t
    return ""


def _identity_ok(url: str, toks: set, state: str, brand_tok: str) -> tuple[bool, str]:
    """Entity-identity guard. Returns (ok, reason-if-not)."""
    path = urlsplit(url).path.lower()
    if any(b in path for b in _POST_BITS):
        return False, "post/permalink/browse page, not a profile"
    # Name-bearing URLs (slugs spelling words out) must carry the business
    # name; opaque IDs (yelp hashes, bing ypid, numeric facebook) pass — they
    # were name-guarded against the SERP title at audit time. Only tokens
    # inside hyphenated segments count, so hash segments stay opaque.
    alpha = [t for seg in path.split("/") if "-" in seg
             for t in re.findall(r"[a-z]+", seg) if len(t) > 2]
    if len(alpha) >= 3:
        if toks and not _guard_ok(url, toks):
            return False, "name guard failed (likely a different business)"
        if brand_tok and brand_tok not in url.lower():
            return False, (f"brand token '{brand_tok}' missing "
                           "(likely a same-industry competitor)")
        # Geo guard: generic industry tokens ('coastal services', 'cleaning
        # and restoration') let a DIFFERENT company in another state pass the
        # name guard (coastal's homeguide slot held a Corpus Christi TX
        # painter, 2026-08-11). A URL that explicitly declares a state must
        # declare the client's.
        declared = _url_states(path)
        code = _state_code(state)
        if declared and code and code not in declared:
            return False, (f"listing is in {'/'.join(sorted(declared)).upper()}, "
                           f"client is {code.upper()}")
    return True, ""


def _gather(slug: str, md: dict, toks: set, state: str = "",
            brand_tok: str = "") -> tuple[str | None, list, list]:
    """-> (gbp_maps_url, live_directory_urls in PLATFORMS order, skip_notes)."""
    napa = md.get("nap_audit") or {}
    curls = md.get("citation_urls") or {}
    notes: list = []

    g = napa.get("google_listing") or {}
    gbp_url = g.get("url")  # found OR discrepancy: it's still THEIR listing
    if not gbp_url:
        rec_path = ROOT / "clients" / f"{slug}.json"
        if rec_path.exists():
            try:
                gbp_url = (json.loads(rec_path.read_text())
                           .get("gbp") or {}).get("listing_url")
            except (json.JSONDecodeError, OSError):
                pass

    live: list = []
    for key in PLATFORMS:  # stable, deterministic order
        e = napa.get(key) or {}
        url = None
        if e.get("status") in ("found", "discrepancy") and e.get("url"):
            url = e["url"]
        elif key not in napa and curls.get(key):
            url = curls[key]  # human-entered slot the audit never touched
        if not url:
            continue
        ok, why = _identity_ok(url, toks, state, brand_tok)
        if not ok:
            notes.append(f"skip {key}: {why} ({url[:70]})")
            continue
        # Canonicalize mobile hosts (m.yelp.com etc.) — sameAs should point
        # at the canonical profile.
        parts = urlsplit(url)
        if parts.netloc.lower().startswith("m."):
            url = url.replace(f"//{parts.netloc}/", f"//www.{parts.netloc[2:]}/", 1)
        live.append(url)
    return gbp_url, live, notes


def _read_current(brand_path: Path) -> tuple[list | None, str]:
    src = brand_path.read_text()
    if "{{BRAND_" in src:
        return None, "unsubstituted scaffold tokens"
    m = _SAME_AS_RE.search(src)
    if not m:
        return None, "no parseable sameAsUrls line"
    try:
        return json.loads(m.group(2)), ""
    except json.JSONDecodeError:
        return None, "sameAsUrls array is not valid JSON"


def _write_desired(brand_path: Path, desired: list) -> None:
    src = brand_path.read_text()
    new = _SAME_AS_RE.sub(
        lambda m: m.group(1) + json.dumps(desired) + m.group(3), src, count=1)
    brand_path.write_text(new)


def _git(args: list, check: bool = True) -> str:
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                       text=True, timeout=300)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()[:200]}")
    return r.stdout


def sync_client(slug: str, cid: str, md: dict, name: str, state: str,
                dry_run: bool, no_deploy: bool) -> str | None:
    """Reconcile one client. Returns a report line, or None when the site
    isn't eligible (no built brand.ts)."""
    brand_path = ROOT / "sites" / slug / "src" / "lib" / "brand.ts"
    if not brand_path.exists():
        return None
    current, err = _read_current(brand_path)
    if current is None:
        return f"{slug}: SKIP ({err})"

    toks = _name_tokens(name or "")
    gbp_url, live, notes = _gather(slug, md, toks, state, _brand_token(name))

    # Base truth that always survives: plan-input socials/same_as_urls.
    base: list = []
    pi = ROOT / "clients" / slug / "plan-input.json"
    if pi.exists():
        try:
            base = (json.loads(pi.read_text()).get("brand")
                    or {}).get("same_as_urls") or []
        except (json.JSONDecodeError, OSError):
            pass
    base_norms = {_norm(u) for u in base}

    # Preserve: everything not on a managed directory domain, plus anything
    # the operator recorded in plan-input. Managed entries get re-derived.
    keep = [u for u in current
            if _norm(u) in base_norms or not _is_managed(u)]
    # plan-input entries missing from the site (scaffold predates them) come
    # back too.
    seen = {_norm(u) for u in keep}
    for u in base:
        if _norm(u) not in seen:
            keep.append(u)
            seen.add(_norm(u))

    additions: list = []
    for url in ([gbp_url] if gbp_url else []) + live:
        n = _norm(url)
        if n in seen:
            continue
        seen.add(n)
        additions.append(url)

    desired = keep + additions
    if {_norm(u) for u in desired} == {_norm(u) for u in current}:
        return f"{slug}: in sync ({len(current)} sameAs URLs)"

    added = [u for u in desired if _norm(u) not in {_norm(c) for c in current}]
    removed = [u for u in current if _norm(u) not in {_norm(d) for d in desired}]
    verdict = (f"{slug}: {len(current)} -> {len(desired)} sameAs URLs "
               f"(+{len(added)}/-{len(removed)})")
    for nt in notes:
        verdict += f"\n    {nt}"
    if dry_run:
        return verdict + "  [dry-run]"

    _write_desired(brand_path, desired)

    rec_path = ROOT / "clients" / f"{slug}.json"
    rec = {}
    if rec_path.exists():
        try:
            rec = json.loads(rec_path.read_text())
        except (json.JSONDecodeError, OSError):
            rec = {}
    on_main = bool((rec.get("build") or {}).get("last_pushed_main_at"))

    deployed = False
    if on_main and not no_deploy:
        # sync-deploy ships COMMITTED history (git subtree split) — commit
        # this one file first or the deploy would not carry the change.
        rel = f"sites/{slug}/src/lib/brand.ts"
        _git(["add", rel])
        _git(["commit", "-m",
              f"{slug}: sameAs citations sync ({len(desired)} URLs) [automated]",
              "--", rel])
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_site.py"),
                            "sync-deploy", "--slug", slug, "--branch", "main",
                            "--allow-dirty"],
                           capture_output=True, text=True, timeout=900, cwd=ROOT)
        deployed = r.returncode == 0
        if not deployed:
            tail = (r.stderr or r.stdout or "").strip().splitlines()[-1:]
            verdict += f"\n    DEPLOY FAILED: {tail[0][:150] if tail else '?'}"
        else:
            verdict += "  [deployed to main]"
    else:
        verdict += "  [source edit only — next deploy carries it]"

    # App work ledger (fail-open) — the client-visible "what we did" feed.
    try:
        from work_log import work_log
        plat_added = sorted({_host(u) for u in added})
        work_log(cid, "citations", "sameas-sync",
                 f"Website schema updated: {len(desired)} directory and "
                 f"profile links now declared to Google/AI assistants"
                 + (f" (new: {', '.join(plat_added)})." if plat_added else "."),
                 evidence={"slug": slug, "added": added, "removed": removed,
                           "total": len(desired), "deployed": deployed},
                 source="citations_sync.py")
    except Exception:
        pass
    return verdict


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", help="single client")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-deploy", action="store_true",
                    help="edit brand.ts but never sync-deploy")
    a = ap.parse_args()

    inv = {s: c for c, s in slug_map().items()}
    rows = _sb("GET", "/rest/v1/user_integrations?provider=eq.citations"
               "&select=client_id,connection_metadata",
               prefer="return=representation") or []
    by_cid = {r["client_id"]: r.get("connection_metadata") or {} for r in rows}
    companies = {c["id"]: c for c in
                 _sb("GET", "/rest/v1/companies?select=id,name,state",
                     prefer="return=representation") or []}

    slugs = [a.slug] if a.slug else sorted(inv)
    changed = 0
    for slug in slugs:
        cid = inv.get(slug)
        if not cid:
            if a.slug:
                print(f"{slug}: no company mapping")
            continue
        rec_path = ROOT / "clients" / f"{slug}.json"
        status = ""
        if rec_path.exists():
            try:
                status = json.loads(rec_path.read_text()).get("status") or ""
            except (json.JSONDecodeError, OSError):
                pass
        if status in _SKIP_STATUS:
            continue
        md = by_cid.get(cid)
        if not md:
            continue  # citations audit has never run — nothing to declare yet
        co = companies.get(cid) or {}
        line = sync_client(slug, cid, md, co.get("name") or "",
                           (co.get("state") or "").strip(),
                           a.dry_run, a.no_deploy)
        if line is None:
            continue
        if "in sync" not in line:
            changed += 1
        print(line)
    if not changed:
        print("citations_sync: all sites in sync — nothing to do.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
