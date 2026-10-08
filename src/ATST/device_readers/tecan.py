from __future__ import annotations

from io import BytesIO
from pathlib import Path
import re
import zipfile
import xml.etree.ElementTree as ET

import pandas as pd

from ATST.device_readers.protocol import DeviceOutput
from ATST.device_readers._utils import (
    normalize_metadata_dates,
    PLATE_ROW_RE,
    WELL_LOCATION_PARTS_RE,
    is_real_layout_value,
)
from ATST.device_readers.logphase600 import (
    format_duration_parts,
    parse_logphase_filename_metadata,
)


XML_NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "office_rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
PLATE_AREA_RE = re.compile(r"^([A-Za-z]+)(\d+)-([A-Za-z]+)(\d+)$")
VALID_PLATE_SIZES = {6, 12, 24, 48, 96, 384, 1536}


class TecanParseError(ValueError):
    """Raised when Tecan device output cannot be parsed."""


class TecanOutput(DeviceOutput):
    """Parsed Tecan data ready to use when building an ATST file."""


class TecanReader:
    """Read Tecan SparkControl exports."""

    def read(
        self,
        raw: bytes | str,
        *,
        filename: str = "",
    ) -> TecanOutput:
        return parse_tecan_output(raw, filename=filename)


def parse_tecan_output(raw: bytes | str, *, filename: str = "") -> TecanOutput:
    """Parse a Tecan xlsx output into ATST-ready fields."""

    rows = read_first_worksheet(raw)
    metadata_fields = parse_metadata_fields(rows)
    readings, temperatures = parse_tecan_readings(rows)
    layout = parse_tecan_layout(rows)
    filename_metadata = parse_filename_hints(filename)

    metadata = build_metadata(metadata_fields, filename_metadata)
    assay = build_assay(metadata_fields, filename_metadata, readings, temperatures)
    file_name = build_atst_file_name(filename, filename_metadata)

    return TecanOutput(
        file_name=file_name,
        metadata=metadata,
        assay=assay,
        readings=readings,
        layout=layout,
    )


def read_first_worksheet(raw: bytes | str) -> list[tuple[int, list[str]]]:
    if isinstance(raw, str):
        raw = raw.encode("latin1")

    try:
        archive = zipfile.ZipFile(BytesIO(raw))
    except zipfile.BadZipFile as exc:
        raise TecanParseError("Tecan output must be an .xlsx workbook.") from exc

    with archive:
        try:
            shared_strings = read_shared_strings(archive)
            sheet_path = first_sheet_path(archive)
            root = ET.fromstring(archive.read(sheet_path))
        except KeyError as exc:
            raise TecanParseError("Tecan workbook is missing required worksheet data.") from exc
        except ET.ParseError as exc:
            raise TecanParseError("Tecan workbook contains invalid XML.") from exc

    rows: list[tuple[int, list[str]]] = []
    for row in root.findall("main:sheetData/main:row", XML_NS):
        values_by_col: dict[int, str] = {}
        for cell in row.findall("main:c", XML_NS):
            reference = cell.get("r", "")
            column_index = column_reference_to_index(reference)
            if column_index is None:
                continue
            values_by_col[column_index] = read_cell_value(cell, shared_strings)

        if any(value.strip() for value in values_by_col.values()):
            max_col = max(values_by_col)
            row_number = int(row.get("r", str(len(rows) + 1)))
            values = [values_by_col.get(index, "") for index in range(max_col + 1)]
            rows.append((row_number, values))

    if not rows:
        raise TecanParseError("Tecan workbook does not contain any readable data.")

    return rows


def read_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []

    strings: list[str] = []
    for item in root.findall("main:si", XML_NS):
        strings.append("".join(text.text or "" for text in item.findall(".//main:t", XML_NS)))
    return strings


def first_sheet_path(archive: zipfile.ZipFile) -> str:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {
        rel.get("Id"): rel.get("Target", "")
        for rel in relationships.findall("rel:Relationship", XML_NS)
    }

    first_sheet = workbook.find("main:sheets/main:sheet", XML_NS)
    if first_sheet is None:
        raise TecanParseError("Tecan workbook does not contain any sheets.")

    relationship_id = first_sheet.get(
        "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    )
    target = targets.get(relationship_id, "")
    if not target:
        raise TecanParseError("Tecan workbook does not point to a worksheet.")

    target = target.lstrip("/")
    if target.startswith("xl/"):
        return target
    return f"xl/{target}"


def column_reference_to_index(reference: str) -> int | None:
    match = re.match(r"([A-Z]+)", reference)
    if match is None:
        return None

    index = 0
    for letter in match.group(1):
        index = index * 26 + ord(letter) - ord("A") + 1
    return index - 1


def read_cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    cell_type = cell.get("t")
    if cell_type == "inlineStr":
        return "".join(text.text or "" for text in cell.findall(".//main:t", XML_NS)).strip()

    value = cell.find("main:v", XML_NS)
    if value is None or value.text is None:
        return ""

    text = value.text.strip()
    if cell_type == "s" and text:
        return shared_strings[int(text)].strip()
    if cell_type == "b":
        return "TRUE" if text == "1" else "FALSE"
    return text


def parse_metadata_fields(rows: list[tuple[int, list[str]]]) -> dict[str, str]:
    fields = {
        "method_name": find_label_value(rows, "method name"),
        "application": find_label_value(rows, "application"),
        "application_version": find_extra_label_value(rows, "application"),
        "device": find_label_value(rows, "device"),
        "serial_number": find_extra_label_value(rows, "device", expected_label="serial number"),
        "firmware": find_label_value(rows, "firmware"),
        "date": find_label_value(rows, "date"),
        "time": find_label_value(rows, "time"),
        "system": find_label_value(rows, "system"),
        "user": find_label_value(rows, "user"),
        "plate": find_label_value(rows, "plate"),
        "plate_name": find_label_value(rows, "name"),
        "plate_area": find_label_value(rows, "plate area"),
        "kinetic_duration": find_label_value(rows, "kinetic duration [hhmmss]"),
        "interval_time": find_label_value(rows, "interval time [hhmmss]"),
        "measurement_mode": find_measurement_mode(rows),
        "measurement_name": find_measurement_name(rows),
        "wavelength": find_label_value(rows, "measurement wavelength [nm]"),
        "number_of_flashes": find_label_value(rows, "number of flashes"),
        "settle_time_ms": find_label_value(rows, "settle time [ms]"),
        "part_of_plate": find_label_value(rows, "part of plate"),
        "start_time": find_label_value(rows, "start time"),
        "end_time": find_label_value(rows, "end time"),
    }
    return {key: value for key, value in fields.items() if value}


def find_label_value(
    rows: list[tuple[int, list[str]]],
    label: str,
    *,
    after_row: int = 0,
    before_row: int | None = None,
) -> str:
    expected = normalize_label(label)
    for row_number, values in rows:
        if row_number <= after_row or (before_row is not None and row_number >= before_row):
            continue
        if not values:
            continue

        current_label, inline_value = split_label_cell(values[0])
        if current_label != expected:
            continue

        return first_nonblank(inline_value, value_in_column(values, 4), first_after_label(values))
    return ""


def find_extra_label_value(
    rows: list[tuple[int, list[str]]],
    label: str,
    *,
    expected_label: str | None = None,
) -> str:
    expected = normalize_label(label)
    for _, values in rows:
        if not values:
            continue

        current_label, _ = split_label_cell(values[0])
        if current_label != expected:
            continue

        extra = value_in_column(values, 4)
        if expected_label is None:
            return extra

        extra_label, extra_value = split_label_cell(extra)
        if extra_label == normalize_label(expected_label):
            return extra_value
        return ""
    return ""


def find_measurement_mode(rows: list[tuple[int, list[str]]]) -> str:
    wavelength_row = find_label_row(rows, "measurement wavelength [nm]")
    if wavelength_row is None:
        return ""
    return find_previous_label_value(rows, "mode", before_row=wavelength_row)


def find_measurement_name(rows: list[tuple[int, list[str]]]) -> str:
    wavelength_row = find_label_row(rows, "measurement wavelength [nm]")
    if wavelength_row is None:
        return ""
    return find_previous_label_value(rows, "name", before_row=wavelength_row)


def find_previous_label_value(
    rows: list[tuple[int, list[str]]],
    label: str,
    *,
    before_row: int,
) -> str:
    expected = normalize_label(label)
    for row_number, values in reversed(rows):
        if row_number >= before_row or not values:
            continue
        current_label, inline_value = split_label_cell(values[0])
        if current_label == expected:
            return first_nonblank(inline_value, value_in_column(values, 4), first_after_label(values))
    return ""


def find_label_row(rows: list[tuple[int, list[str]]], label: str) -> int | None:
    expected = normalize_label(label)
    for row_number, values in rows:
        if not values:
            continue
        current_label, _ = split_label_cell(values[0])
        if current_label == expected:
            return row_number
    return None


def split_label_cell(value: str) -> tuple[str, str]:
    text = str(value).strip()
    if ":" not in text:
        return normalize_label(text), ""
    label, inline_value = text.split(":", 1)
    return normalize_label(label), inline_value.strip()


def normalize_label(value: str) -> str:
    return re.sub(r"\s+", " ", str(value).strip().rstrip(":").casefold())


def value_in_column(values: list[str], index: int) -> str:
    if index >= len(values):
        return ""
    return str(values[index]).strip()


def first_after_label(values: list[str]) -> str:
    for value in values[1:]:
        if str(value).strip():
            return str(value).strip()
    return ""


def parse_tecan_readings(
    rows: list[tuple[int, list[str]]],
) -> tuple[pd.DataFrame, list[float]]:
    header_position, header = find_readings_header(rows)
    time_index = next(
        (
            index
            for index, column in enumerate(header)
            if normalize_label(column) in {"time [s]", "time"}
        ),
        None,
    )
    if time_index is None:
        raise TecanParseError("Tecan readings table is missing the Time column.")

    temperature_index = next(
        (
            index
            for index, column in enumerate(header)
            if normalize_label(column).startswith("temp")
        ),
        None,
    )
    well_columns: list[tuple[int, str]] = []
    for index, column in enumerate(header):
        well = normalize_well_label(column)
        if well:
            well_columns.append((index, well))

    if not well_columns:
        raise TecanParseError("Tecan readings table does not contain well columns.")

    well_names = [well for _, well in well_columns]
    duplicate_wells = sorted({well for well in well_names if well_names.count(well) > 1})
    if duplicate_wells:
        raise TecanParseError(
            "Tecan readings table has duplicate well columns after normalization: "
            f"{', '.join(duplicate_wells)}."
        )

    records: list[dict[str, str]] = []
    temperatures: list[float] = []
    for _, values in rows[header_position + 1 :]:
        first_value = value_at(values, 0)
        if normalize_label(first_value) == "end time":
            break

        time_value = value_at(values, time_index)
        well_values = {
            well: value_at(values, index)
            for index, well in well_columns
        }
        if not time_value and not any(well_values.values()):
            if records:
                break
            continue

        record = {"Time": time_value, **well_values}
        records.append(record)

        if temperature_index is not None:
            temperature = parse_float(value_at(values, temperature_index))
            if temperature is not None:
                temperatures.append(temperature)

    if not records:
        raise TecanParseError("Tecan readings table does not contain any data rows.")

    return pd.DataFrame(records, columns=["Time", *well_names]), temperatures


def find_readings_header(rows: list[tuple[int, list[str]]]) -> tuple[int, list[str]]:
    for position, (_, values) in enumerate(rows):
        labels = [normalize_label(value) for value in values]
        if "time [s]" in labels and any(normalize_well_label(value) for value in values):
            return position, values
    raise TecanParseError("Could not find a Tecan readings table header.")


def parse_tecan_layout(rows: list[tuple[int, list[str]]]) -> pd.DataFrame | None:
    for position, (_, values) in enumerate(rows):
        if not values or str(values[0]).strip() != "<>":
            continue

        columns = [compact_number_text(value) for value in values[1:]]
        records: list[dict[str, str]] = []
        for _, layout_values in rows[position + 1 :]:
            if not layout_values:
                continue
            row_name = str(layout_values[0]).strip().upper()
            if not PLATE_ROW_RE.fullmatch(row_name):
                break

            for index, column in enumerate(columns, start=1):
                if not column.isdigit():
                    continue
                value = value_at(layout_values, index)
                if not is_real_layout_value(value):
                    continue
                records.append(
                    {
                        "well_loc": f"{row_name}{int(column)}",
                        "type": "",
                        "tecan_layout": str(value).strip(),
                    }
                )

        if records:
            return pd.DataFrame(records, columns=["well_loc", "type", "tecan_layout"])
        return None

    return None


def parse_filename_hints(filename: str) -> dict[str, str]:
    stem = Path(filename).stem
    metadata = parse_logphase_filename_metadata(stem)
    isolate_map = parse_isolate_map(metadata.get("isolate_map", ""))
    if len(isolate_map) == 1:
        isolate_id = next(iter(isolate_map.values()))
        metadata["isolate_id"] = isolate_id
        plate_id = "_".join(
            value
            for value in (
                metadata.get("date_start", ""),
                metadata.get("operator", ""),
                metadata.get("experiment_type", ""),
                isolate_id,
            )
            if value
        )
        if plate_id:
            metadata["plate_id"] = plate_id
    return metadata


def parse_isolate_map(value: str) -> dict[str, str]:
    if not value:
        return {}
    try:
        import json

        parsed = json.loads(value)
    except Exception:  # noqa: BLE001
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {str(key): str(item) for key, item in parsed.items() if str(item).strip()}


def build_metadata(
    fields: dict[str, str],
    filename_metadata: dict[str, str],
) -> dict[str, str]:
    metadata = {
        "instrument": tecan_instrument_name(fields.get("device", "")),
        "plate_type": fields.get("plate", ""),
        "date_start": first_nonblank(
            fields.get("start_time"),
            combine_date_time(fields.get("date", ""), fields.get("time", "")),
            filename_metadata.get("date_start"),
        ),
        "operator": first_nonblank(fields.get("user"), filename_metadata.get("operator")),
    }

    optional_fields = {
        "filename": filename_metadata.get("filename", ""),
        "date_end": fields.get("end_time", ""),
        "application": fields.get("application", ""),
        "application_version": fields.get("application_version", ""),
        "serial_number": fields.get("serial_number", ""),
        "firmware": fields.get("firmware", ""),
        "system": fields.get("system", ""),
        "experiment_type": filename_metadata.get("experiment_type", ""),
    }
    metadata.update({key: value for key, value in optional_fields.items() if value})
    return normalize_metadata_dates(metadata)


def build_assay(
    fields: dict[str, str],
    filename_metadata: dict[str, str],
    readings: pd.DataFrame,
    temperatures: list[float],
) -> dict[str, str]:
    wavelength = compact_number_text(fields.get("wavelength", ""))
    plate_area = first_nonblank(fields.get("part_of_plate"), fields.get("plate_area"))

    assay = {
        "readout_type": readout_type(fields.get("measurement_mode", "")),
        "readout_unit": f"od{wavelength}" if wavelength else "od600",
        "time_unit": "seconds",
        "plate_format": infer_plate_format(plate_area, readings.columns) or "96_well",
    }

    if wavelength:
        assay["read_wavelenth"] = f"{wavelength}nm"
    for field, value in (
        ("method_name", fields.get("method_name", "")),
        ("measurement_name", fields.get("measurement_name", "")),
        ("runtime", format_hhmmss_duration(fields.get("kinetic_duration", ""))),
        ("interval", format_hhmmss_duration(fields.get("interval_time", ""))),
        ("total_cycles", str(len(readings))),
        ("number_of_flashes", compact_number_text(fields.get("number_of_flashes", ""))),
        ("settle_time_ms", compact_number_text(fields.get("settle_time_ms", ""))),
        ("plate_area", plate_area),
    ):
        if value:
            assay[field] = value

    temperature_key, temperature_value = temperature_field(temperatures)
    if temperature_value:
        assay[temperature_key] = temperature_value

    for key in ("plate_id", "isolate_id", "isolate_map"):
        if filename_metadata.get(key):
            assay[key] = filename_metadata[key]
    if filename_metadata.get("shaking_frequency"):
        assay["shaking_frequency"] = filename_metadata["shaking_frequency"]

    return assay


def tecan_instrument_name(device: str) -> str:
    device = str(device).strip()
    if not device:
        return "Tecan"
    if device.casefold().startswith("tecan"):
        return device
    return f"Tecan {device}"


def readout_type(value: str) -> str:
    value = str(value).strip().lower()
    if "absorbance" in value:
        return "absorbance"
    return value or "absorbance"


def format_hhmmss_duration(value: str) -> str:
    parts = str(value).strip().split(":")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        return ""

    hours, minutes, seconds = (int(part) for part in parts)
    return format_duration_parts({"d": 0, "h": hours, "min": minutes, "s": seconds})


def temperature_field(values: list[float]) -> tuple[str, str]:
    if not values:
        return "temperature", ""

    minimum = min(values)
    maximum = max(values)
    if minimum == maximum:
        return "temperature", f"{format_number(minimum)}C"
    return "temperature_range", f"{format_number(minimum)}-{format_number(maximum)}C"


def infer_plate_format(plate_area: str, columns) -> str:
    match = PLATE_AREA_RE.fullmatch(str(plate_area).strip())
    if match is not None:
        start_row, start_col, end_row, end_col = match.groups()
        row_count = row_label_to_number(end_row) - row_label_to_number(start_row) + 1
        col_count = int(end_col) - int(start_col) + 1
        plate_size = row_count * col_count
        if plate_size in VALID_PLATE_SIZES:
            return f"{plate_size}_well"

    well_count = sum(1 for column in columns if normalize_well_label(str(column)))
    if well_count in VALID_PLATE_SIZES:
        return f"{well_count}_well"
    return ""


def row_label_to_number(label: str) -> int:
    number = 0
    for letter in label.upper():
        number = number * 26 + ord(letter) - ord("A") + 1
    return number


def build_atst_file_name(filename: str, filename_metadata: dict[str, str]) -> str:
    if filename_metadata.get("plate_id"):
        return f"{filename_metadata['plate_id']}.atst.txt"

    stem = filename_metadata.get("filename") or Path(filename).stem or "tecan_output"
    if stem.lower().endswith(".xlsx"):
        stem = Path(stem).stem
    return f"{stem}.atst.txt"


def normalize_well_label(value: str) -> str:
    match = WELL_LOCATION_PARTS_RE.fullmatch(str(value).strip())
    if match is None:
        return ""
    row, column = match.groups()
    return f"{row.upper()}{int(column)}"


def value_at(values: list[str], index: int) -> str:
    if index >= len(values):
        return ""
    return str(values[index]).strip()


def parse_float(value: str) -> float | None:
    try:
        return float(str(value).strip())
    except ValueError:
        return None


def compact_number_text(value: str) -> str:
    text = str(value).strip()
    if not text:
        return ""
    try:
        number = float(text)
    except ValueError:
        return text
    return format_number(number)


def format_number(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return repr(value)


def combine_date_time(date: str, time: str) -> str:
    return " ".join(value for value in (str(date).strip(), str(time).strip()) if value)


def first_nonblank(*values: str | None) -> str:
    for value in values:
        if value and str(value).strip():
            return str(value).strip()
    return ""
