from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.txt_extractor import extract_txt_bytes

router = APIRouter(prefix="/api/extract", tags=["extract"])

@router.post("/txt")
async def extract_txt(file: UploadFile = File(...), truncate: bool = True):
    if not (file.filename or "").lower().endswith(".txt"):
        raise HTTPException(status_code=400, detail="Only .txt files are allowed.")
    raw = await file.read()
    result = extract_txt_bytes(raw, truncate=truncate)
    return {"ok": True, "type": "txt", "filename": file.filename, **result}
