# Architecture

Two diagrams, following the C4 model: pick one zoom level per
diagram instead of mixing them. Stops at Container level -
Component/Code level diagrams aren't worth it at this project's
size yet.

## 1. System Context

Who uses this, and what does it talk to. No internal structure.

```mermaid
graph TD
    User["Beginner investor<br/>(no financial background)"]
    App["Investor Assistant"]
    Yahoo["Yahoo Finance<br/>(financial data source)"]

    User -- "answers a few questions,<br/>gets ticker suggestions,<br/>explores KPIs" --> App
    App -- "fetches financial statements<br/>and sector data" --> Yahoo
```

## 2. Containers

The main pieces inside the app, and how they connect. Stops here
- no individual function names, no CSS, no caching details.

```mermaid
graph TD
    subgraph Frontend [Streamlit Frontend]
        Discover["Discover Page<br/>(risk/interest questions -> suggested tickers)"]
        Dashboard["KPI Dashboard<br/>(single-company deep dive)"]
        Compare["Compare Stocks Page"]
        Watchlist["Watchlist Page"]
    end

    subgraph Backend [Data & Scoring]
        Fetcher["Financials Fetcher"]
        Engine["KPI Engine"]
        Scorer["Health Scorer<br/>(sector-aware)"]
    end

    Yahoo["Yahoo Finance"]

    Discover --> Engine
    Dashboard --> Engine
    Compare --> Engine
    Watchlist --> Engine

    Engine --> Fetcher
    Engine --> Scorer
    Fetcher --> Yahoo
```