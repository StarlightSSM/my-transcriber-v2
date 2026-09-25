# services/transcribe.py

from pathlib import Path
import logging

import av
from faster_whisper import WhisperModel


# =========================================================
# 기본 설정
# =========================================================

MODEL_SIZE = "large-v3-turbo"

DEVICE = "cpu"
COMPUTE_TYPE = "int8"

DEFAULT_LANGUAGE = "ko"

logger = logging.getLogger("transcription")


# =========================================================
# Whisper 모델 캐시
# =========================================================

_model = None


def get_model():
    """
    Whisper 모델을 한 번만 로드하고 이후에는 재사용합니다.
    """

    global _model

    if _model is None:
        logger.info(
            "Whisper 모델 로딩 시작 | model=%s | device=%s | compute=%s",
            MODEL_SIZE,
            DEVICE,
            COMPUTE_TYPE
        )

        _model = WhisperModel(
            MODEL_SIZE,
            device=DEVICE,
            compute_type=COMPUTE_TYPE
        )

        logger.info(
            "Whisper 모델 로딩 완료 | model=%s",
            MODEL_SIZE
        )

    return _model


# =========================================================
# 오디오 스트림 검증
# =========================================================

def validate_audio_stream(media_path):
    """
    업로드된 미디어 파일에 실제 오디오 스트림이 존재하는지 확인합니다.

    오디오 트랙이 없는 MP4의 경우 faster-whisper 내부에서
    IndexError: tuple index out of range가 발생할 수 있으므로
    Whisper 실행 전에 사전 검증합니다.
    """

    media_path = Path(media_path)

    if not media_path.exists():
        raise FileNotFoundError(
            f"파일을 찾을 수 없습니다: {media_path}"
        )

    try:
        container = av.open(str(media_path))

        try:
            audio_streams = [
                stream
                for stream in container.streams
                if stream.type == "audio"
            ]

            if not audio_streams:
                raise ValueError(
                    "이 파일에서 오디오 트랙을 찾을 수 없습니다. "
                    "음성이 포함된 MP3, MP4, WAV, M4A 파일을 업로드해주세요."
                )

            logger.info(
                "오디오 스트림 확인 완료 | file=%s | audio_streams=%d",
                media_path.name,
                len(audio_streams)
            )

        finally:
            container.close()

    except ValueError:
        raise

    except Exception as e:
        logger.exception(
            "미디어 파일 확인 중 오류 | file=%s",
            media_path
        )

        raise RuntimeError(
            f"미디어 파일을 읽을 수 없습니다: {e}"
        ) from e


# =========================================================
# 미디어 길이 확인
# =========================================================

def get_media_duration(media_path):
    """
    미디어 파일의 전체 길이를 초 단위로 가져옵니다.
    """

    try:
        container = av.open(str(media_path))

        try:
            duration = container.duration

            if duration is None:
                return 0.0

            # PyAV duration은 microseconds 단위
            return float(duration / av.time_base)

        finally:
            container.close()

    except Exception:
        logger.exception(
            "미디어 길이 확인 실패 | file=%s",
            media_path
        )

        return 0.0


# =========================================================
# 전사
# =========================================================

def transcribe_media(
    media_path,
    language=DEFAULT_LANGUAGE,
    progress_callback=None
):
    """
    미디어 파일을 Whisper로 전사합니다.

    반환값:
        text:
            전체 전사 텍스트

        segments:
            [
                {
                    "start": 0.0,
                    "end": 3.2,
                    "text": "안녕하세요."
                },
                ...
            ]
    """

    media_path = Path(media_path)

    if not media_path.exists():
        raise FileNotFoundError(
            f"파일을 찾을 수 없습니다: {media_path}"
        )

    logger.info(
        "전사 시작 | file=%s | model=%s | language=%s",
        media_path.name,
        MODEL_SIZE,
        language
    )

    # -----------------------------------------------------
    # 진행률
    # -----------------------------------------------------

    def update_progress(value):
        if progress_callback:
            progress_callback(int(value))

    update_progress(2)

    # -----------------------------------------------------
    # 오디오 존재 여부 확인
    # -----------------------------------------------------

    validate_audio_stream(media_path)

    update_progress(5)

    # -----------------------------------------------------
    # 전체 길이
    # -----------------------------------------------------

    duration = get_media_duration(media_path)

    logger.info(
        "미디어 길이 확인 | file=%s | duration=%.2f sec",
        media_path.name,
        duration
    )

    # -----------------------------------------------------
    # 모델 로딩
    # -----------------------------------------------------

    model = get_model()

    update_progress(10)

    # -----------------------------------------------------
    # Whisper 실행
    # -----------------------------------------------------

    try:
        segments_iter, info = model.transcribe(
            str(media_path),

            language=language,

            # 음성 구간이 아닌 부분을 제거
            vad_filter=True,

            # beam search
            beam_size=5,

            # 단어 단위 timestamp는 비용이 크므로
            # 기본적으로 segment timestamp 사용
            word_timestamps=False,

            # 이전 segment의 문맥을 활용
            condition_on_previous_text=True
        )

    except Exception as e:

        logger.exception(
            "Whisper 전사 시작 실패 | file=%s",
            media_path
        )

        raise RuntimeError(
            f"음성 전사 중 오류가 발생했습니다: {e}"
        ) from e

    # -----------------------------------------------------
    # 결과 수집
    # -----------------------------------------------------

    result_segments = []
    text_parts = []

    try:

        for segment in segments_iter:

            text = (segment.text or "").strip()

            if not text:
                continue

            item = {
                "start": float(segment.start),
                "end": float(segment.end),
                "text": text
            }

            result_segments.append(item)
            text_parts.append(text)

            # -------------------------------------------------
            # 진행률 계산
            # -------------------------------------------------

            if duration > 0:

                ratio = min(
                    max(segment.end / duration, 0.0),
                    1.0
                )

                # 10 ~ 90%
                progress = 10 + int(ratio * 80)

                update_progress(progress)

    except Exception as e:

        logger.exception(
            "Whisper 결과 처리 실패 | file=%s",
            media_path
        )

        raise RuntimeError(
            f"전사 결과를 처리하는 중 오류가 발생했습니다: {e}"
        ) from e

    # -----------------------------------------------------
    # 최종 텍스트
    # -----------------------------------------------------

    full_text = "\n".join(text_parts).strip()

    if not full_text:
        raise RuntimeError(
            "음성 전사 결과가 비어 있습니다. "
            "음성이 포함된 파일인지 확인해주세요."
        )

    update_progress(90)

    logger.info(
        "전사 완료 | file=%s | segments=%d | text_length=%d",
        media_path.name,
        len(result_segments),
        len(full_text)
    )

    update_progress(100)

    return full_text, result_segments