#!/usr/bin/env python3
"""Deterministic call -> client matching for fathom_sync (2026-09-29).

WHY THIS EXISTS. fathom_sync used to hand a recording to the model with a
roster built ONLY from clients/company_map.json and mark anything it could
not place as "unmatched" forever. Two real losses followed:
  - Katofsky (09-20, recording 184795857): the onboarding call was mined
    minutes after the companies row was created and before bootstrap minted
    a slug, so the client was not on the roster. Lost.
  - RestoPros (09-24, 186419597 + 186576701): the bootstrap job timed out on
    them every 2 hours, so the slug never reached company_map. Both calls
    were read as a sales prospect / pipeline alert. Lost.

The roster now comes from the DATABASE (companies + marketing_sites slugs,
company_map still wins for the slug), so a client exists for matching the
moment its companies row exists, slug or not. Before any model call, hard
evidence is checked:
  1. external calendar-invitee emails vs company / contact emails
  2. the GHL appointment the recording sat on (contact id, email, phone)
  3. the title ("Daniel Restum - Kick Off Call", "RT Olson X BDA ...")
  4. transcript speaker names vs the client's contacts / owner
One unambiguous strong hit wins; anything weaker falls through to the model,
which now sees every roster client (keyed by slug, or by company id when no
slug exists yet).

Sales-pipeline titles ("20 Jobs In 90 Days Guarantee ...") are NOT client
calls; they stay on the prospect lane exactly as before.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUR_DOMAINS = ("restorationai.io", "getrestorationai.com", "ignitesystems",
               "bdadigital.us")
OUR_PEOPLE = ("santino", "levi", "monica", "melia")
SALES_TITLE_RE = re.compile(
    r"20 Jobs In 90 Days|Rank #1 On Google|Guarantee with Restoration AI|"
    r"Strategy Call", re.I)
CLIENT_TITLE_RE = re.compile(
    r"^\s*(?P<name>.+?)\s+-\s+(?:Kick ?Off Call|LIVE Support Call|"
    r"LIVE Follow-?Up Call|Support Call|Follow-?Up Call)", re.I)
_LEGAL_RE = re.compile(r"\b(inc|llc|corp|co|company|services?|the|of|and)\b\.?")


def _norm(s) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", str(s or "").lower())).strip()


def _digits10(p) -> str:
    d = re.sub(r"\D", "", str(p or ""))
    return d[-10:] if len(d) >= 10 else ""


def is_ours(name_or_email: str) -> bool:
    v = str(name_or_email or "").lower()
    return (any(d in v for d in OUR_DOMAINS)
            or any(v.split(" ")[0] == p for p in OUR_PEOPLE))


def is_sales_title(title: str) -> bool:
    return bool(SALES_TITLE_RE.search(title or ""))


def load_roster(sb) -> list[dict]:
    """Every client a call can belong to: [{company, cid, slug, key, plan}].

    slug: company_map.json first (the repo identity), else the
    marketing_sites.rank_ai_slug the bootstrap backstop minted in the DB
    (that row exists within hours of signup even when the repo half has not
    been committed yet). key = slug or company id. Paused/cancelled/
    suspended accounts are left out (dead clients take no new work).
    """
    cmap = json.loads((ROOT / "clients" / "company_map.json").read_text())
    slug_by_cid = {}
    try:
        for r in sb("GET", "/rest/v1/marketing_sites?select=company_id,"
                    "rank_ai_slug") or []:
            if r.get("rank_ai_slug") and r.get("company_id"):
                slug_by_cid.setdefault(r["company_id"], r["rank_ai_slug"])
    except Exception:  # noqa: BLE001 — the repo map still works alone
        pass
    for slug, cid in cmap.items():
        slug_by_cid[cid] = slug                       # company_map wins
    rows = sb("GET", "/rest/v1/companies?select=id,name,timezone,phone,email,"
              "account_owner_name,status,plan,created_at,"
              "integration_settings") or []
    out = []
    for co in rows:
        st = str(co.get("status") or "").strip().lower()
        if st in ("paused", "cancelled", "canceled", "churned", "inactive",
                  "archived", "suspended"):
            continue
        name = str(co.get("name") or "")
        if re.search(r"\btest\b|trachawk|xyz restoration", name.lower()):
            continue
        slug = slug_by_cid.get(co["id"])
        # receptionist-plan accounts stay in the roster for MATCHING only:
        # their calls are recognised (not carded as lost) but fathom_sync
        # does not mine them (see is_minable)
        out.append({"company": co, "cid": co["id"], "slug": slug,
                    "key": slug or co["id"], "plan": co.get("plan")})
    return drop_signup_stubs(out)


def is_signup_stub(co: dict, siblings: list[dict]) -> bool:
    """SIGNUP STUBS (Daniel Restum 2026-09-23): the sales signup can mint a
    PERSON-named companies row that shares the owner's email with the real
    company row ("Daniel Restum" vs "RestoPros of Central Maryland"; the
    stub even got its own marketing_sites slug). A row is a stub when a
    sibling with the same email lists a contact whose full name IS this
    row's name, or when it has no contacts and a sibling does."""
    name = _norm(co.get("name"))
    for sib in siblings:
        if sib.get("id") == co.get("id"):
            continue
        for c in _contacts(sib):
            full = _norm(f"{c.get('first_name', '')} {c.get('last_name', '')}")
            if full and full == name:
                return True
        if _contacts(sib) and not _contacts(co) and len(name.split()) <= 3 \
                and not re.search(r"restor|construct|plumb|clean|llc|inc",
                                  name):
            return True
    return False


def drop_signup_stubs(entries: list[dict]) -> list[dict]:
    by_email: dict[str, list[dict]] = {}
    for e in entries:
        em = str(e["company"].get("email") or "").strip().lower()
        if em:
            by_email.setdefault(em, []).append(e["company"])
    return [e for e in entries
            if not is_signup_stub(e["company"], by_email.get(
                str(e["company"].get("email") or "").strip().lower(), []))]


def is_minable(entry: dict) -> bool:
    """A matched call is mined (intel, cards, promises) for Rank AI clients
    and anything already carrying a pipeline slug."""
    return bool(entry.get("slug")) or entry.get("plan") == "Rank AI"


def roster_hash(roster: list[dict]) -> str:
    return hashlib.sha256("|".join(sorted(
        f"{e['cid']}:{e['key']}" for e in roster)).encode()).hexdigest()[:12]


def _contacts(co: dict) -> list[dict]:
    ints = co.get("integration_settings") or {}
    if isinstance(ints, str):
        try:
            ints = json.loads(ints)
        except ValueError:
            ints = {}
    return [c for c in (ints.get("contacts") or []) if isinstance(c, dict)]


def _index(roster: list[dict]) -> dict:
    idx = {"email": {}, "phone": {}, "ghl": {}, "full": {}, "first": {},
           "company": {}}

    def add(kind, k, cid):
        # our own people sit on some rows (demo/test accounts list Santino
        # as the owner contact) and must never make a call "theirs"
        if k and not (kind in ("full", "first", "email") and is_ours(k)):
            idx[kind].setdefault(k, set()).add(cid)
    for e in roster:
        co, cid = e["company"], e["cid"]
        add("email", str(co.get("email") or "").strip().lower(), cid)
        add("phone", _digits10(co.get("phone")), cid)
        ints = co.get("integration_settings") or {}
        if isinstance(ints, dict):
            add("ghl", ints.get("ghl_contact_id"), cid)
        owner = _norm(co.get("account_owner_name"))
        if len(owner.split()) >= 2:
            add("full", owner, cid)
        for c in _contacts(co):
            add("email", str(c.get("email") or "").strip().lower(), cid)
            add("phone", _digits10(c.get("cell")), cid)
            add("phone", _digits10(c.get("phone")), cid)
            add("ghl", c.get("ghl_contact_id"), cid)
            first, last = _norm(c.get("first_name")), _norm(c.get("last_name"))
            if first and last:
                add("full", f"{first} {last}", cid)
            if first:
                add("first", first.split()[0], cid)
        core = _LEGAL_RE.sub(" ", _norm(co.get("name")))
        core = re.sub(r"\s+", " ", core).strip()
        if len(core) >= 5:
            add("company", core, cid)
    return idx


def _people_hits(idx: dict, names: list[str]) -> tuple[set, set]:
    """(strong cids from full names, weak cids from a unique first name)."""
    strong, weak = set(), set()
    for raw in names:
        n = _norm(raw)
        if not n or is_ours(n):
            continue
        if n in idx["full"]:
            strong |= idx["full"][n]
            continue
        parts = n.split()
        # "Daniel restum" / "Dan Restum": first token may be a nickname,
        # so also try any full name sharing the LAST name + first initial
        if len(parts) >= 2:
            for full, cids in idx["full"].items():
                fp = full.split()
                if fp[-1] == parts[-1] and fp[0][:1] == parts[0][:1]:
                    strong |= cids
        if parts and parts[0] in idx["first"] and len(idx["first"][parts[0]]) == 1:
            weak |= idx["first"][parts[0]]
    return strong, weak


def match_meeting(m: dict, roster: list[dict], *, speakers: list[str] | None = None,
                  anchor_contact: dict | None = None) -> tuple[dict | None, str]:
    """(roster entry, why) or (None, why). Pure: every network lookup is
    done by the caller (speakers from the transcript, the GHL contact behind
    the appointment anchor) so this is cheap to re-run on every retry."""
    title = m.get("title") or m.get("meeting_title") or ""
    if is_sales_title(title):
        return None, "sales-pipeline title (prospect lane)"
    idx = _index(roster)
    by_cid = {e["cid"]: e for e in roster}
    evidence: dict[str, list[str]] = {}

    def hit(cids, why):
        for c in cids:
            evidence.setdefault(c, []).append(why)

    # 1. invitee emails
    for i in (m.get("calendar_invitees") or []):
        em = str((i.get("email") if isinstance(i, dict) else i) or "").lower()
        if em and not is_ours(em) and em in idx["email"]:
            hit(idx["email"][em], f"invitee {em}")
    # 2. the booked appointment's GHL contact
    if anchor_contact:
        gid = anchor_contact.get("id")
        if gid in idx["ghl"]:
            hit(idx["ghl"][gid], "appointment contact id")
        em = str(anchor_contact.get("email") or "").lower()
        if em in idx["email"]:
            hit(idx["email"][em], f"appointment contact {em}")
        ph = _digits10(anchor_contact.get("phone"))
        if ph and ph in idx["phone"]:
            hit(idx["phone"][ph], "appointment contact phone")
    # 3. title
    tm = CLIENT_TITLE_RE.match(title)
    title_people = [tm.group("name")] if tm else []
    s, w = _people_hits(idx, title_people)
    hit(s, f"title names {title_people[0]!r}" if title_people else "title")
    weak_title = w
    nt = _norm(title)
    for core, cids in idx["company"].items():
        if core and re.search(rf"\b{re.escape(core)}\b", nt):
            hit(cids, f"title names the company ({core})")
    # 4. transcript speakers
    s2, w2 = _people_hits(idx, speakers or [])
    hit(s2, "speaker on the call")
    # A call recorded BEFORE the client's companies row existed was a sales
    # conversation, not client work (RestoPros 09-23: Levi's post-demo call
    # the day before signup). 30 minutes of grace: signup and the onboarding
    # call can start together (Katofsky 09-20: row 18:49, call 18:53).
    start = str(m.get("recording_start_time") or m.get("created_at") or "")
    for cid in list(evidence):
        created = str(by_cid[cid]["company"].get("created_at") or "")
        if start and created and _ts(start) is not None and _ts(created) is not None \
                and _ts(start) < _ts(created) - 1800:
            evidence.pop(cid)
    if len(evidence) == 1:
        cid = next(iter(evidence))
        return by_cid[cid], "; ".join(evidence[cid])
    if len(evidence) > 1:
        # several clients named: the one with the most independent evidence
        ranked = sorted(evidence.items(), key=lambda kv: -len(set(kv[1])))
        if len(set(ranked[0][1])) > len(set(ranked[1][1])):
            return by_cid[ranked[0][0]], "; ".join(ranked[0][1])
        return None, "ambiguous: " + ", ".join(
            by_cid[c]["key"] for c in evidence)
    weak = {c for c in (weak_title | w2)
            if not signed_up_after(by_cid[c], m)}
    if len(weak) == 1:
        cid = next(iter(weak))
        return by_cid[cid], "unique first name (title/speaker)"
    return None, "no hard evidence"


def _ts(v: str) -> float | None:
    from datetime import datetime, timezone
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00").replace(" ", "T"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.timestamp()
    except ValueError:
        return None


def signed_up_after(entry: dict, m: dict) -> bool:
    """True when the call predates the client's row by > 30 min."""
    s = _ts(m.get("recording_start_time") or m.get("created_at") or "")
    c = _ts(entry["company"].get("created_at") or "")
    return bool(s and c and s < c - 1800)


def roster_text(roster: list[dict]) -> str:
    """Roster lines for the model fallback (key = slug, or company id)."""
    lines = []
    for e in roster:
        co = e["company"]
        people = "; ".join(
            f"{c.get('first_name', '')} {c.get('last_name', '')}".strip()
            + (f" <{c.get('email')}>" if c.get("email") else "")
            for c in _contacts(co)
            if (c.get("first_name") or c.get("email"))
            and not is_ours(f"{c.get('first_name', '')} {c.get('email', '')}"))
        owner = str(co.get("account_owner_name") or "")
        if is_ours(owner):
            owner = ""
        lines.append(f"- key={e['key']}  company=\"{co.get('name')}\"  "
                     f"owner=\"{owner}\"  "
                     f"people=\"{people}\"")
    return "\n".join(lines)
