from __future__ import annotations

import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
import json
from io import StringIO
from pathlib import Path
import re

import pandas as pd

from ATST.device_readers.protocol import DeviceOutput
from ATST.device_readers._utils import (
    normalize_metadata_dates,
    ISOLATE_ID_RE,
    WELL_LOCATION_PARTS_RE,
    is_real_layout_value,
)
from ATST.device_readers.logphase600 import (
    format_duration_parts,
    parse_filename_shaking_frequency,
    parse_logphase_filename_metadata,
)


TIME_LABEL_RE = re.compile(
    r"^\s*(?:(?P<hours>\d+(?:\.\d+)?)\s*h)?\s*"
    r"(?:(?P<minutes>\d+(?:\.\d+)?)\s*min)?\s*$",
    flags=re.IGNORECASE,
)
VALID_PLATE_FORMATS = (
    (2, 3, "6_well"),
    (3, 4, "12_well"),
    (4, 6, "24_well"),
    (6, 8, "48_well"),
    (8, 12, "96_well"),
    (16, 24, "384_well"),
    (32, 48, "1536_well"),
)


class ClariostarParseError(ValueError):
    """Raised when CLARIOstar device output cannot be parsed."""


class ClariostarOutput(DeviceOutput):
    """Parsed CLARIOstar data ready to use when building an ATST file."""


class ClariostarReader:
    """Read CLARIOstar exports."""

    def read(
        self,
        raw: bytes | str,
        *,
        filename: str = "",
    ) -> ClariostarOutput:
        return parse_clariostar_output(raw, filename=filename)


def parse_clariostar_output(
    raw: bytes | str,
    *,
    filename: str = "",
) -> ClariostarOutput:
    """Parse a CLARIOstar CSV output into ATST-ready fields."""

    rows = read_clariostar_csv(raw)
    header_index = find_clariostar_table_header(rows)
    metadata_fields = parse_metadata_fields(rows[:header_index])
    filename_metadata = parse_logphase_filename_metadata(filename)
    id1_metadata = parse_id1_hints(metadata_fields.get("id1", ""))
    hints = merge_hints(filename_metadata, id1_metadata)

    readings, layout, time_values, well_names = parse_clariostar_table(
        rows,
        header_index,
    )
    metadata = build_metadata(metadata_fields, hints, filename)
    assay = build_assay(
        metadata_fields,
        hints,
        rows[header_index],
        readings,
        time_values,
        well_names,
    )

    return ClariostarOutput(
        file_name=build_atst_file_name(filename, filename_metadata),
        metadata=metadata,
        assay=assay,
        readings=readings,
        layout=layout,
    )


def read_clariostar_csv(raw: bytes | str) -> list[list[str]]:
    if not isinstance(raw, str):
        for encoding in ("utf-8-sig", "cp1252", "latin1"):
            try:
                raw = raw.decode(encoding) # type: ignore
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ClariostarParseError("CLARIOstar output is not valid text.")

    rows = [
        [str(value).strip() for value in row]
        for row in csv.reader(StringIO(raw))
        if any(str(value).strip() for value in row)
    ]
    if not rows:
        raise ClariostarParseError("CLARIOstar CSV is empty.")
    return rows


def find_clariostar_table_header(rows: list[list[str]]) -> int:
    for index, row in enumerate(rows):
        if normalize_label(value_at(row, 0)) == "well" and normalize_label(
            value_at(row, 1)
        ) == "content":
            return index
    raise ClariostarParseError("Could not find a CLARIOstar Well/Content table.")


def parse_metadata_fields(rows: list[list[str]]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for row in rows:
        for cell in row:
            value = str(cell).strip()
            if not value or value.casefold().startswith("unnamed:"):
                continue
            if ":" in value:
                key, item = value.split(":", 1)
                key = normalize_label(key)
                item = item.strip()
                if key and item and not fields.get(key):
                    fields[key] = item
                continue

            normalized = normalize_label(value)
            if normalized in {"absorbance", "fluorescence"}:
                fields.setdefault("measurement_mode", value)
            elif "displayed as" in normalized:
                fields.setdefault("readout_description", value)

    return fields


def parse_id1_hints(value: str) -> dict[str, str]:
    text = str(value).strip()
    if not text:
        return {}

    metadata: dict[str, str] = {}
    parts = [part.strip() for part in text.split("_") if part.strip()]
    if len(parts) >= 2 and parts[0].isdigit() and len(parts[0]) == 4:
        metadata["operator"] = parts[1]
        candidate_parts = parts[2:]
    else:
        candidate_parts = parts

    for index, part in enumerate(candidate_parts):
        shaking_frequency = parse_filename_shaking_frequency(part)
        if not shaking_frequency and (index == len(candidate_parts) - 1) and part.isdigit():
            shaking_frequency = f"{int(part)}rpm"
        if shaking_frequency:
            metadata["shaking_frequency"] = shaking_frequency
            continue

        isolate_id = parse_isolate_id(part)
        if isolate_id:
            metadata["isolate_id"] = isolate_id

    return metadata


def parse_isolate_id(value: str) -> str:
    value = str(value).strip().upper()
    if ISOLATE_ID_RE.fullmatch(value):
        return value
    if any(char.isalpha() for char in value) and any(char.isdigit() for char in value):
        return value
    return ""


def merge_hints(
    filename_metadata: dict[str, str],
    content_metadata: dict[str, str],
) -> dict[str, str]:
    merged = filename_metadata.copy()
    for key, value in content_metadata.items():
        if value:
            merged[key] = value

    if not merged.get("isolate_id"):
        isolate_map = parse_isolate_map(merged.get("isolate_map", ""))
        if len(isolate_map) == 1:
            merged["isolate_id"] = next(iter(isolate_map.values()))

    return merged


def parse_clariostar_table(
    rows: list[list[str]],
    header_index: int,
) -> tuple[pd.DataFrame, pd.DataFrame | None, list[float], list[str]]:
    time_row = rows[header_index + 1] if header_index + 1 < len(rows) else []
    if normalize_label(value_at(time_row, 1)) != "time":
        raise ClariostarParseError("CLARIOstar table is missing the Time row.")

    time_columns = [
        (index, parse_time_minutes(value))
        for index, value in enumerate(time_row[2:], start=2)
        if str(value).strip()
    ]
    if not time_columns:
        raise ClariostarParseError("CLARIOstar table does not contain time values.")

    records = [
        {"Time": format_number(minutes)}
        for _, minutes in time_columns
    ]
    layout_records: list[dict[str, str]] = []
    well_names: list[str] = []
    seen_wells: set[str] = set()

    for row in rows[header_index + 2 :]:
        well = normalize_well_label(value_at(row, 0))
        if not well:
            continue
        if well in seen_wells:
            raise ClariostarParseError(f"Duplicate well location after normalization: {well}")
        seen_wells.add(well)

        content = value_at(row, 1)
        if is_real_layout_value(content):
            layout_records.append(
                {
                    "well_loc": well,
                    "type": "",
                    "content": content,
                }
            )

        values = [value_at(row, index) for index, _ in time_columns]
        well_names.append(well)
        for record, value in zip(records, values):
            record[well] = value

    if not well_names:
        raise ClariostarParseError("CLARIOstar table does not contain well readings.")

    readings = pd.DataFrame(records, columns=["Time", *well_names])
    layout = None
    if layout_records:
        layout = pd.DataFrame(layout_records, columns=["well_loc", "type", "content"])
    return readings, layout, [minutes for _, minutes in time_columns], well_names


def build_metadata(
    fields: dict[str, str],
    hints: dict[str, str],
    filename: str,
) -> dict[str, str]:
    metadata = {
        "instrument": "CLARIOstar",
        "date_start": first_nonblank(
            parse_run_datetime(fields.get("date", ""), fields.get("time", "")),
            hints.get("date_start"),
            fields.get("date"),
        ),
        "operator": first_nonblank(
            user_value(fields.get("user", "")),
            hints.get("operator"),
        ),
        "filename": Path(filename).stem,
        "test_name": fields.get("test_name", ""),
        "experiment_type": fields.get("test_name", ""),
        "id1": fields.get("id1", ""),
    }
    for field, value in (
        ("path", fields.get("path", "")),
        ("test_id", first_nonblank(fields.get("test_id"), fields.get("test_run_no"))),
        ("test_run_no", fields.get("test_run_no", "")),
        ("measurement_mode", fields.get("measurement_mode", "")),
    ):
        if value:
            metadata[field] = value

    return normalize_metadata_dates({key: value for key, value in metadata.items() if value})


def build_assay(
    fields: dict[str, str],
    hints: dict[str, str],
    header_row: list[str],
    readings: pd.DataFrame,
    time_values: list[float],
    well_names: list[str],
) -> dict[str, str]:
    wavelength = parse_wavelength(header_row)
    measurement_name = first_nonblank(*header_row[2:])
    readout = readout_type(fields.get("measurement_mode", measurement_name))
    assay = {
        "readout_type": readout,
        "readout_unit": readout_unit(readout, wavelength, fields),
        "time_unit": "minutes",
        "plate_format": infer_plate_format(well_names),
    }

    if wavelength:
        assay["read_wavelenth"] = f"{wavelength}nm"
    if measurement_name:
        assay["measurement_name"] = measurement_name
    if fields.get("test_name"):
        assay["method_name"] = fields["test_name"]
    if time_values:
        assay["runtime"] = format_minutes_duration(max(time_values))
        interval = common_interval(time_values)
        if interval:
            assay["interval"] = format_minutes_duration(interval)
    assay["total_cycles"] = str(len(readings))

    for key in ("shaking_frequency", "isolate_id", "isolate_map"):
        if hints.get(key):
            assay[key] = hints[key]

    return {key: value for key, value in assay.items() if value}


def parse_run_datetime(date_text: str, time_text: str) -> str:
    date_text = str(date_text).strip()
    time_text = str(time_text).strip()
    if not date_text:
        return ""

    date_value = parse_date(date_text)
    if date_value is None:
        return date_text

    time_value = parse_time(time_text)
    if time_value is None:
        return date_value.strftime("%Y-%m-%d")

    return datetime.combine(date_value.date(), time_value.time()).strftime(
        "%Y-%m-%dT%H:%M:%S"
    )


def parse_date(value: str) -> datetime | None:
    for date_format in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%Y_%m_%d"):
        try:
            return datetime.strptime(value, date_format)  # noqa: DTZ007
        except ValueError:
            continue
    return None


def parse_time(value: str) -> datetime | None:
    for time_format in ("%I:%M:%S %p", "%I:%M %p", "%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(value, time_format)  # noqa: DTZ007
        except ValueError:
            continue
    return None


def parse_time_minutes(value: str) -> float:
    text = str(value).strip()
    if not text:
        raise ClariostarParseError("CLARIOstar table contains a blank Time value.")

    match = TIME_LABEL_RE.fullmatch(text)
    if match is not None and (match.group("hours") or match.group("minutes")):
        hours = float(match.group("hours") or 0)
        minutes = float(match.group("minutes") or 0)
        return hours * 60 + minutes

    try:
        return float(text)
    except InvalidOperation as exc:
        raise ClariostarParseError(f"Unsupported CLARIOstar Time value: {text!r}") from exc


def common_interval(values: list[float]) -> float:
    if len(values) < 2:
        return 0
    intervals = [
        round(values[index] - values[index - 1], 10)
        for index in range(1, len(values))
    ]
    if all(interval == intervals[0] for interval in intervals):
        return intervals[0]
    return 0


def format_minutes_duration(minutes: float) -> str:
    if minutes <= 0:
        return ""
    if not float(minutes).is_integer():
        return f"{minutes:g}min"

    total_minutes = int(minutes)
    return format_duration_parts(
        {
            "d": 0,
            "h": total_minutes // 60,
            "min": total_minutes % 60,
            "s": 0,
        }
    )


def parse_wavelength(header_row: list[str]) -> str:
    for value in header_row[2:]:
        match = re.search(r"\((\d+(?:\.\d+)?)\)", str(value))
        if match is not None:
            return format_number(float(match.group(1)))
        match = re.search(r"(\d+(?:\.\d+)?)\s*nm", str(value), flags=re.IGNORECASE)
        if match is not None:
            return format_number(float(match.group(1)))
    return ""


def readout_type(value: str) -> str:
    value = str(value).casefold()
    if "fluorescence" in value:
        return "fluorescence"
    return "absorbance"


def readout_unit(readout: str, wavelength: str, fields: dict[str, str]) -> str:
    if readout == "absorbance":
        return f"od{wavelength}" if wavelength else "OD"
    description = fields.get("readout_description", "").casefold()
    if "rfu" in description:
        return "RFU"
    return "GFP" if "gfp" in description else "RFU"


def infer_plate_format(well_names: list[str]) -> str:
    max_row = 0
    max_column = 0
    for well in well_names:
        match = WELL_LOCATION_PARTS_RE.fullmatch(well)
        if match is None:
            continue
        row, column = match.groups()
        max_row = max(max_row, row_label_to_number(row))
        max_column = max(max_column, int(column))

    for row_count, column_count, plate_format in VALID_PLATE_FORMATS:
        if max_row <= row_count and max_column <= column_count:
            return plate_format
    return "96_well"


def row_label_to_number(label: str) -> int:
    number = 0
    for letter in label.upper():
        number = number * 26 + ord(letter) - ord("A") + 1
    return number


def normalize_well_label(value: str) -> str:
    match = WELL_LOCATION_PARTS_RE.fullmatch(str(value).strip())
    if match is None:
        return ""
    row, column = match.groups()
    return f"{row.upper()}{int(column)}"


def normalize_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().casefold()).strip("_")


def parse_isolate_map(value: str) -> dict[str, str]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {str(key): str(item) for key, item in parsed.items() if str(item).strip()}


def build_atst_file_name(filename: str, filename_metadata: dict[str, str]) -> str:
    stem = filename_metadata.get("filename") or Path(filename).stem or "clariostar_output"
    return f"{Path(stem).stem}.atst.txt"


def first_nonblank(*values: str | None) -> str:
    for value in values:
        if value and str(value).strip():
            return str(value).strip()
    return ""


def user_value(value: str) -> str:
    value = str(value).strip()
    return "" if value.casefold() == "user" else value


def value_at(values: list[str], index: int) -> str:
    if index >= len(values):
        return ""
    return str(values[index]).strip()


def format_number(value: float | Decimal) -> str:
    if isinstance(value, Decimal):
        return str(value)
    if float(value).is_integer():
        return str(int(value))
    return repr(value)
