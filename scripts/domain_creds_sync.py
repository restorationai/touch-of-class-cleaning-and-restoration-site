#!/usr/bin/env python3
"""Domain credentials sync — the LOCAL half of the encrypted registrar-creds
path (2026-08-03).

Clients who choose the credentials option on the app's "Provide Domain
Access" card post to the `domain-access` edge function, which SEALED-BOX
encrypts {registrar, username, password, notes} with the agency X25519
PUBLIC key and stores only ciphertext in the service-role-only
`domain_credentials` table. Supabase never sees the private key; neither
does any repo.

This script runs on the ops Mac, where the PRIVATE key lives at
~/.rankai/domain-creds.key (0600, generated once, never committed). It
decrypts each unretrieved row into ~/.rankai/portal-creds.json under
"{registrar}:{slug}" — exactly the shape browser_agent/chassis.portal_creds
and the domain_connect playbook already read — then stamps retrieved_at.

Commands:
  sync           decrypt new rows into portal-creds.json (default)
  sync --all     re-decrypt every row, including already-retrieved ones
  init           generate the keypair if missing; print the PUBLIC key to
                 paste into the domain-access edge function
  test           local encrypt/decrypt round-trip with a dummy secret
                 (proves the keypair + envelope format, touches no DB)

Env: SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY (rank-ai/.env).
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
KEY_PATH = Path.home() / ".rankai" / "domain-creds.key"
CREDS_PATH = Path.home() / ".rankai" / "portal-creds.json"


def _sb(method: str, path: str, body=None, prefer: str = "return=representation"):
    url = os.environ["SUPABASE_URL"].rstrip("/") + path
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    r = requests.request(method, url, json=body, timeout=30,
                         headers={"apikey": key,
                                  "Authorization": f"Bearer {key}",
                                  "Content-Type": "application/json",
                                  "Prefer": prefer})
    r.raise_for_status()
    return r.json() if (r.text or "").strip() else None


def _private_key():
    from nacl.public import PrivateKey
    if not KEY_PATH.exists():
        sys.exit(f"No private key at {KEY_PATH} — run: "
                 "python3 scripts/domain_creds_sync.py init")
    return PrivateKey(base64.b64decode(KEY_PATH.read_text().strip()))


def _fingerprint(pub_bytes: bytes) -> str:
    return hashlib.sha256(pub_bytes).hexdigest()[:16]


def cmd_init(_args) -> int:
    from nacl.public import PrivateKey
    if KEY_PATH.exists():
        sk = PrivateKey(base64.b64decode(KEY_PATH.read_text().strip()))
        print(f"Keypair already exists at {KEY_PATH} — reusing.")
    else:
        sk = PrivateKey.generate()
        KEY_PATH.parent.mkdir(exist_ok=True)
        KEY_PATH.write_text(base64.b64encode(bytes(sk)).decode() + "\n")
        os.chmod(KEY_PATH, stat.S_IRUSR | stat.S_IWUSR)
        print(f"Generated keypair; PRIVATE key at {KEY_PATH} (0600). "
              "Never commit it, never upload it.")
    pub = bytes(sk.public_key)
    print(f"PUBLIC key (b64): {base64.b64encode(pub).decode()}")
    print(f"Fingerprint: {_fingerprint(pub)}")
    print("Paste the public key into AGENCY_PUBLIC_KEY_B64 in "
          "app-work/supabase/functions/domain-access/index.ts and redeploy.")
    return 0


def cmd_test(_args) -> int:
    """Round-trip a dummy secret through the exact envelope the edge fn
    produces (libsodium sealed box, base64)."""
    from nacl.public import SealedBox
    sk = _private_key()
    dummy = {"registrar": "godaddy", "username": "dummy@example.com",
             "password": "correct-horse-battery-staple",
             "notes": "round-trip test only"}
    ct = SealedBox(sk.public_key).encrypt(
        json.dumps(dummy).encode())
    ct_b64 = base64.b64encode(ct).decode()
    out = json.loads(SealedBox(sk).decrypt(base64.b64decode(ct_b64)).decode())
    assert out == dummy, f"round-trip mismatch: {out}"
    print(f"OK: sealed-box round-trip verified ({len(ct_b64)} chars "
          f"ciphertext, pubkey fingerprint {_fingerprint(bytes(sk.public_key))}).")
    return 0


def _slug_for(company_id: str, hinted: str | None) -> str | None:
    if hinted:
        return hinted
    try:
        rows = _sb("GET", f"/rest/v1/marketing_sites?company_id=eq.{company_id}"
                   "&select=rank_ai_slug&limit=1") or []
        return (rows[0] if rows else {}).get("rank_ai_slug")
    except Exception:
        return None


def cmd_sync(args) -> int:
    from nacl.public import SealedBox
    sk = _private_key()
    box = SealedBox(sk)
    q = ("/rest/v1/domain_credentials?select=id,company_id,rank_ai_slug,"
         "registrar,account_email,ciphertext,pubkey_fingerprint,created_at,"
         "retrieved_at&order=created_at.asc")
    if not args.all:
        q += "&retrieved_at=is.null"
    rows = _sb("GET", q) or []
    if not rows:
        print("Nothing to sync — no "
              + ("rows at all." if args.all else "unretrieved rows."))
        return 0
    creds = {}
    if CREDS_PATH.exists():
        try:
            creds = json.loads(CREDS_PATH.read_text())
        except json.JSONDecodeError:
            sys.exit(f"{CREDS_PATH} is not valid JSON — fix it by hand first "
                     "(refusing to overwrite).")
    my_fp = _fingerprint(bytes(sk.public_key))
    synced = 0
    for row in rows:
        rid = row["id"]
        if row.get("pubkey_fingerprint") and row["pubkey_fingerprint"] != my_fp:
            print(f"  !! {rid}: encrypted to a DIFFERENT public key "
                  f"({row['pubkey_fingerprint']} vs ours {my_fp}) — skipping")
            continue
        try:
            plain = json.loads(box.decrypt(
                base64.b64decode(row["ciphertext"])).decode())
        except Exception as e:  # noqa: BLE001 — one bad row must not stop the rest
            print(f"  !! {rid}: decrypt failed ({str(e)[:60]}) — skipping")
            continue
        registrar = (plain.get("registrar") or row.get("registrar")
                     or "unknown").strip().lower()
        slug = _slug_for(row["company_id"], row.get("rank_ai_slug"))
        if not slug:
            print(f"  !! {rid}: no slug for {row['company_id']} — skipping")
            continue
        key = f"{registrar}:{slug}"
        creds[key] = {
            "user": plain.get("username") or row.get("account_email") or "",
            "pass": plain.get("password") or "",
            "registrar": registrar,
            "account_email": row.get("account_email")
                             or plain.get("username") or "",
            "notes": plain.get("notes") or "",
            "source": "domain_credentials",
            "cred_id": rid,
        }
        synced += 1
        print(f"  {key}: decrypted -> portal-creds.json "
              f"(submitted {str(row.get('created_at'))[:16]})")
        if not args.dry_run:
            _sb("PATCH", f"/rest/v1/domain_credentials?id=eq.{rid}",
                {"retrieved_at": datetime.now(timezone.utc).isoformat()},
                prefer="return=minimal")
    if synced and not args.dry_run:
        CREDS_PATH.parent.mkdir(exist_ok=True)
        CREDS_PATH.write_text(json.dumps(creds, indent=2) + "\n")
        os.chmod(CREDS_PATH, stat.S_IRUSR | stat.S_IWUSR)
    print(f"{'[dry-run] would sync' if args.dry_run else 'Synced'} "
          f"{synced} credential set(s).")
    return 0


def main() -> int:
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd")
    p_sync = sub.add_parser("sync", help="decrypt new rows into portal-creds")
    p_sync.add_argument("--all", action="store_true",
                        help="re-decrypt already-retrieved rows too")
    p_sync.add_argument("--dry-run", action="store_true")
    sub.add_parser("init", help="generate keypair / print public key")
    sub.add_parser("test", help="local encrypt/decrypt round-trip")
    args = ap.parse_args()
    if args.cmd == "init":
        return cmd_init(args)
    if args.cmd == "test":
        return cmd_test(args)
    if args.cmd is None:
        args = argparse.Namespace(cmd="sync", all=False, dry_run=False)
    return cmd_sync(args)


if __name__ == "__main__":
    sys.exit(main())
