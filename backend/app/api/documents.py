from fastapi import APIRouter, UploadFile, File
from app.storage.file_store import save_upload
from app.services.pipeline import summarize_document_by_id  

router = APIRouter(prefix="/api/documents", tags=["documents"])

# 파일 업로드
@router.post("/")
async def upload_document(file: UploadFile = File(...)):
    meta = await save_upload(file)
    # 1차 MVP: DB 없이 메타만 반환. (나중에 Oracle 연동 시 여기서 DB insert)
    return {
        "message": "uploaded",
        "document": meta
    }

# 문서ID 기반 요약
@router.post("/{document_id}/summary")
async def summarize_document(document_id: str, model: str = "gemma3:4b", mode: str = "news"):
    result = await summarize_document_by_id(document_id, model=model, mode=mode)
    return result

