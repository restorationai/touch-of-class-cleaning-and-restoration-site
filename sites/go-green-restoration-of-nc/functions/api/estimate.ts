// POST /api/estimate — Free Estimate lead form handler (Cloudflare Pages Function).
//
// Pipeline per submission:
//   1. Spam gate: honeypot (`company_website`) + min-render-time token (`fets`,
//      set client-side at page load; must be >= 3s old). Bots get a silent 200.
//   2. Email the client via SendGrid REST (from the verified restorationai.io
//      sender, reply-to the lead when they gave an email). Recipient is resolved
//      at runtime from Supabase: companies.email -> companies.transfer_primary_email
//      -> brand.email (static fallback). No agency BCC — the CRM row (step 4) is
//      our visibility.
//   3. SMS the client's real line. From-number: ESTIMATE_SMS_FROM (agency
//      toll-free, sent via the agency Twilio subaccount creds) when configured;
//      otherwise the client's own Twilio call-tracking number (company_phone_numbers
//      row with number_type=call_tracking, creds in company_phone_setup). Non-fatal.
//   4. Insert a CRM contact row into Supabase `contacts` (the app's contact/job
//      pipeline table; client_id = COMPANY_ID). Non-fatal.
//
// Env (Cloudflare Pages project settings — see rank-ai repo, set via API):
//   SENDGRID_API_KEY           secret  — SendGrid mail send
//   SUPABASE_URL               secret  — app Supabase project URL
//   SUPABASE_SERVICE_ROLE_KEY  secret  — service role (recipient + SMS lookup + contact insert)
//   COMPANY_ID                 plain   — app company id, e.g. CO-1771290587387
//   ESTIMATE_SMS_FROM          secret  — OPTIONAL agency toll-free E.164 (set once
//                                        purchased + verified; unset = client tracking number)
//   ESTIMATE_SMS_SID           secret  — OPTIONAL agency Twilio subaccount SID (set with FROM)
//   ESTIMATE_SMS_TOKEN         secret  — OPTIONAL agency Twilio subaccount auth token (set with FROM)
//
// Brand identity (client email, phone, domain) is imported from the site's own
// brand.ts so this file is identical across client sites.
import { brand } from "../../src/lib/brand";

type Env = {
  SENDGRID_API_KEY?: string;
  SUPABASE_URL?: string;
  SUPABASE_SERVICE_ROLE_KEY?: string;
  COMPANY_ID?: string;
  FALLBACK_TWILIO_SID?: string;
  FALLBACK_TWILIO_TOKEN?: string;
  FALLBACK_TWILIO_FROM?: string;
  ESTIMATE_SMS_FROM?: string;
  ESTIMATE_SMS_SID?: string;
  ESTIMATE_SMS_TOKEN?: string;
};

const FROM_EMAIL = "no-reply@restorationai.io"; // verified SendGrid sender (same as rank-ai scripts)
const MIN_RENDER_MS = 3000;

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

const clean = (v: unknown, max: number) =>
  String(v ?? "").replace(/\s+/g, " ").trim().slice(0, max);

// Who gets the lead email. Live value comes from the app DB so the client can
// change it without a site redeploy: companies.email -> companies.transfer_primary_email
// -> brand.email (baked-in fallback).
async function resolveRecipient(env: Env): Promise<string> {
  const fallback = (brand.email || "").trim();
  if (!env.SUPABASE_URL || !env.SUPABASE_SERVICE_ROLE_KEY || !env.COMPANY_ID) return fallback;
  const rows = (await sbGet(
    env,
    `companies?id=eq.${env.COMPANY_ID}&select=email,transfer_primary_email,integration_settings&limit=1`
  )) as { email?: string; transfer_primary_email?: string;
          integration_settings?: { lead_notify_emails?: string[] } }[] | null;
  const c = rows?.[0];
  // Client-managed recipients list (RT Olson/BDA 2026-09-15: needed a third
  // catch-all address). Merged with the two legacy fields, deduped.
  const extra = (c?.integration_settings?.lead_notify_emails || [])
    .map((x) => String(x || "").trim()).filter(Boolean);
  // BOTH addresses get the lead when both exist (Bob/RT Olson 2026-09-15:
  // office@ was landing in a folder nobody read; a second recipient is
  // cheap insurance). Comma-joined; sendEmail splits.
  const both = [(c?.email || "").trim(), (c?.transfer_primary_email || "").trim(), ...extra]
    .filter((x, i, a) => x && a.indexOf(x) === i);
  return both.length ? both.join(",") : fallback;
}

async function sendEmail(env: Env, lead: Record<string, string>, toEmail: string): Promise<string> {
  if (!env.SENDGRID_API_KEY) return "skipped:no-key";
  if (!toEmail) return "skipped:no-recipient";

  const lines = [
    `New Free Estimate request from ${brand.domain}`,
    "",
    `Name:        ${lead.name}`,
    `Phone:       ${lead.phone}`,
    `City/ZIP:    ${lead.city}`,
    `Email:       ${lead.email || "(not provided)"}`,
    `Lead source: ${lead.lead_source}${lead.attribution ? ` (${lead.attribution})` : ""}`,
    "",
    "Description:",
    lead.description || "(none)",
    "",
    `Submitted:   ${new Date().toISOString()}`,
  ].join("\n");

  const payload: Record<string, unknown> = {
    personalizations: [{ to: toEmail.split(",").map((e) => ({ email: e.trim() })) }],
    from: { email: FROM_EMAIL, name: `${brand.displayName} Website` },
    subject: `New Free Estimate request — ${lead.name}, ${lead.city}`,
    content: [{ type: "text/plain", value: lines }],
  };
  if (lead.email && /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(lead.email)) {
    payload.reply_to = { email: lead.email, name: lead.name };
  }

  const r = await fetch("https://api.sendgrid.com/v3/mail/send", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.SENDGRID_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (r.status === 202) return "sent";
  return `error:${r.status}:${(await r.text()).slice(0, 200)}`;
}

async function sendLeadAutoReply(env: Env, lead: Record<string, string>): Promise<string> {
  // C13 (Santino 2026-09-16): the instant "we got it" email to the LEAD.
  // Transactional, once, only when they volunteered an email. Reply-to is
  // the business's real inbox so answering reaches the client directly.
  // The push to CALL mirrors the post-submit screen: an emergency lead who
  // calls converts; one who waits for a callback keeps shopping.
  if (!env.SENDGRID_API_KEY) return "skipped:no-key";
  const to = (lead.email || "").trim();
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(to)) return "skipped:no-email";
  const phone = (brand.phone || "").trim();
  const lines = [
    `Hi ${(lead.name || "").split(" ")[0] || "there"},`,
    "",
    `We received your request and our team is on it. You'll hear from us shortly.`,
    "",
    phone
      ? `If this is an emergency, don't wait on us: call ${phone} now and we'll dispatch right away.`
      : "",
    "",
    `${brand.displayName}`,
    phone ? `${phone}` : "",
    `https://${brand.domain}`,
  ].filter((l, i, a) => l !== "" || a[i - 1] !== "").join("\n");
  const r = await fetch("https://api.sendgrid.com/v3/mail/send", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.SENDGRID_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      personalizations: [{ to: [{ email: to }] }],
      from: { email: FROM_EMAIL, name: brand.displayName },
      reply_to: { email: (brand.email || FROM_EMAIL), name: brand.displayName },
      subject: `We got your request — ${brand.displayName}`,
      content: [{ type: "text/plain", value: lines }],
    }),
  });
  return r.status === 202 ? "sent" : `error:${r.status}`;
}

async function sbGet(env: Env, path: string): Promise<unknown[] | null> {
  const r = await fetch(`${env.SUPABASE_URL}/rest/v1/${path}`, {
    headers: {
      apikey: env.SUPABASE_SERVICE_ROLE_KEY!,
      Authorization: `Bearer ${env.SUPABASE_SERVICE_ROLE_KEY}`,
    },
  });
  if (!r.ok) return null;
  return (await r.json()) as unknown[];
}

async function resolveSmsSender(
  env: Env,
): Promise<{ from: string; sid: string; token: string } | { skip: string }> {
  // SENDER LADDER (C9 refactor 2026-09-16 — one resolver for both the
  // office alert and the prospect confirmation): the client's own APPROVED
  // toll-free first (house sender rule), then the agency toll-free
  // (ESTIMATE_SMS_*, set fleet-wide by agency_tf_watch.py at verification
  // approval), then the client's provisioned tracking number, then the
  // legacy FALLBACK_TWILIO_* envs.
  if (env.SUPABASE_URL && env.SUPABASE_SERVICE_ROLE_KEY && env.COMPANY_ID) {
    const ps = (await sbGet(
      env,
      `company_phone_setup?id=eq.${env.COMPANY_ID}&select=compliance_status,agent_phone_1,twilio_subaccount_sid,twilio_auth_token&limit=1`
    )) as Record<string, string>[] | null;
    const p0 = ps?.[0];
    if (p0?.compliance_status === "approved" && p0.agent_phone_1
        && p0.twilio_subaccount_sid && p0.twilio_auth_token) {
      return { from: p0.agent_phone_1, sid: p0.twilio_subaccount_sid, token: p0.twilio_auth_token };
    }
  }
  if (env.ESTIMATE_SMS_FROM && env.ESTIMATE_SMS_SID && env.ESTIMATE_SMS_TOKEN) {
    return { from: env.ESTIMATE_SMS_FROM.trim(), sid: env.ESTIMATE_SMS_SID, token: env.ESTIMATE_SMS_TOKEN };
  }
  if (!env.SUPABASE_URL || !env.SUPABASE_SERVICE_ROLE_KEY || !env.COMPANY_ID) return { skip: "skipped:no-supabase-env" };
  const nums = (await sbGet(
    env,
    `company_phone_numbers?company_id=eq.${env.COMPANY_ID}&number_type=eq.call_tracking&select=phone_number&limit=1`
  )) as { phone_number?: string }[] | null;
  const fromNumber = nums?.[0]?.phone_number;
  const setup = (await sbGet(
    env,
    `company_phone_setup?id=eq.${env.COMPANY_ID}&select=twilio_subaccount_sid,twilio_auth_token&limit=1`
  )) as { twilio_subaccount_sid?: string; twilio_auth_token?: string }[] | null;
  const sid = setup?.[0]?.twilio_subaccount_sid;
  const token = setup?.[0]?.twilio_auth_token;
  if (fromNumber && sid && token) return { from: fromNumber, sid, token };
  if (env.FALLBACK_TWILIO_SID && env.FALLBACK_TWILIO_TOKEN && env.FALLBACK_TWILIO_FROM) {
    return { from: env.FALLBACK_TWILIO_FROM, sid: env.FALLBACK_TWILIO_SID, token: env.FALLBACK_TWILIO_TOKEN };
  }
  return { skip: fromNumber ? "skipped:no-twilio-creds" : "skipped:no-call-tracking" };
}

async function twilioSend(
  sender: { from: string; sid: string; token: string }, to: string, body: string,
): Promise<{ ok: boolean; err: string }> {
  const r = await fetch(`https://api.twilio.com/2010-04-01/Accounts/${sender.sid}/Messages.json`, {
    method: "POST",
    headers: {
      Authorization: `Basic ${btoa(`${sender.sid}:${sender.token}`)}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: new URLSearchParams({ From: sender.from, To: to, Body: body }),
  });
  return { ok: r.ok, err: r.ok ? "" : `${r.status}:${(await r.text()).slice(0, 120)}` };
}

async function sendSms(env: Env, lead: Record<string, string>): Promise<string> {
  // RECIPIENTS (Bob/RT Olson 2026-09-15): the client-managed SMS list
  // (integration_settings.lead_notify_sms, edited on the Lead Notifications
  // card) — falls back to the brand line when the list is empty.
  let recipients: string[] = [];
  if (env.SUPABASE_URL && env.SUPABASE_SERVICE_ROLE_KEY && env.COMPANY_ID) {
    const co = (await sbGet(
      env,
      `companies?id=eq.${env.COMPANY_ID}&select=integration_settings&limit=1`
    )) as { integration_settings?: { lead_notify_sms?: string[] } }[] | null;
    recipients = (co?.[0]?.integration_settings?.lead_notify_sms || [])
      .map((x) => String(x || "").trim()).filter(Boolean);
  }
  const toNumber = (brand.phoneRaw || "").trim();
  if (recipients.length === 0) {
    if (!toNumber) return "skipped:no-brand-phone";
    recipients = [toNumber];
  }

  const sender = await resolveSmsSender(env);
  if ("skip" in sender) return sender.skip;

  const body =
    `New estimate request: ${lead.name} ${lead.phone} ${lead.city}` +
    (lead.description ? ` — ${lead.description.slice(0, 80)}` : "");

  let sent = 0;
  let lastErr = "";
  for (const to of recipients) {
    const r = await twilioSend(sender, to, body);
    if (r.ok) sent++;
    else lastErr = r.err;
  }
  if (sent > 0) return `sent:${sent}/${recipients.length}`;
  return `error:${lastErr || "unknown"}`;
}

async function sendProspectSms(env: Env, lead: Record<string, string>): Promise<string> {
  // C9 (Bob/RT Olson): one transactional confirmation to the LEAD, only
  // when they checked the consent box on the form. Points them at the
  // phone line — a submitted-then-called lead closes; one that waits for
  // a callback shops on.
  if (lead.sms_consent !== "yes") return "skipped:no-consent";
  if (!lead.phone) return "skipped:no-phone";
  const sender = await resolveSmsSender(env);
  if ("skip" in sender) return sender.skip;
  const displayPhone = (brand.phone || brand.phoneRaw || "").trim();
  const body =
    `${brand.shortName || brand.displayName}: got your request — ` +
    `we're on it and will call you shortly.` +
    (displayPhone ? ` For emergencies call us now: ${displayPhone}.` : "") +
    ` Reply STOP to opt out.`;
  const r = await twilioSend(sender, lead.phone, body);
  return r.ok ? "sent" : `error:${r.err}`;
}

async function insertContact(env: Env, lead: Record<string, string>): Promise<string> {
  if (!env.SUPABASE_URL || !env.SUPABASE_SERVICE_ROLE_KEY) return "skipped:no-supabase-env";
  const row: Record<string, unknown> = {
    name: lead.name,
    phone: lead.phone,
    city: lead.city,
    type: "Homeowner",
    pipeline_stage: "Inbound",
    role: "Other",
    tags: ["website", "free-estimate"],
    notes: `${lead.description || "(no description)"} — via ${brand.domain} free estimate form` +
      ` [source: ${lead.lead_source}${lead.attribution ? `; ${lead.attribution}` : ""}]`,
  };
  if (lead.email) row.email = lead.email;
  if (env.COMPANY_ID) row.client_id = env.COMPANY_ID;

  const sbHeaders = {
    apikey: env.SUPABASE_SERVICE_ROLE_KEY,
    Authorization: `Bearer ${env.SUPABASE_SERVICE_ROLE_KEY}`,
    "Content-Type": "application/json",
  };
  // (submission event row moved to the main handler 2026-09-15 so it can
  // carry notify_status — the delivery outcome of each channel.)
  const r = await fetch(`${env.SUPABASE_URL}/rest/v1/contacts`, {
    method: "POST",
    headers: { ...sbHeaders, Prefer: "return=minimal" },
    body: JSON.stringify(row),
  });
  if (r.ok) return "inserted";
  const errText = (await r.text()).slice(0, 300);
  // Repeat lead (2026-09-10, Santino's test vanished): contacts are unique
  // per (client_id, phone), so a second submission from a known number 409s.
  // Append to the existing row instead of dropping the lead on the floor.
  if (r.status === 409 && env.COMPANY_ID) {
    const q = `${env.SUPABASE_URL}/rest/v1/contacts?client_id=eq.${env.COMPANY_ID}` +
      `&phone=eq.${encodeURIComponent(lead.phone)}&select=id,notes&limit=1`;
    const existing = (await (await fetch(q, { headers: sbHeaders })).json()) as
      { id: string; notes?: string }[];
    if (existing?.[0]) {
      const stamp = new Date().toISOString().slice(0, 10);
      const addition = `[${stamp}] repeat form submission: ${row.notes}`;
      const merged = `${existing[0].notes || ""}\n${addition}`.slice(0, 8000);
      const u = await fetch(`${env.SUPABASE_URL}/rest/v1/contacts?id=eq.${existing[0].id}`, {
        method: "PATCH", headers: { ...sbHeaders, Prefer: "return=minimal" },
        body: JSON.stringify({ notes: merged, updated_at: new Date().toISOString() }),
      });
      if (u.ok) return "updated-existing";
    }
  }
  return `error:${r.status}:${errText}`;
}

export const onRequestPost: PagesFunction<Env> = async ({ request, env }) => {
  let data: Record<string, unknown>;
  try {
    data = (await request.json()) as Record<string, unknown>;
  } catch {
    return json({ ok: false, error: "invalid-json" }, 400);
  }

  // Spam gates — bots get a quiet success so they don't adapt.
  if (clean(data.company_website, 200)) return json({ ok: true });
  const fets = Number(data.fets || 0);
  if (!fets || Date.now() - fets < MIN_RENDER_MS) return json({ ok: true });

  const lead = {
    name: clean(data.name, 120),
    phone: clean(data.phone, 30),
    city: clean(data.city, 80),
    email: clean(data.email, 160),
    description: clean(data.description, 2000),
    // Source attribution (2026-09-10): the form ships the same persisted
    // classification the DNI number swap uses, so leads attribute like calls.
    lead_source: clean(data.lead_source, 40) || "default",
    sms_consent: data.sms_consent === "yes" ? "yes" : "",
    attribution: [
      data.utm_source && `utm_source=${clean(data.utm_source, 80)}`,
      data.utm_medium && `utm_medium=${clean(data.utm_medium, 80)}`,
      data.utm_campaign && `utm_campaign=${clean(data.utm_campaign, 120)}`,
      // D17 (2026-09-16): real click-id values, not just "present" — the
      // id is what ties a lead (and any later offline conversion upload)
      // back to the exact ad click.
      data.gclid && `gclid=${clean(data.gclid, 120)}`,
      data.msclkid && `msclkid=${clean(data.msclkid, 120)}`,
      data.fbclid && `fbclid=${clean(data.fbclid, 120)}`,
      data.referrer && `ref=${clean(data.referrer, 200)}`,
      data.landing_page && `landing=${clean(data.landing_page, 200)}`,
    ].filter(Boolean).join(" | "),
  };
  if (!lead.name || !lead.phone || !lead.city) {
    return json({ ok: false, error: "missing-required-fields" }, 400);
  }

  const toEmail = await resolveRecipient(env).catch(() => (brand.email || "").trim());

  const [email, sms, db, prospectSms, autoReply] = await Promise.all([
    sendEmail(env, lead, toEmail).catch((e) => `error:${String(e).slice(0, 200)}`),
    sendSms(env, lead).catch((e) => `error:${String(e).slice(0, 200)}`),
    insertContact(env, lead).catch((e) => `error:${String(e).slice(0, 200)}`),
    sendProspectSms(env, lead).catch((e) => `error:${String(e).slice(0, 200)}`),
    sendLeadAutoReply(env, lead).catch((e) => `error:${String(e).slice(0, 200)}`),
  ]);

  // EVERY submission is its own event row (Santino 2026-09-10), now
  // carrying notify_status (2026-09-15: the RT Olson "did the client get
  // the email?" hunt becomes a glance at the card).
  if (env.SUPABASE_URL && env.SUPABASE_SERVICE_ROLE_KEY) {
    await fetch(`${env.SUPABASE_URL}/rest/v1/marketing_form_submissions`, {
      method: "POST",
      headers: {
        apikey: env.SUPABASE_SERVICE_ROLE_KEY,
        Authorization: `Bearer ${env.SUPABASE_SERVICE_ROLE_KEY}`,
        "Content-Type": "application/json", Prefer: "return=minimal",
      },
      body: JSON.stringify({
        company_id: env.COMPANY_ID || null,
        name: lead.name, phone: lead.phone, city: lead.city,
        email: lead.email || null, description: lead.description || null,
        lead_source: lead.lead_source, attribution: lead.attribution || null,
        notify_status: { email: { status: email, to: toEmail },
                         sms: { status: sms },
                         prospect_sms: { status: prospectSms,
                                         consent: lead.sms_consent === "yes" },
                         auto_reply: { status: autoReply } },
      }),
    }).catch(() => null);
  }

  // Email is the primary delivery channel; SMS + DB are best-effort extras.
  const ok = email === "sent";
  const body: Record<string, unknown> = { ok, email, sms, db, prospect_sms: prospectSms, auto_reply: autoReply };
  // Diagnostic only: expose the resolved recipient on explicit TEST submissions
  // so re-tests can verify routing. Never included on real leads.
  if (lead.description.includes("TEST")) body.to = toEmail;
  return json(body, ok ? 200 : 502);
};
