import traceback
from schemas.application import ApplicationCreate
from services import ml_service

payload = ApplicationCreate(
    monthly_income=5000,
    loan_amount=10000,
    term=24,
    employment_status="Employed",
    dti=0.3,
    is_homeowner=True,
    listing_category=1,
    credit_score=700
)

try:
    print("Testing ML Service...")
    res = ml_service.predict(payload)
    print("Result:", res)
except Exception as e:
    traceback.print_exc()

