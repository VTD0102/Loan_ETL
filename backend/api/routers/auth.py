from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db.session import get_db
from schemas.user import TokenOut, UserLogin, UserCreate as UserRegister
from services import auth_service

router = APIRouter()


@router.post("/register", response_model=TokenOut, status_code=201)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    """
    **Register a new customer account.**
    - Validates email uniqueness.
    - Hashes password via strictly via bcrypt.
    - Sets default role to 'customer'.
    - Returns minimal user payload.
    """
    return auth_service.register(db, payload)


@router.post("/login", response_model=TokenOut)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    """
    **Authenticate and generate JWT Session.**
    - Verifies bcrypt hashed password.
    - Generates strict JWT with 24h expiration timestamp.
    - Returns `access_token` containing `sub` (email) parameter for frontend authorization logic.
    """
    return auth_service.login(db, payload)
