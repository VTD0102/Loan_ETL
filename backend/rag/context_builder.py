from sqlalchemy import text
from sqlalchemy.orm import Session


def build_user_context(db: Session, user_id: int) -> str:
    """Query loan_applications + risk data for user, return formatted string for prompt."""
    row = db.execute(
        text(
            "SELECT status, loan_amount, term, monthly_income, dti, credit_score, "
            "is_homeowner, default_probability, risk_level, recommended_amount, recommended_term "
            "FROM loan_applications WHERE user_id = :uid ORDER BY submitted_at DESC LIMIT 1"
        ),
        {"uid": user_id},
    ).fetchone()

    if row is None:
        return "Khách hàng chưa có đơn vay nào."

    (
        status, loan_amount, term, monthly_income, dti, credit_score,
        is_homeowner, default_probability, risk_level, recommended_amount, recommended_term,
    ) = row

    lines = [
        f"- Trạng thái đơn vay gần nhất: {status}",
        f"- Số tiền xin vay: {loan_amount:,.0f} VND",
        f"- Kỳ hạn: {term} tháng",
        f"- Thu nhập hàng tháng: {monthly_income:,.0f} VND",
        f"- DTI (tỷ lệ nợ/thu nhập): {dti:.2%}",
        f"- Credit score tự khai: {credit_score:.0f}",
        f"- Tình trạng sở hữu nhà: {'Có nhà' if is_homeowner else 'Không có nhà'}",
    ]

    if default_probability is not None:
        lines.append(f"- Xác suất vỡ nợ (ML): {default_probability:.2%}")
    if risk_level is not None:
        lines.append(f"- Mức rủi ro: {risk_level}")
    if recommended_amount is not None and recommended_term is not None:
        lines.append(f"- Đề xuất của hệ thống: {recommended_amount:,.0f} VND / {recommended_term} tháng")

    return "\n".join(lines)
