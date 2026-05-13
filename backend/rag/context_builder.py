from typing import Any

from sqlalchemy.orm import Session

from models.application import LoanApplication


def build_user_context(db: Session, user_id: Any) -> str:
    """Build the latest application context used by the RAG prompt."""
    app = (
        db.query(LoanApplication)
        .filter(LoanApplication.user_id == user_id)
        .order_by(LoanApplication.submitted_at.desc())
        .first()
    )

    if app is None:
        return "Khách hàng chưa có đơn vay nào."

    lines = [
        f"- Trạng thái đơn vay gần nhất: {app.status}",
        f"- Số tiền xin vay: {_money(app.loan_amount)}",
        f"- Kỳ hạn: {app.term} tháng",
        f"- Thu nhập hàng tháng: {_money(app.monthly_income)}",
        f"- DTI (tỷ lệ nợ/thu nhập): {_percent(app.dti)}",
        f"- Credit score tự khai: {app.credit_score}",
        f"- Tình trạng sở hữu nhà: {'Có nhà' if app.is_homeowner else 'Không có nhà'}",
    ]

    if app.default_probability is not None:
        lines.append(f"- Xác suất vỡ nợ (ML): {_percent(app.default_probability)}")
    if app.risk_level is not None:
        lines.append(f"- Mức rủi ro: {app.risk_level}")
    if app.recommended_amount is not None and app.recommended_term is not None:
        lines.append(f"- Đề xuất của hệ thống: {_money(app.recommended_amount)} / {app.recommended_term} tháng")
    if app.model_version:
        lines.append(f"- Phiên bản model: {app.model_version}")
    if app.imputed_features:
        lines.append(
            "- Dữ liệu mô hình được hệ thống mặc định/impute, không phải khách hàng cung cấp: "
            + ", ".join(app.imputed_features)
        )

    return "\n".join(lines)


def _money(value: Any) -> str:
    if value is None:
        return "không rõ"
    return f"{float(value):,.0f} VND"


def _percent(value: Any) -> str:
    if value is None:
        return "không rõ"
    val = float(value)
    return f"{val:.2%}" if val <= 1 else f"{(val / 100):.2%}"
