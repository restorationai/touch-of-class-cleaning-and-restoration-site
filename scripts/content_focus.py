#!/usr/bin/env python3
"""content_focus.py — let the client's stated goals actually steer the content.

THE GAP THIS CLOSES (Santino 2026-08-06)
----------------------------------------
"NaRestCo recently said he wants to start ranking more for water damage. Where
in the app can I input that so that the blog posts, YouTube videos, Google posts
are geared around ranking for that?"

The field already existed and was already filled in. companies
.integration_settings.goals is written by the onboarding wizard's Goals step and
editable in the Setup Guide, and NaRestCo's reads:

    {"services": ["Water damage restoration", "fire damage restoration",
                  "mold remediation", "sewage cleanup"], ...}

Nothing read it. Not one line of the pipeline. lib/goals.ts even carries the
comment "so the keyword-plan + geo-grid pipelines can read them" — they never
did. Topic selection came entirely from the ORDER of services in
clients/{slug}/plan-input.json, a file no client can see and only we can edit.
So the answer to "where do I input that" was: nowhere that does anything.

This makes the goals the priority signal. Services named in goals are pulled to
the front of the rotation in the order the client gave them; everything else
keeps its existing relative order behind them. Nothing is dropped — a service
they did not name is deprioritised, never deleted, because a client saying
"more water damage" means "more of that first", not "stop selling fire".

Matching is loose on purpose: goals arrive as prose from a textarea
("Water damage restoration") while plan-input holds slugs
("water-damage-restoration").
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLIENTS_DIR = ROOT / "clients"


def _norm(s: str) -> str:
    """'Water damage restoration' and 'water-damage-restoration' -> same key."""
    return re.sub(r"[^a-z0-9]+", " ", str(s or "").lower()).strip()


def _company_id_for(slug: str) -> str | None:
    rec = CLIENTS_DIR / f"{slug}.json"
    if rec.exists():
        try:
            cid = json.loads(rec.read_text()).get("company_id")
            if cid:
                return cid
        except Exception:
            pass
    cmap = CLIENTS_DIR / "company_map.json"
    if cmap.exists():
        try:
            return json.loads(cmap.read_text()).get(slug)
        except Exception:
            pass
    return None


def goal_services(slug: str) -> list:
    """The services this client asked us to focus on, in their order. [] if none."""
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    cid = _company_id_for(slug)
    if not (url and key and cid):
        return []
    req = urllib.request.Request(
        f"{url}/rest/v1/companies?select=integration_settings&id=eq.{cid}",
        headers={"apikey": key, "Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            rows = json.load(r)
    except Exception:
        return []
    if not rows:
        return []
    goals = ((rows[0].get("integration_settings") or {}).get("goals") or {})
    svcs = goals.get("services")
    return [s for s in svcs if str(s).strip()] if isinstance(svcs, list) else []


def prioritise(slug: str, services: list, quiet: bool = False) -> list:
    """Reorder `services` so the client's stated focus leads.

    Stable: goal-named services come first in the client's own order, the rest
    follow in their existing order. Never drops anything.
    """
    goals = goal_services(slug)
    if not goals or not services:
        return services
    want = [_norm(g) for g in goals]
    ranked = sorted(
        range(len(services)),
        key=lambda i: (want.index(_norm(services[i])) if _norm(services[i]) in want else len(want), i),
    )
    out = [services[i] for i in ranked]
    if not quiet and out != services:
        lead = ", ".join(str(s) for s in out[:3])
        print(f"  [focus] {slug}: client goals put {lead} first "
              f"(was {', '.join(str(s) for s in services[:3])})")
    return out


if __name__ == "__main__":
    import sys
    slug = sys.argv[1]
    pi = json.loads((CLIENTS_DIR / slug / "plan-input.json").read_text())
    svc = pi.get("services") or []
    print("goals   :", goal_services(slug))
    print("before  :", svc[:6])
    print("after   :", prioritise(slug, svc, quiet=True)[:6])
