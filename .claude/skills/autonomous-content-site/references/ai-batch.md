# AI batch content generation (Claude Message Batches)

Canonical files: `scripts/generate_reports_v2.py` (submit/collect), `scripts/_reindex.py`
(serial index rebuild), `scripts/generate_reports.py` (v1 writer).

## Why Message Batches
Generating thousands of long documents one-by-one is slow and expensive. The
**Message Batches API** submits many requests at once and you collect results later.
Pattern: `submit` (build requests + POST batch, write **one state file per batch** to
`data/batches_v2/<batch_id>.json` with `tickers` + the quant snapshot) → a separate
30-min **pickup** job iterates every pending state file, collects the ended ones and
marks them `collected`. Submit waits at most ~30 min in-run (batches can take 24 h;
jobs die at 6 h). The submitter's workflow **must commit the state file** — see
gotchas ("Batch submitted, never collected").

## In-flight items are not "missing"
Tickers listed in a pending state file are in flight. Exclude them from target
selection (`pick_targets`) and from the remaining count the watchdog uses, through one
shared stdlib-only module (`scripts/_reports_state.py`) so both sides agree. Otherwise a
30-min watchdog re-orders the same items every cycle.

## Per-ticker quality gate, not a global one
Run the identity checks (`check_valuation.check_quant`) on each ticker's freshly collected
numbers inside `submit`; exclude failures and leave a `data/reports_v2_hold/<id>` marker.
Never block the whole pipeline on the state of *stored* reports.

## Full refresh without new code
`data/reports_v2_refresh` holding a date makes fill mode treat every report older than
that date as missing; the existing watchdog + shards regenerate the universe and the file
becomes a no-op once everything is newer. The filing trigger defers stale tickers to the
refresh while it is active (no double orders).

## Separate quantitative from qualitative ("숫자는 AI가 쓰지 않는다")
The single most important rule for trustworthy AI content: **the script computes all
numbers; the model only interprets them.**
- Script pulls hard facts from authoritative sources (here: DART financials + KRX) and
  puts them in the JSON. The model receives those numbers as *given evidence* and writes
  only the narrative/interpretation sections.
- Cross-check computed values against a second source before trusting them; hide a metric
  if it fails validation rather than shipping a wrong number.
- Result: the model can't hallucinate figures, and you can regenerate prose cheaply
  ("patch" mode) without recomputing quant.

## Tiered model routing by importance
```python
MODEL_TOP, MODEL_REST, MODEL_TOP_N = "claude-opus-4-8", "claude-sonnet-4-6", 500
model = MODEL_TOP if rank <= MODEL_TOP_N else MODEL_REST   # top items get the strong model
```

## Skip-list for un-generatable items (don't retry forever)
Some items can't be generated (no source data). Record them so fill/watchdog stop retrying:
- Store as **per-item marker files** in a directory (`data/reports_v2_skip/<id>`), not one
  shared file — parallel runs then never conflict on it. Write the date inside the marker.
- Skip **only** when the source really answered "no data" (DART `013`). Quota/maintenance
  errors must abort the run instead — otherwise an outage silently marks a whole run of
  items as permanently un-generatable (this happened).
- Only fill-mode (and the daily backfill run, `REPORT_BACKFILL=1`) adds/refreshes skips.
  **Explicit-id runs never add skips.** The backfill retries skips older than 30 days.
- Repeated batch failures per item go to `data/reports_v2_fail/<id>` (count); after
  `FAIL_LIMIT` the item leaves fill mode until a human looks (cleared on success).

## Global index: rebuild serially, prune to the universe
Parallel generators write only their own item JSON. One serial job (`_reindex.py`,
stdlib-only so it runs without pip) rebuilds the global `*-index.js`:
- It must handle **both** content tiers (e.g. v1 files and v2 files) or entries vanish
  when one writer runs. Merge every source; don't rebuild from a single directory.
- **Prune "ghost" entries**: delete index entries whose id is not in the current universe
  (`data/stocks.js`). Reindex normally only *adds*, so delisted/removed items accumulate
  forever unless you prune against the live universe every run.
- Any other writer of the index must produce the **same shape** (same extra fields, same
  pruning), or two writers will fight and counts will flip-flop between runs.

## Count/stat unification
If a headline count is shown on multiple pages, derive them from **one** source. We write
`stockCount = len(universe)` into the index and have every page read that, instead of each
page counting a different thing (index entries vs universe vs files) and disagreeing.

## Field fallbacks
Empty strings are not missing keys — guard both: `st.get("name_en") or st.get("name") or id`
(not `st.get("name_en", default)`, which returns `""`). For fields a source can't provide,
keep a small manual override map, and still re-check the source each run so a real value
replaces the manual one when it appears.

## Env / secrets
`ANTHROPIC_API_KEY` (+ any data-source keys) as GitHub Actions secrets. Model ids as env
with sane defaults so you can bump models without code changes.
