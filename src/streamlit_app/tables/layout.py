from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from streamlit_app.tables.utils import (
    clean_table,
    normalize_well_loc,
    plate_wells,
    table_is_blank,
    well_sort_key,
)


LAYOUT_KEY_COLUMN = "well_loc"


def layout_conflict_columns(
    current: pd.DataFrame,
    incoming: pd.DataFrame,
    *,
    plate_format: str | None = None,
) -> list[str]:
    """Return incoming columns that would overwrite non-blank current values."""

    incoming = sort_layout_rows(incoming, plate_format=plate_format)
    if table_is_blank(current):
        return []

    return [
        column
        for column in incoming.columns
        if column != LAYOUT_KEY_COLUMN
        and column in current.columns
        and column_has_values(current, column)
    ]


def merge_layout_tables(
    current: pd.DataFrame,
    incoming: pd.DataFrame,
    *,
    replace_columns: Iterable[str] = (),
    plate_format: str | None = None,
) -> pd.DataFrame:
    """Merge incoming layout data without dropping existing layout columns."""

    current = clean_table(current)
    incoming = sort_layout_rows(incoming, plate_format=plate_format)

    if table_is_blank(current):
        return incoming.copy()
    if table_is_blank(incoming):
        return current.copy()

    replace_column_set = set(replace_columns)
    output = current.copy()
    for column in merged_column_order(current.columns, incoming.columns):
        if column not in output.columns:
            output[column] = ""

    for column in replace_column_set:
        if column != LAYOUT_KEY_COLUMN and column in incoming.columns:
            output[column] = ""

    if can_merge_by_well(current, incoming):
        output = merge_by_well(output, current, incoming, replace_column_set)
    else:
        output = merge_by_position(output, current, incoming, replace_column_set)

    ordered_columns = merged_column_order(current.columns, incoming.columns)
    return sort_layout_rows(
        output.loc[:, ordered_columns].fillna(""),
        plate_format=plate_format,
    )


def sort_layout_rows(
    df: pd.DataFrame,
    *,
    plate_format: str | None = None,
) -> pd.DataFrame:
    """Return layout rows ordered naturally by `well_loc` when present."""

    df = complete_layout_rows(df, plate_format=plate_format)
    if LAYOUT_KEY_COLUMN not in df.columns:
        return df

    return (
        df.sort_values(
            LAYOUT_KEY_COLUMN,
            key=lambda column: column.map(well_sort_key),
            kind="mergesort",
        )
        .reset_index(drop=True)
    )


def complete_layout_rows(
    df: pd.DataFrame,
    *,
    plate_format: str | None = None,
) -> pd.DataFrame:
    """Add missing plate wells before sorting a layout table."""

    df = clean_table(df)
    if LAYOUT_KEY_COLUMN not in df.columns:
        return df

    empty_rows = df.apply(
        lambda row: all(str(value).strip() == "" for value in row),
        axis=1,
    )
    df = df.loc[~empty_rows].copy()
    df[LAYOUT_KEY_COLUMN] = df[LAYOUT_KEY_COLUMN].map(normalize_well_loc)
    required_wells = plate_wells(plate_format)

    existing_wells = {
        normalize_well_loc(value)
        for value in df[LAYOUT_KEY_COLUMN]
        if str(value).strip()
    }
    missing_rows = []
    for well in required_wells:
        if well in existing_wells:
            continue

        row = {column: "" for column in df.columns}
        row[LAYOUT_KEY_COLUMN] = well
        missing_rows.append(row)

    if not missing_rows:
        return df

    return pd.concat([df, pd.DataFrame(missing_rows)], ignore_index=True)


def column_has_values(df: pd.DataFrame, column: str) -> bool:
    if column not in df.columns:
        return False

    return bool(
        df[column].fillna("").map(lambda value: str(value).strip()).ne("").any()
    )


def column_value_count(df: pd.DataFrame, column: str) -> int:
    if column not in df.columns:
        return 0

    return int(df[column].fillna("").map(lambda value: str(value).strip()).ne("").sum())


def can_merge_by_well(current: pd.DataFrame, incoming: pd.DataFrame) -> bool:
    return (
        LAYOUT_KEY_COLUMN in current.columns and LAYOUT_KEY_COLUMN in incoming.columns
    )


def merged_column_order(
    current_columns: Iterable[str],
    incoming_columns: Iterable[str],
) -> list[str]:
    columns: list[str] = []

    for column in [*current_columns, *incoming_columns]:
        column = str(column).strip()
        if column and column not in columns:
            columns.append(column)

    if LAYOUT_KEY_COLUMN in columns:
        columns.remove(LAYOUT_KEY_COLUMN)
        columns.insert(0, LAYOUT_KEY_COLUMN)

    return columns


def merge_by_well(
    output: pd.DataFrame,
    current: pd.DataFrame,
    incoming: pd.DataFrame,
    replace_columns: set[str],
) -> pd.DataFrame:
    current_well_index = {
        str(row[LAYOUT_KEY_COLUMN]).strip().upper(): index
        for index, row in output.iterrows()
        if str(row.get(LAYOUT_KEY_COLUMN, "")).strip()
    }

    for _, incoming_row in incoming.iterrows():
        well = str(incoming_row.get(LAYOUT_KEY_COLUMN, "")).strip().upper()
        if well and well in current_well_index:
            output_index = current_well_index[well]
        else:
            output_index = len(output)
            output.loc[output_index, :] = ""
            if well:
                output.at[output_index, LAYOUT_KEY_COLUMN] = well
                current_well_index[well] = output_index

        apply_incoming_row(
            output,
            current,
            incoming_row,
            output_index=int(output_index),  # type: ignore
            replace_columns=replace_columns,
        )

    return output


def merge_by_position(
    output: pd.DataFrame,
    current: pd.DataFrame,
    incoming: pd.DataFrame,
    replace_columns: set[str],
) -> pd.DataFrame:
    for incoming_index, (_, incoming_row) in enumerate(incoming.iterrows()):
        if incoming_index >= len(output):
            output.loc[incoming_index, :] = ""

        apply_incoming_row(
            output,
            current,
            incoming_row,
            output_index=incoming_index,
            replace_columns=replace_columns,
        )

    return output


def apply_incoming_row(
    output: pd.DataFrame,
    current: pd.DataFrame,
    incoming_row: pd.Series,
    *,
    output_index: int,
    replace_columns: set[str],
) -> None:
    for column, value in incoming_row.items():
        if column == LAYOUT_KEY_COLUMN and LAYOUT_KEY_COLUMN in current.columns:
            continue
        if should_apply_column(current, column, replace_columns):  # type: ignore
            output.at[output_index, column] = value


def should_apply_column(
    current: pd.DataFrame,
    column: str,
    replace_columns: set[str],
) -> bool:
    return (
        column not in current.columns
        or column in replace_columns
        or not column_has_values(current, column)
    )
