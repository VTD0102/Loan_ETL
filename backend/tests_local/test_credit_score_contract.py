import sys
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from machinelearning.ml.train_scorecard import ALL_FEATURES
from services.credit_score_service import _build_features


def test_scorecard_service_builds_current_training_feature_contract():
    app = SimpleNamespace(
        monthly_income=Decimal("5000"),
        loan_amount=Decimal("10000"),
        term=36,
        employment_status="Employed",
        is_homeowner=True,
        credit_score=720,
        occupation_type="Laborers",
        years_employed=Decimal("4.5"),
        num_bureau_records=3,
        num_active_credit=2,
        total_overdue_amount=Decimal("125.50"),
        max_credit_overdue_days=12,
        has_bad_debt=False,
        income_verifiable_flag=True,
        age_years=41,
        gender_male_flag=True,
        education_ordinal=4,
        cnt_children=2,
        cnt_fam_members=4,
        is_married_flag=True,
    )

    df = _build_features(app, num_previous_loans=2, previous_default_rate=0.25, dti_p75=0.4)

    assert list(df[ALL_FEATURES].columns) == ALL_FEATURES
    assert df.loc[0, "years_employed"] == 4.5
    assert df.loc[0, "occupation_type"] == "Laborers"
    assert df.loc[0, "num_bureau_records"] == 3
    assert df.loc[0, "age_years"] == 41


if __name__ == "__main__":
    test_scorecard_service_builds_current_training_feature_contract()
    print("credit_score_contract tests passed")
