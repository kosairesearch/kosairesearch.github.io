# Social auto-drafting (Telegram + Apify style-learning)

Canonical files: `scripts/daily_x_post.py` (draft → Telegram), `scripts/fetch_x_style.py`
(Apify scrape → style examples), `.github/workflows/daily_x_post.yml`, `fetch_x_style.yml`.

## Draft-to-Telegram, human posts to the platform
- Do **not** auto-post to X/social from a bot (account bans, spam flags). Instead the job
  writes a ready-to-paste draft and sends it to **Telegram** for a human to copy. Same
  Telegram secrets (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`) drive both alerts and drafts.
- Pausing a noisy alert workflow: comment out its `schedule:` (keep `workflow_dispatch`)
  and **cancel the in-progress run** (`actions_run_trigger` cancel) so it stops now, not
  after its internal loop ends.

## Style-learning: teach tone with real examples, enforce format in code
Goal was "posts that don't read as AI". Two layers:
1. **Few-shot from real high-engagement posts** (scraped via Apify) injected as a STYLE
   REFERENCE block: "match voice/rhythm/line-breaks, NOT content or any recommendation;
   compliance rules always win." Keep hard brand/compliance rules dominant.
2. **Anti-AI-tell prompt rules**: ban "moreover/furthermore/notably/in conclusion/overall",
   no tidy wrap-up, use contractions, vary rhythm, short punchy lines.

But the model is inconsistent about layout. **Enforce structure deterministically in code**
(don't rely on the prompt): after generation, split into sentences and rejoin with blank
lines so paragraphs are always short — protect abbreviations (`Co.`, `Ltd.`, `Inc.`,
`U.S.`, decimals) so you don't split mid-name/number.

## Apify scraping — the hard-won recipe (see gotchas.md for the debugging story)
- **Actor:** free-plan Apify accounts get **demo/`noResults`** data from many X scrapers
  (e.g. apidojo). Use a **pay-per-result** actor that works on free plans, e.g.
  `kaitoeasyapi~twitter-x-data-tweet-scraper-pay-per-result-cheapest`. Make the actor list
  configurable and try several, using the first that returns real tweets.
- **Async, not run-sync:** `run-sync-get-dataset-items` is capped at ~300s and truncates
  large scrapes. Instead: POST `/acts/<actor>/runs` → poll `/actor-runs/<id>` until
  `SUCCEEDED` → GET `/datasets/<dsId>/items`. Poll up to ~10 min (job timeout 15).
- **The actor ignores `sort:Top`/`minimumFavorites`** and returns freshest (0-like) tweets.
  Put the engagement filter **in the query string** as X search operators:
  `"<keyword> min_faves:200 lang:en -filter:replies -filter:nativeretweets"`.
- **Multiple sources:** keyword queries for popular tweets **plus** specific accounts via
  `from:<handle>`. Exempt hand-picked accounts from the like-threshold (you want their
  style regardless of likes) — tag those authors and skip the min-likes gate for them.
- Filter defensively: field names vary across actors — read likes from
  `likeCount/favoriteCount/...` and nested `legacy/public_metrics`; drop retweets, non-EN,
  too-short/long, and spammy ("🚀🚀", "100x", "dm me", "not financial advice").
- Save top-N by likes to `data/x_style_examples.json`; the drafter samples a few per post.
  Refresh weekly. If a run yields <3 examples, **preserve the existing file** (don't
  overwrite good data with nothing).

## LLM call gotchas
- With **adaptive thinking on**, `max_tokens` must budget for thinking + output. Setting it
  too low (e.g. 900) truncates the body → JSON parse fails → run errors. Keep headroom
  (~2000); enforce brevity via the prompt, not by starving `max_tokens`.
- Log the generated text and the delivery response so a "sent but didn't arrive" complaint
  is debuggable: log Telegram's `result.message_id` + `chat` on success, not just "OK".
