# Study Assistant: notes for Claude

Personal Streamlit + SQLite study app (`python run.py`). Code is in `app.py`, `views/`, `crud.py`, `database.py`.

## Where things live
- The PROJECT folder (`Documents\study-assistant`) holds only what is pushed to GitHub: the code and docs. (`static/`, `build/`, `dist/` are
  git-ignored caches and build output.)
- The user's own files live in the DATA folder `database.DATA_DIR` = `%APPDATA%\Study Assistant` (the env variable
  `STUDY_ASSISTANT_DATA` overrides it; an old `project\data` is still used only if it holds `study.db` and the roaming folder does not exist): `study.db`,
  `settings.json`, `quizzes/`, `pdfs/`, `covers/`, `course_photos/`, `grading/`, `syllabus/`, `annotations/`, `equation_sheets/`, `screenshots/` (F2), `logs/` (the exe's server log), `webview/`, `Backups/`.
  Never edit files in it by hand. In code use `database.DATA_DIR`, `data_path(rel)` and `stored_path(path)`; never build paths from `BASE_DIR / "data"`.
  Book paths in the database are relative to the data folder (`pdfs\book_x.pdf`; older rows may start with `data\`).

## Protect the data folder (it was deleted once by a test setup; the originals of many imports were lost)
- NEVER link, junction, symlink or mount the data folder (or anything inside it) into another folder, and never run a recursive delete
  (`git worktree remove`, `rm -r`, `Remove-Item -Recurse`, `shutil.rmtree`) on a folder that contains such a link. A recursive delete follows
  Windows junctions and erases the real files.
- To test or compare a version, COPY what is needed to a scratch folder (a small copy of `study.db` is enough) and point the test at the copy with
  `STUDY_ASSISTANT_DATA`. Never point a test at the real data folder, and never leave a test server running against it. Test the installer only with
  `SA_INSTALL_PROGRAM_DIR` / `SA_INSTALL_DATA_DIR` set to scratch folders.
- Source files outside the project (OneDrive, other drives, Downloads ...) are READ ONLY for this app and for Claude: import = COPY into
  `pdfs/` of the data folder. Never delete, move, rename or edit a file in the user's own drives or OneDrive.
- `backup.py` copies the database, settings and the small folders to `<data folder>\Backups\Snapshots` when the app starts (the library backup in
  Settings goes to `Backups\Library`). Restore from the newest copy there if the data is damaged. Old copies may also exist in `~/StudyAssistantBackup`.

## The Note Reader reads notes; it does not build them

Notes are built outside the app and imported into the Library as type Notes (one `.html` file per chapter, stored under
`pdfs/` (data folder)). The Note Reader (`views/lab_view.py`) shows a course's notes and builds its tabs from the parts each note has.
The app has no note builder any more (the old `notes/` chapter folders and the `lab_chapters` table were removed).

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
- Reference files (textbooks, lecture notes) are in the Library, with stored copies under `pdfs/` (data folder).

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
  (`grading/<id>.json` in the data folder, read from the Gradescope report), so keep the problem numbers and comment numbers the same as the report's.
- A written helper marks the problem file the same way: a click on a problem card (`id="p<n>"`) shows the problem's heading, and a
  click on a sub-problem (`<div class="part">` whose `.pl` label is the letter, e.g. `a)`) shows that part's lines. Problem numbers and
  letters must match the numbering of the problem PDF (the app finds them by their text).

## Backup, export and release (the app does not build anything)
- The app only manages the user's own files: Settings > Backup keeps the library backup (`libbackup.py`) and has Export My Files (`exportfiles.py`: one zip with
  `payload/data/...`, the data folder without `webview` and `Backups`, the database as a consistent copy) and Import (`dataimport.py`: adds missing files, skips
  identical ones, copies a differing file to `Backups\Before Import <time>` before replacing it, replaces the database through sqlite's backup after copying the
  current one there; nothing is deleted; restart afterwards). The app never builds an exe or packages the program.
- The developer builds the release from VS Code: `python build_release.py` builds the app (`build_exe.py`), the installer (`build_installer.py`, from `installer.py`) and
  `dist/release/StudyAssistant-<version>-Windows-Installer.zip`: a CLEAN install (installer + `payload/program`, no personal files). It is uploaded as the asset of the
  GitHub release; people extract it and run `Install Study Assistant.exe`. A clean copy can also be made by copying the project folder alone and running `python run.py`
  (after `pip install -r requirements.txt`).
- The installer COPIES `payload/program` to `Documents\study-assistant` (and `payload/data` to `AppData\Roaming\Study Assistant` when a zip has one); a folder that is
  already there is renamed to `... (old date time)`, never overwritten or deleted. It also registers the program for the current user (HKCU
  `...\Uninstall\StudyAssistant`, no admin) so it appears in Settings > Apps / Control Panel, and copies itself into the program folder as
  `Uninstall Study Assistant.exe` (`--uninstall`, marker `.study-assistant-install.json`). The uninstaller removes the program folder, the Desktop shortcut and that
  registry entry and by default KEEPS the data folder; its window has a "remove everything, including my files" choice (asks again, `--remove-files` for tests) that
  deletes the data folder too. It never enters a link or junction, and refuses a folder without the marker or with a `.git`. Never run it on the development copy. Test
  only with `SA_INSTALL_PROGRAM_DIR` / `SA_INSTALL_DATA_DIR` and `SA_INSTALL_REG_KEY` (a test key name, removed afterwards).
- The release number is `version.py` (`VERSION`, shown in Settings > About, the installer and the installed-apps entry).
- Do not store anything else elsewhere (user profile, registry). The only other extras are the Desktop shortcut and the optional backup folder.
- `build_release.py` skips `static`, `build`, `data`, ... only directly under the project folder; deeper folders of the same name (the built app's
  `streamlit\static` web page) must be copied, or the exe shows a black window with "Not Found".

## Course outlines (`courseoutline.py`, Courses > Outline)
- A course with no outline gets one automatically: the topic list of its syllabus / Lec 0 slides if it has one (`parse_topics`), else the lecture titles
  (`from_titles`; the chapter notes when the lecture files only have generic names). `ensure()` runs when the Outline tab is drawn; the state of each outline
  ({source: syllabus | titles | manual}) is in `settings.json` (`outlines`). An outline with no state, or edited through Edit Outline, is "manual" and is never touched.
- Anything that replaces an outline first copies it to `<data folder>/outlines/`. The editor is a text form (`to_text` / `from_text`).

## Conventions
- Interface text uses APA title case; hover tooltips are all lower case.
- Exams, homework and the course outlines live in the database (use the app or `crud.py`).
