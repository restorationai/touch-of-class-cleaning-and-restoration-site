// Embedded fallback (KV is the primary source; keeps working if KV is unset).
const MAP = {
  "narestco": { cid: "CO-1771290587387", name: "National Restoration Construction" },
  "davis-construction": { cid: "CO-1778778644861", name: "Davis Construction Contractors" },
  "homepriderestorationandcleaning": { cid: "CO-1780333664867", name: "Home Pride Restoration and Cleaning" },
};
// Public intake routes sharing this worker + slug map:
//   /gbpphotos/{slug}     → job-photos fn   (field-crew photos, EXIF-stripped JPEGs)
//   /logo/{slug}          → logo-upload fn  (client logo + brand kit, ORIGINAL bytes)
//   /hub/{slug}/{token}   → crew hub: review QR, request-a-review, photo/file links
//     (token lives in KV next to the client record — secret per company)
//
// LARGE FILES (2026-08-03, Greg/PuroClean 75MB brand kit): this zone is on
// the Free plan (100MB request-body hard cap) and this worker used to buffer
// POST bodies into memory. Big uploads therefore NEVER pass through here —
// the /logo/{slug} page POSTs a tiny ?action=sign JSON (proxied below like
// any POST), gets a signed upload URL scoped to one storage path, and the
// browser PUTs the file DIRECT to Supabase storage (bucket cap 250MB).
// Small files still proxy through; the body is now STREAMED, not buffered.
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
  // SELF-HOSTED QR (2026-08-19, build queue #11): pre-generated per client
  // into the public branding bucket (scripts in upload_links_sync + one-time
  // fleet run). The third-party qrserver stays ONLY as an onerror fallback
  // for clients whose PNG has not been generated yet.
  const qrFallback = reviewUrl
    ? `https://api.qrserver.com/v1/create-qr-code/?size=560x560&margin=2&data=${encodeURIComponent(reviewUrl)}`
    : "";
  const qrImg = reviewUrl && client.cid
    ? `${SB_URL}/storage/v1/object/public/branding/${client.cid}/brand/review-qr.png`
    : qrFallback;
  return `<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">
<title>${name} Crew Hub</title>
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
#js{display:none;position:fixed;inset:0;background:#fff;z-index:50;padding:56px 16px 32px;overflow:auto}
#js.open{display:flex;flex-direction:column;align-items:center;gap:12px}
textarea{width:100%;padding:14px;border:1px solid #cbd5e1;border-radius:12px;font-size:16px;font-family:inherit;min-height:96px;resize:vertical}
.lbl{width:100%;font-size:13px;font-weight:600;color:#64748b;display:flex;flex-direction:column;gap:6px}
.pick{width:100%;display:flex;flex-direction:column;align-items:center;gap:4px;border:2px dashed #cbd5e1;border-radius:12px;padding:16px;text-align:center;cursor:pointer;font-size:15px;font-weight:700;color:#334155}
.pick span{font-weight:500;color:#64748b;font-size:12px}.pick input{display:none}
</style></head><body><div class="wrap">
<h1>${name}</h1><div class="sub">Crew hub, bookmark this page</div>
${reviewUrl ? `<button class="tile" onclick="document.getElementById('qr').classList.add('open')"><span class="ic">⭐</span>Show Review QR<small>Hand your phone to the customer to scan</small></button>` : ""}
<button class="tile" onclick="document.getElementById('rr').classList.add('open')"><span class="ic">💬</span>Request a Review<small>We'll text the customer a review link for you</small></button>
<a class="tile" href="/gbpphotos/${slug}"><span class="ic">📷</span>Upload Photos<small>Job shots, before &amp; afters, any photos &mdash; they go to Google and the website</small></a>
<a class="tile" href="/logo/${slug}"><span class="ic">📎</span>Send Us Files<small>Logo or other files for the marketing team</small></a>
<button class="tile" onclick="document.getElementById('js').classList.add('open')"><span class="ic">📝</span>Add a Job Story<small>Tell us about a job you just finished, we turn it into a website story</small></button>
<button class="tile" style="border:2px solid #dc2626" onclick="document.getElementById('db').style.display='block'"><span class="ic">📄</span>DBA / Trade Name Certificate<small>Snap a photo of your filed DBA paperwork &mdash; we verify the name and take it from there</small></button>
<div id="qr"><button class="close" onclick="this.parentElement.classList.remove('open')">✕</button>
<div class="qrcap">Scan to leave us a review</div>
${qrImg ? `<img src="${qrImg}" alt="Review QR code" onerror="this.onerror=null;this.src='${qrFallback}'">` : ""}
<div class="qrsub">Opens our Google review page, takes about 20 seconds</div>
<div class="qrsub" style="margin-top:6px;font-weight:600;color:#334155">If you can, mention the service we did and your city. It helps another neighbor find us.</div></div>
<div id="rr"><button class="close" onclick="this.parentElement.classList.remove('open')">✕</button>
<div class="qrcap">Request a review</div>
<div class="qrsub">Enter the customer's name and cell, our system takes it from there.</div>
<form id="rrf"><input name="name" placeholder="Customer name" required autocomplete="off">
<input name="phone" id="rrph" placeholder="Cell number" type="tel" inputmode="numeric" maxlength="14" required autocomplete="off">
<button class="btn" type="submit">Send review request</button><div class="msg" id="rrmsg"></div></form></div>
<div id="db" style="display:none;position:fixed;inset:0;background:#fff;z-index:50;padding:56px 16px 32px;overflow:auto"><button class="close" onclick="this.parentElement.style.display='none'">✕</button>
<div style="display:flex;flex-direction:column;align-items:center;gap:12px">
<div class="qrcap">DBA / Trade Name Certificate</div>
<div class="qrsub">A clear photo of the filed paperwork. We check that the registered name matches exactly, then get everything moving.</div>
<form id="dbf" style="width:100%;max-width:340px;display:flex;flex-direction:column;gap:10px">
<label class="pick" style="border-color:#dc2626;color:#b91c1c">＋ Add the certificate photo<span id="dbcount">The whole page, name readable</span><input id="dbfile" type="file" accept="image/*"></label>
<button class="btn" type="submit" id="dbbtn" style="background:#dc2626">Send certificate</button><div class="msg" id="dbmsg"></div></form></div></div>
<div id="js"><button class="close" onclick="this.parentElement.classList.remove('open')">✕</button>
<div class="qrcap">Add a job story</div>
<div class="qrsub">A couple of quick questions while the job is fresh. We turn your answers into a story on the website.</div>
<form id="jsf">
<textarea name="what" placeholder="What happened? (what you found when you got there)" required minlength="60" maxlength="4000"></textarea>
<textarea name="how" placeholder="How did you fix it? (what the crew did on this job)" required minlength="60" maxlength="4000"></textarea>
<input name="city" placeholder="City or neighborhood" required maxlength="120" autocomplete="off">
<input name="customer" placeholder="Customer first name (optional)" maxlength="60" autocomplete="off">
<label class="lbl">Rough date of the job<input name="performed_on" type="date"></label>
<label class="pick">＋ Before photos (optional)<span id="jscountb">When you arrived, the damage</span><input id="jsbefore" type="file" accept="image/*" multiple></label>
<label class="pick">＋ After photos (optional)<span id="jscounta">The finished result</span><input id="jsafter" type="file" accept="image/*" multiple></label>
<button class="btn" type="submit" id="jsbtn">Send job story</button><div class="msg" id="jsmsg"></div></form></div>
<script>
// Phone field: digits only, live-formatted (XXX) XXX-XXXX. E.164 goes on
// the wire (Santino 2026-09-10).
var rrph = document.getElementById('rrph');
function rrDigits(v){var d='';for(var i=0;i<v.length;i++){var c=v[i];if(c>='0'&&c<='9')d+=c;}if(d.length===11&&d[0]==='1')d=d.slice(1);return d.slice(0,10);}
function rrFormat(d){if(!d)return'';if(d.length<4)return'('+d;if(d.length<7)return'('+d.slice(0,3)+') '+d.slice(3);return'('+d.slice(0,3)+') '+d.slice(3,6)+'-'+d.slice(6);}
rrph.addEventListener('input', function(){ rrph.value = rrFormat(rrDigits(rrph.value)); });
document.getElementById('rrf').addEventListener('submit', async (e) => {
  e.preventDefault();
  const f = e.target, m = document.getElementById('rrmsg');
  const dg = rrDigits(f.phone.value);
  if (dg.length !== 10) { m.className='msg err'; m.textContent='Enter a 10-digit cell number.'; return; }
  m.className = 'msg'; m.textContent = 'Sending...';
  try {
    const r = await fetch(location.pathname, {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({action:'review-request', name:f.name.value, phone:'+1'+rrDigits(f.phone.value)})});
    const d = await r.json();
    if (d.ok) { m.className='msg ok'; m.textContent='Done! ' + (d.note || 'Review request queued.'); f.reset(); }
    else { m.className='msg err'; m.textContent = d.error || 'Something went wrong.'; }
  } catch (err) { m.className='msg err'; m.textContent='Network error, try again.'; }
});
// --- Add a Job Story ---
var jsBefore = [], jsAfter = [];
function jsPick(inputId, countId, hint, sink) {
  document.getElementById(inputId).addEventListener('change', function (e) {
    var got = Array.from(e.target.files || []).filter(function (f) { return f.type.indexOf('image/') === 0; }).slice(0, 8);
    sink.length = 0; got.forEach(function (f) { sink.push(f); });
    document.getElementById(countId).textContent =
      got.length ? got.length + ' photo' + (got.length > 1 ? 's' : '') + ' ready' : hint;
  });
}
jsPick('jsbefore', 'jscountb', 'When you arrived, the damage', jsBefore);
jsPick('jsafter', 'jscounta', 'The finished result', jsAfter);
// --- DBA certificate (red tile). One photo, EXIF-stripped like everything
// else, lands in docs/dba/ where the sweep vision-verifies the name.
var dbFile = null;
document.getElementById('dbfile').addEventListener('change', function (e) {
  var f = (e.target.files || [])[0];
  dbFile = f && f.type.indexOf('image/') === 0 ? f : null;
  document.getElementById('dbcount').textContent = dbFile ? '1 photo ready' : 'The whole page, name readable';
});
document.getElementById('dbf').addEventListener('submit', async (e) => {
  e.preventDefault();
  var m = document.getElementById('dbmsg'), b = document.getElementById('dbbtn');
  if (!dbFile) { m.className = 'msg err'; m.textContent = 'Add the certificate photo first.'; return; }
  b.disabled = true; m.className = 'msg'; m.textContent = 'Uploading...';
  try {
    var clean = await jsStrip(dbFile);
    var up = await fetch('/gbpphotos/${slug}?cat=dba&note=' + encodeURIComponent('DBA certificate via hub'),
      { method: 'POST', headers: { 'Content-Type': 'image/jpeg' }, body: clean });
    var d = await up.json();
    if (up.ok && d && d.ok) {
      m.className = 'msg ok'; m.textContent = 'Got it! We verify the name matches and text you either way.';
      e.target.reset(); dbFile = null;
      document.getElementById('dbcount').textContent = 'The whole page, name readable';
    } else { m.className = 'msg err'; m.textContent = (d && d.error) || 'Something went wrong, try again.'; }
  } catch (err) { m.className = 'msg err'; m.textContent = 'Network error, try again.'; }
  b.disabled = false;
});
var jsDate = document.querySelector('#jsf [name=performed_on]');
function jsToday() { return new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10); }
if (jsDate) jsDate.value = jsToday();
// Same mechanics as the Upload Photos page: canvas re-encode (EXIF/GPS gone), longest edge 2000px, JPEG.
function jsStrip(file) {
  return new Promise(function (resolve, reject) {
    var img = new Image();
    img.onload = function () {
      var w = img.width, h = img.height, MAX = 2000;
      if (Math.max(w, h) > MAX) { var s = MAX / Math.max(w, h); w = Math.round(w * s); h = Math.round(h * s); }
      var c = document.createElement('canvas'); c.width = w; c.height = h;
      c.getContext('2d').drawImage(img, 0, 0, w, h);
      c.toBlob(function (b) { b ? resolve(b) : reject(new Error('encode')); }, 'image/jpeg', 0.85);
    };
    img.onerror = reject;
    img.src = URL.createObjectURL(file);
  });
}
document.getElementById('jsf').addEventListener('submit', async (e) => {
  e.preventDefault();
  var f = e.target, m = document.getElementById('jsmsg'), b = document.getElementById('jsbtn');
  b.disabled = true; m.className = 'msg';
  var namesBefore = [], namesAfter = [];
  try {
    var groups = [[jsBefore, namesBefore, 'before'], [jsAfter, namesAfter, 'after']];
    var totalN = jsBefore.length + jsAfter.length, doneN = 0;
    for (var g = 0; g < groups.length; g++) {
      var files = groups[g][0], sink = groups[g][1], tag = groups[g][2];
      for (var i = 0; i < files.length; i++) {
        doneN++;
        m.textContent = 'Uploading photo ' + doneN + ' of ' + totalN + '...';
        try {
          var clean = await jsStrip(files[i]);
          var up = await fetch('/gbpphotos/${slug}?cat=job&note=' + encodeURIComponent('job story ' + tag + ': ' + f.city.value.slice(0, 80)),
            { method: 'POST', headers: { 'Content-Type': 'image/jpeg' }, body: clean });
          if (up.ok) { var ud = await up.json(); if (ud && ud.path) sink.push(String(ud.path).split('/').pop()); }
        } catch (perr) {}
      }
    }
    m.textContent = 'Sending your story...';
    var r = await fetch(location.pathname, { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'job-story', what: f.what.value, how: f.how.value, city: f.city.value,
        customer: f.customer.value, performed_on: f.performed_on.value,
        photos: namesBefore.concat(namesAfter),
        photos_before: namesBefore, photos_after: namesAfter }) });
    var d = await r.json();
    if (d.ok) {
      m.className = 'msg ok'; m.textContent = 'Got it! ' + (d.note || 'Story received.');
      f.reset(); jsBefore.length = 0; jsAfter.length = 0;
      document.getElementById('jscountb').textContent = 'When you arrived, the damage';
      document.getElementById('jscounta').textContent = 'The finished result';
      if (jsDate) jsDate.value = jsToday();
    } else { m.className = 'msg err'; m.textContent = d.error || 'Something went wrong.'; }
  } catch (err) { m.className = 'msg err'; m.textContent = 'Network error, try again.'; }
  b.disabled = false;
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
  // ARMED review request (2026-08-18, Bobby Olson's live test sat parked
  // forever): next_send_at=now makes the dispatcher pick it up on its next
  // 10-min pass — its own gates still enforce business hours (08:00-17:59
  // company-local) and the 1-per-20-min pace, so "queued at 5:30am" sends
  // at 9am exactly as we tell clients. NULL means parked-forever and is
  // reserved for bulk enrollments the team arms deliberately.
  const slugChars = "abcdefghjkmnpqrstuvwxyz23456789";
  let tslug = ""; const rnd = crypto.getRandomValues(new Uint8Array(12));
  for (const b of rnd) tslug += slugChars[b % slugChars.length];
  const armAt = new Date().toISOString();
  const rr = await sb("review_requests", { method: "POST", headers: { Prefer: "return=minimal" },
    body: JSON.stringify({ company_id: client.cid, contact_id: contactId, campaign_type: "reactivation",
      tracking_slug: tslug, status: "pending", step_number: 1, next_send_at: armAt, source: "crew_hub" }) });
  if (!rr.ok) {
    // some deployments lack the source column — retry without it
    const rr2 = await sb("review_requests", { method: "POST", headers: { Prefer: "return=minimal" },
      body: JSON.stringify({ company_id: client.cid, contact_id: contactId, campaign_type: "reactivation",
        tracking_slug: tslug, status: "pending", step_number: 1, next_send_at: armAt }) });
    if (!rr2.ok) return { ok: false, error: "Could not queue the review request." };
  }
  return { ok: true, note: "We'll text them a review link shortly." };
}

// "Add a Job Story": structured submission -> one [JOB STORY] ops note.
// case_study_intake.py's [JOB STORY] lane parses the JSON block verbatim,
// skips classification (it is a case study by construction) and publishes it
// through the same claims gates as every other case study.
async function handleJobStory(client, slug, body, env) {
  const clip = (v, n) => String(v || "").trim().slice(0, n);
  const what = clip(body.what, 4000), how = clip(body.how, 4000), city = clip(body.city, 120);
  if (!what || !how || !city) {
    return { ok: false, error: "Tell us what happened, how you fixed it, and the city." };
  }
  // first names only, always (site pages never carry surnames)
  const customer = clip(body.customer, 60).split(/\s+/)[0] || "";
  let performedOn = clip(body.performed_on, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(performedOn)) performedOn = new Date().toISOString().slice(0, 10);
  // photo filenames as returned by the /gbpphotos upload path (branding/{cid}/job-photos/)
  const cleanNames = (arr) => (Array.isArray(arr) ? arr : []).slice(0, 12)
    .map((p) => String(p).split("/").pop().replace(/[^\w.-]/g, "")).filter(Boolean);
  const photos = cleanNames(body.photos);
  // before/after split (2026-08-19, promised to Bobby on the 08-18 call):
  // site case-study pages + GBP posts can render the two groups separately.
  const photosBefore = cleanNames(body.photos_before);
  const photosAfter = cleanNames(body.photos_after);
  const story = {
    what_happened: what, how_fixed: how, city,
    customer_first_name: customer, performed_on: performedOn,
    photos, photos_before: photosBefore, photos_after: photosAfter,
    submitted_at: new Date().toISOString(),
  };
  const note = "[JOB STORY] " + slug + " submitted from the crew hub:\n" +
    JSON.stringify(story, null, 2);
  const r = await fetch(SB_URL + "/rest/v1/marketing_ops_notes", {
    method: "POST",
    headers: { apikey: env.SB_SERVICE_KEY, Authorization: "Bearer " + env.SB_SERVICE_KEY,
               "Content-Type": "application/json", Prefer: "return=minimal" },
    body: JSON.stringify({ company_id: client.cid, body: note, author: "hub", status: "open" }),
  });
  if (!r.ok) return { ok: false, error: "Could not save the story. Please try again." };
  return { ok: true, note: "Story received. Watch for it on the website." };
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
        if (body.action !== "review-request" && body.action !== "job-story") {
          return Response.json({ ok: false, error: "Unknown action." }, { status: 400 });
        }
        if (!env.SB_SERVICE_KEY) return Response.json({ ok: false, error: "Hub not fully configured." }, { status: 500 });
        if (body.action === "job-story") return Response.json(await handleJobStory(client, slug, body, env));
        return Response.json(await handleReviewRequest(client, body, env));
      }
      return new Response(hubPage(slug, hub[2], client), {
        headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" } });
    }

    // /dni/{slug}.json → per-client tracking-number map for the site's
    // source-attribution DNI script (2026-09-10). KV key dni:{slug}, synced
    // from integration_settings.call_tracking by scripts/dni_sync.py.
    const dni = url.pathname.match(/^\/dni\/([a-z0-9-]+)\.json$/i);
    if (dni) {
      let v = null;
      if (env && env.UPLOAD_MAP) {
        try { v = await env.UPLOAD_MAP.get("dni:" + dni[1].toLowerCase()); } catch (e) {}
      }
      return new Response(v || "{}", { headers: {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Cache-Control": "public, max-age=300" } });
    }

    // /qr/{key} → 302 to whatever URL KV holds under qr:{key}. Printed QR
    // codes (business cards) encode this stable link, so the destination is
    // editable forever with one KV write and no reprint (Tony/Coastal
    // 2026-09-10 was the first).
    const qr = url.pathname.match(/^\/qr\/([a-z0-9-]+)\/?$/i);
    if (qr) {
      let dest = null;
      if (env && env.UPLOAD_MAP) {
        try { dest = await env.UPLOAD_MAP.get("qr:" + qr[1].toLowerCase()); } catch (e) {}
      }
      if (dest) return Response.redirect(dest, 302);
      return new Response("This QR link isn't set up.", { status: 404 });
    }

    // /connect/{slug}[/{provider}] → 302 to a SIGNED connect URL for that
    // client. provider defaults to google; youtube supported (Santino
    // 2026-07-28: one short link shape for both). Token is minted fresh on
    // every click with CONNECT_SIGNING_SECRET (30-day exp), so the short
    // link never goes stale; KV key connect:{slug}[:{provider}] remains as
    // an override/fallback for clients not in the slug map. Raw Supabase
    // links are unreadable and got dropped from an SMS entirely (Jeff/MCC
    // 2026-07-25).
    const cn = url.pathname.match(/^\/connect\/([a-z0-9-]+)(?:\/(google|youtube))?\/?$/i);
    if (cn) {
      const slug = cn[1].toLowerCase();
      const provider = (cn[2] || "google").toLowerCase();
      if (env && env.CONNECT_SIGNING_SECRET) {
        const client = await lookup(slug, env);
        if (client && client.cid) {
          const payload = {
            cid: client.cid, p: provider, jti: crypto.randomUUID(),
            exp: Math.floor(Date.now() / 1000) + 30 * 86400,
            o: "https://app.restorationai.io",
          };
          const pb = b64url(new TextEncoder().encode(JSON.stringify(payload)));
          const sig = await hmac(env.CONNECT_SIGNING_SECRET, pb);
          return Response.redirect(SB_URL + "/functions/v1/connect-link-start?t=" + pb + "." + sig, 302);
        }
      }
      let dest = null;
      if (env && env.UPLOAD_MAP) {
        try {
          dest = await env.UPLOAD_MAP.get("connect:" + slug + (provider === "google" ? "" : ":" + provider));
        } catch (e) {}
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
    // Stream the body through (never buffer — a buffered 75MB brand kit
    // would eat the isolate's memory; big files bypass this path entirely
    // via signed direct-to-storage URLs, see header comment).
    if (request.method === "POST") { init.body = request.body; init.headers["Content-Type"] = request.headers.get("Content-Type") || "image/jpeg"; }
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
