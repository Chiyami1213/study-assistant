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

    st.header("Eye Rest")
    st.caption("A reminder to look away from the screen after every 20 minutes of studying.")
    eye = settings.get_eye_rest()
    with st.container(key="eye_rest_settings"):
        cols = st.columns(4)
        rest = cols[0].number_input("Rest Length (Seconds)", 5, 300, eye["rest_seconds"], 5, key="eye_rest_seconds",
                                    help="how long each eye rest lasts")
        skips = cols[1].number_input("Skips Allowed in a Row", 0, 10, eye["max_skips"], 1, key="eye_max_skips",
                                     help="after this many skipped rests in a row, the next reminder becomes a required rest")
        minutes = cols[2].number_input("Required Rest (Minutes)", 1, 60, eye["required_minutes"], 1, key="eye_required_minutes",
                                       help="how long the required rest lasts; it cannot be skipped")
        with cols[3]:
            st.markdown("<div style='height:1.7rem'></div>", unsafe_allow_html=True)
            sound = st.toggle("Sound", eye["sound"], key="eye_sound", help="a short beep when a rest starts and ends")
        new = {"rest_seconds": int(rest), "max_skips": int(skips), "required_minutes": int(minutes), "sound": bool(sound)}
        if new != {k: eye[k] for k in new}:
            settings.set_eye_rest(**new)
            st.rerun()
