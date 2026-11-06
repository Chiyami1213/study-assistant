"""SQLite connection, schema (DDL) and seed data for Study Assistant."""
import re
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "data" / "study.db"
PDF_DIR = BASE_DIR / "data" / "pdfs"

USER_COURSES = [  # (code, name, sidebar icon)
    ("AE 6009", "Viscous Fluid Flow", "svg:boundary_layer"),
    ("AE 6451", "Electric Propulsion", "svg:ion_rings"),
    ("AE 6765", "Kinetics & Thermodynamics of Gases", ":material/thermostat:"),
    ("PHYS 6105", "Quantum Mechanics I", "svg:spin_electron"),
]

LIBRARY_COURSES = [  # custom subjects without a course number: (name, sidebar icon)
    ("Anatomy", "svg:anatomy_body"),
    ("Tonal Harmony", ":material/piano:"),
    ("Macroeconomics", "svg:macro_globe"),
    ("Pyrochemistry", "svg:flame"),
]

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS courses (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    code           TEXT NOT NULL,
    name           TEXT NOT NULL,
    semester       TEXT NOT NULL,
    school         TEXT,
    photo_file     TEXT,  -- file name of the course photo in data/course_photos
    category       TEXT,
    color          TEXT,  -- tile color (NULL = default from palette)
    is_active      INTEGER NOT NULL DEFAULT 1,
    target_hours   REAL NOT NULL DEFAULT 0,
    icon           TEXT,
    sort_order     INTEGER,  -- manual order within a sidebar section (NULL = default order)
    section        TEXT NOT NULL DEFAULT 'courses',  -- 'courses' (numbered) | 'library' (custom)
    created_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS syllabus_topics (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id   INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    week        INTEGER,
    title       TEXT NOT NULL,
    completed   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS study_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id   INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    hours       REAL NOT NULL,
    note        TEXT,
    logged_on   TEXT NOT NULL DEFAULT (date('now'))
);

-- Reference material (textbook PDFs). pdf_path may be NULL until uploaded.
CREATE TABLE IF NOT EXISTS references_ (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id   INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    pdf_path    TEXT,
    total_pages INTEGER
);

-- body_md = prose/history, derivation_md = collapsible step-by-step,
-- key_formula = LaTeX for the exam formula sheet, importance: 'core' | 'detail'
CREATE TABLE IF NOT EXISTS notes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id     INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    reference_id  INTEGER REFERENCES references_(id) ON DELETE SET NULL,
    title         TEXT NOT NULL,
    body_md       TEXT NOT NULL DEFAULT '',
    derivation_md TEXT,
    key_formula   TEXT,
    importance    TEXT NOT NULL DEFAULT 'detail' CHECK (importance IN ('core','detail')),
    ref_page      INTEGER,
    position      INTEGER NOT NULL DEFAULT 0,
    updated_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS errata (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id     INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    note_id       INTEGER REFERENCES notes(id) ON DELETE SET NULL,
    reference_id  INTEGER REFERENCES references_(id) ON DELETE SET NULL,
    page          INTEGER,
    description   TEXT NOT NULL,
    correction    TEXT,
    status        TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','resolved')),
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS homework_pairs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id     INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    title         TEXT NOT NULL,
    due_date      TEXT,
    due_time      TEXT,   -- 'HH:MM' (optional)
    problem_md    TEXT,
    solution_md   TEXT,
    problem_file  TEXT,
    solution_file TEXT,
    status        TEXT NOT NULL DEFAULT 'todo' CHECK (status IN ('todo','attempted','verified'))
);

-- Flashcards using Leitner boxes (box 1..5).
CREATE TABLE IF NOT EXISTS quizzes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id    INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    note_id      INTEGER REFERENCES notes(id) ON DELETE SET NULL,
    question     TEXT NOT NULL,
    answer       TEXT NOT NULL,
    box          INTEGER NOT NULL DEFAULT 1,
    times_right  INTEGER NOT NULL DEFAULT 0,
    times_wrong  INTEGER NOT NULL DEFAULT 0,
    next_review  TEXT NOT NULL DEFAULT (date('now'))
);

-- Calendar events (homework due dates come from homework_pairs).
CREATE TABLE IF NOT EXISTS events (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    title     TEXT NOT NULL,
    date      TEXT NOT NULL,
    course_id INTEGER REFERENCES courses(id) ON DELETE SET NULL,
    time      TEXT,         -- 'HH:MM' (optional)
    end_time  TEXT          -- 'HH:MM' (optional)
);

-- Library books / PDFs (stored under data/pdfs). course_id is optional.
CREATE TABLE IF NOT EXISTS books (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    author      TEXT,
    kind        TEXT NOT NULL DEFAULT 'Textbook',  -- 'Textbook' | 'Notes'
    edition     TEXT,
    year        TEXT,
    lecture     TEXT,  -- lecture number(s) for notes, e.g. '3' or '3-4'
    pdf_path    TEXT NOT NULL,
    total_pages INTEGER,
    course_id   INTEGER REFERENCES courses(id) ON DELETE SET NULL,
    added_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- A file can belong to several courses (books.course_id only mirrors the first one for older code).
CREATE TABLE IF NOT EXISTS book_courses (
    book_id   INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    PRIMARY KEY (book_id, course_id)
);

-- Weekly class meetings of a course. days = weekday numbers (Mon=0 ... Sun=6), e.g. "1,3" = Tue and Thu.
CREATE TABLE IF NOT EXISTS class_meetings (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id  INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    days       TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time   TEXT NOT NULL,
    location   TEXT
);

-- Days off inside the term (no classes). Both dates are inclusive.
CREATE TABLE IF NOT EXISTS holidays (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date   TEXT NOT NULL
);

-- Web links of a course (class pages, syllabus, ...).
CREATE TABLE IF NOT EXISTS course_links (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    title     TEXT NOT NULL,
    url       TEXT NOT NULL
);

-- Lab: notes being built next to a reference file.
CREATE TABLE IF NOT EXISTS lab_notes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT NOT NULL DEFAULT 'Untitled Note',
    notes      TEXT NOT NULL DEFAULT '',
    exercises  TEXT NOT NULL DEFAULT '',
    summary    TEXT NOT NULL DEFAULT '',
    course_id  INTEGER REFERENCES courses(id) ON DELETE SET NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Note Builder: one notebook per course, made of chapters.
CREATE TABLE IF NOT EXISTS lab_chapters (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id  INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    title      TEXT NOT NULL DEFAULT 'Untitled Chapter',
    notes      TEXT NOT NULL DEFAULT '',
    exercises  TEXT NOT NULL DEFAULT '',
    position   INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    source_book_id INTEGER              -- the Library note the chapter was started from (its quiz questions)
);

-- Quiz attempts: one row per finished quiz (a chapter or lecture of a course).
CREATE TABLE IF NOT EXISTS quiz_attempts (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    book_id   INTEGER NOT NULL,
    taken_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    correct   INTEGER NOT NULL,
    total     INTEGER NOT NULL,
    answers   TEXT,
    assisted  INTEGER NOT NULL DEFAULT 0,  -- correct answers made with the notes or a hint
    notes_used INTEGER NOT NULL DEFAULT 0, -- questions where Check Notes was used
    hints_used INTEGER NOT NULL DEFAULT 0  -- questions where Hint was used
);

-- Notes exported from the Note Builder; the File page lists them under their course.
CREATE TABLE IF NOT EXISTS exported_notes (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    source_note_id INTEGER,
    course_id      INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    title          TEXT NOT NULL,
    notes          TEXT NOT NULL DEFAULT '',
    exercises      TEXT NOT NULL DEFAULT '',
    exported_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Course outline: main topics ('I') with sub topics ('A'), in page order.
CREATE TABLE IF NOT EXISTS course_outline (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    position  INTEGER NOT NULL,
    level     TEXT NOT NULL,
    marker    TEXT NOT NULL,
    title     TEXT NOT NULL,
    hours     TEXT,
    url       TEXT,
    book_id   INTEGER,   -- Library file the point links to (opens its preview)
    page      INTEGER    -- page of that file
);

CREATE INDEX IF NOT EXISTS idx_notes_course  ON notes(course_id);
CREATE INDEX IF NOT EXISTS idx_errata_course ON errata(course_id);
CREATE INDEX IF NOT EXISTS idx_quiz_review   ON quizzes(course_id, next_review);
"""


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with get_conn() as conn:
        had_links = conn.execute("SELECT 1 FROM sqlite_master WHERE name='book_courses'").fetchone()
        conn.executescript(SCHEMA)
        if not had_links:    # first run with multi-course files: carry over each file's single course
            conn.execute("INSERT OR IGNORE INTO book_courses(book_id, course_id) "
                         "SELECT id, course_id FROM books WHERE course_id IS NOT NULL")
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(courses)")]
        if "icon" not in cols:  # migrate databases created before icons existed
            conn.execute("ALTER TABLE courses ADD COLUMN icon TEXT")
        book_cols = [r["name"] for r in conn.execute("PRAGMA table_info(books)")]
        if "lecture" not in book_cols:
            conn.execute("ALTER TABLE books ADD COLUMN lecture TEXT")
            from pdfmeta import split_lecture
            for row in conn.execute("SELECT id, title FROM books WHERE kind IN ('Notes', 'Lecture Notes')").fetchall():
                lecture, title = split_lecture(row["title"])
                if lecture:    # "Lec 2 Notes Measurement..." -> lecture "2", title "Notes Measurement..."
                    conn.execute("UPDATE books SET lecture=?, title=? WHERE id=?", (lecture, title, row["id"]))
        if "year" not in book_cols:
            conn.execute("ALTER TABLE books ADD COLUMN year TEXT")
            for row in conn.execute("SELECT id, edition FROM books WHERE edition IS NOT NULL").fetchall():
                m = re.fullmatch(r"\s*(.*?)\s*\((\d{4})\)\s*", row["edition"])
                if m:      # "7th Edition (2019)" -> edition "7th Edition", year "2019"
                    conn.execute("UPDATE books SET edition=?, year=? WHERE id=?", (m.group(1) or None, m.group(2), row["id"]))
                elif re.fullmatch(r"\d{4}", row["edition"].strip()):   # a bare year
                    conn.execute("UPDATE books SET edition=NULL, year=? WHERE id=?", (row["edition"].strip(), row["id"]))
        if "kind" not in book_cols:
            conn.execute("ALTER TABLE books ADD COLUMN kind TEXT NOT NULL DEFAULT 'Textbook'")
        if "author" not in book_cols:
            conn.execute("ALTER TABLE books ADD COLUMN author TEXT")
        if "time" not in [r["name"] for r in conn.execute("PRAGMA table_info(events)")]:
            conn.execute("ALTER TABLE events ADD COLUMN time TEXT")
        if "book_id" not in [r["name"] for r in conn.execute("PRAGMA table_info(course_outline)")]:
            conn.execute("ALTER TABLE course_outline ADD COLUMN book_id INTEGER")
            conn.execute("ALTER TABLE course_outline ADD COLUMN page INTEGER")
        if "end_time" not in [r["name"] for r in conn.execute("PRAGMA table_info(events)")]:
            conn.execute("ALTER TABLE events ADD COLUMN end_time TEXT")
        if "due_time" not in [r["name"] for r in conn.execute("PRAGMA table_info(homework_pairs)")]:
            conn.execute("ALTER TABLE homework_pairs ADD COLUMN due_time TEXT")
        for table, columns in (("homework_pairs", ("score REAL", "points REAL", "grade_note TEXT")),
                               ("events", ("score REAL", "points REAL", "grade_note TEXT"))):
            have = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})")]
            for column in columns:
                if column.split()[0] not in have:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column}")
        if "course_id" not in [r["name"] for r in conn.execute("PRAGMA table_info(lab_notes)")]:
            conn.execute("ALTER TABLE lab_notes ADD COLUMN course_id INTEGER")
        if "covers" not in [r["name"] for r in conn.execute("PRAGMA table_info(events)")]:
            conn.execute("ALTER TABLE events ADD COLUMN covers TEXT")
        if "source_book_id" not in [r["name"] for r in conn.execute("PRAGMA table_info(lab_chapters)")]:
            conn.execute("ALTER TABLE lab_chapters ADD COLUMN source_book_id INTEGER")
        for col in ("notes_used", "hints_used"):
            if col not in [r["name"] for r in conn.execute("PRAGMA table_info(quiz_attempts)")]:
                conn.execute(f"ALTER TABLE quiz_attempts ADD COLUMN {col} INTEGER NOT NULL DEFAULT 0")
        if "assisted" not in [r["name"] for r in conn.execute("PRAGMA table_info(quiz_attempts)")]:
            conn.execute("ALTER TABLE quiz_attempts ADD COLUMN assisted INTEGER NOT NULL DEFAULT 0")
        if "photo_file" not in cols:
            conn.execute("ALTER TABLE courses ADD COLUMN photo_file TEXT")
        if "category" not in cols:
            conn.execute("ALTER TABLE courses ADD COLUMN category TEXT")
        if "color" not in cols:
            conn.execute("ALTER TABLE courses ADD COLUMN color TEXT")
        if "school" not in cols:
            conn.execute("ALTER TABLE courses ADD COLUMN school TEXT")
        if "sort_order" not in cols:
            conn.execute("ALTER TABLE courses ADD COLUMN sort_order INTEGER")
        if "section" not in cols:
            conn.execute("ALTER TABLE courses ADD COLUMN section TEXT NOT NULL DEFAULT 'courses'")
        have = {r["name"] for r in conn.execute("SELECT name FROM courses")}
        for name, icon in LIBRARY_COURSES:
            if name not in have:
                conn.execute("INSERT INTO courses(code,name,icon,section,semester,target_hours) "
                             "VALUES ('',?,?,'library','',0)", (name, icon))
        if conn.execute("SELECT COUNT(*) FROM courses").fetchone()[0] == 0:
            _seed(conn)


def _seed(conn: sqlite3.Connection) -> None:
    conn.executemany("INSERT INTO courses(code,name,icon,semester,target_hours) VALUES (?,?,?,?,?)",
                     [(c, n, i, "Fall 2026", 60) for c, n, i in USER_COURSES])
    conn.execute("INSERT INTO courses(code,name,icon,is_active,semester,target_hours) "
                 "VALUES ('AAE 532','Orbital Mechanics','svg:orbit_planet',0,'',0)")  # completed
    conn.commit()


if __name__ == "__main__":
    init_db()
    print(f"Database ready at {DB_PATH}")
