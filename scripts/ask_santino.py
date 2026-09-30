#!/usr/bin/env python3
"""ask_santino.py — the ONE way the Claude mini-needs agent escalates.

Santino 2026-09-30: Mini questions go to Claude first; only when Claude
cannot answer does Santino get asked, and he answers Claude (never the Mini
directly). This texts him through the ops-ping path and files one open
[TODO-SANTINO] note carrying the need id, so the answer can be written back
to clients/_ops/mini-needs.md by whichever Claude session he replies to.

Usage:
  python3 scripts/ask_santino.py --need NEED-... --question "..." [--client slug]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

import client_concierge as cc  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--need", required=True)
    ap.add_argument("--question", required=True)
    ap.add_argument("--client", default="_ops")
    a = ap.parse_args()
    cc.load_env()
    q = re.sub(r"\s+", " ", a.question).strip()
    cc._sb("POST", "/rest/v1/marketing_ops_notes",
           {"company_id": None, "author": "mini-needs-agent", "status": "open",
            "body": (f"[TODO-SANTINO] MINI QUESTION {a.need} ({a.client}): {q} "
                     "— reply to Claude; Claude writes the answer back to the Mini.")[:1900]},
           prefer="return=minimal")
    sms = f"Claude needs you (Mini, {a.client}): {q[:430]}{' ...' if len(q) > 430 else ''} Reply to Claude."
    try:
        cc.send_message({"id": cc.OPS_PING_CONTACT_ID, "phone": cc.OPS_PING_CELL},
                        "sms", sms[:640])
        print("texted Santino + filed [TODO-SANTINO]")
    except Exception as e:  # noqa: BLE001
        print(f"note filed; SMS failed: {str(e)[:120]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
