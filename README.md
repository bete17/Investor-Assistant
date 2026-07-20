# Investor-Assistant
Helps pulls every bit of information from the internet that an investor need to fully understand a stock before they invest. Financial Statements, Public Sentiments (reddit, news, etc), Fundamental KPI. The purpose of this is to help investors, financial analyst to do their research faster without having to manually navigate through the internet to find the data your looking for. 

# Features 
1. Stock Storyline : Quick history of the business from it was first founded to recent big information to understand how the stock came to be.

2. Key KPI's : Major indicators of the performance of the stock to show how a stock is doing.

3. Sentiments Analyzer : Analyze the public sentiment to understand what people think about the stock.

4. Risk Engine : Evaluate how risky the stock is and list out the things that makes it risky.

5. Business Model Schema : A diagram that shows how the business is structured to understand the flow of the business

6. A Chatbot : To go deeper into the finnacial reports an agent that can answers your questions about the financial statements.

# 📂 System Architecture & Data Flow

Sentinel is built on a modular, decoupled architecture following clean software engineering principles:

```text
[External Data APIs] ──► [Data Fetching & Caching] ──► [Analysis Engines] ──► [Presentation Layer]
(yFinance / News API)    (data_fetcher.py + Cache)    (risk_engine.py /    (app.py - Streamlit)
                                                      sentiment_analyzer)

# How To Start

1. **Clone the repository**
   Open your terminal and clone the project, then navigate into the project directory:
   ```bash
   git clone <paste-github-repo-url-here>
   cd <repository-name>

