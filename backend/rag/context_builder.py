"""
context_builder.py

Build structured JSON context + RAG prompt text từ loan application + ML results.
Tuân theo: docs/rag_ml_context_requirements.md (4 blocks: form, ML, advisory, quality).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from models.application import LoanApplication


# ── Thresholds & lookup tables ────────────────────────────────────────────────

_DTI_BANDS = [
    (0.30, "Tốt (< 30%)"),
    (0.43, "Cần chú ý (30%–43%)"),
    (float("inf"), "Rủi ro cao (> 43%)"),
]

_CREDIT_BANDS = [
    (580,  "Kém (< 580)"),
    (670,  "Trung bình (580–669)"),
    (740,  "Tốt (670–739)"),
    (800,  "Rất tốt (740–799)"),
    (float("inf"), "Xuất sắc (≥ 800)"),
]

_EDUCATION = {
    1: "Tiểu học",
    2: "THCS",
    3: "THPT",
    4: "Cao đẳng / Đại học",
    5: "Sau đại học",
}

_STABLE_EMPLOYMENT = {"Employed", "Working", "State servant", "Commercial associate"}


# ── Public API ────────────────────────────────────────────────────────────────

def build_user_context(db: Session, user_id: Any) -> str:
    """Trả về text context cho RAG prompt (format section 4 của requirements doc)."""
    ctx = build_context_json(db, user_id)
    return _json_to_text(ctx)


def build_context_json(db: Session, user_id: Any) -> dict:
    """Trả về JSON context đầy đủ 4 block theo requirements doc."""
    app = (
        db.query(LoanApplication)
        .filter(LoanApplication.user_id == user_id)
        .order_by(LoanApplication.submitted_at.desc())
        .first()
    )

    if app is None:
        return {"error": "Khách hàng chưa có đơn vay nào."}

    form_ctx = _build_form_context(app)
    ml_ctx   = _build_ml_context(app)
    advisory = _build_advisory_context(app, ml_ctx)
    quality  = _build_quality_context(app)

    return {
        "form_context":     form_ctx,
        "ml_context":       ml_ctx,
        "advisory_context": advisory,
        "data_quality":     quality,
    }


# ── Block 1: Form context ─────────────────────────────────────────────────────

def _build_form_context(app: LoanApplication) -> dict:
    return {
        "status":           app.status,
        # Core loan
        "loan_amount":      _f(app.loan_amount),
        "term_months":      app.term,
        "monthly_income":   _f(app.monthly_income),
        "dti":              _f(app.dti),
        "credit_score":     app.credit_score,
        # Employment
        "employment_status": app.employment_status,
        "occupation_type":   app.occupation_type,
        "years_employed":    _f(app.years_employed),
        # Lifestyle
        "is_homeowner":      app.is_homeowner,
        "listing_category":  app.listing_category,
        # Bureau
        "num_bureau_records":      app.num_bureau_records,
        "num_active_credit":       app.num_active_credit,
        "total_overdue_amount":    _f(app.total_overdue_amount),
        "max_credit_overdue_days": app.max_credit_overdue_days,
        "has_bad_debt":            app.has_bad_debt,
        "income_verifiable_flag":  app.income_verifiable_flag,
        # Demographics
        "age_years":       app.age_years,
        "gender":          ("Nam" if app.gender_male_flag else "Nữ") if app.gender_male_flag is not None else None,
        "education":       _EDUCATION.get(app.education_ordinal),
        "is_married":      app.is_married_flag,
        "cnt_children":    app.cnt_children,
        "cnt_fam_members": _f(app.cnt_fam_members),
    }


# ── Block 2: ML prediction context ───────────────────────────────────────────

def _build_ml_context(app: LoanApplication) -> dict:
    return {
        "default_probability": _f(app.default_probability),
        "risk_level":          app.risk_level,
        "risk_score":          app.risk_score,        # (1 - prob) * 100, cao = an toàn hơn
        "recommended_amount":  _f(app.recommended_amount),
        "recommended_term":    app.recommended_term,
        "model_version":       app.model_version,
        "has_prediction":      app.default_probability is not None,
    }


# ── Block 3: Derived advisory context ────────────────────────────────────────

def _build_advisory_context(app: LoanApplication, ml_ctx: dict) -> dict:
    loan    = _f(app.loan_amount) or 0
    rec     = ml_ctx.get("recommended_amount") or 0
    prob    = ml_ctx.get("default_probability") or 0
    dti     = _f(app.dti) or 0
    cs      = app.credit_score or 0
    income  = _f(app.monthly_income) or 1

    # Loan vs recommended
    loan_vs_rec = None
    if rec > 0:
        diff_pct = (loan - rec) / rec * 100
        if diff_pct > 10:
            loan_vs_rec = f"Cao hơn đề xuất {diff_pct:.0f}% ({_usd(loan)} so với {_usd(rec)})"
        elif diff_pct < -10:
            loan_vs_rec = f"Thấp hơn đề xuất {abs(diff_pct):.0f}% ({_usd(loan)} so với {_usd(rec)})"
        else:
            loan_vs_rec = f"Phù hợp với đề xuất ({_usd(loan)} ≈ {_usd(rec)})"

    # Term vs recommended
    term_vs_rec = None
    rec_term = ml_ctx.get("recommended_term")
    if app.term and rec_term:
        if app.term > rec_term:
            term_vs_rec = f"Kỳ hạn chọn ({app.term} tháng) dài hơn đề xuất ({rec_term} tháng)"
        elif app.term < rec_term:
            term_vs_rec = f"Kỳ hạn chọn ({app.term} tháng) ngắn hơn đề xuất ({rec_term} tháng)"
        else:
            term_vs_rec = f"Kỳ hạn phù hợp với đề xuất ({app.term} tháng)"

    # Ratios
    loan_to_income        = round(loan / income, 2) if income else None
    loan_to_annual_income = round(loan / (income * 12), 2) if income else None

    # Bands
    dti_band = _band(dti, _DTI_BANDS)
    cs_band  = _band(cs, _CREDIT_BANDS)

    # Primary risk factors (tối đa 4)
    risk_factors: list[str] = []
    if dti > 0.43:
        risk_factors.append("DTI quá cao (> 43%) — tỷ lệ nợ/thu nhập nặng")
    elif dti > 0.30:
        risk_factors.append("DTI ở mức cần chú ý (30%–43%)")
    if cs < 580:
        risk_factors.append("Điểm tín dụng thấp (< 580)")
    elif cs < 670:
        risk_factors.append("Điểm tín dụng trung bình (580–669), chưa đủ mạnh")
    if rec > 0 and loan > rec * 1.1:
        risk_factors.append(f"Số tiền vay cao hơn hạn mức đề xuất ({_usd(loan)} > {_usd(rec)})")
    if app.has_bad_debt:
        risk_factors.append("Có lịch sử nợ xấu")
    if app.max_credit_overdue_days and app.max_credit_overdue_days > 60:
        risk_factors.append(f"Từng quá hạn tối đa {app.max_credit_overdue_days} ngày")
    if app.total_overdue_amount and _f(app.total_overdue_amount) and _f(app.total_overdue_amount) > 0:
        risk_factors.append(f"Còn nợ quá hạn {_usd(_f(app.total_overdue_amount))}")

    # Positive factors (tối đa 4)
    positives: list[str] = []
    if app.is_homeowner:
        positives.append("Có sở hữu nhà (tài sản ổn định)")
    if dti < 0.30:
        positives.append("DTI thấp (< 30%) — gánh nặng nợ nhẹ")
    if cs >= 740:
        positives.append("Điểm tín dụng tốt (≥ 740)")
    if app.income_verifiable_flag:
        positives.append("Thu nhập có thể xác minh")
    if app.employment_status in _STABLE_EMPLOYMENT:
        positives.append("Có việc làm ổn định")
    if app.years_employed and _f(app.years_employed) and _f(app.years_employed) >= 3:
        positives.append(f"Kinh nghiệm làm việc {int(_f(app.years_employed))} năm")
    if app.has_bad_debt is False:
        positives.append("Không có lịch sử nợ xấu")

    # Suggested actions
    actions: list[str] = []
    if rec > 0 and loan > rec * 1.1:
        actions.append(f"Cân nhắc giảm số tiền vay về mức đề xuất ({_usd(rec)})")
    if dti > 0.43:
        actions.append("Giảm DTI: trả bớt nợ hiện tại trước khi vay thêm")
    if cs < 670:
        actions.append("Cải thiện điểm tín dụng: thanh toán đúng hạn, giảm dư nợ thẻ tín dụng")
    if app.has_bad_debt or (app.total_overdue_amount and _f(app.total_overdue_amount) and _f(app.total_overdue_amount) > 0):
        actions.append("Xử lý nợ xấu / nợ quá hạn trước khi nộp đơn lại")
    if prob > 0.4:
        actions.append("Hồ sơ hiện tại có rủi ro cao — nên cải thiện tài chính trước khi nộp lại")

    return {
        "loan_vs_recommended":    loan_vs_rec,
        "term_vs_recommended":    term_vs_rec,
        "loan_to_monthly_income": loan_to_income,
        "loan_to_annual_income":  loan_to_annual_income,
        "dti_band":               dti_band,
        "credit_score_band":      cs_band,
        "primary_risk_factors":   risk_factors[:4],
        "positive_factors":       positives[:4],
        "suggested_actions":      actions,
    }


# ── Block 4: Data quality context ─────────────────────────────────────────────

def _build_quality_context(app: LoanApplication) -> dict:
    imputed = app.imputed_features or []
    if not imputed:
        confidence = "cao"
        note = "Tất cả thông tin do khách hàng cung cấp trực tiếp."
    elif len(imputed) <= 2:
        confidence = "trung bình"
        note = (
            f"Một số dữ liệu được hệ thống mặc định ({', '.join(imputed)}). "
            "Kết quả tư vấn có thể chưa phản ánh toàn bộ tình hình tài chính."
        )
    else:
        confidence = "thấp"
        note = (
            f"Nhiều dữ liệu được hệ thống mặc định ({', '.join(imputed)}). "
            "Nên dùng ngôn ngữ thận trọng khi tư vấn."
        )
    return {
        "imputed_features": imputed,
        "confidence_level": confidence,
        "note":             note,
    }


# ── Text formatter (section 4 format) ─────────────────────────────────────────

def _json_to_text(ctx: dict) -> str:
    if "error" in ctx:
        return ctx["error"]

    f  = ctx["form_context"]
    ml = ctx["ml_context"]
    ad = ctx["advisory_context"]
    q  = ctx["data_quality"]

    lines: list[str] = []

    # ── Block 1: Form ──────────────────────────────────────────────────────────
    lines.append("THÔNG TIN ĐƠN VAY GẦN NHẤT")
    lines.append(f"- Trạng thái đơn: {f['status']}")
    lines.append(f"- Số tiền xin vay: {_usd(f['loan_amount'])}")
    lines.append(f"- Kỳ hạn: {f['term_months']} tháng")
    lines.append(f"- Thu nhập hàng tháng: {_usd(f['monthly_income'])}")
    lines.append(f"- DTI: {_pct(f['dti'])} — {ad['dti_band']}")
    lines.append(f"- Điểm tín dụng: {f['credit_score']} — {ad['credit_score_band']}")
    lines.append(f"- Tình trạng việc làm: {f['employment_status'] or '—'}")
    if f.get("occupation_type"):
        lines.append(f"- Nghề nghiệp: {f['occupation_type']}")
    if f.get("years_employed") is not None:
        lines.append(f"- Năm kinh nghiệm: {int(f['years_employed'])} năm")
    lines.append(f"- Sở hữu nhà: {'Có' if f['is_homeowner'] else 'Không'}")
    lines.append(f"- Mục đích vay: {f['listing_category'] or '—'}")
    if f.get("income_verifiable_flag") is not None:
        lines.append(f"- Thu nhập xác minh: {'Có' if f['income_verifiable_flag'] else 'Không'}")

    # Bureau summary
    bureau: list[str] = []
    if f.get("num_bureau_records") is not None:
        bureau.append(f"hồ sơ tín dụng: {f['num_bureau_records']}")
    if f.get("num_active_credit") is not None:
        bureau.append(f"tín dụng đang hoạt động: {f['num_active_credit']}")
    if f.get("has_bad_debt") is not None:
        bureau.append(f"nợ xấu: {'Có' if f['has_bad_debt'] else 'Không'}")
    if f.get("total_overdue_amount") and f["total_overdue_amount"] > 0:
        bureau.append(f"nợ quá hạn: {_usd(f['total_overdue_amount'])}")
    if bureau:
        lines.append(f"- Lịch sử tín dụng: {' | '.join(bureau)}")

    # ── Block 2: ML ───────────────────────────────────────────────────────────
    lines.append("")
    lines.append("KẾT QUẢ ML")
    if ml["has_prediction"]:
        lines.append(f"- Xác suất vỡ nợ dự đoán: {_pct(ml['default_probability'])}")
        lines.append(f"- Mức rủi ro: {ml['risk_level']}")
        lines.append(f"- Risk score: {ml['risk_score']}/100 (càng cao càng an toàn)")
        if ml["recommended_amount"] is not None:
            lines.append(f"- Hạn mức hệ thống đề xuất: {_usd(ml['recommended_amount'])} / {ml['recommended_term']} tháng")
        if ml["model_version"]:
            lines.append(f"- Phiên bản model: {ml['model_version']}")
        if ad.get("loan_vs_recommended"):
            lines.append(f"- So sánh số tiền: {ad['loan_vs_recommended']}")
        if ad.get("term_vs_recommended"):
            lines.append(f"- So sánh kỳ hạn: {ad['term_vs_recommended']}")
    else:
        lines.append("- Chưa có kết quả ML cho đơn này.")

    # ── Block 3: Advisory ─────────────────────────────────────────────────────
    lines.append("")
    lines.append("PHÂN TÍCH TƯ VẤN")
    if ad["primary_risk_factors"]:
        lines.append("- Yếu tố rủi ro chính:")
        for r in ad["primary_risk_factors"]:
            lines.append(f"  • {r}")
    if ad["positive_factors"]:
        lines.append("- Điểm tích cực:")
        for p in ad["positive_factors"]:
            lines.append(f"  • {p}")
    if ad["suggested_actions"]:
        lines.append("- Khuyến nghị:")
        for a in ad["suggested_actions"]:
            lines.append(f"  • {a}")

    # ── Block 4: Data quality ─────────────────────────────────────────────────
    lines.append("")
    lines.append("ĐỘ TIN CẬY DỮ LIỆU")
    lines.append(f"- Mức độ tin cậy: {q['confidence_level']}")
    lines.append(f"- {q['note']}")

    return "\n".join(lines)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _f(value: Any) -> float | None:
    if value is None:
        return None
    return float(value) if isinstance(value, Decimal) else float(value)


def _usd(value: Any) -> str:
    if value is None:
        return "không rõ"
    return f"${float(value):,.0f}"


def _pct(value: Any) -> str:
    if value is None:
        return "không rõ"
    v = float(value)
    return f"{v:.1%}" if v <= 1 else f"{v / 100:.1%}"


def _band(value: float, bands: list[tuple]) -> str:
    for threshold, label in bands:
        if value < threshold:
            return label
    return bands[-1][1]
