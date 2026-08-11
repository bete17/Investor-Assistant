# Investor Assistant

A Streamlit dashboard that pulls a company's real financial data and turns it
into something you can actually read — plain-language reads on profitability,
growth, debt, and cash flow, valuation multiples judged against the company's
own sector, a sector-aware health score that explains itself, and a
year-over-year diff of what management changed in their own words in the 10-K.

Built for someone who wants to sanity-check a stock without knowing how to read
a balance sheet. If you're a professional analyst you'll want something deeper —
this is meant for a fast, honest first look, not a replacement for real research.

> **Not investment advice.** Everything here is generated from public data for
> research and educational purposes. Do your own research before investing.

---

## Features

### KPI Dashboard
Enter a ticker and get profitability, growth, debt, and liquidity metrics
translated into plain labels (Strong / Healthy / Elevated / Weak), plus
quarterly revenue and net income charts and the company's sector-aware
health score.

Level metrics (margin, ROE, free cash flow) are **trailing twelve months**;
growth is **year over year**. Both conventions matter — see
[Metric conventions](#metric-conventions) for why.

### Valuation
What the market is paying, alongside what the business is worth: price and
the day's move, market cap, P/E (trailing and forward), price-to-sales,
price-to-book, dividend yield and position in the 52-week range.

Each multiple is interpreted against its own sector, because 25× earnings is
ordinary for software and expensive for a bank. The P/E is also weighed
against the company's growth rate, since a 40× multiple on a business growing
40% a year is a different proposition from 40× on one growing 3%.

A lossmaking company is reported as having **no earnings**, never as "cheap" —
it has the lowest possible P/E while describing the worst case on the row.

This section exists because a health score alone quietly invites the reading
that a high number means "buy". A great company at a bad price is still a bad
investment, and the app now says so.

### Sector-aware Health Score
A single 0–100 score combining the KPIs above, normalized against ranges
specific to that company's sector — so a bank and a software company aren't
graded on the same curve. A 25% net margin is unremarkable for software and
exceptional for grocery retail; the score accounts for that.

The score is **explained, not just displayed**: a breakdown shows which
metrics are lifting it and which are holding it back, each as a bar against
that metric's sector range. A coverage badge states how much of the company's
data the score was actually built from — the score re-normalizes by available
weight, which fairly avoids penalizing a data gap but would otherwise make a
score built from three metrics look as confident as one built from seven.

### Watchlist
Save companies and land on them next visit instead of an empty search box.
Stored as a JSON file on the machine running the app.

Note this is **single-user by design** — there's no authentication in this
project, so there's no user to key a list against. That's right for local
use and wrong for a shared deployment, where every visitor would read and
write the same list. Multi-user watchlists need accounts first.

### Compare Stocks
Two companies side by side, each with its own sector-adjusted score, plus a
radar chart across the shared metrics.

### Storyline — MD&A year-over-year diff
Pulls Item 7 (Management's Discussion & Analysis) from the company's 10-K
filings on SEC EDGAR and summarizes **what changed** from the prior year's
language, not just what the current filing says. Each year is badged as either
*Changed vs. prior year* or *First year on record*. News sentiment for the
ticker is shown alongside it.

This is the part of the app that doesn't exist elsewhere in retail tooling —
the language management chooses to change is often more informative than the
numbers alone.

### Discover
For someone with no ticker in mind. A short quiz (risk tolerance, a scenario
check, sector interest, goal) maps to a risk tier, which selects a bounded pool
of well-known companies. That pool is then **ranked live by Health Score**, with
the top matches shown as cards and the full ranked list browsable below.

The quiz pairs a direct self-rating with a scenario question as a consistency
check — self-rated risk tolerance is known to be inflated, so when the two
answers disagree sharply the more conservative one wins rather than averaging.

**What Discover is not:** a screener. The candidate pool is hand-maintained and
bounded, not a live screen of the whole market, so it can't surface a good
company that isn't already in the pool. It's a starting point that funnels into
the dashboard, not a recommendation engine.

---

## Setup

Requires **Python 3.11+** and [uv](https://astral.sh/uv).

```bash
git clone https://github.com/bete17/Investor-Assistant.git
cd Investor-Assistant
uv sync
```

### Environment variables

Copy the example file and fill in what you have:

```bash
cp .env.example .env
```

| Variable | Required for | Notes |
|---|---|---|
| `EDGAR_IDENTITY` | Storyline page | SEC's fair-access policy requires every automated caller to identify itself with a real name and email. Format: `"Your Name your.email@example.com"`. The app refuses to fetch filings without it. |
| One LLM key | Storyline summaries | `GEMINI_API_KEY`, `CEREBRAS_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`, or `COHERE_API_KEY`. Tried in that order; first working key wins. Gemini's free tier is the easiest start. |

The KPI Dashboard, Compare Stocks, Discover and the watchlist work with **no
keys at all** — they only use Yahoo Finance data. Keys are only needed for
Storyline, and that page tells you what to set if you open it without them.

Optionally, set `INVESTOR_ASSISTANT_WATCHLIST` to store the watchlist
somewhere other than `data/watchlist.json`.

Optionally, add numbered suffixes (`GROQ_API_KEY_2`, `GROQ_API_KEY_3`) to spread
load across separate free-tier rate limits.

### Run

```bash
uv run streamlit run UI/kpi_dashboard.py
```

### Tests

```bash
uv run pytest tests/ -v
```

---

## Project structure

```
UI/
  kpi_dashboard.py         Main page (entry point)
  components.py            Shared render helpers (price header, valuation,
                           score drivers) used by more than one page
  skeletons.py             Shared loading-placeholder helpers
  styles.css               Dark-terminal design system
  utils.py                 Formatting helpers
  pages/
    1_compare_stocks.py
    2_storyline.py
    3_discover.py

analytics/                 Pure computation — no I/O, no Streamlit
  kpi_engine.py            KPI calculations (TTM levels, YoY growth)
  health_score.py          0-100 weighted sector-aware score + explanation
  valuation.py             Multiples interpreted against sector bands
  sector_profiles.py       Per-sector normalization ranges
  sector_lookup.py         Cached sector resolution
  storyline_engine.py      MD&A diff + LLM summarization
  sentiment_engine.py      VADER news sentiment
  discover_engine.py       Quiz → risk tier, candidate pool, ranking
  watchlist.py             Local watchlist persistence

data/                      External data access, with on-disk caching
  financials_fetcher.py    yfinance quarterly financials (24h cache)
  market_fetcher.py        yfinance price + valuation snapshot (15m cache)
  news_fetcher.py          yfinance news
  storyline_fetcher.py     SEC EDGAR 10-K Item 7 extraction
  cache/                   Cached JSON (gitignored)
  watchlist.json           Your saved tickers (gitignored)

tests/
docs/architecture.md       C4 context + container diagrams
conftest.py                Test path setup
```

`watchlist.py` sits in `analytics/` rather than `data/` because it holds the
user's own state rather than fetched market data, and never touches the
network.

The layering is deliberate: `data/` fetches, `analytics/` computes on plain
Python data structures, `UI/` renders. Nothing in `analytics/` imports Streamlit,
which is what makes it unit-testable without mocking a web framework.

---

## Metric conventions

Two conventions determine whether the numbers on the dashboard mean anything.
Both were wrong in an earlier version of this project, in ways that made the
app confidently misleading rather than merely incomplete.

### Growth is year over year, not quarter over quarter

Growth compares the latest quarter with **the same quarter a year earlier**.

Almost every real business is seasonal. Apple's fiscal Q2 revenue falls
sharply from its holiday Q1 every single year; retailers swing harder. Under
sequential (quarter-over-quarter) growth, the app reported a large "decline"
for a perfectly healthy company on a predictable annual cycle — and then the
health score docked it for that. Year-over-year is what every earnings release
and every analyst uses, precisely because it cancels seasonality.

Sequential growth is still computed and shown, as a clearly labelled
supplement. It's genuinely useful for spotting a turn early; it just isn't the
headline.

When there's under a year of history, the app falls back to a sequential
comparison **and says so on the page**, because the two mean different things.

### Level metrics are trailing twelve months

Margin, ROE and free cash flow sum the **last four reported quarters**.

A single quarter's net income is roughly a quarter of the annual figure, so
dividing it by (full, point-in-time) shareholder equity produced an ROE about
4× too small — while `sector_profiles.py` benchmarks ROE against Damodaran's
**annual** industry data. Comparing a quarterly numerator to an annual range
meant essentially every company scored near zero on a metric carrying 20% of
the health score.

Balance sheet items (debt, equity, current assets) are point-in-time stocks
and are *not* summed. ROE divides trailing-twelve-month profit by **average**
equity, since profit accumulates over the period while equity is a snapshot.

### Growth off a negative base is described, not calculated

When the comparison quarter was a loss, no percentage is shown.

A company swinging from a $100M loss to a $100M profit computes as **−200%**
under the standard growth formula, which the dashboard rendered as "earnings
are declining" — for unambiguously good news. No sign convention fixes this,
so the app states the swing in words instead ("Swung from a loss to a
profit").

The same reasoning applies elsewhere: ROE and debt-to-equity return nothing
when book equity is negative, rather than reporting a large negative ROE or a
negative leverage ratio that reads as *low* leverage while meaning the
opposite.

---

## Data sources & methodology

**Financial data** comes from Yahoo Finance via `yfinance`. It's free and
convenient, with the tradeoff that it's an unofficial API — fields occasionally
change shape or come back empty, so most of the codebase is defensive about
missing values.

**Filings** come from SEC EDGAR via `edgartools`.

**Sector normalization ranges** are derived from Aswath Damodaran's NYU Stern
industry dataset for net margin and ROE. Debt-to-equity ranges are widened from
Damodaran's market-value figures to plausible book-value levels, since the KPI
engine uses book equity. Current-ratio ranges are the lowest-confidence numbers
in the project — no authoritative cross-sector dataset exists, so they're built
from qualitative sector liquidity characteristics. See `sector_profiles.py` for
full sourcing notes and caveats.

**Sentiment** uses NLTK's VADER on recent news headlines. VADER is a
general-purpose lexicon, not finance-tuned, so treat it as a rough signal.

**Sector P/E bands** (in `valuation.py`) are broad "typical range" figures
for each sector, not a live peer screen — they place a company loosely rather
than precisely, and are wide on purpose. They reflect long-run norms rather
than any single point in the cycle, so a whole sector re-rating pushes many of
its companies outside the band at once. Read "above the band" as *expensive
relative to this sector's history*, not as *overvalued*.

P/E is a poor tool in two sectors and the app says so inline: REITs are
valued on funds from operations because depreciation depresses their reported
earnings, and bank earnings swing with reserve and mark-to-market accounting.

**Price data** is cached for 15 minutes rather than the 24 hours used for
statements — quotes change constantly, and free market data is delayed anyway,
so nothing here is presented as realtime.

---

## Known limitations

- **Discover's candidate pool is hand-maintained.** Ticker symbols change,
  companies get acquired, and tier placements are debatable. Dead symbols return
  no data and sort to the bottom rather than crashing, but the lists go stale.
- **Cold-cache Discover is slow.** Scoring 16 candidates means up to 32 network
  calls on first run for a given sector/tier combination. Subsequent runs hit
  the 24-hour disk cache.
- **Health Score weights are a judgment call**, not a validated model. They
  encode a reasonable view of what matters, not an empirically optimized one.
- **Yahoo Finance sector labels can surprise you.** Alphabet classifies as
  Communication Services, not Technology — so a ticker's score is benchmarked
  against its real sector, which may differ from where intuition puts it.
- **Sector P/E bands are not a peer screen.** They're broad long-run ranges,
  so they place a company loosely. A sector-wide re-rating pushes many of its
  companies outside the band at once.
- **The watchlist is single-user.** No authentication means no user to key it
  against — fine locally, wrong on a shared deployment.
- **No test coverage yet** for `sentiment_engine.py` or the network paths of
  the fetchers. The fetchers' normalization logic *is* covered; what isn't is
  the live call itself.
- **`use_container_width` is deprecated** in current Streamlit versions and
  used throughout the UI. It still works but is slated for removal. Migrating
  to `width=` would raise the minimum Streamlit version, so it hasn't been
  done yet.

---

## Roadmap

- CI on every push
- Progressive rendering on Discover (render each card as its score arrives,
  instead of waiting for the full pool)
- Peer comparison — the sector bands place a company against its industry's
  long-run norms, but not against its actual named competitors today
- Possibly: an AI chat layer grounded in the KPI data

Deferred deliberately: a full screener, DCF-style intrinsic valuation,
authentication, portfolios, notifications. The focus is depth on the core
loop — look up a company, see what it's worth, see what changed, understand
whether it's healthy — rather than breadth.

---

## License

See [LICENSE](LICENSE).