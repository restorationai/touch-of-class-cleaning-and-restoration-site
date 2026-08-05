#!/usr/bin/env python3
"""Case-studies sync — the honest replacement for fabricated job stories.

Background (2026-08-04)
-----------------------
318 service-area pages across 19 client sites carried generator-invented
"A recent {city} response" anecdotes — a property manager who called us, a crew
that arrived in 75 minutes, a claim documented by Tuesday. None of it happened.
Some carried a "this scenario is representative" disclaimer, some did not.
Santino's call: we do not publish job stories unless they are real, and needing
a disclaimer is itself the proof that the content should not be there.

The stories are gone from the pages and from the generator prompts. This script
is the path back for REAL ones.

Flow
----
  clients/{slug}/case-studies.json     <- ops-facing source of truth (Monica)
            |
            |  case_studies_sync.py    (published + validated entries only)
            v
  sites/{slug}/src/data/case-studies.json
            |
            |  CaseStudies.astro       (renders only when non-empty)
            v
  /service-areas/{area}/  ->  "Recent work in {City}"

Every site is seeded with `[]`, so the section renders nothing until a client
actually gives us a job. That mirrors RecentWork.astro, which renders crew job
photos only once real photos exist.

HARD RULE
---------
Nothing in clients/{slug}/case-studies.json may be model-written. It is client
testimony. `--validate` refuses entries carrying the tells of invented copy so a
regression cannot sneak back in through this door.

CLI
---
    python3 scripts/case_studies_sync.py --slug narestco
    python3 scripts/case_studies_sync.py --all
    python3 scripts/case_studies_sync.py --all --seed      # write [] where missing
    python3 scripts/case_studies_sync.py --slug narestco --validate
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLIENTS_DIR = REPO_ROOT / "clients"
SITES_DIR = REPO_ROOT / "sites"

REQUIRED = ("title", "summary")

# Phrases that betray generated prose rather than a real job the client told us
# about. These are exactly the openers the old fabricated stories used.
FABRICATION_TELLS = [
    r"this (scenario|example) is representative",
    r"details (have been )?(generalized|anonymized)",
    r"not attributed to a specific",
    r"does not identify a specific",
    r"representative of the (type of )?(work|calls|loss)",
    r"^a (property manager|homeowner|resident manager|tenant) (overseeing|in|near|at)\b",
]

REQUIRED_CONSENT_NOTE = (
    "case studies describe a real job; confirm the client is OK with it being public"
)


def load(path: Path) -> dict | list:
    return json.loads(path.read_text())


def save(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def client_file(slug: str) -> Path:
    return CLIENTS_DIR / slug / "case-studies.json"


def site_file(slug: str) -> Path:
    return SITES_DIR / slug / "src" / "data" / "case-studies.json"


def blank_client_doc(slug: str) -> dict:
    return {
        "_readme": (
            "REAL case studies only. Never write these with a model, and never publish a job "
            "the client has not confirmed. An entry appears on /service-areas/{area_slug}/ as "
            "'Recent work in {City}'. Leave case_studies empty and the section simply does not "
            "render. Run scripts/case_studies_sync.py after editing. See docs/case-studies.md."
        ),
        "_consent": REQUIRED_CONSENT_NOTE,
        "_schema": {
            "area_slug": "matches sites/{slug}/src/content/serviceAreas/{area_slug}.md (omit = company-wide)",
            "service_slug": "optional; restricts the entry to one city x service page",
            "title": "short, factual, no superlatives — e.g. 'Burst supply line, two-story rental'",
            "summary": "2-4 sentences in plain language: what happened, what we did, outcome. "
                       "Only facts the client confirmed.",
            "performed_on": "YYYY-MM or YYYY-MM-DD",
            "photos": ["https://<supabase>/storage/v1/object/public/branding/{company_id}/case-studies/<file>"],
            "published": "false keeps it staged but unrendered",
        },
        "slug": slug,
        "case_studies": [],
    }


def entries_of(doc) -> list:
    if isinstance(doc, list):
        return doc
    return doc.get("case_studies") or []


def validate(slug: str, entries: list) -> list[str]:
    problems: list[str] = []
    area_dir = SITES_DIR / slug / "src" / "content" / "serviceAreas"
    known_areas = {p.stem for p in area_dir.glob("*.md")} if area_dir.exists() else set()

    for i, c in enumerate(entries):
        where = f"[{i}]"
        if not isinstance(c, dict):
            problems.append(f"{where} not an object")
            continue
        for k in REQUIRED:
            if not (c.get(k) or "").strip():
                problems.append(f"{where} missing required field {k!r}")
        a = c.get("area_slug")
        if a and known_areas and a not in known_areas:
            problems.append(f"{where} area_slug {a!r} has no service-area page")
        blob = f"{c.get('title', '')} {c.get('summary', '')}".strip()
        for pat in FABRICATION_TELLS:
            if re.search(pat, blob, re.I | re.M):
                problems.append(
                    f"{where} reads like generated copy, not a real job (matched /{pat}/). "
                    f"Case studies must be client-supplied."
                )
                break
        d = c.get("performed_on")
        if d and not re.fullmatch(r"\d{4}-\d{2}(-\d{2})?", str(d)):
            problems.append(f"{where} performed_on {d!r} is not YYYY-MM or YYYY-MM-DD")
    return problems


def sync_one(slug: str, seed: bool, validate_only: bool) -> int:
    cf, sf = client_file(slug), site_file(slug)
    if not (SITES_DIR / slug).exists():
        print(f"  {slug}: no site subtree, skipping")
        return 0

    if not cf.exists():
        if seed:
            save(cf, blank_client_doc(slug))
            print(f"  {slug}: seeded {cf.relative_to(REPO_ROOT)}")
        entries = []
    else:
        entries = entries_of(load(cf))

    problems = validate(slug, entries)
    if problems:
        print(f"  {slug}: REJECTED — {len(problems)} problem(s)")
        for p in problems:
            print(f"      {p}")
        return 1
    if validate_only:
        print(f"  {slug}: {len(entries)} entr{'y' if len(entries) == 1 else 'ies'} valid")
        return 0

    published = [
        {
            "area_slug": c.get("area_slug"),
            "service_slug": c.get("service_slug"),
            "title": c.get("title"),
            "summary": c.get("summary"),
            "performed_on": c.get("performed_on"),
            "photos": c.get("photos") or [],
            "published": True,
        }
        for c in entries
        if c.get("published", True)
    ]
    prev = entries_of(load(sf)) if sf.exists() else None
    if prev == published and sf.exists():
        print(f"  {slug}: up to date ({len(published)} published)")
        return 0
    save(sf, published)
    print(f"  {slug}: wrote {len(published)} published -> {sf.relative_to(REPO_ROOT)}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--slug")
    g.add_argument("--all", action="store_true")
    p.add_argument("--seed", action="store_true",
                   help="create clients/{slug}/case-studies.json where missing")
    p.add_argument("--validate", action="store_true",
                   help="validate only; do not write the site data file")
    a = p.parse_args()

    slugs = sorted(d.name for d in SITES_DIR.iterdir() if d.is_dir()) if a.all else [a.slug]
    print(f"==> case-studies sync ({len(slugs)} client{'s' if len(slugs) != 1 else ''})")
    rc = 0
    for s in slugs:
        rc |= sync_one(s, a.seed, a.validate)
    print("==> done" if rc == 0 else "==> FAILED validation")
    return rc


if __name__ == "__main__":
    sys.exit(main())
