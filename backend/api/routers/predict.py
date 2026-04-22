from fastapi import APIRouter, Depends

from backend.api.dependencies import require_customer
from backend.models.application import ApplicationCreate
from backend.services import ml_service

router = APIRouter()


@router.post("")
def predict(
    payload: ApplicationCreate,
    _: dict = Depends(require_customer),
):
    """Run ML inference on form inputs without persisting. Used for preview."""
    return ml_service.predict(payload)
