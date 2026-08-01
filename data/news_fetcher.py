import yfinance as yf
import json
from data.financials_fetcher import is_cache_valid, CACHE_DIR

def fetch_news(ticker: str) -> list:
    """Get all the news and articles related to the stock from yfinance

    Args:
        ticker (str): the companys ID
    returns:
        dict: a dictionary containing all the news and articles related to the stock
    """
    
    # Check if the news data is already cached
    if is_cache_valid(f"{CACHE_DIR}/{ticker.upper()}_news.json"):
        print(f"📦 Loading {ticker.upper()} news from local cache...")
        with open(f"{CACHE_DIR}/{ticker.upper()}_news.json", "r") as f:
            return json.load(f)
    
    stock = yf.Ticker(ticker)
    
    try:
        raw_news = stock.news
        if not raw_news:
            return []
            
        cleaned_news = []
        
        # 2. Extract only what our sentiment analyzer needs
        for item in raw_news:
            # yfinance stores details inside a 'content' sub-dictionary
            content = item.get("content", {}) if "content" in item else item
            
            headline = content.get("title", "")
            provider = content.get("provider", {}).get("displayName", "Unknown") if isinstance(content.get("provider"), dict) else "Unknown"
            pub_date = content.get("pubDate", "")
            
            if headline:
                cleaned_news.append({
                    "headline": headline,
                    "publisher": provider,
                    "published_at": pub_date
                })
                
        # 3. Cache the clean data
        write_news_to_cache(ticker, cleaned_news)
        return cleaned_news
        
    except Exception as e:
        print(f"❌ Error fetching news for {ticker.upper()}: {e}")
        return []

def write_news_to_cache(ticker: str, news_data: dict):
    """Write the news data to a cache file

    Args:
        ticker (str): the companys ID
        news_data (dict): the news data to write to the cache
    """
    
    cache_path = f"{CACHE_DIR}/{ticker.upper()}_news.json"
    
    try:
        with open(cache_path, "w") as f:
            json.dump(news_data, f, indent=2, default=str)
    except Exception as e:
        print(f"❌ Failed to write news cache for {ticker.upper()}: {e}")

# Local Test Runner
if __name__ == "__main__":
    test_ticker = "ASTS"
    print(f"--- Running News Fetcher for {test_ticker} ---")
    articles = fetch_news(test_ticker)
    
    if articles:
        print(f"🎉 Success! Fetched {len(articles)} articles.")
        print("Sample Article Structure:")
        print(json.dumps(articles[0], indent=2))
    else:
        print("⚠️ No articles found or fetch failed.")