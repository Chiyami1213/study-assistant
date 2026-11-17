"""The safety copies can be kept in a folder the student chooses (OneDrive, another drive): the snapshots of the app and the copies made before a merge, an import or a delete go there."""
import pytest

from core import crud, database, settings
from datafiles import backup, libbackup
from library import coursemerge

pytestmark = pytest.mark.usefixtures("fresh_data")


@pytest.fixture(autouse=True)
def usual(monkeypatch):
    monkeypatch.delenv("STUDY_ASSISTANT_BACKUPS", raising=False)
    settings.set_backups_dir("")
    yield
    settings.set_backups_dir("")


def test_the_usual_folder_is_inside_the_data_folder_and_the_chosen_one_replaces_it(tmp_path):
    assert database.backups_dir() == database.DATA_DIR / "Backups" and backup.root() == database.DATA_DIR / "Backups" / "Snapshots"
    assert libbackup.default_dir() == database.DATA_DIR / "Backups" / "Library"
    settings.set_backups_dir(str(tmp_path / "OneDrive" / "Backups"))
    assert settings.get_backups_dir() == str(tmp_path / "OneDrive" / "Backups") and database.backups_dir() == tmp_path / "OneDrive" / "Backups"
    assert backup.root() == tmp_path / "OneDrive" / "Backups" / "Snapshots" and libbackup.default_dir() == tmp_path / "OneDrive" / "Backups" / "Library"
    settings.set_backups_dir("   ")                                                                      # an empty choice goes back to the usual folder
    assert database.backups_dir() == database.DATA_DIR / "Backups"


def test_the_environment_variable_wins_for_tests(tmp_path, monkeypatch):
    settings.set_backups_dir(str(tmp_path / "chosen"))
    monkeypatch.setenv("STUDY_ASSISTANT_BACKUPS", str(tmp_path / "env"))
    assert database.backups_dir() == tmp_path / "env"


def test_a_snapshot_and_the_copy_before_a_merge_are_made_in_the_chosen_folder(tmp_path):
    settings.set_backups_dir(str(tmp_path / "safe"))
    made = backup.run(force=True)
    assert made is not None and tmp_path / "safe" / "Snapshots" in made.parents and (made / "study.db").exists()
    a = crud.add_course("MA 266", "Differential Equations", "Fall 2026", 0, "Active")
    b = crud.add_course("MA 303", "Differential Equations", "Fall 2026", 0, "Active")
    result = coursemerge.merge(a, [b], {a: "MA 266", b: "MA 303"})
    assert tmp_path / "safe" in result["backup"].parents and (result["backup"] / "study.db").exists()
    assert not list((database.DATA_DIR / "Backups").glob("Before Merge *"))                                  # nothing went to the old place
