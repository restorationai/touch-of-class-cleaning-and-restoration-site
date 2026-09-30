#!/usr/bin/env python3
"""lsa_geo.py — LSA service-area coverage: are we advertising everywhere the
client says they work?

Santino 2026-09-30 (AirCare went live targeting only Abilene while her
onboarding wizard lists eight counties): "when we do the LSA ad management, we
should, by default, investigate what areas we should be advertising in based
on the service areas they provide ... then update that for LSA."

Every place the client has told us they work is a SOURCE:
  wizard    companies.service_areas (onboarding wizard: county + cities,
            allCities=true means the whole county)
  gbp       marketing_gbp_profiles.service_areas (Locations tab snapshot of the
            Google Business Profile service area, incl. what parity added)
  site      sites/{slug}/src/content/serviceAreas/*.md (city pages we built)
  priority  integration_settings.goals.priority_areas (client-stated focus)
  brief     integration_settings.site_brief.cities
  hq        companies.city/state (the office)

Each place resolves to a Google geo target by EXACT canonical name (GAQL on
geo_target_constant; never guessed IDs, never fuzzy suggest). A place is
COVERED when its target is on the LSA campaign, or when it is a wizard city
inside a county the campaign targets. Uncovered places are the gap.

Commands:
  audit --slug X [--json]     current LSA targets vs declared areas (read-only)
  apply --slug X [--dry-run]  add the gap as LSA location criteria (validates
                              first; sets the one-time EU-political-ads
                              declaration if missing — Google refuses
                              criteria edits without it)
  check --slug X              audit + file ONE open [FLAG] ops note when the
                              gap changed since the last check (CI entry)
  list-due                    JSON slugs of clients with an LSA account
  report                      fleet table: coverage gap + attention items

Never removes a target (a target outside the declared areas is reported, not
touched). Ownership guard: accounts whose Google name shares no word with the
client (FFS -> A&J Plumbing) are skipped, same as lsa_lead_review.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

import client_concierge as cc  # noqa: E402
from client_ops_sync import _sb, slug_map  # noqa: E402
from lsa_lead_review import _company, _cid_for, _gaql, _ints, _mcc, _owned  # noqa: E402

KV = "lsa-geo"
STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii",
    "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming",
}
FULL = {v.lower(): v for v in STATES.values()}


# ------------------------------------------------------------------ places
def _state(s: str | None, default: str | None) -> str | None:
    s = (s or "").strip().strip(".")
    if s.upper() in STATES:
        return STATES[s.upper()]
    return FULL.get(s.lower()) or default


def _parse(text: str, default_state: str | None):
    """'Roby, TX 79543' / 'Abilene TX' / 'Tom Green County, Texas' -> (name, State, zip)."""
    z = re.search(r"\b(\d{5})(-\d{4})?\b", text or "")
    t = re.sub(r"\b\d{5}(-\d{4})?\b", "", text or "").strip(" ,")
    t = re.sub(r",?\s*(USA|United States)$", "", t, flags=re.I).strip(" ,")
    if not t:
        return None
    name, st = t, default_state
    for pat in (r"^(.*?)[,\s]+([A-Za-z]{2})$", r"^(.*?),\s*([A-Za-z ]{4,})$"):
        m = re.match(pat, t)
        if m and _state(m.group(2), None):
            name, st = m.group(1).strip(" ,"), _state(m.group(2), None)
            break
    if not name or not st or name.upper() in STATES or name.lower() in FULL:
        return None
    return (name.title() if name.isupper() else name), st, (z.group(1) if z else None)


def declared_places(co: dict, slug: str) -> dict:
    """{(name, State): {"sources": set, "county": county-or-None}}"""
    ints = _ints(co)
    hq = _state(co.get("state"), None)
    out: dict = {}

    def add(name, st, src, county=None, zip_=None):
        if not name or not st:
            return
        name = name.strip()
        if name.islower() or name.isupper():
            name = name.title()
        # case-insensitive merge ('Mccamey' from a slug vs 'McCamey' from GBP):
        # keep the spelling with an inner capital, Google's canonical casing
        k = next((x for x in out if x[0].lower() == name.lower() and x[1] == st), None)
        if k and k[0] != name and re.search(r"[a-z][A-Z]", name):
            out[(name, st)] = out.pop(k)
            k = (name, st)
        k = k or (name, st)
        e = out.setdefault(k, {"sources": set(), "county": None, "zip": None})
        e["sources"].add(src)
        e["county"] = e["county"] or county
        e["zip"] = e["zip"] or zip_

    wiz = co.get("service_areas")
    if wiz is None:  # cc.fetch_companies does not select this column
        r = _sb("GET", f"/rest/v1/companies?id=eq.{co['id']}&select=service_areas,city,state") or [{}]
        wiz = r[0].get("service_areas") or []
        co = {**co, "city": co.get("city") or r[0].get("city"), "state": co.get("state") or r[0].get("state")}
        hq = _state(co.get("state"), None)
    if isinstance(wiz, str):
        try:
            wiz = json.loads(wiz)
        except ValueError:
            wiz = []
    for w in wiz if isinstance(wiz, list) else []:
        st = _state(w.get("state"), hq)
        county = (w.get("county") or "").strip()
        if county and w.get("allCities"):
            cname = county if county.lower().endswith(("county", "parish")) else f"{county} County"
            add(cname, st, "wizard")
        for c in w.get("cities") or []:
            add(c, st, "wizard", county=county or None)
    rows = _sb("GET", f"/rest/v1/marketing_gbp_profiles?company_id=eq.{co['id']}"
               "&select=service_areas") or []
    for r in rows:
        for a in r.get("service_areas") or []:
            p = _parse(a, hq)
            if p:
                add(p[0], p[1], "gbp", zip_=p[2])
    for f in sorted((ROOT / "sites" / slug / "src" / "content" / "serviceAreas").glob("*.md")):
        txt = f.read_text()[:1500]
        m = re.search(r'^city:\s*"?([^"\n]+)"?', txt, re.M)
        s = re.search(r'^state:\s*"?([^"\n]+)"?', txt, re.M)
        if m:
            add(m.group(1).strip(), _state(s.group(1) if s else None, hq), "site")
            continue
        parts = f.stem.split("-")
        if len(parts) >= 2 and parts[-1].upper() in STATES:
            add(" ".join(parts[:-1]).title(), STATES[parts[-1].upper()], "site")
    for a in (ints.get("goals") or {}).get("priority_areas") or []:
        p = _parse(a, hq)
        if p:
            add(p[0], p[1], "priority")
    for c in (ints.get("site_brief") or {}).get("cities") or []:
        if isinstance(c, dict):
            add(c.get("label"), _state(c.get("state"), hq), "brief")
    if co.get("city") and hq:
        add(co["city"].title() if co["city"].isupper() else co["city"], hq, "hq")
    return out


# ------------------------------------------------------------------ google
def _q(s: str) -> str:
    return "'" + s.replace("\\", "\\\\").replace("'", "\\'") + "'"


_GEO_CACHE = ROOT / "clients" / "_agency" / "geo-cache.json"
_geo_cache: dict | None = None


def _cache() -> dict:
    global _geo_cache
    if _geo_cache is None:
        try:
            _geo_cache = json.loads(_GEO_CACHE.read_text())
        except (OSError, ValueError):
            _geo_cache = {}
    return _geo_cache


def _save_cache() -> None:
    if _geo_cache is not None:
        _GEO_CACHE.parent.mkdir(parents=True, exist_ok=True)
        _GEO_CACHE.write_text(json.dumps(_geo_cache, indent=0, sort_keys=True))


def place_units(name: str, state: str) -> dict:
    """{"zips": [...], "county": "X County"|None} for a US town (zippopotam ZIPs,
    FCC census county at its first ZIP's point). Cached; fail-soft to empty."""
    key = f"{name},{state}"
    c = _cache()
    if key in c:
        return c[key]
    ab = next((k for k, v in STATES.items() if v == state), None)
    out = {"zips": [], "county": None}
    try:
        import requests
        r = requests.get(f"http://api.zippopotam.us/us/{ab.lower()}/{name.lower()}", timeout=15)
        if r.ok:
            pl = r.json().get("places") or []
            out["zips"] = sorted({p["post code"] for p in pl})
            if pl:
                f = requests.get("https://geo.fcc.gov/api/census/area", timeout=15, params={
                    "lat": pl[0]["latitude"], "lon": pl[0]["longitude"], "format": "json"})
                res = (f.json().get("results") or [{}]) if f.ok else [{}]
                out["county"] = res[0].get("county_name")
    except Exception:  # noqa: BLE001 — containment is best-effort
        pass
    c[key] = out
    return out


def resolve(cl, acid: str, places) -> dict:
    """(name, State) -> (resource_name, canonical, target_type) by exact name."""
    want = {f"{n},{s},United States": (n, s) for n, s in places}
    got = {}
    names = list(want)
    for i in range(0, len(names), 100):
        q = ("SELECT geo_target_constant.resource_name, geo_target_constant.canonical_name, "
             "geo_target_constant.target_type, geo_target_constant.status "
             "FROM geo_target_constant WHERE geo_target_constant.canonical_name IN ("
             + ",".join(_q(n) for n in names[i:i + 100]) + ")")
        for r in _gaql(cl, acid, q):
            g = r.geo_target_constant
            if g.status.name != "ENABLED":
                continue
            prev = got.get(want[g.canonical_name])
            # a name can be both a City and a Township/Neighborhood: prefer City/County
            if not prev or g.target_type in ("City", "County"):
                got[want[g.canonical_name]] = (g.resource_name, g.canonical_name, g.target_type)
    # tiny towns with no City target: fall back to the ZIP the GBP listed
    zips = {f"{m['zip']},{k[1]},United States": k for k, m in places.items()
            if k not in got and isinstance(places, dict) and m.get("zip")}
    if zips:
        q = ("SELECT geo_target_constant.resource_name, geo_target_constant.canonical_name, "
             "geo_target_constant.target_type FROM geo_target_constant "
             "WHERE geo_target_constant.canonical_name IN (" + ",".join(_q(n) for n in zips) + ")")
        for r in _gaql(cl, acid, q):
            g = r.geo_target_constant
            got[zips[g.canonical_name]] = (g.resource_name, g.canonical_name, g.target_type)
    return got


def lsa_state(cl, acid: str) -> dict:
    camps = {}
    for r in _gaql(cl, acid, """SELECT campaign.resource_name, campaign.status,
            campaign.serving_status, campaign.contains_eu_political_advertising
          FROM campaign WHERE campaign.advertising_channel_type = 'LOCAL_SERVICES'
            AND campaign.status != 'REMOVED'"""):
        c = r.campaign
        camps[c.resource_name] = {"status": c.status.name, "serving": c.serving_status.name,
                                  "eu": c.contains_eu_political_advertising.name}
    pos, neg = {}, {}
    for r in _gaql(cl, acid, """SELECT campaign.resource_name, campaign_criterion.negative,
            campaign_criterion.location.geo_target_constant
          FROM campaign_criterion WHERE campaign.advertising_channel_type = 'LOCAL_SERVICES'
            AND campaign.status != 'REMOVED' AND campaign_criterion.type = 'LOCATION'"""):
        (neg if r.campaign_criterion.negative else pos)[
            r.campaign_criterion.location.geo_target_constant] = r.campaign.resource_name
    names = {}
    ids = list(pos) + list(neg)
    for i in range(0, len(ids), 200):
        for r in _gaql(cl, acid, "SELECT geo_target_constant.resource_name, "
                       "geo_target_constant.canonical_name, geo_target_constant.target_type "
                       "FROM geo_target_constant WHERE geo_target_constant.resource_name IN ("
                       + ",".join(_q(x) for x in ids[i:i + 200]) + ")"):
            g = r.geo_target_constant
            names[g.resource_name] = (g.canonical_name, g.target_type)
    return {"campaigns": camps, "pos": pos, "neg": neg, "names": names}


# ------------------------------------------------------------------ audit
def audit(slug: str, cl=None) -> dict:
    cid = _cid_for(slug)
    if not cid:
        raise SystemExit(f"unknown slug {slug}")
    co = _company(cid)
    acid = str((_ints(co).get("lsa") or {}).get("customer_id") or "")
    if not acid:
        return {"slug": slug, "skip": "no LSA account"}
    cl = cl or _mcc()
    try:
        owned, gname = _owned(cl, acid, co)
    except Exception as e:  # noqa: BLE001
        if "permission" in str(e).lower():
            return {"slug": slug, "skip": f"no API access to {acid} (manager link "
                    f"{(_ints(co).get('lsa') or {}).get('link_status')})"}
        raise
    if not owned:
        squash = lambda x: re.sub(r"[^a-z0-9]", "", (x or "").lower())  # noqa: E731
        g, n = squash(gname), squash(co.get("name"))
        if (not re.search(r"[a-z]{3}", (gname or "").lower())  # 'P1177043'
                or (g and (g in n or g in squash(slug) or n.startswith(g[:6])))):
            owned = True
    if not owned:
        return {"slug": slug, "skip": f"LSA account is {gname!r}, not this client"}
    st = lsa_state(cl, acid)
    if not st["campaigns"]:
        return {"slug": slug, "account": acid, "skip": "no LSA campaign"}
    places = declared_places(co, slug)
    geo = resolve(cl, acid, places)
    targeted = set(st["pos"])
    negated = set(st["neg"])
    county_ids = {}  # wizard county name -> geo id
    for (n, s), (rn, _can, tt) in geo.items():
        if tt == "County":
            county_ids[(n.lower().replace(" county", ""), s)] = rn
    tnames = [st["names"].get(g, (g, "?")) for g in targeted]
    covered, gap, unresolved = [], [], []
    for (n, s), meta in sorted(places.items()):
        g = geo.get((n, s))
        cty = meta.get("county")
        if not g and cty and county_ids.get((cty.lower().replace(" county", ""), s)):
            continue  # town without its own target, covered by its county
        if not g:
            unresolved.append({"place": f"{n}, {s}", "sources": sorted(meta["sources"])})
            continue
        row = {"place": f"{n}, {s}", "geo": g[0], "type": g[2], "sources": sorted(meta["sources"])}
        cty = meta.get("county")
        via = county_ids.get(((cty or "").lower().replace(" county", ""), s)) if cty else None
        if g[0] in negated:
            row["note"] = "EXCLUDED on LSA (negative target) — left alone"
            covered.append(row)
        elif g[0] in targeted or (via and via in targeted):
            covered.append(row)
        elif (why := _contained(n, s, g[2], tnames)):
            row["note"] = f"covered by {why}"
            covered.append(row)
        else:
            gap.append(row)
    declared_ids = {g[0] for g in geo.values()}
    outside = [st["names"].get(g, (g, "?"))[0] for g in targeted if g not in declared_ids]
    # a city inside a targeted county is covered; hide redundant city adds when
    # the same run is adding that city's county
    # BROAD = a whole county known only from the wizard, on an account that
    # already runs its own targeting (>= 5 places). Those change lead mix and
    # spend reach, so apply skips them unless --include-broad. On a near-empty
    # account (AirCare: Abilene only) the wizard counties ARE the plan.
    few = len(targeted) < 5
    for r in gap:
        # wizard-only places on an established account: the wizard's
        # allCities lists run to every town in a county (Dry County: 80
        # Riverside/San Bernardino towns), so they are review-tier too
        r["broad"] = r["sources"] == ["wizard"] and not few
    adding_counties = {r["geo"] for r in gap if r["type"] == "County" and not r["broad"]}
    for r in gap:
        n, s = r["place"].rsplit(", ", 1)
        cty = places[(n, s)].get("county")
        via = county_ids.get(((cty or "").lower().replace(" county", ""), s)) if cty else None
        r["redundant"] = bool(via and via in adding_counties and r["type"] != "County")
    _save_cache()
    return {
        "slug": slug, "company_id": cid, "name": co.get("name"), "account": acid,
        "campaigns": st["campaigns"],
        "targets": sorted(st["names"].get(g, (g, "?"))[0] for g in targeted),
        "excluded": sorted(st["names"].get(g, (g, "?"))[0] for g in negated),
        "declared": len(places), "covered": covered, "gap": gap,
        "unresolved": unresolved, "outside_declared": sorted(outside),
    }


def _contained(name: str, state: str, ttype: str, tnames: list) -> str | None:
    """Is this place inside a broader target already on the campaign?"""
    states = {c.split(",")[0] for c, t in tnames if t == "State"}
    if state in states:
        return f"{state} (state)"
    counties = {c.split(",")[0].lower() for c, t in tnames
                if t == "County" and c.endswith(f"{state},United States")}
    zips = {c.split(",")[0] for c, t in tnames if t == "Postal Code"}
    if ttype == "County" or not (counties or zips):
        return None
    u = place_units(name, state)
    if u.get("county") and u["county"].lower() in counties:
        return u["county"]
    hit = [z for z in u.get("zips") or [] if z in zips]
    if hit:
        return f"ZIP {', '.join(hit[:3])}"
    return None


def _print(a: dict) -> None:
    if a.get("skip"):
        print(f"== {a['slug']}: SKIP ({a['skip']})")
        return
    camp = "; ".join(f"{v['status']}/{v['serving']}" for v in a["campaigns"].values())
    print(f"== {a['name']} ({a['slug']})  LSA {a['account']}  [{camp}]")
    print(f"   targeting now ({len(a['targets'])}): {', '.join(a['targets']) or 'NOTHING'}")
    adds = [g for g in a["gap"] if not g["redundant"]]
    print(f"   declared areas: {a['declared']}  covered: {len(a['covered'])}  "
          f"gap: {len(adds)}  unresolved: {len(a['unresolved'])}")
    for g in adds:
        tag = "  (broad: wizard-only, review)" if g.get("broad") else ""
        print(f"     + {g['place']:<34} {g['type']:<8} from {', '.join(g['sources'])}{tag}")
    for u in a["unresolved"]:
        print(f"     ? {u['place']:<34} (no Google geo target) from {', '.join(u['sources'])}")
    if a["outside_declared"]:
        print(f"   targeted but not in any declared source: {', '.join(a['outside_declared'])}")


# ------------------------------------------------------------------ apply
def apply(slug: str, dry: bool, broad: bool = False) -> int:
    cl = _mcc()
    a = audit(slug, cl)
    _print(a)
    adds = [g for g in a.get("gap", []) if not g["redundant"] and (broad or not g.get("broad"))]
    if a.get("skip") or not adds:
        print("   nothing to add")
        return 0
    acid = a["account"]
    camp = next(iter(a["campaigns"]))
    if a["campaigns"][camp]["eu"] != "DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING" and not dry:
        op = cl.get_type("CampaignOperation")
        op.update.resource_name = camp
        op.update.contains_eu_political_advertising = (
            cl.enums.EuPoliticalAdvertisingStatusEnum.DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING)
        op.update_mask.paths.append("contains_eu_political_advertising")
        cl.get_service("CampaignService").mutate_campaigns(customer_id=acid, operations=[op])
        print("   set EU political-ads declaration (required before criteria edits)")
    ops = []
    for g in adds:
        op = cl.get_type("CampaignCriterionOperation")
        op.create.campaign = camp
        op.create.location.geo_target_constant = g["geo"]
        ops.append(op)
    svc = cl.get_service("CampaignCriterionService")
    req = cl.get_type("MutateCampaignCriteriaRequest")
    req.customer_id = acid
    req.operations.extend(ops)
    req.validate_only = True
    svc.mutate_campaign_criteria(request=req)
    print(f"   validated {len(ops)} location add(s)")
    if dry:
        print("   DRY RUN — nothing written")
        return 0
    req.validate_only = False
    svc.mutate_campaign_criteria(request=req)
    names = [g["place"] for g in adds]
    print(f"   ADDED {len(ops)}: {', '.join(names)}")
    try:
        from work_log import work_log
        work_log(a["company_id"], "ads", "lsa-service-areas",
                 f"Local Services ads now also serve {len(names)} more area(s) you told "
                 f"us you cover: {', '.join(names)}",
                 evidence={"account": acid, "added": names}, actor="automation",
                 source="lsa_geo")
    except Exception as e:  # noqa: BLE001
        print(f"  [work-log] warn: {str(e)[:100]}")
    return 0


# ------------------------------------------------------------------ check (CI)
def check(slug: str) -> int:
    a = audit(slug)
    _print(a)
    adds = [g["place"] for g in a.get("gap", []) if not g["redundant"] and not g.get("broad")]
    if a.get("skip") or not adds:
        return 0
    sig = hashlib.sha1("|".join(sorted(adds)).encode()).hexdigest()[:12]
    state = cc.kv_get(KV) or {}
    if state.get(slug) == sig:
        print("   gap unchanged since last flag — no new note")
        return 0
    _sb("POST", "/rest/v1/marketing_ops_notes",
        {"company_id": a["company_id"], "author": "lsa-geo", "status": "open",
         "body": (f"[FLAG] LSA service areas: {len(adds)} area(s) the client says they "
                  f"cover are not targeted on LSA ({a['account']}): {', '.join(adds)}. "
                  f"Now targeting: {', '.join(a['targets']) or 'nothing'}. "
                  f"Fix: python3 scripts/lsa_geo.py apply --slug {slug}")},
        prefer="return=minimal")
    state[slug] = sig
    cc.kv_set(KV, state)
    print("   filed [FLAG] ops note")
    return 0


# ------------------------------------------------------------------ fleet report
def report() -> int:
    cl = _mcc()
    rows = _sb("GET", "/rest/v1/companies?select=id,name,integration_settings->lsa") or []
    sm = slug_map()
    for r in sorted(rows, key=lambda x: x.get("name") or ""):
        lsa = r.get("lsa") or {}
        if not lsa.get("customer_id") or not sm.get(r["id"]):
            continue
        if cc.company_inactive(_company(r["id"])):
            continue
        slug = sm[r["id"]]
        try:
            a = audit(slug, cl)
        except Exception as e:  # noqa: BLE001
            print(f"== {slug}: ERROR {str(e)[:160]}")
            continue
        _print(a)
        att = []
        if lsa.get("link_status") != "ACTIVE":
            att.append(f"manager link {lsa.get('link_status')}")
        v = lsa.get("verification") or ""
        for part in v.split(";"):
            if any(k in part for k in ("FAILED", "NO_SUBMISSION")):
                att.append(part.strip())
        m7 = lsa.get("metrics_7d") or {}
        if lsa.get("campaign_status") == "ENABLED" and not (m7.get("impressions") or 0):
            att.append("enabled but 0 impressions in 7d")
        if lsa.get("campaign_status") != "ENABLED":
            att.append(f"campaign {lsa.get('campaign_status')}")
        l14 = lsa.get("leads_14d") or {}
        print(f"   leads 14d: {l14.get('total', 0)}  spend 7d: ${m7.get('cost_usd', 0)}  "
              f"impr 7d: {m7.get('impressions', 0)}")
        if att:
            print(f"   ATTENTION: {' | '.join(att)}")
    return 0


def cmd_list_due(_a) -> int:
    rows = _sb("GET", "/rest/v1/companies?select=id,integration_settings->lsa->>customer_id") or []
    sm = slug_map()
    due = sorted({sm[r["id"]] for r in rows if r.get("customer_id") and sm.get(r["id"])
                  and not cc.company_inactive(_company(r["id"]))})
    print(json.dumps(due))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("audit")
    p.add_argument("--slug", required=True)
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("apply")
    p.add_argument("--slug", required=True)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--include-broad", action="store_true",
                   help="also add whole wizard-only counties on accounts with their own targeting")
    p = sub.add_parser("check")
    p.add_argument("--slug", required=True)
    sub.add_parser("list-due")
    sub.add_parser("report")
    a = ap.parse_args()
    cc.load_env()
    if a.cmd == "audit":
        r = audit(a.slug)
        print(json.dumps(r, indent=2, default=list)) if a.json else _print(r)
        return 0
    if a.cmd == "apply":
        return apply(a.slug, a.dry_run, a.include_broad)
    if a.cmd == "check":
        return check(a.slug)
    if a.cmd == "list-due":
        return cmd_list_due(a)
    return report()


if __name__ == "__main__":
    sys.exit(main())
