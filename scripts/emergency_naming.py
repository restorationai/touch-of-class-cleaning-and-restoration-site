#!/usr/bin/env python3
"""emergency_naming.py: the EMERGENCY NAMING RULE (Santino 2026-09-30).

"We want to start adding the word emergency to more pages, whether that is
in the headline name or just on the page itself."

URGENT services only (URGENT_FAMILIES below): water damage restoration,
emergency water removal, flood damage, burst pipe / leak, sewage cleanup,
fire damage, smoke damage, storm damage, emergency board-up / tarping,
biohazard / trauma, and emergency plumbing where the client is licensed for
plumbing. Never mold, remodeling, carpet/upholstery, air ducts, general
contracting, testing, insurance or any other non-urgent service.

For an urgent page (the /services/{x}/ page AND every city variant):
  title  leads with "24/7 Emergency" when the client's truth (plan-input
         brand.hours, the claims_lint gate) says 24/7, else "Emergency".
         Never doubled ("Emergency Emergency"): a leading 24/7 / 24 Hour /
         Emergency already in the service name is folded into the lead. The
         keyword headline (everything before " | Brand") stays under about
         60 characters: "24/7" is dropped first, then ", ST".
  h1     same lead: "24/7 Emergency Water Damage Restoration in {City}".
  meta   carries the same lead ("24/7 emergency water damage restoration in ...").
  body   opens with ONE emergency-response line (bold hook + call to act).
         "We answer 24/7" only for 24/7 clients; an on-site time only when
         brand.response_minutes is on file; otherwise no numeric promise.
         Added only where the opening paragraph has no emergency language;
         the rest of the page is never rewritten.
Clients whose truth sets explicit business hours that are NOT 24/7 (e.g.
Davis Construction, Mon-Fri 8-5) get no emergency framing at all: the truth
table says they are closed nights and weekends.

Used by: plan_site.py (planned titles/H1s), build_site.py update_content_md
(the opening line after every render), and this CLI (existing pages).

Usage:
  python3 scripts/emergency_naming.py --slug flood-fixers          # dry-run
  python3 scripts/emergency_naming.py --all --apply
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

SKIP = {"tdi-builders", "mcc-restoration", "mold-solutionz"}   # tdi: hands off; others dead
HEADLINE_MAX = 60
MARK = "<!-- emergency-open -->"

# family -> (hook, action). Hook reads "{hook} in {City}?".
URGENT_FAMILIES: dict[str, tuple[str, str]] = {
    "water": ("Water damage emergency", "stop the water and start drying your property"),
    "water-removal": ("Standing water emergency", "extract the water and start drying"),
    "flood": ("Flooding emergency", "pump out the water and stop the damage from spreading"),
    "basement": ("Flooded basement", "pump out the water and start drying"),
    "ceiling": ("Water coming through the ceiling", "stop the leak damage and start drying"),
    "pipe": ("Burst pipe or leak", "stop the water and start the cleanup"),
    "sewage": ("Sewage backup", "contain the contamination and start the cleanup"),
    "fire": ("Fire damage emergency", "secure the property and start the recovery"),
    "smoke": ("Smoke damage emergency", "stop smoke and soot damage from spreading"),
    "storm": ("Storm damage emergency", "secure the property and stop further damage"),
    "boardup": ("Need an emergency board-up", "secure broken windows, doors and roofs"),
    "bio": ("Need biohazard or trauma cleanup", "handle the cleanup with discretion and care"),
    "plumbing": ("Plumbing emergency", "stop the leak and fix the problem"),
}

URGENT_SLUGS: dict[str, str] = {
    "water-damage-restoration": "water", "24-7-emergency-water-damage-restoration": "water",
    "water-damage-cleanup": "water",
    "emergency-water-removal": "water-removal", "water-cleanup": "water-removal",
    "24-7-emergency-water-cleanup": "water-removal", "water-extraction": "water-removal",
    "carpet-water-extraction": "water-removal", "structural-drying-dehumidification": "water",
    "flood-damage-restoration": "flood", "flood-cleanup": "flood",
    "basement-flooding-cleanup": "basement", "basement-flood-cleanup": "basement",
    "basement-water-cleanup": "basement",
    "ceiling-water-damage-repair": "ceiling",
    "burst-pipe-repair": "pipe", "burst-frozen-pipes": "pipe", "burst-pipe-water-damage-cleanup": "pipe",
    "frozen-pipe-restoration": "pipe", "appliance-leak-cleanup": "pipe", "water-heater-flood-cleanup": "pipe",
    "sewage-cleanup": "sewage", "basement-sewage-cleanup": "sewage", "category-3-water-cleanup": "sewage",
    "emergency-sewage-cleanup": "sewage",
    "fire-damage-restoration": "fire", "commercial-fire-restoration": "fire",
    "smoke-damage-restoration": "smoke", "smoke-damage-cleaning": "smoke", "soot-removal": "smoke",
    "storm-damage-restoration": "storm", "hurricane-damage-restoration": "storm",
    "wind-damage-repair": "storm", "hail-damage-restoration": "storm",
    "emergency-board-up-tarping": "boardup", "emergency-board-up": "boardup",
    "emergency-board-ups": "boardup", "emergency-tarping": "boardup",
    "biohazard-cleanup": "bio", "trauma-scene-cleanup": "bio", "crime-scene-cleanup": "bio",
    "unattended-death-cleanup": "bio", "blood-cleanup": "bio",
    "emergency-plumbing": "plumbing",   # gated: plumbing_licensed()
}
PLUMBING_ONLY = {"plumbing"}

_LEAD_RE = re.compile(r"^(?:(?:24\s*/\s*7|24[- ]hours?|emergency)\s+)+", re.I)
_EMERG_OPEN_RE = re.compile(r"24\s*/\s*7|24[- ]hour|around[- ]the[- ]clock|emergenc|day or night", re.I)


# --------------------------------------------------------------------------- #
# truth
# --------------------------------------------------------------------------- #
def _plan_input(slug: str) -> dict:
    p = ROOT / "clients" / slug / "plan-input.json"
    return json.loads(p.read_text()) if p.exists() else {}


def _client(slug: str) -> dict:
    p = ROOT / "clients" / f"{slug}.json"
    try:
        d = json.loads(p.read_text()) if p.exists() else {}
    except json.JSONDecodeError:
        d = {}
    return d if isinstance(d, dict) else {}


@lru_cache(maxsize=None)
def _plumbing_licenses() -> frozenset:
    out = set()
    for p in (ROOT / "clients").glob("*.json"):
        c = _client(p.stem)
        if str(c.get("vertical") or "").lower() == "plumbing":
            b = _plan_input(p.stem).get("brand") or {}
            out |= {str(x).strip() for x in (b.get("license_numbers") or []) if str(x).strip()}
    return frozenset(out)


def plumbing_licensed(slug: str) -> bool:
    """Licensed for plumbing = a plumbing-vertical client, a license type that
    names plumbing, or a license number shared with a plumbing-vertical client
    (ProRestoration runs on All Pro Plumbing's CSLB license)."""
    if str(_client(slug).get("vertical") or "").lower() == "plumbing":
        return True
    b = _plan_input(slug).get("brand") or {}
    if re.search(r"plumb", str(b.get("license_type") or ""), re.I):
        return True
    lic = {str(x).strip() for x in (b.get("license_numbers") or []) if str(x).strip()}
    return bool(lic & _plumbing_licenses())


def truth(slug: str, plan_input: dict | None = None) -> dict:
    """{is_247, response_minutes, business_hours_only} from the claims_lint truth."""
    from claims_lint import truth_from_plan_input
    pi = plan_input if plan_input is not None else _plan_input(slug)
    t = truth_from_plan_input(pi)
    hours = (t.get("hours") or "").strip()
    return {"is_247": bool(t["is_247"]), "response_minutes": t.get("response_minutes"),
            "business_hours_only": bool(hours) and not t["is_247"]}


def family(service_slug: str, slug: str) -> str | None:
    fam = URGENT_SLUGS.get(service_slug)
    if fam in PLUMBING_ONLY and not plumbing_licensed(slug):
        return None
    return fam


def applies(slug: str, service_slug: str, tr: dict | None = None) -> bool:
    if slug in SKIP or not family(service_slug, slug):
        return False
    tr = tr or truth(slug)
    return not tr["business_hours_only"]


# --------------------------------------------------------------------------- #
# text rules
# --------------------------------------------------------------------------- #
def lead_for(tr: dict) -> str:
    return "24/7 Emergency" if tr["is_247"] else "Emergency"


def _base(name: str) -> str:
    """Service name without any leading 24/7 / 24 Hour / Emergency words."""
    return _LEAD_RE.sub("", name.strip()).strip()


def _has_emergency(s: str) -> bool:
    return bool(re.search(r"\bemergency\b", s, re.I))


def headline(name: str, place: str, tr: dict) -> str:
    """'{lead} {service} in {place}', under HEADLINE_MAX: drop 24/7, then ', ST'."""
    base = _base(name)
    leads = [lead_for(tr)] + (["Emergency"] if tr["is_247"] else [])
    places = [place] + ([place.split(",")[0].strip()] if "," in place else [])
    for pl in places:
        for ld in leads:
            h = f"{ld} {base} in {pl}"
            if len(h) <= HEADLINE_MAX:
                return h
    return f"Emergency {base} in {places[-1]}"


def new_title(title: str, tr: dict) -> str:
    head, sep, tail = title.partition(" | ")
    m = re.match(r"^(?P<svc>.+?) in (?P<place>.+)$", head)
    if not m:
        if _has_emergency(head) and (not tr["is_247"] or re.search(r"24\s*/\s*7", head)):
            return title
        h = f"{lead_for(tr)} {_base(head)}"
        return h + (sep + tail if sep else "")
    if re.search(r"24\s*/\s*7", tail):          # "| 24/7 Response |" already says it
        tr = {**tr, "is_247": False}
    h = headline(m.group("svc"), m.group("place"), tr)
    return h + (sep + tail if sep else "")


def new_h1(h1: str, tr: dict) -> str:
    m = re.match(r"^(?P<svc>.+?) in (?P<place>.+)$", h1)
    if not m:
        return h1 if _has_emergency(h1) and not tr["is_247"] else f"{lead_for(tr)} {_base(h1)}"
    return f"{lead_for(tr)} {_base(m.group('svc'))} in {m.group('place')}"


def new_meta(meta: str, service_name: str, tr: dict) -> str:
    if not meta:
        return meta
    low = meta.lower()
    if _has_emergency(meta):
        if tr["is_247"] and not re.search(r"24\s*/\s*7", meta) and low.startswith("emergency "):
            return "24/7 " + meta[0].lower() + meta[1:]
        return meta
    m = re.match(r"^(24\s*/\s*7)\s+", meta)
    if m:
        return meta[:m.end()] + "emergency " + meta[m.end():]
    words = re.findall(r"[a-z0-9-]+", _base(service_name).lower())
    lead = "24/7 emergency " if tr["is_247"] else "Emergency "
    if words and low.startswith(words[0]):
        return lead + meta[0].lower() + meta[1:]
    # the service phrase sits mid-sentence ("Trusted burst pipe repair in ...")
    probe = " ".join(words[:2])
    i = low.find(probe) if probe else -1
    if i > 0:
        return meta[:i] + lead.lower() + meta[i:]
    return ("24/7 emergency service. " if tr["is_247"] else "Emergency service. ") + meta


def opening_line(fam: str, city: str, tr: dict) -> str:
    hook, action = URGENT_FAMILIES[fam]
    where = f" in {city}" if city else ""
    if tr["is_247"]:
        lead = f"**{hook}{where}? We answer 24/7.**"
        mins = tr.get("response_minutes")
        how = (f"Call now and our crew can be on-site within {mins} minutes to {action}."
               if mins else f"Call now and our crew heads out to {action}.")
    else:
        lead = f"**{hook}{where}? Call now for emergency service.**"
        how = f"Our crew responds fast to {action}."
    return f"{MARK}\n{lead} {how}"


def needs_opening(body: str) -> bool:
    if MARK in body:
        return False
    paras = [p for p in re.split(r"\n\s*\n", body.strip()) if p.strip() and not p.lstrip().startswith("<!--")]
    first = paras[0] if paras else ""
    return not _EMERG_OPEN_RE.search(first[:600])


def with_opening(body: str, fam: str, city: str, tr: dict) -> str:
    if not needs_opening(body):
        return body
    return opening_line(fam, city, tr) + "\n\n" + body.lstrip("\n")


# --------------------------------------------------------------------------- #
# files
# --------------------------------------------------------------------------- #
def _fm_value(line: str) -> str:
    v = line.split(":", 1)[1].strip()
    try:
        return json.loads(v) if v.startswith('"') else v
    except json.JSONDecodeError:
        return v.strip('"')


def apply_text(text: str, slug: str, service_slug: str, tr: dict,
               body_too: bool = True) -> str:
    fam = family(service_slug, slug)
    if not fam or tr["business_hours_only"] or slug in SKIP:
        return text
    m = re.match(r"---\n(.*?)\n---\n?", text, re.S)
    if not m:
        return text
    lines = m.group(1).splitlines()
    vals = {ln.split(":", 1)[0]: _fm_value(ln) for ln in lines if re.match(r"^\w+:", ln)}
    name = vals.get("service_display") or ""
    if not name or name == service_slug:
        name = re.sub(r"\s+in\s+.*$", "", vals.get("h1", "")) or service_slug.replace("-", " ").title()
    out = []
    for ln in lines:
        k = ln.split(":", 1)[0]
        if k == "title":
            ln = "title: " + json.dumps(new_title(_fm_value(ln), tr), ensure_ascii=False)
        elif k == "h1":
            ln = "h1: " + json.dumps(new_h1(_fm_value(ln), tr), ensure_ascii=False)
        elif k == "meta_description":
            ln = "meta_description: " + json.dumps(new_meta(_fm_value(ln), name, tr), ensure_ascii=False)
        out.append(ln)
    body = text[m.end():]
    rendered = "Page body not yet generated" not in text
    if body_too and rendered:
        city = vals.get("city") or ""
        if not city:
            mm = re.match(r"^.+? in (.+)$", vals.get("h1", ""))
            city = mm.group(1).strip() if mm else ""
        body = with_opening(body, fam, city, tr)
    return "---\n" + "\n".join(out) + "\n---\n" + body.lstrip("\n") if body.strip() else \
        "---\n" + "\n".join(out) + "\n---\n"


def apply_site(slug: str, apply: bool) -> dict:
    site = ROOT / "sites" / slug / "src" / "content"
    tr = truth(slug)
    rep = {"slug": slug, "is_247": tr["is_247"], "response_minutes": tr["response_minutes"],
           "skipped": "business hours" if tr["business_hours_only"] else None,
           "files": 0, "changed": 0, "opening_added": 0, "examples": []}
    if tr["business_hours_only"] or slug in SKIP:
        return rep
    files = [(f, f.stem) for f in (site / "services").glob("*.md")]
    files += [(f, f.stem.split("__", 1)[1]) for f in (site / "locations").glob("*__*.md")]
    for f, svc in sorted(files):
        if not family(svc, slug):
            continue
        rep["files"] += 1
        old = f.read_text()
        new = apply_text(old, slug, svc, tr)
        if new != old:
            rep["changed"] += 1
            rep["opening_added"] += int(MARK in new and MARK not in old)
            if len(rep["examples"]) < 3 and "/services/" in str(f):
                t = re.search(r"^title: (.*)$", new, re.M).group(1)
                h = re.search(r"^h1: (.*)$", new, re.M).group(1)
                rep["examples"].append({"file": f.name, "title": t, "h1": h})
            if apply:
                f.write_text(new)
    return rep


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--slug")
    g.add_argument("--all", action="store_true")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    import site_structure as ss
    slugs = [a.slug] if a.slug else [s for s in ss.live_slugs() if s not in SKIP]
    for s in slugs:
        print(json.dumps(apply_site(s, a.apply), ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
