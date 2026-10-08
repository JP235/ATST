from __future__ import annotations

import streamlit as st
from streamlit_app.layout_editor.merge_prompt import show_layout_merge_prompt
from streamlit_app.layout_editor.state import init_state, stage_layout_merge
from streamlit_app.tables.uploads import (
    UploadedTableParseError,
    read_uploaded_layout,
)
from streamlit_app.tables.utils import PLATE_FORMAT_OPTIONS
from streamlit_app.components.layout_preview_editor import (
    layout_preview_editor,
    layout_preview_editor_mode,
    reset_layout_preview_editor_locks_on_page_change,
)
from streamlit_app.privacy import (
    expire_upload_widget,
    upload_widget_key,
)


def main() -> None:
    st.set_page_config(page_title="Layout Editor", layout="wide")
    init_state()
    st.title("Layout editor")

    editor_key = (
        "standalone_layout_preview_editor_"
        f"{st.session_state.standalone_layout_editor_version}"
    )
    reset_layout_preview_editor_locks_on_page_change("layout_editor")
    layout_editor_initial_mode = layout_preview_editor_mode(
        editor_key,
        default="layout_editor",
    )
    layout_editor_locked = layout_editor_initial_mode == "layout_editor"

    controls = st.columns([2, 1, 1], vertical_alignment="bottom")
    with controls[0]:
        uploaded_layout = st.file_uploader(
            "Upload layout CSV/TSV/TXT or ATST",
            type=["csv", "tsv", "txt"],
            key=upload_widget_key("standalone_layout_upload"),
            disabled=(
                st.session_state.get("standalone_layout_merge_pending") is not None
            ),
        )
    with controls[1]:
        st.session_state.standalone_plate_format = st.selectbox(
            "Plate format",
            PLATE_FORMAT_OPTIONS,
            index=PLATE_FORMAT_OPTIONS.index(
                st.session_state.standalone_plate_format
            ),
        )
    with controls[2]:
        st.download_button(
            "Download",
            data=st.session_state.standalone_layout_table.fillna("").to_csv(
                index=False,
                sep="\t",
            ),
            file_name=f"layout_{st.session_state.standalone_plate_format}.tsv",
            mime="text/tab-separated-values",
            use_container_width=True,
            disabled=layout_editor_locked,
            help=(
                "Apply or cancel edits before downloading the layout"
                if layout_editor_locked
                else None
            ),
        )

    if uploaded_layout is not None:
        try:
            incoming_layout = read_uploaded_layout(uploaded_layout)
        except UploadedTableParseError as exc:
            st.session_state.standalone_layout_upload_error = (
                f"Could not load layout: {exc}"
            )
        else:
            st.session_state.standalone_layout_upload_error = None
            stage_layout_merge(incoming_layout)
        expire_upload_widget("standalone_layout_upload")
        st.rerun()

    if st.session_state.standalone_layout_upload_error:
        st.error(st.session_state.standalone_layout_upload_error)

    if show_layout_merge_prompt():
        st.stop()

    st.session_state.standalone_layout_table = layout_preview_editor(
        st.session_state.standalone_layout_table,
        plate_format=st.session_state.standalone_plate_format,
        plate_formats=PLATE_FORMAT_OPTIONS,
        key=editor_key,
        initial_mode="layout_editor",
        show_full_data_table=True,
    )
