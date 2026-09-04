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
- **Batch submitted, never collected (money spent, nothing written)** → the job that
  submitted the batch did not commit its batch-state file (a workflow step reverted it as
  a "global file"), so the 30-min pickup job never knew the batch id. Every submitter
  must commit **one state file per batch** (`data/batches_v2/<batch_id>.json`, unique
  name ⇒ no rebase conflicts); pickup iterates all pending files and marks each
  `collected` once. Test the submit→commit→pickup path with 1–2 items before scaling.
- **Watchdog re-orders the same items every 30 min** → once submit stopped waiting
  in-run, "running jobs < N" no longer meant "nothing in flight". Treat tickers inside
  pending batch files as *in flight*: exclude them from target selection and from the
  "remaining" count (one shared function used by generator *and* watchdog).
- **A whole run's items marked "un-generatable" after a data-source outage** →
  OpenDartReader prints `{'status': '020', ...}` (daily quota) and returns an *empty*
  frame — indistinguishable from "no financials". Capture stdout around every DART call,
  raise on any status other than `000`/`013`, abort the run (exit 3, partial results
  kept, no skip markers), and leave a dated `data/dart_quota_exhausted` marker so the
  watchdog rests until KST midnight.
- **One bad ticker halts everything** → a global "all stored reports must pass identity
  checks before any generation" gate blocked 2,600 stocks on 4 data quirks (one of them a
  delisted "ghost" file nobody could fix). Gate **per ticker on the freshly collected
  numbers** (`check_valuation.check_quant`), hold only the failing ticker
  (`data/reports_v2_hold/<id>`), and exclude ghosts (not in the universe) from checks.
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

## Numbers (quant)
- **Two branches "trust" opposite sources** → after a reverse-split heuristic chose
  `net income ÷ shares` for EPS, a later fallback overwrote TTM net income with
  `disclosed EPS × shares` — one report, two share bases, 5× apart. Once a value is
  rejected, no later block may reuse it (guard on the recorded `eps_src`).
- **`int()` truncates toward zero** → EPS −6.9 stored as −6, 13% off on tiny earners;
  use `round()`. Make the identity checker rounding-aware (±0.5 won × shares).
- **Owner equity == total equity while NCI ≠ 0** → the issuer tagged the total in the
  owner slot; restore with the identity `owner = total − NCI` (annual *and* quarterly).

## Telegram
- "Sent" but user didn't get it → log the API `result` (message_id + chat) to confirm which
  chat received it. Removing a familiar header changes the chat-list preview, so the user
  may not recognize the message arrived — consider keeping a tiny title line.
- Many rapid force-sends can hit flood limits (429) → space test sends out.

## General
- Cron fires late/never → date-guard + multiple crons + watchdog (see pipeline.md).
- A bad scrape overwriting good data → row-count and sanity guards; carry stable fields
  forward from the last good file.
