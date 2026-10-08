from __future__ import annotations

import pandas as pd
import streamlit as st

from streamlit_app.tables.layout import (
    layout_conflict_columns,
    merge_layout_tables,
    sort_layout_rows,
)


def init_state() -> None:
    if "standalone_layout_table" not in st.session_state:
        st.session_state.standalone_layout_table = pd.DataFrame(
            columns=["well_loc", "type"]
        )
    if "standalone_plate_format" not in st.session_state:
        st.session_state.standalone_plate_format = "96_well"
    if "standalone_layout_editor_version" not in st.session_state:
        st.session_state.standalone_layout_editor_version = 0
    if "standalone_layout_merge_pending" not in st.session_state:
        st.session_state.standalone_layout_merge_pending = None
    if "standalone_layout_upload_error" not in st.session_state:
        st.session_state.standalone_layout_upload_error = None


def stage_layout_merge(incoming_layout: pd.DataFrame) -> bool:
    base_layout = st.session_state.standalone_layout_table.copy()
    plate_format = st.session_state.standalone_plate_format
    incoming_layout = sort_layout_rows(incoming_layout, plate_format=plate_format)
    conflict_columns = layout_conflict_columns(
        base_layout,
        incoming_layout,
        plate_format=plate_format,
    )
    if conflict_columns:
        st.session_state.standalone_layout_merge_pending = {
            "base": base_layout,
            "incoming": incoming_layout.copy(),
            "conflicts": conflict_columns,
            "decisions": {},
            "plate_format": plate_format,
        }
        return False

    st.session_state.standalone_layout_table = merge_layout_tables(
        base_layout,
        incoming_layout,
        plate_format=plate_format,
    )
    st.session_state.standalone_layout_merge_pending = None
    st.session_state.standalone_layout_editor_version += 1
    return True


def next_layout_merge_conflict() -> str | None:
    pending = st.session_state.get("standalone_layout_merge_pending")
    if not pending:
        return None

    decisions = pending.get("decisions", {})
    for column in pending.get("conflicts", []):
        if column not in decisions:
            return column
    return None


def resolve_layout_merge_conflict(column: str, *, replace: bool) -> bool:
    pending = st.session_state.get("standalone_layout_merge_pending")
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
        st.session_state.standalone_layout_merge_pending = pending
        return False

    replace_columns = [
        conflict
        for conflict, should_replace in decisions.items()
        if should_replace
    ]
    st.session_state.standalone_layout_table = merge_layout_tables(
        pending["base"],
        pending["incoming"],
        replace_columns=replace_columns,
        plate_format=pending.get("plate_format"),
    )
    st.session_state.standalone_layout_merge_pending = None
    st.session_state.standalone_layout_editor_version += 1
    return True


def cancel_layout_merge() -> None:
    st.session_state.standalone_layout_merge_pending = None
