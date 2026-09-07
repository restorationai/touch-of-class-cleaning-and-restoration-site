# Rank AI Pipeline — agent orientation

One repo, multiple machines. Check `hostname` to know your role:

- **Santino's MacBook Pro**: primary dev/ops machine. Full context lives in
  the session memory system; this file adds nothing for you.
- **Mac Mini** (hostname contains "mini" or "Mini"): you are the browser-agent
  operator box. Your standing orders are in `docs/MINI-OPERATOR.md` — read
  that file at the START of every session and follow it. It tells you how to
  find your work (git-synced inbox + the citation ledger), what is off-limits,
  and how to report every run.

Never commit `.env`, token files, or anything from `~/.rankai` /
`~/.config/rankai`. The encrypted vault (`secrets-vault/`) is the only form
of secret that belongs in git.
