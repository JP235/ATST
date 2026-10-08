from __future__ import annotations

import streamlit as st


def upload_widget_key(name: str) -> str:
    """Return the current disposable key for a file uploader."""

    version = st.session_state.get(f"{name}_version", 0)
    return f"{name}_{version}"


def expire_upload_widget(name: str) -> None:
    """Give an uploader a new identity so Streamlit releases its raw file."""

    version_key = f"{name}_version"
    st.session_state[version_key] = st.session_state.get(version_key, 0) + 1
