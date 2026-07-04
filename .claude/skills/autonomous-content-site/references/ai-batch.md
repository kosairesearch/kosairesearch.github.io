# AI batch content generation (Claude Message Batches)

Canonical files: `scripts/generate_reports_v2.py` (submit/collect), `scripts/_reindex.py`
(serial index rebuild), `scripts/generate_reports.py` (v1 writer).

## Why Message Batches
Generating thousands of long documents one-by-one is slow and expensive. The
**Message Batches API** submits many requests at once and you collect results later.
Pattern: `submit` (build requests + POST batch) → `poll` → `collect` (write per-item
JSON). Store `batch_state.json` between steps.

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
  shared file — parallel runs then never conflict on it.
- Only fill-mode adds skips. **Explicit-id runs never add skips**, so a targeted backfill
  can retry a skipped item after its source data appears.

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
