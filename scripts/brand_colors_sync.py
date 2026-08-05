#!/usr/bin/env python3
"""brand_colors_sync.py — publish a client's real brand colours INTO the app.

THE BUG THIS CLOSES
-------------------
Brand colour had exactly one direction of travel:

    app DB  companies.integration_settings.brand.{primary,secondary}_color
       │    (site_brief_build.py)
       ▼
    clients/{slug}/plan-input.json  brand.{primary,accent}_color
       │    (build_site.py resolve_tokens)
       ▼
    sites/{slug}/tailwind.config.mjs + public/favicon.svg

Everything we LEARN downstream of that arrow — a franchise brand guide, a
palette sampled off the client's logo, a hand-set hex — died in the repo.
Nothing wrote back. So PuroClean's official #D12229 (PuroClean Brand Identity
Guide 2022 p18) reached their live site while the app's Site Build card still
showed the old #c50a1d guess, and `companies.widget_primary_color` sat on its
factory default #ef4444 for all 21 clients — a red the chat widget shows every
client regardless of their actual brand.

This script is the return arrow. It reads the canonical colour out of
plan-input.json and writes it to BOTH places the app reads:
  * companies.integration_settings.brand.primary_color / .secondary_color
    (the two swatches on the Site Build card)
  * companies.widget_primary_color (the chat widget / review redirector theme)

PRECEDENCE — who wins when the two disagree
-------------------------------------------
The app is where a CLIENT expresses a preference, so by default the app wins
and we only backfill what is empty or still factory-default. We never silently
overwrite a colour a human picked in the UI; a divergence is reported instead.

The exception is a LOCKED colour — one we hold on documented authority, e.g. a
franchise brand guide (`brand.brand_kit`) or a logo sample signed off by an
operator. Locked colours are law: they overwrite the app, and site_brief_build
refuses to let an app pick displace them on the next build. The lock is
recorded in plan-input as brand.color_locked / brand.color_source so both ends
of the pipeline can see it.

Usage
-----
    python3 scripts/brand_colors_sync.py --audit            # fleet report, no writes
    python3 scripts/brand_colors_sync.py --slug puroclean-east-las-vegas --apply
    python3 scripts/brand_colors_sync.py --all --apply
    python3 scripts/brand_colors_sync.py --slug reign-restoration --lock --apply

Also called automatically at the end of build_site.py sync-deploy, so shipping
a site republishes its colours to the app.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLIENTS = ROOT / "clients"

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

import requests  # noqa: E402

UA = "rank-ai-brand-colors-sync/1.0"

# The chat widget's factory default (companies.widget_primary_color DEFAULT in
# 20260613145642_remote_schema.sql). Anything still sitting on this value has
# never been deliberately chosen, so we are free to replace it with the
# client's real brand colour.
WIDGET_FACTORY_DEFAULT = "#ef4444"

# build_site.DEFAULTS["BRAND_PRIMARY_COLOR"] — the scaffold's stand-in red. A
# plan-input carrying this is NOT a real brand colour, it is an unanswered
# question, and syncing it to the app would launder a placeholder into a
# client-visible setting.
SCAFFOLD_DEFAULT_PRIMARY = "#dc2626"
# build_site.DEFAULTS["BRAND_DARK_COLOR"] — same reasoning for the page-dark.
SCAFFOLD_DEFAULT_DARK = "#111827"


def _sb(method: str, path: str, body=None, prefer: str = "return=representation"):
    url = os.environ["SUPABASE_URL"].rstrip("/") + path
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    resp = requests.request(method, url, json=body, timeout=30, headers={
        "apikey": key, "Authorization": f"Bearer {key}",
        "Content-Type": "application/json", "Prefer": prefer, "User-Agent": UA,
    })
    resp.raise_for_status()
    return resp.json() if resp.content else None


def _norm(hex_str) -> str:
    """Lowercased #rrggbb, or '' — so #D12229 and #d12229 compare equal."""
    h = (hex_str or "").strip()
    if not h:
        return ""
    if not h.startswith("#"):
        h = "#" + h
    return h.lower()


def company_id_for(slug: str) -> str | None:
    rec_path = CLIENTS / f"{slug}.json"
    if rec_path.exists():
        cid = (json.loads(rec_path.read_text()) or {}).get("company_id")
        if cid:
            return cid
    try:
        cmap = json.loads((CLIENTS / "company_map.json").read_text())
        v = cmap.get(slug)
        return v if isinstance(v, str) else None
    except Exception:
        return None


def canonical_colors(slug: str) -> dict:
    """The colours the repo believes are true for this client.

    Priority for the primary:
      1. brand.brand_kit.primary_colors — a real brand guide (franchise manual,
         style sheet). Authoritative, and implies a lock.
      2. brand.primary_color — hand-set or app-sourced.

    The secondary/accent falls back to brand.dark_color, which is where a
    near-black second brand colour lives on dark-theme clients (Reign)."""
    pi_path = CLIENTS / slug / "plan-input.json"
    if not pi_path.exists():
        return {}
    brand = (json.loads(pi_path.read_text()) or {}).get("brand") or {}
    kit = brand.get("brand_kit") or {}

    primary = secondary = ""
    source = ""
    locked = bool(brand.get("color_locked"))

    kit_primaries = kit.get("primary_colors") or {}
    if isinstance(kit_primaries, dict) and kit_primaries:
        # Brand guides list colours in priority order; the first is the mark.
        ordered = [v for v in kit_primaries.values() if isinstance(v, dict) and v.get("hex")]
        if ordered:
            primary = ordered[0]["hex"]
            if len(ordered) > 1:
                secondary = ordered[1]["hex"]
            source = "brand-kit"
            locked = True

    if not primary:
        primary = brand.get("primary_color") or ""
        source = brand.get("color_source") or ("plan-input" if primary else "")
    if not secondary:
        secondary = brand.get("accent_color") or brand.get("secondary_color") or ""
    if not secondary:
        # A deliberate near-black second brand colour lives in dark_color on
        # dark-theme clients (Reign's #0a0b0e). Only borrow it when it differs
        # from the scaffold's stock dark — otherwise we would publish a
        # template default into a client-visible swatch.
        dark = brand.get("dark_color") or ""
        if _norm(dark) and _norm(dark) != SCAFFOLD_DEFAULT_DARK:
            secondary = dark
    # A second swatch identical to the first tells the client nothing.
    if _norm(secondary) == _norm(primary):
        secondary = ""

    return {
        "primary": _norm(primary),
        "secondary": _norm(secondary),
        "source": source,
        "locked": locked,
        "theme": brand.get("theme") or "light",
        # Preserve the exact casing the brand guide uses for the report.
        "primary_raw": (primary or "").strip(),
        "secondary_raw": (secondary or "").strip(),
    }


_TW_BLOCK = None


def site_tailwind_colors(slug: str) -> dict:
    """What the client's BUILT site actually paints with.

    A third storage location, and the one that wins in the browser. Normally it
    is generated from plan-input, but several sites were hand-tuned directly
    (contrast fixes, logo sampling) and never had the value written back — so
    the audit reads it to surface exactly that drift. Deliberately NOT used as
    a sync source: on some sites primary.DEFAULT is a UI near-black and the
    brand hue lives in `accent`, so publishing it blindly would tell a client
    their brand colour is charcoal."""
    import re
    f = ROOT / "sites" / slug / "tailwind.config.mjs"
    if not f.exists():
        return {}
    txt = f.read_text()
    out = {}
    for name in ("primary", "accent", "dark"):
        # Colour blocks never nest braces, so [^}]* is an exact block match —
        # a bounded `.{0,N}?` silently missed the blocks carrying the long
        # contrast-rationale comments (Reign, TRG).
        m = re.search(r'\b"?' + name + r'"?:\s*\{([^}]*)\}', txt, re.S)
        if not m:
            continue
        d = re.search(r'"?DEFAULT"?:\s*"(#[0-9a-fA-F]{3,8})"', m.group(1))
        if d:
            out[name] = _norm(d.group(1))
    return out


def app_colors(cid: str) -> dict:
    rows = _sb("GET", f"/rest/v1/companies?id=eq.{cid}"
                      "&select=id,name,widget_primary_color,integration_settings")
    if not rows:
        return {}
    row = rows[0]
    ints = row.get("integration_settings") or {}
    if isinstance(ints, str):
        try:
            ints = json.loads(ints)
        except Exception:
            ints = {}
    brand = ints.get("brand") or {}
    return {
        "name": row.get("name"),
        "primary": _norm(brand.get("primary_color")),
        "secondary": _norm(brand.get("secondary_color")),
        "widget": _norm(row.get("widget_primary_color")),
        "_ints": ints,
    }


def plan(slug: str) -> dict:
    """Decide what (if anything) to write for one client. No side effects."""
    cid = company_id_for(slug)
    out = {"slug": slug, "company_id": cid, "actions": [], "notes": []}
    if not cid:
        out["notes"].append("no company_id — not in the app")
        return out
    repo = canonical_colors(slug)
    out["repo"] = repo
    if not repo:
        out["notes"].append("no plan-input.json")
        return out
    if not repo["primary"]:
        out["notes"].append("no brand colour on file — running the scaffold default")
        return out
    if repo["primary"] == SCAFFOLD_DEFAULT_PRIMARY and not repo["locked"]:
        out["notes"].append(f"plan-input primary is the scaffold placeholder "
                            f"{SCAFFOLD_DEFAULT_PRIMARY} — not a real brand colour, "
                            f"refusing to publish it")
        return out

    app = app_colors(cid)
    out["app"] = app
    if not app:
        out["notes"].append(f"company row {cid} missing")
        return out

    # --- primary / secondary on the Site Build card -------------------------
    if not app["primary"]:
        out["actions"].append(("brand.primary_color", app["primary"], repo["primary"], "backfill"))
    elif app["primary"] != repo["primary"]:
        if repo["locked"]:
            out["actions"].append(("brand.primary_color", app["primary"], repo["primary"],
                                   f"locked:{repo['source']}"))
        else:
            out["notes"].append(f"DIVERGED primary: app {app['primary']} vs repo "
                                f"{repo['primary']} — app pick wins, left alone "
                                f"(use --lock to make the repo value authoritative)")

    if repo["secondary"]:
        if not app["secondary"]:
            out["actions"].append(("brand.secondary_color", app["secondary"],
                                   repo["secondary"], "backfill"))
        elif app["secondary"] != repo["secondary"] and repo["locked"]:
            out["actions"].append(("brand.secondary_color", app["secondary"],
                                   repo["secondary"], f"locked:{repo['source']}"))
        elif app["secondary"] != repo["secondary"]:
            out["notes"].append(f"diverged secondary: app {app['secondary']} vs repo "
                                f"{repo['secondary']} — app wins, left alone")

    # --- chat widget theme --------------------------------------------------
    # Only claim the widget colour while it is still the factory red (i.e. never
    # deliberately set) or when we hold an authoritative palette. A widget
    # colour someone chose on purpose is left exactly as it is.
    if app["widget"] != repo["primary"]:
        if app["widget"] in ("", WIDGET_FACTORY_DEFAULT) or repo["locked"]:
            out["actions"].append(("widget_primary_color", app["widget"],
                                   repo["primary"], "factory-default"
                                   if app["widget"] in ("", WIDGET_FACTORY_DEFAULT)
                                   else f"locked:{repo['source']}"))
        else:
            out["notes"].append(f"widget colour {app['widget']} was deliberately set — "
                                f"not replaced with {repo['primary']}")
    return out


def push_colors(slug: str, apply: bool = False, lock: bool = False) -> dict:
    """Plan + optionally write. Returns the plan dict (with 'applied' set)."""
    if lock:
        _set_lock(slug)
    p = plan(slug)
    p["applied"] = False
    if not apply or not p.get("actions"):
        return p

    cid = p["company_id"]
    app = p["app"]
    repo = p["repo"]
    ints = dict(app["_ints"] or {})
    body: dict = {}

    brand_updates = {k: new for k, _old, new, _why in p["actions"] if k.startswith("brand.")}
    if brand_updates:
        # Read-modify-write on the jsonb blob, spreading the existing brand
        # object so fonts / brand-guide pointers written by BrandKitFields
        # survive. (The app's own save() assigns brand wholesale — see the
        # matching fix in components/BrandKitFields.tsx.)
        brand = dict(ints.get("brand") or {})
        for k, v in brand_updates.items():
            brand[k.split(".", 1)[1]] = v
        brand["color_source"] = repo["source"] or "rank-ai"
        brand["color_locked"] = bool(repo["locked"])
        ints["brand"] = brand
        body["integration_settings"] = ints

    for k, _old, new, _why in p["actions"]:
        if k == "widget_primary_color":
            body["widget_primary_color"] = new

    if body:
        _sb("PATCH", f"/rest/v1/companies?id=eq.{cid}", body, prefer="return=minimal")
        p["applied"] = True

    # Mirror the lock into plan-input so the next site_brief_build honours it.
    if repo["locked"]:
        _set_lock(slug, source=repo["source"])
    return p


def _json_style(text: str) -> tuple[int, bool]:
    """Sniff a JSON file's existing indent + whether it escapes non-ASCII.

    clients/*/plan-input.json is written by several scripts that disagree
    (indent=1 vs 2, escaped vs literal em dashes). Reformatting a file to add
    two keys rewrites all ~320 lines and buries the real change, so match
    whatever the file already does."""
    indent = 2
    for line in text.splitlines()[1:]:
        stripped = line.lstrip(" ")
        if stripped and stripped != line:
            indent = len(line) - len(stripped)
            break
    return indent, ("\\u" in text)


def _set_lock(slug: str, source: str = "") -> None:
    """Record brand.color_locked / color_source in plan-input.json."""
    pi_path = CLIENTS / slug / "plan-input.json"
    if not pi_path.exists():
        return
    raw = pi_path.read_text()
    indent, escaped = _json_style(raw)
    pi = json.loads(raw)
    brand = pi.setdefault("brand", {})
    changed = False
    if not brand.get("color_locked"):
        brand["color_locked"] = True
        changed = True
    src = source or brand.get("color_source") or "operator"
    if brand.get("color_source") != src:
        brand["color_source"] = src
        changed = True
    if changed:
        pi_path.write_text(json.dumps(pi, indent=indent, ensure_ascii=escaped) + "\n")


def all_slugs() -> list[str]:
    out = []
    for p in sorted(CLIENTS.glob("*.json")):
        if p.name == "company_map.json":
            continue
        try:
            d = json.loads(p.read_text())
        except Exception:
            continue
        if isinstance(d, dict) and d.get("slug"):
            out.append(d["slug"])
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--slug")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--audit", action="store_true",
                    help="Fleet report of every client's colour state. Never writes.")
    ap.add_argument("--apply", action="store_true", help="Actually write to the app DB")
    ap.add_argument("--lock", action="store_true",
                    help="Mark this client's plan-input colours authoritative "
                         "(they then overwrite the app and survive app picks)")
    args = ap.parse_args()

    if args.audit or not (args.slug or args.all):
        slugs = all_slugs()
        print(f"{'slug':34} {'plan-input':10} {'site':10} {'app':9} {'widget':9} {'lock':5} state")
        wrong = []
        for s in slugs:
            p = plan(s)
            repo = p.get("repo") or {}
            app = p.get("app") or {}
            tw = site_tailwind_colors(s)
            state = "; ".join(p["notes"]) or (
                "PENDING: " + ", ".join(f"{k}->{new}" for k, _o, new, _w in p["actions"])
                if p["actions"] else "in sync")
            # The site is the only surface a visitor sees; flag when it paints
            # something the repo never recorded (hand-edited tailwind).
            if tw.get("primary") and repo.get("primary") and tw["primary"] != repo["primary"]:
                state = f"site paints {tw['primary']} (hand-tuned); " + state
            elif tw.get("primary") and not repo.get("primary"):
                state = (f"site paints {tw['primary']}"
                         + (f"/accent {tw['accent']}" if tw.get("accent") else "")
                         + " but plan-input has NO colour — hand-edited tailwind, "
                           "invisible to the app; " + state)
            print(f"{s:34} {repo.get('primary','') or '-':10} {tw.get('primary','') or '-':10} "
                  f"{app.get('primary','') or '-':9} {app.get('widget','') or '-':9} "
                  f"{'yes' if repo.get('locked') else '-':5} {state}")
            if p["actions"] or p["notes"]:
                wrong.append(s)
        print(f"\n{len(wrong)}/{len(slugs)} clients need attention.")
        return 0

    slugs = [args.slug] if args.slug else all_slugs()
    rc = 0
    for s in slugs:
        p = push_colors(s, apply=args.apply, lock=args.lock)
        head = f"{s}:"
        if p.get("actions"):
            for k, old, new, why in p["actions"]:
                print(f"  {head} {k}: {old or '(empty)'} -> {new}  [{why}]"
                      f"{'' if p['applied'] else '  (dry run, pass --apply)'}")
        for n in p.get("notes", []):
            print(f"  {head} {n}")
        if not p.get("actions") and not p.get("notes"):
            print(f"  {head} in sync")
    return rc


if __name__ == "__main__":
    sys.exit(main())
