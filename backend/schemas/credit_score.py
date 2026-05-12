from pydantic import BaseModel


class CreditScoreResponse(BaseModel):
    member_key:          str
    credit_score:        int
    score_band:          str
    default_probability: float
    risk_level:          str
    top_factors:         list[dict]
