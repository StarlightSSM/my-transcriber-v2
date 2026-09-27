def format_timestamp(seconds):
    """
    초 단위 시간을 SRT 형식으로 변환합니다.

    예:
    65.123
    ->
    00:01:05,123
    """

    seconds = float(
        seconds or 0
    )

    total_seconds = int(
        seconds
    )

    milliseconds = int(
        round(
            (seconds - total_seconds)
            * 1000
        )
    )

    # 1000ms가 넘어가는 경우
    if milliseconds >= 1000:

        total_seconds += 1

        milliseconds = 0

    hours = (
        total_seconds // 3600
    )

    minutes = (
        total_seconds % 3600
    ) // 60

    secs = (
        total_seconds % 60
    )

    return (
        f"{hours:02d}:"
        f"{minutes:02d}:"
        f"{secs:02d},"
        f"{milliseconds:03d}"
    )


def export_srt(
    segments,
    output_path
):
    """
    Whisper segment 결과를 SRT 파일로 저장합니다.
    """

    with open(
        output_path,
        "w",
        encoding="utf-8-sig"
    ) as file:

        for index, segment in enumerate(
            segments,
            start=1
        ):

            start = format_timestamp(
                segment.get(
                    "start",
                    0
                )
            )

            end = format_timestamp(
                segment.get(
                    "end",
                    0
                )
            )

            text = str(
                segment.get(
                    "text",
                    ""
                )
            ).strip()


            file.write(
                f"{index}\n"
            )

            file.write(
                f"{start} --> {end}\n"
            )

            file.write(
                f"{text}\n\n"
            )

    return output_path