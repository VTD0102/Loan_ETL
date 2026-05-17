"""
guardrails.py

Input and output safety guardrails for the CreditIntel RAG pipeline.
- Input:  prompt-injection detection, PII probing, message length
- Output: internal-leak detection, promise detection, length cap
"""
from __future__ import annotations

import re
from dataclasses import dataclass


# ── Result type ───────────────────────────────────────────────────────────────

@dataclass
class GuardrailResult:
    """Outcome of a guardrail check."""
    passed: bool
    reason: str | None = None
    sanitized_text: str | None = None


# ── Constants ─────────────────────────────────────────────────────────────────

MAX_INPUT_LENGTH = 2000
MAX_OUTPUT_LENGTH = 3000

# Prompt-injection patterns (case-insensitive)
_INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"ignore\s+(all\s+)?above",
        r"disregard\s+(all\s+)?(previous|prior|above)",
        r"you\s+are\s+now\s+(?:a|an|the)?\s*\w+",
        r"act\s+as\s+(?:a|an|the)?\s*\w+",
        r"reveal\s+(your\s+)?(system\s+)?prompt",
        r"show\s+(me\s+)?(your\s+)?(system\s+)?prompt",
        r"output\s+(the\s+)?(system\s+)?prompt",
        r"print\s+(the\s+)?(system\s+)?prompt",
        r"what\s+(is|are)\s+your\s+(system\s+)?instructions",
        r"repeat\s+(the\s+)?instructions\s+above",
        r"forget\s+(everything|all)",
        r"override\s+(your\s+)?(system|safety)",
        r"jailbreak",
        r"DAN\s+mode",
        r"bỏ\s+qua\s+(các\s+)?(hướng\s+dẫn|chỉ\s+dẫn|lệnh)\s+(trước\s+đó|ở\s+trên)",
        r"quên\s+(tất\s+cả|mọi\s+thứ|các\s+hướng\s+dẫn)",
        r"(tiết\s+lộ|cho\s+tôi\s+biết|hiển\s+thị|in\s+ra)\s+.{0,30}(prompt|system\s+prompt|hướng\s+dẫn\s+hệ\s+thống)",
        r"(prompt|system\s+prompt|hướng\s+dẫn\s+hệ\s+thống)\s+.{0,30}(của\s+bạn|của\s+anh|của\s+chị)",
        r"lặp\s+lại\s+.{0,30}(hướng\s+dẫn|chỉ\s+dẫn)\s+(ở\s+trên|trước\s+đó)",
    ]
]

# PII probing — asking for other users' data
_PII_PROBING_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"thông\s+tin\s+(của\s+)?user\s+khác",
        r"thông\s+tin\s+(của\s+)?khách\s+hàng\s+khác",
        r"thông\s+tin\s+hồ\s+sơ\s+(của\s+)?khách\s+hàng\s+khác",
        r"cho\s+tôi\s+xem\s+hồ\s+sơ\s+của",
        r"hồ\s+sơ\s+(của\s+)?người\s+khác",
        r"danh\s+sách\s+(tất\s+cả\s+)?(khách\s+hàng|user|người\s+dùng)",
        r"show\s+(me\s+)?(all\s+)?users?",
        r"list\s+(all\s+)?customers?",
        r"other\s+(user|customer|client)('s)?\s+(data|info|profile|application)",
        r"dump\s+(the\s+)?database",
        r"select\s+\*\s+from",
    ]
]

# Internal leak — database artefacts that must never appear in output
_INTERNAL_LEAK_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bloan_applications\b",
        r"\bchat_sessions\b",
        r"\bchat_messages\b",
        r"\busers\b\.\b(password_hash|email)\b",
        r"\bSELECT\b.+\bFROM\b",
        r"\bINSERT\s+INTO\b",
        r"\bUPDATE\b.+\bSET\b",
        r"\bDELETE\s+FROM\b",
        r"\bDROP\s+TABLE\b",
        r"openrouter_api_key",
        r"secret_key\s*=",
        r"password_hash",
        r"sk-[a-zA-Z0-9]{20,}",          # API key pattern
        r"model_version\s*[:=]\s*['\"]",  # internal model metadata
    ]
]

# Promise detection — LLM should never guarantee approval
_PROMISE_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"(chắc\s+chắn|chắn\s+chắn)\s+(sẽ\s+)?được\s+(duyệt|vay|chấp\s+thuận|phê\s+duyệt)",
        r"sẽ\s+được\s+duyệt\s+(ngay|100%|chắc\s+chắn)",
        r"tôi\s+(cam\s+kết|hứa|đảm\s+bảo)\s+.{0,30}(duyệt|vay|chấp\s+thuận)",
        r"(guaranteed|definitely|certainly)\s+(to\s+)?(be\s+)?approv",
        r"(i\s+)?(promise|guarantee)\s+.{0,30}approv",
        r"100%\s+(chance|approval|approved)",
    ]
]

_PROMISE_DISCLAIMER = (
    "\n\n⚠️ *Lưu ý: Kết quả trên chỉ mang tính tư vấn. "
    "Quyết định phê duyệt cuối cùng luôn thuộc về bộ phận Admin của CreditIntel.*"
)


# ── Public API ────────────────────────────────────────────────────────────────

def check_input(message: str) -> GuardrailResult:
    """Validate user message before processing.

    Returns GuardrailResult with ``passed=False`` and a user-friendly
    ``reason`` if the message is rejected.
    """
    # Length check
    if len(message) > MAX_INPUT_LENGTH:
        return GuardrailResult(
            passed=False,
            reason=(
                f"Tin nhắn quá dài ({len(message)} ký tự). "
                f"Vui lòng giới hạn dưới {MAX_INPUT_LENGTH} ký tự."
            ),
        )

    # Empty / whitespace
    if not message or not message.strip():
        return GuardrailResult(
            passed=False,
            reason="Tin nhắn không được để trống.",
        )

    # Prompt injection
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(message):
            return GuardrailResult(
                passed=False,
                reason=(
                    "Xin lỗi, tôi chỉ có thể hỗ trợ các câu hỏi liên quan đến "
                    "khoản vay và tài chính cá nhân. Nếu bạn cần trợ giúp, "
                    "vui lòng đặt câu hỏi cụ thể về hồ sơ vay của bạn."
                ),
            )

    # PII probing
    for pattern in _PII_PROBING_PATTERNS:
        if pattern.search(message):
            return GuardrailResult(
                passed=False,
                reason=(
                    "Vì lý do bảo mật, tôi không thể cung cấp thông tin "
                    "của khách hàng khác. Tôi chỉ có thể hỗ trợ về "
                    "hồ sơ vay của chính bạn."
                ),
            )

    return GuardrailResult(passed=True)


def check_output(response: str) -> GuardrailResult:
    """Validate LLM output before returning to user.

    Returns GuardrailResult. If the response contains unsafe content,
    ``sanitized_text`` provides a safe replacement.
    """
    # Internal leak — hard block
    for pattern in _INTERNAL_LEAK_PATTERNS:
        if pattern.search(response):
            return GuardrailResult(
                passed=False,
                reason="internal_leak",
                sanitized_text=(
                    "Xin lỗi, đã xảy ra lỗi khi xử lý câu trả lời. "
                    "Vui lòng thử lại hoặc đặt câu hỏi khác."
                ),
            )

    # Promise detection — soft fix (append disclaimer)
    sanitized = response
    has_promise = False
    for pattern in _PROMISE_PATTERNS:
        if pattern.search(response):
            has_promise = True
            break

    if has_promise:
        sanitized = response + _PROMISE_DISCLAIMER

    # Length cap
    if len(sanitized) > MAX_OUTPUT_LENGTH:
        # Truncate at the last complete sentence before the cap
        truncated = sanitized[:MAX_OUTPUT_LENGTH]
        last_period = max(
            truncated.rfind("."),
            truncated.rfind("。"),
            truncated.rfind("\n"),
        )
        if last_period > MAX_OUTPUT_LENGTH * 0.6:
            truncated = truncated[: last_period + 1]
        sanitized = truncated + "\n\n*(Câu trả lời đã được rút gọn.)*"

    if sanitized != response:
        return GuardrailResult(passed=True, sanitized_text=sanitized)

    return GuardrailResult(passed=True)
