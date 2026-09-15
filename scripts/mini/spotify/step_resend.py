"""Get to Spotify's 'Check your email' step for FEED: login if needed, walk
Add Podcast -> Find existing -> Somewhere else -> feed URL -> Next -> Send code.
Prints the epoch the code was requested (feed to step_verify.py)."""
import json, pathlib, sys, time
from playwright.sync_api import sync_playwright
from spot import connect, snap

FEED = sys.argv[1] if len(sys.argv) > 1 else "https://podcasts.restorationai.io/narestco/feed.xml"
c = json.loads((pathlib.Path.home() / ".rankai" / "portal-creds.json").read_text())["spotify:agency"]


def login_if_needed(page):
    if "accounts.spotify.com" not in page.url:
        return
    page.fill("#username", c["user"])
    page.click("button[type=submit]")
    time.sleep(4)
    f = page.locator("input[type=password]")
    if f.count() == 0:
        for t in ("Log in with a password", "Use password"):
            l = page.get_by_text(t, exact=False)
            if l.count():
                l.first.click(); time.sleep(3); break
        f = page.locator("input[type=password]")
    if f.count() == 0:
        snap(page, "login-challenge"); raise SystemExit("no password field — challenge? human needed")
    f.first.fill(c["pass"]); page.keyboard.press("Enter"); time.sleep(8)
    print("logged in ->", page.url)


def text(page):
    return page.evaluate("() => document.body.innerText")


with sync_playwright() as pw:
    b, ctx, page = connect(pw)
    page.goto("https://creators.spotify.com/dash/submit", wait_until="domcontentloaded"); time.sleep(5)
    login_if_needed(page)
    if "dash/submit" not in page.url:
        page.goto("https://creators.spotify.com/dash/submit", wait_until="domcontentloaded"); time.sleep(5)
    t = text(page)
    if "What would you like to do?" in t:
        page.locator("div[role=button][aria-labelledby*=addPodcastModalItem-1]").first.click(); time.sleep(3); t = text(page)
    if "Where’s your show hosted?" in t or "Where's your show hosted?" in t:
        page.locator("div[role=button][aria-labelledby*=addPodcastModalItem-2]").first.click(); time.sleep(3); t = text(page)
    print("at:", page.url)
    if "Send code" in t:
        pass
    elif "Check your email" in t:
        page.get_by_role("button", name="Resend").click(); time.sleep(4)
        print("code re-requested at epoch", int(time.time())); snap(page, "code-entry", 600); sys.exit(0)
    else:
        inp = page.locator("#podcastRSSLink")
        inp.click(); inp.fill(""); inp.fill(FEED); time.sleep(1)
        nxt = page.get_by_role("button", name="Next")
        for _ in range(20):
            if not nxt.is_disabled(): break
            time.sleep(1)
        if nxt.is_disabled():
            snap(page, "feed-rejected", 1500); raise SystemExit("feed not accepted")
        nxt.click(); time.sleep(8)
        t = text(page)
        if "Send code" not in t:
            snap(page, "unexpected-after-next", 2000); raise SystemExit("no Send code step")
    if "contact@restorationai.io" not in text(page):
        snap(page, "wrong-owner-email", 1500); raise SystemExit("owner email on feed is not the agency inbox")
    page.get_by_role("button", name="Send code").click(); time.sleep(5)
    print("code requested at epoch", int(time.time()))
    snap(page, "code-entry", 600)
