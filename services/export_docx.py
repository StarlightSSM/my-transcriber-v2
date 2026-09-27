from docx import Document
from docx.shared import Pt


def export_docx(
    paragraphs,
    output_path,
    title="강의 전사본"
):
    """
    전사 결과를 DOCX 파일로 저장합니다.

    paragraphs:
        문자열 리스트

    output_path:
        저장할 DOCX 파일 경로

    title:
        문서 제목
    """

    document = Document()

    # 기본 글꼴
    style = document.styles["Normal"]

    style.font.name = "맑은 고딕"
    style.font.size = Pt(10.5)

    # 제목
    document.add_heading(
        title,
        level=1
    )

    # 본문
    for paragraph in paragraphs:

        if paragraph is None:
            continue

        paragraph = str(paragraph).strip()

        if not paragraph:
            continue

        document.add_paragraph(
            paragraph
        )

    document.save(
        output_path
    )

    return output_path