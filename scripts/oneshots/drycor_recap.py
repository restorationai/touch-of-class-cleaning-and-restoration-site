#!/usr/bin/env python3
"""One-shot 2026-09-16 06:00 PT (9:00am ET): DryCor post-call recap to
Robert — the name confirmation with Tampa (Santino's 09-15 decision), held
overnight by the evening-shoulder rule. kv-guarded."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")
import client_concierge as cc
from client_ops_sync import _sb

GUARD = "oneshot-sent:drycor-recap-2026-09-16"
NAME = "DRYCOR RESTORE TAMPA - 24/7 Emergency Plumbing, Water Damage and Mold Remediation"

def main() -> int:
    if cc.kv_get(GUARD):
        print("already sent")
        return 0
    cid = "CO-1788205391336"
    comp = cc.fetch_companies([cid])[cid]
    ghl = cc.resolve_contact(comp)
    body = ("Morning Rob, great call yesterday. Everything we discussed is "
            "in motion: the site updates are queued (Tampa wording, the 5.0 "
            "rating line, preferred vendor, black logo, and the RGP cities), "
            "the LSA fix is on our list, and the DBA sign is headed to "
            "Ashley. One thing to lock so we can start filing and building: "
            "the exact name. We went with Tampa over Tampa Bay since it's "
            "what people actually search:\n"
            f"{NAME}\n"
            "If that reads right, file it word for word as the fictitious "
            "name (Florida also asks for a one-time newspaper notice, we'll "
            "point you through it), then snap a photo of the filing and "
            "send it through your hub. Everything else rolls from there.")
    r = cc.send_message(ghl, "sms", body, company=comp)
    state = cc.load_state()
    cc.record_sent_message(state, r)
    cc.save_state(state, dry_run=False)
    from datetime import datetime, timezone
    cc.kv_set(GUARD, {"at": datetime.now(timezone.utc).isoformat(),
                      "message_id": r.get("messageId")})
    kv = (_sb("GET", f"/rest/v1/ops_kv?k=eq.rename-convo:{cid}&select=v")
          or [{}])[0].get("v") or {}
    kv["stage"] = "confirmed"
    kv["chosen"] = NAME
    kv["last_outbound"] = body
    _sb("POST", "/rest/v1/ops_kv?on_conflict=k",
        {"k": f"rename-convo:{cid}", "v": kv},
        prefer="resolution=merge-duplicates")
    print("recap sent + rename state armed")
    return 0

if __name__ == "__main__":
    sys.exit(main())
