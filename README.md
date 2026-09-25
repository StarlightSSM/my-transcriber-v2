# 🎙️ my-transcriber

> **강의·회의 음성을 텍스트로 변환하고, AI를 활용해 핵심 내용을 자동으로 정리하는 로컬 기반 음성 기록 서비스**

`my-transcriber`는 MP3, MP4, WAV, M4A 등의 음성·영상 파일을 업로드하면 **음성 인식 → 텍스트 변환 → AI 요약 → 핵심 포인트 및 챕터 생성 → 문서 내보내기**까지 한 번에 처리할 수 있는 Flask 기반 웹 애플리케이션입니다.

음성 인식에는 **faster-whisper**, AI 요약에는 **Ollama를 통한 로컬 LLM**을 사용합니다.

외부 AI API에 의존하지 않고 사용자의 PC에서 주요 AI 처리를 수행하는 것을 목표로 설계했습니다.

---

## ✨ 주요 기능

### 1. 🎧 음성·영상 파일 업로드

지원 형식:

* MP3
* MP4
* WAV
* M4A
* WEBM

업로드 파일은 서버의 `uploads/` 디렉터리에 저장됩니다.

기본 최대 업로드 용량은 **2GB**입니다.

---

### 2. 🎙️ AI 음성 인식

**faster-whisper**를 사용하여 음성을 텍스트로 변환합니다.

현재 기본 설정:

```text
Model: small
Device: CPU
Compute Type: int8
Language: Korean
```

음성 인식 결과에는 각 문장의 시작·종료 시간이 포함됩니다.

예:

```json
{
  "start": 12.35,
  "end": 18.72,
  "text": "오늘은 데이터 분석의 기본 개념에 대해서 살펴보겠습니다."
}
```

이를 이용해 단순한 전체 transcript뿐만 아니라 **시간 기반 챕터와 핵심 구간**을 생성할 수 있습니다.

---

### 3. 🔍 오디오 스트림 검증

영상 파일에 오디오 트랙이 존재하는지 먼저 확인합니다.

예를 들어 영상만 포함된 MP4 파일:

```text
MP4
 └── Video: H.264
 └── Audio: 없음
```

을 업로드하면 Whisper 단계에서 모호한 오류가 발생하는 대신 사용자에게 명확한 오류 메시지를 제공합니다.

```text
이 파일에서 오디오 트랙을 찾을 수 없습니다.
음성이 포함된 MP3, MP4, WAV, M4A 파일을 업로드해주세요.
```

이 검증에는 **PyAV**를 사용합니다.

---

### 4. 📝 Transcript 생성

음성 인식 결과를 하나의 텍스트로 결합하여 전체 강의/회의 내용을 제공합니다.

예:

```text
오늘은 인공지능의 기본적인 개념을 살펴보겠습니다.

먼저 머신러닝과 딥러닝의 차이를 알아보겠습니다.

머신러닝은 데이터를 기반으로 패턴을 학습하는 방법입니다.
```

---

### 5. 🧠 로컬 LLM 기반 AI 요약

**Ollama**를 이용해 사용자의 PC에서 LLM을 실행합니다.

기본 모델:

```text
gemma3:4b
```

처리 구조:

```text
Transcript
     ↓
Ollama
     ↓
Gemma 3 4B
     ↓
┌─────────────────┐
│ 전체 요약        │
│ 핵심 포인트      │
│ 키워드           │
│ 챕터             │
└─────────────────┘
```

외부 AI API를 사용하지 않고 로컬 LLM을 이용하기 때문에 API 호출 비용 없이 개발 및 테스트할 수 있습니다.

---

### 6. 📌 핵심 포인트 추출

강의나 회의 내용에서 중요한 내용을 구조화합니다.

예:

```text
1. 머신러닝과 딥러닝의 차이
2. 지도학습과 비지도학습
3. 데이터 전처리의 중요성
4. 모델 평가 방법
```

---

### 7. 🏷️ 키워드 추출

Transcript를 분석하여 주요 키워드를 생성합니다.

예:

```text
Machine Learning
Deep Learning
Data Preprocessing
Classification
Regression
```

---

### 8. 📚 챕터 생성

Transcript의 시간 정보를 이용해 강의 내용을 구간별로 구성합니다.

예:

```text
00:00 - 05:32
강의 소개

05:33 - 15:21
머신러닝 기본 개념

15:22 - 27:10
지도학습과 비지도학습

27:11 - 39:42
모델 평가 방법
```

---

### 9. 📄 다양한 형식으로 내보내기

현재 지원하는 출력 형식:

| 형식   | 용도         |
| ---- | ---------- |
| TXT  | 일반 텍스트     |
| SRT  | 자막         |
| DOCX | 문서 편집      |
| PDF  | 문서 보관 및 공유 |

향후 JSON 및 Markdown export를 추가할 수 있습니다.

---

## 🏗️ 시스템 구조

```text
                         ┌──────────────────┐
                         │   Web Browser    │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │ Flask Web Server │
                         └────────┬─────────┘
                                  │
                         Upload / Job 생성
                                  │
                                  ▼
                    ┌─────────────────────────┐
                    │     File Validation     │
                    │      PyAV / Audio       │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │     faster-whisper      │
                    │    Speech-to-Text       │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │       Transcript        │
                    │   Timestamp Segments    │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │         Ollama          │
                    │       Gemma 3 4B        │
                    └────────────┬────────────┘
                                 │
                  ┌──────────────┼──────────────┐
                  ▼              ▼              ▼
               Summary       Key Points      Chapters
                  │              │              │
                  └──────────────┼──────────────┘
                                 ▼
                    ┌─────────────────────────┐
                    │        Exporters        │
                    │ TXT / SRT / DOCX / PDF  │
                    └─────────────────────────┘
```

---

## 📁 프로젝트 구조

```text
my-transcriber/
│
├── app.py
├── requirements.txt
├── .env
├── .env.example
├── run.ps1
├── README.md
├── .gitignore
│
├── services/
│   ├── __init__.py
│   ├── transcribe.py
│   ├── summarize.py
│   └── exporters.py
│
├── templates/
│   └── index.html
│
├── uploads/
│   └── .gitkeep
│
├── outputs/
│   └── .gitkeep
│
├── logs/
│   └── .gitkeep
│
└── jobs.db
```

### 주요 파일 설명

| 파일                       | 역할                   |
| ------------------------ | -------------------- |
| `app.py`                 | Flask 서버 및 API       |
| `services/transcribe.py` | faster-whisper 음성 인식 |
| `services/summarize.py`  | Ollama 기반 AI 요약      |
| `services/exporters.py`  | TXT/SRT/DOCX/PDF 생성  |
| `templates/index.html`   | 웹 UI                 |
| `uploads/`               | 업로드 원본 파일            |
| `outputs/`               | 생성된 결과 파일            |
| `logs/`                  | 서버 로그                |
| `jobs.db`                | 작업 상태 및 결과 관리        |

---

# 🛠️ 개발 환경

## 요구사항

* Windows 10/11
* Python 3.10+
* PowerShell
* Ollama
* 충분한 디스크 공간
* 음성 인식 및 LLM 실행을 위한 CPU/RAM

GPU가 없어도 CPU 환경에서 실행할 수 있도록 기본 설정되어 있습니다.

---

# 🚀 설치 방법

## 1. 프로젝트 다운로드

```powershell
cd C:\Users\sumin\Desktop
```

프로젝트 폴더로 이동합니다.

```powershell
cd my-transcriber-v2\my-transcriber-v2
```

---

## 2. 가상환경 생성

```powershell
python -m venv .venv
```

가상환경 활성화:

```powershell
.\.venv\Scripts\Activate.ps1
```

정상적으로 활성화되면:

```text
(.venv) PS C:\Users\...
```

형태로 표시됩니다.

---

## 3. Python 패키지 설치

```powershell
pip install -r requirements.txt
```

설치되는 주요 패키지:

```text
Flask
faster-whisper
PyAV
requests
python-dotenv
python-docx
reportlab
Werkzeug
```

---

# 🤖 Ollama 설치

Ollama는 로컬에서 LLM을 실행하기 위한 런타임입니다.

공식 사이트에서 Windows용 Ollama를 설치합니다.

설치 후 PowerShell을 새로 열고:

```powershell
ollama --version
```

정상적으로 버전이 출력되는지 확인합니다.

---

## Gemma 3 설치

기본 모델을 다운로드합니다.

```powershell
ollama pull gemma3:4b
```

설치된 모델 확인:

```powershell
ollama list
```

테스트:

```powershell
ollama run gemma3:4b
```

한국어 질문을 입력하여 응답이 오는지 확인합니다.

종료:

```text
/bye
```

---

# ⚙️ 환경변수 설정

`.env.example`을 복사하여 `.env`를 생성합니다.

```text
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=gemma3:4b
OLLAMA_TIMEOUT=300
```

### 환경변수 설명

| 변수                | 설명            | 기본값                      |
| ----------------- | ------------- | ------------------------ |
| `OLLAMA_BASE_URL` | Ollama API 주소 | `http://127.0.0.1:11434` |
| `OLLAMA_MODEL`    | 사용할 LLM       | `gemma3:4b`              |
| `OLLAMA_TIMEOUT`  | LLM 요청 제한시간   | `300`                    |

---

# ▶️ 실행

가상환경이 활성화된 상태에서:

```powershell
python app.py
```

서버가 실행되면 브라우저에서:

```text
http://127.0.0.1:5000
```

으로 접속합니다.

---

# 🔄 사용 방법

```text
1. 웹사이트 접속
        ↓
2. MP3 / MP4 업로드
        ↓
3. 파일 검증
        ↓
4. 음성 스트림 확인
        ↓
5. faster-whisper 음성 인식
        ↓
6. Transcript 생성
        ↓
7. Ollama + Gemma 요약
        ↓
8. 핵심 포인트 생성
        ↓
9. 키워드 생성
        ↓
10. 챕터 생성
        ↓
11. TXT / SRT / DOCX / PDF 다운로드
```

---

# 🔌 API

## Health Check

```http
GET /api/health
```

예상 응답:

```json
{
  "status": "ok",
  "ollama": true,
  "model": "gemma3:4b"
}
```

---

## 파일 업로드

```http
POST /api/upload
```

multipart/form-data 방식으로 파일을 전송합니다.

응답에는 작업 ID가 포함됩니다.

```json
{
  "job_id": "467430b64c704ef5baa180a4ade5673f"
}
```

---

## 작업 상태 조회

```http
GET /api/jobs/<job_id>
```

작업 진행률과 현재 상태를 확인할 수 있습니다.

예:

```json
{
  "status": "processing",
  "progress": 65
}
```

---

## 결과 다운로드

```text
GET /api/jobs/<job_id>/export/txt
GET /api/jobs/<job_id>/export/srt
GET /api/jobs/<job_id>/export/docx
GET /api/jobs/<job_id>/export/pdf
```

---

# 🧠 AI 처리 방식

## Speech-to-Text

```text
Audio
 ↓
faster-whisper
 ↓
Timestamped Segments
 ↓
Transcript
```

현재 기본 모델:

```text
small
```

CPU 환경:

```text
device = cpu
compute_type = int8
```

---

## Summarization

```text
Transcript
 ↓
Chunking
 ↓
Ollama
 ↓
Gemma 3 4B
 ↓
Structured JSON
 ↓
Summary
Key Points
Keywords
Chapters
```

긴 Transcript는 하나의 프롬프트로 처리하지 않고 여러 chunk로 나누어 처리한 뒤 결과를 통합하는 구조를 사용합니다.

이를 통해 긴 강의나 회의 녹취에도 대응할 수 있도록 설계했습니다.

---

# 🛡️ 오류 처리

현재 주요 오류 상황을 별도로 처리합니다.

### 오디오가 없는 영상

```text
이 파일에서 오디오 트랙을 찾을 수 없습니다.
```

### 파일이 존재하지 않는 경우

```text
입력 파일을 찾을 수 없습니다.
```

### 미디어 파일을 읽을 수 없는 경우

```text
미디어 파일을 읽을 수 없습니다.
파일이 손상되었거나 지원되지 않는 형식일 수 있습니다.
```

### 음성은 있지만 텍스트가 없는 경우

```text
음성에서 인식된 텍스트가 없습니다.
```

### Ollama 요약 실패

음성 인식 결과는 유지하고 AI 요약 단계만 실패하도록 설계하여, LLM 문제 때문에 전체 Transcript가 사라지지 않도록 합니다.

---

# 💾 데이터 및 개인정보

`my-transcriber`는 로컬 실행을 기본으로 합니다.

주요 데이터 흐름:

```text
사용자 파일
    ↓
로컬 Flask 서버
    ↓
로컬 faster-whisper
    ↓
로컬 Ollama
    ↓
로컬 결과 저장
```

따라서 개발 및 개인 사용 환경에서는 외부 AI API로 음성 데이터를 전송하지 않는 구조로 운영할 수 있습니다.

단, 실제 배포 시에는 서버 운영환경, 로그, 백업, 접근제어, 저장기간 등에 대한 별도의 개인정보 보호 설계가 필요합니다.

---

# 💰 비용

기본적인 로컬 실행 구조에서는 다음과 같습니다.

| 구성요소             | 비용       |
| ---------------- | -------- |
| Flask            | 무료       |
| Python           | 무료       |
| faster-whisper   | 무료/오픈소스  |
| PyAV             | 무료/오픈소스  |
| Ollama Local     | 무료       |
| Gemma 3 4B Local | 로컬 실행    |
| PDF/DOCX 생성      | 무료 라이브러리 |
| 외부 AI API        | 사용하지 않음  |

단, 실제 운영 서버를 구축할 경우에는 서버, 스토리지, 네트워크 등의 인프라 비용이 발생할 수 있습니다.

---

# 📌 현재 개발 상태

### Phase 1 — 기본 기능

* [x] Flask 웹 서버
* [x] 파일 업로드
* [x] 작업(Job) 관리
* [x] SQLite 상태 저장
* [x] faster-whisper 연동
* [x] 한국어 음성 인식
* [x] Timestamp segment 생성
* [x] 오디오 스트림 검증
* [x] 진행률 표시

### Phase 2 — AI 기능

* [x] Ollama 연동
* [x] Gemma 3 4B 연동
* [x] Transcript 기반 요약
* [x] 핵심 포인트 생성
* [x] 키워드 생성
* [x] 챕터 생성
* [x] 긴 Transcript chunk 처리

### Phase 3 — Export

* [x] TXT
* [x] SRT
* [x] DOCX
* [x] PDF

### Phase 4 — 서비스 고도화

* [ ] 사용자 인증
* [ ] 사용자별 파일 관리
* [ ] 작업 큐 시스템
* [ ] Celery / Redis
* [ ] 자동 파일 삭제 정책
* [ ] 대용량 파일 처리 최적화
* [ ] GPU inference
* [ ] 모델 선택 기능
* [ ] Markdown export
* [ ] JSON export
* [ ] 검색 기능
* [ ] Transcript 내 키워드 검색
* [ ] 문장별 재생 위치 이동
* [ ] 요약 결과 편집
* [ ] 챕터 클릭 → 해당 시간으로 이동
* [ ] Docker 배포
* [ ] HTTPS
* [ ] Production WSGI
* [ ] 모니터링 및 로깅 개선

---

# 🚧 향후 발전 방향

## 1. 강의 학습 도구

단순한 Transcript 생성기를 넘어 다음 기능을 추가할 수 있습니다.

```text
강의 영상
   ↓
Transcript
   ↓
AI Summary
   ↓
핵심 개념
   ↓
예상 시험문제
   ↓
Quiz
   ↓
Flashcard
```

---

## 2. 연구 및 업무 기록 도구

강의뿐만 아니라:

* 대학원 세미나
* 연구 미팅
* 인터뷰
* 회의
* 발표
* 온라인 강의

등으로 활용 범위를 확장할 수 있습니다.

---

## 3. 검색 가능한 지식베이스

여러 개의 Transcript를 저장한 뒤:

```text
강의 A
강의 B
세미나 C
회의 D
```

를 하나의 데이터베이스로 관리하고 자연어 검색을 제공할 수 있습니다.

향후에는 RAG를 적용하여:

```text
"지난번 AI Sustainability 관련 세미나에서
언급했던 주요 지표가 뭐였지?"
```

와 같은 질문에도 관련 Transcript를 검색하여 답변하도록 확장할 수 있습니다.

---

# 🎯 프로젝트 목표

`my-transcriber`의 궁극적인 목표는 단순한 음성→텍스트 변환기가 아니라,

> **음성 데이터를 구조화된 지식으로 변환하는 개인용 로컬 AI 지식 관리 서비스**

를 구축하는 것입니다.

핵심 파이프라인은 다음과 같습니다.

```text
Raw Audio
    ↓
Speech Recognition
    ↓
Structured Transcript
    ↓
LLM Understanding
    ↓
Summary / Keywords / Chapters
    ↓
Knowledge
```

---

# 📚 기술 스택

### Backend

* Python
* Flask
* SQLite

### AI / ML

* faster-whisper
* Ollama
* Gemma 3 4B

### Media Processing

* PyAV

### Document Generation

* python-docx
* ReportLab

### Frontend

* HTML
* CSS
* JavaScript

---

# 📄 License

개인 학습 및 연구 목적으로 개발되었습니다.

각 오픈소스 라이브러리와 AI 모델은 해당 프로젝트의 라이선스 및 이용 조건을 따릅니다.

---

# 👩‍💻 Author

**Sumin Shin**

Graduate Student
Big Data Application
Kyung Hee University

---

## 🌱 Project Vision

`my-transcriber`는 음성을 단순히 텍스트로 변환하는 것에서 끝나지 않고,

**Capture → Transcribe → Understand → Organize → Retrieve**

의 흐름을 하나의 로컬 AI 서비스로 구현하는 것을 목표로 합니다.
