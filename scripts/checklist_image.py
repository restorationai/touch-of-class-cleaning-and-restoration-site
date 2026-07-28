#!/usr/bin/env python3
"""Checklist card image — the escalation artifact (Santino 2026-07-28: for
unresponsive clients "send them a screenshot with a checklist of all the
things they need to take care of ... We really want to get you going").

Renders a branded portrait card: green checks for what's done, open circles
for what's stuck, and the hop-on-a-call CTA. Uploaded to the public R2
bucket; the concierge attaches the URL when the escalation ladder fires.

Usage: checklist_image.py --company CO-... [--out path.png]  -> prints URL
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from client_ops_sync import _sb  # noqa: E402
from lead_audit import BUCKET, PUBLIC_BASE, r2_put  # noqa: E402

_FB = str(ROOT / "assets" / "fonts" / "Poppins-Bold.ttf")
_FM = str(ROOT / "assets" / "fonts" / "Poppins-Medium.ttf")


def _font(size: int, bold: bool = False):
    try:
        return ImageFont.truetype(_FB if bold else _FM, size)
    except OSError:
        return ImageFont.load_default()

INK = (15, 23, 42)
MUTED = (100, 116, 139)
GREEN = (5, 150, 105)
AMBER = (217, 119, 6)
BLUE = (14, 88, 116)
BG = (241, 245, 249)
CARD = (255, 255, 255)


def gather(cid: str) -> tuple[str, list[tuple[str, bool]]]:
    co = (_sb("GET", f"/rest/v1/companies?id=eq.{cid}&select=name")
          or [{}])[0]
    name = (co.get("name") or cid).strip()
    items: list[tuple[str, bool]] = []
    ledger = _sb("GET", "/rest/v1/marketing_setup_ledger"
                 f"?company_id=eq.{cid}&kind=eq.client_owed"
                 "&item_key=neq.client-asks&select=title,status,item_key") or []
    for r in ledger:
        if r.get("status") == "na":
            continue
        items.append((r["title"], r.get("status") == "done"))
    asks = _sb("GET", "/rest/v1/marketing_action_plan"
               f"?company_id=eq.{cid}&action_type=eq.client_input"
               "&status=in.(planned,resolved,done)&select=title,status"
               "&order=status.desc&limit=10") or []
    for a in asks:
        t = (a.get("title") or "").replace("ASK CLIENT: ", "").replace("ASK ", "")
        # client-voice cleanup: these titles are written for Monica, not the
        # client — flip third-person phrasing and drop internal tails
        t = t.split(" + ")[0]
        t = re.sub(r"^do they want\b", "Do you want", t, flags=re.I)
        t = re.sub(r"^Send \w+ (his|her|their) website preview.*", "Take a look at your website preview", t, flags=re.I)
        t = t.replace("their ", "your ").replace(" they ", " you ")
        items.append((t[:70], a.get("status") in ("resolved", "done")))
    # dedupe near-identical labels (two "take a look at your preview" asks)
    seen: set[str] = set()
    uniq = []
    for label, done in items:
        k = re.sub(r"[^a-z]", "", label.lower())[:28]
        if k in seen:
            continue
        seen.add(k)
        uniq.append((label, done))
    # done items first so the card opens with wins
    uniq.sort(key=lambda x: not x[1])
    return name, uniq[:9]


def render(name: str, items: list[tuple[str, bool]]) -> Image.Image:
    W, H = 1080, 1350
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([36, 36, W - 36, H - 36], 28, fill=CARD)
    d.rectangle([36, 36, W - 36, 58], fill=BLUE)

    d.text((92, 110), "YOUR SETUP CHECKLIST", font=_font(56, bold=True), fill=INK)
    d.rounded_rectangle([88, 190, 88 + d.textlength(name, font=_font(40, bold=True)) + 40, 250],
                        12, fill=(254, 246, 189))
    d.text((108, 200), name, font=_font(40, bold=True), fill=INK)

    y = 320
    for label, done in items:
        cx, cy = 130, y + 22
        if done:
            d.ellipse([cx - 24, cy - 24, cx + 24, cy + 24], fill=GREEN)
            d.line([cx - 11, cy, cx - 3, cy + 9], fill=CARD, width=6)
            d.line([cx - 3, cy + 9, cx + 13, cy - 10], fill=CARD, width=6)
        else:
            d.ellipse([cx - 24, cy - 24, cx + 24, cy + 24], outline=AMBER, width=6)
        f = _font(34, bold=not done)
        max_w = W - 190 - 100
        while label and d.textlength(label, font=f) > max_w:
            label = label[:-1]
        if d.textlength(label + "…", font=f) <= max_w + 30 and len(label) < 68:
            pass
        d.text((190, y), label, font=f, fill=INK if not done else MUTED)
        y += 84

    d.rounded_rectangle([88, H - 320, W - 88, H - 150], 20, fill=BLUE)
    d.text((W // 2, H - 268), "We really want to get you more visible", font=_font(34, bold=True),
           fill=CARD, anchor="mm")
    d.text((W // 2, H - 224), "on Google & ChatGPT.", font=_font(34, bold=True),
           fill=CARD, anchor="mm")
    d.text((W // 2, H - 178), "Can we hop on a quick call this week?", font=_font(30),
           fill=(191, 219, 254), anchor="mm")
    d.text((W // 2, H - 100), "Rank AI  •  restorationai.io", font=_font(24),
           fill=MUTED, anchor="mm")
    return img


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--company", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    name, items = gather(a.company)
    if not items:
        print("no items — no card generated")
        return 1
    img = render(name, items)
    if a.out:
        img.save(a.out)
    import io
    buf = io.BytesIO()
    img.save(buf, "PNG")
    key = f"checklists/{a.company}.png"
    if not r2_put(BUCKET, key, buf.getvalue(), "image/png"):
        print("r2 upload failed")
        return 1
    print(f"{PUBLIC_BASE}/{key}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
