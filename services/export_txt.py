def export_txt(
    text,
    output_path
):
    """
    전사 결과를 TXT 파일로 저장합니다.
    """

    with open(
        output_path,
        "w",
        encoding="utf-8-sig"
    ) as file:

        file.write(
            text or ""
        )

    return output_path