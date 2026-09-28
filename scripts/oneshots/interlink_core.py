#!/usr/bin/env python3
"""One-shot: add core-service sibling cross-links to each core service page's
internal_links frontmatter. Durable (render skips rendered pages). Idempotent:
only inserts sibling /services/{slug}/ links not already present. Inserts them
right after the leading ["/services/", "/contact/", ...] anchors so the related
services sit near the top of the "Related Coverage" block, before the
service-area variants and blog links.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def run(slug: str, core: list[str]) -> int:
    changed = 0
    sdir = ROOT / "sites" / slug / "src" / "content" / "services"
    for s in core:
        f = sdir / f"{s}.md"
        if not f.exists():
            print(f"  MISSING {f}")
            continue
        text = f.read_text()
        m = re.search(r"^internal_links: (\[.*\])$", text, re.M)
        if not m:
            print(f"  no internal_links line in {s}")
            continue
        links = json.loads(m.group(1))
        siblings = [f"/services/{o}/" for o in core if o != s]
        missing = [x for x in siblings if x not in links]
        if not missing:
            print(f"  {s}: already cross-linked")
            continue
        # insert after the /contact/ anchor (index of first non-anchor entry)
        anchors = {"/services/", "/contact/"}
        i = 0
        while i < len(links) and links[i] in anchors:
            i += 1
        new = links[:i] + missing + links[i:]
        text = text[:m.start()] + "internal_links: " + json.dumps(new) + text[m.end():]
        f.write_text(text)
        print(f"  {s}: +{len(missing)} sibling links")
        changed += 1
    print(f"{slug}: {changed} pages updated")
    return changed


if __name__ == "__main__":
    slug = sys.argv[1]
    core = sys.argv[2].split(",")
    run(slug, core)
