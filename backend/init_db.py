from sqlalchemy import text
from db.session import engine
from models import Base

# Incremental column migrations (idempotent — safe to re-run)
_COLUMN_MIGRATIONS = [
    "ALTER TABLE loan_applications ADD COLUMN IF NOT EXISTS loan_purpose VARCHAR",
]


def init_database():
    try:
        print("⏳ Đang kết nối tới Supabase và khởi tạo các bảng Backend (Sân trước)...")
        Base.metadata.create_all(bind=engine)
        print("✅ THÀNH CÔNG! Đã tạo xong các bảng: users, loan_applications, personal_info.")

        print("⏳ Chạy column migrations...")
        with engine.connect() as conn:
            for sql in _COLUMN_MIGRATIONS:
                try:
                    conn.execute(text(sql))
                    conn.commit()
                    print(f"  ✓ {sql.split()[-1]}")
                except Exception as e:
                    conn.rollback()
                    print(f"  ⚠ Migration skipped ({e})")
        print("✅ Column migrations hoàn tất.")
    except Exception as e:
        print(f"❌ LỖI KẾT NỐI HOẶC TẠO BẢNG: {e}")


if __name__ == "__main__":
    init_database()