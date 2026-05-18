"""
synthetic_service.py — Generates realistic loan applications with matching CIC records.

Creates synthetic users + CIC records + loan applications that pass through
the real ML pipeline. Data distributions match the Home Credit training data
so the existing .pkl models predict correctly without retraining.

Three borrower profiles:
  - GOOD (60%):      Low risk, likely PENDING_REVIEW
  - RISKY (25%):     Medium risk, borderline
  - DEFAULTER (15%): High risk, likely AUTO_REJECTED
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
    return f"synthetic.{slug}.{idx}@creditintel.test"


def _generate_good_profile() -> dict[str, Any]:
    """Good borrower: stable income, low DTI, no bad debt."""
    income = random.uniform(4000, 15000)
    loan = random.uniform(2000, min(income * 3, 50000))
    dti = random.uniform(0.05, 0.30)
    age = random.randint(25, 55)
    years_emp = random.uniform(2, min(age - 20, 25))
    term = random.choice(_TERM_OPTIONS)
    emp = random.choices(["Employed", "Self-employed"], weights=[80, 20])[0]

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
        # CIC matching data
        "_cic": {
            "cic_score": random.randint(680, 850),
            "total_active_loans": random.randint(0, 2),
            "total_outstanding_debt": round(random.uniform(0, income * 6), 2),
            "total_overdue_amount": 0,
            "max_dpd_12m": 0,
            "num_credit_inquiries": random.randint(0, 3),
            "bad_debt_flag": False,
            "blacklist_flag": False,
            "loan_history": [
                {"lender": "VPBank", "amount": round(random.uniform(5000, 20000), 0),
                 "status": "closed", "dpd_max": 0}
                for _ in range(random.randint(0, 3))
            ],
        },
    }


def _generate_risky_profile() -> dict[str, Any]:
    """Risky borrower: moderate income, higher DTI, some overdue."""
    income = random.uniform(2000, 6000)
    loan = random.uniform(5000, min(income * 5, 60000))
    dti = random.uniform(0.30, 0.50)
    age = random.randint(22, 50)
    years_emp = random.uniform(0.5, min(age - 20, 15))
    term = random.choice(_TERM_OPTIONS)
    emp = random.choices(
        ["Employed", "Self-employed", "Other"], weights=[50, 30, 20]
    )[0]
    overdue = round(random.uniform(0, 500), 2)
    dpd = random.randint(5, 60)

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
        "total_overdue_amount": overdue,
        "max_credit_overdue_days": dpd,
        "has_bad_debt": random.choices([True, False], weights=[20, 80])[0],
        "_cic": {
            "cic_score": random.randint(500, 680),
            "total_active_loans": random.randint(1, 4),
            "total_outstanding_debt": round(random.uniform(income * 2, income * 12), 2),
            "total_overdue_amount": overdue,
            "max_dpd_12m": dpd,
            "num_credit_inquiries": random.randint(2, 8),
            "bad_debt_flag": random.choices([True, False], weights=[20, 80])[0],
            "blacklist_flag": False,
            "loan_history": [
                {"lender": random.choice(["VPBank", "Techcombank", "MBBank", "FE Credit"]),
                 "amount": round(random.uniform(2000, 15000), 0),
                 "status": random.choice(["active", "closed", "overdue"]),
                 "dpd_max": random.randint(0, dpd)}
                for _ in range(random.randint(2, 6))
            ],
        },
    }


def _generate_defaulter_profile() -> dict[str, Any]:
    """Defaulter: low income, high DTI, bad debt, high overdue."""
    income = random.uniform(1000, 4000)
    loan = random.uniform(8000, min(income * 8, 80000))
    dti = random.uniform(0.45, 0.85)
    age = random.randint(20, 60)
    years_emp = random.uniform(0, min(age - 18, 8))
    term = random.choice(_TERM_OPTIONS)
    emp = random.choices(
        ["Employed", "Self-employed", "Not employed", "Other"], weights=[30, 20, 30, 20]
    )[0]
    overdue = round(random.uniform(500, 5000), 2)
    dpd = random.randint(30, 180)

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
        "total_overdue_amount": overdue,
        "max_credit_overdue_days": dpd,
        "has_bad_debt": True,
        "_cic": {
            "cic_score": random.randint(300, 500),
            "total_active_loans": random.randint(2, 6),
            "total_outstanding_debt": round(random.uniform(income * 6, income * 24), 2),
            "total_overdue_amount": overdue,
            "max_dpd_12m": dpd,
            "num_credit_inquiries": random.randint(5, 15),
            "bad_debt_flag": True,
            "blacklist_flag": random.choices([True, False], weights=[10, 90])[0],
            "blacklist_reason": "Nợ xấu nhóm 5 kéo dài",
            "loan_history": [
                {"lender": random.choice(["FE Credit", "HomeCredit", "MBBank", "VPBank"]),
                 "amount": round(random.uniform(1000, 10000), 0),
                 "status": random.choice(["overdue", "bad_debt", "written_off"]),
                 "dpd_max": random.randint(30, dpd)}
                for _ in range(random.randint(3, 8))
            ],
        },
    }


# ── Profile picker ────────────────────────────────────────────────────────────

_PROFILE_GENERATORS = {
    "good": _generate_good_profile,
    "risky": _generate_risky_profile,
    "defaulter": _generate_defaulter_profile,
}

_PROFILE_WEIGHTS = [60, 25, 15]  # good, risky, defaulter


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

            status = result.get("status", "UNKNOWN")
            stats["created"] += 1
            if status == "AUTO_REJECTED":
                stats["auto_rejected"] += 1
                if result.get("cic_blacklisted"):
                    stats["cic_blacklisted"] += 1
            else:
                stats["pending_review"] += 1

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
