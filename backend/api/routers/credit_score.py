from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.dependencies import get_current_user, require_admin
from db.session import get_db, get_bureau_db
from schemas.credit_score import CreditScoreResponse
from services.credit_score_service import get_credit_score, get_credit_score_for_application

router = APIRouter()


@router.get("/me", response_model=CreditScoreResponse)
def my_credit_score(
    db:           Session = Depends(get_db),
    bureau_db:    Session = Depends(get_bureau_db),
    current_user: dict    = Depends(get_current_user),
):
    """Return credit score for the authenticated user's latest application."""
    try:
        return get_credit_score(current_user["sub"], db, bureau_db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/applications/{app_id}", response_model=CreditScoreResponse)
def application_credit_score(
    app_id: str,
    db: Session = Depends(get_db),
    bureau_db: Session = Depends(get_bureau_db),
    current_user: dict = Depends(get_current_user),
):
    """Return scorecard result for one application owned by the current user."""
    try:
        return get_credit_score_for_application(app_id, db, user_id=current_user["sub"], bureau_db=bureau_db)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/admin/applications/{app_id}", response_model=CreditScoreResponse)
def admin_application_credit_score(
    app_id: str,
    db: Session = Depends(get_db),
    bureau_db: Session = Depends(get_bureau_db),
    _admin: dict = Depends(require_admin),
):
    """Admin: return scorecard result for one application."""
    try:
        return get_credit_score_for_application(app_id, db, bureau_db=bureau_db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{user_id}", response_model=CreditScoreResponse)
def user_credit_score(
    user_id: str,
    db:      Session = Depends(get_db),
    bureau_db: Session = Depends(get_bureau_db),
    _admin:  dict    = Depends(require_admin),
):
    """Admin: return credit score for any user by user_id."""
    try:
        return get_credit_score(user_id, db, bureau_db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
