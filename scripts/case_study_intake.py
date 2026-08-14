#!/usr/bin/env python3
"""case_study_intake.py — client-supplied case studies -> live site pages.

WHY (2026-08-14): Crew Restoration generates real case studies from call
transcriptions (Zapier) and asked twice to (1) migrate their OLD site's case
studies and (2) keep publishing new ones they email us. We told every client
the same thing: email write-ups to contact@restorationai.io. Those emails
already land as [CLIENT EMAIL] marketing_ops_notes rows (email_inbox_sync.py)
with attachments in branding/{company_id}/docs/ — but nothing ever turned
them into pages. This module closes that loop, and adds an old-site recovery
lane through the Wayback Machine for clients whose previous site is gone.

Two lanes, one publisher:

  ingest   scan unprocessed [CLIENT EMAIL] notes (+ their doc attachments)
           for case-study submissions. An AI classification call decides
           "is this a real project/job case study?" and extracts
           title/city/service/narrative/outcome. Accepted submissions are
           rendered through the content engine's case-study conventions
           (same frontmatter as content_writer.write_markdown, same no-em-
           dash law, same claims_lint truth gate) and published to the
           client's blog collection. Processed note ids live in ops_kv so
           reruns are no-ops.

  recover  Wayback Machine recovery of a client's OLD site's case studies
           (Crew pilot: crew3r.com /job-completed-* and /all-projects/*).
           CDX API finds the archived URLs, we fetch snapshots, extract
           title/date/narrative/job photos (photos re-hosted to the client's
           R2 — never hotlinked from web.archive.org), and render each
           through the same pipeline. Cap 25. Original completion dates are
           preserved in published_at.

TRUTH RULES
-----------
- The client's own narrative is the ONLY source of job facts (the same iron
  rule as CASE STUDY MODE in templates/*/prompts/content-writer.md). The
  model may quote it, never extend it.
- claims_lint is MANDATORY here and blocking: a rendered page with any
  severity=error violation is deleted, not published (content_writer merely
  flags; third-party-supplied text gets the stricter gate).
- Customer names: first names only, never surnames, even when the source
  has them (the old Crew pages used full names in some URLs).
- No em dashes anywhere (LAW 08-05) — sanitize_content + write_markdown
  enforce deterministically.
- Fabrication tells (case_studies_sync.FABRICATION_TELLS) reject a
  submission outright: "this scenario is representative" is not a case study.

After a batch publishes: one commit ("case_study_intake: ...") + sync-deploy
to the branch the site lives on (main for cut-over sites), one
marketing_work_log line per study (feeds the monthly report), one
[FOR MONICA] note with the live links (finished text, no ask).

CLI
---
    python3 scripts/case_study_intake.py ingest --all            # dry-run
    python3 scripts/case_study_intake.py ingest --all --apply
    python3 scripts/case_study_intake.py ingest --slug crew-restoration-construction --apply
    python3 scripts/case_study_intake.py recover --slug crew-restoration-construction          # report what the archive holds
    python3 scripts/case_study_intake.py recover --slug crew-restoration-construction --apply

Nightly: `ingest --all --apply` runs inside .github/workflows/client-ops-sync.yml
(sibling step, advisory `|| true`), so any client can email a case study and
it self-publishes overnight.

Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, ANTHROPIC_API_KEY,
CLOUDFLARE_R2_API_TOKEN (photo re-hosting), GOOGLE_AI_API_KEY (hero fallback
only), GITHUB_PERSONAL_ACCESS_TOKEN (sync-deploy).
"""
from __future__ import annotations

import argparse
import html as html_lib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import requests

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import claims_lint                      # noqa: E402
import content_writer as cw             # noqa: E402 — the content engine's helpers
import image_utils                      # noqa: E402
from case_studies_sync import FABRICATION_TELLS   # noqa: E402
from client_concierge import _sb, kv_get, kv_set, load_env  # noqa: E402
from work_log import company_id_for_slug, work_log          # noqa: E402

REPO_ROOT = SCRIPT_DIR.parent
CLIENTS_DIR = REPO_ROOT / "clients"
SITES_DIR = REPO_ROOT / "sites"

PROCESSED_KEY = "case-study-intake-processed"      # note ids already looked at
PROCESSED_CAP = 4000
RECOVER_KEY = "case-study-recover-{slug}"          # old-site paths already published

CDX_API = "https://web.archive.org/cdx/search/cdx"
WAYBACK_PAGE = "https://web.archive.org/web/{ts}id_/{url}"
# Snapshot cache: a recover dry-run fetches every candidate page; --apply
# right after must not hit the archive a second time for the same bytes.
CACHE_DIR = Path(os.environ.get(
    "CASE_STUDY_INTAKE_CACHE",
    str(Path(tempfile.gettempdir()) / "case-study-intake-cache")))
ARCHIVE_FETCH_SLEEP_S = 1.2
RECOVER_CAP_DEFAULT = 25
MIN_NARRATIVE_CHARS = 120          # thinner than this is a stub, not a story
MAX_PHOTOS_PER_STUDY = 3

# Old-site brand assets are chrome, not job photos.
BRAND_ASSET_RE = re.compile(
    r"Crew_Logo|IICRC|AmericanRedCross|cropped-crew3r|Crew_Social|favicon",
    re.I)
THUMB_SUFFIX_RE = re.compile(r"-\d{2,4}x\d{2,4}\.(jpe?g|png|webp|gif)$", re.I)

TEXT_ATTACH_EXT = {".txt", ".md", ".csv", ".html", ".htm", ".docx", ".pdf"}
IMAGE_ATTACH_EXT = {".jpg", ".jpeg", ".png", ".webp"}
MAX_ATTACH_BYTES = 12 * 1024 * 1024


# ---------------------------------------------------------------------------
# AI prompts
# ---------------------------------------------------------------------------

CLASSIFIER_SYSTEM = """You are a strict intake classifier for a marketing
agency serving restoration contractors. You are given the text of an email a
client sent us (plus any attachment text). Decide whether it is a PROJECT /
JOB CASE STUDY submission: a written account of one real, completed job
(what happened at a property, what the company did, how it ended).

NOT case studies: invoices, review requests, scheduling, questions, general
feedback, photos alone with no written job account, marketing ideas, lists
of customers, legal/insurance paperwork.

Return ONLY one JSON object, no prose, no code fences:
{
  "is_case_study": true|false,
  "confidence": 0.0-1.0,
  "title": "short factual working title ('' if not a case study)",
  "city": "city the job happened in, '' if the text does not say",
  "service": "the service performed, in plain words, '' if unclear",
  "narrative": "the client's own account of the job, verbatim or lightly
                trimmed. NEVER add facts that are not in the source.",
  "outcome": "how the job ended, only if the text says, else ''",
  "performed_on": "YYYY-MM-DD or YYYY-MM if the text gives a date, else ''",
  "customer_first_name": "customer's FIRST name only if present, else ''",
  "reason": "one sentence explaining the verdict"
}
Multiple jobs in one email: pick the most complete single job. Extraction
uses ONLY what the text says. Empty string beats a guess, always."""

RENDERER_SYSTEM = """You write case-study blog pages for a restoration
contractor's website, following the content engine's CASE STUDY MODE rules,
adapted for a client-supplied write-up (not a Google review).

THE IRON RULE: every fact about this specific job comes ONLY from the
submission fields (title, city, service, narrative, outcome, performed_on,
customer_first_name). If the submission does not say it, it did not happen
on this page. No invented addresses, damage extent, costs, timelines,
dialogue, or emotions. Everything beyond the submission is GENERAL education
about how this kind of job works, clearly framed as general process
("on a typical loss like this...", "the standard drying process..."),
never as details of this customer's job.

Structure:
- Title / H1: factual, derived from the submission, e.g.
  "Case Study: Water Damage Restoration for Tammy in Sioux Falls, SD" or
  "Case Study: Basement Water Damage in Brandon, SD". First names only,
  never surnames. No superlatives, no drama.
- Open with 2-3 sentences setting up the situation type, then present the
  client's own account: quote the most story-carrying part of the narrative
  (verbatim, trimmed with "..." allowed, never reworded) as a blockquote
  attributed "from the {company short name} project notes". ONE permitted
  alteration inside a quote: if the narrative names a customer with a full
  name, shorten it to the first name only, everywhere.
- A short facts list where the submission provides them (Location,
  Service, Completed month/year). Omit any line the submission lacks.
- Then 2-3 sections unpacking the craft behind what the notes describe
  (e.g. notes mention a dehumidifier -> what moisture stabilization
  involves generally). This is the general-education layer.
- Close with a call to action using the company phone, and 2-4 FAQ pairs
  about this service type generally.
- 600-900 words. No competitor names. No em dashes anywhere (use commas,
  colons, or parentheses). No promises the brand context does not support:
  no certifications, license claims, response-time guarantees, or review
  counts unless they appear in the brand context provided.
- image_prompt: illustrative editorial restoration imagery for this service
  type. NEVER attempt to depict this customer's actual property and never
  stage fake "job photos" (real photos, when we have them, are attached by
  the pipeline, not by you).

Return ONLY one valid JSON object, no code fences, no prose:
{
  "title": "...",
  "meta_description": "under 160 chars, factual",
  "body_markdown": "...",
  "faq": [{"question": "...", "answer": "..."}],
  "image_prompt": "...",
  "internal_link_suggestions": ["/services/{service-slug}/", "/contact/"]
}
internal_link_suggestions may only use paths that exist in the client
context (services_selected -> /services/{slug}/, /contact/, /about/,
/service-areas/{area-slug}/)."""


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def site_branch(slug: str) -> str:
    """The branch this site actually serves from: main once cut over /
    pushed to main, staging before that."""
    rec = CLIENTS_DIR / f"{slug}.json"
    client = json.loads(rec.read_text()) if rec.exists() else {}
    if client.get("cut_over_at") or client.get("build_status") == "pushed_main":
        return "main"
    return "staging"


def blog_dir(slug: str) -> Path:
    return SITES_DIR / slug / "src" / "content" / "blog"


def eligible_slugs() -> list[str]:
    """Clients that can receive a case-study page: scaffolded blog dir and a
    known company_id."""
    out = []
    for d in sorted(SITES_DIR.iterdir()):
        if d.is_dir() and blog_dir(d.name).exists() and company_id_for_slug(d.name):
            out.append(d.name)
    return out


def fabrication_hit(text: str) -> str | None:
    for pat in FABRICATION_TELLS:
        if re.search(pat, text or "", re.I | re.M):
            return pat
    return None


def client_context(slug: str) -> dict:
    """Compact brand-truth context for the renderer (mirrors
    content_writer.build_prompt_inputs, minus the vertical prompt)."""
    client = cw.load_json(CLIENTS_DIR / f"{slug}.json")
    plan_input = cw.load_json(CLIENTS_DIR / slug / "plan-input.json")
    brand = plan_input.get("brand", {})
    areas = plan_input.get("service_areas", [])
    primary = next((a for a in areas if a.get("primary")), areas[0] if areas else {})
    existing = []
    for md in sorted(blog_dir(slug).glob("*.md")):
        for line in md.read_text().splitlines()[:12]:
            if line.startswith("title:"):
                existing.append({"path": f"/blog/{md.stem}/",
                                 "title": line.split(":", 1)[1].strip().strip('"')})
                break
    return {
        "slug": slug,
        "client": {"display_name": client.get("display_name"),
                   "domain": client.get("domain")},
        "brand": brand,
        "primary_area": primary,
        "service_areas": [{"slug": a.get("slug"), "city": a.get("city"),
                           "state": a.get("state")} for a in areas[:30]],
        "services_selected": plan_input.get("services", []),
        "existing_blog_posts": existing[:40],
        "current_month": datetime.now(timezone.utc).strftime("%B %Y"),
    }


def match_service_slug(service_text: str, services: list) -> str | None:
    """Map a plain-words service to one of the site's service slugs."""
    s = (service_text or "").lower()
    slugs = [str(x) for x in services]
    aliases = {
        "water": "water-damage-restoration", "flood": "water-damage-restoration",
        "fire": "fire-damage-restoration", "smoke": "fire-damage-restoration",
        "soot": "fire-damage-restoration",
        "mold": "mold-remediation", "environmental": "mold-remediation",
        "storm": "storm-damage-restoration", "hail": "storm-damage-restoration",
        "sewage": "sewage-cleanup", "sewer": "sewage-cleanup",
        "biohazard": "biohazard-cleanup", "trauma": "biohazard-cleanup",
        "roof": "roofing", "shingle": "roofing",
        "structure": "general-contracting", "structural": "general-contracting",
        "remodel": "general-contracting", "construction": "general-contracting",
        "content": "contents-restoration", "cleaning": "post-construction-cleaning",
    }
    for word, target in aliases.items():
        if word in s and target in slugs:
            return target
    for sl in slugs:
        if sl.replace("-", " ") in s:
            return sl
    return None


# ---------------------------------------------------------------------------
# Publisher — one submission -> one rendered, gated, deployed page
# ---------------------------------------------------------------------------

def render_study(slug: str, sub: dict) -> dict:
    """AI-render one submission into the content engine's JSON contract."""
    ctx = client_context(slug)
    user = (
        "# Case-study submission (the ONLY source of job facts)\n\n"
        f"```json\n{json.dumps(sub, indent=2, ensure_ascii=False)}\n```\n\n"
        "# Client context (brand truth; general education may draw on this)\n\n"
        f"```json\n{json.dumps(ctx, indent=2, ensure_ascii=False)}\n```\n\n"
        "# Task\n\nWrite the case-study page JSON per the contract. "
        "Return only the JSON object."
    )
    raw, usage = cw.anthropic_call(RENDERER_SYSTEM, user, max_tokens=6000,
                                   temperature=0.4)
    content = cw.parse_llm_json(raw)
    content = cw.sanitize_content(content)
    for k in ("title", "meta_description", "body_markdown"):
        if not (content.get(k) or "").strip():
            raise RuntimeError(f"renderer returned empty {k!r}")
    return content


def rehost_photos(slug: str, post_slug: str, photos: list[tuple[str, bytes]]) -> list[str]:
    """Re-host real job photos to the client's R2 (never hotlink the
    archive / storage). Returns public URLs, first one is the hero."""
    client = cw.load_json(CLIENTS_DIR / f"{slug}.json")
    bucket, domain = f"rankai-{slug}", client["domain"]
    prefix = f"blog/{datetime.now(timezone.utc).strftime('%Y/%m')}/{post_slug}"
    urls: list[str] = []
    for i, (name, data) in enumerate(photos[:MAX_PHOTOS_PER_STUDY]):
        try:
            webp = image_utils.png_to_webp_bytes(data, quality=88)
        except Exception as e:  # noqa: BLE001 — a broken image never kills the study
            print(f"      [warn] photo {name} unreadable: {str(e)[:80]}")
            continue
        key = f"{prefix}/{'hero' if not urls else f'photo-{i}'}.webp"
        if image_utils.upload_bytes_to_r2(bucket, key, webp):
            urls.append(f"https://images.{domain}/{key}")
        else:
            print(f"      [warn] R2 upload failed for {key}")
    return urls


def set_published_at(path: Path, date_str: str) -> None:
    """Preserve the job's original date in frontmatter (recovery lane)."""
    txt = path.read_text()
    txt = re.sub(r'(?m)^published_at: "\d{4}-\d{2}-\d{2}"$',
                 f'published_at: "{date_str}"', txt, count=1)
    path.write_text(txt)


def publish_study(slug: str, sub: dict, *, photos: list[tuple[str, bytes]],
                  preserved_date: str | None, allow_generated_hero: bool) -> dict:
    """Render + gate + write one study. Returns
    {status: published|held, path, url, title, flags} — raises only on
    infrastructure failure (caller decides batch fate)."""
    content = render_study(slug, sub)

    hit = fabrication_hit(f"{content['title']} {content['body_markdown']}")
    if hit:
        return {"status": "held", "title": content["title"],
                "why": f"reads like generated copy (matched /{hit}/)"}

    base = slugify(content["title"])[:80] or f"case-study-{slugify(sub.get('title',''))[:60]}"
    if not base.startswith("case-study"):
        base = f"case-study-{base}"
    post_slug, n = base, 2
    while (blog_dir(slug) / f"{post_slug}.md").exists():
        post_slug, n = f"{base}-{n}", n + 1

    # Hero: real job photos first (re-hosted), generated editorial imagery as
    # the fallback, brand placeholder as the floor (content_writer convention).
    photo_urls = rehost_photos(slug, post_slug, photos) if photos else []
    item = {
        "id": f"case-study-intake-{post_slug}",
        "content_type": "case_study",
        "primary_keyword": " ".join(x for x in [
            (sub.get("service") or "restoration"), "case study",
            (sub.get("city") or "")] if x).strip().lower(),
        "suggested_slug": post_slug,
        "intent": "commercial",
        "service_tags": [s for s in [match_service_slug(
            sub.get("service", ""),
            cw.load_json(CLIENTS_DIR / slug / "plan-input.json").get("services", []))] if s],
    }
    if photo_urls:
        hero_url = photo_urls[0]
        if len(photo_urls) > 1:
            gallery = "\n".join(f"![{content['title']} job photo]({u})"
                                for u in photo_urls[1:])
            content["body_markdown"] += f"\n\n## Photos from this job\n\n{gallery}\n"
    elif allow_generated_hero:
        try:
            hero_url = cw.generate_and_upload_hero(
                slug, item, content.get("image_prompt") or
                f"Editorial restoration photograph illustrating "
                f"{item['primary_keyword']}. No text or logos.")
        except Exception as e:  # noqa: BLE001
            print(f"      [warn] hero generation failed: {str(e)[:100]}")
            client = cw.load_json(CLIENTS_DIR / f"{slug}.json")
            hero_url = f"https://images.{client['domain']}/brand/hero.webp"
    else:
        client = cw.load_json(CLIENTS_DIR / f"{slug}.json")
        hero_url = f"https://images.{client['domain']}/brand/hero.webp"

    path = cw.write_markdown(slug, item, content, hero_url)
    if preserved_date:
        set_published_at(path, preserved_date)

    # MANDATORY claims gate — errors block publication (stricter than
    # content_writer's advisory flags: this lane publishes third-party text).
    truth = claims_lint.load_truth(slug)
    flags = claims_lint.lint_file(path, truth, rel_root=SITES_DIR / slug)
    errors = [f for f in flags if f.get("severity") == "error"]
    if errors:
        path.unlink(missing_ok=True)
        why = "; ".join(f"{f['family']}: {f['context'][:90]}" for f in errors[:3])
        return {"status": "held", "title": content["title"],
                "why": f"claims_lint error(s): {why}"}
    if flags:
        print(f"      claims lint: {len(flags)} review flag(s), no errors — publishing")

    domain = cw.load_json(CLIENTS_DIR / f"{slug}.json")["domain"]
    return {"status": "published", "path": path, "title": content["title"],
            "url": f"https://{domain}/blog/{post_slug}/",
            "flags": flags}


# ---------------------------------------------------------------------------
# Batch finishers — commit/deploy, work log, Monica note
# ---------------------------------------------------------------------------

def _run(cmd: list[str], cwd: Path) -> str:
    out = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed:\n{out.stderr.strip()}")
    return out.stdout.strip()


def commit_and_deploy(slug: str, paths: list[Path], branch: str, lane: str) -> None:
    rels = [str(p.relative_to(REPO_ROOT)) for p in paths]
    _run(["git", "add", *rels], REPO_ROOT)
    msg = (f"case_study_intake: publish {len(paths)} case study page(s) "
           f"for {slug} ({lane})\n\n"
           "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>")
    try:
        _run(["git", "commit", "-m", msg], REPO_ROOT)
    except RuntimeError as e:
        if "nothing to commit" not in str(e).lower():
            raise
    _run(["git", "pull", "--rebase", "--autostash", "origin", "main"], REPO_ROOT)
    try:
        _run(["git", "push", "origin", "main"], REPO_ROOT)
    except RuntimeError:
        # push rejected (concurrent CI push): rebase once more and retry
        _run(["git", "pull", "--rebase", "--autostash", "origin", "main"], REPO_ROOT)
        _run(["git", "push", "origin", "main"], REPO_ROOT)
    print(f"    sync-deploying sites/{slug}/ (branch={branch})...")
    _run(["python3", str(SCRIPT_DIR / "build_site.py"), "sync-deploy",
          "--slug", slug, "--branch", branch, "--allow-dirty"], REPO_ROOT)
    # Mirror to the app's Content view (non-fatal, same as content_writer).
    sub = subprocess.run(["python3", str(SCRIPT_DIR / "supabase_sync.py"),
                          "--slug", slug], cwd=str(REPO_ROOT),
                         capture_output=True, text=True)
    if sub.returncode != 0:
        print(f"    [warn] supabase_sync failed (non-fatal): {sub.stderr[-200:]}")


def finish_batch(slug: str, published: list[dict], branch: str, lane: str) -> None:
    """Verify, work-log, and tell Monica — after the deploy went out."""
    cid = company_id_for_slug(slug)
    client = cw.load_json(CLIENTS_DIR / f"{slug}.json")
    if branch == "main" and published:
        # One CF build covers all pages: poll the first URL, spot-check the rest.
        if cw.verify_published(published[0]["url"]):
            print(f"    live: {published[0]['url']}")
            for p in published[1:]:
                try:
                    r = requests.get(p["url"], timeout=20)
                    print(f"    live check {r.status_code}: {p['url']}")
                except Exception as e:  # noqa: BLE001
                    print(f"    [warn] live check failed: {p['url']} ({str(e)[:60]})")
        else:
            print(f"    [warn] {published[0]['url']} not live within the poll window "
                  f"(build may still be running)")
    for p in published:
        work_log(cid, "site", "case-study",
                 f"New case study published: {p['title']}",
                 evidence={"url": p["url"], "lane": lane},
                 source="case_study_intake")
    links = "\n".join(f"- {p['title']}: {p['url']}" for p in published)
    origin = ("recovered from their old website"
              if lane == "recover" else "from the write-ups they emailed us")
    note = (f"[FOR MONICA] Good news to pass along to {client.get('display_name', slug)}: "
            f"{len(published)} case stud{'y is' if len(published) == 1 else 'ies are'} "
            f"now live on {client.get('domain')}, {origin}. Links:\n{links}\n"
            f"Any new case study they email to contact@restorationai.io will "
            f"publish automatically going forward.")
    _sb("POST", "/rest/v1/marketing_ops_notes",
        body={"company_id": cid, "body": note}, prefer="return=minimal")
    print(f"    [FOR MONICA] note filed ({len(published)} link(s))")


# ---------------------------------------------------------------------------
# Lane 1: ingest — [CLIENT EMAIL] notes -> pages
# ---------------------------------------------------------------------------

NOTE_RE = re.compile(
    r"^\[CLIENT EMAIL\]\s+(?P<sender>\S+)\s+emailed\s+(?P<subject>.+?)\s+on\s+"
    r"(?P<when>\d{4}-\d{2}-\d{2}|unknown date):\s+(?P<snippet>.*?)"
    r"\s*Attachments:\s+(?P<atts>.+?)\.?$", re.S)


def parse_client_email_note(body: str) -> dict | None:
    m = NOTE_RE.match(body or "")
    if not m:
        return None
    atts_raw = m.group("atts").strip()
    files: list[str] = []
    if atts_raw.lower() != "none" and not atts_raw.startswith("present but"):
        atts_raw = re.sub(r"\s*\(saved to their account documents\)\s*$", "", atts_raw)
        files = [f.strip() for f in atts_raw.split(",") if f.strip()]
    return {"sender": m.group("sender"), "subject": m.group("subject").strip("'\""),
            "when": m.group("when"), "snippet": m.group("snippet").strip(),
            "files": files}


def _download_doc(cid: str, filename: str) -> bytes | None:
    import os
    base = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    path = urllib.parse.quote(f"{cid}/docs/{filename}")
    r = requests.get(f"{base}/storage/v1/object/branding/{path}",
                     headers={"Authorization": f"Bearer {key}"}, timeout=120)
    if r.status_code != 200 or len(r.content) > MAX_ATTACH_BYTES:
        return None
    return r.content


def _attachment_text(name: str, data: bytes) -> str:
    ext = Path(name).suffix.lower()
    try:
        if ext in {".txt", ".md", ".csv"}:
            return data.decode("utf-8", errors="replace")
        if ext in {".html", ".htm"}:
            return re.sub(r"(?s)<[^>]+>", " ", data.decode("utf-8", errors="replace"))
        if ext == ".docx":
            import io
            import zipfile
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                xml = z.read("word/document.xml").decode("utf-8", errors="replace")
            xml = xml.replace("</w:p>", "\n")
            return re.sub(r"<[^>]+>", "", xml)
        if ext == ".pdf":
            try:
                import io
                from pypdf import PdfReader
                return "\n".join((pg.extract_text() or "")
                                 for pg in PdfReader(io.BytesIO(data)).pages[:10])
            except ImportError:
                return f"(pdf attachment {name}: text not extracted)"
    except Exception as e:  # noqa: BLE001
        return f"(attachment {name} unreadable: {str(e)[:60]})"
    return ""


def classify_submission(material: str) -> dict:
    raw, _ = cw.anthropic_call(CLASSIFIER_SYSTEM, material[:24000],
                               max_tokens=1500, temperature=0.0)
    return cw.parse_llm_json(raw)


def cmd_ingest(args) -> int:
    load_env()
    slugs = [args.slug] if args.slug else eligible_slugs()
    processed: list[str] = list(kv_get(PROCESSED_KEY) or [])
    processed_set = set(processed)
    apply = args.apply
    print(f"==> case-study ingest ({len(slugs)} client(s))"
          f"{'' if apply else '  [DRY RUN — classify only, publish nothing]'}")

    total_pub = 0
    for slug in slugs:
        cid = company_id_for_slug(slug)
        if not cid or not blog_dir(slug).exists():
            continue
        pat = urllib.parse.quote("[CLIENT EMAIL]*", safe="*")
        notes = _sb("GET", f"/rest/v1/marketing_ops_notes?company_id=eq.{cid}"
                    f"&body=like.{pat}&select=id,body,created_at"
                    "&order=created_at.asc&limit=200") or []
        fresh = [n for n in notes if str(n.get("id")) not in processed_set]
        if not fresh:
            continue
        print(f"\n  {slug}: {len(fresh)} unprocessed client email(s)")
        published: list[dict] = []
        batch_done: list[str] = []
        for n in fresh:
            nid = str(n.get("id"))
            meta = parse_client_email_note(n.get("body", ""))
            if not meta:
                batch_done.append(nid)
                continue
            texts, photos = [], []
            for fname in meta["files"]:
                data = _download_doc(cid, fname)
                if data is None:
                    print(f"    ! could not fetch attachment {fname}")
                    continue
                ext = Path(fname).suffix.lower()
                if ext in TEXT_ATTACH_EXT:
                    t = _attachment_text(fname, data)
                    if t.strip():
                        texts.append(f"--- attachment {fname} ---\n{t[:8000]}")
                elif ext in IMAGE_ATTACH_EXT:
                    photos.append((fname, data))
            material = (f"Email from {meta['sender']} on {meta['when']}, "
                        f"subject: {meta['subject']}\n\n{meta['snippet']}\n\n"
                        + "\n\n".join(texts))
            try:
                verdict = classify_submission(material)
            except Exception as e:  # noqa: BLE001 — classify failure: leave note
                print(f"    ! classify failed for note {nid}: {str(e)[:100]} "
                      "(will retry next run)")
                continue
            is_cs = bool(verdict.get("is_case_study"))
            conf = float(verdict.get("confidence") or 0)
            narrative = (verdict.get("narrative") or "").strip()
            label = (f"note {nid} ({meta['subject'][:50]!r}): "
                     f"{'CASE STUDY' if is_cs else 'not a case study'} "
                     f"conf={conf:.2f} — {verdict.get('reason', '')[:100]}")
            print(f"    {label}")
            if not (is_cs and conf >= 0.7):
                batch_done.append(nid)
                continue
            if len(narrative) < MIN_NARRATIVE_CHARS:
                print(f"      narrative too thin ({len(narrative)} chars) — skipped")
                batch_done.append(nid)
                continue
            hit = fabrication_hit(narrative)
            if hit:
                print(f"      rejected: fabrication tell /{hit}/")
                batch_done.append(nid)
                continue
            sub = {k: verdict.get(k, "") for k in
                   ("title", "city", "service", "narrative", "outcome",
                    "performed_on", "customer_first_name")}
            sub["source"] = f"client email {meta['when']} from {meta['sender']}"
            if not apply:
                print(f"      would publish: {sub['title']!r} "
                      f"({len(photos)} photo(s))")
                continue
            try:
                res = publish_study(slug, sub, photos=photos,
                                    preserved_date=(sub.get("performed_on") or None)
                                    if re.fullmatch(r"\d{4}-\d{2}-\d{2}",
                                                    sub.get("performed_on") or "")
                                    else None,
                                    allow_generated_hero=True)
            except Exception as e:  # noqa: BLE001
                print(f"      ! publish failed: {str(e)[:140]} (will retry next run)")
                continue
            if res["status"] == "published":
                print(f"      published -> {res['url']}")
                published.append(res)
            else:
                print(f"      HELD: {res['why'][:160]}")
            batch_done.append(nid)

        if apply and published:
            commit_and_deploy(slug, [p["path"] for p in published],
                              site_branch(slug), "ingest")
            finish_batch(slug, published, site_branch(slug), "ingest")
            total_pub += len(published)
        if apply and batch_done:
            processed = (processed + batch_done)[-PROCESSED_CAP:]
            processed_set = set(processed)
            kv_set(PROCESSED_KEY, processed)
    print(f"\n==> ingest done: {total_pub} page(s) published")
    return 0


# ---------------------------------------------------------------------------
# Lane 2: recover — Wayback Machine -> pages
# ---------------------------------------------------------------------------

CASE_PATH_RE = re.compile(r"(?:^|/)(?:job-completed-.+|all-projects/.+|"
                          r"projects?/.+|case-stud(?:y|ies)-.+)$", re.I)
HUB_LAST_SEG_RE = re.compile(r"^(?:all-projects|job-completed|projects?|"
                             r".*jobs-completed.*)$", re.I)


def cdx_case_candidates(domain: str) -> list[dict]:
    """Archived, HTML, 200-status case-study-looking URLs, deduped by last
    path segment (same story often lives at /X and /all-projects/X)."""
    r = requests.get(CDX_API, params={
        "url": f"{domain}*", "output": "json", "collapse": "urlkey",
        "fl": "timestamp,original,statuscode,mimetype",
        "filter": "statuscode:200", "limit": "8000"}, timeout=120)
    r.raise_for_status()
    rows = r.json()[1:]
    best: dict[str, dict] = {}
    for ts, orig, _st, mt in rows:
        if "html" not in (mt or ""):
            continue
        u = urllib.parse.urlparse(orig)
        if u.query:
            continue
        path = u.path.rstrip("/") or "/"
        if not CASE_PATH_RE.search(path):
            continue
        last = path.split("/")[-1]
        if HUB_LAST_SEG_RE.match(last):
            continue
        cur = best.get(last)
        if not cur or ts > cur["ts"]:
            best[last] = {"ts": ts, "url": orig, "path": path, "seg": last}
    return sorted(best.values(), key=lambda c: c["seg"])


def fetch_archived_page(cand: dict) -> str | None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = CACHE_DIR / f"{cand['ts']}-{re.sub(r'[^a-z0-9-]', '_', cand['seg'])[:120]}.html"
    if cache.exists():
        return cache.read_text(errors="replace")
    url = WAYBACK_PAGE.format(ts=cand["ts"], url=cand["url"])
    for attempt in (1, 2):
        try:
            r = requests.get(url, timeout=90,
                             headers={"User-Agent": "rank-ai-recovery/1.0"})
            if r.status_code == 200 and len(r.text) > 2000:
                cache.write_text(r.text)
                return r.text
            if r.status_code in (429, 503):
                time.sleep(8 * attempt)
                continue
            return None
        except requests.RequestException:
            time.sleep(5 * attempt)
    return None


def extract_case_study(html: str, cand: dict) -> dict | None:
    """Old Crew WordPress/Elementor job page -> submission dict. Returns None
    when the page has no real narrative (stub)."""
    m = re.search(r'<meta property="og:title" content="([^"]+)"', html)
    title = html_lib.unescape(m.group(1)) if m else ""
    title = re.split(r"\s*\|\s*", title)[0].strip()
    if not title:
        m = re.search(r"<title>(.*?)</title>", html, re.S)
        title = re.split(r"\s*\|\s*", html_lib.unescape(m.group(1)))[0].strip() if m else cand["seg"]

    txt = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
    txt = html_lib.unescape(re.sub(r"(?s)<[^>]+>", "\n", txt))
    flat = re.sub(r"\s+", " ", txt)

    date_iso = None
    dm = re.search(r"Completion date:\s*([A-Z][a-z]+)\s+(\d{1,2})\s*,\s*(\d{4})", flat)
    if dm:
        try:
            date_iso = datetime.strptime(
                f"{dm.group(1)} {dm.group(2)} {dm.group(3)}",
                "%B %d %Y").strftime("%Y-%m-%d")
        except ValueError:
            pass
    if not date_iso:
        date_iso = f"{cand['ts'][:4]}-{cand['ts'][4:6]}-{cand['ts'][6:8]}"

    loc = ""
    lm = re.search(r"Location:\s*([A-Za-z .'-]+?)\s*(?:,\s*(?:USA|SD|IA|MN|NE)\b)*"
                   r"\s*(?:Solutions|Photos|$)", flat)
    if lm:
        loc = lm.group(1).strip().rstrip(",")

    # Format A ("Job Completed for ..." pages): one "Solutions Provided:"
    # narrative block, real completion date, Elementor photo gallery.
    narrative = ""
    nm = re.search(r"Solutions Provided:\s*(.*?)(?:Photos & Videos|Photos and Videos|"
                   r"Trustindex|EXCELLENT|Google rating|$)", flat, re.S)
    if nm:
        narrative = nm.group(1).strip()

    first = ""
    fm = re.search(r"Job Completed for ([A-Z][a-z]+)", title)
    if fm:
        first = fm.group(1)

    service = ""
    seg = cand["seg"].lower()
    for key, pretty in (("water", "water damage restoration"),
                        ("fire-and-env", "fire and environmental damage restoration"),
                        ("fire", "fire damage restoration"),
                        ("environment", "environmental damage cleanup"),
                        ("sewage", "sewage cleanup"),
                        ("structur", "structural repair"),
                        ("mold", "mold remediation"),
                        ("cleaning", "cleaning")):
        if key in seg:
            service = pretty
            break

    # Format B ("Case Study: {Service} - {City}" pages, the Zapier
    # call-transcription output): four labeled sections, generic og:title,
    # no completion date on the page.
    if len(narrative) < MIN_NARRATIVE_CHARS:
        bm = re.search(
            r"Customer Problem\s+(?P<problem>.*?)\s+How Crew Responded\s+"
            r"(?P<response>.*?)\s+Solution Provided\s+(?P<solution>.*?)\s+"
            r"Result\s+(?P<result>.*?)(?:\s+Contact me for a|\s+FREE estimate"
            r"|\s+Trustindex|\s+EXCELLENT|$)", flat, re.S)
        if bm:
            narrative = (
                f"Customer problem: {bm.group('problem').strip()}\n\n"
                f"How the crew responded: {bm.group('response').strip()}\n\n"
                f"Solution provided: {bm.group('solution').strip()}\n\n"
                f"Result: {bm.group('result').strip()}")
            hm = re.search(r"Case Study:\s*([A-Za-z /&]+?)\s*[–—-]\s*"
                           r"([A-Z][A-Za-z .'-]+?)\s+Customer Problem", flat)
            if hm:
                service = service or hm.group(1).strip().lower()
                loc = loc or hm.group(2).strip()
                title = f"Case Study: {hm.group(1).strip()} in {loc}"
            nf = re.match(r"\s*([A-Z][a-z]+)\s+[A-Z]", bm.group("problem"))
            if nf:
                first = first or nf.group(1)
    if len(narrative) < MIN_NARRATIVE_CHARS:
        return None

    # Job photos: STRICT allowlist on the observed upload naming for job
    # galleries (picture-{id}.jpg). Anything looser drags in site chrome
    # (sidebarPhoto.jpg, "Untitled design" template graphics) and a wrong
    # photo on a client's case study is worse than the brand-hero fallback.
    photos = []
    for u in set(re.findall(
            r"https?://[^\"'\s\\)]+/wp-content/uploads/[^\"'\s\\)]+?"
            r"/picture-\d+\.(?:jpe?g|png|webp)", html, re.I)):
        if BRAND_ASSET_RE.search(u) or THUMB_SUFFIX_RE.search(u):
            continue
        photos.append(u)

    return {"title": title, "city": loc, "service": service,
            "narrative": narrative, "outcome": "",
            "performed_on": date_iso, "customer_first_name": first,
            "source": f"old site {cand['path']} (Wayback {cand['ts'][:8]})",
            "_photos_urls": sorted(photos), "_cand": cand}


def fetch_archive_photo(ts: str, img_url: str) -> bytes | None:
    url = f"https://web.archive.org/web/{ts}im_/{img_url}"
    try:
        r = requests.get(url, timeout=90,
                         headers={"User-Agent": "rank-ai-recovery/1.0"})
        if r.status_code == 200 and len(r.content) > 5000:
            return r.content
    except requests.RequestException:
        pass
    return None


def cmd_recover(args) -> int:
    load_env()
    slug = args.slug
    client = cw.load_json(CLIENTS_DIR / f"{slug}.json")
    domain = client["domain"]
    apply = args.apply
    kv_key = RECOVER_KEY.format(slug=slug)
    done: list[str] = list(kv_get(kv_key) or []) if apply else list(kv_get(kv_key) or [])

    print(f"==> old-site case-study recovery for {slug} ({domain})"
          f"{'' if apply else '  [DRY RUN — report only]'}")

    # Inventory cross-check (the cutover harvest ran post-cutover, so its
    # sitemap rows are the NEW site; case-study URLs surface via backlinks/gsc
    # if at all — the CDX index is the real source).
    inv_path = CLIENTS_DIR / slug / "cutover" / "url-inventory.json"
    inv_hits = []
    if inv_path.exists():
        inv = json.loads(inv_path.read_text())
        inv_hits = [u["path"] for u in inv.get("urls", [])
                    if CASE_PATH_RE.search(u.get("path", ""))]
    print(f"    url-inventory: {len(inv_hits)} case-study-looking path(s) "
          f"(inventory was harvested post-cutover; CDX is authoritative)")

    try:
        cands = cdx_case_candidates(domain)
    except Exception as e:  # noqa: BLE001
        print(f"    ! Wayback CDX query failed: {str(e)[:140]}")
        print("    Nothing recoverable without the archive index. Stopping.")
        return 1
    print(f"    CDX: {len(cands)} distinct archived case-study URL(s)")
    if not cands:
        print("    The Wayback Machine holds no case-study/project pages for "
              "this domain. Nothing to recover.")
        return 0

    fresh = [c for c in cands if c["path"] not in done]
    print(f"    {len(fresh)} not yet recovered "
          f"({len(cands) - len(fresh)} already published)")

    extracted, thin = [], 0
    for c in fresh:
        html = fetch_archived_page(c)
        time.sleep(ARCHIVE_FETCH_SLEEP_S)
        if not html:
            print(f"    ! no usable snapshot: {c['path']}")
            continue
        sub = extract_case_study(html, c)
        if not sub:
            thin += 1
            continue
        extracted.append(sub)
    print(f"    extracted {len(extracted)} real case stud(ies), "
          f"{thin} stub(s) skipped")

    # Named customer stories first (the substantial ones), then by length.
    extracted.sort(key=lambda s: (0 if s["customer_first_name"] else 1,
                                  -len(s["narrative"])))
    cap = args.cap
    take = extracted[:cap]

    print(f"\n    {'#':>3}  {'date':10}  {'ph':>2}  {'chars':>5}  title")
    for i, s in enumerate(take, 1):
        print(f"    {i:>3}  {s['performed_on']:10}  {len(s['_photos_urls']):>2}  "
              f"{len(s['narrative']):>5}  {s['title'][:70]}")
    if len(extracted) > cap:
        print(f"    (+{len(extracted) - cap} more beyond the cap of {cap})")

    if not apply:
        print("\n    Dry run complete. Re-run with --apply to publish the above.")
        return 0

    branch = site_branch(slug)
    published: list[dict] = []
    for s in take:
        cand = s.pop("_cand")
        photo_urls = s.pop("_photos_urls")
        photos: list[tuple[str, bytes]] = []
        for u in photo_urls[:MAX_PHOTOS_PER_STUDY]:
            data = fetch_archive_photo(cand["ts"], u)
            time.sleep(0.5)
            if data:
                photos.append((u.rsplit("/", 1)[-1], data))
        print(f"\n    rendering: {s['title'][:70]} ({len(photos)} photo(s) re-hosted)")
        try:
            res = publish_study(slug, s, photos=photos,
                                preserved_date=s["performed_on"],
                                allow_generated_hero=False)
        except Exception as e:  # noqa: BLE001
            print(f"      ! publish failed: {str(e)[:140]}")
            continue
        if res["status"] == "published":
            print(f"      -> {res['url']}")
            published.append(res)
            done.append(cand["path"])
            kv_set(kv_key, done)
        else:
            print(f"      HELD: {res['why'][:160]}")
            done.append(cand["path"])   # held = looked at; do not re-render nightly
            kv_set(kv_key, done)

    if published:
        commit_and_deploy(slug, [p["path"] for p in published], branch, "recover")
        finish_batch(slug, published, branch, "recover")
    print(f"\n==> recovery done: {len(published)} page(s) published")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(
        prog="case_study_intake",
        description="Client-supplied case studies -> live site pages "
                    "(email ingest + old-site Wayback recovery).")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("ingest", help="scan [CLIENT EMAIL] notes for case-study "
                                       "submissions and publish them")
    g = pi.add_mutually_exclusive_group(required=True)
    g.add_argument("--slug")
    g.add_argument("--all", action="store_true")
    pi.add_argument("--apply", action="store_true",
                    help="publish + deploy (default: classify and report only)")
    pi.set_defaults(func=cmd_ingest)

    pr = sub.add_parser("recover", help="recover a client's OLD site's case "
                                        "studies via the Wayback Machine")
    pr.add_argument("--slug", required=True)
    pr.add_argument("--apply", action="store_true",
                    help="publish + deploy (default: report what the archive holds)")
    pr.add_argument("--cap", type=int, default=RECOVER_CAP_DEFAULT)
    pr.set_defaults(func=cmd_recover)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
