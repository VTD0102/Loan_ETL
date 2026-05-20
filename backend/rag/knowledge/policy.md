# Chính Sách Xét Duyệt Cho Vay — CreditIntel

> **Phiên bản:** 2026-05-21
> **Đối tượng áp dụng:** Toàn bộ hồ sơ vay nộp qua nền tảng CreditIntel
> **Cơ quan ban hành:** Hội đồng Tín dụng CreditIntel

---

## 1. Giới Thiệu

CreditIntel là nền tảng đánh giá rủi ro tín dụng ứng dụng trí tuệ nhân tạo, giúp người dùng nộp đơn vay vốn cá nhân và nhận kết quả đánh giá minh bạch, nhanh chóng. Hệ thống sử dụng mô hình học máy **LightGBM** (`customer_lgbm_v4_stability`) được huấn luyện trên dữ liệu thực tế (Home Credit Credit Risk Model Stability) để tính toán **xác suất vỡ nợ** P(default) của từng hồ sơ, phân loại mức độ rủi ro và đề xuất hạn mức/kỳ hạn phù hợp. Bên cạnh đó, hệ thống áp dụng **Scorecard Logistic Regression** để xuất điểm tín dụng dạng FICO (thang 300–850).

Quy trình xét duyệt gồm **hai giai đoạn**:
1. **Giai đoạn AI:** Đánh giá tự động dựa trên mô hình ML và bộ quy tắc nghiệp vụ.
2. **Giai đoạn Admin:** Xét duyệt thủ công bởi bộ phận quản trị đối với những hồ sơ vượt qua bước AI.

Mục tiêu của CreditIntel là đảm bảo người vay nhận được mức tín dụng phù hợp với năng lực tài chính, đồng thời giảm thiểu rủi ro cho cả hai bên và tuân thủ các quy định pháp luật hiện hành.

---

## 2. Phạm Vi Khoản Vay

| Tiêu chí | Giá trị |
|----------|---------|
| **Số tiền vay tối thiểu** | $500 |
| **Số tiền vay tối đa** | $150,000 |
| **Kỳ hạn hỗ trợ** | 12, 24, 36, 48, 60 tháng |
| **Loại khoản vay** | Vay cá nhân không thế chấp |
| **Đối tượng** | Khách hàng đủ 18 tuổi, có tài khoản đã xác thực |

Khách hàng có thể nhập số tiền và kỳ hạn theo nhu cầu thực tế trong phạm vi trên. Hệ thống sẽ tự động đánh giá tính khả thi của mỗi cấu hình.

---

## 3. Tiêu Chí Phân Loại Rủi Ro

Mô hình LightGBM phân loại mỗi hồ sơ thành **ba mức rủi ro** dựa trên xác suất vỡ nợ P(default):

| Mức rủi ro | Ngưỡng P(default) | Quy trình | Ý nghĩa |
|-----------|-------------------|-----------|---------|
| **Thấp (Low)** | P(default) < 20% | Chuyển Admin xét duyệt | Hồ sơ tốt, được ưu tiên |
| **Trung bình (Medium)** | 20% ≤ P(default) < 40% | Chuyển Admin xét duyệt | Hồ sơ chấp nhận được, cần xét thêm |
| **Cao (High)** | P(default) ≥ 40% | **Tự động từ chối (AUTO_REJECTED)** | Rủi ro vượt ngưỡng an toàn |

**Lưu ý quan trọng:**
- Ngưỡng 0.4 là **đường ranh cứng** giữa chấp nhận vào quy trình duyệt và từ chối tự động.
- Xác suất vỡ nợ được tính từ **tổ hợp 35 đặc trưng** tài chính – nhân khẩu – tín dụng, không chỉ một chỉ số đơn lẻ.
- Kết quả P(default) **không công khai dưới dạng số chính xác** cho khách hàng; hệ thống chỉ hiển thị mức rủi ro phân loại.

---

## 4. Quy Trình Tự Động Từ Chối (AUTO_REJECTED)

Hệ thống sẽ tự động từ chối hồ sơ trong **hai trường hợp**:

### 4.1 Vượt ngưỡng rủi ro
Khi xác suất vỡ nợ ≥ 40% (mức High), hồ sơ bị từ chối **ngay lập tức** mà không qua Admin. Các nguyên nhân phổ biến:
- Tỷ lệ nợ trên thu nhập (DTI) vượt 43%.
- Điểm tín dụng dưới 580.
- Thu nhập hàng tháng không đủ trả nợ tối thiểu của khoản vay đề nghị.
- Tình trạng việc làm không ổn định (Not employed) hoặc nguồn thu không xác minh được.
- Có nợ xấu (bad debt) hoặc lịch sử nợ quá hạn nghiêm trọng.
- Tổ hợp bất lợi của nhiều yếu tố cùng lúc.

### 4.2 Nằm trong danh sách CIC blacklist
Trước khi chạy mô hình ML, hệ thống truy vấn dữ liệu CIC (Trung tâm Thông tin Tín dụng). Nếu hồ sơ có `blacklist_flag = true`:
- Trạng thái lập tức chuyển sang **AUTO_REJECTED** với `model_version = "CIC_BLACKLIST"`.
- Không chạy mô hình LightGBM, không hiển thị điểm rủi ro chi tiết.
- Khách hàng **không thể nộp lại** hoặc điều chỉnh qua chatbot cho đến khi xử lý xong với CIC.

Khách hàng bị AUTO_REJECTED do vượt ngưỡng (mục 4.1) có thể cải thiện hồ sơ và nộp lại đơn mới, hoặc sử dụng tính năng **Đề xuất phương án thay thế** qua chatbot AI (xem mục 8).

---

## 5. Các Yếu Tố Tài Chính & Mức Ảnh Hưởng

### 5.1 Tỷ Lệ Nợ Trên Thu Nhập (DTI)

| DTI | Phân loại | Tác động |
|-----|-----------|---------|
| < 30% | **Tốt** | Yếu tố tích cực, nâng điểm hồ sơ |
| 30% – 43% | **Cần chú ý** | Trung tính, không ảnh hưởng quyết định nhiều |
| > 43% | **Rủi ro cao** | Yếu tố bất lợi mạnh, có thể dẫn AUTO_REJECTED khi kết hợp các yếu tố khác |

### 5.2 Điểm Tín Dụng (Credit Score)

Thang FICO 300–850, được tính bởi mô hình Scorecard Logistic Regression dựa trên 30 đặc trưng:

| Điểm | Phân loại |
|------|-----------|
| < 580 | Kém |
| 580 – 669 | Trung bình |
| 670 – 739 | Tốt |
| 740 – 799 | Rất tốt |
| ≥ 800 | Xuất sắc |

Điểm tín dụng do hệ thống tự tính từ dữ liệu khai báo và dữ liệu CIC; khách hàng không cần tự nhập.

### 5.3 Thu Nhập Hàng Tháng & Khả Năng Verify
- Thu nhập càng cao càng giảm rủi ro, nhưng **không đảm bảo phê duyệt** nếu DTI hoặc credit score xấu.
- Thu nhập có thể xác minh (`income_verifiable = true`) được tính là yếu tố tích cực bổ sung.
- Thu nhập không xác minh được sẽ bị **chiết khấu** trong mô hình đánh giá.

### 5.4 Tình Trạng Việc Làm
Hệ thống chấp nhận **5 nhóm tình trạng việc làm**:

| Tình trạng | Mức độ rủi ro chung |
|-----------|--------------------|
| `Employed` (Có việc làm toàn thời gian) | Thấp |
| `Self-employed` (Tự kinh doanh) | Trung bình |
| `Retired` (Hưu trí) | Thấp – Trung bình (theo nguồn hưu trí) |
| `Not employed` (Không có việc làm) | Cao |
| `Other/Unknown` (Khác / Không xác định) | Cao |

### 5.5 Tình Trạng Sở Hữu Nhà
Khách hàng sở hữu nhà (`is_homeowner = true`) được đánh giá có tính ổn định cao hơn, là **yếu tố tích cực** trong mô hình.

### 5.6 Trình Độ Học Vấn
Hệ thống mã hóa trình độ học vấn theo thang ordinal 1–5:
1. Tiểu học
2. THCS
3. THPT
4. Cao đẳng / Đại học
5. Sau đại học

### 5.7 Lịch Sử Tín Dụng CIC
Các trường dữ liệu CIC ảnh hưởng đến quyết định gồm:
- Số bản ghi tín dụng đang hoạt động.
- Tổng dư nợ quá hạn.
- Số ngày quá hạn tối đa.
- Cờ nợ xấu (bad debt).
- Cờ CIC blacklist (xem mục 4.2).

### 5.8 Mục Đích Vay & Kỳ Hạn
- **Mục đích vay** (trả nợ, cải thiện nhà ở, mua xe, học tập, kinh doanh, khác) là đầu vào của mô hình. Các mục đích như *Debt Consolidation* và *Home Improvement* thường được đánh giá rủi ro thấp hơn.
- **Kỳ hạn** dài hơn giảm khoản trả hàng tháng (giảm DTI thực tế) nhưng tăng tổng chi phí lãi và rủi ro biến động tài chính dài hạn. Hệ thống cân nhắc cả hai chiều.

---

## 6. Cơ Chế Đề Xuất Hạn Mức Vay

Khác với các nền tảng truyền thống dùng bảng hạn mức cứng, CreditIntel áp dụng **thuật toán binary search động** để tìm hạn mức tối đa khả thi cho từng hồ sơ:

1. Với mỗi kỳ hạn (12, 24, 36, 48, 60 tháng), hệ thống tìm **số tiền vay tối đa** sao cho P(default) < 0.4.
2. Nếu số tiền khách hàng yêu cầu **khả thi** ở ít nhất một kỳ hạn → đề xuất kỳ hạn **ngắn nhất khả thi**.
3. Nếu số tiền yêu cầu **không khả thi** ở mọi kỳ hạn → đề xuất hạn mức cao nhất mà hệ thống đánh giá được duyệt.

**Hệ quả thực tế:**
- Hạn mức đề xuất **không cố định** theo mức rủi ro — mỗi khách hàng có một mức tối đa riêng, phụ thuộc đầy đủ vào hồ sơ tài chính cá nhân.
- Cùng mức Low risk, hai khách hàng có thể nhận đề xuất khác nhau do khác biệt về DTI, thu nhập, lịch sử CIC.
- Khách hàng có thể nhập số tiền **vượt mức đề xuất**, nhưng điều này làm tăng P(default) và có thể dẫn đến AUTO_REJECTED hoặc bị Admin từ chối.

> **Quan trọng:** Đề xuất của hệ thống chỉ là tham khảo. **Quyết định phê duyệt cuối cùng và hạn mức thực tế do Admin quyết định**, có thể khác đề xuất tùy đánh giá tổng thể.

---

## 7. Vòng Đời Trạng Thái Đơn Vay

Hệ thống quản lý đơn vay qua **9 trạng thái** theo máy trạng thái sau:

| Trạng thái | Ý nghĩa | Chuyển từ | Chuyển sang |
|-----------|---------|----------|------------|
| `PENDING` | Hồ sơ vừa khởi tạo, chưa chạy ML | – | `PENDING_REVIEW`, `AUTO_REJECTED` |
| `PENDING_REVIEW` | Đã chạy ML, đang chờ Admin xét duyệt | `PENDING` | `AWAITING_INFO`, `ADMIN_REJECTED`, `REJECTED` |
| `AUTO_REJECTED` | Bị từ chối tự động bởi AI (P ≥ 0.4) hoặc CIC blacklist | `PENDING` | (Cuối) |
| `ADMIN_REJECTED` | Bị Admin từ chối sau xét duyệt | `PENDING_REVIEW` | (Cuối) |
| `REJECTED` | Từ chối chung (tương đương ADMIN_REJECTED ở một số trường hợp) | `PENDING_REVIEW` | (Cuối) |
| `AWAITING_INFO` | Đã được Admin chấp thuận sơ bộ, chờ KH bổ sung thông tin cá nhân | `PENDING_REVIEW` | `INFO_SUBMITTED` |
| `INFO_SUBMITTED` | KH đã nộp đủ thông tin, chờ xử lý cuối | `AWAITING_INFO` | `APPROVED` |
| `APPROVED` | Đã phê duyệt, chuẩn bị giải ngân | `INFO_SUBMITTED` | `DISBURSED` |
| `DISBURSED` | Đã giải ngân thành công | `APPROVED` | (Cuối) |

**Lưu ý:**
- Sau khi đơn được nộp và chạy ML, **không thể chỉnh sửa thông tin tài chính** trong đơn đó. Để thay đổi, KH cần hủy đơn (nếu còn ở `PENDING_REVIEW`) hoặc nộp đơn mới.
- AUTO_REJECTED và ADMIN_REJECTED đều là trạng thái cuối — KH cần nộp đơn mới để thử lại.

---

## 8. Tính Năng Đề Xuất Phương Án Thay Thế (Loan Adjustment State Machine)

Khi đơn của KH bị **AUTO_REJECTED** (do vượt ngưỡng, không phải CIC blacklist), KH có thể yêu cầu chatbot AI đề xuất phương án thay thế.

### 8.1 Cách kích hoạt
Gửi tin nhắn cho chatbot chứa các từ khóa như:
- *"Tại sao tôi bị từ chối?"*
- *"Có phương án nào khác không?"*
- *"Giúp tôi đổi kỳ hạn"*
- *"Đề xuất gói vay phù hợp"*

### 8.2 Cơ chế tìm phương án
Hệ thống chạy ML real-time với các tổ hợp `(số tiền, kỳ hạn)`:
- **Số tiền thử:** Số tiền gốc của KH và số tiền đề xuất từ binary search.
- **Kỳ hạn thử:** Toàn bộ SUPPORTED_TERMS (12, 24, 36, 48, 60 tháng).
- **Điều kiện chấp nhận:** P(default) ≤ 0.4.
- **Xếp hạng ưu tiên:** Số tiền gần nguyên bản nhất → P(default) thấp nhất → kỳ hạn gần kỳ hạn gốc nhất.

### 8.3 Xác nhận & TTL
Sau khi nhận đề xuất, KH có **30 phút** để trả lời:
- **"Đồng ý" / "Xác nhận" / "OK"** → Hệ thống tự động khởi tạo đơn vay mới theo cấu hình đề xuất.
- **"Không" / "Hủy" / "Thôi"** → Hủy đề xuất, giữ nguyên trạng thái AUTO_REJECTED.
- **Im lặng quá 30 phút** → Đề xuất hết hạn, KH cần yêu cầu lại.

### 8.4 Hạn chế
- Không áp dụng cho hồ sơ bị **CIC blacklist**.
- Không áp dụng cho hồ sơ chưa từng bị AUTO_REJECTED.
- Nếu không tồn tại phương án nào đạt P(default) ≤ 0.4, hệ thống thông báo *"Không tìm được phương án phù hợp"* và gợi ý KH cải thiện hồ sơ trước khi nộp lại.

---

## 9. Quy Trình Sau Khi Được Duyệt — Nộp Thông Tin Cá Nhân

Khi đơn vượt qua bước Admin và chuyển sang **AWAITING_INFO**, KH cần đăng nhập vào mục *"Hồ sơ của tôi"* và bổ sung **đầy đủ các trường sau**:

### 9.1 Trường bắt buộc

| Trường | Mô tả |
|--------|-------|
| `full_name` | Họ tên đầy đủ theo CMND/CCCD |
| `id_card_number` | Số CMND hoặc CCCD (duy nhất trong hệ thống) |
| `phone` | Số điện thoại liên hệ |
| `email` | Email hợp lệ |
| `date_of_birth` | Ngày sinh |
| `address` | Địa chỉ thường trú |

### 9.2 Trường khuyến nghị (không bắt buộc)

| Trường | Mô tả |
|--------|-------|
| `bank_account_number` | Số tài khoản ngân hàng để nhận giải ngân |
| `document_urls` | Ảnh chụp CMND/CCCD mặt trước, mặt sau, ảnh selfie cầm CMND |

### 9.3 Sau khi nộp
- Trạng thái chuyển sang **INFO_SUBMITTED**.
- Bộ phận vận hành xử lý và xác minh thông tin trong **1–3 ngày làm việc**.
- Sau khi xác minh thành công → trạng thái chuyển **APPROVED**, sau đó **DISBURSED** khi giải ngân.

---

## 10. Quy Tắc Sử Dụng Trợ Lý AI (Chatbot)

### 10.1 Phạm vi hỗ trợ
Chatbot AI chỉ trả lời các câu hỏi liên quan đến:
- Tình trạng đơn vay cá nhân của KH.
- Giải thích kết quả ML và yếu tố ảnh hưởng.
- Chính sách và quy trình của CreditIntel.
- Tư vấn cải thiện hồ sơ tài chính cá nhân.

Các câu hỏi ngoài phạm vi (thời tiết, chính trị, lập trình, v.v.) sẽ được lịch sự từ chối.

### 10.2 Giới hạn tần suất
- Tối đa **20 tin nhắn / phút** cho mỗi tài khoản.
- Vượt giới hạn → hệ thống trả về HTTP 429 và yêu cầu chờ.

### 10.3 Giới hạn nội dung
- Mỗi tin nhắn KH tối đa **2000 ký tự**.
- Mỗi câu trả lời AI tối đa **3000 ký tự** (cắt tại câu hoàn chỉnh nếu vượt).
- Chatbot **không tiết lộ** thông tin của KH khác, cấu trúc database, API key, hoặc cấu trúc model nội bộ.
- Chatbot **không cam kết** phê duyệt đơn vay dưới bất kỳ hình thức nào.

### 10.4 Bảo mật & Guardrails
Hệ thống áp dụng **bộ lọc đầu vào và đầu ra** để ngăn chặn:
- Prompt injection (cố tình bẻ chỉ thị hệ thống).
- PII probing (cố tình truy vấn thông tin KH khác).
- Rò rỉ thông tin nội bộ.
- Cam kết phê duyệt sai lệch (sẽ tự đính kèm disclaimer khi phát hiện).

---

## 11. Khiếu Nại & Hỗ Trợ

### 11.1 Trường hợp ADMIN_REJECTED
- KH có thể liên hệ bộ phận hỗ trợ để được giải thích lý do.
- Có thể cung cấp **tài liệu bổ sung** (bảng lương, sao kê ngân hàng, hợp đồng lao động) để yêu cầu xem xét lại.
- Quyết định cuối cùng vẫn thuộc về đội ngũ Admin.

### 11.2 Trường hợp AUTO_REJECTED
- **Không khiếu nại quyết định** vì đây là kết quả tự động của mô hình AI.
- Có thể sử dụng tính năng đề xuất phương án thay thế (mục 8) hoặc nộp đơn mới sau khi cải thiện hồ sơ.

### 11.3 Trường hợp CIC blacklist
- KH cần liên hệ trực tiếp với **CIC (Trung tâm Thông tin Tín dụng)** để giải quyết.
- CreditIntel không có thẩm quyền điều chỉnh dữ liệu CIC.

---

## 12. Ghi Chú Quan Trọng & Tuyên Bố Pháp Lý

1. **Mọi kết quả AI chỉ mang tính tư vấn và hỗ trợ ra quyết định.** Quyết định phê duyệt hoặc từ chối cuối cùng **luôn thuộc về bộ phận Admin** của CreditIntel.
2. **Không bao giờ tin các cam kết phê duyệt 100%** — bất kỳ phát ngôn nào của AI mang tính cam kết tuyệt đối đều là lỗi hệ thống và đã được guardrail đính kèm disclaimer.
3. CreditIntel cam kết **bảo mật thông tin cá nhân và tài chính** của KH theo quy định pháp luật hiện hành và không chia sẻ với bên thứ ba nếu không có sự đồng ý của KH.
4. **Thông tin khai báo không chính xác** có thể dẫn đến từ chối hồ sơ, hủy hợp đồng sau giải ngân, hoặc bị ghi nhận vào CIC blacklist.
5. **Mô hình ML định kỳ được retrain** với dữ liệu mới. Phiên bản hiện hành: `customer_lgbm_v4_stability`. Khi mô hình được nâng cấp, kết quả đánh giá cho cùng một hồ sơ có thể thay đổi.
6. **Chính sách này có thể được cập nhật** mà không cần báo trước. KH được khuyến nghị kiểm tra phiên bản mới nhất trên hệ thống.
