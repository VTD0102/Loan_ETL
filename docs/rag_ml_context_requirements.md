# RAG ML Context Requirements — Tư vấn khoản vay phù hợp

Tài liệu này mô tả các context mà RAG cần nhận từ form khách hàng và kết quả ML để có thể tư vấn khoản vay/gói vay phù hợp. Phạm vi chỉ là thiết kế tài liệu, chưa triển khai code.

## 1. Mục tiêu

RAG cần trả lời được các nhóm câu hỏi sau:

- Khách hàng có nên vay số tiền đã nhập không?
- Gói vay/kỳ hạn nào phù hợp hơn với hồ sơ hiện tại?
- Vì sao ML đánh giá khách hàng ở mức rủi ro Low/Medium/High?
- Khách hàng nên cải thiện yếu tố nào trước khi nộp lại hoặc tăng hạn mức?
- Hệ thống đề xuất hạn mức/kỳ hạn dựa trên dữ liệu nào?

RAG không được thay thế quyết định phê duyệt cuối cùng. Câu trả lời chỉ nên là tư vấn tham khảo dựa trên form, kết quả ML, chính sách nội bộ và knowledge base.

## 2. Luồng context đề xuất

```text
Khách hàng điền form vay
        |
        v
Backend lưu loan_application
        |
        v
ML predict default_probability, risk_level, risk_score, recommended_amount, recommended_term
        |
        v
Context builder gom:
  1. Form context
  2. ML prediction context
  3. Derived advisory context
  4. Data quality/explainability context
        |
        v
RAG prompt + tài liệu policy/FAQ
        |
        v
Chatbot tư vấn khoản vay/gói vay phù hợp
```

Hiện tại backend đã có hướng đi đúng: `chat_service` đảm bảo đơn mới nhất có prediction, sau đó `rag/context_builder.py` build `user_context` và inject vào prompt. Tài liệu này mô tả context nên có đầy đủ hơn để RAG tư vấn tốt hơn.

## 3. Nhóm context RAG cần

### 3.1 Form context từ khách hàng

Đây là dữ liệu khách hàng nhập khi tạo đơn vay. RAG dùng để hiểu nhu cầu vay và năng lực tài chính ban đầu.

| Field | Vai trò với RAG | Cách RAG nên dùng |
|---|---|---|
| `loan_amount` | Số tiền khách muốn vay | So sánh với hạn mức ML đề xuất và thu nhập |
| `term` | Kỳ hạn khách chọn | Đánh giá gánh nặng trả nợ theo thời gian |
| `monthly_income` | Thu nhập hàng tháng | Nền tảng để tư vấn khả năng trả nợ |
| `dti` | Tỷ lệ nợ/thu nhập | Tín hiệu chính để cảnh báo quá tải nợ |
| `credit_score` | Điểm tín dụng tự khai | Giải thích ảnh hưởng đến rủi ro và khả năng duyệt |
| `employment_status` | Tình trạng việc làm | Đánh giá độ ổn định thu nhập |
| `is_homeowner` | Có sở hữu nhà không | Tín hiệu ổn định/tài sản hỗ trợ |
| `listing_category` | Mục đích vay | Gợi ý gói vay phù hợp với mục đích |

Các field optional có thể bổ sung nếu form thu thập được:

| Field | Vai trò với RAG |
|---|---|
| `age_years` | Giải thích risk theo độ tuổi ở mức tổng quát, tránh phân biệt đối xử |
| `num_previous_loans` | Nên được lấy từ lịch sử đơn, không bắt khách nhập |
| `previous_default_rate` | Dùng để giải thích lịch sử rủi ro nếu có |
| `num_bureau_records`, `num_active_credit` | Bối cảnh lịch sử tín dụng ngoài hệ thống |
| `total_overdue_amount`, `max_credit_overdue_days`, `has_bad_debt` | Cảnh báo nợ quá hạn/nợ xấu |
| `income_verifiable_flag` | Giải thích mức độ tin cậy của thu nhập |
| `cnt_children`, `cnt_fam_members`, `is_married_flag` | Chỉ dùng nếu có chính sách rõ ràng; không nên nhấn mạnh quá mức trong câu trả lời |

### 3.2 ML prediction context

Đây là context quan trọng nhất từ ML để RAG cá nhân hóa tư vấn.

| Field | Bắt buộc? | Vai trò |
|---|---:|---|
| `default_probability` | Có | Xác suất vỡ nợ dự đoán, dùng để giải thích risk |
| `risk_level` | Có | Nhóm rủi ro `Low`, `Medium`, `High` |
| `risk_score` | Có | Điểm 0-100 để UI/RAG dễ diễn giải. Theo code hiện tại, field này đang tính bằng `(1 - default_probability) * 100`, nên giá trị cao nghĩa là an toàn hơn, không phải rủi ro cao hơn |
| `recommended_amount` | Có | Hạn mức hệ thống đề xuất |
| `recommended_term` | Có | Kỳ hạn hệ thống đề xuất |
| `model_version` | Nên có | Giúp truy vết kết quả và giải thích version |
| `feature_snapshot` | Nên có | Bản chụp feature đã đưa vào model |
| `imputed_features` | Nên có | Cho biết field nào bị mặc định/impute, giảm độ chắc chắn khi tư vấn |

RAG không nên đọc trực tiếp toàn bộ `feature_snapshot` vào prompt nếu quá dài. Nên chọn lọc các feature có ý nghĩa với khách hàng và có thể giải thích được.

### 3.3 Derived advisory context

Đây là context nên được backend tính ra trước khi đưa vào RAG. Mục tiêu là giúp RAG trả lời ổn định, không tự suy luận công thức tài chính lung tung.

| Context | Cách tính/nguồn | Vai trò tư vấn |
|---|---|---|
| `requested_vs_recommended_amount` | `loan_amount` so với `recommended_amount` | Nói khách đang vay cao/thấp hơn đề xuất |
| `requested_vs_recommended_term` | `term` so với `recommended_term` | Gợi ý giảm/tăng kỳ hạn nếu phù hợp |
| `loan_to_monthly_income` | `loan_amount / monthly_income` | Đánh giá quy mô khoản vay so với thu nhập |
| `loan_to_annual_income` | `loan_amount / (monthly_income * 12)` | Giải thích khả năng vay theo thu nhập năm |
| `dti_band` | Ví dụ: an toàn/cần chú ý/rủi ro cao | Dễ diễn giải hơn số thập phân |
| `credit_score_band` | Poor/Fair/Good/Very good/Excellent | Giải thích điểm tín dụng theo thang phổ biến |
| `primary_risk_factors` | Từ form + feature importance + rule | Nêu 2-4 nguyên nhân chính làm tăng rủi ro |
| `positive_factors` | Từ form + ML context | Nêu các yếu tố tốt như thu nhập ổn, DTI thấp |
| `suggested_actions` | Rule từ policy | Gợi ý hành động cải thiện hồ sơ |
| `confidence_notes` | Dựa trên `imputed_features` | Cảnh báo khi nhiều dữ liệu bị impute |

Ví dụ:

```text
- Khoản vay yêu cầu cao hơn hạn mức ML đề xuất: 20,000,000 VND so với 15,000,000 VND.
- DTI hiện tại: 46%, thuộc nhóm rủi ro cao.
- Điểm tín dụng: 610, thuộc nhóm trung bình/yếu.
- ML đánh giá rủi ro: High, P(default)=43.2%.
- Các yếu tố làm tăng rủi ro: DTI cao, credit score chưa tốt, số tiền vay lớn so với thu nhập.
- Gợi ý: giảm số tiền vay, chọn kỳ hạn phù hợp hơn, hoặc cải thiện DTI trước khi nộp lại.
```

### 3.4 Loan package context

Nếu hệ thống muốn RAG tư vấn "gói vay phù hợp", cần có danh mục gói vay rõ ràng. Nếu chưa có bảng package riêng, RAG chỉ nên tư vấn dựa trên `recommended_amount` và `recommended_term`.

Context tối thiểu cho mỗi gói vay:

| Field | Mô tả |
|---|---|
| `package_name` | Tên gói, ví dụ `Gói an toàn`, `Gói tiêu chuẩn`, `Gói linh hoạt` |
| `min_amount`, `max_amount` | Khoảng số tiền hỗ trợ |
| `allowed_terms` | Kỳ hạn hợp lệ |
| `target_risk_level` | Risk level phù hợp |
| `target_listing_category` | Mục đích vay phù hợp nếu có |
| `dti_limit` | DTI tối đa khuyến nghị |
| `min_credit_score` | Điểm tín dụng tối thiểu khuyến nghị |
| `notes` | Điều kiện/ghi chú chính sách |

Ví dụ package ở mức policy, không phải dữ liệu thật:

| Gói | Phù hợp với | Logic tư vấn |
|---|---|---|
| Gói an toàn | Risk High hoặc DTI cao | Hạn mức thấp, kỳ hạn ngắn/vừa, ưu tiên giảm rủi ro |
| Gói tiêu chuẩn | Risk Medium | Hạn mức vừa phải, cần Admin xét duyệt |
| Gói ưu tiên | Risk Low | Có thể đề xuất gần hạn mức cao nhất theo policy |

Nếu chưa có package catalog, RAG không nên tự tạo tên gói. Thay vào đó trả lời: "Dựa trên kết quả hiện tại, hệ thống đề xuất hạn mức X trong Y tháng."

## 4. Format context đề xuất cho RAG

Context nên có dạng text có cấu trúc, dễ đọc trong prompt:

```text
THÔNG TIN ĐƠN VAY GẦN NHẤT
- Trạng thái đơn: PENDING_REVIEW
- Số tiền khách muốn vay: 20,000,000 VND
- Kỳ hạn khách chọn: 36 tháng
- Thu nhập hàng tháng: 12,000,000 VND
- DTI: 46%
- Credit score: 610
- Việc làm: Employed
- Sở hữu nhà: Không
- Mục đích vay: debt consolidation

KẾT QUẢ ML
- Xác suất vỡ nợ dự đoán: 43.2%
- Mức rủi ro: High
- Risk score: 57/100 (điểm an toàn theo công thức hiện tại; càng cao càng tốt)
- Hạn mức hệ thống đề xuất: 3,000,000 VND
- Kỳ hạn hệ thống đề xuất: 12 tháng
- Phiên bản model: customer_lgbm_v2

PHÂN TÍCH TƯ VẤN
- Khoản vay yêu cầu cao hơn hạn mức hệ thống đề xuất.
- DTI đang ở nhóm rủi ro cao.
- Điểm tín dụng chưa đủ mạnh để hỗ trợ khoản vay lớn.
- Khuyến nghị: giảm số tiền vay, giảm DTI, hoặc nộp lại khi hồ sơ tài chính tốt hơn.

ĐỘ TIN CẬY DỮ LIỆU
- Một số feature bị impute: age_years, ext_source_1, ext_source_3.
- Vì có dữ liệu mặc định, phần giải thích nên dùng ngôn ngữ thận trọng.
```

## 5. Mapping từ ML sang câu trả lời RAG

### 5.1 Risk Low

RAG có thể nói:

- Hồ sơ có rủi ro thấp theo ML.
- Khoản vay có khả năng phù hợp hơn với năng lực tài chính hiện tại.
- Có thể cân nhắc hạn mức/kỳ hạn theo đề xuất hệ thống.
- Vẫn cần Admin xét duyệt cuối cùng.

RAG không được nói:

- "Bạn chắc chắn được duyệt."
- "Ngân hàng sẽ giải ngân."

### 5.2 Risk Medium

RAG có thể nói:

- Hồ sơ ở mức cần xem xét thêm.
- Nên so sánh khoản vay yêu cầu với `recommended_amount`.
- Nếu khoản vay yêu cầu cao hơn đề xuất, nên cân nhắc giảm số tiền hoặc chọn kỳ hạn phù hợp.
- Admin có thể yêu cầu thêm thông tin.

### 5.3 Risk High

RAG có thể nói:

- ML đánh giá rủi ro cao, thường không phù hợp với khoản vay hiện tại.
- Các yếu tố cần cải thiện có thể gồm DTI, credit score, số tiền vay, thu nhập, lịch sử nợ.
- Nên giảm số tiền vay hoặc cải thiện hồ sơ trước khi nộp lại.

RAG không nên đề xuất gói vay lớn hơn hoặc khuyến khích khách vay tiếp khi risk đang cao.

## 6. Nguyên tắc giải thích kết quả ML

RAG nên giải thích theo hướng "yếu tố ảnh hưởng" thay vì khẳng định nhân quả tuyệt đối.

Nên dùng:

- "Các yếu tố có thể làm tăng rủi ro trong hồ sơ của bạn là..."
- "Theo kết quả ML, hồ sơ hiện tại phù hợp hơn với hạn mức..."
- "Nếu thông tin khai báo chưa đầy đủ, kết quả có thể chưa phản ánh toàn bộ tình hình tài chính."

Không nên dùng:

- "Bạn bị từ chối vì đúng một lý do duy nhất là..."
- "Model chắc chắn đúng."
- "Chỉ cần sửa field này là sẽ được duyệt."
- "Tôi có thể thay đổi kết quả xét duyệt cho bạn."

## 7. Những context không nên đưa vào RAG

- Thông tin khách hàng khác.
- Raw database schema hoặc query nội bộ.
- Secret, API key, JWT, connection string.
- Toàn bộ model artifact hoặc tham số nội bộ của model.
- Feature nhạy cảm nếu không có lý do tư vấn rõ ràng.
- Dữ liệu cá nhân định danh như số CCCD, số điện thoại, địa chỉ chi tiết, trừ khi câu hỏi liên quan trực tiếp đến bước xác minh hồ sơ.

## 8. Gợi ý cập nhật context builder sau này

Khi triển khai, có thể mở rộng `backend/rag/context_builder.py` theo thứ tự ưu tiên:

1. Giữ context hiện tại về đơn vay gần nhất.
2. Thêm block `KẾT QUẢ ML` gồm `default_probability`, `risk_level`, `risk_score`, `recommended_amount`, `recommended_term`, `model_version`.
3. Thêm block `PHÂN TÍCH TƯ VẤN` gồm so sánh khoản vay yêu cầu với đề xuất ML, DTI band, credit score band.
4. Thêm block `ĐỘ TIN CẬY DỮ LIỆU` dựa trên `imputed_features`.
5. Nếu có package catalog, thêm block `GÓI VAY CÓ THỂ PHÙ HỢP`.

Không cần embed per-user context vào vector store. Context cá nhân nên được query live theo `user_id` tại request time và inject trực tiếp vào prompt để tránh rò rỉ dữ liệu giữa khách hàng.

## 9. Checklist context tối thiểu

Để RAG tư vấn khoản vay/gói vay ở mức chấp nhận được, cần tối thiểu:

- `loan_amount`
- `term`
- `monthly_income`
- `dti`
- `credit_score`
- `employment_status`
- `is_homeowner`
- `listing_category`
- `default_probability`
- `risk_level`
- `risk_score`
- `recommended_amount`
- `recommended_term`
- `imputed_features`

Nếu thiếu kết quả ML, RAG chỉ nên tư vấn chung theo policy, không nên đưa ra nhận định cá nhân hóa mạnh.

## 10. Câu hỏi cần chốt trước khi triển khai

- Hệ thống có cần tạo package catalog thật không, hay chỉ dùng `recommended_amount` và `recommended_term` từ ML?
- Đơn vị tiền trong UI/backend nên thống nhất là VND hay USD? Hiện policy có ví dụ `$15,000`, còn context builder format là VND.
- Có cho RAG dùng `feature_snapshot` chi tiết không, hay chỉ dùng danh sách feature đã chọn lọc?
- Có cần lưu lại snapshot context đã đưa vào RAG để audit câu trả lời sau này không?
