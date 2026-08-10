# Investor Assistant

A Streamlit dashboard that pulls a company's real financial data and turns it
into something you can actually read — plain-language reads on profitability,
growth, debt, and cash flow, a sector-aware health score, and a year-over-year
diff of what management changed in their own words in the 10-K.

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

### Sector-aware Health Score
A single 0–100 score combining the KPIs above, normalized against ranges
specific to that company's sector — so a bank and a software company aren't
graded on the same curve. A 25% net margin is unremarkable for software and
exceptional for grocery retail; the score accounts for that.

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

The KPI Dashboard, Compare Stocks, and Discover pages work with **no keys at
all** — they only use Yahoo Finance data. Keys are only needed for Storyline.

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
  skeletons.py             Shared loading-placeholder helpers
  styles.css               Dark-terminal design system
  utils.py                 Formatting helpers
  pages/
    1_compare_stocks.py
    2_storyline.py
    3_discover.py

analytics/                 Pure computation — no I/O, no Streamlit
  kpi_engine.py            KPI calculations
  health_score.py          0-100 weighted sector-aware score
  sector_profiles.py       Per-sector normalization ranges
  sector_lookup.py         Cached sector resolution
  storyline_engine.py      MD&A diff + LLM summarization
  sentiment_engine.py      VADER news sentiment
  discover_engine.py       Quiz → risk tier, candidate pool, ranking

data/                      External data access, with on-disk caching
  financials_fetcher.py    yfinance quarterly financials (24h cache)
  news_fetcher.py          yfinance news
  storyline_fetcher.py     SEC EDGAR 10-K Item 7 extraction
  cache/                   Cached JSON (gitignored)

tests/
docs/architecture.md       C4 context + container diagrams
conftest.py                Test path setup
```

The layering is deliberate: `data/` fetches, `analytics/` computes on plain
Python data structures, `UI/` renders. Nothing in `analytics/` imports Streamlit,
which is what makes it unit-testable without mocking a web framework.

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
- **No test coverage yet** for `health_score.py`, `sentiment_engine.py`, or the
  fetchers. `health_score.py` is the highest-risk gap — it's untested math.

---

## Roadmap

- Tests for `health_score.py` and CI on every push
- Progressive rendering on Discover (render each card as its score arrives,
  instead of waiting for the full pool)
- Watchlist
- Possibly: peer similarity/clustering, an AI chat layer grounded in the KPI data

Deferred deliberately: a full screener, valuation multiples, authentication,
portfolios, notifications. The focus is depth on the core loop — look up a
company, see what changed, understand whether it's healthy — rather than
breadth.

---

## License

See [LICENSE](LICENSE).