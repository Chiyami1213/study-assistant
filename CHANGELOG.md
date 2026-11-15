# Changelog

<p align="center"><a href="README.md">Overview</a> &nbsp;|&nbsp; <a href="docs/INSTALL.md">Install</a> &nbsp;|&nbsp; <a href="docs/FILES.md">Your Files</a> &nbsp;|&nbsp; <a href="docs/SHORTCUTS.md">Shortcuts</a> &nbsp;|&nbsp; <a href="docs/HELP.md">Help</a> &nbsp;|&nbsp; <b>Changelog</b></p>

---

## 1.1.0 (not released yet)

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
- **Phase 1 of the study planner: setup and data model.** A new pure, tested `planner` package (`models.py`, `timeutil.py`) holds the term (first day, last day of classes, last day of exams,
  time zone, named breaks), the wake and bed time of each weekday and the minimum study block (30 minutes by default); an invalid setup cannot be built. Times are stored in UTC and shown in the term's
  zone (daylight-saving days included). `planner/store.py` keeps it in the database (new tables `planner_settings` and `planner_awake`), the term dates in the settings the Calendar already uses and the
  breaks as the existing holidays. **Settings > Study Planner** sets the time zone, the awake times and the minimum block. Run the tests with `python -m pytest`.
- **Phase 2 of the study planner: recurring commitments and events (data and logic; the screens come in phase 6).** Courses and **activities** (office hours, work, gym, me-time) have weekly
  meetings with weekdays, times, a place and an optional last day; an activity can be non-busy (shown but not blocking) and can run through breaks. A recurring meeting can be changed for
  **this occurrence only** (skipped, or moved to another time or place) or for the **whole series**. **Events** have a start and end in UTC, an all-day flag, a place, travel minutes before
  and after (counted as busy) and a busy flag; the older dated events (exams) are read as before. `planner/commitments.py` (pure) turns it all into the sorted busy blocks of a date range,
  `planner/commit_store.py` keeps it in the database (new tables `activities`, `activity_meetings`, `meeting_exceptions`; new columns on `events` and `class_meetings`; an older database is
  upgraded without losing a row), and the Calendar already honors the new end dates and exceptions.
- **Phase 3 of the study planner: tasks (data and logic; the screens come in phase 6).** A task has a title, an optional course, a category (Homework, Exam, Quiz, Reading, Project, Other),
  an optional due moment (UTC), an estimate in minutes, optional start-ahead days (start that many days before the due date), a state (todo or done) and the minutes logged. A new task
  inherits the **course's default estimate for its category** (else a built-in one: homework 2 h, exam 10 h, quiz 45 min, reading 1 h, project 10 h, other 1 h) unless an estimate is given;
  changing a default later does not change tasks that exist. The lists are plain functions: **to-do** (by due date), **overdue**, **start soon** (start date within three days, nothing logged yet),
  **no due date** and **completed**. `planner/tasks.py` is pure, `planner/task_store.py` keeps it in the new tables `tasks` and `task_defaults`; a deleted course leaves its tasks (without a course).
- **Phase 4 of the study planner: the free-time engine and the cushion (logic; the screens come in phase 6).** `planner/freetime.py` (pure) computes the **free study time** of any date range: awake time minus
  classes, activities, busy events and their travel time, breaks and sessions already planned, nothing before now, and no piece shorter than the minimum block. The **cushion** of a task is the free time left
  before its deadline after the work that is due by then (earliest deadline first); a task with a start-ahead date cannot use the time before it, so the engine reports the tightest window, which is the exact slack.
  A **negative cushion** means the schedule is impossible (red; under 2 hours is yellow, else green); a deadline that has passed counts as due now. It also gives the **cushion timeline** (the tightest
  cushion of each deadline day) and `planner/service.py` reads it all from the saved setup. Checked against an independent earliest-deadline-first simulation on random cases (about 100) and by hand.
- **Phase 5 of the study planner: study sessions (logic; the screens come in phase 6).** The **auto-planner** fills the free time earliest deadline first, from each task's start-ahead date to its deadline, in
  sessions of at least the minimum block (a task is split across sessions when it has to be, never into a piece shorter than the minimum; a task that needs less than the minimum gets one short session); the
  same input always gives the same plan. Re-planning replaces only the automatic sessions that have not started: **manual sessions and sessions already begun stay** and count as planned time; an overdue task is
  placed as soon as there is room and reported; what does not fit is reported per task. **Manual sessions** can be created, moved, resized, deleted, and all of a task's sessions can be unplanned. Every placement
  is checked: outside the term, in a break or over another session is never allowed; outside the awake hours, over a class or event, or shorter than the minimum block is refused unless forced. Every change
  returns the **new cushion** (`planner/service.py`); a task's own sessions count as work done, so planning its work does not change its cushion, while it does use up free time for the others. New table
  `study_sessions`; `planner/sessions.py` is pure, `planner/session_store.py` keeps them.
- **Phase 6 of the study planner: the Calendar screens.** The Calendar page now has **Week, 2 Days, Day and Month** views with Prev, Today and Next buttons (and a sideways swipe over the day names on a
  touch screen). The time grid shows classes (colored by course, with changed occurrences marked), activities, events with their **travel time** (hatched) and the **study sessions** (dashed, light; solid when
  you placed them), each with a dot for its task's cushion. **Drag** a study session or an event to move it (to another time or day), drag its bottom edge to change its length, drag over empty time to add a
  study session or an event, or click one to open it; a move that only breaks a soft rule (a class, the awake hours) asks first ("Place It Anyway?"), one that breaks a hard rule just says why. **Auto-Plan**
  fills the free time with sessions. Below the grid, **Tasks** lists what is due with a green, yellow or red **cushion badge** (how much free time is left before the deadline), an **Add Task** form (the
  estimate defaults to the course's and the category's), **Default Estimates** per course, and buttons to mark done, unplan or delete; a **warning banner** appears when any cushion is negative. The Add Event
  form can set a place, travel time and whether the event blocks study time. Drawing code is `views/plan_grid.py` (tested), dialogs and the task list are `views/planner_ui.py`.
- **Blocks on the left, dragged into the schedule.** Beside the grid is a panel with a **Drag a custom event** block, your **tasks** (colored by course, with their cushion dot and the time left to plan),
  your **courses** and your **activities**. Drag a task onto the calendar to place a study session there (as long as what is left to plan, 30 minutes to 2 hours); drag the custom event block to open the
  new-event form at that time; drag a course or an activity to add a weekly time on that day. **+ Task** and **+ Activity** add new ones. Free time is shaded in the grid with its length written on it
  (**Show Free Time** switches it off).
- **Phase 7 of the study planner: tracking.** A **study timer** can be started on a task (the play button in the task list) or on one of its sessions; a bar above the calendar shows what you are
  studying and the running time, and **Stop and Log** adds the minutes to the task (rounded to the minute, under half a minute is not logged, a timer left running is cut at 12 hours; it survives closing the
  app). Time can also be logged by hand, and every log can be removed. **Logged time is work done**, so it raises the cushion. A session shows **planned against used** (a bar along its bottom and a line in its
  dialog: done, partly used, not used), and the task list shows the time used. **Suggested estimates:** when you add a task, the form suggests the typical time of your finished tasks of that category (the
  median of the time logged, from the same course when it has at least two, rounded to 5 minutes). `planner/tracking.py` is pure, `planner/track_store.py` keeps the timer and the logs (new tables
  `time_logs` and `study_timer`).
- **Change a class or an activity for one day, or for every week.** Click a class or an activity in the grid to open it. **This Day Only:** change that day's time or place, skip it, or go back to the usual
  (the rest of the weeks stay as they are; a changed day is marked *moved*). **Every Week:** change the weekdays, the time, the place and the last day of the whole series, or remove the weekly time; an activity's
  name, color, place, whether it blocks study time and whether it also happens in breaks can be edited, or the activity deleted. The old Calendar code, the planner and the free time all follow these changes.
- **Settings: a bar to jump to a section.** The top of Settings has a link for each section (Appearance, Eye Rest, Study Planner, Backup, Keyboard Shortcuts, Help, Report an Issue, Danger Zone, About); it
  stays in view while you scroll and the heading it jumps to is lined up under it.
- **The time zone list shows UTC offsets.** Each zone reads like `America/New_York (UTC-05:00, EST)` (the offset in force today), the list runs from west to east, and typing `utc-5` finds a group.

- **Calendar: Day, Week, Month.** The two-day view is gone and Week is the usual view. The Calendar page now has two pages, Calendar and Task List, and the old Tasks, Add Event and This
  Month sections under the grid are gone: their functions moved into the Calendar (every event, also the older dated ones such as exams, opens with a click and can be changed or deleted,
  and a new event can be all day) and the Task List.
- **Terms (semesters).** A term list above the calendar (and on the Task List) switches the active term; its last entry, Manage Terms, adds, changes and deletes terms. The left bars
  show the courses of the active term on top and the other courses in a folded section.
- **Left panel of the Calendar.** Blocks have a grip to drag them into a new order, a ⋯ menu (Details, Rename, Change Color, Hide, Delete) with icons, and a name that renames on double-click.
  A hidden block waits in a Hidden section. Delete asks first (a course is deleted only after the database is copied to `Backups\Before Delete <time>`). The panel folds and opens with
  an animation, its right border is dragged to change the width (double-click: usual width), and a dragged block shows a preview of where it lands (an hour tall, a task as long as its
  session). The line next to the hours zooms the time scale (drag; double-click resets). Auto-Plan lines up with Edit Schedule.
- **Task List page.** Every task in one table, filtered by course (the same blocks as the Calendar panel), grouped by course, category or due week, sorted by due date, category, course, title
  or time left (ascending or descending), searched, edited (all fields), made done, timed, logged or deleted. Personal tasks (no course) can be planned in a break and outside the term.
- **Import From Syllabus.** One button reads each course of the term: the homework and exams already in its course page, and the dated work and class times of its syllabus file in the
  Library. Every new task is added at once (a graded homework or a past exam as finished, exams also on the Calendar); a task already in the list is never added twice. One course can be
  checked row by row first, with any row changed, added or unchecked.
- **Library: sort by type first.** The usual view is a tile for each type; click one to see its files and sort them by course, date added or title. Sort by course shows a tile for each course,
  Date Added a timeline by day (newest or oldest first), Title the plain grid. The row of type buttons is gone.
- **The loading screen waits at least 1 second** (it was 2).
- **Library: Import menu.** Import a Zip lists every pdf and html file in a zip (folders included) on a confirmation page, where the type, title, lecture and course of each can be changed and
  files unchecked, and nothing is imported until you press Import. Update From Folder (also on every course page as Update Files) reads the folder your files are kept in: new files and files that
  changed since they were imported are listed for confirmation, an updated file replaces the stored copy, and files already imported are not listed again. The folder is only read, never changed.
- **The Calendar panel lists courses and activities only.** Tasks are in the Task List.
- **Calendar tiles.** Classes and activities can be dragged on the schedule too (the time changes for that day only; drag the top or bottom edge to change the start or the end). A tile shows a map
  pin before its location and a trash bin at its top right. Deleting a repeating class or activity asks what to delete: this event, this and the following events on this weekday, this and all
  following events, or all events. An event or a study session asks before it is deleted. The warning about work that does not fit has an x to dismiss it.
- **Courses tree** is now a tree from left to right (a pill for each branch and course, no fill, larger text) that fits the window, folds one bubble at a time with a click (everything slides into place
  and the view fits what is left), has one Collapse All / Expand All button, zoom with + / - or the wheel, and drag to move. Self-study courses grow on the branch of their own field with a dashed
  outline and a hover note. A merged course's number is written out (MA 266 / MA 303).
- **Course page.** The Overview is in a fixed order of foldable sections (a row of numbers, Coming Up, Grades, Syllabus, How Well You Know the Material). Add Syllabus reads a syllabus pdf (grading, letter
  grades, instructor, outline) and Edit Syllabus changes any of it. The Resources tab starts with Links and every section folds. Edit Outline can be written lecture by lecture or chapter by chapter in a
  table (number and title), as free text, or pasted from somewhere else.
- **Tidy Up (Library > Import).** Finds files that are in the Library twice (same content) and lets you remove the extra ones (the book that stays takes over their courses), and suggests titles in the
  Library's own form (HW 5 Solution, Midterm 1, a note's topic with its lecture number); both after a confirmation, and the database is copied to Backups first.
- **Merge Courses (Courses page).** Make two or more courses one (MA 266 / MA 303): choose the course that stays and a tag for each part; files, homework and exams are tagged, everything of the other
  courses moves over, the others are deleted, and a copy of the database and settings is kept in Backups\Before Merge.
- **Import From Syllabus** can also write the homework and the exams on the course pages (on by default); what a page has already is not added twice.
- **Holidays and breaks** are managed in Manage Terms (those of the chosen term); removing a holiday or a class time asks first. The "work does not fit" warning has Don't Show Again (and a switch
  in Settings > Study Planner).
- **Speed on slower devices.** Settings > Speed and Effects: Light turns off animations, shadows and blur; Automatic does it by itself when the screen draws slowly (and remembers it); long Library lists
  are drawn 120 files at a time. The Windows setup wizard's check boxes are larger and easier to see.
- **Changing a repeating class.** After a class or an activity is dragged, the app asks: this event, this and the following events on that weekday, this and all following events, or all events; the
  new time shows while dragging, and there is no "moved" label.
- **Imported files are named the Library's way** by default (HW 5, HW 5 Solution, Midterm 1 Practice, a note's topic with its number in the lecture field, Syllabus), and the confirmation page lists
  homework and exam documents first. The loading screen shows the app icon.
- **Library views and timeline.** Files can be shown as Cards, Tiles (a small cover with the details beside it) or a Details table. Date Added is a chain of bullets by day, month or year;
  every group folds up. The sort box and the Newest First button sit in the title row.
- **Courses: a tree of knowledge.** Courses > All > Tree is a mind map: a bubble in the middle, large bubbles for the branches (domain, field, topic) with similar fields on the same branch, and a
  white bubble for each course. A click on a bubble folds its branches into it (and they slide out again), and a click on a course opens it. A course page's Overview starts with what is coming up (homework, exams and tasks).
- **Edit dialogs.** Clicking a class, an activity, an event or a study session opens a compact dialog: a title bar in the course color, the date and times in one row, repeat and until, location,
  Free, and Delete, Cancel, Save.
- **Back and Forward** return to the same place inside a page (the Task List, a Library tile and its sort), in the order the places were visited.
- **Task List.** Every column head sorts (up, down, or both arrows when not sorted by it); a picked course shows only its tasks under its name in its color, with its Completed tasks in a section below.
- **Fixes.** The line under the Settings jump bar no longer crosses its links (the bar looks like the tabs of a course page); a dragged block shows only its preview on the schedule.

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
