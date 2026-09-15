#!/usr/bin/env python3
"""One-shot (2026-09-15 07:00 PT / 9:00am Abilene): text Sarah (Air Care)
the LSA-specific billing link. Queued by Santino 09-14 night. kv-guarded so
a double launchd fire can never double-text."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

import client_concierge as cc  # noqa: E402

GUARD = "oneshot-sent:sarah-lsa-billing-2026-09-15"

def main() -> int:
    if cc.kv_get(GUARD):
        print("already sent — nothing to do")
        return 0
    comp = cc.fetch_companies(["CO-1786411719310"])["CO-1786411719310"]
    ghl = cc.resolve_contact(comp)
    body = ("Morning Sarah! Here's where the card goes for the Local "
            "Services Ads specifically: "
            "https://ads.google.com/localservices/settings/billing "
            "Sign in with the Air Care Google account, then Billing, then "
            "Add payment method. It's a separate screen from regular ads "
            "billing, which is why the earlier link may have looked off. "
            "Once the card is on file and Google finishes the identity "
            "check, your ads can go live right away.")
    r = cc.send_message(ghl, "sms", body, company=comp)
    state = cc.load_state()
    cc.record_sent_message(state, r)
    cc.save_state(state, dry_run=False)
    from datetime import datetime, timezone
    cc.kv_set(GUARD, {"at": datetime.now(timezone.utc).isoformat(),
                      "message_id": r.get("messageId")})
    print("sent:", r.get("messageId"))
    return 0

if __name__ == "__main__":
    sys.exit(main())
