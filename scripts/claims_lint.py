#!/usr/bin/env python3
"""Claims lint — the truth gate for generated marketing content.

Born from a real incident (2026-07): davis-construction (a CONSTRUCTION client,
M-F hours, no IICRC cert) was built on the restoration vertical's templates and
shipped 61 files claiming "24/7", "IICRC-certified" and "emergency response".
This lint makes every availability / credential / response-time claim in
rendered content provably backed by the client's brand truth data, so that
class of fabrication can never ship silently again.

Truth sources (per slug):
  clients/{slug}/plan-input.json   brand.hours, brand.certifications[],
                                   brand.license_numbers / licenseNumbers /
                                   license, brand.founded_year,
                                   brand.response_minutes,
                                   brand.family_owned,
                                   brand.licensed_insured_attested
  clients/{slug}.json              vertical (plan.template / verticals[])
  sites/{slug}/src/lib/brand.ts    gbpReviewCount (synced review count)

Scan surface: sites/{slug}/src/content/**/*.md — frontmatter and body are
linted separately so a violation report says exactly where the claim lives.

Severities:
  error   the claim is not supported by brand truth → exit 1
  review  judgment call (e.g. a neutral "IICRC S500 standard" reference on a
          brand without the cert, or a star-rating claim we cannot verify)

CLI:
  python3 scripts/claims_lint.py --slug davis-construction
  python3 scripts/claims_lint.py --all            # active clients w/ a site
  python3 scripts/claims_lint.py --all --json     # also write
                                                  # clients/{slug}/claims-lint.json

Library use (content_writer.py / build_site.py / plan_site.py):
  from claims_lint import load_truth, lint_text, lint_file, lint_site
  from claims_lint import truth_from_plan_input, sanitize_claims_text, keyword_is_safe
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLIENTS_DIR = REPO_ROOT / "clients"
SITES_DIR = REPO_ROOT / "sites"

# ----------------------------------------------------------------------------
# Truth loading
# ----------------------------------------------------------------------------

# The EXACT same gate the site templates use (Header/Footer/TrustStrip/schema.ts):
#   /24\s*[\/x-]?\s*7|24 ?hours/i  against brand.hours
IS247_RE = re.compile(r"24\s*[\/x-]?\s*7|24 ?hours", re.I)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()


def truth_from_plan_input(plan_input: dict, client: dict | None = None,
                          gbp_review_count: int | None = None) -> dict:
    """Build the truth table from an already-loaded plan-input (and optionally
    the client record + synced review count). Pure — no file IO."""
    brand = plan_input.get("brand", {}) or {}
    client = client or {}

    hours = str(brand.get("hours") or "")
    certs = brand.get("certifications") or []
    if isinstance(certs, str):
        certs = [certs]

    lic = (brand.get("license_numbers") or brand.get("licenseNumbers")
           or brand.get("license") or [])
    if isinstance(lic, str):
        lic = [lic] if lic.strip() else []
    lic = [str(x) for x in lic if str(x).strip()]

    # The explicit "vertical" field is authoritative (scripts/verticals.py);
    # plan.template is historical build state and can be stale (davis was
    # built on the restoration template before the vertical split).
    vertical = client.get("vertical") \
        or (client.get("plan", {}) or {}).get("template") \
        or (client.get("verticals") or [None])[0]

    resp = brand.get("response_minutes")
    try:
        resp = int(resp) if resp not in (None, "", 0, "0") else None
    except (TypeError, ValueError):
        resp = None

    return {
        "hours": hours,
        "is_247": bool(IS247_RE.search(hours)),
        "certifications": [str(c) for c in certs],
        "cert_blob": _norm(" | ".join(str(c) for c in certs)),
        "license_numbers": lic,
        "licensed_ok": bool(lic) or bool(brand.get("licensed_insured_attested")),
        "response_minutes": resp,
        "family_owned": bool(brand.get("family_owned")),
        "founded_year": str(brand.get("founded_year") or ""),
        "gbp_review_count": gbp_review_count,
        "vertical": vertical,
    }


def _read_gbp_review_count(slug: str) -> int | None:
    brand_ts = SITES_DIR / slug / "src" / "lib" / "brand.ts"
    if not brand_ts.exists():
        return None
    m = re.search(r"gbpReviewCount\s*:\s*[\"']?(\d+)[\"']?", brand_ts.read_text())
    return int(m.group(1)) if m else None


def load_truth(slug: str) -> dict:
    """Load the full truth table for a client slug from disk."""
    plan_input_path = CLIENTS_DIR / slug / "plan-input.json"
    plan_input = json.loads(plan_input_path.read_text()) if plan_input_path.exists() else {}
    client_path = CLIENTS_DIR / f"{slug}.json"
    client = json.loads(client_path.read_text()) if client_path.exists() else {}
    truth = truth_from_plan_input(plan_input, client, _read_gbp_review_count(slug))
    truth["slug"] = slug
    return truth


# ----------------------------------------------------------------------------
# Claim pattern families
# ----------------------------------------------------------------------------

F247_RE = re.compile(
    r"24\s*/\s*7|24[- ]hours?\b|around[-. ]the[-. ]clock|day or night"
    r"|open 24|staffed 24|any time of (?:day|night)",
    re.I,
)
# Temporal references like "mold grows within 24 hours" or ranges like
# "12-24 hours" are science, not an availability claim — skip those.
_TEMPORAL_BEFORE_RE = re.compile(
    r"(?:within|in|first|next|after|every|past|last|to|than|the|\d\s*[–—-])\s*(?:the\s+)?$",
    re.I)
_TEMPORAL_AFTER_RE = re.compile(r"^\s*(?:of|to|after)\b", re.I)
# Third-party availability ("most carriers have 24-hour claim lines") is a
# statement about someone else — judgment call, not an error.
_THIRD_PARTY_RE = re.compile(r"carrier|insurer|insurance compan|hotline|utilit", re.I)


def _in_url_token(text: str, start: int, end: int) -> bool:
    """True when the match sits inside a URL/path token (slug or link) —
    e.g. '/blog/what-to-do-first-24-hours-water-damage/'. Slugs are targeting
    artifacts, not shipped claims."""
    ts = start
    while ts > 0 and not text[ts - 1].isspace() and text[ts - 1] not in "\"'`,()[]{}<>":
        ts -= 1
    te = end
    while te < len(text) and not text[te].isspace() and text[te] not in "\"'`,()[]{}<>":
        te += 1
    token = text[ts:te]
    return "/" in token or token.startswith(("http", "www."))

CERT_RE = re.compile(
    r"IICRC|EPA[- ]certified|Lead[- ]Safe|certified (?:restoration|technician|firm|team)",
    re.I,
)
STANDARD_REF_RE = re.compile(r"S5\d{2}|standard", re.I)

RESP_RE = re.compile(
    r"\b(\d{1,3})[- ](?:minute|min)s?\b.{0,40}(?:response|arrival|on.?site)"
    r"|on.?site within",
    re.I | re.S,
)

LIC_RE = re.compile(r"licensed?,? (?:and|&) insured|fully licensed", re.I)

FAM_RE = re.compile(r"family[- ](?:owned|business|run)", re.I)

REVIEW_RE = re.compile(
    r"(\d+)\+?\s+(?:five[- ]star\s+|Google\s+)?reviews"
    r"|rated\s+([45](?:\.\d)?)\s+(?:stars|out of)",
    re.I,
)


def _context(text: str, start: int, end: int, pad: int = 40) -> str:
    snippet = text[max(0, start - pad):min(len(text), end + pad)]
    return re.sub(r"\s+", " ", snippet).strip()


def _violation(family: str, severity: str, reason: str, text: str,
               m: re.Match, source: str, part: str) -> dict:
    return {
        "file": source,
        "part": part,
        "family": family,
        "severity": severity,
        "matched": m.group(0),
        "context": _context(text, m.start(), m.end()),
        "reason": reason,
    }


def lint_text(text: str, truth: dict, source: str = "", part: str = "text") -> list[dict]:
    """Lint one blob of text against a truth table. Returns violation dicts."""
    v: list[dict] = []
    if not text:
        return v

    # -- 24/7 availability family ------------------------------------------
    if not truth["is_247"]:
        for m in F247_RE.finditer(text):
            if _in_url_token(text, m.start(), m.end()):
                continue  # slug / internal link, not a shipped claim
            severity = "error"
            reason = (f"claims round-the-clock availability but brand.hours is "
                      f"\"{truth['hours'] or '(unset)'}\"")
            if "hour" in m.group(0).lower():
                before = text[max(0, m.start() - 24):m.start()]
                after = text[m.end():m.end() + 12]
                if _TEMPORAL_BEFORE_RE.search(before) or _TEMPORAL_AFTER_RE.search(after):
                    continue  # "within 24 hours" / "12-24 hours" — temporal
                window = text[max(0, m.start() - 60):m.end() + 60]
                if _THIRD_PARTY_RE.search(window):
                    severity = "review"
                    reason = ("24-hour availability statement appears to describe a "
                              "third party (carrier/utility) — verify it is not about the brand")
            v.append(_violation("24/7", severity, reason, text, m, source, part))

    # -- Certification family ----------------------------------------------
    for m in CERT_RE.finditer(text):
        if _in_url_token(text, m.start(), m.end()):
            continue  # e.g. /blog/iicrc-certification-explained/ link
        tok = m.group(0).lower()
        if tok.startswith("iicrc"):
            ok = "iicrc" in truth["cert_blob"]
        elif tok.startswith("epa"):
            ok = "epa" in truth["cert_blob"]
        elif tok.startswith("lead"):
            ok = "lead safe" in truth["cert_blob"]
        else:  # generic "certified restoration/technician/firm/team"
            ok = bool(truth["certifications"])
        if ok:
            continue
        severity, reason = "error", "names a certification not present in brand.certifications"
        window = text[max(0, m.start() - 30):m.end() + 30]
        if tok.startswith("iicrc") and STANDARD_REF_RE.search(window):
            # Neutral industry-standard reference ("per the IICRC S500
            # standard") on a brand without the cert — judgment call.
            severity = "review"
            reason = ("IICRC standard reference on an uncertified brand — "
                      "verify it reads as an industry standard, not a credential claim")
        elif tok.startswith("lead") and re.search(
                r"^\s*(?:work |or )?(?:practices|requirements|rules|renovation|"
                r"handling|protocols|asbestos)",
                text[m.end():m.end() + 32], re.I):
            # "lead-safe work practices" / "lead-safe handling protocols" —
            # describes the regulated practice, not a certification the brand
            # holds. Judgment call.
            severity = "review"
            reason = ("lead-safe practice reference on a brand without the cert — "
                      "verify it does not read as an EPA Lead-Safe credential claim")
        elif re.search(r"\b(?:must be|required|requires|regulations?|by law|"
                       r"before disposal)\b", window, re.I):
            # Regulatory statement ("refrigerant must be recovered by an
            # EPA-certified technician") — about the rule, not the brand.
            severity = "review"
            reason = ("certification mention looks like a regulatory reference — "
                      "verify it is not a self-claim")
        v.append(_violation("certification", severity, reason, text, m, source, part))

    # -- Response-time family ------------------------------------------------
    if not truth["is_247"] and not truth["response_minutes"]:
        for m in RESP_RE.finditer(text):
            v.append(_violation(
                "response-time", "error",
                "promises response/arrival timing but brand is neither 24/7 "
                "nor has brand.response_minutes set",
                text, m, source, part))

    # -- License family ------------------------------------------------------
    if not truth["licensed_ok"]:
        for m in LIC_RE.finditer(text):
            severity = "error"
            reason = ("claims licensed status but license_numbers is empty and "
                      "licensed_insured_attested is not set")
            window = text[max(0, m.start() - 80):m.start()]
            if re.search(r"\b(verify|check|confirm|make sure|ask|whether|if a|any)\b",
                         window, re.I):
                # Educational copy about vetting contractors, not a self-claim.
                severity = "review"
                reason = ("licensing mention looks educational (how to verify a "
                          "contractor) — confirm it is not a self-claim")
            v.append(_violation("license", severity, reason, text, m, source, part))

    # -- Family-owned family --------------------------------------------------
    if not truth["family_owned"]:
        for m in FAM_RE.finditer(text):
            v.append(_violation(
                "family-owned", "error",
                "claims family ownership but brand.family_owned is not true",
                text, m, source, part))

    # -- Review-count / rating tripwires --------------------------------------
    for m in REVIEW_RE.finditer(text):
        if m.group(1):  # "N reviews" — check against synced gbpReviewCount ±20%
            claimed = int(m.group(1))
            synced = truth.get("gbp_review_count")
            if synced:
                lo, hi = synced * 0.8, synced * 1.2
                if lo <= claimed <= hi:
                    continue
                reason = (f"claims {claimed} reviews but synced gbpReviewCount "
                          f"is {synced} (allowed ±20%: {int(lo)}-{int(hi)})")
            else:
                reason = (f"claims {claimed} reviews but no synced "
                          f"gbpReviewCount exists for this site")
            v.append(_violation("reviews", "error", reason, text, m, source, part))
        else:  # "rated 4.9 stars" — no synced rating to verify against
            v.append(_violation(
                "reviews", "review",
                "star-rating claim — no synced rating to verify; confirm against GBP",
                text, m, source, part))

    return v


def split_frontmatter(raw: str) -> tuple[str, str]:
    if raw.startswith("---\n"):
        end = raw.find("\n---\n", 4)
        if end > 0:
            return raw[4:end], raw[end + 5:]
    return "", raw


def lint_file(path: Path, truth: dict, rel_root: Path | None = None) -> list[dict]:
    raw = path.read_text()
    fm, body = split_frontmatter(raw)
    src = str(path.relative_to(rel_root)) if rel_root else str(path)
    return (lint_text(fm, truth, src, "frontmatter")
            + lint_text(body, truth, src, "body"))


def lint_site(slug: str) -> tuple[list[dict], dict]:
    """Lint every content markdown file for a client site."""
    truth = load_truth(slug)
    content_dir = SITES_DIR / slug / "src" / "content"
    violations: list[dict] = []
    if content_dir.exists():
        for md in sorted(content_dir.rglob("*.md")):
            violations.extend(lint_file(md, truth, rel_root=SITES_DIR / slug))
    return violations, truth


# ----------------------------------------------------------------------------
# Sanitizer — used by plan_site.py so planned titles/H1s/metas can never
# contain a claim the brand truth doesn't back. Deterministic rewrites.
# ----------------------------------------------------------------------------


def sanitize_claims_text(text: str, truth: dict) -> str:
    if not text:
        return text
    out = text

    if not truth["is_247"]:
        # Targeted rewrites first (best copy), then generic strips.
        out = re.sub(r"24\s*/\s*7 emergency restoration", "restoration services", out, flags=re.I)
        out = re.sub(r"24\s*/\s*7 (response|dispatch)", "prompt scheduling", out, flags=re.I)
        out = re.sub(r"24\s*/\s*7\s*", "", out, flags=re.I)
        out = re.sub(r"\b24[- ]hour\b\s*", "", out, flags=re.I)
        out = re.sub(r"around[-. ]the[-. ]clock\s*", "", out, flags=re.I)
        out = re.sub(r"\bday or night\b\s*", "", out, flags=re.I)
        # An availability implication in titles/metas for a business-hours brand.
        out = re.sub(r"\bemergency\s+", "", out, flags=re.I)
        out = re.sub(r"\bemergency\b", "", out, flags=re.I)

    if "iicrc" not in truth["cert_blob"]:
        out = re.sub(r"IICRC[- ]certified (team|firm|crew|technicians?)",
                     r"experienced \1", out, flags=re.I)
        out = re.sub(r",?\s*IICRC[- ]certified,?\s*", " ", out, flags=re.I)
        out = re.sub(r"\bIICRC\b\s*", "", out)
    if "epa" not in truth["cert_blob"]:
        out = re.sub(r",?\s*EPA[- ]certified,?\s*", " ", out, flags=re.I)
    if "lead safe" not in truth["cert_blob"]:
        out = re.sub(r",?\s*Lead[- ]Safe(?: Certified(?: Firm)?)?,?\s*", " ", out, flags=re.I)

    if not truth["licensed_ok"]:
        out = re.sub(r"(?:fully )?licensed,?\s*(?:and|&)?\s*insured,?\s*", "", out, flags=re.I)
        out = re.sub(r"\bfully licensed\b,?\s*", "", out, flags=re.I)
        # Catch-all: a bare "licensed" adjective outside the compound patterns
        # above ("our licensed plumbing and HVAC team" — plumbing about
        # archetype) must not survive for an unlicensed/unattested brand.
        out = re.sub(r"\b(?:state[- ]|CSLB[- ])?licensed\b,?\s*", "", out, flags=re.I)

    if not truth["family_owned"]:
        out = re.sub(r"family[- ](?:owned(?:[- ]and[- ]operated)?|run|business),?\s*",
                     "", out, flags=re.I)

    if out == text:
        return text

    # Cleanup: whitespace/punctuation debris left by removals.
    out = re.sub(r"\s{2,}", " ", out)
    out = re.sub(r"\s+([,.;:!?])", r"\1", out)
    out = re.sub(r"([,;:])(?:\s*[,;:])+", r"\1", out)
    out = re.sub(r"[,;:]\s*\.", ".", out)
    out = re.sub(r"\.(?:\s*\.)+", ".", out)
    out = re.sub(r"^[\s,.;:&-]+", "", out)
    out = out.strip()
    # Removals can leave a sentence starting lowercase — recapitalize.
    out = re.sub(r"([.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), out)
    if out and out[0].islower():
        out = out[0].upper() + out[1:]
    return out


def keyword_is_safe(keyword: str, truth: dict) -> bool:
    """False for target keywords that would steer copy toward claims the brand
    can't make (e.g. feeding '24/7 restoration phone' to a M-F business)."""
    if truth["is_247"]:
        return True
    return not (F247_RE.search(keyword) or re.search(r"\bemergency\b", keyword, re.I))


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def active_slugs() -> list[str]:
    slugs = []
    for p in sorted(CLIENTS_DIR.glob("*.json")):
        try:
            rec = json.loads(p.read_text())
        except json.JSONDecodeError:
            continue
        if not isinstance(rec, dict) or rec.get("status") != "active":
            continue
        slug = rec.get("slug") or p.stem
        if (CLIENTS_DIR / slug / "plan-input.json").exists():
            slugs.append(slug)
    return slugs


def print_report(slug: str, truth: dict, violations: list[dict]) -> None:
    errs = [x for x in violations if x["severity"] == "error"]
    revs = [x for x in violations if x["severity"] == "review"]
    print(f"==> Claims lint: {slug}")
    print(f"    truth: hours=\"{truth['hours'] or '(unset)'}\" 24/7={truth['is_247']} "
          f"certs={len(truth['certifications'])} license#={len(truth['license_numbers'])} "
          f"family_owned={truth['family_owned']} "
          f"gbp_reviews={truth['gbp_review_count'] or '-'}")
    if not violations:
        print("    CLEAN — no unverified claims found.")
        return
    print(f"    {len(errs)} error(s), {len(revs)} review flag(s)")
    print()
    wf = max((len(x["file"]) for x in violations), default=4)
    wf = min(wf, 64)
    print(f"    {'SEV':7} {'FAMILY':13} {'PART':12} {'FILE':{wf}}  MATCHED (±40 chars)")
    print(f"    {'-'*7} {'-'*13} {'-'*12} {'-'*wf}  {'-'*40}")
    for x in violations:
        print(f"    {x['severity']:7} {x['family']:13} {x['part']:12} "
              f"{x['file'][:wf]:{wf}}  ...{x['context']}...")


def main() -> int:
    ap = argparse.ArgumentParser(description="Truth gate: lint site content claims against brand truth data")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--slug", help="Lint one client")
    g.add_argument("--all", action="store_true", help="Lint all active clients")
    ap.add_argument("--json", action="store_true",
                    help="Also write clients/{slug}/claims-lint.json per client")
    args = ap.parse_args()

    slugs = [args.slug] if args.slug else active_slugs()
    total_errors = 0
    for i, slug in enumerate(slugs):
        if i:
            print()
        violations, truth = lint_site(slug)
        print_report(slug, truth, violations)
        errs = [x for x in violations if x["severity"] == "error"]
        total_errors += len(errs)
        if args.json:
            out = {
                "slug": slug,
                "generated_at": _now_iso(),
                "truth": {k: truth[k] for k in
                          ("hours", "is_247", "certifications", "license_numbers",
                           "licensed_ok", "response_minutes", "family_owned",
                           "founded_year", "gbp_review_count", "vertical")},
                "errors": len(errs),
                "review_flags": len(violations) - len(errs),
                "violations": violations,
            }
            out_path = CLIENTS_DIR / slug / "claims-lint.json"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(out, indent=2) + "\n")
            print(f"    JSON: {out_path.relative_to(REPO_ROOT)}")

    print()
    if total_errors:
        print(f"CLAIMS LINT FAILED — {total_errors} error-severity violation(s) "
              f"across {len(slugs)} client(s). Content claims things the brand "
              f"truth data does not support.")
        return 1
    print(f"Claims lint passed for {len(slugs)} client(s) (errors=0).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
