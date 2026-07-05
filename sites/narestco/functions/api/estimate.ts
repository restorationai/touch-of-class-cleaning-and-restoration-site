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
    `companies?id=eq.${env.COMPANY_ID}&select=email,transfer_primary_email&limit=1`
  )) as { email?: string; transfer_primary_email?: string }[] | null;
  const c = rows?.[0];
  return (c?.email || "").trim() || (c?.transfer_primary_email || "").trim() || fallback;
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
    "",
    "Description:",
    lead.description || "(none)",
    "",
    `Submitted:   ${new Date().toISOString()}`,
  ].join("\n");

  const payload: Record<string, unknown> = {
    personalizations: [{ to: [{ email: toEmail }] }],
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

async function sendSms(env: Env, lead: Record<string, string>): Promise<string> {
  const toNumber = (brand.phoneRaw || "").trim();
  if (!toNumber) return "skipped:no-brand-phone";

  const body =
    `New estimate request: ${lead.name} ${lead.phone} ${lead.city}` +
    (lead.description ? ` — ${lead.description.slice(0, 80)}` : "");

  // Preferred sender: the agency toll-free (one number for all clients), sent
  // from the agency Twilio subaccount. All three secrets are set together once
  // the number is purchased + toll-free-verified (scripts/provision_agency_tollfree.py).
  const agencyFrom = (env.ESTIMATE_SMS_FROM || "").trim();
  let fromNumber: string | undefined;
  let sid: string | undefined;
  let token: string | undefined;

  if (agencyFrom && env.ESTIMATE_SMS_SID && env.ESTIMATE_SMS_TOKEN) {
    fromNumber = agencyFrom;
    sid = env.ESTIMATE_SMS_SID;
    token = env.ESTIMATE_SMS_TOKEN;
  } else {
    // Fallback: the client's own tracking number — only when call-tracking is provisioned.
    if (!env.SUPABASE_URL || !env.SUPABASE_SERVICE_ROLE_KEY || !env.COMPANY_ID) return "skipped:no-supabase-env";
    const nums = (await sbGet(
      env,
      `company_phone_numbers?company_id=eq.${env.COMPANY_ID}&number_type=eq.call_tracking&select=phone_number&limit=1`
    )) as { phone_number?: string }[] | null;
    fromNumber = nums?.[0]?.phone_number;
    if (!fromNumber) return "skipped:no-call-tracking";

    const setup = (await sbGet(
      env,
      `company_phone_setup?id=eq.${env.COMPANY_ID}&select=twilio_subaccount_sid,twilio_auth_token&limit=1`
    )) as { twilio_subaccount_sid?: string; twilio_auth_token?: string }[] | null;
    sid = setup?.[0]?.twilio_subaccount_sid;
    token = setup?.[0]?.twilio_auth_token;
    if (!sid || !token) return "skipped:no-twilio-creds";
  }

  const r = await fetch(`https://api.twilio.com/2010-04-01/Accounts/${sid}/Messages.json`, {
    method: "POST",
    headers: {
      Authorization: `Basic ${btoa(`${sid}:${token}`)}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: new URLSearchParams({ From: fromNumber, To: toNumber, Body: body }),
  });
  if (r.ok) return "sent";
  return `error:${r.status}:${(await r.text()).slice(0, 200)}`;
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
    notes: `${lead.description || "(no description)"} — via ${brand.domain} free estimate form`,
  };
  if (lead.email) row.email = lead.email;
  if (env.COMPANY_ID) row.client_id = env.COMPANY_ID;

  const r = await fetch(`${env.SUPABASE_URL}/rest/v1/contacts`, {
    method: "POST",
    headers: {
      apikey: env.SUPABASE_SERVICE_ROLE_KEY,
      Authorization: `Bearer ${env.SUPABASE_SERVICE_ROLE_KEY}`,
      "Content-Type": "application/json",
      Prefer: "return=minimal",
    },
    body: JSON.stringify(row),
  });
  if (r.ok) return "inserted";
  return `error:${r.status}:${(await r.text()).slice(0, 200)}`;
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
  };
  if (!lead.name || !lead.phone || !lead.city) {
    return json({ ok: false, error: "missing-required-fields" }, 400);
  }

  const toEmail = await resolveRecipient(env).catch(() => (brand.email || "").trim());

  const [email, sms, db] = await Promise.all([
    sendEmail(env, lead, toEmail).catch((e) => `error:${String(e).slice(0, 200)}`),
    sendSms(env, lead).catch((e) => `error:${String(e).slice(0, 200)}`),
    insertContact(env, lead).catch((e) => `error:${String(e).slice(0, 200)}`),
  ]);

  // Email is the primary delivery channel; SMS + DB are best-effort extras.
  const ok = email === "sent";
  const body: Record<string, unknown> = { ok, email, sms, db };
  // Diagnostic only: expose the resolved recipient on explicit TEST submissions
  // so re-tests can verify routing. Never included on real leads.
  if (lead.description.includes("TEST")) body.to = toEmail;
  return json(body, ok ? 200 : 502);
};
