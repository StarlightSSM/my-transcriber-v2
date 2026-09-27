import json


def export_json(
    result,
    output_path
):
    """
    전사 및 AI 분석 결과를 JSON으로 저장합니다.
    """

    with open(
        output_path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            result,
            file,
            ensure_ascii=False,
            indent=2
        )

    return output_path