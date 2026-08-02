"""Resume/complete Houzz onboarding from any wizard state. Usage: houzz_resume.py <slug> [overrides-json]"""
import json
import pathlib
import re
import subprocess
import sys
import time

sys.path.insert(0, "/Users/santino/Desktop/mywebsitecode/rank-ai")
from browser_agent.chassis import Session, company_truth, ledger

SLUG = sys.argv[1]
OV = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
ROOT = pathlib.Path("/Users/santino/Desktop/mywebsitecode/rank-ai")
SCRATCH = pathlib.Path(__file__).parent
STATES = {"AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
          "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
          "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
          "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
          "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
          "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire",
          "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina",
          "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
          "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee",
          "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
          "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming", "DC": "D.C."}

brand = {}
try:
    brand = json.loads((ROOT / "clients" / SLUG / "plan-input.json").read_text()).get("brand", {})
except Exception:
    pass

logo_png = None
imgdir = ROOT / "sites" / SLUG / "public" / "images"
if (imgdir / "logo.png").exists():
    logo_png = imgdir / "logo.png"
elif (imgdir / "logo.webp").exists():
    logo_png = SCRATCH / f"{SLUG}-logo.png"
    subprocess.run(["sips", "-s", "format", "png", str(imgdir / "logo.webp"),
                    "--out", str(logo_png)], capture_output=True)
    if not logo_png.exists():
        logo_png = None


def click_btn(page, *names, required=True):
    for name in names:
        btn = page.get_by_role("button", name=re.compile(f"^{name}$", re.I))
        if btn.count():
            try:
                btn.first.click(timeout=5000)
                print("btn:", name, flush=True)
                return True
            except Exception:
                continue
    if required:
        raise RuntimeError(f"no button of {names}")
    return False


def maybe(page, text, exact=False):
    loc = page.get_by_text(text, exact=exact)
    if loc.count():
        try:
            loc.first.click(timeout=4000)
            print("clicked:", text, flush=True)
            return True
        except Exception:
            return False
    return False


s = Session(playbook="form-fill", slug=SLUG, live=True).start(headless=False)
try:
    truth = company_truth(s.company_id)
    for k in ("phone", "address", "city", "state", "website"):
        truth[k] = OV.get(k) or truth.get(k) or brand.get(k)
    truth = {k: (v.strip() if isinstance(v, str) else v) for k, v in truth.items()}
    zipc = OV.get("zip") or brand.get("postal_code") or truth.get("zip") or ""
    st_full = STATES.get((truth.get("state") or "").upper(), truth.get("state"))
    print("TRUTH:", truth.get("name"), "|", truth.get("phone"), "|", truth.get("address"),
          "|", truth.get("city"), st_full, zipc, flush=True)
    if not s.guard_live(f"Houzz onboarding resume for {SLUG}"):
        raise SystemExit(2)
    s.page.goto("https://www.houzz.com/pro-onboarding-wizard",
                wait_until="domcontentloaded", timeout=60000)
    s.page.wait_for_timeout(6000)

    last_sig = ""
    stuck = 0
    for step in range(16):
        url = s.page.url
        body = s.page.inner_text("body")
        low = body.lower()
        sig = url[:80] + str(len(body)) + body[:150]
        if sig == last_sig:
            stuck += 1
            if stuck >= 3:
                print("STUCK — dumping", flush=True)
                print(body[:600], flush=True)
                s.audit_shot(f"{SLUG}-stuck")
                break
        else:
            stuck = 0
        last_sig = sig
        print(f"\n== {step}: {url[:100]}", flush=True)
        s.audit_shot(f"{SLUG}-resume-{step}")

        if "good time for a demo" in low or "schedule a demo" in low:
            for sel in ("[aria-label='Close']", "[aria-label='close']"):
                if s.page.locator(sel).count():
                    try:
                        s.page.locator(sel).first.click(timeout=3000)
                        print("closed demo modal", flush=True)
                        break
                    except Exception:
                        pass
            else:
                s.page.keyboard.press("Escape")
            s.page.wait_for_timeout(2000)
            continue

        if "pro.houzz.com" in url and "onboarding" not in url:
            print("DASHBOARD — onboarding complete", flush=True)
            break

        if "which best describes you" in low:
            maybe(s.page, "Contractor", exact=True)
            if "professional category" in low:
                combo = s.page.locator("[role='combobox'], [aria-haspopup='listbox']").first
                try:
                    combo.click(timeout=6000)
                    s.page.wait_for_timeout(1500)
                    s.page.locator("[role='option']",
                                   has_text="Environmental Services & Restoration")\
                        .first.click(timeout=6000)
                    print("category set", flush=True)
                except Exception as e:
                    print("category:", str(e)[:60], flush=True)
            maybe(s.page, "Client project(s)")
            click_btn(s.page, "Next")
        elif "why are you signing up" in low or "features interest you" in low:
            maybe(s.page, "Client project(s)")
            s.page.wait_for_timeout(1200)
            if "features interest you" in s.page.inner_text("body").lower():
                try:
                    before = s.page.inner_text("body")
                    s.page.get_by_text("Select all that apply", exact=False)\
                        .first.click(timeout=5000)
                    s.page.wait_for_timeout(1800)
                    after = s.page.inner_text("body")
                    new = [ln.strip() for ln in after.splitlines()
                           if ln.strip() and ln.strip() not in before][:15]
                    print("dropdown revealed:", new, flush=True)
                    s.audit_shot(f"{SLUG}-features-open")
                    pick = next((t for t in new if re.search(
                        r"profile|directory|listing", t, re.I)), None) or \
                        (new[0] if new else None)
                    if pick:
                        s.page.get_by_text(pick, exact=False).first.click(timeout=5000)
                        print("picked feature:", pick, flush=True)
                        s.page.wait_for_timeout(800)
                    s.page.get_by_text("What features interest you?")\
                        .first.click(timeout=4000)
                    s.page.wait_for_timeout(800)
                except Exception as e:
                    print("features dropdown:", str(e)[:80], flush=True)
            click_btn(s.page, "Next")
        elif ("annual revenue" in low or "next project start" in low
              or "how many people work" in low or "what tool" in low):
            if "annual revenue" in low:
                maybe(s.page, "Prefer not to say", exact=True)
            if "how many people work" in low:
                maybe(s.page, "2-10", exact=True)
            if "next project start" in low:
                maybe(s.page, "Within the next week")
            if "what tool" in low:
                maybe(s.page, "Other software")
                s.page.wait_for_timeout(1000)
                sw = s.page.locator("input[placeholder*='oftware']")
                if sw.count():
                    sw.first.fill("Restoration AI")
                    print("software -> Restoration AI", flush=True)
            click_btn(s.page, "Next")
        elif "hear about us" in low:
            maybe(s.page, "AI (e.g. ChatGPT)")
            click_btn(s.page, "Next")
        elif "pro-basic-info" in url:
            f = {"businessName": truth["name"],
                 "businessPhone": re.sub(r"\D", "", truth["phone"] or "")[-10:],
                 "businessWebsite": truth.get("website") or "",
                 "contactFirstName": "Santino", "contactLastName": "Velci"}
            for name, val in f.items():
                el = s.page.locator(f"input[name='{name}']")
                if el.count() and val and not el.first.input_value():
                    el.first.fill(val)
            cb = s.page.locator("input[type='checkbox']").first
            if cb.count() and cb.is_checked():
                cb.uncheck()
                print("unchecked SMS consent", flush=True)
            click_btn(s.page, "Next")
        elif "want help getting set up" in low:
            maybe(s.page, "No, thanks")
            s.page.wait_for_timeout(800)
            click_btn(s.page, "Next")
        elif ("book-demo" in url or "contact-expert" in url
              or "onboarding-pricing" in url):
            print("escaping sales gate -> pro-onboarding", flush=True)
            s.page.goto("https://pro.houzz.com/pro-onboarding",
                        wait_until="domcontentloaded", timeout=60000)
        elif "where are you located" in low:
            fills = {"address": truth.get("address"), "city": truth.get("city"), "zip": zipc}
            for el in s.page.locator("input:visible").all()[:10]:
                ph = " ".join(filter(None, [el.get_attribute("placeholder"),
                                            el.get_attribute("name"),
                                            el.get_attribute("aria-label"),
                                            el.get_attribute("id")])).lower()
                for key, val in fills.items():
                    if key in ph and val and not el.input_value():
                        el.fill(str(val))
                        break
            ns = s.page.locator("select")
            for i in range(ns.count()):
                opts = [o.inner_text().strip() for o in ns.nth(i).locator("option").all()]
                if st_full in opts:
                    ns.nth(i).select_option(label=st_full)
                    print("state ->", st_full, flush=True)
                    break
            if OV.get("private_address"):
                maybe(s.page, "Make Private")
            click_btn(s.page, "Next")
        elif "where do you want to work" in low or "what services do you provide" in low:
            click_btn(s.page, "Next", "Skip")
        elif "profile photo" in low:
            if logo_png and "Update Photo" not in body:
                try:
                    s.page.locator("input[type='file']").first.set_input_files(str(logo_png))
                    s.page.wait_for_timeout(8000)
                    click_btn(s.page, "Save", "Apply", "Done", required=False)
                    s.page.wait_for_timeout(3000)
                except Exception as e:
                    print("photo:", str(e)[:60], flush=True)
            click_btn(s.page, "Next", "Skip")
        else:
            print("UNKNOWN state — text:", flush=True)
            print(body[:500], flush=True)
            if not click_btn(s.page, "Next", "Continue", "Skip", required=False):
                break
        s.page.wait_for_timeout(7000)

    print("\nFINAL:", s.page.url[:120], flush=True)
    s.audit_shot(f"{SLUG}-resume-final")
    ok = "pro.houzz.com" in s.page.url and "pro-onboarding" not in s.page.url.split("?")[0]
    ledger(s.company_id, "form-fill", "houzz-create", "done" if ok else "review_needed",
           live=True)
    print("RESULT:", "done" if ok else "review_needed", flush=True)
finally:
    s.stop()
