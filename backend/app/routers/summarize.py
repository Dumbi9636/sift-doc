from fastapi import APIRouter
from pydantic import BaseModel
from app.services.prompt_builder import build_prompt
from app.services.ollama_client import ollama_generate

router = APIRouter(prefix="/api", tags=["summarize"])

class SummarizeRequest(BaseModel):
    text: str
    model: str = "llama3"
    mode: str = "news"
    max_chars: int = 3000
    temperature: float = 0.1
    top_p: float = 0.9
    
@router.post("/summarize")
async def summarize(req: SummarizeRequest):
    clipped = req.text[:req.max_chars]
    prompt = build_prompt(clipped, req.mode)
    data = await ollama_generate(req.model, prompt, req.temperature, req.top_p)
    return {"ok": True, "model": req.model, "summary": (data.get("response") or "").strip()}
