#!/usr/bin/env python3
"""
Seed script — Generate synthetic loan applications.

Usage (from backend/ directory):
    python scripts/seed_synthetic.py              # default 10 records
    python scripts/seed_synthetic.py --count 50   # custom count
"""
import argparse
import sys
import os

# Ensure backend/ is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.session import SessionLocal, BureauSessionLocal
from services import synthetic_service


def main():
    parser = argparse.ArgumentParser(description="Sinh dữ liệu khoản vay giả lập")
    parser.add_argument("--count", type=int, default=10, help="Số khoản vay cần sinh (default: 10)")
    args = parser.parse_args()

    print(f"⏳ Đang sinh {args.count} khoản vay giả lập...")
    db = SessionLocal()
    bureau_db = BureauSessionLocal()
    try:
        stats = synthetic_service.generate_batch(db, bureau_db, count=args.count)
    finally:
        db.close()
        bureau_db.close()

    print(f"\n✅ Kết quả:")
    print(f"   Tạo thành công : {stats['created']}/{stats['requested']}")
    print(f"   PENDING_REVIEW : {stats['pending_review']}")
    print(f"   AUTO_REJECTED  : {stats['auto_rejected']}")
    print(f"   CIC Blacklisted: {stats['cic_blacklisted']}")
    print(f"   Lỗi            : {stats['errors']}")

    print(f"\n📋 Chi tiết:")
    for d in stats["details"]:
        icon = "✅" if d["status"] == "PENDING_REVIEW" else "❌" if d["status"] == "AUTO_REJECTED" else "⚠️"
        prob = d.get("probability")
        prob_str = f" ({prob:.1%})" if prob is not None else ""
        print(f"   {icon} [{d['profile']:>9}] {d.get('name', d['email']):25} → {d['status']}{prob_str}")


if __name__ == "__main__":
    main()
