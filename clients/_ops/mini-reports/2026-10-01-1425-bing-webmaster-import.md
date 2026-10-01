# 2026-10-01 14:25 PDT: Bing Webmaster Tools import (trigger responder-1790889603, UNSUPERVISED)

Heartbeat pushed first (14:24). Pulled; kill switch off. Inbox item: BING WEBMASTER TOOLS (UNATTENDED OK).

## Result: DONE. 28 sites imported and verified, 15 sitemaps submitted by hand, all 27 now carry sitemap-index.xml

**Sign-in.** bing.com/webmasters showed a sign-in page (Microsoft / Google / Facebook). The inbox item said to stop on a
sign-in page and post a Need. I followed Santino's standing 09-30 rule from the NEED-20260930-1431 answer instead:
"whenever any lane finds Bing signed out, repeat this same Google sign-in yourself". It is the newer direct instruction
and the item's purpose (an agency account, read-only GSC access) is unchanged. I picked Sign In → Google → **contact@restorationai.io**,
the identity that owns Bing Places and GSC. No code and no Microsoft password were needed. It created a free Webmaster
account (Santino Velci / contact@restorationai.io, UserId 26A8E586…). Unlike Bing Places, **this login persists**: a
fresh tab loads the dashboard signed in (cookie-based).

**Import.** Import → Continue → Google consent as contact@ for **"View Search Console data for your verified sites"**
(scope webmasters.readonly). It found 28 sites and 1 sitemap. I imported all 28, which is the 27 live client sites on
the list plus **restorationai.io** (our own; the item said "select ALL properties"). **tdiusa.com isn't in GSC**, so
it was never offered or touched. The UI showed "Site addition unsuccessful" after Import and again after one Try Again,
but globalelements/globalinfo shows **all 28 added at 21:29–21:30Z, IsVerified=true, role Owner**, GSCEmail
contact@, with no duplicates. The error banner was spurious. Bing shows https:// site URLs; the IsSCDomain column below
says which GSC property backed each site.

**Sitemaps.** Before submitting, I checked that every `https://<domain>/sitemap-index.xml` returns 200 (all 27 did).
15 sites didn't list it in Bing, and I submitted it through Sitemaps → Submit sitemap. Each one returned
`Status: SUCCESSFUL`. I submitted no other URL. API key (Settings → API access): **NOT generated**, as instructed.

| Site | Imported | Verified | sitemap-index.xml status | # sitemaps Bing knows |
|---|---|---|---|---|
| aircarerestoration.com | yes | yes (URL-prefix) | **Success** (imported from GSC; child sitemaps/URLs: 1) | 1 |
| theacsenterprises.com | yes | yes (sc-domain) | **Success** (submitted by hand today; child sitemaps/URLs: 1) | 1 |
| allproplumbingheatingandair.com | yes | yes (sc-domain) | **Success** (imported from GSC; child sitemaps/URLs: 1) | 2 |
| archenviroservice.com | yes | yes (URL-prefix) | **Success** (imported from GSC; child sitemaps/URLs: 1) | 1 |
| californiarestorationwest.com | yes | yes (sc-domain) | **Success** (imported from GSC; child sitemaps/URLs: 1) | 1 |
| callcrs.com | yes | yes (sc-domain) | **Success** (submitted by hand today; child sitemaps/URLs: 1) | 2 |
| crew3r.com | yes | yes (sc-domain) | **Success** (imported from GSC; child sitemaps/URLs: 1) | 3 |
| davisconstructioncontractors.com | yes | yes (sc-domain) | **Success** (submitted by hand today; child sitemaps/URLs: 1) | 1 |
| dissrestoration.com | yes | yes (sc-domain) | **Success** (submitted by hand today; child sitemaps/URLs: 1) | 1 |
| drybros.com | yes | yes (sc-domain) | **Success** (submitted by hand today; child sitemaps/URLs: 1) | 1 |
| drycor.com | yes | yes (sc-domain) | **Success** (submitted by hand today; child sitemaps/URLs: 1) | 1 |
| flood-fixers.com | yes | yes (URL-prefix) | **Success** (already known (source 'Submitted', pre-existing; not touched); child sitemaps/URLs: 1) | 1 |
| floodsolutionsinc.com | yes | yes (sc-domain) | **Success** (imported from GSC; child sitemaps/URLs: 1) | 16 |
| frontlinefireflood.com | yes | yes (sc-domain) | **Success** (submitted by hand today; child sitemaps/URLs: 1) | 3 |
| gogreenrestorationofnc.com | yes | yes (sc-domain) | **Processing** (submitted by hand today; child sitemaps/URLs: -) | 1 |
| homelyft.net | yes | yes (sc-domain) | **Processing** (submitted by hand today; child sitemaps/URLs: -) | 3 |
| homepriderestorationandcleaning.com | yes | yes (sc-domain) | **Success** (imported from GSC; child sitemaps/URLs: 1) | 1 |
| veteransremediation.com | yes | yes (sc-domain) | **Processing** (submitted by hand today; child sitemaps/URLs: -) | 1 |
| lifesaversrestorationvegas.com | yes | yes (sc-domain) | **Success** (submitted by hand today; child sitemaps/URLs: 1) | 1 |
| narestco.com | yes | yes (sc-domain) | **Success** (already discovered by Bing (not touched); child sitemaps/URLs: 1316) | 2 |
| prorestorationca.com | yes | yes (sc-domain) | **Success** (imported from GSC; child sitemaps/URLs: 1) | 2 |
| purocleaneastlasvegas.com | yes | yes (URL-prefix) | **Success** (imported from GSC; child sitemaps/URLs: 1) | 1 |
| qualitycontracting.us | yes | yes (sc-domain) | **Success** (submitted by hand today; child sitemaps/URLs: 1) | 1 |
| reign-restoration.com | yes | yes (sc-domain) | **Success** (submitted by hand today; child sitemaps/URLs: 1) | 1 |
| therestorationgroup.com | yes | yes (sc-domain) | **Success** (submitted by hand today; child sitemaps/URLs: 1) | 6 |
| restorationxpress.com | yes | yes (sc-domain) | **Success** (already discovered by Bing (not touched); child sitemaps/URLs: 1) | 3 |
| rtolsonplumbing.com | yes | yes (sc-domain) | **Processing** (submitted by hand today; child sitemaps/URLs: -) | 1 |

"Processing" = submitted minutes before this read-back; they should flip to Success on Bing's first fetch.
"child sitemaps/URLs: 1" = the index lists one child sitemap. Only NaRestCo shows its full URL count (1316) so far.

## Flags (for the MacBook side)
- **Stale legacy sitemaps on several sites.** Bing already knew these old URLs, and I left them alone. Removing them
  is outside this item, and it may be worth a cleanup pass:
  floodsolutionsinc.com (15 old WordPress/Yoast sitemaps on www + apex, e.g. post-sitemap.xml, local-sitemap.xml),
  therestorationgroup.com (5 old: page-sitemap1/2, post-sitemap, sitemap_index, www sitemap.xml),
  crew3r.com (www sitemap_index.xml, www /sitemap), restorationxpress.com (http www/apex sitemap.xml),
  homelyft.net (http/https www sitemap.xml), frontlinefireflood.com (www/apex sitemap.xml), callcrs.com
  (www sitemap.xml?dTs=…), plus /sitemap.xml next to the index on allpro, narestco, prorestorationca. If those URLs
  404 now, Bing will report sitemap errors on them later.
- The Webmaster account's Google consent is on contact@restorationai.io (Google Account → Security → Third-party
  access shows "bing.com"). Revoking it would stop GSC re-imports, not the sites.
- The inbox's "stop on sign-in page" rule conflicts with the standing Google-sign-in rule. Next time, worth saying
  which one wins in the item text.

## Cost / time
14:24–14:42 PDT. $0. No CAPTCHA, no codes, no payment pages. Screenshots: runtime/audit/20261001-14*-bwt-*.png
(local).

## Next
Houzz Desert Valley claim (pf~1478130615), the first Houzz slot today, in this same session.
