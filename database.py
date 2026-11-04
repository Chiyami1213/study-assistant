"""SQLite connection, schema (DDL) and seed data for Study Assistant."""
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "data" / "study.db"
PDF_DIR = BASE_DIR / "data" / "pdfs"

USER_COURSES = [  # (code, name, sidebar icon)
    ("AE 6009", "Viscous Fluid Flow", "svg:flow_cylinder"),
    ("AE 6451", "Electric Propulsion", "svg:ion_rings"),
    ("AE 6765", "Kinetics & Thermodynamics of Gases", ":material/thermostat:"),
    ("PHYS 6105", "Quantum Mechanics I", "svg:spin_electron"),
]

LIBRARY_COURSES = [  # custom subjects without a course number: (name, sidebar icon)
    ("Anatomy", "svg:anatomy_body"),
    ("Tonal Harmony", ":material/piano:"),
    ("Macroeconomics", "svg:macro_globe"),
    ("Thermodynamics", "svg:steam_engine"),
]

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS courses (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    code           TEXT NOT NULL,
    name           TEXT NOT NULL,
    semester       TEXT NOT NULL,
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

-- Library books / PDFs (stored under data/pdfs). course_id is optional.
CREATE TABLE IF NOT EXISTS books (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    author      TEXT,
    edition     TEXT,
    pdf_path    TEXT NOT NULL,
    total_pages INTEGER,
    course_id   INTEGER REFERENCES courses(id) ON DELETE SET NULL,
    added_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
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
        conn.executescript(SCHEMA)
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(courses)")]
        if "icon" not in cols:  # migrate databases created before icons existed
            conn.execute("ALTER TABLE courses ADD COLUMN icon TEXT")
        book_cols = [r["name"] for r in conn.execute("PRAGMA table_info(books)")]
        if "author" not in book_cols:
            conn.execute("ALTER TABLE books ADD COLUMN author TEXT")
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
