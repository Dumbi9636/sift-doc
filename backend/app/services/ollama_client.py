import httpx
from fastapi import HTTPException
from typing import Any, Dict, Optional

OLLAMA_BASE_URL = "http://localhost:11434"

# 전역 클라이언트(커넥션 재사용)
_client: Optional[httpx.AsyncClient] = None

def get_client(timeout_sec: int) -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_sec),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=20),
        )
    return _client

async def ollama_generate(
    model: str,
    prompt: str,
    temperature: float = 0.1,
    top_p: float = 0.9,
    num_predict: int = 120,
    timeout_sec: int = 180,
    keep_alive: str = "30m", # 모델 유지
) -> Dict[str, Any]:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "keep_alive": keep_alive,
        "options": {
            "temperature": temperature,
            "top_p": top_p, 
            # 출력 토큰 제한(성능 개선 방법이 뭐가 더 있을까..)
            "num_predict": num_predict,
            "stop": ["<END>", "\n<END>", "<END>\n"]
        },
    }

    try:
        client = get_client(timeout_sec)
        r = await client.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload)
        r.raise_for_status()
        return r.json()
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Ollama server is not reachable (is ollama running?)")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Ollama error: {e.response.text}")