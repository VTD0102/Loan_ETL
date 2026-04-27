from fastapi import APIRouter, Depends

from api.dependencies import require_customer
from schemas.application import ApplicationCreate
from services import ml_service

router = APIRouter()


@router.post("")
def predict(
    payload: ApplicationCreate,
    _: dict = Depends(require_customer),
):
    """Run ML inference on form inputs without persisting. Used for preview."""
    return ml_service.predict(payload)
