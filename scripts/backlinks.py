#!/usr/bin/env python3
"""backlinks.py — vendor/association backlink targets (queue build, Santino
2026-07-31: "make it dynamic based on the category the company selects").

The Noah Igler playbook's highest-value gap: supplier/association backlinks
(the Trane-installer pattern). Each active Rank AI client gets a per-category
target list in marketing_backlinks; the app's Connect tab renders it next to
the business listings (client-visible progress, team-workable statuses).

Statuses: target (nothing yet) -> requested (outreach made, human sets) ->
live (checker CONFIRMED a link/mention at the saved URL). 'na' = doesn't
apply to this client (e.g. equipment brand they don't run) — human-set only.

Commands:
    seed [--slug X]     upsert the category target set for active Rank AI
                        clients (ignore-duplicates: never clobbers statuses)
    check [--slug X]    fetch saved URLs for non-live rows; a link to the
                        client's domain flips status -> live (with evidence);
                        a name-only mention is recorded but not promoted

Wired into client-ops-sync.yml daily after lsa_detect.
"""
from __future__ import annotations

import argparse
import json
import re
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

from client_ops_sync import _sb, slug_map  # noqa: E402

# Per-vertical target sets. Every client currently maps to 'restoration';
# new industries add a key here and category_for() learns to route them.
CATEGORY_TARGETS: dict[str, list[tuple[str, str, str, str]]] = {
    # (target_key, label, kind, note)
    "restoration": [
        ("iicrc", "IICRC Certified Firm locator", "association",
         "Free with the certification they already hold — the single most "
         "authoritative restoration link there is."),
        ("ria", "RIA member directory", "association",
         "Restoration Industry Association membership listing."),
        ("chamber", "Local Chamber of Commerce", "local",
         "Paid membership the owner signs off on; the best NAP + backlink "
         "combo available locally."),
        ("contractor-connection", "Contractor Connection", "tpa",
         "TPA network profile — applies when they're enrolled."),
        # Trimmed 2026-09-06 (Santino): the vendor/supplier testimonial
        # targets (Dri-Eaz, Phoenix, XPOWER, B-Air, Injectidry, Aramsco,
        # Jon-Don) never converted — replaced with the industry press pair.
        ("rr-magazine", "R&R Magazine", "press",
         "Restoration & Remediation (restorationandremediation.com) — "
         "contributed article or company feature earns the link."),
        ("cr-magazine", "C&R Magazine", "press",
         "Cleaning & Restoration, RIA's magazine (candrmagazine.com) — "
         "member article contribution."),
        # 2026-09-27 (Santino, backlinks badges): the podcast pair the Mini
        # connects from the client's RSS feed (podcasts.restorationai.io).
        ("spotify", "Spotify podcast", "podcast",
         "Client show on Spotify via our RSS feed — Mini lane, verified "
         "live on open.spotify.com."),
        ("apple-podcasts", "Apple Podcasts", "podcast",
         "Client show on Apple Podcasts via the same RSS feed — Mini lane."),
    ],
}


def category_for(co: dict) -> str:
    """Vertical for a company. All current clients are restoration; when the
    wizard category lands in companies, route on it here."""
    del co
    return "restoration"


def _companies(slug: str | None) -> list[dict]:
    cos = _sb("GET", "/rest/v1/companies?status=ilike.active&plan=eq.Rank%20AI"
              "&select=id,name,website") or []
    if slug:
        smap = slug_map()
        cos = [c for c in cos if smap.get(c["id"]) == slug]
    return cos


def cmd_seed(slug: str | None) -> int:
    cos = _companies(slug)
    total = 0
    for co in cos:
        cat = category_for(co)
        rows = [{"company_id": co["id"], "target_key": k, "label": label,
                 "kind": kind, "category": cat, "note": note}
                for k, label, kind, note in CATEGORY_TARGETS.get(cat, [])]
        if not rows:
            continue
        # ignore-duplicates: reseeding must never clobber human statuses/URLs
        _sb("POST", "/rest/v1/marketing_backlinks?on_conflict=company_id,target_key",
            rows, prefer="resolution=ignore-duplicates,return=minimal")
        total += len(rows)
    print(f"seeded {total} target rows across {len(cos)} client(s)")
    return 0


def _norm_domain(d: str | None) -> str:
    d = (d or "").strip().lower()
    d = re.sub(r"^https?://", "", d).strip("/ ")
    return d[4:] if d.startswith("www.") else d


def cmd_check(slug: str | None) -> int:
    cos = {c["id"]: c for c in _companies(slug)}
    if not cos:
        print("no matching companies")
        return 0
    ids = ",".join(f'"{c}"' for c in cos)
    rows = _sb("GET", "/rest/v1/marketing_backlinks?status=in.(target,requested)"
               f"&url=not.is.null&company_id=in.({ids})"
               "&select=id,company_id,target_key,url,status") or []
    now = datetime.now(timezone.utc).isoformat()
    flipped = 0
    for r in rows:
        co = cos.get(r["company_id"])
        if not co or not (r.get("url") or "").startswith("http"):
            continue
        dom = _norm_domain(co.get("website"))
        name = (co.get("name") or "").strip()
        try:
            resp = requests.get(r["url"], timeout=25, headers={
                "User-Agent": "Mozilla/5.0 (rank-ai backlink check)"})
            html = resp.text[:800_000] if resp.ok else ""
        except Exception:
            html = ""
        linked = bool(dom) and dom in html.lower()
        mentioned = bool(name) and name.lower() in html.lower()
        patch = {"last_checked_at": now,
                 "evidence": {"linked": linked, "mentioned": mentioned,
                              "checked_url": r["url"]}}
        if linked:
            patch["status"] = "live"
            flipped += 1
            print(f"  LIVE: {r['target_key']} for {co['name'][:30]} "
                  f"(domain found on page)")
        _sb("PATCH", f"/rest/v1/marketing_backlinks?id=eq.{r['id']}", patch)
    print(f"checked {len(rows)} URL(s), {flipped} flipped to live")
    return 0


# DISCOVERY v2 (Santino 2026-09-27). v1 searched Google and failed both
# ways: it MISSED Air Care's real RIA profile (thin directory indexing) and
# saved two false podcast matches. v2 = direct lookup on the source itself:
#   ria: RIA's own directory — name search (?name=) + slug guesses from the
#        company name (air-care-restoration-llc) — then the profile must
#        actually link the client's domain (checked here AND by `check`).
# Spotify/Apple are NOT discovered (we create those; the Mini records the
# URL). C&R/R&R are article lanes (URL recorded at publication). Existing
# memberships are flagged so we never buy a membership they already have.
RIA_BASE = "https://pro.restorationindustry.org/find-a-member"
_UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"}


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def _ria_candidates(name: str) -> list[str]:
    base = re.sub(r"(?i)[,.]?\s*(llc|l\.l\.c\.|inc\.?|corp\.?|co\.)\s*$", "",
                  name.strip())
    slugs = {_slug(name), _slug(base), f"{_slug(base)}-llc",
             f"{_slug(base)}-inc"}
    urls = [f"{RIA_BASE}/{s}" for s in slugs if s]
    try:
        html = requests.get(RIA_BASE, params={"name": base}, headers=_UA,
                            timeout=25).text
        for s in sorted(set(re.findall(r"find-a-member/([a-z0-9-]+)", html))):
            urls.insert(0, f"{RIA_BASE}/{s}")
    except Exception:  # noqa: BLE001 — slug guesses still run
        pass
    return list(dict.fromkeys(urls))


def cmd_discover(slug: str | None) -> int:
    cos = {c["id"]: c for c in _companies(slug)}
    if not cos:
        print("no matching companies")
        return 0
    ids = ",".join(f'"{c}"' for c in cos)
    rows = _sb("GET", "/rest/v1/marketing_backlinks?target_key=eq.ria"
               f"&url=is.null&company_id=in.({ids})&select=id,company_id") or []
    found = 0
    for r in rows:
        co = cos.get(r["company_id"]) or {}
        name, dom = (co.get("name") or "").strip(), _norm_domain(co.get("website"))
        if not (name and dom):
            continue
        for url in _ria_candidates(name):
            try:
                resp = requests.get(url, headers=_UA, timeout=25)
            except Exception:  # noqa: BLE001
                continue
            if resp.status_code != 200:
                continue
            html = resp.text.lower()
            # The profile must name THIS client's domain — slug collisions
            # between similarly named companies are rejected here.
            if dom not in html:
                continue
            hrefs = re.findall(r'href="([^"]*' + re.escape(dom) + r'[^"]*)"', html)
            broken = any(" " in h for h in hrefs)
            note = ("existing RIA member, found in RIA's own directory "
                    f"{datetime.now(timezone.utc).date()} — no membership "
                    "purchase needed")
            if broken:
                note += ("; WARNING: profile website link is malformed "
                         f"({hrefs[0]!r}) — fix on the profile so the link counts")
            _sb("PATCH", f"/rest/v1/marketing_backlinks?id=eq.{r['id']}",
                {"url": url, "note": note})
            found += 1
            print(f"  RIA MEMBER: {name[:35]} -> {url}"
                  + ("  [malformed link]" if broken else ""))
            break
    print(f"discover: checked {len(rows)} client(s) against RIA's directory, "
          f"{found} existing member(s) found")
    return 0

def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("seed", "check", "discover"):
        p = sub.add_parser(name)
        p.add_argument("--slug")
    a = ap.parse_args()
    return {"seed": cmd_seed, "check": cmd_check,
            "discover": cmd_discover}[a.cmd](a.slug)


if __name__ == "__main__":
    sys.exit(main())
