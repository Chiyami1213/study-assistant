"""Tests never touch the real data folder: STUDY_ASSISTANT_DATA points at a temporary folder before any module of the app is imported."""
import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

_TMP = tempfile.mkdtemp(prefix="sa-tests-")
os.environ["STUDY_ASSISTANT_DATA"] = _TMP
atexit.register(shutil.rmtree, _TMP, ignore_errors=True)         # a folder made by this run
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def fresh_data():
    """An empty database and settings file for one test (the tables are emptied: Windows will not delete a database file that a connection still holds)."""
    import database
    import settings
    database.init_db()
    with database.get_conn() as conn:
        for table in ("planner_settings", "planner_awake", "holidays", "meeting_exceptions", "activity_meetings", "activities", "events", "study_sessions", "tasks", "task_defaults", "class_meetings", "courses"):
            conn.execute(f"DELETE FROM {table}")
        conn.commit()
    for f in (settings.SETTINGS_FILE, settings.SETTINGS_BACKUP):
        Path(f).unlink(missing_ok=True)
    yield
