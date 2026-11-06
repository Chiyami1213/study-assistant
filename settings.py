"""User preferences (appearance) persisted to data/settings.json and the Streamlit theme config."""
import json

from database import BASE_DIR

SETTINGS_FILE = BASE_DIR / "data" / "settings.json"

THEMES = ("light", "dark", "device")

# CSS variables for the app's own UI (sidebar, cards) and the Streamlit override palette
PALETTES = {
    "dark": "--bg:#0e1117;--bg2:#1b1c20;--input:#262730;--border:#2a2c33;--text:#e8e9ec;--hover:#23252c;"
            "--active:#252d42;--active-text:#fff;--card:#22242a;--accent:#4c8dff;--qcard:#141b2a;--qline:#2c3550;"
            "--s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500;",
    "light": "--bg:#ffffff;--bg2:#f4f5f7;--input:#eef0f4;--border:#d9dce3;--text:#2b2d33;--hover:#e9ecf1;"
             "--active:#dfe8fb;--active-text:#111;--card:#f5f6f8;--accent:#2f6fe0;--qcard:#f4f6fb;--qline:#d3d9e6;"
             "--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--s4:#eda100;",
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


def _load():
    try:
        return json.loads(SETTINGS_FILE.read_text())
    except Exception:
        return {}


def _save(data):
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(data))


def get_appearance():
    v = _load().get("appearance", "device")
    return v if v in THEMES else "device"


def set_appearance(choice):
    data = _load()
    data["appearance"] = choice
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
