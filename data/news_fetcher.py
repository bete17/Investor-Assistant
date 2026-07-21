import yfinance as yf
import os
import json
from financials_fetcher import is_cache_valid, CACHE_DIR

def fetch_news(ticker: str):
    """Get all the news and articles related to the stock from yfinance

    Args:
        ticker (str): the companys ID
    returns:
        dict: a dictionary containing all the news and articles related to the stock
    """
    pass

def write_news_to_cache(ticker: str, news_data: dict):
    """Write the news data to a cache file

    Args:
        ticker (str): the companys ID
        news_data (dict): the news data to write to the cache
    """
    pass