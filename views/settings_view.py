"""Settings."""
import sys
from pathlib import Path

import streamlit as st

import settings

SECTIONS = ["Appearance", "Eye Rest", "Study Planner", "Backup", "Keyboard Shortcuts", "Help", "Report an Issue", "Danger Zone", "About"]


def _slug(name):
    return name.lower().replace(" ", "-")


def _section(name):
    """A section heading the top bar can jump to."""
    st.header(name, anchor=_slug(name))


def _jump_bar():
    """The bar at the top of the page: one link for each section."""
    links = "".join(f'<a href="#{_slug(n)}" data-jump="{_slug(n)}"{" class=on" if i == 0 else ""}>{n}</a>' for i, n in enumerate(SECTIONS))
    with st.container(key="settings_nav"):
        st.markdown(f'<nav class="set-nav" aria-label="Sections of this page">{links}</nav>', unsafe_allow_html=True)


OPTIONS = {
    "light": (":material/light_mode:", "Light"),
    "dark": (":material/dark_mode:", "Dark"),
    "device": (":material/desktop_windows:", "Use Device Settings"),
}


def render():
    st.title("Settings")
    _jump_bar()

    _section("Appearance")
    current = settings.get_appearance()
    with st.container(key="appearance"):
        for col, (key, (icon, label)) in zip(st.columns(3), OPTIONS.items()):
            if col.button(label, icon=icon, key=f"appearance_{key}", width="stretch",
                          type="primary" if key == current else "secondary"):
                settings.set_appearance(key)
                st.rerun()

    hidden = settings.get_menu_hidden()
    if st.toggle("Hide the Menu Bar", hidden, help="hides the menu bar on the left so the page uses the whole window; pointing at the left edge shows it, and the menu bar key brings it back"
                 ) != hidden:
        settings.set_menu_hidden(not hidden)
        st.rerun()

    _section("Eye Rest")
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

    _planner_section()
    _backup_section()
    _section("Keyboard Shortcuts")
    st.caption("Type a key, such as d, or a combination, such as ctrl+z. Esc is the Escape key. A shortcut works when you are not typing in a box. "
               "These keys are fixed: F2 saves a screenshot of the app window, F5 refreshes the page (Ctrl + F5 loads it again), F11 turns full screen on and off, and while the menu bar is shown a letter opens a page (h Home, a Calendar, l Library, n Note Reader, c Courses, s Settings).")
    _keys_section("Homework and Exam Reader", "reader", [
        ("draw", "Drawing Mode (On and Off)", "turns drawing mode on; pressing it again turns it off"),
        ("pen", "Pen", "the pen, while drawing"), ("highlighter", "Highlighter", "the highlighter, while drawing"),
        ("eraser", "Eraser", "the eraser, while drawing"), ("undo", "Undo", "undoes the last drawing, while drawing"),
        ("leave", "Leave Drawing Mode", "turns drawing mode off")])
    _keys_section("Menu Bar", "app", [
        ("menu", "Hide or Show the Menu Bar", "hides the menu bar so the page uses the whole window; pointing at the left edge shows it, and pressing the key again brings it back")])
    _keys_section("Note Reader", "notes", [
        ("find", "Find in the Page", "opens the find bar of the note under the pointer"),
        ("leave_full", "Leave Full Screen", "returns from the full screen note to the windows")])
    _help_section()
    _report_section()
    _danger_zone()
    _section("About")
    import helpinfo
    from version import VERSION
    st.caption(f"Study Assistant version {VERSION} · [Project page on GitHub]({helpinfo.REPO_URL})")


def _browse(key, add):
    """Button callback: open the folder window; the chosen folder replaces the text in `key`, or (add) is added as a new line."""
    import folderpick
    current = st.session_state.get(key, "")
    last_line = (current.splitlines() or [""])[-1] if add else current
    chosen = folderpick.pick(last_line, "Choose a Folder")
    if not chosen:
        return
    if add:
        lines = [s.strip() for s in current.splitlines() if s.strip()]
        if chosen not in lines:
            lines.append(chosen)
        chosen = "\n".join(lines)
    st.session_state[key] = chosen


def _backup_section():
    """Where the Library is backed up, the folders the original files live in, Back Up Now and the two ways to restore; then Export and Import."""
    import libbackup
    _section("Backup")
    st.caption("Keeps a copy of every Library file, what each one is, the database and the settings in a folder you choose, so the Library can be "
               "brought back quickly if it is ever lost. The folders where you keep the original files are remembered too: files that are missing "
               "can be found again there by their size and content. Nothing in your own folders is ever changed or deleted.")
    cfg = settings.get_backup()
    row = st.columns([6, 1.3], vertical_alignment="bottom")
    st.session_state.setdefault("backup_dir", cfg.get("dir") or str(libbackup.DEFAULT_DIR))     # set before the box exists so a Browse click can change it
    st.session_state.setdefault("backup_sources", "\n".join(cfg.get("sources", [])))
    folder = row[0].text_input("Backup Folder", key="backup_dir",
                               help="a folder outside the project, such as one on another drive or in onedrive")
    row[1].button("Browse", icon=":material/folder_open:", key="backup_dir_browse", width="stretch", on_click=_browse, args=("backup_dir", False),
                  help="choose the folder in a window")
    row = st.columns([6, 1.3], vertical_alignment="bottom")
    sources = row[0].text_area("Folders With Your Original Files", key="backup_sources", height=110,
                               help="one folder per line, such as your onedrive school documents folder. they are only read", placeholder="/Users/you/Documents/School" if sys.platform == "darwin" else "C:\\Users\\you\\OneDrive\\School Documents")
    row[1].button("Add Folder", icon=":material/create_new_folder:", key="backup_sources_browse", width="stretch", on_click=_browse, args=("backup_sources", True),
                  help="choose a folder in a window and add it to the list")
    wanted = [s.strip() for s in sources.splitlines() if s.strip()]
    if folder.strip() != (cfg.get("dir") or str(libbackup.DEFAULT_DIR)) or wanted != cfg.get("sources", []):
        settings.set_backup(dir=folder.strip(), sources=wanted)
        st.rerun()
    bad = [p for p in wanted if not libbackup.Path(p).is_dir()]
    if bad:
        st.warning("These folders were not found: " + ", ".join(bad))
    a, b, c = st.columns(3)
    if a.button("Back Up Now", icon=":material/backup:", width="stretch", key="backup_now", help="copies new and changed files to the backup folder"):
        with st.spinner("Copying the Library..."):
            try:
                r = libbackup.back_up(folder.strip() or None)
                st.success(f"Backed up {r['books']} files ({r['copied']} new or changed) to {r['folder']}.")
            except OSError as e:
                st.error(f"The backup could not be made: {e}")
    if b.button("Restore Missing Files", icon=":material/restore:", width="stretch", key="backup_restore",
                help="adds back the files the library does not have, from the backup folder or your original folders"):
        try:
            with st.spinner("Restoring..."):
                r = libbackup.restore(folder.strip() or None, wanted)
            st.success(f"Restored {r['restored']} files; {r['skipped']} were already in the Library.")
            if r["missing"]:
                st.warning(f"{len(r['missing'])} files could not be found: " + ", ".join(r["missing"][:8]) + (" ..." if len(r["missing"]) > 8 else ""))
        except (OSError, ValueError) as e:
            st.error(f"There is no usable backup in that folder: {e}")
    with c, st.container(key="backup_db_pop"):                              # styled like the buttons beside it
        with st.popover("Restore Database", icon=":material/database:", width="stretch", help="puts the backed up database and settings back"):
            st.caption("Replaces the database and settings with the ones in the backup folder (courses, homework, grades, exams, outlines). The current ones are "
                       "kept next to them as before-restore copies. Restart the app afterwards.")
            if st.button("Restore Database", key="backup_restore_db"):
                try:
                    libbackup.restore_database(folder.strip() or None)
                    st.success("The database and settings were restored. Close and reopen the app.")
                except OSError as e:
                    st.error(f"Could not restore: {e}")
    if cfg.get("last"):
        st.caption(f"Last backup: {cfg['last'].replace('T', ' ')}")
    _export_import_section()



def _browse_file(key):
    """Button callback: open the file window; the chosen file replaces the text in `key`."""
    import folderpick
    chosen = folderpick.pick_file(st.session_state.get(key, ""), "Choose the Zip to Import")
    if chosen:
        st.session_state[key] = chosen


def _export_import_section():
    """Part of Backup: one zip with the user's own files, to keep as a backup or to bring to another device, and the import of such a zip."""
    import dataimport
    import exportfiles
    st.subheader("Export and Import")
    st.caption("Export My Files makes one zip with your database, settings and imported files (covers, photos, grades and drawings too), to keep as a backup or to take to another "
               "device. On that device, install Study Assistant, then choose the zip under Import. Nothing is deleted: a file that is already there and differs is copied to "
               f"Backups\\Before Import first. Your files are kept in {exportfiles.DATA_DIR}.")
    cols = st.columns([6, 1.3], vertical_alignment="bottom")
    st.session_state.setdefault("export_dest", str(Path.home() / "Desktop"))
    dest = cols[0].text_input("Save the Export In", key="export_dest", help="a folder outside the program folder, such as the desktop, onedrive or a usb drive")
    cols[1].button("Browse", icon=":material/folder_open:", key="export_dest_browse", width="stretch", on_click=_browse, args=("export_dest", False),
                   help="choose the folder in a window")
    if exportfiles.JOB["running"]:
        _export_progress()
    else:
        job = exportfiles.JOB
        if job["result"]:
            st.success(f"Done: {job['result']}")
        if job["error"]:
            st.error(job["error"])
        enough = True
        try:
            info = exportfiles.estimate()
            space = exportfiles.check_space(dest.strip() or ".", info)
            enough = space["ok"]
            st.caption(f"About {info['bytes'] / 2**30:.1f} GB ({info['files']} files) will be packed. "
                       f"Free space on {space['drive']}: {space['free'] / 2**30:.1f} GB; the zip needs up to {space['needed'] / 2**30:.1f} GB.")
            if not enough:
                st.error(f"Not enough free space on {space['drive']}: {(space['needed'] - space['free']) / 2**30:.1f} GB more are needed. "
                         "Free some space or choose a folder on another drive.")
        except OSError as e:
            st.warning(f"That folder cannot be used: {e}")
            enough = False
        if st.button("Export My Files", icon=":material/upload_file:", key="export_make", disabled=not enough,
                     help="packs your files into one zip; nothing is changed or removed"):
            if exportfiles.start(dest.strip()):
                st.rerun()

    row = st.columns([6, 1.3], vertical_alignment="bottom")
    zip_path = row[0].text_input("Zip to Import", key="import_zip", placeholder="C:\\Users\\you\\Desktop\\StudyAssistant-Files-20261109-1200.zip",
                                 help="a zip made by export my files")
    row[1].button("Browse", icon=":material/folder_open:", key="import_zip_browse", width="stretch", on_click=_browse_file, args=("import_zip",),
                  help="choose the zip in a window")
    if dataimport.JOB["running"]:
        _import_progress()
        return
    job = dataimport.JOB
    if job["result"]:
        r = job["result"]
        st.success(f"Imported: {r['added']} files added, {r['replaced']} existing files replaced, {r['same']} existing files written again with the same content. "
                   "Close and reopen the app to use them." + (f" The files that were replaced were first copied to {r['backup']}." if r["backup"] else ""))
    if job["error"]:
        st.error(job["error"])
    info = None
    if zip_path.strip():
        try:
            info = dataimport.inspect(zip_path)
            st.caption(f"This zip holds {info['files']} files ({info['bytes'] / 2**30:.2f} GB)" + ("" if info["has_db"] else " and no database") + ".")
        except RuntimeError as e:
            st.warning(str(e))
    if st.button("Import", icon=":material/download:", key="import_go", disabled=info is None,
                 help="adds the files of the zip to this app; nothing is deleted"):
        if dataimport.start(zip_path):
            st.rerun()


@st.fragment(run_every=1)
def _import_progress():
    import dataimport
    job = dataimport.JOB
    if job["running"]:
        st.progress(min(max(job["fraction"], 0.0), 1.0), text=f"{int(job['fraction'] * 100)}%  {job['message'][:90]}")
    else:
        st.rerun()


@st.fragment(run_every=1)
def _export_progress():
    import exportfiles
    job = exportfiles.JOB
    if job["running"]:
        st.progress(min(max(job["fraction"], 0.0), 1.0), text=f"{int(job['fraction'] * 100)}%  {job['message'][:90]}")
    else:
        st.rerun()


def _danger_zone():
    import libbackup
    _section("Danger Zone")
    with st.container(key="danger_zone", border=True):
        st.markdown("**Clear All Library**")
        st.caption("Removes every file from the Library: the records and the stored copies. A backup is made first, and nothing is removed if that "
                   "fails. Your original files in your own folders and in onedrive are not touched.")
        typed = st.text_input("Type CLEAR LIBRARY to confirm", key="clear_confirm", placeholder="CLEAR LIBRARY")
        if st.button("Clear All Library", icon=":material/delete_forever:", type="primary", key="clear_library", disabled=typed.strip() != "CLEAR LIBRARY"):
            try:
                with st.spinner("Backing up, then clearing..."):
                    r = libbackup.clear_library()
                st.success(f"Removed {r['books']} files from the Library. The backup is in {r['backup']}.")
            except Exception as e:
                st.error(f"Nothing was removed: {e}")


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


def _help_section():
    """Answers to common questions (installing, antivirus warnings, where the files are, backups, connection problems, shortcuts, uninstalling)."""
    import helpinfo
    _section("Help")
    st.caption(f"Answers to common questions. More help is on the [project page]({helpinfo.HELP_URL}).")
    files = helpinfo.where_files()
    for question, answer in helpinfo.FAQ:
        with st.expander(question):
            st.markdown(answer.replace("{files}", files))
    st.caption("Did not find your answer? Report it below.")


def _open_issue(url):
    """Callback of Open on GitHub: collect the chosen screenshots into one folder and open it, then open the issue page in the browser."""
    import webbrowser
    import helpinfo
    s = st.session_state
    uploads = [(f.name, f.getvalue()) for f in (s.get("report_uploads") or [])]
    saved = [Path(p) for p in (s.get("report_saved") or [])]
    folder, names, problems = helpinfo.prepare_attachments(uploads, saved) if (uploads or saved) else (None, [], [])
    try:
        webbrowser.open(url)
        message = "The report is open in your browser. Read it and press Submit new issue there."
    except Exception:
        message = "The browser could not be opened. Copy the report from the preview and post it on the project page."
    if folder:
        helpinfo.reveal(folder)
        message += f" The {len(names)} screenshot{'s are' if len(names) != 1 else ' is'} in the folder that opened: drag {'them' if len(names) != 1 else 'it'} into the description box."
    if problems:
        message += " " + " ".join(problems)
    st.toast(message, icon=":material/open_in_new:")


def _report_section():
    """Report a problem or an idea: a pre-filled GitHub issue opens in the browser; the user reads it and submits it there."""
    import helpinfo
    _section("Report an Issue")
    st.caption("Found a problem, or have an idea? This opens a ready-made report on GitHub in your browser. You read it and press Submit there; "
               "the app sends nothing by itself. A free GitHub account is needed, and reports are public, so leave out anything personal.")
    kind = st.selectbox("What Kind of Report?", list(helpinfo.KINDS), key="report_kind")
    summary = st.text_input("Short Summary", key="report_summary", placeholder="One line, such as: the quiz page stays empty")
    details = st.text_area("Details", key="report_details", height=130, placeholder="What happened, and what did you expect?")
    steps = st.text_area("Steps to Reproduce (Optional)", key="report_steps", height=90, placeholder="1. Open Courses  2. Open a course  3. ...")
    st.file_uploader("Attach Screenshots (Optional)", type=helpinfo.IMAGE_TYPES, accept_multiple_files=True, key="report_uploads",
                     help="pictures of the problem. github takes them when you drop them into the report's text box; the app puts them in one folder for you")
    recent = helpinfo.recent_screenshots()
    if recent:
        st.multiselect("Or Pick Screenshots You Saved With F2", [str(p) for p in recent], key="report_saved", format_func=lambda p: Path(p).stem.replace("Study Assistant ", ""),
                       help="the newest pictures F2 saved in the screenshots folder")
    n_pictures = len(st.session_state.get("report_uploads") or []) + len(st.session_state.get("report_saved") or [])
    if n_pictures:
        st.caption("A screenshot shows everything that was on the screen. Look at each one before you send it: reports are public.")
    c1, c2 = st.columns(2)
    system = c1.checkbox("Include Technical Details", True, key="report_system", help="the app version and the kind of computer. no names, folders or files of yours")
    log = c2.checkbox("Include the End of the App's Log", False, key="report_log",
                      help="the last lines of the log the installed app keeps, with your name and folders replaced. you can read exactly what is included in the preview")
    if log and not helpinfo.log_tail():
        st.caption("There is no log yet (only the installed app keeps one).")
    title, body = helpinfo.build_report(kind, summary or "(no summary)", details, steps, system, log, n_pictures)
    with st.expander("Preview of the Report"):
        st.markdown(f"**{title}**")
        st.code(body, language="markdown")
    ready = bool(summary.strip() and details.strip())
    st.button("Open on GitHub", key="report_open", type="primary", icon=":material/open_in_new:", disabled=not ready,
              on_click=_open_issue, args=(helpinfo.issue_url(kind, title, body),),
              help="opens the report in your browser; it is only sent when you press submit there" if ready else "fill in the summary and the details first")
    st.caption(f"Your browser does not open? Copy the report from the preview and post it at {helpinfo.ISSUES_URL}.")


def _planner_save():
    """Callback of the Save button: read the boxes, validate everything first, then save it (nothing is saved when anything is wrong)."""
    from planner import store
    from planner.models import AwakeTimes, DayWindow, PlannerError
    s = st.session_state
    try:
        awake = AwakeTimes(tuple(DayWindow(s[f"planner_wake_{i}"], s[f"planner_bed_{i}"]) for i in range(7)))
        store.set_timezone(s["planner_tz"])
        store.set_min_block(int(s["planner_block"]))
        store.set_awake(awake)
        s["planner_msg"] = ("ok", "Planner setup saved.")
    except PlannerError as e:
        s["planner_msg"] = ("error", str(e))


def _planner_section():
    """Study planner setup: time zone, awake hours for each weekday and the shortest study block. The term dates and breaks are the Calendar's."""
    import zoneinfo
    from planner import store
    from planner.models import MIN_BLOCK_RANGE, WEEKDAYS
    _section("Study Planner")
    st.caption("The planner places study time only between your wake and bed times, and never in a break. "
               "The term dates and breaks are set in Calendar > Edit Schedule.")
    cfg = store.load_config()
    term = cfg.term
    st.caption(f"Term: {term.start:%b %d, %Y} to {term.classes_end:%b %d, %Y}, exams until {term.exams_end:%b %d, %Y}"
               + ("" if store.term_configured() else " (the app's default dates until you save yours)")
               + (f" · Breaks: {', '.join(b.name for b in term.breaks)}" if term.breaks else " · No breaks"))
    from planner import timeutil
    zones = timeutil.zones_by_offset(zoneinfo.available_timezones())
    labels = {z: timeutil.zone_label(z) for z in zones}                      # 'America/New_York (UTC-05:00, EST)'
    with st.container(key="planner_setup"):
        c1, c2 = st.columns(2)
        c1.selectbox("Time Zone", zones, index=zones.index(term.tz) if term.tz in zones else 0, key="planner_tz", format_func=labels.get,
                          help="all planned times are kept in utc and shown in this time zone; type a place or an offset such as utc-5 to search")
        c2.number_input("Minimum Study Block (Minutes)", MIN_BLOCK_RANGE[0], MIN_BLOCK_RANGE[1], cfg.min_block_minutes, 5, key="planner_block",
                                help="free time shorter than this is not used for planning")
        st.markdown("**Awake Times**")
        for i, name in enumerate(WEEKDAYS):
            w = cfg.awake.for_weekday(i)
            d, wk, bd = st.columns([2, 2, 2], vertical_alignment="center")
            d.markdown(name)
            wk.time_input(f"{name} Wake", w.wake, key=f"planner_wake_{i}", step=300, label_visibility="collapsed", help=f"{name.lower()}: when you wake up")
            bd.time_input(f"{name} Bed", w.bed, key=f"planner_bed_{i}", step=300, label_visibility="collapsed", help=f"{name.lower()}: when you go to bed")
        st.button("Save Planner Setup", key="planner_save", type="primary", on_click=_planner_save)
    msg = st.session_state.pop("planner_msg", None)
    if msg:
        (st.success if msg[0] == "ok" else st.error)(msg[1])
