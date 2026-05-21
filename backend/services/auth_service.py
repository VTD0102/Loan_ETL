from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from models.user import User
from schemas.user import UserCreate as UserRegister, UserLogin, TokenOut
from core.security import create_access_token, hash_password, verify_password


def register(db: Session, bureau_db: Session, payload: UserRegister):
    # Check email
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email đã được đăng ký"
        )

    # Check CCCD uniqueness
    if db.query(User).filter(User.cccd == payload.cccd).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CCCD này đã được sử dụng bởi tài khoản khác"
        )

    hashed_pwd = hash_password(payload.password)
    new_user = User(
        email=payload.email,
        username=payload.username,
        password_hash=hashed_pwd,
        cccd=payload.cccd,
        full_name=payload.full_name,
        phone=payload.phone,
        address=payload.address,
        role="customer"
    )
    db.add(new_user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(400, "Email hoặc CCCD đã tồn tại")
    
    db.refresh(new_user)

    # Automatically generate an external-like bureau profile for this new customer
    from services import cic_service
    try:
        cic_service.create_bureau_profile_if_missing(bureau_db, new_user.cccd, new_user.full_name)
    except Exception as e:
        # If bureau generation fails, rollback the entire registration to prevent orphaned users
        db.delete(new_user)
        db.commit()
        raise HTTPException(500, f"Lỗi hệ thống khi khởi tạo hồ sơ tín dụng: {str(e)}")

    token_payload = {"sub": new_user.email, "role": new_user.role}
    token = create_access_token(token_payload)

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": new_user
    }


def login(db: Session, payload: UserLogin):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    token_payload = {"sub": user.email, "role": user.role}
    token = create_access_token(token_payload)

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user
    }
