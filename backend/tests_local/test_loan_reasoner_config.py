import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from core.config import settings


def test_loan_reasoner_flag_defaults_true():
    assert hasattr(settings, "rag_loan_reasoner_enabled")
    assert settings.rag_loan_reasoner_enabled is True


if __name__ == "__main__":
    test_loan_reasoner_flag_defaults_true()
    print("loan reasoner config test passed")
