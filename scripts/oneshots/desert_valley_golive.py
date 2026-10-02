#!/usr/bin/env python3
"""One-shot 2026-10-02 08:00-11:00 PT: tell Rachelle (Desert Valley) her new
site is live — answering her 10-01 12:39pm "When will that be live" that
Monica parked with "checking with Santino".

Gated on the site ACTUALLY being live (Santino 10-01: launch on
desertvalleyrestoration.com, 301 the Contracting domains): both domains need a
GoDaddy nameserver change first (human-only, registrar law). launchd fires this
every 30 min 08:00-11:00 PT; each run verifies from OUTSIDE the LAN (DoH +
pinned curl, identity = our robots.txt sitemap line):
  - restoration domain live  -> finish the cutover (stamp/GSC/verify, fail-soft),
    then send via monica_oneoff.py; wording depends on whether the .net
    already 301s to the new domain.
  - not live yet             -> exit quietly; at the 11:00 run text Santino once.
kv-guarded so it sends at most once."""
import json
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")
import client_concierge as cc

GUARD = "oneshot-sent:desert-valley-golive-2026-10-02"
CID = "CO-1789170047342"
NEW = "desertvalleyrestoration.com"
OLD = "desertvalleycontracting.net"
DAY = "2026-10-02"
# her 10-01 email "THE LINK DIDN'T OPEN": the SendGrid click-tracked link is
# plain http (url4155 has no TLS), so HTTPS-first browsers / Safe Links fail;
# send the direct https report URL instead
REPORT = ("https://rank-ai-api-production.up.railway.app/report/"
          "CO-1789170047342/2026-09-7bdac808ed.html")

BODY_BOTH = ("Hi Rachelle, your new Desert Valley Restoration website is live "
             "at desertvalleyrestoration.com. Your old desertvalleycontracting.net "
             "address forwards to it automatically, so existing links and "
             "listings keep working. Also, sorry the September results link "
             "didn't open for you, here it is again: " + REPORT)
BODY_NEW_ONLY = ("Hi Rachelle, your new Desert Valley Restoration website is "
                 "live at desertvalleyrestoration.com. We're also pointing your "
                 "old desertvalleycontracting.net address to it so existing "
                 "links and listings keep working. Also, sorry the September "
                 "results link didn't open for you, here it is again: " + REPORT)
CONTEXT = (
    "Answers Rachelle's 10-01 text 'When will that be live' (Monica replied she "
    "was checking with Santino). Santino 10-01: the site launches on the DBA "
    "domain desertvalleyrestoration.com; desertvalleycontracting.net 301s to it "
    "page by page (old Thryv pages map to the matching new pages), so listings "
    "that still show the .net keep working and get updated to the new domain "
    "over time. desertvalleycontracting.com (Namecheap) gets pointed at the new "
    "site too. The Google profile rename to the DBA and its website-field update "
    "are separate steps still in progress; do not promise a date for those. "
    "Their email (desertvalleyco.com) is untouched by any of this. The same "
    "text re-sends her September results page (her 10-01 email said the "
    "emailed link didn't open; this is the direct link). If it still won't "
    "open for her, ask what she sees and pass it along to Santino. If she "
    "asks about the business cards QR code, pass it along to Santino.")


def doh_a(name: str) -> list[str]:
    req = urllib.request.Request(
        f"https://cloudflare-dns.com/dns-query?name={name}&type=A",
        headers={"accept": "application/dns-json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return [a["data"] for a in json.load(r).get("Answer", []) if a.get("type") == 1]


def curl(domain: str, path: str, ip: str) -> tuple[int, str, str]:
    out = subprocess.run(
        ["curl", "-s", "-m", "20", "--resolve", f"{domain}:443:{ip}",
         "-o", "/dev/stdout", "-w", "\n__META__%{http_code} %{redirect_url}",
         f"https://{domain}{path}"], capture_output=True, text=True)
    body, _, meta = out.stdout.rpartition("\n__META__")
    code, _, loc = meta.partition(" ")
    return int(code or 0), loc.strip(), body


def new_live() -> bool:
    try:
        ips = doh_a(NEW)
        if not ips:
            return False
        code, _, body = curl(NEW, "/robots.txt", ips[0])
        return code == 200 and f"https://{NEW}/sitemap-index.xml" in body
    except Exception as e:  # noqa: BLE001
        print(f"new-domain check failed: {e}")
        return False


def old_redirects() -> bool:
    try:
        ips = doh_a(OLD)
        if not ips:
            return False
        code, loc, _ = curl(OLD, "/about-us", ips[0])
        return code == 301 and loc.startswith(f"https://{NEW}/")
    except Exception as e:  # noqa: BLE001
        print(f"old-domain check failed: {e}")
        return False


def text_santino(body: str) -> None:
    try:
        cc.send_message({"id": cc.OPS_PING_CONTACT_ID, "phone": cc.OPS_PING_CELL},
                        "sms", body[:640])
    except Exception as e:  # noqa: BLE001
        print(f"santino ping failed: {e}")


def main() -> int:
    now = datetime.now(ZoneInfo("America/Los_Angeles"))
    if now.date().isoformat() != DAY or now.hour < 8:
        print(f"outside the send window ({now:%Y-%m-%d %H:%M} PT)")
        return 0
    if cc.kv_get(GUARD):
        print("already handled")
        return 0
    if not new_live():
        print(f"{NEW} not live from outside yet ({now:%H:%M} PT)")
        if now.hour >= 11:
            text_santino(f"Desert Valley go-live text to Rachelle NOT sent: {NEW} "
                         "still isn't serving our site at 11am. Check the GoDaddy "
                         "nameservers (needs daisy/henry.ns.cloudflare.com).")
            cc.kv_set(GUARD, {"at": datetime.now(timezone.utc).isoformat(),
                              "result": "gave-up-not-live"})
        return 0

    # finish the cutover (stamp + GSC + apex_live); never blocks the text
    r = subprocess.run(["python3", str(ROOT / "scripts" / "cutover_execute.py"),
                        "run", "--slug", "rachelle-elliston", "--apply"],
                       cwd=str(ROOT), capture_output=True, text=True, timeout=1200)
    print((r.stdout + r.stderr)[-1500:])

    both = old_redirects()
    body = BODY_BOTH if both else BODY_NEW_ONLY
    s = subprocess.run(["python3", str(ROOT / "scripts" / "monica_oneoff.py"),
                        "--company", CID, "--body", body, "--context", CONTEXT,
                        "--send"], cwd=str(ROOT), capture_output=True, text=True,
                       timeout=300)
    print(s.stdout[-1500:], s.stderr[-800:])
    if s.returncode != 0:
        text_santino("Desert Valley go-live text to Rachelle FAILED to send "
                     f"(site is live). Exit {s.returncode}; log "
                     "/tmp/rankai-oneshot-desert-valley-golive.log")
    cc.kv_set(GUARD, {"at": datetime.now(timezone.utc).isoformat(),
                      "result": "sent" if s.returncode == 0 else "send-failed",
                      "variant": "both" if both else "new-only"})
    return 0


if __name__ == "__main__":
    sys.exit(main())
