# Đánh giá báo cáo Loan_ETL_final_v2.md vs. Project thực tế

## Tổng quan

Báo cáo `Loan_ETL_final_v2.md` (~246KB, 1968 dòng) mô tả hệ thống **CreditIntel** — một full-stack loan management & risk assessment system. Sau khi đối chiếu chi tiết với mã nguồn, **nhìn chung báo cáo viết rất tốt, phản ánh chính xác hệ thống thực tế**. Tuy nhiên có một số sai lệch, thiếu sót và điểm cần cải thiện.

---

## I. Những phần viết CHÍNH XÁC và tốt ✅

### 1. Kiến trúc tổng thể
- Mô tả đúng stack: FastAPI backend, React + Vite frontend, PostgreSQL (Supabase), DuckDB (ETL), Qdrant (RAG), OpenRouter (LLM).
- Đúng vai trò từng thành phần: LightGBM risk model + LR scorecard, joblib để nạp `.pkl`.

### 2. ETL Pipeline (Medallion Architecture)
- Mô tả chính xác 3 lớp Bronze → Silver → Gold.
- Đúng file pipeline [pipeline.py](file:///c:/KH086/HQTCSDL/Loan_ETL/machinelearning/etl/pipeline.py): gọi tuần tự `bronze()`, `silver()`, `gold()`.
- Đúng các file SQL: [transform_silver_hcv2.sql](file:///c:/KH086/HQTCSDL/Loan_ETL/machinelearning/database/transform_silver_hcv2.sql) và [transform_gold_hcv2.sql](file:///c:/KH086/HQTCSDL/Loan_ETL/machinelearning/database/transform_gold_hcv2.sql).
- Đúng bảng Gold output: `gold.hc_features_v2` với 35 features.

### 3. Machine Learning
- Đúng 2 model: LightGBM (`retrain_customer_model.py`) và LR Scorecard (`train_scorecard.py`).
- Đúng output: `customer_risk_model.pkl` và `scorecard_model.pkl` trong `machinelearning/ml/models/`.
- Đúng 35 features cho LightGBM, 30 features cho Scorecard.
- Đúng ngưỡng auto-reject: `prob > 0.4` — code xác nhận tại [application_service.py:287](file:///c:/KH086/HQTCSDL/Loan_ETL/backend/services/application_service.py#L287).

### 4. Backend Architecture
- Đúng cấu trúc thư mục: `api/routers/`, `services/`, `models/`, `schemas/`, `core/`, `db/`, `rag/`.
- Đúng các router: `auth`, `applications`, `admin`, `chat`, `credit_score`, `cic`.
- Đúng các service chính: `application_service`, `ml_service`, `credit_score_service`, `admin_service`, `chat_service`, `model_feature_builder`, `loan_suggestion_service`, `cic_service`, `document_service`.

### 5. Máy trạng thái (State Machine)
- Code xác nhận chính xác luồng:
  - Submit → `AUTO_REJECTED` (prob > 0.4) hoặc `PENDING_REVIEW` (prob ≤ 0.4) — [application_service.py:287](file:///c:/KH086/HQTCSDL/Loan_ETL/backend/services/application_service.py#L287)
  - CIC blacklist → `AUTO_REJECTED` ngay — [application_service.py:201](file:///c:/KH086/HQTCSDL/Loan_ETL/backend/services/application_service.py#L201)
  - Admin approve: `PENDING_REVIEW` → `AWAITING_INFO` — [admin_service.py:145](file:///c:/KH086/HQTCSDL/Loan_ETL/backend/services/admin_service.py#L145)
  - Admin reject: `PENDING_REVIEW` → `ADMIN_REJECTED` — [admin_service.py:169](file:///c:/KH086/HQTCSDL/Loan_ETL/backend/services/admin_service.py#L169)
  - Customer submit info: `AWAITING_INFO` → `INFO_SUBMITTED` — [application_service.py:532](file:///c:/KH086/HQTCSDL/Loan_ETL/backend/services/application_service.py#L532)
  - Admin disburse: `INFO_SUBMITTED` → `DISBURSED` — [admin_service.py:369](file:///c:/KH086/HQTCSDL/Loan_ETL/backend/services/admin_service.py#L369)

### 6. RAG Architecture
- Đúng các thành phần: `ingest.py`, `chunking.py`, `retriever.py`, `reranker.py`, `context_builder.py`, `memory.py`, `guardrails.py`, `chain.py`, `router.py`, `personalizer.py`, `query_rewriter.py`.
- Đúng collection name: `creditintel-kb`.
- Đúng parent-child chunking strategy.
- Đúng hybrid search (dense + sparse BM25).

### 7. Frontend
- Đúng cấu trúc: `pages/customer/` và `pages/admin/`.
- Đúng các trang customer: Landing, Login, Register, Dashboard, Apply, Chat, History, ApplicationDetail, SubmitInfo.
- Đúng các trang admin: Dashboard, PendingList, ApplicationList, ApplicationDetail, PersonalInfoView.
- Đúng Zustand auth store, Axios service layer.

---

## II. Những SAI LỆCH phát hiện được ⚠️

### 1. Máy trạng thái — Báo cáo mô tả SAI luồng

> [!WARNING]
> **Sai lệch nghiêm trọng nhất:** Báo cáo mô tả sai luồng trạng thái đơn vay.

**Báo cáo viết (dòng 366-370):**
> "Quản trị viên có hai lựa chọn: phê duyệt để chuyển đơn sang trạng thái chờ bổ sung thông tin, hoặc từ chối thủ công. Khi đơn ở trạng thái chờ bổ sung thông tin, khách hàng nộp tiếp hồ sơ nhân thân, đơn chuyển sang trạng thái đã nộp thông tin. Cuối cùng, quản trị viên **giải ngân** để đưa đơn về trạng thái đã giải ngân."

**Code thực tế:**
- `PENDING_REVIEW` → Admin approve → `AWAITING_INFO`
- `AWAITING_INFO` → Customer submit → `INFO_SUBMITTED`
- `INFO_SUBMITTED` → Admin disburse → `DISBURSED`

**Sai lệch:** Báo cáo không nhắc đến trạng thái `INFO_SUBMITTED`, mà viết dường như khách hàng nộp xong → ngay lập tức `APPROVED` (dòng 368: "Khách hàng phản hồi AWAITING_INFO để đạt APPROVED"). **Thực tế không có trạng thái `APPROVED` trong code** — trạng thái sau khi customer nộp info là `INFO_SUBMITTED`, không phải `APPROVED`.

**Sơ đồ (dòng 370)** ghi:
> `PENDING_REVIEW / AUTO_REJECTED → AWAITING_INFO → INFO_SUBMITTED → DISBURSED`

Sơ đồ này *gần đúng* nhưng phần mô tả văn bản (dòng 366-368) lại viết sai, mâu thuẫn với sơ đồ.

### 2. Dashboard summary — Trạng thái `APPROVED` trong code

Trong [admin_service.py:197](file:///c:/KH086/HQTCSDL/Loan_ETL/backend/services/admin_service.py#L197), code đếm `status == "APPROVED"` cho dashboard, nhưng **không có transition nào đưa đơn về trạng thái `APPROVED`**. Điều này có nghĩa `approved_today` sẽ luôn bằng 0. Báo cáo ghi "số đơn đã duyệt" nhưng thực tế metric này trong code bị "dead" vì không có đơn nào đạt trạng thái `APPROVED`.

### 3. Báo cáo thiếu Sanity Override mechanism

**Báo cáo không đề cập** cơ chế `_apply_sanity_override()` trong [application_service.py:34-80](file:///c:/KH086/HQTCSDL/Loan_ETL/backend/services/application_service.py#L34-L80). Đây là một mechanism quan trọng giúp cap probability xuống 0.15 khi khoản vay quá nhỏ so với thu nhập. Báo cáo chỉ nói "ngưỡng 0.4 cho từ chối tự động" mà không nhắc đến business rule override này.

### 4. CIC Service — Báo cáo viết đúng nhưng thiếu

Báo cáo có nhắc CIC nhưng chưa mô tả rõ luồng `cic_service.py`:
- `lookup_by_cccd()` — tra CCCD trong Bureau DB.
- `apply_cic_to_payload()` — ghi đè dữ liệu tự khai bằng dữ liệu CIC.
- `derive_bureau_features()` — suy ra các feature hành vi từ lịch sử khoản vay CIC.

Đây là thành phần rất quan trọng nhưng trong phần mô tả service (mục VI.1.4), chỉ được nhắc một dòng.

### 5. Loan Adjustment Tool — Cấu trúc code chi tiết hơn

Báo cáo mô tả Loan Adjustment Tool rất tốt ở mức conceptual, nhưng chưa nhắc đến:
- [loan_adjustment_reasoner.py](file:///c:/KH086/HQTCSDL/Loan_ETL/backend/services/loan_adjustment_reasoner.py) — LLM soft-propose.
- [loan_adjustment_tool.py](file:///c:/KH086/HQTCSDL/Loan_ETL/backend/services/loan_adjustment_tool.py) — orchestrator + hard-verify.

Hai file này tách bạch rõ ràng nhưng báo cáo viết chung chung.

### 6. `synthetic_service.py` — Không được đề cập

Service [synthetic_service.py](file:///c:/KH086/HQTCSDL/Loan_ETL/backend/services/synthetic_service.py) (24KB — lớn nhất trong services/) không được nhắc tới trong báo cáo. Cần xác minh vai trò của service này: nếu nó liên quan đến CIC mock data generation, thì nên được nhắc đến.

---

## III. Những điểm CẦN CẢI THIỆN 📝

### A. Về nội dung

| # | Vấn đề | Chi tiết | Mức độ |
|---|--------|----------|--------|
| 1 | **Sơ đồ máy trạng thái sai** | Mô tả văn bản viết "APPROVED" nhưng code dùng `AWAITING_INFO` → `INFO_SUBMITTED` → `DISBURSED`. Cần sửa lại cả văn bản và sơ đồ tại dòng 366-370 | 🔴 Nghiêm trọng |
| 2 | **Thiếu Sanity Override** | Cơ chế business rule override (cap prob=0.15) là quyết định thiết kế quan trọng, cần mô tả ở mục IV hoặc VI | 🟡 Quan trọng |
| 3 | **Thiếu `synthetic_service.py`** | Service 24KB không được nhắc tới | 🟡 Quan trọng |
| 4 | **Thiếu `query_rewriter.py`** | Có file riêng nhưng báo cáo chỉ nhắc chung trong retrieval pipeline | 🟢 Nhỏ |
| 5 | **Thiếu RAG eval tooling** | Project có `eval_dataset.py`, `eval_metrics.py`, `eval_runner.py` trong rag/, nhưng báo cáo chỉ nêu kết quả mà không mô tả tooling | 🟢 Nhỏ |
| 6 | **CIC router chưa được nhắc** | `api/routers/cic.py` và `schemas/cic.py` tồn tại trong code nhưng báo cáo không liệt kê trong bảng API | 🟢 Nhỏ |
| 7 | **Evaluate/Confirm two-phase pattern** | Code có 2 endpoint rõ ràng (`evaluate` + `confirm`) với logic reuse prediction, báo cáo chỉ ghi chung là "nộp đơn" | 🟡 Quan trọng |

### B. Về hình thức

| # | Vấn đề | Gợi ý |
|---|--------|-------|
| 1 | **Hình ảnh placeholder** | Tất cả hình đều là `_[Hình X.Y]_` placeholder. Cần chèn ảnh thật (screenshot UI, sơ đồ kiến trúc, biểu đồ EDA) | 🔴 |
| 2 | **Bảng thuật ngữ thiếu** | Một số thuật ngữ dùng trong báo cáo nhưng không có trong bảng: `SHAP`, `binary search`, `CTE`, `CROSS JOIN`, `pending_action` | 🟢 |
| 3 | **Tài liệu tham khảo** | Mục [12] reference sai tên dataset — đúng phải là "Home Credit Credit Risk **Model Stability**" (Kaggle 2024), không phải "Home Credit Default Risk" (Kaggle 2018). Đây là 2 cuộc thi khác nhau | 🟡 |
| 4 | **Mục lục link** | Các anchor link (`#_Toc231763504`) là từ Word export, không hoạt động trong Markdown thuần | 🟢 |

### C. Về kỹ thuật nên bổ sung

| # | Chủ đề | Lý do |
|---|--------|-------|
| 1 | **Two-phase submit (evaluate + confirm)** | Đây là design pattern quan trọng để tránh desync giữa UI và DB. Code rất phức tạp nhưng báo cáo không nhắc |
| 2 | **CIC enrichment pipeline** | Luồng `lookup_by_cccd` → `apply_cic_to_payload` → `derive_bureau_features` là core flow, nên có sơ đồ riêng |
| 3 | **Model feature contract enforcement** | `check_customer_model_contract.py` và `validate_data.py` nên được nhắc rõ hơn ở phần quality assurance |
| 4 | **FICO score computation timing** | Code gọi `_compute_and_save_fico()` ngay sau commit. Nên mô tả rõ: Scorecard chạy đồng bộ sau LightGBM, kết quả lưu vào `fico_score` column |

---

## IV. Đánh giá tổng kết

### Điểm mạnh
- ✅ **Rất chi tiết** về ETL, ML, và RAG — ba phần chính của project.
- ✅ **Chất lượng viết chuyên nghiệp** — ngôn ngữ học thuật chuẩn, dùng đúng thuật ngữ.
- ✅ **Feature dictionary** rất đầy đủ, khớp với code.
- ✅ **RAG phần viết hay nhất** — mô tả kiến trúc, chunking, hybrid search, reranking, context builder rất sâu và đúng với code thực tế.
- ✅ **So sánh mô hình** (LightGBM vs XGBoost vs RF) viết tốt.
- ✅ **Kết quả eval RAG** minh bạch với 31 test cases.

### Điểm yếu
- ❌ **Sơ đồ máy trạng thái sai** — sai lệch giữa mô tả văn bản và code.
- ❌ **Thiếu hình ảnh** — toàn bộ placeholder.
- ❌ **Bỏ sót một số service quan trọng** (`synthetic_service`, sanity override).
- ❌ **Phần VI (Triển khai hệ thống) viết mỏng** so với phần III-V — có thể bổ sung thêm về database schema, API contract, frontend component tree.

### Điểm đánh giá

| Tiêu chí | Điểm (1-10) |
|----------|-------------|
| **Chính xác so với code** | **8/10** — phần lớn đúng, có 1 sai lệch nghiêm trọng (state machine) |
| **Độ sâu kỹ thuật** | **9/10** — ETL, ML, RAG viết rất chuyên sâu |
| **Độ bao phủ** | **7/10** — thiếu một số service và mechanism |
| **Hình thức** | **6/10** — thiếu hình, link mục lục hỏng, reference sai |
| **Tổng** | **~7.5/10** |

---

## V. Hành động khuyến nghị (ưu tiên)

1. 🔴 **Sửa mô tả máy trạng thái** (dòng 366-370): Thay `APPROVED` bằng luồng đúng `AWAITING_INFO → INFO_SUBMITTED → DISBURSED`.
2. 🔴 **Chèn hình ảnh thật** cho tất cả `_[Hình ...]_` placeholder.
3. 🟡 **Bổ sung mục Sanity Override** ở phần IV hoặc VI.
4. 🟡 **Sửa tài liệu tham khảo [12]**: "Home Credit Credit Risk Model Stability" ≠ "Home Credit Default Risk".
5. 🟡 **Bổ sung two-phase submit** (`evaluate` → `confirm`) trong phần VI.
6. 🟡 **Bổ sung `synthetic_service`** và `cic_service` chi tiết hơn.
7. 🟢 **Sửa link mục lục** để hoạt động trong Markdown.
