#!/usr/bin/env python3
"""lsa_lead_review.py — daily AI review of every client's LSA leads.

Santino 2026-09-27: "reading leads can help Google know what we do and don't
want" + "add a note to the agent so it can understand the client ... we are
not just going to be doing SEO for restoration companies." Per lead:

  1. pull the lead + its conversations (call durations, recording URLs,
     message text) from the Google Ads API
  2. download + transcribe each answered call (call_intel.transcribe)
  3. judge it against the client's LEAD PROFILE (what they do, where, and
     what they do NOT want) — vertical-agnostic, the profile carries the niche
  4. with --apply, tell Google via ProvideLeadFeedback (satisfied / dissatisfied
     + the reason Google accepts) and record Google's credit decision

Missed calls (every call 0s) are NOT judged or rated — nobody spoke, so there
is nothing to rate — but a 0-second streak is flagged loudly (the DryCor
dead-forwarding case, 09-27).

LEAD PROFILE — the per-client note (single source of truth):
  companies.integration_settings.lead_profile =
    {"summary", "wants": [...], "does_not_want": [...], "service_area",
     "notes", "source", "updated_at"}
Auto-seeded by Claude from what we already hold (services, LSA services and
areas, ops notes, meeting intel) the first time a client is reviewed; edit it
any time and the next review uses the edit. `profile --slug X` shows it,
`profile --slug X --reseed` rebuilds the draft.

Ownership guard: an LSA account whose Google name shares no word with the
client's name is NOT reviewed (FFS's linked account is A&J Plumbing's, a
different business — never rate a stranger's leads).

Usage:
  python3 scripts/lsa_lead_review.py list-due                 # JSON slugs
  python3 scripts/lsa_lead_review.py review --slug X [--days 14] [--apply]
  python3 scripts/lsa_lead_review.py profile --slug X [--reseed]
  python3 scripts/lsa_lead_review.py approve --slug X [--confirm-profile] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

import client_concierge as cc  # noqa: E402
from client_ops_sync import _sb, slug_map  # noqa: E402

KV = "lsa-lead-review"
# SAFE MODE (default for --apply, Santino 2026-09-27 first dry runs): only
# verdicts that cannot misteach Google go out automatically — GOOD leads and
# unmistakable junk. JOB_TYPE / GEO / NOT_READY judgments depend on the
# client profile being right (ACS: carpet-cleaning calls read as "wrong job"
# though ACS bids on carpet cleaning), so they are HELD for approval until the
# client's lead_profile carries "confirmed": true, or --mode all is passed.
AUTO_BAD = {"SPAM", "SOLICITATION", "DUPLICATE"}
MIN_CONF_GOOD = 0.75
MIN_CONF_BAD = 0.85          # a wrong "bad" costs the client goodwill with Google
MAX_TRANSCRIBE_S = 900       # skip absurdly long recordings
STOP = {"llc", "inc", "the", "of", "and", "co", "company", "services",
        "service", "lsa", "restoration", "construction", "&", "-", "/"}


# ------------------------------------------------------------------ work log
_REASON_TEXT = {"GEO_MISMATCH": "outside your service area",
                "JOB_TYPE_MISMATCH": "jobs you do not do",
                "NOT_READY_TO_BOOK": "not ready to book",
                "SPAM": "spam", "DUPLICATE": "duplicates",
                "SOLICITATION": "sales calls",
                "SOLICITATION_CALL": "sales calls"}


def sent_ok(decision) -> bool:
    """True when Google accepted the feedback (any credit decision). None,
    HELD and error: decisions never reached Google."""
    d = str(decision or "")
    return bool(d) and not d.startswith(("HELD", "error"))


def work_line(good: int, bad: int, credits: int, bad_whys: list) -> str:
    """One plain client-readable Reports line for a batch of rated leads."""
    n = good + bad
    parts = []
    if good:
        parts.append(f"{good} confirmed as good job{'s' if good != 1 else ''}")
    if bad:
        whys = sorted({_REASON_TEXT.get(str(w or ""), "") for w in bad_whys} - {""})
        parts.append(f"{bad} reported as poor fit"
                     + (f" ({', '.join(whys)})" if whys else ""))
    line = (f"Reviewed and rated {'one' if n == 1 else n} of your Local Services "
            f"Ads leads with Google: {' and '.join(parts)}, so Google learns which "
            "customers to send you.")
    if credits:
        line += (f" Google credited back {credits} lead charge"
                 f"{'s' if credits != 1 else ''}.")
    return line


def log_feedback(cid: str, good: int, bad: int, credits: int, bad_whys: list,
                 source: str, evidence: dict | None = None) -> None:
    """Reports-tab line (2026-09-29, every client action logs). Fail-soft."""
    if not (good or bad):
        return
    try:
        from work_log import work_log
        work_log(cid, "ads", "lsa-lead-feedback",
                 work_line(good, bad, credits, bad_whys),
                 evidence={"good": good, "bad": bad, "credits": credits,
                           **(evidence or {})},
                 actor="automation", source=source)
    except Exception as e:  # noqa: BLE001 — logging never breaks the review
        print(f"  [work-log] warn: {str(e)[:100]}")


# ------------------------------------------------------------------ plumbing
def _mcc():
    from lsa_detect import build_mcc_client
    cl, mcc = build_mcc_client()
    if not cl:
        sys.exit("no Google Ads credentials (MCC)")
    return cl


def _gaql(cl, acid, q):
    from ads_manager import gaql
    return list(gaql(cl, acid, q))


def _company(cid: str) -> dict:
    return cc.fetch_companies([cid]).get(cid) or {}


def _cid_for(slug: str) -> str | None:
    return next((c for c, s in slug_map().items() if s == slug), None)


def _ints(co: dict) -> dict:
    return co.get("integration_settings") or {}


def _tokens(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9&]+", (s or "").lower())
            if w not in STOP and len(w) > 1}


def _owned(cl, acid: str, co: dict) -> tuple[bool, str]:
    """Is this LSA account really this client's? Nameless accounts pass."""
    name = ""
    for r in _gaql(cl, acid, "SELECT customer.descriptive_name FROM customer"):
        name = r.customer.descriptive_name or ""
    if not name.strip():
        return True, "(nameless account)"
    if _tokens(name) & _tokens(co.get("name", "")):
        return True, name
    return False, name


def _account_context(cl, acid: str) -> dict:
    services, geo_ids = [], []
    for r in _gaql(cl, acid, """SELECT campaign_criterion.type,
            campaign_criterion.local_service_id.service_id,
            campaign_criterion.location.geo_target_constant,
            campaign_criterion.negative
          FROM campaign_criterion
          WHERE campaign.advertising_channel_type = 'LOCAL_SERVICES'
            AND campaign.status != 'REMOVED'"""):
        c = r.campaign_criterion
        if c.type_.name == "LOCAL_SERVICE_ID":
            services.append(c.local_service_id.service_id)
        elif c.type_.name == "LOCATION" and not c.negative:
            geo_ids.append(c.location.geo_target_constant)
    areas = []
    if geo_ids:
        ids = ",".join(f"'{g}'" for g in geo_ids[:200])
        for r in _gaql(cl, acid, "SELECT geo_target_constant.canonical_name "
                       f"FROM geo_target_constant WHERE geo_target_constant.resource_name IN ({ids})"):
            areas.append(r.geo_target_constant.canonical_name)
    return {"lsa_services": sorted(set(services)), "lsa_areas": sorted(areas)}


# ------------------------------------------------------------------ profile
PROFILE_SYS = """You write a short LEAD PROFILE for a home-service business so an
AI reviewer can judge incoming phone/message leads for them. Work only from the
facts given. Be concrete and short. The business may be ANY service niche
(restoration, plumbing, HVAC, roofing, remodeling, cleaning...).

WHAT THEY DO comes from site_services (their full service list) plus
custom_services and lsa_services_enabled. A service they offer is WANTED even
when it is not switched on in LSA (ACS 09-27: carpet cleaning is on their
site but not enabled in LSA; carpet leads are GOOD leads). Put something in
does_not_want ONLY when they don't offer it at all, or an ops note / meeting
says they explicitly don't want it.

Reply with ONLY JSON:
{"summary": "one or two sentences: who they are and the jobs they want most",
 "wants": ["job types / customers they want"],
 "does_not_want": ["jobs, customers or requests they do NOT want, e.g. services
   they turned off, work they don't do, sales calls, job seekers"],
 "service_area": "plain-language description of where they work",
 "notes": "anything else that changes whether a lead is good (hours, commercial
   vs residential, insurance work, minimum job size); empty if nothing"}"""


def _site_services(co: dict) -> list:
    """The client's full service list from its plan-input (what the site
    sells), the truest 'what do they do' record we hold."""
    slug = slug_map().get(co.get("id"))
    try:
        pi = json.loads((ROOT / "clients" / slug / "plan-input.json").read_text())
    except Exception:  # noqa: BLE001
        return []
    return [s.get("name") if isinstance(s, dict) else s
            for s in (pi.get("services") or [])]


def seed_profile(cl, acid: str, co: dict, ctx: dict) -> dict:
    ints = _ints(co)
    notes = _sb("GET", "/rest/v1/marketing_ops_notes?company_id=eq."
                f"{co['id']}&select=body,created_at&order=created_at.desc&limit=25") or []
    intel = cc.load_meeting_intel(co) or ""
    facts = {
        "business_name": co.get("name"),
        "city_state": f"{co.get('city')}, {co.get('state')}",
        "custom_services": ints.get("custom_services"),
        "site_services": _site_services(co),
        "site_brief": ints.get("site_brief"),
        "goals": ints.get("goals"),
        "lsa_services_enabled": ctx["lsa_services"],
        "lsa_service_areas": ctx["lsa_areas"][:80],
        "recent_ops_notes": [n["body"][:400] for n in notes],
        "meeting_intel_excerpt": intel[:4000],
    }
    prof = cc.anthropic_json(PROFILE_SYS, json.dumps(facts, default=str)[:24000],
                             max_tokens=2500)
    prof["source"] = "auto-seed (lsa_lead_review) — edit freely, next review uses it"
    prof["updated_at"] = datetime.now(timezone.utc).isoformat()
    return prof


def get_profile(cl, acid, co, ctx, reseed=False, write=True) -> dict:
    ints = _ints(co)
    prof = ints.get("lead_profile")
    if prof and not reseed:
        return prof
    prof = seed_profile(cl, acid, co, ctx)
    if write:
        row = (_sb("GET", f"/rest/v1/companies?id=eq.{co['id']}"
                   "&select=integration_settings") or [{}])[0]
        fresh = row.get("integration_settings") or {}
        fresh["lead_profile"] = prof
        _sb("PATCH", f"/rest/v1/companies?id=eq.{co['id']}",
            {"integration_settings": fresh}, prefer="return=minimal")
    return prof


# ------------------------------------------------------------------ review
REVIEW_SYS = """You review one Google Local Services Ads lead for a home-service
business and decide what feedback to give Google. Google uses this feedback to
learn which leads the business wants and may credit back invalid leads.

Judge ONLY against the business's LEAD PROFILE and the lead evidence. The
business can be any niche; the profile tells you what they do.

Verdicts:
- "good": a real customer asking for a job the business wants, in its area.
- "bad": clearly one of Google's accepted reasons:
    GEO_MISMATCH (customer is outside the service area),
    JOB_TYPE_MISMATCH (asks for work the business doesn't do at all, or that
      the profile's does_not_want explicitly lists; a service in the profile's
      wants or site_services is NEVER a mismatch, even if not enabled in LSA),
    NOT_READY_TO_BOOK (just price shopping / no real need yet),
    SPAM (robocall, wrong number, prank, silent),
    DUPLICATE (same customer, same job, already a lead recently),
    SOLICITATION (someone SELLING to the business, job seekers, vendors).
- "unclear": not enough evidence (very short call, no transcript, mixed).
  Unclear is the safe answer whenever you are not sure.

A customer who needed the service but whom the business failed to help is
still a GOOD lead (the business's miss is not Google's fault).

Reply with ONLY JSON:
{"verdict": "good|bad|unclear",
 "confidence": 0.0-1.0,
 "survey_answer": "VERY_SATISFIED|SATISFIED|NEUTRAL|DISSATISFIED|VERY_DISSATISFIED",
 "satisfied_reason": "BOOKED_CUSTOMER|LIKELY_BOOKED_CUSTOMER|SERVICE_RELATED|HIGH_VALUE_SERVICE|OTHER_SATISFIED_REASON|null",
 "dissatisfied_reason": "GEO_MISMATCH|JOB_TYPE_MISMATCH|NOT_READY_TO_BOOK|SPAM|DUPLICATE|SOLICITATION|OTHER_DISSATISFIED_REASON|null",
 "caller_need": "what the caller wanted, few words",
 "location_mentioned": "city/area if said, else null",
 "summary": "one sentence a busy owner can read"}"""


def _leads(cl, acid: str, since: datetime) -> list:
    s = since.strftime("%Y-%m-%d %H:%M:%S")
    return _gaql(cl, acid, f"""SELECT local_services_lead.id,
          local_services_lead.resource_name, local_services_lead.lead_type,
          local_services_lead.category_id, local_services_lead.service_id,
          local_services_lead.lead_status, local_services_lead.lead_charged,
          local_services_lead.creation_date_time,
          local_services_lead.lead_feedback_submitted,
          local_services_lead.contact_details
        FROM local_services_lead
        WHERE local_services_lead.creation_date_time >= '{s}'
        ORDER BY local_services_lead.creation_date_time""")


def _convos(cl, acid: str, since: datetime) -> dict:
    s = since.strftime("%Y-%m-%d %H:%M:%S")
    out: dict = {}
    for r in _gaql(cl, acid, f"""SELECT local_services_lead_conversation.lead,
          local_services_lead_conversation.conversation_channel,
          local_services_lead_conversation.participant_type,
          local_services_lead_conversation.event_date_time,
          local_services_lead_conversation.phone_call_details.call_duration_millis,
          local_services_lead_conversation.phone_call_details.call_recording_url,
          local_services_lead_conversation.message_details.text
        FROM local_services_lead_conversation
        WHERE local_services_lead_conversation.event_date_time >= '{s}'"""):
        c = r.local_services_lead_conversation
        out.setdefault(c.lead, []).append({
            "channel": c.conversation_channel.name,
            "who": c.participant_type.name,
            "at": c.event_date_time,
            "secs": int(c.phone_call_details.call_duration_millis or 0) // 1000,
            "rec": c.phone_call_details.call_recording_url or None,
            "text": c.message_details.text or None})
    return out


def _transcript(cl, rec_url: str) -> str | None:
    import requests
    import google.auth.transport.requests as gtr
    from call_intel import transcribe
    creds = cl.credentials
    if not creds.valid:
        creds.refresh(gtr.Request())
    r = requests.get(rec_url, headers={"Authorization": f"Bearer {creds.token}"},
                     timeout=120)
    if r.status_code != 200 or "audio" not in r.headers.get("content-type", ""):
        return None
    return transcribe(r.content)


def _submit(cl, acid: str, lead_rn: str, v: dict) -> str:
    svc = cl.get_service("LocalServicesLeadService")
    req = cl.get_type("ProvideLeadFeedbackRequest")
    req.resource_name = lead_rn
    E = cl.enums
    req.survey_answer = getattr(E.LocalServicesLeadSurveyAnswerEnum,
                                v["survey_answer"])
    if v["verdict"] == "good":
        req.survey_satisfied.survey_satisfied_reason = getattr(
            E.LocalServicesLeadSurveySatisfiedReasonEnum,
            v.get("satisfied_reason") or "SERVICE_RELATED")
        if req.survey_satisfied.survey_satisfied_reason.name == "OTHER_SATISFIED_REASON":
            req.survey_satisfied.other_reason_comment = v.get("summary", "")[:200]
    else:
        req.survey_dissatisfied.survey_dissatisfied_reason = getattr(
            E.LocalServicesLeadSurveyDissatisfiedReasonEnum,
            v.get("dissatisfied_reason") or "OTHER_DISSATISFIED_REASON")
        if req.survey_dissatisfied.survey_dissatisfied_reason.name == "OTHER_DISSATISFIED_REASON":
            req.survey_dissatisfied.other_reason_comment = v.get("summary", "")[:200]
    resp = svc.provide_lead_feedback(request=req)
    return resp.credit_issuance_decision.name


def cmd_review(a) -> int:
    cid = _cid_for(a.slug)
    if not cid:
        sys.exit(f"unknown slug {a.slug}")
    co = _company(cid)
    muted = cc.company_inactive(co)
    if muted:
        print(f"{a.slug}: {muted} — skipped")
        return 0
    acid = str((_ints(co).get("lsa") or {}).get("customer_id") or "")
    if not acid:
        print(f"{a.slug}: no LSA account — skipped")
        return 0
    cl = _mcc()
    try:
        ok, gname = _owned(cl, acid, co)
    except Exception as e:  # noqa: BLE001
        # 2026-09-29 RestoPros: the LSA account is detected but the MCC link
        # invite is still PENDING (client hasn't accepted), so every query is
        # USER_PERMISSION_DENIED. That is an access gap the MCC-link watcher
        # already tracks, not a crashed review; skip cleanly so one unlinked
        # account doesn't fail the whole fan-out.
        if "PERMISSION_DENIED" in str(e) or "USER_PERMISSION_DENIED" in repr(e):
            link = (_ints(co).get("lsa") or {}).get("link_status") or "?"
            print(f"{a.slug}: no MCC access to LSA account {acid} "
                  f"(link_status={link}) — skipped until the link is accepted")
            return 0
        raise
    if not ok:
        print(f"{a.slug}: LSA account {acid} is '{gname}', not this client — "
              "NOT reviewing a stranger's leads")
        return 0
    ctx = _account_context(cl, acid)
    prof = get_profile(cl, acid, co, ctx, write=a.apply)
    since = datetime.now(timezone.utc) - timedelta(days=a.days)
    leads = _leads(cl, acid, since)
    convos = _convos(cl, acid, since - timedelta(days=1))
    seen_phones: dict[str, str] = {}
    done = cc.kv_prefix(f"{KV}:{cid}:")
    tally = {"good": 0, "bad": 0, "unclear": 0, "missed": 0,
             "submitted": 0, "credits": 0}
    sent = {"good": 0, "bad": 0, "credits": 0, "whys": []}
    zero_streak = 0
    print(f"== {a.slug} ({co.get('name')}) LSA {acid}: {len(leads)} lead(s) "
          f"in {a.days}d {'[APPLY]' if a.apply else '[dry run]'}")
    for r in leads:
        l = r.local_services_lead
        key = f"{KV}:{cid}:{l.id}"
        phone = l.contact_details.phone_number or ""
        conv = convos.get(l.resource_name, [])
        calls = [c for c in conv if c["channel"] == "PHONE_CALL"]
        msgs = [c for c in conv if c["channel"] == "MESSAGE"]
        prior_same = seen_phones.get(phone)
        if phone:
            seen_phones[phone] = l.creation_date_time
        when = l.creation_date_time[:16]
        if calls and all(c["secs"] == 0 for c in calls) and not msgs:
            tally["missed"] += 1
            zero_streak += 1
            print(f"  {when} MISSED (0s call) {l.service_id or '-'}")
            continue
        zero_streak = 0
        if key in done or l.lead_feedback_submitted:
            continue
        parts = []
        for c in calls:
            t = None
            if c["rec"] and 0 < c["secs"] <= MAX_TRANSCRIBE_S:
                try:
                    t = _transcript(cl, c["rec"])
                except Exception as e:  # noqa: BLE001
                    t = f"(transcription failed: {str(e)[:80]})"
            parts.append(f"CALL {c['secs']}s at {c['at']}:\n{t or '(no transcript)'}")
        for m in msgs:
            parts.append(f"MESSAGE from {m['who']} at {m['at']}: {m['text']}")
        evidence = {
            "lead": {"type": l.lead_type.name, "category": l.category_id,
                     "service": l.service_id, "created": l.creation_date_time,
                     "charged": bool(l.lead_charged),
                     "same_phone_earlier_lead": prior_same},
            "conversations": "\n\n".join(parts)[:14000],
        }
        user = json.dumps({"business": co.get("name"), "lead_profile": prof,
                           "lsa_services_enabled": ctx["lsa_services"],
                           "lsa_service_areas": ctx["lsa_areas"][:60],
                           "evidence": evidence}, default=str)
        try:
            v = cc.anthropic_json(REVIEW_SYS, user, max_tokens=2000)
        except Exception as e:  # noqa: BLE001
            print(f"  {when} review failed: {str(e)[:100]}")
            continue
        verdict = v.get("verdict", "unclear")
        conf = float(v.get("confidence") or 0)
        need = MIN_CONF_GOOD if verdict == "good" else MIN_CONF_BAD
        if verdict in ("good", "bad") and conf < need:
            verdict = "unclear"
        tally[verdict] = tally.get(verdict, 0) + 1
        why = v.get("dissatisfied_reason") if verdict == "bad" else v.get("satisfied_reason")
        print(f"  {when} {verdict.upper():8} {conf:.2f} {why or ''} | "
              f"{v.get('caller_need') or '-'} | {v.get('summary', '')[:140]}")
        decision = None
        held = (verdict == "bad" and a.mode == "safe"
                and not prof.get("confirmed")
                and (v.get("dissatisfied_reason") or "") not in AUTO_BAD)
        if held:
            tally["held"] = tally.get("held", 0) + 1
            decision = "HELD for approval (profile not confirmed)"
            print(f"      -> held: {decision}")
        if a.apply and verdict in ("good", "bad") and not held:
            try:
                decision = _submit(cl, acid, l.resource_name, {**v, "verdict": verdict})
                tally["submitted"] += 1
                if decision.startswith("SUCCESS"):
                    tally["credits"] += 1
                    sent["credits"] += 1
                sent[verdict] += 1
                if verdict == "bad":
                    sent["whys"].append(v.get("dissatisfied_reason"))
                print(f"      -> feedback sent, Google credit decision: {decision}")
            except Exception as e:  # noqa: BLE001
                decision = f"error: {str(e)[:120]}"
                print(f"      -> feedback FAILED: {decision}")
        if a.apply:
            cc.kv_set(key, {"verdict": verdict, "confidence": conf, "why": why,
                            "rn": l.resource_name, "acid": acid,
                            "survey_answer": v.get("survey_answer"),
                            "dissatisfied_reason": v.get("dissatisfied_reason"),
                            "satisfied_reason": v.get("satisfied_reason"),
                            "need": v.get("caller_need"),
                            "summary": v.get("summary"),
                            "location": v.get("location_mentioned"),
                            "credit_decision": decision,
                            "created": l.creation_date_time,
                            "reviewed_at": datetime.now(timezone.utc).isoformat()})
    print(f"  summary: {tally}")
    if zero_streak >= 2:
        print(f"  ALERT: last {zero_streak} LSA calls connected for 0 seconds — "
              "the LSA profile may be forwarding to a dead number")
    if a.apply:
        log_feedback(cid, sent["good"], sent["bad"], sent["credits"], sent["whys"],
                     "lsa_lead_review.py review", {"account_id": acid})
        cc.kv_set("heartbeat:lsa-lead-review", {
            "at": datetime.now(timezone.utc).isoformat(), "last_slug": a.slug})
        cc.kv_set(f"{KV}-summary:{cid}", {
            **tally, "zero_streak": zero_streak, "days": a.days,
            "at": datetime.now(timezone.utc).isoformat()})
        if zero_streak >= 2:
            _sb("POST", "/rest/v1/marketing_ops_notes",
                {"company_id": cid, "author": "lsa-lead-review", "status": "open",
                 "body": f"[FLAG] LSA: last {zero_streak} calls connected for 0 "
                         "seconds. The LSA profile may forward to a dead number; "
                         "check Profile & budget > Phone."},
                prefer="return=minimal")
    return 0


def cmd_approve(a) -> int:
    """Send the HELD verdicts for one client (after Santino confirms its
    lead_profile). --confirm-profile also stamps lead_profile.confirmed so
    future nights send every verdict automatically."""
    cid = _cid_for(a.slug)
    co = _company(cid)
    cl = _mcc()
    if a.confirm_profile:
        row = (_sb("GET", f"/rest/v1/companies?id=eq.{cid}&select=integration_settings") or [{}])[0]
        ints = row.get("integration_settings") or {}
        if ints.get("lead_profile"):
            ints["lead_profile"]["confirmed"] = True
            ints["lead_profile"]["confirmed_at"] = datetime.now(timezone.utc).isoformat()
            _sb("PATCH", f"/rest/v1/companies?id=eq.{cid}",
                {"integration_settings": ints}, prefer="return=minimal")
            print(f"{a.slug}: lead profile confirmed")
    n = ok_n = credits = 0
    whys: list = []
    for k, v in (cc.kv_prefix(f"{KV}:{cid}:") or {}).items():
        if not str(v.get("credit_decision") or "").startswith("HELD"):
            continue
        if a.dry_run:
            print(f"  would send {v.get('why')} | {v.get('summary', '')[:100]}")
            continue
        try:
            dec = _submit(cl, v["acid"], v["rn"], {**v, "verdict": "bad"})
        except Exception as e:  # noqa: BLE001
            dec = f"error: {str(e)[:120]}"
        v["credit_decision"] = dec
        cc.kv_set(k, v)
        n += 1
        if sent_ok(dec):
            ok_n += 1
            whys.append(v.get("dissatisfied_reason"))
            credits += 1 if str(dec).startswith("SUCCESS") else 0
        print(f"  sent {v.get('why')} -> {dec} | {v.get('summary', '')[:100]}")
    if not a.dry_run:
        log_feedback(cid, 0, ok_n, credits, whys, "lsa_lead_review.py approve")
    print(f"{a.slug} ({co.get('name')}): {n} held verdict(s) sent")
    return 0


def cmd_profile(a) -> int:
    cid = _cid_for(a.slug)
    co = _company(cid)
    acid = str((_ints(co).get("lsa") or {}).get("customer_id") or "")
    cl = _mcc()
    ctx = _account_context(cl, acid) if acid else {"lsa_services": [], "lsa_areas": []}
    print(json.dumps(get_profile(cl, acid, co, ctx, reseed=a.reseed), indent=2))
    return 0


def cmd_list_due(_a) -> int:
    rows = _sb("GET", "/rest/v1/companies?select=id,name,integration_settings->lsa->>customer_id") or []
    sm = slug_map()
    due = []
    for r in rows:
        if r.get("customer_id") and sm.get(r["id"]):
            co = _company(r["id"])
            if not cc.company_inactive(co):
                due.append(sm[r["id"]])
    print(json.dumps(sorted(set(due))))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("review")
    r.add_argument("--slug", required=True)
    r.add_argument("--days", type=int, default=14)
    r.add_argument("--apply", action="store_true",
                   help="send feedback to Google + record verdicts (default: dry run)")
    r.add_argument("--mode", choices=("safe", "all"), default="safe",
                   help="safe: auto-send GOOD + spam/solicitation/duplicate; hold "
                        "job-type/geo/not-ready until lead_profile.confirmed")
    r.set_defaults(func=cmd_review)
    p = sub.add_parser("profile")
    p.add_argument("--slug", required=True)
    p.add_argument("--reseed", action="store_true")
    p.set_defaults(func=cmd_profile)
    ap_ = sub.add_parser("approve")
    ap_.add_argument("--slug", required=True)
    ap_.add_argument("--confirm-profile", action="store_true")
    ap_.add_argument("--dry-run", action="store_true")
    ap_.set_defaults(func=cmd_approve)
    sub.add_parser("list-due").set_defaults(func=cmd_list_due)
    a = ap.parse_args()
    cc.load_env()
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
