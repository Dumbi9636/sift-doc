from fastapi import APIRouter, UploadFile, File
from app.storage.file_store import save_upload

router = APIRouter(prefix="/api/documents", tags=["documents"])

@router.post("")
async def upload_document(file: UploadFile = File(...)):
    meta = await save_upload(file)
    # 1차 MVP: DB 없이 메타만 반환. (나중에 Oracle 연동 시 여기서 DB insert)
    return {
        "message": "uploaded",
        "document": meta
    }
