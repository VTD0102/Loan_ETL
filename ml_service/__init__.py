"""Public ML service package interface for CreditIntel."""

from ml_service.dashboard import render_dashboard
from ml_service.data_handler import load_data
from ml_service.prediction_ui import render_predictor

__all__ = ["load_data", "render_dashboard", "render_predictor"]
