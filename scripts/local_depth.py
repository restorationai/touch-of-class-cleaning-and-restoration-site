#!/usr/bin/env python3
"""Local depth — restore the ~120 words of per-city expertise on service-area pages.

Background. Commit 1982eea deleted a generator-written "## A recent {City} response"
section from 318 service-area pages across 19 client sites. The section was a fabricated
customer story and had to go. What went with it was ~120 words per page of body depth
that those pages were earning ranking and E-E-A-T credit for.

This script puts the VOLUME and the E-E-A-T value back without putting the fabrication
back. In the same slot (after the coverage section, before the closing CTA) it writes:

    ## Building stock, site conditions, and permits in {City}

...roughly 120 words about the CITY and the WORK: construction era and dominant wall /
foundation assemblies, plumbing and mechanical vintage and how those systems fail,
soil / drainage / water-table behavior, the weather drivers that actually apply, and who
issues a permit for structural repair locally. Every one of those is a fact about a place,
checkable by anyone, and requires no customer.

The guardrails are the point:

  * The model is given the ENTIRE existing page body and told not to restate it, so the
    new section deepens `## Restoration emergencies common in {City}` instead of echoing it.
  * A fabrication screen rejects the tells of the deleted section — invented customers,
    "called us", crew arrival times, job counts, testimonial quotes, and the disclaimer
    phrasings ("this scenario is representative") that were used to launder it.
  * claims_lint.lint_text runs on every generated section against the client's own brand
    truth, so no 24/7, certification, license, or response-minute claim can ride in.
  * "Write shorter rather than guess" is enforced by acceptance, not just by prompt: a
    70-word section for a city we know less about passes; a padded one that invents an
    ordinance number does not.

Nothing is written to a page until a section passes all three screens. Failures are
reported, not silently dropped.

CLI:
  # phase 1 — generate + screen, writes a review artifact, touches no page
  python3 scripts/local_depth.py generate --files <list.txt> --out <report.json>
  python3 scripts/local_depth.py generate --slug narestco --out <report.json>

  # phase 2 — insert the accepted sections into the markdown bodies
  python3 scripts/local_depth.py apply --report <report.json>

  # inspect
  python3 scripts/local_depth.py show --report <report.json> --slug narestco
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import sys
import threading
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLIENTS_DIR = REPO_ROOT / "clients"
SITES_DIR = REPO_ROOT / "sites"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from claims_lint import load_truth, lint_text  # noqa: E402

# ----------------------------------------------------------------------------
# Model config
# ----------------------------------------------------------------------------

MODEL = "claude-opus-5"
EFFORT = "medium"
MAX_TOKENS = 6000

# $ per 1M tokens (claude-opus-5)
PRICE_IN = 5.00
PRICE_OUT = 25.00
PRICE_CACHE_WRITE = 6.25   # 1.25x input
PRICE_CACHE_READ = 0.50    # 0.1x input

HEADING_TMPL = "## Building stock, site conditions, and permits in {city}"

# Acceptance band. The low end is deliberately generous — a short true section for a
# city we know less about is the CORRECT outcome, not a failure.
MIN_WORDS = 55
TARGET_WORDS = 120
MAX_WORDS = 175   # hard reject above this — the gate is against padding, not 1-word overages
LONG_WORDS = 155  # above this we flag it for a look, but ship it
THIN_WORDS = 95   # below this we flag it in the report as a deliberately-thin city

# ----------------------------------------------------------------------------
# Fabrication screen — the tells of the section this replaces
# ----------------------------------------------------------------------------

FABRICATION_PATTERNS = [
    (r"\bA recent\b", "reintroduces the deleted section's own opener"),
    (r"\b(?:called|contacted|phoned|reached out to) us\b", "invented inbound customer"),
    (r"\ba (?:homeowner|property manager|tenant|landlord|business owner|customer|client|adjuster)\b"
     r"[^.]{0,80}\b(?:called|contacted|reported|reached out|phoned|asked us)\b", "invented customer story"),
    (r"\bwe (?:recently |just )?(?:responded|arrived|were called|got a call|showed up|were on site)\b",
     "invented past response"),
    (r"\bour (?:crew|team|technicians?|staff) (?:arrived|was on site|showed up|responded)\b",
     "invented crew dispatch"),
    (r"\bwe(?:'ve| have) (?:handled|restored|completed|seen|worked on|dried|remediated|serviced)\b",
     "unverifiable track-record claim"),
    # A bare "N homes" is NOT a volume claim when N is a year — "pre-1978 homes" and
    # "1960s homes" are exactly the construction-era facts this section exists to carry.
    # Exclude 1800-2099 so the era language survives, and catch the real shape (a verb of
    # having-done-work in front of the number) with the pattern below it.
    (r"(?<![\w-])(?!(?:1[89]|20)\d\d)\d[\d,]*\s*\+?\s*"
     r"(?:jobs|projects|homes|properties|losses|claims|customers|clients)\b",
     "invented job/volume count"),
    (r"\b(?:completed|restored|serviced|handled|helped|assisted|rebuilt|dried out)\s+"
     r"(?:over\s+|more than\s+|nearly\s+|upwards of\s+)?\d[\d,]*\s*\+?\s*"
     r"(?:jobs|projects|homes|properties|losses|claims|customers|clients|families|buildings)\b",
     "invented track-record count"),
    (r"\b\d[\d,]*\s*(?:\+\s*)?(?:square feet|sq\.?\s?ft\.?)\s+(?:of\s+)?"
     r"(?:restor|remediat|dry|rebuil|mitigat)", "invented square-footage claim"),
    (r"\b(?:hundreds|thousands|dozens) of\s+(?:[a-z]+\s+){0,3}"
     r"(?:jobs|projects|homes|properties|owners|residents|customers|clients)\b",
     "invented volume claim"),
    (r"this scenario|representative of (?:the|our) (?:calls|jobs|work)|details have been generalized"
     r"|names? (?:have been|were) changed|composite (?:of|example)|not attributed to a specific",
     "disclaimer used to launder an invented story"),
    (r"\bon site (?:in|within) \d+\s*(?:minutes|mins|hours)\b", "invented response time"),
    (r"\bwithin \d+\s*(?:minutes|mins)\b", "response-time promise"),
    (r"[“”\"][^\"“”]{25,}[“”\"]", "quoted testimonial text"),
]
FABRICATION_RES = [(re.compile(p, re.I), why) for p, why in FABRICATION_PATTERNS]

# Precision the model should not fake. These are not banned outright — a real
# "2021 International Residential Code" reference is fine — but they get surfaced in the
# report so a human eyeballs every one before it ships.
BRITTLE_PATTERNS = [
    (r"\bordinance\s+(?:no\.?\s*)?[\d-]+", "cites a specific ordinance number"),
    (r"\$\s?\d[\d,]*(?:\.\d\d)?\s*(?:permit|fee|application)", "cites a specific permit fee"),
    (r"\b\d{1,3}(?:\.\d+)?\s*percent\b|\b\d{1,3}(?:\.\d+)?%", "cites a specific percentage"),
    (r"\bsince \d{4}\b|\bin \d{4},", "cites a specific year as fact"),
]
BRITTLE_RES = [(re.compile(p, re.I), why) for p, why in BRITTLE_PATTERNS]


# ----------------------------------------------------------------------------
# Markdown helpers
# ----------------------------------------------------------------------------

def split_frontmatter(raw: str):
    """Return (frontmatter_including_fences, body)."""
    if not raw.startswith("---\n"):
        return "", raw
    end = raw.find("\n---\n", 4)
    if end < 0:
        return "", raw
    return raw[:end + 5], raw[end + 5:]


def body_blocks(body: str):
    return [b for b in body.strip().split("\n\n") if b.strip()]


def word_count(text: str) -> int:
    return len(text.split())


def page_context(path: Path) -> dict:
    raw = path.read_text()
    fm, body = split_frontmatter(raw)
    fm_map = {}
    for line in fm.splitlines():
        if ":" in line and not line.startswith(" "):
            k, v = line.split(":", 1)
            fm_map[k.strip()] = v.strip().strip('"')
    return {"raw": raw, "frontmatter": fm, "body": body.strip(), "fm": fm_map}


# ----------------------------------------------------------------------------
# Prompt construction
# ----------------------------------------------------------------------------

SYSTEM_TMPL = """You are a restoration-industry writer producing one short section of an existing \
service-area page on {display_name}'s website. You are not rewriting the page. You are writing \
ONE section and nothing else.

# The section

Heading (already written for you, do not repeat it in your output):

    {heading}

Around {target} words — aim for 110-130, and treat 145 as a hard ceiling. Two or three plain
paragraphs. No bullet lists, no sub-headings.

Its whole job is to prove that whoever wrote this page understands THIS city's buildings and \
THIS city's rules. Draw on:

- **Construction era and building stock** — when the housing here was largely built, the dominant \
wall and roof assemblies for that era, whether homes sit on slab-on-grade / crawlspace / basement, \
and what that means once water gets into the assembly.
- **Plumbing, mechanical, and material vintage** — the supply and drain materials typical of that \
era (galvanized steel, copper, polybutylene, cast iron, PEX, Orangeburg), the way those systems \
actually fail, and era-linked hazards a restoration scope has to plan around (asbestos-containing \
materials, lead paint, knob-and-tube).
- **Soil, drainage, and water table** — expansive clay, caliche, sand, glacial till, rock, \
engineered fill, high water table — and how it behaves against foundations, crawlspaces, basements, \
and slabs.
- **Weather and seasonal drivers** — freeze depth, monsoon or hurricane season, snow load, wildfire \
smoke, sustained humidity. Only the ones that genuinely apply here.
- **Code, permitting, and the AHJ** — who issues the permit for structural repair or rebuild in this \
city, what typically triggers one, and code context you are confident about (state building code, \
wind or seismic considerations, flood-zone rules, HOA prevalence).

You do not need all five. Use the ones you actually know for this city.

# HARD RULE 1 — never invent a fact about the place

A confidently invented fact about a city is exactly as dishonest as an invented customer. It just \
hides better, because nobody fact-checks a paragraph about soil.

- Never state an ordinance number, permit fee, code edition, adoption date, statistic, percentage, \
elevation, soil classification, or department name you are not actually confident about.
- If something is true regionally rather than municipally, say it at the level you know it \
("across the county", "throughout the Piedmont", "in this part of the valley") rather than dressing \
it up as municipal precision.
- Prefer the durable and checkable (construction era, foundation type, plumbing vintage, climate \
pattern, who pulls the permit) over the specific-sounding and brittle (this year's fee schedule).
- **If you do not know enough about this city to reach {target} words honestly, WRITE A SHORTER \
SECTION.** Seventy true words beat a hundred and twenty padded ones. Nobody is counting your words. \
A homeowner is checking whether you know the place. Never stretch, never hedge into filler, never \
generalize a fact from a different metro onto this one.

# HARD RULE 2 — never invent experience

This section is about the CITY and the WORK. It is never a story about a job.

Forbidden without exception: any customer, homeowner, tenant, property manager, or adjuster, real \
or composite; any past job, arrival time, drying duration, or carrier outcome; any job count, \
project count, or "we have handled X here"; any response-time figure in minutes; any testimonial or \
quoted speech. A disclaimer does not make an invented story acceptable — do not write one and then \
hedge it with "this scenario is representative" or similar.

First person is fine for what the work requires in general ("drying a plaster-and-lath wall here \
means..."). It is never fine for what we have supposedly done.

{truth_block}

# HARD RULE 3 — do not restate the page

You will be given the page's entire existing body. It already has a section on the emergencies \
common in this city (the weather-and-risk overview) and a section on coverage and geography. Your \
section goes UNDERNEATH those: the buildings, the ground, and the paperwork. If a fact is already \
on the page, do not repeat it — go a layer deeper or pick a different fact.

# Voice

Write for an anxious homeowner on a phone, not for a building inspector. Plain declarative \
sentences. Specific nouns. No corporate filler, no "we take pride in", no hyperbole, no restating \
the company name more than once.

# Output

Return JSON only:

  section_markdown  The section body. Paragraphs separated by a blank line. NO heading line — the
                    heading is added for you. Plain markdown, no bullets, no sub-headings.
  facts_used        Short list of the specific local facts you asserted, one short phrase each.
  omitted_because_unsure  What you deliberately left out because you were not confident enough to
                    assert it for this city. Empty string if nothing.
  confidence        "solid" if you know this city well, "partial" if you only know it at the county
                    or metro level, "thin" if you know very little and wrote short on purpose.
"""

OUT_SCHEMA = {
    "type": "object",
    "properties": {
        "section_markdown": {"type": "string"},
        "facts_used": {"type": "array", "items": {"type": "string"}},
        "omitted_because_unsure": {"type": "string"},
        "confidence": {"type": "string", "enum": ["solid", "partial", "thin"]},
    },
    "required": ["section_markdown", "facts_used", "omitted_because_unsure", "confidence"],
    "additionalProperties": False,
}


def truth_block(truth: dict) -> str:
    """The same claims gate the rest of the pipeline runs under, stated for the model."""
    lines = ["# Brand truth (a deploy-time lint checks these)", ""]
    hours = truth.get("hours") or ""
    if truth.get("is_247"):
        lines.append("- Hours: 24/7 — round-the-clock language is permitted.")
    else:
        lines.append(f"- Hours: {hours or '(not set)'} — NEVER write 24/7, around-the-clock, "
                     f"day-or-night, or any after-hours implication.")
    certs = truth.get("certifications") or []
    if certs:
        lines.append(f"- Certifications held: {', '.join(certs)}. Claim no others.")
    else:
        lines.append("- Certifications: none on file. Do not claim the company holds IICRC, EPA, "
                     "Lead-Safe, or any other credential. A neutral reference to an industry "
                     "standard is fine; claiming the credential is not.")
    if truth.get("license_numbers") or truth.get("licensed_insured_attested"):
        lines.append("- Licensure: on file — 'licensed and insured' is permitted.")
    else:
        lines.append("- Licensure: not on file. Do not write 'licensed and insured'.")
    if truth.get("response_minutes"):
        lines.append(f"- Response time on file: {truth['response_minutes']} minutes.")
    else:
        lines.append("- Response minutes: NOT on file. Never state a response time in minutes.")
    if not truth.get("family_owned"):
        lines.append("- Do not write 'family-owned'.")
    lines.append("")
    lines.append("None of the above belongs in this section anyway — it is about the city, not us. "
                 "It is here so you do not drift into it.")
    return "\n".join(lines)


def user_prompt(area: dict, brand: dict, page: dict, heading: str) -> str:
    parts = []
    city = area.get("city", "")
    state = area.get("state", "")
    parts.append(f"# City\n\n**{city}, {state}**\n")
    hood = area.get("neighborhoods") or []
    marks = area.get("landmarks") or []
    zips = area.get("zip_codes") or []
    notes = (area.get("local_notes") or "").strip()
    ctx = []
    if hood:
        ctx.append(f"- Neighborhoods on this page: {', '.join(hood)}")
    if marks:
        ctx.append(f"- Landmarks on this page: {', '.join(marks)}")
    if zips:
        ctx.append(f"- ZIP codes on this page: {', '.join(zips)}")
    if notes:
        ctx.append(f"- Planner's local note: {notes}")
    if ctx:
        parts.append("# Local context already established for this page\n\n" + "\n".join(ctx) + "\n")
    else:
        parts.append("# Local context\n\nNone supplied. Write at the city level only. "
                     "Do not invent a neighborhood, landmark, or ZIP.\n")

    parts.append(
        "# Company base\n\n"
        f"- {brand.get('display_name','')} operates out of "
        f"{brand.get('primary_city','')}, {brand.get('primary_state','')}.\n"
    )

    parts.append(
        "# The page as it stands today — DO NOT REPEAT ANY OF THIS\n\n"
        "Read it in full. Your section is inserted after the coverage section and before the "
        "closing paragraph. Anything already asserted below is off-limits; go deeper or pick a "
        "different fact.\n\n"
        "```markdown\n" + page["body"] + "\n```\n"
    )

    parts.append(
        f"# Your task\n\n"
        f"Write the body of `{heading}` for {city}, {state}. Around {TARGET_WORDS} words (110-130; "
        f"145 hard ceiling) — shorter if that is what you can honestly say about this city. "
        f"Return the JSON object."
    )
    return "\n".join(parts)


# ----------------------------------------------------------------------------
# Screening
# ----------------------------------------------------------------------------

def _shingles(text: str, n: int = 6):
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {tuple(words[i:i + n]) for i in range(max(0, len(words) - n + 1))}


def screen(section: str, truth: dict, existing_body: str) -> dict:
    """Return {'errors': [...], 'warnings': [...]} — errors block the write."""
    errors, warnings = [], []
    s = section.strip()

    if not s:
        errors.append("empty section")
        return {"errors": errors, "warnings": warnings}
    if re.search(r"^\s*#{1,6}\s", s, re.M):
        errors.append("section contains a heading line (the heading is added by the script)")
    if re.search(r"^\s*[-*]\s", s, re.M):
        warnings.append("contains a bullet list (prose was requested)")

    wc = word_count(s)
    if wc > MAX_WORDS:
        errors.append(f"too long: {wc} words (max {MAX_WORDS})")
    elif wc > LONG_WORDS:
        warnings.append(f"long: {wc} words")
    elif wc < MIN_WORDS:
        errors.append(f"too short to be useful: {wc} words (min {MIN_WORDS})")
    elif wc < THIN_WORDS:
        warnings.append(f"deliberately thin: {wc} words")

    for rx, why in FABRICATION_RES:
        m = rx.search(s)
        if m:
            errors.append(f"fabrication screen [{why}]: {m.group(0)[:70]!r}")

    for rx, why in BRITTLE_RES:
        m = rx.search(s)
        if m:
            warnings.append(f"brittle precision [{why}]: {m.group(0)[:70]!r}")

    for v in lint_text(s, truth, source="local-depth", part="body"):
        tag = f"claims_lint {v['severity']} [{v['family']}]: {v['reason']}"
        (errors if v["severity"] == "error" else warnings).append(tag)

    # Near-duplicate of something already on the page?
    have = _shingles(existing_body)
    for sent in re.split(r"(?<=[.!?])\s+", s):
        if word_count(sent) < 8:
            continue
        sh = _shingles(sent)
        if sh and len(sh & have) / len(sh) > 0.5:
            warnings.append(f"echoes existing page copy: {sent[:80]!r}")

    return {"errors": errors, "warnings": warnings}


# ----------------------------------------------------------------------------
# Generation
# ----------------------------------------------------------------------------

_usage_lock = threading.Lock()
USAGE = {"in": 0, "out": 0, "cache_write": 0, "cache_read": 0, "calls": 0}


def record_usage(u) -> None:
    with _usage_lock:
        USAGE["in"] += getattr(u, "input_tokens", 0) or 0
        USAGE["out"] += getattr(u, "output_tokens", 0) or 0
        USAGE["cache_write"] += getattr(u, "cache_creation_input_tokens", 0) or 0
        USAGE["cache_read"] += getattr(u, "cache_read_input_tokens", 0) or 0
        USAGE["calls"] += 1


def spend() -> float:
    return (USAGE["in"] * PRICE_IN
            + USAGE["out"] * PRICE_OUT
            + USAGE["cache_write"] * PRICE_CACHE_WRITE
            + USAGE["cache_read"] * PRICE_CACHE_READ) / 1_000_000


def generate_one(client, path: Path, slug: str, plan: dict, truth: dict,
                 retries: int = 3, extra_user: str = "") -> dict:
    import anthropic

    page = page_context(path)
    area_slug = page["fm"].get("area_slug") or path.stem
    areas = {a.get("slug"): a for a in plan.get("service_areas", [])}
    area = areas.get(area_slug) or {}
    if not area:
        city = page["fm"].get("city", "")
        area = {"city": city, "state": page["fm"].get("state", "")}
    city = area.get("city") or page["fm"].get("city", "")

    brand = dict(plan.get("brand", {}))
    primary = next((a for a in plan.get("service_areas", []) if a.get("primary")),
                   (plan.get("service_areas") or [{}])[0])
    brand.setdefault("primary_city", primary.get("city", ""))
    brand.setdefault("primary_state", primary.get("state", ""))
    brand.setdefault("display_name", truth.get("display_name") or slug)

    heading = HEADING_TMPL.format(city=city)
    system = SYSTEM_TMPL.format(
        display_name=brand.get("display_name", ""),
        heading=heading,
        target=TARGET_WORDS,
        truth_block=truth_block(truth),
    )
    user = user_prompt(area, brand, page, heading) + (extra_user or "")

    last_err = ""
    for attempt in range(1, retries + 1):
        try:
            resp = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                thinking={"type": "adaptive"},
                output_config={
                    "effort": EFFORT,
                    "format": {"type": "json_schema", "schema": OUT_SCHEMA},
                },
                system=[{"type": "text", "text": system,
                         "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": user}],
            )
            record_usage(resp.usage)
            if resp.stop_reason == "refusal":
                last_err = "model refused"
                continue
            text = next((b.text for b in resp.content if b.type == "text"), "")
            data = json.loads(text)
            section = (data.get("section_markdown") or "").strip()
            # normalize whitespace: single blank line between paragraphs
            section = re.sub(r"\n{3,}", "\n\n", section)
            section = re.sub(r"[ \t]+\n", "\n", section)
            result = screen(section, truth, page["body"])
            return {
                "path": str(path.relative_to(REPO_ROOT)),
                "slug": slug,
                "city": city,
                "state": area.get("state", ""),
                "heading": heading,
                "section": section,
                "words_before": word_count(page["body"]),
                "words_section": word_count(section),
                "facts_used": data.get("facts_used") or [],
                "omitted_because_unsure": data.get("omitted_because_unsure") or "",
                "confidence": data.get("confidence") or "",
                "errors": result["errors"],
                "warnings": result["warnings"],
                "ok": not result["errors"],
            }
        except (anthropic.RateLimitError, anthropic.InternalServerError,
                anthropic.APIConnectionError) as e:
            last_err = f"{type(e).__name__}: {e}"
            time.sleep(2 ** attempt)
        except anthropic.BadRequestError as e:
            # A 400 is normally a malformed request and retrying is pointless — except
            # for the bare `invalid_request_error / "Invalid request data"` shape, which
            # we confirmed is transient: the identical payload succeeds on a re-send.
            # A real malformed request names the offending field, so only retry the
            # message-less variant and let anything specific fail fast.
            if "Invalid request data" in str(e):
                last_err = f"transient 400: {str(e)[:120]}"
                time.sleep(2 ** attempt)
                continue
            last_err = f"BadRequestError: {str(e)[:200]}"
            break
        except json.JSONDecodeError as e:
            last_err = f"bad JSON: {e}"
        except Exception as e:  # noqa: BLE001
            last_err = f"{type(e).__name__}: {str(e)[:200]}"
            break

    return {
        "path": str(path.relative_to(REPO_ROOT)),
        "slug": slug, "city": city, "state": area.get("state", ""),
        "heading": "", "section": "", "words_before": word_count(page["body"]),
        "words_section": 0, "facts_used": [], "omitted_because_unsure": "",
        "confidence": "", "errors": [f"generation failed: {last_err}"],
        "warnings": [], "ok": False,
    }


def resolve_targets(args) -> list:
    paths = []
    if args.files:
        for line in Path(args.files).read_text().splitlines():
            line = line.strip()
            if line:
                paths.append(REPO_ROOT / line)
    elif args.slug:
        d = SITES_DIR / args.slug / "src" / "content" / "serviceAreas"
        paths = sorted(d.glob("*.md"))
    else:
        for d in sorted(SITES_DIR.glob("*/src/content/serviceAreas")):
            paths.extend(sorted(d.glob("*.md")))
    live = []
    for p in paths:
        if not p.exists():
            print(f"  ! missing: {p}")
            continue
        raw = p.read_text()
        if "rendered: true" not in raw:
            print(f"  - skip (not rendered): {p.relative_to(REPO_ROOT)}")
            continue
        if HEADING_TMPL.split("{")[0] in raw:
            print(f"  - skip (already has the section): {p.relative_to(REPO_ROOT)}")
            continue
        live.append(p)
    if args.limit:
        live = live[:args.limit]
    return live


def cmd_generate(args) -> int:
    import anthropic

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Missing ANTHROPIC_API_KEY (set -a && source .env && set +a)")
        return 1

    targets = resolve_targets(args)
    if not targets:
        print("Nothing to do.")
        return 0

    by_slug = {}
    for p in targets:
        by_slug.setdefault(p.parts[len(REPO_ROOT.parts) + 1], []).append(p)

    print(f"==> local-depth generate: {len(targets)} page(s) across {len(by_slug)} client(s)")
    print(f"    model={MODEL} effort={EFFORT} workers={args.workers}")
    print()

    client = anthropic.Anthropic(max_retries=4, timeout=900.0)
    results = []
    t0 = time.time()
    done = [0]
    total = len(targets)
    print_lock = threading.Lock()

    ctx = {}
    for slug in by_slug:
        plan_path = CLIENTS_DIR / slug / "plan-input.json"
        plan = json.loads(plan_path.read_text()) if plan_path.exists() else {}
        truth = load_truth(slug)
        truth.setdefault("display_name", (plan.get("brand") or {}).get("display_name", slug))
        ctx[slug] = (plan, truth)

    def report_one(r):
        with print_lock:
            done[0] += 1
            print(f"  [{done[0]:>3}/{total}] {'ok ' if r['ok'] else 'ERR'} "
                  f"{r['slug'][:26]:<26} {r['city'][:20]:<20} "
                  f"{r['words_section']:>3}w {r['confidence']:<7}"
                  + ("" if r["ok"] else f"  <- {r['errors'][0][:70]}")
                  + ("" if not r["warnings"] else f"  (!) {r['warnings'][0][:50]}"))
            sys.stdout.flush()

    def run_wave(items):
        """items: [(path, slug)]"""
        if not items:
            return
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = [ex.submit(generate_one, client, p, s, ctx[s][0], ctx[s][1])
                    for p, s in items]
            for fut in concurrent.futures.as_completed(futs):
                r = fut.result()
                results.append(r)
                report_one(r)

    # Wave 1 — one page per client, all clients in parallel. This writes each
    # client's system-prompt cache entry exactly once instead of once per page,
    # without serializing 19 clients behind each other.
    print(f"  -- wave 1: {len(by_slug)} cache-priming page(s), one per client")
    run_wave([(paths[0], slug) for slug, paths in by_slug.items()])

    # Wave 2 — everything else, one global pool reading those warm caches.
    rest = [(p, slug) for slug, paths in by_slug.items() for p in paths[1:]]
    print(f"  -- wave 2: {len(rest)} remaining page(s)")
    run_wave(rest)

    results.sort(key=lambda r: r["path"])
    elapsed = time.time() - t0
    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "model": MODEL, "effort": EFFORT,
        "usage": dict(USAGE), "spend_usd": round(spend(), 4),
        "elapsed_seconds": round(elapsed, 1),
        "results": results,
    }
    Path(args.out).write_text(json.dumps(report, indent=2))

    ok = [r for r in results if r["ok"]]
    bad = [r for r in results if not r["ok"]]
    warn = [r for r in ok if r["warnings"]]
    print()
    print(f"==> {len(ok)}/{len(results)} accepted, {len(bad)} rejected, {len(warn)} with warnings")
    print(f"    tokens: in={USAGE['in']:,} out={USAGE['out']:,} "
          f"cache_w={USAGE['cache_write']:,} cache_r={USAGE['cache_read']:,}")
    print(f"    spend:  ${spend():.4f}   elapsed: {elapsed/60:.1f} min")
    print(f"    report: {args.out}")
    for r in bad:
        print(f"    REJECT {r['path']}: {r['errors']}")
    return 0


def cmd_apply(args) -> int:
    report = json.loads(Path(args.report).read_text())
    written, skipped = 0, 0
    for r in report["results"]:
        if not r["ok"]:
            skipped += 1
            continue
        path = REPO_ROOT / r["path"]
        raw = path.read_text()
        if r["heading"] in raw:
            print(f"  - already applied: {r['path']}")
            skipped += 1
            continue
        fm, body = split_frontmatter(raw)
        blocks = body_blocks(body)
        if not blocks or blocks[-1].startswith("#"):
            print(f"  ! unexpected structure, skipping: {r['path']}")
            skipped += 1
            continue
        section = r["heading"] + "\n\n" + r["section"].strip()
        blocks.insert(len(blocks) - 1, section)
        # Blocks are markdown paragraphs/headings — they MUST be rejoined with a
        # blank line. A single "\n" here silently glues every heading onto the
        # paragraph above it and the page renders as one wall of text.
        path.write_text(fm + "\n\n".join(b.strip() for b in blocks) + "\n")
        written += 1
    print(f"==> applied {written} section(s), skipped {skipped}")
    return 0


def cmd_regenerate(args) -> int:
    """Re-run only the entries still marked failed in a report, merging results in place.

    Failures fall into two buckets and both want another attempt rather than a hand-edit:
    a transient API error (nothing was written), or a section that overshot the length
    ceiling (real content, wrong size). For the second, the retry is told what it did wrong.
    """
    import anthropic

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Missing ANTHROPIC_API_KEY (set -a && source .env && set +a)")
        return 1

    report = json.loads(Path(args.report).read_text())
    failed = [r for r in report["results"] if not r["ok"]]
    if not failed:
        print("==> nothing to regenerate.")
        return 0
    print(f"==> regenerating {len(failed)} failed page(s)")

    client = anthropic.Anthropic(max_retries=4, timeout=900.0)
    ctx = {}
    for r in failed:
        slug = r["slug"]
        if slug not in ctx:
            pp = CLIENTS_DIR / slug / "plan-input.json"
            plan = json.loads(pp.read_text()) if pp.exists() else {}
            t = load_truth(slug)
            t.setdefault("display_name", (plan.get("brand") or {}).get("display_name", slug))
            ctx[slug] = (plan, t)

    def redo(r):
        plan, truth = ctx[r["slug"]]
        nudge = ""
        for e in r["errors"]:
            if e.startswith("too long"):
                nudge = (f"\n\n# Retry note\n\nA previous attempt for this city ran "
                         f"{r['words_section']} words, which is too long. Same facts, same "
                         f"honesty — but this one MUST come in under 140 words. Cut the "
                         f"least-specific sentence rather than compressing everything.")
        out = generate_one(client, REPO_ROOT / r["path"], r["slug"], plan, truth,
                           extra_user=nudge)
        return r["path"], out

    by_path = {r["path"]: i for i, r in enumerate(report["results"])}
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        for fut in concurrent.futures.as_completed([ex.submit(redo, r) for r in failed]):
            path, out = fut.result()
            report["results"][by_path[path]] = out
            print(f"  {'ok ' if out['ok'] else 'ERR'} {out['slug']:<30} {out['city']:<20} "
                  f"{out['words_section']:>3}w"
                  + ("" if out["ok"] else f"  <- {out['errors'][0][:80]}"))

    report["usage"] = dict(USAGE)
    report["regenerate_spend_usd"] = round(spend(), 4)
    report["spend_usd"] = round(report.get("spend_usd", 0) + spend(), 4)
    Path(args.report).write_text(json.dumps(report, indent=2))
    still = [r for r in report["results"] if not r["ok"]]
    print(f"==> {len(failed) - len(still)} recovered, {len(still)} still failing. "
          f"regenerate spend ${spend():.4f}")
    for r in still:
        print(f"    STILL FAILING {r['path']}: {r['errors']}")
    return 0


def cmd_rescreen(args) -> int:
    """Re-run screen() over an existing report with no new API calls.

    The screen is pure — it takes the stored section, the client's truth table, and the
    page body as it stands on disk. So when a screen pattern turns out to be wrong (the
    first cut read "pre-1978 homes" as a job count), the fix is to correct the pattern and
    re-judge the sections we already paid for, not to regenerate them.
    """
    report = json.loads(Path(args.report).read_text())
    truths, flipped = {}, {"to_ok": [], "to_bad": []}
    for r in report["results"]:
        if not r.get("section"):
            continue
        slug = r["slug"]
        if slug not in truths:
            plan_path = CLIENTS_DIR / slug / "plan-input.json"
            plan = json.loads(plan_path.read_text()) if plan_path.exists() else {}
            t = load_truth(slug)
            t.setdefault("display_name", (plan.get("brand") or {}).get("display_name", slug))
            truths[slug] = t
        page = page_context(REPO_ROOT / r["path"])
        was_ok = r["ok"]
        res = screen(r["section"], truths[slug], page["body"])
        r["errors"], r["warnings"] = res["errors"], res["warnings"]
        r["ok"] = not res["errors"]
        if r["ok"] and not was_ok:
            flipped["to_ok"].append(r["path"])
        elif was_ok and not r["ok"]:
            flipped["to_bad"].append(r["path"])

    Path(args.report).write_text(json.dumps(report, indent=2))
    ok = [r for r in report["results"] if r["ok"]]
    bad = [r for r in report["results"] if not r["ok"]]
    print(f"==> rescreened {len(report['results'])}: {len(ok)} accepted, {len(bad)} rejected")
    print(f"    newly accepted: {len(flipped['to_ok'])}  newly rejected: {len(flipped['to_bad'])}")
    for r in bad:
        print(f"    REJECT {r['path']}: {r['errors']}")
    return 0


def cmd_show(args) -> int:
    report = json.loads(Path(args.report).read_text())
    for r in report["results"]:
        if args.slug and r["slug"] != args.slug:
            continue
        if args.city and args.city.lower() not in r["city"].lower():
            continue
        print("=" * 78)
        print(f"{r['slug']} / {r['city']}, {r['state']}   "
              f"{r['words_section']}w  confidence={r['confidence']}  ok={r['ok']}")
        if r["errors"]:
            print(f"ERRORS: {r['errors']}")
        if r["warnings"]:
            print(f"WARN:   {r['warnings']}")
        print("-" * 78)
        print(r["heading"])
        print()
        print(r["section"])
        if r["omitted_because_unsure"]:
            print(f"\n[omitted: {r['omitted_because_unsure']}]")
        print()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate")
    g.add_argument("--files", help="newline-delimited list of repo-relative page paths")
    g.add_argument("--slug", help="one client slug")
    g.add_argument("--out", required=True)
    g.add_argument("--limit", type=int, default=0)
    g.add_argument("--workers", type=int, default=8)
    g.set_defaults(func=cmd_generate)

    rs = sub.add_parser("rescreen")
    rs.add_argument("--report", required=True)
    rs.set_defaults(func=cmd_rescreen)

    rg = sub.add_parser("regenerate")
    rg.add_argument("--report", required=True)
    rg.add_argument("--workers", type=int, default=6)
    rg.set_defaults(func=cmd_regenerate)

    a = sub.add_parser("apply")
    a.add_argument("--report", required=True)
    a.set_defaults(func=cmd_apply)

    s = sub.add_parser("show")
    s.add_argument("--report", required=True)
    s.add_argument("--slug")
    s.add_argument("--city")
    s.set_defaults(func=cmd_show)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
