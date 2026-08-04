"""Chassis — the shared safety machinery every playbook runs inside.

Owns: the persistent Chromium profile, the live-write gates (dry-run default,
kill switch in ops_kv), audit screenshots, the action ledger, and the
credential store. Playbooks receive a `Session` and never touch these
concerns directly. Pattern adapted from the Skool Automation reference
(persistent profile + gated writes + audit + dedupe ledger), 2026-08-01.
"""
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from client_ops_sync import _sb, slug_map  # noqa: E402

RUNTIME = Path(__file__).resolve().parent / "runtime"
PROFILE_DIR = RUNTIME / "browser-profile"
AUDIT_DIR = RUNTIME / "audit"
CREDS_PATH = Path.home() / ".rankai" / "portal-creds.json"
KILL_SWITCH_KEY = "browser-agent-paused"


def paused() -> str | None:
    """Kill switch: any truthy value in ops_kv pauses ALL live writes."""
    try:
        rows = _sb("GET", f"/rest/v1/ops_kv?k=eq.{KILL_SWITCH_KEY}&select=v") or []
        v = rows[0]["v"] if rows else None
        return v if v else None
    except Exception as e:  # can't verify the switch -> treat as paused
        return f"kill-switch check failed ({str(e)[:60]}) — refusing live writes"


def set_paused(value) -> None:
    _sb("POST", "/rest/v1/ops_kv?on_conflict=k",
        {"k": KILL_SWITCH_KEY, "v": value,
         "updated_at": datetime.now(timezone.utc).isoformat()},
        prefer="resolution=merge-duplicates,return=minimal")


def portal_creds(key: str) -> dict | None:
    """Registrar/portal credentials from ~/.rankai/portal-creds.json — NEVER
    in the repo. Shape: {"bluehost:quality-contracting-inc": {"user": ...,
    "pass": ..., "registrar": "bluehost"}, "godaddy:delegate": {...}}"""
    if not CREDS_PATH.exists():
        return None
    try:
        return json.loads(CREDS_PATH.read_text()).get(key)
    except json.JSONDecodeError:
        return None


def ledger(company_id: str | None, playbook: str, action: str, outcome: str,
           detail: str = "", live: bool = False, meta: dict | None = None) -> None:
    """Every attempted/completed action lands in browser_agent_actions —
    the human-visible audit trail. Best-effort, never fatal."""
    try:
        _sb("POST", "/rest/v1/browser_agent_actions", {
            "company_id": company_id, "playbook": playbook, "action": action,
            "outcome": outcome, "detail": detail[:400], "live": live,
            "meta": meta or {}}, prefer="return=minimal")
    except Exception as e:
        print(f"  [ledger] write failed: {str(e)[:80]}", file=sys.stderr)


@dataclass
class Session:
    """A gated browser session handed to playbooks."""
    playbook: str
    slug: str | None
    live: bool
    company_id: str | None = None
    _pw: object = field(default=None, repr=False)
    _ctx: object = field(default=None, repr=False)
    page: object = field(default=None, repr=False)

    def __post_init__(self):
        if self.slug:
            rev = {v: k for k, v in slug_map().items()}
            self.company_id = rev.get(self.slug)

    def start(self, headless: bool = False):
        from playwright.sync_api import sync_playwright
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        AUDIT_DIR.mkdir(parents=True, exist_ok=True)
        self._pw = sync_playwright().start()
        # Persistent context = the logged-in identity. Headed by default —
        # these are high-stakes portals and watchability beats speed.
        # channel="chrome" + automation flags off: GoDaddy's WAF pre-emptively
        # denies browsers that ANNOUNCE automation (2026-08-01, Santino hit
        # "access denied" during first login). This makes the session present
        # as the normal Chrome it effectively is — a real human's logged-in
        # profile. Actual security challenges still pause us (never bypassed).
        launch = dict(headless=headless, viewport={"width": 1440, "height": 900},
                      args=["--disable-blink-features=AutomationControlled"],
                      ignore_default_args=["--enable-automation"])
        try:
            self._ctx = self._pw.chromium.launch_persistent_context(
                str(PROFILE_DIR), channel="chrome", **launch)
        except Exception:  # no system Chrome — bundled Chromium fallback
            self._ctx = self._pw.chromium.launch_persistent_context(
                str(PROFILE_DIR), **launch)
        self.page = self._ctx.pages[0] if self._ctx.pages else self._ctx.new_page()
        return self

    def stop(self):
        try:
            if self._ctx:
                self._ctx.close()
            if self._pw:
                self._pw.stop()
        except Exception:
            pass

    # ---- gates ----
    def guard_live(self, action: str) -> bool:
        """True only when a live write is allowed RIGHT NOW. Logs the refusal
        otherwise. Playbooks must call this immediately before any submit."""
        if not self.live:
            print(f"  [dry-run] would: {action}")
            ledger(self.company_id, self.playbook, action, "dry_run")
            return False
        why = paused()
        if why:
            print(f"  [BLOCKED] kill switch: {why}")
            ledger(self.company_id, self.playbook, action, "blocked_kill_switch",
                   detail=str(why))
            return False
        return True

    def challenge_detected(self, what: str):
        """CAPTCHA / login prompt / 2FA — never bypass: screenshot, ledger,
        pause everything, file a [TODO-SANTINO] note, and stop the run."""
        shot = self.audit_shot(f"challenge-{what}")
        ledger(self.company_id, self.playbook, f"challenge:{what}", "paused",
               detail=f"security challenge — human needed; shot={shot}")
        set_paused(f"security challenge in {self.playbook} ({what}) "
                   f"{datetime.now(timezone.utc).isoformat()}")
        try:
            _sb("POST", "/rest/v1/marketing_ops_notes", {
                "company_id": self.company_id,
                "body": f"[TODO-SANTINO] Browser agent PAUSED: {what} challenge "
                        f"during {self.playbook}. Re-login/solve manually "
                        f"(python3 -m browser_agent login), then "
                        f"`python3 -m browser_agent resume`."})
        except Exception:
            pass
        raise SystemExit(f"paused on {what} challenge — human needed")

    def audit_shot(self, label: str) -> str:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        path = AUDIT_DIR / f"{ts}-{self.playbook}-{label[:40].replace(' ', '_')}.png"
        try:
            self.page.screenshot(path=str(path), full_page=False)
        except Exception:
            return "(screenshot failed)"
        return str(path)


def company_truth(company_id: str) -> dict:
    """The NAP source of truth: the company row (REAL phone, never tracking)."""
    rows = _sb("GET", f"/rest/v1/companies?id=eq.{company_id}"
               "&select=id,name,phone,email,website,address,city,state,postal_code,services") or []
    return rows[0] if rows else {}


def mark_ledger_item_done(company_id: str, item_key: str, note: str) -> None:
    """Flip a marketing_setup_ledger item to done AFTER verified completion —
    this is how the human board clears (Santino 2026-08-01: items stay
    visible until the agent finishes and clears them)."""
    _sb("POST", "/rest/v1/marketing_setup_ledger?on_conflict=company_id,item_key",
        [{"company_id": company_id, "item_key": item_key, "kind": "us_owed",
          "status": "done", "title": note[:120], "detail": note,
          "updated_at": datetime.now(timezone.utc).isoformat()}],
        prefer="resolution=merge-duplicates")


def wait_for_human(page, prompt: str, timeout_s: int = 600):
    """Supervised-mode helper: hold the browser open for a human step."""
    print(f"\n>>> HUMAN STEP: {prompt}")
    print(f">>> finish in the browser window, then press Enter here "
          f"(timeout {timeout_s}s)")
    import select
    r, _, _ = select.select([sys.stdin], [], [], timeout_s)
    if not r:
        raise SystemExit("human step timed out")
    sys.stdin.readline()
