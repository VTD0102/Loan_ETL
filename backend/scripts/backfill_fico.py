#!/usr/bin/env python3
"""
Backfill fico_score cho tất cả đơn vay chưa có điểm Scorecard.

Chạy từ thư mục backend/:
    python scripts/backfill_fico.py           # dry-run (in ra, không ghi)
    python scripts/backfill_fico.py --commit  # ghi vào DB
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.session import SessionLocal, BureauSessionLocal
from models.application import LoanApplication
from services.credit_score_service import _score_application


def main():
    parser = argparse.ArgumentParser(description="Backfill fico_score")
    parser.add_argument("--commit", action="store_true", help="Ghi vào DB (mặc định: dry-run)")
    args = parser.parse_args()

    db = SessionLocal()
    bureau_db = BureauSessionLocal()

    try:
        apps = (
            db.query(LoanApplication)
            .filter(LoanApplication.fico_score.is_(None))
            .filter(LoanApplication.status != "DRAFT")
            .order_by(LoanApplication.submitted_at)
            .all()
        )

        print(f"{'[DRY-RUN] ' if not args.commit else ''}Tìm thấy {len(apps)} đơn chưa có fico_score")

        ok = fail = 0
        for app in apps:
            try:
                result = _score_application(app, db, bureau_db)
                score = result["credit_score"]
                band = result["score_band"]
                if args.commit:
                    app.fico_score = score
                print(f"  {'✓' if args.commit else '○'} [{app.id}] {app.status:15} → {score} ({band})")
                ok += 1
            except Exception as exc:
                print(f"  ✗ [{app.id}] {app.status:15} → SKIP: {exc}")
                fail += 1

        if args.commit and ok > 0:
            db.commit()
            print(f"\n✅ Đã lưu {ok} điểm FICO. Bỏ qua {fail} đơn lỗi.")
        else:
            print(f"\n{'Dry-run xong' if not args.commit else 'Không có gì để lưu'}. OK={ok}, Fail={fail}")
            if not args.commit:
                print("Chạy lại với --commit để ghi vào DB.")
    finally:
        db.close()
        bureau_db.close()


if __name__ == "__main__":
    main()
