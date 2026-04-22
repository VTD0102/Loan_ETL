from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routers import auth, applications, admin, predict, chat

app = FastAPI(title="CreditIntel API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,         prefix="/auth",         tags=["auth"])
app.include_router(applications.router, prefix="/applications", tags=["applications"])
app.include_router(admin.router,        prefix="/admin",        tags=["admin"])
app.include_router(predict.router,      prefix="/predict",      tags=["predict"])
app.include_router(chat.router,         prefix="/chat",         tags=["chat"])


@app.get("/health")
def health():
    return {"status": "ok"}
