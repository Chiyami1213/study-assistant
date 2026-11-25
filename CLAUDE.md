# Study Assistant: notes for Claude

Personal Streamlit + SQLite study app (`python run.py`). The project root holds only the entry points (`app.py`, `run.py`, `launcher.py`, `version.py`) and these folders:
`core/` (database, crud, settings), `library/` (file details, covers, naming, tidy, merge, outlines, syllabus), `study/` (notes, quizzes, equation sheets, errata, helpers, grade reports, reader),
`datafiles/` (backup, export, import), `desktop/` (screenshot, folder picker, help and report), `planner/` (the study planner), `views/` (every page, plus `navigation.py` and `icons.py`), `tools/`
(developer build scripts and the installer, never in the release) and `tests/`. Import with the folder: `from core import crud`, `from library import naming`. A new module goes into the folder it belongs to
(and into the reload list at the top of `app.py`). The exe must not bundle these packages (it reads them from the project folder): `launcher.py` imports them by name with `importlib`, and the build
scripts do not list them as hidden imports.

## Where things live
- The PROJECT folder (`Documents\study-assistant`) holds only what is pushed to GitHub: the code and docs. (`static/`, `build/`, `dist/` are
  git-ignored caches and build output.)
- The user's own files live in the DATA folder `database.DATA_DIR` = `%APPDATA%\Study Assistant` on Windows and `~/Library/Application Support/Study Assistant` on a Mac (`database.default_data_dir()`; the env variable
  `STUDY_ASSISTANT_DATA` overrides it; an old `project\data` is still used only if it holds `study.db` and the roaming folder does not exist): `study.db`,
  `settings.json`, `pdfs/`, `covers/`, `course_photos/`, `grading/`, `syllabus/`, `annotations/`, `equation_sheets/`, `quiz_progress/` (quizzes saved for later), `screenshots/` (F2), `logs/` (the exe's server log), `webview/`, `Backups/` (the safety copies; the user can keep them elsewhere, e.g. OneDrive: always use `database.backups_dir()`, never `DATA_DIR / "Backups"`, except for temporary scratch folders).
  Never edit files in it by hand. In code use `database.DATA_DIR`, `data_path(rel)` and `stored_path(path)`; never build paths from `BASE_DIR / "data"`.
  Book paths in the database are relative to the data folder (`pdfs\book_x.pdf`; older rows may start with `data\`); `data_path()` reads both kinds of slash, so a Windows database works on a Mac.

## Protect the data folder (it was deleted once by a test setup; the originals of many imports were lost)
- NEVER link, junction, symlink or mount the data folder (or anything inside it) into another folder, and never run a recursive delete
  (`git worktree remove`, `rm -r`, `Remove-Item -Recurse`, `shutil.rmtree`) on a folder that contains such a link. A recursive delete follows
  Windows junctions and erases the real files.
- To test or compare a version, COPY what is needed to a scratch folder (a small copy of `study.db` is enough) and point the test at the copy with
  `STUDY_ASSISTANT_DATA`. Never point a test at the real data folder, and never leave a test server running against it. Test the installer only with
  `SA_INSTALL_PROGRAM_DIR` / `SA_INSTALL_DATA_DIR` set to scratch folders.
- Source files outside the project (OneDrive, other drives, Downloads ...) are READ ONLY for this app and for Claude: import = COPY into
  `pdfs/` of the data folder. Never delete, move, rename or edit a file in the user's own drives or OneDrive.
- `datafiles/backup.py` copies the database, settings and the small folders to `<data folder>\Backups\Snapshots` when the app starts (the library backup in
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
- The quiz of a guide has three parts under the Quiz tab: (1) conceptual questions (`id="qBox"`, the array `Q`; the app scores only these, 12 a chapter), (2) a speed round (`id="speed"`, `srBox`, inside the `quiz` section) and (3) guided numerical practice (`<section id="gpractice">`, after `quiz`). `outline.PART_IDS` / `PARTS` treat `gpractice` and `speed` as part of the Quiz tab.
- A guide may have any mix of those parts (`quiz_view.chapter_parts`: only the parts a guide has are offered, each is a quiz of its own, a quiz written in a form the app cannot read is left out and never an error). The speed round bank may be named `BANK`, `*BANK`, `SPEED*` or `SR*` (`N` and `LIMIT` are read); guided examples of the notes are offered as the guided practice when the guide has no `gpractice` section (`study/quizparts.py`); a guide whose only questions are open (essay: `<details class="q">`) gets open questions with a model answer and "I Had It" / "Not Yet".
- A note with its own quiz script (`id="qBox"`) runs it as it is; older notes get the course's question set injected
  (`quiz_view.book_questions`).
- Reference files (textbooks, lecture notes) are in the Library, with stored copies under `pdfs/` (data folder).

- A note's own light/dark switch (`.theme-btn`, top right) is hidden in the reader and the page follows the app's Light / Dark / device setting (`htmlnotes._THEME`).
- The highlights a student makes in a note (the guide's own highlighter keeps them in localStorage under `sg:<title>:highlights`) are kept INSIDE the stored page as
  `<script type="application/json" id="sa-highlights">` (`study/hlstore.py`): the open page reports each change through the hidden box `hl_sink` (in `app.py`), `hlstore.save` embeds it, a copy is put in
  `static/hl/<book id>.json` which the opening page reads before the guide's own script, and the block is taken out of the page the window shows (a save must not reload the window). Replacing a stored
  note (Update From Folder, Replace) carries the block over (`hlstore.carry_over`). Library import: a file the Library has already (Changed, or In Library by name) is Replaced (the usual) or Kept (`Candidate.existing`).

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
- The app only manages the user's own files: Settings > Backup keeps the library backup (`datafiles/libbackup.py`) and has Export My Files (`datafiles/exportfiles.py`: one zip with
  `payload/data/...`, the data folder without `webview` and `Backups`, the database as a consistent copy) and Import (`datafiles/dataimport.py`: writes every file of the zip, so an
  existing file is replaced; a differing one is first copied to `Backups\Before Import <time>`, an identical one (same CRC) is just written again, replaces the database through sqlite's backup after copying the
  current one there; nothing is deleted; restart afterwards). The app never builds an exe or packages the program.
- The developer builds the release from VS Code: `python tools/build_release.py` builds the app (`tools/build_exe.py`), the installer (`tools/build_installer.py`, from `tools/installer.py`) and
  `dist/release/StudyAssistant-<version>-Windows-Installer.zip`: a CLEAN install (installer + `payload/program`, no personal files). It is uploaded as the asset of the
  GitHub release; people extract it and run `Install Study Assistant.exe`. A clean copy can also be made by copying the project folder alone and running `python run.py`
  (after `pip install -r requirements.txt`).
- The installer (a tkinter wizard, `Wizard` in `tools/installer.py`, drawn at the real screen resolution; pages: welcome, existing version, shortcuts, ready, installing, finish) COPIES
  `payload/program` to `Documents\study-assistant` (and `payload/data` to `AppData\Roaming\Study Assistant` when a zip has one). It finds an installed version (`find_existing`: the marker
  file, or an installed-apps entry) and offers Update (the old program folder is set aside and only deleted after the new copy is in), Uninstall first, or Keep both (own folder,
  registry key `StudyAssistant-<version>`, shortcut name; with a warning that both share the data folder and port 8765). A folder without the marker (a dev copy) is only renamed to
  `... (old date time)`, never deleted. The data folder is never replaced or deleted by an install. Desktop and Start menu shortcuts are options (`make_shortcuts`; tests use
  `SA_INSTALL_SHORTCUT_DIR`). `--silent --existing update|uninstall|both [--no-desktop-shortcut] [--no-start-menu]` for tests. It also registers the program for the current user (HKCU
  `...\Uninstall\StudyAssistant`, no admin) so it appears in Settings > Apps / Control Panel, and copies itself into the program folder as
  `Uninstall Study Assistant.exe` (`--uninstall`, marker `.study-assistant-install.json`). The uninstaller removes the program folder, the Desktop shortcut and that
  registry entry and by default KEEPS the data folder; its window has a "remove everything, including my files" choice (asks again, `--remove-files` for tests) that
  deletes the data folder too. It never enters a link or junction, and refuses a folder without the marker or with a `.git`. Never run it on the development copy. Test
  only with `SA_INSTALL_PROGRAM_DIR` / `SA_INSTALL_DATA_DIR` and `SA_INSTALL_REG_KEY` (a test key name, removed afterwards).
- macOS: `tools/build_mac.py` (PyInstaller `.app`, program code copied into `Contents/Resources/project`, ad hoc `codesign`, `.dmg` with an Applications link) can only run on a Mac; the
  GitHub workflow `.github/workflows/build-macos.yml` builds Apple-Silicon and Intel images, smoke-tests the built app (`--server` mode answers `/_stcore/health`) and attaches the
  `.dmg` to a published release. Platform-specific code: `database.default_data_dir`, `desktop/screenshot.py` (`screencapture`), `desktop/folderpick.py` (`osascript`), `launcher.find_project`.
  Nothing Mac-specific has been run on a real Mac by Claude: the workflow is the test.
- To lower antivirus false alarms: the exes carry version information (`tools/buildinfo.py`), are built `--noupx`, `tools/build_release.py` writes `SHA256SUMS.txt`, and the installer tells the
  user about SmartScreen / antivirus warnings. Real fix: code signing (e.g. SignPath Foundation for open source).
- The loading screen is `launcher.SPLASH` (bar 0 to 100%, at least `MIN_SPLASH` = 1 second). Help and Report an Issue (`desktop/helpinfo.py`, Settings) open a pre-filled GitHub issue; the
  app never sends anything or stores an e-mail address.
- The release number is `version.py` (`VERSION`, shown in Settings > About, the installer and the installed-apps entry).
- Do not store anything else elsewhere (user profile, registry). The only other extras are the Desktop shortcut and the optional backup folder.
- `tools/build_release.py` skips `static`, `build`, `data`, ... only directly under the project folder; deeper folders of the same name (the built app's
  `streamlit\static` web page) must be copied, or the exe shows a black window with "Not Found".

## Course outlines (`library/courseoutline.py`, Courses > Outline)
- A course with no outline gets one automatically: the topic list of its syllabus / Lec 0 slides if it has one (`parse_topics`), else the lecture titles
  (`from_titles`; the chapter notes when the lecture files only have generic names). `ensure()` runs when the Outline tab is drawn; the state of each outline
  ({source: syllabus | titles | manual}) is in `settings.json` (`outlines`). An outline with no state, or edited through Edit Outline, is "manual" and is never touched.
- Anything that replaces an outline first copies it to `<data folder>/outlines/`. The editor is a text form (`to_text` / `from_text`).

## Merged courses (parts)
- Two or more courses can be merged into one (MA 266 / 303 Differential Equations, MA 161 / 162 / 261 Calculus). Every file, homework and exam title of a part ends with its
  tag in brackets, `HW 10 (MA 266)`; the shared textbook is untagged and belongs to every part. `crud.part_tag` / `strip_part` / `in_part` / `course_parts` read the tags; the
  number inside the tag must never be read as a homework or exam number (always `strip_part` first), and pairing a problem file with its solution or graded paper uses the
  number AND the tag (`library_view._pair_key`, `courses_view._homework_book` / `_exam_book`).
- A course with two or more parts gets the *Part of This Course* switch in `courses_view._manage`: `course["part"]` (None = all parts) and `course["parts"]` filter every tab.
  Per-part data: `syllabus/<course id>_<TAG>.json` (`syllabus.load(id, part)`), `course_outline.part` and `settings` outline state `"<id>:<TAG>"`, quiz chapters, resources, homework, exams.
- Merging is done with a script that first copies `study.db` (and the dropped courses' photos) to `Backups\Before Merge <time>`, tags the titles, moves every table row of the dropped
  courses to the kept course and deletes the empty courses; test it on a scratch copy first.

## The study planner (`planner/`, in progress: phases 1 to 7)
- `planner/models.py` and `planner/timeutil.py` are PURE (no database, no Streamlit): the scheduling logic must stay that way. All moments are UTC (`timeutil.utc_iso`), shown in the term's zone.
  `planner/store.py` is the only part that touches the database (`planner_settings`, `planner_awake`), `settings.semester` (term dates) and `holidays` (breaks).
  `planner/commitments.py` is pure too (series, meetings, exceptions, events, `blocks()`); `planner/commit_store.py` saves them (`activities`, `activity_meetings`, `meeting_exceptions`, the
  new columns of `events` and `class_meetings`). `planner/tasks.py` (pure: Task, estimates, the five lists) and `planner/task_store.py` (`tasks`, `task_defaults`). `planner/freetime.py` (pure: `free_intervals`, `slacks` / `cushions`, `timeline`, `report`; the cushion is the tightest window `[r, deadline]`, r = now or the start date of work due by then, minus the demand that cannot start before r) and `planner/service.py` (reads the saved setup, returns the report; every session change returns the new report). `planner/sessions.py` (pure: Session, `placement_problems`, `autoplan`) and `planner/session_store.py` (`study_sessions`; hard problems always refuse, soft ones unless `force=True`). `planner/tracking.py` (pure: timer rounding, planned against used, suggested estimates) and `planner/track_store.py` (`time_logs`, `study_timer`; logged minutes are added to `tasks.logged_minutes`, which the cushion uses as work done). A click on a class or an activity block (`data-open="occ:<course|activity>:<meeting id>:<day>"`) opens `planner_ui.occurrence_dialog` (this day only = `commit_store` exceptions, every week = `update_meeting`). The left panel of draggable blocks is `planner_ui.panel_html` and is dropped through the script `__calPanelV1` (`drop|kind:id|day|minutes`). The Calendar page (`views/calendar_view.py`) draws the grid with `views/plan_grid.py` (pure HTML builders) and uses `views/planner_ui.py` for the cushion banner, task list and dialogs; a drag or click in the grid is reported by the script in app.py (`__calDragV1`) into the hidden box `cal_sink` as `action|what|day|minutes|stamp` and handled by `planner_ui.handle_action`. Mon = 0 for weekdays everywhere. Finished courses are left out of the planner. `crud.meeting_occurrences` (the old Calendar) reads end dates and exceptions too.
- The Calendar page has two pages (`cal_page`): Calendar and Task List (`views/tasklist_view.py`: pure `filter_tasks` / `sort_tasks` / `group_tasks`, the import from syllabus
  `course_work` / `syllabus_items` / `import_rows` / `apply_import` / `auto_import`, with the pure reader `planner/syllabus_read.py`). The left bars (`planner_ui.panel_html`, `filter_panel_html`) are one block
  style: `_block` (grip `.pl-handle`, ⋯ menu, double-click rename); what the user did with a block is kept in `settings.json` key `calendar_blocks` (hidden, names, colors, order), the panel width,
  the hour height and the fold state next to it. Terms are `settings.list_terms()` etc.; `planner_ui.term_select` / `terms_dialog` is the only place they are managed. A personal task
  (`tasks.personal`) has no course and may be planned in a break and outside the term. Everything the grid and the panel report goes through the hidden box `cal_sink` (also on the Task List).
- Prompt for AI (Library > Import, `views/prompt_dialog.py`, pure `study/promptgen.py`; Claude, ChatGPT or Gemini, the differences are the `ASSISTANTS` entries and the `{{...}}` placeholders in the texts): builds the prompt a student pastes into their AI chat from the texts in `study/prompts/` (`study_guide_rules.md`, `homework_exam_pages.md`, `app_format.md`). `app_format.md` MUST be kept in step with the format rules in this file (note section ids, `card id="p<n>"`, `.part` / `.pl`, `.gc` + `.badge`, link texts, file-name words that `library_view.detect_kind` reads); `tests/test_promptgen.py` checks that the file names it asks for are recognized by the Library.
- Calendar import (Task List > Import From Calendar, `views/calendar_import.py`; pure `planner/ical.py` reads .ics with repeats and zones, `planner/calsync.py` saves): items get the source `ical:<feed id>:<key>`
  (tasks and events), the feed keeps `seen` keys so a deleted item is not brought back, feeds are in `settings.json` (`calendar_feeds`, the address is private: never log it or put it in an issue report),
  and `calendar_import.auto_sync` runs once per session from `app.py`. The tutorial (`views/tutorial.py`, state `settings.get_tutorial()`) starts only when the app has no course: a check chain on Home, and a guided tour (`TOUR`: page, window to keep open via `tutorial.wants(name)`, target `css:` / `label:` / `button:`) drawn by `views/tour_overlay.js` in the browser's top layer (`popover`), which writes Back/Next/Skip into the hidden `tour_sink`; a new window or page that the tour should open needs a `wants()` hook there, and the overlay must stay un-`inert`.
- Library (`views/library_view.py`): the usual sort is Type (tiles), Course (tiles), Date Added (timeline) or Title; what is open is kept in `st.session_state["_lib"]`.
- Task categories are `planner.tasks.CATEGORIES` (Homework, Exam, Quiz, Reading, Project, Lab, Other); the `tasks` and `task_defaults` tables carry the list in a CHECK, so a new category needs the schema text in `core/database.py` AND a start-up widening of older databases (`_allow_task_category_lab` edits the stored table text; never copy or drop `tasks`, other tables point at it).
- The Courses tree (`views/course_tree.py`) grows upward from the root "All Disciplines" at the bottom (angles -pi..0); a field whose only topic is General has no General bubble (its courses hang on the field). Bubbles are dragged by the script `__treeDragV1` in app.py (offsets kept in `window.__mmOffsets` per bubble key; a drag moves the bubble's branches too; double-click on the map resets).
- Buttons at the top of every page share one look (outlined, 40 px, icon and text centered) through the key list in the `app.py` CSS block "The buttons at the top of every page"; a new top button needs its key added there.
- README gallery images (`docs/gallery/`) are made with made-up courses only (never the real data folder); update them with the demo data scripts in the scratchpad pattern: scratch `STUDY_ASSISTANT_DATA`, fictional courses, Playwright screenshots.
- Tests: `python -m pytest` (`tests/`, a temporary data folder is set up by `tests/conftest.py`; never the real one). Write tests with every phase.

## The GitHub pages
- `README.md` is the overview with a tab row; the other tabs are `docs/INSTALL.md`, `docs/FILES.md`, `docs/SHORTCUTS.md`, `docs/HELP.md` and the root `CHANGELOG.md`. Every page repeats the same
  tab row (the current tab in bold), directly under its title. When a tab is added or renamed, change the row in all of them. Use absolute GitHub URLs for the Releases and Issues links (relative ones break inside
  `docs/`). `helpinfo.HELP_URL` and the installer link to `docs/HELP.md`.

## Conventions
- Interface text uses APA title case; hover tooltips are all lower case.
- Exams, homework and the course outlines live in the database (use the app or `core/crud.py`).
