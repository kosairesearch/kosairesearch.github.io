---
name: autonomous-content-site
description: >
  Scaffold and operate an autonomous, cron-driven "data + AI content" static site —
  the KOSAI stack. Use when building a new site/business that needs: scheduled data
  collection into a static site, large-scale AI content generation (Claude Message
  Batches), a GitHub Pages front-end reading data/*.js, and social auto-drafting
  (Telegram + Apify style-learning). Also use when wiring GitHub Actions cron pipelines
  that must self-heal and never require babysitting, or when you hit the same gotchas
  (read-only token, Apify scraping, batch skip/reindex, count unification).
---

# Autonomous content site (the KOSAI stack)

A reusable playbook for shipping a **hands-off, self-healing website** where scheduled
jobs collect data + generate AI content, commit it to the repo, and a static GitHub
Pages front-end renders it. Distilled from building kosai.kr.

## The shape of the system

```
GitHub Actions (cron)  ──► Python scripts ──► commit data/*.js + content JSON ──► git push
        │                                                                           │
   watchdog / backfill / self-chain (never stops until done)                 GitHub Pages
        │                                                                           │
Claude Message Batches (bulk AI content)                          static HTML reads data/*.js
        │
Telegram drafts + Apify style-learning (social)
```

Core principles (learned the hard way):
1. **Everything is a scheduled script that commits to the repo.** No server, no DB for
   the front-end — the front-end reads committed `data/*.js` (`window.KOS_* = {...}`).
2. **Jobs must self-heal.** Cron is unreliable (GitHub delays runs hours); use watchdogs
   + self-chaining + skip-lists so a job "runs until the work is actually done".
3. **Parallel jobs commit only their own files** and rebase-retry the push, so they never
   conflict. Global index files are rebuilt by a single serial job.
4. **Never trust the model for formatting or determinism** — enforce structure in code.

## How to use this skill

1. Read the reference file(s) for the pillar(s) you need — each is self-contained with
   patterns, key snippets, and gotchas:
   - `references/pipeline.md` — GitHub Actions cron pipeline conventions (commit/push,
     watchdog, backfill, self-chain, read-only-token → PR-merge flow, KST timestamps).
   - `references/ai-batch.md` — bulk AI content via Claude Message Batches (quant+qual
     separation, skip-list, serial reindex, universe pruning, name fallbacks).
   - `references/static-site.md` — GitHub Pages front-end (data/*.js, i18n, Firebase
     auth, sitemap/SEO, count/stat unification across pages).
   - `references/social.md` — Telegram-drafted social posts + Apify style-learning
     (kaito async scraping, min_faves, account exemption, code-enforced formatting).
   - `references/gotchas.md` — the cross-cutting failures we hit and their fixes. Read
     this first when something "should work but doesn't".
2. In the canonical repo (kosairesearch/kosairesearch.github.io) the real, working
   implementations live at the paths named in each reference — copy and adapt them.
3. Keep the four principles above. When in doubt, prefer a dumb deterministic script
   over a clever prompt.

## Reusing this skill in a new project

- **Same-repo:** it's already in `.claude/skills/` — versioned and available to Claude
  Code in this repo.
- **New repo:** copy the `.claude/skills/autonomous-content-site/` directory in.
- **All sessions (Claude Code on the web):** enable the skill on claude.ai so it loads
  into every cloud session automatically.

## Quick start for a new site

1. `data/` holds generated `*.js` (`window.KOS_LIVE_DATA = {...}` etc.) + per-item content JSON.
2. One collector script per data source → writes `data/*.js`, guarded against bad runs.
3. One `update_*.yml` cron per collector (spread across the day; add a guard so a bad
   scrape never overwrites good data).
4. AI content: a batch submitter + collector + a single serial reindexer (see ai-batch).
5. A watchdog cron that re-kicks unfinished work every 30 min (see pipeline).
6. Front-end HTML reads the committed `data/*.js`. No build step required.
