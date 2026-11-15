"""Tasks of the study planner: work with a due date and a time estimate. Pure: no database, no UI.

A Task has a title, an optional course, a category, an optional due moment (UTC), an estimate in minutes, optional "start ahead" days (start working that many
days before the due date), a state (todo or done) and the minutes already logged. The estimate of a new task comes from the course's default for its category,
else from the built-in default of the category, unless the user gives one. The lists a student looks at (to-do, overdue, start soon, no due date, completed)
are plain functions of the tasks and the clock."""
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from . import timeutil
from .models import PlannerError

CATEGORIES = ("Homework", "Exam", "Quiz", "Reading", "Project", "Other")
TODO, DONE = "todo", "done"
# The built-in estimates (minutes) used when a course has no default for a category: typical figures for a university course.
DEFAULT_ESTIMATES = {"Homework": 120, "Exam": 600, "Quiz": 45, "Reading": 60, "Project": 600, "Other": 60}
ESTIMATE_RANGE = (5, 6000)             # minutes: 5 minutes to 100 hours
MAX_START_AHEAD = 120                  # days
START_SOON_DAYS = 3


def check_category(category):
    if category not in CATEGORIES:
        raise PlannerError(f"The category has to be one of: {', '.join(CATEGORIES)}.")
    return category


def check_estimate(minutes):
    lo, hi = ESTIMATE_RANGE
    if not isinstance(minutes, int) or isinstance(minutes, bool) or not lo <= minutes <= hi:
        raise PlannerError(f"The estimate has to be a whole number of minutes from {lo} to {hi}.")
    return minutes


def check_start_ahead(days):
    if days is not None and (not isinstance(days, int) or isinstance(days, bool) or not 0 <= days <= MAX_START_AHEAD):
        raise PlannerError(f"Start ahead is a whole number of days from 0 to {MAX_START_AHEAD}, or empty.")
    return days


def default_estimate(course_defaults, category):
    """The estimate a new task of this category gets: the course's own default when it has one, else the built-in one.
    `course_defaults` is {category: minutes} of one course (or empty)."""
    check_category(category)
    return (course_defaults or {}).get(category) or DEFAULT_ESTIMATES[category]


@dataclass(frozen=True)
class Task:
    id: int
    title: str
    course_id: int = None
    category: str = "Homework"
    due: datetime = None                    # UTC, or None for a task without a due date
    estimate_minutes: int = 60
    start_ahead_days: int = None            # None: no limit (work may start any time); n: from n days before the due date
    state: str = TODO
    logged_minutes: int = 0
    source: str = None                      # where it came from (None = typed in); ready for imports
    completed: datetime = None              # UTC moment it was marked done
    personal: bool = False                  # not for school: it may be planned in a break and outside the term, and has no course

    def __post_init__(self):
        if not self.title.strip():
            raise PlannerError("A task needs a title.")
        check_category(self.category)
        check_estimate(self.estimate_minutes)
        check_start_ahead(self.start_ahead_days)
        if self.state not in (TODO, DONE):
            raise PlannerError("A task is either todo or done.")
        if not isinstance(self.logged_minutes, int) or isinstance(self.logged_minutes, bool) or self.logged_minutes < 0:
            raise PlannerError("Logged time is a whole number of minutes, not below zero.")
        for moment in (self.due, self.completed):
            if moment is not None and moment.tzinfo is None:
                raise PlannerError("A task's times have to be UTC moments.")
        if self.personal and self.course_id is not None:
            raise PlannerError("A personal task is not for a course.")
        if self.start_ahead_days is not None and self.due is None:
            raise PlannerError("A task without a due date has nothing to start ahead of.")

    @property
    def is_done(self):
        return self.state == DONE

    @property
    def remaining_minutes(self):
        """What is still to do: the estimate minus the time logged (never below zero; nothing once the task is done)."""
        return 0 if self.is_done else max(0, self.estimate_minutes - self.logged_minutes)

    def due_day(self, tz):
        """The local date it is due, or None."""
        return timeutil.local_day(self.due, tz) if self.due else None

    def start_date(self, tz):
        """The first local day work may be planned: the due date minus the start-ahead days; None when there is no limit (or no due date)."""
        if self.due is None or self.start_ahead_days is None:
            return None
        return self.due_day(tz) - timedelta(days=self.start_ahead_days)

    def is_overdue(self, now):
        """Not done, and the due moment has passed (a task due exactly now is not late yet)."""
        return not self.is_done and self.due is not None and self.due < now


# ---------------------------------------------------------------- the lists
def _by_due(task):
    return (task.due is None, task.due or datetime.max.replace(tzinfo=timeutil.UTC), task.title.lower(), task.id)


def todo(tasks):
    """The tasks still to do, soonest due first; those without a due date come last."""
    return sorted((t for t in tasks if not t.is_done), key=_by_due)


def overdue(tasks, now):
    """Tasks not done whose due moment has passed, the longest overdue first."""
    return sorted((t for t in tasks if t.is_overdue(now)), key=_by_due)


def start_soon(tasks, now, tz, days=START_SOON_DAYS):
    """Tasks not done that have a start-ahead date from today up to `days` days away and no time logged yet: the ones to begin about now.
    (A task whose start date has passed with nothing logged counts too: it should have been begun.)"""
    today = timeutil.local_day(now, tz)
    limit = today + timedelta(days=days)
    found = []
    for t in tasks:
        start = t.start_date(tz)
        if t.is_done or start is None or t.logged_minutes or t.is_overdue(now):
            continue
        if start <= limit:
            found.append(t)
    return sorted(found, key=_by_due)


def no_due_date(tasks):
    """Tasks not done that have no due date, by title."""
    return sorted((t for t in tasks if not t.is_done and t.due is None), key=lambda t: (t.title.lower(), t.id))


def completed(tasks):
    """Finished tasks, the most recently finished first."""
    return sorted((t for t in tasks if t.is_done), key=lambda t: (t.completed is None, -(t.completed.timestamp() if t.completed else 0), t.id))


@dataclass(frozen=True)
class TaskLists:
    todo: tuple
    overdue: tuple
    start_soon: tuple
    no_due_date: tuple
    completed: tuple


def lists(tasks, now, tz):
    """All five lists at once, for the clock `now` (a UTC datetime) and the term's zone."""
    tasks = list(tasks)
    return TaskLists(tuple(todo(tasks)), tuple(overdue(tasks, now)), tuple(start_soon(tasks, now, tz)), tuple(no_due_date(tasks)), tuple(completed(tasks)))
