import json
import os
import re
import requests

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b")
TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "300"))


def _clean_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    return json.loads(text)


def _chunk_segments(segments, max_chars=9000):
    chunks, current, size = [], [], 0
    for seg in segments:
        line = f"[{seg['start']:.1f}s] {seg['text']}\n"
        if current and size + len(line) > max_chars:
            chunks.append(current)
            current, size = [], 0
        current.append(seg)
        size += len(line)
    if current:
        chunks.append(current)
    return chunks


def summarize_with_ollama(transcript, segments):
    if not transcript.strip():
        raise ValueError("전사 결과가 비어 있습니다.")

    # Long lectures are summarized hierarchically.
    chunks = _chunk_segments(segments)
    partials = []

    for chunk in chunks:
        source = "\n".join(
            f"[{s['start']:.1f}s] {s['text']}" for s in chunk
        )
        partials.append(_call_ollama(
            f"""
다음은 한국어 강의 전사 일부입니다.
사실을 추가하지 말고 원문에 근거해서 핵심만 정리하세요.

전사:
{source}

JSON 형식으로만 답하세요:
{{
  "overview": "2~4문장 요약",
  "key_points": ["핵심 내용 3~7개"],
  "keywords": ["핵심 키워드 3~10개"],
  "chapters": [
    {{"start": 0.0, "title": "주제"}}
  ]
}}
"""))

    if len(partials) == 1:
        result = partials[0]
    else:
        merged = "\n\n".join(json.dumps(x, ensure_ascii=False) for x in partials)
        result = _call_ollama(
            f"""
아래는 한 강의를 구간별로 요약한 중간 결과입니다.
중복을 제거하고 하나의 강의 요약으로 통합하세요.
사실을 추가하지 마세요. chapters의 start는 가능한 한 원래 타임스탬프를 유지하세요.

중간 결과:
{merged}

JSON만 출력:
{{
  "overview": "3~5문장",
  "key_points": ["핵심 내용 5~10개"],
  "keywords": ["키워드 5~15개"],
  "chapters": [
    {{"start": 0.0, "title": "주제"}}
  ]
}}
""")

    result["available"] = True
    return result


def _call_ollama(prompt):
    response = requests.post(
        f"{OLLAMA_BASE_URL.rstrip('/')}/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.2},
        },
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    return _clean_json(payload["response"])
