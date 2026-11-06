"""Database helper functions (CRUD) used by the Streamlit views."""
import re
from datetime import date, timedelta

import notesfs
import outline
import settings
from database import get_conn


def _all(sql, params=()):
    with get_conn() as c:
        return [dict(r) for r in c.execute(sql, params).fetchall()]


def _one(sql, params=()):
    rows = _all(sql, params)
    return rows[0] if rows else None


def _exec(sql, params=()):
    with get_conn() as c:
        cur = c.execute(sql, params)
        c.commit()
        return cur.lastrowid


# ---------- Courses & syllabus ----------
def label(course):
    """Display name: just the code when the course has no separate title."""
    if not course["code"]:
        return course["name"]
    return course["code"] if course["name"] == course["code"] else f"{course['code']}: {course['name']}"



def list_courses(active_only=False, section="courses"):
    """section: 'courses' (numbered), 'library' (custom subjects) or None for both."""
    where, params = [], []
    if active_only:
        where.append("is_active=1")
    if section:
        where.append("section=?")
        params.append(section)
    sql = "SELECT * FROM courses" + (" WHERE " + " AND ".join(where) if where else "")
    return _all(sql + " ORDER BY code, id", params)


def get_course(course_id):
    return _one("SELECT * FROM courses WHERE id=?", (course_id,))


STATUSES = ("Active", "Self-Study", "Completed")


def course_status(course):
    """Active = current semester, Completed = finished, Self-Study = non-school (section 'library')."""
    if course["section"] == "library":
        return "Self-Study"
    return "Active" if course["is_active"] else "Completed"


def _natural_key(text):
    """Alphabetical with numbers compared numerically (AE 532 < AE 6009)."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", text or "")]


def courses_by_status(status):
    """Courses in a section: manual drag order first, otherwise alphabetical/numerical."""
    items = [c for c in list_courses(section=None) if course_status(c) == status]
    return sorted(items, key=lambda c: (c["sort_order"] is None, c["sort_order"] or 0,
                                        _natural_key(c["code"] or c["name"])))


def set_course_order(course_ids):
    """Persist a manual order for the given courses (list of ids, first = top)."""
    with get_conn() as conn:
        conn.executemany("UPDATE courses SET sort_order=? WHERE id=?",
                         [(i, cid) for i, cid in enumerate(course_ids)])
        conn.commit()


def set_course_status(course_id, status):
    section = "library" if status == "Self-Study" else "courses"
    _exec("UPDATE courses SET section=?, is_active=? WHERE id=?",
          (section, 0 if status == "Completed" else 1, course_id))


def term_label(course):
    """'Fall 2026, Georgia Tech' - semester and school, whichever are set."""
    return ", ".join(x for x in (course.get("semester"), course.get("school")) if x)


COURSE_PALETTE = ["#2f6fb5", "#2e8b7a", "#8a5a9e", "#c26a3a", "#b5483f", "#4f7a3b",
                  "#a1862f", "#3d5a99", "#a8527a", "#2b8794", "#6b5fa6", "#5b6e7c"]


CATEGORY_HUES = {"Aerospace": 215, "Biology": 140, "Chemistry": 12, "Economics": 45,
                 "Engineering": 180, "Mathematics": 95, "Music": 330, "Physics": 285}


def _category_hue(category):
    """Built-in categories have fixed hues; a custom category gets a stable hue from its name."""
    if category in CATEGORY_HUES:
        return CATEGORY_HUES[category]
    import hashlib
    return int(hashlib.md5(category.lower().encode()).hexdigest()[:4], 16) % 360


def _category_shade(category, course_id):
    """Courses in one category share a hue, with a small shift in hue and lightness per course."""
    import colorsys
    hue = (_category_hue(category) + ((course_id * 7) % 5 - 2) * 5) % 360
    light = (0.34, 0.39, 0.44)[course_id % 3]
    r, g, b = colorsys.hls_to_rgb(hue / 360, light, 0.52)
    return "#{:02x}{:02x}{:02x}".format(int(r * 255), int(g * 255), int(b * 255))


def course_color(course):
    """Tile color: the user's choice, else a shade of the category color, else a palette color."""
    if course.get("color"):
        return course["color"]
    if course.get("category"):
        return _category_shade(course["category"], course["id"])
    return COURSE_PALETTE[course["id"] % len(COURSE_PALETTE)]


def darken(hex_color, factor=0.7):
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return "#{:02x}{:02x}{:02x}".format(int(r * factor), int(g * factor), int(b * factor))


CATEGORIES = ["Aerospace", "Biology", "Chemistry", "Economics", "Engineering", "Mathematics", "Music", "Physics"]


def all_categories():
    """Built-in categories first, then any custom category that a course uses (alphabetical)."""
    used = {c["category"] for c in list_courses(section=None) if c.get("category")}
    return CATEGORIES + sorted(used - set(CATEGORIES), key=str.lower)


def normalize_category(name):
    """Trim a typed category; reuse an existing one that differs only by case."""
    name = " ".join((name or "").split())
    if not name:
        return None
    for existing in all_categories():
        if existing.lower() == name.lower():
            return existing
    return name[0].upper() + name[1:]


def set_course_category(course_id, category):
    """category=None clears the label."""
    _exec("UPDATE courses SET category=? WHERE id=?", (category, course_id))


def update_course_fields(course_id, code, name, semester, school, category):
    _exec("UPDATE courses SET code=?, name=?, semester=?, school=?, category=? WHERE id=?",
          (code, name, semester or "", school or None, category, course_id))


def set_course_color(course_id, color):
    """color=None goes back to the default palette color."""
    _exec("UPDATE courses SET color=? WHERE id=?", (color, course_id))


def update_course_info(course_id, semester, school):
    _exec("UPDATE courses SET semester=?, school=? WHERE id=?", (semester or "", school or None, course_id))


def add_course(code, name, semester, target_hours, status="Active", school=None, category=None):
    cid = _exec("INSERT INTO courses(code,name,semester,school,category,target_hours) VALUES (?,?,?,?,?,?)",
                (code, name, semester, school or None, category, target_hours))
    set_course_status(cid, status)
    return cid


def set_course_active(course_id, active):
    _exec("UPDATE courses SET is_active=? WHERE id=?", (int(active), course_id))


def delete_course(course_id):
    _exec("DELETE FROM courses WHERE id=?", (course_id,))


def course_stats(course_id):
    topics = _one("SELECT COUNT(*) n, COALESCE(SUM(completed),0) done FROM syllabus_topics WHERE course_id=?",
                  (course_id,))
    hours = _one("SELECT COALESCE(SUM(hours),0) h FROM study_log WHERE course_id=?", (course_id,))["h"]
    return {"topics": topics["n"], "done": topics["done"], "hours": hours,
            "pct": topics["done"] / topics["n"] if topics["n"] else 0.0}


def list_topics(course_id):
    return _all("SELECT * FROM syllabus_topics WHERE course_id=? ORDER BY week, id", (course_id,))


def add_topic(course_id, week, title):
    _exec("INSERT INTO syllabus_topics(course_id,week,title) VALUES (?,?,?)", (course_id, week, title))


def set_topic_done(topic_id, done):
    _exec("UPDATE syllabus_topics SET completed=? WHERE id=?", (int(done), topic_id))


def log_hours(course_id, hours, note=""):
    _exec("INSERT INTO study_log(course_id,hours,note) VALUES (?,?,?)", (course_id, hours, note))


def recent_logs(course_id, limit=5):
    return _all("SELECT * FROM study_log WHERE course_id=? ORDER BY id DESC LIMIT ?", (course_id, limit))


# ---------- References & notes ----------
def list_references(course_id):
    return _all("SELECT * FROM references_ WHERE course_id=? ORDER BY id", (course_id,))


def add_reference(course_id, title, pdf_path, total_pages):
    return _exec("INSERT INTO references_(course_id,title,pdf_path,total_pages) VALUES (?,?,?,?)",
                 (course_id, title, pdf_path, total_pages))


def set_reference_pdf(ref_id, pdf_path):
    _exec("UPDATE references_ SET pdf_path=? WHERE id=?", (pdf_path, ref_id))


def list_notes(course_id, core_only=False):
    sql = "SELECT * FROM notes WHERE course_id=?" + (" AND importance='core'" if core_only else "")
    return _all(sql + " ORDER BY position, id", (course_id,))


def add_note(course_id, title, body_md, derivation_md, key_formula, importance, ref_page, reference_id=None):
    pos = _one("SELECT COALESCE(MAX(position),0)+1 p FROM notes WHERE course_id=?", (course_id,))["p"]
    return _exec("""INSERT INTO notes(course_id,reference_id,title,body_md,derivation_md,key_formula,
                    importance,ref_page,position) VALUES (?,?,?,?,?,?,?,?,?)""",
                 (course_id, reference_id, title, body_md, derivation_md or None, key_formula or None,
                  importance, ref_page, pos))


def update_note(note_id, **fields):
    allowed = {"title", "body_md", "derivation_md", "key_formula", "importance", "ref_page"}
    fields = {k: v for k, v in fields.items() if k in allowed}
    if not fields:
        return
    sets = ", ".join(f"{k}=?" for k in fields)
    _exec(f"UPDATE notes SET {sets}, updated_at=CURRENT_TIMESTAMP WHERE id=?", (*fields.values(), note_id))


def delete_note(note_id):
    _exec("DELETE FROM notes WHERE id=?", (note_id,))


# ---------- Errata ----------
def list_errata(course_id, status=None, note_id=None):
    sql, p = "SELECT e.*, n.title AS note_title FROM errata e LEFT JOIN notes n ON n.id=e.note_id WHERE e.course_id=?", [course_id]
    if status:
        sql += " AND e.status=?"; p.append(status)
    if note_id:
        sql += " AND e.note_id=?"; p.append(note_id)
    return _all(sql + " ORDER BY e.status DESC, e.id DESC", p)


def add_erratum(course_id, description, correction=None, note_id=None, reference_id=None, page=None):
    return _exec("""INSERT INTO errata(course_id,note_id,reference_id,page,description,correction)
                    VALUES (?,?,?,?,?,?)""",
                 (course_id, note_id, reference_id, page, description, correction or None))


def set_erratum_status(err_id, status):
    _exec("UPDATE errata SET status=? WHERE id=?", (status, err_id))


def delete_erratum(err_id):
    _exec("DELETE FROM errata WHERE id=?", (err_id,))


# ---------- Homework ----------
def list_homework(course_id):
    return _all("SELECT * FROM homework_pairs WHERE course_id=? ORDER BY due_date", (course_id,))


def add_homework(course_id, title, due_date, problem_md, solution_md, problem_file=None, solution_file=None,
                 due_time=None):
    return _exec("""INSERT INTO homework_pairs(course_id,title,due_date,due_time,problem_md,solution_md,
                    problem_file,solution_file) VALUES (?,?,?,?,?,?,?,?)""",
                 (course_id, title, due_date, due_time, problem_md, solution_md, problem_file, solution_file))


def set_homework_status(hw_id, status):
    _exec("UPDATE homework_pairs SET status=? WHERE id=?", (status, hw_id))


def delete_homework(hw_id):
    _exec("DELETE FROM homework_pairs WHERE id=?", (hw_id,))


# ---------- Quizzes / flashcards ----------
BOX_INTERVAL_DAYS = {1: 0, 2: 1, 3: 3, 4: 7, 5: 14}


def list_cards(course_id):
    return _all("SELECT * FROM quizzes WHERE course_id=? ORDER BY id", (course_id,))


def due_cards(course_id):
    return _all("SELECT * FROM quizzes WHERE course_id=? AND next_review<=date('now') ORDER BY box, id",
                (course_id,))


def add_card(course_id, question, answer, note_id=None):
    return _exec("INSERT INTO quizzes(course_id,note_id,question,answer) VALUES (?,?,?,?)",
                 (course_id, note_id, question, answer))


def delete_card(card_id):
    _exec("DELETE FROM quizzes WHERE id=?", (card_id,))


def grade_card(card_id, correct):
    card = _one("SELECT * FROM quizzes WHERE id=?", (card_id,))
    box = min(card["box"] + 1, 5) if correct else 1
    nxt = (date.today() + timedelta(days=BOX_INTERVAL_DAYS[box])).isoformat()
    _exec("""UPDATE quizzes SET box=?, next_review=?, times_right=times_right+?, times_wrong=times_wrong+?
             WHERE id=?""", (box, nxt, int(correct), int(not correct), card_id))


# ---------- Library books ----------
def _attach_courses(books):
    """Add `course_ids` (every course the file belongs to, in the order they were added) to each book."""
    links = {}
    for r in _all("SELECT book_id, course_id FROM book_courses ORDER BY rowid"):
        links.setdefault(r["book_id"], []).append(r["course_id"])
    for b in books:
        b["course_ids"] = links.get(b["id"], [])
    return books


def _as_ids(course_ids):
    if course_ids is None or course_ids == 0:
        return []
    if isinstance(course_ids, int):
        return [course_ids]
    return [int(i) for i in dict.fromkeys(course_ids) if i]


def set_book_courses(book_id, course_ids):
    ids = _as_ids(course_ids)
    with get_conn() as conn:
        conn.execute("DELETE FROM book_courses WHERE book_id=?", (book_id,))
        conn.executemany("INSERT INTO book_courses(book_id, course_id) VALUES (?,?)", [(book_id, i) for i in ids])
        conn.execute("UPDATE books SET course_id=? WHERE id=?", (ids[0] if ids else None, book_id))
        conn.commit()


def list_books():
    return _attach_courses(_all("SELECT b.* FROM books b ORDER BY b.title COLLATE NOCASE"))


def get_book(book_id):
    row = _one("SELECT * FROM books WHERE id=?", (book_id,))
    return _attach_courses([row])[0] if row else None


def add_book(title, author, edition, pdf_path, total_pages, course_ids=None, kind="Textbook", year=None,
             lecture=None):
    book_id = _exec("INSERT INTO books(title,author,edition,year,lecture,pdf_path,total_pages,kind) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (title, author or None, edition or None, year or None, lecture or None, pdf_path, total_pages, kind))
    set_book_courses(book_id, course_ids)
    return book_id


def update_book(book_id, title, author, edition, kind="Textbook", course_ids=None, year=None, lecture=None):
    _exec("UPDATE books SET title=?, author=?, edition=?, year=?, lecture=?, kind=? WHERE id=?",
          (title, author or None, edition or None, year or None, lecture or None, kind, book_id))
    set_book_courses(book_id, course_ids)


def delete_book(book_id):
    _exec("DELETE FROM books WHERE id=?", (book_id,))


# ---------- Calendar ----------
def list_events(start, end):
    return _all("SELECT * FROM events WHERE date BETWEEN ? AND ? ORDER BY date, id", (start, end))


def add_event(title, day, course_id=None, time=None, end_time=None):
    return _exec("INSERT INTO events(title,date,course_id,time,end_time) VALUES (?,?,?,?,?)",
                 (title, day, course_id, time or None, end_time or None))


def update_event(event_id, title, time, end_time=None):
    _exec("UPDATE events SET title=?, time=?, end_time=? WHERE id=?", (title, time or None, end_time or None, event_id))


def set_event_covers(event_id, text):
    """What an exam covers, e.g. 'HW 4, HW 5; Chapters IV, V, VI'."""
    _exec("UPDATE events SET covers=? WHERE id=?", ((text or "").strip() or None, event_id))


def delete_event(event_id):
    _exec("DELETE FROM events WHERE id=?", (event_id,))


def homework_due_between(start, end):
    return _all("SELECT * FROM homework_pairs WHERE due_date BETWEEN ? AND ? AND status != 'verified' "
                "ORDER BY due_date", (start, end))


# ---------- Class meetings (weekly schedule) ----------
DAY_ABBR = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def list_meetings(course_id=None):
    sql = "SELECT * FROM class_meetings" + (" WHERE course_id=?" if course_id else "") + " ORDER BY start_time, id"
    return _all(sql, (course_id,) if course_id else ())


def add_meeting(course_id, days, start_time, end_time, location=None):
    """days: iterable of weekday numbers (Mon=0 ... Sun=6)."""
    days = ",".join(str(d) for d in sorted(set(days)))
    return _exec("INSERT INTO class_meetings(course_id,days,start_time,end_time,location) VALUES (?,?,?,?,?)",
                 (course_id, days, start_time, end_time, location or None))


def delete_meeting(meeting_id):
    _exec("DELETE FROM class_meetings WHERE id=?", (meeting_id,))


def meeting_days_label(meeting):
    return ", ".join(DAY_ABBR[int(d)] for d in meeting["days"].split(",") if d != "")


def meeting_occurrences(first, last):
    """{date: [occurrence]} for every class meeting between two dates (inclusive), inside the semester dates.

    occurrence = dict(meeting_id, course_id, start 'HH:MM', end 'HH:MM', location)."""
    sem = settings.get_semester()
    lo, hi = max(first, date.fromisoformat(sem["start"])), min(last, date.fromisoformat(sem["end"]))
    meetings = list_meetings()
    off = holiday_days(lo, hi)
    out = {}
    day = lo
    while day <= hi:
        for m in ([] if day in off else meetings):
            if str(day.weekday()) in m["days"].split(","):
                out.setdefault(day, []).append({"meeting_id": m["id"], "course_id": m["course_id"],
                                                "start": m["start_time"], "end": m["end_time"],
                                                "location": m["location"]})
        day += timedelta(days=1)
    for items in out.values():
        items.sort(key=lambda o: (o["start"], o["end"]))
    return out


# ---------- Holidays ----------
def list_holidays():
    return _all("SELECT * FROM holidays ORDER BY start_date, id")


def add_holiday(name, start, end):
    return _exec("INSERT INTO holidays(name,start_date,end_date) VALUES (?,?,?)", (name, start, end))


def delete_holiday(holiday_id):
    _exec("DELETE FROM holidays WHERE id=?", (holiday_id,))


def holiday_days(first, last):
    """{date: holiday name} for every holiday day between two dates (inclusive)."""
    out = {}
    for h in list_holidays():
        day, end = date.fromisoformat(h["start_date"]), date.fromisoformat(h["end_date"])
        while day <= end:
            if first <= day <= last:
                out[day] = h["name"]
            day += timedelta(days=1)
    return out


# ---------- Course links ----------
def normalize_url(url):
    """Add https:// when no scheme is typed; None if it does not look like a web address."""
    url = (url or "").strip()
    if not url:
        return None
    if "://" not in url:
        url = "https://" + url
    return url if url.lower().startswith(("http://", "https://")) and "." in url.split("://", 1)[1] else None


def list_links(course_id):
    return _all("SELECT * FROM course_links WHERE course_id=? ORDER BY id", (course_id,))


def add_link(course_id, title, url):
    url = normalize_url(url)
    if not url:
        return None
    title = (title or "").strip() or url.split("://", 1)[1].rstrip("/")
    return _exec("INSERT INTO course_links(course_id,title,url) VALUES (?,?,?)", (course_id, title, url))


def delete_link(link_id):
    _exec("DELETE FROM course_links WHERE id=?", (link_id,))


# ---------- Course outline ----------
def list_outline(course_id):
    return _all("SELECT * FROM course_outline WHERE course_id=? ORDER BY position", (course_id,))


def replace_outline(course_id, items):
    """Replace a course's outline with items = [{level, marker, title, hours, url}] (in order)."""
    with get_conn() as conn:
        conn.execute("DELETE FROM course_outline WHERE course_id=?", (course_id,))
        conn.executemany(
            "INSERT INTO course_outline(course_id,position,level,marker,title,hours,url,book_id,page) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            [(course_id, i, it["level"], it["marker"], it["title"], it.get("hours") or None, it.get("url") or None,
              it.get("book_id") or None, it.get("page") or None)
             for i, it in enumerate(items)])
        conn.commit()


# ---------- Note Builder: one notebook per course, made of chapters ----------
# A chapter's text lives in files under notes/ (see notesfs.py); the database keeps its title and order.
def _chapter(row):
    if not row:
        return None
    course = get_course(row["course_id"])
    return {**row, **notesfs.load(course, row)} if course else row


def list_chapters(course_id):
    return [_chapter(r) for r in _all("SELECT * FROM lab_chapters WHERE course_id=? ORDER BY position, id", (course_id,))]


def get_chapter(chapter_id):
    return _chapter(_one("SELECT * FROM lab_chapters WHERE id=?", (chapter_id,)))


def add_chapter(course_id, title="Untitled Chapter", notes="", exercises=""):
    if not notes:                                        # a new chapter starts as a standard interactive page
        notes = outline.blank_page(title)
    last = _one("SELECT MAX(position) AS p FROM lab_chapters WHERE course_id=?", (course_id,))["p"]
    cid = _exec("INSERT INTO lab_chapters(course_id,title,notes,exercises,position) VALUES (?,?,?,?,?)",
                (course_id, title, notes, "", (last if last is not None else -1) + 1))
    notesfs.save(get_course(course_id), {"id": cid, "title": title}, {"notes": notes})
    return cid


def update_chapter(chapter_id, title, sections):
    row = _one("SELECT * FROM lab_chapters WHERE id=?", (chapter_id,))
    _exec("UPDATE lab_chapters SET title=?, notes=?, exercises=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
          (title, sections.get("notes", ""), "", chapter_id))
    notesfs.save(get_course(row["course_id"]), {**row, "title": title}, sections)    # renames the folder with the title


def delete_chapter(chapter_id):
    row = _one("SELECT * FROM lab_chapters WHERE id=?", (chapter_id,))
    if row:
        notesfs.trash(get_course(row["course_id"]), row)
    _exec("DELETE FROM lab_chapters WHERE id=?", (chapter_id,))


def export_chapter(chapter_id):
    """Copy a chapter to the File page under its course (exporting again replaces the earlier copy)."""
    ch = get_chapter(chapter_id)
    if not ch:
        return None
    _exec("DELETE FROM exported_notes WHERE source_note_id=?", (chapter_id,))
    return _exec("INSERT INTO exported_notes(source_note_id,course_id,title,notes,exercises) VALUES (?,?,?,?,?)",
                 (chapter_id, ch["course_id"], ch["title"], ch["notes"], ""))


def list_exported_notes(course_id):
    return _all("SELECT * FROM exported_notes WHERE course_id=? ORDER BY exported_at DESC, id DESC", (course_id,))


def delete_exported_note(export_id):
    _exec("DELETE FROM exported_notes WHERE id=?", (export_id,))


# ---------- Quizzes ----------
def add_quiz_attempt(course_id, book_id, correct, total, answers=None, assisted=0):
    return _exec("INSERT INTO quiz_attempts(course_id,book_id,correct,total,answers,assisted) VALUES (?,?,?,?,?,?)",
                 (course_id, book_id, correct, total, answers, assisted))


def quiz_stats(course_id):
    """{book id: {attempts, last_correct, last_total, last_assisted, best (best unaided percent), last_at}}."""
    rows = _all("SELECT * FROM quiz_attempts WHERE course_id=? ORDER BY id", (course_id,))
    out = {}
    for r in rows:
        s = out.setdefault(r["book_id"], {"attempts": 0, "best": 0})
        s["attempts"] += 1
        s["best"] = max(s["best"], round(100 * (r["correct"] - r["assisted"]) / r["total"]) if r["total"] else 0)
        s.update(last_correct=r["correct"], last_total=r["total"], last_assisted=r["assisted"], last_at=r["taken_at"])
    return out
