# Changelog

The release number is in `version.py` and shows in Settings > About, the installer and the Windows list of installed apps.

## 1.0.1 (2026-11-09)

Fixes after 1.0:

- **Equation sources with several slide sets.** A source line such as `Lec 6-2, Independent Energy Modes 1–5; Translational Properties 1–11` was read as
  one unknown range, so clicking an equation opened page 1 of the slides. The line is now split at `;` and the part whose title best matches the
  equation's section heading is used, then the slide set is found inside the PDF (equations 4.9 to 4.11 of the Chapter 6 notes now open the
  Translational Properties slides).
- **Chapter links to a newly imported note.** The Add File window only guessed the Lecture number from a leading `Lec 3`, so a note such as
  `AE6765 Chapter 3 Notes.html` was added with an empty Lecture box and links such as `Lec 3 §2.1` or `Ch3` could not find it. `Chapter 3`, `Ch 3` and
  `Ch. 3` in the file name or title now fill the Lecture box (it can still be edited).

## 1.0 (2026-11-09)

First release.

- **Clean installs start empty.** The four built-in subjects (Anatomy, Tonal Harmony, Macroeconomics, Pyrochemistry) and the sample courses are no longer
  created, and the Home page shows the term countdown only after the term dates are saved in the Calendar (Edit Schedule).
- **Uninstaller.** The installer adds Study Assistant to Settings > Apps (per user, no administrator). The uninstaller keeps your files by default;
  a choice in its window removes everything, including your files (it asks again first). It never follows a link or junction.
- **Export My Files Only and Settings > Import.** Export a zip of just your files, then import it on a laptop that already has the app. Nothing is deleted:
  a file that differs is copied to `Backups\Before Import ...` first.
- **Migration zip fix.** The zip skipped every folder named `static`, `build` or `data` at any depth, which removed the app's own web page
  (`streamlit\static`); the new laptop then showed a black window with "Not Found". These names are now skipped only at the top of the project folder.
- **Browse buttons** for the backup folder, the folders with your original files and the migration zip folder.
- **Old note builder removed.** The `notes` folder of the data folder, the `lab_chapters` table and the code behind them are gone; notes are built outside the
  app and imported into the Library.
- **Equation and source-line clicks in the Note Reader.** Equations and the lecture and textbook chips of a source line open the matching page of the slides,
  lecture notes or textbook (slide sets inside one PDF are found from their page headers; the equation's section heading helps choose the page).
- **Disk-space check** before a migration zip is made.
- **Personal files out of the repository.** Notes and quizzes live in the data folder (`%APPDATA%\Study Assistant`) and are no longer tracked; README
  and complete `requirements.txt` for a public repository.
