from __future__ import annotations

import pandas as pd

from streamlit_app.generator.options import ASSAY_SELECT_OPTIONS
from streamlit_app.tables.utils import table_is_blank as is_blank_table


def field_table_to_dict(df: pd.DataFrame, *, block_name: str) -> dict[str, str]:
    """Convert a `field`/`value` editor table into a dictionary.

    Args:
        df: Streamlit editor table with `field` and `value` columns.
        block_name: ATST block name used in validation messages.
    """

    required = {"field", "value"}
    if not required.issubset(df.columns):
        raise ValueError(f"{block_name} table must contain field and value columns.")

    output: dict[str, str] = {}
    for _, row in df.iterrows():
        field = str(row.get("field", "")).strip()
        if not field:
            continue
        if field in output:
            raise ValueError(f"{block_name} has duplicate field {field!r}.")
        output[field] = str(row.get("value", "")).strip()

    return output


def editor_df(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with a simple row index for Streamlit editors."""

    return df.copy().reset_index(drop=True)


def normalize_assay_select_value(field: str, value: str) -> str:
    """Normalize assay selectbox values such as time units and plate format."""

    normalized = str(value).strip()
    if field == "readout_type":
        type_aliases = {
            "absorbance": "Absorbance",
            "fluorescence": "Fluorescence",
        }
        normalized = type_aliases.get(normalized.lower(), normalized)
    elif field == "readout_unit":
        unit_aliases = {
            "od": "OD",
            "od600": "OD",
            "absorbance": "OD",
            "rfu": "RFU",
            "gfp": "GFP",
        }
        normalized = unit_aliases.get(normalized.lower(), normalized)
    elif field == "plate_format":
        normalized = normalized.replace("-well", "_well")
    elif field == "time_unit":
        unit_aliases = {
            "s": "seconds",
            "sec": "seconds",
            "secs": "seconds",
            "second": "seconds",
            "seconds": "seconds",
            "m": "minutes",
            "min": "minutes",
            "mins": "minutes",
            "minute": "minutes",
            "minutes": "minutes",
            "h": "hours",
            "hr": "hours",
            "hrs": "hours",
            "hour": "hours",
            "hours": "hours",
        }
        normalized = unit_aliases.get(normalized.lower(), normalized)
    if normalized in ASSAY_SELECT_OPTIONS[field]:
        return normalized
    return ""


def combined_field_table(
    *,
    default_table: pd.DataFrame,
    extra_table: pd.DataFrame,
    default_rows: list[dict[str, str]],
) -> pd.DataFrame:
    """Combine fixed default fields with user-added extra fields."""

    default_fields = [row["field"] for row in default_rows]

    normalized_default_rows = []
    for index, field in enumerate(default_fields):
        value = default_rows[index].get("value", "")
        matching = default_table.loc[default_table["field"].astype(str) == field]
        if not matching.empty:
            value = str(matching.iloc[0].get("value", value))
        normalized_default_rows.append({"field": field, "value": value})

    normalized_extra_rows = []
    if {"field", "value"}.issubset(extra_table.columns):
        for _, row in extra_table.iterrows():
            field = str(row.get("field", "")).strip()
            if not field or field in default_fields:
                continue
            normalized_extra_rows.append(
                {"field": field, "value": str(row.get("value", ""))}
            )

    return pd.DataFrame([*normalized_default_rows, *normalized_extra_rows])


def split_field_data(
    data: dict[str, str],
    default_rows: list[dict[str, str]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split a block dictionary into default-field and extra-field tables."""

    default_fields = [row["field"] for row in default_rows]
    default_table = pd.DataFrame(
        [
            {
                "field": field,
                "value": str(data.get(field, row.get("value", ""))),
            }
            for field, row in zip(default_fields, default_rows)
        ]
    )
    extra_table = pd.DataFrame(
        [
            {"field": field, "value": str(value)}
            for field, value in data.items()
            if field not in default_fields
        ],
        columns=["field", "value"],
    )
    return default_table, extra_table


def merge_field_data(
    current_data: dict[str, str],
    incoming_data: dict[str, str],
    *,
    incoming_overwrites: bool,
) -> dict[str, str]:
    """Merge current and incoming block data.

    Args:
        current_data: Existing form state.
        incoming_data: Template or device data being loaded.
        incoming_overwrites: Whether non-blank incoming values replace current ones.
    """

    if incoming_overwrites:
        merged = current_data.copy()
        for field, value in incoming_data.items():
            value = str(value)
            if value.strip():
                merged[field] = value
        return merged

    merged = incoming_data.copy()
    for field, value in current_data.items():
        value = str(value)
        if value.strip() or field not in merged:
            merged[field] = value
    return merged


def selected_plate_format(assay_table: pd.DataFrame) -> str:
    """Read the normalized `plate_format` value from an assay field table."""

    if {"field", "value"}.issubset(assay_table.columns):
        matching = assay_table.loc[assay_table["field"].astype(str) == "plate_format"]
        if not matching.empty:
            return normalize_assay_select_value(
                "plate_format",
                str(matching.iloc[0].get("value", "")),
            )
    return ""
