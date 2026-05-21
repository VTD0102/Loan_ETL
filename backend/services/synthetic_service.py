"""
synthetic_service.py — Generates realistic loan applications with matching CIC records.

Creates synthetic users + CIC records + loan applications that pass through
the real ML pipeline. Data distributions match the Home Credit training data
so the existing .pkl models predict correctly without retraining.

Three borrower profiles:
  - GOOD (60%):      Low risk, likely PENDING_REVIEW
  - RISKY (25%):     Medium risk, borderline
  - DEFAULTER (15%): High risk, likely AUTO_REJECTED

v2 — Logically consistent CIC data:
  - total_active_loans matches number of "active" entries in loan_history
  - total_outstanding_debt = sum of active loan amounts
  - total_monthly_installment derived from outstanding debt / avg remaining term
  - CIC score inversely correlates with bad_debt and overdue
  - Synthetic confirmations use varied amounts (not always = suggested)
"""
from __future__ import annotations

import logging
import random
import string
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from fastapi import HTTPException
from models.user import User
from models.cic import CICRecord
from schemas.application import ApplicationCreate
from services import application_service
from core.security import hash_password

logger = logging.getLogger(__name__)

# ── Vietnamese name pools ─────────────────────────────────────────────────────
_HO = ["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Huỳnh", "Phan", "Vũ", "Võ",
       "Đặng", "Bùi", "Đỗ", "Hồ", "Ngô", "Dương", "Lý"]
_TEN_DEM = ["Văn", "Thị", "Đức", "Minh", "Thanh", "Quốc", "Hữu", "Ngọc",
            "Hoàng", "Anh", "Phương", "Thuỳ", "Bảo", "Gia", "Tuấn"]
_TEN = ["An", "Bình", "Cường", "Dũng", "Hà", "Hùng", "Khánh", "Linh",
        "Mai", "Nam", "Phúc", "Quân", "Sơn", "Tâm", "Vy", "Hải",
        "Đạt", "Long", "Thắng", "Trang", "Hiếu", "Khoa", "Nhật"]

_EMPLOYMENT_OPTIONS = ["Employed", "Self-employed", "Retired", "Not employed", "Other"]
_OCCUPATION_MAP = {
    "Employed": ["EMPLOYED", "PRIVATE_SECTOR_EMPLOYEE", "SALARIED_GOVT"],
    "Self-employed": ["SELFEMPLOYED"],
    "Retired": ["RETIRED_PENSIONER"],
    "Not employed": ["OTHER"],
    "Other": ["OTHER"],
}
_CATEGORY_OPTIONS = [
    "Debt Consolidation", "Home Improvement", "Business", "Personal Loan",
    "Auto/Vehicle", "Medical/Dental", "Education", "Other",
]
_TERM_OPTIONS = [12, 24, 36, 48, 60]
_LENDERS = ["VPBank", "Techcombank", "MBBank", "FE Credit", "HomeCredit",
            "TPBank", "SHB", "VIB", "ACB", "Shinhan"]


# ── Consistent CIC builder ───────────────────────────────────────────────────

def _build_consistent_cic(
    *,
    num_active: int,
    num_closed: int,
    income: float,
    cic_score_range: tuple[int, int],
    bad_debt: bool,
    overdue_range: tuple[float, float],
    dpd_range: tuple[int, int],
    blacklist: bool = False,
    blacklist_reason: str | None = None,
) -> dict[str, Any]:
    """
    Build a logically consistent CIC record:
    - loan_history entries match active/closed counts
    - total_outstanding_debt = sum of active loan amounts
    - total_monthly_installment = outstanding_debt / avg_remaining_term
    - CIC score lowered if bad_debt is True
    """
    loan_history = []
    total_outstanding = 0.0
    dpd = random.randint(*dpd_range)

    # Generate active loans
    for _ in range(num_active):
        amt = round(random.uniform(1000, 30000), 0)
        total_outstanding += amt
        loan_history.append({
            "lender": random.choice(_LENDERS),
            "amount": amt,
            "status": "active",
            "dpd_max": random.randint(0, min(dpd, 30)) if not bad_debt else random.randint(10, dpd),
        })

    # Generate closed/overdue loans
    for _ in range(num_closed):
        amt = round(random.uniform(1000, 20000), 0)
        status = "closed"
        if bad_debt and random.random() < 0.5:
            status = random.choice(["overdue", "bad_debt", "written_off"])
        loan_history.append({
            "lender": random.choice(_LENDERS),
            "amount": amt,
            "status": status,
            "dpd_max": random.randint(0, dpd),
        })

    total_outstanding = round(total_outstanding, 2)

    # Monthly installment: divide by a realistic remaining term (6-48 months)
    if total_outstanding > 0 and num_active > 0:
        avg_remaining = random.randint(6, 48)
        monthly_installment = round(total_outstanding / avg_remaining, 2)
    else:
        monthly_installment = 0.0

    overdue = round(random.uniform(*overdue_range), 2) if overdue_range[1] > 0 else 0.0

    # CIC score: if bad_debt, cap the score lower
    score_lo, score_hi = cic_score_range
    if bad_debt:
        score_hi = min(score_hi, 500)
    cic_score = random.randint(score_lo, score_hi)

    inquiries = random.randint(0, 3) + num_active + num_closed

    return {
        "cic_score": cic_score,
        "total_active_loans": num_active,
        "total_outstanding_debt": total_outstanding,
        "total_monthly_installment": monthly_installment,
        "total_overdue_amount": overdue,
        "max_dpd_12m": dpd,
        "num_credit_inquiries": inquiries,
        "bad_debt_flag": bad_debt,
        "blacklist_flag": blacklist,
        "blacklist_reason": blacklist_reason if blacklist else None,
        "loan_history": loan_history,
    }


# ── Profile definitions ──────────────────────────────────────────────────────

def _random_cccd() -> str:
    """Generate a random 12-digit CCCD."""
    return "".join(random.choices(string.digits, k=12))


def _random_name() -> str:
    return f"{random.choice(_HO)} {random.choice(_TEN_DEM)} {random.choice(_TEN)}"


def _random_email(name: str, idx: int) -> str:
    slug = name.lower().replace(" ", "").replace("đ", "d").replace("ă", "a")\
        .replace("â", "a").replace("ê", "e").replace("ô", "o").replace("ơ", "o")\
        .replace("ư", "u").replace("ữ", "u").replace("ứ", "u").replace("ừ", "u")\
        .replace("ũ", "u").replace("ủ", "u").replace("ụ", "u")\
        .replace("ả", "a").replace("ã", "a").replace("ạ", "a")\
        .replace("ắ", "a").replace("ẳ", "a").replace("ẵ", "a").replace("ặ", "a")\
        .replace("ấ", "a").replace("ầ", "a").replace("ẩ", "a").replace("ẫ", "a").replace("ậ", "a")\
        .replace("ế", "e").replace("ề", "e").replace("ể", "e").replace("ễ", "e").replace("ệ", "e")\
        .replace("ố", "o").replace("ồ", "o").replace("ổ", "o").replace("ỗ", "o").replace("ộ", "o")\
        .replace("ớ", "o").replace("ờ", "o").replace("ở", "o").replace("ỡ", "o").replace("ợ", "o")\
        .replace("í", "i").replace("ì", "i").replace("ỉ", "i").replace("ĩ", "i").replace("ị", "i")\
        .replace("ú", "u").replace("ù", "u").replace("ủ", "u").replace("ũ", "u").replace("ụ", "u")\
        .replace("ý", "y").replace("ỳ", "y").replace("ỷ", "y").replace("ỹ", "y").replace("ỵ", "y")
    # Keep only ascii
    slug = "".join(c for c in slug if c.isalnum())
    return f"synthetic.{slug}.{idx}@creditintel.com"


def _generate_good_profile() -> dict[str, Any]:
    """Good borrower: stable income, low DTI, no bad debt, clean CIC."""
    income = random.uniform(4000, 15000)
    loan = random.uniform(2000, min(income * 3, 50000))
    dti = random.uniform(0.05, 0.30)
    age = random.randint(25, 55)
    years_emp = random.uniform(2, min(age - 20, 25))
    term = random.choice(_TERM_OPTIONS)
    emp = random.choices(["Employed", "Self-employed"], weights=[80, 20])[0]

    # CIC: 0-3 active loans, 1-4 closed, no bad debt, high score
    num_active = random.choices([0, 1, 2, 3], weights=[10, 50, 30, 10])[0]
    num_closed = random.randint(1, 4)
    cic = _build_consistent_cic(
        num_active=num_active,
        num_closed=num_closed,
        income=income,
        cic_score_range=(680, 850),
        bad_debt=False,
        overdue_range=(0, 0),
        dpd_range=(0, 5),
    )

    return {
        "monthly_income": round(income, 2),
        "loan_amount": round(loan, 2),
        "term": term,
        "dti": round(dti * 100, 2),  # Schema expects percentage
        "employment_status": emp,
        "occupation_type": random.choice(_OCCUPATION_MAP[emp]),
        "years_employed": round(years_emp, 1),
        "is_homeowner": random.choices([True, False], weights=[60, 40])[0],
        "listing_category": random.choice(_CATEGORY_OPTIONS),
        "age_years": age,
        "education_ordinal": random.choices([3, 4, 5], weights=[20, 50, 30])[0],
        "is_married_flag": random.choices([True, False], weights=[55, 45])[0],
        "income_verifiable_flag": True,
        # Bureau (will be overwritten by CIC, but needed for schema)
        "num_bureau_records": random.randint(1, 5),
        "num_active_credit": random.randint(0, 2),
        "total_overdue_amount": 0,
        "max_credit_overdue_days": 0,
        "has_bad_debt": False,
        "_cic": cic,
    }


def _generate_risky_profile() -> dict[str, Any]:
    """Risky borrower: moderate income, higher DTI, some overdue, mixed CIC."""
    income = random.uniform(2000, 6000)
    loan = random.uniform(5000, min(income * 5, 60000))
    dti = random.uniform(0.30, 0.50)
    age = random.randint(22, 50)
    years_emp = random.uniform(0.5, min(age - 20, 15))
    term = random.choice(_TERM_OPTIONS)
    emp = random.choices(
        ["Employed", "Self-employed", "Other"], weights=[50, 30, 20]
    )[0]

    # CIC: 1-4 active loans, 1-4 closed, sometimes bad debt, medium score
    num_active = random.randint(1, 4)
    num_closed = random.randint(1, 4)
    has_bad = random.choices([True, False], weights=[20, 80])[0]
    cic = _build_consistent_cic(
        num_active=num_active,
        num_closed=num_closed,
        income=income,
        cic_score_range=(450, 680),
        bad_debt=has_bad,
        overdue_range=(0, 1000),
        dpd_range=(5, 60),
    )

    return {
        "monthly_income": round(income, 2),
        "loan_amount": round(loan, 2),
        "term": term,
        "dti": round(dti * 100, 2),
        "employment_status": emp,
        "occupation_type": random.choice(_OCCUPATION_MAP[emp]),
        "years_employed": round(years_emp, 1),
        "is_homeowner": random.choices([True, False], weights=[30, 70])[0],
        "listing_category": random.choice(_CATEGORY_OPTIONS),
        "age_years": age,
        "education_ordinal": random.choices([2, 3, 4], weights=[30, 40, 30])[0],
        "is_married_flag": random.choices([True, False], weights=[40, 60])[0],
        "income_verifiable_flag": random.choices([True, False], weights=[60, 40])[0],
        "num_bureau_records": random.randint(2, 8),
        "num_active_credit": random.randint(1, 4),
        "total_overdue_amount": round(random.uniform(0, 500), 2),
        "max_credit_overdue_days": random.randint(5, 60),
        "has_bad_debt": has_bad,
        "_cic": cic,
    }


def _generate_defaulter_profile() -> dict[str, Any]:
    """Defaulter: low income, high DTI, bad debt, high overdue, bad CIC."""
    income = random.uniform(1000, 4000)
    loan = random.uniform(8000, min(income * 8, 80000))
    dti = random.uniform(0.45, 0.85)
    age = random.randint(20, 60)
    years_emp = random.uniform(0, min(age - 18, 8))
    term = random.choice(_TERM_OPTIONS)
    emp = random.choices(
        ["Employed", "Self-employed", "Not employed", "Other"], weights=[30, 20, 30, 20]
    )[0]

    # CIC: 2-6 active loans, 2-5 closed, always bad debt, low score
    num_active = random.randint(2, 6)
    num_closed = random.randint(2, 5)
    cic = _build_consistent_cic(
        num_active=num_active,
        num_closed=num_closed,
        income=income,
        cic_score_range=(300, 450),
        bad_debt=True,
        overdue_range=(500, 5000),
        dpd_range=(30, 180),
        blacklist=random.choices([True, False], weights=[10, 90])[0],
        blacklist_reason="Nợ xấu nhóm 5 kéo dài",
    )

    return {
        "monthly_income": round(income, 2),
        "loan_amount": round(loan, 2),
        "term": term,
        "dti": round(dti * 100, 2),
        "employment_status": emp,
        "occupation_type": random.choice(_OCCUPATION_MAP[emp]),
        "years_employed": round(years_emp, 1),
        "is_homeowner": random.choices([True, False], weights=[15, 85])[0],
        "listing_category": random.choice(_CATEGORY_OPTIONS),
        "age_years": age,
        "education_ordinal": random.choices([1, 2, 3], weights=[30, 40, 30])[0],
        "is_married_flag": random.choices([True, False], weights=[35, 65])[0],
        "income_verifiable_flag": random.choices([True, False], weights=[30, 70])[0],
        "num_bureau_records": random.randint(3, 12),
        "num_active_credit": random.randint(2, 6),
        "total_overdue_amount": round(random.uniform(500, 5000), 2),
        "max_credit_overdue_days": random.randint(30, 180),
        "has_bad_debt": True,
        "_cic": cic,
    }


# ── Profile picker ────────────────────────────────────────────────────────────

_PROFILE_GENERATORS = {
    "good": _generate_good_profile,
    "risky": _generate_risky_profile,
    "defaulter": _generate_defaulter_profile,
}

_PROFILE_WEIGHTS = [60, 25, 15]  # good, risky, defaulter


def _generate_thin_file_profile() -> dict[str, Any]:
    """Thin-file: little to no credit history, minimal active debt."""
    income = random.uniform(3000, 10000)
    cic = _build_consistent_cic(
        num_active=random.choices([0, 1], weights=[40, 60])[0],
        num_closed=random.randint(0, 1),
        income=income,
        cic_score_range=(550, 700),  # Neutral score
        bad_debt=False,
        overdue_range=(0, 0),
        dpd_range=(0, 0),
    )
    return {"_cic": cic}


# ── Bureau Profile Generator ─────────────────────────────────────────────────

def generate_bureau_profile_data(cccd: str, full_name: str) -> dict[str, Any]:
    """
    Generate only the CIC bureau data for a new customer.
    This simulates an external credit bureau query.
    Weights: 40% good, 30% thin-file, 20% risky, 10% defaulter.
    """
    profile_type = random.choices(
        ["good", "thin_file", "risky", "defaulter"],
        weights=[55, 10, 25, 10]
    )[0]

    if profile_type == "good":
        profile = _generate_good_profile()
    elif profile_type == "thin_file":
        profile = _generate_thin_file_profile()
    elif profile_type == "risky":
        profile = _generate_risky_profile()
    else:
        profile = _generate_defaulter_profile()

    cic_data = profile["_cic"]
    
    # Enrich with user info
    cic_data["cccd"] = cccd
    cic_data["full_name"] = full_name
    return cic_data


def _pick_profile() -> tuple[str, dict]:
    profile_name = random.choices(
        list(_PROFILE_GENERATORS.keys()), weights=_PROFILE_WEIGHTS
    )[0]
    return profile_name, _PROFILE_GENERATORS[profile_name]()


# ── Main generator ────────────────────────────────────────────────────────────

def generate_batch(db: Session, count: int = 10) -> dict[str, Any]:
    """
    Generate a batch of synthetic users + CIC records + loan applications.

    Each synthetic record:
      1. Creates a User (email=synthetic.xxx@creditintel.test, password=Synthetic123!)
      2. Creates a CIC record matching the user's CCCD
      3. Calls application_service.evaluate() → runs through real ML pipeline
         → CIC enrichment happens automatically (Phase A integration)

    Returns stats: {created, auto_rejected, pending_review, errors, details}
    """
    stats = {
        "requested": count,
        "created": 0,
        "auto_rejected": 0,
        "pending_review": 0,
        "cic_blacklisted": 0,
        "errors": 0,
        "details": [],
    }

    for i in range(count):
        profile_name, profile = _pick_profile()
        cic_data = profile.pop("_cic")

        full_name = _random_name()
        cccd = _random_cccd()
        email = _random_email(full_name, i + random.randint(1000, 9999))

        try:
            # 1) Create User
            user = User(
                email=email,
                username=full_name,
                password_hash=hash_password("Synthetic123!"),
                cccd=cccd,
                full_name=full_name,
                phone=f"09{random.randint(10000000, 99999999)}",
                address=f"Số {random.randint(1, 500)}, Đường {random.choice(['Lê Lợi', 'Nguyễn Huệ', 'Trần Hưng Đạo', 'Hai Bà Trưng', 'Lý Thường Kiệt'])}, TP.HCM",
                role="customer",
            )
            db.add(user)
            db.flush()  # Get user.id without committing

            # 2) Create CIC record
            cic = CICRecord(
                cccd=cccd,
                full_name=full_name,
                cic_score=cic_data.get("cic_score"),
                total_active_loans=cic_data.get("total_active_loans", 0),
                total_outstanding_debt=cic_data.get("total_outstanding_debt", 0),
                total_monthly_installment=cic_data.get("total_monthly_installment", 0),
                total_overdue_amount=cic_data.get("total_overdue_amount", 0),
                max_dpd_12m=cic_data.get("max_dpd_12m", 0),
                num_credit_inquiries=cic_data.get("num_credit_inquiries", 0),
                bad_debt_flag=cic_data.get("bad_debt_flag", False),
                blacklist_flag=cic_data.get("blacklist_flag", False),
                blacklist_reason=cic_data.get("blacklist_reason"),
                loan_history=cic_data.get("loan_history", []),
            )
            db.add(cic)
            db.commit()  # Commit user + CIC so evaluate() can find them

            # 3) Build ApplicationCreate payload
            payload = ApplicationCreate(**profile)

            # 4) Run through real ML pipeline (CIC enrichment happens automatically)
            result = application_service.evaluate(db, email, payload)

            from schemas.application import ApplicationConfirm
            status = result.get("status", "UNKNOWN")
            stats["created"] += 1
            if status == "AUTO_REJECTED":
                stats["auto_rejected"] += 1
                if result.get("cic_blacklisted"):
                    stats["cic_blacklisted"] += 1
            else:
                try:
                    # ── Vary confirm amounts for diverse test data ──
                    # Don't always use the exact suggested amount — pick a
                    # strategy so we get a mix of perfect-fit, under, and over.
                    suggested_amt = result.get("suggested_amount", float(payload.loan_amount))
                    suggested_term = result.get("suggested_term", payload.term)
                    original_amt = float(payload.loan_amount)

                    strategy = random.choices(
                        ["exact_suggestion", "original", "between", "over_suggestion"],
                        weights=[30, 25, 30, 15],
                    )[0]

                    if strategy == "exact_suggestion":
                        confirm_amt = suggested_amt
                        confirm_term = suggested_term
                    elif strategy == "original":
                        # Use original if it's within the reviewable cap
                        confirm_amt = min(original_amt, suggested_amt)
                        confirm_term = payload.term
                    elif strategy == "between":
                        # Random amount between 50% and 100% of suggested
                        confirm_amt = round(random.uniform(suggested_amt * 0.5, suggested_amt) / 100) * 100
                        confirm_term = random.choice([t for t in _TERM_OPTIONS if t <= suggested_term] or [suggested_term])
                    else:  # over_suggestion — will likely be rejected by validation
                        confirm_amt = round(suggested_amt * random.uniform(1.05, 1.3) / 100) * 100
                        confirm_term = suggested_term

                    confirm_amt = max(500, confirm_amt)  # enforce minimum

                    profile["loan_amount"] = confirm_amt
                    profile["term"] = confirm_term
                    confirm_payload = ApplicationConfirm(**profile)
                    application_service.confirm(db, email, confirm_payload)
                    stats["pending_review"] += 1
                except HTTPException as e:
                    if e.status_code == 422:
                        stats["auto_rejected"] += 1
                        status = "AUTO_REJECTED"
                    else:
                        raise e

            stats["details"].append({
                "email": email,
                "name": full_name,
                "profile": profile_name,
                "status": status,
                "probability": result.get("default_probability"),
                "risk_level": result.get("risk_level"),
            })

        except Exception as exc:
            db.rollback()
            stats["errors"] += 1
            logger.warning("Synthetic generation failed for %s: %s", email, exc)
            stats["details"].append({
                "email": email,
                "profile": profile_name,
                "status": "ERROR",
                "error": str(exc),
            })

    logger.info(
        "Synthetic batch: %d created (%d rejected, %d pending, %d errors)",
        stats["created"], stats["auto_rejected"], stats["pending_review"], stats["errors"],
    )
    return stats
