import os
import sys

# Make `from src import ...` imports work when running pytest from repo root.
TREND_SENSOR_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if TREND_SENSOR_ROOT not in sys.path:
    sys.path.insert(0, TREND_SENSOR_ROOT)
