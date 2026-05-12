from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.dependencies import get_current_user, require_admin
from db.session import get_db
from schemas.credit_score import CreditScoreResponse
from services.credit_score_service import get_credit_score

router = APIRouter()


@router.get("/me", response_model=CreditScoreResponse)
def my_credit_score(
    db:           Session = Depends(get_db),
    current_user: dict    = Depends(get_current_user),
):
    """Return credit score for the authenticated user's latest application."""
    try:
        return get_credit_score(current_user["sub"], db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{user_id}", response_model=CreditScoreResponse)
def user_credit_score(
    user_id: str,
    db:      Session = Depends(get_db),
    _admin:  dict    = Depends(require_admin),
):
    """Admin: return credit score for any user by user_id."""
    try:
        return get_credit_score(user_id, db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
