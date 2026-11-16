# Changelog

<p align="center"><a href="README.md">Overview</a> &nbsp;|&nbsp; <a href="docs/INSTALL.md">Install</a> &nbsp;|&nbsp; <a href="docs/FILES.md">Your Files</a> &nbsp;|&nbsp; <a href="docs/SHORTCUTS.md">Shortcuts</a> &nbsp;|&nbsp; <a href="docs/HELP.md">Help</a> &nbsp;|&nbsp; <b>Changelog</b></p>

---

## 1.1.0 (2026-11-15)

### Getting started and calendars

- **Getting Started tutorial.** A new student (no course yet) sees a welcome window and a checklist at the top of Home: add courses, set up the term, add class times, add files, make study guides
  with an AI assistant, add tasks, build the schedule. Each step has a button that goes to the right page and opens the right window, and ticks itself off from what you have done. **Skip
  Tutorial** hides it; a **Show the Tutorial** button stays on Home (and in Settings > Help) so it can be opened again at any time. Someone who already has courses never sees it.
- **Import From Calendar** (Task List). Bring the assignments and events of **Canvas**, **Brightspace** and **Google Calendar** into the planner: paste the private calendar link of the service (it is
  read again to keep things up to date: **Sync Now**, and when the app opens, at most every 3 hours) or import an `.ics` file once. You check a table first (task or event, course found from the
  course number in the title, category); repeating events and time zones are handled; an item is never added twice, a changed one is updated, and one you deleted is not brought back. The link is
  only read, and kept only in the settings file of this computer.

### Study planner and Calendar

- **A study planner.** Set up a term (first day, last day of classes and exams, time zone, wake and bed time, the shortest study block) and the planner knows how much free study time you have. The
  **cushion** of a task is the free time left before its deadline after the work due by then; red means the work cannot fit, yellow is under 2 hours, green is more. Everything is stored in UTC and
  shown in the term's time zone (daylight-saving days included); the time zone list shows UTC offsets such as `America/New_York (UTC-05:00, EST)`.
- **Courses, activities, events.** Courses and activities (office hours, work, gym, me-time) have weekly times with weekdays, place and an optional last day; an activity can be non-busy and can run
  through breaks. Events have a start and an end, an all-day switch, a place, travel time before and after (counted as busy) and a busy switch; exams and other dated events open the same way.
- **Tasks.** A task has a title, a course (or none: a personal task that can also be planned in a break), a category (Homework, Exam, Quiz, Reading, Project, **Lab**, Other), a due moment, an estimate,
  optional start-ahead days, a state and the minutes logged. A new task takes the course's default estimate for its category (Default Estimates per course), or a built-in one.
- **Study sessions and Auto-Plan.** Auto-Plan fills the free time, earliest deadline first, with sessions of at least the shortest block; running it again replaces only the automatic sessions that have not
  started. Manual sessions stay. A placement that breaks a hard rule (outside the term, in a break, over another session) is refused; a soft one (over a class, outside the awake hours) asks "Place It
  Anyway?". Work that does not fit is reported, with an x to dismiss the warning, **Don't Show Again** and a switch in Settings > Study Planner.
- **Tracking.** A study timer starts on a task or a session (Stop and Log adds the minutes, and it survives closing the app); time can be logged by hand. Logged time counts as work done, a session
  shows planned against used, and the Add Task form suggests an estimate from your finished tasks of that category.
- **The Calendar page.** Day, Week (the usual view) and Month, with Prev, Today and Next (and a swipe on a touch screen). The grid shows classes (colored by course), activities, events with their
  travel time and the study sessions, with free time shaded and its length written on it (Show Free Time switches it off). The line next to the hours zooms the time scale (drag; double-click resets).
- **Drag and click on the schedule.** Drag a session, an event, a class or an activity to move it (the new time shows while you drag, and a cancelled change bounces back at once); drag its top or bottom
  edge to change the start or the end; drag over empty time to add a session or an event. A tile shows a map pin before its place and a trash bin. Click one for a compact dialog (title bar in the course
  color, date and times in one row, repeat and until, place, Free; Delete, Cancel, Save).
- **Repeating classes and activities.** After a drag, or from the dialog, the app asks what to change: this event, this and the following events on that weekday, this and all following events, or all
  events. Deleting asks the same; an event or a study session asks before it is deleted. A day can be changed or skipped without touching the other weeks.
- **The left panel.** Your courses and activities as blocks (a custom event block, too) to drag onto the schedule: a course or an activity adds a weekly time, the custom event block opens the new-event
  form. Blocks have a grip to drag them into a new order, a ⋯ menu (Details, Rename, Change Color, Hide, Delete), rename on double-click, and a Hidden section. Delete asks first; a course is deleted only
  after the database is copied to `Backups\Before Delete <time>`. The panel folds, and its border is dragged to change the width (double-click: usual width). Tasks are in the Task List.
- **Terms.** A term list above the calendar (and on the Task List) switches the active term; Manage Terms adds, changes and deletes terms, with the wake-up time, the start and end dates and the holidays
  and breaks of that term. The panels show the active term's courses first and the others in a folded section. Removing a holiday or a class time asks first.

### Task List

- **Every task in one table,** filtered by course (the same blocks as the Calendar panel), grouped by course, category or due week, searched, and sorted by clicking any column head (up, down, or both
  arrows when not sorted by it). A picked course shows its tasks under its name in its color, with its Completed tasks below. Edit all fields, mark done, time, log or delete.
- **Import From Syllabus.** One button reads each course of the term: the homework and exams already on its course page, and the dated work and class times of its syllabus file. New tasks are added at
  once (a graded homework or a past exam as finished, exams also on the Calendar) and never twice. One course can be checked row by row first. It can also write the homework and exams on the course pages
  (on by default).

### Courses

- **Course page.** The Overview is a fixed order of foldable sections: a row of numbers, Coming Up (homework, exams, tasks), Grades, Syllabus and How Well You Know the Material. Add Syllabus reads a
  syllabus pdf (grading, letter grades, instructor, outline); Edit Syllabus changes any of it. Resources starts with Links and every section folds. Edit Outline is written lecture by lecture or chapter
  by chapter in a table, as free text, or pasted.
- **Courses tree.** Courses > All > Tree is a tree that grows upward from **All Disciplines** at the bottom: branches for domains, fields and topics (similar fields on the same branch) and a bubble for each
  course, with its photo as the background. Click a bubble to fold or unfold its branches, click a course to open it, **drag any bubble** to move it (it lifts while held, settles when dropped, its branches
  and courses follow, bubbles and lines never overlap: what a held bubble comes near is pushed away, it slides along lines instead of crossing them, and every bubble stays inside the map's rectangle; a line runs from the border of a bubble to the border of its parent), zoom with + / - or the wheel, drag the map to move it, Fit, **Reset View** (the view and every bubble back where it was) and Collapse All. Self-study courses sit on the branch of their
  own field with a dashed outline. A field with only one topic has no extra "General" bubble, and a course's whole title is shown.
- **Merge Courses.** Make two or more courses one (MA 266 / MA 303): choose the course that stays and a tag for each part. Files, homework and exams get the tag, everything of the other courses moves
  over, they are deleted, and a copy of the database and settings is kept in `Backups\Before Merge`. A merged course's number is written out.

### Library

- **Sort and views.** Sort by Type (a tile for each type, the usual view), Course (a tile for each course, like the Courses page), Date Added (a chain of bullets by day, month or year, newest or oldest
  first; every group folds) or Title. Files show as Cards, Tiles or a Details table. Long lists are drawn 120 files at a time.
- **Import menu.** Add a File, Import a Zip (every pdf and html file of a zip, folders included, on a confirmation page where the type, title, lecture and course of each can be changed and files unchecked)
  and Update From Folder (also on every course page as Update Files): new and changed files are listed for confirmation, files already in the Library (same content) are recognized, homework and exam
  documents come first. Your folders are only read, never changed.
- **Imported files are named the Library's way:** HW 5, HW 5 Solution, Midterm 1 Practice, a note's topic with its number in the lecture field, Syllabus. The Type box of Add File and Edit File shows
  the general types first; Homework and Exam show their own types (helper, solution, graded paper, grade explanation, preparation ...) only when chosen.
- **Prompt for AI (Library > Import).** Pick a course, a kind of page (a study guide, a homework helper, a homework or exam grade explanation, an exam reflection or an exam preparation page) and
  your AI assistant (**Claude, ChatGPT or Gemini**), and the app writes a prompt to paste into your own chat with it. It carries the page's contents and style rules, the file name the page
  must have, and the exact format the app reads (section ids, problem cards, grader-comment badges, quiz questions, link texts), and can list your notes from the Library so the assistant links to
  them. Only the way the finished page is handed over differs between the assistants (an artifact for Claude; a downloadable `.html` file or one code block for ChatGPT; Canvas or one code
  block for Gemini). Download the HTML it makes and import it as usual. The Library also recognizes `... Midterm 1 Reflection.html` and `... Final Exam Preparation.html` as those page types,
  and the app reads a link of the form `.../artifact/<id>` at any address (notes pages that are not on the web are linked as `https://study-assistant.local/artifact/notes-<lecture number>#<section id>`).
  The prompt texts are in `study/prompts/` and can be edited.
- **Grade reports are read by the app.** When a graded homework or exam (a Gradescope graded copy, whose first pages are the grade report) is opened and has no grade data yet, the app reads the
  problems, scores, grader comments and where each comment sits on the paper, so a grade explanation can mark the paper. Nothing has to be run by hand.
- **Tidy Up.** Finds files that are in the Library twice and lets you remove the extra ones (the book that stays takes over their courses), and suggests titles in the Library's own form. Both ask
  first, and the database is copied to Backups.

### Windows, macOS and the GitHub pages

- **Study Assistant for macOS.** A `.dmg` for Apple silicon and one for Intel Macs: open it, drag the app into Applications and approve it once (right-click > Open). The files live in
  `~/Library/Application Support/Study Assistant`; an export from Windows imports on a Mac and the other way round. Screenshots (F2), the folder and file pickers use the macOS tools. The Mac app is built
  and checked by GitHub (`.github/workflows/build-macos.yml`, `tools/build_mac.py`).
- **A new setup wizard (Windows),** drawn at the screen's real resolution with a picture panel and Back / Next / Cancel: welcome, existing version, shortcuts, ready, progress with percentage, finish
  (with links to the project page, Help and the issue page). Larger check boxes.
- **The installer finds an installed version** and offers Update (the old program is removed only after the new one is in place), Uninstall the older version first, or Keep both (own folder, shortcut and
  Settings > Apps entry, with a warning that both share one data folder and one address). A newer installed version is warned about, and a folder not made by the installer is only renamed. Your files
  are never replaced. A Desktop shortcut and a Start menu entry are options; the uninstaller removes both.
- **Fewer antivirus false alarms.** The installer says up front that an antivirus or SmartScreen may warn; the exes carry version information and are not compressed with UPX; every release publishes
  its SHA-256 checksum.
- **The GitHub page has tabs** (Overview, Install, Your Files, Shortcuts, Help, Changelog), each its own page in `docs/`; the README has a gallery of the current screens (with made-up courses and files).

### Settings, speed and small things

- **The code is grouped in folders** (`core`, `library`, `study`, `datafiles`, `desktop`, `planner`, `views`, and `tools` for the build scripts and the installer) instead of one long list of files.
- **Streamlit is limited to 1.50 up to 1.66** in `requirements.txt` (what the app was tested with); the exe carries its own copy.
- **Fixes found while checking this release:** the hover note of the Import button no longer stays on top of the window the Import menu opens, the tree's buttons no longer wrap to two lines on a narrow window, a cancelled repeating-event change bounces back, the Import menu closes behind the
  window it opens, and the Remove buttons in Edit Schedule are right-aligned.
- **Help and Report an Issue in Settings.** Help answers the common questions; Report an Issue opens a ready-made GitHub issue in the browser (optional steps, technical details, a log excerpt with your
  name and folders replaced, screenshots you pick or the newest F2 ones). The app sends nothing by itself and keeps no e-mail address.
- **Settings has a bar to jump to a section** (Appearance, Eye Rest, Study Planner, Backup, Keyboard Shortcuts, Help, Report an Issue, Danger Zone, About), styled like the tabs of a course page.
- **3D views in guides work without the internet.** three.js (r128, which the guides use) is kept with the app (`study/vendor`) and put into a guide's page instead of being fetched, so the 3D
  tools show on a device whose network blocks the CDN. The window also lets WebView2 fall back to software drawing when a graphics driver is on its block list, which is what turns WebGL off.
  (The math in guides still comes from the MathJax CDN.)
- **Speed on slower devices.** Settings > Speed and Effects: Light turns off animations, shadows and blur; Automatic does it by itself when the screen draws slowly and remembers it.
- **Buttons at the top of every page look alike** (outlined, one size, icon and text centered), and the Remove buttons in Edit Schedule and Manage Terms use normal text.
- **The old quiz files are gone.** The Quiz tab asks the questions that are in the notes themselves (the `Q` array of a study guide, or a note's Self-check); the `quizzes` folder of question
  files that had to be written outside the app is no longer read.
- **Back and Forward** return to the same place inside a page (the Task List, a Library tile and its sort), in the order the places were visited.
- **The loading screen** shows the app icon with a bar from 0 to 100% and waits at least 1 second.

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
