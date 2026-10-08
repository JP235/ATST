from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd
import streamlit as st

from ATST import (
    ATSTFile,
    MultiReadoutATST,
    write_atst,
    write_linked_atst_bundle,
    write_multi_readout_atst,
)
from ATST.errors import ATSTValidationError
from streamlit_app.components.layout_preview_editor import (
    layout_preview_editor,
    layout_preview_editor_mode,
    reset_layout_preview_editor_locks_on_page_change,
)
from ATST.device_readers import (
    DEVICE_READERS,
    ClariostarParseError,
    LogPhaseParseError,
    TecanParseError,
)
from streamlit_app.generator.builder import (
    entities_from_tables,
    make_atst,
    make_multi_readout_atst,
    normalize_atst_file_name,
    prepare_wide_table,
)
from streamlit_app.generator.defaults import (
    DEFAULT_ASSAY_ROWS,
    DEFAULT_METADATA_ROWS,
    DEFAULT_STUDY_ROWS,
)
from streamlit_app.generator.fields import (
    combined_field_table,
    editor_df,
    field_table_to_dict,
    normalize_assay_select_value,
    selected_plate_format,
    split_field_data,
)
from streamlit_app.generator.inspector import read_uploaded_atst
from streamlit_app.generator.options import (
    ASSAY_SELECT_DEFAULTS,
    ASSAY_SELECT_OPTIONS,
)
from streamlit_app.generator.plotting import plot_readings_by_layout
from streamlit_app.generator.readouts import copy_shared_block, ordered_readouts
from streamlit_app.generator.state import (
    cancel_layout_merge,
    init_state,
    load_device_outputs,
    load_template,
    next_layout_merge_conflict,
    resolve_layout_merge_conflict,
    stage_layout_merge,
)
from streamlit_app.privacy import (
    expire_upload_widget,
    upload_widget_key,
)
from streamlit_app.tables.layout import column_value_count, sort_layout_rows
from streamlit_app.tables.uploads import (
    UploadedTableParseError,
    read_uploaded_layout,
    read_uploaded_table,
    sort_readings_columns,
)
from streamlit_app.tables.utils import PLATE_FORMAT_OPTIONS

_STYLE_PATH = Path(__file__).parent / "style" / "generator.css"


def _section_container(label: str):
    """Create an always-open panel styled like an expanded expander."""

    key = f"atst_section_{label.lower().replace(' ', '_')}"
    container = st.container(border=True, key=key)
    container.html(f'<div class="atst-section-title">{label}</div>')
    return container


def _default_field_editor(
    *,
    state_key: str,
    editor_key: str,
    default_rows: list[dict[str, str]],
    disabled: bool = False,
    current_table: pd.DataFrame | None = None,
) -> pd.DataFrame:
    default_fields = [row["field"] for row in default_rows]
    default_values = {row["field"]: row.get("value", "") for row in default_rows}
    current = (
        current_table.copy()
        if current_table is not None
        else st.session_state[state_key].copy()
    )

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
        editor_df(pd.DataFrame(default_rows_for_editor)),
        key=f"{editor_key}_default",
        hide_index=True,
        num_rows="fixed",
        width="stretch",
        disabled=True if disabled else ["field"],
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


def _assay_default_field_editor(
    *,
    disabled: bool = False,
    current_table: pd.DataFrame | None = None,
    editor_key: str = "assay_default_editor",
    update_global_state: bool = True,
) -> pd.DataFrame:
    default_fields = [row["field"] for row in DEFAULT_ASSAY_ROWS]
    current = (
        current_table.copy()
        if current_table is not None
        else st.session_state.assay_default_table.copy()
    )

    if not {"field", "value"}.issubset(current.columns):
        current = pd.DataFrame(DEFAULT_ASSAY_ROWS)

    values = {row["field"]: row.get("value", "") for row in DEFAULT_ASSAY_ROWS}
    for index, field in enumerate(default_fields):
        matching = current.loc[current["field"].astype(str) == field]
        if not matching.empty:
            values[field] = str(matching.iloc[0].get("value", values[field]))
        elif index < len(current):
            values[field] = str(current.iloc[index].get("value", values[field]))

    header_cols = st.columns([1, 2], vertical_alignment="center")
    header_cols[0].markdown("field")
    header_cols[1].markdown("value")

    normalized_rows = []
    source_values_key = f"{editor_key}_source_values"
    source_values = st.session_state.get(source_values_key, {})
    next_source_values = {}

    for field in default_fields:
        options = ASSAY_SELECT_OPTIONS[field]
        value = normalize_assay_select_value(field, values.get(field, ""))
        if not value:
            value = ASSAY_SELECT_DEFAULTS.get(field, options[0])
        next_source_values[field] = value

        widget_key = f"{editor_key}_{field}"
        if (
            source_values.get(field) != value
            or st.session_state.get(widget_key) not in options
        ):
            st.session_state[widget_key] = value

        row_cols = st.columns([1, 2], vertical_alignment="center")
        row_cols[0].text_input(
            f"ASSAY field {field}",
            value=field,
            disabled=True,
            key=f"{editor_key}_{field}_field",
            label_visibility="collapsed",
        )
        selected_value = row_cols[1].selectbox(
            "value",
            options,
            key=widget_key,
            disabled=disabled,
            label_visibility="collapsed",
        )
        normalized_rows.append({"field": field, "value": selected_value})
        next_source_values[field] = selected_value

    result = pd.DataFrame(normalized_rows)
    if update_global_state:
        st.session_state.assay_default_table = result
    st.session_state[source_values_key] = next_source_values
    return result


def _extra_field_editor(
    *,
    state_key: str,
    editor_key: str,
    disabled: bool = False,
    current_table: pd.DataFrame | None = None,
) -> pd.DataFrame:
    current = (
        current_table.copy()
        if current_table is not None
        else st.session_state[state_key].copy()
    )
    if not {"field", "value"}.issubset(current.columns):
        current = pd.DataFrame(columns=["field", "value"])

    return st.data_editor(
        editor_df(current),
        key=editor_key,
        hide_index=True,
        num_rows="dynamic",
        width="stretch",
        disabled=disabled,
        column_config={
            "field": st.column_config.TextColumn("extra field"),
            "value": st.column_config.TextColumn("value"),
        },
    )


def _readout_selector(
    block_name: str, drafts, *, shared: bool = False, disabled: bool = False
):
    """Render stable, disableable tab buttons and return the selected draft."""

    active_key = f"active_readout_{block_name.lower()}"
    valid_keys = {draft.key for draft in drafts}
    if shared or st.session_state.get(active_key) not in valid_keys:
        st.session_state[active_key] = drafts[0].key
    columns = st.columns(len(drafts))
    for index, (column, draft) in enumerate(zip(columns, drafts)):
        if column.button(
            draft.readout_id,
            key=f"readout_tab_{block_name}_{draft.key}",
            disabled=disabled or (shared and index > 0),
            type=(
                "primary" if st.session_state[active_key] == draft.key else "secondary"
            ),
            use_container_width=True,
        ):
            st.session_state[active_key] = draft.key
            st.rerun()
    return next(draft for draft in drafts if draft.key == st.session_state[active_key])


def _render_readout_long_block(block_name: str, drafts, *, disabled: bool = False):
    block_key = block_name.lower()
    shared = st.checkbox(
        "Use the same for all readouts",
        key=f"share_{block_key}",
        value=st.session_state.shared_readout_blocks.get(block_key, False),
        disabled=disabled,
    )
    st.session_state.shared_readout_blocks[block_key] = shared
    if shared:
        copy_shared_block(st.session_state.readout_drafts, block_key)
    active = _readout_selector(block_name, drafts, shared=shared)
    default_rows = (
        DEFAULT_METADATA_ROWS if block_name == "METADATA" else DEFAULT_ASSAY_ROWS
    )
    default_table, extra_table = split_field_data(
        getattr(active, block_key), default_rows
    )
    version = active.versions.get(block_key, 0)
    prefix = f"{block_key}_{active.key}_{version}"
    if block_name == "ASSAY":
        default_edited = _assay_default_field_editor(
            disabled=disabled,
            current_table=default_table,
            editor_key=prefix,
            update_global_state=False,
        )
    else:
        default_edited = _default_field_editor(
            state_key="metadata_default_table",
            editor_key=prefix,
            default_rows=default_rows,
            disabled=disabled,
            current_table=default_table,
        )
    extra_edited = _extra_field_editor(
        state_key=f"{block_key}_extra_table",
        editor_key=f"{prefix}_extra",
        disabled=disabled,
        current_table=extra_table,
    )
    setattr(
        active,
        block_key,
        field_table_to_dict(
            combined_field_table(
                default_table=default_edited,
                extra_table=extra_edited,
                default_rows=default_rows,
            ),
            block_name=block_name,
        ),
    )
    if shared:
        copy_shared_block(st.session_state.readout_drafts, block_key)
    return active


def template_upload_callback():
    """Clear stale template messages when the upload widget changes."""

    st.session_state.template_message = None
    st.session_state.template_error = None


def device_output_upload_callback():
    """Clear stale device-output messages when the upload widget changes."""

    st.session_state.device_output_message = None
    st.session_state.device_output_error = None


def layout_upload_callback():
    """Clear stale layout upload messages when the upload widget changes."""

    st.session_state.layout_merge_pending = None
    st.session_state.layout_message = None
    st.session_state.layout_upload_error = None


def readings_upload_callback():
    """Clear stale readings state when a new readings upload starts."""

    if st.session_state.get("readings_message") is not None:
        st.session_state.readings_table = pd.DataFrame()
    st.session_state.readings_message = None
    st.session_state.readings_error = None


def inspect_file_upload_callback():
    """Clear the previous inspection when a new ATST file is uploaded."""

    st.session_state.inspected_atst = None
    st.session_state.inspect_file_name = None
    st.session_state.inspect_file_error = None
    st.session_state.pop("inspect_readout_id", None)


def _persist_readout_layout(draft) -> None:
    """Save the working layout table before an immediate Streamlit rerun."""

    if draft is None:
        return
    draft.layout = st.session_state.layout_table.copy()
    if st.session_state.shared_readout_blocks.get("layout", False):
        copy_shared_block(st.session_state.readout_drafts, "layout")


def _show_layout_merge_prompt(active_layout_draft=None) -> bool:
    """Render one pending layout merge decision."""

    pending = st.session_state.get("layout_merge_pending")
    if not pending:
        return False

    column = next_layout_merge_conflict()
    if column is None:
        st.session_state.layout_merge_pending = None
        return False

    conflicts = list(pending.get("conflicts", []))
    decisions = dict(pending.get("decisions", {}))
    source = str(pending.get("source", "Incoming layout"))
    current_count = column_value_count(pending["base"], column)
    incoming_count = column_value_count(pending["incoming"], column)
    position = len(decisions) + 1
    target_key = pending.get("readout_key")

    def persist_if_complete(applied: bool) -> None:
        if not applied:
            return
        target = st.session_state.readout_drafts.get(target_key, active_layout_draft)
        _persist_readout_layout(target)

    st.warning(
        f"{source} includes `{column}`, which already has values in the current layout."
    )
    st.caption(
        f"Column {position} of {len(conflicts)}. "
        f"Current filled cells: {current_count}. "
        f"Incoming filled cells: {incoming_count}."
    )
    replace_col, keep_col, cancel_col = st.columns(3)
    if replace_col.button(
        "Replace column",
        key=f"layout_merge_replace_{position}_{column}",
        use_container_width=True,
    ):
        persist_if_complete(resolve_layout_merge_conflict(column, replace=True))
        st.rerun()
    if keep_col.button(
        "Keep current",
        key=f"layout_merge_keep_{position}_{column}",
        use_container_width=True,
    ):
        persist_if_complete(resolve_layout_merge_conflict(column, replace=False))
        st.rerun()
    if cancel_col.button(
        "Cancel merge",
        key=f"layout_merge_cancel_{position}_{column}",
        use_container_width=True,
    ):
        cancel_layout_merge()
        st.rerun()

    return True


def _render_entities(*, disabled: bool) -> None:
    with _section_container("ENTITIES"):
        entity_uploads = st.file_uploader(
            "Drop CSV/TSV/TXT files",
            type=["csv", "tsv", "txt"],
            accept_multiple_files=True,
            key=upload_widget_key("entity_uploads"),
            label_visibility="collapsed",
            disabled=disabled,
        )
        if entity_uploads:
            loaded_entities: dict[str, pd.DataFrame] = {}
            upload_errors = []
            for uploaded_file in entity_uploads:
                table_name = Path(uploaded_file.name).stem
                try:
                    loaded_entities[table_name] = read_uploaded_table(uploaded_file)
                except UploadedTableParseError as exc:
                    upload_errors.append(
                        f"Could not load entity table {table_name}: {exc}"
                    )

            st.session_state.entity_tables.update(loaded_entities)
            st.session_state.entity_upload_errors = upload_errors
            expire_upload_widget("entity_uploads")
            st.rerun()

        for upload_error in st.session_state.entity_upload_errors:
            st.error(upload_error)

        if st.session_state.entity_tables:
            if st.button("Remove all entity tables", disabled=disabled):
                st.session_state.entity_tables = {}
                st.rerun()
            for table_name, table_df in list(st.session_state.entity_tables.items()):
                st.markdown(f"**{table_name}**")
                if st.button(
                    f"Remove {table_name}",
                    key=f"remove_entity_{table_name}",
                    disabled=disabled,
                ):
                    del st.session_state.entity_tables[table_name]
                    st.rerun()
                st.session_state.entity_tables[table_name] = st.data_editor(
                    editor_df(table_df),
                    key=f"entity_editor_{table_name}",
                    hide_index=True,
                    num_rows="dynamic",
                    width="stretch",
                    disabled=disabled,
                )


def _render_layout_contents(
    *,
    active_plate_format: str,
    layout_editor_key: str,
    layout_editor_locked: bool,
    active_layout_draft=None,
) -> tuple[pd.DataFrame, bool]:
    layout_merge_pending = st.session_state.get("layout_merge_pending") is not None
    with st.container(height=75, border=False, vertical_alignment="center"):
        if layout_editor_locked:
            st.caption("Apply or cancel layout editing before uploading a layout.")
        elif layout_merge_pending:
            st.caption(
                "Finish the pending layout merge before uploading another layout."
            )
        layout_upload = st.file_uploader(
            "Drop CSV/TSV/TXT or ATST",
            type=["csv", "tsv", "txt"],
            key=upload_widget_key("layout_file_upload"),
            on_change=layout_upload_callback,
            label_visibility="collapsed",
            disabled=layout_editor_locked or layout_merge_pending,
        )

    if layout_upload is not None and not layout_merge_pending:
        try:
            incoming_layout = read_uploaded_layout(layout_upload)
        except UploadedTableParseError as exc:
            st.session_state.layout_message = None
            st.session_state.layout_upload_error = f"Could not load layout: {exc}"
        else:
            layout_applied = stage_layout_merge(
                incoming_layout,
                source="Layout upload",
                success_message="Loaded layout.",
                plate_format=active_plate_format,
            )
            if layout_applied:
                _persist_readout_layout(active_layout_draft)
            elif active_layout_draft is not None:
                st.session_state.layout_merge_pending["readout_key"] = (
                    active_layout_draft.key
                )
        expire_upload_widget("layout_file_upload")
        st.rerun()

    if st.session_state.get("layout_message"):
        st.info(st.session_state.layout_message)
    if st.session_state.get("layout_upload_error"):
        st.error(st.session_state.layout_upload_error)

    if _show_layout_merge_prompt(active_layout_draft):
        return st.session_state.layout_table.fillna(""), layout_editor_locked

    current_layout_table = layout_preview_editor(
        editor_df(st.session_state.layout_table),
        plate_format=active_plate_format,
        plate_formats=PLATE_FORMAT_OPTIONS,
        key=layout_editor_key,
    ).fillna("")
    layout_editor_mode_value = st.session_state.get(
        f"{layout_editor_key}_mode",
        layout_preview_editor_mode(layout_editor_key),
    )
    layout_editor_locked = layout_editor_mode_value == "layout_editor"
    st.session_state.layout_table = current_layout_table
    _persist_readout_layout(active_layout_draft)

    st.download_button(
        "Download layout",
        data=current_layout_table.to_csv(index=False, sep="\t").encode("utf-8"),
        file_name="layout.tsv",
        mime="text/tab-separated-values",
        use_container_width=False,
        disabled=layout_editor_locked,
        help=(
            "Apply changes before downloading the layout"
            if layout_editor_locked
            else None
        ),
    )
    return current_layout_table, layout_editor_locked


def _render_readings_contents(
    *,
    active_plate_format: str,
    layout_editor_locked: bool,
    active_readings_draft=None,
) -> None:
    readings_upload = st.file_uploader(
        "Drop CSV/TSV/TXT",
        type=["csv", "tsv", "txt"],
        key=upload_widget_key("readings_upload"),
        on_change=readings_upload_callback,
        label_visibility="collapsed",
        disabled=layout_editor_locked,
    )
    if readings_upload is not None and st.session_state.get("readings_message") is None:
        try:
            st.session_state.readings_table = sort_readings_columns(
                read_uploaded_table(readings_upload),
                plate_format=active_plate_format,
            )
        except (UploadedTableParseError, ValueError) as exc:
            st.session_state.readings_message = None
            st.session_state.readings_error = f"Could not load readings: {exc}"
        else:
            st.session_state.readings_message = "Loaded readings."
            if active_readings_draft is not None:
                active_readings_draft.readings = st.session_state.readings_table.copy()
        expire_upload_widget("readings_upload")
        st.rerun()

    if st.session_state.get("readings_message"):
        st.success(st.session_state.readings_message)
    if st.session_state.get("readings_error"):
        st.error(st.session_state.readings_error)
    if not st.session_state.readings_table.empty:
        st.dataframe(
            st.session_state.readings_table,
            hide_index=True,
            width="stretch",
        )


def _render_readings_plot(
    atst: ATSTFile,
    *,
    key: str,
) -> None:
    with _section_container("READINGS PLOT"):
        _render_readings_plot_contents(atst, key=key)


def _render_readings_plot_contents(
    atst: ATSTFile,
    *,
    key: str,
    settings_key: str | None = None,
) -> None:
    layout = atst.layout.data
    readings = atst.readings.data
    if layout.empty or readings.empty or "well_loc" not in layout.columns:
        return

    group_columns = [column for column in layout.columns if column != "well_loc"]
    default_columns = []
    if "type" in group_columns:
        type_values = layout["type"].fillna("").astype(str).str.strip()
        if type_values.ne("").any():
            default_columns = ["type"]
    settings_key = settings_key or key
    group_by_key = f"readings_plot_group_by_{settings_key}"
    color_by_key = f"readings_plot_color_by_{settings_key}"
    reference_key = f"readings_plot_reference_{settings_key}"
    ignore_types_key = f"readings_plot_ignore_types_{settings_key}"
    legend_key = f"readings_plot_legend_{settings_key}"
    if group_by_key in st.session_state:
        st.session_state[group_by_key] = [
            column
            for column in st.session_state[group_by_key]
            if column in group_columns
        ]
    if st.session_state.get(color_by_key) not in [None, *group_columns]:
        st.session_state[color_by_key] = None
    selected_groups = st.session_state.get(group_by_key, default_columns)
    group_by = st.multiselect(
        "Group panels by:",
        options=group_columns,
        default=selected_groups,
        key=f"{group_by_key}_widget_{key}",
    )
    st.session_state[group_by_key] = group_by
    color_options = [None, *group_columns]
    selected_color = st.session_state.get(color_by_key)
    reference_types = []
    if "type" in layout.columns:
        reference_types = sorted(
            value
            for value in layout["type"].fillna("").astype(str).str.strip().unique()
            if value and value.upper() not in {"NA", "N/A", "NONE"}
        )
    if reference_key in st.session_state:
        st.session_state[reference_key] = [
            value
            for value in st.session_state[reference_key]
            if value in reference_types
        ]
    if ignore_types_key in st.session_state:
        st.session_state[ignore_types_key] = [
            value
            for value in st.session_state[ignore_types_key]
            if value in reference_types
        ]
    selected_references = st.session_state.get(reference_key, [])
    selected_ignored_types = st.session_state.get(ignore_types_key, [])
    color_column, reference_column, ignore_column = st.columns([1, 2, 2])
    with color_column:
        color_by = st.selectbox(
            "Color by:",
            options=color_options,
            index=color_options.index(selected_color),
            format_func=lambda value: "None" if value is None else value,
            key=f"{color_by_key}_widget_{key}",
        )
    with reference_column:
        show_reference = st.multiselect(
            "Show reference:",
            options=reference_types,
            default=selected_references,
            key=f"{reference_key}_widget_{key}",
        )
    with ignore_column:
        ignore_types = st.multiselect(
            "Ignore type:",
            options=reference_types,
            default=selected_ignored_types,
            key=f"{ignore_types_key}_widget_{key}",
        )
    st.session_state[reference_key] = show_reference
    st.session_state[ignore_types_key] = ignore_types
    st.session_state[color_by_key] = color_by
    legend_options = group_columns
    default_legend_fields = [
        column for column in legend_options if column not in group_by
    ]
    if legend_key in st.session_state:
        st.session_state[legend_key] = [
            column
            for column in st.session_state[legend_key]
            if column in legend_options
        ]
    selected_legend_fields = st.session_state.get(legend_key, default_legend_fields)
    include_in_legend = st.multiselect(
        "Include in legend:",
        options=legend_options,
        default=selected_legend_fields,
        key=f"{legend_key}_widget_{key}",
    )
    st.session_state[legend_key] = include_in_legend
    try:
        figure = plot_readings_by_layout(
            atst,
            group_by=group_by,
            color_by=color_by,
            show_reference=show_reference,
            ignore_types=ignore_types,
            include_in_legend=include_in_legend,
        )
    except (ATSTValidationError, ValueError) as exc:
        st.info(str(exc))
        return
    height_ratio = figure.layout.meta["readings_plot_height_ratio"]
    chart_container_key = f"readings_plot_chart_{key}"
    st.html(
        f"""
        <style>
        .st-key-{chart_container_key} {{
            container-type: inline-size;
            width: 100%;
        }}
        .st-key-{chart_container_key} [data-testid="stPlotlyChart"] {{
            width: 100% !important;
            height: calc((100cqw - 80px) * {height_ratio} + 125px) !important;
        }}
        .st-key-{chart_container_key} [data-testid="stPlotlyChart"] > div,
        .st-key-{chart_container_key} .js-plotly-plot,
        .st-key-{chart_container_key} .plot-container,
        .st-key-{chart_container_key} .svg-container {{
            width: 100% !important;
            height: 100% !important;
        }}
        </style>
        """
    )
    with st.container(key=chart_container_key):
        st.plotly_chart(
            figure,
            width="stretch",
            config={"responsive": True},
            key=f"readings_plot_{key}",
        )


def _render_output(*, layout_editor_locked: bool, build_atst, writer) -> None:
    file_name = st.text_input(
        "Output name",
        key="file_name",
        disabled=layout_editor_locked,
    )
    download_mode = st.radio(
        "Download format",
        options=("Standalone ATST file", "Linked-files ZIP"),
        horizontal=True,
        key="download_mode",
        disabled=layout_editor_locked,
        help="Linked-files ZIP puts each table in a named folder beside the ATST container.",
    )
    if not st.button(
        "Generate",
        type="primary",
        disabled=(
            layout_editor_locked
            or st.session_state.get("layout_merge_pending") is not None
        ),
    ):
        return

    try:
        path = Path(normalize_atst_file_name(file_name))
        atst = build_atst(path.name)
        with TemporaryDirectory(prefix="atst-output-") as directory:
            output_path = Path(directory) / path.name
            writer(atst, output_path)
            text = output_path.read_text(encoding="utf-8")
            bundle_bytes = None
            if download_mode == "Linked-files ZIP":
                bundle_path = Path(directory) / f"{path.name}.zip"
                write_linked_atst_bundle(atst, bundle_path)
                bundle_bytes = bundle_path.read_bytes()
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not generate ATST file: {exc}")
        return

    st.code(text, language="text")
    if download_mode == "Linked-files ZIP" and bundle_bytes is not None:
        st.download_button(
            "Download linked-files ZIP",
            data=bundle_bytes,
            file_name=f"{path.name}.zip",
            mime="application/zip",
            on_click="ignore",
        )
    else:
        st.download_button(
            "Download file",
            data=text,
            file_name=path.name,
            mime="text/plain",
            on_click="ignore",
        )


def _render_single_readout_workflow(
    *,
    study_data: dict[str, str],
    layout_editor_locked: bool,
    layout_editor_key: str,
) -> None:
    with _section_container("METADATA"):
        metadata_default_table = _default_field_editor(
            state_key="metadata_default_table",
            editor_key="metadata_default_editor",
            default_rows=DEFAULT_METADATA_ROWS,
            disabled=layout_editor_locked,
        )
        metadata_extra_table = _extra_field_editor(
            state_key="metadata_extra_table",
            editor_key="metadata_extra_editor",
            disabled=layout_editor_locked,
        )

    with _section_container("ASSAY"):
        assay_default_table = _assay_default_field_editor(
            disabled=layout_editor_locked,
        )
        assay_extra_table = _extra_field_editor(
            state_key="assay_extra_table",
            editor_key="assay_extra_editor",
            disabled=layout_editor_locked,
        )

    active_plate_format = (
        selected_plate_format(assay_default_table)
        or ASSAY_SELECT_DEFAULTS["plate_format"]
    )
    if st.session_state.get("layout_merge_pending") is None:
        st.session_state.layout_table = sort_layout_rows(
            st.session_state.layout_table,
            plate_format=active_plate_format,
        )
    with _section_container("LAYOUT"):
        current_layout_table, layout_editor_locked = _render_layout_contents(
            active_plate_format=active_plate_format,
            layout_editor_key=layout_editor_key,
            layout_editor_locked=layout_editor_locked,
        )

    _render_entities(disabled=layout_editor_locked)

    with _section_container("READINGS"):
        _render_readings_contents(
            active_plate_format=active_plate_format,
            layout_editor_locked=layout_editor_locked,
        )

    def build(file_name: str):
        return make_atst(
            file_name=file_name,
            study_data=study_data,
            metadata_data=field_table_to_dict(
                combined_field_table(
                    default_table=metadata_default_table,
                    extra_table=metadata_extra_table,
                    default_rows=DEFAULT_METADATA_ROWS,
                ),
                block_name="METADATA",
            ),
            assay_data=field_table_to_dict(
                combined_field_table(
                    default_table=assay_default_table,
                    extra_table=assay_extra_table,
                    default_rows=DEFAULT_ASSAY_ROWS,
                ),
                block_name="ASSAY",
            ),
            layout_df=prepare_wide_table(
                current_layout_table,
                block_name="LAYOUT",
                plate_format=active_plate_format,
            ),
            readings_df=prepare_wide_table(
                st.session_state.readings_table,
                block_name="READINGS",
                plate_format=active_plate_format,
            ),
            entities=entities_from_tables(st.session_state.entity_tables),
        )

    if not current_layout_table.empty and not st.session_state.readings_table.empty:
        try:
            preview_atst = build("readings-preview.atst.txt")
        except (ATSTValidationError, ValueError) as exc:
            with _section_container("READINGS PLOT"):
                st.info(str(exc))
        else:
            _render_readings_plot(preview_atst, key="single")

    _render_output(
        layout_editor_locked=layout_editor_locked,
        build_atst=build,
        writer=write_atst,
    )


def _render_multi_readout_workflow(
    *,
    study_data: dict[str, str],
    readout_drafts,
    layout_editor_locked: bool,
) -> None:
    with _section_container("READOUT IDS"):
        st.caption("Confirm or edit the identifier for each uploaded output.")
        for draft in readout_drafts:
            draft.readout_id = st.text_input(
                draft.source_name,
                value=draft.readout_id or "",
                key=f"readout_id_{draft.key}",
                disabled=layout_editor_locked,
            ).strip()
        identifiers = [draft.readout_id for draft in readout_drafts]
        if any(not identifier for identifier in identifiers):
            st.error("Every readout must have a readout ID.")
        if len(identifiers) != len(set(identifiers)):
            st.error("Readout IDs must be unique.")

    with _section_container("METADATA"):
        _render_readout_long_block(
            "METADATA", readout_drafts, disabled=layout_editor_locked
        )

    with _section_container("ASSAY"):
        _render_readout_long_block(
            "ASSAY", readout_drafts, disabled=layout_editor_locked
        )

    layout_shared = bool(
        st.session_state.get(
            "share_layout",
            st.session_state.shared_readout_blocks.get("layout", False),
        )
    )
    st.session_state.shared_readout_blocks["layout"] = layout_shared
    if layout_shared:
        copy_shared_block(st.session_state.readout_drafts, "layout")
    active_layout_key = st.session_state.get("active_readout_layout")
    active_layout_draft = (
        readout_drafts[0]
        if layout_shared
        else next(
            (draft for draft in readout_drafts if draft.key == active_layout_key),
            readout_drafts[0],
        )
    )
    st.session_state.layout_table = active_layout_draft.layout.copy()
    assay_default_table, _ = split_field_data(
        active_layout_draft.assay, DEFAULT_ASSAY_ROWS
    )
    active_plate_format = (
        selected_plate_format(assay_default_table)
        or ASSAY_SELECT_DEFAULTS["plate_format"]
    )
    layout_editor_key = (
        f"layout_preview_editor_{active_layout_draft.key}_"
        f"{active_layout_draft.versions.get('layout', 0)}"
    )
    if st.session_state.get("layout_merge_pending") is None:
        st.session_state.layout_table = sort_layout_rows(
            st.session_state.layout_table,
            plate_format=active_plate_format,
        )

    with _section_container("LAYOUT"):
        layout_shared = st.checkbox(
            "Use the same for all readouts",
            key="share_layout",
            value=st.session_state.shared_readout_blocks.get("layout", False),
            disabled=layout_editor_locked,
        )
        st.session_state.shared_readout_blocks["layout"] = layout_shared
        if layout_shared:
            copy_shared_block(st.session_state.readout_drafts, "layout")
        active_layout_draft = _readout_selector(
            "LAYOUT",
            readout_drafts,
            shared=layout_shared,
            disabled=st.session_state.get("layout_merge_pending") is not None,
        )
        _, layout_editor_locked = _render_layout_contents(
            active_plate_format=active_plate_format,
            layout_editor_key=layout_editor_key,
            layout_editor_locked=layout_editor_locked,
            active_layout_draft=active_layout_draft,
        )

    _render_entities(disabled=layout_editor_locked)

    with _section_container("READINGS"):
        active_readings_draft = _readout_selector("READINGS", readout_drafts)
        st.session_state.readings_table = active_readings_draft.readings.copy()
        readings_assay_table, _ = split_field_data(
            active_readings_draft.assay, DEFAULT_ASSAY_ROWS
        )
        readings_plate_format = (
            selected_plate_format(readings_assay_table)
            or ASSAY_SELECT_DEFAULTS["plate_format"]
        )
        _render_readings_contents(
            active_plate_format=readings_plate_format,
            layout_editor_locked=layout_editor_locked,
            active_readings_draft=active_readings_draft,
        )

    plottable_drafts = [
        draft
        for draft in readout_drafts
        if not draft.layout.empty and not draft.readings.empty
    ]
    if plottable_drafts:
        with _section_container("READINGS PLOT"):
            plot_draft = _readout_selector("READINGS PLOT", plottable_drafts)
            plot_assay_table, _ = split_field_data(
                plot_draft.assay, DEFAULT_ASSAY_ROWS
            )
            plot_plate_format = (
                selected_plate_format(plot_assay_table)
                or ASSAY_SELECT_DEFAULTS["plate_format"]
            )
            try:
                preview_atst = make_atst(
                    file_name="readings-preview.atst.txt",
                    study_data=study_data,
                    metadata_data=plot_draft.metadata,
                    assay_data=plot_draft.assay,
                    layout_df=prepare_wide_table(
                        plot_draft.layout,
                        block_name="LAYOUT",
                        plate_format=plot_plate_format,
                    ),
                    readings_df=prepare_wide_table(
                        plot_draft.readings,
                        block_name="READINGS",
                        plate_format=plot_plate_format,
                    ),
                    entities=None,
                )
                preview_atst.readout_id = plot_draft.readout_id or None
            except (ATSTValidationError, ValueError) as exc:
                st.info(str(exc))
            else:
                _render_readings_plot_contents(
                    preview_atst,
                    key=plot_draft.key,
                    settings_key="multi",
                )

    def build(file_name: str):
        prepared_readouts = []
        for draft in readout_drafts:
            plate_format = str(draft.assay.get("plate_format", ""))
            prepared_readouts.append(
                (
                    draft.readout_id,
                    draft.metadata,
                    draft.assay,
                    prepare_wide_table(
                        draft.layout,
                        block_name="LAYOUT",
                        plate_format=plate_format,
                    ),
                    prepare_wide_table(
                        draft.readings,
                        block_name="READINGS",
                        plate_format=plate_format,
                    ),
                )
            )
        return make_multi_readout_atst(
            file_name=file_name,
            study_data=study_data,
            readout_data=prepared_readouts,
            entities=entities_from_tables(st.session_state.entity_tables),
        )

    _render_output(
        layout_editor_locked=layout_editor_locked,
        build_atst=build,
        writer=write_multi_readout_atst,
    )


def _render_readonly_field_block(
    block_name: str,
    data: dict[str, str],
    default_rows: list[dict[str, str]],
) -> None:
    """Render one Generator-style long block without editable widgets."""

    default_fields = [row["field"] for row in default_rows]
    table = pd.DataFrame(
        [
            {"field": field, "value": str(data.get(field, ""))}
            for field in default_fields
        ]
        + [
            {"field": field, "value": str(value)}
            for field, value in data.items()
            if field not in default_fields
        ]
    )
    with _section_container(block_name):
        st.dataframe(table, hide_index=True, width="stretch")


def _render_inspected_entities(entities) -> None:
    with _section_container("ENTITIES"):
        if entities is None or not entities.tables:
            st.caption("No entity tables in this file.")
            return
        for table_name, entity_table in entities.tables.items():
            st.markdown(f"**{table_name}**")
            st.dataframe(entity_table.data, hide_index=True, width="stretch")


def _render_inspected_readout(atst: ATSTFile, *, key: str) -> None:
    _render_readonly_field_block(
        "METADATA", atst.metadata.data, DEFAULT_METADATA_ROWS
    )
    _render_readonly_field_block("ASSAY", atst.assay.data, DEFAULT_ASSAY_ROWS)
    with _section_container("LAYOUT"):
        st.dataframe(atst.layout.data, hide_index=True, width="stretch")
    _render_inspected_entities(atst.entities)
    with _section_container("READINGS"):
        st.dataframe(atst.readings.data, hide_index=True, width="stretch")
    _render_readings_plot(atst, key=key)


def _render_file_inspector() -> None:
    """Render a read-only view of an uploaded ATST file."""

    st.title("Inspect file")
    with _section_container("Upload file"):
        inspected_upload = st.file_uploader(
            "Drop ATST file",
            type=["txt", "tsv", "zip"],
            key=upload_widget_key("inspect_file_upload"),
            on_change=inspect_file_upload_callback,
            label_visibility="collapsed",
        )

    if inspected_upload is not None:
        try:
            st.session_state.inspected_atst = read_uploaded_atst(inspected_upload)
            st.session_state.inspect_file_name = inspected_upload.name
            st.session_state.inspect_file_error = None
        except Exception as exc:  # noqa: BLE001
            st.session_state.inspected_atst = None
            st.session_state.inspect_file_name = None
            st.session_state.inspect_file_error = f"Could not inspect ATST file: {exc}"
        expire_upload_widget("inspect_file_upload")
        st.rerun()

    if st.session_state.get("inspect_file_error"):
        st.error(st.session_state.inspect_file_error)
        return

    inspected = st.session_state.get("inspected_atst")
    if inspected is None:
        return

    st.success(f"Loaded {st.session_state.inspect_file_name}.")
    _render_readonly_field_block("STUDY", inspected.study.data, DEFAULT_STUDY_ROWS)

    if isinstance(inspected, MultiReadoutATST):
        with _section_container("READOUT IDS"):
            st.dataframe(
                inspected.readout_ids.data,
                hide_index=True,
                width="stretch",
            )
            readout_id = st.selectbox(
                "Inspect readout",
                options=list(inspected.readouts),
                key="inspect_readout_id",
            )
        readout_index = list(inspected.readouts).index(readout_id)
        _render_inspected_readout(
            inspected.readouts[readout_id],
            key=f"inspect_{readout_index}",
        )
        return

    _render_inspected_readout(inspected, key="inspect_single")


def _render_generator() -> None:
    """Render the editable ATST generator form."""

    layout_editor_key = (
        f"layout_preview_editor_{st.session_state.get('layout_upload_version', 0)}"
    )
    reset_layout_preview_editor_locks_on_page_change("atst_generator")
    layout_editor_initial_mode = layout_preview_editor_mode(layout_editor_key)
    layout_editor_locked = layout_editor_initial_mode == "layout_editor"
    layout_merge_pending_at_start = (
        st.session_state.get("layout_merge_pending") is not None
    )

    col1, col2 = st.columns([4, 1], vertical_alignment="bottom")
    with col1:
        st.title("ATST Generator")

    with col2:
        st.link_button(
            "ATST GitHub",
            "https://github.com/JP235/ATST/",
            use_container_width=True,
        )
    col1_reader, col2_reader = st.columns([5, 3], vertical_alignment="top")

    with col1_reader:  # noqa: SIM117
        with _section_container("Read Device output"):
            device_col, upload_col = st.columns([2, 3], vertical_alignment="top")
            with device_col:
                device = st.selectbox(
                    "Device",
                    list(DEVICE_READERS),
                    key="device_output_device",
                    label_visibility="collapsed",
                    disabled=layout_editor_locked or layout_merge_pending_at_start,
                )
            with upload_col:
                device_output_upload = st.file_uploader(
                    "Drop raw output",
                    type=["txt", "tsv", "csv", "xlsx"],
                    accept_multiple_files=True,
                    key=upload_widget_key("device_output_upload"),
                    label_visibility="collapsed",
                    on_change=device_output_upload_callback,
                    disabled=layout_editor_locked or layout_merge_pending_at_start,
                )

            if (
                device_output_upload
                and st.session_state.get("device_output_message") is None
            ):
                try:
                    st.session_state.device_output_message = load_device_outputs(
                        device_output_upload,
                        device=device,
                    )
                except (
                    ClariostarParseError,
                    LogPhaseParseError,
                    TecanParseError,
                ) as exc:
                    st.session_state.device_output_message = None
                    st.session_state.device_output_error = (
                        f"Could not read device output: {exc}"
                    )
                except Exception as exc:  # noqa: BLE001
                    st.session_state.device_output_message = None
                    st.session_state.device_output_error = (
                        f"Could not read device output: {exc}"
                    )
                expire_upload_widget("device_output_upload")
                st.rerun()

            if st.session_state.get("device_output_message"):
                messages = st.session_state.device_output_message
                if isinstance(messages, str):
                    messages = [messages]
                for message in messages:
                    st.success(message)
            if st.session_state.get("device_output_error"):
                st.error(st.session_state.device_output_error)

    with col2_reader:  # noqa: SIM117
        with _section_container("Load template"):
            template_upload = st.file_uploader(
                "Drop ATST template",
                type=["txt", "tsv"],
                key=upload_widget_key("template_upload"),
                label_visibility="collapsed",
                on_change=template_upload_callback,
                disabled=layout_editor_locked or layout_merge_pending_at_start,
            )
            if (
                template_upload is not None
                and st.session_state.get("template_message") is None
            ):
                try:
                    st.session_state.template_message = load_template(template_upload)
                except Exception as exc:  # noqa: BLE001
                    st.session_state.template_error = f"Could not load template: {exc}"
                expire_upload_widget("template_upload")
                st.rerun()
            if st.session_state.get("template_message"):
                st.success(st.session_state.template_message)
            if st.session_state.get("template_error"):
                st.error(st.session_state.template_error)

    with _section_container("STUDY"):
        study_default_table = _default_field_editor(
            state_key="study_default_table",
            editor_key="study_default_editor",
            default_rows=DEFAULT_STUDY_ROWS,
            disabled=layout_editor_locked,
        )
        study_extra_table = _extra_field_editor(
            state_key="study_extra_table",
            editor_key="study_extra_editor",
            disabled=layout_editor_locked,
        )

    study_data = field_table_to_dict(
        combined_field_table(
            default_table=study_default_table,
            extra_table=study_extra_table,
            default_rows=DEFAULT_STUDY_ROWS,
        ),
        block_name="STUDY",
    )
    readout_drafts = ordered_readouts(st.session_state.readout_drafts)
    if len(readout_drafts) > 1:
        _render_multi_readout_workflow(
            study_data=study_data,
            readout_drafts=readout_drafts,
            layout_editor_locked=layout_editor_locked,
        )
    else:
        _render_single_readout_workflow(
            study_data=study_data,
            layout_editor_locked=layout_editor_locked,
            layout_editor_key=layout_editor_key,
        )


def render_file_inspector_page() -> None:
    """Render the standalone Streamlit file-inspector page."""

    st.html(_STYLE_PATH)
    init_state()
    _render_file_inspector()


def main() -> None:
    """Render the Streamlit ATST generator form."""

    st.html(_STYLE_PATH)
    init_state()
    _render_generator()


if __name__ == "__main__":
    main()
