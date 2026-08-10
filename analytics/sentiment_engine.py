import os
import json
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer

# Ensure VADER lexicon is downloaded
try:
    nltk.data.find('sentiment/vader_lexicon.zip')
except LookupError:
    nltk.download('vader_lexicon', quiet=True)


class SentimentEngine:
    """
    Analyzes news headline sentiment for stock tickers using VADER NLP.
    """

    def __init__(self, cache_dir: str = None):
        """
        Constructor: Initializes the analyzer instance and VADER engine.
        """
        # Set default cache directory relative to this file if not provided
        if cache_dir is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.cache_dir = os.path.join(base_dir, "data", "cache")
        else:
            self.cache_dir = cache_dir

        # Initialize the VADER Sentiment Engine once on object creation
        self.sia = SentimentIntensityAnalyzer()

    def load_news_from_cache(self, ticker: str) -> list:
        """Loads cached news items for a ticker."""
        file_path = os.path.join(self.cache_dir, f"{ticker.upper()}_news.json")

        if not os.path.exists(file_path):
            print(f"❌ Cache file for {ticker.upper()} does not exist.")
            return []

        try:
            with open(file_path, "r") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except Exception as e:
            print(f"❌ Error reading cache file for {ticker.upper()}: {e}")
            return []

    def calculate_sentiment(self, headline: str) -> float:
        """Scores a single headline string."""
        if not headline:
            return 0.0

        # Uses the instance's pre-loaded VADER engine
        score = self.sia.polarity_scores(headline)
        return score.get("compound", 0.0)

    def generate_aggregate_sentiment_story(self, ticker: str) -> dict:
        """Main orchestrator: Calculates aggregate sentiment and generates narrative."""
        news = self.load_news_from_cache(ticker)
        sentiment_scores = []

        for article in news:
            headline = article.get("headline", "")
            score = self.calculate_sentiment(headline)
            sentiment_scores.append(score)

        if sentiment_scores:
            average_score = sum(sentiment_scores) / len(sentiment_scores)
        else:
            average_score = 0.0

        if average_score > 0.05:
            sentiment_summary = (
                f"Recent breaking news for {ticker.upper()} reflects an overall positive, bullish market tone."
            )
        elif average_score < -0.05:
            sentiment_summary = (
                f"Recent breaking news for {ticker.upper()} indicates an overall negative, cautious market sentiment."
            )
        else:
            sentiment_summary = (
                f"Recent news coverage for {ticker.upper()} is currently neutral with balanced reporting."
            )

        return {
            "ticker": ticker.upper(),
            "average_score": round(average_score, 4),
            "total_articles_analyzed": len(sentiment_scores),
            "sentiment_summary": sentiment_summary,
        }


# --- Test Runner ---
if __name__ == "__main__":
    test_ticker = "ASTS"
    print(f"--- Testing Class-Based Sentiment Engine for {test_ticker} ---")

    # 1. Instantiate the class (triggers __init__)
    analyzer = SentimentEngine()

    # 2. Call the orchestrator method
    result = analyzer.generate_aggregate_sentiment_story(test_ticker)
    print(json.dumps(result, indent=2))