# Thiết kế: Luật mềm cho công cụ điều chỉnh khoản vay (soft-propose / hard-verify)

Ngày: 2026-06-03
Trạng thái: Đã triển khai (2026-06-03)

> Khoá rank liên-strategy đã chốt khi triển khai: **ưu tiên thay đổi ít nhất so với
> đơn gốc** — `_change_magnitude` = tỉ lệ giảm tiền cộng tỉ lệ tăng kỳ hạn (chuẩn hoá),
> với `default_probability` là tiêu chí phụ. Lựa chọn này giữ đúng triết lý UX hiện tại
> (đưa cho khách phương án gần nhất với cái họ xin mà vẫn an toàn) và không phá test hồi quy.

## Bối cảnh

Khi một đơn vay bị `AUTO_REJECTED` (xác suất vỡ nợ > 0.4) và khách hỏi về việc
nộp lại, `chat_service` gọi `loan_adjustment_tool.find_best_reapplication_option`.
Hàm này hiện sinh ứng viên `(số tiền, kỳ hạn)` bằng một **lưới cứng**:
`_candidate_stages` thử hai giai đoạn theo thứ tự cố định — `extend_term`
(giữ nguyên số tiền, tăng kỳ hạn trong `{12,24,36,48,60}`) rồi `reduce_amount`
(ở kỳ hạn tối đa 60 tháng, giảm số tiền xuống 75%/50%/25%/min $500). Mỗi ứng viên
được chạy qua `ml_service.predict`, lọc dưới ngưỡng 0.4, `validate_confirmed_values`,
rồi rank. Giai đoạn đầu có phương án hợp lệ thì dừng luôn, không xét giai đoạn sau.

Việc kích hoạt và điều phối hoàn toàn **tất định** (keyword matching trong
`_is_loan_adjustment_request` + code gọi thẳng service). LLM chỉ diễn đạt lại kết quả
đã tính sẵn; nó không suy luận hướng điều chỉnh, không chọn tham số. Đây là kiến trúc
tool-augmented luật cứng, không phải agentic.

## Mục tiêu

Cho phép LLM (RAG) **suy luận hướng và tham số điều chỉnh** dựa trên hồ sơ rủi ro
của khách (ví dụ: DTI cao thì giảm số tiền hiệu quả hơn kéo dài kỳ hạn), trong khi
**giữ nguyên model rủi ro làm trọng tài cuối** về việc một phương án có an toàn không.
Nói cách khác: LLM *đề xuất*, model *kiểm chứng*.

## Ba bất biến (không được phá)

1. **Model là trọng tài cuối.** Mọi cặp `(số tiền, kỳ hạn)` — bất kể nguồn LLM hay
   lưới cứng — phải qua `ml_service.predict()` và `validate_confirmed_values()`.
   Không con số nào do LLM đề xuất được hiển thị hay chốt nếu chưa qua cổng này.
2. **Worst case = hành vi hiện tại.** Ứng viên lưới cứng luôn nằm trong tập xét, nên
   nếu LLM lỗi hoặc đề xuất vô dụng, kết quả không bao giờ tệ hơn bản hiện tại.
3. **Contract đầu ra bất biến.** `find_best_reapplication_option` vẫn trả về
   `LoanAdjustmentResult` đúng shape cũ. `chat_service`, `build_pending_action`,
   luồng confirm/decline, và `pending_action` của frontend không phải thay đổi.

## Kiến trúc: Cách 3 — hợp nhất LLM + lưới cứng

Chạy *cả hai* nguồn ứng viên (LLM đề xuất + lưới cứng), gộp lại, làm sạch, rồi đưa
toàn bộ qua đúng vòng verify/rank hiện có. Vì lưới cứng luôn có mặt, đây vừa là lưới
an toàn (bất biến #2) vừa cho LLM cơ hội thêm phương án nhắm trúng hồ sơ hơn.

### Thành phần

Logic LLM đặt ở **module mới** `backend/services/loan_adjustment_reasoner.py`, để
`loan_adjustment_tool.py` (hiện ~435 dòng) không phình thêm và giữ một mục đích rõ.

**(a) Risk-factor summarizer** — hàm thuần, tất định, trong reasoner:

```
build_risk_summary(app, previous_applications, existing_monthly_debt) -> dict
```

Trích từ app bị `AUTO_REJECTED`: số tiền/kỳ hạn bị từ chối, `default_probability`,
`dti`, `monthly_income`, nợ hàng tháng hiện có, `employment_status`, `years_employed`,
`has_bad_debt`, `total_overdue_amount`. Là input cho prompt; không gọi LLM; test độc lập.

**(b) LLM candidate proposer** — trong reasoner:

```
propose_candidates(summary: dict) -> list[Candidate]
```

Gọi OpenRouter dùng lại `LLM_MODEL`, `OPENROUTER_BASE_URL`, `temperature=0`,
`max_tokens` nhỏ (~300), singleton có khoá kiểu `_get_classifier_llm` trong `router.py`
(double-checked locking). Trả về tối đa **6** ứng viên. Parse JSON chịu lỗi (xử lý
fence ```json như router.py). **Bất kỳ lỗi/timeout/JSON hỏng → trả `[]`** để caller
tự fallback về lưới.

**(c) Candidate merger** — trong reasoner:

```
merge_candidates(llm_candidates, grid_candidates) -> list[tuple[Decimal, int, str]]
```

Gộp hai nguồn; kẹp `amount` về `[500, 150000]`; ép `term` về `SUPPORTED_TERMS`
(`{12,24,36,48,60}`), term lạ bị loại; khử trùng theo `(amount, term)`. Giữ nhãn
`strategy` và `rationale` (nếu có) để diễn giải về sau.

**(d) Sửa trong `loan_adjustment_tool.py`** — `find_best_reapplication_option`:
thay vì duyệt `_candidate_stages` theo giai đoạn có dừng sớm, hàm sẽ: lấy grid từ
`_candidate_stages`, gọi `reasoner.propose_candidates(summary)` (khi cờ bật),
`merge_candidates(...)`, rồi chạy đúng vòng verify/rank hiện có trên **toàn bộ** tập
hợp nhất. `_passing_rank` vẫn là sort cuối nên thứ hạng tất định với cùng tập passing.

### Thay đổi hành vi có chủ đích: bỏ dừng-sớm-theo-stage

Hiện `find_best_reapplication_option` xét `extend_term` trước; nếu giai đoạn đó có
phương án hợp lệ thì trả luôn, không xét `reduce_amount`. Thiết kế mới **bỏ dừng sớm**:
gom toàn bộ ứng viên (cả hai chiến lược + đề xuất LLM) rồi rank một lần. Lý do: để
phương án "giảm tiền" do LLM đề xuất có cơ hội cạnh tranh công bằng với phương án
"tăng kỳ hạn" của lưới, thay vì bị chặn bởi thứ tự giai đoạn. Hệ quả: với cùng một
đơn, top-1 trả về có thể đổi so với hiện tại nếu một phương án giảm-tiền rank tốt hơn
theo `_passing_rank`. Đây là thay đổi đã được chấp nhận trong thiết kế.

`_passing_rank` hiện tính theo từng strategy (reduce_amount ưu tiên mức giảm nhỏ nhất;
extend_term ưu tiên kỳ hạn tăng ít nhất). Khi rank chung một tập trộn hai strategy,
cần một khoá sort thống nhất. Kế hoạch triển khai phải định nghĩa rõ thứ tự ưu tiên
liên-strategy (đề xuất: ưu tiên `default_probability` thấp, rồi mức thay đổi so với
đơn gốc nhỏ nhất, rồi kỳ hạn ngắn hơn) và cập nhật `_passing_rank` tương ứng — giữ
tất định.

## Luồng dữ liệu

```
chat_service.send
  └─ _is_loan_adjustment_request (keyword, giữ nguyên)
       └─ find_best_reapplication_option(db, user_id)
            ├─ app = latest AUTO_REJECTED
            ├─ summary   = build_risk_summary(app, prev, debt)        [tất định]
            ├─ llm_cands = reasoner.propose_candidates(summary)       [LLM, lỗi→[]]
            ├─ grid_cands = _candidate_stages(app)                    [lưới cứng, luôn có]
            ├─ all = merge_candidates(llm_cands, grid_cands)          [kẹp biên + dedupe]
            ├─ FOR each (amount, term) in all:                        ★ CỔNG CỨNG
            │     prob = ml_service.predict(...)
            │     if prob > 0.4: continue
            │     validate_confirmed_values(...)  # ValueError → bỏ
            │     passing.append(...)
            ├─ rank theo _passing_rank (khoá liên-strategy) → top-3
            └─ return LoanAdjustmentResult(... rationale ...)         [shape CŨ]
```

## Contract của LLM proposer

Prompt tiếng Việt (khớp văn phong `services/`): yêu cầu LLM đề xuất tối đa 6 phương án
`(số tiền, kỳ hạn)` để đưa xác suất vỡ nợ xuống dưới ngưỡng, ưu tiên hướng phù hợp với
yếu tố rủi ro chính, CHỈ trả JSON.

Output schema:

```json
{"candidates": [
  {"amount": 8000, "term": 36, "strategy": "reduce_amount",
   "rationale": "DTI cao nên giảm số tiền tác động mạnh hơn kéo dài kỳ hạn"}
]}
```

- `amount`: số USD; `term` ∈ {12,24,36,48,60}; `strategy` ∈ {extend_term, reduce_amount, both}.
- Mọi field đều được `merge_candidates` làm sạch; LLM gợi ý hướng, không tự quyết kết quả.
- `rationale` của phương án top-1 được thread vào `format_result_for_rag` để LLM chính
  diễn giải *vì sao* khi trả lời khách.

## Xử lý lỗi, fallback, cờ

- **Cờ** `rag_loan_reasoner_enabled: bool = True` trong `core/config.py` (đúng pattern
  `rag_reranker_enabled`). Tắt → bỏ bước LLM, dùng grid thuần (cộng việc bỏ dừng sớm) →
  phục vụ A/B và eval.
- **LLM lỗi/timeout** → `propose_candidates` trả `[]`, log warning, merger còn grid.
- **LLM trả số vô lý** (âm, vượt 150k, term lạ) → merger kẹp/loại; không tới `predict`
  với input bẩn.
- **Không phương án nào dưới ngưỡng** → giữ nguyên nhánh `fallback_proposal` /
  `no_passing_option` hiện có.
- Toàn bộ wrap trong `_LoanAdjustmentToolError` như hiện tại → nếu vỡ, `chat_service`
  trả `_LOAN_ADJUSTMENT_ERROR_MESSAGE`.

## Test (style backend/tests_local/test_*.py, script standalone)

- `build_risk_summary`: tất định, assert các field từ một app giả.
- `merge_candidates`: kẹp biên, khử trùng, loại term lạ, union đúng.
- `propose_candidates`: inject LLM giả trả JSON tốt → parse đúng; trả rác/raise → `[]`.
- Tích hợp `find_best_reapplication_option` với proposer giả:
  - (i) proposer trả `[]` → kết quả **trùng khít tập passing** của bản hiện tại trên
    cùng input (bất biến #2). Lưu ý: thứ hạng top-1 có thể đổi do bỏ dừng sớm; assert
    trên *tập* passing chứ không chỉ top-1, và kiểm tra riêng hành vi ranking mới.
  - (ii) proposer thêm một phương án thật sự dưới ngưỡng → nó xuất hiện trong top-3.

## Ảnh hưởng eval

Vì grid luôn có mặt và `_passing_rank` là sort tất định, bộ eval tất định không regress
do nhiễu sampling của LLM. Có thể chạy A/B `rag_loan_reasoner_enabled` on/off để báo cáo
so sánh.

## Phạm vi KHÔNG làm (YAGNI)

- Không làm vòng lặp agentic/function-calling nhiều bước (đã loại ở giai đoạn thiết kế).
- Không đổi contract `LoanAdjustmentResult`, `build_pending_action`, hay frontend.
- Không đổi cơ chế trigger keyword (`_is_loan_adjustment_request`) hay luồng
  confirm/decline.
- Không đổi ngưỡng auto-reject 0.4 hay logic model.
