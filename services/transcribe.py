from pathlib import Path

import av
from faster_whisper import WhisperModel


# ============================================================
# Whisper 설정
# ============================================================

MODEL_SIZE = "small"
DEVICE = "cpu"
COMPUTE_TYPE = "int8"


# ============================================================
# 오디오 스트림 검사
# ============================================================

def validate_audio_stream(media_path: str):
    """
    미디어 파일에 실제 오디오 스트림이 존재하는지 검사합니다.

    오디오가 없는 MP4/영상 파일을 faster-whisper에 전달하면
    'tuple index out of range'와 같은 내부 오류가 발생할 수 있으므로
    Whisper 실행 전에 명확하게 검사합니다.
    """

    try:
        container = av.open(media_path)

        audio_streams = [
            stream
            for stream in container.streams
            if stream.type == "audio"
        ]

        container.close()

        if not audio_streams:
            raise ValueError(
                "이 파일에서 오디오 트랙을 찾을 수 없습니다. "
                "음성이 포함된 MP3, MP4, WAV, M4A 파일을 업로드해주세요."
            )

    except ValueError:
        # 우리가 직접 발생시킨 오류는 그대로 전달
        raise

    except Exception as e:
        raise ValueError(
            "미디어 파일을 읽을 수 없습니다. "
            "파일이 손상되었거나 지원되지 않는 형식일 수 있습니다. "
            f"원본 오류: {e}"
        )


# ============================================================
# Whisper 음성 인식
# ============================================================

def transcribe_media(
    media_path: str,
    language: str = "ko",
    progress_callback=None,
):
    """
    음성/영상 파일을 faster-whisper를 이용해 텍스트로 변환합니다.

    Parameters
    ----------
    media_path : str
        입력 미디어 파일 경로

    language : str
        음성 언어.
        기본값은 한국어(ko)

    progress_callback : callable | None
        진행률을 전달받을 콜백 함수.
        예:
            progress_callback(50)

    Returns
    -------
    tuple
        transcript : 전체 변환 텍스트
        segments : 타임스탬프가 포함된 구간 목록
    """

    # --------------------------------------------------------
    # 1. 파일 경로 정리
    # --------------------------------------------------------

    media_path = str(Path(media_path))

    if not Path(media_path).exists():
        raise ValueError(
            f"입력 파일을 찾을 수 없습니다: {media_path}"
        )

    # --------------------------------------------------------
    # 2. 오디오 스트림 검사
    # --------------------------------------------------------

    if progress_callback:
        progress_callback(2)

    validate_audio_stream(media_path)

    if progress_callback:
        progress_callback(5)

    # --------------------------------------------------------
    # 3. Whisper 모델 로드
    # --------------------------------------------------------

    model = WhisperModel(
        MODEL_SIZE,
        device=DEVICE,
        compute_type=COMPUTE_TYPE,
    )

    if progress_callback:
        progress_callback(10)

    # --------------------------------------------------------
    # 4. 음성 인식 실행
    # --------------------------------------------------------

    try:
        segments_iter, info = model.transcribe(
            media_path,
            language=language,
            vad_filter=True,
            beam_size=5,
        )

    except Exception as e:
        raise RuntimeError(
            "음성 인식 중 오류가 발생했습니다. "
            "파일의 오디오 형식이나 코덱을 확인해주세요. "
            f"원본 오류: {e}"
        )

    # --------------------------------------------------------
    # 5. 결과 수집
    # --------------------------------------------------------

    segments = []
    transcript_parts = []

    duration = getattr(info, "duration", None)

    for segment in segments_iter:
        text = segment.text.strip()

        # 빈 문장은 제외
        if not text:
            continue

        item = {
            "start": float(segment.start),
            "end": float(segment.end),
            "text": text,
        }

        segments.append(item)
        transcript_parts.append(text)

        # ----------------------------------------------------
        # 진행률 계산
        # Whisper 구간 정보를 이용해 10~90% 사이로 표시
        # ----------------------------------------------------

        if progress_callback and duration:
            progress = 10 + int(
                min(segment.end / duration, 1.0) * 80
            )

            progress_callback(progress)

    # --------------------------------------------------------
    # 6. 최종 transcript 생성
    # --------------------------------------------------------

    transcript = "\n".join(transcript_parts).strip()

    if not transcript:
        raise ValueError(
            "음성에서 인식된 텍스트가 없습니다. "
            "음성이 너무 작거나, 무음 구간이 많거나, "
            "지원하기 어려운 음성일 수 있습니다."
        )

    if progress_callback:
        progress_callback(100)

    return transcript, segments