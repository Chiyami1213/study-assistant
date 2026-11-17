"""User preferences (appearance) persisted to data/settings.json and the Streamlit theme config."""
import json
import os
import shutil
import threading
import time
from datetime import datetime

from core.database import DATA_DIR

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

# Color themes: Graphite is the original look (dark surfaces in neutral grey, the blue accent). The others change the dark surfaces, the accent and the color of the primary buttons; in the light
# appearance only the accent changes. `COLOR_THEMES[key] = (name, dark surfaces, light accent variables, primary color)`.
_S = ("--s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500;--s5:#9b6bdf;--s6:#d6458f;--s7:#3fb8c9;--s8:#8fa34a;")
COLOR_THEMES = {
    "graphite": ("Graphite", None, "", "#ff4b4b"),
    "ocean": ("Ocean", "--bg:#0a1624;--bg2:#112238;--input:#172e4a;--border:#1f3a5c;--text:#e6eef8;--hover:#15293f;--active:#1b3a63;--active-text:#fff;--card:#12253b;--accent:#38a6ff;--qcard:#0e2036;--qline:#26466e;",
              "--accent:#1a7fd1;--active:#d9ecfb;", "#2f8cff"),
    "forest": ("Forest", "--bg:#0c1511;--bg2:#14241c;--input:#1b3126;--border:#243f31;--text:#e6f0ea;--hover:#172a21;--active:#1f4331;--active-text:#fff;--card:#13241b;--accent:#3ec28a;--qcard:#0f1d16;--qline:#2a4d3b;",
               "--accent:#1f9d6b;--active:#dff2e8;", "#2fae78"),
    "plum": ("Plum", "--bg:#130f1c;--bg2:#1e1730;--input:#271e3d;--border:#35294f;--text:#efe9f8;--hover:#231a38;--active:#3a2a63;--active-text:#fff;--card:#1d1530;--accent:#b07cff;--qcard:#181226;--qline:#3b2d5c;",
             "--accent:#7d4fd6;--active:#ebe2fb;", "#9b5de5"),
}

COLOR_THEMES = {k: (n, (d + _S) if d else None, light, primary) for k, (n, d, light, primary) in COLOR_THEMES.items()}          # every theme has the chart colors too

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


# Switches: the off track was a faint grey on white in Light (almost invisible); it gets a track that shows on the page and a thumb with an edge, in every appearance and theme.
SWITCH_CSS = (".stApp label:has(input[role='switch']:not(:checked)) > div:first-of-type {background-color: color-mix(in srgb, var(--text) 38%, var(--bg)) !important;}"
              ".stApp label:has(input[role='switch']) > div:first-of-type > div {box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.18), 0 1px 2px rgba(0, 0, 0, 0.3) !important;}")


def _primary_css(color):
    """The color of the primary buttons, the chosen pills, switches and tabs for a theme other than Graphite (Graphite keeps Streamlit's own red)."""
    return (f":root{{--primary:{color};}}"
            f".stApp button[data-testid^='stBaseButton-primary'] {{background: {color} !important; border-color: {color} !important;}}"
            f".stApp button[data-variant='segmented_control'][aria-checked='true'] {{border-color: {color} !important;}}"
            f".stApp button[data-variant='segmented_control'][aria-checked='true'] p {{color: {color} !important;}}"
            f".stApp [data-baseweb='tab-highlight'] {{background-color: {color} !important;}}"
            f".stApp label:has(input[role='switch']:checked) > div:first-of-type {{background-color: {color} !important;}}"
            f".stApp .stProgress [data-testid='stProgressBarFill'], .stApp [data-testid='stProgressBar'] > div > div {{background-color: {color} !important;}}")


def css_vars(choice, theme="graphite"):
    """The CSS of the appearance (light, dark or the device's) in a color theme."""
    name, dark, light, primary = COLOR_THEMES.get(theme) or COLOR_THEMES["graphite"]
    palettes = {"dark": dark or PALETTES["dark"], "light": PALETTES["light"] + light}
    extra = SWITCH_CSS + (_primary_css(primary) if theme in COLOR_THEMES and theme != "graphite" else "")
    if choice == "device":
        return (f":root{{{palettes['dark']}}}"
                f"@media (prefers-color-scheme: light){{:root{{{palettes['light']}}}}}" + (OVERRIDE if theme in COLOR_THEMES and theme != "graphite" else "") + extra)       # Graphite leaves the surfaces to Streamlit, as it always did
    return f":root{{{palettes[choice]}color-scheme:{choice};}}" + OVERRIDE + extra


def get_color_theme():
    v = _load().get("color_theme", "graphite")
    return v if v in COLOR_THEMES else "graphite"


def set_color_theme(key):
    data = _load()
    data["color_theme"] = key if key in COLOR_THEMES else "graphite"
    _save(data)


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
    "app": {"menu": "m"},                                                                                          # hide or show the menu bar
}


FEED_KINDS = ("Canvas", "Brightspace", "Google Calendar", "Other")


def list_feeds():
    """The calendar feeds the student subscribed to: [{id, name, kind, url, tasks, events, last_sync, status, seen}]."""
    return [dict(f) for f in _load().get("calendar_feeds", []) if isinstance(f, dict) and f.get("id") and f.get("url")]


def add_feed(feed_id, name, kind, url, tasks=True, events=True):
    """Keep a feed (its address is private: it is only stored in the settings file of this computer). Returns the feed."""
    data = _load()
    feeds = [f for f in data.get("calendar_feeds", []) if f.get("id") != feed_id]
    feed = {"id": feed_id, "name": (name or kind).strip() or kind, "kind": kind if kind in FEED_KINDS else "Other", "url": url.strip(), "tasks": bool(tasks), "events": bool(events),
            "last_sync": None, "status": "", "seen": []}
    data["calendar_feeds"] = feeds + [feed]
    _save(data)
    return feed


def update_feed(feed_id, **fields):
    data = _load()
    for f in data.get("calendar_feeds", []):
        if f.get("id") == feed_id:
            f.update(fields)
    _save(data)


def mark_feed_seen(feed_id, keys):
    """Remember the items of a feed that were shown to the student (so a deleted one is not brought back by the next sync)."""
    data = _load()
    for f in data.get("calendar_feeds", []):
        if f.get("id") == feed_id:
            f["seen"] = sorted(set(f.get("seen") or []) | set(keys))[-5000:]
    _save(data)


def remove_feed(feed_id):
    """Forget a feed (what it brought in stays in the planner)."""
    data = _load()
    data["calendar_feeds"] = [f for f in data.get("calendar_feeds", []) if f.get("id") != feed_id]
    _save(data)


def get_auto_sync():
    """True (the usual): the saved feeds are read again when the app opens (at most every few hours)."""
    return bool(_load().get("calendar_auto_sync", True))


def set_auto_sync(on):
    data = _load()
    data["calendar_auto_sync"] = bool(on)
    _save(data)


def get_backups_dir():
    """The folder chosen for the safety copies, or "" for the usual one (<data folder>\\Backups); see database.backups_dir."""
    value = _load().get("backups_dir")
    return value.strip() if isinstance(value, str) else ""


def set_backups_dir(path):
    data = _load()
    if (path or "").strip():
        data["backups_dir"] = path.strip()
    else:
        data.pop("backups_dir", None)
    _save(data)


def get_tutorial():
    """The state of the getting-started tutorial: {"mode": "active" | "dismissed", "welcomed": bool}, or None before the app decided (see views/tutorial.py)."""
    state = _load().get("tutorial")
    return dict(state) if isinstance(state, dict) else None


def set_tutorial(**fields):
    """Change the tutorial state (mode, welcomed); the other fields stay."""
    data = _load()
    state = dict(data.get("tutorial") or {})
    state.update(fields)
    data["tutorial"] = state
    _save(data)


def get_fit_warning():
    """True (the usual) when the Calendar warns that work does not fit before its deadline; False after the student chose Don't Show Again."""
    return bool(_load().get("fit_warning", True))


def set_fit_warning(show):
    data = _load()
    data["fit_warning"] = bool(show)
    _save(data)


PERFORMANCE_MODES = ("auto", "light", "full")


def get_performance():
    """"auto" (the usual: the app turns the effects off by itself on a slow device), "light" (always off) or "full" (always on)."""
    mode = _load().get("performance", "auto")
    return mode if mode in PERFORMANCE_MODES else "auto"


def set_performance(mode):
    data = _load()
    data["performance"] = mode if mode in PERFORMANCE_MODES else "auto"
    _save(data)


def get_menu_hidden():
    """True when the menu bar (the rail on the left) is hidden: it then shows only while the pointer rests at the left edge."""
    return bool(_load().get("menu_hidden", False))


def set_menu_hidden(hidden):
    data = _load()
    data["menu_hidden"] = bool(hidden)
    _save(data)


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


# ---------- Terms: each has a name ("Fall 2026") and its dates; one of them is the active (current) term ----------
def guess_term_name(start):
    """A name for a term from its first day: August to December is Fall, January to May Spring, June and July Summer ("Fall 2026")."""
    from datetime import date as _date
    d = start if isinstance(start, _date) else _date.fromisoformat(start)
    season = "Fall" if d.month >= 8 else "Spring" if d.month <= 5 else "Summer"
    return f"{season} {d.year}"


def _terms_of(data):
    """(terms, active id) of a settings dict. An older settings file has one set of term dates (the key "semester"): that becomes the first term."""
    if isinstance(data.get("terms"), list):
        terms = [dict(t) for t in data["terms"]]
        active = data.get("active_term")
        return terms, (active if any(t["id"] == active for t in terms) else (terms[0]["id"] if terms else None))
    sem = data.get("semester")
    if sem:
        full = {**DEFAULT_SEMESTER, **sem}
        return [{"id": 1, "name": guess_term_name(full["start"]), "start": full["start"], "end": full["end"], "exam_end": full["exam_end"]}], 1
    return [], None


def _check_term(name, start, end, exam_end, terms, ignore_id=None):
    from datetime import date as _date
    if not (name or "").strip():
        raise ValueError("A term needs a name, such as Fall 2026.")
    try:
        s, e, x = _date.fromisoformat(start), _date.fromisoformat(end), _date.fromisoformat(exam_end)
    except (TypeError, ValueError):
        raise ValueError("The term dates are not valid dates.")
    if e < s:
        raise ValueError(f"The last day of classes ({end}) is before the first day ({start}).")
    if x < e:
        raise ValueError(f"The last day of exams ({exam_end}) is before the last day of classes ({end}).")
    if any(t["name"].strip().lower() == name.strip().lower() and t["id"] != ignore_id for t in terms):
        raise ValueError(f"There is already a term called {name.strip()}.")


def _save_terms(data, terms, active):
    data["terms"], data["active_term"] = terms, active
    current = next((t for t in terms if t["id"] == active), None)
    if current:
        data["semester"] = {"start": current["start"], "end": current["end"], "exam_end": current["exam_end"]}     # what older code reads
    _save(data)


def list_terms():
    """All terms, by start date: [{id, name, start, end, exam_end}] (ISO dates)."""
    return sorted(_terms_of(_load())[0], key=lambda t: (t["start"], t["id"]))


def get_active_term():
    """The active term as a dict, or None before any term was saved."""
    terms, active = _terms_of(_load())
    return next((t for t in terms if t["id"] == active), None)


def add_term(name, start, end, exam_end, make_active=False, awake=None):
    """Add a term (dates as ISO text; `awake`: {"wake": "07:00", "bed": "23:00"} to use while it is the active term). Returns its id. The first term is active."""
    data = _load()
    terms, active = _terms_of(data)
    _check_term(name, start, end, exam_end, terms)
    new_id = max([t["id"] for t in terms] + [0]) + 1
    entry = {"id": new_id, "name": name.strip(), "start": start, "end": end, "exam_end": exam_end}
    if awake and awake.get("wake") and awake.get("bed"):
        entry["awake"] = {"wake": awake["wake"], "bed": awake["bed"]}
    terms.append(entry)
    _save_terms(data, terms, new_id if make_active or active is None else active)
    return new_id


def update_term(term_id, name, start, end, exam_end):
    data = _load()
    terms, active = _terms_of(data)
    term = next((t for t in terms if t["id"] == term_id), None)
    if term is None:
        raise ValueError("That term does not exist.")
    _check_term(name, start, end, exam_end, terms, ignore_id=term_id)
    term.update(name=name.strip(), start=start, end=end, exam_end=exam_end)
    _save_terms(data, terms, active)


def set_active_term(term_id):
    data = _load()
    terms, _ = _terms_of(data)
    if not any(t["id"] == term_id for t in terms):
        raise ValueError("That term does not exist.")
    _save_terms(data, terms, term_id)


def delete_term(term_id):
    """Remove a term. The active term can not be removed: make another one active first."""
    data = _load()
    terms, active = _terms_of(data)
    if term_id == active:
        raise ValueError("The active term can not be deleted. Make another term active first.")
    if not any(t["id"] == term_id for t in terms):
        raise ValueError("That term does not exist.")
    _save_terms(data, [t for t in terms if t["id"] != term_id], active)


def semester_set():
    """True once a term was saved (Calendar > Manage Terms or Edit Schedule). A clean install has none, so Home shows no term countdown."""
    return bool(_terms_of(_load())[0])


def get_semester():
    """The active term's dates (ISO): classes start, classes end, end of the exam period (the calendar uses these defaults until a term is saved)."""
    term = get_active_term()
    return {k: (term or DEFAULT_SEMESTER)[k] for k in DEFAULT_SEMESTER}


def set_semester(start, end, exam_end):
    """Change the dates of the active term (the first term is made, named from its first day, when there is none)."""
    term = get_active_term()
    if term is None:
        add_term(guess_term_name(start), start, end, exam_end, make_active=True)
    else:
        update_term(term["id"], term["name"], start, end, exam_end)


# ---------- Blocks of the Calendar panel: which ones are hidden, and the names and colors given to them (a block is "course:7", "task:12" or "activity:3") ----------
def _block_prefs(data):
    prefs = data.get("calendar_blocks")
    return prefs if isinstance(prefs, dict) else {}


def get_hidden_blocks():
    return set(_block_prefs(_load()).get("hidden", []))


def set_block_hidden(ref, hidden=True):
    data = _load()
    prefs = _block_prefs(data)
    hidden_set = set(prefs.get("hidden", []))
    (hidden_set.add if hidden else hidden_set.discard)(ref)
    data["calendar_blocks"] = {**prefs, "hidden": sorted(hidden_set)}
    _save(data)


def get_block_names():
    """{ref: name} the Calendar shows instead of the real name (a course renamed only on the Calendar)."""
    return dict(_block_prefs(_load()).get("names", {}))


def set_block_name(ref, name):
    """Give a block another name on the Calendar; an empty name goes back to the real one."""
    data = _load()
    prefs = _block_prefs(data)
    names = dict(prefs.get("names", {}))
    if (name or "").strip():
        names[ref] = name.strip()
    else:
        names.pop(ref, None)
    data["calendar_blocks"] = {**prefs, "names": names}
    _save(data)


def forget_block(ref):
    """Drop everything saved for a block that was deleted (hidden, name, color, order)."""
    data = _load()
    prefs = _block_prefs(data)
    data["calendar_blocks"] = {"hidden": [r for r in prefs.get("hidden", []) if r != ref], "order": [r for r in prefs.get("order", []) if r != ref],
                               "names": {k: v for k, v in prefs.get("names", {}).items() if k != ref}, "colors": {k: v for k, v in prefs.get("colors", {}).items() if k != ref}}
    _save(data)


def get_block_order():
    """The refs of the Calendar panel's blocks in the order the user dragged them."""
    return list(_block_prefs(_load()).get("order", []))


def set_block_order(refs):
    """Save the order of one group of blocks (the refs in their new order). The other groups keep theirs: only the relative order inside a group matters."""
    data = _load()
    prefs = _block_prefs(data)
    refs = [r for r in dict.fromkeys(refs) if isinstance(r, str) and r]
    keep = [r for r in prefs.get("order", []) if r not in set(refs)]
    data["calendar_blocks"] = {**prefs, "order": keep + refs}
    _save(data)


def get_block_colors():
    return dict(_block_prefs(_load()).get("colors", {}))


def set_block_color(ref, color):
    data = _load()
    prefs = _block_prefs(data)
    colors = dict(prefs.get("colors", {}))
    if color:
        colors[ref] = color
    else:
        colors.pop(ref, None)
    data["calendar_blocks"] = {**prefs, "colors": colors}
    _save(data)


HOUR_PX_DEFAULT, HOUR_PX_RANGE = 56, (32, 140)
PANEL_WIDTH_DEFAULT, PANEL_WIDTH_RANGE = 260, (180, 520)


def get_calendar_hour_px():
    """How tall one hour is in the calendar grid (pixels); 0 or nothing saved = the usual height."""
    try:
        px = int(_load().get("calendar_hour_px") or HOUR_PX_DEFAULT)
    except (TypeError, ValueError):
        px = HOUR_PX_DEFAULT
    return max(HOUR_PX_RANGE[0], min(HOUR_PX_RANGE[1], px))


def set_calendar_hour_px(px):
    data = _load()
    px = int(px or 0)
    if px <= 0:
        data.pop("calendar_hour_px", None)
    else:
        data["calendar_hour_px"] = max(HOUR_PX_RANGE[0], min(HOUR_PX_RANGE[1], px))
    _save(data)


def get_calendar_panel_width():
    try:
        px = int(_load().get("calendar_panel_width") or PANEL_WIDTH_DEFAULT)
    except (TypeError, ValueError):
        px = PANEL_WIDTH_DEFAULT
    return max(PANEL_WIDTH_RANGE[0], min(PANEL_WIDTH_RANGE[1], px))


def set_calendar_panel_width(px):
    """The width of the left panel (pixels); 0 goes back to the usual width."""
    data = _load()
    px = int(px or 0)
    if px <= 0:
        data.pop("calendar_panel_width", None)
    else:
        data["calendar_panel_width"] = max(PANEL_WIDTH_RANGE[0], min(PANEL_WIDTH_RANGE[1], px))
    _save(data)


# ---------- Library: the folders the software reads files from (Update), and the files it has already imported from them ----------
def get_import_folder(course_id=None):
    """The folder to update the Library from: the one set for this course (when a course is given and has its own), else the general one. "" when none is set."""
    folders = _load().get("import_folders") or {}
    return (folders.get(str(course_id)) if course_id else None) or folders.get("all") or ""


def get_own_import_folder(course_id=None):
    """The folder set for exactly this course (or the general one when no course is given); "" when it has none."""
    return (_load().get("import_folders") or {}).get(str(course_id) if course_id else "all") or ""


def set_import_folder(path, course_id=None):
    data = _load()
    folders = dict(data.get("import_folders") or {})
    key = str(course_id) if course_id else "all"
    if (path or "").strip():
        folders[key] = path.strip()
    else:
        folders.pop(key, None)
    data["import_folders"] = folders
    _save(data)


def get_import_sources():
    """{path of a file read from a folder: {"size", "mtime", "book_id"}}: what an Update has imported already."""
    return dict(_load().get("import_sources") or {})


def remember_import_source(key, size, mtime, book_id):
    data = _load()
    sources = dict(data.get("import_sources") or {})
    sources[key] = {"size": size, "mtime": mtime, "book_id": book_id}
    data["import_sources"] = sources
    _save(data)


def get_calendar_panel_open():
    """Is the panel of blocks on the left of the Calendar shown (True) or folded away (False)?"""
    return bool(_load().get("calendar_panel_open", True))


def set_calendar_panel_open(is_open):
    data = _load()
    data["calendar_panel_open"] = bool(is_open)
    _save(data)


def get_outline_state(course_id, part=None):
    """How a course's outline was made: {source: "syllabus" | "titles" | "manual", sig: ...}; {} when it was never set."""
    return _load().get("outlines", {}).get(f"{course_id}:{part}" if part else str(course_id), {})


def set_outline_state(course_id, source, sig="", part=None):
    data = _load()
    data.setdefault("outlines", {})[f"{course_id}:{part}" if part else str(course_id)] = {"source": source, "sig": sig}
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
