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
AGENCY_EMAIL = "contact@restorationai.io"
COVER_PX = 3000          # Spotify/Apple: square, 1400-3000px, JPEG/PNG, RGB
FONT_CANDIDATES = [      # first hit wins; Pillow's bitmap default as last resort
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


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
        # ALWAYS the agency inbox (Santino 2026-09-09): directories send the
        # ownership-verification codes here, so every show connects without
        # a client round trip. Administrative only — never shown to listeners.
        "email": AGENCY_EMAIL,
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


# ----------------------------------------------------------------- cover art
# Spotify refused the first feed (2026-09-08) for having no cover art. The
# cover is rendered DETERMINISTICALLY (Pillow, no image model): directories
# show it at thumbnail size, so it must be flat, high-contrast and legible,
# which is exactly what generated scenes are not. Rule (Santino 2026-09-09):
#   * a light/white logo variant exists  -> logo on the brand colour
#   * only a regular (dark) logo exists   -> logo on a light panel, brand band
#   * no logo in the repo                 -> initials on the brand colour
# Every variant carries the "Restoration Talk" wordmark.

def _hex(c: str | None, default: str) -> tuple:
    c = (c or default).lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _font(size: int):
    from PIL import ImageFont
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def find_logo(slug: str) -> tuple[Path | None, bool]:
    """(path, is_light_variant). Largest raster logo wins; a 'white'/'light'
    variant is preferred because it sits on the brand colour."""
    from PIL import Image
    cands = []
    for p in (ROOT / "clients" / slug).rglob("*"):
        if p.suffix.lower() not in (".png", ".jpg", ".jpeg") or "logo" not in p.name.lower():
            continue
        if "podcast-cover" in p.name:
            continue
        try:
            w, h = Image.open(p).size
        except Exception:
            continue
        light = any(k in p.name.lower() for k in ("white", "light", "inverse", "reverse"))
        cands.append((light, w * h, p))
    if not cands:
        return None, False
    cands.sort(key=lambda t: (t[0], t[1]), reverse=True)
    light, _, p = cands[0]
    return p, light


def _key_background(lg, tol: int = 96, dead: int = 40):
    """Logo exports often arrive with the background baked in (narestco's
    'Logo White.png' is white-on-dark-grey, fully opaque). If the image has
    no transparency and all four corners agree on a colour, fade pixels near
    that colour to transparent so the logo floats on the cover's own ground."""
    from PIL import Image
    if lg.getchannel("A").getextrema()[0] < 255:
        return lg                              # real transparency present
    w, h = lg.size
    corners = [lg.getpixel(p)[:3] for p in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1))]
    ref = tuple(sum(c[i] for c in corners) // 4 for i in range(3))
    if any(max(abs(c[i] - ref[i]) for i in range(3)) > 20 for c in corners):
        return lg                              # corners disagree: not a flat bg
    px = lg.load()
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            d = max(abs(r - ref[0]), abs(g - ref[1]), abs(b - ref[2]))
            if d < tol:   # fully clear inside the dead zone, then a soft ramp
                px[x, y] = (r, g, b, 0 if d <= dead else int(255 * (d - dead) / (tol - dead)))
    return lg


def _initials(name: str) -> str:
    words = [w for w in re.split(r"[^A-Za-z0-9]+", name) if w]
    stop = {"the", "of", "and", "llc", "inc", "co", "corp", "ltd"}
    words = [w for w in words if w.lower() not in stop] or words
    return "".join(w[0] for w in words[:3]).upper() or name[:2].upper()


def render_cover(slug: str, logo: Path | None = None, out: Path | None = None) -> Path:
    from PIL import Image, ImageDraw
    b = brand(slug)
    name = b.get("display_name", slug)
    primary = _hex(b.get("primary_color"), "#1f2937")
    S = COVER_PX
    if logo is None:
        logo, light = find_logo(slug)
    else:
        light = any(k in logo.name.lower() for k in ("white", "light", "inverse", "reverse"))
    out = out or (ROOT / "clients" / slug / "podcast-cover.jpg")

    if logo is not None:
        lg = _key_background(Image.open(logo).convert("RGBA"))
        on_brand = light
        bg = primary if on_brand else _hex(b.get("primary_light"), "#f3f4f6")
        img = Image.new("RGB", (S, S), bg)
        d = ImageDraw.Draw(img)
        # logo box: 72% wide, 40% tall, centred a little above centre
        box_w, box_h = int(S * 0.72), int(S * 0.40)
        scale = min(box_w / lg.width, box_h / lg.height)
        lg = lg.resize((max(1, int(lg.width * scale)), max(1, int(lg.height * scale))),
                       Image.LANCZOS)
        img.paste(lg, ((S - lg.width) // 2, int(S * 0.42) - lg.height // 2), lg)
        if on_brand:
            word_fill, band = (255, 255, 255), None
        else:
            band = primary
            d.rectangle([0, int(S * 0.78), S, S], fill=band)
            word_fill = (255, 255, 255)
        f = _font(int(S * 0.062))
        txt = "RESTORATION TALK"
        tw = d.textlength(txt, font=f)
        d.text(((S - tw) / 2, int(S * 0.845)), txt, font=f, fill=word_fill)
    else:
        img = Image.new("RGB", (S, S), primary)
        d = ImageDraw.Draw(img)
        ini = _initials(name)
        f_big = _font(int(S * (0.42 if len(ini) <= 2 else 0.32)))
        tw = d.textlength(ini, font=f_big)
        d.text(((S - tw) / 2, int(S * 0.20)), ini, font=f_big, fill=(255, 255, 255))
        f_name = _font(int(S * 0.055))
        line = name.upper()
        while d.textlength(line, font=f_name) > S * 0.9 and len(line) > 8:
            line = line[:-4].rstrip() + "…"
        tw = d.textlength(line, font=f_name)
        d.text(((S - tw) / 2, int(S * 0.70)), line, font=f_name, fill=(255, 255, 255))
        f = _font(int(S * 0.048))
        txt = "RESTORATION TALK"
        tw = d.textlength(txt, font=f)
        d.text(((S - tw) / 2, int(S * 0.80)), txt, font=f, fill=_hex(b.get("primary_light"), "#e5e7eb"))
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "JPEG", quality=90, optimize=True)
    print(f"  cover rendered: {out} ({'logo ' + logo.name if logo else 'initials ' + _initials(name)})")
    return out


def ensure_cover(slug: str, m: dict, dry_run: bool = False, force: bool = False,
                 logo: Path | None = None) -> dict:
    """Render + upload the cover once; the manifest remembers the public URL."""
    local = ROOT / "clients" / slug / "podcast-cover.jpg"
    if force or not local.exists():
        render_cover(slug, logo=logo, out=local)
    if force or not m.get("image"):
        if not dry_run:
            r2_put(f"{slug}/cover.jpg", local.read_bytes(), "image/jpeg")
        m["image"] = f"{PUBLIC}/{slug}/cover.jpg"
        if not dry_run:
            save_manifest(slug, m)
    return m


def build_feed(slug: str, m: dict) -> str:
    def esc(t: str) -> str:
        return html.escape(t or "", quote=False)
    image = ""
    if m.get("image"):
        image = (f'  <itunes:image href="{esc(m["image"])}"/>\n'
                 f"  <image><url>{esc(m['image'])}</url><title>{esc(m['title'])}</title>"
                 f"<link>{esc(m['link'])}</link></image>\n")
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
  <managingEditor>{esc(m['email'])} ({esc(m['author'])})</managingEditor>
{image}{chr(10).join(items)}
 </channel>
</rss>
"""


def sync(slug: str, dry_run: bool = False) -> None:
    m = load_manifest(slug)
    m = ensure_cover(slug, m, dry_run=dry_run)   # Spotify rejects feeds without art
    xml = build_feed(slug, m)
    if dry_run:
        print(xml[:600])
        return
    r2_put(f"{slug}/feed.xml", xml.encode(), "application/rss+xml")
    print(f"  feed live: {PUBLIC}/{slug}/feed.xml ({len(m['episodes'])} episode(s))")


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("init", "episode", "sync", "auto", "cover"):
        sp = sub.add_parser(name)
        sp.add_argument("--slug", required=True)
        if name == "episode":
            sp.add_argument("--post", required=True)
        if name == "auto":
            sp.add_argument("--max", type=int, default=3)
        if name == "cover":
            sp.add_argument("--logo", help="raster logo to use (default: auto-pick from clients/<slug>/)")
        sp.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    ensure_bucket()
    if args.cmd == "cover":   # (re)render + upload the art, then republish
        m = ensure_cover(args.slug, load_manifest(args.slug), dry_run=args.dry_run,
                         force=True, logo=Path(args.logo) if args.logo else None)
        print(f"  image: {m['image']}")
        sync(args.slug, args.dry_run)
    elif args.cmd == "init":
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
