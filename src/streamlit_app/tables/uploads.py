from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path

from ATST.blocks import LAYOUT
from ATST.blocks.base_classes import WideTableBlock
from ATST.errors import ATSTError
from ATST.parser.block_parser import parse_block
from ATST.parser.parser import parse_file
import pandas as pd

from streamlit_app.tables.utils import (
    is_well_column,
    normalize_well_loc,
    plate_wells,
    well_sort_key,
)


class UploadedTableParseError(Exception):
    """Raised when an uploaded table or ATST layout block cannot be read."""


def read_uploaded_table(
    uploaded_file, *, atst_block: str | None = None
) -> pd.DataFrame:
    """Read an uploaded CSV/TSV/TXT table or an ATST block table.

    Args:
        uploaded_file: Streamlit uploaded file.
        atst_block: Required ATST block name when reading a table from ATST text.
    """

    name = getattr(uploaded_file, "name", "uploaded file")

    try:
        raw = uploaded_file.getvalue().decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise UploadedTableParseError(
            f"{name} is not valid UTF-8 text. Upload a CSV, TSV, TXT, or ATST text file."
        ) from exc

    try:
        if (
            "===FILE_START" in raw
            or ":::LAYOUT_START" in raw
            or ":::LAYOUT_END" in raw
        ):
            if atst_block is None:
                raise UploadedTableParseError(
                    f"{name} looks like an ATST file, not a standalone table."
                )
            return read_block_from_atst(raw, block_name=atst_block, name=name)

        return read_delimited_table(raw, name=name)
    except UploadedTableParseError:
        raise
    except (ATSTError, pd.errors.ParserError, csv.Error, ValueError) as exc:
        raise UploadedTableParseError(f"Could not read {name}: {exc}") from exc
    except Exception as exc:
        raise UploadedTableParseError(
            f"Could not read {name}. Check that it is a valid table file."
        ) from exc


def read_uploaded_layout(uploaded_file) -> pd.DataFrame:
    """Read an uploaded layout table and normalize well labels."""

    name = getattr(uploaded_file, "name", "uploaded layout")
    return normalize_uploaded_layout(
        read_uploaded_table(uploaded_file, atst_block=LAYOUT),
        name=name,
    )


def normalize_uploaded_layout(df: pd.DataFrame, *, name: str) -> pd.DataFrame:
    """Normalize `well_loc` values and reject duplicate wells.

    Args:
        df: Uploaded layout table.
        name: Source filename used in error messages.
    """

    if "well_loc" not in df.columns:
        return df

    df = df.copy()
    df["well_loc"] = df["well_loc"].map(normalize_well_loc)

    well_values = df["well_loc"].astype(str)
    duplicate_wells = sorted(
        well_values[well_values.ne("") & well_values.duplicated()].unique()
    )
    if duplicate_wells:
        raise UploadedTableParseError(
            f"{name} has duplicate well_loc values after normalizing well labels: "
            f"{', '.join(duplicate_wells)}."
        )

    return df


MISSING_READING_VALUE = ""


def sort_readings_columns(
    df: pd.DataFrame,
    *,
    plate_format: str | None = None,
) -> pd.DataFrame:
    """Return READINGS with `Time` first and sorted well columns only."""

    if "Time" not in df.columns:
        return df

    time_columns = [column for column in df.columns if str(column).strip() == "Time"]
    if not time_columns:
        return df

    time_column = time_columns[0]
    remaining_columns = [column for column in df.columns if column != time_column]
    well_columns = []
    other_columns = []
    for column in remaining_columns:
        if is_well_column(column):
            well_columns.append(column)
        else:
            other_columns.append(column)

    if other_columns:
        raise ValueError(
            "READINGS contains non-well columns after Time: "
            f"{', '.join(str(column) for column in other_columns)}."
        )

    existing_wells = {normalize_well_loc(column) for column in well_columns}
    for well in plate_wells(plate_format):
        if well in existing_wells:
            continue

        df[well] = MISSING_READING_VALUE
        well_columns.append(well)
        existing_wells.add(well)

    return df[[time_column, *sorted(well_columns, key=well_sort_key)]]


def read_block_from_atst(raw: str, *, block_name: str, name: str) -> pd.DataFrame:
    """Read the first matching table block from ATST text."""

    try:
        blocks = parse_file(raw.splitlines())
    except ATSTError as exc:
        raise UploadedTableParseError(
            f"{name} is not a valid ATST file: {exc}"
        ) from exc

    base_dir = linked_file_base_dir(name)
    block = blocks.get(block_name)
    if block is None:
        raise UploadedTableParseError(f"{name} does not contain a {block_name} block.")

    try:
        parsed_block = parse_block(block, base_dir=base_dir)
    except ATSTError as exc:
        raise UploadedTableParseError(
            f"Could not parse the {block_name} block in {name}: {exc}"
        ) from exc

    if isinstance(parsed_block, WideTableBlock):
        if parsed_block.per_readout_data:
            _, first_readout = next(iter(parsed_block.per_readout_data.items()))
            return clean_uploaded_table(
                first_readout.data.copy(),
                name=f"{name} {block_name} readout",
            )

        return clean_uploaded_table(
            parsed_block.data.copy(),
            name=f"{name} {block_name} block",
        )

    raise UploadedTableParseError(f"{name} {block_name} block is not a table block.")


def read_linked_layout_table(
    layout_file: str,
    *,
    name: str,
    base_dir: Path | None,
) -> pd.DataFrame:
    """Read a layout table referenced by an ATST block link."""

    path = Path(layout_file)
    if not path.is_absolute() and base_dir is not None:
        path = base_dir / path

    try:
        raw = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise UploadedTableParseError(
            f"{name} points to layout file {layout_file!r}, but it could not be read: "
            f"{exc.strerror or exc}"
        ) from exc

    return read_delimited_table(raw, name=f"{name} layout_file {layout_file}")


def linked_file_base_dir(name: str) -> Path | None:
    """Return a base directory for linked files when the upload name has one."""

    path = Path(name)
    if path.parent == Path("."):
        return None

    return path.parent


def read_delimited_table(raw: str, *, name: str) -> pd.DataFrame:
    """Read CSV/TSV/TXT table text into a cleaned DataFrame."""

    text = raw.strip("\r\n")
    if not text.strip():
        raise UploadedTableParseError(f"{name} is empty.")

    sep = infer_uploaded_table_separator(text, name=name)

    header = [value.strip() for value in next(csv.reader(StringIO(text), delimiter=sep))]
    if len(header) != len(set(header)):
        raise UploadedTableParseError(f"{name} has duplicate column names.")
    try:
        df = pd.read_csv(
            StringIO(text),
            sep=sep,
            dtype=str,
            keep_default_na=False,
            na_filter=False,
        )
    except pd.errors.ParserError as exc:
        raise UploadedTableParseError(f"Could not parse {name}: {exc}") from exc

    return clean_uploaded_table(df, name=name)


def clean_uploaded_table(df: pd.DataFrame, *, name: str) -> pd.DataFrame:
    """Trim uploaded table cells and validate column names."""

    df = df.copy()
    df.columns = [str(column).strip() for column in df.columns]
    df = df.map(lambda value: str(value).strip())

    if any(not column for column in df.columns):
        raise UploadedTableParseError(f"{name} has one or more blank column names.")
    if len(df.columns) != len(set(df.columns)):
        duplicates = sorted(
            {col for col in df.columns if list(df.columns).count(col) > 1}
        )
        raise UploadedTableParseError(
            f"{name} has duplicate column names: {', '.join(duplicates)}."
        )

    return df


def infer_uploaded_table_separator(raw: str, *, name: str) -> str:
    """Infer a table delimiter, falling back to the filename suffix."""

    suffix = Path(name).suffix.lower()
    suffix_separators = {
        ".csv": ",",
        ".tsv": "\t",
        ".txt": "\t",
    }

    try:
        return csv.Sniffer().sniff(raw[:8192], delimiters=",\t;|").delimiter
    except csv.Error:
        return suffix_separators.get(suffix, "\t")
