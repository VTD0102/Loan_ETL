import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import auth, applications, admin, chat, credit_score, cic

logger = logging.getLogger(__name__)

app = FastAPI(title="CreditIntel API", version="1.0.0")


@app.on_event("startup")
def _prewarm_reranker():
    try:
        from rag.reranker import get_reranker
        reranker = get_reranker()
        if reranker is None:
            logger.info("Reranker disabled (rag_reranker_enabled=False) — skip pre-warm")
            return
        logger.info("Pre-warming reranker model (downloads ~1.1GB on first run)...")
        reranker._ensure_loaded()
        logger.info("Reranker pre-warm complete.")
    except Exception as exc:
        logger.warning("Reranker pre-warm failed (non-fatal): %s", exc)

origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://your-production-domain.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,         prefix="/auth",         tags=["auth"])
app.include_router(applications.router, prefix="/applications", tags=["applications"])
app.include_router(admin.router,        prefix="/admin",        tags=["admin"])
app.include_router(chat.router,         prefix="/chat",         tags=["chat"])
app.include_router(credit_score.router, prefix="/credit-score", tags=["credit-score"])
app.include_router(cic.router)


@app.get("/health")
def health():
    return {"status": "ok"}
