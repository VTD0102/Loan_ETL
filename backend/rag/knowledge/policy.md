# Chính Sách Xét Duyệt Cho Vay — CreditIntel

## 1. Giới Thiệu

CreditIntel là nền tảng đánh giá rủi ro tín dụng ứng dụng trí tuệ nhân tạo, giúp người dùng nộp đơn vay vốn và nhận kết quả đánh giá minh bạch, nhanh chóng. Hệ thống sử dụng mô hình học máy (Random Forest) được huấn luyện trên dữ liệu thực tế để tính toán xác suất vỡ nợ (P(default)) của từng hồ sơ, từ đó phân loại mức độ rủi ro và đề xuất hạn mức phù hợp.

Quy trình xét duyệt gồm hai giai đoạn: đánh giá tự động bởi hệ thống AI và xét duyệt thủ công bởi bộ phận quản trị (Admin). Mục tiêu của CreditIntel là đảm bảo người vay nhận được mức tín dụng phù hợp với năng lực tài chính, đồng thời giảm thiểu rủi ro cho cả hai bên.

---

## 2. Tiêu Chí Đánh Giá Rủi Ro

Hệ thống AI của CreditIntel phân loại mỗi hồ sơ vay thành ba mức rủi ro dựa trên xác suất vỡ nợ P(default):

| Mức rủi ro | Ngưỡng P(default) | Ý nghĩa |
|---|---|---|
| **Thấp (Low)** | P(default) < 20% | Hồ sơ tốt, rủi ro thấp, được ưu tiên xét duyệt |
| **Trung bình (Medium)** | 20% ≤ P(default) ≤ 40% | Hồ sơ chấp nhận được, cần xét duyệt thêm |
| **Cao (High)** | P(default) > 40% | Rủi ro quá cao, bị từ chối tự động |

Xác suất vỡ nợ được tính dựa trên tổng hợp nhiều yếu tố tài chính của người vay, không phải chỉ một chỉ số duy nhất.

---

## 3. Quy Trình Tự Động Từ Chối (AUTO_REJECTED)

Khi xác suất vỡ nợ vượt quá 40%, hệ thống sẽ **tự động từ chối hồ sơ ngay lập tức** mà không cần qua bước xét duyệt của Admin. Quyết định này dựa trên đánh giá rằng mức rủi ro vượt ngưỡng an toàn cho phép.

Các lý do phổ biến dẫn đến AUTO_REJECTED bao gồm:
- Tỷ lệ nợ trên thu nhập (DTI) quá cao, cho thấy gánh nặng tài chính hiện tại đã vượt khả năng chi trả.
- Điểm tín dụng thấp, phản ánh lịch sử tín dụng không tốt.
- Thu nhập hàng tháng không đủ so với số tiền vay và kỳ hạn đề nghị.
- Tình trạng việc làm không ổn định (ví dụ: không có việc làm).
- Sự kết hợp bất lợi của nhiều yếu tố rủi ro cùng lúc.

Khách hàng bị AUTO_REJECTED có thể cải thiện hồ sơ và nộp lại đơn sau khi tình hình tài chính được cải thiện.

---

## 4. Vai Trò Của Các Yếu Tố Tài Chính

### 4.1 Tỷ Lệ Nợ Trên Thu Nhập (DTI)
DTI phản ánh tỷ lệ thu nhập hàng tháng đang dùng để trả nợ hiện có. DTI an toàn thường dưới 35%. DTI trên 43% được xem là ngưỡng rủi ro cao; trên mức này, người vay có thể gặp khó khăn trong việc trả thêm khoản nợ mới.

### 4.2 Điểm Tín Dụng (Credit Score)
Điểm tín dụng (300–850) phản ánh lịch sử vay và trả nợ của người vay. Điểm càng cao, rủi ro vỡ nợ càng thấp. Hệ thống sử dụng điểm tín dụng do khách hàng tự khai báo; sai lệch so với thực tế có thể ảnh hưởng đến kết quả.

### 4.3 Thu Nhập Hàng Tháng
Thu nhập ảnh hưởng trực tiếp đến năng lực trả nợ. Tuy nhiên, thu nhập cao không đảm bảo hồ sơ được chấp thuận nếu các yếu tố khác như DTI hoặc điểm tín dụng ở mức xấu.

### 4.4 Tình Trạng Sở Hữu Nhà
Người sở hữu nhà thường được đánh giá có mức độ ổn định tài chính cao hơn, giúp cải thiện điểm đánh giá rủi ro.

### 4.5 Mục Đích Vay và Kỳ Hạn
Mục đích vay (ví dụ: trả nợ, mua xe, học tập) và kỳ hạn vay (12, 36, hoặc 60 tháng) đều được xem xét trong mô hình đánh giá rủi ro tổng thể.

---

## 5. Đề Xuất Hạn Mức Vay Theo Mức Rủi Ro

Dựa trên kết quả phân loại rủi ro, hệ thống đề xuất hạn mức vay tối đa như sau:

| Mức rủi ro | Hạn mức đề xuất | Kỳ hạn đề xuất |
|---|---|---|
| **Thấp (Low)** | Tối đa $15,000 | 36 tháng |
| **Trung bình (Medium)** | Tối đa $8,000 | 24 tháng |
| **Cao (High)** | Không được duyệt | — |

Đây là đề xuất của hệ thống dựa trên mô hình AI. Quyết định phê duyệt cuối cùng và hạn mức thực tế do **Admin xem xét và quyết định**, có thể khác so với đề xuất tùy theo đánh giá tổng thể.

---

## 6. Quy Trình Sau Khi Được Duyệt — Nộp Thông Tin Cá Nhân

Khi hồ sơ vượt qua bước xét duyệt của Admin, trạng thái sẽ chuyển sang **AWAITING_INFO**. Lúc này, khách hàng cần:

1. Đăng nhập vào hệ thống CreditIntel.
2. Truy cập mục "Hồ sơ của tôi" và chọn đơn vay tương ứng.
3. Tải lên các tài liệu xác minh danh tính: CMND/CCCD và số điện thoại liên lạc.
4. Xác nhận nộp thông tin.

Sau khi nộp thành công, trạng thái chuyển sang **INFO_SUBMITTED** và hồ sơ sẽ được xử lý để hoàn tất giải ngân.

---

## 7. Ghi Chú Quan Trọng

- Mọi kết quả AI chỉ mang tính tư vấn và hỗ trợ ra quyết định.
- **Quyết định phê duyệt hoặc từ chối cuối cùng luôn thuộc về bộ phận Admin** của CreditIntel.
- CreditIntel cam kết bảo mật thông tin cá nhân và tài chính của khách hàng theo quy định pháp luật hiện hành.
- Thông tin khai báo không chính xác có thể dẫn đến từ chối hồ sơ hoặc hủy hợp đồng sau khi giải ngân.
