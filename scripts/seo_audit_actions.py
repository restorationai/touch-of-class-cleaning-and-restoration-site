#!/usr/bin/env python3
"""
seo_audit_actions.py — turn SEO audit findings into reviewable, tiered actions.

Runs DETERMINISTIC (code-verified) checks against a client's LIVE site, classifies
each finding into a confidence/blast-radius tier, and writes them into Supabase
`marketing_action_plan` — the table the app's ACTION PLAN tab renders per client.

Tiers (see the team note on confidence x blast-radius):
  1  deterministic + safe auto-fix   -> assigned_system="auto"
        --apply applies the template fix to sites/{slug}/ and logs status="done".
        Without --apply, writes status="proposed" so a human can trigger it.
  2  generative, low-risk            -> assigned_system="manual", status="proposed"
        (e.g. title/meta rewrites — suggested value goes in the rationale).
  3  judgment / structural           -> assigned_system="manual", status="proposed"
        (e.g. potential cannibalization — always reviewed, never auto-applied).

Dedupe + respect human decisions: rows are keyed by `action_key`. On re-run, an
existing row that the user already DISMISSED is left untouched (never resurrected);
others are refreshed in place. So the monthly cron is idempotent and trustworthy.

Usage:
  python3 scripts/seo_audit_actions.py --slug narestco            # detect + write proposals
  python3 scripts/seo_audit_actions.py --slug narestco --apply    # also auto-apply tier-1 template fixes
  python3 scripts/seo_audit_actions.py --slug narestco --dry-run  # print findings, write nothing
"""
import argparse
import json
import os
import re
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = "Mozilla/5.0 (compatible; RankAI-SEOAudit/1.0)"


# ---------------------------------------------------------------------------
# small http helpers
# ---------------------------------------------------------------------------
def _get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace"), dict(r.headers)


def _head_headers(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return {k.lower(): v for k, v in r.headers.items()}


def _sitemap_urls(origin):
    """Return all <loc> URLs across the sitemap index + child sitemaps."""
    urls = []
    for sm in (f"{origin}/sitemap-index.xml", f"{origin}/sitemap.xml", f"{origin}/sitemap-0.xml"):
        try:
            body, _ = _get(sm)
        except Exception:
            continue
        children = re.findall(r"<loc>\s*([^<]+\.xml)\s*</loc>", body)
        if children:
            for c in children:
                try:
                    cb, _ = _get(c.strip())
                    urls += [u.strip() for u in re.findall(r"<loc>\s*([^<]+?)\s*</loc>", cb)]
                except Exception:
                    pass
        else:
            urls += [u.strip() for u in re.findall(r"<loc>\s*([^<]+?)\s*</loc>", body)]
        if urls:
            break
    # de-dupe, drop the nested .xml locs
    return sorted({u for u in urls if not u.endswith(".xml")})


# ---------------------------------------------------------------------------
# deterministic checks  ->  list of findings
# A finding: dict(action_key, tier, action_type, title, rationale, target,
#                 impact, effort, priority, autofixable)
# ---------------------------------------------------------------------------
def check_sitemap_noindex(origin, urls):
    """Tier 1: noindex /lp/ pages must not be in the public sitemap."""
    lp = [u for u in urls if "/lp/" in u]
    if not lp:
        return None
    return dict(
        action_key="sitemap_excludes_noindex_lp",
        tier=1, action_type="technical_fix", autofixable=True,
        title="Remove noindex /lp/ ad pages from the XML sitemap",
        rationale=(f"{len(lp)} noindex,nofollow /lp/ landing pages are listed in the public "
                   f"sitemap (~{round(100*len(lp)/max(len(urls),1))}% of submitted URLs). This sends "
                   "conflicting signals (GSC 'Submitted URL marked noindex') and wastes crawl budget. "
                   "Fix: exclude '/lp/' in the Astro sitemap filter, then rebuild."),
        target="astro_sitemap_filter", impact="high", effort="low", priority=1,
    )


SECURITY_HEADERS = {
    "strict-transport-security": "HSTS",
    "x-content-type-options": "X-Content-Type-Options",
    "x-frame-options": "X-Frame-Options",
    "referrer-policy": "Referrer-Policy",
}


def check_security_headers(origin):
    """Tier 1: standard safe security headers should be present."""
    try:
        h = _head_headers(origin + "/")
    except Exception:
        return None
    missing = [label for key, label in SECURITY_HEADERS.items() if key not in h]
    if not missing:
        return None
    return dict(
        action_key="security_headers",
        tier=1, action_type="technical_fix", autofixable=True,
        title="Add missing security headers",
        rationale=("Missing: " + ", ".join(missing) + ". Add a Cloudflare Pages public/_headers "
                   "file (HSTS, X-Content-Type-Options, X-Frame-Options, Referrer-Policy). "
                   "Safe, non-breaking (no CSP)."),
        target="pages_headers", impact="medium", effort="low", priority=2,
    )


def check_title_meta(origin):
    """Tier 2: homepage title <=60 chars, meta description present and <=160."""
    findings = []
    try:
        html, _ = _get(origin + "/")
    except Exception:
        return findings
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    title = (m.group(1).strip() if m else "")
    if title and len(title) > 60:
        findings.append(dict(
            action_key="homepage_title_length",
            tier=2, action_type="content_fix", autofixable=False,
            title="Shorten the homepage <title> (truncating in SERPs)",
            rationale=(f"Homepage title is {len(title)} chars (>60 truncates in Google). "
                       f"Current: \"{title[:90]}\". Rewrite to <=60 chars, keep the primary "
                       "keyword + city near the front."),
            target="homepage_title", impact="medium", effort="low", priority=3,
        ))
    md = re.search(r'<meta[^>]+name=["\']description["\'][^>]*content=["\']([^"\']*)', html, re.I)
    desc = (md.group(1).strip() if md else "")
    if not desc or len(desc) > 160:
        findings.append(dict(
            action_key="homepage_meta_description",
            tier=2, action_type="content_fix", autofixable=False,
            title=("Add a homepage meta description" if not desc else "Shorten the homepage meta description"),
            rationale=((f"Meta description is {len(desc)} chars (>160 truncates). " if desc
                        else "Homepage is missing a meta description. ")
                       + "Write a 150-160 char description with the primary service + city + a call to action."),
            target="homepage_meta", impact="low", effort="low", priority=4,
        ))
    return findings


def check_service_area_overlap(urls):
    """Tier 3 (judgment, review-only): localized /services/{x}/ overlapping a
    /service-areas/{city}/{x}/ page can cannibalize. Detect the structural overlap;
    DO NOT auto-act — surface for human review."""
    services = {re.search(r"/services/([^/]+)/?$", u).group(1)
                for u in urls if re.search(r"/services/([^/]+)/?$", u)}
    area_services = {}
    for u in urls:
        m = re.search(r"/service-areas/([^/]+)/([^/]+)/?$", u)
        if m:
            area_services.setdefault(m.group(2), set()).add(m.group(1))
    overlap = sorted(s for s in services if s in area_services)
    if not overlap:
        return None
    return dict(
        action_key="services_vs_service_area_overlap",
        tier=3, action_type="review", autofixable=False,
        title="Review possible cannibalization: /services/ vs /service-areas/ pages",
        rationale=(f"{len(overlap)} services exist both at /services/{{x}}/ and under "
                   f"/service-areas/{{city}}/{{x}}/ (e.g. {', '.join(overlap[:4])}). If the "
                   "/services/ pages are localized to the HQ city they may compete with the "
                   "matching service-area page. JUDGMENT CALL — verify in GSC whether they split "
                   "impressions for the same query before consolidating. Do not auto-change."),
        target="services_information_architecture", impact="medium", effort="medium", priority=3,
    )


# ---------------------------------------------------------------------------
# tier-1 auto-fix (apply to the client's own site copy)
# ---------------------------------------------------------------------------
def apply_tier1(slug, finding):
    """Apply a deterministic template fix to sites/{slug}/. Returns True if a change
    was made (or already in place)."""
    site = ROOT / "sites" / slug
    if finding["action_key"] == "sitemap_excludes_noindex_lp":
        cfg = site / "astro.config.mjs"
        if not cfg.exists():
            return False
        text = cfg.read_text()
        if "/lp/" in text and "!page.includes(\"/lp/\")" in text:
            return True  # already fixed
        new = text.replace('filter: (page) => !page.includes("/404"),',
                           'filter: (page) => !page.includes("/404") && !page.includes("/lp/"),')
        if new != text:
            cfg.write_text(new)
            return True
        return False
    if finding["action_key"] == "security_headers":
        hdr = site / "public" / "_headers"
        if hdr.exists() and "Strict-Transport-Security" in hdr.read_text():
            return True
        hdr.parent.mkdir(parents=True, exist_ok=True)
        hdr.write_text(
            "# Security headers (Cloudflare Pages). No CSP (per-site tuning).\n/*\n"
            "  Strict-Transport-Security: max-age=31536000; includeSubDomains\n"
            "  X-Content-Type-Options: nosniff\n"
            "  X-Frame-Options: SAMEORIGIN\n"
            "  Referrer-Policy: strict-origin-when-cross-origin\n"
            "  Permissions-Policy: geolocation=(), microphone=(), camera=()\n")
        return True
    return False


# ---------------------------------------------------------------------------
# supabase upsert (respect prior human decisions)
# ---------------------------------------------------------------------------
def _sb(method, path, body=None):
    url = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1/" + path
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    headers = {"apikey": key, "Authorization": f"Bearer {key}",
               "Content-Type": "application/json", "Prefer": "return=representation"}
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read().decode()
        return json.loads(raw) if raw else []


def upsert_action(company_id, slug, f, status, assigned_system, now):
    """Insert or refresh one finding. Never resurrects a dismissed row."""
    import urllib.parse
    q = (f"marketing_action_plan?company_id=eq.{urllib.parse.quote(company_id)}"
         f"&action_key=eq.{urllib.parse.quote(f['action_key'])}&select=id,status")
    existing = _sb("GET", q)
    row = {
        "company_id": company_id, "rank_ai_slug": slug, "priority": f["priority"],
        "action_type": f["action_type"], "title": f["title"], "rationale": f["rationale"],
        "target": f["target"], "assigned_system": assigned_system,
        "impact": f["impact"], "effort": f["effort"], "status": status,
        "source_run_at": now, "action_key": f["action_key"], "updated_at": now,
    }
    if existing:
        cur = existing[0]
        if cur["status"] == "dismissed":
            return "skipped (user dismissed)"
        # keep the human-set status (e.g. approved); just refresh the content/timestamp
        upd = {k: v for k, v in row.items() if k not in ("status",)}
        import urllib.parse as up
        _sb("PATCH", f"marketing_action_plan?id=eq.{up.quote(cur['id'])}", upd)
        return f"updated ({cur['status']})"
    row["created_at"] = now
    _sb("POST", "marketing_action_plan", row)
    return f"inserted ({status})"


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True)
    ap.add_argument("--apply", action="store_true", help="apply tier-1 template fixes to sites/{slug}/")
    ap.add_argument("--dry-run", action="store_true", help="print findings, write nothing")
    args = ap.parse_args()

    rec = json.loads((ROOT / "clients" / f"{args.slug}.json").read_text())
    company_id = rec.get("company_id")
    domain = rec.get("domain")
    if not company_id or not domain:
        sys.exit(f"missing company_id/domain in clients/{args.slug}.json")
    origin = f"https://{domain}"
    now = datetime.now(timezone.utc).isoformat()

    urls = _sitemap_urls(origin)
    findings = []
    for chk in (lambda: check_sitemap_noindex(origin, urls),
                lambda: check_security_headers(origin),
                lambda: check_service_area_overlap(urls)):
        r = chk()
        if r:
            findings.append(r)
    findings += check_title_meta(origin)

    print(f"== seo_audit_actions: {args.slug} ({origin}) — {len(urls)} sitemap URLs ==")
    if not findings:
        print("  no findings — site is clean on the deterministic checks.")
    applied_done = set()
    if args.apply:
        for f in findings:
            if f["tier"] == 1 and f["autofixable"]:
                if apply_tier1(args.slug, f):
                    applied_done.add(f["action_key"])
                    print(f"  [tier1 APPLIED] {f['action_key']}")

    for f in findings:
        if f["action_key"] in applied_done:
            status, system = "done", "auto"
        elif f["tier"] == 1:
            status, system = "proposed", "auto"
        else:
            status, system = "proposed", "manual"
        tag = f"T{f['tier']}/{status}"
        if args.dry_run:
            print(f"  [{tag}] {f['title']}")
            continue
        res = upsert_action(company_id, args.slug, f, status, system, now)
        print(f"  [{tag}] {f['title']}  -> {res}")

    if not args.dry_run:
        print("Done. Review tier-2/3 items in the app's ACTION PLAN tab.")


if __name__ == "__main__":
    main()
