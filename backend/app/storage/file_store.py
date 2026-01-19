import os
import uuid
from pathlib import Path
from fastapi import UploadFile, HTTPException

from app.core.config import UPLOAD_DIR, ALLOWED_EXTENSIONS

def ensure_upload_dir():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

def get_extension(filename: str) -> str:
    return Path(filename).suffix.lower()

def validate_file(file: UploadFile) -> None:
    if not file.filename:
        raise HTTPException(status_code=400, detail="파일명이 비어있습니다.")

    ext = get_extension(file.filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 파일 형식입니다. 허용: {sorted(ALLOWED_EXTENSIONS)}"
        )

async def save_upload(file: UploadFile) -> dict:
    """
    파일을 uploads/ 아래에 저장하고 메타데이터 반환
    """
    ensure_upload_dir()
    validate_file(file)

    ext = get_extension(file.filename)
    stored_name = f"{uuid.uuid4().hex}{ext}"
    stored_path = UPLOAD_DIR / stored_name

    # UploadFile은 내부적으로 SpooledTemporaryFile이므로 읽어서 저장
    content = await file.read()
    with open(stored_path, "wb") as f:
        f.write(content)

    return {
        "originalName": file.filename,
        "storedName": stored_name,
        "storedPath": str(stored_path),
        "size": len(content),
        "extension": ext,
    }
