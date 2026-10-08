from __future__ import annotations

import re

import pandas as pd


WELL_LOC_RE = re.compile(r"^([A-Z]+)0*([0-9]+)$")

PLATE_DIMENSIONS: dict[str, tuple[list[str], int]] = {
    "6_well": (["A", "B"], 3),
    "12_well": (["A", "B", "C"], 4),
    "24_well": (["A", "B", "C", "D"], 6),
    "48_well": (["A", "B", "C", "D", "E", "F"], 8),
    "96_well": (["A", "B", "C", "D", "E", "F", "G", "H"], 12),
    "384_well": ([chr(ord("A") + index) for index in range(16)], 24),
    "1536_well": (
        [chr(ord("A") + index) for index in range(26)]
        + ["AA", "AB", "AC", "AD", "AE", "AF"],
        48,
    ),
}

PLATE_FORMAT_OPTIONS = list(PLATE_DIMENSIONS)


def clean_table(df: pd.DataFrame) -> pd.DataFrame:
    clean = df.copy().fillna("")
    clean.columns = [str(column).strip() for column in clean.columns]
    return clean.map(lambda value: str(value).strip())


def table_is_blank(df: pd.DataFrame) -> bool:
    """Return true when a table is empty or all cells are blank."""

    if df.empty:
        return True

    return bool(clean_table(df).isin([""]).all().all())


def plate_wells(plate_format: str | None) -> list[str]:
    rows, column_count = PLATE_DIMENSIONS.get(
        str(plate_format or "96_well"),
        PLATE_DIMENSIONS["96_well"],
    )
    return [f"{row}{column}" for row in rows for column in range(1, column_count + 1)]


def normalize_well_loc(value) -> str:
    """Normalize well labels such as `a01` to `A1`."""

    text = str(value).strip().upper()
    match = WELL_LOC_RE.fullmatch(text)
    if match is None:
        return text

    row, column = match.groups()
    return f"{row}{int(column)}"


def is_well_column(value) -> bool:
    return WELL_LOC_RE.fullmatch(str(value).strip().upper()) is not None


def well_sort_key(value) -> tuple[int, int, str]:
    text = str(value).strip().upper()
    match = WELL_LOC_RE.fullmatch(text)
    if match is None:
        return (10**9, 10**9, text)

    row, column = match.groups()
    row_number = 0
    for letter in row:
        row_number = row_number * 26 + ord(letter) - ord("A") + 1
    return (row_number, int(column), text)
