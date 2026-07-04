# Static site front-end (GitHub Pages)

Canonical files: `index.html`, `Reports.html`, `stock.html`, `data/stocks.js`,
`data/reports-index.js`, `analytics.js`, `firebase-config.js`, `auth-*.js`,
`scripts/generate_sitemap.py`, `CNAME`.

## Data-as-JS, no build step
- Generated data ships as plain JS assigning a global:
  `window.KOS_LIVE_DATA = { lastUpdated, dataDate, stocks: [...] };`
- Pages `<script src="data/stocks.js">` then read `window.KOS_LIVE_DATA`. A light index
  file (`reports-index.js`) holds only list/card fields; full content JSON is fetched
  per-item on the detail page. Keeps initial load small.
- No bundler, no framework required — GitHub Pages serves the repo as-is. `CNAME` sets the
  custom domain; Pages deploys from `main`.

## Reading a data/*.js from Node/Python (for scripts & checks)
```python
# stdlib-only parse of "window.X = {...};"
obj = json.loads(re.search(r"=\s*(\{.*)", open("data/stocks.js").read(), re.S)
                 .group(1).strip().rstrip(";"))
```
```js
global.window = {}; require("./data/stocks.js");   // in Node, for quick verification
```

## i18n
- Register a `{ko: en}` map per page; a helper `T(text)` swaps by current language.
- For entity names, prefer a real localized field (`name_en`) but **fall back to the base
  name** when it's empty, so the English site never shows blanks:
  `_en && d.name_en ? d.name_en : T(d.name)`.

## Auth (optional): Firebase
- `firebase-config.js` + `auth-state.js` / `auth-guard.js` / `social-login.js`. Email +
  social login; `firestore.rules` locks data. Keep it optional — the content site works
  fully without login.

## SEO
- `scripts/generate_sitemap.py` builds `sitemap.xml` from the universe; `robots.txt`,
  per-page `<meta>` / OpenGraph / Twitter cards. Regenerate the sitemap in the data-update
  workflow so new items are indexed.

## Landing stats must match the real data
Don't hardcode headline numbers. Fetch the generated data and display the true count, and
make sure two pages showing "the same" number read the **same source** (see
`ai-batch.md` → count unification). Mismatched counts between landing and list pages is a
classic bug — it happens when each page counts a different set.
