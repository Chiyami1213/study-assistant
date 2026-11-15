"""The planner as the app uses it: reads the saved setup, commitments and tasks and returns the cushion report. The logic itself is in planner.freetime (pure)."""
from datetime import datetime, timezone

from . import commit_store, freetime, store, task_store, timeutil


def cushion_report(now=None, planned=()):
    """The CushionReport for `now` (a UTC datetime; the clock when omitted): free time from today to the last deadline of the unfinished tasks, the cushion of
    each, and the timeline. `planned`: study sessions already placed (anything with start and end); phase 5 supplies them."""
    now = now or datetime.now(timezone.utc)
    config = store.load_config()
    tasks = task_store.list_tasks(include_done=False)
    dated = [t for t in tasks if t.due is not None]
    if not dated:
        return freetime.CushionReport((), (), False)
    tz = config.term.zone
    first = timeutil.local_day(now, tz)
    last = max(first, min(max(timeutil.local_day(t.due, tz) for t in dated), config.term.exams_end))
    blocks = commit_store.commitments(first, last)
    return freetime.report(config, tasks, blocks, planned, now)


def free_time(first, last, now=None, planned=()):
    """The free study intervals (UTC pairs) of the local days first..last from the saved setup."""
    config = store.load_config()
    return freetime.free_intervals(config, commit_store.commitments(first, last), planned, first, last, now)
