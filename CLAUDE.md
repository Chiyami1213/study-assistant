# Study Assistant: notes for Claude

Personal Streamlit + SQLite study app (`python run.py`). Code is in `app.py`, `views/`, `crud.py`, `database.py`.
Personal data (`data/`: database, settings, PDFs) is git-ignored. Never edit files under `data/` by hand.

## The Note Reader reads notes; it does not build them

Notes are built outside the app and imported into the Library as type Notes (one `.html` file per chapter, stored under
`data/pdfs/`). The Note Reader (`views/lab_view.py`) shows a course's notes and builds its tabs from the parts each note has.
The older `notes/<course code>/<id>-<title>/notes.html` chapters are no longer edited.

- A note is ONE self-contained interactive HTML page (inline CSS and JavaScript, no build step, no external images, no links
  to other pages; in-page `#anchors` are fine). Math: MathJax from jsdelivr (`https://cdn.jsdelivr.net/npm/mathjax@3.2.2/es5/tex-svg.js`),
  `\( ... \)` inline and `\[ ... \]` display, light and dark through `prefers-color-scheme`.
- The standard format is a list of `<section id="...">` blocks, each with an `<h2>`. The reader recognizes these parts by id (or
  heading) and shows a tab for each one the note has: Notes first, then the others in the order they appear: `mindmap` (Mind Map), the note itself (every other
  section: `s1`, `s2`, ... , the tab opens at the first), `eqsheet` or `sheet` (Equation Sheet), `assumptions` (Assumptions), `errata`
  (Errata; older notes use a "Notes check" section), `quiz` (Quiz; older notes use a "Self-check" section). Not every note has every
  part, and a part that is missing gets no tab.
- A note with its own quiz script (`id="qBox"`) runs it as it is; older notes get the course's question set injected
  (`quiz_view.book_questions`).
- Reference files (textbooks, lecture notes) are in the Library, with stored copies under `data/pdfs/`.

## Conventions
- Interface text uses APA title case; hover tooltips are all lower case.
- Exams, homework and the course outlines live in the database (use the app or `crud.py`), not in `notes/`.
