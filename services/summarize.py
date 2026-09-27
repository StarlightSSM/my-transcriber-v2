"""
Ollama 기반 강의 분석 서비스

역할:
1. 전사 결과를 Ollama로 전달
2. Qwen3를 이용해 강의 요약
3. 핵심 내용 추출
4. 키워드 추출
5. 챕터 생성
6. Ollama가 없을 경우 fallback 분석 제공
"""

import json
import os
import re
import urllib.request

from typing import Any, Dict, List


# ============================================================
# Ollama 설정
# ============================================================

OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://127.0.0.1:11434/api/generate"
)

OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "qwen3:8b"
)


# ============================================================
# Qwen3 thinking 제거
# ============================================================

def _strip_thinking(
    text: str
):

    text = re.sub(
        r"<think>.*?</think>",
        "",
        text,
        flags=re.S | re.I
    )

    return text.strip()


# ============================================================
# JSON 추출
# ============================================================

def _extract_json(
    text: str
):

    text = _strip_thinking(
        text
    )


    text = (
        text
        .replace("```json", "")
        .replace("```", "")
        .strip()
    )


    start = text.find(
        "{"
    )

    end = text.rfind(
        "}"
    )


    if start < 0 or end <= start:

        raise ValueError(
            "Ollama 응답에서 JSON 객체를 찾을 수 없습니다."
        )


    return json.loads(
        text[start:end + 1]
    )


# ============================================================
# Ollama 호출
# ============================================================

def _ollama(
    prompt: str,
    timeout: int = 300
):

    payload = json.dumps({

        "model": OLLAMA_MODEL,

        "prompt": prompt,

        "stream": False,

        "options": {
            "temperature": 0.1,
            "num_ctx": 16384,
        },

    }).encode(
        "utf-8"
    )


    request = urllib.request.Request(

        OLLAMA_URL,

        data=payload,

        headers={
            "Content-Type":
                "application/json"
        },

        method="POST",
    )


    with urllib.request.urlopen(
        request,
        timeout=timeout
    ) as response:

        body = json.loads(
            response.read().decode(
                "utf-8"
            )
        )


    return body.get(
        "response",
        ""
    )


# ============================================================
# 리스트 정리
# ============================================================

def _clean_list(
    value: Any
) -> List[str]:

    if not isinstance(
        value,
        list
    ):

        return []


    return [
        str(x).strip()
        for x in value
        if str(x).strip()
    ]


# ============================================================
# Ollama 실패 시 fallback
# ============================================================

def _fallback(
    segments: List[Dict[str, Any]]
):

    text = " ".join(
        s.get(
            "text",
            ""
        ).strip()
        for s in segments
    ).strip()


    sentences = [
        s.strip()
        for s in re.split(
            r"(?<=[.!?。！？])\s+",
            text
        )
        if s.strip()
    ]


    summary = (
        " ".join(
            sentences[:8]
        )
        if sentences
        else text[:1200]
    )


    # 통계학 / 데이터 분석 관련 용어
    vocabulary = [

        "카이제곱",
        "교차분석",
        "교차표",
        "독립성",
        "기대빈도",
        "관측빈도",
        "정규성",
        "표준편차",
        "표본",
        "5S",
        "t-test",
        "Welch",
        "Levene",
        "ANOVA",
        "일원배치 분산분석",
        "사후검정",
        "Tukey",
        "Scheffe",
        "독립변수",
        "종속변수",
        "명목변수",
        "교통변수",
        "SPSS",
        "플레스터",
        "스윙",
        "테세트",
        "성별",
    ]


    lower = text.lower()


    keywords = [
        term
        for term in vocabulary
        if term.lower() in lower
    ]


    if not keywords:

        keywords = [
            word
            for word in re.findall(
                r"[가-힣A-Za-z0-9]{2,}",
                text
            )[:10]
        ]


    # --------------------------------------------------------
    # fallback 챕터
    # --------------------------------------------------------

    duration = (
        float(
            segments[-1].get(
                "end",
                0
            )
        )
        if segments
        else 0.0
    )


    if duration > 0:

        count = (
            3
            if duration >= 20 * 60
            else 2
            if duration >= 8 * 60
            else 1
        )


        boundaries = [
            int(
                i * duration / count
            )
            for i in range(count)
        ]

    else:

        boundaries = [0]


    chapters = []


    for i, start in enumerate(
        boundaries
    ):

        end = (
            boundaries[i + 1]
            if i + 1 < len(boundaries)
            else duration
        )


        chunk = " ".join(

            s.get(
                "text",
                ""
            )

            for s in segments

            if (
                float(
                    s.get(
                        "start",
                        0
                    )
                ) >= start

                and

                float(
                    s.get(
                        "start",
                        0
                    )
                ) < end
            )
        )


        title = (
            chunk[:32].strip() + "…"
            if chunk
            else f"강의 내용 {i + 1}"
        )


        chapters.append({
            "start": start,
            "title": title,
        })


    return {

        "summary":
            summary
            or
            "전사 결과를 바탕으로 한 요약을 생성하지 못했습니다.",

        "key_points":
            sentences[:8],

        "keywords":
            keywords[:15],

        "chapters":
            chapters,

        "model":
            "fallback",
    }


# ============================================================
# 강의 분석
# ============================================================

def analyze_lecture(
    segments: List[Dict[str, Any]]
):

    if not segments:

        return {

            "summary":
                "전사 결과가 없습니다.",

            "key_points": [],

            "keywords": [],

            "chapters": [],

            "model": "none",
        }


    # --------------------------------------------------------
    # timestamp 포함 전사 생성
    # --------------------------------------------------------

    lines = []


    for segment in segments:

        lines.append(

            f"["
            f"{float(segment.get('start', 0)):.1f}"
            f"-"
            f"{float(segment.get('end', 0)):.1f}"
            f"] "
            f"{segment.get('text', '').strip()}"
        )


    transcript = "\n".join(
        lines
    )


    # --------------------------------------------------------
    # 너무 긴 강의 처리
    # --------------------------------------------------------

    max_chars = 50000


    if len(transcript) > max_chars:

        transcript_for_prompt = (

            transcript[:25000]

            + "\n...[중간 생략]...\n"

            + transcript[-25000:]
        )

    else:

        transcript_for_prompt = transcript


    # --------------------------------------------------------
    # Qwen3 Prompt
    # --------------------------------------------------------

    prompt = f"""

당신은 한국어 대학 강의 분석기입니다.

아래 내용은 음성인식(STT)을 통해 생성된 강의 전사 결과입니다.
일부 표현은 음성인식 과정에서 잘못 인식되었을 수 있습니다.

목표:

1. 강의의 실제 내용을 근거로 짧고 정확한 요약을 작성합니다.
2. 핵심 내용을 5~10개 bullet로 추출합니다.
3. 실제 강의에 등장한 전문용어만 키워드로 추출합니다.
4. 강의 흐름에 따라 3~8개의 챕터를 만듭니다.
5. 챕터의 start는 반드시 아래 전사의 타임스탬프를 기준으로 합니다.

중요 규칙:

- 원문에 없는 사실을 만들지 마세요.
- 원문에 없는 숫자를 만들지 마세요.
- 통계값을 임의로 수정하지 마세요.
- 새로운 예시를 만들지 마세요.
- 교수자의 주장을 임의로 확대해석하지 마세요.
- 확실하지 않은 전문용어를 억지로 수정하지 마세요.
- 강의에서 실제로 설명한 내용만 요약하세요.
- 전문용어는 문맥상 명백한 경우에만 자연스럽게 정리하세요.
- 반드시 JSON만 출력하세요.
- markdown 코드블록을 사용하지 마세요.

JSON 형식:

{{
  "summary":
    "3~6문장의 자연스러운 한국어 요약",

  "key_points":
    [
      "핵심 내용 1",
      "핵심 내용 2"
    ],

  "keywords":
    [
      "키워드1",
      "키워드2"
    ],

  "chapters":
    [
      {{
        "start": 0,
        "title": "챕터 제목"
      }}
    ]
}}

전사:

{transcript_for_prompt}

"""


    try:

        raw = _ollama(
            prompt
        )


        result = _extract_json(
            raw
        )


        result = {

            "summary":
                str(
                    result.get(
                        "summary",
                        ""
                    )
                ).strip(),

            "key_points":
                _clean_list(
                    result.get(
                        "key_points"
                    )
                ),

            "keywords":
                _clean_list(
                    result.get(
                        "keywords"
                    )
                ),

            "chapters":
                (
                    result.get(
                        "chapters"
                    )
                    if isinstance(
                        result.get(
                            "chapters"
                        ),
                        list
                    )
                    else []
                ),

            "model":
                OLLAMA_MODEL,
        }


        if not result["summary"]:

            raise ValueError(
                "요약이 비어 있습니다."
            )


        # ----------------------------------------------------
        # 챕터 timestamp 정규화
        # ----------------------------------------------------

        duration = float(
            segments[-1].get(
                "end",
                0
            )
        )


        normalized = []


        for chapter in result["chapters"]:

            try:

                start = max(
                    0.0,
                    min(
                        float(
                            chapter.get(
                                "start",
                                0
                            )
                        ),
                        duration
                    )
                )


                title = str(
                    chapter.get(
                        "title",
                        ""
                    )
                ).strip()


                if title:

                    normalized.append({

                        "start": start,

                        "title": title,
                    })


            except (
                TypeError,
                ValueError
            ):

                continue


        result["chapters"] = sorted(
            normalized,
            key=lambda x: x["start"]
        )[:8]


        return result


    except Exception:

        # Ollama가 실행되지 않아도
        # 전사 결과 자체는 사용할 수 있도록 fallback
        return _fallback(
            segments
        )