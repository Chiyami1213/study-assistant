"""Report an Issue: screenshots are collected into one folder, and the report says how many to drag in."""
import os
import time

import helpinfo


def test_report_mentions_the_screenshots():
    _, body = helpinfo.build_report("Something Is Not Working", "x", "details", screenshots=2)
    assert "Drag the 2 pictures" in body
    _, body = helpinfo.build_report("Something Is Not Working", "x", "details", screenshots=1)
    assert "Drag the 1 picture " in body
    _, body = helpinfo.build_report("Something Is Not Working", "x", "details")
    assert "Screenshots" not in body


def test_uploaded_and_saved_pictures_are_copied_with_plain_names(tmp_path, monkeypatch):
    monkeypatch.setattr(helpinfo, "attach_dir", lambda: tmp_path / "report_attachments")
    saved = tmp_path / "Study Assistant 2026-11-15 10-00-00.png"
    saved.write_bytes(b"png-saved")
    folder, names, problems = helpinfo.prepare_attachments([("My Screen.JPG", b"jpg-bytes"), ("notes.txt", b"not a picture")], [saved])
    assert problems == [] and names == ["screenshot-1.jpg", "screenshot-2.png", "screenshot-3.png"]    # a file type that is not a picture is saved as .png
    assert (folder / "screenshot-1.jpg").read_bytes() == b"jpg-bytes" and (folder / "screenshot-3.png").read_bytes() == b"png-saved"
    assert saved.exists()                                                # the original is only read


def test_a_picture_that_is_too_big_is_left_out_with_a_reason(tmp_path, monkeypatch):
    monkeypatch.setattr(helpinfo, "attach_dir", lambda: tmp_path / "ra")
    monkeypatch.setattr(helpinfo, "MAX_IMAGE_MB", 0)
    folder, names, problems = helpinfo.prepare_attachments([("big.png", b"x")], [])
    assert folder is None and names == [] and "larger than" in problems[0]


def test_nothing_chosen_makes_no_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(helpinfo, "attach_dir", lambda: tmp_path / "ra")
    assert helpinfo.prepare_attachments([], []) == (None, [], [])
    assert not (tmp_path / "ra").exists()


def test_a_missing_saved_picture_is_reported_not_fatal(tmp_path, monkeypatch):
    monkeypatch.setattr(helpinfo, "attach_dir", lambda: tmp_path / "ra")
    folder, names, problems = helpinfo.prepare_attachments([("a.png", b"1")], [tmp_path / "gone.png"])
    assert names == ["screenshot-1.png"] and "could not be read" in problems[0]


def test_old_report_folders_are_removed_but_other_folders_are_not(tmp_path, monkeypatch):
    base = tmp_path / "ra"
    monkeypatch.setattr(helpinfo, "attach_dir", lambda: base)
    old, recent, other = base / "report-20200101-000000", base / "report-20991231-000000", base / "my-own-folder"
    for d in (old, recent, other):
        d.mkdir(parents=True)
        (d / "f.png").write_bytes(b"1")
    long_ago = time.time() - 30 * 86400
    os.utime(old, (long_ago, long_ago)); os.utime(other, (long_ago, long_ago))
    helpinfo.prepare_attachments([("a.png", b"1")], [])
    assert not old.exists() and recent.exists() and other.exists()


def test_recent_screenshots_lists_newest_first(tmp_path, monkeypatch):
    import database
    monkeypatch.setattr(database, "DATA_DIR", tmp_path)
    shots = tmp_path / "screenshots"
    shots.mkdir()
    for i, name in enumerate(["a.png", "b.png", "c.png"]):
        p = shots / name
        p.write_bytes(b"1")
        os.utime(p, (1000 + i, 1000 + i))
    (shots / "ignore.txt").write_text("x")
    assert [p.name for p in helpinfo.recent_screenshots()] == ["c.png", "b.png", "a.png"]
    assert [p.name for p in helpinfo.recent_screenshots(limit=2)] == ["c.png", "b.png"]
