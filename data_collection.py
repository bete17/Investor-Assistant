import os
import json
import time
import yfinance as yf

# Define where our cache files will live
CACHE_DIR = "data/cache"
os.makedirs(CACHE_DIR, exist_ok=True)

# Cache expiration limit: 24 hours (in seconds)
CACHE_EXPIRY_LIMIT = 86400  

def is_cache_valid(filepath: str) -> bool:
    """
    Checks if a cached file exists and if it is fresh (less than 24 hours old).
    """
    path = filepath
    
    #checks for file existence
    if not os.path.exists(path):
        return False
    
    #get the file age
    file_creation_time = os.path.getmtime(path)
    current_time = time.time()
    file_age = current_time - file_creation_time
    
    #main function logic
    if file_age >= CACHE_EXPIRY_LIMIT:
        return False
    else:
        return True
    


def fetch_company_financials(ticker: str) -> dict:
    """
    Retrieves the Balance Sheet, Income Statement, and Cash Flow Statement
    for a given ticker. Uses local cache if valid, otherwise pulls from yfinance.
    """
    cache_path = f"{CACHE_DIR}/{ticker.upper()}_financials.json"
    
    # Check our cache first
    if is_cache_valid(cache_path):
        print(f"📦 Loading {ticker.upper()} financials from local cache...")
        with open(cache_path, "r") as f:
            return json.load(f)
            
    print(f"🌐 Fetching live financial data for {ticker.upper()} from yfinance...")
    
    # Initialize the yfinance Ticker object
    stock = yf.Ticker(ticker)
    
    try:
        # TODO 2: Extract the Balance Sheet, Income Statement, and Cash Flow
        # from the 'stock' object and convert them to dictionaries.
        # Hint: Try stock.quarterly_balance_sheet, stock.quarterly_income_stmt, etc.
        # Don't forget to convert them to dicts using .to_dict()!
        
        financial_data = {
            "balance_sheet": {}, # <-- Put your extracted balance sheet dict here
            "income_statement": {}, # <-- Put your extracted income statement dict here
            "cash_flow": {} # <-- Put your extracted cash flow dict here
        }
        
        # Save to cache for next time
        with open(cache_path, "w") as f:
            json.dump(financial_data, f, default=str) # default=str handles date-type keys
            
        return financial_data
        
    except Exception as e:
        print(f"❌ Error fetching data for {ticker.upper()}: {e}")
        return {}


# Quick local test runner
if __name__ == "__main__":
    test_ticker = "AAPL"
    print(f"--- Testing Sentinel Ingestion Pipeline with {test_ticker} ---")
    
    data = fetch_company_financials(test_ticker)
    
    # Check if we got data back
    if data:
        print("🎉 Success! Retrieved keys:", list(data.keys()))
    else:
        print("😢 Failed to retrieve data.")