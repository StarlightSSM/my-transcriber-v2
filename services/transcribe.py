import logging
import math
from faster_whisper import WhisperModel

logger = logging.getLogger("my-transcriber.transcribe")

_MODEL = None


def get_model():
    global _MODEL
    if _MODEL is None:
        logger.info("Loading faster-whisper model")
        _MODEL = WhisperModel(
            "small",
            device="cpu",
            compute_type="int8",
        )
        logger.info("Whisper model loaded")
    return _MODEL


def transcribe_media(path, language="ko", progress_callback=None):
    model = get_model()
    segments_iter, info = model.transcribe(
        path,
        language=language,
        beam_size=5,
        vad_filter=True,
        condition_on_previous_text=True,
    )

    duration = float(info.duration or 0)
    segments = []
    texts = []

    for segment in segments_iter:
        item = {
            "start": round(float(segment.start), 3),
            "end": round(float(segment.end), 3),
            "text": segment.text.strip(),
        }
        if item["text"]:
            segments.append(item)
            texts.append(item["text"])

        if progress_callback and duration > 0:
            progress_callback(min(95, math.floor((item["end"] / duration) * 95)))

    return " ".join(texts), segments
