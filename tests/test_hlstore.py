"""Highlights of an HTML study guide are kept inside its stored page, and the guide's own light/dark switch is hidden in the app (the page follows the app's setting)."""
import base64
import json

import pytest

from core import crud, settings
from core.database import data_path
from study import hlstore, htmlnotes

pytestmark = pytest.mark.usefixtures("fresh_data")


@pytest.fixture(autouse=True)
def scratch_mirror(tmp_path, monkeypatch):
    monkeypatch.setattr(hlstore, "MIRROR_DIR", tmp_path / "hl")                                          # never the project's own static folder
PAGE = "<!doctype html><html><head><title>Guide</title></head><body><h1>Guide</h1><script>var x = 1;</script></body></html>"
KEY = "sg:Guide:highlights"
VALUE = json.dumps([{"id": 1, "c": "yellow", "text": "wing </script> loading"}])


def message(book_id, key=KEY, value=VALUE):
    return f"hl:{book_id}:" + base64.b64encode(json.dumps({"key": key, "value": value}).encode("utf-8")).decode("ascii") + "|123"


def add_guide():
    from core.database import PDF_DIR, stored_path
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    dest = PDF_DIR / "book_guide.html"
    dest.write_text(PAGE, encoding="utf-8")
    return crud.add_book("Guide", "", "", stored_path(dest), None, [], "Notes", "2026", "1", orig_name="guide.html"), dest


def test_the_block_goes_in_and_out_of_a_page_and_the_page_still_ends_with_its_body():
    page = hlstore.embed(PAGE, KEY, VALUE)
    assert 'id="sa-highlights"' in page and page.index("sa-highlights") < page.lower().rindex("</body>")
    clean, found = hlstore.split(page)
    assert found == {"key": KEY, "value": VALUE} and clean == PAGE                                     # a "</script>" inside the text did not end the block
    assert hlstore.embed(page, KEY, VALUE.replace("yellow", "green")).count("sa-highlights") == 1          # a second save replaces the block
    assert hlstore.embed(page, KEY, "") == PAGE and hlstore.split(PAGE) == (PAGE, None)


def test_a_message_from_a_page_is_checked_before_it_is_trusted():
    assert hlstore.decode(message(7)) == (7, KEY, VALUE)
    for bad in ("hl:x:abc|1", "other:7:abc|1", message(7, key="rd-pos:Guide"), "hl:7:%%%|1", message(7, value="x" * (hlstore.MAX_BYTES + 1))):
        with pytest.raises(ValueError):
            hlstore.decode(bad)
    assert hlstore.handle_message("junk") is False


def test_a_saved_highlight_is_written_into_the_stored_page_and_comes_back_when_it_opens():
    book_id, dest = add_guide()
    assert hlstore.handle_message(message(book_id)) is True
    assert hlstore.split(dest.read_text(encoding="utf-8"))[1] == {"key": KEY, "value": VALUE}
    assert (hlstore.MIRROR_DIR / f"{book_id}.json").exists()
    html = htmlnotes.safe_html(dest.read_text(encoding="utf-8"), book_id=book_id)
    assert "sa-highlights" not in html.replace("hl_sink", "") and f"/app/static/hl/{book_id}.json" in html      # the window's page has no block, so a save does not reload it
    assert json.loads((hlstore.MIRROR_DIR / f"{book_id}.json").read_text(encoding="utf-8"))["value"] == VALUE
    assert hlstore.handle_message(message(book_id, value="")) is True                                   # all highlights removed in the page
    assert hlstore.split(dest.read_text(encoding="utf-8")) == (PAGE, None) and not (hlstore.MIRROR_DIR / f"{book_id}.json").exists()


def test_only_a_stored_html_page_is_ever_written():
    from core.database import PDF_DIR, stored_path
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    pdf = PDF_DIR / "book_x.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    book_id = crud.add_book("A pdf", "", "", stored_path(pdf), None, [], "Textbook", "", "", orig_name="x.pdf")
    assert hlstore.save(book_id, KEY, VALUE) is False and pdf.read_bytes() == b"%PDF-1.4" and hlstore.save(99999, KEY, VALUE) is False


def test_replacing_a_stored_guide_with_a_newer_file_keeps_the_highlights_made_in_the_old_one():
    old = hlstore.embed(PAGE, KEY, VALUE)
    newer = PAGE.replace("var x = 1;", "var x = 2;")
    merged = hlstore.carry_over(old, newer)
    assert hlstore.split(merged)[1]["value"] == VALUE and "var x = 2;" in merged
    own = hlstore.embed(newer, KEY, "[]x")
    assert hlstore.carry_over(old, own) == own                                                          # a file that brings its own highlights keeps them


@pytest.mark.parametrize("appearance, mode", [("light", "light"), ("dark", "dark"), ("device", "device")])
def test_the_guides_own_theme_switch_is_hidden_and_the_page_follows_the_app(appearance, mode):
    settings.set_appearance(appearance)
    html = htmlnotes.safe_html(PAGE)
    assert f'var MODE = "{mode}"' in html and ".theme-btn" in html and "display:none!important" in html
    assert html.index("var MODE") < html.index("<title>") + 100 and html.index("var MODE") < html.index("var x = 1;")           # it runs before the page's own scripts


def test_a_page_without_a_head_still_gets_the_early_scripts_first():
    html = htmlnotes.safe_html("<p>no head</p>", book_id=1)
    assert html.startswith("<script>") and html.index("var MODE") < html.index("<p>no head</p>")
