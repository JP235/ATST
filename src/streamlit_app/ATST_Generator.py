from __future__ import annotations

from copy import deepcopy
from datetime import date
from io import StringIO
from pathlib import Path

import pandas as pd
import streamlit as st

from ATST.ATSTFile.ATST import ATSTFile, MultiReadoutATST, read_atst, write_file
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

from ATST.blocks.base_classes import LongTable, LongTableBlock
from streamlit_app.block_default_fields import (
    DEFAULT_ASSAY_ROWS,
    DEFAULT_DATA_ROWS,
    DEFAULT_LAYOUT_ROWS,
    DEFAULT_LAYOUT_SCHEMA_ROWS,
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


def _init_state() -> None:
    defaults = {
        "study_default_table": pd.DataFrame(DEFAULT_STUDY_ROWS),
        "study_extra_table": pd.DataFrame(columns=["field", "value"]),
        "metadata_default_table": pd.DataFrame(DEFAULT_METADATA_ROWS),
        "metadata_extra_table": pd.DataFrame(columns=["field", "value"]),
        "assay_default_table": pd.DataFrame(DEFAULT_ASSAY_ROWS),
        "assay_extra_table": pd.DataFrame(columns=["field", "value"]),
        "layout_table": pd.DataFrame(DEFAULT_LAYOUT_ROWS),
        "data_table": pd.DataFrame(DEFAULT_DATA_ROWS),
        "layout_schema_default_table": pd.DataFrame(DEFAULT_LAYOUT_SCHEMA_ROWS),
        "layout_schema_extra_table": pd.DataFrame(columns=["field", "value"]),
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
    st.session_state.data_table = pd.DataFrame()
    st.session_state.entity_tables = {
        table_name: entity_table.data.copy()
        for table_name, entity_table in atst.entities.tables.items()
    }

    type_definitions = {}
    if atst.layout_schema.type_definitions is not None:
        type_definitions = dict(atst.layout_schema.type_definitions.data)
    (
        st.session_state.layout_schema_default_table,
        st.session_state.layout_schema_extra_table,
    ) = _split_field_data(type_definitions, DEFAULT_LAYOUT_SCHEMA_ROWS)

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


def _layout_schema_from_table(df: pd.DataFrame) -> LayoutSchema:
    type_definitions = _field_table_to_dict(df, block_name="LAYOUT_SCHEMA")
    if not any(value.strip() for value in type_definitions.values()):
        return LayoutSchema()
    return LayoutSchema(
        type_definitions=LongTableBlock(
            name="TYPE_DEFINITIONS",
            data=type_definitions,
        )
    )


def main() -> None:
    st.set_page_config(page_title="ATST Generator", layout="wide")
    _init_state()

    st.title("ATST Generator")

    with st.expander("Load template", expanded=False):
        template_upload = st.file_uploader(
            "Drop an ATST template",
            type=["txt"],
            key="template_upload",
        )
        if template_upload is not None and st.button("Load template"):
            try:
                st.session_state.template_message = _load_template(template_upload)
            except Exception as exc:
                st.error(f"Could not load template: {exc}")
            else:
                st.rerun()
        if st.session_state.get("template_message"):
            st.success(st.session_state.template_message)

    file_name = st.text_input("File name", key="file_name")
    # human_readable = st.toggle("Human-readable table spacing", value=True)

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
        layout_upload = st.file_uploader(
            "Drop a LAYOUT CSV/TSV",
            type=["csv", "tsv", "txt"],
            key="layout_upload",
        )
        if layout_upload is not None and st.button("Load layout file"):
            st.session_state.layout_table = _read_uploaded_table(layout_upload)
            st.rerun()

        col_name = st.text_input("Add layout column", key="layout_new_column")
        if st.button("Add layout column"):
            col_name = col_name.strip()
            if not col_name:
                st.warning("Enter a column name first.")
            elif col_name in st.session_state.layout_table.columns:
                st.warning(f"Column {col_name!r} already exists.")
            else:
                st.session_state.layout_table[col_name] = ""
                st.rerun()

        if st.button("Remove layout table"):
            st.session_state.layout_table = pd.DataFrame(DEFAULT_LAYOUT_ROWS)
            st.rerun()

        st.session_state.layout_table = st.data_editor(
            _editor_df(st.session_state.layout_table),
            key="layout_editor",
            hide_index=True,
            num_rows="dynamic",
            width="stretch",
        )

    with st.expander("ENTITIES"):
        entity_uploads = st.file_uploader(
            "Drop entity table CSV/TSV files",
            type=["csv", "tsv", "txt"],
            accept_multiple_files=True,
            key="entity_uploads",
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
        layout_schema_default_table = _default_field_editor(
            state_key="layout_schema_default_table",
            editor_key="layout_schema_default_editor",
            default_rows=DEFAULT_LAYOUT_SCHEMA_ROWS,
        )
        layout_schema_extra_table = _extra_field_editor(
            state_key="layout_schema_extra_table",
            editor_key="layout_schema_extra_editor",
        )

    with st.expander("DATA", expanded=True):
        data_upload = st.file_uploader(
            "Drop a DATA CSV/TSV",
            type=["csv", "tsv", "txt"],
            key="data_upload",
        )
        if data_upload is not None and st.button("Load data file"):
            st.session_state.data_table = _read_uploaded_table(data_upload)
            st.rerun()

        if st.button("Remove data table"):
            st.session_state.data_table = pd.DataFrame()
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
                    st.session_state.layout_table,
                    block_name="LAYOUT",
                ),
                data_df=_prepare_wide_table(
                    st.session_state.data_table,
                    block_name="DATA",
                ),
                entities=_entities_from_tables(st.session_state.entity_tables),
                layout_schema=_layout_schema_from_table(
                    _combined_field_table(
                        default_table=layout_schema_default_table,
                        extra_table=layout_schema_extra_table,
                        default_rows=DEFAULT_LAYOUT_SCHEMA_ROWS,
                    )
                ),
            )

            output_path = Path("data_exporter") / path.name
            write_file(atst, output_path, human_readable=True)
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
