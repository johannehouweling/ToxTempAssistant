import json

import pytest

from toxtempass.filehandling import (
    get_text_or_bytes_perfile_dict,
    stringyfy_text_dict,
)


def test_get_text_or_bytes_perfile_dict_reads_json_and_csv(tmp_path):
    json_path = tmp_path / "data.json"
    csv_path = tmp_path / "table.csv"

    json.dump({"alpha": 1, "beta": [1, 2]}, json_path.open("w", encoding="utf-8"))
    csv_path.write_text("col1,col2\n1,2\n3,4\n", encoding="utf-8")

    result = get_text_or_bytes_perfile_dict(
        [json_path, csv_path], unlink=False, extract_images=False
    )

    json_entry = result[str(json_path)]
    csv_entry = result[str(csv_path)]

    assert "\"alpha\": 1" in json_entry["text"]
    assert json_entry["origin"] == "document"

    assert "col1, col2" in csv_entry["text"]
    assert "3, 4" in csv_entry["text"]
    assert csv_entry["origin"] == "document"

    combined_text = stringyfy_text_dict({str(json_path): json_entry})
    assert "--- data.json ---" in combined_text


def test_get_text_or_bytes_perfile_dict_reads_xlsx(tmp_path):
    pytest.importorskip("openpyxl")
    import openpyxl

    xlsx_path = tmp_path / "sheet.xlsx"
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Sheet1"
    sheet.append(["A", "B"])
    sheet.append([1, 2])
    sheet.append([3, 4])
    workbook.save(xlsx_path)
    workbook.close()

    result = get_text_or_bytes_perfile_dict([xlsx_path], unlink=False, extract_images=False)

    entry = result[str(xlsx_path)]
    assert "Sheet: Sheet1" in entry["text"]
    assert "1, 2" in entry["text"]
    assert entry["origin"] == "document"
