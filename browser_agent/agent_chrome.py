"""agent_chrome — the Mini's agents use a REAL, already-signed-in Chrome.

Why (Santino 2026-09-30): the agent used to launch Chrome through Playwright
on its own profile folder (runtime/browser-profile). Every login done there
kept disappearing when the session closed. Playwright launches Chrome with a
mock keychain and treats the profile as disposable, so site sessions do not
survive like they do in a normal Chrome, and nothing signed into Santino's
own Chrome ever reaches it.

Now: a dedicated Chrome data folder (~/.rankai/agent-chrome) that is a COPY
of the Chrome profile Santino is already signed into, launched as a normal
Chrome (real keychain, so the copied cookies decrypt and every login is
already there) with a local debugging port. The agent ATTACHES to it, works
in its own tab, and closes only that tab: Chrome stays open and signed in.
(Chrome refuses a debugging port on its default data folder, which is why
this is a copy in its own folder rather than the everyday profile itself.)

Commands (run on the Mini, in Terminal):
  python3 -m browser_agent.agent_chrome setup --from "Profile 1"
      Quit Chrome first. Copies that profile (and Local State) into
      ~/.rankai/agent-chrome. `list` shows which folder is which account.
  python3 -m browser_agent.agent_chrome list
  python3 -m browser_agent.agent_chrome start      # launch it (idempotent)
  python3 -m browser_agent.agent_chrome status

chassis.Session.start() uses it automatically once setup has run; before
that, nothing changes.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

AGENT_DIR = Path.home() / ".rankai" / "agent-chrome"
PORT = 9223
CDP_URL = f"http://127.0.0.1:{PORT}"
CHROME_APP = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
SRC_ROOT = Path.home() / "Library" / "Application Support" / "Google" / "Chrome"
SKIP_DIRS = {"Cache", "Code Cache", "GPUCache", "Service Worker", "DawnCache",
             "GrShaderCache", "ShaderCache", "Crashpad", "optimization_guide_model_store"}


def configured() -> bool:
    return (AGENT_DIR / "Local State").exists() and (AGENT_DIR / "Default").is_dir()


def running() -> bool:
    try:
        with urllib.request.urlopen(f"{CDP_URL}/json/version", timeout=2) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


def start(wait_s: int = 25) -> bool:
    """Launch the agent Chrome if it is not already up. Returns True when the
    debugging port answers."""
    if running():
        return True
    if not configured():
        return False
    subprocess.Popen([CHROME_APP, f"--user-data-dir={AGENT_DIR}",
                      f"--remote-debugging-port={PORT}", "--profile-directory=Default",
                      "--no-first-run", "--no-default-browser-check", "--restore-last-session"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    for _ in range(wait_s * 2):
        if running():
            return True
        time.sleep(0.5)
    return False


def list_profiles() -> None:
    try:
        info = json.loads((SRC_ROOT / "Local State").read_text())["profile"]["info_cache"]
    except Exception as e:  # noqa: BLE001
        print(f"cannot read Chrome profiles: {e}")
        return
    for folder, d in info.items():
        print(f"{folder:12} {d.get('name', ''):24} {d.get('user_name', '')}")


def setup(src_profile: str) -> int:
    src = SRC_ROOT / src_profile
    if not src.is_dir():
        print(f"no Chrome profile folder {src}. Run `list` to see them.")
        return 1
    if subprocess.run(["pgrep", "-x", "Google Chrome"], capture_output=True).returncode == 0:
        print("Quit Google Chrome first (Cmd+Q), then run setup again: "
              "copying a profile while Chrome writes to it can corrupt the copy.")
        return 1
    if AGENT_DIR.exists():
        shutil.rmtree(AGENT_DIR)
    AGENT_DIR.mkdir(parents=True)
    shutil.copy2(SRC_ROOT / "Local State", AGENT_DIR / "Local State")
    shutil.copytree(src, AGENT_DIR / "Default",
                    ignore=lambda d, names: [n for n in names if n in SKIP_DIRS])
    print(f"copied {src_profile} -> {AGENT_DIR}/Default")
    ok = start()
    print("agent Chrome is up on port", PORT if ok else "FAILED to start")
    print("Check it: the window that opened should already be signed in "
          "(Bing Places, Google, etc.). Leave it open; agents attach to it.")
    return 0 if ok else 1


def main() -> int:
    args = sys.argv[1:]
    cmd = args[0] if args else "status"
    if cmd == "list":
        list_profiles()
        return 0
    if cmd == "setup":
        src = args[args.index("--from") + 1] if "--from" in args else "Default"
        return setup(src)
    if cmd == "start":
        ok = start()
        print("running" if ok else "not configured / failed to start")
        return 0 if ok else 1
    print(f"configured={configured()} running={running()} dir={AGENT_DIR} port={PORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
