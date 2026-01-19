from pathlib import Path

# 업로드 파일 저장 위치 (프로젝트 내 backend/uploads)
BASE_DIR = Path(__file__).resolve().parents[2]  # backend/
UPLOAD_DIR = BASE_DIR / "uploads"

# 허용 확장자 (1차 MVP)
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}

# 파일 최대 크기(선택): FastAPI 자체 제한은 없고, 운영 환경에서 Nginx 등으로 제한하는 경우가 많음
MAX_FILE_SIZE_MB = 500
