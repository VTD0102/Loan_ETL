import duckdb
import pandas as pd
from pathlib import Path

# Đường dẫn
DB_PATH = "/home/bminphi/KH086/HQTCSDL/Loan_ETL/machinelearning/data/etl.duckdb"
OUTPUT_FILE = "docs/ml_md/eda_views_export.txt"

# Các view cần xuất (dựa theo file transform_gold_hcv2.sql)
VIEWS_TO_EXPORT = [
    "gold.vw_v2_dti_vs_default",
    "gold.vw_v2_employment_vs_default",
    "gold.vw_v2_dpd_vs_default"
]

def export_views():
    print(f"Kết nối tới DuckDB: {DB_PATH}")
    con = duckdb.connect(DB_PATH, read_only=True)
    
    # Đảm bảo thư mục đầu ra tồn tại
    Path(OUTPUT_FILE).parent.mkdir(parents=True, exist_ok=True)
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("=== TÀI LIỆU THỐNG KÊ EDA TỪ TẦNG GOLD (DUCKDB) ===\n")
        f.write("Dữ liệu này dùng để phân tích nghiệp vụ rủi ro tín dụng.\n\n")
        
        for view in VIEWS_TO_EXPORT:
            print(f"Đang trích xuất: {view}")
            try:
                # Query toàn bộ view
                df = con.execute(f"SELECT * FROM {view}").df()
                
                f.write(f"--- KẾT QUẢ TỪ BẢNG: {view} ---\n")
                # Chuyển dataframe thành dạng text dễ đọc
                f.write(df.to_string(index=False))
                f.write("\n\n" + "="*50 + "\n\n")
            except Exception as e:
                print(f"Lỗi khi đọc {view}: {e}")
                f.write(f"--- LỖI KHI ĐỌC {view} ---\n{e}\n\n")
                
    con.close()
    print(f"Đã xuất thành công ra file: {OUTPUT_FILE}")

if __name__ == "__main__":
    export_views()