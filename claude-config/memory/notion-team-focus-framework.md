---
name: notion-team-focus-framework
description: Notion-based team focus/execution framework (monthly→weekly→daily cascade) built for Restoration AI team
metadata: 
  node_type: memory
  type: project
  originSessionId: 4a2c22a5-6f10-4b5f-b214-ad0f26ff204b
---

Team operating-rhythm framework built in Notion (workspace "Restoration AI 💧") to fix scattered team focus. Cascade: monthly company objective → weekly focus → each person's weekly plan → daily check-in. Decided against a custom dashboard (adoption friction + maintenance) and against GoHighLevel SMS reminders (risks the client-outreach number's 10DLC registration + feels like surveillance).

Built 2026-06-21 under parent page "Team Focus & Execution" (`386d279c-0699-808c-9bf5-fd133c65ba97`). Three databases:
- 🎯 Company Focus `386d279c-0699-8150-af41-c18e2731ec54` — Type=Month/Week, self-relation Parent Month↔Sub-Weeks
- 🗓️ Weekly Plans `386d279c-0699-81be-a5d4-ef5a5faff2a5` — per person, relation→Company Week, "Days Logged" rollup
- ☀️ Daily Check-ins `386d279c-0699-8163-9d6e-ee68aae44cb0` — per person/day, Started At, Today's Goals, Completed? (✅/🟡/❌), relation→Weekly Plan

Notion integration name "Team Ops Framework" (internal token). **API limitation:** cannot create views or the daily template button — those are UI-only and left as manual steps for the user. Reminder chosen: Notion native automation (not Slack — they don't use it).

**Why:** team was scattered on focus/production; user wanted a shared, login-anywhere accountability ritual.
**How to apply:** when iterating, build schema via REST API, hand off views/templates/automations as UI clicks. See [[narestco-paid-and-geogrid-state]] for the broader Restoration AI ops context.
