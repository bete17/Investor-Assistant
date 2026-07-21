#imports
import os
import json
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer

#Ensure the VADER is downloaded
try:
    nltk.data.find('sentiment/vader_lexicon.zip')
except LookupError:
    nltk.download('vader_lexicon', quiet=True)
    
CACHE_DIR = os.path.dirname(os.path.abspath(__file__)) + "/cache"

def load_news_from_cache(ticker: str):
    """Loads news data from a cache file if it exists.

    Args:
        ticker (str): The stock ticker symbol.
    Returns:
        dict: The data loaded from the cache file, or None if the file doesn't exist.
    """
    
    file_path = f"{CACHE_DIR}/{ticker.upper()}_news.json"
    
    # Check if the cache file exists
    if not os.path.exists(file_path):
        print(f"❌ Cache file for {ticker.upper()} does not exist.")
        return []]
    
    # Read the cache file
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        return data if isinstance(data, list) else []
    except Exception as e:
        print(f"❌ Error reading cache file for {ticker.upper()}: {e}")
        return []


def calculate_sentiment(text):
    """Find out whether the news sentiment is positive or negative

    Args:
        text (str): The input text to be analyzed.
    """
    pass

def generate_aggregate_sentiment_story(ticker: str) -> dict:
    """
    Main orchestrator: Loads the ticker's news, calculates sentiment for each,
    averages the scores, and returns a narrative summary for our storyline.
    """
    pass

print ("CACHE_DIR")