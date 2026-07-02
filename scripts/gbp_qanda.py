#!/usr/bin/env python3
"""gbp_qanda.py — curated Google Business Profile Q&A copy for MANUAL posting.

NOTE: Google **discontinued** the My Business Q&A API (mybusinessqanda.googleapis.com
returns 501 "no longer supported"), so GBP Q&A can no longer be seeded via API. This
script now just prints the curated questions + answers so the team/client can paste
them into the GBP dashboard once (Business Profile → Q&A → ask + answer).

The automatable, higher-value Q&A surface is the on-site per-city page FAQ (FAQPage
schema), handled in the content pipeline — not here.

Usage:
  python3 scripts/gbp_qanda.py --slug narestco
"""
from __future__ import annotations
import argparse, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Universal, restoration-true Q&A (generic-true so it's safe across clients).
QANDA: list[tuple[str, str]] = [
    ("How fast can you respond to an emergency?",
     "We offer 24/7 emergency response and typically arrive on-site within about 60 minutes for "
     "water, fire, and storm damage."),
    ("Do you work with insurance companies?",
     "Yes. We work directly with all major insurance carriers, document the damage for your adjuster, "
     "and can bill your claim directly to make the process as easy as possible."),
    ("How long does water damage restoration take?",
     "Structural drying usually takes about 3–5 days, depending on how much water there was and the "
     "materials affected. We set professional drying equipment and monitor moisture daily until the "
     "area is fully dry."),
    ("Can mold grow after water damage?",
     "Yes — mold can begin to grow within 24–48 hours of water exposure. The best prevention is fast, "
     "professional water extraction and drying, which is why we respond around the clock."),
    ("Are you licensed and insured?",
     "Yes, we are fully licensed and insured, and our technicians are trained and certified in water, "
     "fire, and mold restoration."),
]


def main() -> int:
    ap = argparse.ArgumentParser(description="Print curated GBP Q&A copy for manual posting")
    ap.add_argument("--slug")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    slugs = (list(json.loads((ROOT / "clients" / "company_map.json").read_text()).keys())
             if args.all else [args.slug or "(client)"])
    print("NOTE: Google discontinued the GBP Q&A API — post these MANUALLY in the")
    print("Business Profile dashboard (Q&A → ask a question, then answer as the owner).\n")
    for slug in slugs:
        print(f"===== {slug} — GBP Q&A to post manually =====")
        for i, (q, a) in enumerate(QANDA, 1):
            print(f"\nQ{i}. {q}\nA{i}. {a}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
