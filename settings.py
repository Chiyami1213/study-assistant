"""User preferences (appearance) persisted to data/settings.json and the Streamlit theme config."""
import json

from database import BASE_DIR

SETTINGS_FILE = BASE_DIR / "data" / "settings.json"

THEMES = ("light", "dark", "device")

# CSS variables for the app's own UI (sidebar, cards) and the Streamlit override palette
PALETTES = {
    "dark": "--bg:#0e1117;--bg2:#1b1c20;--input:#262730;--border:#2a2c33;--text:#e8e9ec;--hover:#23252c;"
            "--active:#252d42;--active-text:#fff;--card:#22242a;--accent:#4c8dff;",
    "light": "--bg:#ffffff;--bg2:#f4f5f7;--input:#eef0f4;--border:#d9dce3;--text:#2b2d33;--hover:#e9ecf1;"
             "--active:#dfe8fb;--active-text:#111;--card:#f5f6f8;--accent:#2f6fe0;",
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
.stApp [data-testid="stBaseButton-secondary"], .stApp [data-testid="stDownloadButton"] button {
    background: var(--bg) !important; border: 1px solid var(--border) !important;}
.stApp [data-testid="stProgress"] > div > div {background: var(--border) !important;}
.stApp [data-testid="stCode"], .stApp pre {background: var(--input) !important;}
[data-baseweb="popover"] *, [data-baseweb="menu"] {background-color: var(--bg2) !important; color: var(--text) !important;}
[data-testid="stVerticalBlockBorderWrapper"] {border-color: var(--border) !important;}
[data-testid="stTabs"] button p {color: var(--text) !important;}
"""


def css_vars(choice):
    if choice == "device":
        return (f":root{{{PALETTES['dark']}}}"
                f"@media (prefers-color-scheme: light){{:root{{{PALETTES['light']}}}}}")
    return f":root{{{PALETTES[choice]}color-scheme:{choice};}}" + OVERRIDE


def get_appearance():
    try:
        v = json.loads(SETTINGS_FILE.read_text()).get("appearance", "device")
        return v if v in THEMES else "device"
    except Exception:
        return "device"


def set_appearance(choice):
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps({"appearance": choice}))
