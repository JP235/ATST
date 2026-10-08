from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from streamlit.errors import StreamlitSecretNotFoundError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


_COMPONENT_NAME = "layout_preview_editor"
_COMPONENT_DEV_URL = "http://localhost:5173"

try:
    _RELEASE = bool(st.secrets["layout_preview_editor"]["release"])
except (KeyError, StreamlitSecretNotFoundError):
    _RELEASE = True

if _RELEASE:
    _COMPONENT_DIR = Path(__file__).parent / "frontend" / "build"
    logger.info(f'{_COMPONENT_DIR = }')
    _component = components.declare_component(
        _COMPONENT_NAME,
        path=str(_COMPONENT_DIR),
    )
else:
    _component = components.declare_component(
        _COMPONENT_NAME,
        url=_COMPONENT_DEV_URL,
    )

def layout_preview_editor(
    layout_df: pd.DataFrame,
    *,
    plate_format: str,
    plate_formats: list[str],
    key: str,
    initial_mode: str | None = None,
    show_full_data_table: bool = False,
) -> pd.DataFrame:
    """Render the interactive layout preview/editor component.

    Args:
        layout_df: Current layout table.
        plate_format: Active plate format, such as `96_well`.
        plate_formats: Plate format choices shown in the component.
        key: Streamlit component key.
        initial_mode: Optional starting mode for the component.
        show_full_data_table: Show the full editable table below the preview.
    """

    clean_df = layout_df.fillna("").astype(str).map(lambda value: value.strip())
    clean_df.columns = [str(column).strip() for column in layout_df.columns]

    records: list[dict[str, Any]] = clean_df.to_dict("records")  # type: ignore
    columns = [str(column) for column in clean_df.columns]
    current_mode = layout_preview_editor_mode(key, default=initial_mode or "layout_preview")
    default_value = {
        "mode": current_mode,
        "action": "sync",
        "data": records,
        "columns": columns,
        "plateFormat": plate_format,
    }
    value = _component(
        layoutData=records,
        columns=columns,
        plateFormat=plate_format,
        plateFormats=plate_formats,
        initialMode=current_mode,
        showFullDataTable=show_full_data_table,
        key=key,
        default=default_value,
    )
    mode = str(value.get("mode", "layout_preview"))
    action = str(value.get("action", "sync"))
    st.session_state[f"{key}_mode"] = mode
    st.session_state[f"{key}_action"] = action

    result_data = value["data"] if action == "apply" else records
    result = pd.DataFrame(result_data)

    applied_columns = value.get("columns") if action == "apply" else None
    if isinstance(applied_columns, list):
        result_columns = [
            str(column).strip()
            for column in applied_columns
            if str(column).strip()
        ]
    elif action == "apply":
        result_columns = [str(column) for column in result.columns]
    else:
        result_columns = columns

    if result.empty and result_columns:
        result = pd.DataFrame(columns=result_columns)
    for column in result_columns:
        if column not in result.columns:
            result[column] = ""
    extra_columns = [
        column for column in result.columns if column not in result_columns
    ]
    return result[[*result_columns, *extra_columns]].fillna("")


def layout_preview_editor_mode(key: str, *, default: str = "layout_preview") -> str:
    """Return the saved mode for a layout preview editor widget."""

    value = st.session_state.get(key)
    if isinstance(value, dict):
        mode = value.get("mode")
        if isinstance(mode, str):
            return mode
    return str(st.session_state.get(f"{key}_mode", default))


def reset_layout_preview_editor_locks_on_page_change(page_id: str) -> None:
    """Clear active edit locks when moving between Streamlit pages."""

    current_page_key = "layout_preview_editor_active_page"
    previous_page = st.session_state.get(current_page_key)
    if previous_page == page_id:
        return

    for key in list(st.session_state):
        key_text = str(key)
        value = st.session_state[key]

        if key_text.endswith("_mode") and value == "layout_editor":
            st.session_state[key] = "layout_preview"
            action_key = f"{key_text.removesuffix('_mode')}_action"
            if action_key in st.session_state:
                st.session_state[action_key] = "sync"
            continue

        if isinstance(value, dict) and value.get("mode") == "layout_editor":
            st.session_state[key] = {
                **value,
                "mode": "layout_preview",
                "action": "sync",
            }

    st.session_state[current_page_key] = page_id
