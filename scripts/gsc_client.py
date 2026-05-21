#!/usr/bin/env python3
"""
Rank AI — Google Search Console client (agency model).

One OAuth token for contact@restorationai.io, stored at
`rank-ai/.gsc-agency-token.json` (gitignored). Works for every client
property where the agency email has been added as a GSC user — no per-client
setup beyond:
  1. Run `python3 scripts/gsc_setup.py` once (agency OAuth flow)
  2. Client adds contact@restorationai.io to their GSC property as Full user
  3. Add `"gsc_property_url": "sc-domain:{domain}"` to clients/{slug}.json
     (optional — omit to use the default sc-domain:{domain} derived from domain)

GSC property URL formats:
  sc-domain:example.com          — domain property (all subdomains + protocols, preferred)
  https://www.example.com/       — URL-prefix property (legacy)

This module is structured so v2 is a single activation per agency account.
`GSCClient.is_configured(slug)` returns True once the agency token and client
domain are present — no per-client OAuth flow needed. Until then it returns
False and System 4 operates in sitemap-only v1 mode.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

OAUTH_CLIENT_PATH  = ROOT / ".gsc-oauth-client.json"
AGENCY_TOKEN_PATH  = ROOT / ".gsc-agency-token.json"
SCOPES             = ["https://www.googleapis.com/auth/webmasters.readonly"]


class GSCClient:
    """Thin wrapper around google-api-python-client for URL Inspection.

    Uses a single agency-level OAuth token for all clients. Lazy-imports
    google libraries so System 4 v1 (sitemap-only) runs without them.
    """

    def __init__(self, slug: str, domain: str, property_url: str | None = None):
        self.slug = slug
        self.domain = domain
        # Allow explicit override; default to domain property format
        self.site_url = property_url or f"sc-domain:{domain}"
        self._service = None

    @classmethod
    def is_configured(cls, slug: str) -> bool:
        """True when the agency token exists and the client record has a domain.

        Does not verify that the agency account actually has access to this
        client's GSC property — that surfaces as an error on the first inspect()
        call with a clear message.
        """
        if not AGENCY_TOKEN_PATH.exists():
            return False
        client_record = ROOT / "clients" / f"{slug}.json"
        if not client_record.exists():
            return False
        try:
            c = json.loads(client_record.read_text())
            return bool(c.get("domain"))
        except Exception:
            return False

    def _ensure_service(self):
        if self._service is not None:
            return self._service

        if not AGENCY_TOKEN_PATH.exists():
            raise RuntimeError(
                f"Agency GSC token not found at {AGENCY_TOKEN_PATH}. "
                f"Run: python3 scripts/gsc_setup.py"
            )

        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build
        except ImportError as e:
            raise RuntimeError(
                "GSC deps missing. Run: pip install google-auth google-auth-oauthlib "
                "google-api-python-client"
            ) from e

        token_data = json.loads(AGENCY_TOKEN_PATH.read_text())
        creds = Credentials(
            token=token_data.get("token"),
            refresh_token=token_data["refresh_token"],
            token_uri="https://oauth2.googleapis.com/token",
            client_id=token_data["client_id"],
            client_secret=token_data["client_secret"],
            scopes=SCOPES,
        )

        if not creds.valid:
            creds.refresh(Request())
            token_data["token"] = creds.token
            AGENCY_TOKEN_PATH.write_text(json.dumps(token_data, indent=2))

        self._service = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
        return self._service

    def inspect(self, url: str) -> dict | None:
        """Inspect one URL via the GSC URL Inspection API.

        Returns a normalized dict on success, None on permanent failure.
        Raises on transient errors — caller decides on retry.
        """
        try:
            service = self._ensure_service()
        except RuntimeError as e:
            sys.stderr.write(f"GSCClient.inspect skipped ({self.slug}): {e}\n")
            return None

        try:
            result = service.urlInspection().index().inspect(
                body={"inspectionUrl": url, "siteUrl": self.site_url}
            ).execute()
        except Exception as e:
            msg = str(e)
            if "403" in msg or "does not have permission" in msg.lower():
                sys.stderr.write(
                    f"GSC 403 for {self.slug}: agency account may not have access to "
                    f"{self.site_url}. Ask the client to add contact@restorationai.io "
                    f"as a Full user in GSC Settings > Users and permissions.\n"
                )
                return None
            raise

        idx = result.get("inspectionResult", {}).get("indexStatusResult", {})
        verdict = idx.get("verdict", "VERDICT_UNSPECIFIED")

        status_map = {"PASS": "PASS", "PARTIAL": "PARTIAL", "FAIL": "FAIL"}
        return {
            "index_status":   status_map.get(verdict, "UNKNOWN"),
            "coverage_state": idx.get("coverageState", ""),
            "last_crawl_time": idx.get("lastCrawlTime"),
            "fetched_at":     _now_iso(),
        }

    @classmethod
    def from_client_record(cls, slug: str) -> "GSCClient":
        """Construct from a client JSON record. Reads domain + optional gsc_property_url."""
        record_path = ROOT / "clients" / f"{slug}.json"
        c = json.loads(record_path.read_text())
        return cls(
            slug=slug,
            domain=c["domain"],
            property_url=c.get("gsc_property_url"),
        )


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
