---
name: daily-pipeline
description: Restoration AI — 8am all-in-one: apply notes, auto-park/resurface cool-offs, re-scan, repaint the page.
---

You are running the Restoration AI daily pipeline (the single morning job — it replaced the old router/call-list/sync tasks).

Execute this exact command and wait for it to finish (~5-8 minutes):

/usr/bin/python3 ~/restoration-ai/workflows/daily_pipeline.py

What it does, in order, on the ONE permanent Notion page: (1) reads yesterday's notes off the page, (2) applies your written "Your call" move-decisions to GHL, (3) snoozes suggestions you left blank, (4) syncs your call-list notes to GHL, (5) re-scans the pipeline — auto-resurfaces finished 30-day cool-offs and auto-parks clear-cut going-dark leads (both with GHL audit notes), (6) repaints the same page with fresh suggestions + call list, (7) emails the link. It reads the Anthropic key from ~/Desktop/mywebsitecode/rank-ai/.env.

After it finishes, read the last ~10 lines of ~/restoration-ai/daily_pipeline.log and the last ~4 lines of ~/restoration-ai/auto_router.log, and report concisely: decisions applied, contacts auto-parked, contacts resurfaced, suggestions count, and the call-list total. Call out any line containing "failed". Do not edit files.