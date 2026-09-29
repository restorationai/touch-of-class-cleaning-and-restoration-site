#!/usr/bin/env python3
"""awards.py — the AWARDS PIPELINE (Santino 2026-09-27, queue item 20).

Why: award pages and "Best of" wins get a business named by Google AI
Overviews / AI Mode / ChatGPT. Verified cases: Restoration Masters won a
small ad-funded newspaper reader poll ("Best of the Central Coast 2026") and
AI answers now call them "award-winning"/#1; a $30 Quality Business Awards
page sat in Google AI Mode's citation pack in the James Ranks Enid case.
Every client should be systematically ENTERING real award programs and
PROMOTING every real win (site schema/trust strip/meta/llms.txt via
ai_answers.py, which is the one place a won award gets onto a site).

Legit lanes only. Pay-to-verify programs are OK (owner's call, 2026-09-27),
vanity plaques are display-only and never paid, and this pipeline never
fabricates an award, self-crowns, or builds award sites.

Canonical per-client store: ops_kv key `awards:{company_id}` =
  {"slug", "market": {...}, "contests": [...], "programs": {key: {...}},
   "won": [...], "updated_at"}
Re-runs merge by stable id, never duplicate; human-set fields
(status/entered/notes) survive.

Commands (all dry-run unless --apply):
  awards.py catalog                                  # print the program catalog
  awards.py discover-polls --slug X [--apply]        # local Best-of/Readers' Choice contests
  awards.py discover-won   --slug X [--apply]        # existing award pages naming the client
  awards.py plan           --slug X                  # per-client action list, by lane
  awards.py plan --slug X --queue --apply            # Mini tasks -> mini-inbox.md,
                                                     # [FOR MONICA] only for LIVE voting windows
  awards.py confirm-won --slug X --id W [--apply]    # human-confirmed candidate -> ai_answers add-award
  awards.py applied --slug X --program qba [--apply] # record a real submission (+ Reports line)
  awards.py <cmd> --all [...]                        # per-client loop over active clients, fail-open

DataForSEO: Google organic live/advanced, depth 10 (~$0.002/query); every
run is capped at MAX_RUN_COST (~$0.05) and stops querying past it.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import html as _html
import json
import re
import sys
import urllib.parse
from datetime import date, datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import client_ops_sync as cos  # noqa: E402  load_env, slug_map, _sb (fail-soft)

cos.load_env()
import ai_answers  # noqa: E402  add-award + brand/plan readers (never duplicated here)

CLIENTS = ROOT / "clients"
SITES = ROOT / "sites"
INBOX = CLIENTS / "_ops" / "mini-inbox.md"
DEAD = set(ai_answers.DEAD)  # mcc-restoration, mold-solutionz
DFS_ORGANIC = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"
MAX_RUN_COST = 0.05
MAX_PAGE_FETCHES = 8
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")
TODAY = date.today()

# ============================================================== CATALOG
# `verified` = the URL/terms were fetched or confirmed on 2026-09-27; the note
# says what was actually seen. Anything unverified says so explicitly.
CATALOG: dict[str, dict] = {
    "qba": {
        "name": "Quality Business Awards (USA)",
        "url": "https://qualitybusinessawards.com",
        "apply_url": "https://qualitybusinessawards.com/request-consideration",
        "type": "application",
        "cost": "$30 one-time admin fee, ONLY if accepted (payable later)",
        "how": "Request-consideration form: pick city + category from their fixed lists, "
               "applying year 2026/2027. Scored on ratings/reviews across platforms.",
        "ai_value": "Proven Google AI Mode citation (Enid case: '#1 Best Air Duct Cleaning in "
                    "Enid'); indexed, dofollow award page.",
        "lane": "mini",           # Mini submits; Santino pays on acceptance
        "pay_lane": "human",
        "min_rating": 4.8,        # roadmap: 4.8+ REAL ratings only
        "citation_key": None,
        "domains": ["qualitybusinessawards.com"],
        "site_link": True,
        "verified": True,
        "verified_note": "Form fetched 09-27: fee notice '$30 admin fee if my application is "
                         "accepted. Payable later'. Bakersfield + North Las Vegas in the city "
                         "list. NO water-damage/restoration category: closest are Mold "
                         "Remediation, Plumbing, General Contractor, Carpet Cleaning.",
    },
    "threebestrated": {
        "name": "ThreeBestRated (Top 3 in city)",
        "url": "https://threebestrated.com",
        "apply_url": "https://threebestrated.com/submit-business?reason=new",
        "type": "editorial",
        "cost": "Free listing consideration (decline paid upsells)",
        "how": "Submit the business; their 50-point editorial inspection picks the top 3 per "
               "city + category.",
        "ai_value": "Quoted by ChatGPT/Perplexity for 'best X in city'; Top-3 badge.",
        "lane": "mini",
        "citation_key": "threebestrated",
        "domains": ["threebestrated.com"],
        "site_link": True,
        "verified": True,
        "verified_note": "Submit link found on threebestrated.com homepage 09-27.",
    },
    "expertise": {
        "name": "Expertise.com Best-of lists",
        "url": "https://www.expertise.com",
        "apply_url": "https://www.expertise.com/review-me",
        "type": "editorial",
        "cost": "Free inclusion (advertising optional, never needed)",
        "how": "Request a review; selection by review scores/volume/volatility across "
               "databases. Also a live citations lane (Mini blitz).",
        "ai_value": "ChatGPT's favorite listicle source for local 'best X in Y'.",
        "lane": "mini",
        "citation_key": "expertise",
        "domains": ["expertise.com"],
        "site_link": True,
        "verified": True,
        "verified_note": "review-me returns 200; /about/our-selection-process fetched 09-27.",
    },
    "houzz": {
        "name": "Best of Houzz (Service)",
        "url": "https://www.houzz.com/best-of-houzz",
        "type": "auto_from_reviews",
        "cost": "Free, automatic",
        "how": "Automatic yearly (announced ~Jan-Feb) from number + quality of Houzz reviews; "
               "needs a Houzz pro profile.",
        "ai_value": "Badge + houzz.com profile is a ChatGPT-cited source.",
        "lane": "auto",
        "citation_key": "houzz",
        "domains": ["houzz.com"],
        "site_link": True,
        "verified": True,
        "verified_note": "best-of-houzz page 200; criteria per Houzz 'How to earn' article.",
    },
    "angi_ssa": {
        "name": "Angi Super Service Award",
        "url": "https://www.angi.com/standards/super-service-award.htm",
        "type": "auto_from_reviews",
        "cost": "Free, automatic",
        "how": "Awarded early Feb: 4.5+ avg AND 3+ new Angi reviews in the Nov 1 - Oct 31 "
               "window, 4.5+ lifetime, good standing, owner background check.",
        "ai_value": "Angi is a ChatGPT-cited source; award badge on profile.",
        "lane": "auto",
        "citation_key": "angi",
        "domains": ["angi.com", "angieslist.com"],
        "site_link": True,
        "window": {"eligibility_end": f"{TODAY.year}-10-31", "announce": "early February"},
        "verified": True,
        "verified_note": "Criteria confirmed via search 09-27 (page 403s to scripts).",
    },
    "nextdoor_faves": {
        "name": "Nextdoor Fave Awards (Neighborhood Faves)",
        "url": "https://business.nextdoor.com/en-us/small-business/fave-awards",
        "type": "auto_from_reviews",
        "cost": "Free (claim the free Business Page)",
        "how": "Neighbors 'Fave' businesses year-round; annual voting window; businesses share "
               "their unique Fave link. Winners per neighborhood per category.",
        "ai_value": "Trophy badge + Local Faves hub placement; neighbor proof.",
        "lane": "monica",          # vote rally while the window is open
        "citation_key": "nextdoor",
        "domains": ["nextdoor.com"],
        "site_link": False,
        "window": {"voting_start": "2026-09-10", "voting_end": "2026-09-30",
                   "winners": "early October 2026"},
        "verified": True,
        "verified_note": "Nextdoor blog + BusinessWire 2026-09-10: voting open through Sept 30, "
                         "2026, winners early October.",
    },
    "bbb_torch": {
        "name": "BBB Torch Awards for Ethics",
        "url": "https://www.bbb.org/all/torch-awards",
        "type": "application",
        "cost": "Free to apply (long application + in-person interview)",
        "how": "Per local BBB. Central California 2026: finalists named July 27, event Sept 23 "
               "(Fresno). Next cycle applications typically open spring.",
        "ai_value": "Real, reputable, press-covered; bbb.org is a ChatGPT-cited source.",
        "lane": "human",
        "citation_key": "bbb",
        "domains": ["bbb.org"],
        "site_link": True,
        "verified": True,
        "verified_note": "bbb.org/all/torch-awards 200; Central CA 2026 timeline from "
                         "thebusinessjournal.com 09-27. Southern Nevada cycle UNVERIFIED.",
    },
    "local_poll": {
        "name": "Local newspaper / chamber 'Best of' + Readers' Choice polls",
        "url": None,
        "type": "reader_poll",
        "cost": "Usually free to enter/vote (some ad-funded; decline ad packages)",
        "how": "Discovered per market (discover-polls). Nominate (write-in) during nominations, "
               "then vote-rally customers/staff/social during voting.",
        "ai_value": "THE Restoration Masters pattern: a small newspaper poll win repeated in "
                    "title/meta/schema/llms.txt made AI call them #1.",
        "lane": "mini",           # nominations = Mini; voting = Monica rally
        "citation_key": None,
        "domains": [],
        "site_link": True,
        "verified": True,
        "verified_note": "Per-contest verification lives on each contest record.",
    },
    "citybestawards": {
        "name": "City Best Awards (national online voting network)",
        "url": "https://citybestawards.com",
        "type": "reader_poll",
        "cost": "Free to be nominated/voted; sells ads + 'Billing & Renewals' upsells. "
                "Never pay.",
        "how": "Anyone can nominate a business into a city+category ballot; public votes once "
               "per 24h per nominee.",
        "ai_value": "UNPROVEN: low-authority national network, not the newspaper-poll pattern. "
                    "Display-only if a client wins; never a priority, never paid.",
        "lane": "human",
        "citation_key": None,
        "domains": ["citybestawards.com"],
        "site_link": False,
        "never_pay": True,
        "verified": True,
        "verified_note": "Bakersfield ballot page fetched 09-27 (2026 ballots, 'Nominate a "
                         "Business', ad/billing upsells).",
    },
    "businessrate": {
        "name": "BusinessRate 'Best of' (vanity)",
        "url": "https://businessrate.com",
        "type": "pay_to_verify",
        "cost": "Sells plaques/certificates. NEVER pay.",
        "how": "Auto-generated from Google ratings; not an application.",
        "ai_value": "Vanity, non-indexable (roadmap: scam). Display-only if already received; "
                    "never linked, never paid.",
        "lane": "human",
        "citation_key": None,
        "domains": ["businessrate.com"],
        "site_link": False,
        "never_pay": True,
        "verified": False,
        "verified_note": "businessrate.com 403s to scripts; classification from "
                         "docs/ai-citation-roadmap.md.",
    },
}

# Contests we have verified by hand, keyed by organizer domain. Enriches any
# discovered contest on that domain and is seeded for clients in that market.
KNOWN_CONTESTS: dict[str, dict] = {
    "bakersfield.com": {
        "name": "The Bakersfield Californian Best of Kern County Readers' Choice",
        "organizer": "The Bakersfield Californian (Bakersfield Life)",
        "url": "https://www.bakersfield.com/best-of-kern/",
        "ballot_url": "https://www.bakersfield.com/bestof2026/",
        "markets": {"counties": ["Kern County"], "cities": ["Bakersfield"], "state": "CA"},
        "self_nomination": True,
        "self_nomination_note": "Online nomination system: pick from the list or submit a "
                                "'write-in'; top 10 nominations per category make the ballot. "
                                "Organizer publishes 'Nominate Us'/'Vote for Us' logos for "
                                "nominees to promote themselves.",
        "relevant_categories": ["Best plumbing service", "Best home improvement building "
                                "contractor", "Best carpet cleaning",
                                "Best cleaning/janitorial services"],
        "category_note": "2026 poll had 187 categories and NO water damage/restoration "
                         "category (Home Services section checked 09-27).",
        "cycle_year": 2026,
        "dates": {"nominations_end": None, "voting_start": "2026-02-17",
                  "voting_end": "2026-03-03", "winners": "2026-04-23"},
        "next_cycle": "2027 cycle: nominations expected ~Dec 2026-Jan 2027, voting ~mid Feb "
                      "2027 (2026 pattern). bestof2027 page not up yet (404 on 09-27).",
        "notify": "Email webmaster@bakersfield.com with name, business name, phone, email to "
                  "be added to Best of notifications (organizer's own instruction).",
        "organizer_mentions": ["Bakersfield Californian", "Best of Kern"],
        "verified": "2026-09-27",
    },
    "beautiful.bakochamber.com": {
        "name": "Beautiful Bakersfield Awards 2027 (Greater Bakersfield Chamber of Commerce)",
        "organizer": "Greater Bakersfield Chamber of Commerce",
        "url": "https://beautiful.bakochamber.com/",
        "ballot_url": "https://beautiful.bakochamber.com/wp-content/uploads/2026/06/"
                      "2027-Nomination-Sheet.pdf",
        "kind": "committee",   # judged nomination narrative, not a popularity vote
        "markets": {"counties": ["Kern County"], "cities": ["Bakersfield"], "state": "CA"},
        "self_nomination": None,
        "self_nomination_note": "Nomination form on the site (#nominate); max two nominations "
                                "per individual/business/org; work must be completed in 2026. "
                                "Self-nomination neither allowed nor barred on the sheet "
                                "(UNVERIFIED).",
        "relevant_categories": ["Small Business of the Year (25 employees or fewer)",
                                "Business Person of the Year", "Large Business/Corporation "
                                "of the Year"],
        "category_note": "Civic award judged on community impact, since 1990; 'biggest night "
                         "in Bakersfield's civic life'. Needs a real community story.",
        "cycle_year": 2027,
        "dates": {"nominations_start": "2026-06-01", "nominations_end": "2027-01-29"},
        "next_cycle": "Nominations for 2027 open now, deadline Fri Jan 29, 2027.",
        "verified": "2026-09-27",
    },
    "bestoflasvegas.com": {
        "name": "Las Vegas Review-Journal Best of Las Vegas",
        "organizer": "Las Vegas Review-Journal (with NERUS Strategies)",
        "url": "https://www.bestoflasvegas.com/",
        "markets": {"counties": ["Clark County"], "cities": ["Las Vegas", "North Las Vegas",
                                                           "Henderson"], "state": "NV"},
        "self_nomination": None,
        "self_nomination_note": "Public nomination round; business self-nomination not "
                                "confirmed (UNVERIFIED).",
        "relevant_categories": ["Restoration Services", "Plumber", "Remodeler/Contractor",
                                "Cleaning Services", "Carpet & Flooring Cleaner"],
        "category_note": "Has a real 'Restoration Services' category (2025 category list "
                         "checked 09-27).",
        "cycle_year": 2026,
        "dates": {"nominations_start": "2026-07-13", "nominations_end": "2026-07-29",
                  "voting_start": "2026-08-17", "voting_end": "2026-09-10",
                  "winners": "2026-12-06"},
        "next_cycle": "2027 nominations expected ~mid July 2027 (2026: Jul 13-29).",
        "aliases": ["reviewjournal.com", "shopbestoflasvegas.com"],
        "organizer_mentions": ["Best of Las Vegas", "Review-Journal"],
        "verified": "2026-09-27",
    },
}

# Never a contest organizer (listicles/directories/social/infra).
NON_CONTEST_DOMAINS = {
    "yelp.com", "expertise.com", "threebestrated.com", "angi.com", "houzz.com",
    "homeadvisor.com", "thumbtack.com", "bbb.org", "facebook.com", "instagram.com",
    "x.com", "twitter.com", "tiktok.com", "youtube.com", "reddit.com", "linkedin.com",
    "wikipedia.org", "ballotpedia.org", "tripadvisor.com", "google.com", "yellowpages.com",
    "mapquest.com", "nextdoor.com", "businessrate.com", "qualitybusinessawards.com",
    "pinterest.com", "apple.com", "webull.com", "nasdaq.com", "citybestawards.com",
}
_COMPANY_TOKENS = ("restoration", "restor", "damage", "flood", "mold", "plumb", "rooter",
                   "roofing", "hvac", "carpet", "construction", "contracting", "servpro",
                   "puroclean", "dental", "law", "realty", "salon", "clinic", "insurance")
_MEDIA_TOKENS = ("news", "times", "herald", "tribune", "journal", "californian", "post",
                 "gazette", "register", "press", "weekly", "magazine", "daily", "record",
                 "chronicle", "observer", "courier", "bee", "reporter", "dispatch",
                 "examiner", "leader", "voice", "sun", "star", "review", "life", "media",
                 "tv", "radio", "kget", "kero", "ksby", "ktla", "ksnv", "fox", "abc", "nbc",
                 "cbs", "chamber", "secondstreet", "bestof", "readerschoice", "vote", "nerus")
_CONTEST_RE = re.compile(
    r"(?i)\bbest\s+of\b|readers?['’]?\s*choice|people['’]?s\s*choice|community['’]?s?\s*"
    r"choice|\bfaves?\b|favorites?\s+(?:contest|awards?|poll)|\bnominat\w*|\bballot\b|"
    r"readers['’]?\s+poll|\bvote\s+(?:now|for)\b|business\s+awards?")
_ELECTION_RE = re.compile(r"(?i)election|candidate|ballot\s+measure|proposition|city\s+council|"
                          r"mayor|primary|voter\s+guide|sample\s+ballot")
_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_DATE_RE = re.compile(
    r"(?i)\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|"
    r"sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?\s+(\d{1,2})"
    r"(?:st|nd|rd|th)?(?:,?\s*(20\d\d))?")


# ============================================================== plumbing
def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def _sid(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:12]


def _domain(url: str) -> str:
    d = urllib.parse.urlparse(url or "").netloc.lower()
    return d[4:] if d.startswith("www.") else d


def _root_domain(d: str) -> str:
    parts = d.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else d


def company_id(slug: str) -> str | None:
    for cid, s in cos.slug_map().items():
        if s == slug:
            return cid
    return None


def kv_get(k: str):
    rows = cos._sb("GET", f"/rest/v1/ops_kv?k=eq.{urllib.parse.quote(k)}&select=v",
                   prefer="return=representation")
    return rows[0]["v"] if rows else None


def kv_set(k: str, v) -> None:
    cos._sb("POST", "/rest/v1/ops_kv?on_conflict=k",
            {"k": k, "v": v, "updated_at": _now()},
            prefer="resolution=merge-duplicates,return=minimal")


def load_record(slug: str, cid: str) -> dict:
    rec = None
    try:
        rec = kv_get(f"awards:{cid}")
    except Exception as e:  # noqa: BLE001 — fail-open, start fresh
        print(f"  [warn] ops_kv read failed ({str(e)[:80]}); starting from empty record")
    rec = rec if isinstance(rec, dict) else {}
    rec.setdefault("slug", slug)
    rec.setdefault("contests", [])
    rec.setdefault("programs", {})
    rec.setdefault("won", [])
    return rec


def save_record(cid: str, rec: dict, apply: bool) -> None:
    rec["updated_at"] = _now()
    if not apply:
        print(f"  (dry-run) would write ops_kv awards:{cid} "
              f"[{len(rec['contests'])} contests, {len(rec['won'])} won]")
        return
    kv_set(f"awards:{cid}", rec)
    print(f"  wrote ops_kv awards:{cid} [{len(rec['contests'])} contests, {len(rec['won'])} won]")


# ------------------------------------------------------------- client facts
def client_facts(slug: str) -> dict:
    pi = ai_answers._plan_input(slug)
    bt = SITES / slug / "src" / "lib" / "brand.ts"
    src = bt.read_text() if bt.exists() else ""
    b = pi.get("brand") or {}
    areas = pi.get("service_areas") or []
    prim = next((a for a in areas if isinstance(a, dict) and a.get("primary")), None) \
        or (areas[0] if areas and isinstance(areas[0], dict) else {})
    city = prim.get("city") or ai_answers._brand_field(src, "primaryCity") or b.get("city") or ""
    state = prim.get("state") or ai_answers._brand_field(src, "primaryState") or b.get("state") or ""
    display = (ai_answers._brand_field(src, "displayName") or b.get("display_name") or "").strip()
    dba = ai_answers._brand_field(src, "dbaName").strip()
    legal = (ai_answers._brand_field(src, "legalName") or b.get("legal_name") or "").strip()
    names = []
    for n in (display, dba.split("-")[0] if dba else "", b.get("short_name") or "", legal):
        n = re.sub(r"(?i)[\s,]+(inc|llc|corp|co)\.?\s*$", "", (n or "").strip()).strip()
        if n and len(n) >= 4 and _norm(n) not in {_norm(x) for x in names}:
            names.append(n)
    phone = ai_answers._brand_field(src, "phone") or b.get("phone") or ""
    rating = ai_answers._brand_field(src, "gbpRatingValue")
    count = ai_answers._brand_field(src, "gbpReviewCount")
    services = [(s.get("slug") or s.get("name")) if isinstance(s, dict) else str(s)
                for s in (pi.get("services") or [])]
    other_cities = [a.get("city") for a in areas if isinstance(a, dict) and a.get("city")
                    and a.get("city") != city][:3]
    return {
        "slug": slug, "names": names, "city": city, "state": state, "phone": phone,
        "phone10": re.sub(r"\D", "", phone)[-10:], "domain": _domain(
            ai_answers._brand_field(src, "canonicalUrl")) or "",
        "rating": float(rating) if re.fullmatch(r"\d(\.\d+)?", rating or "") else None,
        "reviews": int(count) if (count or "").isdigit() else None,
        "services": services, "template": pi.get("template") or "restoration",
        "county": b.get("county") or prim.get("county"), "lat": b.get("lat"),
        "lng": b.get("lng"), "other_cities": other_cities,
        "awards": [a for a in (b.get("awards") or []) if a.get("name")],
    }


def resolve_county(f: dict, rec: dict) -> str | None:
    """plan-input county > cached market.county > OSM reverse geocode (free, fail-open)."""
    if f.get("county"):
        return f["county"]
    m = rec.get("market") or {}
    if m.get("county") and m.get("city") == f["city"]:
        return m["county"]
    if f.get("lat") and f.get("lng"):
        try:
            r = requests.get("https://nominatim.openstreetmap.org/reverse", timeout=15,
                             params={"lat": f["lat"], "lon": f["lng"], "format": "json",
                                     "zoom": 10, "addressdetails": 1},
                             headers={"User-Agent": "RankAI-awards/1.0"})
            return (r.json().get("address") or {}).get("county")
        except Exception:  # noqa: BLE001
            return None
    return None


def citation_urls(cid: str) -> dict:
    try:
        rows = cos._sb("GET", f"/rest/v1/user_integrations?client_id=eq.{cid}"
                       "&provider=eq.citations&select=connection_metadata",
                       prefer="return=representation") or []
        return dict(((rows[0].get("connection_metadata") or {}).get("citation_urls") or {})
                    if rows else {})
    except Exception as e:  # noqa: BLE001
        print(f"  [warn] citation read failed: {str(e)[:80]}")
        return {}


# ------------------------------------------------------------- DataForSEO
class DFS:
    def __init__(self):
        import geogrid_scan as gs
        u, p = gs.load_dfs_creds()
        self.auth = base64.b64encode(f"{u}:{p}".encode()).decode()
        self.cost = 0.0

    def serp(self, q: str) -> list[dict]:
        if self.cost >= MAX_RUN_COST:
            print(f"  [dfs] cost cap ${MAX_RUN_COST:.2f} reached; skipping: {q}")
            return []
        try:
            r = requests.post(DFS_ORGANIC, timeout=120, headers={
                "Authorization": "Basic " + self.auth, "Content-Type": "application/json"},
                json=[{"keyword": q, "language_code": "en", "location_code": 2840,
                       "depth": 10}])
            task = (r.json().get("tasks") or [{}])[0]
        except Exception as e:  # noqa: BLE001
            print(f"  [dfs] error on '{q}': {str(e)[:80]}")
            return []
        self.cost += float(task.get("cost") or 0)
        items = (((task.get("result") or [{}])[0] or {}).get("items")) or []
        return [{"title": it.get("title") or "", "url": it.get("url") or "",
                 "domain": _domain(it.get("url") or ""), "snippet": it.get("description") or ""}
                for it in items if it.get("type") == "organic"]


def fetch_text(url: str) -> str:
    """Visible page text. Decodes TownNews/BLOX ROT47-obfuscated premium bodies
    (bakersfield.com et al. ship 'kAm...' lines that are ROT47 <p> tags)."""
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent": UA})
        if r.status_code >= 400:
            return ""
        s = r.text
    except Exception:  # noqa: BLE001
        return ""
    s = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", s)
    t = _html.unescape(re.sub(r"<[^>]+>", "\n", s))
    out = []
    for line in t.split("\n"):
        line = line.strip()
        if line.startswith(("kAm", "k9", "kFa", "kC")) and " " in line:
            line = re.sub(r"<[^>]+>", " ", "".join(
                chr(33 + ((ord(c) + 14) % 94)) if 33 <= ord(c) <= 126 else c for c in line))
        if line:
            out.append(line)
    return re.sub(r"[ \t]+", " ", "\n".join(out))


# ------------------------------------------------------------- phase logic
def _parse_dates(text: str, default_year: int) -> dict:
    """Pull labelled dates ('Voting will start on Feb. 17, 2026') out of text."""
    found: dict[str, str] = {}
    for m in _DATE_RE.finditer(text or ""):
        mon = _MONTHS[m.group(1)[:3].lower()]
        yr = int(m.group(3) or default_year)
        try:
            d = date(yr, mon, int(m.group(2))).isoformat()
        except ValueError:
            continue
        ctx = text[max(0, m.start() - 110):m.start()].lower()
        ctx = ctx.split(". ")[-1] if ". " in ctx else ctx   # same sentence only
        base = None
        for mm in re.finditer(r"nominat|vot(e|ing|es)\b|winner|result|announc|celebrat|gala",
                              ctx):
            base = mm.group(0)
        tail = ctx[-30:]
        end = re.search(r"until|through|thru|\bby\b|deadline|clos|\bends?\b", tail)
        begin = re.search(r"open|begin|start|\bon\b", tail)
        kind = None
        if base and base.startswith("nominat"):
            kind = "nominations_end" if end or not begin else "nominations_start"
        elif base and base.startswith("vot"):
            kind = "voting_end" if end or not begin else "voting_start"
        elif base:
            kind = "winners"
        if kind and kind not in found:
            found[kind] = d
    return found


def compute_phase(dates: dict, text: str = "") -> tuple[str, str]:
    """-> (phase, basis). Phases: nominations_open, between_rounds, voting_open,
    voting_closed (results pending), winners_announced, closed, unknown."""
    t = TODAY.isoformat()
    ns, ne = dates.get("nominations_start"), dates.get("nominations_end")
    vs, ve, w = dates.get("voting_start"), dates.get("voting_end"), dates.get("winners")
    if vs and ve and vs <= t <= ve:
        return "voting_open", "dates"
    if ns and ne and ns <= t <= ne:
        return "nominations_open", "dates"
    if ne and vs and ne < t < vs:
        return "between_rounds", "dates"
    if ve and t > ve:
        if w and re.match(r"\d{4}-\d\d-\d\d", w) and t < w:
            return "voting_closed", "dates"
        return ("winners_announced" if w else "closed"), "dates"
    if vs and t < vs and not ns:
        return "between_rounds", "dates"
    low = (text or "").lower()
    if ne and not ns and t <= ne and re.search(r"nominat\w*[^.]{0,80}\bopen", low):
        return "nominations_open", "dates+text"
    if ve and not vs and t <= ve and re.search(r"vot\w*[^.]{0,80}\bopen|vote now", low):
        return "voting_open", "dates+text"
    past = [d for d in (ns, ne, vs, ve, w) if d and re.match(r"\d{4}-\d\d-\d\d", d)]
    if past and all(d < t for d in past):
        return "closed", "dates"
    if re.search(r"vote now|voting is (now )?open|cast your vote|voting (runs|continues)", low) \
            and not re.search(r"voting (has )?(ended|closed)", low):
        return "voting_open", "text"
    if re.search(r"nominate now|nominations (are )?(now )?open|submit (a |your )?nominations?",
                 low) and not re.search(r"nominations (have )?(ended|closed)", low):
        return "nominations_open", "text"
    if re.search(r"winners (are|were) announced|results are in|votes are in|congratulations "
                 r"to (the|our|all) winners", low):
        return "winners_announced", "text"
    if re.search(r"nominations (have )?(ended|closed)", low):
        return "between_rounds", "text"
    return "unknown", "none"


# ============================================================== discover-polls
def _is_contest(hit: dict, f: dict, county: str | None) -> bool:
    d = hit["domain"]
    if not d or _root_domain(d) in NON_CONTEST_DOMAINS or d in NON_CONTEST_DOMAINS:
        return False
    if f["domain"] and _root_domain(d) == _root_domain(f["domain"]):
        return False
    blob = f"{hit['title']} {hit['snippet']} {urllib.parse.unquote(hit['url'])}"
    if not _CONTEST_RE.search(blob) or _ELECTION_RE.search(hit["title"]):
        return False
    loc = [f["city"], f["state"] if len(f["state"]) > 2 else ""] + ([county] if county else [])
    local = any(x and x.lower() in blob.lower() for x in loc) \
        or (county and county.replace(" County", "").lower() in blob.lower())
    if not local:
        return False
    flat = d.replace("-", "").replace(".", "")
    media = any(tok in flat for tok in _MEDIA_TOKENS)
    company = any(tok in flat for tok in _COMPANY_TOKENS)
    return media or not company


def _contest_key(url: str) -> tuple[str, str]:
    d = _domain(url)
    for kd, kc in KNOWN_CONTESTS.items():
        if d == kd or d.endswith("." + kd) or any(d == a or d.endswith("." + a)
                                                  for a in kc.get("aliases", [])):
            return kd, kd
    if "secondstreetapp.com" in d or d.startswith("vote.") or "bestof" in d:
        seg = re.sub(r"\d{4}|[^a-z]+", "", (urllib.parse.urlparse(url).path.split("/") + ["", ""])[1].lower())
        return f"{d}/{seg}", d
    return _root_domain(d), d


def _known_for_market(f: dict, county: str | None) -> list[str]:
    out = []
    for kd, kc in KNOWN_CONTESTS.items():
        mk = kc["markets"]
        if mk.get("state") and mk["state"] != f["state"]:
            continue
        cities = [f["city"]] + list(f.get("other_cities") or [])
        if (county and county in mk.get("counties", [])) or any(c in mk.get("cities", [])
                                                               for c in cities):
            out.append(kd)
    return out


def _merge_contest(rec: dict, new: dict) -> str:
    for c in rec["contests"]:
        if c["id"] == new["id"]:
            human = {k: c[k] for k in ("status", "entered", "notes", "nominated_at",
                                       "voting_rally_filed") if k in c}
            aliases = sorted(set((c.get("aliases") or []) + (new.get("aliases") or [])
                                 + [new.get("url")]) - {None, c.get("url")})[:8]
            ev = (c.get("evidence") or []) + [e for e in (new.get("evidence") or [])
                                              if e not in (c.get("evidence") or [])]
            c.update({k: v for k, v in new.items() if v not in (None, [], {})})
            c.update(human)
            c["aliases"], c["evidence"] = aliases, ev[-6:]
            return "updated"
    new.setdefault("first_seen", _now())
    rec["contests"].append(new)
    return "new"


def discover_polls(slug: str, apply: bool, dfs: DFS | None = None) -> dict:
    cid = company_id(slug)
    if not cid:
        print(f"{slug}: no company_id; skipped")
        return {}
    f = client_facts(slug)
    rec = load_record(slug, cid)
    county = resolve_county(f, rec)
    rec["market"] = {"city": f["city"], "state": f["state"], "county": county}
    yr, nxt = TODAY.year, TODAY.year + 1
    city = f["city"]
    print(f"{slug} [{cid}] market: {city}, {f['state']} / {county or 'county ?'}")
    queries = [f"best of {city} {yr} vote", f"{city} readers choice {yr} nominations",
               f"best of {city} {nxt}", f"{city} {f['state']} people's choice awards {yr}"]
    if county:
        queries.append(f"best of {county} {yr}")
    queries.append(f"{city} chamber of commerce business awards {yr}")
    for oc in (f.get("other_cities") or [])[:1]:
        queries.append(f"best of {oc} {yr} readers choice")
    dfs = dfs or DFS()
    start_cost = dfs.cost
    cands: dict[str, dict] = {}
    for q in queries:
        for h in dfs.serp(q):
            if not _is_contest(h, f, county):
                continue
            key, d = _contest_key(h["url"])
            c = cands.setdefault(key, {"key": key, "domain": d, "hits": []})
            c["hits"].append({**h, "query": q})
    # Seed verified market contests even if SERP missed them this run.
    for kd in _known_for_market(f, county):
        cands.setdefault(kd, {"key": kd, "domain": kd, "hits": []})

    fetched = 0
    counts = {"new": 0, "updated": 0}
    # Unknown candidates first so pages about a known contest can fold into it.
    for key in sorted(cands, key=lambda k: k in KNOWN_CONTESTS):
        c = cands[key]
        known = KNOWN_CONTESTS.get(key)
        hits = c["hits"]
        top = hits[0] if hits else {}
        url = (known or {}).get("url") or top.get("url")
        text = " ".join(f"{h['title']}. {h['snippet']}" for h in hits)
        if not known and fetched < MAX_PAGE_FETCHES and url:
            text = fetch_text(url)[:40000] + "\n" + text
            fetched += 1
            # A business's own "vote for us in Best of Kern" page is evidence of
            # the KNOWN contest, not a contest of its own.
            fold = next((kd for kd, kc in KNOWN_CONTESTS.items()
                         if kd in cands and any(mn.lower() in text.lower()
                                                for mn in kc.get("organizer_mentions", []))),
                        None)
            if fold and not any(t in c["domain"] for t in _MEDIA_TOKENS[:20]):
                cands[fold]["hits"] += hits
                print(f"  (folded {c['domain']} into known contest {fold})")
                continue
        if known:
            dates = dict(known["dates"])
            phase, basis = compute_phase(dates)
        else:
            dates = _parse_dates(text, yr)
            phase, basis = compute_phase(dates, text)
        name = (known or {}).get("name") or re.split(r"\s[|\-–]\s", top.get("title") or key)[0][:120]
        self_nom = (known or {}).get("self_nomination")
        if self_nom is None and re.search(r"(?i)write[- ]in|nominate (your|a) (business|"
                                          r"favorite)|businesses (may|can) nominate", text):
            self_nom = True
        rec_c = {
            "id": _sid(key), "key": key, "name": name,
            "organizer": (known or {}).get("organizer") or c["domain"],
            "url": url, "ballot_url": (known or {}).get("ballot_url"),
            "aliases": sorted({h["url"] for h in hits if h["url"] != url})[:8],
            "phase": phase, "phase_basis": basis, "dates": dates,
            "self_nomination": self_nom, "kind": (known or {}).get("kind") or "reader_poll",
            "self_nomination_note": (known or {}).get("self_nomination_note"),
            "relevant_categories": (known or {}).get("relevant_categories"),
            "category_note": (known or {}).get("category_note"),
            "next_cycle": (known or {}).get("next_cycle"),
            "notify": (known or {}).get("notify"),
            "verified": bool(known), "verified_on": (known or {}).get("verified"),
            "market": f"{city}, {f['state']}", "last_seen": _now(),
            "evidence": [{"q": h["query"], "title": h["title"][:140], "url": h["url"]}
                         for h in hits[:3]],
        }
        rec_c.setdefault("status", "verified" if known else "candidate")
        counts[_merge_contest(rec, rec_c)] += 1
        flag = "VERIFIED" if known else "candidate"
        print(f"  - [{flag}] {name}\n      {url}\n      phase={phase} ({basis}) "
              f"dates={json.dumps(dates)} self_nom={self_nom}")
    rec["contests"].sort(key=lambda c: (not c.get("verified"), c.get("name") or ""))
    rec["last_discover_polls"] = {"at": _now(), "cost": round(dfs.cost - start_cost, 4),
                                  "queries": len(queries)}
    print(f"  contests: {counts['new']} new, {counts['updated']} updated; "
          f"DFS ${dfs.cost - start_cost:.4f}")
    save_record(cid, rec, apply)
    return rec


# ============================================================== discover-won
def _name_on_page(f: dict, text: str) -> str | None:
    nt = _norm(text)
    for n in f["names"]:
        if len(_norm(n)) >= 8 and _norm(n) in nt:
            return n
    return None


def _award_from_page(prog: str | None, url: str, title: str, text: str, f: dict) -> dict | None:
    """Program-specific extraction. Returns an award dict only when the page
    itself states the award (never inferred)."""
    yr = str(TODAY.year)
    ym = re.search(r"\b(20\d\d)\b", title or "")
    year = ym.group(1) if ym else None
    city = f["city"]
    if prog == "qba":
        m = re.search(r"(?i)(best\s+[\w &/-]{3,50}?\s+in\s+[\w .'-]{3,40})", title + " " + text[:3000])
        if m:
            return {"name": f"Quality Business Awards {m.group(1).strip()}", "year": year or yr,
                    "organizer": "Quality Business Awards", "url": url}
    if prog == "threebestrated":
        m = re.search(r"(?i)(?:3|three)\s+best\s+([\w &/-]{3,50}?)\s+in\s+([\w .'-]{3,40}?)(?:,|\s-|$)",
                      title)
        if m:
            return {"name": f"ThreeBestRated Top 3 {m.group(1).strip()} in {m.group(2).strip()}",
                    "year": year or yr, "organizer": "ThreeBestRated", "url": url}
    if prog == "expertise":
        m = re.search(r"(?i)best\s+([\w &/-]{3,60}?)\s+in\s+([\w .'-]{3,40}?)(?:,|\s-|\||$)", title)
        if m:
            return {"name": f"Expertise.com Best {m.group(1).strip()} in {m.group(2).strip()}",
                    "year": year or yr, "organizer": "Expertise.com", "url": url}
    if prog == "houzz":
        m = re.search(r"(?i)best of houzz\s+(20\d\d)", text)
        if m:
            return {"name": "Best of Houzz", "year": m.group(1), "category": "Service",
                    "organizer": "Houzz", "url": url}
    if prog == "angi_ssa":
        m = re.search(r"(?i)super service award[^\n]{0,20}?(20\d\d)", text)
        if m:
            return {"name": "Angi Super Service Award", "year": m.group(1),
                    "organizer": "Angi", "url": url}
    if prog == "nextdoor_faves":
        m = re.search(r"(?i)(20\d\d)\s+(?:neighborhood\s+)?faves?(?:\s+awards?)?\s+winner", text)
        if m:
            return {"name": "Nextdoor Neighborhood Fave", "year": m.group(1),
                    "organizer": "Nextdoor", "url": url}
    if prog == "businessrate":
        m = re.search(r"(?i)best of (20\d\d)", title + " " + text[:2000])
        if m:
            return {"name": f"BusinessRate Best of {m.group(1)}", "year": int(m.group(1)),
                    "organizer": "BusinessRate", "display_only": True}
    _ = city
    return None


def _program_for(domain: str) -> str | None:
    for k, p in CATALOG.items():
        if any(domain == d or domain.endswith("." + d) for d in p.get("domains", [])):
            return k
    return None


def _already_on_site(f: dict, aw: dict) -> bool:
    for a in f["awards"]:
        if (aw.get("url") and a.get("url") == aw["url"]) or _norm(a.get("name")) == _norm(aw["name"]):
            return True
        if aw.get("organizer") == a.get("organizer") == "BusinessRate" and \
                str(aw.get("year")) == str(a.get("year")):
            return True
    return False


def add_award_via_ai_answers(slug: str, aw: dict) -> None:
    """The ONE path onto the site: ai_answers add-award (plan-input + sync/deploy)."""
    ns = argparse.Namespace(slug=slug, name=aw["name"], year=str(aw.get("year") or "") or None,
                            category=aw.get("category"), organizer=aw.get("organizer"),
                            url=aw.get("url") if aw.get("site_link", True) else None,
                            image=None)
    ai_answers.cmd_add_award(ns)


def discover_won(slug: str, apply: bool, dfs: DFS | None = None) -> dict:
    cid = company_id(slug)
    if not cid:
        print(f"{slug}: no company_id; skipped")
        return {}
    f = client_facts(slug)
    rec = load_record(slug, cid)
    if not f["names"]:
        print(f"{slug}: no business name on file; skipped")
        return rec
    n0 = f["names"][0]
    sites = " OR ".join(f"site:{d}" for k in ("qba", "threebestrated", "expertise",
                                               "businessrate") for d in CATALOG[k]["domains"])
    queries = [f'"{n0}" award', f'"{n0}" "best of"',
               f'"{n0}" {f["city"]} readers choice OR winner OR "best of {TODAY.year}"',
               f'"{n0}" {sites}']
    if len(f["names"]) > 1:
        queries.append(f'"{f["names"][1]}" award OR "best of"')
    print(f"{slug} [{cid}] names={f['names']} city={f['city']}")
    dfs = dfs or DFS()
    start_cost = dfs.cost
    hits: dict[str, dict] = {}
    for q in queries:
        for h in dfs.serp(q):
            d = h["domain"]
            if not d or (f["domain"] and _root_domain(d) == _root_domain(f["domain"])):
                continue
            prog = _program_for(d)
            blob = f"{h['title']} {h['snippet']} {h['url']}"
            if prog or re.search(r"(?i)award|best of|winner|readers?['’]?\s*choice|top 3|"
                                 r"\bfaves?\b|super service", blob):
                hits.setdefault(h["url"], {**h, "program": prog})
    fetched, found = 0, []
    for url, h in hits.items():
        if fetched >= MAX_PAGE_FETCHES:
            break
        if _root_domain(h["domain"]) in {"facebook.com", "instagram.com", "linkedin.com",
                                         "yelp.com", "x.com", "twitter.com", "youtube.com"}:
            continue
        text = fetch_text(url)
        fetched += 1
        who = _name_on_page(f, text)
        local = (f["city"] and f["city"].lower() in text.lower()) or \
            (f["phone10"] and f["phone10"] in re.sub(r"\D", "", text))
        if not who or not local:
            continue
        aw = _award_from_page(h["program"], url, h["title"], text, f)
        entry = {"id": _sid(url), "url": url, "title": h["title"][:160],
                 "program": h["program"], "matched_name": who, "found_at": _now()}
        if aw:
            aw["site_link"] = CATALOG.get(h["program"] or "", {}).get("site_link", True)
            entry.update({"award": aw, "verified": True})
        else:
            entry.update({"verified": False,
                          "note": "names the client + city but no award statement parsed; "
                                  "human confirm (confirm-won) before it goes on the site"})
        found.append(entry)
    counts = {"added": 0, "already": 0, "candidates": 0}
    known_ids = {w.get("id") for w in rec["won"]}
    for e in found:
        aw = e.get("award")
        if e["verified"] and aw and aw.get("display_only") and not _already_on_site(f, aw):
            e["verified"] = False
            e["note"] = "vanity/pay-to-verify program: display-only, never auto-added or paid"
        status = "candidate"
        if e["verified"] and aw:
            if _already_on_site(f, aw):
                status = "on_site"
                counts["already"] += 1
            elif apply:
                add_award_via_ai_answers(slug, aw)
                status = "added"
                e["added_at"] = _now()
                counts["added"] += 1
            else:
                status = "would_add"
                counts["added"] += 1
        else:
            counts["candidates"] += 1
        e["status"] = status
        print(f"  - [{status}] {e['title']}\n      {e['url']}"
              + (f"\n      award: {ai_answers.award_label(aw)}" if aw else "")
              + (f"\n      note: {e['note']}" if e.get("note") else ""))
        if e["id"] in known_ids:
            for w in rec["won"]:
                if w.get("id") == e["id"]:
                    keep = {k: w[k] for k in ("added_at", "congrats_listed", "notes") if k in w}
                    w.update(e)
                    w.update(keep)
        else:
            rec["won"].append(e)
    # Awards already on the site (e.g. DV's BusinessRate) are part of the record too.
    for a in f["awards"]:
        wid = _sid("site", _norm(a["name"]))
        if wid not in {w.get("id") for w in rec["won"]}:
            rec["won"].append({"id": wid, "status": "on_site", "award": a, "verified": True,
                               "title": ai_answers.award_label(a), "url": a.get("url"),
                               "program": _program_for(_domain(a.get("url") or "")) or (
                                   "businessrate" if a.get("organizer") == "BusinessRate" else None),
                               "found_at": _now(), "source": "plan-input brand.awards"})
    rec["last_discover_won"] = {"at": _now(), "cost": round(dfs.cost - start_cost, 4),
                                "pages_checked": fetched, "serp_hits": len(hits)}
    print(f"  won: {counts['added']} {'added' if apply else 'would add'}, {counts['already']} "
          f"already on site, {counts['candidates']} need human review; "
          f"DFS ${dfs.cost - start_cost:.4f}")
    save_record(cid, rec, apply)
    return rec


# ============================================================== plan
def _qba_category(f: dict) -> str:
    svc = set(f["services"])
    if f["template"] == "plumbing" or {"emergency-plumbing", "plumbing"} & svc and \
            "plumb" in " ".join(f["names"]).lower():
        return "Plumbing"
    for s, cat in (("mold-remediation", "Mold Remediation"), ("plumbing", "Plumbing"),
                   ("emergency-plumbing", "Plumbing"), ("carpet-cleaning", "Carpet Cleaning"),
                   ("hvac", "HVAC Services"), ("roofing", "Roofing")):
        if s in svc:
            return cat
    return "General Contractor"


GUARDRAILS = ("Guardrails: REAL NAP only (settled business name, real address, REAL business "
              "phone, never a tracking number); new logins use setup-{slug}@restorationai.io; "
              "CAPTCHA = one checkbox click max, puzzles -> park; ANY payment/fee screen -> "
              "STOP, park, structured Need type=human (Santino pays); one submission per "
              "client per program; daytime PT; ledger line + commit/push the moment it is "
              "submitted; do not accept ad/upsell packages. After a real submission run "
              "`python3 scripts/awards.py applied --slug {slug} --program <key> --apply` so it "
              "shows in the client's Reports tab.")


def build_plan(slug: str) -> tuple[dict, list[dict]]:
    cid = company_id(slug)
    f = client_facts(slug)
    rec = load_record(slug, cid) if cid else {"contests": [], "programs": {}, "won": []}
    cites = citation_urls(cid) if cid else {}
    acts: list[dict] = []
    progs = rec.setdefault("programs", {})

    def act(lane, key, title, detail, file=False, **kw):
        acts.append({"lane": lane, "key": key, "title": title, "detail": detail,
                     "file": file, **kw})

    def pstat(k, status, reason=""):
        prev = progs.get(k) or {}
        if prev.get("status") in ("applied", "won", "declined", "queued") and \
                status in ("eligible", "missing"):
            return prev["status"]
        progs[k] = {**prev, "status": status, "reason": reason, "updated_at": _now()}
        return status

    rating, reviews = f["rating"], f["reviews"]
    # --- Quality Business Awards
    q = CATALOG["qba"]
    if rating is None or rating < q["min_rating"]:
        pstat("qba", "ineligible", f"GBP rating {rating} < {q['min_rating']} (real ratings only)")
    else:
        st = pstat("qba", "eligible", f"GBP {rating} from {reviews} reviews")
        if st == "eligible":
            cat = _qba_category(f)
            act("mini", "qba-apply", f"Submit Quality Business Awards application ({cat}, "
                f"{f['city']})",
                f"Form: {q['apply_url']}. City '{f['city']}', category '{cat}', applying year "
                f"{TODAY.year} (pick {TODAY.year + 1} if {TODAY.year} is closed). Business "
                f"email field = client's own; contact/login = setup-{slug}@restorationai.io. "
                f"Tick the $30 fee notice (payable later ONLY if accepted); pay nothing now.")
            act("human", "qba-pay", "Pay QBA $30 admin fee IF accepted (Santino)",
                "Acceptance email lands in contact@ via the setup alias. After payment, run "
                "awards.py discover-won so the award page goes onto the site.")
    # --- citation-backed editorial programs
    for k in ("threebestrated", "expertise"):
        p = CATALOG[k]
        if cites.get(p["citation_key"]):
            pstat(k, "listed", cites[p["citation_key"]])
        elif pstat(k, "missing", "no listing URL on the citations card") == "missing":
            act("mini", f"{k}-apply", f"{p['name']}: submit {f['names'][0] if f['names'] else slug}",
                f"{p['apply_url']} ({p['cost']}). Also a citations lane: skip if the blitz "
                f"already did it (check mini-ledger).")
    # --- automatic review-driven programs
    for k in ("houzz", "angi_ssa"):
        p = CATALOG[k]
        if cites.get(p["citation_key"]):
            pstat(k, "eligible_auto", "profile exists; award follows reviews")
            extra = (" Angi window closes Oct 31: 3+ new Angi reviews at 4.5+ needed."
                     if k == "angi_ssa" else "")
            act("auto", k, f"{p['name']}: automatic from reviews", p["how"] + extra)
        else:
            pstat(k, "no_profile", f"no {p['citation_key']} profile on file")
    # --- Nextdoor Faves (program-level voting window)
    nd = CATALOG["nextdoor_faves"]
    w = nd["window"]
    live = w["voting_start"] <= TODAY.isoformat() <= w["voting_end"]
    if cites.get("nextdoor"):
        pstat("nextdoor_faves", "listed", cites["nextdoor"])
        if live:
            act("monica", "nextdoor-rally", f"Nextdoor Fave Awards voting is LIVE until "
                f"{w['voting_end']}: vote rally",
                "Ask the client to share their Nextdoor Fave link with past customers, staff and "
                "social before the window closes (link is on their Nextdoor Business Page).",
                file=True, window_end=w["voting_end"],
                note_body=(f"[FOR MONICA] AWARDS-VOTE-nextdoor-{TODAY.year} Nextdoor's {TODAY.year}"
                           f" Fave Awards voting is open until {w['voting_end']}. Ask them to "
                           f"share their Nextdoor Fave link (on their Nextdoor Business Page) "
                           f"with happy past customers, their staff and their social pages so "
                           f"neighbors can vote for them. One short, friendly ask. Their "
                           f"listing: {cites['nextdoor']}"))
    else:
        pstat("nextdoor_faves", "no_profile", "no Nextdoor Business Page on file")
        act("mini", "nextdoor-claim", "Claim/create the Nextdoor Business Page",
            "Needed for Fave Awards (next voting window ~Sept "
            f"{TODAY.year + 1 if not live else TODAY.year}). Blitz lane already covers it.")
    # --- BBB Torch
    pstat("bbb_torch", "info", CATALOG["bbb_torch"]["how"])
    act("human", "bbb-torch", "BBB Torch Awards: decide whether to apply next cycle",
        CATALOG["bbb_torch"]["how"] + " Long application + interview; best for clients "
        "with a strong ethics/community story.")
    # --- local polls
    for c in rec.get("contests") or []:
        if c.get("status") == "ignored":
            continue
        ph = c.get("phase")
        conf_ok = c.get("verified") or c.get("phase_basis") == "dates"
        tag = f"{c['name']} ({c.get('organizer')})"
        if ph == "nominations_open" and c.get("kind") == "committee":
            act("human", f"poll-committee-{c['id']}", f"Nomination narrative: {tag}",
                f"Deadline {c['dates'].get('nominations_end') or '?'}. Judged award, needs a "
                f"real community story (volunteering, donations, local impact). Categories: "
                f"{', '.join(c.get('relevant_categories') or [])}. Get the story from the client "
                f"(Monica can ask later), write it, then Mini submits. {c['url']}")
        elif ph == "nominations_open":
            if c.get("self_nomination") is not False and not c.get("nominated_at"):
                cats = ", ".join(c.get("relevant_categories") or []) or "the closest " \
                    "home-services/restoration/plumbing category"
                act("mini", f"poll-nominate-{c['id']}", f"Nominate {f['names'][0] if f['names'] else slug} in {tag}",
                    f"{c.get('ballot_url') or c['url']}. Write-in nomination in: {cats}. "
                    f"One nomination per category, as the business. Nominations close "
                    f"{c['dates'].get('nominations_end') or '(date unknown)'}.")
            act("monica", f"poll-nominate-share-{c['id']}", f"(list only) nomination share ask: {tag}",
                "Not filed: Monica asks are filed only during a live VOTING window.")
        elif ph == "voting_open":
            act("monica", f"poll-rally-{c['id']}", f"Vote rally: {tag} voting open until "
                f"{c['dates'].get('voting_end') or '?'}",
                "Only if the client is on the ballot (nominee). Ask them to share the vote link "
                "with customers, staff and social.", file=bool(conf_ok) and not c.get("voting_rally_filed"),
                window_end=c["dates"].get("voting_end"),
                note_body=(f"[FOR MONICA] AWARDS-VOTE-{c['id']} {c['name']} voting is open "
                           f"until {c['dates'].get('voting_end') or 'soon'}. If they are on the "
                           f"ballot, ask them to share the vote link ({c.get('ballot_url') or c['url']}) "
                           f"with happy customers, their staff and their social pages. One short, "
                           f"friendly ask, no pressure."))
        elif ph in ("between_rounds",):
            act("human", f"poll-wait-{c['id']}", f"{tag}: between rounds",
                f"Check whether the client made the ballot. Voting starts "
                f"{c['dates'].get('voting_start') or '?'}.")
        else:
            nxt = c.get("next_cycle") or "next cycle dates unknown; re-run discover-polls monthly"
            detail = f"Phase: {ph}. {nxt}"
            if c.get("category_note"):
                detail += f" {c['category_note']}"
            if c.get("notify"):
                detail += f" ACTION: {c['notify']}"
            act("human", f"poll-watch-{c['id']}", f"{tag}: watch for next cycle", detail)
    # --- won awards
    for wn in rec.get("won") or []:
        aw = wn.get("award") or {}
        if wn.get("status") == "added":
            act("monica", f"congrats-{wn['id']}", f"(list only) Congratulations + 'we added "
                f"{ai_answers.award_label(aw)} to your site'",
                "Share, not an ask. Not auto-filed (Monica notes are filed only for live "
                "voting windows); send via scripts/monica_oneoff.py when approved.")
        elif wn.get("status") == "candidate":
            act("human", f"confirm-{wn['id']}", f"Confirm possible award page: {wn.get('title')}",
                f"{wn.get('url')} . If it is a real award naming the client: "
                f"awards.py confirm-won --slug {slug} --id {wn['id']} --apply")
    pstat("businessrate", "display_only" if any(
        (w.get("award") or {}).get("organizer") == "BusinessRate" for w in rec.get("won") or [])
        else "n/a", "never pay")
    return rec, acts


def print_plan(slug: str, rec: dict, acts: list[dict]) -> None:
    print(f"\n=== AWARDS PLAN: {slug} ===")
    print("programs: " + "; ".join(f"{k}={v.get('status')}" for k, v in
                                   (rec.get("programs") or {}).items()))
    for lane, label in (("mini", "MINI (browser agent)"), ("monica", "MONICA"),
                        ("human", "SANTINO / HUMAN"), ("auto", "AUTOMATIC (no action)")):
        rows = [a for a in acts if a["lane"] == lane]
        if not rows:
            continue
        print(f"\n[{label}]")
        for a in rows:
            flag = " (FILE [FOR MONICA]: live voting window)" if a.get("file") else ""
            print(f"  - {a['title']}{flag}\n      {a['detail']}")


def queue(slug: str, rec: dict, acts: list[dict], apply: bool) -> None:
    cid = company_id(slug)
    body = INBOX.read_text() if INBOX.exists() else "# Mini inbox\n\n"
    blocks = []
    for a in (x for x in acts if x["lane"] == "mini"):
        marker = f"<!-- awards:{slug}:{a['key']} -->"
        if marker in body:
            print(f"  inbox: already queued {a['key']}")
            continue
        blocks.append(f"- [ ] **AWARDS — {slug}: {a['title']} (from awards.py, "
                      f"{TODAY.isoformat()}; daytime, unsupervised OK for form submits):** "
                      f"{a['detail']} {GUARDRAILS.format(slug=slug)} Afterwards: check this "
                      f"off with the result line; if the program shows a public URL naming "
                      f"the client, put it in the report so the MacBook runs "
                      f"awards.py discover-won. {marker}\n")
        rec.setdefault("queued", {})[a["key"]] = _now()
    if blocks:
        head, sep, rest = body.partition("\n\n")
        new = head + sep + "".join(b + "\n" for b in blocks) + rest if sep else body + "\n" + "".join(blocks)
        if apply:
            INBOX.write_text(new)
        print(f"  inbox: {'appended' if apply else 'would append'} {len(blocks)} AWARDS task(s)")
    for a in (x for x in acts if x["lane"] == "monica" and x.get("file")):
        m = re.search(r"AWARDS-VOTE-[\w-]+", a["note_body"])
        marker = m.group(0) if m else a["key"]
        try:
            dup = cos._sb("GET", f"/rest/v1/marketing_ops_notes?company_id=eq.{cid}"
                          f"&body=like.*{marker}*&select=id&limit=1",
                          prefer="return=representation")
        except Exception:  # noqa: BLE001
            dup = None
        if dup:
            print(f"  monica: {marker} already filed")
            continue
        if not apply:
            print(f"  monica: would file {marker}")
            continue
        cos._sb("POST", "/rest/v1/marketing_ops_notes",
                {"company_id": cid, "body": a["note_body"], "author": "awards", "status": "open"})
        for c in rec.get("contests") or []:
            if c["id"] in marker:
                c["voting_rally_filed"] = _now()
        print(f"  monica: filed {marker}")


def cmd_plan(slug: str, apply: bool, do_queue: bool) -> None:
    rec, acts = build_plan(slug)
    print_plan(slug, rec, acts)
    if do_queue:
        queue(slug, rec, acts, apply)
    cid = company_id(slug)
    if cid and apply:
        rec["last_plan"] = {"at": _now(), "actions": len(acts)}
        save_record(cid, rec, True)


def cmd_confirm_won(slug: str, wid: str, apply: bool, name: str | None) -> None:
    cid = company_id(slug)
    rec = load_record(slug, cid)
    wn = next((w for w in rec["won"] if w.get("id") == wid), None)
    if not wn:
        sys.exit(f"no won entry {wid} for {slug}")
    aw = wn.get("award") or {}
    if name:
        aw = {**aw, "name": name}
    if not aw.get("name"):
        sys.exit("candidate has no parsed award name: pass --name 'exact award text from the page'")
    aw.setdefault("url", wn.get("url"))
    if CATALOG.get(wn.get("program") or "", {}).get("never_pay"):
        aw["site_link"] = False
    print(f"confirm: {ai_answers.award_label(aw)} <- {wn.get('url')}")
    if apply:
        add_award_via_ai_answers(slug, aw)
        wn.update({"award": aw, "verified": True, "status": "added", "added_at": _now(),
                   "confirmed_by": "human"})
    save_record(cid, rec, apply)


def cmd_applied(slug: str, program: str, apply: bool, note: str | None) -> None:
    """Record a REAL award submission (Mini or human) and put it in the
    client's Reports tab (2026-09-29, every client action logs)."""
    cid = company_id(slug)
    if not cid:
        sys.exit(f"{slug}: no company_id")
    prog = CATALOG.get(program)
    rec = load_record(slug, cid)
    contest = next((c for c in rec.get("contests") or [] if c.get("id") == program), None)
    name = (prog or {}).get("name") or (contest or {}).get("title") or program
    if not (prog or contest):
        sys.exit(f"unknown program/contest {program!r} (catalog keys: {', '.join(CATALOG)})")
    print(f"{slug}: applied -> {name}")
    if not apply:
        print("  [dry-run] re-run with --apply to record it")
        return
    if prog:
        progs = rec.setdefault("programs", {})
        progs[program] = {**progs.get(program, {}), "status": "applied",
                          "applied_at": _now(), **({"notes": note} if note else {})}
    else:
        contest.update({"status": "entered", "entered": True, "nominated_at": _now()})
    save_record(cid, rec, True)
    try:
        from work_log import work_log
        work_log(cid, "citations", "award-applied",
                 f"Entered your business for the {name} award. Wins get featured "
                 "on your website and are cited by Google and AI assistants.",
                 evidence={"program": program, "note": note}, source="awards.py applied")
    except Exception as e:  # noqa: BLE001 — logging never blocks the record
        print(f"  [work-log] warn: {str(e)[:100]}")


# ============================================================== main
def active_slugs() -> list[str]:
    try:
        rows = cos._sb("GET", "/rest/v1/companies?status=ilike.active&select=id",
                       prefer="return=representation") or []
        sm = cos.slug_map()
        out = sorted({sm[r["id"]] for r in rows if r["id"] in sm})
    except Exception as e:  # noqa: BLE001
        print(f"[warn] companies read failed ({str(e)[:80]}); using local client records")
        out = []
        for p in CLIENTS.glob("*.json"):
            try:
                if json.loads(p.read_text()).get("status") in ("active", "live"):
                    out.append(p.stem)
            except (OSError, json.JSONDecodeError, AttributeError):
                pass
    return [s for s in sorted(out) if s not in DEAD and (CLIENTS / s / "plan-input.json").exists()]


def print_catalog() -> None:
    print(f"{'key':16} {'type':18} {'lane':7} {'verified':8} cost")
    for k, p in CATALOG.items():
        print(f"{k:16} {p['type']:18} {p['lane']:7} {str(p['verified']):8} {p['cost']}")
        print(f"{'':16} {p.get('apply_url') or p.get('url') or '(per market)'}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("cmd", choices=["catalog", "discover-polls", "discover-won", "plan",
                                    "confirm-won", "applied"])
    ap.add_argument("--slug")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--apply", action="store_true", help="write ops_kv / site / inbox / notes")
    ap.add_argument("--queue", action="store_true", help="plan: Mini inbox + live-window Monica")
    ap.add_argument("--id", help="confirm-won: won entry id")
    ap.add_argument("--name", help="confirm-won: exact award name if not parsed")
    ap.add_argument("--program", help="applied: catalog key (qba, ...) or contest id")
    ap.add_argument("--note", help="applied: what was submitted (optional)")
    a = ap.parse_args()
    if a.cmd == "catalog":
        print_catalog()
        return 0
    if a.cmd == "applied":
        if not (a.slug and a.program):
            ap.error("applied needs --slug and --program")
        cmd_applied(a.slug, a.program, a.apply, a.note)
        return 0
    if a.cmd == "confirm-won":
        if not (a.slug and a.id):
            ap.error("confirm-won needs --slug and --id")
        cmd_confirm_won(a.slug, a.id, a.apply, a.name)
        return 0
    slugs = [a.slug] if a.slug else active_slugs() if a.all else []
    if not slugs:
        ap.error("--slug or --all")
    if a.slug in DEAD:
        print(f"{a.slug} is a dead client; skipped")
        return 0
    dfs = None
    failures = 0
    for s in slugs:
        try:
            if a.cmd in ("discover-polls", "discover-won"):
                dfs = dfs or DFS()
                dfs.cost = 0.0  # the ~$0.05 cap is per client per command
                (discover_polls if a.cmd == "discover-polls" else discover_won)(s, a.apply, dfs)
            else:
                cmd_plan(s, a.apply, a.queue)
        except Exception as e:  # noqa: BLE001 — per-client fail-open
            failures += 1
            print(f"{s}: FAILED ({type(e).__name__}: {str(e)[:160]})")
    return 1 if failures and failures == len(slugs) else 0


if __name__ == "__main__":
    sys.exit(main())
