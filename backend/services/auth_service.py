from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.core.security import create_access_token, hash_password, verify_password
from backend.models.user import UserLogin, UserRegister


def register(db: Session, payload: UserRegister):
    # TODO: check email not already taken
    # TODO: create user row in DB
    # TODO: return TokenOut
    raise NotImplementedError


def login(db: Session, payload: UserLogin):
    # TODO: fetch user by email
    # TODO: verify password
    # TODO: return TokenOut with access_token
    raise NotImplementedError
