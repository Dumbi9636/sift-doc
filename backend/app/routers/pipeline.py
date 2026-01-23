# pipeline.py
"""
긴 문서를 빠르게 요약하기 위해 Map-Reduce+병렬화 구조를 도입하고,
불릿 추출·필터링, 프롬프트 강화, continue 로직을 개선한 FastAPI 라우터입니다.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from typing import Literal, List
import time, re, asyncio

from app.services.txt_extractor import extract_txt_bytes
from app.services.prompt_builder import build_prompt, build_news_prompt, build_chunk_prompt
from app.services.ollama_client import ollama_generate

# ── 불릿 추출용 정규식과 도우미 ────────────────────────────────────────────
_BULLET_RE = re.compile(r"^\s*(?:[-•]|\d+[\.\)\-])\s*(.*)$")

def _ascii_letter_ratio(s: str) -> float:
    letters = sum(1 for ch in s if 'A' <= ch <= 'Z' or 'a' <= ch <= 'z')
    return letters / max(1, len(s))

def get_bullets(text: str) -> List[str]:
    bullets = []
    for raw in (text or "").splitlines():
        m = _BULLET_RE.match(raw)
        if not m:
            continue
        content = (m.group(1) or "").strip()
        if not content:
            continue
        bullets.append("- " + content)
    return bullets

def _dedup_key(line: str) -> str:
    s = line.strip()
    s = s.replace("<END>", "")
    s = re.sub(r"^\-\s*", "", s)          # 앞 "- " 제거
    s = re.sub(r"[.\u00B7·…,'\"“”‘’]", "", s)  # 마침표/가운뎃점/따옴표 등 제거
    s = re.sub(r"\s+", " ", s).strip()   # 공백 정규화
    return s

def normalize_bullets(text: str) -> List[str]:
    bullets, seen = [], set()
    for b in get_bullets(text):
        b = re.sub(r"\s+", " ", b).strip()
        b = b.replace("<END>", "").strip()

        core = b[2:].strip()
        if len(core) < 6:
            continue

        ratio = _ascii_letter_ratio(core)
        if ratio >= 0.55 and len(core) < 80:
            continue

        key = _dedup_key(b)
        if key in seen:
            continue
        seen.add(key)
        bullets.append(b)
    return bullets

# 성능 검증 디버깅
def _ns_to_ms(v):
    return None if v is None else int(v / 1_000_000)

def pick_ollama_metrics(d: dict) -> dict:
    out = {}
    for k in ["done_reason", "prompt_eval_count", "eval_count"]:
        if k in d:
            out[k] = d.get(k)

    for k in ["total_duration", "load_duration", "prompt_eval_duration", "eval_duration"]:
        if k in d:
            out[k] = _ns_to_ms(d.get(k))

    # tok/s 추가
    ev = out.get("eval_count")
    ev_ms = out.get("eval_duration")
    if ev is not None and ev_ms:
        out["tok_per_sec"] = round(ev / (ev_ms / 1000), 2)

    pv = out.get("prompt_eval_count")
    pv_ms = out.get("prompt_eval_duration")
    if pv is not None and pv_ms:
        out["prompt_tok_per_sec"] = round(pv / (pv_ms / 1000), 2)

    return out


def render_5(bullets: List[str]) -> str:
    return "\n".join(bullets[:5])

def split_text(text: str, max_len: int) -> List[str]:
    # 개행 단위로 길이를 맞춰 자름
    chunks, pos, length = [], 0, len(text)
    while pos < length:
        end = min(pos + max_len, length)
        newline_pos = text.rfind("\n", pos, end)
        if newline_pos <= pos: newline_pos = end
        chunk = text[pos:newline_pos]
        if chunk: chunks.append(chunk)
        pos = newline_pos
    return chunks

def bullet_looks_cut(line: str) -> bool:
    s = line.strip()
    # 문장 끝이 어색한 패턴들
    return s.endswith(("하고", "하며", "및", "또는", "등", "으로", "를", "은", "는", ":", ",", "·", "…"))
    
def bullet_complete(line: str) -> bool:
    s = line.strip()
    s = s.replace("<END>", "").strip()
    # "~다" 또는 "~다."로 끝나면 완성으로 간주
    return bool(re.search(r"다[.!?]?$", s))

def build_continue_prompt(article_tail: str, current_bullets: List[str], remain: int) -> str:
    existing = "\n".join(current_bullets) if current_bullets else "(없음)"
    return f"""
당신은 뉴스 기사의 핵심 수치와 사실관계를 왜곡 없이 전달하는 한국어 요약 전문가입니다.

현재까지 작성한 불릿:
{existing}

금지:
- 위 불릿에서 이미 언급된 '숫자/연도/계약건수/승인건수/서비스명/사업명'을 다시 쓰지 마라.
- 같은 사실을 다른 말로 반복하지 마라.

남은 불릿 {remain}줄을 추가하세요.

규칙:
1. 한국어로만 작성
2. 문장은 평서문(~다. 체)으로 끝낼 것
3. 원문에 없는 숫자·정보를 추가하지 말 것
4. 고유명사·날짜·금액 등 핵심 수치는 원문 그대로 유지
5. 서두나 인사 없이 결과만 출력
6. 각 줄은 “- ”로 시작
7. “마지막 불릿이 문장 중간에서 끝났으면, 그 불릿을 먼저 완성하고 나머지 불릿을 작성하라.”

[원문 뒤쪽 발췌]
{article_tail}
""".strip()

def build_repair_prompt(article_tail: str, current_bullets: List[str]) -> str:
    existing = "\n".join(current_bullets) if current_bullets else "(없음)"
    return f"""
당신은 뉴스 기사의 사실/수치를 왜곡 없이 전달하는 한국어 요약 전문가입니다.

아래 '현재 불릿'은 마지막 문장이 끊겼거나 불완전할 수 있습니다.
[원문 뒤쪽 발췌]를 참고해 사실/수치를 유지하면서,
불릿 5줄을 완전한 문장으로 다시 작성하세요.

규칙:
1. 한국어만
2. 정확히 5줄
3. 각 줄은 "- "로 시작
4. 원문에 없는 정보/숫자 추가 금지
5. 중복 금지
6. 각 문장은 "~다."로 끝내기
7. 마지막 불릿이 끊겼다면 먼저 자연스럽게 완성할 것
8. 서두/인사 없이 결과만 출력

[현재 불릿]
{existing}

[원문 뒤쪽 발췌]
{article_tail}
""".strip()

# ── FastAPI 라우터 ───────────────────────────────────────────────────────
router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])
DEFAULT_MODEL = "gemma3:4b"

@router.post("/txt")
async def pipeline_txt(
    file: UploadFile = File(...),
    model: str = Form(DEFAULT_MODEL),
    mode: Literal["news", "default", "report"] = Form("news"),
    temperature: float = Form(0.0),
    top_p: float = Form(0.9),
    num_predict: int = Form(300),
    max_chars: int = Form(1200),
    truncate_extract: bool = Form(True),
    include_text: bool = Form(False),
):
    # 파일 검증 및 텍스트 추출
    if not (file.filename or "").lower().endswith(".txt"):
        raise HTTPException(status_code=400, detail="Only .txt files are allowed.")
    raw = await file.read()
    extracted = extract_txt_bytes(raw, truncate=truncate_extract)
    full_text = extracted["text"]
    clipped = full_text[:max_chars]

    # 뉴스 모드: 긴 문서는 map-reduce+병렬 처리, 짧은 문서는 1회+보강 처리
    final_repair_metrics = None
    use_map_reduce = mode == "news" and len(clipped) > 800
    t0 = time.perf_counter()

    if mode == "news" and use_map_reduce:
        m1 = {}
        m2 = None
        m3 = None
        # 1. 텍스트를 여러 조각으로 분할
        chunks = split_text(clipped, 600)

        # 2. 각 조각을 병렬로 요약
        async def summarise_chunk(c):
            return await ollama_generate(
                model=model,
                prompt=build_chunk_prompt(c),
                mode="default",
                temperature=0.1,
                top_p=top_p,
                num_predict = 120,
                timeout_sec=120,
            )
        t_map_start = time.perf_counter()
        chunk_responses = await asyncio.gather(*(summarise_chunk(c) for c in chunks))
        map_metrics = [pick_ollama_metrics(r) for r in chunk_responses if isinstance(r, dict)]
        t_map_end = time.perf_counter()

        intermediate = [
            res.get("response", "").strip()
            for res in chunk_responses if res.get("response")
        ]
        combined = "\n".join(intermediate)

        # 3. 중간 요약을 다시 뉴스 형식으로 요약
        t_reduce_start = time.perf_counter()
        final_prompt = build_news_prompt(combined)
        final_data = await ollama_generate(
            model=model,
            prompt=final_prompt,
            mode="news",
            temperature=temperature,
            top_p=top_p,
            num_predict=num_predict,
            timeout_sec=180,
        )
        reduce_metrics = pick_ollama_metrics(final_data)
        t_reduce_end = time.perf_counter()

        out = (final_data.get("response") or "").strip()
        bullets = normalize_bullets(out)
        bullets_final = bullets[:]
        summary = render_5(bullets_final) if bullets_final else out
        

        # 최종 검증 후, 필요하면 마지막으로 repair 1회 더
        final_need_repair = (
            len(bullets_final) < 5 or
            (bullets_final and (not bullet_complete(bullets_final[-1]) or bullet_looks_cut(bullets_final[-1])))
        )

        if final_need_repair:
            tail = clipped[-600:]
            final_repair_prompt = build_repair_prompt(tail, bullets_final)

            dataF = await ollama_generate(
                model=model,
                prompt=final_repair_prompt,
                mode="news",
                temperature=temperature,
                top_p=top_p,
                num_predict=220,     # 너무 크게 말고(속도), 5줄 나오게 적당히
                timeout_sec=60,
            )
            final_repair_metrics = pick_ollama_metrics(dataF)
            outF = (dataF.get("response") or "").strip()
            bulletsF = normalize_bullets(outF)
            if bulletsF:
                bullets_final = bulletsF[:5]

        # (repair 반영된 bullets_final 기준으로 summary 다시 만들기)
        summary = render_5(bullets_final) if bullets_final else out

        extract_resp = {
            "encoding": extracted["encoding"],
            "bytes": extracted["bytes"],
            "lines": extracted["lines"],
            "input_chars": len(full_text),
            "sent_chars": len(clipped),
            "map_chunks": len(chunks),
            "map_time_ms": int((t_map_end - t_map_start) * 1000),
            "reduce_time_ms": int((t_reduce_end - t_reduce_start) * 1000),
            "ollama": {
                        "map": map_metrics[:5],          # chunk가 많으면 너무 길어지니 앞 5개만
                        "map_count": len(map_metrics),
                        "reduce": reduce_metrics,
                        "final_repair": final_repair_metrics if final_need_repair else None,
                    },
        }
        if include_text:
            extract_resp["text"] = clipped
            extract_resp["prompt_debug"] = final_prompt[:800]
        t1 = time.perf_counter()
        return {
            "ok": True,
            "filename": file.filename,
            "extract": extract_resp,
            "summarize": {"model": model, "mode": mode, "summary": summary},
            "meta": {
                "elapsed_ms": int((t1 - t0) * 1000),
                "ms_build_prompt": 0,
                "ms_ollama": extract_resp["map_time_ms"] + extract_resp["reduce_time_ms"],
            },
        }

    if mode == "news":
        m1 = {}
        m2 = None
        m3 = None

        # 1차 프롬프트: 강화된 뉴스 프롬프트
        t_prompt_start = time.perf_counter()
        prompt = build_news_prompt(clipped)
        t_prompt_end = time.perf_counter()

        # 1차 호출
        t_call1_start = time.perf_counter()
        data1 = await ollama_generate(
            model=model,
            prompt=prompt,
            mode="news_first",
            temperature=temperature,
            top_p=top_p,
            num_predict=num_predict,
            timeout_sec=180,
        )
        t_call1_end = time.perf_counter()
        m1 = pick_ollama_metrics(data1)

        out1 = (data1.get("response") or "").strip()
        bullets1 = normalize_bullets(out1)

        first_done_reason = data1.get("done_reason")
        first_bullets = len(bullets1) 
        # length면 불릿 수와 무관하게 "끊김" 확률이 매우 높으므로 repair 우선
        last_bullet = bullets1[-1] if bullets1 else ""
        need_repair = (
            first_done_reason == "length" or
            (first_bullets > 0 and not bullet_complete(last_bullet)) or
            (first_bullets > 0 and bullet_looks_cut(last_bullet))
        )

        # add는 "정상적으로 끝났는데 불릿 수만 부족"할 때만
        need_add = (first_bullets < 5) and (not need_repair)

        bullets_final = bullets1[:]

        prompt_build_ms = (t_prompt_end - t_prompt_start) * 1000
        call1_ms = (t_call1_end - t_call1_start) * 1000
        call2_ms = 0.0
        out2 = ""  #  2차 응답 디버그용 (없으면 빈 문자열)

        # 2차 호출: add(부족분 채우기) 또는 repair(5줄인데 끊김/length면 재작성)
        if need_repair:
            tail = clipped[-600:]
            repair_prompt = build_repair_prompt(tail, bullets_final)

            t_call2_start = time.perf_counter()
            data2 = await ollama_generate(
                model=model,
                prompt=repair_prompt,
                mode="news",
                temperature=temperature,
                top_p=top_p,
                num_predict=num_predict,
                timeout_sec=60,
            )
            t_call2_end = time.perf_counter()
            call2_ms = (t_call2_end - t_call2_start) * 1000

            out2 = (data2.get("response") or "").strip()
            bullets2 = normalize_bullets(out2)
            m2 = pick_ollama_metrics(data2)

            # 1) repair 결과 적용 (있으면 그걸 우선)
            if bullets2:
                bullets_final = bullets2[:5]
            else:
                # fallback 파싱
                lines = [ln.strip() for ln in out2.splitlines() if ln.strip()]
                lines = [ln.replace("<END>", "").strip() for ln in lines]

                tmp = []
                for ln in lines:
                    if ln.startswith("-"):
                        tmp.append("- " + ln[1:].lstrip())
                    elif ln.startswith("•"):
                        tmp.append("- " + ln[1:].lstrip())
                    else:
                        m = re.match(r"^\d+[\.\)\-]\s*(.*)$", ln)
                        if m:
                            tmp.append("- " + (m.group(1) or "").strip())
                    if len(tmp) >= 5:
                        break

                if tmp:
                    bullets_final = tmp[:5]

            # 2) bullets2가 있든 없든, 5줄 미만이면 add 실행
            if len(bullets_final) < 5:
                remain = 5 - len(bullets_final)
                tail = clipped[-500:]
                cont_prompt = build_continue_prompt(tail, bullets_final, remain)
                cont_tokens = min(320, 120 + (remain * 60))

                t_call3_start = time.perf_counter()
                data3 = await ollama_generate(
                    model=model,
                    prompt=cont_prompt,
                    mode="news",
                    temperature=temperature,
                    top_p=top_p,
                    num_predict=cont_tokens,
                    timeout_sec=60,
                )
                t_call3_end = time.perf_counter()
                call2_ms += (t_call3_end - t_call3_start) * 1000

                out3 = (data3.get("response") or "").strip()
                bullets3 = normalize_bullets(out3)
                m3 = pick_ollama_metrics(data3)

                seen = set(_dedup_key(x) for x in bullets_final)
                for b in bullets3:
                    k = _dedup_key(b)
                    if k not in seen:
                        bullets_final.append(b)
                        seen.add(k)
                    if len(bullets_final) >= 5:
                        break



            
        elif need_add:
            remain = 5 - first_bullets
            tail = clipped[-500:]
            cont_prompt = build_continue_prompt(tail, bullets_final, remain)
            cont_tokens = min(240, 80 + remain * 40)
            t_call2_start = time.perf_counter()
            data2 = await ollama_generate(
                model=model,
                prompt=cont_prompt,
                mode="news",
                temperature=temperature,
                top_p=top_p,
                num_predict=cont_tokens,
                timeout_sec=60,
            )
            t_call2_end = time.perf_counter()
            call2_ms = (t_call2_end - t_call2_start) * 1000

            out2 = (data2.get("response") or "").strip()
            bullets2 = normalize_bullets(out2)
            m2 = pick_ollama_metrics(data2)

            seen = set(_dedup_key(x) for x in bullets_final)
            for b in bullets2:
                k = _dedup_key(b)
                if k not in seen:
                    bullets_final.append(b)
                    seen.add(k)
                if len(bullets_final) >= 5:
                    break



        summary = render_5(bullets_final) if bullets_final else out
        extract_resp = {
            "encoding": extracted["encoding"],
            "bytes": extracted["bytes"],
            "lines": extracted["lines"],
            "input_chars": len(full_text),
            "sent_chars": len(clipped),
            "first_done_reason": first_done_reason,
            "first_bullets": first_bullets,
            "continued": (need_add or need_repair),
            "need_add": need_add,
            "need_repair": need_repair,
            # 디버그(핵심): raw 응답 일부
            "raw_tail_1": (data1.get("response") or "")[-120:],
            "raw_head_2": out2[:300] if out2 else "",
            "raw_tail_2": out2[-120:] if out2 else "",
            "ollama_1": m1,
            "ollama_2": m2,
            "ollama_3": m3,
        }
        
        if include_text:
            extract_resp["text"] = clipped
            extract_resp["prompt_debug"] = prompt[:800]
        t1 = time.perf_counter()
        return {
            "ok": True,
            "filename": file.filename,
            "extract": extract_resp,
            "summarize": {
                "model": model, "mode": mode, "summary": summary, "done_reason": first_done_reason,
            },
            "meta": {
                "elapsed_ms": int((t1 - t0) * 1000),
                "ms_build_prompt": int(prompt_build_ms),
                "ms_ollama": int(call1_ms + call2_ms),
            },
        }
    
    # default / report 모드
    t_prompt_start = time.perf_counter()
    prompt = build_prompt(clipped, mode)
    t_prompt_end = time.perf_counter()

    t_call_start = time.perf_counter()
    data = await ollama_generate(
        model=model,
        prompt=prompt,
        mode=mode,
        temperature=temperature,
        top_p=top_p,
        num_predict=num_predict,
        timeout_sec=180,
    )
    t_call_end = time.perf_counter()

    summary = (data.get("response") or "").strip()
    extract_resp = {
        "encoding": extracted["encoding"],
        "bytes": extracted["bytes"],
        "lines": extracted["lines"],
        "input_chars": len(full_text),
        "sent_chars": len(clipped),
        "revealed_done_reason": data.get("done_reason"),
    }
    if include_text:
        extract_resp["text"] = clipped
        extract_resp["prompt_debug"] = prompt[:800]
    t1 = time.perf_counter()
    return {
        "ok": True,
        "filename": file.filename,
        "extract": extract_resp,
        "summarize": {
            "model": model, "mode": mode, "summary": summary, "done_reason": data.get("done_reason"),
        },
        "meta": {
            "elapsed_ms": int((t1 - t0) * 1000),
            "ms_build_prompt": int((t_prompt_end - t_prompt_start) * 1000),
            "ms_ollama": int((t_call_end - t_call_start) * 1000),
        },
    }
