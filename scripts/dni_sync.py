#!/usr/bin/env python3
"""Publish each client's tracking-number map to Cloudflare KV (dni:{slug})
for the site DNI script (source attribution, Santino 2026-09-10).

Truth lives in companies.integration_settings.call_tracking (one entry per
source, written by call_tracking.provision) — this script only DERIVES the
public map. gbp/website stay out of the map: gbp is the profile number and
website is the default already baked into the built site.

Run after provisioning new numbers, or fleet-wide with no args.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from client_ops_sync import _sb, slug_map  # noqa: E402

KV_NS = "404d46bf0c72404495ab66d15157c499"  # 'upload-links'
PUBLIC_SOURCES = ("google_ads", "yelp", "chatgpt", "gemini", "facebook",
                  "instagram", "bing")


def _fmt(num: str) -> str:
    d = re.sub(r"\D", "", num or "")[-10:]
    return f"({d[:3]}) {d[3:6]}-{d[6:]}" if len(d) == 10 else num


def _kv_put(key: str, value: str) -> None:
    acct = os.environ["CLOUDFLARE_ACCOUNT_ID"]
    tok = os.environ["CLOUDFLARE_R2_API_TOKEN"]
    req = urllib.request.Request(
        f"https://api.cloudflare.com/client/v4/accounts/{acct}/storage/kv/"
        f"namespaces/{KV_NS}/values/{key}",
        data=value.encode(), method="PUT",
        headers={"Authorization": f"Bearer {tok}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        if not json.loads(r.read()).get("success"):
            raise RuntimeError(f"KV put failed for {key}")


def sync(only_slug: str | None = None) -> int:
    smap = slug_map()  # {company_id: slug}
    rows = _sb("GET", "/rest/v1/companies?select=id,integration_settings"
               "&integration_settings=not.is.null",
               prefer="return=representation") or []
    published = 0
    for co in rows:
        slug = smap.get(co.get("id"))
        if not slug or (only_slug and slug != only_slug):
            continue
        ints = co.get("integration_settings") or {}
        if isinstance(ints, str):
            try:
                ints = json.loads(ints)
            except Exception:
                continue
        ct = ints.get("call_tracking") or {}
        sources = {}
        for src in PUBLIC_SOURCES:
            num = (ct.get(src) or {}).get("number")
            if num:
                sources[src] = {"raw": num, "fmt": _fmt(num)}
        if not sources:
            continue
        _kv_put(f"dni:{slug}", json.dumps({"sources": sources}))
        print(f"  dni:{slug} -> {len(sources)} sources")
        published += 1
    print(f"==> {published} client map(s) published")
    return 0


if __name__ == "__main__":
    sys.exit(sync(sys.argv[1] if len(sys.argv) > 1 else None))
