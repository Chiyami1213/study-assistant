# Study Assistant: notes for Claude

Personal Streamlit + SQLite study app (`python run.py`). Code is in `app.py`, `views/`, `crud.py`, `database.py`.
Personal data (`data/`: database, settings, PDFs) is git-ignored. Never edit files under `data/` by hand.

## Note Builder chapters are plain files: edit these when asked to build or change notes

    notes/<course code>/<id>-<chapter title>/notes.md        Notes tab
    notes/<course code>/<id>-<chapter title>/exercises.md    Exercises tab

- Write Markdown. Math: `$...$` inline, `$$...$$` display (KaTeX syntax). Headings `##` per section, short bullets.
- Interactive notes: save a single self-contained page as `notes.html` (or `exercises.html`) in the same folder and
  delete the `.md` of that tab. Inline CSS and JavaScript, MathJax from the jsdelivr CDN (`\( \)` inline math),
  step-through derivations, no external images. The app shows the file as it is; do not link to other pages.
- The app picks up saved changes within a couple of seconds. Keep the folder name as it is (the number is the chapter id;
  the app renames the folder if the chapter title changes).
- Reference files (textbooks, lecture notes) are in the Library; their stored copies are under `data/pdfs/`.
  Read them there when asked to build notes from a textbook page.

## Conventions
- Interface text uses APA title case; hover tooltips are all lower case.
- Exams, homework and the course outlines live in the database (use the app or `crud.py`), not in `notes/`.
