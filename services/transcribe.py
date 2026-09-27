import logging

import av
from faster_whisper import WhisperModel


logger = logging.getLogger(
    "transcription"
)


_model = None


# ============================================================
# Whisper 모델
# ============================================================

def get_model():

    global _model


    if _model is None:

        logger.info(
            "Whisper 모델 로딩 시작 | "
            "model=large-v3-turbo | "
            "device=cpu | "
            "compute=int8"
        )


        _model = WhisperModel(
            "large-v3-turbo",
            device="cpu",
            compute_type="int8"
        )


        logger.info(
            "Whisper 모델 로딩 완료 | "
            "model=large-v3-turbo"
        )


    return _model


# ============================================================
# 오디오 스트림 확인
# ============================================================

def _validate_audio_stream(
    file_path
):

    try:

        with av.open(file_path) as container:

            audio_streams = [
                stream
                for stream in container.streams
                if stream.type == "audio"
            ]


            if not audio_streams:

                raise ValueError(
                    "이 파일에서 오디오 트랙을 찾을 수 없습니다. "
                    "음성이 포함된 MP3, MP4, WAV, M4A, WEBM "
                    "파일을 업로드해주세요."
                )


            duration = (
                (container.duration or 0)
                / av.time_base
            )


            logger.info(
                "오디오 스트림 확인 완료 | "
                "file=%s | "
                "audio_streams=%s | "
                "duration=%.2f sec",
                file_path,
                len(audio_streams),
                duration
            )


            return duration


    except ValueError:

        raise


    except Exception as exc:

        raise ValueError(
            f"미디어 파일을 읽을 수 없습니다: {exc}"
        ) from exc


# ============================================================
# 전사
# ============================================================

def transcribe_media(
    file_path,
    progress_callback=None
):

    # 먼저 오디오 트랙 존재 여부 확인
    _validate_audio_stream(
        file_path
    )


    model = get_model()


    logger.info(
        "전사 시작 | "
        "file=%s | "
        "model=large-v3-turbo | "
        "language=ko",
        file_path
    )


    segments_iter, info = model.transcribe(

        file_path,

        language="ko",

        vad_filter=True,

        beam_size=5,

        condition_on_previous_text=True,
    )


    total_duration = float(
        info.duration or 0
    )


    segment_list = []
    text_parts = []


    for seg in segments_iter:

        text = seg.text.strip()


        if not text:
            continue


        text_parts.append(
            text
        )


        segment_list.append({
            "start": float(
                seg.start
            ),
            "end": float(
                seg.end
            ),
            "text": text,
        })


        if (
            progress_callback
            and total_duration > 0
        ):

            progress_callback(
                min(
                    90,
                    int(
                        (
                            seg.end
                            / total_duration
                        )
                        * 90
                    )
                )
            )


    if progress_callback:

        progress_callback(
            90
        )


    full_text = " ".join(
        text_parts
    ).strip()


    logger.info(
        "전사 완료 | "
        "file=%s | "
        "segments=%s | "
        "chars=%s",
        file_path,
        len(segment_list),
        len(full_text)
    )


    return (
        full_text,
        segment_list
    )