# Study Assistant: notes for Claude

Personal Streamlit + SQLite study app (`python run.py`). Code is in `app.py`, `views/`, `crud.py`, `database.py`.
Personal data (`data/`: database, settings, PDFs) is git-ignored. Never edit files under `data/` by hand.

## Note Builder chapters are plain files: edit these when asked to build or change notes

    notes/<course code>/<id>-<chapter title>/notes.html    the whole chapter, one page

- A chapter is ONE interactive HTML page; its last section, `<section id="exercises">`, holds the exercises (the
  app's Exercises tab opens the same page scrolled to that section). The page is self-contained (inline CSS and JavaScript, no build step, no external
  images). Study guides include interactive animation: step-through derivations, sliders and canvas or SVG animations
  that show the idea, not decoration.
- Math: MathJax from the jsdelivr CDN (`https://cdn.jsdelivr.net/npm/mathjax@3.2.2/es5/tex-svg.js`), `\( ... \)` inline
  and `\[ ... \]` display. Support light and dark with `prefers-color-scheme`.
- Start from the standard format: new chapters begin as a page with one `<section>` per topic (`.key` idea box,
  `.eq` equations, `.deriv` step-through derivation, `.demo` animation canvas, `.example`) and a small script at the
  end. Keep that structure so pages look alike; replace the grey `.todo` placeholders with real content.
- Do not link to other pages (the app shows the file in a frame, and in-page `#anchors` are handled by the app).
- Markdown (`notes.md`, `$...$` math) still works as a fallback, but HTML is the default. If you convert a tab to HTML,
  delete its `.md` file.
- The app picks up saved changes within a couple of seconds. Keep the folder name as it is (the number is the chapter id;
  the app renames the folder if the chapter title changes).
- Reference files (textbooks, lecture notes) are in the Library; their stored copies are under `data/pdfs/`.
  Read them there when asked to build notes from a textbook page. Pre-Claude HTML notes (kind "Notes") there show the
  house style.

## Conventions
- Interface text uses APA title case; hover tooltips are all lower case.
- Exams, homework and the course outlines live in the database (use the app or `crud.py`), not in `notes/`.
