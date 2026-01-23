# improved_prompt_builder.py
"""
뉴스 요약 및 청크 요약을 위해 역할/작업/규칙을 명확히 정의한 프롬프트 빌더입니다.
"""

def build_news_prompt(text: str) -> str:
    return f"""
[Role]
당신은 뉴스 기사의 핵심 수치와 사실관계를 왜곡 없이 전달하는 한국어 요약 전문가입니다.

[Task]
제시된 '원문'을 바탕으로 반드시 5개의 불릿포인트(-)로 요약하세요.

[Rules]
1. 한국어로만 작성하세요.
2. 각 문장은 팩트 중심의 평서문(~다. 체)으로 끝내세요.
3. 원문에 없는 숫자를 지어내거나 추측하지 마세요 (Hallucination 금지).
4. 고유명사, 날짜, 금액 등 핵심 수치는 원문 그대로 유지하세요.
5. 서두나 인사말 없이 결과만 출력하세요.
6. 각 줄은 '- '로 시작하세요.
7. 5줄을 초과해 출력하지 마세요.

[Self-check]
출력 직전에 불릿 줄 수를 세어라.
- 불릿이 5개가 아니면, 스스로 수정해서 정확히 5개로 맞춘 뒤 출력하라.

[Output Format]
- 핵심 내용 1
- 핵심 내용 2
- 핵심 내용 3
- 핵심 내용 4
- 핵심 내용 5

[원문]
{text}
""".strip()

def build_chunk_prompt(text: str) -> str:
    return f"""
아래 내용을 한국어로 간결하게 요약해라.

규칙:
- 한국어만 사용한다.
- 원문에 없는 내용을 추가하지 않는다.
- 핵심 내용을 3~5문장 이내로 전달한다.
- 고유명사/수치/연도는 원문 그대로 유지한다.
- 서두나 인사는 쓰지 않는다.

[본문]
{text}
""".strip()

def build_report_prompt(text: str) -> str:
    return f"아래 내용을 한국어로 구조화 요약해라.\\n\\n[원문]\\n{text}"

def build_default_prompt(text: str) -> str:
    return f"아래 텍스트를 한국어로 5줄 이내로 요약하라.\\n\\n[원문]\\n{text}"

def build_prompt(text: str, mode: str) -> str:
    if mode == "news":
        return build_news_prompt(text)
    if mode == "report":
        return build_report_prompt(text)
    return build_default_prompt(text)
