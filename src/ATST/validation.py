"""Shared, non-mutating validation for parsed and programmatically edited data."""
from __future__ import annotations

from datetime import date, datetime
import re
import pandas as pd
from ATST.errors import ATSTValidationError
from ATST.parser.string_parser import parse_identifier, parse_str

REQUIRED = {
    "FILE_INFO": {"file_name", "format", "format_version", "created_on", "field_delimiter", "encoding"},
    "STUDY": {"title", "study_id"},
    "ASSAY": {"readout_type", "readout_unit", "time_unit"},
}
DATE_FIELDS = {"created_on", "date", "date_start", "date_end", "date_export"}
ISO_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}(?:T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?(?:Z|[+-][0-9]{2}:[0-9]{2})?)?\Z")


def validate_date(value: str, *, context: str) -> None:
    if not ISO_DATE.fullmatch(value):
        raise ATSTValidationError(f"{context} must be an ISO 8601 date or datetime: {value!r}")
    try:
        if "T" in value:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        else:
            date.fromisoformat(value)
    except ValueError as exc:
        raise ATSTValidationError(f"{context} is not a valid date: {value!r}") from exc


def validate_long_table(name: str, data: dict[str, str]) -> None:
    if not isinstance(data, dict):
        raise ATSTValidationError(f"{name} must be a dictionary of strings.")
    missing = REQUIRED.get(name, set()) - set(data)
    if missing:
        raise ATSTValidationError(f"{name} missing required fields: {', '.join(sorted(missing))}")
    for key, value in data.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ATSTValidationError(f"{name} fields and values must be strings.")
        if parse_identifier(key) != key:
            raise ATSTValidationError(f"{name} field names must not have surrounding spaces.")
        parse_str(value)
        if key in REQUIRED.get(name, ()) and not value.strip():
            raise ATSTValidationError(f"{name}.{key} must be non-empty.")
        if key in DATE_FIELDS and value:
            validate_date(value, context=f"{name}.{key}")
    if name == "FILE_INFO":
        for key, expected in {"format": "ATST", "format_version": "0.1", "field_delimiter": "TAB", "encoding": "UTF-8"}.items():
            if data[key] != expected:
                raise ATSTValidationError(f"FILE_INFO.{key} must be {expected!r}.")
        if not data["file_name"].endswith((".atst.txt", ".atst.tsv")):
            raise ATSTValidationError("FILE_INFO.file_name must use .atst.txt or .atst.tsv")
    if name == "ASSAY" and data["time_unit"] not in {"s", "seconds", "min", "minutes", "h", "hours"}:
        raise ATSTValidationError("ASSAY.time_unit must be s, seconds, min, minutes, h, or hours.")


def validate_table(data: pd.DataFrame, *, context: str, allowed=()) -> None:
    if not isinstance(data, pd.DataFrame):
        raise ATSTValidationError(f"{context} must be a DataFrame.")
    if data.empty:
        raise ATSTValidationError(f"{context} must contain at least one row and column.")
    columns = [parse_identifier(str(column), allow_reserved=allowed) for column in data.columns]
    if len(columns) != len(set(columns)):
        raise ATSTValidationError(f"{context} has duplicate columns.")
    if list(data.columns) != columns:
        raise ATSTValidationError(f"{context} columns must be normalized strings.")
    for row in data.itertuples(index=False, name=None):
        for value in row:
            if not pd.isna(value):
                parse_str(str(value))


def validate_ids(values, *, context: str) -> list[str]:
    ids = []
    for value in values:
        if pd.isna(value):
            raise ATSTValidationError(f"{context} identifiers must be non-empty.")
        identifier = parse_identifier(str(value))
        if str(value) != identifier:
            raise ATSTValidationError(f"{context} identifiers must not have surrounding spaces.")
        ids.append(identifier)
    if len(ids) != len(set(ids)):
        raise ATSTValidationError(f"{context} identifiers must be unique.")
    return ids


def validate_entities(entities) -> None:
    if entities is None:
        return
    names = []
    for key, table in entities.tables.items():
        name = parse_identifier(table.table_name)
        names.append(name)
        if key != name:
            raise ATSTValidationError(f"ENTITIES table key {key!r} differs from name {name!r}.")
        pk = parse_identifier(table.pk)
        validate_table(table.data, context=f"ENTITIES.{name}")
        if pk not in table.data:
            raise ATSTValidationError(f"ENTITIES.{name} missing primary key column {pk!r}.")
        validate_ids(table.data[pk], context=f"ENTITIES.{name}.{pk}")
    if len(names) != len(set(names)):
        raise ATSTValidationError("ENTITIES table names must be unique.")


def validate_readout_registry(block) -> list[str]:
    if list(block.data.columns) != ["readout_id"]:
        raise ATSTValidationError("READOUT_IDS must contain only the readout_id column.")
    ids = validate_ids(block.data["readout_id"], context="READOUT_IDS.readout_id")
    if not ids:
        raise ATSTValidationError("READOUT_IDS must contain at least one readout_id.")
    return ids
