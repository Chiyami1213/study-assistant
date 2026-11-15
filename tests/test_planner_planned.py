"""Phase 5: how planned sessions are counted by the cushion (planned_minutes, and the cushion with sessions that belong to tasks)."""
from datetime import date, datetime, time, timedelta, timezone

from planner import freetime as F
from planner import sessions as S
from planner import tasks as T
from planner import timeutil
from planner.models import AwakeTimes, PlannerConfig, Term

NY = "America/New_York"
TERM = Term(date(2026, 9, 1), date(2026, 12, 8), date(2026, 12, 18), NY)
CFG = PlannerConfig(TERM, AwakeTimes.uniform(time(9), time(17)), 30)
MON = date(2026, 9, 7)
NOW = timeutil.to_utc(MON, time(9), NY)


def at(d, hh=0, mm=0):
    return timeutil.to_utc(d, time(hh, mm), NY)


def sess(id, task_id, d, h1, h2):
    return S.Session(id, task_id, at(d, h1), at(d, h2), S.AUTO)


def test_planned_minutes_counts_only_the_task_and_only_inside_the_window():
    s = [sess(1, 1, MON, 9, 11), sess(2, 2, MON, 11, 12), sess(3, 1, MON + timedelta(days=1), 9, 10)]
    assert F.planned_minutes(s, 1, at(MON, 9), at(MON + timedelta(days=5))) == 180
    assert F.planned_minutes(s, 1, at(MON, 10), at(MON, 23)) == 60                                      # a session cut by the window counts up to it
    assert F.planned_minutes(s, 1, at(MON, 9), at(MON, 10)) == 60
    assert F.planned_minutes(s, 2, at(MON, 9), at(MON, 11)) == 0                                        # before the session
    assert F.planned_minutes(s, 9, at(MON, 9), at(MON + timedelta(days=5))) == 0                        # another task
    assert F.planned_minutes([(at(MON, 9), at(MON, 11))], 1, at(MON, 9), at(MON, 23)) == 0               # a plain interval belongs to nobody


def test_sessions_of_a_task_lower_its_work_but_a_plain_busy_interval_does_not():
    t = T.Task(1, "HW", None, "Homework", at(MON + timedelta(days=1), 17), 300)
    plain = [(at(MON, 10), at(MON, 12))]
    owned = [sess(1, 1, MON, 10, 12)]
    free_plain = F.FreeTime(F.free_intervals(CFG, [], plain, MON, MON + timedelta(days=1), NOW))
    free_owned = F.FreeTime(F.free_intervals(CFG, [], owned, MON, MON + timedelta(days=1), NOW))
    a = F.cushions([t], free_plain, NOW, TERM.zone, plain)[0]
    b = F.cushions([t], free_owned, NOW, TERM.zone, owned)[0]
    assert a.cushion_minutes == 960 - 120 - 300                    # the time is gone and the work is still all to do
    assert b.cushion_minutes == 960 - 120 - 180                    # the time is gone but 120 minutes of the work are placed
    assert b.demand_minutes == 180


def test_logged_time_and_planned_time_both_reduce_the_work():
    t = T.Task(1, "HW", None, "Homework", at(MON + timedelta(days=1), 17), 300, logged_minutes=60)
    owned = [sess(1, 1, MON, 10, 11)]
    free = F.FreeTime(F.free_intervals(CFG, [], owned, MON, MON + timedelta(days=1), NOW))
    x = F.cushions([t], free, NOW, TERM.zone, owned)[0]
    assert x.demand_minutes == 300 - 60 - 60 and x.cushion_minutes == (960 - 60) - 180


def test_more_planned_than_needed_never_makes_the_work_negative():
    t = T.Task(1, "HW", None, "Homework", at(MON + timedelta(days=1), 17), 60)
    owned = [sess(1, 1, MON, 9, 12)]
    free = F.FreeTime(F.free_intervals(CFG, [], owned, MON, MON + timedelta(days=1), NOW))
    x = F.cushions([t], free, NOW, TERM.zone, owned)[0]
    assert x.demand_minutes == 0
