"""
Full ETL pipeline — Home Credit Default Risk.

Bronze → Silver → Gold (DuckDB local)

Run: python -m machinelearning.etl.pipeline
"""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BASE_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from machinelearning.etl.load_bronze import main as bronze
from machinelearning.etl.etl_silver import main as silver
from machinelearning.etl.etl_gold import main as gold


if __name__ == "__main__":
    bronze()
    silver()
    gold()
