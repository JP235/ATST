from __future__ import annotations

from copy import deepcopy
from datetime import date
from html import escape
from io import StringIO
from pathlib import Path
import re

from ATST.ATSTFile.ATST import ATSTFile, MultiReadoutATST
from ATST.ATSTFile.read_files import read_atst
from ATST.ATSTFile.write_files import write_atst
import pandas as pd
import streamlit as st
from streamlit_tags import st_tags

from ATST.blocks import (
    Assay,
    Data,
    Entities,
    EntityTable,
    FileMetadata,
    Layout,
    LayoutSchema,
    Metadata,
    Study,
)

from ATST.blocks.base_classes import LongTableBlock, WideTableBlock
from streamlit_app.block_default_fields import (
    DEFAULT_ASSAY_ROWS,
    DEFAULT_DATA_ROWS,
    DEFAULT_LAYOUT_ROWS,
    DEFAULT_METADATA_ROWS,
    DEFAULT_STUDY_ROWS,
)

PLATE_FORMAT_OPTIONS = [
    "6_well",
    "12_well",
    "24_well",
    "48_well",
    "96_well",
    "384_well",
    "1536_well",
]
TIME_UNIT_OPTIONS = ["seconds", "minutes", "hours"]
ASSAY_SELECT_OPTIONS = {
    "time_unit": TIME_UNIT_OPTIONS,
    "plate_format": PLATE_FORMAT_OPTIONS,
}
ASSAY_SELECT_DEFAULTS = {
    "plate_format": "96_well",
}
INTEGER_RE = re.compile(r"^[+-]?\d+$")
CATEGORICAL_RE = re.compile(r"^CATEGORICAL\((.*)\)$", re.IGNORECASE)
WELL_LOC_RE = re.compile(r"^([A-Za-z]+)(\d+)$")
TAG_BACKGROUND_COLOR = "#eef9ef"
TAG_TEXT_COLOR = "#1f3b22"
TAG_BORDER_COLOR = "#cdeecd"
PLATE_FORMAT_DIMENSIONS = {
    "6_well": (["A", "B"], 3, 70),
    "12_well": (["A", "B", "C"], 4, 50),
    "24_well": ([chr(code) for code in range(ord("A"), ord("D") + 1)], 6, 50),
    "48_well": ([chr(code) for code in range(ord("A"), ord("F") + 1)], 8, 50),
    "96_well": ([chr(code) for code in range(ord("A"), ord("H") + 1)], 12, 45),
    "384_well": ([chr(code) for code in range(ord("A"), ord("P") + 1)], 24, 30),
    "1536_well": (
        [chr(code) for code in range(ord("A"), ord("Z") + 1)]
        + [f"A{chr(code)}" for code in range(ord("A"), ord("F") + 1)],
        48,
        20,
    ),
}
LAYOUT_TYPE_COLORS = [
    "#2f6fed",
    "#d64545",
    "#158f63",
    "#b45f06",
    "#7c4dff",
    "#008c95",
    "#c02f87",
    "#6b7f00",
    "#e07a22",
    "#4f6f52",
    "#84563c",
    "#5065a8",
    "#9b5cc6",
    "#3a8ca5",
    "#c44f63",
    "#6c6f7f",
]


def _init_state() -> None:
    defaults = {
        "study_default_table": pd.DataFrame(DEFAULT_STUDY_ROWS),
        "study_extra_table": pd.DataFrame(columns=["field", "value"]),
        "metadata_default_table": pd.DataFrame(DEFAULT_METADATA_ROWS),
        "metadata_extra_table": pd.DataFrame(columns=["field", "value"]),
        "assay_default_table": pd.DataFrame(DEFAULT_ASSAY_ROWS),
        "assay_extra_table": pd.DataFrame(columns=["field", "value"]),
        "layout_table": pd.DataFrame(DEFAULT_LAYOUT_ROWS),
        "layout_upload_version": 0,
        "layout_upload_loaded_token": None,
        "layout_upload_had_file": False,
        "layout_message": None,
        "data_table": pd.DataFrame(DEFAULT_DATA_ROWS),
        "layout_schema_table": pd.DataFrame(columns=["field", "value"]),
        "layout_schema_constraints_table": pd.DataFrame(
            columns=["type", "REQUIRED_COLUMNS", "OPTIONAL_COLUMNS"]
        ),
        "layout_schema_constraints_enabled": False,
        "layout_schema_inferred_values": {},
        "layout_schema_widget_version": 0,
        "entity_tables": {},
        "file_name": "new_assay.atst.txt",
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            try:
                st.session_state[key] = value.copy()
            except (TypeError, AttributeError):
                st.session_state[key] = deepcopy(value)


def _read_uploaded_table(uploaded_file) -> pd.DataFrame:
    suffix = Path(uploaded_file.name).suffix.lower()
    raw = uploaded_file.getvalue().decode("utf-8-sig")
    sep = "\t" if suffix in {".tsv", ".txt"} else ","
    return pd.read_csv(
        StringIO(raw),
        sep=sep,
        dtype=str,
        keep_default_na=False,
        na_filter=False,
    )


def _field_table_to_dict(df: pd.DataFrame, *, block_name: str) -> dict[str, str]:
    required = {"field", "value"}
    if not required.issubset(df.columns):
        raise ValueError(f"{block_name} table must contain field and value columns.")

    output: dict[str, str] = {}
    for idx, row in df.iterrows():
        field = str(row.get("field", "")).strip()
        if not field:
            continue
        if field in output:
            raise ValueError(f"{block_name} has duplicate field {field!r}.")
        output[field] = str(row.get("value", "")).strip()

    return output


def _editor_df(df: pd.DataFrame) -> pd.DataFrame:
    return df.copy().reset_index(drop=True)


def _clear_layout_schema_widget_state() -> None:
    st.session_state.layout_schema_widget_version = (
        st.session_state.get("layout_schema_widget_version", 0) + 1
    )
    for key in list(st.session_state):
        if str(key).startswith("layout_schema_editor"):
            del st.session_state[key]
        elif str(key).startswith("layout_schema_type_tags"):
            del st.session_state[key]
        elif str(key).startswith("layout_constraint_"):
            del st.session_state[key]


def _clear_layout_editor_widget_state() -> None:
    if "layout_editor" in st.session_state:
        del st.session_state.layout_editor


def _reset_layout_schema_state() -> None:
    st.session_state.layout_schema_table = pd.DataFrame(columns=["field", "value"])
    st.session_state.layout_schema_constraints_table = pd.DataFrame(
        columns=["type", "REQUIRED_COLUMNS", "OPTIONAL_COLUMNS"]
    )
    st.session_state.layout_schema_inferred_values = {}
    _clear_layout_schema_widget_state()


def _reset_layout_table() -> None:
    st.session_state.layout_table = pd.DataFrame(DEFAULT_LAYOUT_ROWS)
    st.session_state.layout_upload_version = (
        st.session_state.get("layout_upload_version", 0) + 1
    )
    st.session_state.layout_upload_loaded_token = None
    st.session_state.layout_upload_had_file = False
    st.session_state.layout_message = None
    _clear_layout_editor_widget_state()
    for key in list(st.session_state):
        if str(key).startswith("layout_upload_") and key not in {
            "layout_upload_version",
            "layout_upload_loaded_token",
            "layout_upload_had_file",
        }:
            del st.session_state[key]
    _reset_layout_schema_state()
    _reset_layout_schema_state()


def _uploaded_file_token(uploaded_file) -> tuple[str, int]:
    return (uploaded_file.name, len(uploaded_file.getvalue()))


def _default_field_editor(
    *,
    state_key: str,
    editor_key: str,
    default_rows: list[dict[str, str]],
) -> pd.DataFrame:
    default_fields = [row["field"] for row in default_rows]
    default_values = {row["field"]: row.get("value", "") for row in default_rows}
    current = st.session_state[state_key].copy()

    if not {"field", "value"}.issubset(current.columns):
        current = pd.DataFrame(default_rows)

    default_rows_for_editor = []
    for index, field in enumerate(default_fields):
        value = default_values[field]
        matching = current.loc[current["field"].astype(str) == field]
        if not matching.empty:
            value = str(matching.iloc[0].get("value", value))
        elif index < len(current):
            value = str(current.iloc[index].get("value", value))
        default_rows_for_editor.append({"field": field, "value": value})

    default_edited = st.data_editor(
        _editor_df(pd.DataFrame(default_rows_for_editor)),
        key=f"{editor_key}_default",
        hide_index=True,
        num_rows="fixed",
        width="stretch",
        disabled=["field"],
        column_config={
            "field": st.column_config.TextColumn("field"),
            "value": st.column_config.TextColumn("value"),
        },
    )

    normalized_rows = []
    for index, field in enumerate(default_fields):
        value = default_values[field]
        if index < len(default_edited):
            value = str(default_edited.iloc[index].get("value", value))
        normalized_rows.append({"field": field, "value": value})

    return pd.DataFrame(normalized_rows)


def _normalize_assay_select_value(field: str, value: str) -> str:
    normalized = str(value).strip()
    if field == "plate_format":
        normalized = normalized.replace("-well", "_well")
    elif field == "time_unit":
        normalized = normalized.replace("seconds", "s")
        normalized = normalized.replace("minutes", "min")
        normalized = normalized.replace("hours", "h")
    if normalized in ASSAY_SELECT_OPTIONS[field]:
        return normalized
    return ""


def _format_assay_select_value(value: str) -> str:
    return str(value).replace("_well", "-well")


def _assay_default_field_editor() -> pd.DataFrame:
    default_fields = [row["field"] for row in DEFAULT_ASSAY_ROWS]
    current = st.session_state.assay_default_table.copy()

    if not {"field", "value"}.issubset(current.columns):
        current = pd.DataFrame(DEFAULT_ASSAY_ROWS)

    values = {row["field"]: row.get("value", "") for row in DEFAULT_ASSAY_ROWS}
    for index, field in enumerate(default_fields):
        matching = current.loc[current["field"].astype(str) == field]
        if not matching.empty:
            values[field] = str(matching.iloc[0].get("value", values[field]))
        elif index < len(current):
            values[field] = str(current.iloc[index].get("value", values[field]))

    editable_rows = [
        {"field": field, "value": values[field]}
        for field in default_fields
        if field not in ASSAY_SELECT_OPTIONS
    ]
    edited = st.data_editor(
        _editor_df(pd.DataFrame(editable_rows)),
        key="assay_default_editor_default",
        hide_index=True,
        num_rows="fixed",
        width="stretch",
        disabled=["field"],
        column_config={
            "field": st.column_config.TextColumn("field"),
            "value": st.column_config.TextColumn("value"),
        },
    )

    normalized_rows = []
    for index, row in edited.iterrows():
        field = str(row.get("field", "")).strip()
        if not field:
            continue
        normalized_rows.append({"field": field, "value": str(row.get("value", ""))})

    row_values = {row["field"]: row["value"] for row in normalized_rows}
    for field, options in ASSAY_SELECT_OPTIONS.items():
        widget_key = f"assay_{field}"
        value = _normalize_assay_select_value(field, values.get(field, ""))
        if not value:
            value = ASSAY_SELECT_DEFAULTS.get(field, "")
        if (
            widget_key not in st.session_state
            or st.session_state[widget_key] not in options
        ):
            st.session_state[widget_key] = value

        selected_value = st.selectbox(
            field,
            options,
            index=(
                options.index(st.session_state[widget_key])
                if st.session_state[widget_key]
                else None
            ),
            format_func=_format_assay_select_value,
            placeholder=f"Select {field}",
            key=widget_key,
        )
        row_values[field] = selected_value or ""

    return pd.DataFrame(
        [
            {"field": field, "value": row_values.get(field, "")}
            for field in default_fields
        ]
    )


def _extra_field_editor(*, state_key: str, editor_key: str) -> pd.DataFrame:
    current = st.session_state[state_key].copy()
    if not {"field", "value"}.issubset(current.columns):
        current = pd.DataFrame(columns=["field", "value"])

    edited = st.data_editor(
        _editor_df(current),
        key=editor_key,
        hide_index=True,
        num_rows="dynamic",
        width="stretch",
        column_config={
            "field": st.column_config.TextColumn("extra field"),
            "value": st.column_config.TextColumn("value"),
        },
    )
    return edited


def _combined_field_table(
    *,
    default_table: pd.DataFrame,
    extra_table: pd.DataFrame,
    default_rows: list[dict[str, str]],
) -> pd.DataFrame:
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


def _split_field_data(
    data: dict[str, str],
    default_rows: list[dict[str, str]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
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


def _non_empty_values(series: pd.Series) -> list[str]:
    values = []
    for value in series.fillna(""):
        normalized = str(value).strip()
        if normalized:
            values.append(normalized)
    return values


def _unique_values(values: list[str]) -> list[str]:
    seen = set()
    output = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _join_csv(values: list[str]) -> str:
    return ", ".join(values)


def _safe_widget_key(value: str) -> str:
    normalized = re.sub(r"[^0-9A-Za-z_]+", "_", str(value).strip())
    return normalized.strip("_") or "blank"


def _strip_categorical(value: str) -> str:
    normalized = str(value).strip()
    match = CATEGORICAL_RE.match(normalized)
    if match:
        return match.group(1).strip()
    return normalized


def _categorical_definition(value: str) -> str:
    normalized = str(value).strip()
    if CATEGORICAL_RE.match(normalized):
        return normalized
    return f"CATEGORICAL({normalized})"


def _is_number(value: str) -> bool:
    try:
        float(value)
    except ValueError:
        return False
    return True


def _infer_layout_schema_type(series: pd.Series) -> str:
    values = _non_empty_values(series)
    if not values:
        return "string"
    if all(INTEGER_RE.fullmatch(value) for value in values):
        return "integer"
    if all(_is_number(value) for value in values):
        return "float"
    return "string"


def _schema_rows_from_layout(
    layout_df: pd.DataFrame,
) -> tuple[list[dict[str, str]], dict[str, str]]:
    df = layout_df.copy()
    df.columns = [str(column).strip() for column in df.columns]

    inferred_values: dict[str, str] = {"type": ""}
    if "type" in df.columns:
        inferred_values["type"] = _join_csv(
            _unique_values(_non_empty_values(df["type"]))
        )

    for column in df.columns:
        if column in {"well_loc", "type"}:
            continue
        inferred_values[column] = _infer_layout_schema_type(df[column])

    previous_inferred = st.session_state.get("layout_schema_inferred_values", {})
    current_values = _field_table_to_dict(
        st.session_state.layout_schema_table,
        block_name="LAYOUT_SCHEMA",
    )

    rows = []
    for field, inferred_value in inferred_values.items():
        current_value = current_values.get(field)
        previous_value = previous_inferred.get(field)
        if current_value is not None and current_value != previous_value:
            value = (
                _strip_categorical(current_value) if field == "type" else current_value
            )
        else:
            value = inferred_value
        rows.append({"field": field, "value": value})

    return rows, inferred_values


def _layout_schema_editor(layout_df: pd.DataFrame) -> pd.DataFrame:
    rows, inferred_values = _schema_rows_from_layout(layout_df)
    type_row = next((row for row in rows if row["field"] == "type"), None)
    type_values = _split_csv(type_row["value"] if type_row else "")
    type_suggestions = _split_csv(inferred_values.get("type", ""))
    widget_version = st.session_state.get("layout_schema_widget_version", 0)
    type_tags_key = f"layout_schema_type_tags_{widget_version}"
    previous_type_value = st.session_state.get(
        "layout_schema_inferred_values",
        {},
    ).get("type", "")
    current_type_tags = st.session_state.get(type_tags_key)
    current_type_tag_values = (
        _split_csv(current_type_tags)
        if isinstance(current_type_tags, str)
        else list(current_type_tags or [])
    )
    if current_type_tags is None:
        st.session_state[type_tags_key] = type_suggestions
        type_values = type_suggestions
    elif _join_csv(current_type_tag_values) == previous_type_value:
        st.session_state[type_tags_key] = type_suggestions
        type_values = type_suggestions

    edited_type_values = (
        st_tags(
            label="type",
            text="Add a layout type",
            value=type_values,
            suggestions=type_suggestions,
            key=type_tags_key,
        )
        or []
    )

    editable_rows = [row for row in rows if row["field"] != "type"]

    edited = st.data_editor(
        _editor_df(pd.DataFrame(editable_rows, columns=["field", "value"])),
        key=f"layout_schema_editor_{widget_version}",
        hide_index=True,
        num_rows="fixed",
        width="stretch",
        disabled=["field"],
        column_config={
            "field": st.column_config.TextColumn("layout column"),
            "value": st.column_config.TextColumn("schema type"),
        },
    )

    normalized = edited.fillna("")
    normalized["field"] = normalized["field"].map(lambda value: str(value).strip())
    normalized["value"] = normalized["value"].map(lambda value: str(value).strip())
    normalized = pd.DataFrame(
        [
            {"field": "type", "value": _join_csv(edited_type_values)},
            *normalized.to_dict(orient="records"),
        ],
        columns=["field", "value"],
    )
    st.session_state.layout_schema_table = normalized
    st.session_state.layout_schema_inferred_values = {
        **inferred_values,
        "type": _join_csv(_split_csv(inferred_values.get("type", ""))),
    }
    return normalized


def _constraint_rows(
    schema_df: pd.DataFrame,
) -> pd.DataFrame:
    schema_values = _field_table_to_dict(schema_df, block_name="LAYOUT_SCHEMA")
    type_values = _split_csv(_strip_categorical(schema_values.get("type", "")))
    schema_columns = [
        field for field in schema_values if field not in {"well_loc", "type"}
    ]

    current = st.session_state.layout_schema_constraints_table.copy()
    if not {"type", "REQUIRED_COLUMNS", "OPTIONAL_COLUMNS"}.issubset(current.columns):
        current = pd.DataFrame(columns=["type", "REQUIRED_COLUMNS", "OPTIONAL_COLUMNS"])

    current_by_type = {}
    for _, row in current.iterrows():
        type_value = str(row.get("type", "")).strip()
        if not type_value:
            continue
        current_by_type[type_value] = {
            "REQUIRED_COLUMNS": str(row.get("REQUIRED_COLUMNS", "")).strip(),
            "OPTIONAL_COLUMNS": str(row.get("OPTIONAL_COLUMNS", "")).strip(),
        }

    row_types = type_values or list(current_by_type)
    rows = []
    for type_value in row_types:
        required = _split_csv(
            current_by_type.get(type_value, {}).get("REQUIRED_COLUMNS", "")
        )
        optional = _split_csv(
            current_by_type.get(type_value, {}).get("OPTIONAL_COLUMNS", "")
        )
        excluded = [
            column
            for column in schema_columns
            if column not in set(required) | set(optional)
        ]
        rows.append(
            {
                "type": type_value,
                "REQUIRED_COLUMNS": _join_csv(required),
                "OPTIONAL_COLUMNS": _join_csv(optional),
                "EXCLUDED_COLUMNS": _join_csv(excluded),
            }
        )

    return pd.DataFrame(
        rows,
        columns=["type", "REQUIRED_COLUMNS", "OPTIONAL_COLUMNS", "EXCLUDED_COLUMNS"],
    )


def _layout_schema_constraints_editor(schema_df: pd.DataFrame) -> pd.DataFrame:
    enabled = st.checkbox(
        "Advanced config",
        value=False,
        key="layout_schema_constraints_enabled",
        disabled=True,
    )
    if not enabled:
        return pd.DataFrame(columns=["type", "REQUIRED_COLUMNS", "OPTIONAL_COLUMNS"])

    widget_version = st.session_state.get("layout_schema_widget_version", 0)
    schema_values = _field_table_to_dict(schema_df, block_name="LAYOUT_SCHEMA")
    schema_columns = [
        field for field in schema_values if field not in {"well_loc", "type"}
    ]
    current_rows = _constraint_rows(schema_df)

    header = st.columns([1, 2, 2, 2])
    header[0].markdown("**type**")
    header[1].markdown("**required**")
    header[2].markdown("**optional**")
    header[3].markdown("**excluded**")

    rows = []
    for _, row in current_rows.iterrows():
        type_value = str(row.get("type", "")).strip()
        if not type_value:
            continue

        key_part = _safe_widget_key(type_value)
        required_values = _split_csv(str(row.get("REQUIRED_COLUMNS", "")))
        optional_values = _split_csv(str(row.get("OPTIONAL_COLUMNS", "")))

        columns = st.columns([1, 2, 2, 2])
        columns[0].text_input(
            "type",
            value=type_value,
            disabled=True,
            key=f"layout_constraint_type_{widget_version}_{key_part}",
        )
        with columns[1]:
            required_values = (
                st_tags(
                    label="required",
                    text="Add a column",
                    value=required_values,
                    suggestions=schema_columns,
                    key=f"layout_constraint_required_{widget_version}_{key_part}",
                )
                or []
            )
        with columns[2]:
            optional_values = (
                st_tags(
                    label="optional",
                    text="Add a column",
                    value=optional_values,
                    suggestions=schema_columns,
                    key=f"layout_constraint_optional_{widget_version}_{key_part}",
                    # label_visibility="collapsed",
                )
                or []
            )

        columns[3].text_input(
            "excluded",
            value=_join_csv(
                list(
                    column
                    for column in schema_columns
                    if column not in set(required_values) | set(optional_values)
                )
            ),
            disabled=True,
            key=f"layout_constraint_excluded_{widget_version}_{key_part}",
            label_visibility="collapsed",
        )
        rows.append(
            {
                "type": type_value,
                "REQUIRED_COLUMNS": _join_csv(required_values),
                "OPTIONAL_COLUMNS": _join_csv(optional_values),
            }
        )

    output = pd.DataFrame(
        rows,
        columns=["type", "REQUIRED_COLUMNS", "OPTIONAL_COLUMNS"],
    )
    st.session_state.layout_schema_constraints_table = output
    return output


def _selected_plate_format(assay_table: pd.DataFrame) -> str:
    if {"field", "value"}.issubset(assay_table.columns):
        matching = assay_table.loc[assay_table["field"].astype(str) == "plate_format"]
        if not matching.empty:
            return _normalize_assay_select_value(
                "plate_format",
                str(matching.iloc[0].get("value", "")),
            )
    return ""


def _plate_dimensions_for_preview(
    layout_df: pd.DataFrame,
    plate_format: str,
) -> tuple[list[str], int, int]:
    if plate_format in PLATE_FORMAT_DIMENSIONS:
        return PLATE_FORMAT_DIMENSIONS[plate_format]

    rows = []
    columns = []
    if "well_loc" in layout_df.columns:
        for well_loc in layout_df["well_loc"].fillna(""):
            parsed = _parse_well_loc(well_loc)
            if parsed is None:
                continue
            row_label, column_number = parsed
            rows.append(row_label)
            columns.append(column_number)

    if not rows or not columns:
        return [], 0, 1

    return _unique_values(rows), max(columns), 24


def _parse_well_loc(value: object) -> tuple[str, int] | None:
    match = WELL_LOC_RE.fullmatch(str(value).strip())
    if match is None:
        return None
    return match.group(1).upper(), int(match.group(2))


def _layout_preview_groupby_options(layout_df: pd.DataFrame) -> list[str]:
    df = layout_df.copy()
    df.columns = [str(column).strip() for column in df.columns]
    return [column for column in df.columns if column != "well_loc"]


def _default_layout_groupby_column(options: list[str]) -> str:
    if "type" in options:
        return "type"
    return options[0] if options else ""


def _value_color_map(layout_df: pd.DataFrame, groupby_column: str) -> dict[str, str]:
    if groupby_column not in layout_df.columns:
        return {}
    values = _unique_values(_non_empty_values(layout_df[groupby_column]))
    return {
        value: LAYOUT_TYPE_COLORS[index % len(LAYOUT_TYPE_COLORS)]
        for index, value in enumerate(values)
    }


def _layout_preview_html(
    layout_df: pd.DataFrame,
    assay_table: pd.DataFrame,
    groupby_column: str,
) -> str | None:
    df = layout_df.copy().fillna("")
    df.columns = [str(column).strip() for column in df.columns]
    if "well_loc" not in df.columns or groupby_column not in df.columns:
        return None

    value_colors = _value_color_map(df, groupby_column)
    plate_format = _selected_plate_format(assay_table)
    row_labels, column_count, cell_size = _plate_dimensions_for_preview(
        df, plate_format
    )
    if not row_labels or column_count == 0:
        return None

    wells_by_location = {}
    for _, row in df.iterrows():
        parsed = _parse_well_loc(row.get("well_loc", ""))
        if parsed is None:
            continue
        row_label, column_number = parsed
        wells_by_location[(row_label, column_number)] = str(
            row.get(groupby_column, "")
        ).strip()

    header_cells = "".join(
        f'<th class="layout-preview-column">{column_number}</th>'
        for column_number in range(1, column_count + 1)
    )
    body_rows = []
    has_blank_wells = False
    for row_label in row_labels:
        cells = []
        for column_number in range(1, column_count + 1):
            well_loc = f"{row_label}{column_number}"
            group_value = wells_by_location.get((row_label, column_number), "")
            if not group_value:
                has_blank_wells = True
            color = value_colors.get(group_value, "#d9dde3")
            title = (
                f"{well_loc} {groupby_column}: {group_value}"
                if group_value
                else f"{well_loc} {groupby_column}: blank"
            )
            cells.append(
                "<td>"
                f'<span class="layout-preview-dot" '
                f'style="background-color: {color};" '
                f'title="{escape(title)}"></span>'
                "</td>"
            )
        body_rows.append(
            "<tr>"
            f'<th class="layout-preview-row">{escape(row_label)}</th>'
            + "".join(cells)
            + "</tr>"
        )

    legend_items = []
    for group_value, color in value_colors.items():
        legend_items.append(
            '<span class="layout-preview-legend-item">'
            f'<span class="layout-preview-dot" style="background-color: {color};">'
            "</span>"
            f"<span>{escape(group_value)}</span>"
            "</span>"
        )
    print(len(row_labels), plate_format)
    # if has_blank_wells:
    #     legend_items.append(
    #         '<span class="layout-preview-legend-item">'
    #         '<span class="layout-preview-dot" '
    #         'style="background-color: #d9dde3;"></span>'
    #         "<span>blank</span>"
    #         "</span>"
    #     )
    legend_html = (
        '<div class="layout-preview-legend">' + "".join(legend_items) + "</div>"
        if legend_items
        else ""
    )

    return f"""
<style>
.layout-preview-wrap {{
    --layout-preview-cell-size: {cell_size}px;
    margin-block-end: 1rem;
    display: flex;
    gap: 1rem;
    overflow-x: auto;
    background: #ffffff;
    height: calc(var(--layout-preview-cell-size, 24px) * {1.1 + len(row_labels)});
}}
.layout-preview-table {{
    border-collapse: collapse;
    table-layout: fixed;
    width: max-content;
    margin: 0 !important;
}}
.layout-preview-table th,
.layout-preview-table td {{
    width: var(--layout-preview-cell-size, 24px);
    height: var(--layout-preview-cell-size, 24px);
    min-width: var(--layout-preview-cell-size, 24px);
    text-align: center;
    padding: 0px;
}}
.layout-preview-table td {{
    font-size: 0px;
}}
.layout-preview-table th {{
    color: #4b5563;
    font-size: 13px;
    font-weight: 600;
}}
.layout-preview-row {{
    position: sticky;
    left: 0;
    z-index: 1;
    background: #ffffff;
}}
.layout-preview-dot {{
    display: inline-block;
    width:  calc(var(--layout-preview-cell-size, 24px) / 1.7);
    height: calc(var(--layout-preview-cell-size, 24px) / 1.7);
    border: 1px solid rgba(31, 41, 55, 0.25);
    border-radius: 50%;
    box-sizing: border-box;
    vertical-align: middle;
}}
.layout-preview-legend {{
    display: flex;
    flex-direction: column;
    flex-wrap: wrap;
    gap: 8px 14px;
    color: #374151;
    font-size: 12px;
    
}}
.layout-preview-legend-item {{
    display: inline-flex;
    align-items: center;
    gap: 5px;
    max-width: 180px;
}}
</style>
<div class="layout-preview-wrap">
    <table class="layout-preview-table">
        <thead><tr><th></th>{header_cells}</tr></thead>
        <tbody>{"".join(body_rows)}</tbody>
    </table>
    {legend_html}
</div>
"""


def _layout_preview(layout_df: pd.DataFrame, assay_table: pd.DataFrame) -> None:
    if layout_df is None or assay_table is None:
        return
    
    groupby_options = _layout_preview_groupby_options(layout_df)
    if not groupby_options:
        # st.caption("Add a layout column other than well_loc to preview groups.")
        return

    groupby_key = "layout_preview_groupby"
    if st.session_state.get(groupby_key) not in groupby_options:
        st.session_state[groupby_key] = _default_layout_groupby_column(groupby_options)

    with st.container(border=True):
        st.markdown("**Plate preview**")
        with st.container(horizontal=True, vertical_alignment="center"):
            st.markdown("*Group by:*")

            groupby_column = st.selectbox(
                "Plate preview",
                groupby_options,
                key=groupby_key,
                width=120,
                label_visibility="collapsed",
            )

        preview_html = _layout_preview_html(layout_df, assay_table, groupby_column)
        if preview_html is None:
            # st.caption(
            #     "Add valid well_loc values and select a plate_format to preview."
            # )
            return None
        st.markdown(preview_html, unsafe_allow_html=True)


def _load_template(uploaded_file) -> str:
    cache_dir = Path("data_exporter") / "_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    template_path = cache_dir / "_uploaded_template.atst.txt"
    template_path.write_bytes(uploaded_file.getvalue())

    loaded = read_atst(template_path)
    if isinstance(loaded, MultiReadoutATST):
        readout_id = next(iter(loaded.readouts))
        atst = loaded.readouts[readout_id]
        message = f"Loaded first readout from multi-readout template: {readout_id}"
    else:
        atst = loaded
        message = "Loaded template."

    st.session_state.file_name = str(
        atst.file_info.data.get("file_name") or uploaded_file.name
    )
    (
        st.session_state.study_default_table,
        st.session_state.study_extra_table,
    ) = _split_field_data(atst.study.data, DEFAULT_STUDY_ROWS)
    (
        st.session_state.metadata_default_table,
        st.session_state.metadata_extra_table,
    ) = _split_field_data(atst.metadata.data, DEFAULT_METADATA_ROWS)
    (
        st.session_state.assay_default_table,
        st.session_state.assay_extra_table,
    ) = _split_field_data(atst.assay.data, DEFAULT_ASSAY_ROWS)
    st.session_state.assay_time_unit = _normalize_assay_select_value(
        "time_unit",
        str(atst.assay.data.get("time_unit", "")),
    )
    st.session_state.assay_plate_format = _normalize_assay_select_value(
        "plate_format",
        str(atst.assay.data.get("plate_format", "")),
    )

    st.session_state.layout_table = atst.layout.data.copy()
    _clear_layout_editor_widget_state()
    st.session_state.data_table = pd.DataFrame()
    st.session_state.entity_tables = {
        table_name: entity_table.data.copy()
        for table_name, entity_table in atst.entities.tables.items()
    }

    type_definition_rows = []
    if atst.layout_schema.type_definitions is not None:
        for field, value in atst.layout_schema.type_definitions.data.items():
            if field == "well_loc":
                continue
            display_value = _strip_categorical(value) if field == "type" else value
            type_definition_rows.append({"field": field, "value": display_value})

    st.session_state.layout_schema_table = pd.DataFrame(
        type_definition_rows,
        columns=["field", "value"],
    )
    st.session_state.layout_schema_inferred_values = {}
    _clear_layout_schema_widget_state()

    if atst.layout_schema.type_constraints is not None:
        st.session_state.layout_schema_constraints_table = (
            atst.layout_schema.type_constraints.data.copy()
        )
        st.session_state.layout_schema_constraints_enabled = True
    else:
        st.session_state.layout_schema_constraints_table = pd.DataFrame(
            columns=["type", "REQUIRED_COLUMNS", "OPTIONAL_COLUMNS"]
        )
        st.session_state.layout_schema_constraints_enabled = False

    return message


def _prepare_wide_table(df: pd.DataFrame, *, block_name: str) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(column).strip() for column in df.columns]
    df = df.fillna("")
    df = df.map(lambda value: "" if pd.isna(value) else str(value).strip())

    empty_rows = df.apply(
        lambda row: all(str(value).strip() == "" for value in row), axis=1
    )
    df = df.loc[~empty_rows].copy()

    if df.empty:
        raise ValueError(f"{block_name} table is empty.")

    return df


def _download_bytes(text: str) -> bytes:
    return text.encode("utf-8")


def _dataframe_download_bytes(df: pd.DataFrame, *, sep: str = "\t") -> bytes:
    return df.to_csv(index=False, sep=sep).encode("utf-8")


def _layout_download_file_name(file_name: str) -> str:
    name = Path(file_name).name
    for suffix in (".atst.txt", ".txt", ".tsv", ".csv"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    return f"{name or 'layout'}_layout.tsv"


def _make_atst(
    *,
    file_name: str,
    study_data: dict[str, str],
    metadata_data: dict[str, str],
    assay_data: dict[str, str],
    layout_df: pd.DataFrame,
    data_df: pd.DataFrame,
    entities: Entities,
    layout_schema: LayoutSchema,
) -> ATSTFile:
    return ATSTFile(
        file_info=FileMetadata(
            data={
                "file_name": file_name,
                "format": "ATST",
                "format_version": "0.1",
                "created_on": date.today().isoformat(),
                "field_delimiter": "TAB",
                "encoding": "UTF-8",
            },
        ),
        study=Study(data=study_data),
        metadata=Metadata(data=metadata_data),
        assay=Assay(data=assay_data),
        layout=Layout(data=layout_df),
        data=Data(data=data_df),
        entities=entities,
        layout_schema=layout_schema,
        readout_manifest=None,
    )


def _entities_from_tables(tables: dict[str, pd.DataFrame]) -> Entities:
    entity_tables = {}
    for table_name, table_data in tables.items():
        df = _prepare_wide_table(table_data, block_name=f"ENTITIES.{table_name}")
        if len(df.columns) == 0:
            continue
        pk = str(df.columns[0])
        entity_tables[table_name] = EntityTable(
            name="ENTITIES",
            table_name=table_name,
            pk=pk,
            data=df,
        )
    return Entities(tables=entity_tables)


def _validate_constraint_columns(
    constraints_df: pd.DataFrame,
    schema_fields: set[str],
) -> None:
    for _, row in constraints_df.iterrows():
        type_value = str(row.get("type", "")).strip()
        required = set(_split_csv(str(row.get("REQUIRED_COLUMNS", ""))))
        optional = set(_split_csv(str(row.get("OPTIONAL_COLUMNS", ""))))
        unknown = (required | optional) - schema_fields
        overlap = required & optional
        if unknown:
            raise ValueError(
                f"TYPE_CONSTRAINTS row {type_value!r} references unknown columns: "
                f"{_join_csv(sorted(unknown))}."
            )
        if overlap:
            raise ValueError(
                f"TYPE_CONSTRAINTS row {type_value!r} lists columns as both "
                f"required and optional: {_join_csv(sorted(overlap))}."
            )


def _layout_schema_from_tables(
    schema_df: pd.DataFrame,
    constraints_df: pd.DataFrame,
) -> LayoutSchema:
    raw_type_definitions = _field_table_to_dict(schema_df, block_name="LAYOUT_SCHEMA")
    type_value = _strip_categorical(raw_type_definitions.get("type", ""))
    non_reserved_definitions = {
        field: value
        for field, value in raw_type_definitions.items()
        if field not in {"well_loc", "type"} and value.strip()
    }

    if not type_value and not non_reserved_definitions:
        return LayoutSchema()

    type_definitions = {
        "well_loc": "string",
        "type": _categorical_definition(type_value),
        **non_reserved_definitions,
    }

    constraints = None
    if not constraints_df.empty:
        normalized_constraints = constraints_df.copy().fillna("")
        normalized_constraints = normalized_constraints.map(
            lambda value: str(value).strip()
        )
        normalized_constraints = normalized_constraints.loc[
            normalized_constraints["type"].astype(str).str.strip() != ""
        ].copy()
        if not normalized_constraints.empty:
            schema_fields = set(non_reserved_definitions)
            _validate_constraint_columns(normalized_constraints, schema_fields)
            constraints = WideTableBlock(
                name="TYPE_CONSTRAINTS",
                data=normalized_constraints[
                    ["type", "REQUIRED_COLUMNS", "OPTIONAL_COLUMNS"]
                ],
            )

    return LayoutSchema(
        type_definitions=LongTableBlock(
            name="TYPE_DEFINITIONS",
            data=type_definitions,
        ),
        type_constraints=constraints,
    )


def template_upload_callback():
    st.session_state.template_message = None


def layout_upload_callback(upload_key: str):
    layout_upload = st.session_state.get(upload_key)
    if layout_upload is None:
        if st.session_state.get("layout_upload_had_file"):
            _reset_layout_table()
        return

    st.session_state.layout_upload_had_file = True
    st.session_state.layout_message = None


def data_upload_callback():
    if st.session_state.get("data_message") is not None:
        st.session_state.data_table = pd.DataFrame()
        # st.rerun()
    st.session_state.data_message = None


def main() -> None:
    # st.set_page_config(page_title="ATST Generator", layout="wide")
    st.html(
        """
    <style>
        .stMainBlockContainer {
            max-width: min(70rem, 1200px, 90%);
            margin: auto;
        }
    </style>
    """
    )

    _init_state()

    col1, col2 = st.columns([4, 1], vertical_alignment="bottom")
    with col1:
        st.title("ATST Generator")

    with col2:
        st.link_button(
            "ATST Generator GitHub",
            "https://github.com/JP235/ATST/",
            use_container_width=True,
        )

    with st.expander("Load template", expanded=False):
        template_upload = st.file_uploader(
            "Drop ATST template",
            type=["txt"],
            key="template_upload",
            on_change=template_upload_callback,
        )
        if (
            template_upload is not None
            and st.session_state.get("template_message") is None
        ):
            try:
                st.session_state.template_message = _load_template(template_upload)
            except Exception as exc:
                st.error(f"Could not load template: {exc}")
            else:
                st.rerun()
        if st.session_state.get("template_message"):
            st.success(st.session_state.template_message)

    file_name = st.text_input("File name", key="file_name")

    with st.expander("STUDY", expanded=True):
        study_default_table = _default_field_editor(
            state_key="study_default_table",
            editor_key="study_default_editor",
            default_rows=DEFAULT_STUDY_ROWS,
        )
        study_extra_table = _extra_field_editor(
            state_key="study_extra_table",
            editor_key="study_extra_editor",
        )

    with st.expander("METADATA", expanded=True):
        metadata_default_table = _default_field_editor(
            state_key="metadata_default_table",
            editor_key="metadata_default_editor",
            default_rows=DEFAULT_METADATA_ROWS,
        )
        metadata_extra_table = _extra_field_editor(
            state_key="metadata_extra_table",
            editor_key="metadata_extra_editor",
        )

    with st.expander("ASSAY", expanded=True):
        assay_default_table = _assay_default_field_editor()
        assay_extra_table = _extra_field_editor(
            state_key="assay_extra_table",
            editor_key="assay_extra_editor",
        )

    with st.expander("LAYOUT", expanded=True):
        layout_upload_key = (
            f"layout_upload_{st.session_state.get('layout_upload_version', 0)}"
        )
        layout_upload = st.file_uploader(
            "Drop CSV/TSV/TXT",
            type=["csv", "tsv", "txt"],
            key=layout_upload_key,
            on_change=layout_upload_callback,
            args=(layout_upload_key,),
            label_visibility="collapsed",
        )
        if layout_upload is not None:
            layout_upload_token = _uploaded_file_token(layout_upload)
        else:
            layout_upload_token = None

        if (
            layout_upload is not None
            and layout_upload_token != st.session_state.layout_upload_loaded_token
        ):
            st.session_state.layout_table = _read_uploaded_table(layout_upload)
            st.session_state.layout_upload_loaded_token = layout_upload_token
            st.session_state.layout_upload_had_file = True
            _clear_layout_editor_widget_state()
            _reset_layout_schema_state()
            st.session_state.layout_message = "Loaded layout."
            st.rerun()

        
        addcol_l, addcol_r = st.columns([4, 1], vertical_alignment="bottom")
        with addcol_l:
            col_name = st.text_input("Add layout column", key="layout_new_column")
        with addcol_r:
            if st.button("Add to layout", use_container_width=True):
                col_name = col_name.strip()
                if not col_name:
                    st.warning("Enter a column name first.")
                elif col_name in st.session_state.layout_table.columns:
                    st.warning(f"Column {col_name!r} already exists.")
                else:
                    st.session_state.layout_table[col_name] = ""
                    _clear_layout_editor_widget_state()
                    st.rerun()

        layout_preview_slot = st.empty()

        current_layout_table = st.data_editor(
            _editor_df(st.session_state.layout_table),
            key="layout_editor",
            hide_index=True,
            num_rows="dynamic",
            width="stretch",
        ).fillna("")
        # st.session_state.layout_table = current_layout_table

        with layout_preview_slot.container():
            _layout_preview(current_layout_table, assay_default_table)

        st.download_button(
            "Download layout",
            data=_dataframe_download_bytes(current_layout_table),
            file_name=_layout_download_file_name(file_name),
            mime="text/tab-separated-values",
            use_container_width=True,
        )
        

    with st.expander("ENTITIES"):
        entity_uploads = st.file_uploader(
            "Drop CSV/TSV/TXT files",
            type=["csv", "tsv", "txt"],
            accept_multiple_files=True,
            key="entity_uploads",
            label_visibility="collapsed",
        )
        if entity_uploads and st.button("Load entity files"):
            for uploaded_file in entity_uploads:
                table_name = Path(uploaded_file.name).stem
                st.session_state.entity_tables[table_name] = _read_uploaded_table(
                    uploaded_file
                )
            st.rerun()

        if st.session_state.entity_tables:
            if st.button("Remove all entity tables"):
                st.session_state.entity_tables = {}
                st.rerun()
            for table_name, table_df in list(st.session_state.entity_tables.items()):
                st.markdown(f"**{table_name}**")
                if st.button(f"Remove {table_name}", key=f"remove_entity_{table_name}"):
                    del st.session_state.entity_tables[table_name]
                    st.rerun()
                st.session_state.entity_tables[table_name] = st.data_editor(
                    _editor_df(table_df),
                    key=f"entity_editor_{table_name}",
                    hide_index=True,
                    num_rows="dynamic",
                    width="stretch",
                )
        # else:
        #     st.caption("No entity tables uploaded.")

    with st.expander("LAYOUT_SCHEMA"):
        layout_schema_table = _layout_schema_editor(current_layout_table)
        layout_schema_constraints_table = _layout_schema_constraints_editor(
            layout_schema_table
        )

    with st.expander("DATA", expanded=True):
        data_upload = st.file_uploader(
            "Drop CSV/TSV/TXT",
            type=["csv", "tsv", "txt"],
            key="data_upload",
            on_change=data_upload_callback,
            label_visibility="collapsed",
        )
        if data_upload is not None and st.session_state.get("data_message") is None:
            st.session_state.data_table = _read_uploaded_table(data_upload)
            st.session_state.data_message = "Loaded data."
            st.rerun()

        if not st.session_state.data_table.empty:
            st.dataframe(
                st.session_state.data_table,
                hide_index=True,
                width="stretch",
            )

    if st.button("Generate", type="primary"):
        try:
            path = Path(file_name)

            atst = _make_atst(
                file_name=path.with_suffix(".atst.txt").name,
                study_data=_field_table_to_dict(
                    _combined_field_table(
                        default_table=study_default_table,
                        extra_table=study_extra_table,
                        default_rows=DEFAULT_STUDY_ROWS,
                    ),
                    block_name="STUDY",
                ),
                metadata_data=_field_table_to_dict(
                    _combined_field_table(
                        default_table=metadata_default_table,
                        extra_table=metadata_extra_table,
                        default_rows=DEFAULT_METADATA_ROWS,
                    ),
                    block_name="METADATA",
                ),
                assay_data=_field_table_to_dict(
                    _combined_field_table(
                        default_table=assay_default_table,
                        extra_table=assay_extra_table,
                        default_rows=DEFAULT_ASSAY_ROWS,
                    ),
                    block_name="ASSAY",
                ),
                layout_df=_prepare_wide_table(
                    current_layout_table,
                    block_name="LAYOUT",
                ),
                data_df=_prepare_wide_table(
                    st.session_state.data_table,
                    block_name="DATA",
                ),
                entities=_entities_from_tables(st.session_state.entity_tables),
                layout_schema=_layout_schema_from_tables(
                    layout_schema_table,
                    layout_schema_constraints_table,
                ),
            )

            output_path = Path("data_exporter") / path.name
            write_atst(atst, output_path, human_readable=True)
            text = output_path.read_text(encoding="utf-8")

        except Exception as exc:
            st.error(f"Could not generate ATST file: {exc}")
            return

        st.success(f"Wrote {output_path}")
        st.download_button(
            "Download ATST",
            data=_download_bytes(text),
            file_name=path.name,
            mime="text/plain",
        )
        st.code(text, language="text")


if __name__ == "__main__":
    main()
