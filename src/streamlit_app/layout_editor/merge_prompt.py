from __future__ import annotations

import streamlit as st

from streamlit_app.layout_editor.state import (
    cancel_layout_merge,
    next_layout_merge_conflict,
    resolve_layout_merge_conflict,
)
from streamlit_app.tables.layout import column_value_count


def show_layout_merge_prompt() -> bool:
    pending = st.session_state.get("standalone_layout_merge_pending")
    if not pending:
        return False

    column = next_layout_merge_conflict()
    if column is None:
        cancel_layout_merge()
        return False

    conflicts = list(pending.get("conflicts", []))
    decisions = dict(pending.get("decisions", {}))
    position = len(decisions) + 1
    current_count = column_value_count(pending["base"], column)
    incoming_count = column_value_count(pending["incoming"], column)

    st.warning(
        f"Uploaded layout includes `{column}`, which already has values "
        "in the current layout."
    )
    st.caption(
        f"Column {position} of {len(conflicts)}. "
        f"Current filled cells: {current_count}. "
        f"Incoming filled cells: {incoming_count}."
    )
    replace_col, keep_col, cancel_col = st.columns(3)
    if replace_col.button(
        "Replace column",
        key=f"standalone_layout_merge_replace_{position}_{column}",
        use_container_width=True,
    ):
        resolve_layout_merge_conflict(column, replace=True)
        st.rerun()
    if keep_col.button(
        "Keep current",
        key=f"standalone_layout_merge_keep_{position}_{column}",
        use_container_width=True,
    ):
        resolve_layout_merge_conflict(column, replace=False)
        st.rerun()
    if cancel_col.button(
        "Cancel merge",
        key=f"standalone_layout_merge_cancel_{position}_{column}",
        use_container_width=True,
    ):
        cancel_layout_merge()
        st.rerun()

    return True
