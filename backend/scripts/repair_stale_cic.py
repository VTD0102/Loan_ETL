#!/usr/bin/env python3
"""
repair_stale_cic.py — One-time repair for stale CIC records.

Fixes CIC records created before the total_monthly_installment migration:
1. Recomputes total_monthly_installment from total_outstanding_debt / 36
2. Recomputes total_outstanding_debt from loan_history active entries
3. Syncs total_active_loans with loan_history active count
4. Reports all repairs made

Run: python scripts/repair_stale_cic.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.session import SessionLocal
from models.cic import CICRecord
from sqlalchemy import or_

_FALLBACK_TERM = 36


def repair():
    db = SessionLocal()
    try:
        # Find ALL CIC records for audit
        all_records = db.query(CICRecord).all()
        print(f"Total CIC records: {len(all_records)}")

        repaired = 0
        issues = []

        for cic in all_records:
            changes = []
            loan_history = cic.loan_history or []
            active_in_history = [l for l in loan_history if l.get("status") == "active"]

            # ── Fix 1: Sync total_active_loans with loan_history ──
            actual_active = len(active_in_history)
            if cic.total_active_loans != actual_active and actual_active > 0:
                changes.append(
                    f"  active_loans: {cic.total_active_loans} → {actual_active}"
                )
                cic.total_active_loans = actual_active

            # ── Fix 2: Recompute outstanding_debt from active loans ──
            if active_in_history:
                computed_debt = sum(float(l.get("amount", 0)) for l in active_in_history)
                current_debt = float(cic.total_outstanding_debt or 0)
                if current_debt == 0 and computed_debt > 0:
                    changes.append(
                        f"  outstanding_debt: {current_debt} → {round(computed_debt, 2)}"
                    )
                    cic.total_outstanding_debt = round(computed_debt, 2)

            # ── Fix 3: Recompute monthly_installment ──
            outstanding = float(cic.total_outstanding_debt or 0)
            installment = float(cic.total_monthly_installment or 0)
            if outstanding > 0 and installment == 0:
                new_installment = round(outstanding / _FALLBACK_TERM, 2)
                changes.append(
                    f"  monthly_installment: 0 → {new_installment} (est. {_FALLBACK_TERM}mo)"
                )
                cic.total_monthly_installment = new_installment

            # ── Fix 4: Installment > outstanding (impossible) ──
            outstanding = float(cic.total_outstanding_debt or 0)
            installment = float(cic.total_monthly_installment or 0)
            if installment > outstanding and outstanding > 0:
                new_installment = round(outstanding / _FALLBACK_TERM, 2)
                changes.append(
                    f"  installment > debt: {installment} → {new_installment}"
                )
                cic.total_monthly_installment = new_installment

            if changes:
                repaired += 1
                print(f"\n🔧 CCCD={cic.cccd} (score={cic.cic_score}):")
                for c in changes:
                    print(c)

        if repaired > 0:
            db.commit()
            print(f"\n✅ Repaired {repaired}/{len(all_records)} CIC records.")
        else:
            print("\n✅ No repairs needed — all CIC records are consistent.")

        # ── Verification pass ──
        print("\n── Verification ──")
        bad = db.query(CICRecord).filter(
            CICRecord.total_active_loans > 0,
            or_(
                CICRecord.total_outstanding_debt == None,
                CICRecord.total_outstanding_debt == 0,
                CICRecord.total_monthly_installment == None,
                CICRecord.total_monthly_installment == 0,
            )
        ).count()
        print(f"Records with active_loans>0 but missing debt/installment: {bad}")
        if bad == 0:
            print("✅ ALL CLEAR — no integrity violations remain.")
        else:
            print(f"⚠️  {bad} records still have issues (may have active_loans "
                  "from profile but no matching loan_history entries).")

    finally:
        db.close()


if __name__ == "__main__":
    repair()
