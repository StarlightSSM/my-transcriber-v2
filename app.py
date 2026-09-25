import json
import logging
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, send_from_directory
from werkzeug.utils import secure_filename

from services.transcribe import transcribe_media
from services.summarize import summarize_with_ollama
from services.exporters import export_txt, export_srt, export_docx, export_pdf

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
LOG_DIR = BASE_DIR / "logs"
DB_PATH = BASE_DIR / "jobs.db"

for folder in (UPLOAD_DIR, OUTPUT_DIR, LOG_DIR):
    folder.mkdir(parents=True, exist_ok=True)

MAX_CONTENT_LENGTH = 2 * 1024 * 1024 * 1024
ALLOWED_EXTENSIONS = {"mp3", "mp4", "wav", "m4a", "webm"}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "app.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("my-transcriber")

db_lock = threading.Lock()


def db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db_lock, db() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            original_filename TEXT NOT NULL,
            stored_filename TEXT NOT NULL,
            status TEXT NOT NULL,
            progress INTEGER DEFAULT 0,
            transcript TEXT DEFAULT '',
            segments_json TEXT DEFAULT '[]',
            summary_json TEXT DEFAULT '{}',
            error TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """)
        conn.commit()


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def update_job(job_id, **fields):
    if not fields:
        return
    fields["updated_at"] = now_iso()
    assignments = ", ".join(f"{k}=?" for k in fields)
    values = list(fields.values()) + [job_id]
    with db_lock, db() as conn:
        conn.execute(f"UPDATE jobs SET {assignments} WHERE id=?", values)
        conn.commit()


def get_job(job_id):
    with db() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not row:
        return None
    data = dict(row)
    data["segments"] = json.loads(data.pop("segments_json") or "[]")
    data["summary"] = json.loads(data.pop("summary_json") or "{}")
    return data


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def run_job(job_id, path):
    try:
        update_job(job_id, status="transcribing", progress=1, error="")
        logger.info("Transcription started: %s", job_id)

        def progress_callback(percent):
            update_job(job_id, progress=max(1, min(95, int(percent))))

        transcript, segments = transcribe_media(
            str(path),
            language="ko",
            progress_callback=progress_callback,
        )

        update_job(
            job_id,
            status="transcribed",
            progress=96,
            transcript=transcript,
            segments_json=json.dumps(segments, ensure_ascii=False),
        )

        # Summary is intentionally a separate stage so the user can still
        # download/read the transcript if Ollama is unavailable.
        try:
            update_job(job_id, status="summarizing", progress=97)
            summary = summarize_with_ollama(transcript, segments)
            update_job(
                job_id,
                status="done",
                progress=100,
                summary_json=json.dumps(summary, ensure_ascii=False),
            )
        except Exception as summary_error:
            logger.exception("Summary failed: %s", job_id)
            fallback = {
                "available": False,
                "error": str(summary_error),
                "overview": "",
                "key_points": [],
                "keywords": [],
                "chapters": [],
            }
            update_job(
                job_id,
                status="done",
                progress=100,
                summary_json=json.dumps(fallback, ensure_ascii=False),
            )

        logger.info("Job completed: %s", job_id)

    except Exception as exc:
        logger.exception("Job failed: %s", job_id)
        update_job(job_id, status="error", error=str(exc), progress=0)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/health")
def health():
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    ollama_ok = False
    try:
        response = requests.get(f"{ollama_url.rstrip('/')}/api/tags", timeout=2)
        ollama_ok = response.ok
    except requests.RequestException:
        pass

    return jsonify({
        "status": "ok",
        "ollama": ollama_ok,
        "model": os.getenv("OLLAMA_MODEL", "gemma3:4b"),
    })


@app.route("/api/upload", methods=["POST"])
def upload():
    file = request.files.get("media")
    if not file or not file.filename:
        return jsonify({"error": "파일을 선택하세요."}), 400

    if not allowed_file(file.filename):
        return jsonify({
            "error": "지원 형식은 MP3, MP4, WAV, M4A, WEBM입니다."
        }), 400

    job_id = uuid.uuid4().hex
    safe_name = secure_filename(file.filename)
    stored_name = f"{job_id}_{safe_name}"
    save_path = UPLOAD_DIR / stored_name
    file.save(save_path)

    created = now_iso()
    with db_lock, db() as conn:
        conn.execute("""
        INSERT INTO jobs
        (id, original_filename, stored_filename, status, progress, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (job_id, file.filename, stored_name, "queued", 0, created, created))
        conn.commit()

    thread = threading.Thread(
        target=run_job,
        args=(job_id, save_path),
        daemon=True,
    )
    thread.start()

    return jsonify({"job_id": job_id}), 202


@app.route("/api/jobs/<job_id>")
def job_status(job_id):
    job = get_job(job_id)
    if not job:
        return jsonify({"error": "작업을 찾을 수 없습니다."}), 404
    return jsonify(job)


@app.route("/api/jobs/<job_id>/export/<kind>")
def export_result(job_id, kind):
    job = get_job(job_id)
    if not job:
        return jsonify({"error": "작업을 찾을 수 없습니다."}), 404
    if job["status"] != "done":
        return jsonify({"error": "작업이 아직 완료되지 않았습니다."}), 409

    base = Path(job["original_filename"]).stem
    try:
        if kind == "txt":
            filename = export_txt(base, job["transcript"], OUTPUT_DIR)
        elif kind == "srt":
            filename = export_srt(base, job["segments"], OUTPUT_DIR)
        elif kind == "docx":
            filename = export_docx(base, job["transcript"], job["summary"], OUTPUT_DIR)
        elif kind == "pdf":
            filename = export_pdf(base, job["transcript"], job["summary"], OUTPUT_DIR)
        elif kind == "json":
            filename = f"{base}_analysis.json"
            (OUTPUT_DIR / filename).write_text(
                json.dumps({
                    "filename": job["original_filename"],
                    "transcript": job["transcript"],
                    "segments": job["segments"],
                    "summary": job["summary"],
                }, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        else:
            return jsonify({"error": "지원하지 않는 형식입니다."}), 400
    except Exception as exc:
        logger.exception("Export failed")
        return jsonify({"error": str(exc)}), 500

    return send_from_directory(OUTPUT_DIR, filename, as_attachment=True)


@app.errorhandler(413)
def too_large(_):
    return jsonify({"error": "파일은 최대 2GB까지 업로드할 수 있습니다."}), 413


if __name__ == "__main__":
    init_db()
    logger.info("SERVER_START")
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
