import atexit
import json
import logging
import os
import threading
from logging.handlers import RotatingFileHandler

from flask import Flask, jsonify, render_template, request, send_file
from werkzeug.utils import secure_filename

from services.export_docx import export_docx
from services.export_json import export_json
from services.export_pdf import export_pdf
from services.export_srt import export_srt
from services.export_txt import export_txt
from services.summarize import analyze_lecture
from services.transcribe import transcribe_media


# ============================================================
# 기본 경로
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
OUTPUT_FOLDER = os.path.join(BASE_DIR, "outputs")
LOG_FOLDER = os.path.join(BASE_DIR, "logs")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(LOG_FOLDER, exist_ok=True)


# ============================================================
# Flask
# ============================================================

app = Flask(__name__)

# 최대 2GB
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024 * 1024

ALLOWED_EXTENSIONS = {
    "mp3",
    "mp4",
    "wav",
    "m4a",
    "webm",
}


# ============================================================
# Logger
# ============================================================

def _logger(name, filename):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = RotatingFileHandler(
            os.path.join(LOG_FOLDER, filename),
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )

        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
            )
        )

        logger.addHandler(handler)

    return logger


server_logger = _logger(
    "server",
    "server.log"
)

error_logger = _logger(
    "error",
    "error.log"
)

transcription_logger = _logger(
    "transcription",
    "transcription.log"
)


# ============================================================
# 전역 상태
# ============================================================

state_lock = threading.Lock()

latest_result = {
    "stem": "",
    "filename": "",
    "text": "",
    "segments": [],
    "summary": "",
    "key_points": [],
    "keywords": [],
    "chapters": [],
    "model": "",
}

progress_state = {
    "percent": 0,
    "status": "idle",
    "error": "",
    "stage": "대기 중",
}


# ============================================================
# 파일 관련
# ============================================================

def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )


def _reset_state(filename):

    stem = os.path.splitext(filename)[0]

    with state_lock:

        latest_result.update({
            "stem": stem,
            "filename": filename,
            "text": "",
            "segments": [],
            "summary": "",
            "key_points": [],
            "keywords": [],
            "chapters": [],
            "model": "",
        })

        progress_state.update({
            "percent": 0,
            "status": "processing",
            "error": "",
            "stage": "파일 분석 중",
        })


# ============================================================
# 전사 + AI 분석
# ============================================================

def run_transcription(save_path, filename):

    try:

        # ----------------------------------------------------
        # Whisper 전사 진행률
        # ----------------------------------------------------

        def update_transcription(percent):

            with state_lock:

                progress_state["percent"] = max(
                    progress_state["percent"],
                    int(percent)
                )

                progress_state["stage"] = "음성 전사 중"


        # ----------------------------------------------------
        # Whisper
        # ----------------------------------------------------

        text, segments = transcribe_media(
            save_path,
            progress_callback=update_transcription
        )


        # ----------------------------------------------------
        # 전사 결과 저장
        # ----------------------------------------------------

        with state_lock:

            latest_result["text"] = text
            latest_result["segments"] = segments

            progress_state["percent"] = 91
            progress_state["stage"] = "AI 요약 준비 중"


        # ----------------------------------------------------
        # Ollama / Qwen3 분석
        # ----------------------------------------------------

        analysis = analyze_lecture(
            segments
        )


        # ----------------------------------------------------
        # 분석 결과 저장
        # ----------------------------------------------------

        with state_lock:

            latest_result["summary"] = analysis.get(
                "summary",
                ""
            )

            latest_result["key_points"] = analysis.get(
                "key_points",
                []
            )

            latest_result["keywords"] = analysis.get(
                "keywords",
                []
            )

            latest_result["chapters"] = analysis.get(
                "chapters",
                []
            )

            latest_result["model"] = analysis.get(
                "model",
                ""
            )

            progress_state["percent"] = 100
            progress_state["status"] = "done"
            progress_state["stage"] = "완료되었습니다."


        server_logger.info(
            "작업 완료 | file=%s | model=%s",
            filename,
            latest_result["model"]
        )


    except Exception as exc:

        error_logger.exception(
            "전사/분석 실패 | file=%s",
            filename
        )

        with state_lock:

            progress_state.update({
                "status": "error",
                "stage": "오류가 발생했습니다.",
                "error": str(exc),
            })


# ============================================================
# 상태 API용 데이터
# ============================================================

def _result_payload():

    with state_lock:

        return json.loads(
            json.dumps(
                latest_result,
                ensure_ascii=False
            )
        )


def _progress_payload():

    with state_lock:

        return dict(
            progress_state
        )


# ============================================================
# 메인 페이지
# ============================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# ============================================================
# Health Check
# ============================================================

@app.route("/api/health")
def api_health():

    return jsonify({
        "ok": True,
        "service": "my-transcriber",
    })


# ============================================================
# 업로드
# ============================================================

@app.route(
    "/upload",
    methods=["POST"]
)
@app.route(
    "/api/upload",
    methods=["POST"]
)
def upload():

    if "media" not in request.files:

        return jsonify({
            "ok": False,
            "error": "파일이 없습니다.",
        }), 400


    file = request.files["media"]


    if not file.filename:

        return jsonify({
            "ok": False,
            "error": "파일을 선택하세요.",
        }), 400


    if not allowed_file(file.filename):

        return jsonify({
            "ok": False,
            "error": (
                "MP3 / MP4 / WAV / M4A / WEBM "
                "파일만 업로드할 수 있습니다."
            ),
        }), 400


    filename = secure_filename(
        file.filename
    )


    # 같은 이름의 파일이 있으면 _1, _2...
    stem, ext = os.path.splitext(filename)

    candidate = filename
    index = 1

    while os.path.exists(
        os.path.join(
            UPLOAD_FOLDER,
            candidate
        )
    ):

        candidate = (
            f"{stem}_{index}{ext}"
        )

        index += 1


    filename = candidate


    save_path = os.path.join(
        UPLOAD_FOLDER,
        filename
    )


    file.save(
        save_path
    )


    _reset_state(
        filename
    )


    server_logger.info(
        "파일 업로드 완료 | file=%s",
        filename
    )


    # 백그라운드 전사
    thread = threading.Thread(
        target=run_transcription,
        args=(save_path, filename),
        daemon=True,
    )

    thread.start()


    return jsonify({
        "ok": True,
        "job_id": "latest",
        "filename": filename,
    })


# ============================================================
# 진행률
# ============================================================

@app.route("/progress")
@app.route("/api/progress")
def progress():

    return jsonify(
        _progress_payload()
    )


# ============================================================
# 결과
# ============================================================

@app.route("/api/result")
def api_result():

    return jsonify(
        _result_payload()
    )


# ============================================================
# 기존 프론트 호환용
# ============================================================

@app.route(
    "/api/jobs/<job_id>"
)
def api_job(job_id):

    return jsonify({
        "job_id": job_id,
        **_progress_payload(),
        "result": _result_payload(),
    })


# ============================================================
# 다운로드
# ============================================================

@app.route(
    "/download/<fmt>"
)
@app.route(
    "/api/download/<fmt>"
)
def download(fmt):

    fmt = fmt.lower()

    result = _result_payload()


    if not result["text"]:

        return jsonify({
            "ok": False,
            "error": "먼저 전사를 진행하세요.",
        }), 400


    stem = result.get(
        "stem"
    ) or "result"


    # --------------------------------------------------------
    # TXT
    # --------------------------------------------------------

    if fmt == "txt":

        output_path = os.path.join(
            OUTPUT_FOLDER,
            f"{stem}.txt"
        )

        export_txt(
            result["text"],
            output_path
        )


    # --------------------------------------------------------
    # SRT
    # --------------------------------------------------------

    elif fmt == "srt":

        output_path = os.path.join(
            OUTPUT_FOLDER,
            f"{stem}.srt"
        )

        export_srt(
            result["segments"],
            output_path
        )


    # --------------------------------------------------------
    # DOCX
    # --------------------------------------------------------

    elif fmt == "docx":

        output_path = os.path.join(
            OUTPUT_FOLDER,
            f"{stem}.docx"
        )

        paragraphs = group_into_paragraphs(
            result["segments"]
        )

        export_docx(
            paragraphs,
            output_path,
            title="강의 전사본"
        )


    # --------------------------------------------------------
    # PDF
    # --------------------------------------------------------

    elif fmt == "pdf":

        output_path = export_pdf(
            stem,
            result["text"],
            result["summary"],
            OUTPUT_FOLDER
        )


    # --------------------------------------------------------
    # JSON
    # --------------------------------------------------------

    elif fmt == "json":

        output_path = os.path.join(
            OUTPUT_FOLDER,
            f"{stem}_analysis.json"
        )

        export_json(
            result,
            output_path
        )


    else:

        return jsonify({
            "ok": False,
            "error": "지원하지 않는 형식입니다.",
        }), 400


    server_logger.info(
        "파일 다운로드 완료 | format=%s | path=%s",
        fmt,
        output_path
    )


    return send_file(
        output_path,
        as_attachment=True
    )


# ============================================================
# 문단 묶기
# ============================================================

def group_into_paragraphs(
    segments,
    gap_threshold=2.0
):

    if not segments:
        return []


    paragraphs = []

    current = [
        segments[0]["text"]
    ]


    for i in range(
        1,
        len(segments)
    ):

        gap = (
            float(segments[i]["start"])
            - float(segments[i - 1]["end"])
        )


        if gap >= gap_threshold:

            paragraphs.append(
                " ".join(current)
            )

            current = [
                segments[i]["text"]
            ]

        else:

            current.append(
                segments[i]["text"]
            )


    if current:

        paragraphs.append(
            " ".join(current)
        )


    return paragraphs


# ============================================================
# 오류 처리
# ============================================================

@app.errorhandler(413)
def too_large(error):

    return jsonify({
        "ok": False,
        "error": (
            "파일 크기가 너무 큽니다. "
            "최대 2GB까지 업로드할 수 있습니다."
        ),
    }), 413


@app.errorhandler(404)
def not_found(error):

    if request.path.startswith(
        "/api/"
    ):

        return jsonify({
            "ok": False,
            "error": "API 경로를 찾을 수 없습니다.",
            "path": request.path,
        }), 404


    return (
        "페이지를 찾을 수 없습니다.",
        404
    )


@app.errorhandler(500)
def internal_error(error):

    error_logger.exception(
        "500 Internal Server Error | path=%s",
        request.path
    )


    if request.path.startswith(
        "/api/"
    ):

        return jsonify({
            "ok": False,
            "error": "서버 내부 오류가 발생했습니다.",
        }), 500


    return (
        "서버 내부 오류가 발생했습니다.",
        500
    )


# ============================================================
# 종료
# ============================================================

@atexit.register
def shutdown_server():

    server_logger.info(
        "SERVER_SHUTDOWN"
    )


# ============================================================
# 실행
# ============================================================

if __name__ == "__main__":

    server_logger.info(
        "SERVER_START | upload=%s | output=%s",
        UPLOAD_FOLDER,
        OUTPUT_FOLDER
    )

    app.run(
        debug=True,
        use_reloader=False
    )