# Tham khảo Chi tiết: `train_model.py` và `predict_engine.py`

Tài liệu này mô tả chi tiết hai module ML chính trong dự án: `ml/train_model.py` và `ml/predict_engine.py`.
Nội dung bao gồm mục đích, luồng xử lý, tham số, đầu vào/đầu ra, dữ liệu cần thiết và các chỉ số đánh giá.

## 1. `ml/train_model.py`

### Mục đích
- Train model RandomForest cho bài toán dự đoán rủi ro vỡ nợ.
- Lấy dữ liệu từ bảng `gold.loan_features_v1`.
- Lưu artifact model gồm pipeline, danh sách feature và ngưỡng rủi ro vào `ml/models/loan_risk_model.pkl`.

### Luồng chính
1. Kết nối PostgreSQL bằng engine từ `utils/db_connection.get_engine()`.
2. Đọc toàn bộ dữ liệu từ `gold.loan_features_v1`.
3. Kiểm tra tồn tại cột mục tiêu `is_default`.
4. Chuẩn bị dữ liệu:
   - Loại bỏ các cột `is_default` và `loan_id` nếu có.
   - Giữ lại chỉ các cột số (numeric) để tránh lỗi với `StandardScaler`.
   - Điền giá trị null bằng median của từng cột.
5. Chia tập dữ liệu train/test:
   - `test_size=0.2`
   - `random_state=42`
   - `stratify=y`
6. Xây dựng pipeline:
   - `StandardScaler()`
   - `RandomForestClassifier(...)`
7. Huấn luyện pipeline với `X_train`, `y_train`.
8. Đánh giá trên tập test với các chỉ số:
   - `ROC-AUC`
   - `F1-Score`
   - `classification_report`
9. Lưu artifact chứa:
   - `pipeline`
   - `feature_cols`
   - `thresholds` (`low`, `high`)

### Tham số Model cố định
- `n_estimators=200`
- `max_depth=15`
- `min_samples_leaf=5`
- `min_samples_split=10`
- `random_state=42`
- `n_jobs=-1`
- `class_weight='balanced'`

### Ngưỡng rủi ro
- `LOW_THRESHOLD = 0.2`
- `HIGH_THRESHOLD = 0.4`

Các giá trị này lấy từ `config/settings.yaml` trong mục `ml`, nếu không tồn tại sẽ dùng mặc định.

### Input
- Bảng SQL: `gold.loan_features_v1`
- Dữ liệu phải có cột mục tiêu `is_default`.
- Các cột feature phải là numeric hoặc có thể lọc xuống numeric.

### Output
- File artifact: `ml/models/loan_risk_model.pkl`
- Artifact chứa:
  - `pipeline`: pipeline huấn luyện
  - `feature_cols`: danh sách các cột feature dùng trong model
  - `thresholds`: ngưỡng rủi ro {low, high}

### Các chỉ số đánh giá
- `ROC-AUC`: Đánh giá khả năng phân biệt giữa hai lớp default / non-default.
- `F1-Score`: Cân bằng giữa precision và recall khi phân loại.
- `classification_report`: Bao gồm precision, recall, f1-score và support cho mỗi lớp.

### Quy tắc quan trọng
- Chia dữ liệu stratified trước khi fit.
- Loại bỏ cột không numeric trước khi scale.
- Điền missing value bằng median để tránh NaN.
- Lưu feature order để `predict_engine.py` dùng chính xác.

---

## 2. `ml/predict_engine.py`

### Mục đích
- Nạp model đã huấn luyện.
- Lấy feature cho một `loan_number` từ `gold.loan_features_v1`.
- Dự đoán xác suất vỡ nợ.
- Tính toán mức độ rủi ro, điểm nội bộ và đề xuất số tiền/kỳ hạn.
- Lưu kết quả vào bảng `core.risk_assessment`.

### Luồng chính
1. Kiểm tra `loan_number` tồn tại trong `core.loans`.
2. Nạp artifact model từ `ml/models/loan_risk_model.pkl`.
3. Đọc dữ liệu feature từ `gold.loan_features_v1` theo `listing_key`.
4. Loại bỏ các cột không dùng cho model: `is_default`, `listing_key`, `member_key`, `loan_number`, `loan_key`.
5. Đồng bộ cột với `feature_cols` đã lưu:
   - Thêm cột thiếu với giá trị 0.
   - Loại bỏ cột lạ.
   - Sắp xếp cột theo đúng order.
6. Điền null bằng median.
7. Dự đoán với `pipeline.predict_proba(X)`.
8. Tính toán:
   - `probability_of_default`
   - `risk_level` (Low/Medium/High)
   - `risk_score_internal`
   - `recommended_amount`
   - `recommended_term`
9. Lưu/ghi đè vào `core.risk_assessment`.

### Input chính
- `loan_number`: integer, tương đương với `loan_number` VARCHAR trong `core.loans`.
- Model artifact file `ml/models/loan_risk_model.pkl`.
- Dữ liệu feature trong `gold.loan_features_v1` có `listing_key` tương ứng.

### Output
- Kết quả trả về dạng dict bao gồm:
  - `listing_key`
  - `loan_number`
  - `probability_of_default`
  - `risk_level`
  - `risk_score_internal`
  - `recommended_amount`
  - `recommended_term`
  - `assessment_date`
- Bản ghi được ghi vào bảng `core.risk_assessment` với cột:
  - `listing_key`
  - `loan_number`
  - `probability_of_default`
  - `risk_score_internal`
  - `risk_level`
  - `recommended_amount`
  - `recommended_term`
  - `assessment_date`

### Business rules và đề xuất
- `get_risk_level(pd_val, thresholds)`:
  - `< low`: `Low`
  - `<= high`: `Medium`
  - `> high`: `High`
- `recommend_loan(pd_val, thresholds)`:
  - Low risk → `15000` USD, `36` months
  - Medium risk → `8000` USD, `24` months
  - High risk → `3000` USD, `12` months

### Tương thích dữ liệu
- `loan_number` input là số nguyên nhưng so sánh với `loan_number` VARCHAR trong DB.
- Nếu `feature_cols` mất đồng bộ với `gold.loan_features_v1`, module sẽ:
  - Báo warning nếu thiếu cột.
  - Tự thêm cột thiếu với giá trị 0.
  - Loại bỏ cột phụ.

### Tham số CLI
- Gọi được trực tiếp bằng command line:
  - `python ml/predict_engine.py 65928`
- Nếu không có tham số hoặc giá trị không hợp lệ, module hiển thị hướng dẫn.

### Các lưu ý quan trọng
- `ml/models/loan_risk_model.pkl` phải tồn tại; nếu không cần chạy `ml/train_model.py` trước.
- `core.loans` phải chứa `loan_number` được yêu cầu.
- `gold.loan_features_v1` phải chứa dữ liệu feature cho `listing_key` tương ứng.
- `predict_engine.py` dựa vào độ khớp cột giữa dữ liệu hiện tại và model artifact.

---

## 3. Mối liên hệ giữa hai module

- `train_model.py` tạo artifact model và lưu danh sách `feature_cols` cùng `thresholds`.
- `predict_engine.py` nạp artifact này, đảm bảo feature alignment khi dự đoán.
- Nếu schema feature thay đổi, nên chạy lại `train_model.py` để tái tạo artifact.

## 4. Checklist khi sử dụng

- [ ] Đã thiết lập `config/settings.yaml` đúng PostgreSQL.
- [ ] Đã chạy `database/init_database.sql`.
- [ ] Đã chạy ETL đến `gold.loan_features_v1`.
- [ ] Đã chạy `python ml/train_model.py`.
- [ ] Đã gọi `python ml/predict_engine.py <loan_number>` hoặc qua UI.

## 5. Gợi ý mở rộng

- Có thể thêm log chi tiết hơn cho `train_model.py` để ghi lại `feature_cols` và distribution dữ liệu.
- Có thể mở rộng `recommend_loan()` thành module scoring thực tế theo quy tắc nghiệp vụ.
- Nên kiểm tra thêm dữ liệu đầu vào trong `predict_engine.py` để đảm bảo không có NaN không mong muốn.
