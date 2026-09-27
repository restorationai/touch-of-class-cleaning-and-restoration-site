#!/usr/bin/env python3
"""secrets_backup.py — encrypted off-machine backup of the secret files.

Santino 2026-09-06: "if this computer breaks I'd love for them to be stored
somewhere secure." The secrets (.env, Gmail/GSC OAuth tokens) must never sit
in the GitHub repo in plaintext — one leaked commit burns every client
credential at once. This script tars them, encrypts with AES-256 (openssl,
passphrase-derived key via PBKDF2), and uploads the ciphertext to the
PRIVATE R2 bucket. The passphrase lives ONLY in Santino's password manager;
without it the uploaded blob is noise.

Backup:   python3 scripts/secrets_backup.py backup
Restore:  python3 scripts/secrets_backup.py restore [--stamp YYYY-MM-DD]
          (on a fresh machine: needs only this repo + CLOUDFLARE_R2_API_TOKEN
           + CLOUDFLARE_ACCOUNT_ID exported, then the passphrase when asked;
           writes the files back to their real paths.)
List:     python3 scripts/secrets_backup.py list

Passphrase: SECRETS_BACKUP_PASSPHRASE env var, else interactive prompt.
"""
from __future__ import annotations

import argparse
import getpass
import io
import os
import subprocess
import sys
import tarfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")
import requests  # noqa: E402

BUCKET = "rankai-leads-private"   # never publicly served
PREFIX = "secrets-backup"
CF_API = "https://api.cloudflare.com/client/v4"

# The files that make a machine "ours". Paths outside the repo are captured
# with a portable tag so restore can put them back anywhere.
TARGETS = [
    (ROOT / ".env", "repo/.env"),
    (ROOT / ".gsc-agency-token.json", "repo/.gsc-agency-token.json"),
    (Path.home() / ".config" / "rankai" / "gmail_token.json",
     "config/gmail_token.json"),
    (Path.home() / ".config" / "rankai" / "gmail_token_getrestorationai.json",
     "config/gmail_token_getrestorationai.json"),
    # Browser-agent portal credentials (2026-09-06: surfaced as missing on
    # the Mac Mini — anything a fresh machine needs belongs in this list).
    (Path.home() / ".rankai" / "portal-creds.json",
     "rankai/portal-creds.json"),
    (Path.home() / ".rankai" / "domain-creds.key",
     "rankai/domain-creds.key"),
    # 2026-09-27 (Santino: "everything in GitHub, pick up on a new computer"):
    # every remaining gitignored secret + Claude's own config.
    (ROOT / ".gsc-oauth-client.json", "repo/.gsc-oauth-client.json"),
    (ROOT / ".secrets" / "ga4-sa.json", "repo/.secrets/ga4-sa.json"),
    (ROOT / ".secrets" / "geocoding-key", "repo/.secrets/geocoding-key"),
    (ROOT / "kpi-dashboard" / "config.env", "repo/kpi-dashboard/config.env"),
    (Path.home() / ".claude" / "settings.json", "claude/settings.json"),
    (Path.home() / ".claude" / "settings.local.json",
     "claude/settings.local.json"),
]
# Per-client Google Ads OAuth tokens (clients/{slug}/.ads-token.json).
TARGETS += [(p, f"repo/{p.relative_to(ROOT)}")
            for p in sorted(ROOT.glob("clients/*/.ads-token.json"))]


def _headers() -> dict:
    tok = (os.environ.get("CLOUDFLARE_R2_API_TOKEN")
           or os.environ["CLOUDFLARE_API_TOKEN"])
    return {"Authorization": f"Bearer {tok}"}


def _obj_url(key: str) -> str:
    acc = os.environ["CLOUDFLARE_ACCOUNT_ID"]
    return f"{CF_API}/accounts/{acc}/r2/buckets/{BUCKET}/objects/{key}"


def passphrase(confirm: bool) -> str:
    p = os.environ.get("SECRETS_BACKUP_PASSPHRASE")
    if p:
        return p
    # Unattended daily refresh (2026-09-27): the passphrase may live in the
    # macOS login keychain (service rankai-secrets-backup) — never in git or
    # .env. Add once with:
    #   security add-generic-password -a "$USER" -s rankai-secrets-backup -w
    try:
        r = subprocess.run(["security", "find-generic-password", "-s",
                            "rankai-secrets-backup", "-w"],
                           capture_output=True, text=True, timeout=10)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:  # noqa: BLE001 — fall through to interactive prompt
        pass
    p = getpass.getpass("backup passphrase: ")
    if confirm and getpass.getpass("confirm passphrase: ") != p:
        sys.exit("passphrases do not match")
    if len(p) < 12:
        sys.exit("use at least 12 characters")
    return p


def openssl(args: list[str], data: bytes, pw: str) -> bytes:
    r = subprocess.run(["openssl", "enc"] + args +
                       ["-aes-256-cbc", "-pbkdf2", "-iter", "600000",
                        "-salt", "-pass", "env:SB_PASS"],
                       input=data, capture_output=True,
                       env={**os.environ, "SB_PASS": pw})
    if r.returncode != 0:
        sys.exit("openssl failed: " + r.stderr.decode()[:200])
    return r.stdout


def cmd_backup() -> int:
    pw = passphrase(confirm=True)
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for path, arcname in TARGETS:
            if not path.exists():
                print(f"  ! missing (skipped): {path}")
                continue
            tf.add(path, arcname=arcname)
            print(f"  + {arcname}")
    blob = openssl(["-e"], buf.getvalue(), pw)
    key = f"{PREFIX}/{date.today().isoformat()}.tar.gz.enc"
    r = requests.put(_obj_url(key), data=blob,
                     headers={**_headers(),
                              "Content-Type": "application/octet-stream"},
                     timeout=60)
    r.raise_for_status()
    print(f"encrypted backup uploaded: r2://{BUCKET}/{key} ({len(blob)} bytes)")
    # Santino 2026-09-06: "I'd rather [store] in GitHub" — the CIPHERTEXT
    # also lands in the repo (secrets-vault/), so a fresh machine needs only
    # a git clone + the passphrase. Plaintext secrets stay banned from git;
    # this blob without the passphrase is noise. Stable filename so history
    # doesn't accumulate one blob per day.
    vault = ROOT / "secrets-vault" / "vault.tar.gz.enc"
    vault.parent.mkdir(exist_ok=True)
    vault.write_bytes(blob)
    print(f"ciphertext also written to {vault.relative_to(ROOT)} — commit it "
          "to make the GitHub copy current.")
    print("passphrase is NOT stored anywhere — keep it in your password manager.")
    return 0


def cmd_list() -> int:
    acc = os.environ["CLOUDFLARE_ACCOUNT_ID"]
    r = requests.get(f"{CF_API}/accounts/{acc}/r2/buckets/{BUCKET}/objects",
                     params={"prefix": PREFIX + "/"}, headers=_headers(),
                     timeout=30).json()
    for o in r.get("result", []):
        print(f"  {o['key']}  {o.get('size', '?')}B")
    return 0


def cmd_restore(stamp: str | None) -> int:
    # Prefer the in-repo vault (works right after a bare git clone, no
    # Cloudflare credentials needed); R2 remains the dated fallback.
    vault = ROOT / "secrets-vault" / "vault.tar.gz.enc"
    if vault.exists() and not stamp:
        print(f"restoring from in-repo vault {vault.relative_to(ROOT)}")
        blob = vault.read_bytes()
    else:
        key = f"{PREFIX}/{stamp or date.today().isoformat()}.tar.gz.enc"
        r = requests.get(_obj_url(key), headers=_headers(), timeout=60)
        if r.status_code == 404:
            print(f"no backup at {key} — run 'list' to see available stamps")
            return 1
        r.raise_for_status()
        blob = r.content
    pw = passphrase(confirm=False)
    raw = openssl(["-d"], blob, pw)
    by_arc = {arc: path for path, arc in TARGETS}
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tf:
        for m in tf.getmembers():
            dest = by_arc.get(m.name)
            if not dest:
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                print(f"  exists, NOT overwriting: {dest} "
                      "(delete it first if you mean to)")
                continue
            src = tf.extractfile(m)
            dest.write_bytes(src.read())
            dest.chmod(0o600)
            print(f"  restored: {dest}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("backup")
    sub.add_parser("list")
    sp = sub.add_parser("restore")
    sp.add_argument("--stamp", help="YYYY-MM-DD of the backup to restore")
    args = ap.parse_args()
    if args.cmd == "backup":
        return cmd_backup()
    if args.cmd == "list":
        return cmd_list()
    return cmd_restore(args.stamp)


if __name__ == "__main__":
    sys.exit(main())
