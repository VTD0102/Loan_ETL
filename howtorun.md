# Hướng dẫn chạy dự án Loan_ETL toàn tập trên Windows

Tài liệu này hướng dẫn chi tiết từng bước để khởi chạy dự án, từ lúc clone code về đến lúc hệ thống hoạt động hoàn chỉnh.

---

## 1. Cài đặt môi trường (Chỉ làm 1 lần đầu tiên)

### 1.1. Yêu cầu hệ thống
- **Python 3.10+** (nhớ tick `Add Python to PATH` khi cài)
- **Node.js** (để chạy frontend)
- **Docker Desktop** (để chạy Qdrant)

### 1.2. Tạo môi trường ảo (Virtual Environment)
Mở PowerShell (hoặc Terminal trong VS Code) tại thư mục gốc của project (`Loan_ETL/`):
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 1.3. Cài đặt thư viện
**Cho Backend:**
```powershell
pip install -r backend/requirements.txt
```

**Cho Frontend:**
Mở thêm một tab Terminal mới:
```powershell
cd frontend
npm install
```

---

## 2. Quy trình khởi chạy hệ thống (Làm hàng ngày)

Khi muốn chạy project, bạn cần mở **3 tab Terminal** chạy song song.

### Tab 1: Khởi động Cơ sở dữ liệu Vector (Qdrant)
Bật **Docker Desktop** lên trước.
Mở Terminal, gõ lệnh sau để khởi tạo Qdrant:
```powershell
# Chạy lệnh này nếu bạn khởi động lần đầu tiên:
docker run -d --name creditintel-qdrant -p 6333:6333 qdrant/qdrant

# Các lần sau mở máy lên, chỉ cần start lại container đã có:
docker start creditintel-qdrant
```

👉 **Cách kiểm tra Qdrant đã chạy chưa:**
Gõ lệnh sau vào PowerShell, nếu hiện chữ xanh báo version là OK:
```powershell
Invoke-RestMethod http://127.0.0.1:6333/
```
*(Hoặc mở trình duyệt truy cập: `http://localhost:6333/dashboard` để xem giao diện quản lý)*.

---

### Tab 2: Khởi chạy Backend (FastAPI)
Mở một tab Terminal khác, bật môi trường ảo và chạy Server:
```powershell
.\venv\Scripts\Activate.ps1
cd backend
uvicorn main:app --reload
```
👉 Khi thấy dòng `Application startup complete.` là Backend đã sẵn sàng (cổng 8000). Cứ để treo tab này ở đó.

---

### Tab 3: Khởi chạy Frontend (React)
Mở tab Terminal thứ 3:
```powershell
cd frontend
npm run dev
```
👉 Frontend sẽ chạy ở cổng 5173. Bạn có thể mở trình duyệt vào link `http://localhost:5173/` để xem giao diện web. Cứ để treo tab này ở đó.

---

## 3. Nạp dữ liệu Tri thức cho AI (Ingest RAG)

**Chỉ cần chạy 1 lần duy nhất** để nạp chính sách vào Qdrant (hoặc khi nào bạn sửa nội dung file Markdown trong `backend/rag/knowledge/`).

Mở một tab PowerShell mới, nhớ bật môi trường ảo và vào thư mục `backend`:
```powershell
.\venv\Scripts\Activate.ps1
cd backend
python -m rag.ingest
```
Lệnh này sẽ tự chạy và kết thúc (không treo). Nó báo `Done. Ingested 76 chunks.` là thành công.

👉 **Cách kiểm tra xem đã nạp dữ liệu xong chưa:**
Gõ lệnh này vào PowerShell:
```powershell
(Invoke-RestMethod http://127.0.0.1:6333/collections/creditintel-kb).result
```
*Nhìn vào kết quả:*
- `status`: Báo `green` là ổn.
- `vectors_count`: Nếu bằng **76** (đúng số chunk) thì tức là toàn bộ trí thức đã nằm trong bộ nhớ AI.

---

## 4. (Tuỳ chọn) Chạy Pipeline Dữ liệu và Train AI Model
Nếu bạn cần load lại dữ liệu Parquet ra database, hoặc muốn cho Machine Learning học lại model mới:

Bật môi trường ảo ở thư mục gốc (`Loan_ETL/`), chạy lần lượt 3 lệnh:
```powershell
# 1. Chạy 3 lớp ETL (Bronze -> Silver -> Gold)
python -m machinelearning.etl.pipeline

# 2. Huấn luyện mô hình rủi ro (LightGBM)
python -m machinelearning.ml.retrain_customer_model

# 3. Huấn luyện mô hình điểm tín dụng (Scorecard)
python -m machinelearning.ml.train_scorecard
```
*(Yêu cầu đã cài `pip install -r machinelearning/requirements.txt` và đã có sẵn dữ liệu Parquet thô tải từ Kaggle).*
