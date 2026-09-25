# services/summarize.py

import json
import logging
import os
import re
from typing import Any, Dict, List

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


logger = logging.getLogger("summarization")


# =========================================================
# Ollama
# =========================================================

def call_ollama(
    prompt: str,
    system_prompt: str
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
            "temperature": 0.1
        }
    }

    try:

        response = requests.post(
            url,
            json=payload,
            timeout=OLLAMA_TIMEOUT
        )

        response.raise_for_status()

        data = response.json()

        content = (
            data
            .get("message", {})
            .get("content", "")
        )

        if not content:
            raise RuntimeError(
                "Ollama 응답 내용이 없습니다."
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

    except Exception as e:

        logger.exception(
            "Ollama 요약 요청 실패"
        )

        raise RuntimeError(
            f"AI 요약 처리 중 오류가 발생했습니다: {e}"
        ) from e


# =========================================================
# JSON 추출
# =========================================================

def extract_json(text: str) -> Dict[str, Any]:

    text = text.strip()

    # ```json ... ``` 제거
    text = re.sub(
        r"```json\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"```\s*$",
        "",
        text
    )

    text = text.strip()

    # 전체 JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 첫 번째 { ~ 마지막 } 탐색
    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1:

        candidate = text[start:end + 1]

        try:
            return json.loads(candidate)

        except json.JSONDecodeError:
            pass

    raise ValueError(
        "AI 응답에서 JSON을 찾을 수 없습니다."
    )


# =========================================================
# Chunk 분리
# =========================================================

def split_text(
    text: str,
    max_chars: int = 8000
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

        if (
            current
            and current_length
            + len(paragraph)
            + 1
            > max_chars
        ):

            chunks.append(
                "\n".join(current)
            )

            current = []
            current_length = 0

        current.append(
            paragraph
        )

        current_length += (
            len(paragraph) + 1
        )

    if current:
        chunks.append(
            "\n".join(current)
        )

    return chunks


# =========================================================
# Chunk 분석
# =========================================================

CHUNK_SYSTEM_PROMPT = """
당신은 대학 강의 전사 분석 전문가입니다.

주어진 전사만을 근거로 강의 내용을 구조화하세요.

중요 규칙:

1. 원문에 없는 내용을 만들지 마세요.
2. 추측을 사실처럼 쓰지 마세요.
3. 숫자와 통계값을 변경하지 마세요.
4. 교수자가 말하지 않은 개념을 추가하지 마세요.
5. 전사의 문맥을 유지하세요.
6. 전문용어는 일관된 이름을 사용하세요.
7. 핵심 내용과 예시는 구분하세요.
8. 불확실한 내용은 확정적으로 표현하지 마세요.

반드시 JSON만 반환하세요.
"""


def analyze_chunk(
    chunk: str
) -> Dict[str, Any]:

    prompt = f"""
다음 강의 전사 구간을 분석하세요.

--- BEGIN TRANSCRIPT ---

{chunk}

--- END TRANSCRIPT ---

다음 JSON 구조로 반환하세요.

{{
  "summary": "이 구간의 핵심 내용을 3~6문장으로 정리",
  "key_points": [
    "핵심 내용 1",
    "핵심 내용 2"
  ],
  "keywords": [
    "키워드1",
    "키워드2"
  ],
  "concepts": [
    {{
      "term": "개념명",
      "description": "강의에서 설명된 의미"
    }}
  ],
  "methods": [
    "통계 방법 또는 분석 방법"
  ],
  "examples": [
    "강의에서 제시된 사례 또는 예시"
  ]
}}
"""

    raw = call_ollama(
        prompt,
        CHUNK_SYSTEM_PROMPT
    )

    try:

        return extract_json(raw)

    except Exception:

        logger.exception(
            "Chunk JSON parsing 실패"
        )

        # JSON parsing 실패 시 최소 구조 반환
        return {
            "summary": raw,
            "key_points": [],
            "keywords": [],
            "concepts": [],
            "methods": [],
            "examples": []
        }


# =========================================================
# 최종 통합
# =========================================================

FINAL_SYSTEM_PROMPT = """
당신은 대학 강의 분석 결과를 통합하는 AI입니다.

여러 강의 구간의 분석 결과를 하나의 최종 결과로 통합하세요.

규칙:

1. 입력된 분석 결과만 사용하세요.
2. 새로운 사실을 추가하지 마세요.
3. 서로 다른 구간에서 같은 개념이 반복되면 통합하세요.
4. 숫자와 통계값을 변경하지 마세요.
5. 핵심 개념의 의미를 유지하세요.
6. 중요한 설명을 지나치게 압축하지 마세요.
7. 강의의 실제 흐름을 반영하세요.
8. 확실하지 않은 내용을 추측하지 마세요.

반드시 JSON만 반환하세요.
"""


def merge_analyses(
    analyses: List[Dict[str, Any]]
) -> Dict[str, Any]:

    serialized = json.dumps(
        analyses,
        ensure_ascii=False,
        indent=2
    )

    prompt = f"""
다음은 한 강의를 여러 구간으로 나누어 분석한 결과입니다.

이 결과들을 하나의 강의 분석 결과로 통합하세요.

--- BEGIN ANALYSES ---

{serialized}

--- END ANALYSES ---

다음 JSON 구조를 사용하세요.

{{
  "overview": "강의 전체 내용을 5~10문장 정도로 설명",
  "key_points": [
    "핵심 내용 1",
    "핵심 내용 2",
    "핵심 내용 3"
  ],
  "keywords": [
    "키워드1",
    "키워드2"
  ],
  "concepts": [
    {{
      "term": "개념명",
      "description": "개념 설명"
    }}
  ],
  "methods": [
    "분석 방법 또는 통계 방법"
  ],
  "chapters": [
    {{
      "title": "주제명",
      "summary": "해당 주제의 내용"
    }}
  ]
}}
"""

    raw = call_ollama(
        prompt,
        FINAL_SYSTEM_PROMPT
    )

    try:

        return extract_json(raw)

    except Exception:

        logger.exception(
            "최종 JSON parsing 실패"
        )

        return {
            "overview": raw,
            "key_points": [],
            "keywords": [],
            "concepts": [],
            "methods": [],
            "chapters": []
        }


# =========================================================
# 전체 요약
# =========================================================

def summarize_transcript(
    transcript: str,
    progress_callback=None
) -> Dict[str, Any]:

    if not transcript or not transcript.strip():
        return {
            "overview": "",
            "key_points": [],
            "keywords": [],
            "concepts": [],
            "methods": [],
            "chapters": []
        }

    chunks = split_text(
        transcript,
        max_chars=8000
    )

    logger.info(
        "AI 요약 시작 | chunks=%d | model=%s",
        len(chunks),
        OLLAMA_MODEL
    )

    analyses = []

    total = len(chunks)

    for index, chunk in enumerate(chunks):

        logger.info(
            "강의 구간 분석 | %d/%d",
            index + 1,
            total
        )

        analysis = analyze_chunk(
            chunk
        )

        analyses.append(
            analysis
        )

        if progress_callback:

            # 전체 과정에서
            # 0~70%를 chunk 분석에 사용
            percent = int(
                ((index + 1) / total) * 70
            )

            progress_callback(percent)

    # -----------------------------------------------------
    # 최종 통합
    # -----------------------------------------------------

    logger.info(
        "강의 분석 결과 통합 시작"
    )

    result = merge_analyses(
        analyses
    )

    if progress_callback:
        progress_callback(100)

    logger.info(
        "AI 요약 완료 | chunks=%d",
        len(chunks)
    )

    return result