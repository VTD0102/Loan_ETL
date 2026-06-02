# Hướng Dẫn Kỹ Thuật: Phương Pháp Tính Điểm Credit Scorecard (LR Scorecard v2)

Tài liệu này cung cấp chi tiết toàn diện và chuyên sâu nhất về mặt toán học, thuật toán, đặc trưng đầu vào, và cơ chế tính toán điểm tín dụng FICO của mô hình **Credit Scorecard v2** sử dụng trong hệ thống **CreditIntel**. 

---

## 1. Giới Thiệu Chung Về Credit Scorecard

Trong quản trị rủi ro tín dụng, mô hình học máy (như LightGBM hay XGBoost) dự báo ra xác suất mặc định nợ (Probability of Default - PD), tức là khả năng khách hàng không hoàn trả khoản vay ($p \in [0, 1]$). Tuy nhiên, đối với người dùng cuối (khách hàng) và nhân viên phê duyệt tín dụng, con số xác suất thập phân này rất khó hiểu và thiếu tính trực quan.

**Credit Scorecard** là công cụ chuyển đổi xác suất vỡ nợ $p$ thành một điểm số tín dụng nằm trong dải điểm chuẩn hóa từ $300$ đến $850$ (chuẩn FICO). Điểm số này có các đặc tính ưu việt:
* **Tính trực quan**: Điểm càng cao biểu thị khách hàng càng an toàn (rủi ro càng thấp). Điểm càng thấp biểu thị rủi ro càng cao.
* **Tính dễ giải thích (Explainability)**: Có khả năng phân rã điểm số cuối cùng thành các điểm cộng/trừ chi tiết cho từng thuộc tính của khách hàng (ví dụ: cộng điểm nhờ thâm niên làm việc cao, trừ điểm do lịch sử trễ hạn).
* **Đồng bộ hóa quốc tế**: Sử dụng phương pháp **FICO PDO (Points to Double the Odds)** tiêu chuẩn được thừa nhận rộng rãi bởi các định chế tài chính toàn cầu.

---

## 2. Cơ Sở Toán Học Của Mô Hiện Tại (Logistic Regression)

Thuật toán hồi quy Logistic là nền tảng của Credit Scorecard truyền thống nhờ tính chất tuyến tính của nó đối với Log-Odds.

### 2.1. Hàm Sigmoid và Xác Suất Mặc Định Nợ
Xác suất mặc định nợ $p = P(\text{default})$ của khách hàng được mô hình hóa bằng hàm Sigmoid:
$$p = \sigma(\text{logit}) = \frac{1}{1 + e^{-\text{logit}}}$$

Trong đó, $\text{logit}$ (còn gọi là Log-Odds vỡ nợ) là một tổ hợp tuyến tính của các đặc trưng đầu vào:
$$\text{logit} = \ln\left(\frac{p}{1 - p}\right) = \beta_0 + \beta_1 z_1 + \beta_2 z_2 + \dots + \beta_M z_M$$

* $\beta_0$: Hệ số tự do (Intercept) của mô hình.
* $\beta_i$: Hệ số hồi quy (Coefficient) ứng với đặc trưng thứ $i$.
* $z_i$: Giá trị đã qua tiền xử lý (chuẩn hóa StandardScaler hoặc mã hóa OrdinalEncoder) của đặc trưng thứ $i$.

### 2.2. Khái Niệm Odds và Log-Odds Tốt
Trong hồi quy Logistic Scorecard, chúng ta định nghĩa **Odds of Good** (Tỷ lệ thắng của khách hàng tốt) đại diện cho tỷ số giữa khả năng khách hàng không mặc định nợ (Good) và mặc định nợ (Bad):
$$\text{Odds}_{\text{good}} = \frac{P(\text{Good})}{P(\text{Bad})} = \frac{1 - p}{p}$$

Lấy logarit tự nhiên hai vế, ta được **Log-Odds tốt**:
$$\ln(\text{Odds}_{\text{good}}) = \ln\left(\frac{1 - p}{p}\right) = -\ln\left(\frac{p}{1 - p}\right) = -\text{logit}$$

Từ mối liên hệ này, ta thấy Log-Odds tốt tỉ lệ nghịch hoàn hảo với logit mặc định nợ của mô hình.

---

## 3. Hệ Thức Định Tỉ Lệ FICO (FICO Scaling Methodology)

Công thức FICO quy định điểm số tín dụng tỷ lệ thuận với logarit tự nhiên của tỷ số Odds tốt thông qua một quan hệ tuyến tính:
$$\text{Score} = \text{Offset} + \text{Factor} \times \ln(\text{Odds}_{\text{good}})$$

Thay thế $\ln(\text{Odds}_{\text{good}}) = -\text{logit}$, ta thu được công thức tính điểm từ logit:
$$\text{Score} = \text{Offset} - \text{Factor} \times \text{logit}$$

Để xác định hai hằng số định tỉ lệ $\text{Factor}$ và $\text{Offset}$, hệ thống thiết lập hai điều kiện biên chuẩn hóa quốc tế:
1. **Base Score ($S_0$)**: Điểm tín dụng tại tỷ lệ Odds tốt cơ sở ($\text{Odds}_0$). Trong hệ thống, ta chọn $\text{Base\_Score} = 600$ tại tỷ lệ $\text{Base\_Odds} = 50:1$ (tức là cứ 50 khách hàng tốt thì mới có 1 khách hàng vỡ nợ, tương đương xác suất vỡ nợ $p_0 = \frac{1}{51} \approx 1.96\%$).
2. **PDO (Points to Double the Odds)**: Lượng điểm tăng thêm khi tỷ lệ Odds tốt tăng gấp đôi (ví dụ Odds tăng từ 50 thành 100). Trong hệ thống, ta chọn $\text{PDO} = 20$.

### 3.1. Thiết Lập Hệ Phương Trình
Từ hai điều kiện trên, ta có hệ phương trình:
$$(1) \quad S_0 = \text{Offset} + \text{Factor} \times \ln(\text{Odds}_0)$$
$$(2) \quad S_0 + \text{PDO} = \text{Offset} + \text{Factor} \times \ln(2 \times \text{Odds}_0)$$

### 3.2. Giải Tìm Hệ Số Factor
Trừ phương trình $(2)$ cho $(1)$, ta loại bỏ được $\text{Offset}$:
$$\text{PDO} = \text{Factor} \times \left( \ln(2 \times \text{Odds}_0) - \ln(\text{Odds}_0) \right)$$
$$\text{PDO} = \text{Factor} \times \ln\left(\frac{2 \times \text{Odds}_0}{\text{Odds}_0}\right)$$
$$\text{PDO} = \text{Factor} \times \ln(2)$$

Từ đó, hệ số chuyển đổi $\text{Factor}$ được xác định bằng công thức:
$$\text{Factor} = \frac{\text{PDO}}{\ln(2)}$$

Với $\text{PDO} = 20$:
$$\text{Factor} = \frac{20}{\ln(2)} \approx 28.85390081777927$$

### 3.3. Giải Tìm Hằng Số Offset
Thay hệ số $\text{Factor}$ ngược lại vào phương trình $(1)$:
$$\text{Offset} = S_0 - \text{Factor} \times \ln(\text{Odds}_0)$$

Với $S_0 = 600$ và $\text{Odds}_0 = 50$:
$$\text{Offset} = 600 - 28.8539 \times \ln(50) \approx 600 - 28.8539 \times 3.912023 \approx 487.12285141018974$$

### 3.4. Công Thức Quy Đổi FICO Chuẩn Hóa
Định nghĩa hằng số logit cơ sở: $\text{Base\_Logit} = -\ln(\text{Base\_Odds\_Good}) = -\ln(50) \approx -3.912023005428146$.

Thay thế $\text{Offset} = \text{Base\_Score} + \text{Factor} \times \text{Base\_Logit}$ vào công thức quy đổi điểm:
$$\text{Score} = \text{Base\_Score} - \text{Factor} \times (\text{logit} - \text{Base\_Logit})$$

Sau khi tính toán, điểm số sẽ được làm tròn về số nguyên gần nhất và giới hạn cứng trong dải điểm FICO chuẩn $[300, 850]$:
$$\text{FICO\_Score} = \max\left(300, \min\left(850, \text{Round}(\text{Score})\right)\right)$$

---

## 4. Công Thức Phân Rã Điểm Số Chi Tiết (Points Breakdown Logic)

Một đặc trưng quan trọng của Scorecard là khả năng phân rã điểm số cuối cùng thành tổng điểm của từng thuộc tính. 

Thế phương trình tuyến tính logit $\text{logit} = \beta_0 + \sum_{i=1}^{M} \beta_i z_i$ vào công thức tính điểm FICO:
$$\text{Score} = \text{Base\_Score} - \text{Factor} \times \left( \beta_0 + \sum_{i=1}^{M} \beta_i z_i - \text{Base\_Logit} \right)$$
$$\text{Score} = \underbrace{\text{Base\_Score} - \text{Factor} \times (\beta_0 - \text{Base\_Logit})}_{\text{Base Points (Điểm Cơ Sở)}} + \sum_{i=1}^{M} \underbrace{(-\text{Factor} \times \beta_i \times z_i)}_{\text{Points of Feature } i \text{ (Điểm Đặc Trưng i)}}$$

### 4.1. Điểm Cơ Sở Của Mô Hình (Model Base Points)
Điểm cơ sở là điểm số khách hàng nhận được khi tất cả các đặc trưng đầu vào đã chuẩn hóa bằng $0$ ($z_i = 0$, tương đương với việc các đặc trưng đều bằng giá trị trung bình/trung vị của tập huấn luyện):
$$\text{Base\_Points} = \text{Base\_Score} - \text{Factor} \times (\beta_0 - \text{Base\_Logit})$$

### 4.2. Điểm Đóng Góp Cho Đặc Trưng Chuẩn Hóa
Với mỗi đặc trưng thứ $i$, lượng điểm cộng hoặc trừ phụ thuộc trực tiếp vào giá trị chuẩn hóa $z_i$:
$$\text{Points}_i = -\text{Factor} \times \beta_i \times z_i$$

Lượng điểm thay đổi khi đặc trưng chuẩn hóa $z_i$ tăng thêm 1 độ lệch chuẩn ($\Delta z_i = +1$) được định nghĩa là:
$$\text{Points\_per\_Std\_Dev}_i = -\text{Factor} \times \beta_i$$

### 4.3. Quy Đổi Trực Tiếp Từ Giá Trị Thô (Raw Values to Points)
Đối với đặc trưng số thô $x_i$, quá trình chuẩn hóa StandardScaler được thực hiện bằng cách trừ đi giá trị trung bình $\mu_i$ và chia cho độ lệch chuẩn $\sigma_i$:
$$z_i = \frac{x_i - \mu_i}{\sigma_i}$$

Thay thế $z_i$ vào công thức tính điểm thành phần:
$$\text{Points}_i = -\text{Factor} \times \beta_i \times \frac{x_i - \mu_i}{\sigma_i}$$
$$\text{Points}_i = \underbrace{\left( \frac{-\text{Factor} \times \beta_i}{\sigma_i} \right)}_{\text{Points per Unit (Điểm trên 1 đơn vị thô)}} \times x_i + \underbrace{\left( \frac{\text{Factor} \times \beta_i \times \mu_i}{\sigma_i} \right)}_{\text{Constant shift}}$$

Công thức này cho phép hệ thống lập bảng tra điểm trực tiếp (Points Table) từ giá trị thô của khách hàng mà không cần thực hiện bước chuẩn hóa trung gian trong quá trình hiển thị giao diện.

---

## 5. Bảng Tham Số Đặc Trưng & Hệ Số Mô Hình Thực Tế (v2 Stability)

Mô hình **Scorecard v2 Stability** hiện tại sử dụng **30 đặc trưng** an toàn, khách quan từ bảng `gold.hc_features_v2` (loại bỏ hoàn toàn biến tự khai `credit_score_midpoint`). Dưới đây là bảng thông số hệ số hồi quy $\beta_i$ và điểm đóng góp trên mỗi độ lệch chuẩn ($\text{Points/Std}$) thu được từ tệp artifact thực tế [scorecard_model.pkl](file:///D:/GIT%20REPO/loan-etl/Loan_ETL/machinelearning/ml/models/scorecard_model.pkl):

* **Intercept ($\beta_0$)**: `-2.6539`
* **Base Logit ($\text{Base\_Logit}$)**: `-3.9120`
* **Base Points**: $600 - 28.8539 \times (-2.6539 - (-3.9120)) \approx 600 - 28.8539 \times 1.2581 \approx 563.70$ điểm.

### Bảng Hệ Số Và Điểm Đóng Góp Chi Tiết
| STT | Mã Đặc Trưng | Hệ số ($\beta_i$) | Điểm / Std | Chiều Ảnh Hưởng | Ý Nghĩa Biến Số |
| :---: | :--- | :---: | :---: | :---: | :--- |
| **1** | `num_bureau_records` | -0.2843 | **+8.20** | Cộng điểm | Tổng số lượng hồ sơ tín dụng lịch sử tại Bureau (Càng nhiều càng uy tín). |
| **2** | `age_years` | -0.2543 | **+7.34** | Cộng điểm | Tuổi thực tế của khách hàng (Lớn tuổi ít rủi ro hơn). |
| **3** | `is_homeowner_flag` | -0.0845 | **+2.44** | Cộng điểm | Cờ sở hữu nhà riêng (Có nhà riêng giảm rủi ro). |
| **4** | `years_employed` | -0.0764 | **+2.20** | Cộng điểm | Số năm làm việc tại cơ quan hiện tại (Thâm niên cao càng tốt). |
| **5** | `education_ordinal` | -0.0755 | **+2.18** | Cộng điểm | Trình độ học vấn được mã hóa thứ tự 1-5 (Học vấn cao giảm rủi ro). |
| **6** | `loan_amount_to_income` | -0.0744 | **+2.15** | Cộng điểm | Tỷ lệ số tiền vay trên thu nhập năm (Tỷ lệ thấp là tốt). |
| **7** | `occupation_type` | -0.0307 | **+0.89** | Cộng điểm | Nhóm ngành nghề/công việc của khách hàng. |
| **8** | `is_married_flag` | -0.0114 | **+0.33** | Cộng điểm | Tình trạng hôn nhân (Đã kết hôn có xu hướng ổn định hơn). |
| **9** | `total_overdue_amount` | -0.0076 | **+0.22** | Cộng điểm | Tổng số tiền nợ quá hạn ghi nhận tại liên ngân hàng. |
| **10** | `income_missing_flag` | 0.0000 | **-0.00** | Không đổi | Cờ báo khuyết thiếu thu nhập đầu vào. |
| **11** | `dti_missing_flag` | 0.0000 | **-0.00** | Không đổi | Cờ báo khuyết thiếu tỷ lệ nợ DTI đầu vào. |
| **12** | `total_debt_to_income` | 0.0022 | **-0.06** | Trừ điểm | Tổng dư nợ hiện tại chia cho thu nhập tháng. |
| **13** | `employment_status_grouped` | 0.0077 | **-0.22** | Trừ điểm | Nhóm trạng thái việc làm. |
| **14** | `log_monthly_income` | 0.0118 | **-0.34** | Trừ điểm | Log tự nhiên của thu nhập tháng ($LN(1 + \text{monthly\_income})$). |
| **15** | `total_prolongations` | 0.0138 | **-0.40** | Trừ điểm | Tổng số lần khách hàng đã gia hạn nợ quá hạn. |
| **16** | `avg_dpd_recent` | 0.0214 | **-0.62** | Trừ điểm | Số ngày quá hạn trung bình trong các kỳ thanh toán gần nhất. |
| **17** | `debt_to_income_ratio` | 0.0250 | **-0.72** | Trừ điểm | Tỷ lệ nợ trên thu nhập định kỳ hàng tháng (DTI). |
| **18** | `payment_to_income` | 0.0250 | **-0.72** | Trừ điểm | Số tiền thanh toán định kỳ chia cho thu nhập tháng. |
| **19** | `max_credit_overdue_days` | 0.0386 | **-1.11** | Trừ điểm | Số ngày nợ quá hạn lớn nhất trên báo cáo liên ngân hàng. |
| **20** | `num_active_credit` | 0.0418 | **-1.21** | Trừ điểm | Số lượng tài khoản tín dụng đang hoạt động (Vay nhiều nơi). |
| **21** | `num_previous_loans` | 0.0512 | **-1.48** | Trừ điểm | Số lượng khoản vay cũ đã từng đăng ký tại hệ thống. |
| **22** | `current_debt_ratio` | 0.0601 | **-1.73** | Trừ điểm | Tỷ lệ dư nợ hiện tại trên hạn mức được cấp. |
| **23** | `max_dpd_24m` | 0.0681 | **-1.96** | Trừ điểm | Số ngày quá hạn lớn nhất trong vòng 24 tháng qua. |
| **24** | `num_cb_queries` | 0.1007 | **-2.90** | Trừ điểm | Tổng số lần các tổ chức tài chính truy vấn thông tin CIC. |
| **25** | `cb_queries_30d` | 0.1278 | **-3.69** | Trừ điểm | Số lần truy vấn thông tin CIC trong 30 ngày qua (Credit Hunger). |
| **26** | `high_dti_flag` | 0.1639 | **-4.73** | Trừ điểm | Cờ cảnh báo tỷ lệ DTI vượt ngưỡng phân vị 75% hệ thống. |
| **27** | `has_bad_debt` | 0.1714 | **-4.95** | Trừ điểm | Đang có nợ xấu thuộc các nhóm nợ xấu liên ngân hàng. |
| **28** | `income_verifiable_flag` | 0.1960 | **-5.66** | Trừ điểm | Cờ phạt khi không thể xác minh được nguồn thu nhập hợp pháp. |
| **29** | `num_installs_dpd10` | 0.2084 | **-6.01** | Trừ điểm | Số kỳ thanh toán bị quá hạn từ 10 ngày trở lên. |
| **30** | `previous_default_rate` | 0.3919 | **-11.31** | Trừ điểm | Tỷ lệ đơn vay bị từ chối/vỡ nợ trong quá khứ (Rủi ro lịch sử). |

---

## 6. Xử Lý Khuyết Thiếu Dữ Liệu Và Đặc Trưng Phân Loại

Để đảm bảo mô hình vận hành ổn định trong môi trường real-time mà không gặp lỗi tính toán khi dữ liệu đầu vào bị thiếu (null), pipeline áp dụng các quy tắc tiền xử lý nghiêm ngặt:

### 6.1. Xử lý khuyết thiếu (Imputation)
* **Đặc trưng số (Numerical)**: Điền khuyết thiếu bằng giá trị trung vị (`Median`) được tính toán từ tập huấn luyện. Giá trị trung vị này cũng được dùng làm điểm neo chuẩn hóa ($\mu_i$).
* **Đặc trưng phân loại (Categorical)**: Điền khuyết thiếu bằng chuỗi `'Other/Unknown'`.

### 6.2. Mã hóa biến phân loại (Ordinal Encoding)
Hai biến phân loại là `employment_status_grouped` và `occupation_type` đi qua bộ mã hóa `OrdinalEncoder` ánh xạ các chuỗi danh mục thành số nguyên. Nhằm tránh lỗi khi gặp nhãn dữ liệu mới lạ ở môi trường production (Out-of-Vocabulary), bộ mã hóa được cấu hình gán giá trị mặc định bằng `-1` (`handle_unknown="use_encoded_value", unknown_value=-1`).

---

## 7. Quy Trình Tính Điểm Chi Tiết Từng Bước (Algorithm Pipeline)

Khi nhận được yêu cầu tính điểm tín dụng thông qua API, hệ thống thực hiện tuần tự 6 bước sau:

1. **Bước 1: Điền khuyết thiếu**:
   Hệ thống kiểm tra các trường dữ liệu đầu vào. Nếu có trường giá trị số bị thiếu, điền bằng trung vị lịch sử của trường đó. Nếu trường phân loại bị thiếu, điền bằng `'Other/Unknown'`.
2. **Bước 2: Tiền xử lý đặc trưng**:
   * Áp dụng StandardScaler chuyển các đặc trưng số $x_i$ thành $z_i = \frac{x_i - \mu_i}{\sigma_i}$.
   * Áp dụng OrdinalEncoder chuyển các đặc trưng phân loại thành giá trị số nguyên danh mục.
3. **Bước 3: Tính toán Logit mặc định nợ**:
   Nhân vector đặc trưng đã xử lý với vector hệ số $\beta$ của mô hình, cộng với hệ số tự do $\beta_0$:
   $$\text{logit} = \beta_0 + \sum_{i=1}^{M} \beta_i z_i$$
4. **Bước 4: Chuyển đổi sang điểm số FICO**:
   Sử dụng công thức FICO Scaling Engine để chuyển đổi từ giá trị logit sang thang điểm:
   $$\text{Score} = 600 - 28.8539 \times (\text{logit} - (-3.9120))$$
5. **Bước 5: Áp giới hạn điểm số (Clamping)**:
   Giới hạn điểm số tín dụng nằm trong khoảng từ 300 đến 850 điểm:
   $$\text{FICO\_Score} = \max(300, \min(850, \text{Round}(\text{Score})))$$
6. **Bước 6: Phân rã lý do và giải thích kết quả**:
   Sử dụng giá trị đóng góp của từng biến số để xác định các đặc trưng làm tăng hoặc giảm điểm của khách hàng mạnh nhất. Trả về kết quả điểm số FICO, phân hạng tín dụng (Poor, Fair, Good, Very Good, Excellent) và danh sách các Adverse Reasons (Lý do bất lợi).

---

## 8. Các Ví Dụ Tính Toán Thực Tế

Để hiểu rõ hơn về cách thức quy đổi, dưới đây là các ví dụ minh họa bằng số liệu cụ thể.

### 8.1. Quy đổi trực tiếp từ Xác suất vỡ nợ (PD) sang Điểm FICO
Giả sử mô hình dự báo ra các mức xác suất vỡ nợ khác nhau, điểm số được tính toán như sau:

* **Trường hợp A: Xác suất vỡ nợ cực thấp $p = 0.30\%$**
  $$\text{logit} = \ln\left(\frac{0.003}{1 - 0.003}\right) = \ln(0.003009) \approx -5.8061$$
  $$\text{Score} = 600 - 28.8539 \times (-5.8061 - (-3.9120)) = 600 - 28.8539 \times (-1.8941) \approx 600 + 54.65 \approx 655 \text{ điểm}$$
* **Trường hợp B: Xác suất vỡ nợ chuẩn neo cơ sở $p = 1.96\%$**
  $$\text{logit} = \ln\left(\frac{0.0196}{1 - 0.0196}\right) = \ln(0.02) \approx -3.9120$$
  $$\text{Score} = 600 - 28.8539 \times (-3.9120 - (-3.9120)) = 600 \text{ điểm}$$
* **Trường hợp C: Xác suất vỡ nợ trung bình danh mục $p = 8.00\%$**
  $$\text{logit} = \ln\left(\frac{0.08}{1 - 0.08}\right) = \ln(0.086956) \approx -2.4423$$
  $$\text{Score} = 600 - 28.8539 \times (-2.4423 - (-3.9120)) = 600 - 28.8539 \times 1.4697 \approx 600 - 42.41 \approx 558 \text{ điểm}$$
* **Trường hợp D: Xác suất vỡ nợ cực cao $p = 40.00\%$ (Ngưỡng từ chối tự động)**
  $$\text{logit} = \ln\left(\frac{0.40}{1 - 0.40}\right) = \ln(0.666667) \approx -0.4055$$
  $$\text{Score} = 600 - 28.8539 \times (-0.4055 - (-3.9120)) = 600 - 28.8539 \times 3.5065 \approx 600 - 101.18 \approx 499 \text{ điểm}$$

---

### 8.2. Ví dụ tính điểm chi tiết cho một hồ sơ khách hàng cụ thể
Xét một hồ sơ khách hàng đăng ký vay vốn có các thông tin thực tế như sau:

#### Thông tin hồ sơ khách hàng:
1. `num_bureau_records` (Số hồ sơ tại CIC): **8** (trung vị tập mẫu là 4, độ lệch chuẩn là 4.5. Giá trị chuẩn hóa $z_1 = \frac{8 - 4}{4.5} \approx 0.89$)
2. `age_years` (Tuổi): **35 tuổi** (trung vị tập mẫu là 42, độ lệch chuẩn là 12.0. Giá trị chuẩn hóa $z_2 = \frac{35 - 42}{12.0} \approx -0.58$)
3. `years_employed` (Thâm niên việc làm): **5 năm** (trung vị là 4, độ lệch chuẩn là 6.3. Giá trị chuẩn hóa $z_3 = \frac{5 - 4}{6.3} \approx 0.16$)
4. `income_verifiable_flag` (Xác minh thu nhập): **1** (Có xác minh được. Biến nhị phân. Giá trị chuẩn hóa $z_4 = 0.40$)
5. `num_installs_dpd10` (Kỳ quá hạn >10 ngày): **0 kỳ** (Giá trị chuẩn hóa $z_5 = -0.50$)
6. `high_dti_flag` (DTI cao): **0** (Giá trị chuẩn hóa $z_6 = -0.30$)
7. `num_active_credit` (Số khoản vay đang mở): **3 tài khoản** (trung vị là 2, độ lệch chuẩn là 1.77. Giá trị chuẩn hóa $z_7 = \frac{3 - 2}{1.77} \approx 0.56$)
8. *Giả định các đặc trưng còn lại đều ở mức trung bình (chuẩn hóa $z_i = 0$).*

#### Bước 1: Tính toán logit mặc định nợ
Sử dụng các hệ số $\beta$ tương ứng từ bảng tham số đặc trưng:
$$\text{logit} = \beta_0 + \sum \beta_i z_i$$
$$\text{logit} = -2.6539 + [ (-0.2843 \times 0.89) + (-0.2543 \times -0.58) + (-0.0764 \times 0.16) + (0.1960 \times 0.40) + (0.2084 \times -0.50) + (0.1639 \times -0.30) + (0.0418 \times 0.56) ]$$
$$\text{logit} = -2.6539 + [ -0.2530 + 0.1475 - 0.0122 + 0.0784 - 0.1042 - 0.0492 + 0.0234 ]$$
$$\text{logit} = -2.6539 + [ -0.1693 ] = -2.8232$$

Xác suất vỡ nợ dự báo tương ứng:
$$p = \frac{1}{1 + e^{-(-2.8232)}} = \frac{1}{1 + e^{2.8232}} \approx \frac{1}{1 + 16.83} \approx 5.61\%$$

#### Bước 2: Quy đổi sang điểm FICO
$$\text{Score} = 600 - 28.8539 \times (-2.8232 - (-3.9120))$$
$$\text{Score} = 600 - 28.8539 \times (1.0888)$$
$$\text{Score} = 600 - 31.416 \approx 568.58 \text{ điểm}$$

Làm tròn về số nguyên gần nhất: **569 điểm**.
Khách hàng này có điểm tín dụng FICO là **569** (Phân hạng **Kém - Poor** do dưới ngưỡng 580). 

#### Bước 3: Phân rã điểm thành phần giải thích cho khách hàng
* **Model Base Points**: $+563.70$
* **Điểm đóng góp của các đặc trưng chính**:
  * `num_bureau_records`: $-28.8539 \times (-0.2843) \times 0.89 \approx +7.30$ (Cộng điểm do có lịch sử CIC phong phú)
  * `age_years`: $-28.8539 \times (-0.2543) \times (-0.58) \approx -4.26$ (Bị trừ điểm do tuổi trẻ hơn trung bình)
  * `years_employed`: $-28.8539 \times (-0.0764) \times 0.16 \approx +0.35$ (Cộng điểm do thâm niên làm việc cao hơn trung bình)
  * `income_verifiable_flag`: $-28.8539 \times 0.1960 \times 0.40 \approx -2.26$ (Bị trừ điểm do phân phối thu nhập xác minh)
  * `num_installs_dpd10`: $-28.8539 \times 0.2084 \times (-0.50) \approx +3.01$ (Cộng điểm do không có kỳ quá hạn quá 10 ngày)
  * `num_active_credit`: $-28.8539 \times 0.0418 \times 0.56 \approx -0.68$ (Bị trừ điểm nhẹ do mở hơi nhiều khoản vay)
  * `high_dti_flag`: $-28.8539 \times 0.1639 \times (-0.30) \approx +1.42$ (Cộng điểm do DTI an toàn dưới ngưỡng phân vị 75%)
* **Tổng điểm**: $563.70 + 7.30 - 4.26 + 0.35 - 2.26 + 3.01 - 0.68 + 1.42 = 568.58 \approx 569$ điểm.

---

## 9. Mối Liên Hệ Toán Học Giữa Giá Trị SHAP Và Điểm Số Scorecard

Hệ thống `credit_score_service` sử dụng bộ giải thích SHAP (SHAP LinearExplainer) để phân tích các yếu tố ảnh hưởng mạnh nhất cho từng hồ sơ khách hàng. Có một mối liên hệ toán học hoàn hảo và đồng bộ 1-1 giữa giá trị SHAP và điểm số đóng góp của Scorecard.

### 9.1. Định nghĩa giá trị SHAP trong mô hình tuyến tính
Đối với mô hình hồi quy tuyến tính (như Logit của hồi quy Logistic), giá trị SHAP của đặc trưng thứ $i$ đại diện cho mức độ đóng góp của đặc trưng đó vào độ lệch của logit dự báo so với logit trung bình kỳ vọng của toàn tập dữ liệu:
$$\text{logit} = E[\text{logit}] + \sum_{i=1}^{M} \text{SHAP}_i$$

Trong đó:
* $E[\text{logit}]$: Giá trị logit kỳ vọng trung bình trên toàn tập huấn luyện.
* $\text{SHAP}_i$: Giá trị SHAP của đặc trưng $i$, tính bằng:
  $$\text{SHAP}_i = \beta_i \times (z_i - E[z_i])$$

Vì tất cả các đặc trưng số đã được StandardScaler chuẩn hóa về trung bình bằng $0$ ($E[z_i] = 0$), công thức đơn giản hóa thành:
$$\text{SHAP}_i = \beta_i \times z_i$$

### 9.2. Công thức liên hệ trực tiếp
Thế quan hệ $\text{SHAP}_i = \beta_i z_i$ vào công thức tính điểm đóng góp đặc trưng $\text{Points}_i = -\text{Factor} \times \beta_i z_i$:
$$\text{Points}_i = -\text{Factor} \times \text{SHAP}_i$$

Với $\text{Factor} \approx 28.8539$:
$$\text{Points}_i \approx -28.8539 \times \text{SHAP}_i$$

#### Ý nghĩa nghiệp vụ:
Mối liên hệ này chứng minh rằng giá trị SHAP của một đặc trưng chính là hình ảnh phản chiếu ngược chiều của điểm đóng góp FICO:
* Đặc trưng có **SHAP âm** ($\text{SHAP}_i < 0$, làm giảm rủi ro vỡ nợ) sẽ tương ứng với **Điểm đóng góp dương** ($\text{Points}_i > 0$, cộng điểm FICO).
* Đặc trưng có **SHAP dương** ($\text{SHAP}_i > 0$, làm tăng rủi ro vỡ nợ) sẽ tương ứng với **Điểm đóng góp âm** ($\text{Points}_i < 0$, trừ điểm FICO).

Hệ thống tận dụng tính chất này để gọi trực tiếp thư viện SHAP trong backend nhằm trích xuất nhanh 3 đặc trưng ảnh hưởng mạnh nhất (có trị tuyệt đối $|\text{SHAP}_i|$ hoặc $|\text{Points}_i|$ lớn nhất) phục vụ cho tính năng tư vấn của Chatbot AI và giải thích cho khách hàng mà không cần cài đặt lại các công thức tính điểm thủ công.

---

## 10. Phân Nhóm Dải Điểm Và Ngưỡng Quyết Định Hệ Thống (Decision Cut-offs)

Điểm tín dụng FICO cuối cùng được phân nhóm thành các dải chất lượng để định vị mức độ rủi ro tín dụng của khách hàng:

| Phổ Điểm FICO | Phân Hạng Chất Lượng | Tỷ Lệ Khách Hàng Thực Tế | Tỷ Lệ Vỡ Nợ Thực Tế (PD) | Hành Động Đề Xuất (Nếu Dùng Scorecard Độc Lập) |
| :---: | :---: | :---: | :---: | :--- |
| **300 – 499** | **Yếu (Poor)** | $0.05\%$ | $13.10\%$ | **Từ chối ngay lập tức (Auto Reject)**. |
| **500 – 579** | **Trung bình thấp (Fair)** | $23.74\%$ | $7.66\%$ | **Hạn chế duyệt / Chuyển thẩm định kỹ**. |
| **580 – 669** | **Tốt (Good)** | $76.18\%$ | $1.81\%$ | **Phê duyệt chuẩn / Áp dụng lãi suất chuẩn**. |
| **670 – 739** | **Khá tốt (Very Good)** | $0.03\%$ | $0.00\%$ | **Ưu tiên phê duyệt nhanh / Giảm lãi suất**. |
| **740 – 850** | **Xuất sắc (Excellent)** | $<0.01\%$ | $0.00\%$ | **Phê duyệt siêu tốc / Hạn mức tối đa / Ưu đãi lãi suất**. |

### Chiến lược kết hợp mô hình phê duyệt tối ưu
Hệ thống CreditIntel áp dụng giải pháp tối ưu hóa lợi nhuận danh mục bằng cách kết hợp song hành hai mô hình:
1. **Dùng LightGBM v4 làm bộ lọc chặn (Auto Reject)**: Tận dụng khả năng dự báo phi tuyến chính xác của thuật toán Ensemble cây quyết định với ROC-AUC cao (0.8065) để từ chối tự động các hồ sơ rủi ro cao ($PD > 40\%$).
2. **Dùng Scorecard v2 làm công cụ Chấm điểm & Giải thích (Pricing & Explainability)**: Đối với các hồ sơ vượt qua bộ lọc chặn, sử dụng điểm FICO để định phí rủi ro (lãi suất tăng dần nếu điểm giảm từ 670 về 500), đồng thời phục vụ giải thích trực quan và tư vấn cải thiện điểm tín dụng thông qua trợ lý Chatbot AI.
