"""
pytest automatically loads this file before running tests.

 modules are split across four folders:
  - kpi_engine.py, health_score.py, sector_profiles.py,
    discover_engine.py, sector_lookup.py, storyline_engine.py,
    sentiment_engine.py                       -> analytics/
  - utils.py, kpi_dashboard.py                -> UI/
  - storyline_fetcher.py, financials_fetcher.py,
    news_fetcher.py                           -> data/

This adds all four to Python's search path so imports like
`from kpi_engine import ...`, `from utils import ...`, and
`from storyline_fetcher import ...` work no matter where pytest is run from.


"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
ANALYTICS_FOLDER = os.path.join(PROJECT_ROOT, "analytics")
UI_FOLDER = os.path.join(PROJECT_ROOT, "UI")
DATA_FOLDER = os.path.join(PROJECT_ROOT, "data")

sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, ANALYTICS_FOLDER)
sys.path.insert(0, UI_FOLDER)
sys.path.insert(0, DATA_FOLDER)