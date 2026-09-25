# app.py

import os
import threading
import atexit
import logging
from logging.handlers import RotatingFileHandler

from flask import (
    Flask,
    request,
    render_template,
    send_file,
    jsonify
)

from werkzeug.utils import secure_filename

from services.transcribe import transcribe_media
from services.correct import correct_transcript
from services.summarize import summarize_transcript

from services.export_txt import export_txt
from services.export_srt import export_srt
from services.export_docx import export_docx
from services.export_pdf import export_pdf


# =========================================================
# Flask 기본 설정
# =========================================================

app = Flask(__name__)

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

UPLOAD_FOLDER = os.path.join(
    BASE_DIR,
    "uploads"
)

OUTPUT_FOLDER = os.path.join(
    BASE_DIR,
    "outputs"
)

LOG_FOLDER = os.path.join(
    BASE_DIR,
    "logs"
)


# 지원 확장자
ALLOWED_EXTENSIONS = {
    "mp3",
    "mp4",
    "wav",
    "m4a",
    "webm"
}


# 최대 업로드 용량
# 2GB
app.config["MAX_CONTENT_LENGTH"] = (
    2 * 1024 * 1024 * 1024
)


# =========================================================
# 폴더 생성
# =========================================================

os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)

os.makedirs(
    OUTPUT_FOLDER,
    exist_ok=True
)

os.makedirs(
    LOG_FOLDER,
    exist_ok=True
)


# =========================================================
# Logging
# =========================================================

LOG_FORMAT = (
    "%(asctime)s | %(levelname)s | "
    "%(name)s | %(message)s"
)

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def create_logger(
    name,
    filename,
    level=logging.INFO
):

    logger = logging.getLogger(name)

    logger.setLevel(level)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        LOG_FORMAT,
        datefmt=DATE_FORMAT
    )

    file_handler = RotatingFileHandler(
        os.path.join(
            LOG_FOLDER,
            filename
        ),
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )

    file_handler.setFormatter(
        formatter
    )

    file_handler.setLevel(
        level
    )

    console_handler = logging.StreamHandler()

    console_handler.setFormatter(
        formatter
    )

    console_handler.setLevel(
        level
    )

    logger.addHandler(
        file_handler
    )

    logger.addHandler(
        console_handler
    )

    return logger


server_logger = create_logger(
    "server",
    "server.log",
    logging.INFO
)


error_logger = create_logger(
    "error",
    "error.log",
    logging.ERROR
)


transcription_logger = create_logger(
    "transcription",
    "transcription.log",
    logging.INFO
)


# =========================================================
# Werkzeug HTTP Logging
# =========================================================

werkzeug_logger = logging.getLogger(
    "werkzeug"
)


if not any(
    isinstance(
        handler,
        RotatingFileHandler
    )
    for handler in werkzeug_logger.handlers
):

    werkzeug_handler = RotatingFileHandler(
        os.path.join(
            LOG_FOLDER,
            "server.log"
        ),
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )

    werkzeug_handler.setFormatter(
        logging.Formatter(
            LOG_FORMAT,
            datefmt=DATE_FORMAT
        )
    )

    werkzeug_logger.addHandler(
        werkzeug_handler
    )


werkzeug_logger.setLevel(
    logging.INFO
)


# =========================================================
# 결과 상태
# =========================================================

latest_result = {
    "text": "",
    "corrected_text": "",
    "segments": [],
    "summary": {}
}


progress_state = {
    "percent": 0,
    "status": "idle",
    "stage": "",
    "error": ""
}


state_lock = threading.Lock()


# =========================================================
# 파일 확장자
# =========================================================

def allowed_file(filename):

    return (
        "."
        in filename
        and filename.rsplit(
            ".",
            1
        )[1].lower()
        in ALLOWED_EXTENSIONS
    )


# =========================================================
# 진행률 업데이트
# =========================================================

def set_progress(
    percent=None,
    status=None,
    stage=None,
    error=None
):

    with state_lock:

        if percent is not None:
            progress_state["percent"] = int(
                max(0, min(100, percent))
            )

        if status is not None:
            progress_state["status"] = status

        if stage is not None:
            progress_state["stage"] = stage

        if error is not None:
            progress_state["error"] = error


# =========================================================
# 전체 AI 처리
# =========================================================

def run_processing(
    save_path
):

    filename = os.path.basename(
        save_path
    )

    transcription_logger.info(
        "AI 전사 작업 시작 | file=%s",
        filename
    )

    set_progress(
        percent=0,
        status="processing",
        stage="음성 전사 준비",
        error=""
    )

    try:

        # =================================================
        # 1. Whisper 전사
        # =================================================

        def transcription_progress(
            value
        ):

            # Whisper 자체는 0~100
            # 전체 pipeline에서는 0~60
            mapped = int(
                value * 0.60
            )

            set_progress(
                percent=mapped,
                stage="음성 전사 중"
            )


        text, segments = transcribe_media(
            save_path,
            progress_callback=transcription_progress
        )


        transcription_logger.info(
            "1단계 전사 완료 | segments=%d",
            len(segments)
        )


        # =================================================
        # 2. 문맥/전문용어 교정
        # =================================================

        set_progress(
            percent=60,
            stage="전사 결과 문맥 교정 중"
        )


        def correction_progress(
            value
        ):

            # 60~80
            mapped = 60 + int(
                value * 0.20
            )

            set_progress(
                percent=mapped,
                stage="전문용어 및 문맥 교정 중"
            )


        corrected_text = correct_transcript(
            text,
            progress_callback=correction_progress
        )


        if not corrected_text:
            corrected_text = text


        transcription_logger.info(
            "2단계 전사 교정 완료 | corrected_length=%d",
            len(corrected_text)
        )


        # =================================================
        # 3. AI 요약
        # =================================================

        set_progress(
            percent=80,
            stage="강의 내용 분석 및 요약 중"
        )


        def summary_progress(
            value
        ):

            # 80~100
            mapped = 80 + int(
                value * 0.20
            )

            set_progress(
                percent=mapped,
                stage="강의 내용 분석 및 요약 중"
            )


        try:

            summary = summarize_transcript(
                corrected_text,
                progress_callback=summary_progress
            )

        except Exception as e:

            # 요약 실패가 전사 전체 실패가 되지 않도록 처리
            error_logger.exception(
                "AI 요약 실패 | file=%s",
                filename
            )

            summary = {
                "overview": "",
                "key_points": [],
                "keywords": [],
                "concepts": [],
                "methods": [],
                "chapters": [],
                "error": str(e)
            }


        # =================================================
        # 결과 저장
        # =================================================

        with state_lock:

            latest_result["text"] = text

            latest_result["corrected_text"] = (
                corrected_text
            )

            latest_result["segments"] = (
                segments
            )

            latest_result["summary"] = (
                summary
            )


            progress_state["percent"] = 100
            progress_state["status"] = "done"
            progress_state["stage"] = "처리 완료"
            progress_state["error"] = ""


        transcription_logger.info(
            "전체 처리 완료 | file=%s",
            filename
        )


    except Exception as e:

        with state_lock:

            progress_state["status"] = "error"

            progress_state["stage"] = (
                "처리 중 오류 발생"
            )

            progress_state["error"] = (
                str(e)
            )


        error_logger.exception(
            "AI 전사 작업 중 오류 발생 | file=%s",
            filename
        )

        transcription_logger.exception(
            "AI 전사 작업 실패 | file=%s",
            filename
        )


# =========================================================
# 문단 분리
# =========================================================

def group_into_paragraphs(
    segments,
    gap_threshold=2.0
):

    if not segments:
        return []

    paragraphs = []

    current_paragraph = [
        segments[0]["text"]
    ]

    for i in range(
        1,
        len(segments)
    ):

        previous_end = (
            segments[i - 1]["end"]
        )

        current_start = (
            segments[i]["start"]
        )

        gap = (
            current_start
            - previous_end
        )

        if gap >= gap_threshold:

            paragraphs.append(
                " ".join(
                    current_paragraph
                )
            )

            current_paragraph = [
                segments[i]["text"]
            ]

        else:

            current_paragraph.append(
                segments[i]["text"]
            )

    if current_paragraph:

        paragraphs.append(
            " ".join(
                current_paragraph
            )
        )

    return paragraphs


# =========================================================
# 메인 페이지
# =========================================================

@app.route("/")
def home():

    try:

        with state_lock:

            text = latest_result[
                "text"
            ]

            corrected_text = (
                latest_result[
                    "corrected_text"
                ]
            )

            segments = list(
                latest_result[
                    "segments"
                ]
            )

            summary = dict(
                latest_result[
                    "summary"
                ]
            )


        paragraphs = group_into_paragraphs(
            segments
        )


        return render_template(
            "index.html",

            text=text,

            corrected_text=(
                corrected_text
            ),

            paragraphs=paragraphs,

            summary=summary,

            processing=(
                progress_state[
                    "status"
                ] == "processing"
            )
        )


    except Exception:

        error_logger.exception(
            "메인 페이지 처리 중 오류 발생"
        )

        return (
            "서버 오류가 발생했습니다.",
            500
        )


# =========================================================
# 파일 업로드
# =========================================================

@app.route(
    "/upload",
    methods=["POST"]
)
def upload():

    try:

        if "media" not in request.files:

            server_logger.warning(
                "파일 업로드 실패 | 파일이 없음"
            )

            return (
                "파일이 없습니다.",
                400
            )


        file = request.files[
            "media"
        ]


        if file.filename == "":

            server_logger.warning(
                "파일 업로드 실패 | 파일명이 없음"
            )

            return (
                "파일을 선택하세요.",
                400
            )


        if not allowed_file(
            file.filename
        ):

            server_logger.warning(
                "지원하지 않는 파일 형식 | filename=%s",
                file.filename
            )

            return (
                "지원되는 파일 형식은 "
                "mp3, mp4, wav, m4a, webm입니다.",
                400
            )


        filename = secure_filename(
            file.filename
        )


        save_path = os.path.join(
            UPLOAD_FOLDER,
            filename
        )


        file.save(
            save_path
        )


        server_logger.info(
            "파일 업로드 완료 | file=%s",
            filename
        )


        # =================================================
        # 상태 초기화
        # =================================================

        with state_lock:

            latest_result[
                "text"
            ] = ""

            latest_result[
                "corrected_text"
            ] = ""

            latest_result[
                "segments"
            ] = []

            latest_result[
                "summary"
            ] = {}


            progress_state[
                "percent"
            ] = 0

            progress_state[
                "status"
            ] = "processing"

            progress_state[
                "stage"
            ] = "작업 준비 중"

            progress_state[
                "error"
            ] = ""


        # =================================================
        # background thread
        # =================================================

        thread = threading.Thread(
            target=run_processing,
            args=(save_path,),
            daemon=True
        )

        thread.start()


        return render_template(
            "index.html",

            text="",

            corrected_text="",

            paragraphs=[],

            summary={},

            processing=True
        )


    except Exception:

        error_logger.exception(
            "파일 업로드 처리 중 오류 발생"
        )

        return (
            "파일 업로드 중 오류가 발생했습니다.",
            500
        )


# =========================================================
# 진행률
# =========================================================

@app.route(
    "/progress"
)
def progress():

    try:

        with state_lock:

            return jsonify(
                progress_state.copy()
            )

    except Exception:

        error_logger.exception(
            "진행률 조회 오류"
        )

        return jsonify({
            "percent": 0,
            "status": "error",
            "stage": "",
            "error": (
                "진행률을 가져오는 중 "
                "오류가 발생했습니다."
            )
        }), 500


# =========================================================
# 다운로드
# =========================================================

@app.route(
    "/download/<fmt>"
)
def download(fmt):

    try:

        with state_lock:

            text = (
                latest_result[
                    "text"
                ]
            )

            segments = list(
                latest_result[
                    "segments"
                ]
            )


        if not text:

            return (
                "먼저 전사를 진행하세요.",
                400
            )


        filename = (
            f"result.{fmt}"
        )


        output_path = os.path.join(
            OUTPUT_FOLDER,
            filename
        )


        if fmt == "txt":

            export_txt(
                text,
                output_path
            )


        elif fmt == "srt":

            export_srt(
                segments,
                output_path
            )


        elif fmt == "docx":

            paragraphs = (
                group_into_paragraphs(
                    segments
                )
            )

            export_docx(
                paragraphs,
                output_path
            )


        elif fmt == "pdf":

            paragraphs = (
                group_into_paragraphs(
                    segments
                )
            )

            export_pdf(
                paragraphs,
                output_path
            )


        else:

            server_logger.warning(
                "지원하지 않는 다운로드 형식 | format=%s",
                fmt
            )

            return (
                "지원하지 않는 형식입니다.",
                400
            )


        server_logger.info(
            "파일 다운로드 완료 | format=%s",
            fmt
        )


        return send_file(
            output_path,
            as_attachment=True
        )


    except Exception:

        error_logger.exception(
            "파일 다운로드 처리 오류 | format=%s",
            fmt
        )

        return (
            "파일 생성 중 오류가 발생했습니다.",
            500
        )


# =========================================================
# 404
# =========================================================

@app.errorhandler(404)
def page_not_found(error):

    server_logger.warning(
        "404 Not Found | path=%s",
        request.path
    )

    return (
        "페이지를 찾을 수 없습니다.",
        404
    )


# =========================================================
# 413
# =========================================================

@app.errorhandler(413)
def request_entity_too_large(error):

    server_logger.warning(
        "파일 용량 초과 | path=%s",
        request.path
    )

    return (
        "파일 크기가 너무 큽니다. "
        "최대 2GB까지 업로드할 수 있습니다.",
        413
    )


# =========================================================
# 500
# =========================================================

@app.errorhandler(500)
def internal_server_error(error):

    error_logger.error(
        "500 Internal Server Error | path=%s | error=%s",
        request.path,
        error
    )

    return (
        "서버 내부 오류가 발생했습니다.",
        500
    )


# =========================================================
# 정상 종료
# =========================================================

@atexit.register
def shutdown_server():

    server_logger.info(
        "=" * 60
    )

    server_logger.info(
        "SERVER_SHUTDOWN"
    )

    server_logger.info(
        "Flask 서버가 정상적으로 종료되었습니다."
    )

    server_logger.info(
        "=" * 60
    )


# =========================================================
# 서버 실행
# =========================================================

if __name__ == "__main__":

    server_logger.info(
        "=" * 60
    )

    server_logger.info(
        "SERVER_START"
    )

    server_logger.info(
        "Flask 서버를 시작합니다."
    )

    server_logger.info(
        "Upload folder: %s",
        UPLOAD_FOLDER
    )

    server_logger.info(
        "Output folder: %s",
        OUTPUT_FOLDER
    )

    server_logger.info(
        "Log folder: %s",
        LOG_FOLDER
    )

    server_logger.info(
        "=" * 60
    )

    app.run(
        debug=True,
        use_reloader=False
    )