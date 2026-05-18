from sqlalchemy import text
from db.session import engine
from models import Base

# Incremental column migrations (idempotent — safe to re-run)
_COLUMN_MIGRATIONS = [
    "ALTER TABLE loan_applications ADD COLUMN IF NOT EXISTS loan_purpose VARCHAR",
    "ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS error BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS summary TEXT",
    "ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS summary_covers_until_id UUID",
    "ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS summary_updated_at TIMESTAMP",
    # CIC integration: CCCD on users
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS cccd VARCHAR(12) UNIQUE",
    "ALTER TABLE loan_applications ALTER COLUMN credit_score DROP NOT NULL",
]

# Idempotent index migrations — prevent race-condition duplicates
_INDEX_MIGRATIONS = [
    # Only ONE active (non-rejected) application per user at a time.
    # DB-level guard against TOCTOU race in evaluate()/confirm().
    """CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_app_per_user
       ON loan_applications(user_id)
       WHERE status NOT IN ('AUTO_REJECTED','ADMIN_REJECTED','REJECTED')""",
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

        print("⏳ Chạy index migrations...")
        with engine.connect() as conn:
            for sql in _INDEX_MIGRATIONS:
                try:
                    conn.execute(text(sql))
                    conn.commit()
                    idx_name = sql.split("IF NOT EXISTS")[-1].strip().split()[0] if "IF NOT EXISTS" in sql else "index"
                    print(f"  ✓ {idx_name}")
                except Exception as e:
                    conn.rollback()
                    print(f"  ⚠ Index migration skipped ({e})")
        print("✅ Index migrations hoàn tất.")
    except Exception as e:
        print(f"❌ LỖI KẾT NỐI HOẶC TẠO BẢNG: {e}")


if __name__ == "__main__":
    init_database()
