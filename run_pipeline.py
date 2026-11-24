"""
Run the whole AutoVoice pipeline end to end:  python run_pipeline.py

To use a REAL dataset instead of synthetic data:
  1. put it at data/raw/reviews.csv with the columns listed in docs/data_dictionary.md
  2. run:  python run_pipeline.py --real
     (skips the generator and the planted-signal validation, which only make
      sense for synthetic data)
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))
sys.path.insert(0, str(Path(__file__).parent / "powerbi"))
sys.path.insert(0, str(Path(__file__).parent / "site"))

import build_db  # noqa: E402
import build_pbip  # noqa: E402
import build_site  # noqa: E402
import charts  # noqa: E402
import clean  # noqa: E402
import drivers  # noqa: E402
import early_warning  # noqa: E402
import generate_data  # noqa: E402
import powerbi_export  # noqa: E402
import run_queries  # noqa: E402
import sentiment  # noqa: E402
import themes  # noqa: E402
import validate_planted  # noqa: E402

REAL = "--real" in sys.argv

STEPS = [
    ("1  Generate synthetic data", generate_data.main, not REAL),
    ("2  Clean", clean.main, True),
    ("5a Tag themes + theme sentiment", themes.main, True),
    ("4  Sentiment models", sentiment.main, True),
    ("3  Build SQLite database", build_db.main, True),
    ("3  Run SQL queries", run_queries.main, True),
    ("7a Key drivers, ranking, scenarios", drivers.main, True),
    ("7b Early-warning alerts", early_warning.main, True),
    ("6  Export Power BI tables", powerbi_export.main, True),
    ("6  Generate Power BI project (PBIP)", build_pbip.main, True),
    ("   Charts", charts.main, True),
    ("   Validate against planted signals", validate_planted.main, not REAL),
    ("   Build showcase site data", build_site.main, True),
]

if __name__ == "__main__":
    t0 = time.time()
    for name, fn, enabled in STEPS:
        if not enabled:
            continue
        print(f"\n=== {name} " + "=" * (60 - len(name)))
        fn()
    print(f"\nDone in {time.time() - t0:.0f}s")
