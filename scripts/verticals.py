#!/usr/bin/env python3
"""
Rank AI — single source of truth for client → vertical → template resolution.

Every pipeline script that touches templates/{vertical}/... MUST resolve the
path through this module. Nothing in the pipeline is allowed to hardcode
templates/restoration/ (root cause of the davis-construction incident: a
construction client silently received restoration prompts/archetypes).

FAIL-LOUD POLICY
  - An ACTIVE client without an explicit "vertical" field in
    clients/{slug}.json is a hard error (we never guess).
  - A vertical whose asset file doesn't exist is a hard error — unless the
    client record EXPLICITLY opts into another vertical's copy of that asset
    via "vertical_template_fallback". Implicit cross-vertical borrowing is
    exactly the bug this module exists to prevent.

Client record fields:
  vertical                    (required, str)  e.g. "restoration" | "construction"
  vertical_template_fallback  (optional)       EXPLICIT cross-vertical asset use:
                                - str: blanket fallback vertical for any asset
                                       missing from the primary vertical
                                - dict: per-asset map, e.g.
                                       {"prompts/onsite-audit.md": "restoration"}
                                       ("*" key = blanket)
  vertical_override_ack       (optional, str)  legacy/alias spelling of the
                              blanket string form above; honored identically.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLIENTS_DIR = REPO_ROOT / "clients"
TEMPLATES_DIR = REPO_ROOT / "templates"

# Non-vertical directories under templates/ (shared infrastructure).
NON_VERTICAL_DIRS = {"astro-starter"}


def _die(msg: str, code: int = 1) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def known_verticals() -> list[str]:
    """Verticals = directories under templates/ minus shared infra dirs."""
    if not TEMPLATES_DIR.exists():
        return []
    return sorted(
        p.name for p in TEMPLATES_DIR.iterdir()
        if p.is_dir() and p.name not in NON_VERTICAL_DIRS
    )


def _load_client(slug: str) -> dict:
    path = CLIENTS_DIR / f"{slug}.json"
    if not path.exists():
        _die(f"No client record at {path}")
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as e:
        _die(f"Invalid JSON in {path}: {e}")
    return {}  # unreachable


def get_vertical(slug: str, client: dict | None = None, *, required: bool = True) -> str | None:
    """Return the client's explicit vertical.

    Active clients MUST carry a "vertical" field; missing → hard error naming
    the fix. For non-active clients (or required=False) a missing vertical
    returns None so read-only tooling can degrade gracefully.
    """
    client = client if client is not None else _load_client(slug)
    vertical = client.get("vertical")
    if vertical:
        if vertical not in known_verticals():
            _die(
                f"Client {slug} has vertical={vertical!r} but templates/{vertical}/ "
                f"does not exist. Known verticals: {', '.join(known_verticals()) or '(none)'}. "
                f"Fix clients/{slug}.json or create the templates/{vertical}/ directory."
            )
        return vertical
    if required and client.get("status") == "active":
        _die(
            f"Client {slug} is ACTIVE but clients/{slug}.json has no \"vertical\" field. "
            f"The pipeline refuses to guess (davis-construction incident). "
            f"Fix: add \"vertical\": \"<one of: {', '.join(known_verticals())}>\" "
            f"to clients/{slug}.json."
        )
    if required:
        _die(
            f"Client {slug} has no \"vertical\" field in clients/{slug}.json. "
            f"Add \"vertical\": \"<one of: {', '.join(known_verticals())}>\"."
        )
    return None


def _explicit_fallback_vertical(client: dict, relative_path: str) -> str | None:
    """Return the EXPLICIT fallback vertical for this asset, if the client
    record declares one. Never implicit."""
    fb = client.get("vertical_template_fallback")
    if isinstance(fb, str) and fb:
        return fb
    if isinstance(fb, dict):
        v = fb.get(relative_path) or fb.get("*")
        if v:
            return str(v)
    ack = client.get("vertical_override_ack")
    if isinstance(ack, str) and ack:
        return ack
    return None


def resolve_template(slug: str, relative_path: str, client: dict | None = None) -> Path:
    """Resolve templates/{vertical}/{relative_path} for a client. Fail loud.

    Returns the existing Path. Exits with a clear error if the vertical's
    asset is missing and no explicit fallback covers it.
    """
    client = client if client is not None else _load_client(slug)
    vertical = get_vertical(slug, client)
    candidate = TEMPLATES_DIR / vertical / relative_path
    if candidate.exists():
        return candidate

    fb_vertical = _explicit_fallback_vertical(client, relative_path)
    if fb_vertical:
        if fb_vertical not in known_verticals():
            _die(
                f"Client {slug} declares vertical_template_fallback={fb_vertical!r} "
                f"but templates/{fb_vertical}/ does not exist."
            )
        fb_path = TEMPLATES_DIR / fb_vertical / relative_path
        if fb_path.exists():
            print(
                f"[verticals] {slug}: using templates/{fb_vertical}/{relative_path} "
                f"(explicit vertical_template_fallback; primary vertical={vertical} "
                f"lacks this asset)",
                file=sys.stderr,
            )
            return fb_path
        _die(
            f"Client {slug} is vertical={vertical}; templates/{vertical}/{relative_path} "
            f"does not exist and the declared fallback "
            f"templates/{fb_vertical}/{relative_path} doesn't either."
        )

    _die(
        f"Client {slug} is vertical={vertical} but templates/{vertical}/{relative_path} "
        f"does not exist. Build the {vertical} vertical asset or set "
        f"clients/{slug}.json \"vertical_template_fallback\" (vertical_override_ack) "
        f"to consciously use another vertical's asset."
    )
    return candidate  # unreachable


def template_exists(slug: str, relative_path: str, client: dict | None = None) -> bool:
    """Non-fatal existence check (for coverage gates / status displays)."""
    client = client if client is not None else _load_client(slug)
    vertical = client.get("vertical")
    if not vertical:
        return False
    return (TEMPLATES_DIR / vertical / relative_path).exists()


if __name__ == "__main__":
    # Tiny CLI for debugging: python3 scripts/verticals.py <slug> [relative_path]
    if len(sys.argv) < 2:
        print(f"Known verticals: {', '.join(known_verticals())}")
        sys.exit(0)
    s = sys.argv[1]
    if len(sys.argv) > 2:
        print(resolve_template(s, sys.argv[2]))
    else:
        print(get_vertical(s))
