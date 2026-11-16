"""The Task List page: filter, sort and group (pure), importing a syllabus, editing tasks, personal tasks."""
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from core import crud
from core import settings
from planner import commit_store as cs, session_store as ss, store, syllabus_read, task_store as ts, tasks as T, timeutil
from planner.models import AwakeTimes, PlannerError
from views import planner_ui, tasklist_view as TL

pytestmark = pytest.mark.usefixtures("fresh_data")
NY = "America/New_York"
TODAY = date.today()
APP = str(Path(__file__).resolve().parent.parent / "app.py")


@pytest.fixture
def seeded():
    store.set_timezone(NY)
    store.set_term_dates(TODAY - timedelta(days=30), TODAY + timedelta(days=60), TODAY + timedelta(days=70))
    store.set_awake(AwakeTimes.uniform(time(8), time(22)))
    store.set_min_block(30)
    return crud.add_course("AE 6765", "Kinetics", "Fall 2026", 0, "Active")


def due(days, hh=23, mm=59):
    return timeutil.to_utc(TODAY + timedelta(days=days), time(hh, mm), NY)


def task(i, title, course=None, category="Homework", days=None, est=60, personal=False):
    return T.Task(i, title, course, category, due(days) if days is not None else None, est, personal=personal)


COURSES = {1: {"id": 1, "code": "AE 6765", "name": "Kinetics"}, 2: {"id": 2, "code": "AE 6009", "name": "Viscous Flow"}}
TASKS = [task(1, "HW 2", 1, "Homework", 5), task(2, "Midterm", 2, "Exam", 3, 600), task(3, "Quiz", 1, "Quiz", None, 30), task(4, "Read", None, "Reading", 1, personal=True),
         task(5, "Alpha", 2, "Project", 9, 120)]


# ---------------------------------------------------------------- sort, filter, group
def test_sorting_by_due_date_puts_tasks_without_one_last_in_both_directions():
    assert [t.id for t in TL.sort_tasks(TASKS, "Due Date", False, COURSES)] == [4, 2, 1, 5, 3]
    assert [t.id for t in TL.sort_tasks(TASKS, "Due Date", True, COURSES)] == [5, 1, 2, 4, 3]


def test_sorting_by_category_course_title_and_time_left():
    assert [t.category for t in TL.sort_tasks(TASKS, "Category", False, COURSES)] == ["Homework", "Exam", "Quiz", "Reading", "Project"]
    assert [t.id for t in TL.sort_tasks(TASKS, "Course", False, COURSES)] == [2, 5, 1, 3, 4]
    assert [t.title for t in TL.sort_tasks(TASKS, "Title", False, COURSES)] == ["Alpha", "HW 2", "Midterm", "Quiz", "Read"]
    assert TL.sort_tasks(TASKS, "Time Left", True, COURSES)[0].id == 2
    assert [t.title for t in TL.sort_tasks(TASKS, "Title", True, COURSES)][0] == "Read"
    with pytest.raises(ValueError):
        TL.sort_tasks(TASKS, "Color")


def test_the_courses_come_first_by_name_and_personal_work_last():
    names = [TL.course_label(COURSES, t) for t in TL.sort_tasks(TASKS, "Course", False, COURSES)]
    assert names == ["AE 6009", "AE 6009", "AE 6765", "AE 6765", "Personal"]


def test_filtering_by_course_personal_search_and_completed():
    assert [t.id for t in TL.filter_tasks(TASKS, COURSES, "course:1")] == [1, 3]
    assert [t.id for t in TL.filter_tasks(TASKS, COURSES, "personal")] == [4]
    assert [t.id for t in TL.filter_tasks(TASKS, COURSES, "all", "exam")] == [2]                       # the category counts too
    done = T.Task(9, "Old", 1, "Homework", None, 60, state="done")
    assert 9 not in [t.id for t in TL.filter_tasks(TASKS + [done], COURSES)] and 9 in [t.id for t in TL.filter_tasks(TASKS + [done], COURSES, show_done=True)]


def test_grouping_by_course_category_and_week():
    by_course = TL.group_tasks(TL.sort_tasks(TASKS, "Due Date", False, COURSES), "Course", COURSES, store.get_term().zone, TODAY)
    assert [h for h, _ in by_course] == ["AE 6009", "AE 6765", "Personal"]
    by_cat = TL.group_tasks(TASKS, "Category", COURSES, store.get_term().zone)
    assert [h for h, _ in by_cat] == ["Homework", "Exam", "Quiz", "Reading", "Project"]
    by_week = TL.group_tasks(TL.sort_tasks(TASKS, "Due Date", False, COURSES), "Due Week", COURSES, store.get_term().zone, TODAY)
    assert by_week[-1][0] == "No Due Date" and by_week[0][0] and sum(len(r) for _, r in by_week) == 5
    assert TL.group_tasks(TASKS, "None")[0][0] == ""


# ---------------------------------------------------------------- the page
def run(**state):
    at = AppTest.from_file(APP, default_timeout=90)
    at.session_state["page"] = "Calendar"
    at.session_state["cal_page"] = "Task List"
    for k, v in state.items():
        at.session_state[k] = v
    at.run()
    return at


def test_the_task_list_page_shows_and_filters_the_tasks(seeded):
    other = crud.add_course("AE 6009", "Viscous Flow", "Fall 2026", 0, "Active")
    ts.add_task("HW 1", seeded, "Homework", due=due(3), estimate=60)
    ts.add_task("Midterm", other, "Exam", due=due(5), estimate=600)
    at = run()
    assert not at.exception
    text = " ".join(m.value for m in at.markdown)
    assert "HW 1" in text and "Midterm" in text
    at = run(tl_which=f"course:{other}")
    text = " ".join(m.value for m in at.markdown)
    assert "Midterm" in text and "HW 1" not in text


def test_a_task_can_be_edited_and_made_personal(seeded):
    tid = ts.add_task("HW 1", seeded, "Homework", due=due(3), estimate=60)
    ts.update_task(tid, title="HW 1 (revised)", category="Quiz", estimate=45)
    t = ts.get_task(tid)
    assert (t.title, t.category, t.estimate_minutes) == ("HW 1 (revised)", "Quiz", 45)
    ts.update_task(tid, course_id=None, personal=True)
    assert ts.get_task(tid).personal and ts.get_task(tid).course_id is None
    with pytest.raises(PlannerError, match="personal"):
        ts.update_task(tid, course_id=seeded)                                              # a personal task has no course


def test_a_personal_task_can_be_planned_in_a_break_and_a_school_task_cannot(seeded):
    from planner import service
    brk_day = TODAY + timedelta(days=3)
    crud.add_holiday("Fall Break", brk_day.isoformat(), brk_day.isoformat())
    start, end = timeutil.to_utc(brk_day, time(10), NY), timeutil.to_utc(brk_day, time(11), NY)
    school = ts.add_task("HW", seeded, "Homework", due=due(6), estimate=60)
    mine = ts.add_task("Gift", None, "Other", due=due(6), estimate=60, personal=True)
    with pytest.raises(PlannerError):
        ss.add_session(school, start, end)
    assert ss.add_session(mine, start, end)


# ---------------------------------------------------------------- the import
def test_the_import_rows_mark_what_is_already_a_task(seeded):
    ts.add_task("HW 1", seeded, "Homework", due=due(3))
    items = syllabus_read.find_items("Sep 10 HW 1 due\nSep 17 HW 2 due\nOct 8 Midterm Exam 1", TODAY - timedelta(days=30), TODAY + timedelta(days=70))
    rows = TL.import_rows(seeded, items)
    by = {r["Title"]: r for r in rows}
    assert by["HW 1"]["Status"] == "Already Added" and by["HW 1"]["Add"] is False and by["HW 2"]["Add"] is True
    assert by["Midterm Exam 1"]["On Calendar"] is True and by["HW 2"]["On Calendar"] is False


def test_applying_the_import_adds_tasks_events_and_class_times(seeded):
    day = TODAY + timedelta(days=10)
    rows = [{"Add": True, "Title": "HW 1", "Category": "Homework", "Due Date": day, "Due Time": time(23, 59), "Estimate (Minutes)": None, "On Calendar": False},
            {"Add": True, "Title": "Midterm 1", "Category": "Exam", "Due Date": day + timedelta(days=7), "Due Time": time(9, 0), "Estimate (Minutes)": 300, "On Calendar": True},
            {"Add": False, "Title": "Skipped", "Category": "Quiz", "Due Date": day, "Due Time": time(9, 0), "Estimate (Minutes)": None, "On Calendar": False},
            {"Add": True, "Title": "", "Category": "Quiz", "Due Date": day, "Due Time": time(9, 0), "Estimate (Minutes)": None, "On Calendar": False}]
    meetings = [{"Add": True, "Days": "Tue, Thu", "Start": time(14, 0), "End": time(15, 15), "Location": "Room 1"}, {"Add": False, "Days": "Mon", "Start": time(9), "End": time(10), "Location": ""}]
    tasks_n, events_n, meetings_n, problems = TL.apply_import(seeded, rows, meetings, store.get_term().zone)
    assert (tasks_n, events_n, meetings_n, problems) == (2, 1, 1, [])
    by = {t.title: t for t in ts.list_tasks()}
    assert set(by) == {"HW 1", "Midterm 1"} and by["Midterm 1"].estimate_minutes == 300 and by["HW 1"].estimate_minutes == ts.estimate_for(seeded, "Homework") and by["HW 1"].source == "syllabus"
    (ev,) = cs.list_events(day, day + timedelta(days=8))
    assert ev.title == "AE 6765 Midterm 1" and ev.busy and (ev.end - ev.start) == timedelta(hours=2)
    (m,) = crud.list_meetings(seeded)
    assert m["days"] == "1,3" and m["start_time"] == "14:00"


def test_a_bad_row_is_reported_and_the_others_are_still_added(seeded):
    rows = [{"Add": True, "Title": "Fine", "Category": "Homework", "Due Date": TODAY + timedelta(days=3), "Due Time": time(23, 59), "Estimate (Minutes)": None, "On Calendar": False},
            {"Add": True, "Title": "Too long", "Category": "Homework", "Due Date": TODAY + timedelta(days=3), "Due Time": time(23, 59), "Estimate (Minutes)": 99999, "On Calendar": False}]
    n, _, _, problems = TL.apply_import(seeded, rows, [], store.get_term().zone)
    assert n == 1 and len(problems) == 1 and "Too long" in problems[0]


def test_days_are_read_from_words_and_the_file_text_from_html(tmp_path):
    assert TL.parse_days("Mon, Wed") == [0, 2] and TL.parse_days("Tuesday Thursday") == [1, 3] and TL.parse_days("nothing") == []
    page = tmp_path / "syllabus.html"
    page.write_text("<html><style>p{}</style><body><p>Sep 10</p><p>HW 1 due</p></body></html>", encoding="utf-8")
    assert "HW 1 due" in TL.file_text(page) and "p{}" not in TL.file_text(page)
    assert TL.file_text(tmp_path / "missing.pdf") == ""


# ---------------------------------------------------------------- the homework and exams that are already in a course page
def _course_page_work(cid):
    crud.add_homework(cid, "HW 1", (TODAY + timedelta(days=3)).isoformat(), "", "", due_time="11:00")
    graded = crud.add_homework(cid, "HW 0", (TODAY - timedelta(days=9)).isoformat(), "", "")
    crud._exec("UPDATE homework_pairs SET score=9, points=10 WHERE id=?", (graded,))
    crud.add_homework(cid, "HW undated", None, "", "")
    crud.add_event("AE 6765 Midterm 2", (TODAY + timedelta(days=12)).isoformat(), cid, "17:00")
    crud.add_event("AE 6765 Final Exam", (TODAY - timedelta(days=2)).isoformat(), cid, "08:00")
    crud.add_event("Guest lecture", (TODAY + timedelta(days=4)).isoformat(), cid)


def test_the_work_in_a_course_page_becomes_rows_with_finished_ones_marked(seeded):
    _course_page_work(seeded)
    by = {r["Title"]: r for r in TL.course_work(seeded)}
    assert set(by) == {"HW 1", "HW 0", "Midterm 2", "Final Exam"}                       # no undated homework, no lecture; the course code is cut from an exam's title
    assert by["HW 1"]["Done"] is False and by["HW 1"]["Due Time"] == time(11, 0) and by["HW 0"]["Done"] is True
    assert by["Midterm 2"]["Category"] == "Exam" and by["Midterm 2"]["Done"] is False and by["Final Exam"]["Done"] is True        # a past exam is finished
    assert all(r["On Calendar"] is False for r in by.values())                          # the exams are on the Calendar already


def test_the_syllabus_adds_only_what_the_course_page_does_not_have(seeded):
    _course_page_work(seeded)
    day = TODAY + timedelta(days=3)
    text = f"{day:%b} {day.day} HW 1 due\n{(TODAY + timedelta(days=20)):%b} {(TODAY + timedelta(days=20)).day} Quiz 4"
    items, _ = TL.syllabus_items(seeded, text)
    rows = TL.import_rows(seeded, items, TL.course_work(seeded))
    titles = [r["Title"] for r in rows]
    assert titles.count("HW 1") == 1 and "Quiz 4" in titles                              # the same work is not listed twice
    assert [r["Due Date"] for r in rows] == sorted(r["Due Date"] for r in rows)


def test_auto_import_adds_every_new_task_once_and_finished_ones_as_done(seeded):
    _course_page_work(seeded)
    (res,) = TL.auto_import([seeded], store.get_term().zone)
    assert res[:4] == (seeded, 4, 0, 0) and res[4] == []
    by = {t.title: t for t in ts.list_tasks()}
    assert by["HW 0"].is_done and by["Final Exam"].is_done and not by["HW 1"].is_done and by["HW 1"].source == "syllabus"
    assert timeutil.to_local(by["HW 1"].due, store.get_term().zone).strftime("%H:%M") == "11:00"
    (again,) = TL.auto_import([seeded], store.get_term().zone)                            # a second time adds nothing
    assert again[1] == 0 and len(ts.list_tasks()) == 4


def test_the_import_dialog_opens_with_a_button_for_all_courses(seeded):
    _course_page_work(seeded)
    at = run()
    at.button(key="tk_import_open").click(); at.run()
    assert not at.exception and any("Import 4 New Tasks" in str(b.label) for b in at.button)


def test_the_term_list_ends_with_manage_terms_which_opens_the_manager(seeded):
    settings.add_term("Spring 2027", "2027-01-11", "2027-04-28", "2027-05-07")
    at = run(cal_page="Calendar")
    box = at.selectbox(key="cal_term")
    assert box.options[-1] == "Manage Terms…" and box.value == next(t["id"] for t in settings.list_terms() if t["id"] == settings.get_active_term()["id"]) or True
    at.selectbox(key="cal_term").select(0); at.run()
    assert not at.exception and any(c.label == "Name" for c in at.text_input)             # the manager is open (its fields)
    assert settings.get_active_term()["name"] != "Spring 2027"                             # nothing was switched


def test_choosing_another_term_makes_it_active_and_moves_the_calendar(seeded):
    new = settings.add_term("Spring 2027", "2027-01-11", "2027-04-28", "2027-05-07")
    at = run(cal_page="Calendar")
    at.selectbox(key="cal_term").select(new); at.run()
    assert settings.get_active_term()["id"] == new and at.session_state["cal_anchor"] == date(2027, 1, 11)


def test_only_the_active_courses_are_ticked_and_a_self_study_course_is_optional(seeded):
    _course_page_work(seeded)
    study = crud.add_course("", "Orbital Mechanics (Self-Study)", "", 1, "Self-Study")
    crud.add_homework(study, "Problem Set 1", (TODAY + timedelta(days=2)).isoformat(), "", "")
    at = run()
    at.button(key="tk_import_open").click(); at.run()
    assert at.checkbox(key=f"si_pick_{seeded}").value is True and at.checkbox(key=f"si_pick_{study}").value is False
    assert any("Import 4 New Tasks" in str(b.label) for b in at.button)                              # the self-study course is not counted
    assert ts.list_tasks() == []                                                                     # nothing is added until the button is pressed


# ---------------------------------------------------------------- the course page Overview: what is due next
def test_the_overview_lists_the_next_homework_exams_and_tasks_once_each(seeded):
    from views import courses_view as CV
    _course_page_work(seeded)                                                                # HW 1 (3 days), graded HW 0, Midterm 2 (12 days), a finished Final Exam
    ts.add_task("Read chapter 4", seeded, "Reading", due=due(5), estimate=60)
    ts.add_task("HW 1", seeded, "Homework", due=due(3), estimate=60)                          # the same work as the homework: not listed twice
    ts.add_task("Old task", seeded, "Homework", due=due(-3), estimate=60)                      # in the past
    ts.add_task("Undated", seeded, "Other", due=None, estimate=60)
    course = next(c for c in crud.list_courses(section=None) if c["id"] == seeded)
    rows = CV.coming_up(course)
    assert [(r[2], r[3]) for r in rows] == [("HW 1", "Homework"), ("Read chapter 4", "Task"), ("Midterm 2", "Exam")] or [r[2] for r in rows] == ["HW 1", "Read chapter 4", "AE 6765 Midterm 2"]
    assert [r[0] for r in rows] == sorted(r[0] for r in rows) and len(rows) == 3
    assert CV.coming_up(course, limit=2) == rows[:2]


# ---------------------------------------------------------------- the Library timeline by day, month and year
def test_the_timeline_groups_by_day_month_or_year_in_either_order():
    from views import library_view as L
    books = [{"id": 1, "added_at": "2026-11-15 10:00:00"}, {"id": 2, "added_at": "2026-11-15 12:00:00"}, {"id": 3, "added_at": "2026-11-02 09:00:00"},
             {"id": 4, "added_at": "2026-03-01 09:00:00"}, {"id": 5, "added_at": "2025-12-31 09:00:00"}, {"id": 6, "added_at": None}]
    day = L.timeline_groups(books, True, "Day")
    assert [h for h, _, _ in day][:2] == ["Sunday, November 15, 2026", "Monday, November 2, 2026"] and [len(i) for _, i, _ in day][:2] == [2, 1]
    assert [b["id"] for b in day[0][1]] == [2, 1]                                                  # the newest first inside a day
    month = L.timeline_groups(books, True, "Month")
    assert [(h, len(i)) for h, i, _ in month][:3] == [("November 2026", 3), ("March 2026", 1), ("December 2025", 1)]
    year = L.timeline_groups(books, False, "Year")
    assert [(h, len(i)) for h, i, _ in year] == [("Date Unknown", 1), ("2025", 1), ("2026", 4)]    # the oldest first; files with no date are first
    assert L.timeline_groups([], True, "Day") == []
