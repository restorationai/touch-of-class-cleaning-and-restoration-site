"""Nightly citations sweep — the browser agent's scheduled pass.

Runs only playbook steps that have EARNED unattended status (3 clean
supervised completions). Tonight that is: Bing dashboard Sync + listing
verification. New playbooks (Houzz/BBB/...) join here only after their
supervised runs. The WORK QUEUE is the Ops Attention board itself: the
scheduled citations audit detects new live listings and updates the cards,
so completion is always detection-based, never honor-system.

Run: python3 -m browser_agent.sweep   (launchd: nightly 21:30 local)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from browser_agent.chassis import Session, ledger, paused  # noqa: E402


def bing_sync(s: Session) -> str:
    # SSO (Bing sessions are session-scoped — every run signs in fresh)
    s.page.goto("https://www.bing.com/forbusiness/genericLogin",
                wait_until="domcontentloaded", timeout=60000)
    s.page.wait_for_timeout(6000)
    if "genericLogin" in s.page.url:
        try:
            with s._ctx.expect_page(timeout=30000) as pi:
                s.page.mouse.click(1174, 295)
                s.page.wait_for_timeout(1500)
                s.page.keyboard.press("Enter")
            pop = pi.value
            pop.wait_for_load_state("domcontentloaded")
            pop.wait_for_timeout(4000)
            try:
                if pop.locator("text=contact@restorationai.io").count():
                    pop.locator("text=contact@restorationai.io").first.click(timeout=8000)
            except Exception:
                pass
            for _ in range(6):
                try:
                    if pop.is_closed():
                        break
                    pop.wait_for_timeout(2500)
                except Exception:
                    break
        except Exception as e:
            return f"sso failed: {str(e)[:80]}"
    s.page.wait_for_timeout(6000)
    s.page.goto("https://www.bing.com/forbusiness/multipleEntities",
                wait_until="domcontentloaded", timeout=60000)
    s.page.wait_for_timeout(8000)
    if "genericLogin" in s.page.url:
        return "not signed in after sso"
    try:
        s.page.get_by_text(re.compile("^Sync$", re.I)).first.click(timeout=6000)
        s.page.wait_for_timeout(45000)
    except Exception:
        pass  # Sync button absent = nothing new; dashboard still verifies
    s.page.goto("https://www.bing.com/forbusiness/multipleEntities",
                wait_until="domcontentloaded", timeout=60000)
    s.page.wait_for_timeout(8000)
    body = s.page.inner_text("body")[:2000]
    m = re.search(r"Total listings:\s*(\d+).*?Published:\s*(\d+)", body, re.S)
    shot = s.audit_shot("nightly-sync")
    return (f"listings={m.group(1)} published={m.group(2)} shot={shot}"
            if m else f"count unparsed shot={shot}")


def main() -> int:
    why = paused()
    if why:
        print(f"sweep skipped — kill switch: {why}")
        return 0
    s = Session(playbook="nightly-sweep", slug=None, live=True).start(headless=False)
    try:
        result = bing_sync(s)
        print("bing:", result)
        ledger(None, "nightly-sweep", "bing-sync", "done", detail=result, live=True)
    finally:
        s.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
