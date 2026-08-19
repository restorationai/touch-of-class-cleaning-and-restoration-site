#!/usr/bin/env python3
"""faq_backfill.py — area-hub FAQs, fleet-wide, without re-rendering bodies.

WHY (SEO queue item 3, 2026-08-19): the area-page checklist marks locally
specific Q&As + FAQPage schema as a MUST, and our area HUB pages shipped with
faq: [] while service and city-service pages carry both. This script fills
ONLY the faq frontmatter of already-rendered service-area pages, grounded in
each page's own rendered body, so the bodies (already unique and lint-clean)
never churn.

Guardrails:
  - 4-5 Q&As, every one area-specific; grounded ONLY in the page body +
    brand facts passed in; inventing neighborhoods/permits/times is banned in
    the prompt AND checked after: claims_lint runs on every updated file and
    an error-severity hit reverts that file.
  - A rotation seed varies question TYPES per page so sibling pages differ.
  - Only touches files with archetype service-area, rendered: true, faq: [].

Usage:
  python3 scripts/faq_backfill.py --slug reign-restoration [--limit 3] [--dry-run]
  python3 scripts/faq_backfill.py --all
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITES = ROOT / "sites"
CLIENTS = ROOT / "clients"
sys.path.insert(0, str(Path(__file__).parent))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

import requests  # noqa: E402
import claims_lint  # noqa: E402

API = "https://api.anthropic.com/v1/messages"
MODEL = os.environ.get("RANKAI_RENDER_MODEL", "claude-sonnet-4-6")

# Question-type rotation — the seed picks a SUBSET so sibling pages ask
# different things (the uniqueness rule applies to FAQs too).
ANGLES = [
    "coverage: whether specific neighborhoods/communities NAMED IN THE BODY are served",
    "travel/response framing for this city (NO minute promises unless the body states one)",
    "which of the services listed are most requested in this city, per the body's local context",
    "what happens first when someone in this city calls (process, grounded in body/brand facts)",
    "how this city's housing stock or conditions (per the body) affect the work",
    "insurance/claims handling as it applies locally (only if the body mentions insurance)",
    "scheduling/availability for this city (no availability claims beyond brand facts)",
]

SYSTEM = """You write FAQ entries for ONE service-area page of a local home-services company.
Produce EXACTLY 4 or 5 Q&As specific to the named city.

HARD RULES:
1. GROUNDING: every factual detail must come from the PAGE BODY or the BRAND FACTS provided.
   NEVER invent neighborhoods, landmarks, permit rules, response times, prices, guarantees,
   licenses, certifications, or availability. If the body names neighborhoods, you may use
   them; if not, do not name any.
2. AREA-SPECIFIC: each question must be one that would read wrong on another town's page.
   Generic trade questions (what is water damage, how does drying work) are BANNED here.
3. VOICE: plain 6th-grade words. The answer states the question's fact directly in the first
   sentence (AI-citation friendly), 2-4 sentences total. Never use em dashes or en dashes.
4. Use the ANGLES list as your question types, in the given order, one question per angle.
5. Output ONLY a JSON array: [{"question": "...", "answer": "..."}]"""


def anthropic_faq(brand: str, city: str, state: str, body: str,
                  angles: list[str]) -> list[dict]:
    user = (f"BRAND FACTS:\n{brand}\n\nCITY: {city}, {state}\n\n"
            f"ANGLES (one question each, in order):\n"
            + "\n".join(f"- {a}" for a in angles)
            + f"\n\nPAGE BODY (the ONLY source of local facts):\n{body[:6000]}")
    for attempt in range(3):
        r = requests.post(API, headers={
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"},
            json={"model": MODEL, "max_tokens": 1200, "system": SYSTEM,
                  "messages": [{"role": "user", "content": user}]},
            timeout=120)
        if r.status_code in (429, 529) or r.status_code >= 500:
            time.sleep(5 * (attempt + 1))
            continue
        r.raise_for_status()
        text = "".join(b.get("text", "") for b in r.json()["content"]).strip()
        m = re.search(r"\[.*\]", text, re.S)
        if not m:
            continue
        try:
            faq = json.loads(m.group(0))
        except json.JSONDecodeError:
            continue
        clean = [{"question": str(q.get("question", "")).strip(),
                  "answer": str(q.get("answer", "")).strip()}
                 for q in faq if q.get("question") and q.get("answer")]
        if 3 <= len(clean) <= 6:
            # the no-dash rule is absolute in client copy
            for q in clean:
                q["question"] = re.sub(r"\s*[—–]\s*", ", ", q["question"])
                q["answer"] = re.sub(r"\s*[—–]\s*", ", ", q["answer"])
            return clean
    return []


def brand_block(slug: str) -> str:
    try:
        rec = json.loads((CLIENTS / f"{slug}.json").read_text())
    except (OSError, json.JSONDecodeError):
        rec = {}
    plan = rec.get("plan") or {}
    try:
        pi = json.loads((CLIENTS / slug / "plan" / "plan-input.json").read_text())
    except (OSError, json.JSONDecodeError):
        pi = {}
    brand = pi.get("brand") or {}
    svcs = pi.get("services") or plan.get("services") or []
    svc_names = [s.get("display_name", s) if isinstance(s, dict) else s for s in svcs]
    return (f"Company: {rec.get('display_name', slug)}\n"
            f"Phone: {brand.get('phone', '')}\n"
            f"Base city: {brand.get('city') or ''}, {brand.get('state') or ''}\n"
            f"Services: {', '.join(map(str, svc_names[:14]))}")


def eligible_files(slug: str) -> list[Path]:
    d = SITES / slug / "src" / "content" / "serviceAreas"
    if not d.is_dir():
        return []
    out = []
    for f in sorted(d.glob("*.md")):
        head = f.read_text()[:20000]
        fm = head.split("\n---\n", 1)[0]
        if ('archetype: "service-area"' in fm and "\nrendered: true" in fm
                and re.search(r"^faq: \[\]\s*$", fm, re.M)):
            out.append(f)
    return out


def process_file(slug: str, f: Path, brand: str, seed: int,
                 dry_run: bool) -> str:
    text = f.read_text()
    fm, body = text.split("\n---\n", 1)
    city = (re.search(r'^city: "(.*)"$', fm, re.M) or [None, ""])[1]
    state = (re.search(r'^state: "(.*)"$', fm, re.M) or [None, ""])[1]
    if not city:
        return f"SKIP {f.name}: no city in frontmatter"
    # rotate which 4-5 angles this page gets, keeping neighbors different
    rot = [ANGLES[(seed + i) % len(ANGLES)] for i in range(5)]
    faq = anthropic_faq(brand, city, state, body, rot)
    if not faq:
        return f"FAIL {f.name}: no valid FAQ from model"
    if dry_run:
        return (f"DRY {f.name}: {len(faq)} Q&As, first: "
                f"{faq[0]['question'][:70]!r}")
    new_fm = re.sub(r"^faq: \[\]\s*$", "faq: " + json.dumps(faq), fm,
                    count=1, flags=re.M)
    f.write_text(new_fm + "\n---\n" + body)
    # truth gate: an error-severity claim reverts the file
    truth = claims_lint.load_truth(slug)
    violations = claims_lint.lint_file(f, truth, rel_root=SITES / slug)
    errors = [v for v in violations if v["severity"] == "error"]
    if errors:
        f.write_text(text)
        return (f"REVERTED {f.name}: lint error "
                f"{errors[0]['family']}: ...{errors[0]['context'][:60]}...")
    return f"OK {f.name}: {len(faq)} Q&As"


def run_slug(slug: str, limit: int | None, dry_run: bool) -> tuple[int, int]:
    files = eligible_files(slug)
    if limit:
        files = files[:limit]
    if not files:
        print(f"  {slug}: nothing eligible (no rendered area hubs with empty faq)")
        return (0, 0)
    brand = brand_block(slug)
    ok = fail = 0
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(process_file, slug, f, brand, i, dry_run): f
                for i, f in enumerate(files)}
        for fut in as_completed(futs):
            msg = fut.result()
            print(f"  {slug}: {msg}")
            if msg.startswith(("OK", "DRY")):
                ok += 1
            else:
                fail += 1
    return (ok, fail)


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--slug")
    g.add_argument("--all", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    slugs = ([args.slug] if args.slug else
             sorted(p.name for p in SITES.iterdir()
                    if (p / "src" / "content" / "serviceAreas").is_dir()))
    tot_ok = tot_fail = 0
    for slug in slugs:
        ok, fail = run_slug(slug, args.limit, args.dry_run)
        tot_ok += ok
        tot_fail += fail
    print(f"\n{tot_ok} page(s) updated, {tot_fail} failed/reverted.")
    return 0 if tot_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
