"""
pytest automatically loads this file before running tests.

Your modules are split across two folders:
  - kpi_engine.py, health_score.py, sector_profiles.py -> project root
  - utils.py, kpi_dashboard.py                          -> UI/

This adds both to Python's search path so `from kpi_engine import ...`
and `from utils import ...` both work no matter where pytest is run
from.
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
UI_FOLDER = os.path.join(PROJECT_ROOT, "UI")

sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, UI_FOLDER)