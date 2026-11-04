"""Database helper functions (CRUD) used by the Streamlit views."""
import re
from datetime import date, timedelta

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


def add_course(code, name, semester, target_hours, status="Active"):
    cid = _exec("INSERT INTO courses(code,name,semester,target_hours) VALUES (?,?,?,?)",
                (code, name, semester, target_hours))
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


def add_homework(course_id, title, due_date, problem_md, solution_md, problem_file=None, solution_file=None):
    return _exec("""INSERT INTO homework_pairs(course_id,title,due_date,problem_md,solution_md,
                    problem_file,solution_file) VALUES (?,?,?,?,?,?,?)""",
                 (course_id, title, due_date, problem_md, solution_md, problem_file, solution_file))


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
def list_books():
    return _all("SELECT b.*, c.code AS course_code, c.name AS course_name FROM books b "
                "LEFT JOIN courses c ON c.id=b.course_id ORDER BY b.title COLLATE NOCASE")


def get_book(book_id):
    return _one("SELECT * FROM books WHERE id=?", (book_id,))


def add_book(title, author, edition, pdf_path, total_pages, course_id=None):
    return _exec("INSERT INTO books(title,author,edition,pdf_path,total_pages,course_id) VALUES (?,?,?,?,?,?)",
                 (title, author or None, edition or None, pdf_path, total_pages, course_id))


def update_book(book_id, title, author, edition):
    _exec("UPDATE books SET title=?, author=?, edition=? WHERE id=?",
          (title, author or None, edition or None, book_id))


def delete_book(book_id):
    _exec("DELETE FROM books WHERE id=?", (book_id,))
