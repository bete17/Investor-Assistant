# Investor-Assistant
Helps pulls every bit of information from the internet that an investor need to fully understand a stock before they invest. Financial Statements, Public Sentiments (reddit, news, etc), Fundamental KPI. The purpose of this is to help investors, financial analyst to do their research faster without having to manually navigate through the internet to find the data your looking for. 

# Features 
1. Stock Storyline : Quick history of the business from it was first founded to recent big information to understand how the stock came to be.

2. Key KPI's : Major indicators of the performance of the stock to show how a stock is doing.

3. Sentiments Analyzer : Analyze the public sentiment to understand what people think about the stock.

4. Risk Engine : Evaluate how risky the stock is and list out the things that makes it risky.

5. Business Model Schema : A diagram that shows how the business is structured to understand the flow of the business

6. A Chatbot : To go deeper into the finnacial reports an agent that can answers your questions about the financial statements.

# 📂 System Architecture

Sentinel is built on a modular, decoupled architecture following clean software engineering principles:

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                        TIER 3: PRESENTATION (UI)                        │
│                           app.py (Streamlit)                            │
│  ┌─────────────────────────┐ ┌───────────────────┐ ┌─────────────────┐  │
│  │ Custom CSS (style.css)  │ │ Metric KPI Cards  │ │ Timeline Layout │  │
│  └─────────────────────────┘ └───────────────────┘ └─────────────────┘  │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ (Data Requests)
┌────────────────────────────────────▼────────────────────────────────────┐
│                  TIER 2: ANALYTICAL ENGINE LAYER                        │
│  ┌───────────────────────┐ ┌───────────────────┐ ┌───────────────────┐  │
│  │ sentiment_analyzer.py │ │ risk_classifier.p │ │timeline_builder.p │  │
│  │  (VADER News Pulse)   │ │  (ML Risk Model)  │ │(LLM 10-K Storyline│  │
│  └───────────────────────┘ └───────────────────┘ └───────────────────┘  │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ (Cache Reads / API Calls)
┌────────────────────────────────────▼────────────────────────────────────┐
│              TIER 1: DATA INGESTION & LOCAL CACHING LAYER               │
│  ┌───────────────────────┐ ┌───────────────────┐ ┌───────────────────┐  │
│  │ financials_fetcher.py │ │  news_fetcher.py  │ │  sec_extractor.py │  │
│  │   (yfinance API)      │ │   (yfinance/News) │ │  (edgartools API) │  │
│  └───────────┬───────────┘ └─────────┬─────────┘ └─────────┬─────────┘  │
│              └───────────────────────┼─────────────────────────┘        │
│                                      ▼                                  │
│                       Local File Cache (data/cache/*.json)               │
└─────────────────────────────────────────────────────────────────────────┘
```

# How To Start
1. **Clone the repository**
   Open your terminal and clone the project, then navigate into the project directory:
   ```bash (cmd)
   git clone <paste-github-repo-url-here>
   cd <repository-name>
   ```
2.***Create virtual environment***
```bash (cmd)
   python -m venv venv
   venv\Scripts\activate.bat
   ```
***Note : You will know the virtual env is activated when you see (venv) appear at the beginning of your terminal prompt.***

3.***Install packages***
```bash (cmd)
   python -m pip install --upgrade pip
   pip install -r requirements.txt
```

