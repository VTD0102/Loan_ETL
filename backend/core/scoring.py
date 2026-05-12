import math

_BASE   = 600
_ODDS   = 50
_PDO    = 20
_FACTOR = _PDO / math.log(2)


def pd_to_credit_score(pd_value: float) -> int:
    """Convert default probability to FICO-style score (300–850)."""
    p    = max(1e-6, min(1 - 1e-6, float(pd_value)))
    odds = (1 - p) / p
    return max(300, min(850, round(_BASE + _FACTOR * math.log(odds / _ODDS))))


def score_to_band(score: int) -> str:
    if score >= 740: return "Excellent"
    if score >= 670: return "Good"
    if score >= 580: return "Fair"
    return "Poor"
