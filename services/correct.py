# services/correct.py

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv


# =========================================================
# 환경 변수
# =========================================================

load_dotenv()

OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_BASE_URL",
    "http://127.0.0.1:11434"
)

OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "qwen3:8b"
)

OLLAMA_TIMEOUT = int(
    os.getenv(
        "OLLAMA_TIMEOUT",
        "300"
    )
)


logger = logging.getLogger("correction")


# =========================================================
# 강의 전문용어 사전
# =========================================================

DOMAIN_TERMS = [
    # 통계
    "카이제곱",
    "카이제곱 검정",
    "독립성 검정",
    "기대빈도",
    "관측빈도",
    "교차분석",
    "교차표",
    "독립변수",
    "종속변수",
    "정규성",
    "등분산성",
    "Levene 검정",
    "Levene's test",
    "Welch 검정",
    "Welch test",
    "t 검정",
    "t-test",
    "ANOVA",
    "일원배치 분산분석",
    "분산분석",
    "사후검정",
    "Tukey",
    "Scheffe",
    "F 검정",
    "유의수준",
    "유의확률",
    "p-value",
    "p값",
    "표본",
    "모집단",
    "표준편차",
    "평균",
    "분산",
    "정규분포",
    "상관분석",
    "회귀분석",

    # 통계 프로그램
    "SPSS",
    "AMOS",
    "PLS",

    # 통신사
    "SKT",
    "SK텔레콤",
    "KT",
    "LG U+",
    "LG유플러스",

    # 데이터
    "데이터",
    "셀프 데이터",
    "크로스 테이블",
    "crosstab",
    "변수",
    "범주형 변수",
    "연속형 변수",
    "명목척도",
    "서열척도",
    "등간척도",
    "비율척도",
]


# =========================================================
# 기본 시스템 프롬프트
# =========================================================

SYSTEM_PROMPT = """
당신은 한국어 대학 강의 전사 결과를 교정하는 전문 전사 교정기입니다.

당신의 목적은 음성인식(STT)이 잘못 인식한 표현을
강의의 문맥과 전문용어를 고려하여 교정하는 것입니다.

반드시 다음 규칙을 지키세요.

1. 원문에 없는 새로운 사실을 추가하지 마세요.
2. 교수자가 말하지 않은 설명을 만들어내지 마세요.
3. 숫자, 통계값, 날짜, 비율을 임의로 변경하지 마세요.
4. 전문용어가 음성인식 과정에서 잘못 변환된 경우에만 교정하세요.
5. 문맥이 불확실하면 원래 표현을 유지하세요.
6. 단순한 말투나 구어체를 지나치게 문어체로 바꾸지 마세요.
7. 의미가 바뀌는 문장 재작성은 하지 마세요.
8. 동일한 전문용어는 가능한 한 동일한 표현으로 통일하세요.
9. 영어 전문용어가 명확한 경우 한국어와 영어를 함께 표시할 수 있습니다.
10. 교정 결과는 원래 강의 내용을 최대한 보존해야 합니다.
11. 요약하지 마세요.
12. 내용을 삭제하지 마세요.
13. 문맥상 추측만 가능한 경우 억지로 수정하지 마세요.
"""


# =========================================================
# Ollama 요청
# =========================================================

def call_ollama(
    prompt: str,
    system_prompt: str = SYSTEM_PROMPT
) -> str:

    url = OLLAMA_BASE_URL.rstrip("/") + "/api/chat"

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "stream": False,
        "options": {
            "temperature": 0.0
        }
    }

    logger.info(
        "Ollama 요청 | model=%s | prompt_length=%d",
        OLLAMA_MODEL,
        len(prompt)
    )

    try:

        response = requests.post(
            url,
            json=payload,
            timeout=OLLAMA_TIMEOUT
        )

        response.raise_for_status()

        data = response.json()

        message = data.get("message", {})
        content = message.get("content", "")

        if not content:
            raise RuntimeError(
                "Ollama 응답에 content가 없습니다."
            )

        return content.strip()

    except requests.exceptions.ConnectionError as e:

        raise RuntimeError(
            "Ollama 서버에 연결할 수 없습니다. "
            "Ollama가 실행 중인지 확인해주세요."
        ) from e

    except requests.exceptions.Timeout as e:

        raise RuntimeError(
            "Ollama 응답 시간이 초과되었습니다."
        ) from e

    except requests.exceptions.HTTPError as e:

        raise RuntimeError(
            f"Ollama HTTP 오류가 발생했습니다: {e}"
        ) from e

    except Exception as e:

        logger.exception("Ollama 요청 실패")

        raise RuntimeError(
            f"AI 교정 처리 중 오류가 발생했습니다: {e}"
        ) from e


# =========================================================
# 긴 텍스트 분할
# =========================================================

def split_text(
    text: str,
    max_chars: int = 7000
) -> List[str]:

    text = text.strip()

    if not text:
        return []

    if len(text) <= max_chars:
        return [text]

    paragraphs = re.split(
        r"\n+",
        text
    )

    chunks = []
    current = []

    current_length = 0

    for paragraph in paragraphs:

        paragraph = paragraph.strip()

        if not paragraph:
            continue

        paragraph_length = len(paragraph)

        if (
            current
            and current_length + paragraph_length + 1
            > max_chars
        ):
            chunks.append(
                "\n".join(current)
            )

            current = []
            current_length = 0

        current.append(paragraph)

        current_length += paragraph_length + 1

    if current:
        chunks.append(
            "\n".join(current)
        )

    return chunks


# =========================================================
# 전문용어 사전 문자열
# =========================================================

def build_term_dictionary() -> str:

    return ", ".join(DOMAIN_TERMS)


# =========================================================
# 전사 교정 프롬프트
# =========================================================

def build_correction_prompt(
    transcript: str,
    context: Optional[Dict[str, Any]] = None
) -> str:

    context_text = ""

    if context:

        try:
            context_text = json.dumps(
                context,
                ensure_ascii=False,
                indent=2
            )

        except Exception:
            context_text = str(context)

    return f"""
다음은 한국어 대학 강의의 음성인식 결과입니다.

목표는 음성인식 오류를 강의 문맥에 맞게 교정하는 것입니다.

### 전문용어 후보 사전

{build_term_dictionary()}

### 지금까지 파악된 강의 문맥

{context_text if context_text else "(아직 없음)"}

### 원본 전사

--- BEGIN TRANSCRIPT ---

{transcript}

--- END TRANSCRIPT ---

다음 기준으로 교정하세요.

- 음성인식 오류가 명확한 전문용어를 교정합니다.
- 같은 개념은 같은 용어로 통일합니다.
- 숫자와 통계값은 그대로 유지합니다.
- 문장의 의미는 그대로 유지합니다.
- 불확실한 표현은 그대로 둡니다.
- 새로운 내용을 추가하지 않습니다.
- 요약하지 않습니다.

교정된 전사만 출력하세요.
"""


# =========================================================
# 단일 chunk 교정
# =========================================================

def correct_chunk(
    transcript: str,
    context: Optional[Dict[str, Any]] = None
) -> str:

    if not transcript.strip():
        return ""

    prompt = build_correction_prompt(
        transcript,
        context
    )

    result = call_ollama(prompt)

    return result.strip()


# =========================================================
# 전체 전사 교정
# =========================================================

def correct_transcript(
    transcript: str,
    context: Optional[Dict[str, Any]] = None,
    progress_callback=None
) -> str:

    if not transcript or not transcript.strip():
        return ""

    chunks = split_text(
        transcript,
        max_chars=7000
    )

    if not chunks:
        return ""

    corrected_chunks = []

    total = len(chunks)

    logger.info(
        "전사 교정 시작 | chunks=%d | model=%s",
        total,
        OLLAMA_MODEL
    )

    for index, chunk in enumerate(chunks):

        logger.info(
            "전사 교정 chunk 처리 | %d/%d",
            index + 1,
            total
        )

        try:

            corrected = correct_chunk(
                chunk,
                context=context
            )

            if corrected:
                corrected_chunks.append(
                    corrected
                )
            else:
                # AI 응답이 비어 있으면 원문 보존
                corrected_chunks.append(
                    chunk
                )

        except Exception:

            logger.exception(
                "전사 교정 실패 | chunk=%d/%d",
                index + 1,
                total
            )

            # 교정 실패 시 원문을 버리지 않음
            corrected_chunks.append(
                chunk
            )

        if progress_callback:

            percent = int(
                ((index + 1) / total) * 100
            )

            progress_callback(percent)

    corrected_text = "\n\n".join(
        corrected_chunks
    ).strip()

    logger.info(
        "전사 교정 완료 | original=%d | corrected=%d",
        len(transcript),
        len(corrected_text)
    )

    return corrected_text