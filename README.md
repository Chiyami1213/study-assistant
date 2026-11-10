# Study Assistant

Version 1.0.1 (`version.py`). See the [changelog](#changelog) below for what changed in each release.

A personal study app for coursework: a course library (textbooks, lecture notes, homework and exam PDFs), a Note Reader for interactive HTML
notes, homework and exam readers with drawing and grade explanations, a calendar, quizzes and a Home page with what is due. It runs locally
(Streamlit + SQLite) in its own desktop window; nothing is sent anywhere.

## Download and install (Windows)

Download `StudyAssistant-1.0.1-Windows-Installer.zip` from the [Releases](../../releases) page, extract the whole zip, and run `Install Study Assistant.exe` from the
extracted folder (keep the `payload` folder next to it). It installs the app for your user only (no administrator needed), puts a shortcut on the desktop and
lists Study Assistant under Settings > Apps, where it can be uninstalled (your files are kept unless you choose to remove them). Windows may ask you to confirm
the first start, because the exe is not code-signed. The app starts empty; add your own courses and files.

## Run

```
pip install -r requirements.txt
python run.py            # desktop window (Windows needs the Edge WebView2 runtime)
python run.py --browser  # or in your web browser
```

## Where your files go

The project folder holds only code. Everything you add (database, settings, imported PDFs and notes, covers, photos, drawings) is kept in
`%APPDATA%\Study Assistant`, created empty on first run. Imports are always copies; your original files are never changed or deleted.

## Moving to another computer

Settings > Migrate makes one zip with the program, your files and an installer (`Install Study Assistant.exe`). Extract it on the new computer and run the
installer: it copies the program to `Documents\study-assistant` and your files to `%APPDATA%\Study Assistant`, and renames (never overwrites) anything
already there. To start clean instead, just copy this project folder.

## Build the exe (optional)

```
pip install pyinstaller
python build_exe.py      # dist/StudyAssistant/StudyAssistant.exe and dist/installer/Install Study Assistant.exe
```

## Changelog

The full history is in [CHANGELOG.md](CHANGELOG.md).

**1.0.1**
- Course outlines build themselves from the syllabus topics (or the Lec 0 slides), otherwise from the lecture or chapter titles; Courses > Outline > Edit Outline edits
  them as text and Auto Build rebuilds them. A replaced outline is copied to the data folder first.
- PDF reader: zoom works in every view mode, drag the page to move it, Ctrl + wheel zooms, and a zoom step keeps your place.
- Note Reader: an equation whose source line names several slide sets opens the set that matches its section.
- Add File reads `Chapter 3`, `Ch 3` as the lecture number, so links to a newly imported note find it.

**1.0**
- First release: clean installs start empty, an installer that registers an uninstaller (keep or remove your files), Export My Files Only and Settings > Import,
  the migration zip fix, Browse buttons, and equation and source-line clicks in the Note Reader.

See `CLAUDE.md` for the conventions of the code base and the format of the notes the Note Reader reads.
