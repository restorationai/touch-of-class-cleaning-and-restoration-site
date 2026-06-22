# Dev Spec — RestorationAI Analytics (GA4 + Microsoft Clarity)

One GA4 **property** for the entire lifecycle (marketing → signup → onboarding) so we can
follow a user end-to-end, plus Microsoft Clarity for qualitative session replay. Separation
between funnels is by **hostname / `funnel` parameter**, never by separate properties.

## Surfaces

| Surface | URL | `funnel` value | Notes |
|---|---|---|---|
| Website | restorationai.io | `site` | marketing |
| Quiz | audit.restorationai.io | `quiz` | A/B split test runs here |
| Opt Digital | apply.restorationai.io | `apply` | marketing funnel |
| **App** | app.restorationai.io | `app` | authenticated product: signup + 13-step onboarding |

All four are subdomains of `restorationai.io`, so GA4 stitches sessions across them
automatically with one tag — **no cross-domain configuration** (that's only for different
root domains).

---

## 1. GA4 — single property, single web stream

- **One** GA4 property, **one** web data stream (one Measurement ID `G-XXXXXXX`). Do **not**
  create a stream or property per subdomain.
- Install the same gtag on all four subdomains, with `funnel` hard-set per subdomain:

```html
<script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXX"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  // 'site' | 'quiz' | 'apply' | 'app' depending on the subdomain
  gtag('config', 'G-XXXXXXX', { funnel: 'quiz' });
</script>
```

### Why one property (not separate per funnel or for the app)
GA4 unifies users only **within** a property. Separate properties would count the same
person as different users across marketing → signup → app, destroying the full
acquisition→activation journey and the ability to attribute *which marketing source produces
users who finish onboarding*. One property keeps the journey intact; you still isolate any
funnel completely by filtering on `funnel`/`hostname`.

---

## 2. GA4 — custom dimensions

GA4 Admin → **Custom definitions → Create custom dimension** (all **Event**-scoped),
parameter names matching exactly:

| Dimension | Parameter | Example values |
|---|---|---|
| Funnel | `funnel` | site / quiz / apply / app |
| Variant | `variant` | A / B |
| Step number | `step_number` | 1, 2, 3, 4 … |
| Step id | `step_id` | q4_property_type / onboarding_5_billing |

Register before launch — GA4 only collects custom dimensions from the moment they're defined.

---

## 3. GA4 — quiz events (enables question-level drop-off)

A single-page quiz fires one `page_view`, so steps are invisible unless we send an event per
question.

```js
gtag('event', 'quiz_start',  { funnel: 'quiz', variant: variant, quiz_id: 'audit_v1' });

// fire on EACH question VIEW — this powers the funnel drop-off report
gtag('event', 'quiz_step',   { funnel: 'quiz', variant: variant, step_number: 4, step_id: 'q4_property_type' });

gtag('event', 'quiz_complete', { funnel: 'quiz', variant: variant, quiz_id: 'audit_v1' });  // key event
```

- Assign `variant` once at `quiz_start`; attach it to every quiz event in the session so A/B
  stays consistent. If A/B live on different paths (`/quiz/a`, `/quiz/b`) derive it from the
  path; if same URL, read it from the split-test assignment.
- Fire `quiz_step` on question **view**, not completion, so a stalled user still registers the
  step they reached.

---

## 4. GA4 — Opt Digital (apply) events

```js
gtag('event', 'apply_start',  { funnel: 'apply' });
gtag('event', 'apply_submit', { funnel: 'apply' });   // key event
```

---

## 5. GA4 — App: signup + 13-step onboarding

The app is the activation half of the journey. Track signup and each onboarding step so we
can see exactly where in the 13 steps people stall — same pattern as the quiz.

```js
// account created
gtag('event', 'sign_up', { funnel: 'app', method: 'email' });   // key event (GA4 recommended name)

// onboarding wizard
gtag('event', 'onboarding_start', { funnel: 'app' });
gtag('event', 'onboarding_step',  { funnel: 'app', step_number: 5, step_id: 'onboarding_5_business_info' }); // each step view, 1..13
gtag('event', 'onboarding_complete', { funnel: 'app' });        // key event
```

### Enable User-ID (the payoff of one property)
As soon as the account exists, set the app user id so GA stitches the user's anonymous
pre-signup marketing sessions to their authenticated app sessions across devices:

```js
gtag('config', 'G-XXXXXXX', { user_id: APP_USER_ID });
```

Also enable it at the property level: Admin → **Reporting identity** → Blended (or
Observed). Never put PII (email, phone, name) in `user_id` — use the internal app user id.

---

## 6. GA4 — mark key events (conversions)

Admin → **Events → mark as key event**: `quiz_complete`, `apply_submit`, `sign_up`,
`onboarding_complete` (+ any booking/lead event on the main site).

---

## 7. GA4 — how to read it

- **Isolate a funnel:** any report → **Comparison** → `funnel exactly matches quiz` (or filter
  by Hostname). Zero cross-funnel contamination.
- **Quiz A vs B:** Explore → **Funnel exploration**, steps `quiz_start → quiz_step(1) → … →
  quiz_complete`, **breakdown = Variant**.
- **Q4 abandonment:** the drop between the step-3 and step-4 rows in that funnel.
- **Onboarding drop-off:** Funnel exploration, steps `sign_up → onboarding_step(1..13) →
  onboarding_complete` — see which of the 13 steps loses people.
- **Full lifecycle:** because it's one property + User-ID, you can segment "users whose first
  session source = X" and see their `sign_up` / `onboarding_complete` rate.

---

## 8. Microsoft Clarity — TWO projects (marketing vs app), for privacy

| Clarity project | Covers | Masking posture |
|---|---|---|
| **Brand marketing** | restorationai.io + audit. + apply. | default masking |
| **App** | app.restorationai.io | **strict masking** (authenticated, collects business data) |

- The three **marketing** subdomains share ONE Clarity project (filter funnels by URL +
  custom tags). This mirrors the GA property and keeps the GA↔Clarity link clean.
- The **app** gets its **own** Clarity project because the onboarding wizard collects
  account/business data — set masking to **Strict**, and mask or exclude any sensitive or
  payment fields (`data-clarity-mask` on those elements). Verify nothing sensitive is captured
  before relying on recordings.

Custom tags (both projects) so recordings/heatmaps are filterable and you can find sessions by
step reached:

```js
clarity('set', 'funnel', 'quiz');                 // set per surface
clarity('set', 'variant', variant);               // quiz only
clarity('set', 'step', String(stepNumber));       // quiz step or onboarding step — find sessions that reached step N
```

- Keep **Clarity → Google Analytics** connected (the brand-marketing project to the single GA4
  property). Optionally connect the app project too.

---

## 9. QA before launch

1. GA4 **DebugView** on each subdomain: confirm `funnel` is correct and step events fire with
   the right `step_number`/`variant`.
2. Cross a marketing page → app and confirm User-ID stitches the session (same user).
3. Confirm Clarity recordings carry the `funnel`/`variant`/`step` tags.
4. Confirm the app Clarity project masks the onboarding inputs (no PII/business data visible).
5. Run one quiz on Variant A and one on B; confirm both appear, separated, in Funnel
   exploration; run one signup→onboarding and confirm the onboarding funnel populates.
