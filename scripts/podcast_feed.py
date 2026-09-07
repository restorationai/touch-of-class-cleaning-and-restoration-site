#!/usr/bin/env python3
"""podcast_feed.py — per-client podcast feeds: episodes from blog posts,
hosted RSS that Spotify/Apple ingest automatically.

The Spotify system (roadmap "System 5 audio -> RSS -> Spotify/Apple";
Santino go 2026-09-06). Architecture: the browser is only needed ONCE per
client (create the show, point it at our RSS URL). After that, publishing
an episode = adding an item to the feed — pure cloud, no browser ever again.
Each episode description links the source article + the client's site
(the dofollow-from-Spotify motion, done with real content, not TTS spam).

Storage: R2 bucket `rankai-podcasts`, served at
https://podcasts.restorationai.io/{slug}/feed.xml and .../{slug}/{ep}.mp3.
Narration reuses video_maker's script + TTS stack (ElevenLabs, Google
fallback). Episode manifest: clients/{slug}/podcast.json.

Usage:
  python3 scripts/podcast_feed.py init --slug X          # bucket paths + empty feed
  python3 scripts/podcast_feed.py episode --slug X --post <blog-post-slug>
  python3 scripts/podcast_feed.py sync --slug X          # rebuild + upload feed.xml
  python3 scripts/podcast_feed.py auto --slug X [--max 3] # episodes for newest posts
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import sys
from email.utils import format_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")
import requests  # noqa: E402

BUCKET = "rankai-podcasts"
PUBLIC = "https://podcasts.restorationai.io"
CF_API = "https://api.cloudflare.com/client/v4"


def _cf_headers() -> dict:
    return {"Authorization": "Bearer " + (
        os.environ.get("CLOUDFLARE_R2_API_TOKEN")
        or os.environ["CLOUDFLARE_API_TOKEN"])}


def r2_put(key: str, data: bytes, ctype: str) -> None:
    acc = os.environ["CLOUDFLARE_ACCOUNT_ID"]
    r = requests.put(f"{CF_API}/accounts/{acc}/r2/buckets/{BUCKET}/objects/{key}",
                     data=data, headers={**_cf_headers(), "Content-Type": ctype},
                     timeout=120)
    r.raise_for_status()


def ensure_bucket() -> None:
    acc = os.environ["CLOUDFLARE_ACCOUNT_ID"]
    requests.post(f"{CF_API}/accounts/{acc}/r2/buckets", json={"name": BUCKET},
                  headers=_cf_headers(), timeout=30)  # 409 if exists — fine
    # custom domain podcasts.restorationai.io (zone restorationai.io is ours)
    z = requests.get(f"{CF_API}/zones?name=restorationai.io",
                     headers=_cf_headers(), timeout=30).json().get("result") or []
    if z:
        requests.post(f"{CF_API}/accounts/{acc}/r2/buckets/{BUCKET}/domains/custom",
                      json={"domain": "podcasts.restorationai.io",
                            "zoneId": z[0]["id"], "enabled": True},
                      headers=_cf_headers(), timeout=30)  # 409 if attached


def brand(slug: str) -> dict:
    pi = json.loads((ROOT / "clients" / slug / "plan-input.json").read_text())
    return pi.get("brand", {})


def manifest_path(slug: str) -> Path:
    return ROOT / "clients" / slug / "podcast.json"


def load_manifest(slug: str) -> dict:
    p = manifest_path(slug)
    if p.exists():
        return json.loads(p.read_text())
    b = brand(slug)
    name = b.get("display_name", slug)
    city = b.get("primary_city", "")
    return {
        "title": f"{name} | Restoration Talk",
        "description": (f"Straight answers about water, fire, mold and storm "
                        f"damage from the {name} team"
                        + (f" in {city}" if city else "")
                        + ". Real jobs, real costs, and what to do when it "
                        "happens to you."),
        "link": f"https://{json.loads((ROOT / 'clients' / (slug + '.json')).read_text()).get('domain', '')}",
        "language": "en-us",
        "author": name,
        "email": b.get("email", "contact@restorationai.io"),
        "episodes": [],
    }


def save_manifest(slug: str, m: dict) -> None:
    manifest_path(slug).write_text(json.dumps(m, indent=2) + "\n")


def _strip_md(t: str) -> str:
    t = re.sub(r"^---.*?---", "", t, flags=re.S)          # frontmatter
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", t)             # images
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)        # links -> text
    t = re.sub(r"[#*_`>|-]{1,}", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def episode_from_post(slug: str, post_slug: str, dry_run: bool = False) -> dict:
    import video_maker as vm
    m = load_manifest(slug)
    if any(e["slug"] == post_slug for e in m["episodes"]):
        print(f"  episode for {post_slug} already exists — skipping")
        return m
    blog = ROOT / "sites" / slug / "src" / "content" / "blog" / f"{post_slug}.md"
    cs = ROOT / "sites" / slug / "src" / "content" / "caseStudies" / f"{post_slug}.md"
    src = blog if blog.exists() else cs
    if not src.exists():
        sys.exit(f"no post at {blog}")
    raw = src.read_text()
    title_m = re.search(r'^title:\s*"?([^"\n]+)"?', raw, re.M)
    title = title_m.group(1).strip() if title_m else post_slug
    body = _strip_md(raw)[:6500]  # ~4-5 min narration

    # conversational rewrite via the video script brain would be ideal; v1
    # narrates a tightened article read with an intro/outro wrapper.
    b = brand(slug)
    name = b.get("display_name", slug)
    narration = (f"Welcome to Restoration Talk from {name}. Today: {title}. "
                 + body +
                 f" That's it for this episode. Find more guides, and reach "
                 f"{name} any time, at our website. Thanks for listening.")

    work = ROOT / "clients" / slug / "podcast-work"
    work.mkdir(exist_ok=True)
    mp3 = work / f"{post_slug}.mp3"
    if not dry_run:
        vm.synthesise_speech(narration, mp3)
        key = f"{slug}/{post_slug}.mp3"
        r2_put(key, mp3.read_bytes(), "audio/mpeg")
        size = mp3.stat().st_size
    else:
        size = 0
    domain = json.loads((ROOT / "clients" / f"{slug}.json").read_text()).get("domain", "")
    section = "case-studies" if src == cs else "blog"
    m["episodes"].insert(0, {
        "slug": post_slug,
        "title": title,
        "url": f"{PUBLIC}/{slug}/{post_slug}.mp3",
        "bytes": size,
        "published_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "description": (f"{title} — the full guide, read for you by the {name} "
                        f"team. Read it here: https://{domain}/{section}/{post_slug}/ "
                        f"or visit https://{domain}/ for help right now."),
    })
    if not dry_run:
        save_manifest(slug, m)
    print(f"  episode published: {title}")
    return m


def build_feed(slug: str, m: dict) -> str:
    def esc(t: str) -> str:
        return html.escape(t or "", quote=False)
    items = []
    for e in m["episodes"]:
        pub = format_datetime(dt.datetime.fromisoformat(e["published_at"]))
        items.append(f"""  <item>
   <title>{esc(e['title'])}</title>
   <description>{esc(e['description'])}</description>
   <enclosure url="{e['url']}" length="{e.get('bytes', 0)}" type="audio/mpeg"/>
   <guid isPermaLink="false">{slug}-{e['slug']}</guid>
   <pubDate>{pub}</pubDate>
  </item>""")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
 <channel>
  <title>{esc(m['title'])}</title>
  <description>{esc(m['description'])}</description>
  <link>{esc(m['link'])}</link>
  <language>{m['language']}</language>
  <itunes:author>{esc(m['author'])}</itunes:author>
  <itunes:explicit>false</itunes:explicit>
  <itunes:category text="Education"/>
  <itunes:owner><itunes:name>{esc(m['author'])}</itunes:name><itunes:email>{esc(m['email'])}</itunes:email></itunes:owner>
{chr(10).join(items)}
 </channel>
</rss>
"""


def sync(slug: str, dry_run: bool = False) -> None:
    m = load_manifest(slug)
    xml = build_feed(slug, m)
    if dry_run:
        print(xml[:600])
        return
    r2_put(f"{slug}/feed.xml", xml.encode(), "application/rss+xml")
    print(f"  feed live: {PUBLIC}/{slug}/feed.xml ({len(m['episodes'])} episode(s))")


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("init", "episode", "sync", "auto"):
        sp = sub.add_parser(name)
        sp.add_argument("--slug", required=True)
        if name == "episode":
            sp.add_argument("--post", required=True)
        if name == "auto":
            sp.add_argument("--max", type=int, default=3)
        sp.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    ensure_bucket()
    if args.cmd == "init":
        save_manifest(args.slug, load_manifest(args.slug))
        sync(args.slug, args.dry_run)
    elif args.cmd == "episode":
        episode_from_post(args.slug, args.post, args.dry_run)
        sync(args.slug, args.dry_run)
    elif args.cmd == "auto":
        blog = ROOT / "sites" / args.slug / "src" / "content" / "blog"
        posts = sorted(blog.glob("*.md"),
                       key=lambda p: p.stat().st_mtime, reverse=True)[:args.max]
        for p in posts:
            episode_from_post(args.slug, p.stem, args.dry_run)
        sync(args.slug, args.dry_run)
    elif args.cmd == "sync":
        sync(args.slug, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
