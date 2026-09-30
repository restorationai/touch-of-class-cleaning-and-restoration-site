#!/usr/bin/env python3
"""services_we_handle_rollout.py: wire the GBP parity list into service pages.

Santino 2026-09-30 (parity between what the GBP says we do and what the site
shows): every GBP service that maps onto an existing page is visibly named on
that page and emitted in its Service schema. Data comes from
clients/{slug}/gbp-service-map.json via site_structure.write_page_services()
(-> sites/{slug}/src/data/gbp-services.json), refreshed on every map save.

Per site (and the astro starters, so new builds carry it):
  src/lib/gbp-services.ts               gbpServicesFor(service_slug)
  src/components/ServicesWeHandle.astro  "Services We Handle" list, rendered
                                         inside the body prose right after
                                         <Content /> (inherits the theme)
  src/pages/services/[slug].astro        import + list + schema_ctx.service_offers
  src/lib/schema.ts                      Service.hasOfferCatalog from service_offers
Idempotent. tdi-builders and dead clients are never touched.

Usage:
  python3 scripts/services_we_handle_rollout.py            # dry-run
  python3 scripts/services_we_handle_rollout.py --apply
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import site_structure as ss  # noqa: E402

SKIP = {"tdi-builders", "mcc-restoration", "mold-solutionz"}
STARTERS = [ss.ROOT / "templates" / "astro-starter", ss.ROOT / "templates" / "astro-starter-light"]

LIB = '''// Services-we-handle lists (Santino 2026-09-30, GBP <-> site parity). Generated
// from clients/{slug}/gbp-service-map.json by scripts/site_structure.py
// write_page_services(): every GBP service mapped onto a page, in plain
// customer language, deduped; declined / undecided services never list.
// Do not edit ~/data/gbp-services.json by hand.
import data from "~/data/gbp-services.json";

const lists = data as Record<string, string[]>;

export function gbpServicesFor(serviceSlug: string | undefined): string[] {
  return (serviceSlug && Array.isArray(lists[serviceSlug]) && lists[serviceSlug]) || [];
}
'''

COMPONENT = '''---
// "Services We Handle" (Santino 2026-09-30, GBP <-> site parity): every GBP
// service mapped onto this page, named visibly so a customer or Google
// checking the site finds it. Rendered inside the body prose so it inherits
// the site theme. Data: ~/lib/gbp-services (never hand-edited).
interface Props {
  items: string[];
}
const { items = [] } = Astro.props;
---
{items.length > 0 && (
  <div class="services-we-handle" data-parity="gbp-services">
    <h2>Services We Handle</h2>
    <ul>
      {items.map((name) => <li>{name}</li>)}
    </ul>
  </div>
)}
'''

SCHEMA_TYPE_OLD = "  service_display?: string;\n"
SCHEMA_TYPE_NEW = ("  service_display?: string;\n"
                   "  // GBP services mapped onto this page (Service.hasOfferCatalog)\n"
                   "  service_offers?: string[];\n")
SCHEMA_FN_OLD = """    url: `${brand.canonicalUrl}${ctx.url}`,
    description: ctx.meta_description,
  };
}
"""
SCHEMA_FN_NEW = """    url: `${brand.canonicalUrl}${ctx.url}`,
    description: ctx.meta_description,
    // GBP <-> site parity (Santino 2026-09-30): the GBP services this page covers
    ...(ctx.service_offers && ctx.service_offers.length
      ? {
          hasOfferCatalog: {
            "@type": "OfferCatalog",
            name: `${ctx.service_display} services`,
            itemListElement: ctx.service_offers.map((n) => ({
              "@type": "Offer",
              itemOffered: { "@type": "Service", name: n },
            })),
          },
        }
      : {}),
  };
}
"""


def patch_page(t: str) -> str:
    if "gbpServicesFor" in t:
        return t
    # imports: after the last import line of the frontmatter
    fm_end = t.index("\n---", 3)
    head, rest = t[:fm_end], t[fm_end:]
    imports = list(re.finditer(r"^import .*;$", head, re.M))
    if not imports:
        raise ValueError("no import lines")
    at = imports[-1].end()
    head = (head[:at] + '\nimport ServicesWeHandle from "~/components/ServicesWeHandle.astro";'
            '\nimport { gbpServicesFor } from "~/lib/gbp-services";' + head[at:])
    head += "\n// GBP <-> site parity list + Service schema offers (Santino 2026-09-30)" \
            "\nconst serviceOffers = gbpServicesFor(data.service_slug);"
    t = head + rest
    # schema_ctx
    m = re.search(r"schema_ctx=\{\{\s*\n(\s*)", t)
    if not m:
        raise ValueError("no schema_ctx")
    t = t[:m.end()] + "service_offers: serviceOffers,\n" + m.group(1) + t[m.end():]
    # list after <Content />
    n = len(re.findall(r"<Content\s*/>", t))
    if n != 1:
        raise ValueError(f"{n} <Content /> tags")
    t = re.sub(r"(<Content\s*/>)", r"\1\n        <ServicesWeHandle items={serviceOffers} />", t, count=1)
    return t


def patch_schema(t: str) -> str:
    if "service_offers" in t:
        return t
    if t.count(SCHEMA_TYPE_OLD) < 1 or t.count(SCHEMA_FN_OLD) != 1:
        raise ValueError("schema.ts shape not recognised")
    return t.replace(SCHEMA_TYPE_OLD, SCHEMA_TYPE_NEW, 1).replace(SCHEMA_FN_OLD, SCHEMA_FN_NEW, 1)


def roll(root: Path, apply: bool, is_site: bool) -> list[str]:
    done = []
    page = root / "src" / "pages" / "services" / "[slug].astro"
    if not page.exists():
        return done
    writes = {
        root / "src" / "lib" / "gbp-services.ts": LIB,
        root / "src" / "components" / "ServicesWeHandle.astro": COMPONENT,
    }
    writes[page] = patch_page(page.read_text())
    sch = root / "src" / "lib" / "schema.ts"
    if sch.exists():
        writes[sch] = patch_schema(sch.read_text())
    data = root / "src" / "data" / "gbp-services.json"
    for p, body in writes.items():
        if not p.exists() or p.read_text() != body:
            done.append(str(p.relative_to(ss.ROOT)))
            if apply:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(body)
    if apply:
        if is_site:
            ss.write_page_services(root.name)
        elif not data.exists():
            data.parent.mkdir(parents=True, exist_ok=True)
            data.write_text("{}\n")
    return done


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--slug")
    a = ap.parse_args()
    roots = [(ss.SITES / a.slug, True)] if a.slug else \
        [(ss.SITES / s, True) for s in ss.live_slugs() if s not in SKIP] + [(r, False) for r in STARTERS]
    for root, is_site in roots:
        if root.name in SKIP:
            continue
        try:
            d = roll(root, a.apply, is_site)
        except ValueError as e:
            print(f"  {root.name}: SKIPPED ({e})")
            continue
        print(f"  {root.name}: {len(d)} file(s) {'written' if a.apply else 'to write'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
