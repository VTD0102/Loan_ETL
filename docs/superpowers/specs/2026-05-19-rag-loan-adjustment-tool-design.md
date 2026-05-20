# RAG Loan Adjustment Tool V1 — Design

**Date**: 2026-05-19
**Status**: Approved (pending user review)
**Scope**: `backend/services/chat_service.py`, `backend/services/loan_adjustment_tool.py`, `backend/services/application_service.py`, `backend/models/chat.py`, `backend/init_db.py`, `backend/schemas/chat.py`, `backend/tests_local/`

## Mục tiêu

Khi khách hàng bị từ chối tự động, chatbot/RAG có thể giúp thử phương án nộp lại bằng cách đổi kỳ hạn vay và, nếu cần, dùng mức tiền gợi ý từ model. Hệ thống chỉ nộp lại đơn sau khi user xác nhận rõ trong chat.

V1 tập trung vào "tăng khả năng qua vòng tự động" bằng trạng thái `PENDING_REVIEW`. Chatbot không được hứa chắc chắn hồ sơ sẽ được duyệt cuối cùng, vì admin review và chính sách vận hành vẫn là bước sau.

## Phạm vi không bao gồm

- Không sửa trực tiếp row `AUTO_REJECTED` cũ.
- Không tự động nộp lại nếu user chưa xác nhận rõ.
- Không thay đổi model ML, threshold `0.4`, hay chính sách admin review.
- Không thêm OpenRouter function calling trong V1; tool orchestration nằm trong backend service để test deterministic.
- Không làm UI wizard mới. User có thể dùng chat text: hỏi phương án, rồi trả lời "đồng ý".

## Approach được chọn

Tool orchestration nằm trong `chat_service`:

1. `chat_service.send()` vẫn là entrypoint của chatbot.
2. Nếu user hỏi kiểu "bị từ chối, đổi kỳ hạn nào để dễ được duyệt hơn", service gọi tool mô phỏng trước khi gọi RAG.
3. Kết quả tool được inject vào context cho `rag.chain.invoke()` để LLM giải thích bằng tiếng Việt và hỏi xác nhận.
4. Proposal được lưu thành pending action trên `ChatSession`.
5. Nếu user xác nhận trong cùng session, service gọi `application_service.confirm()` để tạo đơn mới với payload đã đề xuất.

Lý do chọn approach này: không phụ thuộc model tool-calling, không cần frontend mới, reuse flow `confirm()` hiện có, và có thể test bằng monkeypatch mà không gọi external services.

## Architecture

### Schema: `ChatSession.pending_action`

Thêm một JSON column vào `backend/models/chat.py`:

```python
pending_action: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
```

`backend/init_db.py` thêm migration idempotent:

```python
"ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS pending_action JSONB",
```

Pending action shape:

```json
{
  "type": "loan_term_adjustment",
  "status": "pending_confirmation",
  "source_application_id": "...",
  "proposal": {
    "loan_amount": "25000000",
    "term": 36,
    "default_probability": 0.3521,
    "risk_level": "Medium",
    "risk_score": 61,
    "model_version": "..."
  },
  "created_at": "2026-05-19T10:15:00Z",
  "expires_at": "2026-05-19T10:45:00Z"
}
```

The JSON lives on the session because confirmation is conversational state. It is not shown in chat history unless a future frontend explicitly needs action metadata.

### Tool module: `backend/services/loan_adjustment_tool.py`

Responsibilities:

- Find the latest `AUTO_REJECTED` application for the user.
- Reconstruct an `ApplicationConfirm` payload from that rejected application.
- Run what-if predictions with `ml_service.predict()` without writing DB.
- Rank candidate terms and return a proposal only if it can reach `PENDING_REVIEW` (`default_probability <= 0.4`).
- Refuse proposal for CIC blacklist rows (`model_version == "CIC_BLACKLIST"`) because changing term does not address blacklist rejection.

Candidate strategy:

1. Keep original `loan_amount`; try terms `12, 24, 36, 48, 60`.
2. If no term passes, try `recommended_amount` from the rejected row when it is positive; test all terms again.
3. Prefer candidates that pass threshold. Rank by:
   - original amount before reduced amount,
   - lower `default_probability`,
   - closer term to current term,
   - lower term as final tie-breaker.
4. If no candidate passes, return a no-proposal result with the best observed probability for explanation only.

The tool does not call `application_service.evaluate()` because `evaluate()` may write an `AUTO_REJECTED` row. Final submission uses `application_service.confirm()` only after user confirmation.

### Chat orchestration

`chat_service.send()` adds two deterministic branches before the normal RAG answer path:

1. **Confirmation branch**
   - If `session.pending_action.type == "loan_term_adjustment"` and the user message is a clear affirmative response, call `application_service.confirm()` with the stored proposal.
   - On success, clear `pending_action`, persist the assistant answer, and return without calling LLM.
   - If the action is expired or stale, clear it and ask the user to rerun the what-if request.

2. **Proposal branch**
   - If the message asks for improving a rejection, changing term, or increasing approval chance, call `loan_adjustment_tool.find_best_reapplication_option()`.
   - If a proposal exists, augment `user_context` with a "Tool result" block and call the normal RAG chain.
   - Persist `pending_action` only after the assistant response successfully asks for confirmation.
   - If no proposal exists, inject the no-proposal result so RAG can explain why changing term is not enough.

All other messages continue through the current RAG path unchanged.

### Intent and confirmation detection

V1 uses deterministic Vietnamese keyword matching, not LLM classification:

- Adjustment intent examples: `bị từ chối`, `không được duyệt`, `đổi kỳ hạn`, `đổi thời hạn`, `nộp lại`, `tăng khả năng`, `dễ được duyệt`.
- Affirmative examples: `đồng ý`, `xác nhận`, `nộp lại`, `gửi lại`, `ok`, `duyệt phương án này`.
- Negative examples clear pending action without submit: `không`, `hủy`, `bỏ qua`, `đổi phương án khác`.

Affirmation only triggers when a valid pending action exists in the current session.

### Response behavior

For a successful proposal, assistant wording must include:

- Original rejection context.
- Proposed `loan_amount` and `term`.
- Estimated `default_probability` and expected status `PENDING_REVIEW`.
- A clear caveat: this improves the automated screening result, not a final approval guarantee.
- A clear confirmation prompt: "Bạn có muốn nộp lại với phương án này không?"

For successful confirmation:

- Return application id, status, loan amount, term, and probability.
- State that the old rejected application was not modified.

For no proposal:

- Explain that term/amount adjustments tested by the tool still do not pass the automatic threshold.
- Suggest the next safe action: review income verification, overdue debt, CIC status, or contact support/admin depending on rejection reason.

## Error handling

- No rejected application: answer normally with RAG; no pending action.
- Latest rejected application is CIC blacklist: no proposal; do not create pending action.
- Active application exists when confirming: surface existing `application_service.confirm()` error and clear stale pending action.
- ML unavailable during simulation: raise/propagate a service error consistent with current chat RAG error behavior.
- ML unavailable during final confirm: do not clear pending action unless the stored proposal is expired; user can retry after service recovery.
- Expired pending action: clear it and ask the user to request a fresh simulation.

## Data integrity and audit

- The old `AUTO_REJECTED` row remains immutable.
- The new application is created through `application_service.confirm()`, so the existing active-application guard, CIC enrichment, validation, prediction, and DB write path remain the source of truth.
- Stored proposal values are treated as a pending user intent, not as final truth. `confirm()` recomputes prediction at submit time.
- Pending action expiry is 30 minutes to reduce stale submissions.

## Testing plan

Local tests live under `backend/tests_local/` and use monkeypatch/fakes only:

1. Tool selects a passing term while keeping original amount.
2. Tool falls back to recommended amount when no term passes at original amount.
3. Tool returns no proposal for CIC blacklist.
4. Proposal chat path stores `session.pending_action` and does not write a new application.
5. Confirmation chat path calls `application_service.confirm()`, clears pending action, and persists the assistant response.
6. Negative response clears pending action without submission.
7. Expired action clears pending action and asks user to rerun simulation.
8. Non-adjustment chat messages keep the existing RAG path.

## Acceptance criteria

- A customer with latest `AUTO_REJECTED` application can ask chat for a better term.
- The system evaluates allowed terms without writing a new application.
- The assistant asks for explicit confirmation before submission.
- On confirmation, a new application is created through `application_service.confirm()`.
- The rejected application is not modified.
- All new behavior is covered by local tests without Qdrant/OpenRouter.
- Existing non-live RAG/chat/application tests continue passing.
