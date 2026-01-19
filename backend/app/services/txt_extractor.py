from fastapi import HTTPException

MAX_BYTES = 10 * 1024 * 1024
MAX_TEXT_CHARS = 2_000_000

def decode_with_fallback(raw: bytes) -> tuple[str, str]:
    for enc in ("utf-8-sig", "utf-8"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            pass
    for enc in ("cp949", "euc-kr"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            pass
    raise UnicodeDecodeError("unknown", b"", 0, 1, "Failed to decode with common encodings")

def basic_binary_guard(raw: bytes) -> None:
    if b"\x00" in raw:
        raise HTTPException(status_code=400, detail="Binary-like file detected (NULL byte found).")

    control = 0
    printable = 0
    for b in raw[:20000]:
        if b in (9, 10, 13):
            printable += 1
        elif 32 <= b <= 126 or b >= 128:
            printable += 1
        else:
            control += 1

    if (control + printable) > 0 and control / (control + printable) > 0.2:
        raise HTTPException(status_code=400, detail="Too many control characters; file may be binary.")

def extract_txt_bytes(raw: bytes, truncate: bool = True) -> dict:
    if len(raw) == 0:
        raise HTTPException(status_code=400, detail="Empty file.")
    if len(raw) > MAX_BYTES:
        raise HTTPException(status_code=413, detail=f"File too large. Max {MAX_BYTES} bytes.")

    basic_binary_guard(raw)

    try:
        text, encoding = decode_with_fallback(raw)
    except UnicodeDecodeError:
        raise HTTPException(status_code=422, detail="Failed to decode text file with supported encodings.")

    if len(text) > MAX_TEXT_CHARS:
        if truncate:
            text = text[:MAX_TEXT_CHARS]
        else:
            raise HTTPException(status_code=413, detail=f"Text too long. Max {MAX_TEXT_CHARS} chars.")

    return {
        "text": text,
        "encoding": encoding,
        "bytes": len(raw),
        "lines": text.count("\n") + (1 if text else 0),
    }
