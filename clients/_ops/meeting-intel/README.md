# Meeting intel — this directory is an ARCHIVE, not the live store

**Nothing has written a file here since 2026-07-12, and nothing will.** The
files below are the pre-migration history and are still read at compose time,
so they stay.

Live meeting intel lives in Supabase `ops_kv` under `meeting-intel/{slug}`.
It moved there on 2026-07-12 (commit e9362053) when the concierge, the email
intake and the Fathom sync were migrated off the Mac onto the Railway
ops-worker, whose filesystem is disposable.

`client_concierge.load_meeting_intel()` merges BOTH sources — these files
plus the KV — so a client's history is complete either way.

## Why this README exists

On 2026-08-05 "meetings aren't becoming tasks" was reported because this
directory had no file newer than 2026-07-12. The pipeline was in fact
running normally and had processed both of the previous day's meetings within
the hour. A frozen directory listing is not evidence of a stalled job.

To see what the sync is actually doing:

```
python3 scripts/fathom_sync.py status     # heartbeat, recent runs, per client
python3 scripts/fathom_sync.py watch      # would a card be filed right now?
```

`watch` runs daily from the ops-worker (`--send`) and files a
`[TODO-SANTINO]` card when a client meeting produces no board work, or when
the sync itself stops completing runs.
