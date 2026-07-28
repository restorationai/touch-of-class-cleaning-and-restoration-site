// Embedded fallback (KV is the primary source; keeps working if KV is unset).
const MAP = {
  "narestco": { cid: "CO-1771290587387", name: "National Restoration Construction" },
  "davis-construction": { cid: "CO-1778778644861", name: "Davis Construction Contractors" },
  "homepriderestorationandcleaning": { cid: "CO-1780333664867", name: "Home Pride Restoration and Cleaning" },
};
// Public intake routes sharing this worker + slug map:
//   /gbpphotos/{slug}     → job-photos fn   (field-crew photos, EXIF-stripped JPEGs)
//   /logo/{slug}          → logo-upload fn  (client logo, ORIGINAL bytes preserved)
//   /hub/{slug}/{token}   → crew hub: review QR, request-a-review, photo/file links
//     (token lives in KV next to the client record — secret per company)
const ROUTES = {
  gbpphotos: { fn: "https://nyscciinkhlutvqkgyvq.supabase.co/functions/v1/job-photos", kind: "jobphotos" },
  logo: { fn: "https://nyscciinkhlutvqkgyvq.supabase.co/functions/v1/logo-upload", kind: "logoupload" },
};
const SB_URL = "https://nyscciinkhlutvqkgyvq.supabase.co";
function b64url(bytes){let bin="";const b=new Uint8Array(bytes);for(let i=0;i<b.length;i++)bin+=String.fromCharCode(b[i]);return btoa(bin).replace(/\+/g,"-").replace(/\//g,"_").replace(/=+$/,"");}
async function hmac(secret,msg){const key=await crypto.subtle.importKey("raw",new TextEncoder().encode(secret),{name:"HMAC",hash:"SHA-256"},false,["sign"]);const sig=await crypto.subtle.sign("HMAC",key,new TextEncoder().encode(msg));return b64url(sig);}
async function lookup(slug, env){
  if (env && env.UPLOAD_MAP) {
    try { const v = await env.UPLOAD_MAP.get(slug); if (v) return JSON.parse(v); } catch (e) {}
  }
  return MAP[slug] || null;
}
const esc = (s) => String(s || "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

function hubPage(slug, token, client) {
  const name = esc(client.name);
  const reviewUrl = client.review_url || "";
  const qrImg = reviewUrl
    ? `https://api.qrserver.com/v1/create-qr-code/?size=560x560&margin=2&data=${encodeURIComponent(reviewUrl)}`
    : "";
  return `<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">
<title>${name} — Crew Hub</title>
<style>
:root{color-scheme:light}*{box-sizing:border-box;margin:0}
body{font-family:-apple-system,system-ui,sans-serif;background:#f1f5f9;color:#0f172a;min-height:100vh}
.wrap{max-width:430px;margin:0 auto;padding:20px 16px 40px}
h1{font-size:19px;margin:4px 0 2px}.sub{color:#64748b;font-size:13px;margin-bottom:18px}
.tile{display:block;width:100%;background:#fff;border:1px solid #e2e8f0;border-radius:16px;padding:18px;margin-bottom:12px;text-align:left;font-size:16px;font-weight:700;color:#0f172a;text-decoration:none;box-shadow:0 1px 2px rgba(15,23,42,.05);cursor:pointer}
.tile small{display:block;font-weight:500;color:#64748b;font-size:13px;margin-top:3px}
.tile .ic{font-size:22px;margin-right:8px}
#qr,#rr{display:none;position:fixed;inset:0;background:#fff;z-index:50;padding:24px 16px;overflow:auto}
#qr.open,#rr.open{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px}
#qr img{width:min(78vw,340px);height:auto;border:1px solid #e2e8f0;border-radius:12px;padding:8px;background:#fff}
.close{position:absolute;top:14px;right:14px;background:#f1f5f9;border:none;border-radius:999px;width:38px;height:38px;font-size:17px;cursor:pointer}
.qrcap{font-size:17px;font-weight:800;text-align:center}.qrsub{color:#64748b;font-size:13px;text-align:center;max-width:280px}
form{width:100%;max-width:340px;display:flex;flex-direction:column;gap:10px}
input{width:100%;padding:14px;border:1px solid #cbd5e1;border-radius:12px;font-size:16px}
.btn{background:#2563eb;color:#fff;border:none;border-radius:12px;padding:15px;font-size:16px;font-weight:700;cursor:pointer}
.msg{font-size:14px;text-align:center;min-height:18px}.ok{color:#059669}.err{color:#dc2626}
</style></head><body><div class="wrap">
<h1>${name}</h1><div class="sub">Crew hub — bookmark this page</div>
${reviewUrl ? `<button class="tile" onclick="document.getElementById('qr').classList.add('open')"><span class="ic">⭐</span>Show Review QR<small>Hand your phone to the customer to scan</small></button>` : ""}
<button class="tile" onclick="document.getElementById('rr').classList.add('open')"><span class="ic">💬</span>Request a Review<small>We'll text the customer a review link for you</small></button>
<a class="tile" href="/gbpphotos/${slug}"><span class="ic">📷</span>Upload Job Photos<small>Before &amp; after shots go to Google and the website</small></a>
<a class="tile" href="/logo/${slug}"><span class="ic">📎</span>Send Us Files<small>Logo or other files for the marketing team</small></a>
<div id="qr"><button class="close" onclick="this.parentElement.classList.remove('open')">✕</button>
<div class="qrcap">Scan to leave us a review</div>
${qrImg ? `<img src="${qrImg}" alt="Review QR code">` : ""}
<div class="qrsub">Opens our Google review page — takes about 20 seconds</div></div>
<div id="rr"><button class="close" onclick="this.parentElement.classList.remove('open')">✕</button>
<div class="qrcap">Request a review</div>
<div class="qrsub">Enter the customer's name and cell — our system takes it from there.</div>
<form id="rrf"><input name="name" placeholder="Customer name" required autocomplete="off">
<input name="phone" placeholder="Cell number" type="tel" required autocomplete="off">
<button class="btn" type="submit">Send review request</button><div class="msg" id="rrmsg"></div></form></div>
<script>
document.getElementById('rrf').addEventListener('submit', async (e) => {
  e.preventDefault();
  const f = e.target, m = document.getElementById('rrmsg');
  m.className = 'msg'; m.textContent = 'Sending...';
  try {
    const r = await fetch(location.pathname, {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({action:'review-request', name:f.name.value, phone:f.phone.value})});
    const d = await r.json();
    if (d.ok) { m.className='msg ok'; m.textContent='Done! ' + (d.note || 'Review request queued.'); f.reset(); }
    else { m.className='msg err'; m.textContent = d.error || 'Something went wrong.'; }
  } catch (err) { m.className='msg err'; m.textContent='Network error, try again.'; }
});
</script></div></body></html>`;
}

async function handleReviewRequest(client, body, env) {
  const name = String(body.name || "").trim();
  const digits = String(body.phone || "").replace(/\D/g, "");
  const ten = digits.length === 11 && digits.startsWith("1") ? digits.slice(1) : digits;
  if (!name || ten.length !== 10) return { ok: false, error: "Enter a name and a 10-digit cell number." };
  const phone = "+1" + ten;
  const sb = (path, init) => fetch(`${SB_URL}/rest/v1/${path}`, {
    ...init,
    headers: { apikey: env.SB_SERVICE_KEY, Authorization: `Bearer ${env.SB_SERVICE_KEY}`,
               "Content-Type": "application/json", Prefer: "return=representation", ...(init && init.headers) },
  });
  // find-or-create the contact (match on last-10 phone)
  let contactId = null;
  const q = await sb(`contacts?client_id=eq.${client.cid}&phone=eq.${encodeURIComponent(phone)}&select=id`, {});
  if (q.ok) { const rows = await q.json(); if (rows[0]) contactId = rows[0].id; }
  if (!contactId) {
    const parts = name.split(/\s+/);
    const ins = await sb("contacts", { method: "POST", body: JSON.stringify({
      client_id: client.cid, name, first_name: parts[0], last_name: parts.slice(1).join(" ") || null,
      phone, tags: ["Reactivation List", "Crew Hub"], type: "customer" }) });
    if (!ins.ok) return { ok: false, error: "Could not save the customer." };
    contactId = (await ins.json())[0].id;
  }
  // parked review request — the team's send gates decide when it goes out
  const slugChars = "abcdefghjkmnpqrstuvwxyz23456789";
  let tslug = ""; const rnd = crypto.getRandomValues(new Uint8Array(12));
  for (const b of rnd) tslug += slugChars[b % slugChars.length];
  const rr = await sb("review_requests", { method: "POST", headers: { Prefer: "return=minimal" },
    body: JSON.stringify({ company_id: client.cid, contact_id: contactId, campaign_type: "reactivation",
      tracking_slug: tslug, status: "pending", step_number: 1, next_send_at: null, source: "crew_hub" }) });
  if (!rr.ok) {
    // some deployments lack the source column — retry without it
    const rr2 = await sb("review_requests", { method: "POST", headers: { Prefer: "return=minimal" },
      body: JSON.stringify({ company_id: client.cid, contact_id: contactId, campaign_type: "reactivation",
        tracking_slug: tslug, status: "pending", step_number: 1, next_send_at: null }) });
    if (!rr2.ok) return { ok: false, error: "Could not queue the review request." };
  }
  return { ok: true, note: "The marketing team has it from here." };
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    const hub = url.pathname.match(/^\/hub\/([a-z0-9-]+)\/([a-z0-9]+)\/?$/i);
    if (hub) {
      const slug = hub[1].toLowerCase();
      const client = await lookup(slug, env);
      if (!client || !client.hub || client.hub !== hub[2]) {
        return new Response("This link isn't set up. Please check the link.", { status: 404 });
      }
      if (request.method === "POST") {
        let body = {};
        try { body = await request.json(); } catch (e) {}
        if (body.action !== "review-request") {
          return Response.json({ ok: false, error: "Unknown action." }, { status: 400 });
        }
        if (!env.SB_SERVICE_KEY) return Response.json({ ok: false, error: "Hub not fully configured." }, { status: 500 });
        return Response.json(await handleReviewRequest(client, body, env));
      }
      return new Response(hubPage(slug, hub[2], client), {
        headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" } });
    }

    // /connect/{slug} → 302 to the client's current signed Google-connect
    // URL (KV key connect:{slug}, written when client_ops_sync mints an
    // ask). The raw Supabase links are unreadable and got dropped from an
    // SMS entirely (Jeff/MCC 2026-07-25); short link, full signed token at
    // the destination.
    const cn = url.pathname.match(/^\/connect\/([a-z0-9-]+)\/?$/i);
    if (cn) {
      let dest = null;
      if (env && env.UPLOAD_MAP) {
        try { dest = await env.UPLOAD_MAP.get("connect:" + cn[1].toLowerCase()); } catch (e) {}
      }
      if (dest) return Response.redirect(dest, 302);
      return new Response("This connect link isn't active anymore. Text us and we'll send a fresh one.",
        { status: 404 });
    }

    const m = url.pathname.match(/^\/(gbpphotos|logo)\/([a-z0-9-]+)\/?$/i);
    if (!m) return new Response("Not found", { status: 404 });
    const route = ROUTES[m[1].toLowerCase()];
    const client = await lookup(m[2].toLowerCase(), env);
    if (!route || !client) return new Response("This upload link isn't set up. Please check the link.", { status: 404 });
    const payload = { k: route.kind, cid: client.cid, name: client.name, exp: Math.floor(Date.now()/1000) + 5*365*86400 };
    const pb = b64url(new TextEncoder().encode(JSON.stringify(payload)));
    const token = pb + "." + (await hmac(env.SIGNING_SECRET, pb));
    const init = { method: request.method, headers: {} };
    if (request.method === "POST") { init.body = await request.arrayBuffer(); init.headers["Content-Type"] = request.headers.get("Content-Type") || "image/jpeg"; }
    // forward the page's own query params (cat/note/fn for categorized
    // uploads) alongside our signed token — previously dropped (2026-07-24)
    const fwd = new URLSearchParams(url.search);
    fwd.set("t", token);
    const resp = await fetch(route.fn + "?" + fwd.toString(), init);
    const headers = new Headers();
    headers.set("Content-Type", request.method === "GET" ? "text/html; charset=utf-8" : "application/json; charset=utf-8");
    headers.set("Cache-Control", "no-store");
    return new Response(resp.body, { status: resp.status, headers });
  }
};
