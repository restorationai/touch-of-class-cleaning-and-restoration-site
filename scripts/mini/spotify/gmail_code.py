"""Read the contact@restorationai.io inbox for a directory's ownership code.
Read-only Gmail (messages.list/get). Token ~/.config/rankai/gmail_token.json,
OAuth client from rank-ai/.env. Santino 2026-09-09: the agency inbox is the
owner address on every podcast feed, so codes always land here."""
import base64, json, re, sys, time, urllib.parse, urllib.request
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "CLAUDE.md").exists())  # repo root


def _env():
    env = {}
    for line in (ROOT / ".env").read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def access_token():
    env = _env()
    t = json.loads((Path.home() / ".config" / "rankai" / "gmail_token.json").read_text())
    data = urllib.parse.urlencode({
        "client_id": env["GOOGLE_OAUTH_CLIENT_ID"],
        "client_secret": env["GOOGLE_OAUTH_CLIENT_SECRET"],
        "refresh_token": t["refresh_token"], "grant_type": "refresh_token"}).encode()
    return json.load(urllib.request.urlopen("https://oauth2.googleapis.com/token", data, timeout=20))["access_token"]


def get(tok, path):
    req = urllib.request.Request("https://gmail.googleapis.com/gmail/v1/users/me/" + path,
                                 headers={"Authorization": "Bearer " + tok})
    return json.load(urllib.request.urlopen(req, timeout=30))


def body_text(payload) -> str:
    out = []

    def walk(p):
        d = (p.get("body") or {}).get("data")
        if d:
            out.append(base64.urlsafe_b64decode(d + "===").decode("utf-8", "ignore"))
        for c in p.get("parts") or []:
            walk(c)
    walk(payload)
    return re.sub(r"<[^>]+>", " ", "\n".join(out))


def list_recent(sender="spotify", days=14, n=5):
    tok = access_token()
    q = urllib.parse.quote(f"from:{sender} newer_than:{days}d")
    ids = [m["id"] for m in (get(tok, f"messages?q={q}&maxResults={n}").get("messages") or [])]
    rows = []
    for mid in ids:
        m = get(tok, f"messages/{mid}?format=metadata&metadataHeaders=Subject&metadataHeaders=From&metadataHeaders=Date")
        h = {x["name"]: x["value"] for x in m["payload"]["headers"]}
        rows.append((h.get("Date", "?")[:25], h.get("From", "?")[:45], h.get("Subject", "?")[:70], mid))
    return rows


def find_code(after_epoch: int, sender="spotify", digits=8, timeout_s=600, every=15):
    """Newest matching mail received at/after after_epoch; returns (code, subject)."""
    q = urllib.parse.quote(f"from:{sender} after:{after_epoch - 120}")
    deadline = time.time() + timeout_s
    seen = set()
    while time.time() < deadline:
        tok = access_token()
        for mid in [m["id"] for m in (get(tok, f"messages?q={q}&maxResults=5").get("messages") or [])]:
            if mid in seen:
                continue
            seen.add(mid)
            msg = get(tok, f"messages/{mid}?format=full")
            hdr = {h["name"].lower(): h["value"] for h in msg["payload"].get("headers", [])}
            ts = int(msg.get("internalDate", "0")) // 1000
            text = body_text(msg["payload"])
            m = re.search(r"(?<!\d)(\d{%d})(?!\d)" % digits, text)
            print(f"  mail {hdr.get('from', '?')[:40]} | {hdr.get('subject', '?')[:60]} | ts={ts} | code={'yes' if m else 'no'}")
            if m and ts >= after_epoch - 120:
                return m.group(1), hdr.get("subject", "")
        time.sleep(every)
    return None, None


if __name__ == "__main__":
    tok = access_token()
    print("mailbox:", get(tok, "profile")["emailAddress"])
    for r in list_recent(*(sys.argv[1:2] or ["spotify"])):
        print("  ", " | ".join(r[:3]))
