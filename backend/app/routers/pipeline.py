# app/routers/pipeline.py
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from typing import Literal
import time

from app.services.txt_extractor import extract_txt_bytes
from app.services.prompt_builder import build_prompt
from app.services.ollama_client import ollama_generate

# router 
router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])

# Ollama model 
DEFAULT_MODEL = "phi3"

#--------------------------------helpers----------------------------------#

def get_bullets(summary: str) -> list[str]:
    lines = [ln.strip() for ln in summary.splitlines() if ln.strip()]
    return [ln for ln in lines if ln.startswith("-")]

def bullet_looks_cut(line: str) -> bool:
    # 문장 끝이 너무 어색하면 끊김으로 판단(필요 최소)
    s = line.strip()
    return s.endswith(("(", "“", "\"", "’", "'", "·", ":", ","))

# 끊김 현상 확인
def ollama_cut_by_length(data: dict) -> bool:
    """Ollama가 길이 제한(num_predict) 때문에 잘렸는지"""
    return (data.get("done_reason") == "length")

# build 5개 미만으로
def count_bullets(summary: str) -> int:
    if not summary:
        return 0
    lines = [ln.strip() for ln in summary.splitlines() if ln.strip()]
    return sum(1 for ln in lines if ln.startswith("-"))

# 중복되는 요약 결과 제거
def dedupe_lines(summary: str) -> str:
    """줄 단위 중복 제거(순서 유지)"""
    seen = set()
    out = []
    for ln in summary.splitlines():
        key = ln.strip()
        if not key:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(ln)
    return "\n".join(out)

def keep_first_5_bullets(summary: str) -> str:
    """news 모드: 불릿(-) 5줄로 강제 고정"""
    lines = [ln.strip() for ln in summary.splitlines() if ln.strip()]
    bullets = [ln for ln in lines if ln.startswith("-")]
    if bullets:
        return "\n".join(bullets[:5])
    return summary  # 혹시 불릿이 아예 없으면 원문 유지

def is_truncated(summary: str, mode: str) -> bool:
    if not summary:
        return True

    # news 모드: 불릿 5줄을 기대하는 경우
    if mode == "news":
        return count_bullets(summary) < 5

    # 그 외 모드: 마지막이 너무 애매하게 끝나면 끊김으로 간주
    s = summary.strip()
    if s.endswith(("(", "“", "\"", "’", "'", "·", ":", ",")):
        return True
    return False

#--------------------------------endpoint----------------------------------#

@router.post("/txt")
async def pipeline_txt(
    file: UploadFile = File(...),

    # 요약 옵션
    model: str = Form(DEFAULT_MODEL),
    mode: Literal["news", "default", "report"] = Form("news"),
    temperature: float = Form(0.1),
    top_p: float = Form(0.9),
    num_predict: int = Form(120),

    # 응답 속도 조정
    max_chars: int = Form(3000),
    truncate_extract: bool = Form(True),

    # 응답 옵션
    include_text: bool = Form(False),  # 원문 응답 포함 여부
):
    t0 = time.perf_counter()

    # 1) 확장자 체크
    if not (file.filename or "").lower().endswith(".txt"):
        raise HTTPException(status_code=400, detail="Only .txt files are allowed.")

    raw = await file.read()

    # 2) 추출 서비스 호출
    extracted = extract_txt_bytes(raw, truncate=truncate_extract)
    full_text = extracted["text"]

    # 3) 요약 입력 컷(속도 개선)
    clipped = full_text[:max_chars]

    # 4) 프롬프트 생성 서비스 호출( 시간 측정 )
    t_prompt_start = time.perf_counter()
    prompt = build_prompt(clipped, mode)
    t_prompt_end = time.perf_counter()

    # 5) 1차 ollama 호출 (시간 측정)
    t_ollama_start = time.perf_counter()
    data = await ollama_generate(
        model=model,
        prompt=prompt,
        temperature=temperature,
        top_p=top_p,
        num_predict=num_predict,
        timeout_sec=180,
    )
    t_ollama_end = time.perf_counter()

    summary = (data.get("response") or "").strip()
    summary = summary.replace("<END>", "").strip()

    # 5.5) 끊기면 continue 1회(완결 보장)
    # - 불릿 부족(<5) OR Ollama가 length 컷(done_reason=="length")이면 이어쓰기
    bullets = get_bullets(summary)
    first_bullets = len(bullets)
    
    # 불릿이 이미 5개 이상이면 continue 금지
    if len(bullets) >= 5:
        need_continue = False
    else:
        # 불릿이 부족할 때만 이어쓰기
        need_continue = (mode == "news") and (first_bullets < 5)


    if need_continue:
        # 이어쓰기에는 원문 전체 말고 뒤쪽 일부만
        tail = clipped[-1200:]  # 800~1500 사이 

        continue_prompt = f"""
    아래 요약이 5줄로 완성되지 않았거나, 문장이 중간에 끊겼다.
    같은 형식으로 부족한 불릿(-)만 이어서 작성하라.
    반드시 최종 결과가 총 5줄 불릿이 되게 하라.
    5번째 불릿 다음 줄에 <END>만 출력하고 즉시 종료하라.
    <END> 이후에는 아무 것도 출력하지 마라.
    추가 설명/서두/인사 금지. 한국어만.
    
    [현재 요약]
    {summary}

    [원문(뒤쪽 발췌)]
    {tail}
    """.strip()

        data2 = await ollama_generate(
            model=model,
            prompt=continue_prompt,
            temperature=temperature,
            top_p=top_p,
            num_predict=100,   # 이어쓰기용(조금 여유)
            timeout_sec=180,
        )
        summary2 = (data2.get("response") or "").strip()
        summary = (summary + "\n" + summary2).strip()
        summary = summary.replace("<END>", "").strip()

    # 5.6) 후처리 (중복 제거 + 5줄 고정)
    summary = dedupe_lines(summary)
    if mode == "news":
        summary = keep_first_5_bullets(summary)


    # 6) 응답 구성
    extract_resp = {
        "encoding": extracted["encoding"],
        "bytes": extracted["bytes"],
        "lines": extracted["lines"],
        "input_chars": len(full_text),
        "sent_chars": len(clipped),
        "first_done_reason": data.get("done_reason"),
        "first_bullets": first_bullets,
        "continued": need_continue
    }
    if include_text:
        extract_resp["text"] = clipped  

    t1 = time.perf_counter()
    return {
        "ok": True,
        "filename": file.filename,
        "extract": extract_resp,
        "summarize": {
            "model": model,
            "mode": mode,
            "summary": summary,
            "ollama_done": data.get("done", True),
            "eval_count": data.get("eval_count"),
            "eval_duration": data.get("eval_duration"),
            "done_reason": data.get("done_reason"),
            "prompt_eval_count": data.get("prompt_eval_count"),
            "prompt_eval_duration": data.get("prompt_eval_duration"),

        },
        "meta": {
            "elapsed_ms": int((t1 - t0) * 1000),

            # 디버깅용 타이밍
            "ms_build_prompt": int((t_prompt_end - t_prompt_start) * 1000),
            "ms_ollama": int((t_ollama_end - t_ollama_start) * 1000),
        }

    }
