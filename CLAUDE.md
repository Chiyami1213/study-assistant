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

## Homework Helpers and Grade Explanations are written outside the app too

A helper (hints for each problem) or a grade explanation (rubric, what was written, why points were lost, corrected answers) for one
homework or exam is a single self-contained `.html` page, imported into the Library as type Homework Helper, Grade Explanation,
Exam Helper or Exam Grade Explanation (the file name decides: "helper" / "hint" or "grade" / "explanation"). The title and the Homework
Number (or "Midterm 1", "Final" in the title) pair it with the problem file and the graded file of the same course.
- The viewer shows the page beside the paper (problem file for a helper, graded file for an explanation). A grade explanation sits
  under the app's own header (title, Open Homework / Open Solution, the total). A homework or exam without a written page still shows
  the automatic Homework Helper or Grade Explanation panel.
- Links to notes are the sections' addresses at any host (`.../artifact/<id>#s2-2`) with the visible text `Lec N §x.y · Title` (or `Ch2 · Title` with no `#id`, which opens that chapter's notes at the top)
  (or `(Lec N)` for an example, `#ex-3`): the app reads the lecture number from the text and the section from the `#id`, and opens
  the course's Notes of that lecture number at that id. A link without a lecture number inherits it from another link to the same
  address. Any other such link is read by its text ("Midterm 2 Preparation", "Final Exam Preparation", "Midterm 1 Reflection",
  "Midterm 1 Grades", "Homework 4 Helper", "Homework 4 Solution"): it opens that page of the same course (a Grades link opens the graded
  paper with its explanation beside it, a Helper link the problem file with its helper). Preparation and Reflection pages
  (kinds Exam Preparation and Exam Reflection) get the same link handling when opened on their own.
- A written grade explanation also marks the paper: a click on a problem card (`<section class="card" id="p1">`, id `p<problem>`), on a
  score tile or contents link to `#p<problem>`, or on a grader comment (`.gc` with a numbered `.badge`, the number being the comment's
  number in the grade report) shows that page of the graded paper and marks the place. This needs the app's own grade data
  (`data/grading/<id>.json`, read from the Gradescope report), so keep the problem numbers and comment numbers the same as the report's.
- A written helper marks the problem file the same way: a click on a problem card (`id="p<n>"`) shows the problem's heading, and a
  click on a sub-problem (`<div class="part">` whose `.pl` label is the letter, e.g. `a)`) shows that part's lines. Problem numbers and
  letters must match the numbering of the problem PDF (the app finds them by their text).

## Conventions
- Interface text uses APA title case; hover tooltips are all lower case.
- Exams, homework and the course outlines live in the database (use the app or `crud.py`), not in `notes/`.
