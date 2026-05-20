# Câu Hỏi Thường Gặp (FAQ) — CreditIntel

> **Phiên bản:** 2026-05-21
> Các câu hỏi được nhóm theo chủ đề. Mọi nội dung trong FAQ này tuân thủ chính sách trong [policy.md].

---

## A. Mô Hình AI & Cách Đánh Giá

**Q: CreditIntel dùng mô hình AI nào để đánh giá hồ sơ?**
A: Hệ thống sử dụng **LightGBM** (phiên bản nội bộ `customer_lgbm_v4_stability`) để dự đoán xác suất vỡ nợ P(default), và **Logistic Regression Scorecard** để xuất điểm tín dụng dạng FICO (thang 300–850). Hai mô hình này được huấn luyện trên bộ dữ liệu Home Credit Credit Risk Model Stability và được retrain định kỳ.

---

**Q: Sự khác biệt giữa ba mức rủi ro LOW, MEDIUM và HIGH là gì?**
A: **LOW** (P(default) < 20%) — hồ sơ tốt, được ưu tiên chuyển Admin. **MEDIUM** (20% ≤ P(default) < 40%) — hồ sơ chấp nhận được, vẫn chuyển Admin xét duyệt thêm. **HIGH** (P(default) ≥ 40%) — vượt ngưỡng an toàn, **bị từ chối tự động (AUTO_REJECTED)** và không qua Admin.

---

**Q: Hệ thống dựa vào những yếu tố nào để đánh giá rủi ro?**
A: Mô hình kết hợp **35 đặc trưng** bao gồm: số tiền vay, kỳ hạn, mục đích vay, thu nhập, DTI, điểm tín dụng, tình trạng việc làm, sở hữu nhà, trình độ học vấn, dữ liệu CIC (số bản ghi tín dụng, nợ quá hạn, nợ xấu), và nhiều yếu tố khác. Không có yếu tố đơn lẻ nào quyết định kết quả.

---

**Q: Hệ thống có công khai con số P(default) chính xác của tôi không?**
A: Không. Hệ thống chỉ hiển thị **mức rủi ro phân loại** (Low/Medium/High) và **điểm tín dụng FICO**. Con số P(default) chính xác chỉ dùng nội bộ cho mô hình.

---

## B. AUTO_REJECTED & CIC Blacklist

**Q: Tại sao đơn vay của tôi bị AUTO_REJECTED ngay lập tức?**
A: Có **hai nguyên nhân** dẫn đến AUTO_REJECTED:
1. **Vượt ngưỡng rủi ro:** Mô hình AI tính P(default) ≥ 40%, thường do DTI cao, điểm tín dụng thấp, thu nhập không đủ, việc làm không ổn định, hoặc tổ hợp nhiều yếu tố bất lợi.
2. **CIC blacklist:** Hồ sơ có trong danh sách đen của Trung tâm Thông tin Tín dụng (CIC). Trong trường hợp này, hệ thống **không chạy mô hình ML** và đánh dấu `model_version = "CIC_BLACKLIST"`.

---

**Q: CIC blacklist là gì và làm sao biết tôi có nằm trong đó không?**
A: CIC (Trung tâm Thông tin Tín dụng) lưu trữ lịch sử tín dụng quốc gia. Nếu bạn có nợ xấu nghiêm trọng chưa xử lý hoặc bị các tổ chức tín dụng đánh dấu, bạn có thể bị `blacklist_flag = true`. Khi đơn vay bị từ chối với lý do *"CIC blacklist"*, bạn cần **liên hệ trực tiếp với CIC** để giải quyết — CreditIntel không có thẩm quyền điều chỉnh dữ liệu này.

---

**Q: Hệ thống CreditIntel có xem xét lại quyết định AUTO_REJECTED không?**
A: Không. Quyết định AUTO_REJECTED được thực hiện hoàn toàn tự động và không thể khiếu nại. Tuy nhiên, bạn có **hai lựa chọn**:
1. Sử dụng tính năng **đề xuất phương án thay thế** qua chatbot (chỉ áp dụng nếu không bị CIC blacklist).
2. **Cải thiện hồ sơ tài chính** (giảm DTI, tăng credit score, ổn định việc làm) rồi nộp đơn mới.

---

**Q: Tôi có thể nộp đơn vay mới sau khi bị từ chối không?**
A: Có. Bạn có thể nộp đơn mới bất cứ lúc nào sau khi bị AUTO_REJECTED hoặc ADMIN_REJECTED. Tuy nhiên, nếu nộp lại ngay mà không cải thiện hồ sơ, **kết quả thường tương tự**. Chúng tôi khuyến nghị dành thời gian cải thiện DTI, điểm tín dụng, hoặc ổn định thu nhập trước khi nộp lại.

---

## C. Hạn Mức Vay & Cơ Chế Đề Xuất

**Q: Số tiền vay tối thiểu và tối đa CreditIntel cho phép là bao nhiêu?**
A: **Tối thiểu $500**, **tối đa $150,000**. Bạn có thể nhập số tiền theo nhu cầu trong khoảng này. Hệ thống sẽ tự đánh giá tính khả thi.

---

**Q: Kỳ hạn vay nào được hỗ trợ?**
A: CreditIntel hỗ trợ **5 kỳ hạn cố định**: **12, 24, 36, 48, 60 tháng**. Bạn không thể nhập kỳ hạn tùy chỉnh.

---

**Q: Hệ thống đề xuất hạn mức vay dựa trên tiêu chí gì?**
A: Hệ thống dùng **thuật toán binary search động**: với mỗi kỳ hạn (12/24/36/48/60 tháng), tìm số tiền vay tối đa sao cho P(default) < 40%. Sau đó:
- Nếu số tiền bạn yêu cầu khả thi ở ít nhất một kỳ hạn → đề xuất kỳ hạn ngắn nhất khả thi.
- Nếu không khả thi ở bất kỳ kỳ hạn nào → đề xuất hạn mức cao nhất hệ thống đánh giá được duyệt.

**Hạn mức đề xuất không cố định theo mức rủi ro** — mỗi khách hàng có một mức tối đa riêng phụ thuộc đầy đủ vào hồ sơ cá nhân.

---

**Q: Tôi có thể xin vay số tiền nhiều hơn mức hệ thống đề xuất không?**
A: Có thể. Nhưng nếu số tiền yêu cầu vượt mức đề xuất, P(default) sẽ tăng và có thể dẫn đến **AUTO_REJECTED** hoặc bị Admin từ chối. Hãy cân nhắc giữa nhu cầu thực tế và khả năng được duyệt.

---

**Q: Hạn mức thực tế tôi nhận được có giống hạn mức đề xuất không?**
A: Không nhất thiết. Đề xuất chỉ là tham khảo dựa trên mô hình AI. **Quyết định cuối cùng và hạn mức thực tế do Admin xét duyệt** và có thể khác đề xuất tùy đánh giá tổng thể.

---

## D. Các Yếu Tố Tài Chính Cá Nhân

**Q: DTI ở mức nào được xem là an toàn?**
A: **DTI < 30%** được phân loại *Tốt* — yếu tố tích cực. **30% ≤ DTI ≤ 43%** là *Cần chú ý* — trung tính. **DTI > 43%** là *Rủi ro cao* — yếu tố bất lợi mạnh, kết hợp với các chỉ số khác có thể dẫn đến AUTO_REJECTED.

---

**Q: Làm thế nào để giảm tỷ lệ DTI của tôi?**
A: DTI = Tổng nợ phải trả hàng tháng / Thu nhập hàng tháng. Bạn có thể giảm DTI bằng cách:
1. **Trả bớt nợ hiện có** (đặc biệt các khoản có lãi suất cao).
2. **Tăng thu nhập** (thêm việc, đầu tư).
3. **Tránh phát sinh nợ mới** trước khi nộp đơn.

Mục tiêu lý tưởng là đưa DTI xuống **dưới 30%**.

---

**Q: Điểm tín dụng được phân loại như thế nào?**
A: Thang FICO 300–850 được chia 5 mức:
- **< 580:** Kém
- **580 – 669:** Trung bình
- **670 – 739:** Tốt
- **740 – 799:** Rất tốt
- **≥ 800:** Xuất sắc

Điểm dưới 580 thường làm tăng đáng kể rủi ro được hệ thống ghi nhận và có thể dẫn AUTO_REJECTED khi kết hợp với DTI cao.

---

**Q: Điểm tín dụng do tôi tự khai báo hay hệ thống tự tính?**
A: Hệ thống **tự tính** điểm tín dụng dựa trên mô hình Scorecard Logistic Regression (30 đặc trưng), kết hợp dữ liệu khai báo và dữ liệu CIC. Bạn không cần nhập thủ công.

---

**Q: Tại sao thu nhập của tôi khá cao nhưng vẫn bị từ chối?**
A: Thu nhập cao là yếu tố tích cực **nhưng không đủ**. Nếu DTI cao (phần lớn thu nhập đã dùng trả nợ cũ), hoặc điểm tín dụng thấp, hoặc thu nhập không xác minh được, mô hình vẫn có thể đánh giá rủi ro ở mức cao. Mô hình xem xét tổng thể nhiều yếu tố.

---

**Q: Thu nhập có cần xác minh được không?**
A: Không bắt buộc khi nộp đơn, nhưng **thu nhập xác minh được** (`income_verifiable = true`) là yếu tố tích cực. Thu nhập không xác minh sẽ bị **chiết khấu** trong mô hình đánh giá, làm tăng rủi ro tính toán.

---

**Q: Tại sao tình trạng việc làm lại ảnh hưởng đến kết quả xét duyệt?**
A: Việc làm phản ánh tính ổn định nguồn thu để trả nợ. Hệ thống nhận diện **5 nhóm**:
- `Employed` (toàn thời gian) → rủi ro thấp
- `Self-employed` (tự kinh doanh) → rủi ro trung bình
- `Retired` (hưu trí) → thấp đến trung bình
- `Not employed` (không việc làm) → rủi ro cao
- `Other/Unknown` (khác / không xác định) → rủi ro cao

---

**Q: Tôi có nhà riêng thì có lợi thế gì trong xét duyệt không?**
A: Có. Trường `is_homeowner = true` là **tín hiệu tích cực** trong mô hình, phản ánh sự ổn định tài chính cao hơn. Tuy nhiên đây chỉ là một yếu tố trong nhiều yếu tố — không đảm bảo phê duyệt nếu các chỉ số khác xấu.

---

**Q: Mục đích vay có ảnh hưởng đến kết quả xét duyệt không?**
A: Có. Các mục đích như **Debt Consolidation** (trả nợ) và **Home Improvement** (cải thiện nhà ở) thường được đánh giá rủi ro thấp hơn so với vay kinh doanh hoặc mục đích không xác định. Tuy nhiên đây chỉ là một yếu tố trong mô hình tổng thể.

---

**Q: Kỳ hạn vay tôi chọn có ảnh hưởng đến kết quả xét duyệt không?**
A: Có. Kỳ hạn dài hơn có khoản trả hàng tháng thấp hơn (giúp giảm DTI thực tế) nhưng tăng tổng chi phí lãi và rủi ro biến động dài hạn. Kỳ hạn ngắn cho thấy cam kết trả nợ nhanh hơn nhưng làm tăng áp lực dòng tiền. Mô hình cân nhắc cả hai chiều.

---

**Q: Trình độ học vấn ảnh hưởng thế nào?**
A: Hệ thống mã hóa trình độ theo thang ordinal 1–5 (Tiểu học → Sau đại học). Trình độ cao thường tương quan với thu nhập ổn định và rủi ro thấp hơn, nhưng tác động không lớn bằng DTI, điểm tín dụng hay thu nhập.

---

## E. Tính Năng Đề Xuất Phương Án Thay Thế (Chatbot)

**Q: Sau khi bị AUTO_REJECTED, tôi có thể nhờ chatbot đề xuất phương án khác không?**
A: Có. Bạn có thể nhắn chatbot AI với các từ khóa như *"Có phương án nào khác không?"*, *"Giúp tôi đổi kỳ hạn"*, hoặc *"Đề xuất gói vay phù hợp"*. Hệ thống sẽ chạy ML real-time để tìm cấu hình `(số tiền, kỳ hạn)` có P(default) ≤ 0.4.

**Lưu ý:** Tính năng này **không áp dụng** cho hồ sơ bị CIC blacklist.

---

**Q: Sau khi nhận đề xuất, tôi có bao lâu để xác nhận?**
A: **30 phút**. Trong khoảng thời gian này:
- Trả lời *"Đồng ý" / "Xác nhận" / "OK"* → hệ thống tự động khởi tạo đơn vay mới theo cấu hình đề xuất.
- Trả lời *"Không" / "Hủy" / "Thôi"* → hủy đề xuất.
- Im lặng quá 30 phút → đề xuất hết hạn, bạn cần yêu cầu lại.

---

**Q: Nếu hệ thống không tìm được phương án phù hợp thì sao?**
A: Trong trường hợp này, chatbot sẽ thông báo *"Không tìm được phương án phù hợp"* — nghĩa là không có tổ hợp `(số tiền, kỳ hạn)` nào đạt P(default) ≤ 0.4 với hồ sơ hiện tại. Bạn cần cải thiện các chỉ số tài chính cá nhân trước khi nộp lại.

---

## F. Vòng Đời Trạng Thái Đơn Vay

**Q: Đơn vay của tôi có thể có những trạng thái nào?**
A: Hệ thống quản lý 9 trạng thái:
1. `PENDING` — vừa khởi tạo, chưa chạy ML.
2. `PENDING_REVIEW` — đã chạy ML, chờ Admin xét duyệt.
3. `AUTO_REJECTED` — bị AI từ chối tự động (cuối).
4. `ADMIN_REJECTED` — bị Admin từ chối (cuối).
5. `REJECTED` — từ chối chung (cuối).
6. `AWAITING_INFO` — Admin chấp thuận sơ bộ, chờ bổ sung thông tin.
7. `INFO_SUBMITTED` — đã nộp thông tin cá nhân, chờ xử lý cuối.
8. `APPROVED` — đã phê duyệt, chuẩn bị giải ngân.
9. `DISBURSED` — đã giải ngân thành công (cuối).

---

**Q: Sự khác biệt giữa AUTO_REJECTED và ADMIN_REJECTED là gì?**
A: **AUTO_REJECTED** là kết quả tự động của AI (P(default) ≥ 0.4 hoặc CIC blacklist) — **không qua Admin và không thể khiếu nại**. **ADMIN_REJECTED** là quyết định thủ công của Admin sau khi xem hồ sơ ở trạng thái PENDING_REVIEW — **có thể khiếu nại** bằng cách cung cấp tài liệu bổ sung.

---

**Q: Sau khi nộp đơn, bao lâu thì Admin xét duyệt?**
A: Thông thường **1 đến 3 ngày làm việc** sau khi đơn có trạng thái `PENDING_REVIEW`. Thời gian có thể dài hơn nếu cần xác minh thêm hoặc khối lượng hồ sơ tăng cao. Bạn sẽ nhận thông báo khi trạng thái thay đổi.

---

**Q: Tôi có thể cập nhật thông tin trong đơn sau khi đã nộp không?**
A: **Không.** Sau khi đơn vay đã nộp và hệ thống đã chạy ML, bạn không thể chỉnh sửa thông tin tài chính. Để thay đổi số tiền, kỳ hạn hoặc thông tin khác, bạn cần:
1. Hủy đơn hiện tại (nếu còn ở `PENDING_REVIEW`), hoặc
2. Nộp đơn mới với thông tin chính xác hơn.

Hãy kiểm tra kỹ thông tin trước khi xác nhận nộp.

---

## G. Bổ Sung Thông Tin Cá Nhân (AWAITING_INFO)

**Q: Sau khi được chuyển sang trạng thái AWAITING_INFO, tôi cần làm gì?**
A: Đăng nhập vào CreditIntel, vào *"Hồ sơ của tôi"* và bổ sung **6 trường bắt buộc**:
- `full_name` — Họ tên đầy đủ theo CMND/CCCD
- `id_card_number` — Số CMND hoặc CCCD
- `phone` — Số điện thoại liên hệ
- `email` — Email hợp lệ
- `date_of_birth` — Ngày sinh
- `address` — Địa chỉ thường trú

Khuyến nghị (không bắt buộc): `bank_account_number` (số tài khoản nhận giải ngân) và `document_urls` (ảnh CMND/CCCD và selfie cầm CMND).

Sau khi nộp, trạng thái chuyển sang `INFO_SUBMITTED` và hồ sơ được xử lý trong 1–3 ngày làm việc.

---

**Q: Tôi có thể nộp thông tin bằng CMND cũ (9 số) không?**
A: Có. Hệ thống chấp nhận cả CMND (9 số) và CCCD (12 số). Tuy nhiên số `id_card_number` phải **duy nhất trong hệ thống** — nếu trùng với tài khoản khác, bạn cần liên hệ hỗ trợ.

---

**Q: Sau khi đơn ở trạng thái APPROVED, bao lâu thì được giải ngân?**
A: Sau khi đơn chuyển `APPROVED`, bộ phận vận hành sẽ giải ngân vào tài khoản ngân hàng đã đăng ký. Trạng thái sẽ chuyển sang `DISBURSED` khi giao dịch hoàn tất.

---

## H. Sử Dụng Trợ Lý AI (Chatbot)

**Q: Chatbot AI của CreditIntel có thể trả lời những gì?**
A: Chatbot trả lời các câu hỏi về:
- Tình trạng đơn vay cá nhân của bạn.
- Giải thích kết quả ML và yếu tố ảnh hưởng (DTI, credit score, etc.).
- Chính sách và quy trình của CreditIntel.
- Tư vấn cải thiện hồ sơ tài chính.
- Đề xuất phương án thay thế khi bị AUTO_REJECTED.

Các câu hỏi ngoài phạm vi (thời tiết, chính trị, lập trình...) sẽ bị lịch sự từ chối.

---

**Q: Có giới hạn tần suất nhắn tin với chatbot không?**
A: Có. Mỗi tài khoản gửi **tối đa 20 tin nhắn / phút**. Vượt giới hạn → hệ thống trả về HTTP 429 và yêu cầu chờ 1 phút trước khi gửi tiếp.

---

**Q: Mỗi tin nhắn có giới hạn độ dài không?**
A: Có. Tin nhắn của bạn **tối đa 2000 ký tự**. Câu trả lời của AI **tối đa 3000 ký tự** (nếu dài hơn sẽ được cắt tại câu hoàn chỉnh cuối cùng).

---

**Q: Chatbot có thể tiết lộ thông tin của khách hàng khác không?**
A: **Tuyệt đối không.** Hệ thống có bộ lọc đầu vào (input guardrail) phát hiện các yêu cầu cố ý truy vấn thông tin người khác và sẽ từ chối ngay lập tức. Tương tự, đầu ra cũng được kiểm tra để ngăn rò rỉ tên bảng database, API key, hoặc cấu trúc model.

---

**Q: Chatbot có thể đảm bảo tôi sẽ được duyệt không?**
A: **Không bao giờ.** Bất kỳ phát ngôn nào của AI mang tính cam kết tuyệt đối (*"chắc chắn được duyệt"*, *"100% được duyệt"*) đều là lỗi và sẽ được hệ thống tự động đính kèm disclaimer. **Quyết định phê duyệt cuối cùng luôn thuộc về Admin.**

---

## I. Bảo Mật & Pháp Lý

**Q: Thông tin cá nhân và tài chính của tôi có được bảo mật không?**
A: CreditIntel cam kết bảo vệ toàn bộ thông tin theo các tiêu chuẩn bảo mật dữ liệu hiện hành. Dữ liệu của bạn chỉ được sử dụng cho mục đích đánh giá tín dụng và xử lý hồ sơ vay, **không chia sẻ với bên thứ ba** nếu không có sự đồng ý của bạn.

---

**Q: Nếu Admin từ chối hồ sơ của tôi (ADMIN_REJECTED), tôi có thể khiếu nại không?**
A: Có. Bạn có thể liên hệ bộ phận hỗ trợ của CreditIntel để được giải thích lý do từ chối. Trong một số trường hợp, bạn có thể cung cấp **tài liệu bổ sung** (bảng lương, sao kê ngân hàng, hợp đồng lao động) để đề nghị xem xét lại. Tuy nhiên, quyết định cuối cùng vẫn thuộc về đội ngũ Admin.

---

**Q: Nếu tôi khai báo sai thông tin thì sao?**
A: Thông tin khai báo không chính xác có thể dẫn đến:
1. **Từ chối hồ sơ** ngay tại bước đánh giá.
2. **Hủy hợp đồng** sau khi đã giải ngân (kèm yêu cầu hoàn trả toàn bộ).
3. Trường hợp nghiêm trọng: **bị ghi nhận vào CIC blacklist**, ảnh hưởng dài hạn đến khả năng vay vốn tại mọi tổ chức tín dụng trong tương lai.

Hãy luôn khai báo trung thực.

---

**Q: Khi mô hình AI được nâng cấp, kết quả đánh giá cũ có còn giá trị không?**
A: Mô hình được retrain định kỳ. Phiên bản hiện hành: `customer_lgbm_v4_stability`. Khi nâng cấp, kết quả đánh giá cho cùng một hồ sơ **có thể thay đổi**. Mỗi đơn vay được đánh dấu phiên bản model tại thời điểm xét duyệt — kết quả cũ vẫn được lưu nguyên trạng cho mục đích kiểm toán.
