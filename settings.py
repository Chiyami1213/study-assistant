"""User preferences (appearance) persisted to data/settings.json and the Streamlit theme config."""
import json
import os
import shutil
import threading
import time
from datetime import datetime

from database import DATA_DIR

SETTINGS_FILE = DATA_DIR / "settings.json"
SETTINGS_BACKUP = DATA_DIR / "settings.json.bak"

THEMES = ("light", "dark", "device")

# CSS variables for the app's own UI (sidebar, cards) and the Streamlit override palette
PALETTES = {
    "dark": "--bg:#0e1117;--bg2:#1b1c20;--input:#262730;--border:#2a2c33;--text:#e8e9ec;--hover:#23252c;"
            "--active:#252d42;--active-text:#fff;--card:#22242a;--accent:#4c8dff;--qcard:#141b2a;--qline:#2c3550;"
            "--s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500;--s5:#9b6bdf;--s6:#d6458f;--s7:#3fb8c9;--s8:#8fa34a;",
    "light": "--bg:#ffffff;--bg2:#f4f5f7;--input:#eef0f4;--border:#d9dce3;--text:#2b2d33;--hover:#e9ecf1;"
             "--active:#dfe8fb;--active-text:#111;--card:#f5f6f8;--accent:#2f6fe0;--qcard:#f4f6fb;--qline:#d3d9e6;"
             "--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--s4:#eda100;--s5:#7a4fc4;--s6:#c2337a;--s7:#1f9db0;--s8:#6f8530;",
}

# Streamlit has no runtime theme API, so explicit Light/Dark are applied by overriding its surfaces.
OVERRIDE = """
.stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {background: var(--bg) !important;}
.stApp, .stApp p, .stApp label, .stApp li, .stApp h1, .stApp h2, .stApp h3, .stApp h4,
.stApp [data-testid="stMetricValue"], .stApp [data-testid="stMetricLabel"],
.stApp [data-testid="stWidgetLabel"] p, .stApp button p {color: var(--text) !important;}
.stApp [data-baseweb="input"], .stApp [data-baseweb="base-input"], .stApp [data-baseweb="textarea"],
.stApp [data-baseweb="select"] > div, .stApp textarea, .stApp input {
    background: var(--input) !important; color: var(--text) !important;}
.stApp button[data-testid^="stBaseButton-secondary"], .stApp [data-testid="stDownloadButton"] button,
.stApp [data-testid="stFormSubmitButton"] button {
    background: var(--bg) !important; border: 1px solid var(--border) !important;}
.stApp [data-testid="stProgressBarTrack"] {background: var(--border) !important;}
.stApp [data-testid="stCode"], .stApp pre {background: var(--input) !important;}
[data-baseweb="popover"] *, [data-baseweb="menu"] {background-color: var(--bg2) !important; color: var(--text) !important;}
[data-testid="stVerticalBlockBorderWrapper"] {border-color: var(--border) !important;}
[data-testid="stTabs"] button p {color: var(--text) !important;}
/* filter pills (segmented controls) and primary buttons follow the explicit theme */
.stApp button[data-variant="segmented_control"][aria-checked="false"] {background: var(--bg) !important; border-color: var(--border) !important;}
.stApp button[data-variant="segmented_control"][aria-checked="false"] p {color: var(--text) !important;}
.stApp button[data-testid^="stBaseButton-primary"] p {color: #fff !important;}
/* the whole select box (including the arrow part) follows the theme */
/* text, number, date and select frames: the whole frame (not just the inner field) follows the theme,
   in the page and in pop-up windows */
:is(.stApp, [role="dialog"]) :is([data-testid="stTextInputRootElement"], [data-testid="stNumberInputContainer"],
    [data-testid="stSelectbox"] [role="group"], [data-testid="stMultiSelect"] [role="group"],
    [data-testid="stMultiSelect"] [data-baseweb="select"] > div, [data-testid="stTextAreaRootElement"], [data-testid="stDateInputField"], [data-testid="stFileUploaderDropzone"]) {
    background: var(--input) !important; border-color: var(--border) !important;}
:is(.stApp, [role="dialog"]) :is([data-testid="stSelectbox"], [data-testid="stMultiSelect"]) :is(button, button svg) {color: var(--text) !important;}
/* time pickers and any other inputs inside pop-up windows follow the theme */
[role="dialog"] [data-baseweb="input"], [role="dialog"] [data-baseweb="base-input"], [role="dialog"] input {
    background: var(--input) !important; color: var(--text) !important; border-color: var(--border) !important;}
[role="dialog"] [data-testid="stTimeInput"] svg {color: var(--text) !important;}
[data-testid="stTimeInputTimeDisplay"] {background: var(--input) !important; color: var(--text) !important;}
/* placeholder text and the pop-up close button stay readable on the themed surface */
:is(.stApp, [role="dialog"]) :is(input, textarea)::placeholder {color: #8b90a0 !important; opacity: 1 !important;}
[role="dialog"] button[aria-label="Close"], [role="dialog"] button[aria-label="Close"] svg {color: var(--text) !important;}
/* disabled buttons keep a visible gray edge */
:is(.stApp, [role="dialog"]) button:disabled {border: 1px solid var(--border) !important; background: transparent !important;
    opacity: 0.7;}
:is(.stApp, [role="dialog"]) button:disabled p {color: var(--text) !important;}
/* select dropdown lists render outside .stApp in their own virtual list */
[data-testid="stSelectboxVirtualDropdown"] {background: var(--bg2) !important;}
[data-testid="stSelectboxVirtualDropdown"] [role="option"] {color: var(--text) !important;}
[data-testid="stSelectboxVirtualDropdown"] [role="option"]:hover,
[data-testid="stSelectboxVirtualDropdown"] [role="option"][aria-selected="true"] {background: var(--hover) !important;}
/* only one highlighted row: while the mouse is on another option, the selected one loses its highlight */
[data-testid="stSelectboxVirtualDropdown"]:has([role="option"]:hover) [role="option"][aria-selected="true"]:not(:hover) {
    background: transparent !important;}
/* the selected Light/Dark/Device card is a primary button on a light tint: keep its text dark */
.stApp .st-key-appearance button[data-testid^="stBaseButton-primary"] p {color: var(--active-text) !important;}
/* dialogs render outside .stApp, so they need their own filter-pill rules */
[role="dialog"] button[data-variant="segmented_control"][aria-checked="false"] {background: var(--bg2) !important; border-color: var(--border) !important;}
[role="dialog"] button[data-variant="segmented_control"][aria-checked="false"] p {color: var(--text) !important;}
[role="dialog"] {background: var(--bg2) !important;}
[role="dialog"] p, [role="dialog"] label, [role="dialog"] h2, [role="dialog"] span {color: var(--text) !important;}
[role="dialog"] input, [role="dialog"] [data-baseweb="select"] > div, [role="dialog"] [data-testid="stFileUploaderDropzone"] {
    background: var(--input) !important; color: var(--text) !important;}
[role="dialog"] button[data-testid^="stBaseButton-secondary"] {background: var(--bg2) !important; border: 1px solid var(--border) !important;}
"""


def css_vars(choice):
    if choice == "device":
        return (f":root{{{PALETTES['dark']}}}"
                f"@media (prefers-color-scheme: light){{:root{{{PALETTES['light']}}}}}")
    return f":root{{{PALETTES[choice]}color-scheme:{choice};}}" + OVERRIDE


def _read(path):
    """The parsed file, None when it is missing or cannot be read (another copy of the app may be writing it at that moment: try again)."""
    for _ in range(4):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except Exception:
            time.sleep(0.05)
    return None


def _load():
    """All settings. A file that cannot be read falls back to the last good copy (settings.json.bak), never to an empty set that a save would
    then write over everything."""
    data = _read(SETTINGS_FILE)
    if data is None and SETTINGS_FILE.exists() and SETTINGS_FILE.stat().st_size > 2:
        data = _read(SETTINGS_BACKUP)
    return data if isinstance(data, dict) else {}


def _save(data):
    """Written to a temporary file and moved into place, so a reader never sees half a file; the previous good file is kept as .bak."""
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = SETTINGS_FILE.with_name(f"settings.{os.getpid()}.{threading.get_ident()}.tmp")       # one per writer
    tmp.write_text(json.dumps(data), encoding="utf-8")
    try:
        if _read(SETTINGS_FILE) is not None:
            shutil.copyfile(SETTINGS_FILE, SETTINGS_BACKUP)
    except OSError:
        pass
    for attempt in range(8):                       # on Windows the move fails while another reader has the file open for a moment
        try:
            os.replace(tmp, SETTINGS_FILE)
            return
        except PermissionError:
            time.sleep(0.03 * (attempt + 1))
    SETTINGS_FILE.write_text(json.dumps(data), encoding="utf-8")
    tmp.unlink(missing_ok=True)


def get_appearance():
    v = _load().get("appearance", "device")
    return v if v in THEMES else "device"


def set_appearance(choice):
    data = _load()
    data["appearance"] = choice
    _save(data)


# Key bindings, one group per reader. A binding is a key such as "d", or a combination such as "ctrl+z"; "esc" is the Escape key.
DEFAULT_KEYS = {
    "reader": {"draw": "d", "pen": "p", "highlighter": "h", "eraser": "e", "undo": "ctrl+z", "leave": "esc"},     # homework and exam PDFs
    "notes": {"find": "ctrl+f", "leave_full": "esc"},                                                              # the Note Reader
}


def get_keys():
    saved = _load().get("keys", {})
    return {g: {a: (saved.get(g, {}).get(a) or d) for a, d in acts.items()} for g, acts in DEFAULT_KEYS.items()}


def set_keys(group, **values):
    data = _load()
    keys = data.get("keys", {})
    keys[group] = {**get_keys()[group], **values}
    data["keys"] = keys
    _save(data)


def reset_keys(group):
    data = _load()
    data.setdefault("keys", {}).pop(group, None)
    _save(data)


def get_backup():
    """{dir: where the Library backup is kept, sources: [folders the original files are kept in], last: time of the last backup}"""
    return _load().get("backup", {})


def set_backup(**values):
    data = _load()
    data["backup"] = {**data.get("backup", {}), **values}
    _save(data)


def get_recent_courses():
    """When each course page was last opened: {course id (str): ISO time}."""
    return _load().get("recent_courses", {})


def touch_course(course_id):
    data = _load()
    recent = data.get("recent_courses", {})
    recent[str(course_id)] = datetime.now().isoformat(timespec="seconds")
    data["recent_courses"] = recent
    _save(data)


DEFAULT_EYE_REST = {"rest_seconds": 20, "sound": True, "max_skips": 3, "required_minutes": 5}


def get_eye_rest():
    """Eye rest reminders: seconds of rest each time, sound on/off, skips allowed in a row, length (minutes) of the required rest after that."""
    saved = _load().get("eye_rest", {})
    out = dict(DEFAULT_EYE_REST)
    for k, v in saved.items():
        if k in out and type(v) is type(out[k]):
            out[k] = v
    return out


def set_eye_rest(**values):
    data = _load()
    data["eye_rest"] = {**get_eye_rest(), **values}
    _save(data)


DEFAULT_SEMESTER = {"start": "2026-08-24", "end": "2026-12-08", "exam_end": "2026-12-18"}


def get_semester():
    """Term dates (ISO): classes start, classes end, end of the exam period."""
    sem = _load().get("semester", {})
    return {k: sem.get(k, v) for k, v in DEFAULT_SEMESTER.items()}


def set_semester(start, end, exam_end):
    data = _load()
    data["semester"] = {"start": start, "end": end, "exam_end": exam_end}
    _save(data)


def get_collapsed():
    """Sidebar sections the user folded (remembered between sessions)."""
    return set(_load().get("collapsed_sections", []))


def set_collapsed(sections):
    data = _load()
    data["collapsed_sections"] = sorted(sections)
    _save(data)


def get_lab():
    """Lab page state: window order, open reference file and page per file, open note."""
    return _load().get("lab", {})


def set_lab(lab):
    data = _load()
    data["lab"] = lab
    _save(data)
