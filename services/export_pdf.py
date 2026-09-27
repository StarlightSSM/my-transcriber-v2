import os

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont


# ============================================================
# 한글 폰트
# ============================================================

FONT_NAME = "HYSMyeongJo-Medium"

pdfmetrics.registerFont(
    UnicodeCIDFont(
        FONT_NAME
    )
)


# ============================================================
# 파일명 정리
# ============================================================

def _safe_stem(stem):

    stem = str(
        stem or "result"
    ).strip()


    # 확장자 제거
    if "." in stem:

        stem = stem.rsplit(
            ".",
            1
        )[0]


    result = ""

    for char in stem:

        if (
            char.isalnum()
            or char in "-_ "
        ):

            result += char

        else:

            result += "_"


    result = result.strip()


    return (
        result
        or "result"
    )


# ============================================================
# 텍스트 줄바꿈
# ============================================================

def wrap_text(
    text,
    font_name,
    font_size,
    max_width
):

    text = str(
        text or ""
    )


    lines = []

    current = ""


    for char in text:

        candidate = (
            current
            + char
        )


        width = pdfmetrics.stringWidth(
            candidate,
            font_name,
            font_size
        )


        if width <= max_width:

            current = candidate

        else:

            if current:

                lines.append(
                    current
                )

            current = char


    if current:

        lines.append(
            current
        )


    return lines


# ============================================================
# PDF 출력
# ============================================================

def _draw_text(
    c,
    text,
    x,
    y,
    max_width,
    font_size,
    line_height,
    margin,
    page_height
):

    lines = wrap_text(
        text,
        FONT_NAME,
        font_size,
        max_width
    )


    if not lines:

        lines = [""]


    for line in lines:

        if y < margin:

            c.showPage()

            c.setFont(
                FONT_NAME,
                font_size
            )

            y = (
                page_height
                - margin
            )


        c.drawString(
            x,
            y,
            line
        )


        y -= line_height


    return y


# ============================================================
# PDF 생성
# ============================================================

def export_pdf(
    stem,
    text,
    summary,
    out_dir
):
    """
    강의 분석 PDF 생성

    Parameters
    ----------
    stem:
        원본 파일명 stem

    text:
        전사 원문

    summary:
        AI 요약

    out_dir:
        PDF 저장 폴더
    """

    os.makedirs(
        out_dir,
        exist_ok=True
    )


    safe_stem = _safe_stem(
        stem
    )


    output_path = os.path.join(
        out_dir,
        f"{safe_stem}_analysis.pdf"
    )


    # --------------------------------------------------------
    # PDF 생성
    # --------------------------------------------------------

    c = canvas.Canvas(
        output_path,
        pagesize=A4
    )


    width, height = A4

    margin = 50

    max_width = (
        width
        - margin * 2
    )


    # --------------------------------------------------------
    # 제목
    # --------------------------------------------------------

    c.setFont(
        FONT_NAME,
        18
    )


    c.drawString(
        margin,
        height - margin,
        "강의 분석 결과"
    )


    y = (
        height
        - margin
        - 35
    )


    # --------------------------------------------------------
    # 요약
    # --------------------------------------------------------

    c.setFont(
        FONT_NAME,
        13
    )


    y = _draw_text(
        c,
        "요약",
        margin,
        y,
        max_width,
        13,
        20,
        margin,
        height
    )


    y -= 8


    c.setFont(
        FONT_NAME,
        10.5
    )


    y = _draw_text(
        c,
        summary or "요약이 없습니다.",
        margin,
        y,
        max_width,
        10.5,
        17,
        margin,
        height
    )


    y -= 20


    # --------------------------------------------------------
    # 전사 원문
    # --------------------------------------------------------

    c.setFont(
        FONT_NAME,
        13
    )


    y = _draw_text(
        c,
        "전사 원문",
        margin,
        y,
        max_width,
        13,
        20,
        margin,
        height
    )


    y -= 8


    c.setFont(
        FONT_NAME,
        10.5
    )


    paragraphs = str(
        text or ""
    ).splitlines()


    for paragraph in paragraphs:

        paragraph = paragraph.strip()


        if not paragraph:

            y -= 8

            continue


        y = _draw_text(
            c,
            paragraph,
            margin,
            y,
            max_width,
            10.5,
            17,
            margin,
            height
        )


        y -= 5


    c.save()


    return output_path