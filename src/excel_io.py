"""Minimal XLSX import/export helpers for CRM in PC.

This module writes and reads simple Excel workbooks without third-party
packages. It supports one worksheet with text/number/boolean/date-like values.
"""

from __future__ import annotations

from pathlib import Path
import re
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PACKAGE_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_CONTENT = "http://schemas.openxmlformats.org/package/2006/content-types"


def _xml_declaration(root: ET.Element) -> bytes:
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _cell_ref(row: int, column: int) -> str:
    return f"{_column_name(column)}{row}"


def _string_cell(row: int, column: int, value) -> ET.Element:
    cell = ET.Element(f"{{{NS_MAIN}}}c", {"r": _cell_ref(row, column), "t": "inlineStr"})
    inline = ET.SubElement(cell, f"{{{NS_MAIN}}}is")
    text = ET.SubElement(inline, f"{{{NS_MAIN}}}t")
    text.text = "" if value is None else str(value)
    return cell


def export_section_to_xlsx(section: dict, path: str | Path) -> Path:
    """Export section records to an .xlsx file and return the destination path."""

    path = Path(path)
    headers = [field["name"] for field in section.get("fields", [])]
    rows = [headers]
    for record in section.get("records", []):
        rows.append([_format_value(record.get("values", {}).get(field["id"]), field.get("type")) for field in section.get("fields", [])])

    workbook = ET.Element(f"{{{NS_MAIN}}}workbook", {"xmlns:r": NS_REL})
    sheets = ET.SubElement(workbook, f"{{{NS_MAIN}}}sheets")
    ET.SubElement(sheets, f"{{{NS_MAIN}}}sheet", {"name": "CRM", "sheetId": "1", f"{{{NS_REL}}}id": "rId1"})

    workbook_rels = ET.Element(f"{{{NS_PACKAGE_REL}}}Relationships")
    ET.SubElement(
        workbook_rels,
        f"{{{NS_PACKAGE_REL}}}Relationship",
        {"Id": "rId1", "Type": f"{NS_REL}/worksheet", "Target": "worksheets/sheet1.xml"},
    )

    root_rels = ET.Element(f"{{{NS_PACKAGE_REL}}}Relationships")
    ET.SubElement(
        root_rels,
        f"{{{NS_PACKAGE_REL}}}Relationship",
        {"Id": "rId1", "Type": f"{NS_REL}/officeDocument", "Target": "xl/workbook.xml"},
    )

    types = ET.Element(f"{{{NS_CONTENT}}}Types")
    ET.SubElement(types, f"{{{NS_CONTENT}}}Default", {"Extension": "rels", "ContentType": "application/vnd.openxmlformats-package.relationships+xml"})
    ET.SubElement(types, f"{{{NS_CONTENT}}}Default", {"Extension": "xml", "ContentType": "application/xml"})
    ET.SubElement(
        types,
        f"{{{NS_CONTENT}}}Override",
        {"PartName": "/xl/workbook.xml", "ContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"},
    )
    ET.SubElement(
        types,
        f"{{{NS_CONTENT}}}Override",
        {"PartName": "/xl/worksheets/sheet1.xml", "ContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"},
    )

    worksheet = ET.Element(f"{{{NS_MAIN}}}worksheet")
    sheet_data = ET.SubElement(worksheet, f"{{{NS_MAIN}}}sheetData")
    for row_index, row_values in enumerate(rows, start=1):
        row = ET.SubElement(sheet_data, f"{{{NS_MAIN}}}row", {"r": str(row_index)})
        for column_index, value in enumerate(row_values, start=1):
            row.append(_string_cell(row_index, column_index, value))

    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _xml_declaration(types))
        archive.writestr("_rels/.rels", _xml_declaration(root_rels))
        archive.writestr("xl/workbook.xml", _xml_declaration(workbook))
        archive.writestr("xl/_rels/workbook.xml.rels", _xml_declaration(workbook_rels))
        archive.writestr("xl/worksheets/sheet1.xml", _xml_declaration(worksheet))
    return path


def import_rows_from_xlsx(path: str | Path) -> list[dict[str, str]]:
    """Read first worksheet from an .xlsx file as dictionaries keyed by header."""

    path = Path(path)
    with ZipFile(path) as archive:
        shared_strings = _read_shared_strings(archive)
        sheet_name = _first_sheet_name(archive)
        sheet = ET.fromstring(archive.read(sheet_name))

    rows = []
    for row in sheet.findall(f".//{{{NS_MAIN}}}row"):
        cells = {}
        for cell in row.findall(f"{{{NS_MAIN}}}c"):
            reference = cell.attrib.get("r", "A1")
            column = _column_index(reference)
            cells[column] = _read_cell_value(cell, shared_strings)
        if cells:
            rows.append([cells.get(index, "") for index in range(1, max(cells) + 1)])

    if not rows:
        return []
    headers = [str(value).strip() for value in rows[0]]
    result = []
    for row in rows[1:]:
        item = {header: row[index] if index < len(row) else "" for index, header in enumerate(headers) if header}
        if any(str(value).strip() for value in item.values()):
            result.append(item)
    return result


def import_values_for_section(section: dict, path: str | Path) -> list[dict]:
    """Map Excel rows to CRM field IDs using field names as Excel headers."""

    rows = import_rows_from_xlsx(path)
    fields_by_name = {field["name"].strip(): field for field in section.get("fields", [])}
    mapped = []
    for row in rows:
        values = {}
        for header, value in row.items():
            field = fields_by_name.get(header.strip())
            if not field:
                continue
            values[field["id"]] = _parse_value(value, field.get("type"))
        if values:
            mapped.append(values)
    return mapped


def _first_sheet_name(archive: ZipFile) -> str:
    workbook_rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    for relationship in workbook_rels:
        target = relationship.attrib.get("Target", "")
        if "worksheets/" in target:
            return "xl/" + target.lstrip("/")
    return "xl/worksheets/sheet1.xml"


def _read_shared_strings(archive: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    strings = []
    for item in root.findall(f"{{{NS_MAIN}}}si"):
        strings.append("".join(text.text or "" for text in item.findall(f".//{{{NS_MAIN}}}t")))
    return strings


def _read_cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        text = cell.find(f".//{{{NS_MAIN}}}t")
        return text.text if text is not None and text.text is not None else ""
    value = cell.find(f"{{{NS_MAIN}}}v")
    raw = value.text if value is not None and value.text is not None else ""
    if cell_type == "s" and raw.isdigit():
        return shared_strings[int(raw)] if int(raw) < len(shared_strings) else ""
    if cell_type == "b":
        return "Так" if raw == "1" else "Ні"
    return raw


def _column_index(reference: str) -> int:
    letters = re.sub(r"[^A-Z]", "", reference.upper())
    index = 0
    for letter in letters:
        index = index * 26 + ord(letter) - 64
    return index or 1


def _format_value(value, field_type: str | None) -> str:
    if field_type == "checkbox":
        return "Так" if value else "Ні"
    return "" if value is None else str(value)


def _parse_value(value, field_type: str | None):
    if field_type == "checkbox":
        return str(value).strip().lower() in {"1", "true", "так", "yes", "y", "+"}
    return "" if value is None else str(value).strip()
