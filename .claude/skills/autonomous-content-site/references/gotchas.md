# Cross-cutting gotchas (read this when "it should work but doesn't")

Real failures hit while building kosai.kr, with the fix. Each cost real time — check here
first.

## GitHub / deploy
- **Push/MCP write 403 in a cloud session** → the session token is read-only. Don't retry
  or route around it. Owner installs the Claude GitHub App with write on the repo, then
  start a **new session**. Deploy via commit → PR → squash-merge (Pages serves `main`).
- **`list_workflow_runs` result too large** → it's saved to a file; parse just the id with
  python, don't read the whole dump.
- **`get_job_logs` shows only cleanup lines** → it returns the tail; the diagnostic prints
  are above the commit step. Increase `tail_lines` (55–62).
- **Merge conflict on PR after force-pushes** → rebase the branch onto `origin/main`
  (`git rebase origin/main`) and re-push before merging.
- **"Unverified" commits** → set `git config user.email noreply@anthropic.com` (+ name)
  before committing; don't reset-author on commits that already belong to `main`.

## AI content
- **Ghost entries in the global index** → reindex only *adds*; entries for removed items
  linger. Prune the index against the live universe every run.
- **A whole tier of content disappears when one writer runs** → that writer rebuilt the
  index from only its own directory. Every index writer must merge all tiers + prune the
  same way.
- **`x.get("field", default)` returns `""`** for present-but-empty fields → use
  `x.get("field") or fallback`.
- **Counts disagree across pages** → each page counts a different set. Derive one number
  (e.g. `stockCount`) at generation time and read it everywhere.

## Apify / X scraping (the long one)
Symptom → cause → fix:
- Actor returns 10 items all `{"noResults": true}` → apidojo-style actor can't scrape (X
  block or free-plan demo) → switch to a pay-per-result actor (kaito) and try several.
- Actor returns `{"demo": ...}` items → free plan / unrented actor demo mode → same fix.
- Run never finishes / your client times out at ~290s → `run-sync` cap → use async
  start+poll+fetch.
- 320 real tweets returned but **0 pass the filter**, all `likeCount: 0`, `createdAt` = now
  → actor ignored `sort:Top`/`minimumFavorites` and returned latest → put `min_faves:N`
  **in the query string**.
- A specific account's posts get dropped by the like filter → exempt that author from the
  min-likes gate.

## LLM
- Output truncated / JSON parse fails with adaptive thinking → `max_tokens` too low; raise
  it, enforce length via prompt.
- Model won't follow layout rules consistently → stop asking; post-process the text in code
  (sentence-split, protect abbreviations).

## Telegram
- "Sent" but user didn't get it → log the API `result` (message_id + chat) to confirm which
  chat received it. Removing a familiar header changes the chat-list preview, so the user
  may not recognize the message arrived — consider keeping a tiny title line.
- Many rapid force-sends can hit flood limits (429) → space test sends out.

## General
- Cron fires late/never → date-guard + multiple crons + watchdog (see pipeline.md).
- A bad scrape overwriting good data → row-count and sanity guards; carry stable fields
  forward from the last good file.
