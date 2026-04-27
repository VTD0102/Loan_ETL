from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models.user import User
from schemas.user import UserCreate as UserRegister, UserLogin, TokenOut
from core.security import create_access_token, hash_password, verify_password


def register(db: Session, payload: UserRegister):
    existing_user = db.query(User).filter(User.email == payload.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    hashed_pwd = hash_password(payload.password)
    new_user = User(
        email=payload.email,
        username=payload.username,
        password_hash=hashed_pwd,
        role="customer"
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

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
