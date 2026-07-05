#!/usr/bin/env python3
"""
Rank AI — Quarterly Press Release drafter (System: authority moat).

Robinson-teardown adoption: their authority moat is press-release syndication —
third-party pages repeating their response-time claim in indexable text. We do
the same, truth-gated: one 350-500 word local-news-style release per client per
quarter, generated from brand data ONLY (CLAIMS TRUTH TABLE rules via
scripts/claims_lint.py — a draft that fails lint is never saved).

Flow:
  1. Monthly authority cron runs `draft --all` (railway.authority-cron.toml).
     The script no-ops unless it's the first month of a quarter OR the current
     quarter has no row yet (catch-up), so quarterly cadence emerges from the
     monthly cron.
  2. Draft is upserted to marketing_press_releases (status=draft) and written
     to clients/{slug}/press/{quarter}.md.
  3. Operator reviews in the app (Marketing → Reports → Press Releases card):
     Approve → paste into Press Advantage / EIN Presswire → Mark published
     with the syndicated URL.

Idempotent: if a draft/approved/published row already exists for the quarter,
the client is skipped.

Subcommands:
  draft --slug X [--quarter 2026-Q3]   Draft for one client
  draft --all [--quarter 2026-Q3]      Draft for every active client in
                                       clients/company_map.json
  Flags: --force (bypass the quarter-month gate, not the row-exists skip)

Env (rank-ai/.env):
  ANTHROPIC_API_KEY                          release generation
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY    marketing_press_releases upsert

Docs: rank-ai/docs/press-releases.md
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import claims_lint  # noqa: E402 — truth table + lint_text live here

ROOT = SCRIPT_DIR.parent
CLIENTS_DIR = ROOT / "clients"
SITES_DIR = ROOT / "sites"
load_dotenv(ROOT / ".env")

SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
TABLE = "marketing_press_releases"

ANTHROPIC_API = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-sonnet-4-6"

MAX_ATTEMPTS = 3          # generation attempts before refusing to save
WORDS_MIN, WORDS_MAX = 350, 500
# Soft acceptance band — journalism trims are fine, bloat is not.
WORDS_HARD_MIN, WORDS_HARD_MAX = 320, 560


def die(msg: str, code: int = 1) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


# ----------------------------------------------------------------------------
# Quarter helpers
# ----------------------------------------------------------------------------


def quarter_of(dt: datetime) -> str:
    return f"{dt.year}-Q{(dt.month - 1) // 3 + 1}"


def quarter_start(quarter: str) -> datetime:
    """'2026-Q3' -> 2026-07-01 (UTC)."""
    m = re.fullmatch(r"(\d{4})-Q([1-4])", quarter)
    if not m:
        die(f"Bad quarter format: {quarter!r} (expected e.g. 2026-Q3)")
    return datetime(int(m.group(1)), (int(m.group(2)) - 1) * 3 + 1, 1,
                    tzinfo=timezone.utc)


def is_first_month_of_quarter(dt: datetime) -> bool:
    return dt.month in (1, 4, 7, 10)


# ----------------------------------------------------------------------------
# Supabase (service role, same REST pattern as gbp.py)
# ----------------------------------------------------------------------------


def _sb_headers() -> dict:
    return {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
            "Content-Type": "application/json"}


def sb_existing_row(company_id: str, quarter: str) -> dict | None:
    r = requests.get(
        f"{SB_URL}/rest/v1/{TABLE}",
        params={"company_id": f"eq.{company_id}", "quarter": f"eq.{quarter}",
                "select": "quarter,status,title"},
        headers=_sb_headers(), timeout=30)
    r.raise_for_status()
    rows = r.json()
    return rows[0] if rows else None


def sb_upsert_draft(company_id: str, quarter: str, title: str, body: str) -> None:
    r = requests.post(
        f"{SB_URL}/rest/v1/{TABLE}?on_conflict=company_id,quarter",
        headers={**_sb_headers(),
                 "Prefer": "resolution=merge-duplicates,return=minimal"},
        data=json.dumps([{
            "company_id": company_id,
            "quarter": quarter,
            "title": title,
            "body_markdown": body,
            "status": "draft",
            "updated_at": now_iso(),
        }]), timeout=30)
    r.raise_for_status()


def sb_quarter_row_count(quarter: str) -> int:
    """How many press-release rows exist for this quarter (any client)."""
    r = requests.get(
        f"{SB_URL}/rest/v1/{TABLE}",
        params={"quarter": f"eq.{quarter}", "select": "company_id"},
        headers=_sb_headers(), timeout=30)
    r.raise_for_status()
    return len(r.json())


# ----------------------------------------------------------------------------
# Brand facts — ONLY truth-table-backed data ever reaches the model
# ----------------------------------------------------------------------------


def _read_synced_rating(slug: str) -> tuple[str | None, int | None]:
    """gbpRatingValue / gbpReviewCount synced into brand.ts by
    sync_brand_reviews.py (never hand-edited — real ratings only)."""
    brand_ts = SITES_DIR / slug / "src" / "lib" / "brand.ts"
    if not brand_ts.exists():
        return None, None
    raw = brand_ts.read_text()
    rating = re.search(r"gbpRatingValue\s*:\s*[\"']([\d.]+)[\"']", raw)
    count = re.search(r"gbpReviewCount\s*:\s*[\"']?(\d+)[\"']?", raw)
    return (rating.group(1) if rating else None,
            int(count.group(1)) if count else None)


def _recent_expansions(slug: str, quarter: str) -> list[str]:
    """Cities present in plan-input.json now but not at quarter start —
    derived from git history so 'recent expansion' is provable, not vibes."""
    rel = f"clients/{slug}/plan-input.json"
    before = quarter_start(quarter).strftime("%Y-%m-%d")
    try:
        rev = subprocess.run(
            ["git", "rev-list", "-1", f"--before={before}", "HEAD", "--", rel],
            cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
        if not rev:
            return []
        old = json.loads(subprocess.run(
            ["git", "show", f"{rev}:{rel}"],
            cwd=ROOT, capture_output=True, text=True, check=True).stdout)
        old_cities = {a["city"] for a in old.get("service_areas", [])}
        cur = json.loads((ROOT / rel).read_text())
        return [a["city"] for a in cur.get("service_areas", [])
                if a["city"] not in old_cities]
    except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError, OSError):
        return []


def build_facts(slug: str, quarter: str) -> dict:
    plan_input = json.loads((CLIENTS_DIR / slug / "plan-input.json").read_text())
    client = json.loads((CLIENTS_DIR / f"{slug}.json").read_text())
    brand = plan_input.get("brand", {}) or {}
    areas = plan_input.get("service_areas", []) or []
    primary = next((a for a in areas if a.get("primary")), areas[0] if areas else {})
    rating, review_count = _read_synced_rating(slug)
    truth = claims_lint.load_truth(slug)

    services = [s.replace("-", " ") for s in (plan_input.get("services") or [])]

    facts = {
        "display_name": brand.get("display_name") or client.get("display_name"),
        "legal_name": brand.get("legal_name"),
        "site_url": f"https://{client.get('domain')}" if client.get("domain") else None,
        "phone": brand.get("phone"),
        "street_address": brand.get("street_address"),
        "city": primary.get("city"),
        "state": primary.get("state"),
        "postal_code": brand.get("postal_code"),
        "founded_year": brand.get("founded_year") or None,
        "services": services[:8],
        "cities_served": [f"{a['city']}, {a['state']}" for a in areas],
        "recent_expansion_cities": _recent_expansions(slug, quarter),
        # Truth-gated proof points — omitted entirely when not backed by data:
        "available_24_7": bool(truth["is_247"]),
        "response_minutes": truth["response_minutes"],
        "certifications": truth["certifications"],
        "license_numbers": truth["license_numbers"],
        "license_authority": brand.get("license_authority"),
        "family_owned": bool(truth["family_owned"]),
        "google_rating": rating,
        "google_review_count": review_count,
    }
    return facts


# ----------------------------------------------------------------------------
# Anthropic (streaming SSE — same rationale as content_writer.anthropic_call)
# ----------------------------------------------------------------------------


def anthropic_call(system: str, user: str, *, model: str = ANTHROPIC_MODEL,
                   max_tokens: int = 2000, temperature: float = 0.6,
                   max_retries: int = 4) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        die("Missing ANTHROPIC_API_KEY (see rank-ai/.env).")
    body = {"model": model, "max_tokens": max_tokens, "temperature": temperature,
            "system": system, "messages": [{"role": "user", "content": user}],
            "stream": True}
    data = json.dumps(body).encode()
    last = ""
    for attempt in range(1, max_retries + 1):
        req = urllib.request.Request(ANTHROPIC_API, data=data, method="POST",
                                     headers={"x-api-key": api_key,
                                              "anthropic-version": "2023-06-01",
                                              "content-type": "application/json",
                                              "accept": "text/event-stream"})
        chunks: list[str] = []
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                for raw_line in resp:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if not payload:
                        continue
                    try:
                        evt = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    if evt.get("type") == "content_block_delta":
                        chunks.append(evt.get("delta", {}).get("text", ""))
                    elif evt.get("type") == "error":
                        raise RuntimeError(f"API error event: {evt}")
            return "".join(chunks)
        except Exception as e:  # noqa: BLE001 — retry any transport failure
            last = str(e)
            print(f"  anthropic attempt {attempt}/{max_retries} failed: {last}",
                  file=sys.stderr)
    die(f"Anthropic call failed after {max_retries} attempts: {last}")
    return ""  # unreachable


SYSTEM_PROMPT = """You are a wire-service journalist writing a local-market press release for a home-services company. You write in clean AP style: factual, third-person, no hype adjectives, no exclamation points.

ABSOLUTE TRUTH RULES — violating any of these makes the release unusable:
- Use ONLY facts present in the FACTS JSON. Never invent numbers, years, certifications, awards, employee counts, project counts, response times, or availability claims.
- If a fact is null, absent, or false in FACTS, it does not exist. Omit it — do not hedge around it.
- Only claim 24/7 or emergency-response availability if available_24_7 is true.
- Only cite the Google rating/review count if google_rating / google_review_count are present, and use those exact values.
- Only name certifications that appear verbatim in certifications.
- Quotes are attributed to "a spokesperson for {display_name}" (a generic company spokesperson — never invent a personal name or title)."""

USER_PROMPT = """Write a quarterly local-news-style press release announcing this company's continued service (and expansion, if recent_expansion_cities is non-empty) in its market.

FACTS (the only permissible source of claims):
{facts_json}

REQUIREMENTS:
- 350-500 words total (body including boilerplate, excluding the headline).
- Structure, in markdown:
  1. A headline as a single `# ` line (title case, newsworthy, no clickbait).
  2. A dateline paragraph starting exactly: **{city}, {state}** — {date_line} — followed by the lead sentence.
  3. 3-5 body paragraphs: what the company does, the truth-gated proof points (availability, rating/reviews, certifications, license, founding year — only those present in FACTS), the cities served, and the expansion news if any.
  4. Exactly one quoted statement (1-3 sentences) attributed to a spokesperson for {display_name}.
  5. A boilerplate section starting `**About {display_name}**` with: what the company is, founding year if present, service area, then NAP on its own lines (address, phone) and the website URL.
- Do not mention Rank AI, SEO, marketing, or press releases themselves.
- Do not fabricate anything not in FACTS.
{feedback}

Return ONLY the markdown. First line must be the `# ` headline."""


# ----------------------------------------------------------------------------
# Draft generation + truth gate
# ----------------------------------------------------------------------------


def word_count(md: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", md))


def generate_release(slug: str, quarter: str, model: str) -> tuple[str, str]:
    """Returns (title, body_markdown). Dies if it cannot produce a draft that
    passes the CLAIMS TRUTH TABLE lint within MAX_ATTEMPTS."""
    facts = build_facts(slug, quarter)
    truth = claims_lint.load_truth(slug)
    date_line = datetime.now(timezone.utc).strftime("%B %-d, %Y")

    feedback = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        user = USER_PROMPT.format(
            facts_json=json.dumps(facts, indent=2),
            city=facts.get("city") or "",
            state=facts.get("state") or "",
            date_line=date_line,
            display_name=facts.get("display_name") or "",
            feedback=feedback)
        raw = anthropic_call(SYSTEM_PROMPT, user, model=model).strip()
        raw = re.sub(r"^```(?:markdown)?\s*|\s*```$", "", raw).strip()

        lines = raw.splitlines()
        if not lines or not lines[0].startswith("# "):
            feedback = "\nPREVIOUS ATTEMPT REJECTED: first line must be a `# ` headline."
            continue
        title = lines[0][2:].strip()
        body = "\n".join(lines[1:]).strip()

        problems: list[str] = []
        wc = word_count(body)
        if not (WORDS_HARD_MIN <= wc <= WORDS_HARD_MAX):
            problems.append(f"body is {wc} words; target {WORDS_MIN}-{WORDS_MAX}")

        violations = claims_lint.lint_text(f"{title}\n{body}", truth,
                                           source=f"press/{quarter}", part="release")
        errors = [x for x in violations if x["severity"] == "error"]
        reviews = [x for x in violations if x["severity"] != "error"]
        for x in errors:
            problems.append(f"CLAIMS violation [{x['family']}]: {x['reason']} "
                            f"(matched: {x['matched']!r})")

        if not problems:
            for x in reviews:
                print(f"  review-flag [{x['family']}]: {x['reason']} "
                      f"(context: {x['context'][:80]})")
            print(f"  draft OK on attempt {attempt} ({wc} words, "
                  f"{len(reviews)} review-flags)")
            return title, body

        print(f"  attempt {attempt}/{MAX_ATTEMPTS} rejected: "
              f"{'; '.join(problems)}", file=sys.stderr)
        feedback = ("\nPREVIOUS ATTEMPT REJECTED — fix ALL of these without "
                    "introducing new claims:\n- " + "\n- ".join(problems))

    die(f"[{slug}] could not produce a lint-clean {quarter} draft in "
        f"{MAX_ATTEMPTS} attempts — refusing to save (CLAIMS TRUTH TABLE).")
    return "", ""  # unreachable


def write_repo_copy(slug: str, quarter: str, title: str, body: str) -> Path:
    path = CLIENTS_DIR / slug / "press" / f"{quarter}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    fm = (f"---\ntitle: {json.dumps(title)}\nquarter: {quarter}\n"
          f"status: draft\ngenerated_at: {now_iso()}\n---\n\n")
    path.write_text(fm + f"# {title}\n\n{body}\n")
    return path


def draft_one(slug: str, company_id: str, quarter: str, model: str) -> str:
    """Returns one of: 'drafted', 'skipped-exists'."""
    existing = sb_existing_row(company_id, quarter)
    if existing:
        print(f"[{slug}] {quarter} already has a {existing['status']} release "
              f"({existing['title']!r}) — skipping (idempotent).")
        return "skipped-exists"

    print(f"[{slug}] drafting {quarter} press release…")
    title, body = generate_release(slug, quarter, model)
    sb_upsert_draft(company_id, quarter, title, body)
    path = write_repo_copy(slug, quarter, title, body)
    print(f"[{slug}] saved draft: {path.relative_to(ROOT)} + Supabase row "
          f"({company_id}, {quarter}, status=draft)")
    return "drafted"


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------


def active_slugs() -> dict[str, str]:
    """slug -> company_id for every active client in company_map.json."""
    cmap = json.loads((CLIENTS_DIR / "company_map.json").read_text())
    out = {}
    for slug, company_id in cmap.items():
        client_path = CLIENTS_DIR / f"{slug}.json"
        if not client_path.exists():
            continue
        if json.loads(client_path.read_text()).get("status") == "active":
            out[slug] = company_id
    return out


def cmd_draft(args: argparse.Namespace) -> int:
    if not SB_URL or not SB_KEY:
        die("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY must be set (rank-ai/.env).")

    now = datetime.now(timezone.utc)
    quarter = args.quarter or quarter_of(now)

    # Quarterly gate for the monthly cron: run in the first month of a quarter,
    # or in months 2-3 ONLY as catch-up when the quarter has no rows yet
    # (e.g. the first-month run failed). --quarter / --force bypass the gate.
    if not args.quarter and not args.force:
        if not is_first_month_of_quarter(now) and sb_quarter_row_count(quarter) > 0:
            print(f"Gate: {now:%Y-%m} is not the first month of {quarter} and "
                  f"{quarter} already has releases — no-op (quarterly cadence).")
            return 0

    if args.all:
        targets = active_slugs()
    else:
        cmap = json.loads((CLIENTS_DIR / "company_map.json").read_text())
        if args.slug not in cmap:
            die(f"Unknown slug {args.slug!r} — not in clients/company_map.json")
        targets = {args.slug: cmap[args.slug]}

    failures = 0
    for slug, company_id in targets.items():
        try:
            draft_one(slug, company_id, quarter, args.model or ANTHROPIC_MODEL)
        except SystemExit:
            raise
        except Exception as e:  # noqa: BLE001 — one client must not kill --all
            failures += 1
            print(f"[{slug}] FAILED: {e}", file=sys.stderr)
    if failures:
        print(f"{failures} client(s) failed.", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Quarterly press-release drafter")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("draft", help="Draft this quarter's release(s)")
    who = d.add_mutually_exclusive_group(required=True)
    who.add_argument("--slug", help="One client slug")
    who.add_argument("--all", action="store_true",
                     help="Every active client in company_map.json")
    d.add_argument("--quarter", help="Override quarter, e.g. 2026-Q3 "
                                     "(also bypasses the cadence gate)")
    d.add_argument("--force", action="store_true",
                   help="Bypass the quarterly cadence gate (not the "
                        "row-exists idempotency skip)")
    d.add_argument("--model", help=f"Override Anthropic model "
                                   f"(default: {ANTHROPIC_MODEL})")
    d.set_defaults(fn=cmd_draft)
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
