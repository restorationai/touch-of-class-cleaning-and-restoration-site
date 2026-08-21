#!/usr/bin/env python3
"""Mint a Gmail refresh token for one of OUR mailboxes (Monica email
evolution 2c, 2026-08-20: contact@getrestorationai.com joins the email
intake so client mail to the sales-era inbox stops being invisible).

Same flow email_intake.py's `auth` uses: localhost:5173/connect/google/
callback is a registered redirect URI on the shared OAuth client. The
app-work vite dev server normally owns port 5173 — stop it first, restart
it after (this script refuses to start if the port is taken).

SAFETY: after the exchange, the Gmail profile is fetched and the signed-in
address must MATCH --account, or the token is discarded — a sign-in with
the wrong Google account can never be stored under the wrong name.

Usage:
  set -a && source .env && set +a
  python3 scripts/gmail_auth_bootstrap.py --account contact@getrestorationai.com
  # a browser tab opens; sign in AS THAT ACCOUNT and approve

Prints the token JSON path plus the compact JSON for the CI secret.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

SCOPE = "https://www.googleapis.com/auth/gmail.modify"
REDIRECT_PORT = 5173
REDIRECT = f"http://localhost:{REDIRECT_PORT}/connect/google/callback"


def _http(url: str, data: bytes | None = None, headers: dict | None = None) -> dict:
    req = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode() or "{}")


def default_token_path(account: str) -> Path:
    domain = account.split("@", 1)[1]
    stem = domain.rsplit(".", 1)[0].replace(".", "-")
    return Path.home() / ".config" / "rankai" / f"gmail_token_{stem}.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--account", required=True,
                    help="the mailbox to sign in as (login_hint + verified)")
    ap.add_argument("--out", help="token path (default derived from account)")
    args = ap.parse_args()
    out_path = Path(args.out) if args.out else default_token_path(args.account)

    try:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).parent.parent / ".env")
    except Exception:  # noqa: BLE001
        pass
    cid = os.environ["GOOGLE_OAUTH_CLIENT_ID"]
    secret = os.environ["GOOGLE_OAUTH_CLIENT_SECRET"]

    import http.server
    import socketserver
    import webbrowser

    auth_url = ("https://accounts.google.com/o/oauth2/v2/auth?"
                + urllib.parse.urlencode({
                    "client_id": cid, "redirect_uri": REDIRECT,
                    "response_type": "code", "scope": SCOPE,
                    "access_type": "offline", "prompt": "consent",
                    "login_hint": args.account}))
    code_holder: dict = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            code_holder["code"] = (q.get("code") or [""])[0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Done - you can close this tab.")

        def log_message(self, *a):
            pass

    print(f"Sign in as {args.account} in the tab this opens:\n{auth_url}\n")
    webbrowser.open(auth_url)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", REDIRECT_PORT), H) as httpd:
        while not code_holder.get("code"):
            httpd.handle_request()

    tok = _http("https://oauth2.googleapis.com/token",
                data=urllib.parse.urlencode({
                    "code": code_holder["code"], "client_id": cid,
                    "client_secret": secret, "redirect_uri": REDIRECT,
                    "grant_type": "authorization_code"}).encode(),
                headers={"Content-Type": "application/x-www-form-urlencoded"})
    if "refresh_token" not in tok:
        print(f"ERROR: no refresh_token in response: {tok}", file=sys.stderr)
        return 1

    # THE ACCOUNT CHECK: whoever actually signed in is who we verify.
    prof = _http("https://gmail.googleapis.com/gmail/v1/users/me/profile",
                 headers={"Authorization": f"Bearer {tok['access_token']}"})
    got = (prof.get("emailAddress") or "").lower()
    if got != args.account.lower():
        print(f"ERROR: signed in as {got!r}, expected {args.account!r} — "
              "token DISCARDED. Re-run and pick the right account.",
              file=sys.stderr)
        return 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(tok))
    out_path.chmod(0o600)
    print(f"Verified {got}. Refresh token stored at {out_path}")
    print("\nCI secret value (single line):")
    print(json.dumps({"refresh_token": tok["refresh_token"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
