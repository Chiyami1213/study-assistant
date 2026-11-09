"""Study Assistant installer. Built into "Install Study Assistant.exe" (see build_installer.py); it needs nothing else installed.

It sits next to a `payload` folder that holds
  payload\\program   the program (code, and the app's exe when it was included)   -> <Documents>\\study-assistant
  payload\\data      (only in a full migration) your files and settings             -> %APPDATA%\\Study Assistant
It only COPIES from the payload. A destination folder that already has something in it is never overwritten or deleted: it is renamed to
"<name> (old <date and time>)" first. Nothing outside the two folders is touched, except a Study Assistant shortcut on the Desktop.

Command line (for tests): --silent runs without a window; the folders can be set with SA_INSTALL_PROGRAM_DIR and SA_INSTALL_DATA_DIR."""
import os
import shutil
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path


def here():
    return Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent


def targets():
    home = Path.home()
    program = Path(os.environ.get("SA_INSTALL_PROGRAM_DIR") or (home / "Documents" / "study-assistant"))
    data = Path(os.environ.get("SA_INSTALL_DATA_DIR") or (Path(os.environ.get("APPDATA") or (home / "AppData" / "Roaming")) / "Study Assistant"))
    return program, data


def set_aside(folder):
    """Rename an existing, non-empty folder out of the way (never delete it). Returns the new path or None."""
    if folder.exists() and any(folder.iterdir()):
        new = folder.with_name(f"{folder.name} (old {datetime.now():%Y%m%d-%H%M%S})")
        folder.rename(new)
        return new
    return None


def copy_tree(source, target, progress):
    """Copy every file of `source` into `target` (created), checking each file's size afterwards."""
    files = [p for p in source.rglob("*") if p.is_file()]
    total = sum(p.stat().st_size for p in files) or 1
    done = 0
    target.mkdir(parents=True, exist_ok=True)
    for p in files:
        dest = target / p.relative_to(source)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, dest)
        if dest.stat().st_size != p.stat().st_size:
            raise RuntimeError(f"the copy of {p.name} is incomplete (is the disk full?)")
        done += p.stat().st_size
        progress(done / total)
    return len(files)


def shortcut(program):
    exe = program / "dist" / "StudyAssistant" / "StudyAssistant.exe"
    if not exe.exists() or os.name != "nt" or os.environ.get("SA_INSTALL_PROGRAM_DIR"):      # no shortcut for test installs
        return False
    desktop = Path.home() / "Desktop"
    script = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%s'); $s.TargetPath='%s'; $s.WorkingDirectory='%s'; $s.Save()"
              % (desktop / "Study Assistant.lnk", exe, exe.parent))
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", script], check=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=60)
        return True
    except Exception:
        return False


def install(log, progress):
    payload = here() / "payload"
    program_src, data_src = payload / "program", payload / "data"
    if not (program_src / "app.py").exists():
        raise RuntimeError(f"The package is incomplete: {program_src} is missing. Extract the whole zip first, then run this again from the extracted folder.")
    program, data = targets()
    full = data_src.is_dir()
    steps = 2 if full else 1
    state = {"n": 0}

    def part(p):
        progress((state["n"] + p) / steps)

    log(f"Installing the program to {program}")
    old = set_aside(program)
    if old:
        log(f"  the folder that was there was kept as: {old.name}")
    log(f"  {copy_tree(program_src, program, part)} files copied")
    state["n"] = 1
    if full:
        log(f"Restoring your files to {data}")
        old = set_aside(data)
        if old:
            log(f"  the folder that was there was kept as: {old.name}")
        log(f"  {copy_tree(data_src, data, part)} files copied")
        state["n"] = 2
    else:
        log("This is a clean install: no personal files are brought along. The app makes its own empty data folder the first time it runs.")
    log("A Study Assistant shortcut was put on the Desktop." if shortcut(program)
        else "Start it with: python run.py (in the program folder, after pip install -r requirements.txt).")
    progress(1.0)
    log("Done. You can close this window and open Study Assistant. The extracted package folder is no longer needed.")


def main():
    if "--silent" in sys.argv:
        install(print, lambda f: None)
        return
    import tkinter as tk
    from tkinter import messagebox, ttk
    root = tk.Tk()
    root.title("Study Assistant Installer")
    root.geometry("580x360")
    program, data = targets()
    full = (here() / "payload" / "data").is_dir()
    tk.Label(root, text="Study Assistant", font=("Segoe UI", 16, "bold")).pack(pady=(14, 2))
    tk.Label(root, text=("This installs the program and brings all of your files along." if full
                         else "This installs a clean copy of the program, without any personal files."), wraplength=540).pack()
    tk.Label(root, text=f"Program folder:  {program}\nYour files:  {data if full else '(created empty on first run: ' + str(data) + ')'}",
             justify="left", fg="#444", wraplength=540).pack(pady=6)
    tk.Label(root, text="Existing folders are never overwritten: they are renamed first.", fg="#444").pack()
    bar = ttk.Progressbar(root, length=520, maximum=1.0)
    bar.pack(pady=8)
    box = tk.Text(root, height=8, width=70, state="disabled")
    box.pack(padx=10)
    btn = tk.Button(root, text="Install", width=14)
    btn.pack(pady=8)

    def log(msg):
        box.config(state="normal")
        box.insert("end", msg + "\n")
        box.see("end")
        box.config(state="disabled")

    def work():
        try:
            install(lambda m: root.after(0, log, m), lambda f: root.after(0, lambda: bar.config(value=f)))
            root.after(0, lambda: btn.config(text="Close", state="normal", command=root.destroy))
        except Exception as e:
            msg = str(e)
            root.after(0, lambda: (log(f"Stopped: {msg}"), messagebox.showerror("Study Assistant Installer", msg), btn.config(state="normal")))

    def start():
        btn.config(state="disabled")
        threading.Thread(target=work, daemon=True).start()

    btn.config(command=start)
    root.mainloop()


if __name__ == "__main__":
    main()
