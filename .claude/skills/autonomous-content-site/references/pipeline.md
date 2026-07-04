# Pipeline: GitHub Actions cron conventions

Canonical files: `.github/workflows/update_data.yml`, `reports_watchdog.yml`,
`backfill_missing.yml`, `generate_reports_v2.yml`, and `scripts/collect_data.py`.

## Cron is unreliable — design around it
- GitHub scheduled runs are delayed by minutes to **hours** at busy times, and can be
  skipped entirely. Never assume a cron fires on time.
- Spread the same job across several cron times and add a **date-guard** in the script so
  only the first run of the day actually does the work:
  ```python
  st = load_state()                     # data/_x_daily.json (cached, not committed)
  if st.get("last_date") == today and not force:
      log("이미 오늘 처리함 — 스킵"); return
  ```
- For "run every N minutes" reliably, don't rely on `*/10` cron (skipped under load).
  Instead run a low-frequency cron whose job **loops internally** for a bounded time:
  ```yaml
  on: { schedule: [{ cron: '11 0,5,10,15,20 * * *' }] }   # every 5h
  ```
  ```bash
  end=$(( SECONDS + 16200 ))    # 4.5h < 5h cron, so it exits and saves state cleanly
  while [ "$SECONDS" -lt "$end" ]; do python scripts/job.py || true; sleep 600; done
  ```
  The loop must finish **before** the next cron so the state cache's post-step saves.

## Parallel jobs must not conflict on push
- Each job commits **only the files it owns** (its own per-item JSON + skip markers).
  It does NOT commit global/index files (those are rebuilt by one serial job).
- Revert anything the script incidentally touched, then rebase-retry the push:
  ```bash
  git add data/reports_v2 data/reports_v2_skip 2>/dev/null || true
  git checkout -q -- data/batch_state.json data/reports-index.js 2>/dev/null || true
  git commit -m "..." || exit 0
  for i in $(seq 1 25); do
    git fetch origin main -q || true
    if git rebase origin/main && git push origin main; then break; fi
    git rebase --abort 2>/dev/null || true
    sleep $(( (RANDOM % 9) + 2 ))       # random backoff to spread the push window
  done
  ```
- `concurrency.group: <unique-per-run>` so parallel backfill chunks don't cancel each other.

## Self-healing: watchdog + backfill + self-chain
- **Self-chain:** a fill job, after finishing its chunk, dispatches the next chunk if work
  remains AND it made progress (progress==0 ⇒ stop, avoids infinite loop):
  ```bash
  added=$(( after - before )); remaining=$(python scripts/_remaining.py "$FILL_TO")
  if [ "$remaining" -gt 0 ] && [ "$added" -gt 0 ]; then gh workflow run fill.yml -f ...; fi
  ```
- **Watchdog:** a 30-min cron that (a) rebuilds the global index serially, (b) checks
  remaining work, (c) re-kicks N parallel shards if fewer than N runs are active. This
  guarantees completion even if a self-chain link is dropped. See `reports_watchdog.yml`.
- **Backfill for stragglers:** items permanently `skip`-marked (see ai-batch) are excluded
  from fill mode forever; add a separate daily job that retries them by **explicit id**
  (which bypasses the skip path). See `backfill_missing.yml`.

## Data-integrity guards (never let a bad run nuke good data)
```python
if len(results) < 50:                         # too few rows ⇒ scrape failed
    log("비정상 수집 — 갱신 건너뜀"); sys.exit(1)
mcap_ok = sum(1 for s in results.values() if (s.get("mcap") or 0) > 0)
if mcap_ok < len(results) * 0.5:              # source degraded ⇒ keep old data
    sys.exit(1)
# carry forward stable fields (e.g. English names) from the previous committed file
```

## Read-only token → PR-merge flow (Claude Code on the web)
- Cloud sessions often get a **read-only** GitHub token: `git push` and MCP writes 403
  ("denied to <user>" / "Resource not accessible by integration"). Verify with:
  ```bash
  curl -s -o /dev/null -w '%{http_code}\n' \
    "http://local_proxy@127.0.0.1:PORT/git/<owner>/<repo>/info/refs?service=git-receive-pack"
  ```
  200 = writable, 403 = read-only.
- Fix: the repo owner installs the **Claude GitHub App** on the repo with write
  (`github.com/apps/claude/installations/new`), then a **new session** gets write.
- Once writable, the reliable deploy loop is: commit on the feature branch → push →
  `create_pull_request` → `merge_pull_request` (squash). Repeat per change. GitHub Pages
  deploys from `main`, so merging is what makes changes go live.
- Timestamps in commit messages / data files: use **KST**:
  `TZ='Asia/Seoul' date +'%Y-%m-%d %H:%M KST'`.

## Inspecting Actions from a session
- `mcp__github__actions_run_trigger` (run_workflow / cancel_workflow_run), `actions_list`
  (list_workflow_runs / list_workflow_jobs), `get_job_logs` (return_content + tail_lines).
- `list_workflow_runs` output is huge — it often exceeds the tool limit and is saved to a
  file; parse `workflow_runs[0].id` with a tiny python snippet instead of reading it all.
- `get_job_logs` returns only the **tail**; the diagnostic prints you want are usually a
  few lines above the commit step — increase `tail_lines` (e.g. 55–62) to reach them.
