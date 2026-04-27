from db.session import engine
from models import Base

def init_database():
    try:
        print("⏳ Đang kết nối tới Supabase và khởi tạo các bảng Backend (Sân trước)...")
        # Lệnh này sẽ tự động dò tìm các models và tạo bảng trên DB nếu chưa có
        Base.metadata.create_all(bind=engine)
        print("✅ THÀNH CÔNG! Đã kết nối Supabase và tạo xong 3 bảng: users, loan_applications, personal_info.")
    except Exception as e:
        print(f"❌ LỖI KẾT NỐI HOẶC TẠO BẢNG: {e}")

if __name__ == "__main__":
    init_database()