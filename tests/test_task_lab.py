"""The task category Lab, and a database made before it existed (its CHECK is widened in place, nothing is lost)."""
import sqlite3

import pytest

import database
from planner import tasks as T

pytestmark = pytest.mark.usefixtures("fresh_data")


def test_lab_is_a_category_with_a_default_estimate():
    assert "Lab" in T.CATEGORIES and T.DEFAULT_ESTIMATES["Lab"] > 0
    assert set(T.DEFAULT_ESTIMATES) == set(T.CATEGORIES)


def test_an_old_database_accepts_lab_after_the_start_up_check_and_keeps_its_tasks():
    old = "'Quiz','Reading','Project','Other')"
    conn = sqlite3.connect(database.DB_PATH)
    conn.execute("PRAGMA writable_schema=ON")
    for name in ("tasks", "task_defaults"):                                   # make the tables look like the ones of an older version
        sql = conn.execute("SELECT sql FROM sqlite_master WHERE name=?", (name,)).fetchone()[0]
        conn.execute("UPDATE sqlite_master SET sql=? WHERE name=?", (sql.replace("'Quiz','Reading','Project','Lab','Other')", old), name))
    version = conn.execute("PRAGMA schema_version").fetchone()[0]
    conn.execute(f"PRAGMA schema_version={version + 1}")
    conn.commit()
    conn.close()
    conn = sqlite3.connect(database.DB_PATH)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO tasks(title, category, estimate_minutes, created_utc) VALUES ('x', 'Lab', 60, 't')")
    conn.execute("INSERT INTO tasks(title, category, estimate_minutes, created_utc) VALUES ('keep', 'Quiz', 30, 't')")
    conn.commit()
    conn.close()
    database.init_db()
    database.init_db()                                                         # a second start changes nothing
    with database.get_conn() as c:
        c.execute("INSERT INTO tasks(title, category, estimate_minutes, created_utc) VALUES ('lab one', 'Lab', 60, 't')")
        c.commit()
        assert [tuple(r) for r in c.execute("SELECT title, category FROM tasks ORDER BY id")] == [("keep", "Quiz"), ("lab one", "Lab")]
        assert c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
