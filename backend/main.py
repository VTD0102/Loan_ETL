from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import auth, applications, admin, chat, credit_score, cic

app = FastAPI(title="CreditIntel API", version="1.0.0")

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
