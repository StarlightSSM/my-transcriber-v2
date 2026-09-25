from pathlib import Path


def _safe_stem(stem):
    return "".join(
        c if c not in '\\/:*?"<>|' else "_"
        for c in stem
    )


def export_txt(stem, text, out_dir):
    name = f"{_safe_stem(stem)}_transcript.txt"

    output_path = Path(out_dir) / name
    output_path.write_text(
        text,
        encoding="utf-8"
    )

    return name