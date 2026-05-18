"""
document_service.py

Uploads supporting documents to Supabase Storage.
Falls back to local /uploads/ if Supabase is not configured.
"""
import uuid
import os
from pathlib import Path
from typing import List

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from models.application import LoanApplication
from models.personal_info import PersonalInfo

_ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png"}
_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
_LOCAL_UPLOAD_DIR = Path(__file__).parents[2] / "uploads"


async def upload_documents(
    db: Session,
    app_id: str,
    user_email: str,
    bank_account_number: str,
    files: List[UploadFile],
) -> dict:
    from models.user import User
    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        raise HTTPException(401, "User not found")

    app = db.query(LoanApplication).filter(LoanApplication.id == app_id).first()
    if not app:
        raise HTTPException(404, "Application not found")
    if app.user_id != user.id:
        raise HTTPException(403, "Forbidden")
    if app.status not in ("AWAITING_INFO", "INFO_SUBMITTED"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Trạng thái đơn là '{app.status}'. Yêu cầu 'AWAITING_INFO' hoặc 'INFO_SUBMITTED'.",
        )

    # Validate files
    for f in files:
        ext = Path(f.filename or "").suffix.lower()
        if ext not in _ALLOWED_EXTENSIONS:
            raise HTTPException(400, f"File '{f.filename}' không hợp lệ. Chấp nhận: PDF, DOC, DOCX, JPG, PNG")

    # Upload files
    urls = []
    for f in files:
        content = await f.read()
        if len(content) > _MAX_FILE_SIZE:
            raise HTTPException(400, f"File '{f.filename}' quá lớn (tối đa 10 MB)")
        url = await _upload_file(content, f.filename or "document", app_id)
        urls.append(url)

    # Update existing PersonalInfo if available, otherwise store URLs on the
    # application itself.  We NEVER create a PersonalInfo skeleton with fake
    # required fields — that blocks submit_personal_info() and will corrupt
    # future CIC lookups by id_card_number.
    info = db.query(PersonalInfo).filter(PersonalInfo.application_id == app.id).first()
    if info:
        info.bank_account_number = bank_account_number
        info.document_urls = urls
        app.status = "INFO_SUBMITTED"
    else:
        # PersonalInfo not yet created — stash document URLs on the application
        # so they can be merged later when submit_personal_info() is called.
        app.feature_snapshot = {
            **(app.feature_snapshot or {}),
            "_pending_document_urls": urls,
            "_pending_bank_account": bank_account_number,
        }
        # Do NOT change status to INFO_SUBMITTED; personal info is still missing.

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(500, "Lỗi khi lưu tài liệu")
    if info:
        db.refresh(info)

    return {"document_urls": urls, "bank_account_number": bank_account_number}


async def _upload_file(content: bytes, filename: str, app_id: str) -> str:
    """Upload to Supabase Storage if configured, else save locally."""
    unique_name = f"{app_id}/{uuid.uuid4()}_{filename}"

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY")

    if supabase_url and supabase_key:
        return await _upload_supabase(content, unique_name, supabase_url, supabase_key)

    return _save_local(content, unique_name)


async def _upload_supabase(content: bytes, path: str, url: str, key: str) -> str:
    try:
        import httpx
        bucket = "loan-documents"
        upload_url = f"{url}/storage/v1/object/{bucket}/{path}"
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                upload_url,
                content=content,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/octet-stream",
                },
            )
        resp.raise_for_status()
        return f"{url}/storage/v1/object/public/{bucket}/{path}"
    except Exception as exc:
        raise HTTPException(500, f"Upload Supabase thất bại: {exc}") from exc


def _save_local(content: bytes, path: str) -> str:
    dest = _LOCAL_UPLOAD_DIR / path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)
    return f"/uploads/{path}"
