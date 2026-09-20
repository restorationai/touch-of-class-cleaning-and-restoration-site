#!/usr/bin/env python3
"""Setup ledger — the overseer (Santino 2026-07-28: "no client should ever get
left behind"). For every ACTIVE client on the Rank AI plan (other plans are
deliberately ignored), derive the setup state from the systems themselves —
never from someone having marked a box — and route every gap:

  us_owed      -> Santino's attention list (nightly ops email + app
                  SuperadminDashboard reads marketing_setup_ledger)
  client_owed  -> Monica already owns these via the checklist/ask passes;
                  the ledger just aggregates counts for the app + the
                  escalation ladder
  auto         -> the ledger FIXES it itself (GSC registration + IndexNow
                  for live sites)

Items:
  site-built      preview site exists in sites/{slug} (CRITICAL when the
                  kickoff call is within 3 days or already past)
  site-live       the client's real domain serves our site; if WE control
                  the zone and the site is built but not live, the detail
                  says LAUNCH NOW (own-domain policy, PuroClean 2026-07-28)
  domain-access   built + domain known + zone not ours + not live ->
                  client-owed registrar-access ask
  gsc-indexnow    live site registered in Search Console + IndexNow-pinged
                  (auto-heals: runs gsc_register + indexnow once, marks done)
  google-connected  reflects user_integrations state (ask pass owns nudges)
  client-asks     open client_input count + no-reply streak (ladder input)
  citations-blocked creation-queue readiness (Santino 2026-08-03): missing
                  logo / empty companies NAP auto-heals from the branding
                  bucket / GBP first; what no system holds becomes a Monica
                  ask + this amber client_owed card
  map-rankings    the geo-grid actually populates (Santino 2026-08-04): auto-
                  heals business identity + city-ring config + cron roster; the
                  only cards left are real decisions — no GBP location selected,
                  no service areas planned, or a scan that genuinely found the
                  listing at 0 of N points
  video-channel   YouTube connected but the Google account owns no channel, so
                  nothing can be published (verified live against the API)

Run:  python3 scripts/setup_ledger.py [--dry-run]
Wired into client_ops_sync's nightly pass via ensure_ledger().
"""
from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CLIENTS_DIR = ROOT / "clients"
SITES_DIR = ROOT / "sites"
sys.path.insert(0, str(ROOT / "scripts"))

from client_ops_sync import (  # noqa: E402
    DOMAIN_ACCESS_ASK_GENERIC, DOMAIN_ACCESS_ASK_GODADDY,
    DOMAIN_ACCESS_INVITE_EMAIL, DOMAIN_ACCESS_TRUTH, _sb, slug_map)



def _site_unfinished_bits(slug: str) -> list[str]:
    """Cheap finishing-pass check shared by the site-finished ledger item and
    the preview reveal gate: images on disk, real palette, no pages still
    dripping. (2026-09-04: with the nightly render drip, day 7 can arrive
    before the long tail has rendered — the reveal must wait for BOTH.)"""
    bits = []
    if not (SITES_DIR / slug / "public" / "images" / "hero-bg.webp").exists():
        bits.append("images")
    try:
        _pi = json.loads((CLIENTS_DIR / slug / "plan-input.json").read_text())
        _pb = _pi.get("brand") or {}
        if not (_pb.get("primary_color") or (_pb.get("colors") or {}).get("primary")):
            bits.append("brand colors")
    except (OSError, json.JSONDecodeError):
        pass
    pend = 0
    base = SITES_DIR / slug / "src" / "content"
    if base.is_dir():
        for _md in base.rglob("*.md"):
            try:
                _raw = _md.read_text(errors="ignore")
            except OSError:
                continue
            _fm = _raw[:_raw.find("\n---", 3) + 4] if _raw.startswith("---") else _raw
            if not re.search(r"^rendered:\s*true\b", _fm, re.M):
                pend += 1
    if pend:
        bits.append(f"{pend} page(s) still rendering")
    return bits

def _norm_domain(d: str | None) -> str:
    d = (d or "").strip().lower()
    d = re.sub(r"^https?://", "", d).strip("/ ")
    return d[4:] if d.startswith("www.") else d


def _client_record(slug: str) -> dict:
    p = CLIENTS_DIR / f"{slug}.json"
    try:
        return json.loads(p.read_text()) if p.exists() else {}
    except json.JSONDecodeError:
        return {}


def _our_zones() -> dict[str, str]:
    """{domain: zone_status} for zones on our Cloudflare account. status
    'active' = NS actually point at us (launchable); 'pending' = zone created
    but the registrar cutover hasn't happened (crew3r 2026-07-28)."""
    tok = os.environ.get("CLOUDFLARE_API_TOKEN")
    if not tok:
        return {}
    out: dict[str, str] = {}
    page = 1
    try:
        while True:
            r = requests.get("https://api.cloudflare.com/client/v4/zones",
                             headers={"Authorization": f"Bearer {tok}"},
                             params={"per_page": 50, "page": page}, timeout=30)
            body = r.json()
            for z in body.get("result") or []:
                out[z["name"].lower()] = z.get("status") or "?"
            if page >= (body.get("result_info") or {}).get("total_pages", 1):
                break
            page += 1
    except Exception:
        pass
    return out


# ---- domain-access state machine (Santino 2026-08-03) ----------------------
# none -> promised -> delegate_granted | creds_provided -> ns_live
# State lives on marketing_sites (domain_access_status + registrar/email/
# timestamps). Writers: the app's Site tab "Provide Domain Access" card sets
# promised (client claim) and creds_provided (encrypted creds via the
# domain-access edge fn); THIS ledger sets delegate_granted (executing the
# Ops Attention "Delegate access confirmed" click, marketing_ops_notes
# pattern like APPROVE-PHONE-SWAP) and ns_live (the existing Cloudflare
# zone check — zone active == NS point at us).
_DA_STATES = ("none", "promised", "delegate_granted", "creds_provided", "ns_live")

# NS-suffix -> registrar guess, precomputed here (not an edge fn) so the app
# dropdown can pre-select without a live lookup. Suffix match on `dig NS`.
_REGISTRAR_NS = {
    "domaincontrol.com": "godaddy",
    "registrar-servers.com": "namecheap",
    "ionos.com": "ionos", "ionos.de": "ionos", "ui-dns.com": "ionos",
    "ui-dns.de": "ionos", "ui-dns.org": "ionos", "ui-dns.biz": "ionos",
    "bluehost.com": "bluehost",
    "hostgator.com": "hostgator", "websitewelcome.com": "hostgator",
    "squarespacedns.com": "squarespace", "googledomains.com": "squarespace",
    "wixdns.net": "wix",
    "cloudflare.com": "cloudflare",
    "worldnic.com": "networksolutions", "register.com": "networksolutions",
    "name-services.com": "enom", "enom.com": "enom",
    "hover.com": "hover",
    "dreamhost.com": "dreamhost",
    "wordpress.com": "wordpress",
    "dns-parking.com": "hostinger", "hostinger.com": "hostinger",
    "inmotionhosting.com": "inmotion",
    # observed in our own client fleet (2026-08-03 backfill)
    "monikerdns.net": "moniker",              # prorestorationca.com
    "hostmonster.com": "bluehost",            # QCI — HostMonster = Bluehost family,
                                              # matches portal-creds "bluehost:{slug}"
}


def _registrar_guess(domain: str) -> str | None:
    """Guess the registrar from the domain's live NS records (dig)."""
    try:
        out = subprocess.run(["dig", "+short", "NS", domain],
                             capture_output=True, text=True, timeout=20).stdout
    except Exception:
        return None
    for line in out.splitlines():
        ns = line.strip().rstrip(".").lower()
        if ".awsdns-" in ns:   # Route53 suffixes vary by TLD (.com/.net/.co.uk)
            return "route53"
        for suffix, reg in _REGISTRAR_NS.items():
            if ns.endswith(suffix):
                return reg
    return None


def _domain_access_row(cid: str) -> dict | None:
    """The marketing_sites domain-access columns for this company (or None
    when no marketing_sites row exists yet — nothing to track)."""
    try:
        rows = _sb("GET", f"/rest/v1/marketing_sites?company_id=eq.{cid}"
                   "&select=id,domain_access_status,domain_registrar,"
                   "domain_registrar_guess,domain_account_email,"
                   "domain_access_domain,domain_access_promised_at,"
                   "domain_access_granted_at,domain_ns_live_at&limit=1",
                   prefer="return=representation") or []
        return rows[0] if rows else None
    except Exception:
        return None


# ---- delegate-access VERIFICATION (Santino 2026-08-05) --------------------
# The old "Delegate access confirmed ✓ (invite landed at setup@)" button
# asserted a fact about an inbox nobody had checked — Crew Restoration went
# green on an invite that never existed, and Monica stopped asking the one
# person who could unblock the launch. Now a human click is recorded as
# exactly what it is (a human assertion) and the mailbox is the evidence.
#
#   registrar_email   a real registrar invitation is in the agency mailbox
#   client_creds      the client handed over credentials (no email expected)
#   ns_truth          the nameservers already point at us — nothing to prove
#   human_pending     a human clicked less than GRACE hours ago; still looking
#   human_unverified  a human clicked, the mailbox reads fine, NO invite exists
#   human_unchecked   a human clicked but the mailbox could not be read
# human_unverified is the honest-mismatch state: the card goes red, the
# attention list says so, access is NOT treated as in hand, and the state
# column is rolled back to what it was before the click (so the CLIENT-facing
# "Provide Domain Access" card stops claiming we hold something we don't).
# The grace is short on purpose: the button means "the invite already
# arrived", and a registrar invitation lands in the mailbox within seconds.
_ASSERT_GRACE_HOURS = 1


def _scan_registrar_invites(cos: list[dict], cid_to_slug: dict):
    """(cid -> [invite...], scan_ok, error, ambiguous). Never raises."""
    try:
        import domain_access_email as dae
        sites = _sb("GET", "/rest/v1/marketing_sites?select=company_id,domain,"
                    "domain_registrar,domain_registrar_guess",
                    prefer="return=representation") or []
        return dae.invites_by_company(cos, cid_to_slug, {
            s["company_id"]: {"domain": s.get("domain"),
                              "registrar": s.get("domain_registrar"),
                              "registrar_guess": s.get("domain_registrar_guess")}
            for s in sites})
    except Exception as e:  # noqa: BLE001 — a mailbox hiccup never kills the ledger
        return {}, False, f"invite scan failed: {str(e)[:140]}", []


def _manual_assertion(cid: str) -> dict | None:
    """The newest human 'I confirmed access manually' click, whatever its
    note status (the executor resolves the note; the assertion is still a
    fact we have to keep honest about)."""
    try:
        rows = _sb("GET", "/rest/v1/marketing_ops_notes"
                   f"?company_id=eq.{cid}"
                   "&body=like.*%5BDELEGATE-ACCESS-CONFIRMED%5D*"
                   "&select=id,body,author,created_at,status"
                   "&order=created_at.desc&limit=1",
                   prefer="return=representation") or []
        return rows[0] if rows else None
    except Exception:  # noqa: BLE001
        return None


def _hours_since(iso: str | None) -> float:
    try:
        return (datetime.now(timezone.utc) - datetime.fromisoformat(
            str(iso).replace("Z", "+00:00"))).total_seconds() / 3600.0
    except (ValueError, TypeError, AttributeError):
        return 0.0


def _delegate_verification(cid: str, da_status: str, invites: list[dict],
                           scan_ok: bool) -> dict:
    """How do we actually know this client's access claim is true?"""
    inv = (invites or [None])[0]
    if da_status == "ns_live":
        return {"state": "ns_truth", "invite": None, "assertion": None}
    if inv:
        return {"state": "registrar_email",
                "invite": {k: inv.get(k) for k in
                           ("registrar", "inviter", "date", "subject", "to",
                            "gmail_url", "customer_number")}
                | {"why": (inv.get("match") or {}).get("why")},
                "assertion": None}
    if da_status == "creds_provided":
        return {"state": "client_creds", "invite": None, "assertion": None}
    note = _manual_assertion(cid)
    if not note:
        return {"state": None, "invite": None, "assertion": None}
    rec = {"at": note.get("created_at"), "by": note.get("author") or "an operator",
           "hours": round(_hours_since(note.get("created_at")), 1)}
    if not scan_ok:
        return {"state": "human_unchecked", "invite": None, "assertion": rec}
    if rec["hours"] < _ASSERT_GRACE_HOURS:
        return {"state": "human_pending", "invite": None, "assertion": rec}
    return {"state": "human_unverified", "invite": None, "assertion": rec}


def _verification_line(v: dict) -> str:
    """One sentence naming the evidence (or the lack of it)."""
    st, inv, a = v.get("state"), v.get("invite") or {}, v.get("assertion") or {}
    if st == "registrar_email":
        return (f"VERIFIED: a {inv.get('registrar', 'registrar')} access invite "
                f"from {inv.get('inviter') or 'the owner'} landed at "
                f"{inv.get('to') or DOMAIN_ACCESS_INVITE_EMAIL} on "
                f"{str(inv.get('date') or '')[:10]}.")
    if st == "client_creds":
        return "VERIFIED: the client submitted their login through the encrypted form."
    if st == "human_pending":
        return (f"{a.get('by')} marked this confirmed by hand "
                f"{a.get('hours')}h ago — we are still looking for the matching "
                "invite in the agency inbox.")
    if st == "human_unchecked":
        return (f"{a.get('by')} marked this confirmed by hand — the agency "
                "inbox could NOT be read this run, so nothing is verified.")
    if st == "human_unverified":
        return (f"NOT VERIFIED: {a.get('by')} marked this confirmed by hand "
                f"{a.get('hours')}h ago, but no registrar access invite for "
                "this client has EVER arrived at "
                f"{DOMAIN_ACCESS_INVITE_EMAIL}. Treat access as not in hand.")
    return ""


_REGISTRAR_LABEL = {
    "godaddy": "GoDaddy", "namecheap": "Namecheap", "bluehost": "Bluehost",
    "hostgator": "HostGator", "squarespace": "Squarespace", "wix": "Wix",
    "networksolutions": "Network Solutions", "name.com": "Name.com",
    "enom": "eNom", "hover": "Hover", "dreamhost": "DreamHost",
    "ionos": "IONOS", "hostinger": "Hostinger", "porkbun": "Porkbun",
    "moniker": "Moniker", "inmotion": "InMotion", "cloudflare": "Cloudflare",
    "wordpress": "WordPress.com", "route53": "AWS Route 53",
    "domain.com": "Domain.com", "web.com": "Web.com", "shopify": "Shopify",
}


def _launch_card(owner: str, domain: str, built: bool, live: bool,
                 ours: bool, zstat: str, da_status: str, da: dict,
                 v: dict) -> tuple[str, str, str, str | None]:
    """THE one domain/launch card (kind, status, title, detail).

    Before 2026-08-05 this same story rendered as THREE separate items —
    "Registrar / domain access", "Live on real domain", and a duplicate
    "domain access" ask inside Waiting-on-N. One card now tells the whole
    truth and its text changes by state: needs access -> we have access,
    cutover pending -> live.
    """
    reg = da.get("domain_registrar") or da.get("domain_registrar_guess")
    reg_txt = (f" (looks like {_REGISTRAR_LABEL.get(reg, reg.title())})"
               if reg else "")
    evidence = _verification_line(v)
    if live:
        return ("auto", "done", f"Website is live on {domain}", None)
    if not domain:
        return ("us_owed", "blocked",
                "No web address on file — decide before anything can launch",
                "Nobody has told us which web address this website should live "
                "on. Two ways forward: use one they already own (we need "
                "access to it), or we buy one for them and launch the same day.")
    if not built:
        return ("us_owed", "blocked", f"Website not built yet — {domain} waiting",
                "Nothing to launch until the site is built.")
    if ours:
        return ("us_owed", "open",
                f"Ready to launch: flip {domain} to the new site — our job, today",
                f"{domain} already points at us, so nothing is blocking the "
                "launch. Push the site to production and it is live.")
    in_hand = da_status in ("delegate_granted", "creds_provided") \
        and v.get("state") not in ("human_unverified",)
    if in_hand:
        how = ("their login" if da_status == "creds_provided"
               else "access to their domain account")
        detail = (f"We have {how}, so nothing more is needed from {owner}. "
                  f"Our move: point {domain} at the new website (nameserver "
                  "cutover, email-safe rule applies). " + evidence)
        if da_status == "creds_provided":
            detail += (" Run scripts/domain_creds_sync.py on the ops Mac first "
                       "to decrypt the credentials into the browser agent.")
        return ("us_owed", "open",
                f"We have access to {domain} — our move: point it at the new site",
                detail)
    if v.get("state") == "human_unverified":
        return ("us_owed", "open",
                f"{domain} was marked confirmed by hand, but no invite ever arrived",
                evidence + " Either forward the invite to "
                f"{DOMAIN_ACCESS_INVITE_EMAIL} (or accept it wherever it "
                f"landed), or {owner} still has to send it. The state has been "
                "rolled back to where it was before the click, so the client's "
                "own card no longer says we have access and Monica is asking "
                "again. This stays red until real evidence shows up.")
    if v.get("state") in ("human_pending", "human_unchecked"):
        return ("us_owed", "open",
                f"{domain} marked confirmed by hand — checking the inbox",
                evidence + " If no invite turns up, this card turns red and "
                "the ask goes back to the client.")
    if da_status == "promised":
        return ("client_owed", "open",
                f"{owner} says access to {domain} was sent — nothing has arrived",
                f"We searched every registrar email ever sent to "
                f"{DOMAIN_ACCESS_INVITE_EMAIL}: no access invite for this "
                f"client{reg_txt}. Monica is on a gentle 'did it go to "
                f"{DOMAIN_ACCESS_INVITE_EMAIL}?' nudge. The moment a real "
                "invite lands, this card flips itself.")
    return ("client_owed", "open",
            f"{owner} needs to send us access to {domain} — the site is built "
            "and waiting",
            f"The website is finished; the only thing left is access to the "
            f"account where {domain} was bought{reg_txt}. We cannot get this "
            "ourselves — no domain company will hand a customer's account to "
            f"an agency. {owner} either sends an access invite to "
            f"{DOMAIN_ACCESS_INVITE_EMAIL} (GoDaddy: account.godaddy.com/access "
            "-> Invite to Access -> Domains permission) or gives us the login. "
            "Monica is asking, and the app's Site tab shows him the same card."
            + (f" {zstat.title()} zone is already staged on our Cloudflare, so "
               "the cutover takes minutes once access arrives."
               if zstat == "pending" else ""))


def _owner_first_name(co: dict) -> str:
    """The client's first name for card copy — Santino 2026-08-05: cards
    should read 'Kyle needs to create 4 listings', not 'client-owed creates'.
    Falls back to 'The client' when we genuinely do not know a human name."""
    ints = co.get("integration_settings") or {}
    if isinstance(ints, str):
        try:
            ints = json.loads(ints)
        except json.JSONDecodeError:
            ints = {}
    contacts = [c for c in (ints.get("contacts") or []) if isinstance(c, dict)]
    pick = (next((c for c in contacts if c.get("preferred")), None)
            or next((c for c in contacts if c.get("role") == "owner"), None)
            or (contacts[0] if contacts else {}))
    first = (pick.get("first_name") or "").strip()
    if not first and co.get("account_owner_name"):
        first = str(co["account_owner_name"]).split()[0]
    if not first:
        for m in co.get("management_contacts") or []:
            if isinstance(m, dict) and (m.get("name") or "").strip():
                first = str(m["name"]).split()[0]
                break
    first = re.sub(r"[^A-Za-z'-]", "", first)
    return first.capitalize() if len(first) > 1 else "The client"


def _site_serves_us(domain: str, brand_name: str, indexnow_key: str | None = None,
                    slug: str | None = None) -> bool:
    """True only when the domain serves OUR build. Brand-name matching is
    useless here — the client's OLD site obviously contains their name
    (crew3r.com false-positived) — so require our own markers.

    2026-08-31 tightened after Life Savers: their old Scorpion-hosted site
    happened to contain "/images/logo", which flipped domain-access to
    ns_live/done and silently killed the access ask for weeks. The generic
    marker is GONE. The strongest proof is the client's own IndexNow key
    file (unique per client, only our builds serve it); the /_astro/ bundle
    marker stays as fallback for older records without a key."""
    try:
        if indexnow_key:
            k = requests.get(f"https://{domain}/{indexnow_key}.txt", timeout=15,
                             headers={"User-Agent": "Mozilla/5.0 (rank-ai ledger)"})
            if k.status_code == 200 and indexnow_key in k.text:
                return True
        r = requests.get(f"https://{domain}/", timeout=20,
                         headers={"User-Agent": "Mozilla/5.0 (rank-ai ledger)"})
        if r.status_code != 200:
            return False
        # 2026-09-20 hardening (FIX Restoration): the old "/_astro/" marker
        # false-positived on fixofutah.com — the client's PREVIOUS agency
        # also builds with Astro, so the generic bundle marker stamped
        # apex_live=true on a site that still runs on their nameservers.
        # Identity, not vibes: hashed /_astro/ asset FILENAMES are unique
        # per build — require an exact filename intersection with OUR
        # deployed preview. No slug/deploy to compare against = not proven.
        if "/_astro/" not in r.text:
            return False
        if not slug:
            return False
        try:
            dep = requests.get(f"https://rankai-{slug}.pages.dev/", timeout=20,
                               headers={"User-Agent": "Mozilla/5.0 (rank-ai ledger)"})
            ours = set(re.findall(r"/_astro/[A-Za-z0-9_.-]+\.(?:css|js)", dep.text))
            theirs = set(re.findall(r"/_astro/[A-Za-z0-9_.-]+\.(?:css|js)", r.text))
            return bool(ours and (ours & theirs))
        except Exception:  # noqa: BLE001 — cannot prove identity = not live
            return False
    except Exception:
        return False


def _upcoming_kickoff(ints: dict) -> str | None:
    """ISO start time of a future kickoff appointment, else None."""
    gcid = ints.get("ghl_contact_id")
    key = os.environ.get("GHL_API_KEY")
    if not (gcid and key):
        return None
    try:
        r = requests.get(
            f"https://services.leadconnectorhq.com/contacts/{gcid}/appointments",
            headers={"Authorization": f"Bearer {key}", "Version": "2021-07-28",
                     "User-Agent": "Mozilla/5.0 (rank-ai ops)"}, timeout=20)
        for ev in r.json().get("events") or []:
            if "kickoff" not in (ev.get("title") or "").lower():
                continue
            try:
                t = datetime.strptime(ev.get("startTime", "")[:19], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
            if t > datetime.now() - timedelta(hours=12):
                return ev.get("startTime")
    except Exception:
        pass
    return None


# ---- citations-build per-platform status (Santino 2026-08-02) --------------
# The app renders the "Create listings we own" card as a checklist straight
# from evidence.platform_status (title stays untouched for backward compat):
#   live              -> checked/strikethrough (NAP audit found the listing)
#   submitted_pending -> half-state (browser agent completed the create/submit
#                        but the directory hasn't published it / the audit
#                        hasn't re-found it yet)
#   todo              -> empty checkbox
# Porch stays excluded (self-serve pro signup killed upstream, 2026-08-02).
# expertise removed 2026-08-06, same reasoning that removed Porch: a card must
# never demand work we cannot actually do. Walking the whole /review-me flow
# showed it is not a listing we create — step 4 is a Calendly booking for a
# sales call with Expertise, their editorial team decides listings on their own
# timeline, and their booking widget was broken besides. It sat on this list
# claiming work we owed 23 clients while 0 of 23 had one. Presence is still
# AUDITED (citations_audit keeps the platform), we just stop promising it.
_US_CREATE_PLATFORMS = ("bing_places", "apple_maps", "bbb",
                        "houzz", "homeguide")
_PS_LABEL = {"live": "live",
             "submitted_pending": "created — pending publish",
             "todo": "not started"}
# Expertise.com is not a listing we create, it is an APPLICATION we file.
# Expertise picks almost everyone it lists through its own editorial research
# and only accepts requests in two categories, Home Improvement being the one
# restoration sits in. Whether a client is listed is their decision on their
# timeline, so "created — pending publish" would be a claim we cannot back
# (Santino 2026-08-05, the same standard the concierge guards enforce on
# Monica's copy: never report work as done that is not done).
_PS_LABEL_BY_PLATFORM = {
    "expertise": {"submitted_pending": "applied — awaiting their editorial review",
                  "todo": "not applied yet"},
}


def _ps_label(platform: str, state: str) -> str:
    return (_PS_LABEL_BY_PLATFORM.get(platform, {}).get(state)
            or _PS_LABEL[state])
# browser_agent_actions outcomes that mean "the create actually went through"
# (recon_done / review_needed / deferred_* / needs_* never count).
# 2026-08-04: the Bing dashboard investigation minted two new outcomes that
# were never added here, so six clients Bing had ALREADY created still read
# "not started" on the card.
_SUBMITTED_OUTCOMES = ("done", "done_public", "exists", "already_exists",
                       "pending_publish_bing_queue", "published")
# ...and the subset that means the listing is actually LIVE, not merely filed.
_LIVE_OUTCOMES = ("published", "done_public")


# ---- BING: the dashboard is the truth, and it is read every night ----------
# Four independent bugs made this card lie until 2026-08-04 (all fixed here):
#   1. the per-client bing-publish-status rows are written live=False — they
#      are dashboard OBSERVATIONS, and `live` records whether the RUN was
#      permitted to write, not whether the row counts. The old query filtered
#      live=is.true and therefore saw none of them.
#   2. outcomes pending_publish_bing_queue / published were missing from
#      _SUBMITTED_OUTCOMES (above).
#   3. the only sweep row read was the 08-01 agency batch (company_id NULL),
#      whose detail names five clients in prose — so anything Bing picked up
#      in a LATER sync (Coastal, Mold Solutionz, and every future client)
#      could never match, no matter how long it sat on the dashboard.
#   4. there was no path to `live` at all: platform_status only reached
#      "live" via nap_audit.bing_places, which reads `missing` for all 20
#      clients because Bing Maps listings aren't discoverable the way the
#      citations audit searches. Crew and Home Pride are PUBLISHED on Bing
#      and still showed "not started".
# The fix reads the nightly sweep's own dashboard snapshot (meta.rows =
# name + status for EVERY listing), which self-updates and needs no
# per-client bookkeeping, and treats a Published listing as live.
_BING_STATUS_STATE = {"published": "live",
                      "pending publish": "submitted_pending",
                      "needs review": "submitted_pending",
                      "suspended": "submitted_pending"}


def _bing_name_key(name: str) -> str:
    """Normalized business name for matching a Bing dashboard row to a client.

    Bing carries the GBP title, which drifts from the app's company name by
    legal suffix and spacing ('RestorationXpress' vs 'Restoration Xpress',
    'Crew Restoration & Construction' vs '... Inc.')."""
    parts: list[str] = []
    for w in re.split(r"[^A-Za-z0-9]+", name or ""):
        if not w:
            continue
        # CamelCase-aware split so RestorationXpress == Restoration Xpress
        parts += [p.lower() for p in
                  (re.findall(r"[A-Z][a-z0-9]*|[A-Z]+(?![a-z])|[a-z0-9]+", w) or [w])]
    drop = {"inc", "llc", "l", "c", "co", "corp", "the", "and", "of", "ltd"}
    return " ".join(p for p in parts if p and p not in drop)


def _bing_snapshot() -> dict:
    """Bing state per client, from every source, newest wins.

    Returns {"by_name": {name_key: {"status", "at"}},
             "by_company": {company_id: {"state", "url", "at"}},
             "batch": [rows]}"""
    out = {"by_name": {}, "by_company": {}, "batch": []}
    try:
        # 1. the nightly sweep's dashboard snapshot — the self-updating source
        snaps = _sb("GET", "/rest/v1/browser_agent_actions"
                    "?playbook=eq.nightly-sweep&action=eq.bing-sync"
                    "&select=meta,created_at&order=created_at.desc&limit=8",
                    prefer="return=representation") or []
        for snap in snaps:  # newest first; older ones only fill gaps
            for row in ((snap.get("meta") or {}).get("rows") or []):
                key = _bing_name_key(row.get("name") or "")
                if key and key not in out["by_name"]:
                    out["by_name"][key] = {"status": (row.get("status") or "").lower(),
                                           "at": snap.get("created_at")}
    except Exception:
        pass
    try:
        # 2. per-client status rows. NO live filter (bug 1) — these are reads.
        rows = _sb("GET", "/rest/v1/browser_agent_actions"
                   "?playbook=eq.bing-places&company_id=not.is.null"
                   "&action=eq.bing-publish-status"
                   "&select=company_id,outcome,detail,meta,created_at"
                   "&order=created_at.desc&limit=200",
                   prefer="return=representation") or []
        for r_ in rows:
            cid = r_.get("company_id")
            if not cid or cid in out["by_company"]:
                continue
            oc = (r_.get("outcome") or "").lower()
            out["by_company"][cid] = {
                "state": "live" if oc in _LIVE_OUTCOMES else
                         ("submitted_pending" if oc in _SUBMITTED_OUTCOMES else "todo"),
                "url": (r_.get("meta") or {}).get("public_url"),
                "at": r_.get("created_at")}
    except Exception:
        pass
    try:
        # 3. the 08-01 agency batch row, kept as the legacy fallback only
        out["batch"] = _sb("GET", "/rest/v1/browser_agent_actions"
                           "?playbook=eq.bing-places&company_id=is.null"
                           "&outcome=in.(done,done_public,exists,already_exists,"
                           "live_write_unintended)&select=detail,meta",
                           prefer="return=representation") or []
    except Exception:
        pass
    return out


def _bing_state(cid: str, name: str, slug: str, bing: dict) -> str:
    """'live' | 'submitted_pending' | 'todo' for one client's Bing listing."""
    snap = (bing.get("by_name") or {}).get(_bing_name_key(name))
    if snap:
        return _BING_STATUS_STATE.get(snap["status"], "submitted_pending")
    per = (bing.get("by_company") or {}).get(cid)
    if per:
        return per["state"]
    if _sweep_mentions_client(bing.get("batch") or [], name, slug):
        return "submitted_pending"
    return "todo"


def _sweep_mentions_client(sweep_rows: list[dict], name: str, slug: str) -> bool:
    """True when a batch sweep row's detail/meta names this client — by slug,
    leading name words, or initials (the batch log abbreviates: FF = Flood
    Fixers, RX = RestorationXpress)."""
    name = (name or "").strip()
    words = [w for w in re.split(r"[^A-Za-z0-9]+", name) if w]
    parts: list[str] = []
    for w in words:  # CamelCase-aware: "RestorationXpress" -> Restoration, Xpress
        parts += re.findall(r"[A-Z][a-z0-9]*|[A-Z]+(?![a-z])", w) or [w]
    initials = "".join(p[0].upper() for p in parts if p)
    prefix2 = " ".join(words[:2]).lower()
    for r_ in sweep_rows:
        text = f"{r_.get('detail') or ''} {json.dumps(r_.get('meta') or {})}"
        low = text.lower()
        if slug and len(slug) >= 4 and slug in low:
            return True
        if len(prefix2) >= 8 and prefix2 in low:
            return True
        if len(initials) >= 2 and re.search(rf"\b{initials}\b", text):
            return True
    return False


def _agent_submitted_platforms(cid: str) -> set[str]:
    """us-create platforms where browser_agent_actions shows a completed
    create/submit for this company (action names look like 'houzz-create',
    'create-listing' under a platform playbook, ...).

    live=is.true stays for these: a DRY-RUN create must never read as
    submitted. Bing is deliberately NOT decided here — its state comes from
    _bing_state(), which reads the dashboard rather than our own attempts."""
    subs: set[str] = set()
    try:
        acts = _sb("GET", f"/rest/v1/browser_agent_actions?company_id=eq.{cid}"
                   "&live=is.true&select=playbook,action,outcome",
                   prefer="return=representation") or []
    except Exception:
        acts = []
    for a in acts:
        if (a.get("outcome") or "") not in _SUBMITTED_OUTCOMES:
            continue
        blob = f"{a.get('playbook') or ''} {a.get('action') or ''}".lower()
        for plat in _US_CREATE_PLATFORMS:
            if plat == "bing_places":
                continue
            if plat.split("_")[0] in blob:  # apple / bbb / houzz / homeguide
                subs.add(plat)
    return subs


def _upsert(rows: list[dict], dry_run: bool) -> None:
    """Upsert ledger rows, stamping done_at ONLY on the open->done TRANSITION.

    done_at (added 2026-08-02) is the milestone timestamp work_report.py
    renders ("Your website went live on ..."). The nightly sweep re-stamps
    updated_at on EVERY pass — that is exactly the bug that made flip times
    unrecoverable — so done_at must be: preserved verbatim while a row stays
    done, set to now() only when it transitions into done, cleared when a
    row reopens. If the pre-read of current state fails, ship WITHOUT
    done_at (never risk overwriting a real flip time with a guess)."""
    if not rows or dry_run:
        return
    now = datetime.now(timezone.utc).isoformat()
    try:
        cur: dict[tuple[str, str], dict] = {}
        for cid in {r["company_id"] for r in rows}:
            keys = ",".join(sorted({r["item_key"] for r in rows
                                    if r["company_id"] == cid}))
            for c in _sb("GET", "/rest/v1/marketing_setup_ledger"
                         f"?company_id=eq.{cid}&item_key=in.({keys})"
                         "&select=item_key,status,done_at",
                         prefer="return=representation") or []:
                cur[(cid, c["item_key"])] = c
        for r in rows:
            prev = cur.get((r["company_id"], r["item_key"])) or {}
            if r.get("status") == "done":
                # already done with a stamp -> keep it (write-back of the
                # same value, never a re-stamp); fresh transition -> now()
                r["done_at"] = (prev.get("done_at")
                                if prev.get("status") == "done"
                                and prev.get("done_at") else now)
            else:
                r["done_at"] = None  # reopened -> the old milestone is void
    except Exception:
        # PostgREST bulk upsert needs uniform keys — drop done_at everywhere
        for r in rows:
            r.pop("done_at", None)
    for r in rows:
        r["updated_at"] = now
    _sb("POST", "/rest/v1/marketing_setup_ledger?on_conflict=company_id,item_key",
        rows, prefer="resolution=merge-duplicates")


def _gsc_heal(domain: str, slug: str) -> str:
    """Idempotent GSC registration + IndexNow for a live domain."""
    msgs = []
    try:
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "gsc_register.py"),
                            "--domain", domain], capture_output=True, text=True, timeout=300)
        msgs.append("gsc:" + ("ok" if "VERIFIED" in (r.stdout + r.stderr) or "already" in
                              (r.stdout + r.stderr).lower() else "check"))
    except Exception as e:
        msgs.append(f"gsc:err {str(e)[:40]}")
    try:
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_site.py"),
                            "indexnow", "--slug", slug], capture_output=True, text=True, timeout=180)
        msgs.append("indexnow:" + ("ok" if "202" in r.stdout or "200" in r.stdout else "check"))
    except Exception as e:
        msgs.append(f"indexnow:err {str(e)[:40]}")
    return " ".join(msgs)


def _check_doc_uploads(cid: str, name: str, dry_run: bool) -> None:
    """Client hub document uploads -> a [TODO-SANTINO] note that persists in
    Today until dismissed (Santino 2026-07-31: Curt's Home Pride insurance
    PDF sat unseen in storage for a day because nothing announced it).
    Seen-state lives in ops_kv 'docs-seen' so each file alerts exactly once."""
    sb_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    r = requests.post(f"{os.environ['SUPABASE_URL']}/storage/v1/object/list/branding",
                      headers={"apikey": sb_key, "Authorization": f"Bearer {sb_key}",
                               "Content-Type": "application/json"},
                      json={"prefix": f"{cid}/docs/", "limit": 100}, timeout=30)
    if not r.ok:
        return
    paths: list[str] = []
    for folder in [f.get("name") for f in r.json() if f.get("name")]:
        rf = requests.post(f"{os.environ['SUPABASE_URL']}/storage/v1/object/list/branding",
                           headers={"apikey": sb_key, "Authorization": f"Bearer {sb_key}",
                                    "Content-Type": "application/json"},
                           json={"prefix": f"{cid}/docs/{folder}/", "limit": 100}, timeout=30)
        if rf.ok:
            paths += [f"{folder}/{f['name']}" for f in rf.json() if f.get("name")]
    if not paths:
        return
    seen_rows = _sb("GET", "/rest/v1/ops_kv?k=eq.docs-seen&select=v") or []
    seen = set((seen_rows[0].get("v") or []) if seen_rows else [])
    new = [p for p in paths if f"{cid}/{p}" not in seen]
    if not new:
        return
    # De-duplicate retry uploads of the same document (timestamp prefixes vary)
    base = sorted({re.sub(r"^\d+-", "", p.split("/")[-1]) for p in new})
    if not dry_run:
        _sb("POST", "/rest/v1/marketing_ops_notes", [{
            "company_id": cid,
            "body": f"[TODO-SANTINO] {name} uploaded {len(base)} document(s) via "
                    f"their hub link: {', '.join(base)[:200]} — stored under "
                    f"docs/{new[0].split('/')[0]}. Review and use it, then hit Done."}])
        seen.update(f"{cid}/{p}" for p in new)
        _sb("POST", "/rest/v1/ops_kv?on_conflict=k",
            {"k": "docs-seen", "v": sorted(seen)},
            prefer="resolution=merge-duplicates,return=minimal")
    print(f"  [{cid}] new client document upload(s): {', '.join(base)[:120]}")


# ---- citations readiness (Santino 2026-08-03 follow-up) ---------------------
# The nightly creation queue (browser_agent/sweep.py) skips clients missing a
# logo or with an empty companies-row NAP — those skip reasons were invisible.
# This pass makes them VISIBLE work: auto-heal what a system already holds
# (branding-bucket logo -> sites/{slug}/public/images/; GBP connection or
# clients-record snapshot -> empty companies NAP fields), and only what no
# system holds becomes a Monica ask + amber client_owed card.
#
# The bucket-logo helpers moved to brand_assets.py 2026-08-14 (Air Care build):
# build_site's scaffold now pulls the logo at scaffold time with the SAME code,
# so the two passes can never drift apart.

from brand_assets import (  # noqa: E402 — shared with build_site scaffold
    bucket_logo_files as _bucket_logo_files,
    pull_bucket_logo as _pull_bucket_logo,
)


def _nap_backfill_from_gbp(cid: str, slug: str, co: dict, dry_run: bool) -> list[str]:
    """Fill EMPTY companies-row NAP fields from what a system already holds:
    the GBP connection (live API) first, else the clients/{slug}.json gbp
    snapshot (flood-fixers pattern 2026-08-03: GBP had the full address while
    the card sat blank). NEVER overwrites a non-empty field — the card is the
    client-facing source of truth; we only seed blanks. Mutates co in place
    so downstream cards see the healed row. Returns patched field names."""
    need = [f for f in ("phone", "address", "city", "state", "postal_code")
            if not (co.get(f) or "").strip()]
    if not need:
        return []
    vals: dict = {}
    try:
        import gbp as _gbp
        rec = (_client_record(slug).get("gbp") or {})
        place = _gbp._place_id_from_connection(cid)
        if not place:
            pi = CLIENTS_DIR / slug / "plan-input.json"
            if pi.exists():
                place = (json.loads(pi.read_text()).get("brand") or {}).get("place_id")
        place = place or rec.get("place_id")
        tok = _gbp.get_access_token(cid) if place else None
        loc = _gbp.find_location(tok, place) if tok and place else None
        if loc:
            addr = loc.get("storefrontAddress") or {}
            vals = {"phone": (loc.get("phoneNumbers") or {}).get("primaryPhone"),
                    "address": ", ".join(addr.get("addressLines") or []) or None,
                    "city": addr.get("locality"),
                    "state": addr.get("administrativeArea"),
                    "postal_code": addr.get("postalCode")}
        elif rec.get("listing_phone") or rec.get("listing_address"):
            vals = {"phone": rec.get("listing_phone")}
            m = re.match(r"^(.*?),\s*([^,]+),\s*([A-Z]{2})\s+(\d{5})",
                         rec.get("listing_address") or "")
            if m:
                vals.update({"address": m.group(1), "city": m.group(2),
                             "state": m.group(3), "postal_code": m.group(4)})
    except Exception:
        return []
    patch = {f: vals[f] for f in need if vals.get(f)}
    if not patch:
        return []
    if not dry_run:
        _sb("PATCH", f"/rest/v1/companies?id=eq.{cid}", patch)
    co.update(patch)
    return sorted(patch)


def _citations_readiness(cid: str, slug: str, co: dict, platform_status: dict,
                         dry_run: bool, rows: list, attention: list,
                         owner: str = "The client") -> None:
    """Queue-readiness blockers become visible work. Only runs for clients
    the creation queue actually wants (a platform still todo); when nothing
    is pending the card flips done and asks retire."""
    from client_ops_sync import action_key, insert_plan_row
    if not platform_status:
        return  # no citations audit yet — nothing to gate on
    todo = sorted(k for k, v in platform_status.items()
                  if (v or {}).get("status") == "todo")
    logo_seed, nap_seed = f"citations-logo-{slug}", f"citations-nap-{slug}"

    def _retire(seed: str) -> None:
        if dry_run:
            return
        _sb("PATCH", "/rest/v1/marketing_action_plan"
            f"?company_id=eq.{cid}&action_key=eq.{action_key(cid, seed)}"
            "&status=eq.planned", {"status": "resolved"})

    if not todo:  # every buildable platform live/submitted — stand down
        _retire(logo_seed)
        _retire(nap_seed)
        rows.append({"company_id": cid, "item_key": "citations-blocked",
                     "kind": "client_owed", "status": "done",
                     "title": "Everything we need to build their listings is on file",
                     "detail": None,
                     "evidence": {"blockers": []}})
        return

    imgdir = SITES_DIR / slug / "public" / "images"
    logo_ok = (imgdir / "logo.png").exists() or (imgdir / "logo.webp").exists()
    # HOLDING IT COUNTS, even before it has been pulled into the repo (Santino
    # 2026-08-08). Curt (Home Pride) was asked to "send their logo file" while
    # FIVE logos sat in his branding bucket and his live site was already
    # serving one: logo_ok only looked at sites/{slug}/public/images, and the
    # bucket pull below is skipped entirely on a dry run, so a reporting pass
    # would re-seed the ask every time. Never ask for what we already have.
    if not logo_ok:
        try:
            logo_ok = bool(_bucket_logo_files(cid))
        except Exception:
            pass
    if not logo_ok and not dry_run:
        pulled = None
        try:
            pulled = _pull_bucket_logo(cid, slug)
        except Exception:
            pass
        if pulled:
            logo_ok = True
            attention.append(f"{slug}: logo pulled from branding bucket -> "
                             f"sites/{slug}/public/images/{pulled} — citation "
                             "queue unblocked (commit the file)")
    napped: list[str] = []
    try:
        napped = _nap_backfill_from_gbp(cid, slug, co, dry_run)
    except Exception:
        pass
    if napped:
        attention.append(f"{slug}: companies-row NAP backfilled from GBP "
                         f"({', '.join(napped)})")
    phone_ok = bool((co.get("phone") or "").strip())
    addr_ok = bool((co.get("address") or "").strip()) or bool(
        (co.get("city") or "").strip() and (co.get("postal_code") or "").strip())

    blockers: list[str] = []
    if not logo_ok:
        blockers.append("logo")
        if insert_plan_row(
                cid, slug, logo_seed,
                title="ASK CLIENT: send their logo file so we can finish "
                      "their directory listings",
                rationale=(
                    "We're creating their business listings across the major "
                    "directories (HomeGuide, Houzz, BBB, ...) and the missing "
                    "input is their LOGO as a clean file — the original "
                    "PNG/JPG from their designer, not a photo of a truck or "
                    "business card. MONICA: send the HUB LINK and nothing "
                    "else — "
                    f"https://restorationai.io/logo/{slug} (no login, works "
                    "from a phone). NEVER offer email or 'reply with the file "
                    "attached' (Santino 2026-08-08): an emailed attachment "
                    "only lands in an ops row that needs a human to file it, "
                    "whereas a hub upload goes straight to storage and pins "
                    "its own task. We watch their uploads automatically, so "
                    "the listings build resumes on its own once it lands."),
                action_type="client_input",
                target=f"https://restorationai.io/logo/{slug}",
                impact="high", effort="low", dry_run=dry_run):
            attention.append(f"{slug}: seeded Monica ask — logo needed for "
                             "citations build")
    else:
        _retire(logo_seed)
    if not (phone_ok and addr_ok):
        blockers.append("nap")
        miss = " and ".join(m for m, bad in (("phone number", not phone_ok),
                                             ("address", not addr_ok)) if bad)
        if insert_plan_row(
                cid, slug, nap_seed,
                title="ASK CLIENT: what phone number and address should show "
                      "publicly on their directory listings?",
                rationale=(
                    f"Their Business Information card is missing their {miss} "
                    "and no system we can reach holds it (their GBP "
                    "connection/snapshot was already checked), so their "
                    "directory listings cannot be created. MONICA: ONE "
                    "question, plain words — what phone number and street "
                    "address should appear publicly on their listings? If "
                    "they work from home and don't publish an address, city "
                    "+ ZIP is enough — say so."),
                action_type="client_input", target=None,
                impact="high", effort="low", dry_run=dry_run):
            attention.append(f"{slug}: seeded Monica ask — phone/address "
                             "needed for citations build")
    else:
        _retire(nap_seed)

    if blockers:
        what = {"logo": "their logo file",
                "nap": "their public phone number + address"}
        rows.append({
            "company_id": cid, "item_key": "citations-blocked",
            "kind": "client_owed", "status": "open",
            "title": f"{owner} needs to send "
                     + " and ".join(what[b] for b in blockers)
                     + " before we can build their listings",
            "detail": ("The nightly citation-creation queue is skipping this "
                       "client. "
                       + ("Logo: nothing usable in their brand uploads — "
                          f"upload link https://restorationai.io/logo/{slug}. "
                          if "logo" in blockers else "")
                       + ("Phone/address: the Business Information card is "
                          "empty and no connected system holds it. "
                          if "nap" in blockers else "")
                       + "Monica has the ask; the queue resumes automatically "
                         "once this lands."),
            "evidence": {"blockers": blockers, "platforms_waiting": todo}})
    else:
        rows.append({"company_id": cid, "item_key": "citations-blocked",
                     "kind": "client_owed", "status": "done",
                     "title": "Everything we need to build their listings is on file",
                     "detail": None,
                     "evidence": {"blockers": [], "platforms_waiting": todo}})


# ---------------------------------------------------------------------------
# map-rankings health (Santino 2026-08-04: "map rankings not populating seems
# to be the biggest issue")
#
# The geo-grid is the first tab a client opens, and the ONLY thing that ever
# made an empty one visible was the "data-fresh" check below — which is gated
# on geogrid-cities.json EXISTING. So the two loudest failure modes were also
# the two completely invisible ones:
#
#   * no config files at all  -> geogrid_cron SKIPs the slug silently, forever.
#     ProRestoration sat in the cron roster from 2026-07 to 2026-08-04 with a
#     healthy Google connection, a place_id, 105 reviews — and zero scans ever,
#     because nobody had run geogrid_setup for them. Nothing anywhere said so.
#   * config written with NO business identity -> every point matches nothing,
#     the scan bills full price, and the dashboard renders an all-red grid that
#     looks exactly like a real ranking collapse (HomeLyft 2026-08-03).
#
# This item derives the whole chain — identity -> config -> roster -> scans ->
# results — from the systems themselves, heals every link that is free to heal,
# and cards ONLY what a human genuinely has to decide. The baseline scan itself
# is deliberately NOT fired here: healing the config is enough for the existing
# data-fresh heal (immediately below) to pick the client up on the same pass,
# inside its own capped DataForSEO budget. One place spends money, not two.
# ---------------------------------------------------------------------------

_GG_MAX_CITIES = 6        # ring cap — a run costs keywords x cities x ~$0.34
_GG_MAX_KEYWORDS = 2      # fleet pattern: the 2 head map-pack terms
_GG_MIN_SEPARATION_MI = 9.0   # two centers closer than this scan the same ground
_GG_MAX_GEOCODES = 18     # Nominatim is 1 req/sec — bound the wall time


def _gg_miles_apart(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat_mi = (a[0] - b[0]) * 69.0
    lng_mi = (a[1] - b[1]) * 69.0 * math.cos(math.radians((a[0] + b[0]) / 2))
    return math.hypot(lat_mi, lng_mi)


def _gg_identity(slug: str, cid: str, dry_run: bool = False) -> dict:
    """Business identity (place_id / cid) for Maps matching, from the cheapest
    source that has it, and backfilled where the scanner will actually look.

    Order — all three are FREE, no DataForSEO spend:
      1. clients/{slug}/plan-input.json brand   (what geogrid_scan reads)
      2. clients/{slug}.json gbp block          (stamped at audit/onboarding)
      3. the client's OWN google integration    (the OAuth exchange auto-selects
         a place_id; the repo brand block can lag a connect by weeks)

    Returns {"place_id", "google_cid", "source", "healed"}. When identity is
    found outside plan-input, it is written INTO plan-input brand — that file is
    the one geogrid_scan.load_center() matches listings on, so an un-backfilled
    identity is the same as no identity at all.
    """
    out = {"place_id": None, "google_cid": None, "source": None, "healed": False}
    p = CLIENTS_DIR / slug / "plan-input.json"
    plan = {}
    if p.exists():
        try:
            plan = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            plan = {}
    brand = plan.get("brand") or {}
    if brand.get("place_id") or brand.get("google_cid"):
        return {"place_id": brand.get("place_id"), "google_cid": brand.get("google_cid"),
                "source": "plan-input", "healed": False}

    found_pid = found_cid = None
    src = None
    gbp = (_client_record(slug).get("gbp") or {})
    if gbp.get("place_id") or gbp.get("google_cid") or gbp.get("cid"):
        found_pid = gbp.get("place_id")
        found_cid = gbp.get("google_cid") or gbp.get("cid")
        src = "client-record"
    else:
        try:
            for row in _sb("GET", f"/rest/v1/user_integrations?client_id=eq.{cid}"
                           "&provider=eq.google&select=connection_metadata",
                           prefer="return=representation") or []:
                md = row.get("connection_metadata") or {}
                if md.get("place_id"):
                    found_pid, src = md["place_id"], "google-connection"
                    break
        except Exception:  # noqa: BLE001 — identity lookup must never kill the ledger
            pass
    if not (found_pid or found_cid):
        return out

    out.update(place_id=found_pid, google_cid=(str(found_cid) if found_cid else None),
               source=src)
    # Backfill plan-input brand — without this the scanner still can't see it.
    if p.exists() and not dry_run:
        try:
            raw = p.read_text()
            brand = plan.setdefault("brand", {})
            if found_pid:
                brand["place_id"] = found_pid
            if found_cid:
                brand["google_cid"] = str(found_cid)
            # Re-emit at the file's OWN indent. These files are hand-edited and
            # committed; rewriting a 1-space file at indent=2 turns a two-line
            # identity backfill into a 167-line diff that buries the real change.
            m = re.match(r"\{\r?\n( +)", raw)
            p.write_text(json.dumps(plan, indent=len(m.group(1)) if m else 2,
                                    ensure_ascii=False))
            out["healed"] = True
        except OSError:
            pass
    return out


def _gg_config_state(slug: str) -> tuple[int, int]:
    """(keyword count, city count) from the two files the cron reads. Counts, not
    existence: AAA's geogrid-cities.json existed but held `[]`, which reads as
    'configured' to every exists()-based check and scans nothing."""
    d = CLIENTS_DIR / slug
    n_kw = n_ct = 0
    try:
        kw = d / "geogrid-keywords.txt"
        if kw.exists():
            n_kw = len([ln for ln in kw.read_text().splitlines() if ln.strip()])
    except OSError:
        pass
    try:
        ct = d / "geogrid-cities.json"
        if ct.exists():
            n_ct = len(json.loads(ct.read_text()) or [])
    except (OSError, json.JSONDecodeError):
        pass
    return n_kw, n_ct


def _gg_ensure_roster(slug: str, cid: str) -> bool:
    """Make sure the slug is in clients/company_map.json — the cron's roster IS
    that file (geogrid_cron iterates COMPANY_MAP.keys()). A client can have
    perfect config and still never be scanned if the mapping is missing."""
    p = CLIENTS_DIR / "company_map.json"
    try:
        cm = json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return False
    if cm.get(slug) == cid:
        return False
    cm[slug] = cid
    try:
        p.write_text(json.dumps(cm, indent=1) + "\n")
        return True
    except OSError:
        return False


def _gg_heal_config(slug: str, cid: str) -> tuple[int, int]:
    """Generate geogrid-keywords.txt + geogrid-cities.json from plan-input, the
    same derivation geogrid_setup uses. Returns (keywords, cities) written.

    The ring is picked for SPREAD, not plan order. Service-area lists are written
    for site content, so they open with the neighbours nearest the shop: The
    Restoration Group's first six (Kenilworth, Union, Elizabeth, Westfield,
    Cranford, Springfield) all sit inside ~6 miles, and a 9.5-mile grid on each
    would re-scan one town cluster six times over — full price — while Newark,
    Jersey City and Manhattan went untracked. So candidates are accepted only
    when they're at least _GG_MIN_SEPARATION_MI from every center already taken.

    Geocoding is Nominatim at 1 req/sec, so candidates examined are bounded too;
    an auto-generated ring stays deliberately small and a human can widen it.
    """
    import geogrid_setup as gsetup  # local sibling; heavy-ish, imported on demand

    plan = json.loads((CLIENTS_DIR / slug / "plan-input.json").read_text())
    brand = plan.get("brand") or {}
    # HOME-CITY FALLBACK (DryCor 2026-09-02): a client with a verified listing
    # but no service_areas yet (site plan not run) used to be un-healable —
    # blocked on a card while their Map Rankings tab sat blank. One home-city
    # ring is always derivable: the brand center if plan-input has it, else a
    # geocode of the company's own city. The full multi-city ring still
    # arrives when the site plan writes service_areas; this gets DATA on the
    # tab from the first overnight pass.
    if not (plan.get("service_areas") or []):
        label = None
        try:
            co = (_sb("GET", f"/rest/v1/companies?id=eq.{cid}"
                      "&select=city,state", prefer="return=representation") or [{}])[0]
            label = (co.get("city") or "").strip() or None
        except Exception:
            co = {}
        lat = lng = None
        if brand.get("lat") and brand.get("lng"):
            lat, lng = float(brand["lat"]), float(brand["lng"])
        elif label:
            geo = gsetup.geocode_city(label, (co.get("state") or "").strip())
            if geo:
                lat, lng = geo
        if lat is not None and label:
            keywords = gsetup.derive_keywords(slug, _GG_MAX_KEYWORDS)
            if keywords:
                d = CLIENTS_DIR / slug
                (d / "geogrid-keywords.txt").write_text("\n".join(keywords) + "\n")
                (d / "geogrid-cities.json").write_text(json.dumps(
                    [{"label": label, "lat": lat, "lng": lng,
                      "miles_list": [6.5, 9.5, 15]}], indent=2) + "\n")
                return len(keywords), 1
        return 0, 0
    areas, seen = [], set()
    for a in plan.get("service_areas") or []:
        label = f"{a.get('city')}, {a.get('state')}"
        if not a.get("city") or label in seen:
            continue
        seen.add(label)
        areas.append(a)
    areas.sort(key=lambda a: 0 if a.get("primary") else 1)

    cities: list[dict] = []
    geocodes = 0
    for a in areas:
        if len(cities) >= _GG_MAX_CITIES or geocodes >= _GG_MAX_GEOCODES:
            break
        label = f"{a['city']}, {a['state']}"
        if a.get("primary") and brand.get("lat") and brand.get("lng"):
            lat, lng = float(brand["lat"]), float(brand["lng"])
        else:
            geocodes += 1
            geo = gsetup.geocode_city(a["city"], a["state"])
            time.sleep(1.1)  # Nominatim: <=1 req/sec
            if not geo:
                continue
            lat, lng = geo
        if any(_gg_miles_apart((lat, lng), (c["lat"], c["lng"])) < _GG_MIN_SEPARATION_MI
               for c in cities):
            continue  # already covered by a grid we're scanning
        cities.append({"label": label, "lat": lat, "lng": lng})
        # Backfill the BUSINESS center off the primary city when the brand block
        # has none. geogrid_scan.load_center hard-requires brand.lat/lng, so a
        # config generated without it produces a client that is "configured" and
        # still cannot be scanned — the exact half-fixed state this item exists
        # to abolish (FireDEX/AAA/MCC/Paul Davis all had no brand center).
        if a.get("primary") and not (brand.get("lat") and brand.get("lng")):
            plan.setdefault("brand", {})["lat"] = lat
            plan["brand"]["lng"] = lng
            brand = plan["brand"]
            raw = (CLIENTS_DIR / slug / "plan-input.json").read_text()
            m = re.match(r"\{\r?\n( +)", raw)
            (CLIENTS_DIR / slug / "plan-input.json").write_text(
                json.dumps(plan, indent=len(m.group(1)) if m else 2,
                           ensure_ascii=False))
    if not cities:
        return 0, 0
    keywords = gsetup.derive_keywords(slug, _GG_MAX_KEYWORDS)
    if not keywords:
        return 0, 0
    d = CLIENTS_DIR / slug
    (d / "geogrid-keywords.txt").write_text("\n".join(keywords) + "\n")
    (d / "geogrid-cities.json").write_text(json.dumps(cities, indent=2) + "\n")
    return len(keywords), len(cities)


def _map_and_video_rows(cid: str, slug: str, gi, rows: list[dict],
                        attention: list[str], _HEALS: dict, dry_run: bool,
                        owner: str = "The client") -> None:
    """map-rankings + video-channel cards for one client (appends to `rows`).

    Split out of ensure_ledger so the two newest checks can be evaluated on
    their own — `python3 scripts/setup_ledger.py --map-video-only` — without
    triggering a whole nightly pass (which also provisions phone numbers and
    imports media). Same code either way; there is no second implementation.
    """
    # ---- map-rankings (Santino 2026-08-04) -----------------------------
    # Runs BEFORE data-fresh on purpose: whatever config this heals, the
    # data-fresh block below sees on the SAME pass and schedules the first
    # scan for, inside its own DataForSEO budget. See the module-level note.
    try:
        n_kw, n_ct = _gg_config_state(slug)
        ident = _gg_identity(slug, cid, dry_run)
        has_ident = bool(ident["place_id"] or ident["google_cid"])
        if ident["healed"]:
            attention.append(f"{slug}: map identity backfilled from "
                             f"{ident['source']} — scans can match the listing now")
        has_areas = bool((json.loads((CLIENTS_DIR / slug / "plan-input.json").read_text())
                          .get("service_areas") or [])
                         if (CLIENTS_DIR / slug / "plan-input.json").exists() else False)
        google_connected = bool(gi)
        healed_now = False

        # AUTO-HEAL: identity is the only hard requirement. With service
        # areas the generator builds the full spread ring; without them it
        # falls back to a home-city 3-radius grid (DryCor 2026-09-02) so the
        # client's Map Rankings tab has data while the site plan catches up.
        if not (n_kw and n_ct) and has_ident \
                and not dry_run and _HEALS.get("ggconfig", 0) > 0:
            _HEALS["ggconfig"] -= 1
            n_kw, n_ct = _gg_heal_config(slug, cid)
            healed_now = bool(n_kw and n_ct)
            if healed_now:
                attention.append(f"{slug}: map-rankings config GENERATED "
                                 f"({n_kw} keywords x {n_ct} cities) — baseline scan queued")
        if (n_kw and n_ct) and not dry_run and _gg_ensure_roster(slug, cid):
            attention.append(f"{slug}: added to the geo-grid cron roster "
                             "(company_map) — it was configured but never scheduled")

        scans = []
        if n_kw and n_ct:
            scans = _sb("GET", "/rest/v1/marketing_geogrid_scans"
                        f"?company_id=eq.{cid}&select=found_points,total_points,"
                        "scanned_at,keyword,city_label&order=scanned_at.desc"
                        f"&limit={min(max(n_kw * n_ct, 1), 20)}",
                        prefer="return=representation") or []
        found_total = sum(s.get("found_points") or 0 for s in scans)
        pts_total = sum(s.get("total_points") or 0 for s in scans)

        status, kind, title, detail = "done", "auto", "Map ranks are being tracked", None
        if not (n_kw and n_ct):
            if has_ident:
                # heal budget spent this pass (or home-city fallback found no
                # city on the company row — the ops digest's NO MAP DATA line
                # is the alarm for that) — next run picks it up
                status, kind = "open", "auto"
                title = "Map rank tracking is being set up"
                detail = ("Their map-rank tracking has no city grid yet. It "
                          "generates automatically on the next overnight pass.")
            elif google_connected and not has_ident:
                status, kind = "open", "us_owed"
                title = "Map rank tracking is stuck: nobody picked which Google listing to track"
                detail = ("Their Google account is connected, but no Business "
                          "Profile location is attached to it — so we have no "
                          "listing to look for in the map results and rankings "
                          "can never populate. Pick their location on the Google "
                          "connection (or add place_id to their client record).")
                attention.append(f"{slug}: MAP RANKINGS BLOCKED — google connected "
                                 "but no place_id/location selected")
            elif not has_areas:
                status, kind = "blocked", "us_owed"
                title = "Map rank tracking is stuck: no cities have been planned for them"
                detail = ("We track map rank per city, and this client has no "
                          "service-area list yet — run the site plan first.")
                attention.append(f"{slug}: map rankings blocked — no service_areas in plan-input")
            else:
                # No Google connection at all. The google-connected card
                # ALREADY owns this ask; duplicating it would put the same
                # nag in front of Santino twice.
                status, kind = "blocked", "client_owed"
                title = "Map rank tracking is waiting on their Google connection"
                detail = ("We can't track their map rankings until their Google "
                          "account is connected — that's the 'Google NOT "
                          "connected' item above, no separate action needed.")
        elif not scans:
            status, kind = "open", "auto"
            title = "Map rank tracking: first scan still running"
            detail = (f"Tracking is configured ({n_kw} keywords x {n_ct} cities) "
                      "but no scan has ever run. The baseline runs automatically.")
            if not healed_now:
                attention.append(f"{slug}: map-rankings configured but ZERO scans ever "
                                 "— baseline queued")
        elif pts_total and found_total == 0:
            # THE REAL FINDING. Config is right, identity is right, the scan
            # billed — and the listing appeared at no point on the grid. That
            # is a genuine local-visibility problem, not a plumbing bug.
            status, kind = "open", "us_owed"
            title = "They rank NOWHERE on Google Maps across their whole service area"
            detail = ("Their listing isn't surfacing in Google Maps at ANY point "
                      f"across the last {len(scans)} map scan(s) — 0 of {pts_total} "
                      "grid points. Worth checking their Business Profile is "
                      "verified, categorised, and that the service area matches "
                      "where we're scanning.")
            attention.append(f"{slug}: 0/{pts_total} map points — listing not surfacing "
                             "in Maps at all (check GBP verification/categories)")
        else:
            title = (f"Map ranks tracked across {n_ct} cities and {n_kw} keywords")

        rows.append({"company_id": cid, "item_key": "map-rankings", "kind": kind,
                     "status": status, "title": title, "detail": detail,
                     "evidence": {"keywords": n_kw, "cities": n_ct,
                                  "identity": has_ident,
                                  "identity_source": ident["source"],
                                  "scans_seen": len(scans),
                                  "found_points": found_total,
                                  "total_points": pts_total}})
    except Exception as e:  # noqa: BLE001 — a health check must never kill the ledger
        attention.append(f"{slug}: map-rankings check failed ({str(e)[:90]})")

    # ---- video-channel (Santino 2026-08-04) ----------------------------
    # "Connected" is not "publishable". A Google account can finish the
    # whole YouTube OAuth flow while owning no channel at all — every read
    # succeeds and only the final upload fails, after we've already paid
    # for the script, the narration and the images (ProRestoration).
    try:
        import video_maker as _vm
        yt = _vm.youtube_channel_state(slug)
        if yt["connected"] and yt["has_channel"] is False:
            rows.append({"company_id": cid, "item_key": "video-channel",
                         "kind": "client_owed", "status": "open",
                         "title": f"{owner} needs to create a YouTube channel — we cannot post videos without one",
                         "detail": ("Their Google account is linked for video, but "
                                    "it doesn't have a YouTube channel yet — so "
                                    "nothing we produce can be published. Monica is "
                                    "asking them to create one (it takes about 30 "
                                    "seconds); video production is paused for them "
                                    "until it exists."),
                         "evidence": {"connected": True, "has_channel": False,
                                      "reason": yt["reason"]}})
            attention.append(f"{slug}: YouTube connected with NO CHANNEL — "
                             "video pipeline is paused for them")
        elif yt["connected"] and yt["has_channel"]:
            rows.append({"company_id": cid, "item_key": "video-channel",
                         "kind": "client_owed", "status": "done",
                         "title": f"YouTube channel ready to publish to: {yt['channel_title'] or yt['channel_id']}",
                         "detail": None,
                         "evidence": {"connected": True, "has_channel": True,
                                      "channel_id": yt["channel_id"],
                                      "channel_title": yt["channel_title"]}})
        # not connected, or has_channel is None (unverifiable) -> no card.
        # Never assert a gap we could not actually read.
    except Exception as e:  # noqa: BLE001
        attention.append(f"{slug}: video-channel check failed ({str(e)[:90]})")


def ensure_ledger(dry_run: bool, cid_to_slug: dict | None = None) -> list[str]:
    """Evaluate the ledger for every Active Rank AI client. Returns attention
    lines (us-owed gaps) for the nightly ops email."""
    cid_to_slug = cid_to_slug or slug_map()
    zones = _our_zones()
    cos = _sb("GET", "/rest/v1/companies?status=ilike.active&plan=eq.Rank%20AI"
              "&select=id,name,phone,address,city,state,postal_code,website,"
              "services,integration_settings,email,account_owner_name,"
              "management_contacts,transfer_1_name",
              prefer="return=representation") or []
    attention: list[str] = []
    # Registrar delegate invitations, read ONCE per run from the agency
    # mailbox (2026-08-05). This is the evidence layer behind every
    # "delegate access" claim — see _delegate_verification().
    invite_map, invite_scan_ok, invite_err, invite_ambiguous = _scan_registrar_invites(
        cos, cid_to_slug)
    if not invite_scan_ok:
        attention.append("domain-access: agency inbox NOT readable this run "
                         f"({invite_err}) — delegate claims stay UNVERIFIED")
    for amb in invite_ambiguous:
        attention.append(
            "domain-access: a "
            f"{amb['invite']['registrar']} access invite from "
            f"{amb['invite']['inviter']!r} ({amb['invite']['date'][:10]}) "
            "matches more than one client — "
            + ", ".join(c["name"] for c in amb["candidates"])
            + " — nobody was auto-advanced")
    # per-run auto-heal budget: 2 geo-grid re-scans (DFS cost) + 3 media
    # imports + 3 tracking-number provisions + 3 GBP phone swaps + 2 geo-grid
    # config generations (free, but each geocodes a city ring at 1.1s/city)
    _HEALS = {"geogrid": 2, "media": 3, "calltrack": 3, "swap": 3, "citations": 2,
              "ggconfig": 2}
    bing = _bing_snapshot()  # fetched once; reused per client
    # Clients whose GBP the agency actually manages. Bing Places imports ONLY
    # those, so this is the honest answer to "why is Bing still not started?"
    # (scripts/gbp_admin_invite.py keeps it current on the daily pass).
    try:
        from gbp_admin_invite import manager_slugs
        _gbp_managers = manager_slugs()
    except Exception:
        _gbp_managers = set()

    for co in cos:
        cid = co["id"]
        slug = cid_to_slug.get(cid)
        if not slug:
            attention.append(f"(no slug) {co.get('name')}: not in slug map — bootstrap missing")
            continue
        ints = co.get("integration_settings") or {}
        if isinstance(ints, str):
            try:
                ints = json.loads(ints)
            except json.JSONDecodeError:
                ints = {}
        rows: list[dict] = []
        owner = _owner_first_name(co)

        # ---- site-built --------------------------------------------------
        built = (SITES_DIR / slug / "src").exists()
        kickoff = None if built else _upcoming_kickoff(ints)
        detail = None
        if not built:
            detail = f"No website has been built for {owner} yet."
            if kickoff:
                try:
                    days = (datetime.strptime(kickoff[:19], "%Y-%m-%d %H:%M:%S")
                            - datetime.now()).days
                    if days <= 3:
                        detail = (f"CRITICAL: kickoff {kickoff} is {max(days, 0)} day(s) away "
                                  "and NO preview site exists — build it before the call.")
                except ValueError:
                    pass
        rows.append({"company_id": cid, "item_key": "site-built", "kind": "us_owed",
                     "status": "done" if built else "open",
                     "title": "Website built and ready to preview",
                     "detail": detail,
                     "evidence": {"kickoff": kickoff, "site_dir": built}})
        if not built:
            attention.append(f"{slug}: SITE NOT BUILT" + (f" — {detail}" if detail and "CRITICAL" in detail else ""))

        # ---- site-finished (2026-09-04, Frontline: a rendered site shipped
        # grey placeholder heroes + the default palette for a day and only
        # Santino's eyeballs caught it). A BUILT site stays "open" here until
        # its finishing pass is done: real images on disk and a real brand
        # palette in plan-input. The nightly render sweep auto-fills images;
        # colors auto-extract from the logo at scaffold — this row is the
        # backstop that makes any survivor visible on Ops Attention.
        if built:
            unfinished = []
            if not (SITES_DIR / slug / "public" / "images" / "hero-bg.webp").exists():
                unfinished.append("images (no hero-bg.webp)")
            try:
                _pi = json.loads((CLIENTS_DIR / slug / "plan-input.json").read_text())
                _pb = _pi.get("brand") or {}
                if not (_pb.get("primary_color") or (_pb.get("colors") or {}).get("primary")):
                    unfinished.append("brand colors (default palette)")
            except (OSError, json.JSONDecodeError):
                pass
            # pages still dripping out (nightly render cap) — informational
            # until done, and a hard block on cutover
            _pend = 0
            for _md in (SITES_DIR / slug / "src" / "content").rglob("*.md"):
                try:
                    _raw = _md.read_text(errors="ignore")
                except OSError:
                    continue
                _fm = _raw[:_raw.find("\n---", 3) + 4] if _raw.startswith("---") else _raw
                if not re.search(r"^rendered:\s*true\b", _fm, re.M):
                    _pend += 1
            if _pend:
                unfinished.append(f"{_pend} page(s) still rendering (nightly drip)")
            rows.append({"company_id": cid, "item_key": "site-finished", "kind": "us_owed",
                         "status": "open" if unfinished else "done",
                         "title": "Site finishing pass (images + brand colors)",
                         "detail": (f"Built site still missing: {', '.join(unfinished)}. "
                                    "Images auto-fill on the nightly render sweep; colors: "
                                    "set plan-input brand colors (or re-pull logo) then "
                                    "build_site.py retint." if unfinished else None),
                         "evidence": {"unfinished": unfinished}})
            if unfinished:
                attention.append(f"{slug}: SITE UNFINISHED — {', '.join(unfinished)}")

        # ---- THE LAUNCH CARD: domain access + going live, ONE truth --------
        # Santino 2026-08-05: Crew showed THREE items telling one story —
        # "Registrar / domain access", "Live on real domain", and a duplicate
        # domain ask inside "Waiting on N things". They are now a single
        # card (item_key domain-access) whose text changes by state. The
        # site-live row survives ONLY as the milestone work_report.py reads
        # (status 'na' while it is not live, so it never renders a card).
        domain = _norm_domain(_client_record(slug).get("domain") or co.get("website"))
        live = False
        if domain and built:
            live = _site_serves_us(domain, co.get("name") or "",
                                   _client_record(slug).get("indexnow_key"),
                                   slug=slug)
        zstat = zones.get(domain, "") if domain else ""
        ours = zstat == "active"
        rows.append({"company_id": cid, "item_key": "site-live", "kind": "auto",
                     "status": "done" if live else "na",
                     "title": (f"Website is live on {domain}" if live
                               else "Website not live yet"),
                     "detail": None,
                     "evidence": {"domain": domain, "zone_status": zstat or "none"}})
        if not domain:
            kind, status, title, detail = _launch_card(
                owner, "", built, False, False, "", "none", {}, {})
            rows.append({"company_id": cid, "item_key": "domain-access",
                         "kind": kind, "status": status, "title": title,
                         "detail": detail, "evidence": {"domain": None}})
            if built:
                attention.append(f"{slug}: site built, NO DOMAIN on file — decide buy vs client's registrar")
        else:
            if built and not live:
                attention.append(f"{slug}: built but NOT LIVE on {domain} — "
                                 + ("LAUNCH NOW (zone active)" if ours else
                                    ("NS cutover pending (zone ready)" if zstat == "pending"
                                     else "needs domain access")))
            # ---- domain-access STATE MACHINE (2026-08-03) -------------------
            # none -> promised -> delegate_granted | creds_provided -> ns_live
            gap_open = bool(built and domain and not ours and not live)
            # PREVIEW-FIRST GATE (Santino 2026-09-09, Frontline: "site is
            # ready" landed with no link because the reveal lane was still
            # in its 7-day window — the two lanes now merge AT THE END:
            # reveal the preview -> client sees it -> THEN ask for domain
            # access). The domain ask holds while the preview ask has not
            # yet been seeded, or was seeded under 2 days ago with no
            # client response (silence past 2 days releases the hold so a
            # quiet client never blocks a launch). Access already promised/
            # granted skips the gate — never un-ask what's in motion.
            # da MUST be fetched before the gate reads it (2026-09-17: the
            # 09-09 gate landed above the old assignment — UnboundLocalError
            # on the first gap_open client killed the whole ledger pass, and
            # a later gap_open client would have read the PREVIOUS client's
            # row). One fetch, up front, both bugs gone.
            da = _domain_access_row(cid) or {}
            if gap_open and (da.get("domain_access_status") or "none") == "none":
                try:
                    _pv = _sb("GET", "/rest/v1/marketing_action_plan"
                              f"?company_id=eq.{cid}"
                              f"&action_key=eq.site-preview-feedback-{slug}"
                              "&select=status,created_at&limit=1",
                              prefer="return=representation") or []
                    if not _pv:
                        gap_open = False  # preview not even revealed yet
                        attention.append(
                            f"{slug}: domain-access ask HELD — preview not "
                            "revealed yet (preview-first launch protocol)")
                    elif _pv[0].get("status") in ("planned", "in_progress"):
                        from datetime import datetime as _dt2
                        _age = (datetime.now(timezone.utc) - _dt2.fromisoformat(
                            str(_pv[0]["created_at"]).replace("Z", "+00:00"))).days
                        if _age < 2:
                            gap_open = False
                            attention.append(
                                f"{slug}: domain-access ask HELD — preview "
                                f"sent {_age}d ago, waiting for the client's "
                                "reaction (releases after 2 days)")
                except Exception:  # noqa: BLE001 — gate must never kill the pass
                    pass
            da_status = da.get("domain_access_status") or "none"
            try:
                patch: dict = {}
                if (ours or live) and da:
                    # ns_live auto-detect — the zone check we already run IS
                    # the evidence; no click, no claim, just the NS truth.
                    if da_status != "ns_live":
                        patch["domain_access_status"] = "ns_live"
                        patch["domain_ns_live_at"] = datetime.now(
                            timezone.utc).isoformat()
                        da_status = "ns_live"
                        attention.append(f"{slug}: domain access -> ns_live "
                                         "(zone active / site serves us)")
                elif gap_open and da:
                    # precompute the registrar guess for the app's dropdown
                    if (da.get("domain_access_domain") != domain
                            or not da.get("domain_registrar_guess")):
                        patch["domain_access_domain"] = domain
                        guess = _registrar_guess(domain)
                        if guess:
                            patch["domain_registrar_guess"] = guess
                    # EVIDENCE FIRST (2026-08-05): a real registrar invitation
                    # sitting in the agency mailbox advances the state on its
                    # own — no click, no claim, an actual email we can point
                    # at. This is the path that should carry every client.
                    _invs = invite_map.get(cid) or []
                    if _invs and da_status not in ("delegate_granted", "ns_live"):
                        patch["domain_access_status"] = "delegate_granted"
                        patch["domain_access_granted_at"] = (
                            _invs[0].get("date")
                            or datetime.now(timezone.utc).isoformat())
                        if not da.get("domain_registrar"):
                            patch["domain_registrar"] = _invs[0].get("registrar")
                        da_status = "delegate_granted"
                        attention.append(
                            f"{slug}: delegate access VERIFIED from the inbox "
                            f"({_invs[0].get('registrar')} invite from "
                            f"{_invs[0].get('inviter')}, "
                            f"{str(_invs[0].get('date'))[:10]}) — ready for the "
                            "NS cutover")
                    # Ops Attention "I confirmed access manually" click executor
                    # (marketing_ops_notes pattern, same as APPROVE-PHONE-SWAP:
                    # no note -> nothing happens, ever). A human assertion is
                    # recorded as exactly that and stays distinguishable from
                    # the verified path forever — see _delegate_verification.
                    elif da_status not in ("delegate_granted", "ns_live"):
                        confirms = _sb(
                            "GET", "/rest/v1/marketing_ops_notes"
                            f"?company_id=eq.{cid}&status=eq.open"
                            "&body=like.*%5BDELEGATE-ACCESS-CONFIRMED%5D*"
                            "&select=id", prefer="return=representation") or []
                        if confirms and not dry_run:
                            patch["domain_access_status"] = "delegate_granted"
                            patch["domain_access_granted_at"] = datetime.now(
                                timezone.utc).isoformat()
                            da_status = "delegate_granted"
                            for cn in confirms:
                                _sb("PATCH", "/rest/v1/marketing_ops_notes"
                                    f"?id=eq.{cn['id']}",
                                    {"status": "resolved",
                                     "resolved_at": datetime.now(
                                         timezone.utc).isoformat()})
                            attention.append(f"{slug}: delegate access asserted "
                                             "BY HAND (no invite in the inbox "
                                             "yet) — verifying")
                if patch and da and not dry_run:
                    _sb("PATCH", f"/rest/v1/marketing_sites?id=eq.{da['id']}",
                        patch)
            except Exception as e:  # noqa: BLE001 — state upkeep must never kill the ledger
                attention.append(f"{slug}: domain-access state update failed "
                                 f"({str(e)[:80]})")
            # How do we KNOW? (registrar email / client creds / a human's word)
            verify = _delegate_verification(cid, da_status,
                                            invite_map.get(cid) or [],
                                            invite_scan_ok)
            # FALSE GREEN ROLLBACK (2026-08-05): a human assertion the mailbox
            # cannot back up is not access. Put the state column back where it
            # was before the click — otherwise the client's own "Provide
            # Domain Access" card in the app keeps telling THEM we hold
            # something we never received (Crew Restoration, 2026-08-04).
            if verify.get("state") == "human_unverified" \
                    and da_status == "delegate_granted":
                pre = "promised" if da.get("domain_access_promised_at") else "none"
                if not dry_run and da.get("id"):
                    try:
                        _sb("PATCH", f"/rest/v1/marketing_sites?id=eq.{da['id']}",
                            {"domain_access_status": pre,
                             "domain_access_granted_at": None})
                        open_flags = _sb(
                            "GET", "/rest/v1/marketing_ops_notes"
                            f"?company_id=eq.{cid}&status=eq.open"
                            "&body=like.*%5BDOMAIN-ACCESS-UNVERIFIED%5D*"
                            "&select=id", prefer="return=representation") or []
                        if not open_flags:
                            _sb("POST", "/rest/v1/marketing_ops_notes", [{
                                "company_id": cid, "author": "rank-ai ledger",
                                "status": "open",
                                "body": ("[DOMAIN-ACCESS-UNVERIFIED] "
                                         f"{domain} was marked 'access confirmed' "
                                         "by hand, but no registrar access invite "
                                         "for this client has ever reached "
                                         f"{DOMAIN_ACCESS_INVITE_EMAIL}. Rolled "
                                         f"the state back to '{pre}' so nothing "
                                         "claims we hold access. If the invite "
                                         "went somewhere else, forward or accept "
                                         "it from that inbox; otherwise the "
                                         "client still has to send it.")}])
                    except Exception as e:  # noqa: BLE001
                        attention.append(f"{slug}: false-green rollback failed "
                                         f"({str(e)[:80]})")
                da_status = pre
            access_in_hand = (da_status in ("delegate_granted", "creds_provided",
                                            "ns_live")
                              and verify.get("state") != "human_unverified")
            kind, status, title, detail = _launch_card(
                owner, domain, built, live, ours, zstat, da_status, da, verify)
            # The card owns its own status: done ONLY when the site is
            # actually live. gap_open is the ACCESS gap (false once the zone
            # is ours), and using it here used to make the whole launch card
            # vanish the moment the nameservers landed — exactly when
            # "flip it live, today" needs to be the loudest row on the board.
            rows.append({"company_id": cid, "item_key": "domain-access",
                         "kind": kind, "status": status,
                         "title": title, "detail": detail,
                         "evidence": {"domain": domain,
                                      "zone_status": zstat or "none",
                                      "access_status": da_status,
                                      "verified_by": verify.get("state"),
                                      "invite": verify.get("invite"),
                                      "assertion": verify.get("assertion"),
                                      "access_in_hand": access_in_hand,
                                      "mailbox_readable": invite_scan_ok,
                                      "registrar": da.get("domain_registrar"),
                                      "registrar_guess": da.get("domain_registrar_guess"),
                                      "account_email": da.get("domain_account_email")}})
            if gap_open and access_in_hand:
                attention.append(
                    f"{slug}: domain access in hand ({da_status}, "
                    f"{verify.get('state')}) — run the NS cutover for {domain}")
            if gap_open and verify.get("state") == "human_unverified":
                attention.append(
                    f"{slug}: FALSE GREEN — {domain} was marked 'access "
                    f"confirmed' by hand {(verify.get('assertion') or {}).get('hours')}h "
                    "ago but NO registrar invite has ever reached "
                    f"{DOMAIN_ACCESS_INVITE_EMAIL}. Access is NOT in hand; the "
                    "client ask is back on.")
            # Monica actually asks via marketing_action_plan (gather_items),
            # NOT this ledger table — before 2026-08-03 the domain-access
            # ledger card claimed "Monica is asking them" while no
            # client_input row existed, so the ask never ranked anywhere
            # (Mold Solutionz: site built, cutover pending, and Andrea's
            # next draft led with the customer list). Seeding is now STATE-
            # GATED: none -> the rank-1 access ask; promised (or a human
            # assertion the mailbox cannot back up) -> a verify nudge ("did
            # the invite go to setup@?"); access genuinely in hand -> both
            # rows retired, Monica stops asking. Titles contain "domain" so
            # the concierge's ask_rank keeps them at launch-blocker
            # priority (1).
            try:
                from client_ops_sync import action_key, insert_plan_row
                seed = f"domain-access-{slug}"
                seed_verify = f"domain-verify-{slug}"

                def _retire_ask(key_seed: str) -> None:
                    if dry_run:
                        return
                    _sb("PATCH", "/rest/v1/marketing_action_plan"
                        f"?company_id=eq.{cid}"
                        f"&action_key=eq.{action_key(cid, key_seed)}"
                        "&status=eq.planned", {"status": "resolved"})

                def _refresh_rationale(key_seed: str, rationale: str,
                                       marker: str) -> None:
                    """insert_plan_row is find-or-create, so a row seeded
                    before a policy change keeps its old briefing forever.
                    The registrar truth is too important for that: any OPEN
                    row still missing it gets rewritten in place (2026-08-04).
                    """
                    if dry_run:
                        return
                    rows_ = _sb(
                        "GET", "/rest/v1/marketing_action_plan"
                        f"?company_id=eq.{cid}"
                        f"&action_key=eq.{action_key(cid, key_seed)}"
                        "&status=eq.planned&select=id,rationale",
                        prefer="return=representation") or []
                    for r_ in rows_:
                        if marker in str(r_.get("rationale") or ""):
                            continue
                        _sb("PATCH",
                            f"/rest/v1/marketing_action_plan?id=eq.{r_['id']}",
                            {"rationale": rationale})
                        attention.append(f"{slug}: refreshed the domain-access "
                                         "ask briefing with the registrar "
                                         "truth (we can never fetch access "
                                         "ourselves)")

                def _reopen_ask(key_seed: str) -> None:
                    """Bring a resolved row back to planned (insert_plan_row
                    is find-or-create and never re-opens on its own)."""
                    if dry_run:
                        return
                    _sb("PATCH", "/rest/v1/marketing_action_plan"
                        f"?company_id=eq.{cid}"
                        f"&action_key=eq.{action_key(cid, key_seed)}"
                        "&status=eq.resolved", {"status": "planned"})

                # Inside the grace window we touch nothing: the invite may
                # still be landing. After a false-green rollback da_status is
                # already back at the client's real position ('promised' when
                # they claimed to have sent it -> gentle nudge; 'none' when
                # nobody ever claimed anything -> the full ask returns).
                _waiting = verify.get("state") in ("human_pending",
                                                   "human_unchecked")
                if gap_open and _waiting:
                    pass  # verifying — leave every ask exactly as it is
                elif gap_open and da_status == "promised":
                    _retire_ask(seed)
                    _reopen_ask(seed_verify)
                    if insert_plan_row(
                            cid, slug, seed_verify,
                            title="ASK CLIENT: did the domain access invite "
                                  f"reach {DOMAIN_ACCESS_INVITE_EMAIL}?",
                            rationale=(
                                "Someone on our side believes access to "
                                f"{domain} was already provided, but nothing "
                                "has landed in our inbox. MONICA: this is a "
                                "gentle verification, not a re-ask — never "
                                "re-explain the whole thing. ONE question on "
                                "normal cooldown: did the access invite go to "
                                f"{DOMAIN_ACCESS_INVITE_EMAIL}? If they used a "
                                "different email or aren't sure, offer a quick "
                                "15-minute call to do it together. Thank them "
                                "for already acting on it."),
                            action_type="client_input", target=domain,
                            impact="high", effort="low", dry_run=dry_run):
                        attention.append(f"{slug}: seeded Monica VERIFY nudge — "
                                         f"domain access claimed for {domain}")
                elif gap_open and da_status == "none":
                    _retire_ask(seed_verify)
                    # RE-OPEN (Santino 2026-08-04, Reign): Jerrott answered
                    # "yes it's with GoDaddy, I've got all the information",
                    # the classifier resolved the ask as answered, and the
                    # thing we actually need — access — never arrived. The
                    # state machine is the authority: while
                    # domain_access_status is 'none' and the gap is open, the
                    # client still owes us access, so a resolved ask goes
                    # back to planned. Naming the registrar is not access.
                    if not dry_run:
                        reop = _sb(
                            "PATCH", "/rest/v1/marketing_action_plan"
                            f"?company_id=eq.{cid}"
                            f"&action_key=eq.{action_key(cid, seed)}"
                            "&status=eq.resolved", {"status": "planned"},
                            prefer="return=representation") or []
                        if reop:
                            attention.append(
                                f"{slug}: domain-access ask was resolved but "
                                "access is still NOT in hand (status=none) — "
                                "RE-OPENED; knowing the registrar is not "
                                "access")
                    ask_how = (DOMAIN_ACCESS_ASK_GODADDY
                               if (da.get("domain_registrar")
                                   or da.get("domain_registrar_guess")
                                   or "") == "godaddy"
                               else DOMAIN_ACCESS_ASK_GENERIC)
                    _rationale = (
                                f"Their new website is BUILT and ready to go live on "
                                f"{domain}; the only thing missing is access to the "
                                "place where they bought the domain. "
                                + DOMAIN_ACCESS_TRUTH + " HOW THEY GRANT IT: "
                                + ask_how + " MONICA: plain words only, never say "
                                "'registrar' or 'nameservers', and NEVER tell them "
                                "we will reach out to GoDaddy or anyone else. ONE "
                                "question, their choice of two easy paths: they send "
                                "us access from their domain account (about two "
                                "minutes), or we hop on a quick 15-minute call and do "
                                "it together while they're signed in, we drive and "
                                "they hold their own phone on a VIDEO call, nobody visits them. Their current site keeps "
                                "working the whole time. Finding out WHICH company "
                                "holds the domain is useful but does not close this "
                                "ask, only the access does. This outranks every other "
                                "ask except showing them their finished site — "
                                "nothing can launch without it.")
                    if insert_plan_row(
                            cid, slug, seed,
                            title="ASK CLIENT: send us access to their domain "
                                  f"({domain}) so the new site can go live",
                            rationale=_rationale,
                            action_type="client_input", target=domain,
                            impact="high", effort="low", dry_run=dry_run):
                        attention.append(f"{slug}: seeded Monica ask — domain "
                                         f"access for {domain}")
                    else:
                        # Row already existed: make sure its briefing is the
                        # CURRENT one, not whatever policy was live the day it
                        # was seeded (2026-08-04).
                        _refresh_rationale(seed, _rationale,
                                           "WE CANNOT GET DOMAIN ACCESS")
                else:
                    # gap closed, or access already in hand — stop asking
                    _retire_ask(seed)
                    _retire_ask(seed_verify)
            except Exception as e:  # noqa: BLE001 — seeding must never kill the ledger
                attention.append(f"{slug}: domain-access ask seeding failed "
                                 f"({str(e)[:80]})")

        # ---- two stage-blocker watchdogs (2026-08-10, Build Stages board) --
        # Both are "board column with no ask generator" gaps the Kanban
        # exposed. Visibility only — the fulfilment is agent/human work.
        #
        # (1) Customer list received but never LOADED into review_requests:
        # Rudy uploaded LSR_CUSTOMER_LIST.csv on 08-03 and nothing ingested it
        # — the reviews pipeline read as "no list" while the client had done
        # their part. Same invisibility class as the unlaunched-site gap.
        try:
            docs_notes = _sb("GET", "/rest/v1/marketing_ops_notes"
                             f"?company_id=eq.{cid}&body=ilike.*customer*list*"
                             "&select=id&limit=1") or []
            if docs_notes:
                reqs = _sb("GET", "/rest/v1/review_requests"
                           f"?company_id=eq.{cid}&select=id&limit=1") or []
                if not reqs:
                    attention.append(
                        f"{slug}: customer list UPLOADED but never loaded into "
                        "review_requests — ingest it and launch the reactivation "
                        "campaign (sender per 08-03 policy)")
        except Exception:  # noqa: BLE001
            pass
        #
        # (2) Google connected but NO listing synced (TRG: account holds two
        # listings, none selected; MCC: account holds zero). Every GBP system
        # silently skips these clients.
        try:
            g_active = _sb("GET", "/rest/v1/user_integrations"
                           f"?client_id=eq.{cid}&provider=eq.google&status=eq.active"
                           "&select=id&limit=1") or []
            if g_active:
                gprof = _sb("GET", "/rest/v1/marketing_gbp_profiles"
                            f"?company_id=eq.{cid}&select=id&limit=1") or []
                if not gprof:
                    attention.append(
                        f"{slug}: Google CONNECTED but no GBP listing synced — "
                        "account has either zero listings (create+verify one) or "
                        "several (a selection is needed); every GBP system is "
                        "skipping this client meanwhile")
        except Exception:  # noqa: BLE001
            pass

        # ---- gsc-indexnow (auto-heal once per live site) -------------------
        if live:
            existing = _sb("GET", "/rest/v1/marketing_setup_ledger"
                           f"?company_id=eq.{cid}&item_key=eq.gsc-indexnow&select=status",
                           prefer="return=representation") or []
            if not existing or existing[0].get("status") != "done":
                note = "dry-run" if dry_run else _gsc_heal(domain, slug)
                rows.append({"company_id": cid, "item_key": "gsc-indexnow", "kind": "auto",
                             "status": "done" if not dry_run else "open",
                             "title": "Registered the live site with Google Search Console",
                             "detail": note, "evidence": {"domain": domain}})
                attention.append(f"{slug}: gsc/indexnow auto-heal -> {note}")

        # ---- content-queue watchdog (visibility only, 2026-08-09) ----------
        # Crew went LIVE with 1 seed item in content-queue.json and nobody
        # noticed until Santino asked; 13 clients were in the same state.
        # Queue-filling is agent work (rank-ai-keyword-researcher), so this
        # never auto-heals — it makes the gap impossible to miss in the
        # digest's attention list for LIVE sites only.
        if live:
            try:
                import json as _json
                qp = ROOT / "clients" / slug / "content-queue.json"
                q = _json.loads(qp.read_text()) if qp.exists() else []
                items = q if isinstance(q, list) else (q.get("items") or [])
                unwritten = [i for i in items if not (
                    i.get("written") or str(i.get("status")) == "written")]
                if len(unwritten) <= 1:
                    attention.append(
                        f"{slug}: LIVE with an empty content queue "
                        f"({len(unwritten)} unwritten) — run the keyword "
                        f"researcher (System 1) to fill it")
            except Exception:  # noqa: BLE001 — watchdog never kills the ledger
                pass

        # ---- google-connected (reflect only) -------------------------------
        gi = _sb("GET", f"/rest/v1/user_integrations?client_id=eq.{cid}"
                 "&provider=eq.google&select=id", prefer="return=representation") or []
        rows.append({"company_id": cid, "item_key": "google-connected", "kind": "client_owed",
                     "status": "done" if gi else "open",
                     "title": ("Google account connected" if gi else
                               f"{owner} has not connected his Google account yet"),
                     "detail": None if gi else
                     f"Until {owner} clicks one link, we cannot touch their Google "
                     "Business Profile, reviews or rankings. Monica is texting "
                     "him this link until it's done: "
                     f"https://restorationai.io/connect/{slug}",
                     "evidence": {}})

        # ---- gbp-verified (Voice of Merchant) --------------------------------
        # Why (2026-08-01): "connected" != "verified". QCI + Paul Davis sat
        # invisible to Bing's GBP import (and most GBP features) because their
        # listings are unverified, and nothing surfaced it as its own card —
        # QCI's verification video was even rejected 07-30. Go Green's
        # suspension also shows here (complyWithGuidelines). Distinct card so
        # verification gaps never hide inside the citations rollup.
        vom_state = None   # verified | suspended | pending | unverified
        try:
            if gi:
                import gbp as _gbp
                _tok = _gbp.get_access_token(cid)
                _place = _gbp._place_id_from_connection(cid)
                _loc = _gbp.find_location(_tok, _place) if _tok and _place else None
                if _tok and _loc:
                    _ln = _loc["name"] if _loc["name"].startswith("locations/") \
                        else "locations/" + _loc["name"].split("locations/")[-1]
                    _vr = requests.get(
                        "https://mybusinessverifications.googleapis.com/v1/"
                        f"{_ln}/VoiceOfMerchantState",
                        headers={"Authorization": f"Bearer {_tok}"}, timeout=30)
                    if _vr.ok:
                        vom = _vr.json()
                        if vom.get("hasVoiceOfMerchant"):
                            vom_state = "verified"
                            rows.append({"company_id": cid, "item_key": "gbp-verified",
                                         "kind": "auto", "status": "done",
                                         "title": "Google has verified their Business Profile",
                                         "detail": None, "evidence": {}})
                        elif "complyWithGuidelines" in vom:
                            _why = (vom["complyWithGuidelines"] or {}).get(
                                "recommendationReason", "SUSPENDED")
                            vom_state = "suspended"
                            rows.append({"company_id": cid, "item_key": "gbp-verified",
                                         "kind": "us_owed", "status": "open",
                                         "title": "Google SUSPENDED their Business "
                                                  "Profile — file the appeal",
                                         "detail": "Google disabled the listing "
                                                   f"({_why}). It is NOT publicly "
                                                   "visible; posts/photos/reviews all "
                                                   "blocked until reinstated. Appeal at "
                                                   "support.google.com/business — get "
                                                   "Google's suspension email from the "
                                                   "client first (date + violation).",
                                         "evidence": {"reason": _why}})
                            attention.append(f"{slug}: GBP SUSPENDED ({_why}) — "
                                             "reinstatement appeal needed")
                        else:
                            _pend = bool((vom.get("verify") or {})
                                         .get("hasPendingVerification"))
                            vom_state = "pending" if _pend else "unverified"
                            rows.append({"company_id": cid, "item_key": "gbp-verified",
                                         "kind": "client_owed", "status": "open",
                                         "title": ("Google has not verified their "
                                                   "listing — it is invisible on Maps"
                                                   + (" (a verification is with "
                                                      "Google right now)"
                                                      if _pend else "")),
                                         "detail": "Google hasn't verified the listing, "
                                                   "so it's invisible on Maps and to "
                                                   "Bing's import. The OWNER completes "
                                                   "verification (usually a video walk-"
                                                   "through) at business.google.com — "
                                                   "Monica can walk them through it."
                                                   + (" A verification is already "
                                                      "submitted and awaiting Google."
                                                      if _pend else ""),
                                         "evidence": {"pending": _pend}})
        except Exception:
            pass

        # GBP-VERIFICATION ASK (Santino 2026-08-03: top messaging priority,
        # paired with the domain ask when both are open — the launch-blocker
        # pair; QCI sat unverified with Monica never asking). unverified ->
        # seed the rank-1 client_input ask; verified/suspended/pending ->
        # retire it (suspended goes through the reinstatement appeal;
        # pending is already with Google — nothing for the client to do).
        try:
            from client_ops_sync import action_key, insert_plan_row
            vseed = f"gbp-verify-{slug}"
            if vom_state == "unverified":
                if insert_plan_row(
                        cid, slug, vseed,
                        title=f"ASK CLIENT: {owner} needs to verify their "
                              "Google listing — it is invisible on Maps "
                              "until then",
                        rationale=(
                            "Google has NOT verified their Business Profile: "
                            "the listing is invisible on Maps and to Bing's "
                            "import — a LAUNCH BLOCKER on par with domain "
                            "access (top messaging priority, Santino "
                            "2026-08-03). The OWNER completes verification, "
                            "usually a short video walk-through, at "
                            "business.google.com. MONICA: plain words, no "
                            "jargon; offer to hop on a quick 15-minute call "
                            "and do the video walk-through together, we "
                            "guide, they hold their own phone on a VIDEO call, nobody visits them. When the "
                            "domain-access ask is also open, bundle EXACTLY "
                            "these two in one message (the launch-blocker "
                            "pair exception) with one shared call offer."),
                        action_type="client_input", target=None,
                        impact="high", effort="low", dry_run=dry_run):
                    attention.append(f"{slug}: seeded Monica ask — GBP "
                                     "verification (launch blocker)")
            elif vom_state in ("verified", "suspended", "pending") and not dry_run:
                _sb("PATCH", "/rest/v1/marketing_action_plan"
                    f"?company_id=eq.{cid}"
                    f"&action_key=eq.{action_key(cid, vseed)}"
                    "&status=eq.planned", {"status": "resolved"})
        except Exception as e:  # noqa: BLE001 — seeding must never kill the ledger
            attention.append(f"{slug}: gbp-verify ask seeding failed "
                             f"({str(e)[:80]})")

        # PREVIEW-SHARE HEAL (Santino 2026-08-03: HomeLyft's polished site
        # sat unshared — the share seeding only lived in the site-build CI
        # write-back, which local builds skip). preview_ready/pushed_staging
        # + no share ask EVER + no open hold note -> seed the ask here, so
        # this class of miss can't recur whatever built the site.
        try:
            _site = _sb("GET", f"/rest/v1/marketing_sites?company_id=eq.{cid}"
                        "&select=build_status,cloudflare_pages_url,"
                        "scaffolded_at,last_pushed_staging_at,apex_live&limit=1",
                        prefer="return=representation") or []
            _site = _site[0] if _site else {}
            # apex_live AUTO-HEAL (Santino 2026-09-11: QCI + California
            # Restoration West served our build for days with apex_live
            # stuck false, so stages, previews and launch logic downstream
            # all lied). `live` was computed above by _site_serves_us —
            # that serve check IS the evidence; no click, no claim.
            if live and not _site.get("apex_live"):
                try:
                    if not dry_run:
                        _sb("PATCH", "/rest/v1/marketing_sites"
                            f"?company_id=eq.{cid}", {"apex_live": True})
                    _site["apex_live"] = True
                    attention.append(f"{slug}: apex_live healed -> true "
                                     "(domain serves our build)")
                except Exception:  # noqa: BLE001 — heal must never kill the ledger
                    pass
            # PERCEPTION WINDOW (Santino 2026-09-03, Kenny/Veterans pilot):
            # the reveal waits 7 days from the first staging push, so the
            # brand pass finishes and the build reads as crafted, not
            # instant. An open note matching "share now|release early"
            # overrides; Santino's dated holds still extend it the other way.
            import datetime as _dtmod
            # STABLE ANCHOR (2026-09-20): staging pushes re-stamp
            # last_pushed_staging_at on every redeploy, resetting this
            # window (the FIX/DryCor clock bug). scaffolded_at is the
            # immutable first-build moment — prefer it.
            _staged = str(_site.get("scaffolded_at")
                          or _site.get("last_pushed_staging_at") or "")[:10]
            _in_window = False
            if _staged and not _site.get("apex_live"):
                try:
                    _age = (_dtmod.date.today()
                            - _dtmod.date.fromisoformat(_staged)).days
                    # keep in sync with client_concierge.PREVIEW_SOAK_DAYS
                    _in_window = _age < 10
                except ValueError:
                    pass
                # Drip-aware (2026-09-04): the reveal waits for the LATER of
                # day 7 and the finishing pass (all pages rendered, images,
                # colors). A 12-day build reveals at day 12, not day 7 with a
                # placeholder long tail. "share now" still overrides both.
                if not _in_window and _site_unfinished_bits(slug):
                    _in_window = True
            if _in_window:
                _release = any(
                    re.search(r"share\s+now|release\s+early|reveal\s+now",
                              str(n.get("body", "")), re.I)
                    for n in _sb("GET", "/rest/v1/marketing_ops_notes"
                                 f"?company_id=eq.{cid}&status=eq.open"
                                 "&select=body&limit=20",
                                 prefer="return=representation") or [])
                if not _release:
                    attention.append(
                        f"{slug}: site in the 10-day perception window "
                        f"(staged {_staged}) — preview reveal holds until "
                        "day 10; note 'share now' to release early")
            # pushed_main included 2026-09-11 (DryCor: a site pushed through
            # to the production pages.dev — but not cut over — sat with NO
            # preview reveal for 10 days because this gate only knew the
            # staging states; any built-not-live state must qualify)
            if (not _in_window and not _site.get("apex_live")
                    and _site.get("build_status") in ("preview_ready",
                                                      "pushed_staging",
                                                      "pushed_main")):
                fb_key = f"site-preview-feedback-{slug}"
                _ever = _sb("GET", "/rest/v1/marketing_action_plan"
                            f"?company_id=eq.{cid}&action_key=eq.{fb_key}"
                            "&select=id&limit=1",
                            prefer="return=representation") or []
                _hold = any(
                    re.search(r"(hold|don'?t share|defect)", str(n.get("body", "")), re.I)
                    and re.search(r"preview|site", str(n.get("body", "")), re.I)
                    for n in _sb("GET", "/rest/v1/marketing_ops_notes"
                                 f"?company_id=eq.{cid}&status=eq.open"
                                 "&select=body&limit=20",
                                 prefer="return=representation") or [])
                if not _ever and not _hold:
                    _preview = (_site.get("cloudflare_pages_url")
                                or f"https://staging.rankai-{slug}.pages.dev")
                    if not dry_run:
                        _sb("POST", "/rest/v1/marketing_action_plan", [{
                            "company_id": cid, "rank_ai_slug": slug,
                            "action_key": fb_key,
                            "action_type": "client_input", "status": "planned",
                            "priority": 1, "impact": "high", "effort": "low",
                            "title": "Take a look at your new website preview "
                                     "and tell us your thoughts",
                            "target": _preview,
                            "rationale": "New site build finished at " + _preview +
                                         " — SHOW IT TO THEM. Send that exact link, "
                                         "ask what they think, collect change "
                                         "requests. A client who has never seen "
                                         "their finished site gets this BEFORE any "
                                         "other ask (Santino 2026-08-04, Reign)."}])
                    attention.append(f"{slug}: preview ready but the share ask "
                                     f"was never seeded — HEALED ({_preview})")
        except Exception as e:  # noqa: BLE001 — healing must never kill the ledger
            attention.append(f"{slug}: preview-share heal failed ({str(e)[:80]})")

        # ---- client-asks aggregate (ladder input) ---------------------------
        asks = _sb("GET", "/rest/v1/marketing_action_plan"
                   f"?company_id=eq.{cid}&action_type=eq.client_input&status=eq.planned"
                   "&select=action_key,title", prefer="return=representation") or []
        ask_titles = [re.sub(r"^ASK (CLIENT: )?", "", (a.get("title") or "").strip())
                      for a in asks]
        rows.append({"company_id": cid, "item_key": "client-asks", "kind": "client_owed",
                     "status": "open" if asks else "done",
                     "title": (f"Waiting on {owner} for {len(asks)} thing"
                               f"{'s' if len(asks) != 1 else ''}" if asks
                               else f"Nothing outstanding from {owner}"),
                     "detail": ("They've stopped answering texts on this many items — "
                                "Monica's next message proposes a 15-minute call to knock "
                                "them all out at once, with a checklist picture attached."
                                if len(asks) >= 4 else None),
                     "evidence": {"count": len(asks), "titles": ask_titles[:10]}})
        if len(asks) >= 4:
            attention.append(f"{slug}: {len(asks)} open client asks — propose a setup call (ladder)")

        _map_and_video_rows(cid, slug, gi, rows, attention, _HEALS, dry_run,
                            owner)

        # ---- DATA FRESHNESS (Santino 2026-07-28: "I don't want to have to
        # always check every day"). The tabs must stay alive on their own:
        #   geo-grid   newest scan > 8 days old, imageless, or city config
        #              drifted (1 city configured vs 4+ service areas) ->
        #              AUTO re-scan (capped per run); config drift -> attention
        #   photos     google connected but no imported GBP media -> AUTO import
        # Heals are capped so one bad night can't burn budget.
        try:
            if (CLIENTS_DIR / slug / "geogrid-cities.json").exists():
                gg_cities = json.loads(
                    (CLIENTS_DIR / slug / "geogrid-cities.json").read_text())
                n_areas = len(json.loads((CLIENTS_DIR / slug / "plan-input.json")
                                         .read_text()).get("service_areas") or []) \
                    if (CLIENTS_DIR / slug / "plan-input.json").exists() else 0
                newest = _sb("GET", "/rest/v1/marketing_geogrid_scans"
                             f"?company_id=eq.{cid}&select=scanned_at,image_url"
                             "&order=scanned_at.desc&limit=1",
                             prefer="return=representation") or []
                age_days = 999
                has_img = False
                if newest:
                    try:
                        age_days = (datetime.now(timezone.utc) - datetime.fromisoformat(
                            newest[0]["scanned_at"].replace("Z", "+00:00"))).days
                    except (ValueError, KeyError):
                        pass
                    has_img = bool(newest[0].get("image_url"))
                drift = len(gg_cities) <= 1 and n_areas >= 4
                stale = age_days > 8 or not has_img
                if drift:
                    attention.append(f"{slug}: geo-grid config drift — {len(gg_cities)} "
                                     f"city configured vs {n_areas} service areas (reseed the ring)")
                if stale and not drift and not dry_run and _HEALS["geogrid"] > 0:
                    _HEALS["geogrid"] -= 1
                    subprocess.Popen([sys.executable,
                                      str(ROOT / "scripts" / "geogrid_cron.py"),
                                      "--slug", slug])
                    attention.append(f"{slug}: geo-grid stale ({age_days}d"
                                     + ("" if has_img else ", no image") + ") — re-scan started")
                rows_fresh = {"company_id": cid, "item_key": "data-fresh", "kind": "auto",
                              "status": "open" if (stale or drift) else "done",
                              "title": "Map ranking data is up to date",
                              "detail": (f"Newest map scan is {age_days} day(s) old"
                                         + ("" if has_img else " and has no map image")
                                         + ("; city ring needs reseeding" if drift else "")
                                         if (stale or drift) else None),
                              "evidence": {"age_days": age_days, "image": has_img,
                                           "cities": len(gg_cities), "areas": n_areas}}
                _upsert([rows_fresh], dry_run)
        except Exception:
            pass
        try:
            gi_google = bool(gi)
            if gi_google and not dry_run and _HEALS["media"] > 0:
                sb_url = os.environ["SUPABASE_URL"].rstrip("/")
                sb_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
                r = requests.post(f"{sb_url}/storage/v1/object/list/branding",
                                  headers={"apikey": sb_key,
                                           "Authorization": f"Bearer {sb_key}"},
                                  json={"prefix": f"{cid}/job-photos/posted/",
                                        "limit": 3}, timeout=30)
                have_media = any(isinstance(f, dict) and f.get("id") for f in (r.json() or []))
                if not have_media:
                    _HEALS["media"] -= 1
                    subprocess.run([sys.executable, str(ROOT / "scripts" / "gbp.py"),
                                    "media-import", "--slug", slug],
                                   capture_output=True, text=True, timeout=600)
                    attention.append(f"{slug}: GBP photo library imported (Photos tab was empty)")
        except Exception:
            pass

        # ---- CALL TRACKING (Santino 2026-07-28: "fully automated... least
        # amount of human touch"). Auto-provisions a county-local tracking
        # number (gbp source) for every Rank AI client that lacks one, capped
        # per run. The GBP phone SWAP auto-runs only when AUTO_PHONE_SWAP=1
        # (flipped on once the pilot numbers pass Santino's test call);
        # until then the swap stays one command: gbp.py set-phone --slug X.
        try:
            ct = (ints.get("call_tracking") or {})
            has_number = bool((ct.get("gbp") or {}).get("number"))
            if not has_number and not dry_run and _HEALS.get("calltrack", 0) > 0:
                _HEALS["calltrack"] -= 1
                r = subprocess.run([sys.executable,
                                    str(ROOT / "scripts" / "call_tracking.py"),
                                    "provision", "--slug", slug, "--source", "gbp"],
                                   capture_output=True, text=True, timeout=120)
                line = (r.stdout or r.stderr or "").strip().splitlines()[-1:]
                attention.append(f"{slug}: call tracking -> {line[0][:110] if line else 'no output'}")
                has_number = "provisioned" in (line[0] if line else "")
            # The FULL standard source set provisions in the same heal
            # (Santino 2026-09-16: new signups were only getting gbp +
            # website — Desert Valley/Flood&Fire/Go Green/Heritage/Paul
            # Davis all landed with 2 of 7 — while the rest of the fleet
            # had the complete set from the 08-24 rollout). Order matters:
            # website first (the site DNI default), then the ad/AI
            # channels. Site WIRING (brand.ts + DNI script + deploy)
            # stays with site_call_tracking.py / the build pipeline.
            if has_number and not dry_run:
                # google_ads is CONDITIONAL (Santino 2026-09-16: most
                # restoration clients never run ads — the number only ever
                # displays to ad-click visitors, so for a no-ads client
                # it's pure idle spend). Provision it only when there is
                # real ads evidence: an LSA/Ads detection stamp or a
                # google_ads_customer_id in the client record.
                _crec = _client_record(slug)
                ads_evidence = bool(
                    ints.get("lsa")
                    or (_crec.get("brand") or {}).get("google_ads_customer_id")
                    or _crec.get("google_ads_customer_id")
                    or (ROOT / "clients" / slug / "ads-journal.md").exists())
                for src in ("website", "google_ads", "yelp", "chatgpt",
                            "gemini", "bing"):
                    if src == "google_ads" and not ads_evidence:
                        continue
                    if (ct.get(src) or {}).get("number"):
                        continue
                    if _HEALS.get("calltrack", 0) <= 0:
                        break
                    _HEALS["calltrack"] -= 1
                    r = subprocess.run([sys.executable,
                                        str(ROOT / "scripts" / "call_tracking.py"),
                                        "provision", "--slug", slug,
                                        "--source", src],
                                       capture_output=True, text=True,
                                       timeout=120)
                    line = (r.stdout or r.stderr or "").strip().splitlines()[-1:]
                    attention.append(f"{slug}: {src} call tracking -> "
                                     f"{line[0][:110] if line else 'no output'}")
            # The GBP phone SWAP is NEVER automatic (Santino 2026-07-28: "a
            # human overseeing and confirming the push live for every single
            # client"). The human clicks "Approve phone swap" on the client's
            # Ops Attention card, which drops an [APPROVE-PHONE-SWAP] ops
            # note; this executor performs the swap on the next pass and
            # resolves the note. No approval note -> nothing happens, ever.
            swapped = bool((ct.get("gbp") or {}).get("gbp_swapped_at"))
            if has_number and not swapped:
                approvals = _sb("GET", "/rest/v1/marketing_ops_notes"
                                f"?company_id=eq.{cid}&status=eq.open"
                                "&body=like.*%5BAPPROVE-PHONE-SWAP%5D*&select=id",
                                prefer="return=representation") or []
                if approvals and not dry_run:
                    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "gbp.py"),
                                        "set-phone", "--slug", slug],
                                       capture_output=True, text=True, timeout=300)
                    line = (r.stdout or r.stderr or "").strip().splitlines()[-1:]
                    ok = bool(line and "->" in line[0])
                    if ok:
                        co2 = _sb("GET", f"/rest/v1/companies?id=eq.{cid}"
                                  "&select=integration_settings",
                                  prefer="return=representation") or [{}]
                        i2 = co2[0].get("integration_settings") or {}
                        if isinstance(i2, str):
                            i2 = json.loads(i2)
                        i2.setdefault("call_tracking", {}).setdefault("gbp", {})[
                            "gbp_swapped_at"] = datetime.now(timezone.utc).isoformat()
                        _sb("PATCH", f"/rest/v1/companies?id=eq.{cid}",
                            {"integration_settings": i2})
                        for ap in approvals:
                            _sb("PATCH", f"/rest/v1/marketing_ops_notes?id=eq.{ap['id']}",
                                {"status": "resolved",
                                 "resolved_at": datetime.now(timezone.utc).isoformat()})
                        swapped = True
                    attention.append(f"{slug}: APPROVED phone swap executed -> "
                                     f"{line[0][:100] if line else 'no output'}")
                else:
                    attention.append(f"{slug}: tracking number "
                                     f"{ct.get('gbp', {}).get('number', '?')} ready — "
                                     "awaiting your 'Approve phone swap' click in Ops Attention")
            rows.append({"company_id": cid, "item_key": "call-tracking", "kind": "auto",
                         "status": "done" if has_number else "open",
                         "title": ("Call tracking live: " + ct.get("gbp", {}).get("number", "")
                                   if has_number else "Call tracking number pending"),
                         "detail": None if has_number else
                         "A county-local tracking number gets provisioned automatically "
                         "on the next ops pass.",
                         "evidence": {"gbp_number": ct.get("gbp", {}).get("number"),
                                      "swapped": swapped}})
        except Exception:
            pass

        # ---- CITATIONS discovery/NAP audit (Santino 2026-07-28, priority):
        # auto-discovers each client's directory listings, prepopulates the
        # Connect tab slots, and flags phone discrepancies. Re-audits monthly.
        platform_status: dict = {}  # readiness pass below reads this
        try:
            cit = _sb("GET", f"/rest/v1/user_integrations?client_id=eq.{cid}"
                      "&provider=eq.citations&select=connection_metadata",
                      prefer="return=representation") or []
            napa = ((cit[0].get("connection_metadata") or {}).get("nap_audit")
                    if cit else None) or {}
            newest_chk = max((v.get("checked_at") or "" for v in napa.values()),
                             default="")
            stale_c = True
            if newest_chk:
                try:
                    stale_c = (datetime.now(timezone.utc) - datetime.fromisoformat(
                        newest_chk.replace("Z", "+00:00"))).days > 30
                except ValueError:
                    pass
            if stale_c and not dry_run and _HEALS.get("citations", 0) > 0:
                _HEALS["citations"] -= 1
                r = subprocess.run([sys.executable,
                                    str(ROOT / "scripts" / "citations_audit.py"),
                                    "--slug", slug],
                                   capture_output=True, text=True, timeout=600)
                tail_ = (r.stdout or r.stderr or "").strip().splitlines()[-1:]
                attention.append(f"{slug}: citations audit -> {tail_[0][:110] if tail_ else 'no output'}")
                cit = _sb("GET", f"/rest/v1/user_integrations?client_id=eq.{cid}"
                          "&provider=eq.citations&select=connection_metadata",
                          prefer="return=representation") or []
                napa = ((cit[0].get("connection_metadata") or {}).get("nap_audit")
                        if cit else None) or {}
            # 'google_listing' is the client's own GBP (first-class audit
            # source, Santino 2026-08-03) — not a directory, so it stays out
            # of the found/missing/wrong-phone counts; its mismatch gets its
            # own attention line below instead.
            n_found = sum(1 for k, v in napa.items()
                          if v.get("status") in ("found", "discrepancy")
                          and k != "google_listing")
            n_disc = sum(1 for k, v in napa.items()
                         if v.get("status") == "discrepancy"
                         and k != "google_listing")
            # A missing HomeAdvisor is not a gap — there's no free listing to
            # create (paid lead-gen only). Existing ones still get NAP-checked.
            n_missing = sum(1 for k, v in napa.items()
                            if v.get("status") == "missing"
                            and k not in ("homeadvisor", "google_listing"))
            if napa:
                # Split the missing listings by who can create them:
                #   us    — Bing Places (imports from their GBP, which we hold),
                #           Apple Maps (Business Connect agency claim), BBB (form)
                #   client — platforms that require the OWNER's identity / phone
                #           verification (Thumbtack, Angi free claim), plus
                #           Facebook (personal account) and Yelp claiming.
                # HomeAdvisor is EXCLUDED (Santino 2026-07-31): no free listing
                # exists — it's ~$300/yr membership + $15-100/lead. Never send
                # a client to sign up there as a "citation". Angi stays because
                # the basic profile claim is free (Angi Ads/Leads are not — the
                # claim ask must never morph into an Ads signup).
                _missing = {k for k, v in napa.items() if v.get("status") == "missing"}
                _lbl = {"bing_places": "Bing Places", "apple_maps": "Apple Maps",
                        "bbb": "BBB", "thumbtack": "Thumbtack",
                        "angi": "Angi (free claim only — never Angi Ads/Leads)",
                        "facebook": "Facebook", "yelp": "Yelp",
                        "expertise": "Expertise.com application",
                        "houzz": "Houzz", "porch": "Porch",
                        "homeguide": "HomeGuide", "nextdoor": "Nextdoor",
                        "yellowpages": "YellowPages"}
                # Split mirrors the app's owner badges: us = no owner identity
                # needed; client = owner claim / phone verification required.
                # Porch removed from us_create 2026-08-02: recon found Porch
                # killed self-serve pro signup entirely (insurance pivot; all
                # signup URLs 404, listing requires contacting Pro Support) —
                # a card must never demand an impossible action. Presence on
                # Porch is still AUDITED; legacy listings just can't be built.
                client_create = [_lbl[k] for k in ("yelp", "facebook", "thumbtack",
                                                   "angi", "nextdoor", "yellowpages")
                                 if k in _missing]
                # Per-platform checklist state (Santino 2026-08-02): the app
                # renders citations-build from evidence.platform_status.
                agent_subs = _agent_submitted_platforms(cid)
                platform_status = {}
                for plat in _US_CREATE_PLATFORMS:
                    _pst = (napa.get(plat) or {}).get("status")
                    if _pst in ("found", "discrepancy"):
                        # a discrepancy listing still EXISTS — never re-create;
                        # the wrong phone is tracked on the citations card
                        _state = "live"
                    elif plat == "bing_places":
                        # Bing answers for itself: the nightly dashboard read
                        # knows published vs pending vs absent, and the
                        # citations audit never will (Bing Maps listings are
                        # not discoverable the way it searches).
                        _state = _bing_state(cid, co.get("name") or "", slug, bing)
                    elif plat in agent_subs:
                        _state = "submitted_pending"
                    else:
                        _state = "todo"
                    platform_status[plat] = {"status": _state,
                                             "label": _ps_label(plat, _state)}
                # The card's outstanding list is now derived from the SAME
                # truth as the checklist. It used to come straight from the
                # citations audit's `missing` set, which is why Crew — live on
                # Bing since before 08-01 — kept being told we owed them a
                # Bing listing. Anything still todo or pending stays visible;
                # only 'live' drops off.
                us_create = [_lbl[k] for k in _US_CREATE_PLATFORMS
                             if platform_status[k]["status"] != "live"]
                if dry_run:
                    print(f"  [citations-build] {slug}: " + ", ".join(
                        f"{k}={v['status']}" for k, v in platform_status.items()))
                # Say WHAT'S NEEDED, not what a scan counted (Santino
                # 2026-08-05: "Directory listings: 3 found, 0 wrong phone, 10
                # missing" told him nothing — the headline names the person,
                # the action and the listings; the counts move to the detail).
                if client_create:
                    _c_title = (f"{owner} needs to create {len(client_create)} "
                                f"listing{'s' if len(client_create) != 1 else ''}: "
                                + ", ".join(client_create))
                elif n_disc:
                    _c_title = (f"{n_disc} directory listing"
                                f"{'s' if n_disc != 1 else ''} show the wrong "
                                "phone number — fix them")
                else:
                    _c_title = "Directory listings: nothing needed from the client"
                _c_detail = ""
                if client_create:
                    _c_detail = ("Each of these needs the owner's own identity to "
                                 "sign up (phone or email verification), so we "
                                 f"cannot do them for {owner} — Monica has the "
                                 "ask. ")
                if n_disc:
                    _c_detail += (f"{n_disc} existing listing"
                                  f"{'s' if n_disc != 1 else ''} show a phone "
                                  "number that doesn't match the Business "
                                  "Information card; we fix those ourselves. ")
                _c_detail += (f"Directory check: {n_found} listing(s) found, "
                              f"{n_missing} still missing across the "
                              "directories we track.")
                rows.append({"company_id": cid, "item_key": "citations", "kind": "client_owed",
                             "status": "open" if (n_disc or client_create) else "done",
                             "title": _c_title,
                             "detail": _c_detail or None,
                             "evidence": {"found": n_found, "discrepancies": n_disc,
                                          "missing": n_missing,
                                          "client_creates": client_create}})
                if us_create:
                    # Santino 2026-08-01 (corrected): these STAY visible until
                    # actually finished — the browser agent works them and marks
                    # each done only after verified completion, so a human can
                    # always see what's outstanding and catch breakage.
                    _bing_st = platform_status["bing_places"]["status"]
                    if _bing_st == "live":
                        # Bing is done — the card must not keep explaining it.
                        _bing_line = ""
                    elif _bing_st == "submitted_pending":
                        _bing_line = ("Bing Places already has their listing "
                                      "imported from their Google profile and "
                                      "is publishing it on its own queue "
                                      "(7-12 days from import, nothing to "
                                      "action); ")
                    elif slug in _gbp_managers:
                        _bing_line = ("Bing Places imports straight from their "
                                      "GBP (we hold manager access); ")
                    else:
                        # Never claim access we do not have — this is the
                        # actual reason a client never reaches Bing.
                        _bing_line = ("Bing Places imports from their Google "
                                      "profile, and we are NOT a manager on it "
                                      "yet — the owner has to add "
                                      "contact@restorationai.io before Bing "
                                      "can see them; ")
                    rows.append({"company_id": cid, "item_key": "citations-build",
                                 "kind": "us_owed", "status": "open",
                                 "title": f"We create {len(us_create)} listing"
                                          f"{'s' if len(us_create) != 1 else ''} "
                                          f"for them: {', '.join(us_create)}",
                                 "detail": _bing_line
                                           + "Apple Maps via Business "
                                           "Connect agency claim; BBB via their request "
                                           "form. Always the Business Information card "
                                           "NAP with the REAL phone number. The browser "
                                           "agent works these; done = verified complete.",
                                 "evidence": {"platforms": us_create,
                                              "queued_for_agent": True,
                                              "gbp_manager_access": slug in _gbp_managers,
                                              "platform_status": platform_status}})
                else:
                    rows.append({"company_id": cid, "item_key": "citations-build",
                                 "kind": "us_owed", "status": "done",
                                 "title": "Every listing we create ourselves is done",
                                 "detail": None,
                                 "evidence": {"platform_status": platform_status}})
                if n_disc:
                    attention.append(f"{slug}: {n_disc} directory listing(s) show a WRONG "
                                     "phone — fix against the canonical card")
                if (napa.get("google_listing") or {}).get("status") == "discrepancy":
                    attention.append(f"{slug}: GOOGLE LISTING NAP differs from the "
                                     "Business Information card — TOP fix (the "
                                     "citations analysis top-line has the details)")
        except Exception:
            pass

        # ---- CITATIONS READINESS (Santino 2026-08-03 follow-up): the queue's
        # skip reasons (no logo / empty NAP) become auto-heals or visible work.
        try:
            _citations_readiness(cid, slug, co, platform_status, dry_run,
                                 rows, attention, owner)
        except Exception as e:  # noqa: BLE001 — readiness must never kill the ledger
            attention.append(f"{slug}: citations-readiness pass failed "
                             f"({str(e)[:80]})")

        # ---- LSA follow-THROUGH (Santino 2026-07-30): a "Yes, wants LSA"
        # click in Ops Attention must surface the setup work, not vanish.
        # Santino runs LSA setup personally — us_owed, never a Monica ask.
        try:
            li = (ints.get("lsa_intent") or {}) if isinstance(ints, dict) else {}
            if not isinstance(li, dict):
                li = {}   # legacy plain-string lsa_intent (e.g. Crew) — no dict fields to read
            lsa_done = bool((ints.get("lsa") or {}).get("setup_done")
                            or (ints.get("lsa") or {}).get("customer_id"))
            if li.get("answer") == "yes" and not lsa_done:
                rows.append({"company_id": cid, "item_key": "lsa-setup",
                             "kind": "us_owed", "status": "open",
                             "title": "They said yes to Local Services Ads — nobody has started the setup",
                             "detail": "Santino runs this conversation personally "
                                       f"(marked YES {str(li.get('decided_at') or '')[:10]}). "
                                       "Mark integration_settings.lsa.setup_done when live.",
                             "evidence": {"decided_at": li.get("decided_at")}})
            elif li.get("answer") == "yes" and lsa_done:
                rows.append({"company_id": cid, "item_key": "lsa-setup",
                             "kind": "us_owed", "status": "done",
                             "title": "Local Services Ads are set up",
                             "detail": None, "evidence": {}})
        except Exception:
            pass

        # ---- Client hub document uploads -> Today (persists until Done)
        try:
            _check_doc_uploads(cid, co.get("name") or slug, dry_run)
        except Exception:
            pass

        # ---- Open AI-optimization recommendations (Santino 2026-07-30):
        # "open unanswered optimization recommendations should count as a
        # to-do needed by us." Every open suggestion the optimizer parked
        # (services/categories/pages/description/hours) stays on OUR board
        # until it's applied or dismissed in Locations -> AI optimization.
        # KEEP verdicts are informational ("looks good"), not to-dos.
        try:
            sugs = _sb("GET", f"/rest/v1/marketing_gbp_suggestions?company_id=eq.{cid}"
                       "&status=eq.open&verdict=neq.KEEP&select=item_type") or []
            if sugs:
                by_type = Counter(s.get("item_type") or "?" for s in sugs)
                breakdown = ", ".join(f"{n} {t}" for t, n in sorted(by_type.items()))
                rows.append({"company_id": cid, "item_key": "gbp-suggestions",
                             "kind": "us_owed", "status": "open",
                             "title": f"{len(sugs)} suggested change"
                                      f"{'s' if len(sugs) != 1 else ''} to their Google "
                                      "listing need your yes or no",
                             "detail": f"Locations -> AI optimization ({breakdown}). "
                                       "Apply or dismiss each — open recommendations "
                                       "are our to-do, not background noise.",
                             "evidence": {"open": len(sugs), "by_type": dict(by_type)}})
            else:
                rows.append({"company_id": cid, "item_key": "gbp-suggestions",
                             "kind": "us_owed", "status": "done",
                             "title": "No Google listing changes waiting on a decision",
                             "detail": None, "evidence": {}})
        except Exception:
            pass

        # ---- Site imagery completeness (2026-07-31): per-service images
        # were manual agent work, so unfinished sites shipped with every
        # service card on the shared services.webp fallback (Coastal: all 12).
        # Complete = image on disk AND registered in image-meta.json —
        # serviceImage() only resolves registered images, so an unregistered
        # file still renders the fallback.
        try:
            svc_dir = SITES_DIR / slug / "src" / "content" / "services"
            if built and svc_dir.is_dir():
                stems = sorted(p.stem for p in svc_dir.glob("*.md"))
                simg_dir = SITES_DIR / slug / "public" / "images" / "services"
                meta_p = SITES_DIR / slug / "src" / "data" / "image-meta.json"
                try:
                    smeta = json.loads(meta_p.read_text()) if meta_p.exists() else {}
                except json.JSONDecodeError:
                    smeta = {}
                s_missing = [s for s in stems
                             if not ((simg_dir / f"{s}.webp").exists()
                                     and f"/images/services/{s}.webp" in smeta)]
                if s_missing:
                    rows.append({"company_id": cid, "item_key": "site-imagery",
                                 "kind": "us_owed", "status": "open",
                                 "title": f"{len(s_missing)} of {len(stems)} service pages still show "
                                          "the generic stock photo — generate the real ones",
                                 "detail": "Generate + register with: python3 scripts/"
                                           f"gen_site_images.py --slug {slug} --services "
                                           "(writes the base webp, the 480/768/1200w "
                                           "variants and image-meta.json), then redeploy "
                                           "the site.",
                                 "evidence": {"total": len(stems),
                                              "missing": s_missing}})
                    attention.append(f"{slug}: {len(s_missing)}/{len(stems)} service "
                                     "cards on the fallback image — run the imagery "
                                     "finisher")
                elif stems:
                    rows.append({"company_id": cid, "item_key": "site-imagery",
                                 "kind": "us_owed", "status": "done",
                                 "title": f"All {len(stems)} service pages have their own photo",
                                 "detail": None, "evidence": {"total": len(stems)}})
        except Exception:
            pass

        _upsert(rows, dry_run)

    return attention


def _seed_build_blocker_ask(cid: str, slug: str, dry_run: bool, key: str,
                            title: str, rationale: str) -> None:
    """One client_input plan row per reason a site build is BLOCKED on data
    only the client can give us. Rank 1 — nothing else we could ask for is
    worth more than the thing standing between them and a website. Deduped by
    action_key (the table has no unique constraint), so this is safe to call
    on every sweep; the row retires itself when the build finally runs."""
    if dry_run:
        return
    action_key = f"site-build-blocked-{key}-{slug}"
    try:
        dup = _sb("GET", "/rest/v1/marketing_action_plan"
                  f"?company_id=eq.{cid}&action_key=eq.{action_key}&select=id",
                  prefer="return=representation") or []
        if dup:
            return
        _sb("POST", "/rest/v1/marketing_action_plan", [{
            "company_id": cid, "rank_ai_slug": slug, "action_key": action_key,
            "action_type": "client_input", "status": "planned", "priority": 1,
            "impact": "high", "effort": "low", "title": title,
            "rationale": rationale}])
    except Exception:
        pass


def ensure_auto_site_build(dry_run: bool, cid_to_slug: dict | None = None,
                           cap: int = 4) -> list[str]:
    """Auto-build preview sites — site builds never wait on approval (Santino
    2026-07-28: "I definitely don't want site builds to be backlogged just
    because I haven't said yes or no"). For Active Rank AI clients with NO
    sites/{slug}: seed/enrich plan-input from the truth table (services +
    company contact block, the manual Mold Solutionz steps mechanized), then
    plan -> scaffold -> render. Cap 1 per run (render cost/time). Imagery is
    NOT auto-generated — the attention line flags the built site for the
    hero/photo pass. Disable with AUTO_SITE_BUILD=0."""
    if os.environ.get("AUTO_SITE_BUILD", "1") == "0":
        return ["auto-build disabled (AUTO_SITE_BUILD=0)"]
    cid_to_slug = cid_to_slug or slug_map()
    cos = _sb("GET", "/rest/v1/companies?status=ilike.active&plan=eq.Rank%20AI"
              "&select=id,name,phone,email,address,city,state,postal_code,services,"
              "integration_settings,service_areas,website",
              prefer="return=representation") or []
    out: list[str] = []
    built = 0
    for co in cos:
        if built >= cap:
            break
        cid, slug = co["id"], cid_to_slug.get(co["id"])
        if not slug or (SITES_DIR / slug / "src").exists():
            continue
        # PAYMENT GATE (Santino 2026-08-28, after the "Loopple" junk signup
        # landed as Active): no card, no website. Evidence of payment = at
        # least one billing_invoices row (the Stripe webhook writes these for
        # every paying signup) OR integration_settings.billing_vetted=true
        # (manual override for special arrangements like invoice-billed
        # clients). Errs safe: a legit payer missing both shows up in the
        # ops digest as a one-line fix, a freeloader never gets a render.
        ints = co.get("integration_settings") or {}
        if isinstance(ints, str):
            try:
                ints = json.loads(ints)
            except ValueError:
                ints = {}
        has_invoice = bool(_sb(
            "GET", f"/rest/v1/billing_invoices?company_id=eq.{cid}&select=id&limit=1"))
        if not has_invoice and ints.get("billing_vetted") is not True:
            out.append(f"{slug}: cannot auto-build — no payment on file "
                       "(no billing invoice; set integration_settings."
                       "billing_vetted=true to override)")
            continue
        services = [s for s in (co.get("services") or []) if s]
        if not services:
            # An UNESCALATED blocker is the same as no blocker. Paul Davis
            # Charleston signed up 2026-07-07 with services=[] and this line
            # printed into the ops digest every single night for four weeks
            # while no one ever asked Kenneth for his service list, because
            # nothing turned it into a client-facing ask (found 2026-08-05).
            out.append(f"{slug}: cannot auto-build — no confirmed services in "
                       "truth table (ask seeded for Monica)")
            _seed_build_blocker_ask(
                cid, slug, dry_run, "services",
                "Confirm the services you want on your new website",
                "Their Services list in the app is EMPTY, which is the ONLY "
                "thing stopping their website from being built — the build is "
                "otherwise fully automatic. Ask which services they actually "
                "sell (water, fire, mold, reconstruction, ...) and tick them "
                "in the app. Do NOT guess on their behalf; a wrong service "
                "list ships wrong pages.")
            continue
        pi_path = CLIENTS_DIR / slug / "plan-input.json"
        if not pi_path.exists():
            out.append(f"{slug}: cannot auto-build — no plan-input.json (bootstrap missing)")
            continue

        # LOGO SOAK (Santino 2026-08-10): wait up to 7 days for the client's
        # real logo before building — every image on the site is generated
        # FROM the brand assets, and Go Green + Dry County both shipped
        # without their uploaded logo. After 7 days from signup, build
        # anyway (a placeholder logo beats an invisible client).
        try:
            import requests as _rq
            _r = _rq.post(
                os.environ["SUPABASE_URL"].rstrip("/") + "/storage/v1/object/list/branding",
                headers={"Authorization": "Bearer " + os.environ["SUPABASE_SERVICE_ROLE_KEY"],
                         "apikey": os.environ["SUPABASE_SERVICE_ROLE_KEY"],
                         "Content-Type": "application/json"},
                json={"prefix": f"{cid}/brand/", "limit": 5}, timeout=15)
            has_logo = bool(_r.ok and _r.json())
        except Exception:  # noqa: BLE001 — a storage hiccup must not stall builds
            has_logo = True
        # SOAK RETIRED (Santino 2026-09-03, content-now/brand-later): the
        # build NEVER waits on a logo anymore. No upload -> harvest one from
        # the client's existing website right here (brand_assets.
        # harvest_logo_from_web; a real hub upload always outranks the
        # harvest by filename sort). Still nothing -> build with neutral
        # brand anyway and keep Monica's logo ask alive — the 7-day
        # perception window hides every intermediate state from the client.
        if not has_logo and not dry_run:
            try:
                import brand_assets as _ba
                _site_url = (co.get("website") or "").strip()
                if _site_url and _ba.harvest_logo_from_web(cid, _site_url):
                    has_logo = True
                    out.append(f"{slug}: logo HARVESTED from {_site_url} "
                               "into the brand bucket (upload still wins if "
                               "one arrives)")
            except Exception:  # noqa: BLE001 — harvest failure must not stall builds
                pass
        if not has_logo:
            _seed_build_blocker_ask(
                cid, slug, dry_run, "logo",
                "Send over your logo so we can make your website match your brand",
                "We could not find a usable logo on their existing website "
                "and nothing is uploaded yet. The site build proceeds with "
                "a neutral look; ask them to upload the logo via their hub "
                "link so the brand pass can repaint before the day-7 reveal.")
            out.append(f"{slug}: no logo found anywhere — building with "
                       "neutral brand; Monica logo ask seeded")
        if dry_run:
            out.append(f"{slug}: WOULD auto-build preview site ({len(services)} services)")
            built += 1
            continue
        try:
            pi = json.loads(pi_path.read_text())
            # map confirmed service names -> catalog slugs (simple normalize)
            import verticals
            cat = json.loads(Path(verticals.resolve_template(slug, "services.json")).read_text())
            by_norm = {re.sub(r"[^a-z]", "", s["display_name"].lower()): s["slug"]
                       for s in cat["services"]}
            cat_words = {s2["slug"]: set(re.findall(r"[a-z]+", s2["display_name"].lower()))
                         for s2 in cat["services"]}
            svc_slugs = []
            for s in services:
                key = re.sub(r"[^a-z]", "", s.lower())
                hit = by_norm.get(key) or next(
                    (v for k, v in by_norm.items() if key[:12] and key[:12] in k), None)
                if not hit:
                    # word-overlap fallback: "Biohazard & Trauma Cleanup" ->
                    # biohazard-cleanup even though the exact key differs
                    words = set(re.findall(r"[a-z]+", s.lower())) - {"and", "services", "service"}
                    best, score = None, 0.0
                    for cslug, cw in cat_words.items():
                        ov = len(words & cw) / max(len(words | cw), 1)
                        if ov > score:
                            best, score = cslug, ov
                    if score >= 0.5:
                        hit = best
                if hit and hit not in svc_slugs:
                    svc_slugs.append(hit)
            if not svc_slugs:
                out.append(f"{slug}: cannot auto-build — no services mapped to catalog")
                continue
            pi["services"] = svc_slugs
            # Areas: geogrid city ring (bootstrap seeds it) + company state,
            # else the company's own city (QCI 2026-07-28: plan generate died
            # on 'At least one service area is required')
            if not (pi.get("service_areas") or []):
                areas = []
                st = (co.get("state") or "").strip()
                # FIRST: the app's Site Build brief — the cities a human
                # explicitly picked (QCI 2026-07-29: brief had 8 cities, the
                # auto-build shipped 1 because it never read the brief).
                ints_b = co.get("integration_settings") or {}
                if isinstance(ints_b, str):
                    try:
                        ints_b = json.loads(ints_b)
                    except json.JSONDecodeError:
                        ints_b = {}
                for c_ in (ints_b.get("site_brief") or {}).get("cities") or []:
                    city = (c_.get("label") or "").strip()
                    cst = (c_.get("state") or st).strip()
                    if city:
                        areas.append({
                            "city": city, "state": cst,
                            "slug": re.sub(r"[^a-z0-9]+", "-",
                                           f"{city} {cst}".lower()).strip("-"),
                            **({"primary": True} if not areas else {})})
                # SECOND: the onboarding wizard's territory picker writes
                # companies.service_areas (county + cities) — the AI Dispatcher
                # reads it, but the site build never did (Coastal + QCI both
                # shipped with a fraction of their cities, 2026-07-30).
                if not areas:
                    _ST_ABBR = {"alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
                                "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
                                "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
                                "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
                                "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
                                "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
                                "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
                                "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
                                "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
                                "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
                                "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
                                "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
                                "wisconsin": "WI", "wyoming": "WY"}
                    sa_raw = co.get("service_areas")
                    if isinstance(sa_raw, str):
                        try:
                            sa_raw = json.loads(sa_raw)
                        except json.JSONDecodeError:
                            sa_raw = []
                    for terr in sa_raw or []:
                        tst = (terr.get("state") or st or "").strip()
                        tst = _ST_ABBR.get(tst.lower(), tst[:2].upper() if len(tst) > 2 else tst.upper())
                        for city in terr.get("cities") or []:
                            city = str(city).strip()
                            # campus/base entries aren't ranking targets
                            if not city or len(city) > 40 or "university" in city.lower():
                                continue
                            city = re.sub(r"\s*\(.*\)$", "", city)  # "El Paso de Robles (Paso Robles)"
                            areas.append({
                                "city": city, "state": tst,
                                "slug": re.sub(r"[^a-z0-9]+", "-",
                                               f"{city} {tst}".lower()).strip("-"),
                                **({"primary": True} if not areas else {})})
                gg = CLIENTS_DIR / slug / "geogrid-cities.json"
                if not areas and gg.exists():
                    try:
                        for c_ in json.loads(gg.read_text()):
                            city = (c_.get("city") or c_.get("label") or "").strip()
                            if city:
                                areas.append({
                                    "city": city, "state": st,
                                    "slug": re.sub(r"[^a-z0-9]+", "-",
                                                   f"{city} {st}".lower()).strip("-"),
                                    **({"primary": True} if not areas else {})})
                    except json.JSONDecodeError:
                        pass
                if not areas and (co.get("city") or "").strip():
                    city = co["city"].strip()
                    areas = [{"city": city, "state": st,
                              "slug": re.sub(r"[^a-z0-9]+", "-",
                                             f"{city} {st}".lower()).strip("-"),
                              "primary": True}]
                if not areas:
                    out.append(f"{slug}: cannot auto-build — no cities anywhere in the truth table")
                    continue
                pi["service_areas"] = areas
            pi.setdefault("template", "restoration")
            pi.setdefault("blog_seed_count", 8)
            b = pi.setdefault("brand", {})
            b.setdefault("display_name", (co.get("name") or slug).strip())
            b.setdefault("phone", co.get("phone") or "")
            b.setdefault("email", co.get("email") or "")
            b.setdefault("street_address", co.get("address") or "")
            b.setdefault("city", co.get("city") or "")
            b.setdefault("state", co.get("state") or "")
            b.setdefault("postal_code", co.get("postal_code") or "")
            # Honor the theme the client picked in the wizard (Go Green shipped
            # dark+red against an explicit "light" intake, 2026-07-28). The
            # primary color stays the scaffold default until a human brand pass
            # — auto-extracting from branding uploads is unsafe (they're often
            # photos, not clean logo files).
            ints_ = co.get("integration_settings") or {}
            if isinstance(ints_, str):
                try:
                    ints_ = json.loads(ints_)
                except json.JSONDecodeError:
                    ints_ = {}
            theme_pick = ((ints_.get("site_brief") or {}).get("theme")
                          or ints_.get("theme") or "").strip().lower()
            if theme_pick == "light":
                b.setdefault("theme", "light")
            # Wizard licensing -> brand truth table + trust badges (Coastal's
            # IICRC sat recorded-but-unused, 2026-07-30). Only VERIFIED claims.
            lic = ints_.get("licensing") or {}
            certs = [c.strip().upper() for c in
                     str(lic.get("certifications") or "").split(",") if c.strip()]
            if certs and "certifications" not in b:
                names = {"IICRC": "IICRC Certified Firm",
                         "WTR": "WRT (Water Damage Restoration Technician)",
                         "WRT": "WRT (Water Damage Restoration Technician)",
                         "ASD": "ASD (Applied Structural Drying)",
                         "AMRT": "AMRT (Applied Microbial Remediation)",
                         "FSRT": "FSRT (Fire & Smoke Restoration)"}
                # ARRAY, not a joined string — the scaffold casts this into
                # brand.ts as string[] verbatim, and a string crashed
                # HomeLyft's whole build on .some() (2026-08-01).
                b["certifications"] = [names.get(c, c) for c in certs]
            if lic.get("license_number") and "license_numbers" not in b:
                b["license_numbers"] = [str(lic["license_number"])]
            # The wizard's licensing.trust_badges is the client's OWN attested
            # checklist — the same intake object we already trust for
            # certifications and the license number. Reading it fills the two
            # truth-table fields claims_lint gates on, so the renderer is
            # allowed to say what the client actually attested instead of
            # being neutralized into vagueness (DISS 2026-08-04: attested
            # "24/7 Emergency Service" + insured, but brand.hours was empty so
            # every availability sentence would have linted as an error).
            # Nothing here is inferred — an unchecked badge stays unclaimed.
            attested = [str(t) for t in (lic.get("trust_badges") or []) if t]
            att_blob = " | ".join(attested).lower()
            is_247 = "24/7" in att_blob or "24-7" in att_blob
            if is_247 and "hours" not in b:
                b["hours"] = "24/7"
            if lic.get("insured") and "licensed_insured_attested" not in b:
                b["licensed_insured_attested"] = True
            if lic.get("founded_year") and "founded_year" not in b:
                b["founded_year"] = str(lic["founded_year"])
            badges = []
            if any(c.startswith("IICRC") for c in certs):
                badges.append("IICRC Certified Firm")
            if lic.get("insured"):
                badges.append("Licensed & Insured")
            # 24/7 is a CLAIM, not a default — only badge it when the client
            # ticked it in the wizard (it was previously appended for every
            # client regardless of what they attested).
            if is_247:
                badges.append("24/7 Emergency Service")
            badges.append("Locally Owned & Operated")
            b.setdefault("trust_badges", badges)
            # Primary area = the company's own city when it's in the list
            # (Vandenberg Village outranked Santa Maria purely by wizard
            # ordering, 2026-07-30).
            home_city = (co.get("city") or "").strip().lower()
            sa_list = pi.get("service_areas") or []
            if home_city and sa_list and not any(
                    a.get("primary") and a.get("city", "").strip().lower() == home_city
                    for a in sa_list):
                hit = next((a for a in sa_list
                            if a.get("city", "").strip().lower() == home_city), None)
                if hit:
                    for a in sa_list:
                        a.pop("primary", None)
                    hit["primary"] = True
            pi_path.write_text(json.dumps(pi, indent=1) + "\n")
            for cmdline, tmo in [
                ([sys.executable, str(ROOT / "scripts" / "plan_site.py"),
                  "generate", "--slug", slug], 300),
                ([sys.executable, str(ROOT / "scripts" / "build_site.py"),
                  "scaffold", "--slug", slug], 900),
                ([sys.executable, str(ROOT / "scripts" / "build_site.py"),
                  "render", "--slug", slug, "--workers", "4", "--push"], 5400),
            ]:
                r = subprocess.run(cmdline, capture_output=True, text=True, timeout=tmo)
                if r.returncode != 0:
                    tail = (r.stderr or r.stdout or "").strip().splitlines()[-1:]
                    raise RuntimeError(f"{cmdline[2]} failed: {tail}")
            # scaffold/render leave a nested .git in the site dir — committing
            # it to the monorepo creates an empty gitlink (2026-07-28)
            nested = SITES_DIR / slug / ".git"
            if nested.exists():
                import shutil
                shutil.rmtree(nested, ignore_errors=True)
            # Re-pull the logo: the ledger drops the branding-bucket logo into
            # sites/{slug}/public/images/ on the FIRST sweep, and the scaffold
            # above then replaces public/ wholesale — so by the time anyone
            # runs the imagery pass the client's real mark is gone and every
            # generated van wears nothing (DISS 2026-08-04). Cheap and
            # idempotent; ordering is the whole fix.
            try:
                if _pull_bucket_logo(cid, slug):
                    out.append(f"{slug}: brand logo restored after scaffold")
            except Exception:
                pass
            built += 1
            # WRITE-BACK (2026-08-03, second occurrence: HomeLyft 08-01, Reign
            # 08-03): builds that run OUTSIDE the site-build CI never patched
            # marketing_sites, so the app's Site tab stayed blank. Mirror
            # site-build.yml's "Mark preview ready" step: flip the row to
            # preview_ready + staging URL, and seed Monica's preview-feedback
            # plan row so the client gets shown their new site.
            preview = f"https://staging.rankai-{slug}.pages.dev"
            try:
                rec_ = json.loads((CLIENTS_DIR / f"{slug}.json").read_text())
                # upsert, not PATCH: a missing row would make PATCH a silent
                # 0-row no-op and the tab would stay blank anyway
                _sb("POST", "/rest/v1/marketing_sites?on_conflict=rank_ai_slug",
                    {"rank_ai_slug": slug, "company_id": cid,
                     "build_status": "preview_ready",
                     "cloudflare_pages_url": preview,
                     "github_repo": (rec_.get("build") or {}).get("github_repo"),
                     "plan_status": rec_.get("plan_status"),
                     "plan_template": (rec_.get("plan") or {}).get("template"),
                     "plan_url_count": (rec_.get("plan") or {}).get("url_count"),
                     "plan_generated_at": (rec_.get("plan") or {}).get("generated_at"),
                     "scaffolded_at": (rec_.get("build") or {}).get("scaffolded_at"),
                     "last_pushed_staging_at": (rec_.get("build") or {}).get("last_rendered_at"),
                     "updated_at": rec_.get("updated_at")},
                    prefer="resolution=merge-duplicates,return=minimal")
                fb_row = {"company_id": cid, "rank_ai_slug": slug,
                          "action_key": f"site-preview-feedback-{slug}",
                          "action_type": "client_input", "status": "planned",
                          "priority": 1, "impact": "high", "effort": "low",
                          "title": "Take a look at your new website preview and "
                                   "tell us your thoughts",
                          "target": preview,
                          "rationale": "New site build finished at " + preview +
                                       " — SHOW IT TO THEM. Send that exact link, ask "
                                       "what they think, collect change requests. A "
                                       "client who has never seen their finished site "
                                       "gets this BEFORE any other ask (Santino "
                                       "2026-08-04, Reign)."}
                # manual dedupe (table has no unique constraint on action_key)
                dup_ = _sb("GET", "/rest/v1/marketing_action_plan"
                           f"?company_id=eq.{cid}&action_key=eq.{fb_row['action_key']}"
                           "&select=id", prefer="return=representation") or []
                if not dup_:
                    _sb("POST", "/rest/v1/marketing_action_plan", [fb_row])
            except Exception as e_:
                out.append(f"{slug}: built OK but marketing_sites write-back "
                           f"FAILED — {str(e_)[:120]} (app Site tab will look "
                           "blank until patched by hand)")
            has_brand_asset = False
            try:
                sb_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
                sb_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
                r_ = requests.post(f"{sb_url}/storage/v1/object/list/branding",
                                   headers={"Authorization": f"Bearer {sb_key}",
                                            "apikey": sb_key,
                                            "Content-Type": "application/json"},
                                   json={"prefix": f"{cid}/brand/", "limit": 5},
                                   timeout=20)
                has_brand_asset = r_.status_code == 200 and bool(r_.json())
            except Exception:
                pass
            # BRAND PASS IS AUTOMATIC (Santino 2026-09-03, Kenny pilot):
            # instead of only FLAGGING the built site for a human, file the
            # [DEV] brand-pass card right here — the twice-daily dev agent
            # (2:07am + 1:07pm) generates hero + per-service imagery, applies
            # the logo/palette when a brand upload exists, all inside the
            # 7-day perception window. No logo on file yet -> the card says
            # to harvest one from the client's existing website first, with
            # Monica's logo ask as the fallback.
            try:
                _brand_card = (
                    f"[DEV] AUTO brand pass for the freshly built {slug} site: "
                    "run gen_site_images (hero + per-service set + team) per "
                    "the image style guide"
                    + ("; client brand upload EXISTS in branding/" + cid +
                       "/brand — apply logo (favicon_sync) + derive palette "
                       "(brand_colors_sync)" if has_brand_asset else
                       "; NO brand upload yet — first try harvesting the logo "
                       "from their existing live website (header img / "
                       "og:image / favicon), save it to branding/" + cid +
                       "/brand/, then apply; if none found, leave the Monica "
                       "logo ask in place and generate imagery in neutral "
                       "palette")
                    + f". Finish BEFORE the day-7 preview reveal. "
                    f"SITE: sites/{slug} — staging")
                _sb("POST", "/rest/v1/marketing_ops_notes",
                    {"company_id": cid, "body": _brand_card, "status": "open"})
            except Exception:  # noqa: BLE001 — card filing must not fail the build report
                pass
            out.append(f"{slug}: AUTO-BUILT preview site ({len(svc_slugs)} services) — "
                       "brand-pass card auto-filed for the next agent run"
                       + (f"; client brand upload EXISTS (branding/{cid}/brand)"
                          if has_brand_asset else
                          "; no brand upload yet — agent will try harvesting "
                          "from their old site"))
        except Exception as e:
            out.append(f"{slug}: auto-build FAILED — {str(e)[:140]}")
    out += _reconcile_marketing_sites(dry_run, cos, cid_to_slug)
    return out


def _reconcile_marketing_sites(dry_run: bool, cos: list[dict],
                               cid_to_slug: dict) -> list[str]:
    """Heal marketing_sites rows that are BEHIND the repo (AAA 2026-08-05).

    The write-back above only fires on the run that builds a site. Anything
    built before that patch shipped — or built by hand, or by a CI run that
    died after rendering — keeps a build_status='pending' row forever, and the
    app's Site tab shows the client nothing while a finished site sits in the
    monorepo. AAA Water Damage was 'pending' from 2026-07-28 to 2026-08-05
    with a rendered 174-URL site on disk.

    Conservative by construction:
      * only ever fills fields the DB has as NULL/'pending' — never downgrades
        a row that is further along than the repo record,
      * only writes cloudflare_pages_url when the repo says a Cloudflare Pages
        project actually EXISTS (build.pages_status != 'local-only'), so a
        site that was never deployed does not get a URL that 404s.
    """
    out: list[str] = []
    _AHEAD = {"pending": 0, "scaffolded": 1, "preview_ready": 2,
              "pushed_staging": 2, "preview_live": 3, "pushed_main": 4}
    try:
        from bootstrap_client import domain_from_website
    except Exception:
        domain_from_website = lambda _w: None  # noqa: E731
    for co in cos:
        cid = co["id"]
        slug = cid_to_slug.get(cid)
        if not slug:
            continue
        # The domain heal runs even for clients with no site yet: the
        # "{slug}.invalid" placeholder outlives bootstrap whenever the wizard
        # DID capture a website (4 clients on 2026-08-05), and every
        # domain-access / NS-cutover line downstream reads this column.
        try:
            real_domain = domain_from_website(co.get("website"))
            if real_domain:
                rows_ = _sb("GET", f"/rest/v1/marketing_sites?rank_ai_slug=eq.{slug}"
                            "&select=id,domain", prefer="return=representation") or []
                if rows_ and str(rows_[0].get("domain") or "").endswith(".invalid"):
                    if dry_run:
                        out.append(f"{slug}: WOULD set domain "
                                   f"{rows_[0]['domain']} -> {real_domain}")
                    else:
                        _sb("PATCH", f"/rest/v1/marketing_sites?id=eq.{rows_[0]['id']}",
                            {"domain": real_domain}, prefer="return=minimal")
                        out.append(f"{slug}: domain placeholder replaced with the "
                                   f"real one on file — {real_domain}")
        except Exception as e:
            out.append(f"{slug}: domain heal failed — {str(e)[:100]}")
        if not (SITES_DIR / slug / "src").exists():
            continue
        rec_p = CLIENTS_DIR / f"{slug}.json"
        if not rec_p.exists():
            continue
        try:
            rec = json.loads(rec_p.read_text())
            bld = rec.get("build") or {}
            repo_status = rec.get("build_status")
            if not repo_status:
                continue
            rows = _sb("GET", f"/rest/v1/marketing_sites?rank_ai_slug=eq.{slug}"
                       "&select=id,build_status,plan_status,cloudflare_pages_url,"
                       "github_repo,plan_url_count", prefer="return=representation") or []
            if not rows:
                continue
            row = rows[0]
            db_status = row.get("build_status") or "pending"
            patch: dict = {}
            if _AHEAD.get(repo_status, 0) > _AHEAD.get(db_status, 0):
                patch["build_status"] = repo_status
            if not row.get("plan_status") or row["plan_status"] == "pending":
                if rec.get("plan_status"):
                    patch["plan_status"] = rec["plan_status"]
                    patch["plan_template"] = (rec.get("plan") or {}).get("template")
                    patch["plan_url_count"] = (rec.get("plan") or {}).get("url_count")
                    patch["plan_generated_at"] = (rec.get("plan") or {}).get("generated_at")
            if not row.get("github_repo") and bld.get("github_repo"):
                patch["github_repo"] = bld["github_repo"]
            if not row.get("cloudflare_pages_url"):
                proj = bld.get("pages_project")
                if proj and bld.get("pages_status") != "local-only":
                    patch["cloudflare_pages_url"] = (
                        f"https://{proj}.pages.dev" if repo_status == "pushed_main"
                        else f"https://staging.{proj}.pages.dev")
            if not patch:
                continue
            if dry_run:
                out.append(f"{slug}: WOULD heal stale marketing_sites row "
                           f"({db_status} -> {patch.get('build_status', db_status)})")
                continue
            patch["scaffolded_at"] = bld.get("scaffolded_at")
            patch["last_pushed_staging_at"] = (bld.get("last_pushed_staging_at")
                                               or bld.get("last_rendered_at"))
            patch["updated_at"] = datetime.now(timezone.utc).isoformat()
            _sb("PATCH", f"/rest/v1/marketing_sites?id=eq.{row['id']}", patch,
                prefer="return=minimal")
            out.append(f"{slug}: marketing_sites row was STALE — healed "
                       f"{db_status} -> {patch.get('build_status', db_status)}"
                       + ("" if patch.get("cloudflare_pages_url") else
                          " (no Pages URL: site has never been deployed)"))
        except Exception as e:
            out.append(f"{slug}: marketing_sites reconcile failed — {str(e)[:100]}")
    return out


def ensure_map_and_video(dry_run: bool, cid_to_slug: dict | None = None) -> list[str]:
    """Evaluate ONLY map-rankings + video-channel for every active Rank AI
    client and write those cards. Same code path ensure_ledger uses.

    Exists so these two can be re-run on demand (after a geo-grid fix, after a
    client creates their channel) without kicking off a full nightly pass —
    which would also provision tracking numbers, import GBP media and fire
    auto-builds. Cheap: no DataForSEO spend of its own."""
    cid_to_slug = cid_to_slug or slug_map()
    cos = _sb("GET", "/rest/v1/companies?status=ilike.active&plan=eq.Rank%20AI"
              "&select=id,name", prefer="return=representation") or []
    attention: list[str] = []
    heals = {"ggconfig": 2}
    for co in cos:
        cid = co["id"]
        slug = cid_to_slug.get(cid)
        if not slug:
            continue
        gi = _sb("GET", f"/rest/v1/user_integrations?client_id=eq.{cid}"
                 "&provider=eq.google&select=id", prefer="return=representation") or []
        rows: list[dict] = []
        _map_and_video_rows(cid, slug, gi, rows, attention, heals, dry_run)
        _upsert(rows, dry_run)
    return attention


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass
    if "--map-video-only" in sys.argv:
        print(f"==> map-rankings + video-channel ({'dry-run' if dry else 'live'})")
        for line in ensure_map_and_video(dry):
            print("  ATTENTION:", line)
    else:
        print(f"==> Setup ledger ({'dry-run' if dry else 'live'})")
        for line in ensure_ledger(dry):
            print("  ATTENTION:", line)
