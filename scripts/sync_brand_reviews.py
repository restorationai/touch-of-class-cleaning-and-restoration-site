#!/usr/bin/env python3
"""Sync REAL Google Business Profile ratings + review snippets into each site's
brand.ts (and the llms.txt rating line).

Truthful-ratings pipeline: competitors fabricate AggregateRating values; we only
ever publish what the live GBP actually says. Sources:

  marketing_gbp_profiles  (Supabase) -> rating, review_count
  marketing_gbp_reviews   (Supabase) -> up to 6 recent 4-5 star review snippets

Writes (surgical regex edits, never a rewrite):
  sites/{slug}/src/lib/brand.ts   -> gbpRatingValue, gbpReviewCount, gbpReviews
  sites/{slug}/public/llms.txt    -> "- Rated {rating}/5 from {count} Google reviews"

Skips gracefully when a client has no company_id or no marketing_gbp_profiles row
(e.g. davis-construction) — the site then builds without an AggregateRating and
the on-page ReviewsStrip renders nothing.

Usage:
  python3 scripts/sync_brand_reviews.py narestco homepriderestorationandcleaning
  python3 scripts/sync_brand_reviews.py --all
  python3 scripts/sync_brand_reviews.py --all --dry-run
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

MAX_REVIEWS = 6          # snippets stored in brand.ts
MIN_STARS = 4            # only 4-5 star reviews are quotable proof
MIN_TEXT_LEN = 30        # skip star-only / one-word reviews
MAX_TEXT_LEN = 300       # truncate long reviews at a word boundary

GBP_FIELD_COMMENT = (
    "  // GBP rating fields — synced from the live Google Business Profile by\n"
    "  // scripts/sync_brand_reviews.py; never hand-edited (real ratings only).\n"
)


def _sb_get(path: str):
    r = requests.get(
        f"{SB_URL}/rest/v1/{path}",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def company_id_for(slug: str) -> str | None:
    rec = ROOT / "clients" / f"{slug}.json"
    if rec.exists():
        cid = json.loads(rec.read_text()).get("company_id")
        if cid:
            return cid
    cmap = ROOT / "clients" / "company_map.json"
    return json.loads(cmap.read_text()).get(slug) if cmap.exists() else None


def fetch_profile(cid: str) -> dict | None:
    rows = _sb_get(f"marketing_gbp_profiles?company_id=eq.{cid}&select=rating,review_count")
    if not rows or rows[0].get("rating") is None or not rows[0].get("review_count"):
        return None
    return rows[0]


def _clean_text(raw: str) -> str:
    """Strip HTML (owner replies embed <br>), collapse whitespace, truncate."""
    txt = re.sub(r"<[^>]+>", " ", raw)
    txt = html.unescape(txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    if len(txt) > MAX_TEXT_LEN:
        cut = txt[:MAX_TEXT_LEN].rsplit(" ", 1)[0].rstrip(",.;:!— ")
        txt = cut + "…"
    return txt


def _when_label(create_time: str | None) -> str:
    if not create_time:
        return ""
    try:
        d = dt.datetime.fromisoformat(create_time.replace("Z", "+00:00"))
        return d.strftime("%B %Y")
    except ValueError:
        return ""


def fetch_reviews(cid: str) -> list[dict]:
    """Recent 4-5 star reviews with real text. Returns [] if the table is empty,
    missing, or has an unexpected shape (rating+count-only mode)."""
    try:
        probe = _sb_get(f"marketing_gbp_reviews?company_id=eq.{cid}&select=*&limit=1")
    except requests.RequestException as e:
        print(f"    note: marketing_gbp_reviews not readable ({e}); rating+count only")
        return []
    if not probe:
        return []
    cols = set(probe[0].keys())
    needed = {"reviewer_name", "star_rating", "comment", "create_time"}
    if not needed.issubset(cols):
        print(f"    note: marketing_gbp_reviews missing columns {needed - cols}; rating+count only")
        return []

    rows = _sb_get(
        f"marketing_gbp_reviews?company_id=eq.{cid}"
        f"&star_rating=gte.{MIN_STARS}&comment=not.is.null"
        f"&select=reviewer_name,star_rating,comment,create_time"
        f"&order=create_time.desc&limit=30"
    )
    out: list[dict] = []
    for rv in rows:
        text = _clean_text(rv.get("comment") or "")
        if len(text) < MIN_TEXT_LEN:
            continue
        name = (rv.get("reviewer_name") or "").strip()
        first = name.split()[0].title() if name else "Verified customer"
        out.append({
            "author": first,
            "rating": int(rv.get("star_rating") or 5),
            "text": text,
            "when": _when_label(rv.get("create_time")),
        })
        if len(out) >= MAX_REVIEWS:
            break
    return out


def _ts_str(v: str) -> str:
    return json.dumps(v, ensure_ascii=False)


def render_reviews_ts(reviews: list[dict]) -> str:
    """The gbpReviews entry for brand.ts, matching the file's 2-space style."""
    if not reviews:
        return ("  gbpReviews: [] as "
                "{ author: string; rating: number; text: string; when: string }[],")
    lines = ["  gbpReviews: ["]
    for r in reviews:
        lines.append(
            f"    {{ author: {_ts_str(r['author'])}, rating: {r['rating']}, "
            f"text: {_ts_str(r['text'])}, when: {_ts_str(r['when'])} }},"
        )
    lines.append("  ] as { author: string; rating: number; text: string; when: string }[],")
    return "\n".join(lines)


def update_brand_ts(path: Path, rating: str, count: str, reviews: list[dict], dry: bool) -> list[str]:
    src = path.read_text()
    changes: list[str] = []

    def sub_field(field: str, value: str, text: str) -> str:
        pattern = rf'({field}:\s*")[^"]*(")'
        if not re.search(pattern, text):
            raise SystemExit(f"  ERROR: {path} has no {field} field — brand.ts format changed?")
        new_text, n = re.subn(pattern, lambda m: m.group(1) + value + m.group(2), text, count=1)
        return new_text

    old_rating = re.search(r'gbpRatingValue:\s*"([^"]*)"', src).group(1) if re.search(r'gbpRatingValue:\s*"([^"]*)"', src) else "?"
    old_count = re.search(r'gbpReviewCount:\s*"([^"]*)"', src).group(1) if re.search(r'gbpReviewCount:\s*"([^"]*)"', src) else "?"
    src = sub_field("gbpRatingValue", rating, src)
    src = sub_field("gbpReviewCount", count, src)
    if (old_rating, old_count) != (rating, count):
        changes.append(f"rating {old_rating or '∅'} -> {rating}, count {old_count or '∅'} -> {count}")
    else:
        changes.append(f"rating {rating}, count {count} (unchanged)")

    reviews_block = render_reviews_ts(reviews)
    existing = re.search(
        r"[ \t]*gbpReviews:\s*\[.*?\]\s*as\s*\{[^}]*\}\[\],", src, flags=re.DOTALL
    )
    if existing:
        if existing.group(0) != reviews_block:
            src = src[: existing.start()] + reviews_block + src[existing.end():]
            changes.append(f"gbpReviews -> {len(reviews)} snippet(s)")
    else:
        # Insert right after the gbpReviewCount line (stable anchor).
        anchor = re.search(r'[ \t]*gbpReviewCount:\s*"[^"]*",\n', src)
        src = src[: anchor.end()] + reviews_block + "\n" + src[anchor.end():]
        changes.append(f"gbpReviews field added ({len(reviews)} snippet(s))")

    # Provenance comment above the gbp block (once).
    if "sync_brand_reviews" not in src.split("gbpRatingValue")[0]:
        m = re.search(r'[ \t]*gbpRatingValue:', src)
        if m and "sync_brand_reviews.py; never hand-edited" not in src:
            src = src[: m.start()] + GBP_FIELD_COMMENT + src[m.start():]
            changes.append("provenance comment added")

    if not dry:
        path.write_text(src)
    return changes


def update_llms_txt(path: Path, rating: str, count: str, dry: bool) -> str | None:
    if not path.exists():
        return None
    src = path.read_text()
    line = f"- Rated {rating}/5 from {count} Google reviews"
    if re.search(r"^- Rated .*Google reviews$", src, flags=re.M):
        new = re.sub(r"^- Rated .*Google reviews$", line, src, count=1, flags=re.M)
        change = "llms.txt rating line updated" if new != src else "llms.txt rating line unchanged"
    elif "## Key facts" in src:
        new = src.replace("## Key facts\n\n", f"## Key facts\n\n{line}\n", 1)
        change = "llms.txt rating line added"
    else:
        return "llms.txt has no '## Key facts' section — skipped"
    if not dry and new != src:
        path.write_text(new)
    return change


def sync(slug: str, dry: bool) -> None:
    tag = "[dry-run] " if dry else ""
    site = ROOT / "sites" / slug
    brand_ts = site / "src" / "lib" / "brand.ts"
    if not brand_ts.exists():
        print(f"  {slug}: skip — no {brand_ts.relative_to(ROOT)}")
        return
    cid = company_id_for(slug)
    if not cid:
        print(f"  {slug}: skip — no company_id in clients/{slug}.json")
        return
    profile = fetch_profile(cid)
    if not profile:
        print(f"  {slug}: skip — no marketing_gbp_profiles row for {cid} (GBP sync never ran)")
        return

    rating = f"{float(profile['rating']):.1f}"
    count = str(int(profile["review_count"]))
    reviews = fetch_reviews(cid)

    changes = update_brand_ts(brand_ts, rating, count, reviews, dry)
    llms_change = update_llms_txt(site / "public" / "llms.txt", rating, count, dry)
    if llms_change:
        changes.append(llms_change)
    print(f"  {tag}{slug}: {rating}★ / {count} reviews — " + "; ".join(changes))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("slugs", nargs="*", help="client slugs (sites/{slug})")
    ap.add_argument("--all", action="store_true", help="every directory under sites/")
    ap.add_argument("--dry-run", action="store_true", help="report changes without writing")
    args = ap.parse_args()

    if not (SB_URL and SB_KEY):
        print("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY missing from .env"); return 1
    slugs = args.slugs
    if args.all:
        slugs = sorted(p.name for p in (ROOT / "sites").iterdir() if (p / "src" / "lib" / "brand.ts").exists())
    if not slugs:
        ap.print_help(); return 1

    print(f"sync_brand_reviews: {', '.join(slugs)}")
    for slug in slugs:
        sync(slug, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
