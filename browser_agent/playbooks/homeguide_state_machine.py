"""Create/complete a HomeGuide free pro listing from any state.

Usage: python3 -m browser_agent.playbooks.homeguide_state_machine <slug> [--resume]

Reference driver from the narestco supervised run (2026-08-02, clean) — see
PORTALS['homeguide'] in form_fill.py for the pinned flow map. Supervised
until 3 clean completions (1/3 so far). --resume skips the /pro hero signup
and goes straight to the wizard/app phases (persistent profile keeps login).

Hard rules honored here: creds are SAVED to ~/.rankai/portal-creds.json
BEFORE any submit (this script refuses to run without them); the
services/{svc}/creditcard page is the paid wall — we navigate away, never
fill it; CAPTCHA -> challenge_detected(); SMS phone verification -> stop.
Email-code bridge: if a verify state ever appears (none did on run 1), the
operator writes the code to <scratch>/hg_code.txt within 10 min.
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from browser_agent.chassis import Session, company_truth, ledger  # noqa: E402
from scripts.listings import record_listing  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
SERVICE_ID = "f876B6Fz"  # Water Damage Cleanup And Restoration
SERVICE_TYPEAHEAD = "Water Damage"
SVC_PILLS = ("Mold Inspection And Removal", "General Contracting")
PAY_RX = re.compile(r"credit card|card number|billing|payment method|add a card|"
                    r"buy credits|purchase credits", re.I)
AVOID_BTN = re.compile(r"trial|credit|upgrade|buy|card|subscribe|premium|add funds|"
                       r"deposit|budget", re.I)


def _logo_png(slug: str) -> pathlib.Path | None:
    imgdir = ROOT / "sites" / slug / "public" / "images"
    if (imgdir / "logo.png").exists():
        return imgdir / "logo.png"
    if (imgdir / "logo.webp").exists():
        out = pathlib.Path(tempfile.gettempdir()) / f"{slug}-hg-logo.png"
        subprocess.run(["sips", "-s", "format", "png", str(imgdir / "logo.webp"),
                        "--out", str(out)], capture_output=True)
        if out.exists():
            return out
    return None


def _brand(slug: str) -> dict:
    try:
        return json.loads((ROOT / "clients" / slug / "plan-input.json")
                          .read_text()).get("brand", {})
    except Exception:
        return {}


def dump_state(page):
    for el in page.locator("input:visible, textarea:visible, select:visible").all()[:25]:
        try:
            print("   in:", el.evaluate(
                "e => [e.tagName, e.type||'', e.name||'', e.id||'', e.placeholder||'',"
                "(e.value||'').slice(0,40)].join(' | ')"), flush=True)
        except Exception:
            pass
    for el in page.locator("button:visible, [role='button']:visible").all()[:25]:
        try:
            t = re.sub(r"\s+", " ", el.inner_text() or "").strip()[:70]
            if t:
                print("   btn: [", t, "]", flush=True)
        except Exception:
            pass


def advance(page, *extra):
    names = list(extra) + ["Next", "Continue", "Save and continue", "Sign up",
                           "Submit", "Save", "Done", "Finish"]
    for name in names:
        for el in page.get_by_role("button",
                                   name=re.compile(f"^{re.escape(name)}", re.I)).all():
            try:
                t = (el.inner_text() or "").strip()
                if AVOID_BTN.search(t):
                    continue
                el.click(timeout=5000)
                print("  btn:", t[:50], flush=True)
                return True
            except Exception:
                continue
    return False


def wait_code(scratch: pathlib.Path):
    code_file = scratch / "hg_code.txt"
    print("WAITING_FOR_CODE: write code or link to", code_file, flush=True)
    code_file.unlink(missing_ok=True)
    for _ in range(120):
        if code_file.exists() and code_file.read_text().strip():
            return code_file.read_text().strip()
        time.sleep(5)
    return None


def main() -> int:
    slug = sys.argv[1]
    resume = "--resume" in sys.argv
    creds = (json.loads((pathlib.Path.home() / ".rankai/portal-creds.json").read_text())
             .get("homeguide", {}).get(slug))
    if not creds:
        print(f"no homeguide.{slug} creds in ~/.rankai/portal-creds.json — save "
              "email+password FIRST (policy: creds exist before any submit)")
        return 1
    brand = _brand(slug)
    logo = _logo_png(slug)
    scratch = pathlib.Path(tempfile.gettempdir())

    s = Session(playbook="form-fill", slug=slug, live=True).start(headless=False)
    try:
        truth = company_truth(s.company_id)
        truth = {k: (v.strip() if isinstance(v, str) else v) for k, v in truth.items()}
        zipc = truth.get("postal_code") or brand.get("postal_code") or ""
        founded = str(brand.get("founded_year") or "")
        desc = brand.get("homeguide_intro") or (
            f"{truth['name']} serves {truth.get('city')} and the surrounding area"
            + (f" (est. {founded})" if founded else "") +
            ". We provide 24/7 water damage cleanup and restoration, fire and "
            "smoke damage repair, mold remediation, storm damage restoration, "
            "and reconstruction.")
        print("TRUTH:", truth.get("name"), "|", truth.get("phone"), "|",
              truth.get("city"), truth.get("state"), zipc, flush=True)

        # ---- Step 0: dedupe (always) ----
        s.page.goto(f"https://homeguide.com/search?service={SERVICE_ID}&zipcode={zipc}",
                    wait_until="domcontentloaded", timeout=60000)
        s.page.wait_for_timeout(9000)  # JS-rendered
        s.audit_shot(f"{slug}-hg-dedupe")
        if truth["name"].lower() in s.page.inner_text("body").lower() and not resume:
            print("ALREADY LISTED — claim path / ledger exists, never duplicate",
                  flush=True)
            ledger(s.company_id, "form-fill", "homeguide-create", "exists")
            return 0

        # ---- Signup (skipped on --resume) ----
        if not resume:
            s.page.goto("https://homeguide.com/pro", wait_until="domcontentloaded",
                        timeout=60000)
            s.page.wait_for_timeout(5000)
            zf = s.page.locator("input#zip")
            zf.click(timeout=8000)
            s.page.keyboard.type(zipc, delay=45)
            s.page.locator("input#service").click(timeout=8000)
            s.page.keyboard.type(SERVICE_TYPEAHEAD, delay=70)
            s.page.wait_for_timeout(2500)
            s.page.get_by_text(re.compile(r"water damage (cleanup|restoration)",
                                          re.I)).first.click(timeout=8000)
            s.page.wait_for_timeout(1500)
            if zf.count() and zf.input_value() != zipc:  # geo-ip zip clobber guard
                zf.click()
                zf.press("Meta+a")
                zf.press("Backspace")
                s.page.keyboard.type(zipc, delay=45)
            s.audit_shot(f"{slug}-hg-pro-filled")
            if not s.guard_live("homeguide signup start (Sign up for free)"):
                return 2
            s.page.get_by_role("button", name=re.compile("sign up for free", re.I))\
                .first.click(timeout=10000)
            s.page.wait_for_timeout(4000)
            # modal: Sign up with email -> email + mobile(GBP primary) + password
            advance(s.page, "Sign up with email")
            s.page.wait_for_timeout(3000)
            for sel, val in (("input[type=email], input[name*='email' i]",
                              creds["email"]),
                             ("input[type=tel]",
                              re.sub(r"\D", "", truth["phone"])[-10:]),
                             ("input[type=password]", creds["password"])):
                el = s.page.locator(sel)
                if el.count() and not el.first.input_value():
                    el.first.click(timeout=6000)
                    s.page.keyboard.type(val, delay=40)
            for el in s.page.locator("input[type=checkbox]").all()[:6]:
                try:  # 'enable texts…' consent comes PRE-TICKED
                    lab = (el.evaluate("e => (e.closest('label')||{}).innerText || ''")
                           or "").lower()
                    if el.is_checked() and re.search(r"text|sms", lab):
                        el.uncheck()
                        print("  unchecked SMS consent", flush=True)
                except Exception:
                    pass
            s.audit_shot(f"{slug}-hg-signup-filled")
            if not s.guard_live("homeguide account create (Sign up)"):
                return 2
            advance(s.page, "Sign up")
            s.page.wait_for_timeout(7000)

        # ---- Wizard: body-text state machine ----
        if resume:
            s.page.goto(f"https://homeguide.com/pro/onboarding/more-services"
                        f"?service={SERVICE_ID}&isOnboarding=true",
                        wait_until="domcontentloaded", timeout=60000)
            s.page.wait_for_timeout(6000)
        last_sig, stuck, transient = "", 0, 0
        for step in range(30):
            url = s.page.url
            try:
                body = s.page.inner_text("body")
            except Exception:
                s.page.wait_for_timeout(4000)
                body = s.page.inner_text("body")
            low = body.lower()
            nbtn = s.page.locator("button:visible, [role='button']:visible").count()
            if len(body) < 200 and nbtn == 0:  # mid-navigation shell
                transient += 1
                if transient <= 4:
                    s.page.wait_for_timeout(5000)
                    continue
            transient = 0
            sig = url[:90] + str(len(body)) + body[:120]
            stuck = stuck + 1 if sig == last_sig else 0
            last_sig = sig
            print(f"\n== {step}: {url[:110]}", flush=True)
            s.audit_shot(f"{slug}-hg-{step}")
            if stuck >= 3:
                print("STUCK — dump + stop", flush=True)
                dump_state(s.page)
                break

            if "captcha" in low or s.page.locator(
                    "iframe[src*='captcha'], iframe[src*='recaptcha'], "
                    "iframe[src*='hcaptcha']").count():
                s.challenge_detected("captcha")
            if re.search(r"(verify|confirm).{0,30}phone|code.{0,30}(text|sms)", low):
                print("PHONE VERIFICATION — stop, number is the client's", flush=True)
                ledger(s.company_id, "form-fill", "homeguide-create",
                       "blocked_phone_verification", detail=url[:200], live=True)
                return 3
            if re.search(r"(verify|confirm).{0,40}e-?mail|verification code|"
                         r"check your (inbox|email)", low):
                val = wait_code(scratch)
                if not val:
                    return 3
                if val.startswith("http"):
                    s.page.goto(val, wait_until="domcontentloaded", timeout=60000)
                else:
                    box = s.page.locator("input[type=text]:visible, "
                                         "input[type=tel]:visible").first
                    box.click()
                    s.page.keyboard.type(val, delay=60)
                    advance(s.page, "Verify", "Confirm")
                s.page.wait_for_timeout(6000)
                continue

            if "creditcard" in url:  # THE upsell wall — never fill, walk away
                print("creditcard wall — leaving wizard (decline)", flush=True)
                s.audit_shot(f"{slug}-hg-ccwall-declined")
                break
            if "more-services" in url:  # category PILLS are <button>s
                for pill in SVC_PILLS:
                    try:
                        s.page.get_by_role("button", name=re.compile(
                            f"^{re.escape(pill)}$", re.I)).first.click(timeout=4000)
                        print("  pill:", pill, flush=True)
                    except Exception:
                        pass
                advance(s.page) or advance(s.page, "Skip")
            elif "business-info" in url:
                for name, val in (("business-name", truth["name"]),
                                  ("website", truth.get("website") or "")):
                    el = s.page.locator(f"input[id='{name}']")
                    if el.count() and val and not el.first.input_value():
                        el.first.click(timeout=5000)
                        s.page.keyboard.type(val, delay=35)
                advance(s.page) or advance(s.page, "Skip")
            elif "profile-image" in url:
                if logo and s.page.locator("input[type='file']").count():
                    s.page.locator("input[type='file']").first\
                        .set_input_files(str(logo))
                    s.page.wait_for_timeout(9000)
                    advance(s.page, "Save", "Apply")
                    s.page.wait_for_timeout(3000)
                advance(s.page) or advance(s.page, "Skip")
            elif "business-intro" in url:
                ta = s.page.locator("textarea:visible")
                if ta.count() and not ta.first.input_value():
                    ta.first.click()
                    s.page.keyboard.type(desc, delay=8)
                advance(s.page)
            elif ("tutorial-aperture" in url or "job-preference" in url
                  or "geo-preference" in url or "/budget" in url):
                # job-prefs come all pre-checked; geo default = 25mi; budget
                # is inert with no card on file. Continue through all.
                advance(s.page) or advance(s.page, "Skip")
            elif "app.homeguide.com" in url:
                print("app dashboard reached — wizard over", flush=True)
                break
            elif not (advance(s.page) or advance(s.page, "Skip", "No thanks",
                                                 "Not now")):
                print("UNKNOWN state — dump + stop", flush=True)
                dump_state(s.page)
                break
            s.page.wait_for_timeout(6000)

        # ---- App profile completion (the wizard skips full NAP) ----
        s.page.goto("https://app.homeguide.com/pros/profile/edit-info",
                    wait_until="domcontentloaded", timeout=60000)
        s.page.wait_for_timeout(8000)

        def set_field(sel, val):
            el = s.page.locator(sel)
            if el.count():
                el.first.click(timeout=6000)
                el.first.press("Meta+a")
                el.first.press("Backspace")
                if val:
                    s.page.keyboard.type(str(val), delay=30)
                print(f"  {sel} -> {val}", flush=True)

        # NB: #address-suite has name='business-name'; #year-founded &
        # #number-of-employees come prefilled '0' — set explicitly by id.
        set_field("input#street-address", truth.get("address"))
        set_field("input#address-suite", "")
        set_field("input#postal-code", zipc)
        set_field("input#company-email", truth.get("email"))
        if founded:
            set_field("input#year-founded", founded)
        plan_path = ROOT / "clients" / slug / "plan-input.json"
        plan = json.loads(plan_path.read_text()) if plan_path.exists() else {}
        gcid = plan.get("google_cid") or plan.get("brand", {}).get("google_cid") or ""
        if gcid:
            g = s.page.locator("input[placeholder*='Google Business']")
            if g.count() and not g.first.input_value():
                g.first.click(timeout=5000)
                s.page.keyboard.type(f"https://maps.google.com/?cid={gcid}", delay=25)
        s.audit_shot(f"{slug}-hg-editinfo")
        advance(s.page, "Save")
        s.page.wait_for_timeout(6000)

        # ---- Public URL: appears in /search within minutes ----
        public_url = None
        name_slug = re.sub(r"[^a-z0-9]+", "-", truth["name"].lower()).strip("-")
        for attempt in range(4):
            s.page.goto(f"https://homeguide.com/search?service={SERVICE_ID}"
                        f"&zipcode={zipc}", wait_until="domcontentloaded",
                        timeout=60000)
            s.page.wait_for_timeout(9000)
            for el in s.page.locator("a").all()[:150]:
                h = el.get_attribute("href") or ""
                if name_slug[:30] in h:
                    public_url = ("https://homeguide.com" + h if h.startswith("/")
                                  else h).split("?")[0]
                    break
            if public_url:
                break
            print(f"  not in search yet (attempt {attempt + 1}) — waiting 60s",
                  flush=True)
            time.sleep(60)
        print("PUBLIC_URL:", public_url, flush=True)
        s.audit_shot(f"{slug}-hg-final-search")
        if public_url:
            s.page.goto(public_url, wait_until="domcontentloaded", timeout=60000)
            s.page.wait_for_timeout(7000)
            ok = truth["name"].lower() in s.page.inner_text("body").lower()
            s.audit_shot(f"{slug}-hg-public-profile")
            if ok:
                record_listing(s.company_id, "homeguide", public_url)
                ledger(s.company_id, "form-fill", "homeguide-create", "done",
                       detail=f"free listing live: {public_url}", live=True,
                       meta={"public_url": public_url})
                print("RESULT: done", flush=True)
                return 0
        ledger(s.company_id, "form-fill", "homeguide-create", "review_needed",
               detail="profile created but public URL not verified", live=True)
        print("RESULT: review_needed", flush=True)
        return 1
    finally:
        s.stop()


if __name__ == "__main__":
    sys.exit(main())
