"""
pytest automatically loads this file before running tests.

Your modules are split across three folders:
  - kpi_engine.py, health_score.py, sector_profiles.py -> project root
  - utils.py, kpi_dashboard.py                          -> UI/
  - storyline_fetcher.py, financials_fetcher.py       -> data/

This adds all three to Python's search path so imports like
`from kpi_engine import ...`, `from utils import ...`, and
`from storyline_fetcher import ...` work no matter where pytest is run from.
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
UI_FOLDER = os.path.join(PROJECT_ROOT, "UI")
DATA_FOLDER = os.path.join(PROJECT_ROOT, "data")

sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, UI_FOLDER)
sys.path.insert(0, DATA_FOLDER)