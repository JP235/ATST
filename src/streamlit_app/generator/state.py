from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import pandas as pd
import streamlit as st

from ATST.device_readers import DEVICE_READERS
from streamlit_app.generator.defaults import (
    DEFAULT_ASSAY_ROWS,
    DEFAULT_LAYOUT_ROWS,
    DEFAULT_METADATA_ROWS,
    DEFAULT_READINGS_ROWS,
    DEFAULT_STUDY_ROWS,
)
from streamlit_app.generator.fields import (
    combined_field_table,
    field_table_to_dict,
    merge_field_data,
    normalize_assay_select_value,
    split_field_data,
)
from streamlit_app.generator.templates import TemplateATST, read_atst_lax
from streamlit_app.generator.readouts import ReadoutDraft, new_readout_draft, ordered_readouts
from streamlit_app.tables.layout import (
    layout_conflict_columns,
    merge_layout_tables,
    sort_layout_rows,
)
from streamlit_app.tables.uploads import sort_readings_columns


def init_state() -> None:
    """Initialize Streamlit session defaults for the ATST generator."""

    defaults = {
        "study_default_table": pd.DataFrame(DEFAULT_STUDY_ROWS),
        "study_extra_table": pd.DataFrame(columns=["field", "value"]),
        "metadata_default_table": pd.DataFrame(DEFAULT_METADATA_ROWS),
        "metadata_extra_table": pd.DataFrame(columns=["field", "value"]),
        "assay_default_table": pd.DataFrame(DEFAULT_ASSAY_ROWS),
        "assay_extra_table": pd.DataFrame(columns=["field", "value"]),
        "layout_table": pd.DataFrame(DEFAULT_LAYOUT_ROWS),
        "layout_upload_version": 0,
        "layout_message": None,
        "layout_merge_pending": None,
        "readings_table": pd.DataFrame(DEFAULT_READINGS_ROWS),
        "entity_tables": {},
        "file_name": "new_assay.atst.txt",
        "device_output_message": None,
        "device_output_error": None,
        "device_output_loaded": False,
        "template_message": None,
        "template_error": None,
        "layout_upload_error": None,
        "readings_message": None,
        "readings_error": None,
        "entity_upload_errors": [],
        "inspected_atst": None,
        "inspect_file_name": None,
        "inspect_file_error": None,
        "readout_drafts": {},
        "shared_readout_blocks": {
            "metadata": False,
            "assay": False,
            "layout": False,
        },
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            try:
                st.session_state[key] = value.copy()
            except (TypeError, AttributeError):
                st.session_state[key] = deepcopy(value)


def clear_layout_editor_widget_state() -> None:
    """Remove layout editor widget keys so the component can reload cleanly."""

    for key in list(st.session_state):
        if str(key).startswith("layout_preview_editor"):
            del st.session_state[key]


def reset_layout_table() -> None:
    """Restore the layout editor to a blank default table."""

    st.session_state.layout_table = pd.DataFrame(DEFAULT_LAYOUT_ROWS)
    st.session_state.layout_upload_version = (
        st.session_state.get("layout_upload_version", 0) + 1
    )
    st.session_state.layout_message = None
    st.session_state.layout_merge_pending = None
    clear_layout_editor_widget_state()
    for key in list(st.session_state):
        if str(key).startswith("layout_upload_") and key != "layout_upload_version":
            del st.session_state[key]


def apply_layout_table(
    layout: pd.DataFrame,
    *,
    plate_format: str | None = None,
) -> None:
    """Apply a layout table and refresh the layout editor component."""

    st.session_state.layout_table = sort_layout_rows(
        layout,
        plate_format=plate_format or st.session_state.get("assay_plate_format"),
    )
    st.session_state.layout_merge_pending = None
    st.session_state.layout_upload_version = (
        st.session_state.get("layout_upload_version", 0) + 1
    )
    clear_layout_editor_widget_state()


def stage_layout_merge(
    incoming_layout: pd.DataFrame,
    *,
    source: str,
    success_message: str,
    plate_format: str | None = None,
) -> bool:
    """Apply a layout merge immediately, or stage column conflicts for review."""

    base_layout = st.session_state.layout_table.copy()
    plate_format = plate_format or st.session_state.get("assay_plate_format")
    incoming_layout = sort_layout_rows(incoming_layout, plate_format=plate_format)
    conflict_columns = layout_conflict_columns(
        base_layout,
        incoming_layout,
        plate_format=plate_format,
    )
    if conflict_columns:
        st.session_state.layout_merge_pending = {
            "source": source,
            "base": base_layout,
            "incoming": incoming_layout.copy(),
            "conflicts": conflict_columns,
            "decisions": {},
            "success_message": success_message,
            "plate_format": plate_format,
        }
        st.session_state.layout_message = (
            f"{source} has layout columns that need review."
        )
        return False

    apply_layout_table(
        merge_layout_tables(
            base_layout,
            incoming_layout,
            plate_format=plate_format,
        ),
        plate_format=plate_format,
    )
    st.session_state.layout_message = success_message
    return True


def next_layout_merge_conflict() -> str | None:
    """Return the next pending layout column that needs a decision."""

    pending = st.session_state.get("layout_merge_pending")
    if not pending:
        return None

    decisions = pending.get("decisions", {})
    for column in pending.get("conflicts", []):
        if column not in decisions:
            return column
    return None


def resolve_layout_merge_conflict(column: str, *, replace: bool) -> bool:
    """Record one layout merge decision and apply the merge when complete."""

    pending = st.session_state.get("layout_merge_pending")
    if not pending:
        return False

    decisions = dict(pending.get("decisions", {}))
    decisions[column] = replace
    pending["decisions"] = decisions

    remaining = [
        conflict
        for conflict in pending.get("conflicts", [])
        if conflict not in decisions
    ]
    if remaining:
        st.session_state.layout_merge_pending = pending
        return False

    replace_columns = [
        conflict for conflict, should_replace in decisions.items() if should_replace
    ]
    merged_layout = merge_layout_tables(
        pending["base"],
        pending["incoming"],
        replace_columns=replace_columns,
        plate_format=pending.get("plate_format"),
    )
    success_message = pending.get("success_message", "Merged layout.")
    apply_layout_table(merged_layout, plate_format=pending.get("plate_format"))
    st.session_state.layout_message = success_message
    st.session_state.layout_merge_pending = None
    return True


def cancel_layout_merge() -> None:
    """Discard a staged layout merge."""

    st.session_state.layout_merge_pending = None
    st.session_state.layout_message = "Layout merge cancelled."


def current_field_state_data(
    *,
    default_state_key: str,
    extra_state_key: str,
    default_rows: list[dict[str, str]],
    block_name: str,
) -> dict[str, str]:
    """Read current default and extra field tables as a block data dictionary."""

    return field_table_to_dict(
        combined_field_table(
            default_table=st.session_state[default_state_key],
            extra_table=st.session_state[extra_state_key],
            default_rows=default_rows,
        ),
        block_name=block_name,
    )


def set_field_state_data(
    data: dict[str, str],
    *,
    default_state_key: str,
    extra_state_key: str,
    default_rows: list[dict[str, str]],
) -> None:
    """Split block data into default and extra Streamlit field tables."""

    (
        st.session_state[default_state_key],
        st.session_state[extra_state_key],
    ) = split_field_data(data, default_rows)


def load_template(uploaded_file) -> str:
    """Load an ATST template into app state.

    Args:
        uploaded_file: Streamlit uploaded ATST file. When device output has
            already been loaded, parsed device fields are preserved.
    """

    with TemporaryDirectory(prefix="atst-template-") as directory:
        template_path = Path(directory) / "uploaded.atst.txt"
        template_path.write_bytes(uploaded_file.getvalue())
        atst = read_atst_lax(template_path)
    if atst.multi_readout_file:
        if not atst.readouts:
            raise ValueError("Multi-readout template has no declared readout IDs")
        return _load_multi_readout_template(atst, uploaded_file.name)
    if len(st.session_state.get("readout_drafts", {})) > 1:
        return _apply_single_template_to_readouts(atst)
    if atst.readout_id is not None:
        message = f"Loaded first readout from multi-readout template: {atst.readout_id}"
    else:
        message = "Loaded template."

    if st.session_state.get("device_output_loaded"):
        layout_applied = load_template_without_overwriting(atst)
        message = f"{message} Existing device output fields were preserved."
        if not layout_applied:
            message = f"{message} Resolve layout column conflicts below."
        return message

    st.session_state.file_name = str(
        atst.file_info.data.get("file_name") or uploaded_file.name
    )
    set_field_state_data(
        atst.study.data,
        default_state_key="study_default_table",
        extra_state_key="study_extra_table",
        default_rows=DEFAULT_STUDY_ROWS,
    )
    set_field_state_data(
        atst.metadata.data,
        default_state_key="metadata_default_table",
        extra_state_key="metadata_extra_table",
        default_rows=DEFAULT_METADATA_ROWS,
    )
    set_field_state_data(
        atst.assay.data,
        default_state_key="assay_default_table",
        extra_state_key="assay_extra_table",
        default_rows=DEFAULT_ASSAY_ROWS,
    )
    st.session_state.assay_time_unit = normalize_assay_select_value(
        "time_unit",
        str(atst.assay.data.get("time_unit", "")),
    )
    st.session_state.assay_plate_format = normalize_assay_select_value(
        "plate_format",
        str(atst.assay.data.get("plate_format", "")),
    )

    layout_applied = True
    if not atst.layout.data.empty:
        layout_applied = stage_layout_merge(
            atst.layout.data,
            source="Template",
            success_message="Merged template layout.",
        )
    st.session_state.readings_table = pd.DataFrame()
    if atst.entities is None:
        st.session_state.entity_tables = {}
    else:
        st.session_state.entity_tables = {
            table_name: entity_table.data.copy()
            for table_name, entity_table in atst.entities.tables.items()
        }

    if not layout_applied:
        return f"{message} Resolve layout column conflicts below."
    return message


def _apply_single_template_to_readouts(atst: TemplateATST) -> str:
    """Apply one template payload as a baseline for every existing readout."""

    for draft in st.session_state.readout_drafts.values():
        draft.metadata = merge_field_data(
            draft.metadata, atst.metadata.data, incoming_overwrites=False
        )
        draft.assay = merge_field_data(
            draft.assay, atst.assay.data, incoming_overwrites=False
        )
        draft.layout = merge_layout_tables(
            draft.layout,
            atst.layout.data,
            plate_format=draft.assay.get("plate_format"),
        )
        for block_name in ("metadata", "assay", "layout"):
            draft.versions[block_name] = draft.versions.get(block_name, 0) + 1

    current_study = current_field_state_data(
        default_state_key="study_default_table",
        extra_state_key="study_extra_table",
        default_rows=DEFAULT_STUDY_ROWS,
        block_name="STUDY",
    )
    set_field_state_data(
        merge_field_data(current_study, atst.study.data, incoming_overwrites=False),
        default_state_key="study_default_table",
        extra_state_key="study_extra_table",
        default_rows=DEFAULT_STUDY_ROWS,
    )
    if atst.entities is not None:
        for name, table in atst.entities.tables.items():
            st.session_state.entity_tables.setdefault(name, table.data.copy())
    return (
        "Loaded single-readout template and applied it to all "
        f"{len(st.session_state.readout_drafts)} readouts. Existing device fields were preserved."
    )


def _load_multi_readout_template(atst: TemplateATST, uploaded_name: str) -> str:
    """Apply every readout from a multi-readout template."""

    existing = ordered_readouts(st.session_state.readout_drafts)
    by_id = {draft.readout_id: draft for draft in existing}
    used_keys: set[str] = set()
    next_order = max((draft.upload_order for draft in existing), default=-1) + 1
    result: dict[str, ReadoutDraft] = dict(st.session_state.readout_drafts)
    
    assert atst.readouts, 'No readouts found'
    
    for index, (readout_id, template) in enumerate(atst.readouts.items()):
        draft = by_id.get(readout_id)
        if draft is None:
            remaining = [item for item in existing if item.key not in used_keys]
            draft = remaining[0] if remaining else None
        if draft is None:
            draft = ReadoutDraft(
                key=uuid4().hex,
                readout_id=readout_id,
                upload_order=next_order + index,
                source_name=uploaded_name,
            )
            result[draft.key] = draft
        used_keys.add(draft.key)
        if not st.session_state.get("device_output_loaded"):
            draft.readout_id = readout_id
        draft.metadata = merge_field_data(
            draft.metadata, template.metadata, incoming_overwrites=not st.session_state.get("device_output_loaded")
        )
        draft.assay = merge_field_data(
            draft.assay, template.assay, incoming_overwrites=not st.session_state.get("device_output_loaded")
        )
        if not template.layout.empty:
            if draft.layout.empty or not st.session_state.get("device_output_loaded"):
                draft.layout = template.layout.copy()
            else:
                draft.layout = merge_layout_tables(
                    draft.layout,
                    template.layout,
                    plate_format=draft.assay.get("plate_format"),
                )
        for block_name in ("metadata", "assay", "layout"):
            draft.versions[block_name] = draft.versions.get(block_name, 0) + 1

    st.session_state.readout_drafts = result
    st.session_state.shared_readout_blocks = dict(atst.shared_blocks or {})
    for block_name, shared in st.session_state.shared_readout_blocks.items():
        st.session_state[f"share_{block_name}"] = shared
    st.session_state.file_name = str(
        atst.file_info.data.get("file_name") or uploaded_name
    )
    set_field_state_data(
        atst.study.data,
        default_state_key="study_default_table",
        extra_state_key="study_extra_table",
        default_rows=DEFAULT_STUDY_ROWS,
    )
    if atst.entities is not None:
        st.session_state.entity_tables.update(
            {
                name: table.data.copy()
                for name, table in atst.entities.tables.items()
            }
        )
    return f"Loaded multi-readout template with {len(atst.readouts)} readouts."


def load_template_without_overwriting(atst: TemplateATST) -> bool:
    """Merge template data into state without overwriting existing field values."""

    for block_name, default_key, extra_key, default_rows, template_data in (
        (
            "STUDY",
            "study_default_table",
            "study_extra_table",
            DEFAULT_STUDY_ROWS,
            atst.study.data,
        ),
        (
            "METADATA",
            "metadata_default_table",
            "metadata_extra_table",
            DEFAULT_METADATA_ROWS,
            atst.metadata.data,
        ),
        (
            "ASSAY",
            "assay_default_table",
            "assay_extra_table",
            DEFAULT_ASSAY_ROWS,
            atst.assay.data,
        ),
    ):
        current_data = current_field_state_data(
            default_state_key=default_key,
            extra_state_key=extra_key,
            default_rows=default_rows,
            block_name=block_name,
        )
        merged_data = merge_field_data(
            current_data,
            template_data,
            incoming_overwrites=False,
        )
        set_field_state_data(
            merged_data,
            default_state_key=default_key,
            extra_state_key=extra_key,
            default_rows=default_rows,
        )

    assay_data = current_field_state_data(
        default_state_key="assay_default_table",
        extra_state_key="assay_extra_table",
        default_rows=DEFAULT_ASSAY_ROWS,
        block_name="ASSAY",
    )
    st.session_state.assay_time_unit = normalize_assay_select_value(
        "time_unit",
        str(assay_data.get("time_unit", "")),
    )
    st.session_state.assay_plate_format = normalize_assay_select_value(
        "plate_format",
        str(assay_data.get("plate_format", "")),
    )

    layout_applied = True
    if not atst.layout.data.empty:
        layout_applied = stage_layout_merge(
            atst.layout.data,
            source="Template",
            success_message="Merged template layout.",
        )

    if atst.entities is None:
        return layout_applied

    for table_name, entity_table in atst.entities.tables.items():
        if table_name not in st.session_state.entity_tables:
            st.session_state.entity_tables[table_name] = entity_table.data.copy()

    return layout_applied


def load_device_output(uploaded_file, *, device: str) -> str:
    """Parse device output and update filename, metadata, assay, and readings.

    Args:
        uploaded_file: Streamlit uploaded raw device output.
        device: Device reader name selected in the UI.
    """

    if device not in DEVICE_READERS:
        raise ValueError(f"Unsupported device: {device}")

    parsed = DEVICE_READERS[device].read(
        uploaded_file.getvalue(),
        filename=uploaded_file.name,
    )

    st.session_state.file_name = parsed.file_name
    metadata_data = merge_field_data(
        current_field_state_data(
            default_state_key="metadata_default_table",
            extra_state_key="metadata_extra_table",
            default_rows=DEFAULT_METADATA_ROWS,
            block_name="METADATA",
        ),
        parsed.metadata,
        incoming_overwrites=True,
    )
    assay_data = merge_field_data(
        current_field_state_data(
            default_state_key="assay_default_table",
            extra_state_key="assay_extra_table",
            default_rows=DEFAULT_ASSAY_ROWS,
            block_name="ASSAY",
        ),
        parsed.assay,
        incoming_overwrites=True,
    )
    set_field_state_data(
        metadata_data,
        default_state_key="metadata_default_table",
        extra_state_key="metadata_extra_table",
        default_rows=DEFAULT_METADATA_ROWS,
    )
    set_field_state_data(
        assay_data,
        default_state_key="assay_default_table",
        extra_state_key="assay_extra_table",
        default_rows=DEFAULT_ASSAY_ROWS,
    )
    st.session_state.assay_time_unit = normalize_assay_select_value(
        "time_unit",
        assay_data.get("time_unit", ""),
    )
    st.session_state.assay_plate_format = normalize_assay_select_value(
        "plate_format",
        assay_data.get("plate_format", ""),
    )
    st.session_state.readings_table = sort_readings_columns(
        parsed.readings,
        plate_format=assay_data.get("plate_format", ""),
    )
    if parsed.layout is not None and not parsed.layout.empty:
        apply_layout_table(
            parsed.layout,
            plate_format=assay_data.get("plate_format", ""),
        )
    st.session_state.device_output_loaded = True

    return (
        f"Loaded {device} output with {len(parsed.readings)} reads "
        f"and {len(parsed.readings.columns) - 1} wells."
    )


def load_device_outputs(uploaded_files, *, device: str) -> str | list[str]:
    """Parse a batch of device outputs into stable per-readout drafts."""

    if len(uploaded_files) == 1:
        st.session_state.readout_drafts = {}
        return load_device_output(uploaded_files[0], device=device)
    if device not in DEVICE_READERS:
        raise ValueError(f"Unsupported device: {device}")

    base_metadata = current_field_state_data(
        default_state_key="metadata_default_table",
        extra_state_key="metadata_extra_table",
        default_rows=DEFAULT_METADATA_ROWS,
        block_name="METADATA",
    )
    base_assay = current_field_state_data(
        default_state_key="assay_default_table",
        extra_state_key="assay_extra_table",
        default_rows=DEFAULT_ASSAY_ROWS,
        block_name="ASSAY",
    )
    existing = ordered_readouts(st.session_state.readout_drafts)
    existing_by_id = {draft.readout_id: draft for draft in existing}
    used_existing: set[str] = set()
    drafts: dict[str, ReadoutDraft] = {}
    messages: list[str] = []
    for index, uploaded_file in enumerate(uploaded_files):
        parsed = DEVICE_READERS[device].read(
            uploaded_file.getvalue(), filename=uploaded_file.name
        )
        parsed_draft = new_readout_draft(
            parsed, upload_order=index, source_name=uploaded_file.name
        )
        draft = existing_by_id.get(parsed_draft.readout_id)
        if draft is None or draft.key in used_existing:
            remaining = [item for item in existing if item.key not in used_existing]
            draft = remaining[0] if remaining else parsed_draft
        used_existing.add(draft.key)
        reused_existing = draft is not parsed_draft

        template_metadata = draft.metadata if reused_existing else base_metadata
        template_assay = draft.assay if reused_existing else base_assay
        template_layout = (
            draft.layout.copy()
            if reused_existing and not draft.layout.empty
            else st.session_state.layout_table.copy()
        )
        draft.metadata = merge_field_data(
            template_metadata, parsed_draft.metadata, incoming_overwrites=True
        )
        draft.assay = merge_field_data(
            template_assay, parsed_draft.assay, incoming_overwrites=True
        )
        if parsed_draft.layout.empty:
            draft.layout = template_layout
        else:
            conflicts = layout_conflict_columns(
                template_layout,
                parsed_draft.layout,
                plate_format=draft.assay.get("plate_format"),
            )
            draft.layout = merge_layout_tables(
                template_layout,
                parsed_draft.layout,
                replace_columns=conflicts,
                plate_format=draft.assay.get("plate_format"),
            )
        draft.readings = parsed_draft.readings.copy()
        draft.source_name = uploaded_file.name
        draft.upload_order = index
        for block_name in ("metadata", "assay", "layout"):
            draft.versions[block_name] = draft.versions.get(block_name, 0) + 1
        drafts[draft.key] = draft
        messages.append(
            f"Loaded {uploaded_file.name} as {device}: "
            f"{len(draft.readings)} reads and "
            f"{max(len(draft.readings.columns) - 1, 0)} wells."
        )

    for draft in existing:
        if draft.key not in used_existing:
            drafts[draft.key] = draft

    st.session_state.readout_drafts = drafts
    st.session_state.file_name = "multi_readout.atst.txt"
    st.session_state.device_output_loaded = True
    st.session_state.shared_readout_blocks = {
        "metadata": False,
        "assay": False,
        "layout": False,
    }
    return messages
