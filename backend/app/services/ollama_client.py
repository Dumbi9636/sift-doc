# ollama_client.py
"""
Ollama 모델을 안정적으로 호출하는 래퍼입니다.
뉴스 모드에서 토큰 수와 컨텍스트를 넉넉히 설정하고, stop 토큰을 적절히 지정하여
모델이 불필요한 문단을 작성하는 것을 방지합니다.
"""

import httpx
from fastapi import HTTPException
from typing import Any, Dict, Optional

OLLAMA_BASE_URL = "http://localhost:11434"
_client: Optional[httpx.AsyncClient] = None

def get_client(timeout_sec: int) -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_sec),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=20),
        )
    return _client

def _stop_for_mode(mode: str) -> list[str]:
    if mode.startswith("news"):
        return ["\n\n\n", "\n###", "\n---"]
    return ["\n\n\n", "\n###", "\n---"]





async def ollama_generate(
    model: str,
    prompt: str,
    mode: str = "news",
    temperature: float = 0.1,
    top_p: float = 0.9,
    num_predict: int = 200,
    timeout_sec: int = 180,
    keep_alive: str = "30m",
) -> Dict[str, Any]:
    if mode.startswith("news"):
        num_ctx = 2048
        num_predict = min(max(num_predict, 120), 260)  # 필요 이상 생성 방지
        temperature = min(temperature, 0.2)
    else:
        num_ctx = 4096

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "keep_alive": keep_alive,
        "options": {
            "temperature": temperature,
            "top_p": top_p,
            "num_predict": num_predict,
            "num_ctx": num_ctx,
            "stop": _stop_for_mode(mode),
            "num_batch": 256,   # 또는 512 (VRAM 여유 있으면)
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
