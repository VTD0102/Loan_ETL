"""FastAPI router exports for CreditIntel."""

from backend.api.routers import admin, applications, auth, chat, predict

__all__ = ["admin", "applications", "auth", "chat", "predict"]
