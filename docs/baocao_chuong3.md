# CHƯƠNG III. DỮ LIỆU, ETL VÀ PHÂN TÍCH RỦI RO TÍN DỤNG

---

## 3.1 Tổng quan kiến trúc dữ liệu

Trong bài toán chấm điểm và dự đoán rủi ro tín dụng, chất lượng của dữ liệu đầu vào quyết định trực tiếp đến độ tin cậy của mô hình. Dữ liệu tín dụng thô vốn phức tạp: phân tán trên nhiều bảng quan hệ, chứa tỉ lệ giá trị khuyết thiếu cao, và phải trải qua nhiều bước biến đổi trước khi trở thành các đặc trưng (features) có ý nghĩa thống kê cho thuật toán học máy. Để giải quyết bài toán này một cách có hệ thống, CreditIntel áp dụng **Medallion Architecture** — một kiến trúc dữ liệu phân tầng được thiết kế cho các hệ thống phân tích hiện đại.

### Sơ đồ luồng dữ liệu

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                        CREDITINTEL — DATA PIPELINE FLOW                          │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   Raw Dataset (Kaggle)           DuckDB (Analytical Warehouse)                   │
│   ┌─────────────────┐           ┌──────────────────────────────────────────────┐ │
│   │  138 Parquet     │           │                                              │ │
│   │  files (~27GB)   │────────►  │  ┌─────────┐   ┌──────────┐   ┌──────────┐  │ │
│   │  • train_base    │  Bronze   │  │ BRONZE   │   │ SILVER   │   │  GOLD    │  │ │
│   │  • train_static  │  Loader   │  │ 6 bảng   │──►│ 1 bảng   │──►│ 1 bảng   │  │ │
│   │  • train_person  │ (Python)  │  │ thô gốc  │   │ đã làm   │   │ ML-ready │  │ │
│   │  • train_bureau  │           │  │          │   │ sạch     │   │ features │  │ │
│   │  • train_applprev│           │  └─────────┘   └──────────┘   └────┬─────┘  │ │
│   └─────────────────┘           │                                     │        │ │
│                                  └─────────────────────────────────────┼────────┘ │
│                                                                       │          │
│                                                                       ▼          │
│                                  ┌──────────────────────────────────────────────┐ │
│                                  │          ML TRAINING & INFERENCE              │ │
│                                  │  ┌───────────────┐  ┌───────────────────┐    │ │
│                                  │  │ LightGBM v4   │  │ Scorecard LR      │    │ │
│                                  │  │ (Risk Model)  │  │ (FICO 300–850)    │    │ │
│                                  │  └───────┬───────┘  └────────┬──────────┘    │ │
│                                  │          │                   │               │ │
│                                  │          ▼                   ▼               │ │
│                                  │    P(default) ──► Xét duyệt tự động         │ │
│                                  │    FICO score ──► Cấp điểm tín dụng         │ │
│                                  └──────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### Vai trò của từng tầng

- **Bronze** — Tầng nạp thô: Đọc nguyên bản các file Parquet từ Kaggle vào DuckDB bằng lệnh `read_parquet()`, không thực hiện bất kỳ phép biến đổi nào. Dữ liệu ở tầng này giữ nguyên cấu trúc gốc của nhà cung cấp, bao gồm cả giá trị null và các cột không sử dụng. Mục đích là tạo một **bản lưu trữ bất biến** (immutable snapshot) để đảm bảo tính truy vết (data lineage).

- **Silver** — Tầng chuẩn hóa: Thực hiện ba phép biến đổi cốt lõi — (1) Join các bảng đa cấp (depth=0 và depth=1) thành một bảng phẳng duy nhất `silver.hc_v2_cleansed`, (2) Tổng hợp (aggregate) các bảng lịch sử depth=1 xuống mức một bản ghi trên mỗi đơn vay (case_id), (3) Chuẩn hóa tên cột, kiểu dữ liệu và xử lý null bằng `COALESCE`. Đây là bước quyết định chất lượng dữ liệu cho toàn bộ hạ nguồn.

- **Gold** — Tầng đặc trưng: Biến đổi các trường đã chuẩn hóa thành **feature vector sẵn sàng cho ML** (bảng `gold.hc_features_v2`). Tại đây, các tỉ lệ tài chính (DTI, loan-to-income), biến phân loại (education_ordinal, employment_status_grouped), cờ nhị phân (has_bad_debt, high_dti_flag) và cờ thiếu dữ liệu (income_missing_flag, dti_missing_flag) được thiết kế và tính toán.

### Quyết định thiết kế: DuckDB làm Analytical Warehouse

Một quyết định kiến trúc quan trọng của dự án là sử dụng **DuckDB** thay vì các giải pháp như Pandas hoặc Spark cho khâu xử lý dữ liệu. Lý do cụ thể:

1. **Xử lý out-of-core**: Bộ dữ liệu Home Credit tổng dung lượng ~27GB — vượt quá giới hạn bộ nhớ RAM phổ thông. DuckDB thực hiện xử lý trực tiếp trên đĩa (disk-based processing) kết hợp bộ nhớ đệm thông minh, cho phép join và aggregate trên hàng chục triệu bản ghi mà không yêu cầu máy chủ với RAM lớn.

2. **Đọc Parquet gốc và xử lý ETL bằng SQL**: DuckDB hỗ trợ hàm `read_parquet()` với khả năng đọc glob pattern (`train_static_0_*.parquet`) và thực hiện toàn bộ phép biến đổi ETL (join, aggregate, feature engineering) bằng SQL thuần — tất cả đều chạy out-of-core, tránh tràn RAM. Pandas DataFrame chỉ được sử dụng ở bước cuối cùng khi load tập dữ liệu Gold (đã nhỏ gọn) vào thuật toán huấn luyện.

3. **SQL thuần cho biến đổi**: Toàn bộ logic chuyển đổi Silver và Gold được viết bằng SQL chuẩn (file `.sql` riêng biệt), tách bạch khỏi code điều phối Python. Điều này tạo thuận lợi cho việc kiểm tra, tái sử dụng và bảo trì logic nghiệp vụ.

4. **Single-file deployment**: Toàn bộ Analytical Warehouse được lưu trong một file duy nhất (`data/etl.duckdb`), không yêu cầu cài đặt hoặc vận hành server cơ sở dữ liệu, phù hợp với bối cảnh dự án đồ án.

---

## 3.2 Phân tích tập dữ liệu (Dataset)

### 3.2.1 Nguồn dữ liệu

Hệ thống CreditIntel sử dụng **hai bộ dữ liệu** với vai trò khác nhau rõ ràng:

**Nguồn chính — Home Credit Credit Risk Model Stability (Kaggle):**

Đây là bộ dữ liệu duy nhất được dùng để **huấn luyện cả hai mô hình ML** (LightGBM Risk Model và Logistic Regression Scorecard). Bộ dữ liệu bao gồm thông tin vay vốn thực tế từ Home Credit Group — một tổ chức tài chính tiêu dùng hoạt động tại nhiều quốc gia, chuyên phục vụ phân khúc khách hàng ít hoặc chưa có lịch sử tín dụng chính thức. Dữ liệu bao phủ nhiều chiều thông tin: nhân khẩu học, thu nhập, khoản vay, lịch sử trả nợ tại Trung tâm thông tin tín dụng (Credit Bureau), và lịch sử đơn vay trước đó — tạo thành bức tranh toàn diện về hồ sơ rủi ro của người vay.

**Nguồn tham chiếu — Prosper Loan Dataset (~113K khoản vay, 2005–2014):**

Bộ dữ liệu Prosper **không** tham gia vào quá trình huấn luyện mô hình hiện tại. Vai trò duy nhất của nó là cung cấp **tham chiếu thiết kế nghiệp vụ** cho ứng dụng Web: cấu trúc các thực thể (borrowers, loans, credit_profiles), luồng trạng thái đơn vay (Application State Machine), và dải giá trị hợp lệ cho các trường nhập liệu trên giao diện người dùng. Sự phân tách này đảm bảo rằng model ML hoạt động trên dữ liệu tín dụng cập nhật và đa dạng hơn, trong khi Web App vẫn mô phỏng được quy trình cho vay thực tế.

### 3.2.2 Đặc trưng dữ liệu

Bộ dữ liệu Home Credit mang hai đặc trưng kỹ thuật then chốt ảnh hưởng trực tiếp đến thiết kế pipeline:

**Dữ liệu quan hệ đa bảng (Multi-table Relational):**

Không giống các bộ dữ liệu tabular thông thường (một file CSV duy nhất), Home Credit tổ chức thông tin theo mô hình quan hệ với **6 bảng chính**, phân thành hai nhóm theo độ sâu liên kết:

| Bảng | Depth | Số bản ghi | Quan hệ | Nội dung |
|---|:---:|---:|---|---|
| `train_base` | 0 | 1.53M | Bảng gốc | Nhãn `target` (is_default) và ngày quyết định |
| `train_static_0` | 0 | 1.53M | 1:1 với base | Khoản vay, thu nhập, DPD, thanh toán |
| `train_static_cb_0` | 0 | 1.50M | 1:1 với base | Lịch sử tra cứu Credit Bureau |
| `train_person_1` | 1 | 2.97M | N:1 với base | Nhân khẩu học (sinh nhật, học vấn, việc làm) |
| `train_credit_bureau_a_1` | 1 | 15.9M | N:1 với base | Hợp đồng tín dụng tại Bureau (DPD, nợ, gia hạn) |
| `train_applprev_1` | 1 | 6.5M | N:1 với base | Lịch sử đơn vay trước đó |

- Các bảng **depth=0** có quan hệ 1:1 với `train_base` qua khóa `case_id`, join trực tiếp.
- Các bảng **depth=1** có quan hệ N:1 (nhiều bản ghi trên mỗi case_id), **bắt buộc phải aggregate** (đếm, tính trung bình, lấy max) trước khi join về bảng chính. Đây là thách thức kỹ thuật cốt lõi của pipeline ETL.

**Định dạng Parquet tối ưu cho dữ liệu lớn:**

Toàn bộ dữ liệu thô có dung lượng khoảng **~27GB**, được phân tách thành **138 file Parquet**. Việc sử dụng Apache Parquet thay vì CSV mang lại ba lợi thế thực tiễn:

- **Nén columnar**: Parquet lưu trữ dữ liệu theo cột thay vì theo dòng, cho tỉ lệ nén cao hơn CSV từ 5–10 lần trên dữ liệu có nhiều giá trị lặp (ví dụ: cột trạng thái hợp đồng, loại nghề nghiệp).
- **Predicate pushdown**: Khi thực thi truy vấn lọc (`WHERE target IS NOT NULL`), DuckDB chỉ đọc các row group thỏa điều kiện thay vì quét toàn bộ file — giảm đáng kể lượng I/O trên đĩa.
- **Schema tự mô tả**: Mỗi file Parquet chứa sẵn metadata về kiểu dữ liệu của từng cột, loại bỏ nhu cầu khai báo schema thủ công khi nạp dữ liệu vào DuckDB.

### 3.2.3 Nhóm thuộc tính nghiệp vụ

Bộ dữ liệu Home Credit chứa tổng cộng **467 biến gốc** (theo từ điển `feature_definitions.csv`), phân tán trên 6 bảng thô. Trong đó, các biến có ý nghĩa trực tiếp cho bài toán đánh giá rủi ro tín dụng được phân thành **bốn nhóm nghiệp vụ** như sau. Lưu ý: đây là các biến thô chưa qua xử lý ETL — việc biến đổi và tổng hợp chúng thành đặc trưng ML sẽ được trình bày tại mục 3.3.

**Nhóm 1: Thu nhập & Khoản vay**

Các biến phản ánh quy mô khoản vay và năng lực tài chính khai báo của người vay — nền tảng để đánh giá khả năng trả nợ.

| Đặc trưng gốc (Mã Kaggle) | Ý nghĩa nghiệp vụ | Bảng thô chứa dữ liệu |
|---|---|---|
| `credamount_770A` | Số tiền vay hoặc hạn mức thẻ tín dụng | `train_static_0` |
| `annuity_780A` | Số tiền trả góp hàng tháng (annuity) | `train_static_0` |
| `maininc_215A` | Thu nhập chính hàng tháng của khách hàng | `train_static_0` |
| `currdebt_22A` | Tổng nợ hiện tại của khách hàng | `train_static_0` |
| `totaldebt_9A` | Tổng dư nợ toàn bộ các khoản vay | `train_static_0` |
| `mainoccupationinc_384A` | Thu nhập từ nghề nghiệp chính | `train_person_1` |
| `credamount_590A` | Số tiền vay của các đơn vay trước đó | `train_applprev_1` |

**Nhóm 2: Hành vi trễ hạn & Lịch sử tín dụng ngoại vi (Credit Bureau)**

Nhóm biến có sức dự báo mạnh nhất — phản ánh hành vi trả nợ thực tế của khách hàng trên toàn hệ thống tài chính, được ghi nhận bởi Trung tâm thông tin tín dụng.

| Đặc trưng gốc (Mã Kaggle) | Ý nghĩa nghiệp vụ | Bảng thô chứa dữ liệu |
|---|---|---|
| `maxdpdlast24m_143P` | Số ngày quá hạn tối đa trong 24 tháng gần nhất | `train_static_0` |
| `maxdpdlast12m_727P` | Số ngày quá hạn tối đa trong 12 tháng gần nhất | `train_static_0` |
| `maxdpdlast3m_392P` | Số ngày quá hạn tối đa trong 3 tháng gần nhất | `train_static_0` |
| `avgdbddpdlast3m_4187120P` | Trung bình ngày quá hạn trong 3 tháng gần nhất | `train_static_0` |
| `numinstlswithdpd10_728L` | Số kỳ trả góp bị quá hạn trên 10 ngày | `train_static_0` |
| `numactivecreds_622L` | Số khoản tín dụng đang hoạt động | `train_static_0` |
| `dpdmax_139P` | Số ngày quá hạn tối đa trên hợp đồng đang hoạt động tại Bureau | `train_credit_bureau_a_1` |
| `dpdmax_757P` | Số ngày quá hạn tối đa trên hợp đồng đã đóng tại Bureau | `train_credit_bureau_a_1` |
| `debtoutstand_525A` | Dư nợ còn lại trên hợp đồng hiện tại tại Bureau | `train_credit_bureau_a_1` |
| `debtoverdue_47A` | Số tiền quá hạn trên hợp đồng hiện tại tại Bureau | `train_credit_bureau_a_1` |
| `overdueamountmax_155A` | Số tiền quá hạn tối đa trên hợp đồng đang hoạt động | `train_credit_bureau_a_1` |
| `prolongationcount_599L` | Số lần gia hạn (rollover) hợp đồng tín dụng | `train_credit_bureau_a_1` |
| `numberofcontrsvalue_258L` | Số hợp đồng đang hoạt động ghi nhận tại Bureau | `train_credit_bureau_a_1` |
| `numberofoverdueinstls_725L` | Số kỳ trả góp đang quá hạn trên hợp đồng hoạt động | `train_credit_bureau_a_1` |

**Nhóm 3: Hành vi đơn vay nội bộ & Truy vấn CIC**

Các biến phản ánh lịch sử nộp đơn trước đó và tần suất bị tra cứu tín dụng — tín hiệu về mức độ "đói tín dụng" (credit hunger) của khách hàng.

| Đặc trưng gốc (Mã Kaggle) | Ý nghĩa nghiệp vụ | Bảng thô chứa dữ liệu |
|---|---|---|
| `applications30d_658L` | Số đơn vay nộp trong 30 ngày gần nhất | `train_static_0` |
| `cntpmts24_3658933L` | Số tháng có thanh toán trong 24 tháng qua | `train_static_0` |
| `avgpmtlast12m_4525200A` | Trung bình số tiền thanh toán trong 12 tháng qua | `train_static_0` |
| `cntincpaycont9m_3716944L` | Số lần thanh toán đến trong 9 tháng qua | `train_static_0` |
| `days30_165L` | Số lần bị tra cứu tín dụng trong 30 ngày qua | `train_static_cb_0` |
| `days180_256L` | Số lần bị tra cứu tín dụng trong 180 ngày qua | `train_static_cb_0` |
| `numberofqueries_373L` | Tổng số lần bị tra cứu tại Trung tâm tín dụng | `train_static_cb_0` |
| `for3years_128L` | Số đơn vay bị từ chối trong 3 năm qua | `train_static_cb_0` |
| `status_219L` | Trạng thái đơn vay trước đó (A=Duyệt, D/N=Từ chối) | `train_applprev_1` |
| `actualdpd_943P` | Số ngày quá hạn thực tế trên đơn vay trước đó | `train_applprev_1` |

**Nhóm 4: Nhân khẩu học & Nghề nghiệp**

Đặc điểm cá nhân và hoàn cảnh sống của người vay — phản ánh mức ổn định tài chính dài hạn.

| Đặc trưng gốc (Mã Kaggle) | Ý nghĩa nghiệp vụ | Bảng thô chứa dữ liệu |
|---|---|---|
| `birth_259D` | Ngày sinh của người vay | `train_person_1` |
| `education_927M` | Trình độ học vấn (giá trị ẩn danh) | `train_person_1` |
| `incometype_1044T` | Loại hình thu nhập (Employed, Self-employed, Retired...) | `train_person_1` |
| `empl_employedtotal_800L` | Thời gian làm việc tổng cộng | `train_person_1` |
| `housetype_905L` | Loại hình nhà ở (sở hữu, thuê, ở cùng gia đình) | `train_person_1` |
| `familystate_447L` | Tình trạng hôn nhân | `train_person_1` |
| `gender_992L` | Giới tính | `train_person_1` |
| `maritalst_703L` | Tình trạng hôn nhân (nguồn thứ hai) | `train_person_1` |

### 3.2.4 Thách thức dữ liệu thực tế

Hai thách thức cốt lõi của bộ dữ liệu ảnh hưởng đến toàn bộ chiến lược xây dựng pipeline và huấn luyện mô hình:

**Thách thức 1: Dữ liệu khuyết thiếu (Missing Values)**

Các bảng lịch sử depth=1 có đặc thù là **không phải khách hàng nào cũng có dữ liệu**. Cụ thể:

- Bảng `train_credit_bureau_a_1` chứa 15.9M bản ghi nhưng chỉ bao phủ **1.39M case_id duy nhất** trên tổng số 1.53M — nghĩa là khoảng **9% đơn vay không có bất kỳ bản ghi Bureau nào**.
- Bảng `train_applprev_1` bao phủ **1.22M case_id** — khoảng **20% đơn vay không có lịch sử ứng dụng trước đó**.
- Các trường nhân khẩu học (`birth_date`, `employment_length`, `education_level`) cũng có tỉ lệ null đáng kể do không phải thông tin bắt buộc khi nộp đơn.

Pipeline ETL xử lý thách thức này bằng chiến lược **LEFT JOIN kết hợp COALESCE có chọn lọc**:
- Các bảng depth=1 được aggregate trước, sau đó `LEFT JOIN` với bảng chính để giữ lại toàn bộ đơn vay — kể cả những đơn không có dữ liệu lịch sử.
- Hàm `COALESCE(value, 0)` **chỉ** được áp dụng cho các biến đếm tần suất và hành vi (như số ngày trễ hạn, số hợp đồng, nợ quá hạn) với hàm ý nghiệp vụ rõ ràng: "không có lịch sử tín dụng" tương đương với "không có vi phạm". Ngược lại, với các biến tài chính liên tục (như thu nhập `stated_monthly_income`), giá trị khuyết **vẫn được giữ nguyên là NULL** để bảo toàn tính trung thực của dữ liệu — tránh nhầm lẫn giữa "thu nhập bằng 0" và "không khai báo thu nhập".
- Tại tầng Gold, hai cờ `income_missing_flag` và `dti_missing_flag` được tạo riêng để mô hình ML có thể **học được sự khác biệt** giữa "giá trị bằng 0 thật" và "giá trị bị khuyết thiếu" — kỹ thuật quan trọng trong xử lý dữ liệu tín dụng.

**Thách thức 2: Mất cân bằng nhãn trầm trọng (Class Imbalance)**

Nhãn đầu ra `target` (biến `is_default`) có phân bố **cực kỳ lệch**: tỉ lệ khách hàng vỡ nợ chỉ chiếm khoảng **3.14%** trên tổng số 1.53M bản ghi. Tỉ lệ ~31:1 giữa nhãn âm (trả nợ bình thường) và nhãn dương (vỡ nợ) tạo ra hai rủi ro cho mô hình:

- **Rủi ro trong huấn luyện**: Nếu không có biện pháp xử lý, thuật toán sẽ có xu hướng dự đoán tất cả là "không vỡ nợ" để đạt accuracy cao (~97%), nhưng hoàn toàn bỏ sót nhóm khách hàng rủi ro — đối tượng chính mà hệ thống cần phát hiện.
- **Rủi ro trong đánh giá**: Các chỉ số như Accuracy trở nên vô nghĩa. Hệ thống phải dựa vào **ROC-AUC**, **Recall**, và **Precision tại ngưỡng hoạt động** (threshold=0.4) để đánh giá chính xác hiệu quả mô hình.

Thách thức này đòi hỏi kỹ thuật xử lý đặc biệt ở giai đoạn huấn luyện mô hình (sẽ được trình bày chi tiết trong phần xây dựng mô hình), bao gồm tham số `is_unbalance=True` cho LightGBM và lựa chọn hàm mất mát phù hợp cho Logistic Regression Scorecard.

---

## 3.3 Kiến trúc ETL Pipeline (Medallion Architecture)

### 3.3.1 Tổng quan ETL Pipeline

Pipeline ETL của CreditIntel được thiết kế theo nguyên tắc **điều phối tuần tự** (sequential orchestration): mỗi tầng xử lý xong mới kích hoạt tầng kế tiếp, đảm bảo tính nhất quán dữ liệu xuyên suốt. File điều phối chính `pipeline.py` thực thi trình tự:

```python
# machinelearning/etl/pipeline.py
from machinelearning.etl.load_bronze import main as bronze
from machinelearning.etl.etl_silver import main as silver
from machinelearning.etl.etl_gold   import main as gold

if __name__ == "__main__":
    bronze()   # Bước 1: Nạp dữ liệu thô
    silver()   # Bước 2: Làm sạch và chuẩn hóa
    gold()     # Bước 3: Feature Engineering
```

Kiến trúc này mang ba đặc điểm thiết kế quan trọng:

- **Tách bạch ngôn ngữ**: Code điều phối (Python) chỉ đảm nhận vai trò gọi hàm, quản lý kết nối và in log. Toàn bộ logic biến đổi dữ liệu nằm trong các file SQL riêng biệt (`transform_silver_hcv2.sql`, `transform_gold_hcv2.sql`), được đọc và thực thi qua SQLAlchemy. Sự phân tách này cho phép chỉnh sửa logic nghiệp vụ mà không ảnh hưởng đến code hạ tầng.

- **Khả năng tái tạo (Reproducibility)**: Mỗi tầng đều sử dụng lệnh `CREATE OR REPLACE TABLE` — chạy lại pipeline bất kỳ lúc nào cũng cho ra kết quả giống hệt, miễn dữ liệu nguồn không thay đổi. Không có trạng thái ẩn hay phụ thuộc thứ tự ngoài trình tự Bronze → Silver → Gold.

- **Tự kiểm chứng (Self-verification)**: Mỗi bước ETL kết thúc bằng một khối kiểm tra tự động — đếm số dòng, tính default rate, đo tỷ lệ null — và in kết quả ra console. Nếu pipeline chạy xong mà không báo lỗi, người vận hành có thể tin tưởng vào tính toàn vẹn của dữ liệu đầu ra.

### 3.3.2 Lớp Bronze — Nạp dữ liệu thô hiệu suất cao

Lớp Bronze (`load_bronze.py`) chịu trách nhiệm nạp toàn bộ dữ liệu thô từ 138 file Parquet (~27GB) vào DuckDB, tạo ra **6 bảng Bronze** tương ứng với 6 bảng nguồn từ Kaggle.

**Kỹ thuật nạp dữ liệu:**

Hệ thống sử dụng hàm `read_parquet()` gốc của DuckDB kết hợp **glob pattern** để xử lý các bảng bị chia nhỏ thành nhiều file:

```sql
CREATE OR REPLACE TABLE bronze.train_static_0 AS
SELECT * FROM read_parquet('train_static_0_*.parquet')
```

Cú pháp `*` cho phép DuckDB tự động phát hiện và gom tất cả các file có tên khớp mẫu vào cùng một bảng — kỹ thuật đặc biệt quan trọng với bảng `train_credit_bureau_a_1` (chứa 15.9M bản ghi, chia thành nhiều file Parquet). Toàn bộ quá trình đọc và ghi diễn ra **out-of-core**: DuckDB stream dữ liệu từ đĩa qua bộ nhớ đệm rồi ghi vào file `.duckdb`, không bao giờ cần load toàn bộ dataset vào RAM.

**Nguyên tắc bất biến (Immutability):**

Lớp Bronze áp dụng triết lý `SELECT *` — không lọc, không đổi tên, không ép kiểu. Dữ liệu được sao chép nguyên trạng từ Parquet vào DuckDB, bao gồm cả giá trị null, cột không sử dụng và metadata gốc. Mục đích là tạo một **bản sao lưu trữ bất biến** (immutable snapshot) đóng vai trò điểm tham chiếu: nếu cần kiểm tra lại logic ở tầng Silver hoặc Gold, luôn có thể truy ngược về Bronze mà không cần tải lại từ Kaggle.

**Kiểm chứng sau nạp:**

Sau khi nạp xong 6 bảng, hệ thống mở lại kết nối ở chế độ `read_only=True` và thực hiện hai phép kiểm tra:
- **Đếm dòng** từng bảng để xác nhận dữ liệu đã được ghi đầy đủ.
- **Thống kê phân bố nhãn** trên `bronze.train_base`: tổng số bản ghi, số lượng default, tỷ lệ default (%) — phát hiện sớm sai lệch nếu file nguồn bị hỏng hoặc thiếu.

### 3.3.3 Lớp Silver — Làm sạch và chuẩn hóa đa bảng

Đây là tầng phức tạp nhất của pipeline. File `transform_silver_hcv2.sql` thực hiện nhiệm vụ chuyển đổi 6 bảng Bronze thô (với cấu trúc depth khác nhau) thành **một bảng phẳng duy nhất** `silver.hc_v2_cleansed` — sẵn sàng cho Feature Engineering.

Quy trình được triển khai qua 4 khối CTE (Common Table Expression), mỗi khối xử lý một bảng depth=1, kết thúc bằng một phép `JOIN` tổng hợp.

**CTE 1: `person_applicant` — Lọc người nộp đơn chính**

Bảng `train_person_1` chứa thông tin của nhiều cá nhân liên quan đến cùng một đơn vay (người vay chính, người bảo lãnh, người liên hệ). Hệ thống lọc chính xác người nộp đơn bằng điều kiện `WHERE num_group1 = 0`, chỉ giữ lại bản ghi đầu tiên (applicant) cho mỗi `case_id`.

Tại đây, một số phép chuẩn hóa quan trọng được thực hiện:
- **Rời rạc hóa thời gian làm việc** (`empl_employedtotal_800L`): Giá trị phân loại (`LESS_ONE`, `MORE_ONE`, `MORE_FIVE`) được chuyển thành số năm ước lượng (0.5, 3.0, 7.0) để phù hợp với input số cho ML.
- **Ép kiểu an toàn** cho các trường phân loại (`gender`, `house_type`, `marital_status`) sang `VARCHAR`, đảm bảo tương thích kiểu dữ liệu khi join.

**CTE 2: `bureau_agg` — Tổng hợp lịch sử Credit Bureau**

Bảng `train_credit_bureau_a_1` là bảng lớn nhất (15.9M bản ghi → 1.39M case_id duy nhất). Mỗi khách hàng có thể có hàng chục hợp đồng tín dụng tại các tổ chức tài chính khác nhau. CTE này **cuộn** toàn bộ lịch sử thành một dòng duy nhất trên mỗi `case_id` thông qua các phép tổng hợp:

| Phép tổng hợp | Trường đầu ra | Ý nghĩa nghiệp vụ |
|---|---|---|
| `COUNT(*)` | `num_bureau_contracts` | Tổng số hợp đồng tín dụng |
| `COUNT(*) FILTER(WHERE ...)` | `num_contracts_type_a`, `type_b` | Đếm theo loại trạng thái hợp đồng |
| `MAX(dpdmax_139P)` | `max_dpd_active` | Quá hạn nặng nhất trên hợp đồng đang hoạt động |
| `MAX(dpdmax_757P)` | `max_dpd_closed` | Quá hạn nặng nhất trên hợp đồng đã đóng |
| `SUM(debtoutstand_525A)` | `total_outstanding_debt` | Tổng dư nợ trên tất cả hợp đồng |
| `SUM(debtoverdue_47A)` | `total_overdue_amount_bureau` | Tổng số tiền quá hạn |
| `MAX(overdueamountmax_155A)` | `max_overdue_amount` | Số tiền quá hạn tối đa |
| `SUM(prolongationcount_599L)` | `total_prolongations` | Tổng số lần gia hạn hợp đồng |
| `AVG(instlamount_768A)` | `avg_instalment_active` | Trung bình tiền trả góp hàng tháng |

Tất cả giá trị số đều được bọc trong `COALESCE(..., 0)` để đảm bảo các case_id có dữ liệu Bureau nhưng thiếu một số trường cụ thể vẫn trả về giá trị mặc định hợp lệ.

**CTE 3: `prev_app_agg` — Tổng hợp lịch sử đơn vay trước đó**

Bảng `train_applprev_1` (6.5M bản ghi → 1.22M case_id) ghi nhận tất cả các lần nộp đơn vay trước đây. CTE này trích xuất các tín hiệu hành vi quan trọng:

- **Đếm theo trạng thái** (`status_219L`): Phân loại đơn đã duyệt (`A`), bị từ chối (`D`, `N`, `Q`), và đang hoạt động (`K`).
- **Tỷ lệ từ chối lịch sử** (`previous_rejection_rate`): Tính bằng số đơn bị từ chối / tổng đơn — một proxy cho mức độ "uy tín tín dụng" tích lũy. Phép tính sử dụng `NULLIF(COUNT(*), 0)` để tránh lỗi chia cho 0.
- **DPD trên đơn vay trước** (`max_prev_dpd`, `avg_prev_dpd`): Lịch sử quá hạn trên các khoản vay trước đó — tín hiệu dự báo mạnh cho hành vi trả nợ tương lai.

**CTE 4: `cb_static` — Trích xuất truy vấn Credit Bureau tĩnh**

Bảng `train_static_cb_0` (depth=0, join trực tiếp) cung cấp các chỉ số tra cứu tín dụng theo khung thời gian:
- `days30_165L` → `cb_queries_30d` (30 ngày)
- `days90_310L` → `cb_queries_90d` (90 ngày)
- `days180_256L` → `cb_queries_180d` (180 ngày)
- `numberofqueries_373L` → `num_cb_queries` (tổng)

Ngoài ra, số lần bị từ chối trong 3 năm (`for3years_128L`) và 1 năm (`foryear_618L`) cũng được trích xuất — đây là tín hiệu mạnh về "credit hunger" khi khách hàng liên tục bị từ chối nhưng vẫn tiếp tục nộp đơn.

**Phép JOIN tổng hợp cuối cùng:**

Bốn CTE được join lại với bảng chính theo chiến lược phân tầng:

```
train_base (b) ──[INNER JOIN]── train_static_0 (s)     -- depth=0, bắt buộc có
                 ──[LEFT JOIN]── cb_static (cbs)        -- depth=0, có thể thiếu
                 ──[LEFT JOIN]── person_applicant (pa)   -- depth=1, có thể thiếu
                 ──[LEFT JOIN]── bureau_agg (ba)         -- depth=1, có thể thiếu
                 ──[LEFT JOIN]── prev_app_agg (paa)      -- depth=1, có thể thiếu
```

- **INNER JOIN** duy nhất giữa `train_base` và `train_static_0`: đảm bảo mỗi đơn vay trong bảng kết quả đều có đầy đủ thông tin khoản vay cơ bản.
- **LEFT JOIN** cho 4 bảng còn lại: giữ lại toàn bộ đơn vay kể cả khi khách hàng không có lịch sử Bureau hoặc đơn vay trước đó.

Hai bộ lọc bổ sung tại mệnh đề `WHERE` loại bỏ các bản ghi không hợp lệ:
- `b.target IS NOT NULL`: Chỉ giữ đơn vay có nhãn (đã biết kết quả trả nợ).
- `s.credamount_770A > 0 AND s.annuity_780A > 0`: Loại bỏ các bản ghi có số tiền vay hoặc tiền trả góp bằng 0 — không có ý nghĩa nghiệp vụ.

Tại Silver, hệ thống thực hiện các phép **biến đổi phái sinh** trực tiếp trong mệnh đề `SELECT`. Các thao tác này được tổng hợp trong ma trận dưới đây:

**Ma trận biến đổi dữ liệu tầng Silver**

| Tên cột đích (Silver) | Thao tác biến đổi (Logic SQL) | Mục đích nghiệp vụ |
|---|---|---|
| `term` | `GREATEST(6, LEAST(120, ROUND(credamount / annuity)))` | Suy ra kỳ hạn vay thực tế từ số tiền và mức trả góp, giới hạn trong khoảng chuẩn 6–120 tháng. |
| `debt_to_income_ratio` | `annuity / maininc_215A` | Đánh giá áp lực trả nợ trên thu nhập (DTI), chỉ tính khi thu nhập > 0 để tránh lỗi chia cho 0. |
| `age_years` | `(date_decision - birth_date) / 365.25` | Chuyển đổi khoảng cách từ ngày sinh đến ngày quyết định thành số năm tuổi thực tế. |
| `employment_status` | `CASE WHEN income_type IN ...` | Gom nhóm các loại hình thu nhập thô thành 5 nhóm chuẩn (Employed, Self-employed, Retired, Not employed, Other/Unknown) cho ML. |
| `income_verifiable` | `TRUE` nếu có nguồn thu nhập từ việc làm và `employment_length > 0` | Cờ xác định tính minh bạch và độ tin cậy của nguồn thu nhập khai báo. |
| `is_homeowner` | `TRUE` nếu `house_type = 'OWNED'` | Cờ xác nhận khách hàng có sở hữu bất động sản (tín hiệu tài sản đảm bảo). |
| `is_married` | `TRUE` nếu `family_state IN ('MARRIED', 'LIVING_WITH_PARTNER')` | Xác nhận tình trạng hôn nhân, hộ gia đình thường có mức độ ổn định tài chính cao hơn. |
| `employment_length` | Ánh xạ: `LESS_ONE` → 0.5, `MORE_ONE` → 3.0, `MORE_FIVE` → 7.0 | Rời rạc hóa chuỗi phân loại thời gian làm việc thành dữ liệu số liên tục để model dễ học. |

**Lập chỉ mục (Indexing):**

Sau khi tạo bảng, hai chỉ mục được tạo để tối ưu truy vấn hạ nguồn:
- `idx_hcv2_silver_default` trên cột `is_default` — hỗ trợ lọc nhanh theo nhãn.
- `idx_hcv2_silver_member` trên cột `member_key` — hỗ trợ truy vấn theo khách hàng.

### 3.3.4 Lớp Gold — Feature Engineering cho mô hình ML

File `transform_gold_hcv2.sql` biến đổi bảng Silver đã chuẩn hóa thành bảng `gold.hc_features_v2` — **feature vector cuối cùng** được sử dụng trực tiếp bởi cả hai mô hình (LightGBM và Scorecard). Dưới đây là toàn bộ các đặc trưng được tạo ra và các phương pháp Feature Engineering được áp dụng.


### 3.3.4 Lớp Gold — Feature Engineering cho mô hình ML

File `transform_gold_hcv2.sql` biến đổi bảng Silver đã chuẩn hóa thành bảng `gold.hc_features_v2` — **feature vector cuối cùng** được sử dụng trực tiếp bởi cả hai mô hình (LightGBM và Scorecard). Các kỹ thuật Feature Engineering và danh sách toàn bộ đặc trưng được tạo ra được chia thành 5 nhóm phương pháp nghiệp vụ cốt lõi, đồng bộ chặt chẽ với kiến trúc phân loại tại mô hình ML:

**Từ điển Đặc trưng Tầng Gold (Gold Feature Schema)**

| Đặc trưng (Gold Name) | Ý nghĩa nghiệp vụ | Xử lý tại Gold (SQL Logic) |
|---|---|---|
| **Nhóm 1: Nhóm thu nhập, khoản vay và gánh nặng nợ** | | |
| `loan_original_amount` | Tổng số tiền khách hàng đề nghị vay. Đây là cơ sở tuyệt đối để đánh giá quy mô rủi ro tín dụng ban đầu. | `Numeric` |
| `term` | Kỳ hạn vay thực tế tính bằng tháng, phản ánh thời gian chịu rủi ro tín dụng của khoản vay (kỳ hạn dài = rủi ro cao). | `Integer` |
| `stated_monthly_income` | Thu nhập hàng tháng do khách hàng tự khai báo. Thường tiềm ẩn rủi ro khai khống nên cần kết hợp biến cờ xác minh. | `Numeric` |
| `debt_to_income_ratio` | Tỷ lệ DTI ban đầu (Annuity / Thu nhập). Đây là chỉ báo cốt lõi nhất về áp lực trả nợ hàng tháng của khách hàng. | `Numeric` |
| `loan_amount_to_income` | Tỷ lệ dư nợ trên thu nhập năm, cho thấy khách hàng đang vay gấp bao nhiêu lần thu nhập hàng năm của họ. | `ROUND(loan_original_amount / (stated_monthly_income * 12), 5)` |
| `log_monthly_income` | Thu nhập đã được chuẩn hóa logarit để giảm thiểu nhiễu từ các khách hàng có thu nhập cực cao (outliers). | `LN(1 + stated_monthly_income)` |
| `payment_to_income` | Tỷ lệ trả góp trên thu nhập. Bản chất là DTI nhưng dùng tên gọi khác thống nhất với tiêu chuẩn Scorecard. | `debt_to_income_ratio` |
| `current_debt_ratio` | Tỷ lệ dư nợ hiện tại trên khoản vay đề xuất. Tỷ lệ cao chứng tỏ khách hàng đang cạn kiệt hạn mức tín dụng. | `ROUND(current_debt / loan_original_amount, 5)` |
| `total_debt_to_income` | Tỷ lệ tổng gánh nặng nợ (tất cả tổ chức) trên thu nhập năm. Chỉ báo toàn diện nhất về khả năng vỡ nợ toàn cục. | `ROUND(total_debt / (stated_monthly_income * 12), 5)` |
| **Nhóm 2: Nhóm hành vi trễ hạn và lịch sử tín dụng** | | |
| `max_dpd_24m` | Số ngày quá hạn lớn nhất trong 2 năm qua. Khách hàng từng trễ hạn lâu thường có xác suất tái vỡ nợ cực cao. | `Integer` |
| `max_dpd_12m` | Số ngày quá hạn lớn nhất trong 1 năm qua. Phản ánh những khó khăn tài chính ngắn hạn gần đây. | `Integer` |
| `max_dpd_3m` | Số ngày quá hạn lớn nhất trong 3 tháng qua. Tín hiệu rủi ro "nóng" báo hiệu khả năng mất thanh toán tức thời. | `Integer` |
| `avg_dpd_24m` | Trung bình số ngày trễ hạn trong 2 năm. Giúp thuật toán phân biệt người thỉnh thoảng quên trả nợ với người trễ hạn có hệ thống. | `Numeric` |
| `avg_dpd_recent` | Trung bình số ngày trễ hạn trong 3 tháng gần nhất, nhấn mạnh hành vi trả nợ hiện tại. | `avg_dpd_3m` |
| `num_active_credit` | Số lượng khoản vay đang còn hiệu lực thanh toán. Thể hiện mức độ phụ thuộc tín dụng hiện tại của người vay. | `Integer` |
| `num_installs_dpd10` | Số kỳ trả góp bị trễ trên 10 ngày. Trễ quá 10 ngày thường do thiếu hụt dòng tiền thực sự thay vì lỗi quên nộp. | `Integer` |
| `num_installs_dpd5` | Số kỳ trả góp bị trễ trên 5 ngày. Dấu hiệu cảnh báo sớm của việc quản lý tài chính cá nhân yếu kém. | `Integer` |
| `avg_payment_12m` | Trung bình số tiền đã thanh toán mỗi tháng trong năm qua, chứng minh năng lực tài chính và thiện chí trả nợ thực tế. | `Numeric` |
| `num_payments_24m` | Tần suất thanh toán trong 24 tháng. Tần suất trả nợ đều đặn tỷ lệ thuận với uy tín tín dụng của khách hàng. | `Integer` |
| `num_incoming_payments_9m` | Tần suất thanh toán gần đây (9 tháng), xác nhận khách hàng vẫn đang duy trì dòng tiền ổn định phục vụ trả nợ. | `Integer` |
| `num_bureau_records` | Tổng số hợp đồng từng ghi nhận trên hệ thống CIC. Khách hàng không có hồ sơ (thin-file) thường khó định lượng rủi ro. | `Integer` |
| `num_active_credit_bureau` | Số lượng hợp đồng đang vay tại các tổ chức khác (theo CIC). Món nợ chồng chéo làm tăng rủi ro vỡ nợ dây chuyền. | `Integer` |
| `total_outstanding_debt` | Tổng dư nợ hiện tại trên toàn bộ hệ thống CIC. | `Numeric` |
| `total_overdue_amount` | Tổng số tiền đang quá hạn tại CIC. Chỉ báo cực kỳ nguy hiểm nếu giá trị lớn hơn 0. | `Numeric` |
| `max_credit_overdue_days` | Số ngày quá hạn tồi tệ nhất từng được ghi nhận trên cả hợp đồng đóng và mở tại CIC. | `GREATEST(max_dpd_bureau_active, max_dpd_bureau_closed)` |
| `max_overdue_amount` | Khoản tiền phạt/quá hạn lớn nhất từng bị ghi nhận tại CIC. | `Numeric` |
| `max_overdue_instls` | Số kỳ trả góp liên tiếp bị trễ hạn cao nhất tại CIC. | `Integer` |
| `total_prolongations` | Tổng số lần khách hàng phải xin gia hạn hợp đồng (cơ cấu lại nợ) tại tổ chức khác do mất khả năng thanh toán. | `Integer` |
| `has_bad_debt` | Cờ đánh dấu nợ xấu ngay lập tức. Khách hàng có cờ này thường bị auto-reject (từ chối tự động) trong thực tế. | `CASE WHEN total_overdue_amount > 0 THEN 1 ELSE 0 END` |
| **Nhóm 3: Nhóm hành vi nội bộ và truy vấn CIC** | | |
| `num_apps_30d` | Số đơn vay đã nộp trong 30 ngày qua. Báo hiệu hiện tượng "cơn đói tín dụng" (Credit Hunger) đầy rủi ro. | `Integer` |
| `num_previous_loans` | Số đơn vay nội bộ đã từng được duyệt trước đây. Thể hiện khách hàng quen thuộc, thường có rủi ro thấp hơn. | `Integer` |
| `previous_default_rate` | Tỷ lệ đơn vay bị từ chối trong lịch sử. Proxy đo lường độ uy tín tích lũy của người vay đối với tổ chức. | `Numeric` |
| `max_prev_app_dpd` | Mức độ trễ hạn nghiêm trọng nhất trên các hợp đồng cũ nội bộ. | `Integer` |
| `avg_prev_app_dpd` | Xu hướng trễ hạn trung bình trên các hợp đồng cũ nội bộ. | `Numeric` |
| `cb_queries_30d` | Số lần tổ chức tín dụng tra cứu hồ sơ CIC trong 1 tháng. Tra cứu liên tục là cờ đỏ báo hiệu rủi ro cao. | `Integer` |
| `cb_queries_90d` | Mức độ tra cứu CIC trong vòng 1 quý. | `Integer` |
| `num_cb_queries` | Tổng số lần tra cứu CIC trong toàn bộ lịch sử tín dụng. | `Integer` |
| **Nhóm 4: Nhóm nhân khẩu học và nghề nghiệp** | | |
| `age_years` | Tuổi thực tế tại thời điểm nộp đơn. Khách hàng quá trẻ hoặc quá già thường có rủi ro vỡ nợ biến động cao. | `Numeric` |
| `years_employed` | Thâm niên làm việc ước lượng. Thâm niên càng cao chứng tỏ dòng tiền trả nợ càng bền vững. | `COALESCE(employment_length, 0)::NUMERIC` |
| `education_ordinal` | Trình độ học vấn. Nhóm học vấn cao thường có ý thức bảo vệ điểm tín dụng cá nhân tốt hơn. | `CASE s.education_level WHEN 'a55475b1' THEN 2 ... ELSE 2 END` |
| `is_homeowner_flag` | Khách hàng sở hữu bất động sản. Yếu tố giảm rủi ro mạnh vì đóng vai trò như tài sản đảm bảo ngầm (implicit collateral). | `CASE WHEN is_homeowner THEN 1 ELSE 0 END` |
| `income_verifiable_flag` | Thu nhập có thể xác minh từ hợp đồng lao động. Nguồn thu nhập minh bạch làm giảm đáng kể nguy cơ vỡ nợ. | `CASE WHEN income_verifiable THEN 1 ELSE 0 END` |
| `is_married_flag` | Tình trạng đã kết hôn. Người có gia đình thường ổn định về chỗ ở và có tinh thần trách nhiệm tài chính cao hơn. | `CASE WHEN is_married THEN 1 ELSE 0 END` |
| `employment_status_grouped` | Phân khúc lao động (Đi làm, Nghỉ hưu...). Theo EDA, nhóm Nghỉ hưu an toàn hơn hẳn do có lương hưu cố định. | `Categorical` |
| `occupation_type` | Đặc thù nghề nghiệp chi tiết. Các ngành nghề rủi ro cao/thấp sẽ được mô hình ML tự động gán trọng số phù hợp. | `Categorical` |
| **Nhóm 5: Nhóm cờ khuyết dữ liệu** | | |
| `high_dti_flag` | Cảnh báo DTI nằm trong top 25% rủi ro nhất toàn tập dữ liệu. Tính ngưỡng động để tránh lạm phát kinh tế làm sai lệch điểm. | `CASE WHEN debt_to_income_ratio > d.p75 THEN 1 ELSE 0 END` |
| `income_missing_flag` | Cờ đánh dấu tệp khách hàng từ chối hoặc không thể cung cấp chứng minh thu nhập. Tín hiệu ẩn (latent signal) về rủi ro. | `CASE WHEN stated_monthly_income IS NULL THEN 1 ELSE 0 END` |
| `dti_missing_flag` | Cờ phụ thuộc khi không tính được DTI. Giúp thuật toán học được quy luật rủi ro từ sự "thiếu minh bạch thông tin". | `CASE WHEN debt_to_income_ratio IS NULL THEN 1 ELSE 0 END` |

*(Ghi chú: Ngoài ra bảng còn chứa 2 trường định danh là `listing_key`, `member_key` và 3 trường metadata kiểm soát `is_default`, `date_decision`, `WEEK_NUM`. Những trường này CHỈ phục vụ truy vấn và đối soát, hoàn toàn KHÔNG đưa vào quá trình huấn luyện nhằm triệt tiêu hoàn toàn rủi ro rò rỉ dữ liệu - Data Leakage).*

Các kỹ thuật Feature Engineering chính được chia thành 6 nhóm phương pháp:

**1. Biến đổi tỷ lệ tài chính (Financial Ratios)**

Từ các giá trị tuyệt đối (thu nhập, khoản vay, nợ), hệ thống tạo ra các tỷ lệ có sức dự báo cao hơn:

| Feature tạo ra | Công thức | Ý nghĩa |
|---|---|---|
| `loan_amount_to_income` | `loan / (monthly_income × 12)` | Tỷ lệ khoản vay so với thu nhập hàng năm |
| `log_monthly_income` | `LN(1 + income)` | Thu nhập sau biến đổi logarit, giảm skewness |
| `payment_to_income` | `= DTI` (alias) | Tỷ lệ trả góp trên thu nhập |
| `current_debt_ratio` | `current_debt / loan_amount` | Mức nợ hiện tại so với khoản vay đang xét |
| `total_debt_to_income` | `total_debt / (income × 12)` | Tổng gánh nặng nợ so với năng lực thu nhập |

Các phép chia đều sử dụng `NULLIF(denominator, 0)` để tránh lỗi chia cho 0, và kết quả được `ROUND` tới 5 chữ số thập phân.

**2. Cờ cảnh báo rủi ro (Risk Flagging)**

- **`high_dti_flag`**: Bằng 1 khi DTI vượt ngưỡng bách phân vị thứ 75 (`quantile_cont(dti, 0.75)`) của toàn bộ tập dữ liệu. Ngưỡng được tính động qua một CTE `dti_threshold` và áp dụng bằng `CROSS JOIN`, đảm bảo ngưỡng phản ánh chính xác phân phối dữ liệu thực tế thay vì dùng hằng số cố định.
- **`has_bad_debt`**: Bằng 1 khi `total_overdue_amount > 0` — tín hiệu trực tiếp về nợ xấu hiện hành.

**3. Tổng hợp DPD đa nguồn (Days Past Due Consolidation)**

Dữ liệu quá hạn tồn tại ở hai nguồn: (a) DPD nội bộ từ `train_static_0` (`max_dpd_24m`, `max_dpd_3m`, `avg_dpd_recent`) và (b) DPD ngoại vi từ Bureau aggregate (`max_dpd_bureau_active`, `max_dpd_bureau_closed`). Tại tầng Gold, hệ thống hợp nhất hai nguồn bằng:

```sql
GREATEST(s.max_dpd_bureau_active, s.max_dpd_bureau_closed) AS max_credit_overdue_days
```

Phép `GREATEST` lấy giá trị lớn hơn giữa DPD trên hợp đồng đang hoạt động và đã đóng — đảm bảo mô hình nắm bắt được mức quá hạn nghiêm trọng nhất từng xảy ra trên bất kỳ hợp đồng nào tại Bureau.

**4. Mã hóa thứ tự cho biến phân loại (Ordinal Encoding)**

Trường `education_927M` trong dữ liệu gốc chứa các giá trị ẩn danh (masked) như `a55475b1`, `P97_36_170`. Hệ thống chuyển đổi thành biến thứ tự `education_ordinal` (1–5) dựa trên phân bố tần suất:

| Giá trị ẩn danh | Tần suất | Ordinal | Giả định trình độ |
|---|---:|:---:|---|
| `a55475b1` | 798K | 2 | Trung học phổ thông |
| `P97_36_170` | 409K | 3 | Trung cấp / Cao đẳng |
| `P33_146_175` | 259K | 4 | Đại học |
| `P106_81_188` | 55K | 5 | Sau đại học |
| `P17_36_170` | 5K | 1 | Dưới trung học |
| `P157_18_172` | 631 | 1 | Dưới trung học |

Logic giả định: giá trị xuất hiện phổ biến nhất tương ứng trình độ phổ thông (đông đảo nhất trong dân số), giá trị hiếm hơn tương ứng trình độ chuyên sâu. Các cờ boolean (`is_homeowner_flag`, `income_verifiable_flag`, `is_married_flag`) cũng được chuyển từ kiểu `BOOLEAN` sang `INTEGER` (0/1) để tương thích với đầu vào ML.

**5. Cờ khuyết dữ liệu (Missing Indicator Flags)**

Hai cột đặc biệt được tạo riêng để mô hình phân biệt giữa "giá trị thực bằng 0" và "không có dữ liệu":
- `income_missing_flag`: Bằng 1 khi `stated_monthly_income IS NULL`.
- `dti_missing_flag`: Bằng 1 khi `debt_to_income_ratio IS NULL`.

Kỹ thuật này (còn gọi là **missing indicator method**) cho phép thuật toán ML tự học xem "thiếu thông tin thu nhập" có phải là yếu tố rủi ro hay không — thay vì buộc hệ thống phải đoán giá trị thay thế bằng imputation.

**6. Analytical Views phục vụ Dashboard**

Ngoài bảng Gold chính, file SQL còn tạo 3 view phân tích trực tiếp trên DuckDB, phục vụ trực quan hóa dữ liệu cho trang Admin Dashboard trên ứng dụng Web:

| View | Mục đích | Phân nhóm |
|---|---|---|
| `vw_v2_dti_vs_default` | Tỷ lệ vỡ nợ theo dải DTI | Low (<0.2), Medium (0.2–0.5), High (0.5–1.0), Very High (1.0+) |
| `vw_v2_employment_vs_default` | Tỷ lệ vỡ nợ theo tình trạng việc làm | 5 nhóm employment_status |
| `vw_v2_dpd_vs_default` | Tỷ lệ vỡ nợ theo mức DPD | No DPD, 1–30, 31–90, 90+ ngày |

Các view này được truy vấn trực tiếp bởi backend API để hiển thị biểu đồ phân tích rủi ro, không cần tính toán lại tại thời điểm request.

### 3.3.5 Kiểm định chất lượng dữ liệu (Automated Data Validation)

Trong kiến trúc Data Engineering, việc kiểm soát toàn vẹn dữ liệu (Data Integrity) là yêu cầu bắt buộc trước quá trình huấn luyện mô hình học máy. Hệ thống triển khai script `validate_data.py` đóng vai trò như một automated quality gate, thực thi tự động ngay sau quy trình ETL tại tầng Silver nhằm ngăn chặn các dị thường dữ liệu (data anomalies).

Quá trình kiểm định được thiết lập dựa trên 5 quy tắc chuẩn hóa (Validation Rules):

| Quy tắc kiểm định (Validation Rule) | Ngưỡng yêu cầu (Threshold) | Mục đích kỹ thuật (Technical Purpose) |
|---|---|---|
| **1. Row count** | ≥ 100,000 dòng | Đảm bảo tính đầy đủ của mẫu dữ liệu, loại trừ lỗi mất mát bản ghi trong quá trình phân tích ETL. |
| **2. Schema consistency** | Tồn tại đủ 9 trường cốt lõi | Bảo vệ luồng dữ liệu khỏi lỗi KeyError do cấu trúc bảng thay đổi bất thường (schema drift). |
| **3. Null rate check** | Null ≤ 40% (Target = 0%) | Duy trì mật độ thông tin tối thiểu cho các đặc trưng tài chính; đảm bảo nhãn dự báo không bị khuyết thiếu. |
| **4. Default rate bounds** | [1% – 50%] | Cảnh báo sớm các lỗi gán nhãn hàng loạt (all zeros/all ones) bắt nguồn từ sai lệch logic SQL. |
| **5. Categorical integrity** | Nhóm Employment = 5 classes | Xác thực tính chặt chẽ của các phép biến đổi phân loại (categorical mapping). |

Hệ thống hoạt động theo cơ chế fail-fast: nếu bất kỳ quy tắc nào vi phạm ngưỡng thiết lập, pipeline sẽ lập tức kích hoạt lỗi và đình chỉ tiến trình. Khi bộ dữ liệu vượt qua các ngưỡng integrity khắt khe này, nó được đưa vào phân tích chuyên sâu nhằm rút ra các insight kinh doanh và định hướng cho mô hình dự báo.

> **[🖼️ Figure 3.1: Automated Data Validation Flow]**

---

## 3.4 Phân tích dữ liệu & Nhận định nghiệp vụ (Exploratory Data Analysis)

### 3.4.1 Phân bố tỷ lệ vỡ nợ và thách thức mất cân bằng nhãn

Tập dữ liệu tại tầng Gold đạt quy mô 1,526,659 quan sát hợp lệ. Phân tích phân bố nhãn mục tiêu cho thấy tỷ lệ vỡ nợ (default rate) ghi nhận ở mức xấp xỉ 3.14%.

Từ góc độ thống kê, sự phân bố này biểu hiện đặc trưng của hiện tượng mất cân bằng nhãn (Class Imbalance). Đối với bài toán phân loại nhị phân (Binary Classification), sự chênh lệch lớn giữa lớp đa số (performing loans) và lớp thiểu số (non-performing loans) tạo ra nghịch lý độ chính xác (Accuracy Paradox). Một mô hình cơ bản có thể đạt độ chính xác cao bằng cách thiên vị dự đoán toàn bộ quan sát thuộc lớp đa số, song lại hoàn toàn mất khả năng nhận diện rủi ro cốt lõi. Do đó, hiện trạng phân bố này đặt ra yêu cầu thiết yếu về việc áp dụng các kỹ thuật cân bằng trọng số (Class Weights) và điều chỉnh hàm mục tiêu trong quá trình tối ưu hóa thuật toán.

Bên cạnh đó, quá trình EDA cũng ghi nhận tỷ lệ khuyết thiếu dữ liệu (Null rate) lớn nhất xấp xỉ 33.49% tại các biến tài chính. Sự xuất hiện phổ biến của các giá trị Null phản ánh thực tế về hành vi không khai báo hoặc thiếu thông tin lịch sử của người vay. Dưới lăng kính Machine Learning, việc bảo lưu trạng thái thiếu hụt này thông qua các biến cờ (Missing Indicators) cung cấp thêm tín hiệu phân loại, cho phép mô hình học được mối tương quan tiềm ẩn giữa mức độ minh bạch thông tin và xác suất vỡ nợ.

> **[🖼️ Figure 3.2: Rows in Silver vs Gold Dataset]**
> **[🖼️ Figure 3.3: Gold Feature Null-rate Distribution]**

### 3.4.2 Phân tích áp lực nợ (DTI)

Tỷ lệ nợ trên thu nhập (Debt-to-Income Ratio - DTI) là một chỉ báo nền tảng phản ánh áp lực tài chính của người vay. Số liệu thống kê từ tập dữ liệu thể hiện mối tương quan đồng biến giữa tỷ lệ DTI và mức độ rủi ro tín dụng:

| Phân khúc DTI (DTI Band) | Tỷ lệ vỡ nợ (Default Rate) |
|---|:---:|
| **Low (<0.2)** | 3.04% |
| **Medium (0.2-0.5)** | 3.78% |
| **High (0.5-1.0)** | 4.70% |
| **Very High (1.0+)** | 6.28% |

Dữ liệu cho thấy tỷ lệ vỡ nợ tăng dần từ 3.04% ở nhóm Low lên 6.28% ở nhóm Very High. Về mặt nghiệp vụ, chỉ số DTI cao tương đồng với sự suy giảm năng lực trả nợ (Reduced repayment capacity). Việc phần lớn thu nhập bị phân bổ cho các nghĩa vụ nợ hiện tại làm giảm biên độ an toàn tài chính (Financial resilience), khiến khách hàng có xu hướng nhạy cảm hơn trước các cú sốc kinh tế vĩ mô hoặc biến cố cá nhân. Trong hoạt động thẩm định (Underwriting), DTI đóng vai trò như một affordability indicator quan trọng để đánh giá giới hạn cấp tín dụng.

> **[🖼️ Figure 3.4: DTI vs Default Rate Correlation]**

### 3.4.3 Phân tích lịch sử tín dụng (DPD)

Lịch sử thanh toán trễ hạn (Days Past Due - DPD) cung cấp dữ kiện quan sát trực tiếp về hành vi tín dụng quá khứ. 

| Mức độ trễ hạn quá khứ (DPD Band) | Tỷ lệ vỡ nợ (Default Rate) |
|---|:---:|
| **No DPD** | 2.49% |
| **1-30 days** | 4.04% |
| **31-90 days** | 12.20% |
| **90+ days** | 12.78% |

Phân tích cho thấy sự phân hóa rủi ro sâu sắc giữa các phân khúc. Đáng chú ý là sự gia tăng đáng kể của tỷ lệ vỡ nợ khi khách hàng chuyển từ nhóm trễ hạn ngắn (1-30 days: 4.04%) sang nhóm trễ hạn trung hạn (31-90 days: 12.20%). Sự biến động này minh họa cho một Risk escalation threshold (Ngưỡng leo thang rủi ro). Việc khách hàng vượt qua ngưỡng 30 ngày thường phản ánh sự chuyển đổi từ các lỗi thanh toán mang tính thời điểm sang trạng thái mất khả năng thanh toán hệ thống (Non-performing loan - NPL). Do đó, mức độ nghiêm trọng của lịch sử trễ hạn (Delinquency severity) biểu hiện tương quan thuận với xác suất vỡ nợ tương lai, đóng vai trò là behavioral risk indicator chủ lực trong thẩm định tín dụng.

> **[🖼️ Figure 3.5: DPD Risk Escalation Threshold]**

### 3.4.4 Phân tích nhân khẩu học & tài chính

Việc đối chiếu xác suất vỡ nợ với trạng thái việc làm cung cấp các insight đa chiều về tính ổn định tài chính:

| Trạng thái việc làm (Employment) | Tỷ lệ vỡ nợ (Default Rate) |
|---|:---:|
| **Employed** | 3.51% |
| **Not employed** | 3.41% |
| **Self-employed** | 3.04% |
| **Retired** | 1.83% |

Dữ liệu quan sát cho thấy nhóm khách hàng hưu trí (Retired) biểu hiện rủi ro thấp nhất (1.83%), trong khi nhóm người lao động làm công ăn lương (Employed) lại ghi nhận tỷ lệ cao nhất (3.51%). Hiện tượng thống kê này có thể được lý giải thông qua đặc tính ổn định thu nhập (Income stability). Nhóm hưu trí sở hữu dòng tiền ổn định ít chịu tác động bởi thị trường lao động, kèm theo thói quen chi tiêu thận trọng, tạo nên mức độ ổn định thanh toán (Repayment stability) cao. Ngược lại, thu nhập của nhóm Employed chịu ảnh hưởng trực tiếp từ tính bất định của việc làm (Employment uncertainty) và áp lực chi tiêu thường nhật. Do đó, đặc điểm việc làm cung cấp supplementary risk signal bổ trợ cho các tín hiệu tài chính cốt lõi.

> **[🖼️ Figure 3.6: Employment vs Default Risk Distribution]**

### 3.4.5 Nhận định nghiệp vụ rút ra từ dữ liệu

Tổng hợp các kết quả phân tích khám phá, bộ dữ liệu cung cấp 3 cơ sở chính:

1. **Hierarchy of Evidence:** Phân tích xác nhận tính phân tầng trong các chỉ báo rủi ro. Các tín hiệu hành vi tín dụng quá khứ (Bureau/DPD signals) cho thấy sức mạnh dự báo vượt trội so với các chỉ báo nhân khẩu học (Demographic signals).
2. **Early-stage underwriting filtering:** Sự phân hóa rủi ro rõ nét tại các ngưỡng cực đoan của DTI và DPD cho phép thiết lập các quy tắc từ chối tự động (Auto-reject screening) ở giai đoạn đầu của phễu thẩm định.
3. **ML Readiness:** Chất lượng của tập dữ liệu tại tầng Gold với các feature được chuẩn hóa, đi kèm tín hiệu Missing Indicators, cung cấp nền tảng vững chắc cho quá trình lập mô hình dự báo (Predictive modeling).

**Hạn chế của phân tích:** Cần lưu ý rằng Exploratory Data Analysis (EDA) chỉ nhằm mục đích đo lường các mối tương quan thống kê (Statistical correlation) hiện hữu trong tập dữ liệu lịch sử. Kết quả này không mang tính khẳng định về quan hệ nhân quả (Causality) và không thay thế cho các nghiên cứu nguyên nhân kinh tế vĩ mô chuyên sâu.

Những insight này tạo tiền đề quan trọng cho việc lựa chọn feature engineering và kiến trúc mô hình ở Chương IV.
