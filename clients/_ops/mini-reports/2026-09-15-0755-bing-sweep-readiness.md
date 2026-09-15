# Bing sweep migration — step 1 readiness check (report only, nothing changed)

Run: 2026-09-15 ~07:55 PT, Mac Mini (Ignites-Mac-mini.local), unsupervised item.

## 1. Repo + imports
- `git pull --rebase --autostash origin main` → up to date (HEAD after 420646ee).
- `python3 -c "import browser_agent.sweep"` → **OK, no missing packages.**
  Only noise: urllib3 `NotOpenSSLWarning` (system Python 3.9 built against
  LibreSSL 2.8.3). Harmless, but note this machine's `python3` is the Apple
  system 3.9 with user-site packages, not a venv.
- Pillow 11.3.0 and Playwright present (used today for Spotify).

## 2. Bing session on the persistent Chrome profile
Checked via the held Chrome on the suite profile
(`browser_agent/runtime/browser-profile`, CDP port 9223):
- https://www.bing.com/webmasters/home → redirects to the marketing page
  with a **Sign In** button. **Not logged in.**
- https://www.bingplaces.com/Dashboard → redirects to bing.com/forbusiness
  with **Sign in**. **Not logged in.**
- Screenshots: session scratchpad (not committed).
- Consequence: step 2 needs a one-time human Microsoft login on this profile
  (`python3 -m browser_agent login`) before the bing-places playbook can run.
  Santino is on-site today; can be done when step 2 lands.

## 3. `.env` at repo root
Present (`-rw-------`, 7346 bytes, dated Sep 6). Keys checked by name only:
- SUPABASE_URL: present
- SUPABASE_SERVICE_ROLE_KEY: present
- ANTHROPIC_API_KEY: present

## 4. Paths for the launchd plist
- macOS user: `ignitesystems` (uid 501)
- repo path: `/Users/ignitesystems/dev/rank-ai` (also in `~/.rankai-repo-path`)
- python: `/usr/bin/python3` → 3.9 system Python; user-site packages under
  `~/Library/Python/3.9/lib/python/site-packages`
- Chrome: `/Applications/Google Chrome.app` (152.0.7977.83)
- kill switch: off (`python3 -m browser_agent status`)

## Flags
- `python3 -m browser_agent run` on this checkout only lists playbooks
  `apple-maps`, `bing-places`, `domain-connect`; the houzz/homeguide/
  expertise/yellowpages state machines are standalone scripts with
  MacBook-only absolute paths hardcoded (`/Users/santino/Desktop/mywebsitecode/rank-ai`).
  They will not run here without a path fix — see the Houzz item in today's daily report.
- Two Chromes run on this box: Santino's default-profile Chrome and the
  suite-profile Chrome on CDP 9223. The sweep must use the suite profile
  (Chrome 152 ignores `--remote-debugging-port` on the default profile).

## Would queue next
Step 2 as planned: launchd plist for the 11:30 PT sweep on this machine, after
a supervised Microsoft login on the suite profile and one clean supervised sweep.
