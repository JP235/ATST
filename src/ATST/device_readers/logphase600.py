from __future__ import annotations

from datetime import datetime
import json
import csv
from io import StringIO
from pathlib import Path
import re

import pandas as pd
from ATST.numeric import NUMBER, duration_text

from ATST.device_readers.protocol import DeviceOutput
from ATST.device_readers._utils import (
    normalize_metadata_dates,
    EXPORT_DATETIME_RE,
    FILENAME_RE,
    FILENAME_SHAKING_FREQUENCY_RE,
    ISOLATE_ID_RE,
    ISOLATE_STRING_RE,
    PLATE_TOKEN_RE,
    RUN_DATE_RE,
    WELL_LOCATION_RE,
)


class LogPhase600Output(DeviceOutput):
    """Parsed LogPhase600 data ready to use when building an ATST file."""


class LogPhase600Reader:
    """Read LogPhase600 exports."""

    def read(
        self,
        raw: bytes | str,
        *,
        filename: str = "",
    ) -> LogPhase600Output:
        return parse_logphase600_output(raw, filename=filename)


class LogPhaseParseError(ValueError):
    """Raised when LogPhase600 device output cannot be parsed."""


def parse_logphase600_output(
    raw: bytes | str,
    *,
    filename: str = "",
) -> LogPhase600Output:
    """Parse raw LogPhase600 output into ATST-ready fields.

    Args:
        raw: Uploaded device-output bytes or decoded text.
        filename: Original filename, used to infer metadata and output name.
    """

    text = decode_logphase_text(raw)
    lines = text.splitlines()
    data_start_idx = find_logphase_table_start(lines)
    header = parse_logphase_header(lines[:data_start_idx])
    readings = parse_logphase_readings(lines[data_start_idx:])
    filename_metadata = parse_logphase_filename_metadata(filename)
    filename_metadata = apply_header_plate_number(
        filename_metadata,
        header.get("plate_number", ""),
    )

    metadata = build_metadata(header, filename_metadata)
    assay = build_assay(header, filename_metadata)
    file_name = build_atst_file_name(filename, filename_metadata)

    return LogPhase600Output(
        file_name=file_name,
        metadata=metadata,
        assay=assay,
        readings=readings,
    )


def decode_logphase_text(raw: bytes | str) -> str:
    """Decode uploaded LogPhase text, accepting UTF-8 with BOM or latin1."""

    if isinstance(raw, str):
        return raw

    for encoding in ("utf-8-sig", "latin1"):
        try:
            return raw.decode(encoding)  # type: ignore
        except UnicodeDecodeError:
            continue

    raise LogPhaseParseError("Device output is not valid text.")


def find_logphase_table_start(lines: list[str]) -> int:
    """Return the index of the readings header row in LogPhase output."""

    for index, line in enumerate(lines):
        columns = [column.strip() for column in line.split("\t")]
        if columns and columns[0] == "Time" and "A1" in columns:
            return index

        columns = [column.strip() for column in line.split(",")]
        if columns and columns[0] == "Time" and "A1" in columns:
            return index

    raise LogPhaseParseError(
        "Could not find the LogPhase table header row starting with Time and A1."
    )


def parse_logphase_header(lines: list[str]) -> dict[str, str]:
    """Parse key/value header lines before the readings table."""

    header: dict[str, str] = {}

    for line in lines:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = re.sub(r"[^a-z0-9]+", "_", key.strip().lower()).strip("_")
        if key:
            header[key] = value.strip()

    return header


def parse_logphase_readings(lines: list[str]) -> pd.DataFrame:
    """Parse the LogPhase readings table into `Time` and well columns."""

    if not lines:
        raise LogPhaseParseError("Device output does not contain a readings table.")

    header_line = lines[0]
    sep = "\t" if "\t" in header_line else ","
    table_text = "\n".join(lines).strip("\r\n")
    columns = [cell.strip() for cell in next(csv.reader([header_line], delimiter=sep))]
    if len(columns) != len(set(columns)):
        raise LogPhaseParseError("Readings table has duplicate column names")

    try:
        df = pd.read_csv(
            StringIO(table_text),
            sep=sep,
            dtype=str,
            keep_default_na=False,
            na_filter=False,
        )
    except pd.errors.ParserError as exc:
        raise LogPhaseParseError(f"Could not parse readings table: {exc}") from exc

    if len(df.columns) == 1:
        fallback_sep = "," if sep == "\t" else "\t"
        df = pd.read_csv(
            StringIO(table_text),
            sep=fallback_sep,
            dtype=str,
            keep_default_na=False,
            na_filter=False,
        )

    df.columns = [str(column).strip() for column in df.columns]
    df = df.map(lambda value: str(value).strip())

    if "Time" not in df.columns:
        raise LogPhaseParseError("Readings table is missing the Time column.")

    well_columns = [
        column for column in df.columns if WELL_LOCATION_RE.fullmatch(column)
    ]
    if not well_columns:
        raise LogPhaseParseError("Readings table does not contain well columns.")

    non_empty_readings = df[well_columns].apply(
        lambda row: any(str(value).strip() for value in row),
        axis=1,
    )
    has_time = df["Time"].str.strip().ne("")
    df = df.loc[non_empty_readings | has_time, ["Time", *well_columns]].copy()

    if df.empty:
        raise LogPhaseParseError("Readings table does not contain any data rows.")

    df["Time"] = df["Time"].map(time_value_to_seconds)
    return df.reset_index(drop=True)


def time_value_to_seconds(value: str) -> str:
    """Convert a LogPhase time value into seconds as ATST text."""

    value = str(value).strip()
    if not value:
        raise LogPhaseParseError("Readings table contains a blank Time value.")

    if NUMBER.fullmatch(value):
        return value
    try:
        return duration_text(value, hours_to_units=3600, minutes_to_units=60)
    except ValueError as exc:
        raise LogPhaseParseError(f"Unsupported Time value: {value!r}") from exc


def parse_logphase_filename_metadata(filename: str) -> dict[str, str]:
    """Infer run metadata from a LogPhase export filename when possible."""

    name = Path(filename).name
    for suffix in (".txt", ".tsv", ".csv"):
        if name.lower().endswith(suffix):
            name = name[: -len(suffix)]
            break

    metadata: dict[str, str] = {"filename": name}
    shaking_frequency = parse_filename_shaking_frequency(name)
    if shaking_frequency:
        metadata["shaking_frequency"] = shaking_frequency

    match = FILENAME_RE.search(name)
    if match is None:
        metadata.update(parse_relaxed_filename_metadata(name))
        return metadata

    date_start = match.group("date_start").replace("_", "-")
    operator, experiment_type, isolate_string = parse_filename_body(
        match.group("body")
    )
    isolates = ISOLATE_ID_RE.findall(isolate_string)
    isolate_map = build_isolate_map(isolates, "")

    metadata.update(
        {
            "date_start": date_start,
            "operator": operator,
            "experiment_type": experiment_type,
            "filename": name,
        }
    )
    if isolate_map:
        metadata["isolate_map"] = json.dumps(isolate_map, sort_keys=True)

    export_datetime = parse_export_datetime(
        match.group("export_date"),
        match.group("export_time"),
    )
    if export_datetime:
        metadata["date_export"] = export_datetime

    return metadata


def parse_filename_shaking_frequency(name: str) -> str:
    match = FILENAME_SHAKING_FREQUENCY_RE.search(name)
    if match is None:
        return ""
    return f"{match.group('rpm')}rpm"


def parse_relaxed_filename_metadata(name: str) -> dict[str, str]:
    """Best-effort filename parsing for files outside the usual convention."""

    metadata: dict[str, str] = {}

    date_start_match = RUN_DATE_RE.search(name)
    if date_start_match is not None:
        metadata["date_start"] = date_start_match.group(0).replace("_", "-")

    export_match = last_match(EXPORT_DATETIME_RE.finditer(name))
    if export_match is not None:
        metadata["date_export"] = parse_export_datetime(
            export_match.group("export_date"),
            export_match.group("export_time"),
        )

    body = relaxed_filename_body(name, date_start_match, export_match)
    filename_plate_num = parse_relaxed_plate_num(body)
    if filename_plate_num:
        body = remove_trailing_plate_num(body, filename_plate_num)

    operator, experiment_type, isolate_string = parse_filename_body(body)
    isolates = ISOLATE_ID_RE.findall(isolate_string)
    isolate_map = build_isolate_map(isolates, "")

    for key, value in (
        ("operator", operator),
        ("experiment_type", experiment_type),
        ("isolate_map", json.dumps(isolate_map, sort_keys=True) if isolate_map else ""),
    ):
        if value:
            metadata[key] = value

    return metadata


def apply_header_plate_number(
    filename_metadata: dict[str, str],
    plate_number: str,
) -> dict[str, str]:
    metadata = filename_metadata.copy()
    metadata.pop("plate_num", None)
    metadata.pop("isolate_id", None)
    metadata.pop("plate_id", None)

    plate_num = str(plate_number).strip()
    if not plate_num:
        return metadata

    metadata["plate_num"] = plate_num
    isolate_map = parse_isolate_map(metadata.get("isolate_map", ""))
    isolate_id = isolate_map.get(plate_num)
    if not isolate_id and len(isolate_map) == 1:
        isolate_id = next(iter(isolate_map.values()))

    if isolate_id:
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
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {str(key): str(item) for key, item in parsed.items() if str(item).strip()}


def last_match(matches) -> re.Match[str] | None:
    last = None
    for last in matches:
        pass
    return last


def relaxed_filename_body(
    name: str,
    date_start_match: re.Match[str] | None,
    export_match: re.Match[str] | None,
) -> str:
    body = name
    if export_match is not None:
        body = f"{body[: export_match.start()]}{body[export_match.end() :]}"
    if date_start_match is not None:
        body = f"{body[: date_start_match.start()]}{body[date_start_match.end() :]}"
    return body.strip(" _-")


def parse_relaxed_plate_num(body: str) -> str:
    plate_match = PLATE_TOKEN_RE.search(body)
    if plate_match is not None:
        return plate_match.group("plate_num")

    parts = [part for part in re.split(r"[_\s]+", body.strip(" _-")) if part]
    if parts and parts[-1].isdigit():
        return parts[-1]

    return ""


def remove_trailing_plate_num(body: str, plate_num: str) -> str:
    body = PLATE_TOKEN_RE.sub(" ", body)
    body = re.sub(rf"(?:(?<=^)|(?<=[_\s])){re.escape(plate_num)}$", "", body)
    return body.strip(" _-")


def build_isolate_map(isolates: list[str], plate_num: str) -> dict[str, str]:
    if not isolates:
        return {}
    if len(isolates) == 1:
        return {plate_num: isolates[0]} if plate_num else {"1": isolates[0]}
    return {str(index + 1): isolate for index, isolate in enumerate(isolates)}


def parse_filename_body(body: str) -> tuple[str, str, str]:
    """Split the filename body into operator, experiment type, and isolates."""

    body = body.strip(" _-")
    if not body:
        return "", "", ""
    if "_" not in body and re.search(r"\s", body):
        return "", "", ""

    parts = [part for part in body.split("_") if part]
    if not parts:
        return "", "", ""

    isolate_string = ""
    if ISOLATE_STRING_RE.fullmatch(parts[-1]):
        isolate_string = parts.pop()

    descriptor_parts = parts
    if not descriptor_parts:
        return "", "", isolate_string
    if len(descriptor_parts) == 1:
        return "", descriptor_parts[0], isolate_string

    return descriptor_parts[0], "_".join(descriptor_parts[1:]), isolate_string


def parse_export_datetime(export_date: str, export_time: str) -> str:
    """Parse a LogPhase export date/time pair into ISO-like text."""

    try:
        parsed = datetime.strptime(  # noqa: DTZ007
            f"{export_date} {export_time}",
            "%d-%b-%Y %H-%M-%S",
        )
    except ValueError:
        return ""

    return parsed.isoformat()


def build_metadata(
    header: dict[str, str],
    filename_metadata: dict[str, str],
) -> dict[str, str]:
    """Build ATST `METADATA` fields from parsed header and filename data."""

    metadata = {
        "instrument": first_nonblank(header.get("instrument"), "LogPhase600"),
        "plate_type": header.get("plate_type", ""),
        "date_start": first_nonblank(
            header.get("date_start"),
            header.get("date"),
            filename_metadata.get("date_start"),
        ),
        "operator": first_nonblank(
            header.get("operator"),
            filename_metadata.get("operator"),
        ),
    }

    for field in ("date_export", "experiment_type"):
        value = first_nonblank(header.get(field), filename_metadata.get(field))
        if value:
            metadata[field] = value

    return normalize_metadata_dates(metadata)


def build_assay(
    header: dict[str, str],
    filename_metadata: dict[str, str],
) -> dict[str, str]:
    """Build ATST `ASSAY` fields from parsed header and filename data."""

    wavelength = parse_wavelength(header.get("read", ""))
    plate_format = parse_plate_format(header.get("plate_type", "")) or "96_well"
    runtime, interval, read_count = parse_discontinuous_kinetics(
        header.get("discontinuous_kinetics", "")
    )

    assay = {
        "readout_type": "absorbance",
        "readout_unit": f"od{wavelength}" if wavelength else "od600",
        "time_unit": "seconds",
        "plate_format": plate_format,
    }

    if wavelength:
        assay["read_wavelenth"] = f"{wavelength}nm"

    plate_num = str(header.get("plate_number", "")).strip()
    assay.update(
        {
            key: filename_metadata[key]
            for key in (
                "plate_id",
                "isolate_id",
                "filename",
                "isolate_map",
            )
            if filename_metadata.get(key)
        }
    )

    if plate_num:
        assay["plate_num"] = plate_num
    if header.get("plate_number"):
        assay["device_plate_number"] = header["plate_number"]
    if runtime:
        assay["runtime"] = runtime
    if interval:
        assay["interval"] = interval
    if read_count:
        assay["read_count"] = read_count

    for header_key, assay_key in (
        ("incubator", "incubator"),
        ("temperature_setpoint", "temperature_setpoint"),
        ("temperature_gradient", "temperature_gradient"),
        ("shaking", "shaking"),
        ("shaking_frequency", "shaking_frequency"),
    ):
        if header.get(header_key):
            assay[assay_key] = header[header_key]

    if not assay.get("shaking_frequency") and filename_metadata.get(
        "shaking_frequency"
    ):
        assay["shaking_frequency"] = filename_metadata["shaking_frequency"]

    return assay


def first_nonblank(*values: str | None) -> str:
    for value in values:
        if value and str(value).strip():
            return str(value).strip()
    return ""


def parse_wavelength(value: str) -> str:
    """Extract a wavelength value such as `600` from text like `600 nm`."""

    match = re.search(r"(\d+(?:\.\d+)?)\s*nm", value, flags=re.IGNORECASE)
    if match is None:
        return ""

    number = float(match.group(1))
    if number.is_integer():
        return str(int(number))
    return f"{number:g}"


def parse_plate_format(value: str) -> str:
    """Extract an ATST plate format such as `96_well` from text."""

    match = re.search(r"(\d+)\s*well", value, flags=re.IGNORECASE)
    if match is None:
        return ""
    return f"{match.group(1)}_well"


def parse_discontinuous_kinetics(value: str) -> tuple[str, str, str]:
    """Parse runtime, interval, and read count from kinetics header text."""

    if not value:
        return "", "", ""

    runtime = parse_labeled_duration(value, "Runtime")
    interval = parse_labeled_duration(value, "Interval")
    read_count = ""

    read_count_match = re.search(r"(\d+)\s+Reads?", value, flags=re.IGNORECASE)
    if read_count_match is not None:
        read_count = read_count_match.group(1)

    return runtime, interval, read_count


def parse_labeled_duration(value: str, label: str) -> str:
    match = re.search(
        rf"{label}\s+(?P<duration>\d+(?::\d+)*)(?:\s+\((?P<format>[^)]+)\))?",
        value,
        flags=re.IGNORECASE,
    )
    if match is None:
        return ""

    duration = match.group("duration")
    duration_format = match.group("format")
    if duration_format:
        formatted = format_duration_from_pattern(duration, duration_format)
        if formatted:
            return formatted

    return duration


def format_duration_from_pattern(duration: str, duration_format: str) -> str:
    fields = [normalize_duration_field(field) for field in duration_format.split(":")]
    values = duration.split(":")
    if len(fields) != len(values):
        return ""

    totals = {"d": 0, "h": 0, "min": 0, "s": 0}
    for field, value in zip(fields, values):
        if field not in totals:
            return ""
        totals[field] += int(value)

    return format_duration_parts(totals)


def normalize_duration_field(field: str) -> str:
    normalized = field.strip().lower()
    aliases = {
        "d": "d",
        "dd": "d",
        "day": "d",
        "days": "d",
        "h": "h",
        "hh": "h",
        "hour": "h",
        "hours": "h",
        "m": "min",
        "mm": "min",
        "min": "min",
        "mins": "min",
        "minute": "min",
        "minutes": "min",
        "s": "s",
        "ss": "s",
        "sec": "s",
        "secs": "s",
        "second": "s",
        "seconds": "s",
    }
    return aliases.get(normalized, normalized)


def format_duration_parts(parts: dict[str, int]) -> str:
    if not any(parts.values()):
        return "0s"

    output = []
    for field in ("d", "h", "min", "s"):
        value = parts[field]
        if value:
            unit = "D" if field == "d" else field
            output.append(f"{value}{unit}")
    return "".join(output)


def build_atst_file_name(
    filename: str,
    filename_metadata: dict[str, str],
) -> str:
    """Build the default ATST output filename for parsed device output."""

    if filename_metadata.get("plate_id"):
        return f"{filename_metadata['plate_id']}.atst.txt"

    stem = filename_metadata.get("filename") or Path(filename).stem or "logphase_output"
    return f"{stem}.atst.txt"
