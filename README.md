# Study Assistant

Version 1.0 (`version.py`).

A personal study app for coursework: a course library (textbooks, lecture notes, homework and exam PDFs), a Note Reader for interactive HTML
notes, homework and exam readers with drawing and grade explanations, a calendar, quizzes and a Home page with what is due. It runs locally
(Streamlit + SQLite) in its own desktop window; nothing is sent anywhere.

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

See `CLAUDE.md` for the conventions of the code base and the format of the notes the Note Reader reads.
