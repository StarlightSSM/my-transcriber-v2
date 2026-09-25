from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
)
from reportlab.lib.styles import getSampleStyleSheet


def _safe_stem(stem):
    return "".join(
        c if c not in '\\/:*?"<>|' else "_"
        for c in stem
    )


def export_pdf(stem, text, summary, out_dir):
    name = f"{_safe_stem(stem)}_analysis.pdf"

    path = Path(out_dir) / name

    font_candidates = [
        Path("C:/Windows/Fonts/malgun.ttf"),
        Path("C:/Windows/Fonts/NanumGothic.ttf"),
    ]

    font_path = next(
        (
            p
            for p in font_candidates
            if p.exists()
        ),
        None,
    )

    if not font_path:
        raise RuntimeError(
            "한글 PDF용 폰트를 찾지 못했습니다. "
            "C:/Windows/Fonts/malgun.ttf를 확인하세요."
        )

    pdfmetrics.registerFont(
        TTFont(
            "Korean",
            str(font_path)
        )
    )

    styles = getSampleStyleSheet()

    styles["BodyText"].fontName = "Korean"
    styles["Title"].fontName = "Korean"
    styles["Heading2"].fontName = "Korean"

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4
    )

    story = [
        Paragraph(
            "강의 분석 결과",
            styles["Title"]
        ),

        Spacer(1, 12),

        Paragraph(
            summary.get("overview", ""),
            styles["BodyText"]
        ),

        Spacer(1, 12),

        Paragraph(
            "핵심 내용",
            styles["Heading2"]
        ),
    ]

    for item in summary.get(
        "key_points",
        []
    ):
        story.append(
            Paragraph(
                f"• {item}",
                styles["BodyText"]
            )
        )

    story += [
        Spacer(1, 12),

        Paragraph(
            "전사 원문",
            styles["Heading2"]
        ),

        Paragraph(
            text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br/>"),
            styles["BodyText"]
        ),
    ]

    doc.build(story)

    return name