"""Finish the Spotify submission: pull the 8-digit ownership code from the
agency inbox (sent to the feed's owner email = contact@restorationai.io),
enter it, keep the defaults (category Education, language from the feed),
and walk Next/Done until the show page or dashboard appears.
usage: python3 step_verify.py <epoch-when-code-was-requested>"""
import sys, time
from playwright.sync_api import sync_playwright
from spot import connect, snap
from gmail_code import find_code

sent_at = int(sys.argv[1])


def text(page):
    return page.evaluate("() => document.body.innerText")


with sync_playwright() as pw:
    b, ctx, page = connect(pw)
    print("at:", page.url)
    if "Check your email" not in text(page):
        snap(page, "verify-unexpected", 1500); raise SystemExit("not on the code-entry step")
    code, subj = find_code(sent_at, sender="creators.spotify.com", digits=8, timeout_s=600, every=15)
    print("code found:", bool(code), "| subject:", subj)
    if not code:
        raise SystemExit("no code email within 10 min")
    inp = page.locator("#verification_code")
    inp.click(); inp.fill(code); time.sleep(2)
    nxt = page.get_by_role("button", name="Next")
    for _ in range(15):
        if not nxt.is_disabled(): break
        time.sleep(1)
    if nxt.is_disabled():
        snap(page, "code-not-accepted", 1200); raise SystemExit("Next stayed disabled after code entry")
    nxt.click(); time.sleep(8)
    # Walk any remaining default-accepting steps (language / confirm / done).
    for i in range(6):
        t = text(page)
        snap(page, f"post-verify-{i}", 1800)
        if "dash/submit" not in page.url and "addpodcast" not in page.url:
            break
        clicked = False
        for name in ("Next", "Done", "Finish", "Submit", "Continue", "Go to dashboard"):
            btn = page.get_by_role("button", name=name)
            if btn.count() and not btn.first.is_disabled():
                print("clicking", name); btn.first.click(); time.sleep(8); clicked = True; break
        if not clicked:
            break
    print("FINAL URL:", page.url)
    snap(page, "final", 3000)
