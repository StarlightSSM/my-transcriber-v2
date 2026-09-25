# my-transcriber v2
# 음성 녹음 파일 요약 프로그램

강의 MP3/MP4 등을 업로드하면

**음성 전사 → AI 요약 → 핵심 포인트 → 챕터 → TXT/SRT/PDF/DOCX/JSON 다운로드**

까지 로컬에서 처리하는 개인용 Flask 웹앱입니다.

## 1. 최종 구조

```text
my-transcriber-v2/
├─ app.py
├─ requirements.txt
├─ .env.example
├─ run.ps1
├─ jobs.db                 # 최초 실행 시 자동 생성
├─ uploads/
├─ outputs/
├─ logs/
├─ services/
│  ├─ __init__.py
│  ├─ transcribe.py
│  ├─ summarize.py
│  └─ exporters.py
└─ templates/
   └─ index.html
```

## 2. 개발 환경

권장:
- Windows 10/11
- Python 3.11
- VS Code
- Git
- Ollama
- CPU 실행 가능. GPU가 있으면 이후 CUDA 전환 가능

## 3. 최초 설치

PowerShell에서 프로젝트 폴더로 이동:

```powershell
cd "C:\Users\sumin\Desktop\Extract_Sync_Media\my-transcriber-v2"
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

## 4. Ollama 설정

Ollama를 설치한 뒤 실행하고, `.env`의 `OLLAMA_MODEL`에 실제 설치한 모델명을 넣습니다.

예:

```powershell
ollama pull gemma3:4b
ollama list
```

그 다음:

```powershell
python app.py
```

브라우저:

```text
http://127.0.0.1:5000
```

## 5. 동작 흐름

```text
브라우저
  ↓
Flask /api/upload
  ↓
uploads/
  ↓
background thread
  ↓
faster-whisper
  ↓
transcript + timestamp
  ↓
Ollama
  ↓
summary / key_points / keywords / chapters
  ↓
브라우저 결과 화면
  ↓
TXT / SRT / PDF / DOCX / JSON
```

## 6. 현재 구현된 기능

- MP3 / MP4 / WAV / M4A / WEBM 업로드
- 최대 2GB 업로드
- faster-whisper CPU int8
- 한국어 전사
- 타임스탬프 보존
- 전사 진행률
- SQLite 작업 상태 저장
- Ollama 로컬 요약
- 긴 강의를 chunk → 요약 → 통합하는 계층형 요약
- 핵심 내용
- 키워드
- 챕터 타임스탬프
- TXT / SRT / DOCX / PDF / JSON
- Ollama 연결 상태 표시
- 오류 로그
- 서버 재시작 후 작업 메타데이터 보존

## 7. 개발 단계

### Phase 1 — 로컬 기능 검증
1. 짧은 MP3 3~5분으로 전사
2. 20~30분 강의로 전사
3. Ollama 요약
4. TXT/SRT 다운로드 확인
5. PDF/DOCX 확인

### Phase 2 — 품질 개선
- Whisper model 선택
- 한국어 hallucination 감소
- 문장 부호 보정
- 중복 문장 제거
- chapter 품질 개선
- 요약 프롬프트 개선

### Phase 3 — 서비스화
- Redis/Celery 또는 작업 큐
- 사용자별 job 분리
- 파일 자동 삭제 정책
- 인증
- rate limit
- CSRF
- reverse proxy
- HTTPS
- Docker
- 배포 서버

## 8. 배포 직전 체크리스트

- [ ] `debug=False`
- [ ] 개발용 Flask server 대신 Gunicorn/Waitress 등 WSGI 서버 사용
- [ ] HTTPS
- [ ] 인증/권한
- [ ] 업로드 파일 바이러스/악성 파일 정책
- [ ] 파일 크기/시간 제한
- [ ] 업로드 자동 삭제
- [ ] 로그 개인정보 점검
- [ ] Ollama 서버 외부 노출 금지
- [ ] 작업 큐 적용
- [ ] 동시 작업 제한
- [ ] 장애 복구
- [ ] 환경변수 분리
- [ ] secret 저장소 사용
- [ ] DB 백업 정책
- [ ] Docker 이미지 고정
- [ ] 도메인 연결
- [ ] HTTPS 인증서
- [ ] 모니터링

## 9. 중요한 설계 원칙

이 버전에서는 요약 실패가 전사 실패로 처리되지 않습니다.

즉:

```text
Whisper 성공 + Ollama 실패
        ↓
전사 결과는 정상 표시
        ↓
요약만 실패 상태로 표시
```

따라서 로컬 LLM을 설치하지 않았더라도 전사 도구로는 사용할 수 있습니다.

## 10. 기존 프로젝트에서 적용할 때

기존 `my-transcriber`를 바로 덮어쓰기보다 이 v2를 별도 폴더에서 먼저 실행하세요.

검증이 끝나면 기존 프로젝트에 필요한 파일만 병합하는 방식이 안전합니다.
