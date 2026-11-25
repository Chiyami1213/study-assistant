"""Done on the Home page (homework or exam) is done in the Task List too, and the other way round."""
from datetime import date, time

import pytest

from core import crud
from planner import linkdone, store, task_store as ts, timeutil

pytestmark = pytest.mark.usefixtures("fresh_data")


def setup_course():
    store.set_timezone("America/New_York")
    cid = crud.add_course("AE 6009", "Viscous Fluid Flow", "Fall 2026", 0, "Active")
    due = timeutil.to_utc(date(2026, 11, 16), time(23, 59), "America/New_York")
    task_id = ts.add_task("HW 4", cid, "Homework", due, 120)
    hw = crud.add_homework(cid, "HW 4", "2026-11-16", "", "", due_time="23:59")
    return cid, ts.get_task(task_id), hw


def test_done_on_home_marks_the_task_and_undo_opens_it_again():
    cid, task, hw = setup_course()
    other_id = ts.add_task("HW 5", cid, "Homework", timeutil.to_utc(date(2026, 11, 20), time(23, 59), "America/New_York"), 120)
    crud.set_homework_status(hw, "verified")
    assert linkdone.from_home("Homework", hw, True) == 1
    assert ts.get_task(task.id).is_done and not ts.get_task(other_id).is_done                  # only the task of that title
    assert linkdone.from_home("Homework", hw, True) == 0
    linkdone.from_home("Homework", hw, False)
    assert not ts.get_task(task.id).is_done


def test_done_in_the_task_list_marks_the_homework_and_the_exam_event():
    cid, task, hw = setup_course()
    t = ts.get_task(task.id)
    ts.set_done(t.id, True)
    assert linkdone.from_task(t, True) == 1
    assert [h["status"] for h in crud.list_homework(cid)] == ["verified"]
    linkdone.from_task(t, False)
    assert [h["status"] for h in crud.list_homework(cid)] == ["todo"]
    ex = crud.add_event("Midterm 1", "2026-11-20", cid)
    exam_id = ts.add_task("Midterm 1", cid, "Exam", timeutil.to_utc(date(2026, 11, 20), time(9), "America/New_York"), 600)
    assert linkdone.from_task(ts.get_task(exam_id), True) == 1 and crud.list_events("2026-11-20", "2026-11-20")[0]["done"]


def test_the_home_page_lists_lab_reports_and_projects_and_ticks_them_done():
    from datetime import date, time
    from views import home_view
    cid = crud.add_course("AE 7", "Lab Course", "Fall 2026", 0, "Active")
    due = timeutil.to_utc(date(2026, 12, 4), time(17), "America/New_York")
    lab = ts.add_task("Lab 2 Report", cid, "Lab", due, 180)
    proj = ts.add_task("Project Proposal", cid, "Project", due, 300)
    ts.add_task("HW 9", cid, "Homework", due, 120)                                            # homework is listed from the course page, not from here
    by_id = {cid: crud.get_course(cid)}
    got = {t[2]: t for t in home_view._tasks(by_id, False)}
    assert set(got) == {"Lab 2 Report", "Project Proposal"} and got["Lab 2 Report"][:2] == ("2026-12-04", "17:00") and got["Project Proposal"][3] == "Project"
    home_view._complete("Lab", lab)
    assert [t[2] for t in home_view._tasks(by_id, False)] == ["Project Proposal"] and [t[2] for t in home_view._tasks(by_id, True)] == ["Lab 2 Report"]
    home_view._undo("Lab", lab)
    assert len(home_view._tasks(by_id, False)) == 2
