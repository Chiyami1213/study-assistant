"""Note Reader chapters as plain files, so Claude in VS Code (or any editor) can edit them directly.

    notes/<course code>/<id>-<chapter title>/notes.html      (one interactive page; its last section is the exercises)

The app reads these files every time it draws a chapter, so changes made outside the app show up there."""
import re
import shutil

from database import BASE_DIR

ROOT = BASE_DIR / "notes"
FIELDS = ("notes",)
HTML_START = ("<!doctype", "<html", "<div", "<section", "<main", "<body", "<style")


def is_html(text):
    return (text or "").lstrip().lower().startswith(HTML_START)


def _safe(text, fallback):
    return re.sub(r"[^A-Za-z0-9 _.-]+", "", (text or "").strip()).strip(" .") or fallback


def _course_dir(course):
    return ROOT / _safe(course["code"] or course["name"], f"course-{course['id']}")


def chapter_dir(course, ch, create=False):
    """Folder of a chapter. It is renamed when the chapter title changes (the numeric id keeps it findable)."""
    base = _course_dir(course)
    want = f"{ch['id']:03d}-{_safe(ch['title'], 'chapter')}"
    found = next((p for p in base.glob(f"{ch['id']:03d}-*") if p.is_dir()), None) if base.exists() else None
    if found and found.name != want:
        try:
            found.rename(base / want)
            found = base / want
        except OSError:                      # a file is open somewhere: keep the old folder name for now
            pass
    path = found or (base / want)
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def _file(folder, field):
    """The file holding a field: the .html one if it exists, else the .md one."""
    for ext in (".html", ".md"):
        p = folder / f"{field}{ext}"
        if p.exists():
            return p
    return None


def read_field(folder, field):
    p = _file(folder, field)
    return p.read_text(encoding="utf-8", errors="replace") if p else None


def write_field(folder, field, text):
    """Save a field as .html (interactive page) or .md; the other kind is removed. Unchanged files are left alone."""
    text = text or ""
    ext = ".html" if is_html(text) else ".md"
    target, current = folder / f"{field}{ext}", _file(folder, field)
    if current and current != target:
        current.unlink()
    if current == target and target.read_text(encoding="utf-8", errors="replace") == text:
        return
    folder.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8", newline="")


def _fold_old_exercises(folder, notes):
    """Chapters made before exercises moved into the page: add the old exercises file as the page's last section."""
    old = _file(folder, "exercises")
    if not old:
        return notes
    text = old.read_text(encoding="utf-8", errors="replace")
    if 'id="exercises"' not in notes and text.strip():
        problems = re.findall(r'<details class="problem">.*?</details>', text, re.S)
        inner = "\n".join(problems) if problems else (
            "" if is_html(text) else '<div class="example" style="white-space:pre-wrap">' + _escape(text) + "</div>")
        if inner:
            block = ('<section id="exercises">\n<h2><span class="num">Exercises</span>Practice problems</h2>\n' + inner + "\n</section>")
            low = notes.lower()
            marker = "</main>" if "</main>" in low else "</body>"
            i = low.rfind(marker)
            notes = notes[:i] + block + "\n" + notes[i:] if i >= 0 else notes + block
    old.unlink()
    return notes


def _escape(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def load(course, ch):
    """{'notes'} of a chapter from its file. A chapter that has no file yet is filled from the copy in the database
    (chapters made before the files existed)."""
    folder = chapter_dir(course, ch)
    text = read_field(folder, "notes") if folder.exists() else None
    if text is None:
        text = ch.get("notes") or ""
        write_field(chapter_dir(course, ch, create=True), "notes", text)         # created empty if need be
    if folder.exists() and _file(folder, "exercises"):
        merged = _fold_old_exercises(folder, text)
        if merged != text:
            write_field(folder, "notes", merged)
            text = merged
    return {"notes": text}


def save(course, ch, sections):
    folder = chapter_dir(course, ch, create=True)
    for f in FIELDS:
        write_field(folder, f, sections.get(f, ""))


def trash(course, ch):
    """Move a removed chapter's folder to notes/.removed (never deleted outright)."""
    folder = chapter_dir(course, ch)
    if folder.exists():
        dest = ROOT / ".removed" / folder.parent.name
        dest.mkdir(parents=True, exist_ok=True)
        shutil.move(str(folder), str(dest / folder.name))


def signature(course, ch):
    """Changes whenever a file of the chapter changes (used to refresh the app after outside edits)."""
    folder = chapter_dir(course, ch)
    return tuple(sorted((p.name, p.stat().st_mtime_ns) for p in folder.iterdir())) if folder.exists() else ()
