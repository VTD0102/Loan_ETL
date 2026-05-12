"""
Full ETL pipeline — Home Credit Default Risk.

Bronze → Silver → Gold (DuckDB local)

Run: python -m etl.pipeline
"""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from etl.load_bronze import main as bronze
from etl.etl_silver import main as silver
from etl.etl_gold import main as gold


if __name__ == "__main__":
    bronze()
    silver()
    gold()
