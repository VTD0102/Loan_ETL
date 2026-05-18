"""
personalizer.py

Build personalized context and tone instructions based on the user's
profile and latest application status.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ── Result type ───────────────────────────────────────────────────────────────

@dataclass
class PersonalizationContext:
    """Container for personalized prompt variables."""
    user_display_name: str = "Quý khách"
    application_status: str | None = None
    tone_instructions: str = ""
    greeting_line: str = ""


# ── Status → Tone mapping ────────────────────────────────────────────────────

_STATUS_TONES: dict[str | None, dict[str, str]] = {
    # Application rejected (auto or admin)
    "auto_rejected": {
        "tone": (
            "Giọng điệu: ĐỒNG CẢM và KHÍCH LỆ. "
            "Khách hàng vừa bị từ chối — tuyệt đối không trách móc hay phán xét. "
            "Tập trung vào giải thích lý do một cách tế nhị và gợi ý các bước cải thiện cụ thể. "
            "Dùng ngôn ngữ tích cực: 'Bạn có thể cải thiện bằng cách...' thay vì 'Bạn bị từ chối vì...'."
        ),
        "greeting": "Tôi hiểu đơn vay của bạn chưa đạt yêu cầu lần này. Tôi sẽ giúp bạn hiểu rõ hơn và tìm cách cải thiện.",
    },
    "admin_rejected": {
        "tone": (
            "Giọng điệu: ĐỒNG CẢM và CHUYÊN NGHIỆP. "
            "Đơn bị Admin từ chối — giải thích rằng đây là quyết định sau khi xem xét kỹ. "
            "Gợi ý liên hệ bộ phận hỗ trợ nếu muốn biết thêm chi tiết. "
            "Vẫn tích cực: có thể nộp lại sau khi cải thiện."
        ),
        "greeting": "Tôi thấy đơn vay gần nhất chưa được phê duyệt. Hãy để tôi giúp bạn tìm hiểu thêm.",
    },

    # Pending review
    "pending_review": {
        "tone": (
            "Giọng điệu: KHÍCH LỆ và THÔNG TIN. "
            "Đơn đang chờ Admin xem xét — giải thích quy trình rõ ràng, "
            "ước tính thời gian (1–3 ngày làm việc). "
            "Có thể chia sẻ kết quả ML sơ bộ nếu khách hàng hỏi."
        ),
        "greeting": "Đơn vay của bạn đang được xem xét. Tôi có thể giúp bạn hiểu thêm về kết quả đánh giá sơ bộ.",
    },

    # Approved & awaiting info
    "approved": {
        "tone": (
            "Giọng điệu: CHÚC MỪNG và HƯỚNG DẪN. "
            "Đơn đã được duyệt — bày tỏ chúc mừng chân thành. "
            "Hướng dẫn bước tiếp theo rõ ràng: nộp CMND/CCCD."
        ),
        "greeting": "Chúc mừng bạn! Đơn vay đã được phê duyệt. Tôi sẽ hướng dẫn bạn các bước tiếp theo.",
    },
    "awaiting_info": {
        "tone": (
            "Giọng điệu: HƯỚNG DẪN CỤ THỂ. "
            "Khách hàng cần nộp thêm hồ sơ — hướng dẫn chi tiết từng bước: "
            "vào Hồ sơ của tôi → chọn đơn → tải lên CMND/CCCD + số điện thoại."
        ),
        "greeting": "Đơn vay của bạn đã qua bước xét duyệt. Bước tiếp theo là nộp thông tin cá nhân để hoàn tất.",
    },
    "info_submitted": {
        "tone": (
            "Giọng điệu: YÊN TÂM và CHUYÊN NGHIỆP. "
            "Thông tin đã nộp — xác nhận hồ sơ đang được xử lý. "
            "Trả lời các câu hỏi về thời gian giải ngân nếu có."
        ),
        "greeting": "Thông tin cá nhân của bạn đã được nộp thành công. Hồ sơ đang trong quá trình xử lý.",
    },

    # No application yet
    None: {
        "tone": (
            "Giọng điệu: THÂN THIỆN và CHÀO ĐÓN. "
            "Khách hàng chưa có đơn vay — giới thiệu ngắn gọn dịch vụ CreditIntel. "
            "Khuyến khích nộp đơn nếu phù hợp. Giải thích quy trình dễ hiểu."
        ),
        "greeting": "Chào mừng bạn đến với CreditIntel! Tôi có thể giúp bạn tìm hiểu về dịch vụ vay vốn của chúng tôi.",
    },
}

# ── Intent-specific instructions ─────────────────────────────────────────────

_INTENT_INSTRUCTIONS: dict[str, str] = {
    "loan_inquiry": (
        "Khách hàng đang hỏi về khoản vay. Tập trung vào: số tiền vay, kỳ hạn, "
        "trạng thái đơn, so sánh với hạn mức đề xuất. Trích dẫn dữ liệu cụ thể "
        "từ hồ sơ nếu có. Chỉ nêu trạng thái đơn hiện tại khi khách hàng hỏi trực tiếp "
        "về trạng thái hiện tại; nếu họ hỏi một tình huống/chính sách, hãy trả lời đúng "
        "tình huống đó trước."
    ),
    "risk_explanation": (
        "Khách hàng muốn hiểu kết quả đánh giá rủi ro. Giải thích: xác suất vỡ nợ, "
        "risk score, mức rủi ro (LOW/MEDIUM/HIGH) bằng ngôn ngữ dễ hiểu. "
        "Tránh thuật ngữ kỹ thuật phức tạp. Ví dụ: thay vì 'P(default) = 0.35' "
        "nói 'Xác suất vỡ nợ ước tính khoảng 35%'."
    ),
    "policy_question": (
        "Khách hàng hỏi về chính sách. Trả lời dựa trên tài liệu chính sách, "
        "trích dẫn rõ nguồn (ví dụ: 'Theo policy.md'). Nếu câu hỏi nằm ngoài "
        "phạm vi tài liệu, nói rõ và gợi ý liên hệ hỗ trợ. Với các câu hỏi về "
        "AUTO_REJECTED, bị từ chối, AWAITING_INFO, DTI, hạn mức LOW/MEDIUM/HIGH, "
        "hãy trả lời theo quy tắc/chính sách chung. Không được bác bỏ giả định của "
        "người dùng bằng trạng thái hồ sơ hiện tại, trừ khi họ hỏi rõ 'trạng thái "
        "đơn hiện tại của tôi là gì'."
    ),
    "personal_advice": (
        "Khách hàng muốn tư vấn cải thiện hồ sơ. Đưa ra khuyến nghị CỤ THỂ "
        "và CÓ THỂ HÀNH ĐỘNG dựa trên yếu tố rủi ro/tích cực trong hồ sơ. "
        "Ví dụ: 'DTI của bạn hiện tại là 45% — bạn nên trả bớt X khoản nợ để giảm xuống dưới 35%'."
    ),
    "greeting": (
        "Đây là lời chào / cảm ơn. Phản hồi thân thiện, ngắn gọn. "
        "Giới thiệu ngắn bản thân là trợ lý tín dụng CreditIntel. "
        "Gợi ý những gì bạn có thể giúp. Nếu tin nhắn chỉ là 'giúp với' hoặc quá "
        "mơ hồ, hãy hỏi người dùng muốn hỗ trợ vấn đề gì về khoản vay/hồ sơ; không "
        "tự phân tích trạng thái đơn hoặc chỉ số tài chính."
    ),
    "off_topic": (
        "Câu hỏi KHÔNG liên quan đến tài chính/tín dụng. "
        "Từ chối LỊCH SỰ và hướng dẫn quay lại chủ đề. "
        "Ví dụ: 'Tôi chuyên về tư vấn tín dụng nên chưa thể giúp câu hỏi này. "
        "Bạn có muốn hỏi gì về khoản vay hoặc hồ sơ tài chính không?'"
    ),
}


# ── Public API ────────────────────────────────────────────────────────────────

def build_personalization(
    user: "User | None",
    app: "LoanApplication | None",
) -> PersonalizationContext:
    """Build personalized context from user profile + latest application.

    Caller is responsible for fetching ``user`` and ``app`` from the database
    (or passing ``None``). This keeps the RAG layer decoupled from the ORM
    session.
    """
    ctx = PersonalizationContext()

    if user is not None and getattr(user, "username", None):
        ctx.user_display_name = user.username

    if app is not None:
        ctx.application_status = (app.status or "").lower()
    else:
        ctx.application_status = None

    tone_config = _STATUS_TONES.get(ctx.application_status) or _STATUS_TONES.get(None)
    ctx.tone_instructions = tone_config["tone"]
    ctx.greeting_line = tone_config["greeting"]
    return ctx


def get_intent_instructions(intent: str) -> str:
    """Return intent-specific instructions for the LLM prompt."""
    return _INTENT_INSTRUCTIONS.get(intent, _INTENT_INSTRUCTIONS["loan_inquiry"])
