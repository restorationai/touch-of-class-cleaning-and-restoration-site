#!/usr/bin/env python3
"""
Rank AI — Google Search Console client wrapper.

Wraps the GSC URL Inspection API for use by System 4 (refresh_scorer). Per
client we store an OAuth token at `clients/{slug}/.gsc-token.json` (gitignored).
The OAuth flow + initial token grant is handled by `scripts/gsc_setup.py` — a
one-time per-client setup. After that, this client refreshes its access token
automatically using the stored refresh token.

This module is structured so that v2 activation is a single env-var flip:
once `rank-ai/.gsc-oauth-client.json` (the OAuth client secret JSON) AND a
per-client `clients/{slug}/.gsc-token.json` exist, `GSCClient.is_configured()`
returns True and `inspect()` returns real data. Until then it returns None
and System 4 Layer 1 operates in sitemap-only v1 mode.

See `docs/system-4-v2-activation.md` for the full setup walkthrough.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

OAUTH_CLIENT_PATH = ROOT / ".gsc-oauth-client.json"
SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]


def per_client_token_path(slug: str) -> Path:
    return ROOT / "clients" / slug / ".gsc-token.json"


class GSCClient:
    """Thin wrapper around google-api-python-client for URL Inspection.

    Construct one per client. Reuses the access token across calls within the
    same process. Lazy-imports google libraries so the rest of System 4 can run
    without them installed (v1 sitemap-only mode).
    """

    def __init__(self, slug: str, domain: str):
        self.slug = slug
        self.domain = domain
        self.site_url = f"sc-domain:{domain}"  # GSC "domain property" form
        self._service = None
        self._creds = None

    @classmethod
    def is_configured(cls, slug: str) -> bool:
        """Cheap check: do BOTH the OAuth client secret AND the per-client token exist?"""
        return OAUTH_CLIENT_PATH.exists() and per_client_token_path(slug).exists()

    def _ensure_service(self):
        """Lazy import + auth. Raises RuntimeError with a helpful message if not configured."""
        if self._service is not None:
            return self._service
        if not OAUTH_CLIENT_PATH.exists():
            raise RuntimeError(
                f"OAuth client secret not found at {OAUTH_CLIENT_PATH}. "
                f"Run the v2 activation steps in docs/system-4-v2-activation.md."
            )
        token_path = per_client_token_path(self.slug)
        if not token_path.exists():
            raise RuntimeError(
                f"GSC token not found for {self.slug} at {token_path}. "
                f"Run: python3 scripts/gsc_setup.py --slug {self.slug}"
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

        token_data = json.loads(token_path.read_text())
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
            # Persist refreshed access token
            token_data["token"] = creds.token
            token_path.write_text(json.dumps(token_data, indent=2))

        self._creds = creds
        self._service = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
        return self._service

    def inspect(self, url: str) -> dict | None:
        """Inspect one URL via GSC URL Inspection API.

        Returns a normalized dict (matching the schema the v2 spec expects), or
        None on permanent failure. Transient errors raise — caller decides retry.
        """
        try:
            service = self._ensure_service()
        except RuntimeError as e:
            sys.stderr.write(f"GSCClient.inspect skipped: {e}\n")
            return None

        body = {"inspectionUrl": url, "siteUrl": self.site_url}
        result = service.urlInspection().index().inspect(body=body).execute()

        idx = result.get("inspectionResult", {}).get("indexStatusResult", {})
        verdict = idx.get("verdict", "VERDICT_UNSPECIFIED")
        coverage_state = idx.get("coverageState", "")
        last_crawl = idx.get("lastCrawlTime")

        if verdict == "PASS":
            index_status = "PASS"
        elif verdict == "PARTIAL":
            index_status = "PARTIAL"
        elif verdict == "FAIL":
            index_status = "FAIL"
        else:
            index_status = "UNKNOWN"

        return {
            "index_status": index_status,
            "coverage_state": coverage_state,
            "last_crawl_time": last_crawl,
            "fetched_at": _now_iso(),
        }


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
