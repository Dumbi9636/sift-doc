from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.documents import router as documents_router
from app.routers.extract_txt import router as extract_txt_router
from app.routers.summarize import router as summarize_router
from app.routers.pipeline import router as pipeline_router

# 개발용 에러메세지 포함
import logging
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Sift API", version="0.1.0")

# 개발 단계 CORS (나중에 배포 시 도메인 제한 예정)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "sift-backend"}

# router 등록 
app.include_router(documents_router) # 문서
app.include_router(extract_txt_router) # 텍스트 추출
app.include_router(summarize_router) # Ollama 요약 
app.include_router(pipeline_router) # 텍스트 추출 + Ollama 요약 pipeline
