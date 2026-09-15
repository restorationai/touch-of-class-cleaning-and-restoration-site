"""CDP helper for the held Spotify-for-Creators Chrome (port 9223).
Launch the held browser with:
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    --user-data-dir=<repo>/browser_agent/runtime/browser-profile \
    --remote-debugging-port=9223 --no-first-run --no-default-browser-check \
    --window-size=1440,900 --disable-blink-features=AutomationControlled \
    https://creators.spotify.com/ &
"""
import json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

CDP = "http://localhost:9223"
SHOTS = Path(__file__).resolve().parent / "shots"
SHOTS.mkdir(exist_ok=True)


def connect(pw):
    b = pw.chromium.connect_over_cdp(CDP)
    ctx = b.contexts[0]
    pages = [p for p in ctx.pages if "spotify" in p.url] or ctx.pages
    return b, ctx, pages[-1]


def snap(page, label="snap", n=4000):
    path = SHOTS / f"{label}.png"
    try:
        page.screenshot(path=str(path), full_page=False)
    except Exception as e:
        path = f"(shot failed {e})"
    print("URL:", page.url)
    print("TITLE:", page.title())
    print("SHOT:", path)
    try:
        print("TEXT:\n" + page.evaluate("() => document.body.innerText")[:n])
    except Exception as e:
        print("text failed", e)
    try:
        els = page.evaluate("""() => [...document.querySelectorAll('a,button,input,select,textarea,[role=button],[role=radio],[role=option],[role=checkbox]')].map(e=>({t:e.tagName, r:e.getAttribute('role'), type:e.type||'', id:e.id||'', ph:e.placeholder||'', al:e.getAttribute('aria-label')||'', txt:(e.innerText||e.value||'').trim().slice(0,80), href:(e.href||'').slice(0,120), dis:e.disabled||false, vis:!!(e.offsetParent)})).filter(e=>e.vis && e.t!=='A')""")
        print("ELEMENTS:")
        for e in els[:80]:
            print(" ", json.dumps(e))
    except Exception as e:
        print("els failed", e)


if __name__ == "__main__":
    with sync_playwright() as pw:
        b, ctx, page = connect(pw)
        print("pages:", [p.url for p in ctx.pages])
        snap(page, sys.argv[1] if len(sys.argv) > 1 else "snap")
