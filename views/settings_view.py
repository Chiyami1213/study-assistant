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

    st.header("Keyboard Shortcuts")
    st.caption("Type a key, such as d, or a combination, such as ctrl+z. Esc is the Escape key. A shortcut works when you are not typing in a box.")
    _keys_section("Homework and Exam Reader", "reader", [
        ("draw", "Drawing Mode (On and Off)", "turns drawing mode on; pressing it again turns it off"),
        ("pen", "Pen", "the pen, while drawing"), ("highlighter", "Highlighter", "the highlighter, while drawing"),
        ("eraser", "Eraser", "the eraser, while drawing"), ("undo", "Undo", "undoes the last drawing, while drawing"),
        ("leave", "Leave Drawing Mode", "turns drawing mode off")])
    _keys_section("Note Reader", "notes", [
        ("find", "Find in the Page", "opens the find bar of the note under the pointer"),
        ("leave_full", "Leave Full Screen", "returns from the full screen note to the windows")])


_MODIFIERS = ("ctrl", "alt", "shift")
_NAMED = ("esc", "enter", "tab", "space", "backspace", "delete", "home", "end", "pageup", "pagedown", "arrowup", "arrowdown", "arrowleft", "arrowright") + \
    tuple(f"f{i}" for i in range(1, 13))


def _normal_key(text):
    """The binding as the page script writes it ('ctrl+z'), or None when it is not a key."""
    t = (text or "").strip().lower().replace(" ", "").replace("control", "ctrl").replace("escape", "esc").replace("cmd", "ctrl")
    parts = t.split("+") if t != "+" else ["+"]
    if t.endswith("++"):
        parts = t[:-2].split("+") + ["+"]
    key, mods = parts[-1], parts[:-1]
    if not key or any(m not in _MODIFIERS for m in mods) or len(set(mods)) != len(mods) or not (len(key) == 1 or key in _NAMED):
        return None
    return "+".join([m for m in _MODIFIERS if m in mods] + [key])


def _keys_section(title, group, rows):
    """A group of key binding boxes for one reader, saved as they are changed."""
    st.subheader(title)
    saved = settings.get_keys()[group]
    with st.container(key=f"keys_{group}"):
        cols = st.columns(3)
        entered = {}
        for i, (action, label, tip) in enumerate(rows):
            entered[action] = cols[i % 3].text_input(label, saved[action], key=f"key_{group}_{action}", help=tip, max_chars=16)
        fixed = {a: _normal_key(v) for a, v in entered.items()}
        bad = [label for (a, label, _), v in zip(rows, fixed.values()) if v is None]
        if bad:
            st.error("Not a key: " + ", ".join(bad) + ". Use a single key such as d, or a combination such as ctrl+z.")
        used = [v for v in fixed.values() if v]
        if len(used) != len(set(used)):
            st.warning("The same key is used for more than one action in this reader.")
        if not bad and fixed != saved:
            settings.set_keys(group, **fixed)
            st.rerun()
        if st.button("Reset to Defaults", key=f"keys_reset_{group}", help=f"puts the {title.lower()} shortcuts back as they were"):
            settings.reset_keys(group)
            for action, *_ in rows:
                st.session_state.pop(f"key_{group}_{action}", None)
            st.rerun()
