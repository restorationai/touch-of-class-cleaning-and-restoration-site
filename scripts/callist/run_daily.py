#!/usr/bin/env python3
"""Railway entrypoint for the daily call-list pipeline.

On first boot of a fresh volume, seeds RAI_BASE from the `callist-seed` blob
in Supabase ops_kv (uploaded from the Mac at migration time) so snooze/grace/
synced-note state carries over. Then runs daily_pipeline.main().
"""
import base64, json, os, sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # scripts/ for client_concierge

BASE = Path(os.environ.get("RAI_BASE") or os.path.expanduser("~/restoration-ai"))


def seed_if_empty():
    if (BASE / "snooze.json").exists() or not os.environ.get("SUPABASE_URL"):
        return
    from client_concierge import kv_get, load_env
    load_env()
    seed = kv_get("callist-seed")
    if not seed:
        print("[run_daily] no callist-seed in ops_kv; starting fresh state")
        BASE.mkdir(parents=True, exist_ok=True)
        return
    BASE.mkdir(parents=True, exist_ok=True)
    for name, b64 in seed.items():
        (BASE / name).write_bytes(base64.b64decode(b64))
    print(f"[run_daily] seeded {len(seed)} state file(s) into {BASE}")


if __name__ == "__main__":
    seed_if_empty()
    # Same-day guard: worker restarts (redeploys) must not re-run the whole
    # pipeline (double email, double GHL note posts). --force overrides.
    from datetime import date
    stamp = BASE / "callist_last_run.txt"
    today = date.today().isoformat()
    dry = "--dry-run" in sys.argv
    if (not dry and "--force" not in sys.argv and stamp.exists()
            and stamp.read_text().strip() == today):
        print(f"[run_daily] already ran {today} — skipping (use --force)")
        sys.exit(0)
    import daily_pipeline
    daily_pipeline.main(dry_run=dry)
    if not dry:
        stamp.write_text(today)
