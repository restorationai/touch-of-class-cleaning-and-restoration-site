# Mini Needs — structured requests the responder answers automatically

The Mini appends one line per missing input (format in docs/MINI-OPERATOR.md).
GitHub Actions (mini-responder.yml) answers mechanical types within seconds of
the push and fires the Mini's trigger; judgment calls route to Santino.
States: [ ] open · [x] fulfilled · [~] routed to Santino · [!] failed.

- [x] NEED-CANARY-202609271838 | type=company-nap | client=narestco | for=daily responder canary -> National Restoration Construction | 1530 S Dash Point RD, Federal Way, WA 98003 | REAL phone (206) 883-0333 | https://narestco.com
- [ ] NEED-20260927-1140-sweep | type=human | client=_ops | question=First Mini scheduled sweep (launchd 11:30 09-27) ran UNATTENDED and its code opens ads.google.com/localservices (lsa_phone_sweep) despite the Mini no-LSA rule; MacBook 11:30 job also on (double HomeGuide risk). Keep plist loaded, skip LSA on Mini, disable one 11:30 job? | for=mini-sweep
