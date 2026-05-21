from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from db.session import get_db, get_bureau_db
from schemas.user import TokenOut, UserLogin, UserCreate as UserRegister, UserRead, UserUpdate
from services import auth_service
from api.dependencies import get_current_user
from models.user import User

router = APIRouter()


@router.post("/register", response_model=TokenOut, status_code=201)
def register(payload: UserRegister, db: Session = Depends(get_db), bureau_db: Session = Depends(get_bureau_db)):
    """
    **Register a new customer account.**
    - Validates email uniqueness.
    - Hashes password via strictly via bcrypt.
    - Sets default role to 'customer'.
    - Returns minimal user payload.
    """
    return auth_service.register(db, bureau_db, payload)


@router.post("/login", response_model=TokenOut)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    """
    **Authenticate and generate JWT Session.**
    - Verifies bcrypt hashed password.
    - Generates strict JWT with 24h expiration timestamp.
    - Returns `access_token` containing `sub` (email) parameter for frontend authorization logic.
    """
    return auth_service.login(db, payload)


@router.get("/me", response_model=UserRead)
def get_me(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    **Get current logged in user profile.**
    """
    email = current_user.get("sub")
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy người dùng"
        )
    return user


@router.put("/profile", response_model=UserRead)
def update_profile(
    payload: UserUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    **Update specific user profile fields.**
    - Allows editing: email, username, address, and password.
    - Prevents editing: cccd, full_name, phone, role.
    """
    email = current_user.get("sub")
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy người dùng"
        )
    
    if payload.username is not None:
        user.username = payload.username.strip()
        
    if payload.email is not None:
        new_email = payload.email.strip()
        if new_email != user.email:
            # Kiểm tra xem email mới đã được dùng bởi ai khác chưa
            existing = db.query(User).filter(User.email == new_email).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email này đã được sử dụng bởi người dùng khác"
                )
            user.email = new_email
            
    if payload.address is not None:
        user.address = payload.address.strip()
        
    if payload.password is not None and payload.password.strip() != "":
        from core.security import hash_password
        user.password_hash = hash_password(payload.password)
        
    db.commit()
    db.refresh(user)
    return user
