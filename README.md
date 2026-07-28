# Investor Assistant

A dashboard that pulls a company's real financial data and turns it into
something you can actually read — plain-language reads on profitability,
growth, debt, and cash flow, plus a sector-aware health score.

This is built for someone who wants to sanity-check a stock without
knowing how to read a balance sheet. If you're a professional analyst
you'll probably want something deeper — this is meant for a fast,
honest first look, not a replacement for real research.

## What it does right now

- **KPI Dashboard** — enter a ticker, get profitability, growth, debt,
  and liquidity metrics translated into plain labels (Strong / Healthy
  / Elevated / etc.), plus quarterly revenue and net income charts.
- **Sector-aware Health Score** — a single 0-100 score combining the
  KPIs above, normalized against ranges specific to that company's
  sector, so a bank and a software company aren't graded the same way.
- **Compare Stocks** — put two companies side by side.

## Planned, not built yet

- A guided flow for people with no ticker in mind ("I don't know where
  to start")
- A watchlist
- Possibly: peer similarity/clustering, an AI chat layer grounded in
  the KPI data

Listing these here so it's clear what's real vs. an idea on the roadmap.

## Data source

Financial data comes from Yahoo Finance via `yfinance`. Sector
normalization ranges are informed by Aswath Damodaran's NYU Stern
industry dataset — see `sector_profiles.py` for specifics and known
limitations.

## Architecture

See `docs/architecture.md` for a system context and container diagram.

## Getting started

This project uses [uv](https://astral.sh/uv) for dependency management.

```bash
git clone <repo-url>
cd Investor-Assistant
uv sync
```

Run the app:
```bash
uv run streamlit run UI/kpi_dashboard.py
```

Run the tests:
```bash
uv run pytest tests/ -v
```