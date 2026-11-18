"""Highlights a student makes in an HTML study guide, kept INSIDE the stored copy of that guide so they do not disappear.

A study guide's own highlighter keeps its highlights in the browser (localStorage, key "sg:<title>:highlights"), which is lost when the browser data is cleared, when the app is opened on another
port or computer, or when the stored page is replaced. While a guide is open in the app, its page reports every change of that key (see htmlnotes._HL); `save` embeds the value in the page
itself as `<script type="application/json" id="sa-highlights">{"key": ..., "value": ...}</script>`, so the highlights travel with the file (backup, export, import) and come back whenever it is opened.

The page the app shows has the block taken out (`split`), so a save does not change what the open window shows (that would reload it); a copy of the value is put in static/hl/<book id>.json,
where the opening page reads it (synchronously, before the guide's own script reads its highlights). PURE except for `save`, `mirror` and `handle_message`."""
import base64
import json
import os
import re

from core import database

MAX_BYTES = 4_000_000                                             # a guard against a page that sends something huge
BLOCK = re.compile(r'<script[^>]*\bid="sa-highlights"[^>]*>(.*?)</script>\s*', re.I | re.S)
MIRROR_DIR = database.BASE_DIR / "static" / "hl"                  # served at /app/static/hl (Streamlit static serving)
MIRROR_URL = "/app/static/hl/{}.json"


def split(text):
    """(the page without the highlights block, {"key": ..., "value": ...} or None)."""
    found = None
    m = BLOCK.search(text)
    if m:
        try:
            data = json.loads(m.group(1).replace("<\\/", "</"))
            if isinstance(data, dict) and isinstance(data.get("key"), str) and isinstance(data.get("value"), str):
                found = {"key": data["key"], "value": data["value"]}
        except ValueError:
            found = None
    return BLOCK.sub("", text), found


def embed(text, key, value):
    """The page with its highlights block set to `value` (a block that is there is replaced; an empty value takes it out)."""
    clean, _ = split(text)
    if not value:
        return clean
    payload = json.dumps({"key": key, "value": value}, ensure_ascii=False).replace("</", "<\\/")
    block = f'<script type="application/json" id="sa-highlights">{payload}</script>\n'
    i = clean.lower().rfind("</body>")
    return clean + block if i < 0 else clean[:i] + block + clean[i:]


def decode(message):
    """(book id, key, value) of the text a page writes into the hidden box: 'hl:<book id>:<base64 of {"key", "value"}>|<stamp>'. ValueError when it is not one."""
    head, _, _stamp = message.partition("|")
    parts = head.split(":", 2)
    if len(parts) != 3 or parts[0] != "hl" or not parts[1].isdigit():
        raise ValueError("not a highlights message")
    data = json.loads(base64.b64decode(parts[2], validate=True).decode("utf-8"))
    key, value = data.get("key"), data.get("value")
    if not isinstance(key, str) or not re.fullmatch(r"sg:.{1,300}:highlights", key) or not (value is None or isinstance(value, str)):
        raise ValueError("not a highlights message")
    if value is not None and len(value) > MAX_BYTES:
        raise ValueError("too large")
    return int(parts[1]), key, value or ""


def _html_path(book_id):
    from core import crud
    from core.database import data_path
    book = crud.get_book(book_id)
    if not book or not str(book.get("pdf_path") or "").lower().endswith((".html", ".htm")):
        return None
    path = data_path(book["pdf_path"])
    return path if path.is_file() else None


def mirror(book_id, found):
    """Keep the copy the opening page reads (None: there are no saved highlights, the copy is taken away)."""
    target = MIRROR_DIR / f"{int(book_id)}.json"
    if found is None:
        target.unlink(missing_ok=True)
        return
    MIRROR_DIR.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(found, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, target)


def save(book_id, key, value):
    """Write the highlights into the stored page of this book. Returns True when it was saved. Only a stored .html page of the Library is ever written (a stored copy, never the original)."""
    path = _html_path(book_id)
    if path is None:
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    new = embed(text, key, value)
    if new != text:
        tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
        tmp.write_text(new, encoding="utf-8")
        os.replace(tmp, path)
    mirror(book_id, {"key": key, "value": value} if value else None)
    return True


def handle_message(message):
    """The text written into the hidden box by a page: save it. Returns True when something was saved."""
    try:
        book_id, key, value = decode(message)
    except (ValueError, TypeError):
        return False
    return save(book_id, key, value)


def carry_over(old_text, new_text):
    """When a stored page is replaced by a newer copy of the file, the highlights made in the old one stay (unless the new file brings its own)."""
    _, mine = split(new_text)
    if mine is not None:
        return new_text
    _, old = split(old_text)
    return embed(new_text, old["key"], old["value"]) if old and old["value"] else new_text
