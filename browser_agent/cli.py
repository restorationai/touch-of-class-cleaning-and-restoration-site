"""CLI: login / run / pause / resume / status. See README.md."""
from __future__ import annotations

import argparse
import importlib

from .chassis import PROFILE_DIR, Session, paused, set_paused

PLAYBOOKS = {
    "apple-maps": "browser_agent.playbooks.apple_maps",
    "bing-places": "browser_agent.playbooks.bing_places",
    "domain-connect": "browser_agent.playbooks.domain_connect",
}


def main() -> int:
    ap = argparse.ArgumentParser(prog="browser_agent")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("login", help="open the persistent profile for human login")
    pr = sub.add_parser("run", help="run a playbook (dry-run unless --live)")
    pr.add_argument("--playbook", required=True, choices=sorted(PLAYBOOKS))
    pr.add_argument("--slug")
    pr.add_argument("--domain")
    pr.add_argument("--registrar")
    pr.add_argument("--live", action="store_true")
    pr.add_argument("--headless", action="store_true")
    pr.add_argument("--cdp", metavar="URL", default=None,
                    help="attach to a logged-in human Chrome over CDP "
                         "(e.g. http://localhost:9222) instead of the "
                         "persistent profile — authorized session reuse")
    pp = sub.add_parser("pause", help="engage the kill switch")
    pp.add_argument("--reason", default="manual pause")
    sub.add_parser("resume", help="release the kill switch")
    sub.add_parser("status")
    a = ap.parse_args()

    if a.cmd == "status":
        why = paused()
        print(f"kill switch: {'PAUSED — ' + str(why) if why else 'off'}")
        print(f"profile: {PROFILE_DIR} ({'exists' if PROFILE_DIR.exists() else 'not yet created'})")
        return 0
    if a.cmd == "pause":
        set_paused(a.reason)
        print("paused.")
        return 0
    if a.cmd == "resume":
        set_paused("")
        print("resumed.")
        return 0
    if a.cmd == "login":
        s = Session(playbook="login", slug=None, live=False).start(headless=False)
        print("Log into the agency accounts (Google, Bing/Microsoft, GoDaddy…) "
              "in this window. Close the window when done — the profile persists.")
        try:
            s.page.goto("https://accounts.google.com/")
            s._ctx.wait_for_event("close", timeout=0)
        except Exception:
            pass
        finally:
            s.stop()
        return 0

    # run
    mod = importlib.import_module(PLAYBOOKS[a.playbook])
    s = Session(playbook=a.playbook, slug=a.slug, live=a.live).start(
        headless=a.headless, cdp_url=a.cdp)
    try:
        kwargs = {}
        if a.playbook == "domain-connect":
            kwargs = {"domain": a.domain, "registrar": a.registrar}
        return mod.run(s, **kwargs)
    finally:
        s.stop()
