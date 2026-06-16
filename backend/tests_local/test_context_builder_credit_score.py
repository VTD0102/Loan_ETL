"""RAG context phải hiển thị điểm Scorecard (fico_score), không phải điểm khách tự khai.

Lỗi gốc: context_builder đọc app.credit_score (khách tự khai, thường None) thay vì
app.fico_score (điểm Scorecard tính ở submission). Hậu quả: chatbot báo "Credit Score
là None" trong khi màn hình scorecard hiển thị 564.
"""
from decimal import Decimal
from types import SimpleNamespace

from rag import context_builder


def _make_app(**overrides):
    defaults = dict(
        status="PENDING_REVIEW",
        loan_amount=Decimal("10000"),
        term=12,
        monthly_income=Decimal("3000"),
        dti=Decimal("0.20"),
        credit_score=None,
        fico_score=None,
        employment_status="Employed",
        occupation_type="Engineer",
        years_employed=Decimal("5"),
        is_homeowner=True,
        listing_category="Personal",
        num_bureau_records=2,
        num_active_credit=1,
        total_overdue_amount=Decimal("0"),
        max_credit_overdue_days=0,
        has_bad_debt=False,
        income_verifiable_flag=True,
        age_years=30,
        gender_male_flag=True,
        education_ordinal=4,
        is_married_flag=False,
        cnt_children=0,
        cnt_fam_members=Decimal("1"),
        # ML block
        default_probability=Decimal("0.225"),
        risk_level="Medium",
        risk_score=77,
        recommended_amount=Decimal("12000"),
        recommended_term=12,
        model_version="customer_lgbm_v4_stability",
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_form_context_prefers_fico_score():
    """fico_score=564, credit_score=None → context phải hiển thị 564, không phải None."""
    app = _make_app(fico_score=564, credit_score=None)
    form = context_builder._build_form_context(app)
    assert form["credit_score"] == 564, f"kỳ vọng 564, nhận {form['credit_score']!r}"


def test_advisory_uses_fico_for_band_and_risk():
    """Điểm 564 < 580 → band 'Kém' và xuất hiện yếu tố rủi ro 'điểm tín dụng thấp'."""
    app = _make_app(fico_score=564, credit_score=None)
    ml = context_builder._build_ml_context(app)
    adv = context_builder._build_advisory_context(app, ml)
    assert adv["credit_score_band"] == "Kém (< 580)", adv["credit_score_band"]
    assert any("Điểm tín dụng thấp" in r for r in adv["primary_risk_factors"]), adv["primary_risk_factors"]


def test_none_when_no_fico():
    """Không có fico_score → None (credit_score tự khai đã bị bỏ, không bịa ra điểm)."""
    app = _make_app(fico_score=None)
    form = context_builder._build_form_context(app)
    assert form["credit_score"] is None, f"kỳ vọng None, nhận {form['credit_score']!r}"


if __name__ == "__main__":
    test_form_context_prefers_fico_score()
    test_advisory_uses_fico_for_band_and_risk()
    test_none_when_no_fico()
    print("context_builder credit_score tests passed")
