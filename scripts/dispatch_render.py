#!/usr/bin/env python3
"""dispatch_render.py — hand a site's pending pages to the cloud renderer.

The dev agent calls this instead of rendering page volume inline (scale-up,
Santino 2026-09-03): after editing a site plan + scaffolding, run

    python3 scripts/dispatch_render.py --slug {slug}

and the site-render workflow renders every pending page with parallel
workers and deploys to the branch the site already lives on. Returns 0 on
a successful dispatch (the render itself completes in the cloud minutes
later). Uses GITHUB_PERSONAL_ACCESS_TOKEN (or GH_PAT / GITHUB_TOKEN).
"""
from __future__ import annotations

import argparse
import os
import sys

import requests

REPO = "restorationai/Rank-AI-Pipeline"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True)
    args = ap.parse_args()
    token = (os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN")
             or os.environ.get("GH_PAT") or os.environ.get("GITHUB_TOKEN"))
    if not token:
        print("dispatch_render: no GitHub token in env")
        return 1
    r = requests.post(
        f"https://api.github.com/repos/{REPO}/actions/workflows/site-render.yml/dispatches",
        headers={"Authorization": f"Bearer {token}",
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "rank-ai-dev-agent"},
        json={"ref": "main", "inputs": {"slug": args.slug}}, timeout=30)
    if r.status_code == 204:
        print(f"dispatch_render: {args.slug} queued — cloud render + deploy "
              "lands in minutes")
        return 0
    print(f"dispatch_render failed ({r.status_code}): {r.text[:140]}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
