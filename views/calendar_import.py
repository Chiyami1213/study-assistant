"""Import From Calendar (Task List): the assignments and events of Canvas, Brightspace, Google Calendar or Shovel come into the planner, from an .ics file or from a feed (the private calendar link of
the service) that the app reads again to keep up to date. The student reviews the rows first (task or event, course, category); what a feed brought in is updated by the next reading and
never added twice (see planner/calsync.py). A feed address is private: it is kept only in the settings file of this computer, and the app only reads it."""
import uuid
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from core import crud, settings
from planner import calsync, store

HELP = {
    "Canvas": "Canvas: open **Calendar**, then **Calendar Feed** (at the bottom right) and copy the link.",
    "Brightspace": "Brightspace: open **Calendar**, then **Subscribe** (or the settings of the calendar) and copy the link of the feed.",
    "Google Calendar": "Google Calendar (a computer): **Settings** > the calendar > **Integrate calendar** > **Secret address in iCal format**. To import without a link: **Settings** > **Import & export** > **Export**, then use Import a File.",
    "Shovel": "Shovel: open the **Calendar** tab, press the **share** icon at the top, choose what to include (events, planned tasks, or both) and copy the .ics link. For one course: its settings > share. Timed items come in as events on your Calendar, so Shovel's planned study time is not turned into a second task.",
    "Other": "Any calendar service that gives an iCalendar address (a link ending in .ics, or starting with webcal://).",
}
AUTO_HOURS = 3


def _courses():
    return [{"id": c["id"], "code": c.get("code") or "", "name": c.get("name") or ""} for c in crud.list_courses(section=None)]


def _when(row):
    zone = store.get_term().zone
    if row["kind"] == "Task":
        return row["due"].astimezone(zone).strftime("%a %b %d, %H:%M")
    start = row["start"].astimezone(zone)
    return start.strftime("%a %b %d") + ("" if row["all_day"] else start.strftime(", %H:%M"))


def _review(found, feed_id, key, after=None):
    """The table of rows to check, and the button that saves them. `after(keys)` runs once they are saved (a feed remembers what it showed)."""
    if not found:
        st.info("Nothing to bring in: the calendar has no upcoming items.")
        return
    courses = {c["id"]: crud.label(c) for c in crud.list_courses(section=None)}
    names = ["No Course"] + list(courses.values())
    by_name = {v: k for k, v in courses.items()}
    frame = pd.DataFrame([{"Add": not r["exists"] or r["changed"], "Type": r["kind"], "Title": r["title"], "When": _when(r), "Course": courses.get(r["course_id"], "No Course"), "Category": r["category"],
                           "Status": "Changed" if r["changed"] else "Already There" if r["exists"] else "New"} for r in found])
    from planner import tasks as T
    got = st.data_editor(frame, key=f"{key}_table", hide_index=True, width="stretch", num_rows="fixed",
                         column_config={"Add": st.column_config.CheckboxColumn("Add"), "Type": st.column_config.SelectboxColumn("Type", options=["Task", "Event"], required=True),
                                        "Title": st.column_config.TextColumn("Title", required=True), "When": st.column_config.TextColumn("When", disabled=True),
                                        "Course": st.column_config.SelectboxColumn("Course", options=names, required=True),
                                        "Category": st.column_config.SelectboxColumn("Category", options=list(T.CATEGORIES), required=True), "Status": st.column_config.TextColumn("Status", disabled=True)}).to_dict("records")
    chosen = []
    for r, g in zip(found, got):
        if g["Add"]:
            chosen.append({**r, "kind": g["Type"], "title": (g["Title"] or r["title"]).strip(), "category": g["Category"], "course_id": by_name.get(g["Course"])})
    st.caption("Task: has a due date and is planned around. Event: a block on the Calendar. Change the type, the course or the category in the table before adding.")
    if st.button(f"Add {len(chosen)} Item{'s' if len(chosen) != 1 else ''}", key=f"{key}_go", type="primary", disabled=not chosen):
        result = calsync.apply(chosen, feed_id)
        if after:
            after([r["key"] for r in found])
        for k in (f"{key}_rows",):
            st.session_state.pop(k, None)
        st.session_state["lib_toast"] = f"Added {result['added']}, updated {result['updated']}" + (f", skipped {result['skipped']}" if result["skipped"] else "") + "."
        st.rerun()


def _saved_feeds():
    feeds = settings.list_feeds()
    if not feeds:
        return
    st.markdown("**Your Calendars**")
    for f in feeds:
        name, info, sync, drop = st.columns([2.2, 3, 1.4, 1.1], vertical_alignment="center")
        name.markdown(f"**{f['name']}**  \n{f['kind']}")
        info.caption((f"Last read {f['last_sync']}" if f.get("last_sync") else "Not read yet") + (f" · {f['status']}" if f.get("status") else "")
                     + f" · brings in {'tasks' if f.get('tasks', True) else ''}{' and ' if f.get('tasks', True) and f.get('events', True) else ''}{'events' if f.get('events', True) else ''}")
        if sync.button("Sync Now", key=f"feed_sync_{f['id']}", icon=":material/sync:", width="stretch"):
            st.session_state["lib_toast"] = sync_one(f)
            st.rerun()
        if drop.button("", key=f"feed_rm_{f['id']}", icon=":material/delete:", help="stop reading this calendar (what it brought in stays)"):
            settings.remove_feed(f["id"])
            st.rerun()
    if st.toggle("Read my calendars when the app opens", settings.get_auto_sync(), key="cal_auto_sync", help="at most every few hours; only what you already brought in is updated and new items of the kinds you chose are added"):
        if not settings.get_auto_sync():
            settings.set_auto_sync(True)
    elif settings.get_auto_sync():
        settings.set_auto_sync(False)
    st.divider()


def sync_one(feed):
    """Read one saved feed again; returns a short message (and keeps when it was read, or why it could not be)."""
    try:
        result = calsync.sync_feed(feed, _courses())
        settings.mark_feed_seen(feed["id"], result["keys"])
        settings.update_feed(feed["id"], last_sync=datetime.now().strftime("%b %d, %H:%M"), status="", synced_at=datetime.now(timezone.utc).isoformat())
        return f"{feed['name']}: added {result['added']}, updated {result['updated']}."
    except Exception as e:
        settings.update_feed(feed["id"], status="could not be read")
        return f"{feed['name']} could not be read ({str(e)[:80]})."


def auto_sync():
    """Once in a while when the app opens: read the saved feeds again (a few hours apart), quietly. Returns the messages."""
    if not settings.get_auto_sync():
        return []
    out = []
    now = datetime.now(timezone.utc)
    for f in settings.list_feeds():
        last = f.get("synced_at")
        try:
            if last and (now - datetime.fromisoformat(last)).total_seconds() < AUTO_HOURS * 3600:
                continue
        except ValueError:
            pass
        out.append(sync_one(f))
    return out


@st.dialog("Import From Calendar", width="large")
def import_dialog():
    st.caption("Bring the assignments and events of Canvas, Brightspace, Google Calendar or Shovel into the planner. A calendar link keeps them up to date; a file is a one-time import.")
    _saved_feeds()
    feed_tab, file_tab = st.tabs(["Add a Calendar Link", "Import a File"])
    with feed_tab:
        kind = st.selectbox("Service", list(settings.FEED_KINDS), key="cal_kind")
        st.caption(HELP[kind])
        name = st.text_input("Name", value=kind, key="cal_name")
        url = st.text_input("Calendar Link", key="cal_url", placeholder="https://... or webcal://...", help="the private link of your calendar; it is only kept on this computer, and only read")
        feed_id = st.session_state.setdefault("_cal_feed_id", uuid.uuid4().hex[:8])
        a, b = st.columns(2)
        tasks_on = a.checkbox("Bring in assignments and due dates as tasks", True, key="cal_tasks")
        events_on = b.checkbox("Bring in events", True, key="cal_events")
        if st.button("Read the Calendar", key="cal_read", icon=":material/cloud_download:", disabled=not url.strip()):
            try:
                text = calsync.fetch(url)
                st.session_state["cal_feed_rows"] = calsync.rows(text, feed_id, courses=_courses(), source=kind)
            except Exception as e:
                st.session_state.pop("cal_feed_rows", None)
                st.error(f"The calendar could not be read: {str(e)[:160]}")
        found = st.session_state.get("cal_feed_rows")
        if found is not None:
            found = [r for r in found if (r["kind"] == "Task" and tasks_on) or (r["kind"] == "Event" and events_on)]

            def keep(keys):
                settings.add_feed(feed_id, name, kind, url, tasks_on, events_on)
                settings.mark_feed_seen(feed_id, keys)
                settings.update_feed(feed_id, last_sync=datetime.now().strftime("%b %d, %H:%M"), synced_at=datetime.now(timezone.utc).isoformat())
                st.session_state.pop("_cal_feed_id", None)
            _review(found, feed_id, "cal_feed", after=keep)
            st.caption("Adding also saves the link, so Sync Now (and the reading when the app opens) keeps these items up to date.")
    with file_tab:
        up = st.file_uploader("Calendar File (.ics)", type=["ics"], key="cal_file", help="Google Calendar: Settings > Import & export > Export. Canvas, Brightspace and Shovel: save the feed link's file.")
        if up is not None:
            try:
                st.session_state["cal_file_rows"] = calsync.rows(up.getvalue().decode("utf-8", errors="replace"), "file", courses=_courses())
            except Exception as e:
                st.error(f"The file could not be read: {str(e)[:160]}")
            _review(st.session_state.get("cal_file_rows") or [], "file", "cal_file")
