#!/usr/bin/env python3
"""
Rank AI build-site implementation. Phase 1 = scaffold (deterministic, free).

  scaffold   Copy starter to sites/{slug}/, substitute brand tokens, generate
             one content-collection markdown per planned URL, init git, create
             GitHub repo at restorationai/{slug}-site, push initial commit,
             attempt Cloudflare Pages project creation (gated).

  status     Show current build state for a client.

Run `render`, `push-staging`, `push-main`, `cut-over` are phase 2/3 (not
implemented yet).

Environment (from rank-ai/.env):
  CLOUDFLARE_API_TOKEN          Pages API access (uses R2 token in our setup)
  CLOUDFLARE_R2_API_TOKEN       R2 PUT (future render step)
  CLOUDFLARE_ACCOUNT_ID
  GITHUB_PERSONAL_ACCESS_TOKEN  Used for both repo create and git push

Spec: rank-ai/docs/build-site-skill-spec.md
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import requests  # Supabase storage list (urllib is WAF-blocked on supabase.co)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verticals  # noqa: E402 — per-client vertical → template resolution (fail-loud)
from work_log import company_id_for_slug, work_log  # noqa: E402 — fail-open ledger

REPO_ROOT = Path(__file__).resolve().parent.parent
CLIENTS_DIR = REPO_ROOT / "clients"
TEMPLATES_DIR = REPO_ROOT / "templates"
SITES_DIR = REPO_ROOT / "sites"
STARTER_DIR = TEMPLATES_DIR / "astro-starter"

GH_OWNER = "restorationai"   # locked per architectural decision
GH_API = "https://api.github.com"
CF_API = "https://api.cloudflare.com/client/v4"

# State contractor-license verification pages (footer license link).
STATE_LICENSE_LOOKUP = {
    "WA": "https://secure.lni.wa.gov/verify/",
    "NJ": "https://newjersey.mylicense.com/verification/",
    "CT": "https://www.elicense.ct.gov/Lookup/LicenseLookup.aspx",
    "CA": "https://www.cslb.ca.gov/OnlineServices/CheckLicenseII/CheckLicense.aspx",
    "NV": "https://www.nvcontractorsboard.com/",
    "FL": "https://www.myfloridalicense.com/wl11.asp",
    "TX": "https://www.tdlr.texas.gov/LicenseSearch/",
    "UT": "https://secure.utah.gov/llv/search/index.html",
    "AL": "https://genconbd.alabama.gov/ROSTER-SEARCH.aspx",
    "PA": "https://hicsearch.attorneygeneral.gov/",
    "NY": "https://appext20.dos.ny.gov/lcns_public/chk_load",
    "MA": "https://services.oca.state.ma.us/hic/licenseelist.aspx",
}

BINARY_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2", ".ttf"}


# ----------------------------------------------------------------------------
# IO helpers
# ----------------------------------------------------------------------------


def die(msg: str, code: int = 1) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict:
    if not path.exists():
        die(f"Missing required file: {path}")
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as e:
        die(f"Invalid JSON in {path}: {e}")


def save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n")


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


# ----------------------------------------------------------------------------
# Token resolution
# ----------------------------------------------------------------------------


DEFAULTS = {
    # Canonical palette matching the narestco visual reference (dark + red).
    # Per-client overrides flow through plan-input.json's brand block.
    # Default palette is STANDARDIZED BLACK (Santino 2026-09-04: "instead of it
    # being red, make the color black and standardized"). Real clients almost
    # never see it: scaffold auto-extracts the palette from the client's logo
    # (see _palette_from_logo) and plan-input overrides always win. The black
    # default is the no-logo/no-colors fallback only.
    "BRAND_DARK_COLOR": "#111827",      # dark.DEFAULT — dominant background (gray-900)
    "BRAND_PRIMARY_COLOR": "#171717",   # primary.DEFAULT — the client's ACTUAL brand hex
    "BRAND_PRIMARY_CTA": "#171717",     # primary-600 — solid fills that carry WHITE text
    "BRAND_PRIMARY_DARK": "#000000",    # primary-700 — hover state
    "BRAND_PRIMARY_LIGHT": "#e5e5e5",   # primary-200 — light tint
    # cta.* — the SOLID-FILL pair (button background + the label on it),
    # resolved together so the pair always clears AA. See resolve_tokens.
    "BRAND_CTA_FILL": "#171717",        # cta.DEFAULT — every call-to-action fill
    "BRAND_CTA_FG": "#ffffff",          # cta.fg      — the label ON that fill
    "BRAND_CTA_HOVER": "#000000",       # cta.hover
    "BRAND_ACCENT_COLOR": "#525252",    # accent — urgent highlights
    "BRAND_ACCENT_FG": "#ffffff",       # accent.fg — label on the accent fill
    "BRAND_FONT_SANS": "Inter",
    "BRAND_FONT_DISPLAY": "Inter",
}


def fetch_job_photos(company_id: str, limit: int = 24) -> list[str]:
    """Build-time: public URLs of the client's uploaded job photos (from the intake
    link, branding/{cid}/job-photos[/posted]) for the site's 'Recent Work' gallery.
    Non-fatal — returns [] on missing creds or any error."""
    sb_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    sb_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not (company_id and sb_url and sb_key):
        return []
    hdr = {"apikey": sb_key, "Authorization": f"Bearer {sb_key}", "Content-Type": "application/json"}
    urls: list[str] = []
    for sub in ("job-photos", "job-photos/posted"):
        try:
            r = requests.post(f"{sb_url}/storage/v1/object/list/branding", headers=hdr,
                              json={"prefix": f"{company_id}/{sub}/", "limit": 100,
                                    "sortBy": {"column": "created_at", "order": "desc"}}, timeout=20)
            if not r.ok:
                continue
            for f in r.json():
                n = f.get("name") or ""
                if f.get("id") and n.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                    urls.append(f"{sb_url}/storage/v1/object/public/branding/{company_id}/{sub}/{n}")
        except Exception:
            continue
    return urls[:limit]


_US_STATE_ABBR = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE",
    "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ",
    "new mexico": "NM", "new york": "NY", "north carolina": "NC",
    "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR",
    "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
    "district of columbia": "DC",
}


def _state_abbr(state) -> str:
    """'Mississippi' / ' ca ' -> 'MS' / 'CA'. The wizard writes full names and
    the geo pickers write codes; a PostalAddress must carry the code."""
    s = str(state or "").strip()
    if not s:
        return ""
    return _US_STATE_ABBR.get(s.lower(), s.upper() if len(s) == 2 else s)


def _mirror_nested_brand(brand: dict) -> None:
    """Derive the FLAT brand keys resolve_tokens reads from the NESTED blocks
    intake extraction writes.

    plan-input.json now carries brand.colors {primary, secondary, accent,
    palette} and brand.fonts {heading, body}, but token resolution historically
    read only the flat mirrors (primary_color, dark_color, accent_color,
    font_sans, font_display) — so every nested-only client scaffolded in the
    default red/Inter until someone hand-wrote the mirrors (Air Care
    2026-08-14: Sarha's exact hexes sat in brand.colors while the scaffold
    shipped the canonical red). The nested blocks stay the source of truth;
    the flat keys are derived here and nobody hand-writes them again.
    setdefault means an explicit flat key still wins, so legacy flat-key
    plan-inputs resolve byte-identically."""
    colors = brand.get("colors")
    if isinstance(colors, dict):
        if colors.get("primary"):
            brand.setdefault("primary_color", colors["primary"])
            # NEVER the raw primary as the canvas (2026-09-11 law, DryCor):
            # dark surfaces stay neutral; the brand hue survives as a whisper.
            brand.setdefault("dark_color", _neutral_dark(colors["primary"]))
        if colors.get("accent"):
            brand.setdefault("accent_color", colors["accent"])
    fonts = brand.get("fonts")
    if isinstance(fonts, dict):
        if fonts.get("body"):
            brand.setdefault("font_sans", fonts["body"])
        if fonts.get("heading"):
            brand.setdefault("font_display", fonts["heading"])


def resolve_tokens(client: dict, plan_input: dict, allow_missing_domain: bool = False) -> tuple[dict, dict]:
    """Return (string_tokens, json_tokens). JSON tokens substitute as bare
    JS literals (no surrounding quotes)."""
    brand = dict(plan_input.get("brand", {}) or {})
    _mirror_nested_brand(brand)  # nested brand.colors/fonts -> flat mirrors
    # SAME BUG, WIDER BLAST RADIUS than llms.txt (see build_llms_substitutions).
    # A null domain f-strings into "https://None" and lands in every token that
    # embeds it — most damagingly BRAND_CANONICAL_URL, which the starter writes
    # into public/robots.txt as the Sitemap: directive. Eight sites shipped
    # "Sitemap: https://None/sitemap-index.xml", including crew3r.com after it
    # went live, so every crawler and AI agent was pointed at a host that does
    # not exist. Refuse rather than stringify.
    slug = client["slug"]
    domain = (client.get("domain") or "").strip()
    if not domain or domain.endswith(".invalid"):
        if allow_missing_domain:
            # Colour-only callers (retint) never write URL tokens; a loud
            # placeholder keeps the guard's spirit without blocking pre-domain
            # clients from colour fixes (Life Savers 2026-08-10). Anything
            # that DOES write this into a page would be caught by the normal
            # scaffold path, which still refuses.
            domain = f"{slug}.invalid"
        else:
            raise ValueError(
                f"scaffold tokens for {slug}: domain is {client.get('domain')!r}. "
                "Set the real domain on the client record first — a null domain "
                "silently becomes 'https://None' in robots.txt, canonicals and "
                "schema.")

    # Resolve primary area for derived city/state
    areas = plan_input.get("service_areas", [])
    primary_area = next((a for a in areas if a.get("primary")), areas[0] if areas else {})

    # Phone — keep both formatted and raw forms
    phone_display = brand.get("phone", "")
    phone_raw = "+1" + re.sub(r"\D", "", phone_display) if phone_display else ""

    # Display defaults
    display_name = brand.get("display_name", client.get("display_name", slug))
    short_name = brand.get("short_name", display_name)
    initials = "".join(w[0].upper() for w in display_name.split()[:2]) or slug[:2].upper()

    # Vertical trade-identity copy — resolved from the client's vertical
    # (templates/{vertical}/vertical-tokens.json, fail-loud), never hardcoded
    # in the starter (industry-bleed audit 2026-07-31: the light starter's
    # About paragraph shipped All Pro's "plumbing, heating, and air
    # conditioning" identity on four restoration sites, one of them live).
    vt = load_json(verticals.resolve_template(slug, "vertical-tokens.json", client=client))

    def _vertical_copy(key: str) -> str:
        # brand block override wins (verbatim — hand-written copy may contain
        # braces); otherwise the vertical default with {display_name}/{city}/
        # {state} formatted in.
        if key in brand:
            return str(brand[key])
        return str(vt[key]).format(
            display_name=display_name,
            city=primary_area.get("city", ""),
            state=primary_area.get("state", ""),
        )

    string_tokens = {
        "BRAND_SLUG": slug,
        "BRAND_DISPLAY_NAME": display_name,
        "BRAND_SHORT_NAME": short_name,
        "BRAND_LEGAL_NAME": brand.get("legal_name", display_name),
        "BRAND_DOMAIN": domain,
        "BRAND_CANONICAL_URL": f"https://{domain}",
        "BRAND_PHONE": phone_display,
        "BRAND_PHONE_RAW": phone_raw,
        "BRAND_EMAIL": brand.get("email", ""),
        "BRAND_HOURS": brand.get("hours", "24/7"),
        "BRAND_FOUNDED_YEAR": str(brand.get("founded_year", "")),
        "BRAND_PRIMARY_CITY": primary_area.get("city", ""),
        "BRAND_PRIMARY_STATE": primary_area.get("state", ""),
        # The PHYSICAL address city/state, which is NOT the same thing as the
        # primary MARKETING city (DISS Restoration 2026-08-05: office at 712
        # Spearman Ave, Farrell PA 16121, primary target Youngstown OH — the
        # PostalAddress schema composed the real street + real ZIP with the
        # wrong locality and shipped an address that does not exist, on a
        # fleet whose whole citations programme is NAP consistency). Falls
        # back to the primary area so every client where the two ARE the same
        # regenerates byte-identical.
        "BRAND_ADDRESS_CITY": (brand.get("city") or "").strip() or primary_area.get("city", ""),
        "BRAND_ADDRESS_STATE": _state_abbr(brand.get("state")) or primary_area.get("state", ""),
        "BRAND_STREET_ADDRESS": brand.get("street_address", ""),
        "BRAND_POSTAL_CODE": brand.get("postal_code", ""),
        "BRAND_LAT": str(brand.get("lat", "")),
        "BRAND_LNG": str(brand.get("lng", "")),
        "BRAND_PLACE_ID": brand.get("place_id", ""),
        "BRAND_GOOGLE_CID": brand.get("google_cid", ""),
        "BRAND_LICENSE_AUTHORITY": brand.get("license_authority", ""),
        # Footer links the license number to the state's verification page —
        # instantly checkable beats merely printed (Green Restoration pattern,
        # 2026-07-23). Empty when no license on file; the Footer guards.
        "BRAND_LICENSE_LOOKUP_URL": brand.get(
            "license_lookup_url",
            STATE_LICENSE_LOOKUP.get(str(primary_area.get("state", "")).upper(), "")
            if brand.get("license_numbers") else ""),
        "BRAND_LICENSE_TYPE": brand.get("license_type", ""),
        "BRAND_GBP_RATING_VALUE": str(brand.get("gbp_rating_value", "")),
        "BRAND_GBP_REVIEW_COUNT": str(brand.get("gbp_review_count", "")),
        "BRAND_VERTICAL": (verticals.get_vertical(slug, client, required=False)
                           or "restoration"),
        "BRAND_TAGLINE": _vertical_copy("tagline"),
        "BRAND_CTA_LABEL": _vertical_copy("cta_label"),
        "BRAND_TRADE_NOUN": _vertical_copy("trade_noun"),
        "BRAND_SPECIALIST_PHRASE": _vertical_copy("specialist_phrase"),
        "BRAND_ANNOUNCEMENT_SUFFIX": _vertical_copy("announcement_suffix"),
        "BRAND_HOME_ABOUT_BLURB": _vertical_copy("home_about_blurb"),
        "BRAND_LOGO_URL": brand.get("logo_url", f"https://images.{domain}/brand/logo.png"),
        "BRAND_INITIALS": initials,
        "BRAND_IMAGES_BASE": f"https://images.{domain}",
        "BRAND_GOOGLE_MAPS_API_KEY": brand.get("google_maps_api_key", ""),
        "BRAND_GA4_MEASUREMENT_ID": brand.get("ga4_measurement_id", ""),
        "BRAND_CLARITY_PROJECT_ID": brand.get("clarity_project_id", ""),
        **DEFAULTS,
    }

    # Per-client override for any DEFAULTS-style fields
    for k in DEFAULTS:
        bk = k.replace("BRAND_", "").lower()
        if bk in brand:
            string_tokens[k] = str(brand[bk])

    # ---- Google Fonts stylesheet URL (Air Care 2026-08-14) ------------------
    # BaseLayout hardcoded the Inter URL, so choosing Anton/Poppins changed the
    # tailwind families but never LOADED them — the browser silently fell back
    # and every non-Inter build got hand-edited. The starter (dark + light)
    # now carries {{BRAND_GOOGLE_FONTS_URL}}; resolve it from the chosen
    # families. Shape matches the Air Care hand-fix: the display face loads
    # bare (Anton ships one weight), the body face carries the full weight
    # ramp the starter's utilities use. Inter/Inter — the default — resolves
    # to the exact URL the template used to hardcode, so every legacy client
    # scaffolds byte-identically. brand.google_fonts_url wins for anything
    # fancier (multi-weight display faces, italics).
    if brand.get("google_fonts_url"):
        string_tokens["BRAND_GOOGLE_FONTS_URL"] = str(brand["google_fonts_url"])
    else:
        sans = (string_tokens["BRAND_FONT_SANS"] or "Inter").strip()
        disp = (string_tokens["BRAND_FONT_DISPLAY"] or sans).strip()
        wght = ":wght@400;500;600;700;800;900"
        fams = ([f"family={disp.replace(' ', '+')}"] if disp != sans else [])
        fams.append(f"family={sans.replace(' ', '+')}{wght}")
        string_tokens["BRAND_GOOGLE_FONTS_URL"] = (
            "https://fonts.googleapis.com/css2?" + "&".join(fams) + "&display=swap")

    # Full primary shade ramp derived from the client's actual color
    # (2026-07-28: the template carried hardcoded RED 50-950 shades and only
    # DEFAULT/600 were substituted — Mold Solutionz's lime brand shipped as a
    # green/red patchwork). Every shade now comes from the brand hue.
    import colorsys

    def _shade(hexcol: str, l_target: float) -> str:
        hexcol = (hexcol or "#dc2626").lstrip("#")
        if len(hexcol) != 6:
            hexcol = "dc2626"
        r, g, b = (int(hexcol[i:i + 2], 16) / 255 for i in (0, 2, 4))
        h, _l, s = colorsys.rgb_to_hls(r, g, b)
        r2, g2, b2 = colorsys.hls_to_rgb(h, l_target, s)
        return "#%02x%02x%02x" % (round(r2 * 255), round(g2 * 255), round(b2 * 255))

    def _rel_lum(hexcol: str) -> float:
        """WCAG relative luminance (sRGB, gamma-corrected)."""
        hx = (hexcol or "").lstrip("#")
        if len(hx) != 6:
            return 0.0
        out = []
        for i in (0, 2, 4):
            c = int(hx[i:i + 2], 16) / 255
            out.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
        return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]

    def _contrast(a: str, b: str) -> float:
        la, lb = _rel_lum(a), _rel_lum(b)
        if la < lb:
            la, lb = lb, la
        return (la + 0.05) / (lb + 0.05)

    prim = string_tokens["BRAND_PRIMARY_COLOR"]
    ramp = {50: 0.97, 100: 0.92, 200: 0.84, 300: 0.72, 400: 0.61,
            500: 0.50, 600: 0.42, 700: 0.34, 800: 0.27, 900: 0.21, 950: 0.12}
    for shade, l_ in ramp.items():
        string_tokens[f"BRAND_PRIMARY_{shade}"] = _shade(prim, l_)

    # ---- Contrast-safe CTA fill (2026-08-05, Reign Restoration) -------------
    # The starter uses the brand color in TWO structurally different roles:
    #   * primary.DEFAULT   -> text-primary on a dark surface  (wants the REAL
    #                          brand hex; the client recognises this as "our
    #                          colour")
    #   * primary-600 / 700 -> SOLID FILLS that render WHITE text (hero CTA,
    #                          announcement bar, mobile call bar, form submit)
    # Both used to be the same token, so a light brand colour forced a choice
    # between a legible button and the client's actual colour. Reign's gold is
    # #f2b623 — white on it is 1.8:1 — so the previous pass shipped a darkened
    # #8c6a18 as "the brand colour" and Jerrott replied "the yellow need to
    # match the logo color." Now the roles are split: DEFAULT keeps the real
    # hex, and the CTA fill walks down the SAME hue/saturation until white
    # clears WCAG AA (4.5:1). No-ops for dark brands (red #dc2626 = 4.8:1,
    # so every existing client regenerates byte-identical); fires for the
    # light ones (lime, gold, sky) that were shipping unreadable buttons.
    if "primary_cta" not in brand:
        cta = prim
        if _contrast("#ffffff", cta) < 4.5:
            l_ = colorsys.rgb_to_hls(
                *(int(prim.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)))[1]
            while l_ > 0.04:
                l_ -= 0.005
                cand = _shade(prim, l_)
                if _contrast("#ffffff", cand) >= 4.6:  # 0.1 of headroom
                    cta = cand
                    break
            else:
                cta = _shade(prim, 0.04)
        string_tokens["BRAND_PRIMARY_CTA"] = cta
    cta = string_tokens["BRAND_PRIMARY_CTA"]
    string_tokens["BRAND_PRIMARY_600"] = cta

    if "primary_dark" not in brand:
        # 700 is the CTA's hover — must stay DARKER than the fill it hovers
        # from, which the fixed L=0.34 rung cannot guarantee once the fill has
        # been walked down.
        cta_l = colorsys.rgb_to_hls(
            *(int(cta.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)))[1]
        string_tokens["BRAND_PRIMARY_DARK"] = _shade(
            prim, max(min(ramp[700], cta_l - 0.08), 0.04))
    string_tokens["BRAND_PRIMARY_700"] = string_tokens["BRAND_PRIMARY_DARK"]
    # Walking 600/700 down can leave the fixed 800/900/950 rungs LIGHTER than
    # 700 (a gold 700 lands near L=0.24 while the 800 rung is pinned at 0.27),
    # which would invert the ramp. Keep the tail monotonically darker.
    prev_l = colorsys.rgb_to_hls(
        *(int(string_tokens["BRAND_PRIMARY_700"].lstrip("#")[i:i + 2], 16) / 255
          for i in (0, 2, 4)))[1]
    for shade in (800, 900, 950):
        cap = max(prev_l - 0.045, 0.02)
        l_ = min(ramp[shade], cap)
        string_tokens[f"BRAND_PRIMARY_{shade}"] = _shade(prim, l_)
        prev_l = l_
    if "primary_light" not in brand:
        string_tokens["BRAND_PRIMARY_LIGHT"] = string_tokens["BRAND_PRIMARY_200"]

    # ---- CTA fill + label, resolved as a PAIR (2026-08-05 round 3, Reign) ---
    # The block above darkens the FILL until WHITE can sit on it. That keeps
    # the button legible and loses the thing the client actually cares about:
    # Jerrott Gray looked at the shipped gold button and said it a second time
    # — "Action to call on the website need to match golds as the logo." He is
    # right. #976e09 is not #f2b623, and "it passes contrast" is not an answer
    # to "that is not my colour." A button has TWO colours and we had been
    # moving the wrong one.
    #
    # So: hold the fill at the client's real hex and move the LABEL instead.
    #   dark brand  (#dc2626): fill = brand hex, label = white      (unchanged)
    #   light brand (#f2b623): fill = brand hex, label = near-black (10.8:1,
    #                          better than the 4.6:1 the darkened fill gave)
    #   neither label clears AA: only then fall back to the darkened fill.
    # primary-600/700 are LEFT ALONE — they are still correct for brand-tinted
    # TEXT on a white surface (Hero's outline button, ProcessSection icons),
    # which is a different problem with a different answer.
    surface = string_tokens.get("BRAND_DARK_COLOR") or "#0a0b0e"
    if "cta_fill" not in brand:
        white_c, dark_c = _contrast("#ffffff", prim), _contrast(surface, prim)
        if max(white_c, dark_c) >= 4.5:
            string_tokens["BRAND_CTA_FILL"] = prim
            string_tokens["BRAND_CTA_FG"] = ("#ffffff" if white_c >= dark_c
                                             else surface)
        else:
            string_tokens["BRAND_CTA_FILL"] = cta
            string_tokens["BRAND_CTA_FG"] = "#ffffff"
    fill, fill_fg = string_tokens["BRAND_CTA_FILL"], string_tokens["BRAND_CTA_FG"]
    if "cta_hover" not in brand:
        if fill == cta:
            # White-label case: the 700 rung already is this button's hover and
            # every existing client resolves here, byte-identical to before.
            string_tokens["BRAND_CTA_HOVER"] = string_tokens["BRAND_PRIMARY_700"]
        else:
            # Dark-label case: 700 is a deep brown-gold that would read as a
            # different button on hover. Darken by one gentle step and keep the
            # label's AA, backing off upward if the step breaks it.
            fill_l = colorsys.rgb_to_hls(
                *(int(fill.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)))[1]
            hov = _shade(prim, max(fill_l - 0.07, 0.04))
            if _contrast(fill_fg, hov) < 4.5:
                hov = _shade(prim, min(fill_l + 0.07, 0.96))
            string_tokens["BRAND_CTA_HOVER"] = hov
    if "accent_color" not in brand:
        # btn-accent is the same kind of button as btn-primary (a phone CTA on
        # service and service-area pages), so it carries the same fill. Was
        # `cta`, which for a light brand left those buttons olive while the
        # hero button went gold — one call button, two colours.
        string_tokens["BRAND_ACCENT_COLOR"] = fill
    acc = string_tokens["BRAND_ACCENT_COLOR"]
    string_tokens["BRAND_ACCENT_FG"] = (
        "#ffffff" if _contrast("#ffffff", acc) >= _contrast(surface, acc)
        else surface)

    json_tokens = {
        "BRAND_LICENSE_NUMBERS_JSON": json.dumps(brand.get("license_numbers", [])),
        "BRAND_CERTIFICATIONS_JSON": json.dumps(brand.get("certifications", [])),
        "BRAND_TRUST_BADGES_JSON": json.dumps(brand.get("trust_badges", [])),
        "BRAND_LICENSED_INSURED_ATTESTED_JSON": json.dumps(bool(brand.get("licensed_insured_attested", False))),
        "BRAND_SAME_AS_URLS_JSON": json.dumps(brand.get("same_as_urls", [])),
        "BRAND_JOB_PHOTOS_JSON": json.dumps(fetch_job_photos(client.get("company_id", ""))),
    }

    return string_tokens, json_tokens


def build_llms_substitutions(plan_input: dict, client: dict,
                             allow_placeholder: bool = False) -> dict:
    """Computed llms.txt fields — services list, areas list, etc."""
    # A null domain used to render straight into the file as "https://None/..."
    # because an f-string will happily stringify None. Eight sites shipped that
    # way (259 dead URLs), including one that went live — and llms.txt is the
    # file AI crawlers read, so every citation path we build was pointing at a
    # host that does not exist. Fail loudly instead: a scaffold that cannot name
    # the site has no business writing its AI index.
    #
    # allow_placeholder is the scaffold's EXPLICIT no-domain-anywhere path
    # (2026-08-14): the caller has already checked the client record AND the
    # app company record, warned loudly, and the {slug}.invalid placeholder is
    # healed by sync-deploy's rehydration guard the moment a real domain lands.
    domain = (client.get("domain") or "").strip()
    if not domain or domain.endswith(".invalid"):
        if allow_placeholder:
            domain = f"{client.get('slug') or plan_input.get('_slug')}.invalid"
        else:
            raise ValueError(
                f"llms.txt for {client.get('slug')}: domain is {client.get('domain')!r}. "
                "Set the real domain on the client record before scaffolding, or the "
                "AI index ships with unreachable URLs.")
    services = plan_input.get("services", [])
    areas = plan_input.get("service_areas", [])
    certs = plan_input.get("brand", {}).get("certifications", [])

    # Note: services here are slugs; the human display name comes from the
    # client's vertical services catalog. We re-load it for display.
    catalog_path = verticals.resolve_template(client["slug"], "services.json", client=client)
    catalog = {s["slug"]: s for s in load_json(catalog_path)["services"]}

    # llms.txt spec recommends markdown link lists: "- [Name](url)"
    svc_lines = []
    for slug in services:
        s = catalog.get(slug, {"display_name": slug})
        svc_lines.append(f"- [{s['display_name']}](https://{domain}/services/{slug}/)")
    area_lines = []
    for a in areas:
        area_lines.append(f"- [{a['city']}, {a['state']}](https://{domain}/service-areas/{a['slug']}/)")

    radius_default = f"Greater {areas[0]['city']} region" if areas else "Local area"
    radius = plan_input.get("service_radius_description") or radius_default

    return {
        "LLMS_SERVICES_INDEX": "\n".join(svc_lines) if svc_lines else "(no services)",
        "LLMS_SERVICE_AREAS_INDEX": "\n".join(area_lines) if area_lines else "(no areas)",
        # Never default to an unverified "Licensed and insured" claim — only list
        # certifications we actually have on file (hardcoded-claims audit).
        "LLMS_CERTIFICATIONS": ", ".join(certs) if certs else "Available on request",
        "LLMS_SERVICE_RADIUS": radius,
        # Official profiles (2026-09-05): the same sameAs set schema carries,
        # surfaced for AI ingestion — socials AND directory profiles both
        # corroborate the entity here.
        "LLMS_SAME_AS_INDEX": "\n".join(
            f"- {u}" for u in (plan_input.get("brand", {}).get("same_as_urls")
                               or plan_input.get("same_as_urls") or [])) or
            "(profiles listed in page schema)",
    }


def substitute_text(text: str, tokens: dict) -> tuple[str, set]:
    for k, v in tokens.items():
        # plan-input JSON nulls surface as None ("place_id": null crashed the
        # RestorationXpress scaffold 2026-07-23) — treat as empty, never crash.
        text = text.replace(f"{{{{{k}}}}}", "" if v is None else str(v))
    return text, set(re.findall(r"\{\{[A-Z_]+\}\}", text))


# ----------------------------------------------------------------------------
# Starter copy + substitution
# ----------------------------------------------------------------------------


def _starter_protected(rel: str) -> bool:
    """Site PRODUCT files a re-scaffold must never flatten (2026-08-19; a
    re-scaffold after a plan change rmtree'd src/ and public/ wholesale and
    wiped 124 rendered RT Olson pages + the real-photo set back to starter
    state, twice). Code refreshes from the starter; product survives:
      - src/content/**/*.md   rendered page bodies (config.ts still updates)
      - public/images/**      real photos + generated imagery + variants
      - src/data/image-meta.json  the resize/serviceImage registry
      - prompts/**            per-site prompt patches (interim until every
                              vertical ships its own render prompts)"""
    return (
        (rel.startswith("src/content/") and rel.endswith(".md"))
        or rel.startswith("public/images/")
        or rel == "src/data/image-meta.json"
        or rel.startswith("prompts/")
    )


def copy_starter(site_dir: Path) -> None:
    if not site_dir.exists():
        site_dir.mkdir(parents=True, exist_ok=True)
        shutil.copytree(STARTER_DIR, site_dir, dirs_exist_ok=True)
        return
    # Existing site: refresh CODE from the starter, preserve PRODUCT.
    # (node_modules / .astro survive too — never part of the starter.)
    kept = 0
    for child in STARTER_DIR.iterdir():
        target = site_dir / child.name
        if child.is_file():
            shutil.copy2(child, target)
            continue
        # Directory: merge file-by-file so protected product survives.
        for f in child.rglob("*"):
            if not f.is_file():
                continue
            rel = f.relative_to(STARTER_DIR).as_posix()
            dst = site_dir / rel
            if _starter_protected(rel) and dst.exists():
                kept += 1
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dst)
    if kept:
        print(f"    starter copy preserved {kept} existing product file(s) "
              "(rendered content / images / prompts)")


LIGHT_OVERLAY_DIR = TEMPLATES_DIR / "astro-starter-light"


def apply_light_overlay(site_dir: Path) -> int:
    """Overlay the light-theme file variants (brand.theme == 'light').

    The starter is dark-navy by design; the overlay is the proven light
    conversion (sourced from the all-pro/prorestoration hand conversions,
    2026-07-23) captured as drop-in replacements. Same component contracts,
    light surfaces."""
    if not LIGHT_OVERLAY_DIR.exists():
        return 0
    n = 0
    for f in LIGHT_OVERLAY_DIR.rglob("*"):
        if not f.is_file():
            continue
        rel = f.relative_to(LIGHT_OVERLAY_DIR)
        dst = site_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dst)
        n += 1
    return n


def substitute_in_tree(root: Path, tokens: dict) -> tuple[int, set]:
    """Walk root, substitute tokens in every text file, return (files_changed, unsubstituted_set)."""
    files_changed = 0
    leftover: set = set()
    SKIP_DIRS = {"node_modules", ".astro", "dist", ".git"}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(p in SKIP_DIRS for p in path.parts):
            continue
        if path.suffix in BINARY_EXTS:
            continue
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            continue
        new_text, leftover_here = substitute_text(text, tokens)
        if new_text != text:
            path.write_text(new_text)
            files_changed += 1
        leftover |= leftover_here
    # README's literal {{TOKEN}} doc strings are expected leftovers — strip from set
    leftover.discard("{{TOKEN}}")
    leftover.discard("{{TOKENS}}")
    return files_changed, leftover


# ----------------------------------------------------------------------------
# Content collection markdown generation
# ----------------------------------------------------------------------------


# Map archetype → (collection_dir, filename_template)
ARCHETYPE_TO_COLLECTION = {
    "home":               ("pages", "home"),
    "about":              ("pages", "about"),
    "contact":            ("pages", "contact"),
    "services-hub":       ("pages", "services"),
    "service-areas-hub":  ("pages", "service-areas"),
    "blog-index":         ("pages", "blog-index"),
    "service-landing":    ("services", None),       # derived
    "service-area":       ("serviceAreas", None),   # derived
    "service-area-service": ("locations", None),    # derived
    "blog-post":          ("blog", None),           # derived
    "legal":              ("legal", None),          # derived
}


def derive_filename(page: dict) -> str:
    """Compute the markdown filename (without .md) for a given plan page."""
    arc = page["archetype"]
    url = page["url_path"]
    coll, fixed_name = ARCHETYPE_TO_COLLECTION[arc]
    if fixed_name:
        return fixed_name
    # Strip trailing slash, split
    parts = [p for p in url.split("/") if p]
    if arc == "service-landing":
        # /services/{slug}/ -> slug
        return parts[-1]
    if arc == "service-area":
        # /service-areas/{slug}/ -> slug
        return parts[-1]
    if arc == "service-area-service":
        # /service-areas/{area}/{service}/ -> area__service
        return f"{parts[1]}__{parts[2]}"
    if arc == "blog-post":
        # /blog/{slug}/ -> slug
        return parts[-1]
    if arc == "legal":
        # /privacy/ -> privacy
        return parts[-1]
    return slugify(url)


def page_hash(page: dict) -> str:
    """SHA-256 of plan-relevant fields. Used for idempotency on re-scaffold."""
    payload = json.dumps({
        k: page.get(k) for k in [
            "url_path", "archetype", "title", "h1", "meta_description",
            "primary_keyword", "secondary_keywords", "search_intent",
            "target_word_count", "image_roles", "schema_stubs", "priority",
            "internal_links_out",
        ]
    }, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def derive_breadcrumb(page: dict, services_lookup: dict, areas_lookup: dict) -> list[dict]:
    """Compute breadcrumb trail from URL structure."""
    arc = page["archetype"]
    url = page["url_path"]
    parts = [p for p in url.split("/") if p]

    crumbs = [{"name": "Home", "url": "/"}]
    if arc == "home":
        return crumbs
    if arc == "blog-index":
        crumbs.append({"name": "Blog"})
        return crumbs
    if arc == "service-landing":
        crumbs.append({"name": "Services", "url": "/services/"})
        svc = services_lookup.get(parts[-1])
        crumbs.append({"name": svc["display_name"] if svc else parts[-1]})
        return crumbs
    if arc == "service-area":
        crumbs.append({"name": "Service Areas", "url": "/service-areas/"})
        area = areas_lookup.get(parts[-1])
        crumbs.append({"name": area["city"] if area else parts[-1]})
        return crumbs
    if arc == "service-area-service":
        area_slug, service_slug = parts[1], parts[2]
        crumbs.append({"name": "Service Areas", "url": "/service-areas/"})
        area = areas_lookup.get(area_slug)
        crumbs.append({
            "name": area["city"] if area else area_slug,
            "url": f"/service-areas/{area_slug}/",
        })
        svc = services_lookup.get(service_slug)
        crumbs.append({"name": svc["display_name"] if svc else service_slug})
        return crumbs
    if arc == "blog-post":
        crumbs.append({"name": "Blog", "url": "/blog/"})
        crumbs.append({"name": page["title"]})
        return crumbs
    if arc == "legal":
        crumbs.append({"name": page["title"].split(" |")[0]})
        return crumbs
    # services-hub, service-areas-hub, about, contact — single segment
    name_map = {
        "services-hub": "Services",
        "service-areas-hub": "Service Areas",
        "about": "About",
        "contact": "Contact",
    }
    crumbs.append({"name": name_map.get(arc, parts[0].title())})
    return crumbs


PLACEHOLDER_BODY = (
    "<!-- Page body not yet generated. Run `build_site.py render --slug {slug}` "
    "to populate. The frontmatter above is the source-of-truth metadata from the plan. -->\n"
    "\nPlaceholder content for {h1}.\n"
)


def write_content_md(
    site_dir: Path,
    page: dict,
    plan_input: dict,
    services_lookup: dict,
    areas_lookup: dict,
    blog_topics_lookup: dict,
    internal_links: dict,
) -> Path:
    arc = page["archetype"]
    coll, _ = ARCHETYPE_TO_COLLECTION[arc]
    fname = derive_filename(page)
    out = site_dir / "src" / "content" / coll / f"{fname}.md"
    out.parent.mkdir(parents=True, exist_ok=True)

    # RENDERED-CONTENT GUARD (2026-08-19). A re-scaffold must NEVER flatten a
    # page that render already wrote — re-scaffolding after a plan change
    # wiped 37 rendered RT Olson pages back to placeholders mid-launch
    # (2026-08-18; same class as the NaRestCo trauma-page overwrite). A page
    # whose frontmatter says rendered: true keeps its file untouched; the
    # plan's metadata for it is refreshed by the next targeted
    # `render --url ... --force`, never by scaffold.
    if out.exists():
        try:
            head = out.read_text()[:20000]
        except OSError:
            head = ""
        # only the FRONTMATTER counts (up to the closing ---): a body that
        # happens to quote the words "rendered: true" must not trigger this
        frontmatter = head.split("\n---\n", 1)[0]
        if "\nrendered: true" in frontmatter:
            print(f"    KEPT (rendered): {out.relative_to(site_dir)}")
            return out

    url = page["url_path"]
    parts = [p for p in url.split("/") if p]

    # Build collection-specific frontmatter fields
    fm: dict = {
        "archetype": arc,
        "title": page["title"],
        "h1": page["h1"],
        "meta_description": page["meta_description"],
        "primary_keyword": page["primary_keyword"],
        "secondary_keywords": page.get("secondary_keywords", []),
        "search_intent": page.get("search_intent", ""),
        "priority": page.get("priority", 0),
        "plan_hash": page_hash(page),
        "generated_at": now_iso(),
        "manual_override": False,
        "internal_links": internal_links.get(url, []),
        "breadcrumb": derive_breadcrumb(page, services_lookup, areas_lookup),
        "faq": [],
    }

    if arc == "service-landing":
        svc = services_lookup.get(parts[-1])
        fm["service_slug"] = parts[-1]
        fm["service_display"] = svc["display_name"] if svc else parts[-1]
    elif arc == "service-area":
        area = areas_lookup.get(parts[-1])
        fm["area_slug"] = parts[-1]
        fm["city"] = area["city"] if area else ""
        fm["state"] = area["state"] if area else ""
        fm["primary"] = bool(area.get("primary")) if area else False
    elif arc == "service-area-service":
        area = areas_lookup.get(parts[1])
        svc = services_lookup.get(parts[2])
        fm["area_slug"] = parts[1]
        fm["service_slug"] = parts[2]
        fm["city"] = area["city"] if area else ""
        fm["state"] = area["state"] if area else ""
        fm["service_display"] = svc["display_name"] if svc else parts[2]
        if svc and svc.get("content_guardrails") == "sensitive":
            fm["content_guardrails"] = "sensitive"
    elif arc == "blog-post":
        slug = parts[-1]
        topic = blog_topics_lookup.get(slug, {})
        # Bulk-seeded launch posts: stagger published_at across the preceding
        # ~4 weeks instead of stamping every seed with the same launch date
        # (identical dates on 10+ posts looks programmatic and gives Google no
        # publish cadence). Deterministic per slug so re-scaffolds are stable.
        if topic.get("published_at"):
            fm["published_at"] = topic["published_at"]
        else:
            from datetime import date, timedelta
            offset = (sum(slug.encode()) % 28) + 1   # 1..28 days back
            fm["published_at"] = (date.today() - timedelta(days=offset)).isoformat()
        fm["services"] = topic.get("services", [])
    elif arc == "legal":
        fm["ref"] = parts[-1]

    body = PLACEHOLDER_BODY.format(slug=plan_input.get("_slug", ""), h1=page["h1"])

    # YAML frontmatter — use json.dumps for arrays/objects which is valid YAML
    lines = ["---"]
    for k, v in fm.items():
        if isinstance(v, (list, dict, bool)):
            lines.append(f"{k}: {json.dumps(v)}")
        elif isinstance(v, (int, float)):
            lines.append(f"{k}: {v}")
        else:
            # String — needs quoting if it contains : or special chars
            escaped = str(v).replace('"', '\\"')
            lines.append(f'{k}: "{escaped}"')
    lines.append("---")
    lines.append(body)

    out.write_text("\n".join(lines))
    return out


def render_all_content(
    site_dir: Path,
    plan_input: dict,
    url_plan: dict,
    internal_links: dict,
) -> int:
    """Write one content collection markdown file per planned URL."""
    # Build lookups
    services_lookup = {s["slug"]: s for s in plan_input.get("services_resolved", [])}
    # If services_resolved isn't present (it's not — services in plan-input is a slug list),
    # rebuild from the client's vertical template (resolved fail-loud per client)
    _slug = plan_input.get("_slug", "")
    if not services_lookup:
        catalog = load_json(verticals.resolve_template(_slug, "services.json"))
        catalog_by_slug = {s["slug"]: s for s in catalog["services"]}
        services_lookup = {
            s: catalog_by_slug[s] for s in plan_input.get("services", []) if s in catalog_by_slug
        }

    areas_lookup = {a["slug"]: a for a in plan_input.get("service_areas", [])}

    blog_topics = load_json(verticals.resolve_template(_slug, "seed-blog-topics.json"))
    blog_topics_lookup = {t["slug"]: t for t in blog_topics["topics"]}

    count = 0
    for page in url_plan["pages"]:
        write_content_md(
            site_dir, page, plan_input,
            services_lookup, areas_lookup, blog_topics_lookup,
            internal_links,
        )
        count += 1
    return count


# ----------------------------------------------------------------------------
# Git + GitHub operations
# ----------------------------------------------------------------------------


def gh_token() -> str:
    t = os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not t:
        die("Missing GITHUB_PERSONAL_ACCESS_TOKEN env var (see rank-ai/.env).")
    return t


def gh_api(method: str, path: str, body: dict | None = None) -> dict:
    url = f"{GH_API}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {gh_token()}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = resp.read().decode()
            return json.loads(payload) if payload else {}
    except urllib.error.HTTPError as e:
        body_text = e.read().decode(errors="replace")
        raise RuntimeError(f"GitHub {method} {path} -> HTTP {e.code}: {body_text}")


def gh_repo_exists(name: str) -> bool:
    try:
        gh_api("GET", f"/repos/{GH_OWNER}/{name}")
        return True
    except RuntimeError as e:
        if "HTTP 404" in str(e):
            return False
        raise


def gh_create_repo(name: str, description: str, private: bool = False) -> dict:
    return gh_api("POST", "/user/repos", {
        "name": name,
        "description": description,
        "private": private,
        "auto_init": False,
        "has_issues": True,
        "has_projects": False,
        "has_wiki": False,
    })


def git(cmd: list[str], cwd: Path) -> str:
    out = subprocess.run(
        ["git"] + cmd, cwd=str(cwd),
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(cmd)} failed (exit {out.returncode}):\n"
            f"  stdout: {out.stdout.strip()}\n  stderr: {out.stderr.strip()}"
        )
    return out.stdout.strip()


def git_init_and_push(site_dir: Path, repo_name: str, commit_message: str) -> None:
    token = gh_token()
    remote = f"https://x-access-token:{token}@github.com/{GH_OWNER}/{repo_name}.git"

    is_new = not (site_dir / ".git").exists()
    if is_new:
        git(["init", "-b", "main"], site_dir)
        # Set local committer for the repo. The user can override globally.
        git(["config", "user.name", "Rank AI Build"], site_dir)
        git(["config", "user.email", "build@restorationai.io"], site_dir)
        git(["remote", "add", "origin", remote], site_dir)
    else:
        # Update remote URL (token may have rotated)
        try:
            git(["remote", "set-url", "origin", remote], site_dir)
        except RuntimeError:
            git(["remote", "add", "origin", remote], site_dir)

    git(["add", "."], site_dir)
    # Skip commit if nothing changed
    try:
        git(["commit", "-m", commit_message], site_dir)
    except RuntimeError as e:
        if "nothing to commit" in str(e).lower():
            print("      (no changes to commit)")
        else:
            raise

    # --force: a previous failed CI attempt may have already pushed to the
    # per-client repo (PuroClean round-2, 2026-07-23); these repos are
    # machine-generated and force-overwritten by every sync-deploy anyway.
    git(["push", "-u", "--force", "origin", "main"], site_dir)

    # Create or update staging branch (mirror of main initially)
    branches = git(["branch", "-a"], site_dir)
    if "staging" not in branches:
        git(["checkout", "-b", "staging"], site_dir)
    else:
        git(["checkout", "staging"], site_dir)
        try:
            git(["merge", "main", "--ff-only"], site_dir)
        except RuntimeError:
            pass
    git(["push", "-u", "--force", "origin", "staging"], site_dir)
    git(["checkout", "main"], site_dir)


# ----------------------------------------------------------------------------
# Cloudflare Pages project creation (gated on OAuth)
# ----------------------------------------------------------------------------


def cf_api(method: str, path: str, token: str, body: dict | None = None) -> dict:
    url = f"{CF_API}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode(errors="replace")
        raise RuntimeError(f"Cloudflare {method} {path} -> HTTP {e.code}: {body_text}")


def cf_pages_project_exists(account_id: str, project_name: str, token: str) -> bool:
    try:
        cf_api("GET", f"/accounts/{account_id}/pages/projects/{project_name}", token)
        return True
    except RuntimeError as e:
        if "HTTP 404" in str(e):
            return False
        raise


def cf_create_pages_project(account_id: str, project_name: str, repo_name: str, token: str) -> dict:
    body = {
        "name": project_name,
        "production_branch": "main",
        "source": {
            "type": "github",
            "config": {
                "owner": GH_OWNER,
                "repo_name": repo_name,
                "production_branch": "main",
                "pr_comments_enabled": True,
                "deployments_enabled": True,
                "preview_branch_includes": ["staging"],
                "preview_deployment_setting": "custom",
            },
        },
        "build_config": {
            "build_command": "npm run build",
            "destination_dir": "dist",
            "root_dir": "",
        },
    }
    return cf_api("POST", f"/accounts/{account_id}/pages/projects", token, body)


def cf_creds() -> tuple[str, str]:
    token = (
        os.environ.get("CLOUDFLARE_PAGES_API_TOKEN")
        or os.environ.get("CLOUDFLARE_R2_API_TOKEN")
        or os.environ.get("CLOUDFLARE_API_TOKEN")
        or ""
    )
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
    if not token or not account_id:
        die("Missing CLOUDFLARE_* env vars (see rank-ai/.env).")
    return token, account_id


# ----------------------------------------------------------------------------
# Anthropic API + prompt template handling (render phase)
# ----------------------------------------------------------------------------

ANTHROPIC_API = "https://api.anthropic.com/v1/messages"
ANTHROPIC_DEFAULT_MODEL = "claude-sonnet-4-6"


def anthropic_call(system: str, user: str, *, model: str = ANTHROPIC_DEFAULT_MODEL,
                   max_tokens: int = 4096, temperature: float = 0.6,
                   max_retries: int = 3) -> tuple[str, dict]:
    import socket
    import time

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        die("Missing ANTHROPIC_API_KEY env var (see rank-ai/.env).")
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    data = json.dumps(body).encode()

    last_err: str = ""
    for attempt in range(1, max_retries + 1):
        req = urllib.request.Request(ANTHROPIC_API, data=data, method="POST",
                                     headers={
                                         "x-api-key": api_key,
                                         "anthropic-version": "2023-06-01",
                                         "content-type": "application/json",
                                     })
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                payload = json.loads(resp.read().decode())
            content = payload["content"][0]["text"]
            usage = payload.get("usage", {})
            return content, usage
        except urllib.error.HTTPError as e:
            err = e.read().decode(errors="replace")
            # 429 / 5xx are retryable. 4xx (except 429) usually mean malformed request.
            if e.code == 429 or 500 <= e.code < 600:
                last_err = f"HTTP {e.code}: {err[:300]}"
                wait = 2 ** attempt
                print(f"      retry {attempt}/{max_retries} in {wait}s ({last_err[:100]}...)")
                time.sleep(wait)
                continue
            raise RuntimeError(f"Anthropic POST -> HTTP {e.code}: {err}")
        except (urllib.error.URLError, socket.timeout, ConnectionResetError) as e:
            last_err = str(e)
            wait = 2 ** attempt
            print(f"      retry {attempt}/{max_retries} in {wait}s (network: {last_err[:100]})")
            time.sleep(wait)
            continue

    raise RuntimeError(f"Anthropic POST failed after {max_retries} retries. Last error: {last_err}")


# Simple {dotted.key} + {dotted.key|filter} substitution. Empty value if missing.
PROMPT_VAR_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_.]*(?:\|[a-z]+)*)\}")

PROMPT_FILTERS = {
    "lower": str.lower,
    "upper": str.upper,
    "title": str.title,
}


def _resolve_dot(ctx: dict, dotted: str) -> str:
    cur = ctx
    for part in dotted.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return ""
        if cur is None:
            return ""
    if isinstance(cur, (list, dict)):
        return json.dumps(cur)
    return str(cur)


def prompt_render(template: str, ctx: dict) -> str:
    def repl(m: re.Match) -> str:
        expr = m.group(1)
        parts = expr.split("|")
        value = _resolve_dot(ctx, parts[0])
        for f in parts[1:]:
            if f in PROMPT_FILTERS:
                value = PROMPT_FILTERS[f](value)
        return value
    return PROMPT_VAR_RE.sub(repl, template)


def load_prompt(site_dir: Path, archetype: str) -> tuple[str, str, dict]:
    """Return (system_prompt, user_prompt_template, frontmatter)."""
    system_path = site_dir / "prompts" / "_system.md"
    if not system_path.exists():
        die(f"Missing system prompt at {system_path}")
    system_prompt = system_path.read_text().strip()

    user_path = site_dir / "prompts" / f"{archetype}.md"
    if not user_path.exists():
        return system_prompt, "", {}

    raw = user_path.read_text()
    # Parse frontmatter
    fm: dict = {}
    body = raw
    if raw.startswith("---\n"):
        end = raw.find("\n---\n", 4)
        if end > 0:
            fm_block = raw[4:end]
            body = raw[end + 5:]
            for line in fm_block.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    v = v.strip()
                    if v.isdigit():
                        fm[k.strip()] = int(v)
                    else:
                        fm[k.strip()] = v
    return system_prompt, body.strip(), fm


SENSITIVE_BLOCK = (
    "# Sensitive content guardrails (REQUIRED)\n\n"
    "This service involves sensitive contexts. Apply these additional rules:\n\n"
    "- Use a clinical, empathetic tone. Avoid graphic detail.\n"
    "- Do not describe the scene, the substances, or the trauma directly.\n"
    "- Focus on logistics: discretion, certifications, insurance, response, what the visitor can expect from us.\n"
    "- FAQ topics should be: privacy, response time, certifications, insurance, family/property coordination — NOT details of the incident.\n"
    "- Acknowledge difficulty briefly; do not dwell.\n"
)


def build_prompt_context(
    page: dict,
    plan_input: dict,
    client: dict,
    services_lookup: dict,
    areas_lookup: dict,
    blog_topics_lookup: dict,
    prompt_fm: dict,
) -> dict:
    """Resolve a flat ctx dict for prompt substitution."""
    arc = page["archetype"]
    url = page["url_path"]
    parts = [p for p in url.split("/") if p]

    brand = dict(plan_input.get("brand", {}))
    primary_area = next((a for a in plan_input.get("service_areas", []) if a.get("primary")),
                        plan_input.get("service_areas", [{}])[0])
    brand.setdefault("primary_city", primary_area.get("city", ""))
    brand.setdefault("primary_state", primary_area.get("state", ""))
    brand.setdefault("display_name", client.get("display_name", ""))
    brand["domain"] = client["domain"]
    brand["canonical_url"] = f"https://{client['domain']}"
    # license_numbers_suffix is " (#X, #Y)" or ""
    licnums = brand.get("license_numbers", [])
    if licnums:
        brand["license_numbers_suffix"] = " (#" + ", #".join(licnums) + ")"
    else:
        brand["license_numbers_suffix"] = ""

    ctx = {
        "brand": brand,
        "page": page,
        "target_word_count": prompt_fm.get("target_word_count", 700),
        "faq_count": prompt_fm.get("faq_count", 4),
        "sensitive_block": "",
    }

    # Archetype-specific extras
    if arc == "service-landing":
        svc = services_lookup.get(parts[-1], {})
        svc["short_or_display_name"] = svc.get("short_name") or svc.get("display_name", "")
        ctx["service"] = svc
        if svc.get("content_guardrails") == "sensitive":
            ctx["sensitive_block"] = SENSITIVE_BLOCK
    elif arc == "service-area":
        ctx["area"] = areas_lookup.get(parts[-1], {})
    elif arc == "service-area-service":
        area = areas_lookup.get(parts[1], {})
        svc = services_lookup.get(parts[2], {})
        svc["short_or_display_name"] = svc.get("short_name") or svc.get("display_name", "")
        ctx["area"] = area
        ctx["service"] = svc
        if svc.get("content_guardrails") == "sensitive":
            ctx["sensitive_block"] = SENSITIVE_BLOCK
    elif arc == "blog-post":
        slug = parts[-1]
        ctx["post"] = blog_topics_lookup.get(slug, {})
    elif arc == "legal":
        ctx["legal_ref"] = parts[-1]

    return ctx


def parse_llm_json(text: str) -> dict:
    """Robust JSON parse — strip code fences if present."""
    text = text.strip()
    if text.startswith("```"):
        # Strip opening fence (```json or ```)
        text = re.sub(r"^```[a-z]*\n", "", text)
        text = re.sub(r"\n```\s*$", "", text)
    return json.loads(text)


def update_content_md(
    site_dir: Path,
    page: dict,
    body_markdown: str,
    faq: list,
) -> Path:
    """Re-write the markdown for a page, updating body and faq while preserving
    the existing frontmatter structure."""
    arc = page["archetype"]
    coll, _ = ARCHETYPE_TO_COLLECTION[arc]
    fname = derive_filename(page)
    path = site_dir / "src" / "content" / coll / f"{fname}.md"
    if not path.exists():
        die(f"Cannot render — content file missing: {path}. Did you run scaffold?")

    raw = path.read_text()
    # Split frontmatter from body
    if not raw.startswith("---\n"):
        die(f"Malformed frontmatter in {path}")
    end = raw.find("\n---\n", 4)
    if end < 0:
        die(f"Unclosed frontmatter in {path}")
    fm_block = raw[4:end]
    # Parse fm_block line-by-line — same shape we wrote in write_content_md
    fm: dict = {}
    for line in fm_block.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        k = k.strip()
        v = v.strip()
        if v.startswith("[") or v.startswith("{") or v in ("true", "false", "null"):
            try:
                fm[k] = json.loads(v)
            except json.JSONDecodeError:
                fm[k] = v
        elif v.startswith('"') and v.endswith('"'):
            fm[k] = json.loads(v) if v.startswith('"') else v
        elif re.match(r"^-?\d+(\.\d+)?$", v):
            fm[k] = float(v) if "." in v else int(v)
        else:
            fm[k] = v

    # HOUSE LAW (Santino 2026-08-05, enforced here 2026-08-31 after TDI shipped
    # 2,582 of them): NO EM DASHES in anything client-facing. The restoration
    # content-writer prompt bans them but the construction/plumbing prompts
    # didn't, and prompts drift — this strip is the guarantee. Applies to the
    # body and every string frontmatter field (titles, meta descriptions, FAQ).
    def _no_em(s):
        if isinstance(s, str) and "—" in s:
            s = re.sub(r"\s*—\s*", ", ", s)
            s = re.sub(r",\s*,", ",", s)
            s = re.sub(r"([.!?:;])\s*,\s*", r"\1 ", s)
        return s
    body_markdown = _no_em(body_markdown)
    faq = [{k: _no_em(v) for k, v in item.items()} for item in faq] \
        if isinstance(faq, list) else faq
    fm = {k: _no_em(v) for k, v in fm.items()}

    # Update render-specific fields
    fm["faq"] = faq
    fm["generated_at"] = now_iso()
    # Mark as rendered (not just scaffolded) by clearing the placeholder marker
    fm["rendered"] = True

    # Re-serialize
    lines = ["---"]
    for k, v in fm.items():
        if isinstance(v, (list, dict, bool)):
            lines.append(f"{k}: {json.dumps(v)}")
        elif isinstance(v, (int, float)):
            lines.append(f"{k}: {v}")
        else:
            escaped = str(v).replace('"', '\\"')
            lines.append(f'{k}: "{escaped}"')
    lines.append("---")
    lines.append(body_markdown.strip())

    path.write_text("\n".join(lines) + "\n")
    return path


def cost_estimate(usage: dict, model: str) -> float:
    """Rough USD cost estimate for one Anthropic call."""
    # Sonnet 4.6 (as of 2026): $3/MTok input, $15/MTok output, $0.30 cache read, $3.75 cache create (5m)
    inp = usage.get("input_tokens", 0)
    out = usage.get("output_tokens", 0)
    cache_r = usage.get("cache_read_input_tokens", 0)
    cache_w = usage.get("cache_creation_input_tokens", 0)
    return (inp * 3 + cache_r * 0.30 + cache_w * 3.75 + out * 15) / 1_000_000


def log_cost(site_dir: Path, page: dict, usage: dict, model: str, dollars: float) -> None:
    log = site_dir / ".rank-ai" / "cost-log.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a") as f:
        f.write(json.dumps({
            "ts": now_iso(),
            "url": page["url_path"],
            "archetype": page["archetype"],
            "model": model,
            "usage": usage,
            "dollars": round(dollars, 6),
        }) + "\n")


# ----------------------------------------------------------------------------
# Subcommand: render
# ----------------------------------------------------------------------------


def _is_already_rendered(site_dir: Path, page: dict) -> bool:
    """Check if the content file already has rendered: true in frontmatter."""
    arc = page["archetype"]
    coll, _ = ARCHETYPE_TO_COLLECTION[arc]
    fname = derive_filename(page)
    path = site_dir / "src" / "content" / coll / f"{fname}.md"
    if not path.exists():
        return False
    try:
        raw = path.read_text()
        if not raw.startswith("---\n"):
            return False
        end = raw.find("\n---\n", 4)
        if end < 0:
            return False
        fm_block = raw[4:end]
        for line in fm_block.splitlines():
            if line.startswith("rendered: true"):
                return True
            if line.startswith("manual_override: true"):
                return True
    except Exception:
        pass
    return False


def cmd_render(args) -> int:
    import concurrent.futures
    import threading

    slug = args.slug
    client = load_json(CLIENTS_DIR / f"{slug}.json")
    plan_input = load_json(CLIENTS_DIR / slug / "plan-input.json")
    plan_input["_slug"] = slug
    url_plan = load_json(CLIENTS_DIR / slug / "plan" / "url-plan.json")

    site_dir = SITES_DIR / slug
    if not site_dir.exists():
        die(f"Site dir {site_dir} doesn't exist. Run scaffold first.")

    # Build lookups (catalogs resolved from the client's vertical, fail-loud)
    catalog = load_json(verticals.resolve_template(slug, "services.json", client=client))
    catalog_by_slug = {s["slug"]: s for s in catalog["services"]}
    services_lookup = {
        s: catalog_by_slug[s] for s in plan_input.get("services", []) if s in catalog_by_slug
    }
    areas_lookup = {a["slug"]: a for a in plan_input.get("service_areas", [])}
    blog_topics = load_json(verticals.resolve_template(slug, "seed-blog-topics.json", client=client))
    blog_topics_lookup = {t["slug"]: t for t in blog_topics["topics"]}

    # Filter pages
    pages = url_plan["pages"]
    if args.archetype:
        pages = [p for p in pages if p["archetype"] == args.archetype]
    if args.url:
        pages = [p for p in pages if p["url_path"] == args.url]
    # Order by priority desc so high-value pages render first (best output if interrupted)
    pages.sort(key=lambda p: -p.get("priority", 0))
    if args.limit:
        pages = pages[: args.limit]

    if not pages:
        die("No pages matched the filter.")

    # Skip already-rendered unless --force
    skipped_pre = 0
    if not args.force:
        filtered = []
        for p in pages:
            if _is_already_rendered(site_dir, p):
                skipped_pre += 1
            else:
                filtered.append(p)
        pages = filtered

    total_target = len(pages)
    print(f"==> Rendering {total_target} page(s) for {slug}")
    if skipped_pre:
        print(f"    Skipping {skipped_pre} already-rendered (use --force to override).")
    print(f"    Model: {args.model}")
    print(f"    Workers: {args.workers}")
    if args.archetype:
        print(f"    Archetype filter: {args.archetype}")
    if args.limit:
        print(f"    Limit: {args.limit}")
    print()

    cost_lock = threading.Lock()
    print_lock = threading.Lock()
    done_counter = {"n": 0}
    total_cost = 0.0
    succeeded = 0
    failed: list = []
    rendered_paths: list = []

    def render_one(page: dict) -> tuple[str, dict | str]:
        """Returns (status, info). status ∈ {success, no_prompt, api_error, non_json, empty}."""
        arc = page["archetype"]
        url = page["url_path"]
        system_prompt, user_template, prompt_fm = load_prompt(site_dir, arc)
        if not user_template:
            return ("no_prompt", url)
        ctx = build_prompt_context(page, plan_input, client, services_lookup,
                                   areas_lookup, blog_topics_lookup, prompt_fm)
        user_prompt = prompt_render(user_template, ctx)
        try:
            raw, usage = anthropic_call(system_prompt, user_prompt,
                                        model=args.model,
                                        max_tokens=prompt_fm.get("max_tokens", 4096),
                                        temperature=prompt_fm.get("temperature", 0.6))
        except RuntimeError as e:
            return ("api_error", str(e)[:200])
        try:
            data = parse_llm_json(raw)
        except json.JSONDecodeError:
            return ("non_json", raw[:200])
        body = data.get("body_markdown", "").strip()
        faq = data.get("faq", [])
        if not body:
            return ("empty", "")
        md_path = update_content_md(site_dir, page, body, faq)
        dollars = cost_estimate(usage, args.model)
        with cost_lock:
            log_cost(site_dir, page, usage, args.model, dollars)
        return ("success", {
            "body_len": len(body),
            "faq_count": len(faq),
            "dollars": dollars,
            "usage": usage,
            "path": str(md_path),
        })

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_to_page = {executor.submit(render_one, p): p for p in pages}
        for future in concurrent.futures.as_completed(future_to_page):
            page = future_to_page[future]
            arc = page["archetype"]
            url = page["url_path"]
            try:
                status, info = future.result()
            except Exception as e:
                status, info = ("exception", str(e)[:200])

            with print_lock:
                done_counter["n"] += 1
                n = done_counter["n"]
                if status == "success":
                    nonlocal_cost = info["dollars"]
                    total_cost += nonlocal_cost
                    succeeded += 1
                    if info.get("path"):
                        rendered_paths.append(info["path"])
                    print(f"[{n:3}/{total_target}] ✓ {arc} :: {url}")
                    print(f"           {info['body_len']:>5} chars + {info['faq_count']} FAQ  "
                          f"${nonlocal_cost:.4f}  "
                          f"{info['usage'].get('input_tokens',0)}+{info['usage'].get('output_tokens',0)} tok")
                elif status == "no_prompt":
                    print(f"[{n:3}/{total_target}] ⚠ {arc} :: {url} — no prompt for archetype")
                    failed.append((url, "no_prompt"))
                else:
                    print(f"[{n:3}/{total_target}] ✗ {arc} :: {url} — {status}: {info}")
                    failed.append((url, f"{status}: {str(info)[:120]}"))

    print()
    print(f"==> Render summary")
    print(f"    Succeeded:   {succeeded}/{total_target}")
    print(f"    Failed:      {len(failed)}")
    print(f"    Skipped:     {skipped_pre} (already rendered)")
    print(f"    Total cost:  ${total_cost:.4f}")
    if failed:
        print()
        print("    Failures (first 10):")
        for url, reason in failed[:10]:
            print(f"      {url} :: {reason}")

    # Claims lint (truth gate) on the just-rendered batch. Non-fatal by design
    # but LOUD: error hits mean the batch asserts availability / certification /
    # license / response-time claims the brand truth data does not support
    # (the davis-construction incident class). Fix before push/cut-over.
    if rendered_paths:
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            import claims_lint
            truth = claims_lint.load_truth(slug)
            violations: list = []
            for mp in rendered_paths:
                violations.extend(claims_lint.lint_file(Path(mp), truth, rel_root=site_dir))
            errors = [v for v in violations if v["severity"] == "error"]
            print()
            print("==> Claims lint (truth gate) on this render batch")
            if not violations:
                print(f"    Clean — {len(rendered_paths)} file(s), no unverified claims.")
            else:
                for v in violations:
                    print(f"    [{v['severity'].upper():6}] {v['family']:13} "
                          f"{v['part']:11} {v['file']}")
                    print(f"             ...{v['context'][:120]}...")
                if errors:
                    print()
                    print("    " + "!" * 70)
                    print(f"    !! {len(errors)} ERROR-severity claim(s) in this batch — the content")
                    print("    !! asserts things the brand truth data does not support.")
                    print("    !! DO NOT push-main / cut-over until fixed. Re-check with:")
                    print(f"    !!   python3 scripts/claims_lint.py --slug {slug}")
                    print("    " + "!" * 70)
        except Exception as e:  # noqa: BLE001 — the gate must never break a render run
            print(f"    [warn] claims lint failed (non-fatal): {str(e)[:160]}")

    # Update client record
    client.setdefault("build", {})
    if succeeded:
        client["build"]["last_rendered_at"] = now_iso()
        client["build_status"] = "content_rendered" if succeeded == len(pages) else "content_partial"
    save_json(CLIENTS_DIR / f"{slug}.json", client)

    if args.push and succeeded > 0:
        print()
        print("==> Pushing to staging branch...")
        git_init_and_push(
            site_dir,
            client["build"]["github_repo"].split("/", 1)[1],
            f"Render {succeeded} page(s) via build_site.py at {now_iso()}",
        )
        print("    Pushed.")

    return 0 if not failed else 2


# ----------------------------------------------------------------------------
# Subcommand: scaffold
# ----------------------------------------------------------------------------


def _company_domain_from_app(cid: str | None) -> tuple[str | None, str | None]:
    """The app's record of the client's domain: companies.website first, then
    marketing_sites.domain (Air Care 2026-08-14: clients/{slug}.json had
    domain null while the company card said www.aircarerestoration.com all
    along — the build agent hand-stamped it). Returns (bare_host, source) or
    (None, None); 'https://www.foo.com/x' normalizes to 'foo.com'."""
    sb_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    sb_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not (cid and sb_url and sb_key):
        return None, None
    hdr = {"apikey": sb_key, "Authorization": f"Bearer {sb_key}"}

    def _norm(d) -> str:
        d = re.sub(r"^https?://", "", str(d or "").strip().lower()).split("/")[0]
        return d[4:] if d.startswith("www.") else d

    for path, field, src in (
            (f"/rest/v1/companies?id=eq.{cid}&select=website",
             "website", "companies.website"),
            (f"/rest/v1/marketing_sites?company_id=eq.{cid}&select=domain",
             "domain", "marketing_sites.domain")):
        try:
            r = requests.get(f"{sb_url}{path}", headers=hdr, timeout=20)
            for row in (r.json() if r.ok else []):
                dom = _norm(row.get(field))
                if dom and "." in dom and not dom.endswith((".invalid", ".pages.dev")):
                    return dom, src
        except Exception:
            continue
    return None, None



def _palette_from_logo(logo_path) -> dict | None:
    """Auto-extract a brand palette from the client's logo (Santino 2026-09-04:
    Frontline scaffolded default-red under an orange/blue logo — brand colors
    must be automatic, not a step someone remembers).

    Clusters saturated pixels by hue: the biggest cluster's weighted mean is
    primary, the second (when it holds >= 12% of colored pixels) is accent, and
    dark is a deep shade of primary so page surfaces stay on-brand. Returns
    None — leaving the standardized black default — when the logo is missing,
    effectively monochrome, or PIL is unavailable (CI without Pillow)."""
    try:
        import colorsys as _cs
        from collections import defaultdict
        from PIL import Image
    except ImportError:
        print("      palette: Pillow not installed — keeping standardized default")
        return None
    try:
        im = Image.open(logo_path).convert("RGBA")
        im.thumbnail((300, 300))
        clusters: dict[int, list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])
        colored = 0
        for r, g, b, a in im.getdata():
            if a < 200:
                continue
            h, l, sat = _cs.rgb_to_hls(r / 255, g / 255, b / 255)
            if sat < 0.25 or l > 0.92 or l < 0.08:
                continue  # grey / white / black pixels are not brand hues
            colored += 1
            c = clusters[int(h * 12) % 12]  # 30-degree hue buckets
            c[0] += r; c[1] += g; c[2] += b; c[3] += 1
        if colored < 150:  # logo is essentially monochrome — black default is right
            return None
        ranked = sorted(clusters.values(), key=lambda c: -c[3])

        def _hex(c):
            n = c[3]
            return "#%02x%02x%02x" % (round(c[0] / n), round(c[1] / n), round(c[2] / n))

        primary = _hex(ranked[0])
        accent = None
        if len(ranked) > 1 and ranked[1][3] >= colored * 0.12:
            accent = _hex(ranked[1])
        # dark surface = NEUTRAL charcoal (2026-09-11 law — see _neutral_dark:
        # brand-tinted canvases made whole sites read as one color)
        dark = _neutral_dark(primary)
        out = {"primary_color": primary, "dark_color": dark}
        if accent:
            out["accent_color"] = accent
        return out
    except Exception as e:  # noqa: BLE001 — never fail a scaffold over colors
        print(f"      palette: extraction errored ({str(e)[:80]}) — keeping default")
        return None


def _neutral_dark(primary_hex: str) -> str:
    """Dark SURFACES are neutral, never the brand color (Santino 2026-09-11,
    DryCor: petrol-blue canvases made the whole site read blue; the winning
    variant kept every dark surface near-black charcoal, with the brand color
    living only in small doses — links, icons, the logo — and ONE saturated
    action color reserved for CTAs). This keeps at most a whisper of the
    primary's hue (saturation <= 0.06) at lightness 0.09, so surfaces read
    neutral while still being microscopically the client's own."""
    import colorsys as _cs
    try:
        h, l, s = _cs.rgb_to_hls(*(int(primary_hex[i:i + 2], 16) / 255
                                   for i in (1, 3, 5)))
    except Exception:  # noqa: BLE001
        return "#16181d"
    # EXCEPTION (Santino 2026-09-11): a brand color that is ALREADY dark and
    # muted (deep navy, forest, near-black) works as a canvas — that identity
    # survives at wall size, and forcing charcoal there would make every
    # dark-theme site look the same. Only saturated or lighter primaries
    # (DryCor's petrol at 0.70 saturation was the failure) get neutralized.
    if l <= 0.22 and s <= 0.50:
        r, g, b = _cs.hls_to_rgb(h, min(l, 0.13), s)
        return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))
    r, g, b = _cs.hls_to_rgb(h, 0.09, min(s, 0.06))
    return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


def _palette_from_site(domain: str | None) -> list[str]:
    """Brand hues from the client's EXISTING website (2026-09-11, DryCor:
    logo-only extraction picked teal while drycor.com is saturated in
    #e4002b red everywhere — the live site's CSS is the strongest
    brand-truth signal we have, so it now outranks the logo)."""
    if not domain:
        return []
    try:
        import re as _re
        import colorsys as _cs
        from collections import defaultdict
        import requests as _rq
        html = _rq.get(f"https://{domain}", timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (rank-ai brand scan)"}).text
        blobs = [html]
        for href in _re.findall(
                r'<link[^>]+rel=["\']stylesheet["\'][^>]+href=["\']([^"\']+)',
                html)[:3]:
            if href.startswith("//"):
                href = "https:" + href
            elif href.startswith("/"):
                href = f"https://{domain}" + href
            if href.startswith("http"):
                try:
                    blobs.append(_rq.get(href, timeout=10).text)
                except Exception:  # noqa: BLE001
                    pass
        clusters: dict[int, list[float]] = defaultdict(
            lambda: [0.0, 0.0, 0.0, 0])
        for blob in blobs:
            for hx in _re.findall(r"#([0-9a-fA-F]{6})\b", blob):
                r, g, b = (int(hx[i:i + 2], 16) for i in (0, 2, 4))
                h, l, sat = _cs.rgb_to_hls(r / 255, g / 255, b / 255)
                if sat < 0.25 or l > 0.92 or l < 0.08:
                    continue
                c = clusters[int(h * 12) % 12]
                c[0] += r; c[1] += g; c[2] += b; c[3] += 1
        ranked = sorted((c for c in clusters.values() if c[3] >= 3),
                        key=lambda c: -c[3])
        return ["#%02x%02x%02x" % (round(c[0] / c[3]), round(c[1] / c[3]),
                                   round(c[2] / c[3])) for c in ranked[:4]]
    except Exception:  # noqa: BLE001 — never fail a scaffold over colors
        return []


def _auto_palette(logo_path, domain: str | None):
    """Site CSS hues first, logo as confirmation/fallback."""
    import colorsys as _cs

    def hue(hx):
        return _cs.rgb_to_hls(*(int(hx[i:i + 2], 16) / 255
                                for i in (1, 3, 5)))[0]

    site = _palette_from_site(domain)
    logo = _palette_from_logo(logo_path)
    if not site:
        return logo
    primary = site[0]
    accent = None
    candidates = site[1:] + ([logo.get("accent_color"),
                              logo.get("primary_color")] if logo else [])
    for cand in candidates:
        if not cand:
            continue
        d = abs(hue(cand) - hue(primary))
        if min(d, 1 - d) >= 0.12:
            accent = cand
            break
    dark = _neutral_dark(primary)
    out = {"primary_color": primary, "dark_color": dark}
    if accent:
        out["accent_color"] = accent
    return out


def cmd_scaffold(args) -> int:
    slug = args.slug
    client = load_json(CLIENTS_DIR / f"{slug}.json")
    plan_input_path = CLIENTS_DIR / slug / "plan-input.json"
    if not plan_input_path.exists():
        die(f"Missing plan input at {plan_input_path}. Run rank-ai-plan-site first.")
    plan_input = load_json(plan_input_path)
    plan_input["_slug"] = slug   # carry slug for placeholder body
    cid = client.get("company_id") or company_id_for_slug(slug)

    # Domain pre-check (2026-08-14): the client record missing a domain used to
    # hard-refuse at token time even when the app already knew it. Heal from
    # the app company record before hydration; only a domain truly known
    # NOWHERE proceeds — loudly — on the {slug}.invalid placeholder, which
    # sync-deploy's rehydration guard heals once the real domain lands.
    allow_placeholder = False
    _dom = str(client.get("domain") or "").strip()
    if not _dom or _dom.lower() == "none":
        app_domain, dom_src = _company_domain_from_app(cid)
        if app_domain:
            client["domain"] = app_domain
            client["updated_at"] = now_iso()
            save_json(CLIENTS_DIR / f"{slug}.json", client)
            print(f"    domain: {app_domain} stamped onto clients/{slug}.json "
                  f"from the app ({dom_src}) — record had none")
        else:
            allow_placeholder = True
            print(f"    WARNING: no domain anywhere — clients/{slug}.json AND the app "
                  "company record are both empty.")
            print(f"             Scaffolding on the {slug}.invalid placeholder; canonicals, "
                  "robots.txt and llms.txt")
            print("             carry it until a real domain lands (sync-deploy rehydrates "
                  "them automatically).")
            print("             Do NOT cut this site over before that.")

    url_plan_path = CLIENTS_DIR / slug / "plan" / "url-plan.json"
    internal_links_path = CLIENTS_DIR / slug / "plan" / "internal-links.json"
    if not url_plan_path.exists() or not internal_links_path.exists():
        die(f"Missing plan artifacts in {url_plan_path.parent}. Run rank-ai-plan-site generate.")
    url_plan = load_json(url_plan_path)
    internal_links = load_json(internal_links_path)

    site_dir = SITES_DIR / slug
    repo_name = f"{slug}-site"

    print(f"==> Scaffolding {slug} → {site_dir}")
    print(f"    Plan URLs: {len(url_plan['pages'])}")
    print(f"    GitHub repo: {GH_OWNER}/{repo_name}")
    print()

    # Step 1: Copy starter + substitute tokens
    print("[1/5] Copying starter and substituting brand tokens...")
    copy_starter(site_dir)
    if (plan_input.get("brand", {}) or {}).get("theme") == "light":
        n = apply_light_overlay(site_dir)
        print(f"      light theme: {n} overlay file(s) applied")

    # VERTICAL RENDER PROMPTS (2026-08-19, the rt-olson lesson: a plumbing
    # site scaffolded with restoration prompts — the model wrote 124 clean
    # plumbing pages anyway but refused the services hub outright). When
    # templates/{vertical}/prompts/render/ exists, its briefs OVERLAY the
    # starter's restoration set. The vertical dir is canonical: it also
    # overwrites per-site copies on re-scaffold, so prompt fixes graduate
    # into the template instead of living as site-local patches.
    vertical = str(client.get("vertical") or "restoration").lower()
    vdir = TEMPLATES_DIR / vertical / "prompts" / "render"
    if vdir.is_dir():
        vn = 0
        for f in vdir.glob("*.md"):
            shutil.copy2(f, site_dir / "prompts" / f.name)
            vn += 1
        print(f"      vertical prompts ({vertical}): {vn} brief(s) overlaid")

    # Client's uploaded logo from the branding bucket (Air Care 2026-08-14:
    # the ledger's nightly pass pulls these, the scaffold did not — every
    # build whose client had already uploaded a logo got hand-fixed). Same
    # helper the ledger uses; must run AFTER copy_starter (which resets
    # public/) and BEFORE token resolution (logoUrl points at the local file).
    brand_block = plan_input.setdefault("brand", {})
    pulled_logo = None
    if cid:
        try:
            from brand_assets import pull_bucket_logo
            pulled_logo = pull_bucket_logo(cid, slug)
        except Exception as e:
            print(f"      logo: bucket pull errored ({str(e)[:120]}) — keeping default")
    if pulled_logo:
        # In-memory only — plan-input.json on disk stays as intake wrote it.
        # An explicit brand.logo_url still wins.
        brand_block.setdefault("logo_url", f"/images/{pulled_logo}")
        # CURATED-LOGO GUARD (DryCor 2026-09-11: a hand-tuned horizontal
        # header logo from the client's brand kit was clobbered by the raw
        # bucket file on re-scaffold). A logo already COMMITTED for this
        # site is curated truth — the bucket pull only stands when the repo
        # has no version of its own.
        try:
            committed = subprocess.run(
                ["git", "show", f"HEAD:sites/{slug}/public/images/{pulled_logo}"],
                capture_output=True, cwd=REPO_ROOT).stdout
            _cur = SITES_DIR / slug / "public" / "images" / pulled_logo
            if committed and _cur.exists() and _cur.read_bytes() != committed:
                _cur.write_bytes(committed)
                print("      logo: kept the curated committed version "
                      "(bucket file differs)")
        except Exception:  # noqa: BLE001 — guard must never kill a scaffold
            pass
        print(f"      logo: pulled from branding bucket -> public/images/{pulled_logo} "
              f"(logoUrl {brand_block['logo_url']})")
        # Auto-palette (2026-09-04): no colors anywhere -> read them off the
        # logo and PERSIST to plan-input.json so retint and re-scaffolds agree.
        has_colors = bool(brand_block.get("primary_color")
                          or (brand_block.get("colors") or {}).get("primary"))
        if not has_colors:
            pal = _auto_palette(
                SITES_DIR / slug / "public" / "images" / pulled_logo,
                client.get("domain"))
            if pal:
                brand_block.update(pal)
                save_json(plan_input_path, {k: v for k, v in plan_input.items()
                                            if k != "_slug"})
                print(f"      palette: auto-extracted from live site + logo — "
                      f"primary {pal['primary_color']}"
                      f" accent {pal.get('accent_color', '(none)')} dark {pal['dark_color']}")
    else:
        print(f"      NOTE: no logo in branding bucket for {cid or slug} — scaffolding "
              "with the default logoUrl.")
        print("            (Client uploads land via the hub's Send Us Files page; "
              "re-run scaffold or setup_ledger to pull later.)")

    string_tokens, json_tokens = resolve_tokens(
        client, plan_input, allow_missing_domain=allow_placeholder)
    llms_tokens = build_llms_substitutions(
        plan_input, client, allow_placeholder=allow_placeholder)
    all_tokens = {**string_tokens, **json_tokens, **llms_tokens}
    files_changed, leftover = substitute_in_tree(site_dir, all_tokens)
    if leftover:
        print(f"      WARNING: {len(leftover)} unsubstituted tokens: {sorted(leftover)}")
    print(f"      Files modified: {files_changed}")

    # IndexNow proof-of-ownership file, minted HERE so it is part of the very
    # first push. Bing caches its verdict on the (host, key) pair forever, so a
    # key must never be pinged before its file is serving — see THE 403 TRAP.
    # `client` is mutated in place and saved at step 6 below.
    ensure_indexnow_key(slug, client)

    # Step 2: Generate content collection markdown
    print(f"[2/5] Generating {len(url_plan['pages'])} content collection entries...")
    # Make sure src/content has fresh subdirectories
    content_root = site_dir / "src" / "content"
    for sub in ("pages", "services", "serviceAreas", "locations", "blog", "legal"):
        (content_root / sub).mkdir(parents=True, exist_ok=True)
    count = render_all_content(site_dir, plan_input, url_plan, internal_links)
    print(f"      Wrote {count} markdown files.")

    # Step 3: Create GitHub repo (idempotent)
    print(f"[3/5] Ensuring GitHub repo {GH_OWNER}/{repo_name} exists...")
    if gh_repo_exists(repo_name):
        print("      Repo already exists, reusing.")
    else:
        description = f"Rank AI restoration site for {client['display_name']}."
        gh_create_repo(repo_name, description, private=args.private)
        print("      Repo created.")

    # Step 4: Git init + commit + push (main + staging)
    print("[4/5] Pushing to GitHub (main + staging)...")
    commit = args.message or f"Scaffold from rank-ai-build-site at {now_iso()}"
    try:
        git_init_and_push(site_dir, repo_name, commit)
    finally:
        # ALWAYS remove the nested .git, even when the push dies — so the
        # monorepo tracks files directly instead of recording sites/{slug}/
        # as a submodule pointer. A push failure that left .git behind is how
        # rt-olson got committed as a gitlink and re-scaffolded for 8 nights
        # (2026-08-10..18). A re-run re-inits from scratch, so nothing is
        # lost by stripping here.
        nested_git = site_dir / ".git"
        if nested_git.exists():
            import shutil as _shutil
            _shutil.rmtree(nested_git)
            print("      Removed nested .git (monorepo-safe).")
    print("      Pushed to main and staging.")

    # Step 5: Cloudflare Pages project (gated on OAuth)
    print(f"[5/5] Creating Cloudflare Pages project rankai-{slug} (Git-connected)...")
    cf_token, account_id = cf_creds()
    project_name = f"rankai-{slug}"
    pages_status = "skipped"
    if cf_pages_project_exists(account_id, project_name, cf_token):
        print(f"      Pages project {project_name} already exists, reusing.")
        pages_status = "exists"
    else:
        try:
            cf_create_pages_project(account_id, project_name, repo_name, cf_token)
            print(f"      Pages project created.")
            pages_status = "created"
        except RuntimeError as e:
            err = str(e)
            if "github" in err.lower() and ("not authorized" in err.lower() or "10000" in err or "permission" in err.lower()):
                print()
                print("      ⚠ Cloudflare ↔ GitHub OAuth not yet authorized for this account.")
                print("        One-time manual step required:")
                print(f"          1. Open https://dash.cloudflare.com/{account_id}/workers-and-pages")
                print("          2. Create application → Pages → Connect to Git → authorize 'restorationai'")
                print("          3. Re-run this scaffold command (it's idempotent)")
                print()
                print("        Everything else succeeded; the repo is on GitHub and ready.")
                pages_status = "oauth_required"
            else:
                print(f"      Pages create failed: {err}")
                pages_status = "failed"

    # Step 6: Update client record
    client["build"] = client.get("build", {})
    client["build"].update({
        "scaffolded_at": now_iso(),
        "github_repo": f"{GH_OWNER}/{repo_name}",
        "pages_project": project_name,
        "starter_version": (STARTER_DIR / "VERSION").read_text().strip(),
        "url_count": len(url_plan["pages"]),
        "pages_status": pages_status,
    })
    client["build_status"] = "scaffolded"
    client["updated_at"] = now_iso()
    save_json(CLIENTS_DIR / f"{slug}.json", client)

    work_log(
        client.get("company_id") or company_id_for_slug(slug), "site",
        "preview-built",
        f"Built the first working preview of the new website — "
        f"{len(url_plan['pages'])} pages scaffolded and pushed for review.",
        evidence={"slug": slug, "github_repo": f"{GH_OWNER}/{repo_name}",
                  "pages_project": project_name, "url_count": len(url_plan["pages"])},
        source="build_site.py scaffold")

    print()
    print("==> Scaffold complete.")
    print(f"    Local working tree: {site_dir}")
    print(f"    GitHub repo:        https://github.com/{GH_OWNER}/{repo_name}")
    if pages_status in ("created", "exists"):
        print(f"    Pages project:      https://dash.cloudflare.com/{account_id}/pages/view/{project_name}")
    print()
    print("    Next: implement render to populate page body content + images,")
    print("          then push-staging to preview at *.pages.dev.")
    return 0


# ----------------------------------------------------------------------------
# Subcommand: status
# ----------------------------------------------------------------------------


def cmd_retint(args) -> int:
    """Re-derive the colour files from plan-input without a full re-scaffold.

    Only two files in a built site carry brand colour — tailwind.config.mjs and
    public/favicon.svg — and both are pure token substitutions of the starter.
    When a client's real palette arrives after the build (a brand guide, a logo
    sample), re-running scaffold would re-render every page and cost real money;
    this rewrites just the colour surface.

    It also repairs sites scaffolded before the full 50→950 ramp generator
    landed, which carry stock Tailwind rungs around a correct DEFAULT — e.g.
    PuroClean's primary-700 hover was generic #b91c1c instead of a darkened
    #D12229."""
    slug = args.slug
    site_dir = SITES_DIR / slug
    if not site_dir.exists():
        die(f"No site at {site_dir}")
    client = load_json(CLIENTS_DIR / f"{slug}.json")
    plan_input = load_json(CLIENTS_DIR / slug / "plan-input.json")
    string_tokens, json_tokens = resolve_tokens(client, plan_input,
                                                allow_missing_domain=True)
    tokens = {**string_tokens, **json_tokens}

    targets = [("tailwind.config.mjs", STARTER_DIR / "tailwind.config.mjs"),
               ("public/favicon.svg", STARTER_DIR / "public" / "favicon.svg")]

    def _mask(text: str) -> set[str]:
        """Lines with colour values blanked, so only STRUCTURE compares."""
        return {re.sub(r"#[0-9a-fA-F]{3,8}\b", "#", l.strip())
                for l in text.splitlines() if l.strip()}

    pending = []
    blocked = []
    for rel, src in targets:
        if not src.exists():
            continue
        dst = site_dir / rel
        new, leftover = substitute_text(src.read_text(), tokens)
        if leftover:
            print(f"    WARNING {rel}: unsubstituted {sorted(leftover)}")
        # Refuse to discard hand-tuning. Anything the CURRENT file has that the
        # regenerated output does not is human work — TRG's AA-contrast
        # rationale, their three-element hand-drawn favicon. The reverse
        # (generated has lines the site lacks) just means the starter moved on
        # since the site was scaffolded, which is exactly what retint is for.
        if dst.exists() and not args.force:
            extra = sorted(_mask(dst.read_text()) - _mask(new))
            if extra:
                blocked.append((rel, extra))
                continue
        if not dst.exists() or dst.read_text() != new:
            pending.append((rel, dst, new))

    # All or nothing: a site with a regenerated favicon but a hand-tuned
    # tailwind would paint two different brand colours.
    if blocked:
        for rel, extra in blocked:
            print(f"    SKIP {rel}: hand-tuned — {len(extra)} line(s) not in the "
                  f"regenerated output, e.g. {extra[0][:70]!r}")
        print(f"    Nothing rewritten for {slug} (retint is all-or-nothing so the "
              f"colour surface stays coherent). Re-run with --force to overwrite.")
        return 1

    changed = []
    for rel, dst, new in pending:
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(new)
        changed.append(rel)

    print(f"==> retint {slug}: primary={tokens.get('BRAND_PRIMARY_COLOR')} "
          f"cta={tokens.get('BRAND_PRIMARY_CTA')} accent={tokens.get('BRAND_ACCENT_COLOR')} "
          f"dark={tokens.get('BRAND_DARK_COLOR')}")
    print(f"    rewrote: {', '.join(changed) if changed else '(nothing — already current)'}")
    if changed:
        print("    Next: sync-deploy --branch main to ship it.")
    return 0


def cmd_status(args) -> int:
    slug = args.slug
    client = load_json(CLIENTS_DIR / f"{slug}.json")
    print(json.dumps({
        "slug": slug,
        "display_name": client.get("display_name"),
        "domain": client.get("domain"),
        "status": client.get("status"),
        "plan_status": client.get("plan_status"),
        "build_status": client.get("build_status"),
        "plan": client.get("plan"),
        "build": client.get("build"),
    }, indent=2))
    return 0


# ----------------------------------------------------------------------------
# Subcommand: sync-deploy  (push monorepo subtree → per-client GitHub repo)
# ----------------------------------------------------------------------------
#
# The Rank AI pipeline lives in a single monorepo (rank-ai/) for orchestration
# and AI-agent context. Each client's deployable site lives at sites/{slug}/.
# Cloudflare Pages can only watch ONE git repo per project, so we push each
# client's subtree to a dedicated per-client GitHub repo at
# github.com/{GH_OWNER}/{slug}-site. Cloudflare watches that repo and rebuilds
# on every push.
#
# Implementation: `git subtree split --prefix=sites/{slug}` builds a synthetic
# branch containing only the subtree's commits, which we then force-push to
# the per-client repo. Force-push because the per-client repo's history (from
# the original scaffold) is incompatible with the subtree's synthetic history.
# The per-client repo is a derived deploy artifact — git history there is not
# meant to be authoritative or human-meaningful. The monorepo is the source of
# truth.


def repo_root() -> Path:
    """Return the monorepo root (where rank-ai/.git lives)."""
    return REPO_ROOT


def _ensure_remote(name: str, url: str, cwd: Path) -> None:
    try:
        existing = git(["remote", "get-url", name], cwd)
        if existing.strip() != url:
            git(["remote", "set-url", name, url], cwd)
    except RuntimeError:
        git(["remote", "add", name, url], cwd)


_REHYDRATE_TARGETS = (
    "src/lib/brand.ts",
    "astro.config.mjs",
    "public/llms.txt",
    "public/ai.txt",
    "public/robots.txt",
    "public/_redirects",
)


def _rehydrate_domain(slug: str, site_dir: Path, mono: Path) -> None:
    """Heal every `https://None` a domain-attached-after-scaffold left behind.

    Scaffold hydrates brand.ts / astro.config.mjs / llms.txt from the client
    record at scaffold time; a client whose domain arrives later ships
    `https://None` in canonicals, schema, and the ENTIRE sitemap (crew3r.com
    served 668 sitemap URLs on host 'none' for 3 days, 2026-08-11). Every
    deploy now re-reads the record and heals the known carriers, committing
    just those files so the fix rides the push it precedes.

    Also heals `{slug}.invalid` (2026-08-14): scaffold's explicit no-domain-
    anywhere path stamps that placeholder instead of crashing, on the promise
    that this guard swaps in the real domain at the next deploy."""
    client_path = CLIENTS_DIR / f"{slug}.json"
    if not client_path.exists():
        return
    domain = str(json.loads(client_path.read_text()).get("domain") or "").strip()
    no_domain = (not domain or domain.lower() == "none"
                 or domain.endswith(".invalid"))
    if no_domain:
        # No real domain to heal FROM — but a served "https://None" host is
        # strictly worse than the sanctioned {slug}.invalid placeholder
        # (which THIS guard swaps for the real domain the moment one lands).
        # 2026-09-05 fleet scan: coastal/dry-county/homelyft/mold-solutionz
        # sat poisoned for weeks precisely because this branch returned.
        placeholder = f"{slug}.invalid"
        changed = []
        for rel in _REHYDRATE_TARGETS:
            p = site_dir / rel
            if not p.exists():
                continue
            s = p.read_text()
            healed = (s.replace("https://images.None", f"https://images.{placeholder}")
                       .replace("https://images.none", f"https://images.{placeholder}")
                       .replace("https://None", f"https://{placeholder}")
                       .replace("https://none/", f"https://{placeholder}/")
                       .replace('domain: "None"', f'domain: "{placeholder}"'))
            if healed != s:
                p.write_text(healed)
                changed.append(rel)
        if changed:
            rels = [f"sites/{slug}/{c}" for c in changed]
            git(["add", *rels], mono)
            git(["commit", "-m",
                 f"{slug}: quarantine stale https://None host behind the "
                 f"{placeholder} placeholder (no real domain on record yet)",
                 "--", *rels], mono)
            print(f"    [rehydrate] NO DOMAIN on record — https://None "
                  f"quarantined as {placeholder}; attach the real domain and "
                  "the next deploy heals it")
        return
    changed = []
    for rel in _REHYDRATE_TARGETS:
        p = site_dir / rel
        if not p.exists():
            continue
        s = p.read_text()
        healed = (s.replace("https://images.None", f"https://images.{domain}")
                   .replace("https://images.none", f"https://images.{domain}")
                   .replace(f"https://images.{slug}.invalid", f"https://images.{domain}")
                   .replace("https://None", f"https://{domain}")
                   .replace("https://none/", f"https://{domain}/")
                   .replace('domain: "None"', f'domain: "{domain}"')
                   .replace(f"{slug}.invalid", domain))
        if healed != s:
            p.write_text(healed)
            changed.append(rel)
    if changed:
        rels = [f"sites/{slug}/{c}" for c in changed]
        git(["add", *rels], mono)
        git(["commit", "-m",
             f"{slug}: rehydrate stale host (https://None / {slug}.invalid) -> "
             f"https://{domain} (domain attached after scaffold; auto-healed at deploy)",
             "--", *rels], mono)
        print(f"    [rehydrate] healed stale host -> https://{domain} in: "
              + ", ".join(changed))


def cmd_sync_deploy(args) -> int:
    slug = args.slug
    branch = args.branch
    site_dir = SITES_DIR / slug
    if not site_dir.exists():
        die(f"No subtree at {site_dir}. Run scaffold first.")

    mono = repo_root()
    if not (mono / ".git").exists():
        die(
            f"Expected monorepo at {mono} with a .git directory. The new topology "
            f"keeps everything in one repo and uses subtree push to ship per-client. "
            f"Run `git init` at {mono} or fix the topology before sync-deploy."
        )

    # Repo name: default to convention, but a client can override via
    # build.github_repo in their client record (useful for clients onboarded
    # before the {slug}-site convention was locked in).
    client_repo = f"{slug}-site"
    client_record_path = mono / "clients" / f"{slug}.json"
    if client_record_path.exists():
        client_record = json.loads(client_record_path.read_text())
        gh_field = client_record.get("build", {}).get("github_repo")
        if gh_field and "/" in gh_field:
            # Stored as "owner/repo" — extract repo part
            client_repo = gh_field.split("/", 1)[1]
    remote_name = f"deploy-{slug}"
    remote_url = f"https://x-access-token:{gh_token()}@github.com/{GH_OWNER}/{client_repo}.git"

    print(f"==> Syncing sites/{slug}/ → github.com/{GH_OWNER}/{client_repo}")
    print(f"    Target branch: {branch}")
    print(f"    Monorepo: {mono}")
    print()

    # LAUNCH-PATH REHYDRATION GUARD (2026-08-11): heal stale https://None
    # before anything ships. Runs on every branch — staging previews with a
    # known domain deserve correct canonicals too.
    _rehydrate_domain(slug, site_dir, mono)

    # Step 1: Working tree must be clean for subtree split to work cleanly
    status = git(["status", "--porcelain"], mono)
    if status.strip() and not args.allow_dirty:
        die(
            "Working tree has uncommitted changes. Subtree push from a dirty tree "
            "is risky. Either commit/stash changes, or re-run with --allow-dirty."
        )

    # Step 2: Ensure the per-client GitHub repo exists
    print(f"[1/4] Checking that github.com/{GH_OWNER}/{client_repo} exists...")
    if not gh_repo_exists(client_repo):
        print(f"      Repo missing. Creating it now...")
        client = load_json(CLIENTS_DIR / f"{slug}.json") if (CLIENTS_DIR / f"{slug}.json").exists() else {}
        description = f"Rank AI restoration site for {client.get('display_name', slug)}."
        gh_create_repo(client_repo, description, private=args.private)
        print(f"      Created.")
    else:
        print(f"      Repo exists, reusing.")

    # Step 3: Configure remote on the monorepo
    print(f"[2/4] Configuring remote {remote_name!r} on monorepo...")
    _ensure_remote(remote_name, remote_url, mono)
    print(f"      Remote set.")

    # Step 4: Subtree split — create a synthetic branch containing only sites/{slug}/'s history
    temp_branch = f"_sync-deploy-{slug}-{branch}"
    print(f"[3/4] Splitting subtree sites/{slug}/ into temp branch {temp_branch!r}...")
    # Clean up any leftover temp branch from a previous run
    try:
        git(["branch", "-D", temp_branch], mono)
    except RuntimeError:
        pass
    git(["subtree", "split", "--prefix", f"sites/{slug}", "-b", temp_branch], mono)
    print(f"      Split complete.")

    # Step 5: Force-push to per-client repo's target branch
    print(f"[4/4] Force-pushing {temp_branch} → {remote_name}/{branch}...")
    git(["push", "--force", remote_name, f"{temp_branch}:{branch}"], mono)
    print(f"      Pushed.")

    # Cleanup
    try:
        git(["branch", "-D", temp_branch], mono)
    except RuntimeError:
        pass

    # Step 6: Update client record
    rec_path = CLIENTS_DIR / f"{slug}.json"
    prev_build_status = None
    if rec_path.exists():
        client = load_json(rec_path)
        prev_build_status = client.get("build_status")
        client.setdefault("build", {})
        client["build"]["github_repo"] = f"{GH_OWNER}/{client_repo}"
        if branch == "main":
            client["build"]["last_pushed_main_at"] = now_iso()
            client["build_status"] = "pushed_main"
        else:
            client["build"]["last_pushed_staging_at"] = now_iso()
            client["build_status"] = "pushed_staging"
        client["updated_at"] = now_iso()
        save_json(rec_path, client)

    # Work ledger (fail-open). Production pushes vastly outnumber first-time
    # launches — the detail reads correctly for both ("updated and deployed").
    _client_rec = load_json(rec_path) if rec_path.exists() else {}
    _cid = _client_rec.get("company_id") or company_id_for_slug(slug)
    _domain = (_client_rec.get("domain") or "").strip()
    if branch == "main":
        _live = f"https://{_domain}/" if _domain else f"https://rankai-{slug}.pages.dev/"
        work_log(_cid, "site", "production-deploy",
                 f"Website updated and deployed to production ({_live}).",
                 evidence={"slug": slug, "branch": branch,
                           "github_repo": f"{GH_OWNER}/{client_repo}", "url": _live},
                 source="build_site.py sync-deploy")
    else:
        work_log(_cid, "site", "staging-deploy",
                 "Updated website pushed to the staging preview for review "
                 "before going live.",
                 evidence={"slug": slug, "branch": branch,
                           "github_repo": f"{GH_OWNER}/{client_repo}",
                           "url": f"https://staging.rankai-{slug}.pages.dev/"},
                 source="build_site.py sync-deploy")

    # PREVIEW-PIPELINE EVENT (Santino 2026-09-12: DryCor's finished build sat
    # 10 days unannounced — the nightly ledger heal was the only seeder and
    # its gate missed pushed_main). The FIRST transition into a built state
    # files a visible ops card THE MOMENT IT HAPPENS. The client reveal
    # itself still rides the soak window + the hold / "share now" note
    # overrides (setup_ledger seeds the ask; client_concierge sends it) —
    # this card is the guarantee a human can see the clock running.
    if (_cid and branch in ("staging", "main")
            and prev_build_status not in ("pushed_staging", "pushed_main",
                                          "preview_ready", "cut_over")):
        _purl = (f"https://staging.rankai-{slug}.pages.dev/" if branch != "main"
                 else f"https://rankai-{slug}.pages.dev/")
        try:
            import requests as _rq
            _base = os.environ["SUPABASE_URL"].rstrip("/")
            _key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
            _rq.post(f"{_base}/rest/v1/marketing_ops_notes", timeout=20,
                     headers={"apikey": _key, "Authorization": f"Bearer {_key}",
                              "Prefer": "return=minimal"},
                     json=[{"company_id": _cid, "status": "open",
                            "author": "build_site.py",
                            "body": f"[PREVIEW PIPELINE] {slug}: first build is "
                                    f"LIVE at {_purl} . The client reveal seeds "
                                    "automatically and goes out after the "
                                    "10-day soak window. Note 'share now' to "
                                    "release early, or 'hold preview' to stop "
                                    "it. Nothing else needed for it to send."}])
            print("      preview-pipeline card filed (first build)")
        except Exception as _e:  # noqa: BLE001 — a deploy never fails over a card
            print(f"      (preview-pipeline card failed: {str(_e)[:80]})")

    print()
    print("==> Sync complete.")
    print(f"    GitHub repo:    https://github.com/{GH_OWNER}/{client_repo}")
    print(f"    Cloudflare Pages will auto-build the {branch} branch.")
    if branch == "main":
        print(f"    Production URL: https://rankai-{slug}.pages.dev/")
    else:
        print(f"    Preview URL:    https://staging.rankai-{slug}.pages.dev/")

    # Publish the colours this build just painted back to the app, so the Site
    # Build card's swatches and the chat widget show the client's real brand
    # instead of the factory red. Non-fatal: a deploy must never fail over a
    # cosmetic sync. See scripts/brand_colors_sync.py for the precedence rules.
    try:
        from brand_colors_sync import push_colors
        _bc = push_colors(slug, apply=True)
        if _bc.get("applied"):
            print("    brand colors:   " + ", ".join(
                f"{k}->{new}" for k, _o, new, _w in _bc["actions"]))
    except Exception as e:
        print(f"    brand colors:   sync skipped ({str(e)[:120]})")

    # IndexNow ping on production deploys — entirely non-fatal (deploy already
    # succeeded; a failed ping just means Bing finds the pages the slow way).
    # See the IndexNow section above for the ~2 min Cloudflare build-lag note.
    if branch == "main":
        try:
            status, n = indexnow_ping(slug)
            print(f"    IndexNow ping:  HTTP {status} ({n} URLs) "
                  f"[{'accepted' if status in (200, 202) else 'not accepted'}]")
        except Exception as e:
            print(f"    IndexNow ping skipped: {str(e)[:120]}")
    return 0


def cmd_sync_deploy_all(args) -> int:
    """Bulk sync — push every client subtree to its per-client repo on the given branch."""
    slugs = []
    for site_dir in sorted(SITES_DIR.iterdir()):
        if site_dir.is_dir() and not site_dir.name.startswith("_"):
            slugs.append(site_dir.name)
    if not slugs:
        die("No client subtrees found under sites/.")

    print(f"==> Bulk sync-deploy for {len(slugs)} client(s), branch={args.branch}")
    print(f"    Slugs: {', '.join(slugs)}")
    print()

    failures = []
    for slug in slugs:
        print(f"────────────── {slug} ──────────────")
        sub_args = argparse.Namespace(
            slug=slug, branch=args.branch,
            private=args.private, allow_dirty=args.allow_dirty,
        )
        try:
            cmd_sync_deploy(sub_args)
        except SystemExit as e:
            failures.append((slug, str(e)))
        except Exception as e:
            failures.append((slug, str(e)[:200]))
        print()

    print(f"==> Bulk sync done. Succeeded: {len(slugs) - len(failures)}/{len(slugs)}")
    if failures:
        print("    Failures:")
        for s, e in failures:
            print(f"      {s}: {e[:120]}")
        return 2
    return 0


# ----------------------------------------------------------------------------
# IndexNow (Bing fast-indexing; Bing feeds ChatGPT's web retrieval)
# ----------------------------------------------------------------------------
#
# After every production (main) sync-deploy we ping api.indexnow.org with the
# client's live URL list so Bing picks up new/changed pages within hours, not
# weeks. The key file sites/{slug}/public/{key}.txt is served at
# https://{domain}/{key}.txt by the deployed site, which is how IndexNow
# verifies ownership.
#
# URL source: the LIVE sitemap (https://{domain}/sitemap-index.xml → child
# sitemaps → page URLs). NOTE: Cloudflare Pages takes ~2 min to build after the
# push, so the sitemap fetched at ping time may be one deploy behind — that's
# fine, URLs are stable and IndexNow only needs the URL list, not the content.
# If the live sitemap can't be fetched (staging domain, site not yet live), we
# fall back to pinging just the homepage.
#
# ---------------------------------------------------------------------------
# THE 403 TRAP (diagnosed 2026-08-05 — davis / flood-fixers / puroclean)
# ---------------------------------------------------------------------------
# Bing's IndexNow binds a VERDICT to the (host, key) pair the first time it
# tries to validate, and it does NOT re-validate afterwards. If the very first
# ping for a host happens before https://{host}/{key}.txt is actually serving
# — which is exactly what a ping racing the Cloudflare Pages build does — the
# pair is marked bad permanently and every later ping returns:
#
#     HTTP 403 {"errorCode":"UserForbiddedToAccessSite", ...}
#
# even after the key file has been live and byte-correct for weeks. Proof it
# is a stale verdict and not a real ownership problem: the identical host +
# key + keyLocation payload is accepted by Yandex (HTTP 202) while Bing and
# api.indexnow.org (same backend) both 403.
#
# There is no cache-bust API. The ONLY remedy is to retire the poisoned key
# and validate a fresh one: mint a new key, ship {newkey}.txt, then ping with
# the new key. That is what rotate_indexnow_key() does, and indexnow_ping()
# triggers it automatically the moment Bing returns UserForbiddedToAccessSite
# against a key file we have verified is live.
#
# Prevention (so a new launch can never poison itself): ensure_indexnow_key()
# now runs at SCAFFOLD time, so {key}.txt is committed with the site's very
# first push and is already serving before any ping is possible. The old
# behaviour — minting the key lazily inside the first ping — guaranteed that
# the first ping for every client raced its own key file.

INDEXNOW_ENDPOINT = "https://www.bing.com/indexnow"  # bing endpoint: api.indexnow.org caches premature 403s (davis/FF hit this); bing accepts the same protocol
INDEXNOW_URL_CAP = 500
# Bing's error code for "this (host,key) pair is blacklisted" — the stale
# verdict described above. Distinct from a genuinely missing key file, which we
# rule out ourselves before ever sending the ping.
INDEXNOW_STALE_VERDICT = "UserForbiddedToAccessSite"


def _http_get(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "rank-ai-indexnow/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def _sitemap_locs(xml: str) -> list[str]:
    return [m.strip() for m in re.findall(r"<loc>\s*([^<]+?)\s*</loc>", xml)]


def collect_live_urls(domain: str, cap: int = INDEXNOW_URL_CAP) -> list[str]:
    """Page URLs from the live sitemap index (child sitemaps expanded), capped.
    Raises on a failed index fetch — caller decides the fallback."""
    index_xml = _http_get(f"https://{domain}/sitemap-index.xml")
    urls: list[str] = []
    for child in _sitemap_locs(index_xml):
        if len(urls) >= cap:
            break
        if child.endswith(".xml"):  # child sitemap → expand
            try:
                urls.extend(_sitemap_locs(_http_get(child)))
            except Exception:
                continue  # one bad child sitemap shouldn't kill the ping
        else:  # index unexpectedly contained page URLs directly
            urls.append(child)
    # De-dup preserving order, then cap.
    seen: set[str] = set()
    out = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out[:cap]


def _write_key_file(slug: str, key: str) -> Path:
    """Drop sites/{slug}/public/{key}.txt (content == key, no trailing newline).
    Astro copies public/ verbatim to the site root, so this serves at
    https://{domain}/{key}.txt — the IndexNow proof of ownership."""
    key_file = SITES_DIR / slug / "public" / f"{key}.txt"
    key_file.parent.mkdir(parents=True, exist_ok=True)
    current = key_file.read_text().strip() if key_file.exists() else None
    if current != key:
        key_file.write_text(key)
    return key_file


def ensure_indexnow_key(slug: str, client: dict | None = None) -> str:
    """Guarantee the client has an IndexNow key AND that its proof file exists
    on disk, so the key ships with the site's next (or first) push.

    Called at SCAFFOLD time — that is the whole point. Minting the key lazily
    inside the first ping meant every client's first ping raced its own key
    file to Cloudflare and lost, poisoning the (host, key) pair with Bing
    forever. See THE 403 TRAP above.

    Idempotent: existing keys are never rotated here, only backfilled with a
    missing key file. Persists the client record only when something changed."""
    path = CLIENTS_DIR / f"{slug}.json"
    rec = client if client is not None else load_json(path)
    key = (rec.get("indexnow_key") or "").strip()
    minted = False
    if not key:
        import uuid
        key = uuid.uuid4().hex
        rec["indexnow_key"] = key
        minted = True
    key_file = SITES_DIR / slug / "public" / f"{key}.txt"
    had_file = key_file.exists() and key_file.read_text().strip() == key
    _write_key_file(slug, key)
    if minted:
        # Only persist when we own the record load; a caller passing `client`
        # in is mid-edit and will save it itself.
        if client is None:
            save_json(path, rec)
        print(f"    indexnow: minted key for {slug} + wrote {key}.txt (ships with next deploy)")
    elif not had_file:
        print(f"    indexnow: restored missing key file {key}.txt for {slug}")
    return key


def rotate_indexnow_key(slug: str, reason: str = "") -> str:
    """Retire a key Bing has permanently rejected and mint a fresh one.

    Bing binds a pass/fail verdict to the (host, key) pair on first validation
    and never re-checks, so a key that was pinged before its file was live is
    dead forever — no amount of re-pinging revives it. A NEW key is a new pair
    with no verdict, which is the only way back to a 200. The old key file is
    deliberately LEFT in place: it is 32 bytes, it is still a valid ownership
    proof, and deleting it could invalidate submissions already in Bing's
    queue."""
    path = CLIENTS_DIR / f"{slug}.json"
    rec = load_json(path)
    old = (rec.get("indexnow_key") or "").strip()
    import uuid
    new = uuid.uuid4().hex
    rec["indexnow_key"] = new
    if old:
        hist = rec.setdefault("indexnow_key_history", [])
        hist.append({"key": old, "retired_at": now_iso(),
                     "reason": reason or "bing stale verdict (UserForbiddedToAccessSite)"})
    rec["updated_at"] = now_iso()
    save_json(path, rec)
    _write_key_file(slug, new)
    print(f"    indexnow: ROTATED {slug} {old or '(none)'} → {new}")
    print(f"              wrote sites/{slug}/public/{new}.txt — deploy to main, "
          f"then re-ping with the new key")
    return new


def indexnow_ping(slug: str, *, auto_rotate: bool = True) -> tuple[int, int]:
    """POST the client's live URLs to IndexNow. Returns (http_status, url_count).
    200/202 = accepted. Raises on missing key/domain or network failure of the
    ping itself (sitemap failure just degrades to a homepage-only ping)."""
    client = load_json(CLIENTS_DIR / f"{slug}.json")
    domain = (client.get("domain") or "").strip().rstrip("/")
    if not domain:
        raise RuntimeError(f"{slug}: no 'domain' in client record")
    # Mints the key + writes the proof file if either is missing. This ping
    # will correctly SKIP below (file not live yet) and the next deploy
    # re-pings — which is exactly the race we must not lose.
    key = ensure_indexnow_key(slug)

    # Never ping before the key file is verifiably live — pinging in the same
    # breath as the deploy that first ships the key races Cloudflare's build,
    # and Bing CACHES the failed key validation (puroclean 2026-07-31: 403s
    # persisted even after the key file was live). Poll up to ~60s; if it's
    # still not serving, skip cleanly — the next deploy re-pings.
    key_url = f"https://{domain}/{key}.txt"
    key_live = False
    for attempt in range(5):
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(key_url, headers={
                        "User-Agent": "rank-ai-indexnow/1.0"}), timeout=15) as r:
                if r.status == 200 and r.read(200).decode().strip() == key:
                    key_live = True
                    break
        except Exception:
            pass
        if attempt < 4:
            time.sleep(15)
    if not key_live:
        print(f"    indexnow: key file not live at {key_url} yet — ping SKIPPED "
              "(avoids Bing caching a failed validation; next deploy retries)")
        return (0, 0)

    try:
        urls = collect_live_urls(domain)
        if not urls:
            urls = [f"https://{domain}/"]
    except Exception as e:
        print(f"    indexnow: live sitemap fetch failed ({str(e)[:80]}) — pinging homepage only")
        urls = [f"https://{domain}/"]

    payload = {
        "host": domain,
        "key": key,
        "keyLocation": f"https://{domain}/{key}.txt",
        "urlList": urls,
    }
    req = urllib.request.Request(
        INDEXNOW_ENDPOINT,
        data=json.dumps(payload).encode(),
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    body = ""
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            status = r.status
    except urllib.error.HTTPError as e:
        status = e.code
        try:
            body = e.read().decode("utf-8", "replace")[:400]
        except Exception:
            body = ""

    # Stale-verdict self-heal. We only get here having PROVEN the key file is
    # live and byte-correct (the poll above), so a 403 cannot mean "we don't
    # own the domain" — it means Bing is replaying a verdict it cached when
    # this key raced its own deploy. Rotate to a fresh key now; the file is
    # written immediately and the next production deploy ships + re-pings it.
    if status == 403 and INDEXNOW_STALE_VERDICT in body and auto_rotate:
        print(f"    indexnow: Bing replayed a stale rejection for this key "
              f"({INDEXNOW_STALE_VERDICT}) even though {key_url} serves the "
              f"correct value — the key is burned, rotating.")
        rotate_indexnow_key(slug, reason=f"bing 403 {INDEXNOW_STALE_VERDICT} on {domain}")
    elif status not in (200, 202) and body:
        print(f"    indexnow: HTTP {status} — {body}")
    return status, len(urls)


def cmd_indexnow(args) -> int:
    if getattr(args, "rotate", False):
        rotate_indexnow_key(args.slug, reason="manual --rotate")
        print("Key rotated. Deploy to main (sync-deploy --branch main) so the new "
              "key file goes live, then re-run indexnow.")
        return 0
    status, n = indexnow_ping(args.slug, auto_rotate=not getattr(args, "no_rotate", False))
    ok = status in (200, 202)
    print(f"IndexNow ping for {args.slug}: HTTP {status} "
          f"({'accepted' if ok else 'NOT accepted'}), {n} URL(s) submitted")
    return 0 if ok else 1


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------


def cmd_add_pages(args) -> int:
    """Incrementally write content markdown ONLY for planned URLs that don't yet have a
    file. Unlike `scaffold` (which overwrites every page with a placeholder), this never
    touches existing/rendered pages — used after new services are added to plan-input so
    new service + location pages get scaffolded without wiping rendered content."""
    slug = args.slug
    plan_input = load_json(CLIENTS_DIR / slug / "plan-input.json")
    plan_input["_slug"] = slug
    url_plan = load_json(CLIENTS_DIR / slug / "plan" / "url-plan.json")
    internal_links = load_json(CLIENTS_DIR / slug / "plan" / "internal-links.json")
    site_dir = SITES_DIR / slug

    catalog = load_json(verticals.resolve_template(slug, "services.json"))
    catalog_by_slug = {s["slug"]: s for s in catalog["services"]}
    services_lookup = {s: catalog_by_slug[s] for s in plan_input.get("services", []) if s in catalog_by_slug}
    areas_lookup = {a["slug"]: a for a in plan_input.get("service_areas", [])}
    blog_topics = load_json(verticals.resolve_template(slug, "seed-blog-topics.json"))
    blog_topics_lookup = {t["slug"]: t for t in blog_topics["topics"]}

    new = 0
    for page in url_plan["pages"]:
        coll, _ = ARCHETYPE_TO_COLLECTION[page["archetype"]]
        out = site_dir / "src" / "content" / coll / f"{derive_filename(page)}.md"
        if out.exists():
            continue
        write_content_md(site_dir, page, plan_input,
                         services_lookup, areas_lookup, blog_topics_lookup, internal_links)
        new += 1
    print(f"  {slug}: wrote {new} new page file(s); {len(url_plan['pages']) - new} existing untouched")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="build_site",
        description="Rank AI — build site (Skill 3, phase 1: scaffold + GitHub + Pages).",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    pap = sub.add_parser("add-pages", help="Write content md ONLY for new planned URLs (never overwrites rendered pages)")
    pap.add_argument("--slug", required=True)
    pap.set_defaults(func=cmd_add_pages)

    ps = sub.add_parser("scaffold", help="Copy starter, substitute tokens, push to GitHub, create Pages project")
    ps.add_argument("--slug", required=True)
    ps.add_argument("--private", action="store_true", help="Create the GitHub repo as private (default public)")
    ps.add_argument("--message", help="Override the commit message")
    ps.set_defaults(func=cmd_scaffold)

    pst = sub.add_parser("status", help="Show current build state of a client")
    pst.add_argument("--slug", required=True)
    pst.set_defaults(func=cmd_status)

    pr = sub.add_parser("render", help="Generate body content + FAQ for planned URLs via Anthropic")
    pr.add_argument("--slug", required=True)
    pr.add_argument("--archetype", help="Filter to one archetype (e.g., service-area-service)")
    pr.add_argument("--url", help="Filter to one URL path (e.g., /services/water-damage-restoration/)")
    pr.add_argument("--limit", type=int, help="Render at most N pages")
    pr.add_argument("--model", default=ANTHROPIC_DEFAULT_MODEL,
                    help=f"Anthropic model (default: {ANTHROPIC_DEFAULT_MODEL})")
    pr.add_argument("--workers", type=int, default=4,
                    help="Concurrent render workers (default: 4)")
    pr.add_argument("--force", action="store_true",
                    help="Re-render pages even if rendered: true in frontmatter")
    pr.add_argument("--push", action="store_true",
                    help="Commit and push to staging after rendering")
    pr.set_defaults(func=cmd_render)

    # retint: re-derive tailwind + favicon colours from plan-input
    prt = sub.add_parser(
        "retint",
        help="Regenerate the site's colour files (tailwind.config.mjs, favicon.svg) "
             "from plan-input brand colours — no re-render, no LLM cost",
    )
    prt.add_argument("--slug", required=True)
    prt.add_argument("--force", action="store_true",
                     help="Overwrite even if the file looks hand-tuned")
    prt.set_defaults(func=cmd_retint)

    # sync-deploy: monorepo subtree → per-client GitHub repo
    psd = sub.add_parser(
        "sync-deploy",
        help="Push sites/{slug}/ subtree to per-client GitHub repo (Cloudflare auto-builds)",
    )
    psd.add_argument("--slug", required=True)
    psd.add_argument("--branch", required=True, choices=["main", "staging"],
                     help="Target branch on the per-client repo. main = production, staging = preview.")
    psd.add_argument("--private", action="store_true",
                     help="If the per-client repo needs to be created, make it private (default: public).")
    psd.add_argument("--allow-dirty", action="store_true",
                     help="Allow sync even if monorepo working tree has uncommitted changes.")
    psd.set_defaults(func=cmd_sync_deploy)

    # sync-deploy-all: bulk version
    psda = sub.add_parser(
        "sync-deploy-all",
        help="Run sync-deploy for every client under sites/",
    )
    psda.add_argument("--branch", required=True, choices=["main", "staging"])
    psda.add_argument("--private", action="store_true")
    psda.add_argument("--allow-dirty", action="store_true")
    psda.set_defaults(func=cmd_sync_deploy_all)

    # indexnow: manual ping (also runs automatically after sync-deploy --branch main)
    pin = sub.add_parser(
        "indexnow",
        help="Ping api.indexnow.org with the client's live sitemap URLs (Bing fast-indexing)",
    )
    pin.add_argument("--slug", required=True)
    pin.add_argument("--rotate", action="store_true",
                     help="Retire the current key and mint a fresh one WITHOUT pinging. "
                          "Use when Bing has cached a rejection for the current key "
                          "(HTTP 403 UserForbiddedToAccessSite despite a live key file). "
                          "Deploy to main afterwards, then ping.")
    pin.add_argument("--no-rotate", action="store_true",
                     help="Do not auto-rotate the key if Bing replays a stale 403.")
    pin.set_defaults(func=cmd_indexnow)

    return p


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
