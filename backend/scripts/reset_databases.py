import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.session import engine, bureau_engine, BureauBase
from models import Base
from init_db import init_database

def reset_dbs():
    print("⚠️  CẢNH BÁO: Bắt đầu XÓA TOÀN BỘ BẢNG DỮ LIỆU...")
    
    print("Xóa các bảng Main DB...")
    Base.metadata.drop_all(bind=engine)
    print("Đã xóa xong các bảng Main DB.")
    
    print("Xóa các bảng Bureau DB...")
    BureauBase.metadata.drop_all(bind=bureau_engine)
    print("Đã xóa xong các bảng Bureau DB.")
    
    print("\nKhởi tạo lại CSDL mới hoàn toàn...")
    init_database()
    print("\n✅ HOÀN TẤT VIỆC DỌN DẸP HỆ THỐNG!")

if __name__ == "__main__":
    reset_dbs()
