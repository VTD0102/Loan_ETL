from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.security import decode_access_token

bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
        return payload
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def require_customer(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user.get("role") != "customer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Customers only")
    return current_user


def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins only")
    return current_user
