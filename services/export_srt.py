from pathlib import Path


def _safe_stem(stem):
    return "".join(
        c if c not in '\\/:*?"<>|' else "_"
        for c in stem
    )


def _srt_time(seconds):
    ms = int(round(seconds * 1000))

    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)

    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def export_srt(stem, segments, out_dir):
    name = f"{_safe_stem(stem)}_transcript.srt"

    lines = []

    for i, seg in enumerate(segments, 1):
        lines += [
            str(i),
            f"{_srt_time(seg['start'])} --> {_srt_time(seg['end'])}",
            seg["text"],
            "",
        ]

    output_path = Path(out_dir) / name

    output_path.write_text(
        "\n".join(lines),
        encoding="utf-8-sig"
    )

    return name