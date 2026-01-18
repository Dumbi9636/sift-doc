# Backend (FastAPI)

## Run
```bash
python -m venv .venv
# activate venv (Windows)
# .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000


---

## 5) .env 예시 파일
`backend/.env.example`
```env
# OLLAMA_BASE_URL=http://localhost:11434
# OLLAMA_MODEL=llama3.1
