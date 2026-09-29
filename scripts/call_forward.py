#!/usr/bin/env python3
"""call_forward.py — change where one of a client's tracking numbers rings.

Santino 2026-09-29 (Bob Olson / RT Olson): Bob emailed the ServiceTitan lines
his Google Ads and Facebook Ads tracking numbers should forward to. Monica
read it, answered "I'll pass this along to Santino" twice, and nothing
changed for a day, because no tool existed and the classifier treated
anything about ads as not-a-change-request. This is that tool. Monica's
feedback router calls apply() directly when a client names the number
(category "call_routing"), so a clear request runs the moment it arrives.

How routing works: every tracking number's Twilio webhook hits the Railway
API (api/main.py /twilio/voice), which forwards to
integration_settings.call_tracking.{source}.forward_to when set, else
companies.phone. So a forward change is one field; the API re-reads the
company within 2 minutes (its TwiML cache TTL).

Usage:
  python3 scripts/call_forward.py show --company CO-...
  python3 scripts/call_forward.py set --company CO-... --source google_ads --to 951-257-9526 [--apply]
  python3 scripts/call_forward.py set --company CO-... --source meta_ads --reset --apply   # back to the main line
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

# What clients call a source -> the call_tracking key. Paid ads first: a
# client saying "Facebook Ads" means the ads number, not the page button.
SOURCE_ALIASES = [
    (r"google\s*ads|adwords|google\s*ppc|search\s*ads", "google_ads"),
    (r"(facebook|meta|fb|instagram)\s*ads?|meta_ads", "meta_ads"),
    (r"local\s*services|\blsa\b", "lsa"),
    (r"google\s*(business|profile|maps|listing)|\bgbp\b|\bgmb\b", "gbp"),
    (r"web\s*site|\bsite\b|website", "website"),
    (r"\bbing\b", "bing"),
    (r"\byelp\b", "yelp"),
    (r"chat\s*gpt", "chatgpt"),
    (r"gemini", "gemini"),
    (r"instagram", "instagram"),
    (r"facebook|\bfb\b", "facebook"),
]


def resolve_source(text: str, available: list[str]) -> str | None:
    t = (text or "").strip().lower()
    if t in available:
        return t
    for pat, key in SOURCE_ALIASES:
        if re.search(pat, t) and key in available:
            return key
    return None


def e164(num: str) -> str | None:
    d = re.sub(r"\D", "", num or "")
    if len(d) == 11 and d.startswith("1"):
        d = d[1:]
    if len(d) != 10 or d[0] in "01":
        return None
    return "+1" + d


def pretty(num: str) -> str:
    d = re.sub(r"\D", "", num)[-10:]
    return f"{d[:3]}-{d[3:6]}-{d[6:]}"


def _load(cid: str) -> dict:
    import client_concierge as cc
    cc.load_env()
    rows = cc._sb("GET", f"/rest/v1/companies?id=eq.{cid}"
                  "&select=name,phone,integration_settings") or []
    if not rows:
        raise RuntimeError(f"unknown company {cid}")
    return rows[0]


def apply(company_id: str, source_text: str, to: str | None, *,
          who: str = "the client", quote: str = "", reset: bool = False,
          dry_run: bool = False, notify_client: bool = True) -> dict:
    """Point one tracking number at `to` (or back to the main line with
    reset). Returns {"ok", "source", "number", "from", "to", "line"} or
    {"ok": False, "why"}. Never raises for a bad request: the caller files a
    human task with the reason instead."""
    import client_concierge as cc
    co = _load(company_id)
    ints = co.get("integration_settings") or {}
    ct = ints.get("call_tracking") or {}
    src = resolve_source(source_text, list(ct))
    if not src:
        return {"ok": False, "why": f"no tracking number for {source_text!r} "
                f"(have: {', '.join(sorted(ct)) or 'none'})"}
    target = None if reset else e164(to or "")
    if not reset and not target:
        return {"ok": False, "why": f"not a valid US number: {to!r}"}
    entry = ct[src]
    if target and re.sub(r"\D", "", target) == re.sub(r"\D", "", entry.get("number") or ""):
        return {"ok": False, "why": "that is the tracking number itself (a loop)"}
    before = entry.get("forward_to") or co.get("phone") or ""
    if (entry.get("forward_to") or None) == target:
        return {"ok": True, "source": src, "number": entry.get("number"),
                "from": before, "to": target or co.get("phone"),
                "line": "already set", "noop": True}
    now = datetime.now(timezone.utc).isoformat()
    if target:
        entry.update(forward_to=target, forward_set_at=now,
                     forward_note=f"{who}: {quote[:160]}" if quote else who)
    else:
        for k in ("forward_to", "forward_set_at", "forward_note"):
            entry.pop(k, None)
    label = src.replace("_", " ").replace("meta ads", "Facebook Ads") \
        .replace("google ads", "Google Ads").replace("gbp", "Google profile")
    dest = pretty(target) if target else f"your main line ({pretty(co.get('phone') or '')})"
    line = (f"Your {label} tracking number ({pretty(entry.get('number') or '')}) "
            f"now rings {dest}.")
    if dry_run:
        return {"ok": True, "source": src, "number": entry.get("number"),
                "from": before, "to": target, "line": line, "dry_run": True}
    cc._sb("PATCH", f"/rest/v1/companies?id=eq.{company_id}",
           {"integration_settings": ints}, prefer="return=minimal")
    try:
        from work_log import work_log
        work_log(company_id, "ads" if "ads" in src or src == "lsa" else "calls",
                 "tracking-forward-update", line,
                 evidence={"source": src, "tracking_number": entry.get("number"),
                           "from": before, "to": target or "main line",
                           "quote": quote[:300], "who": who},
                 actor="monica", source="call_forward.apply")
    except Exception as e:  # noqa: BLE001
        print(f"  [work-log] warn: {str(e)[:90]}")
    return {"ok": True, "source": src, "number": entry.get("number"),
            "from": before, "to": target, "line": line}


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sh = sub.add_parser("show")
    sh.add_argument("--company", required=True)
    st = sub.add_parser("set")
    st.add_argument("--company", required=True)
    st.add_argument("--source", required=True)
    st.add_argument("--to")
    st.add_argument("--reset", action="store_true")
    st.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    if a.cmd == "show":
        co = _load(a.company)
        for k, v in sorted(((co.get("integration_settings") or {})
                            .get("call_tracking") or {}).items()):
            print(f"{k:12} {v.get('number')} -> {v.get('forward_to') or co.get('phone')}"
                  + ("" if v.get("forward_to") else "  (main line)"))
        return 0
    r = apply(a.company, a.source, a.to, reset=a.reset, who="operator",
              dry_run=not a.apply)
    print(r)
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
