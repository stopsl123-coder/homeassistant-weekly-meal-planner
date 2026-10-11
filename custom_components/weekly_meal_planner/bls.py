"""Bundeslebensmittelschlüssel 4.0 data import."""

from __future__ import annotations

import io
import math
import re
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Iterator
from typing import Any

BLS_DATA_URL = "https://www.blsdb.de/assets/uploads/BLS_4_0_2025_DE.zip"
_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_CELL_REF = re.compile(r"([A-Z]+)")
_FOOD_COLUMNS = {
    "A": "code",
    "B": "name",
    "C": "name_en",
    "G": "calories",
    "M": "protein",
    "P": "fat",
    "S": "carbs",
}


def parse_bls_archive(payload: bytes) -> Iterator[dict[str, Any]]:
    """Yield German BLS food records from the official XLSX download."""
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            workbook_bytes = archive.read(
                "BLS_4_0_2025_DE/BLS_4_0_Daten_2025_DE.xlsx"
            )
        with zipfile.ZipFile(io.BytesIO(workbook_bytes)) as workbook:
            shared_strings = _read_shared_strings(workbook)
            worksheet_path = _worksheet_path(workbook)
            yield from _parse_worksheet(workbook, worksheet_path, shared_strings)
    except (KeyError, OSError, zipfile.BadZipFile, ET.ParseError) as err:
        raise ValueError("BLS-Datendatei ist ungültig oder unvollständig.") from err


def _parse_worksheet(
    workbook: zipfile.ZipFile, worksheet_path: str, shared_strings: list[str]
) -> Iterator[dict[str, Any]]:
    row_tag = f"{{{_MAIN_NS}}}row"
    cell_tag = f"{{{_MAIN_NS}}}c"
    value_tag = f"{{{_MAIN_NS}}}v"
    with workbook.open(worksheet_path) as sheet:
        for _, row in ET.iterparse(sheet, events=("end",)):
            if row.tag != row_tag:
                continue
            if row.attrib.get("r") == "1":
                row.clear()
                continue
            fields: dict[str, Any] = {}
            for cell in row.findall(cell_tag):
                match = _CELL_REF.match(cell.attrib.get("r", ""))
                if match is None or match.group(1) not in _FOOD_COLUMNS:
                    continue
                value = cell.find(value_tag)
                if value is None or value.text is None:
                    continue
                if cell.attrib.get("t") == "s":
                    try:
                        cell_value: Any = shared_strings[int(value.text)]
                    except (IndexError, ValueError):
                        continue
                else:
                    cell_value = value.text
                fields[_FOOD_COLUMNS[match.group(1)]] = cell_value
            row.clear()

            if not fields.get("code") or not fields.get("name"):
                continue
            values = {
                key: _number(fields.get(key))
                for key in ("calories", "protein", "fat", "carbs")
            }
            if any(value is None for value in values.values()):
                continue
            yield {
                "code": str(fields["code"]),
                "name": str(fields["name"]),
                "name_en": str(fields.get("name_en", "")),
                **values,
            }


def _read_shared_strings(workbook: zipfile.ZipFile) -> list[str]:
    try:
        with workbook.open("xl/sharedStrings.xml") as source:
            strings = []
            for _, item in ET.iterparse(source, events=("end",)):
                if item.tag != f"{{{_MAIN_NS}}}si":
                    continue
                strings.append(
                    "".join(text.text or "" for text in item.iter(f"{{{_MAIN_NS}}}t"))
                )
                item.clear()
            return strings
    except KeyError:
        return []


def _worksheet_path(workbook: zipfile.ZipFile) -> str:
    workbook_xml = ET.fromstring(workbook.read("xl/workbook.xml"))
    first_sheet = workbook_xml.find(f"{{{_MAIN_NS}}}sheets/{{{_MAIN_NS}}}sheet")
    if first_sheet is None:
        raise ValueError("BLS-Datendatei enthält kein Tabellenblatt.")
    relationship_id = first_sheet.attrib.get(f"{{{_REL_NS}}}id")
    if not relationship_id:
        raise ValueError("BLS-Tabellenblatt hat keinen Dateiverweis.")
    relationships = ET.fromstring(workbook.read("xl/_rels/workbook.xml.rels"))
    for relationship in relationships.findall(
        f"{{{_PACKAGE_REL_NS}}}Relationship"
    ):
        if relationship.attrib.get("Id") != relationship_id:
            continue
        target = relationship.attrib.get("Target", "")
        return target.lstrip("/") if target.startswith("/") else f"xl/{target}"
    raise ValueError("BLS-Tabellenblattdatei fehlt.")


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number >= 0 else None
