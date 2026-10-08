from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from ATST.blocks import LAYOUT
from ATST.blocks.base_classes import WideTableBlock
from ATST.errors import ATSTValidationError


LAYOUT_KEY_COLUMNS = ("well_loc", "curve_id")


@dataclass
class Layout(WideTableBlock):
    """Layout annotations keyed by `well_loc` or `curve_id`."""

    name: str = LAYOUT

    @classmethod
    def read_layout(cls, path: str | Path):
        """Read a CSV/TSV layout table and normalize common column names.

        Args:
            path: Path to a delimited layout table.
        """

        path = Path(path)
        separator = _infer_layout_table_separator(path)

        df = pd.read_csv(path, sep=separator, encoding="utf-8-sig")
        df = df.rename(columns={col: _canonical_column_name(col) for col in df.columns})

        return cls(data=df)


def layout_key_column(data: pd.DataFrame, *, context: str = LAYOUT) -> str:
    """Return the single identity column used by a layout table."""

    present = [column for column in LAYOUT_KEY_COLUMNS if column in data.columns]
    if len(present) != 1:
        choices = " or ".join(LAYOUT_KEY_COLUMNS)
        if present:
            raise ATSTValidationError(
                f"{context} must contain exactly one of {choices}, not both."
            )
        raise ATSTValidationError(
            f"{context} must contain exactly one of {choices}."
        )

    return present[0]


def layout_key_values(
    data: pd.DataFrame,
    *,
    context: str = LAYOUT,
) -> tuple[str, list[str]]:
    """Return and validate the identity column and its normalized values."""

    key_column = layout_key_column(data, context=context)
    values = [
        "" if pd.isna(value) else str(value).strip()
        for value in data[key_column]
    ]
    if any(value == "" for value in values):
        raise ATSTValidationError(
            f"{context}.{key_column} values must be non-empty."
        )

    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    if duplicates:
        raise ATSTValidationError(
            f"{context}.{key_column} values must be unique: "
            + ", ".join(sorted(duplicates))
        )

    return key_column, values


def _infer_layout_table_separator(path: Path) -> str:
    import csv

    suffix_separators = {
        ".csv": ",",
        ".tsv": "\t",
    }
    sample = path.read_text(encoding="utf-8-sig", errors="replace")[:8192]

    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
        return dialect.delimiter
    except csv.Error:
        return suffix_separators.get(path.suffix.lower(), ",")


def _canonical_column_name(value) -> str:
    import re

    canonical_columns = {
        "well": "well_loc",
        "phage": "phage_id",
        "isolate": "isolate_id",
        "moi_level": "moi",
    }
    text = str(value).strip().lower()
    text = re.sub(r"[^0-9a-z]+", "_", text).strip("_")
    return canonical_columns.get(text, text)
