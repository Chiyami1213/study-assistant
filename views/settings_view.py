"""Settings."""
import streamlit as st

import settings

OPTIONS = {
    "light": (":material/light_mode:", "Light"),
    "dark": (":material/dark_mode:", "Dark"),
    "device": (":material/desktop_windows:", "Use Device Settings"),
}


def render():
    st.title("Settings")

    st.header("Appearance")
    current = settings.get_appearance()
    with st.container(key="appearance"):
        for col, (key, (icon, label)) in zip(st.columns(3), OPTIONS.items()):
            if col.button(label, icon=icon, key=f"appearance_{key}", width="stretch",
                          type="primary" if key == current else "secondary"):
                settings.set_appearance(key)
                st.rerun()
