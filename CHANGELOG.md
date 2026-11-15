# Changelog

<p align="center"><a href="README.md">Overview</a> &nbsp;|&nbsp; <a href="docs/INSTALL.md">Install</a> &nbsp;|&nbsp; <a href="docs/FILES.md">Your Files</a> &nbsp;|&nbsp; <a href="docs/SHORTCUTS.md">Shortcuts</a> &nbsp;|&nbsp; <a href="docs/HELP.md">Help</a> &nbsp;|&nbsp; <b>Changelog</b></p>

---

## Unreleased: study planner (planned as 1.1.0)

- **Phase 1 of the study planner: setup and data model.** A new pure, tested `planner` package (`models.py`, `timeutil.py`) holds the term (first day, last day of classes, last day of exams,
  time zone, named breaks), the wake and bed time of each weekday and the minimum study block (30 minutes by default); an invalid setup cannot be built. Times are stored in UTC and shown in the term's
  zone (daylight-saving days included). `planner/store.py` keeps it in the database (new tables `planner_settings` and `planner_awake`), the term dates in the settings the Calendar already uses and the
  breaks as the existing holidays. **Settings > Study Planner** sets the time zone, the awake times and the minimum block. Run the tests with `python -m pytest`.

## 1.0.2 (not released yet)

- **Study Assistant for macOS.** A `.dmg` for Apple silicon and one for Intel Macs: open it, drag Study Assistant into Applications, and approve it once (right-click > Open). The
  files live in `~/Library/Application Support/Study Assistant`; an export from Windows imports on a Mac and the other way round (stored paths are read with either kind of slash).
  F2 screenshots use macOS `screencapture`, the folder and file pickers use macOS dialogs, and the Mac app is built and checked by GitHub (`.github/workflows/build-macos.yml`,
  `build_mac.py`) because a Mac app cannot be built on Windows.
- **A new setup wizard (Windows).** Drawn at the screen's real resolution (no blurry text), with a picture panel and Back / Next / Cancel like the usual installers: welcome page,
  existing-version page, shortcuts, ready to install, progress bar with percentage, and a finish page.
- **The installer finds an installed version.** It says which version is installed and offers **Update (overwrite)** (the old program is only removed after the new one is in place), **Uninstall
  the older version first** (shortcuts and the installed-apps entry go too), or **Keep both** (its own folder, shortcut and Settings > Apps entry, with a warning that the two share one
  data folder and one address). A newer installed version is warned about, and a folder that was not made by the installer is only renamed, never deleted. Your files are never replaced.
- **Shortcut options.** A Desktop shortcut and / or a Start menu entry, as chosen; the uninstaller removes both.
- **Antivirus heads-up and fewer false alarms.** The installer says up front that an antivirus or SmartScreen may warn and that Study Assistant contains no virus. The exes now carry
  version information (product, publisher, version) and are not compressed with UPX, and every release publishes its SHA-256 checksum.
- **The GitHub page has tabs.** The README is now a short overview with a row of tabs (Overview, Install, Your Files, Shortcuts, Help, Changelog); each tab is its own page in `docs/`, and every page
  repeats the tab row. The installer and the app link to the Help tab.
- **The last page of the installer** links to the GitHub project page, to the new Help section and to the issue page.
- **Loading screen with a progress bar.** The start-up screen keeps its look and adds a bar from 0% to 100% that takes at least two seconds (and waits near the end if the server is slow).
- **Help and Report an Issue in Settings.** Help answers the common questions (installing, antivirus warnings, where files are, backups, connection problems, shortcuts, uninstalling). Report an
  Issue opens a ready-made GitHub issue in the browser (kind, summary, details, optional steps and technical details; an optional log excerpt with your name and folders replaced); the
  app sends nothing by itself and keeps no e-mail address. **Screenshots can be attached:** pick pictures (or the newest ones F2 saved); on Open on GitHub the app copies them into one folder, opens it,
  and you drop them into the report's text box (GitHub takes pictures that way). The README has the same Help section, and issue templates are added.

## 1.0.1 (2026-11-15)

- **Streamlit's own top-right icons are hidden.** The Deploy button, the three-dot menu and the "Running..." text no longer show in the app window or in a browser
  (`toolbarMode = "minimal"` and a style rule); the app has its own Settings page instead.
- **Fewer lost connections.** The app window now keeps its session for a day after a lost connection (sleep, a locked screen, a busy computer) instead of Streamlit's
  2 minutes, so it comes back to the same page. If the hidden server stops by itself, the window starts it again and reloads the page instead of staying on
  "Connection error". The installed app writes the server's messages to `logs\server.log` in the data folder (kept under 2 MB; not part of an export).
- **Progress bar for Export and Import.** Exporting and importing a zip show a progress bar with the percentage and the file being packed or written (it did not show
  before, because the page reloaded the code that held the progress). The import now writes every file of the zip, so existing files are replaced by the zip's
  versions (files that differ are first copied to `Backups\Before Import ...`); a file that has the same size but other content is now noticed too.
- **Screenshot with F2.** F2 saves a picture of the app window (the desktop window, or the browser it runs in) as a PNG in the new `screenshots` folder of the data folder
  (`%APPDATA%\Study Assistant\screenshots`), named with the date and time; a message shows where it went. It also works while a note has focus.
- **Full screen with F11.** F11 turns the desktop window's full screen on and off (also while a note has focus). In a browser, F11 stays the browser's own.
- **F5 refreshes the page.** F5 draws the page again with fresh data and you stay where you are (also inside a note); Ctrl + F5 loads the whole page again.
- **Hide the menu bar.** Press **m** (not while typing in a box) to hide the menu bar so the page uses the whole window; pointing at the left edge shows it above the
  page, and pressing the key again brings it back. Settings has a Hide the Menu Bar switch and a key box to change the key; the choice is remembered.
- **Instructor's notes on a homework.** A homework can carry the notes the instructor gave (what to hand in, hints); they are shown under its row on the course's
  Homework tab.
- **Menu keys.** While the menu bar is shown (or peeking at the left edge), a letter opens a page: **h** Home, **a** Calendar, **l** Library, **n** Note Reader,
  **c** Courses, **s** Settings. The keys do not work while typing in a box, with Ctrl, Alt or Shift, or in drawing mode.
- **Preparation link on past exams.** The Exams tab of a course now shows the Preparation page next to Solution, Reflection and Graded for exams that are over too
  (it was only shown for upcoming exams).
- **Equation sheets for past exams.** The Equation Sheets section of a course's Exams tab lists every exam, so a sheet can be built (or rebuilt) for a midterm that
  is over, not only for the exams still to come.
- **Two ways to check a course quiz.** The Quiz tab has a Checking Mode choice. *Check After Finishing* works as before (nothing is marked until Finish And Score).
  *Check After Each Answer* marks an answer as soon as it is pressed: the right option turns green, a wrong choice red, the explanation is shown, and the answer
  cannot be changed. Check Notes and Hint are not available for an answered question in that mode. The score and the record of attempts are the same.
- **Finished quizzes can be viewed again, and the history is kept.** Each finished chapter quiz has a View button in the Quiz tab that opens any of its attempts: the score,
  every question with the answer you gave, the right answer and the explanation (kept with the attempt, so it still shows if the notes change later). A retake adds a new
  attempt and never removes the earlier ones. The history is deleted only by Clear Attempt History (for one quiz, or for the whole course), after a confirmation.
- **Quiz options are shuffled.** About 8 in 10 written questions had the right answer as the second option, so the options of every question are now put in a new
  random order for each attempt (and for the questions the Note Reader adds to a note, once per session). The right answer is spread evenly over A to D. Questions whose
  options refer to each other ("All of the above", "Both A and B", "option C") or are a row of numbers keep their order, and an "It depends" option stays last.
- **Save a quiz for later.** A quiz that is running has a Save For Later button. It keeps the quiz as it is (the questions and options in their order, the answers given, the
  notes and hints used, the checking mode) in the new `quiz_progress` folder of the data folder and returns to the quiz list, where the chapter shows Resume and Discard Saved
  Quiz. Resuming carries on exactly where you stopped (an exported zip and the backups carry the saved quizzes too). Finishing a resumed quiz removes its saved copy; Start and
  Retake never delete a saved quiz, and finished attempts are never touched.
- **Courses that were merged keep their parts apart.** When two courses are merged into one (for example MA 266 and MA 303 as Differential Equations), each file and homework
  title carries its part in brackets (`HW 10 (MA 266)`, `Exam 1 Graded (MA 303)`). The Homework and Exams tabs and the Library pair a problem file, its solution and its graded paper
  by number *and* part, so the two HW 10 files are never mixed up, and the number inside the bracket is never read as a homework number.
- **A merged course shows one part at a time.** A course made of several courses (MA 266 / 303 Differential Equations, MA 161 / 162 / 261 Calculus) has a *Part of This Course* switch
  above its tabs (each part, or All Parts). Overview (grades and the part's own syllabus and grade weights), Homework, Exams, Outline (each part has its own, built from its own
  syllabus or lectures), Resources and Quiz all show only the chosen part; files without a part (the shared textbook) show in every part. The part's syllabus data is kept as
  `syllabus\<course id>_<part>.json`, and outline rows have a part.

## 1.0.0 (2026-11-10)

First release.

- **Clean installs start empty.** No built-in courses or subjects are created, and the Home page shows the term countdown only after the term dates are saved in
  the Calendar (Edit Schedule).
- **Installer and uninstaller.** The installer adds Study Assistant to Settings > Apps (per user, no administrator). The uninstaller keeps your files by default;
  a choice in its window removes everything, including your files (it asks again first). It never follows a link or junction.
- **Backup, Export My Files and Import.** Settings > Backup keeps a library backup and snapshots, exports a zip of just your files (to keep, or to take to another
  device) and imports such a zip on a device that has the app. Nothing is deleted on import: a file that differs is copied to `Backups\Before Import ...` first.
  The app does not build or package the program; releases are built separately.
- **Course outlines build themselves, and stay editable.** A course with no outline gets one from the topic list in its syllabus or Lec 0 slides
  ("Course Outline", "Course Topics" ...), otherwise from its lecture titles (or, when the lecture files only have names such as "Week 3 Lecture", its
  chapter notes). An automatic outline follows the Library (a new lecture adds a point) until it is edited. **Courses > Outline > Edit Outline** edits the
  outline as plain text (one point per line, indent for each level, markers numbered for you, `[9 Hours]` and links kept), with Use Syllabus Topics and
  Use Lecture Titles to start from; saving makes it your own and it is never replaced automatically. **Auto Build** on the Outline tab builds it again
  at any time (it asks first when the outline is your own, and then the outline follows the Library again). Every outline that is replaced
  is first copied to the `outlines` folder of the data folder.
- **PDF reader zoom and pan in every view mode.** A zoomed page keeps its width and can be scrolled to every edge. Drag the page with the mouse to move it
  (the middle button also pans in drawing mode), Ctrl + wheel or a trackpad pinch zooms (a 400% step was added), and a zoom step keeps the point in the middle of
  the view where it was.
- **Equation and source-line clicks in the Note Reader.** Equations and the lecture and textbook chips of a source line open the matching page of the slides,
  lecture notes or textbook. A source line that names several slide sets (`Lec 6-2, Independent Energy Modes 1–5; Translational Properties 1–11`) opens the set that
  matches the equation's section.
- **Chapter links to a newly imported note.** Add File reads `Chapter 3`, `Ch 3` or `Ch. 3` in the file name or title as the Lecture number, so links such as
  `Lec 3 §2.1` or `Ch3` find the note.
- **Browse buttons** for the backup folder, the folders with your original files and the export folder.
- **Old note builder removed.** Notes are built outside the app and imported into the Library.
- **Disk-space check** before an export is made.
