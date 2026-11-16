"""Bringing calendars into the planner: an .ics file, or a feed (the private calendar link of Canvas, Brightspace or Google Calendar) that is read again to keep the planner up to date.

`rows(...)` turns the text of a calendar into the rows a student reviews (a task or an event, its course and category, new or already there); `apply(...)` saves the chosen rows. Every item
that comes in is saved with a source `ical:<feed id>:<key>`, so reading the same calendar again updates what is there and never adds it twice; the keys of everything a feed has brought
in are kept (`seen`), so a task the student deleted is not brought back. A feed is only ever READ (nothing is sent to it). Database access is here, the network only in `fetch`."""
import re
import urllib.request
from datetime import date, datetime, time, timedelta, timezone

from planner import commit_store, ical, store, task_store, timeutil
from planner import tasks as T

UTC = timezone.utc
MAX_BYTES = 20 * 2 ** 20
DEFAULT_ESTIMATE = None                                                  # a new task takes the estimate of its course and category
WINDOW_DAYS = 200                                                        # how far ahead a calendar is read


def fetch(url, timeout=20):
    """The text of a calendar feed. `webcal://` is read as `https://`. Only the address the student gave is read."""
    url = url.strip()
    if url.lower().startswith("webcal://"):
        url = "https://" + url[9:]
    if not re.match(r"https?://", url, re.I):
        raise ValueError("The feed address has to start with https:// or webcal://.")
    req = urllib.request.Request(url, headers={"User-Agent": "StudyAssistant", "Accept": "text/calendar, */*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("The calendar is too large.")
    text = data.decode("utf-8", errors="replace")
    if "BEGIN:VCALENDAR" not in text.upper():
        raise ValueError("That address did not give a calendar (it has to be an iCalendar feed, an .ics link).")
    return text


def _local_midnight(day, zone):
    return datetime.combine(day, time.min).replace(tzinfo=zone).astimezone(UTC)


def _due_of(occ, zone):
    """The UTC due moment of a task: the due time, or 23:59 (the zone of the term) of an all-day date."""
    moment = occ.get("due") or occ["start"]
    if isinstance(moment, datetime):
        return moment
    return datetime.combine(moment, time(23, 59)).replace(tzinfo=zone).astimezone(UTC)


def _event_times(occ, zone):
    """(start, end) UTC for an event; an all-day one from local midnight to local midnight after its last day."""
    if occ["all_day"]:
        first = occ["start"] if not isinstance(occ["start"], datetime) else occ["start"].date()
        end = occ["end"] if not isinstance(occ["end"], datetime) else (occ["end"].date() if occ["end"] else None)
        end = end if end and end > first else first + timedelta(days=1)
        return _local_midnight(first, zone), _local_midnight(end, zone)
    start, end = occ["start"], occ["end"] if occ["end"] and occ["end"] > occ["start"] else occ["start"] + timedelta(hours=1)
    return start, end


def rows(text, feed_id, *, courses, now=None, include_past=False, seen=()):
    """The rows to review for a calendar text: [{key, source, kind ("Task" or "Event"), title, start, end, all_day, due, category, course_id, location, url, done, exists, changed, new}].
    `courses`: [{id, code, name}]; `seen`: the keys this feed brought in before."""
    now = now or datetime.now(UTC)
    zone = store.get_term().zone
    items = ical.parse(text, zone)
    first = now - (timedelta(days=400) if include_past else timedelta(days=1))
    occs = ical.occurrences(items, first, now + timedelta(days=WINDOW_DAYS), zone)
    prefix = f"ical:{feed_id}:"
    tasks = {t.source: t for t in task_store.list_tasks() if t.source and t.source.startswith(prefix)}
    events = commit_store.events_by_source(prefix)
    out = []
    for occ in occs:
        kind, category = ical.classify(occ)
        source = prefix + occ["key"]
        row = {"key": occ["key"], "source": source, "kind": "Task" if kind == "task" else "Event", "title": occ["title"], "all_day": occ["all_day"], "category": category,
               "course_id": ical.match_course(occ, courses), "location": occ["location"], "url": occ["url"], "done": occ["done"], "description": occ["description"]}
        row["due"] = _due_of(occ, zone)
        row["start"], row["end"] = _event_times(occ, zone)
        if kind == "task" and not include_past and row["due"] < now - timedelta(days=1):
            continue
        existing = tasks.get(source) if kind == "task" else events.get(source)
        row["exists"] = existing is not None
        row["new"] = occ["key"] not in set(seen) and existing is None
        if existing is not None:
            row["changed"] = (existing.title != row["title"] or existing.due != row["due"]) if kind == "task" else (existing.title != row["title"] or existing.start != row["start"] or existing.end != row["end"])
        else:
            row["changed"] = False
        out.append(row)
    return out


def apply(selected, feed_id, zone=None):
    """Save the rows the student chose (each with the final `kind`, `title`, `category`, `course_id`, `estimate`): new ones are added, ones that are there already are updated.
    Returns {"added": n, "updated": n, "skipped": n, "keys": [the keys handled]}."""
    added = updated = skipped = 0
    keys = []
    prefix = f"ical:{feed_id}:"
    tasks = {t.source: t for t in task_store.list_tasks() if t.source and t.source.startswith(prefix)}
    events = commit_store.events_by_source(prefix)
    for r in selected:
        try:
            if r["kind"] == "Task":
                due = r["due"]
                if r["source"] in tasks:
                    existing = tasks[r["source"]]
                    if existing.title != r["title"] or existing.due != due:
                        task_store.update_task(existing.id, title=r["title"], due=due)
                        updated += 1
                    else:
                        skipped += 1
                else:
                    cat = r["category"] if r["category"] in T.CATEGORIES else "Other"
                    tid = task_store.add_task(r["title"], r.get("course_id"), cat, due, r.get("estimate") or DEFAULT_ESTIMATE, source=r["source"])
                    if r.get("done"):
                        task_store.set_done(tid)
                    added += 1
            else:
                start, end = r["start"], r["end"]
                if r["source"] in events:
                    existing = events[r["source"]]
                    if existing.title != r["title"] or existing.start != start or existing.end != end:
                        commit_store.update_event(existing.id, r["title"], start, end, r["all_day"], r.get("location") or "", existing.commute_before, existing.commute_after, existing.busy, existing.course_id)
                        updated += 1
                    else:
                        skipped += 1
                else:
                    commit_store.add_event(r["title"], start, end, r["all_day"], r.get("location") or "", course_id=r.get("course_id"), source=r["source"])
                    added += 1
            keys.append(r["key"])
        except Exception:
            skipped += 1
    return {"added": added, "updated": updated, "skipped": skipped, "keys": keys}


def sync_feed(feed, courses, text=None, now=None):
    """Read a saved feed again and keep the planner up to date without asking: what the feed has brought in before is updated, new items of the kinds the feed is set to bring in are added
    (a deleted one stays deleted). Returns the counts of `apply`; raises when the feed cannot be read."""
    text = text if text is not None else fetch(feed["url"])
    found = rows(text, feed["id"], courses=courses, now=now, seen=feed.get("seen") or [])
    wanted = []
    for r in found:
        if r["exists"]:
            wanted.append(r)
        elif r["new"] and ((r["kind"] == "Task" and feed.get("tasks", True)) or (r["kind"] == "Event" and feed.get("events", True))):
            wanted.append(r)
    return apply(wanted, feed["id"])
