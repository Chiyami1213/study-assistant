"""Study Assistant installer. Built into "Install Study Assistant.exe" (see build_installer.py); it needs nothing else installed.

It sits next to a `payload` folder that holds
  payload\\program   the program (code, and the app's exe when it was included)   -> <Documents>\\study-assistant
  payload\\data      (only in a zip that carries files) your files and settings             -> %APPDATA%\\Study Assistant
It only COPIES from the payload. A destination folder that already has something in it is never overwritten or deleted: it is renamed to
"<name> (old <date and time>)" first. Nothing outside the two folders is touched, except a Study Assistant shortcut on the Desktop.

It also registers the program for the current user only (no administrator needed) in Windows' list of installed apps (Settings > Apps, Control
Panel > Programs), with an uninstaller: "Uninstall Study Assistant.exe" in the program folder (this same exe, run with --uninstall). The uninstaller
removes the program folder, the desktop shortcut and that registry entry. By default it KEEPS your files (the data folder); a tick box in its window
("also delete my files", off by default, asks again) or --remove-files makes it a clean uninstall that deletes the data folder too. It never follows a
link or junction, and refuses to touch a folder that was not made by this installer or that holds a git repository.

Command line (for tests): --silent runs without a window; --uninstall uninstalls (with --silent: without a window; add --remove-files to delete the
data folder as well); the folders can be set with SA_INSTALL_PROGRAM_DIR and SA_INSTALL_DATA_DIR, and the registry entry's name with
SA_INSTALL_REG_KEY (a test install only registers when it is set)."""
import json
import os
import shutil
import stat
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

from version import VERSION

APP_NAME = "Study Assistant"
UNINSTALL_NAME = "Uninstall Study Assistant.exe"
UNINSTALL_SCRIPT = "uninstall_study_assistant.py"                 # used instead of the exe when this runs from source
MARKER = ".study-assistant-install.json"                          # written into the program folder by the installer; the uninstaller needs it
REG_PARENT = r"Software\Microsoft\Windows\CurrentVersion\Uninstall"


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


def reg_key_name():
    return os.environ.get("SA_INSTALL_REG_KEY") or "StudyAssistant"


def wants_registry():
    """A test install (SA_INSTALL_PROGRAM_DIR set) leaves the registry alone unless a test key name is given."""
    return os.name == "nt" and (not os.environ.get("SA_INSTALL_PROGRAM_DIR") or bool(os.environ.get("SA_INSTALL_REG_KEY")))


def register(program, data, size_bytes):
    """Add the program to the current user's list of installed apps (HKCU, no administrator needed). Returns True when it worked."""
    if not wants_registry():
        return False
    try:
        import winreg
        exe = program / "dist" / "StudyAssistant" / "StudyAssistant.exe"
        if getattr(sys, "frozen", False):
            command = f'"{program / UNINSTALL_NAME}" --uninstall'
        else:
            command = f'"{Path(sys.executable).with_name("pythonw.exe")}" "{program / UNINSTALL_SCRIPT}" --uninstall'
        values = {"DisplayName": APP_NAME, "DisplayVersion": VERSION, "Publisher": APP_NAME,
                  "InstallLocation": str(program), "InstallDate": datetime.now().strftime("%Y%m%d"),
                  "DisplayIcon": str(exe if exe.exists() else program / UNINSTALL_NAME), "UninstallString": command,
                  "QuietUninstallString": command + " --silent"}
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, REG_PARENT + "\\" + reg_key_name(), 0, winreg.KEY_WRITE) as key:
            for name, value in values.items():
                winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
            winreg.SetValueEx(key, "EstimatedSize", 0, winreg.REG_DWORD, int(size_bytes // 1024))
            winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)
        return True
    except Exception:
        return False


def unregister(name=None):
    if os.name != "nt":
        return
    try:
        import winreg
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, REG_PARENT + "\\" + (name or reg_key_name()))
    except OSError:
        pass


def is_link(path):
    """True for a symbolic link or a Windows junction. These are never followed or emptied."""
    try:
        st = os.lstat(path)
    except OSError:
        return False
    return stat.S_ISLNK(st.st_mode) or bool(getattr(st, "st_file_attributes", 0) & 0x400)


def remove_tree(folder, keep, skipped, protect_db=True):
    """Delete what is inside `folder` (files, then empty folders) without ever entering a link or junction, or the paths in `keep`.
    With protect_db a folder that holds a study.db (a data folder inside the program folder) is left alone too. Whatever is left out or
    cannot be deleted is added to `skipped`."""
    for entry in list(os.scandir(folder)):
        path = Path(entry.path)
        if path in keep:
            continue
        if is_link(path):
            skipped.append(path)
        elif entry.is_dir(follow_symlinks=False):
            if protect_db and (path / "study.db").exists():
                skipped.append(path)
                continue
            remove_tree(path, keep, skipped, protect_db)
            try:
                path.rmdir()
            except OSError:
                skipped.append(path)
        else:
            try:
                os.chmod(path, stat.S_IWRITE)
                path.unlink()
            except OSError:
                skipped.append(path)


def shortcut_target(link):
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", "(New-Object -ComObject WScript.Shell).CreateShortcut('%s').TargetPath" % link],
                             capture_output=True, text=True, timeout=60, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return out.stdout.strip()
    except Exception:
        return ""


def uninstall(log, progress, remove_files=False):
    """Remove the program folder, the desktop shortcut and the installed-apps entry. Your files (the data folder) are kept unless remove_files
    is set (a clean uninstall), in which case the data folder is deleted too."""
    program = here()
    marker = program / MARKER
    if not marker.exists():
        raise RuntimeError(f"{program} was not made by the Study Assistant installer, so nothing was removed.")
    if (program / ".git").exists():
        raise RuntimeError(f"{program} holds a git repository (a development copy), so nothing was removed.")
    info = json.loads(marker.read_text(encoding="utf-8"))
    data = Path(info.get("data") or targets()[1])
    own = Path(sys.executable) if getattr(sys, "frozen", False) else Path(__file__).resolve()
    if remove_files:
        if "study assistant" not in data.name.lower() or data == program or data in program.parents or is_link(data):
            raise RuntimeError(f"{data} does not look like the Study Assistant data folder, so nothing was removed.")
    keep = {own, marker} if remove_files else {own, marker, data}
    progress(0.1)
    skipped = []
    log(f"Removing the program from {program}")
    remove_tree(program, keep, skipped)
    progress(0.6)
    if remove_files and data.exists():
        log(f"Deleting your files in {data}")
        remove_tree(data, set(), skipped, protect_db=False)
        try:
            data.rmdir()
        except OSError:
            skipped.append(data)
    progress(0.8)
    desktop_link = Path(info["shortcut"]) if info.get("shortcut") else None
    if desktop_link and desktop_link.exists() and shortcut_target(desktop_link).lower().startswith(str(program).lower()):
        desktop_link.unlink()
        log("The Desktop shortcut was removed.")
    unregister(info.get("reg_key"))
    log("The entry in the list of installed apps was removed.")
    left = [p for p in skipped if p != own]
    if left:
        log(f"{len(left)} items could not be removed (a link, or a file that is in use: close Study Assistant and run the uninstaller again):")
        for p in left[:6]:
            log(f"  {p}")
    else:
        marker.unlink(missing_ok=True)
    if remove_files:
        log("Your files were deleted (clean uninstall)." if not any(str(p).startswith(str(data)) for p in left) else "Some of your files could not be deleted (see above).")
    else:
        log(f"Your files in {data} were kept. Delete that folder yourself if you no longer want them.")
    progress(1.0)
    return own, program, not left


def finish_removal(own, program, clean):
    """The uninstaller cannot delete itself while it runs: a hidden helper waits, deletes it, then removes the program folder if it is empty."""
    if not clean:
        return
    if getattr(sys, "frozen", False):
        script = ("$p='%s'; for($i=0;$i -lt 30;$i++){ Remove-Item -LiteralPath $p -Force -ErrorAction SilentlyContinue; if(-not (Test-Path -LiteralPath $p)){break}; Start-Sleep 1 }; "
                  "if(-not (Get-ChildItem -LiteralPath '%s' -Force)){ Remove-Item -LiteralPath '%s' -ErrorAction SilentlyContinue }" % (own, program, program))
        subprocess.Popen(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", script], stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    else:
        try:
            own.unlink()
            program.rmdir()
        except OSError:
            pass


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
    made_shortcut = shortcut(program)
    log("A Study Assistant shortcut was put on the Desktop." if made_shortcut
        else "Start it with: python run.py (in the program folder, after pip install -r requirements.txt).")
    try:                                                    # what the uninstaller needs: this program, and a marker that this folder is ours
        if getattr(sys, "frozen", False):
            shutil.copyfile(sys.executable, program / UNINSTALL_NAME)
        else:
            shutil.copyfile(Path(__file__), program / UNINSTALL_SCRIPT)
        size = sum(p.stat().st_size for p in program.rglob("*") if p.is_file())
        (program / MARKER).write_text(json.dumps({"version": VERSION, "installed": datetime.now().isoformat(timespec="seconds"), "program": str(program), "data": str(data),
                                                  "shortcut": str(Path.home() / "Desktop" / "Study Assistant.lnk") if made_shortcut else "",
                                                  "reg_key": reg_key_name()}, indent=1), encoding="utf-8")
        log("It can be uninstalled from Settings > Apps > Installed apps (Study Assistant)." if register(program, data, size)
            else "It could not be added to the list of installed apps, so there is no uninstaller entry.")
    except OSError as e:
        log(f"The uninstaller could not be set up: {e}")
    progress(1.0)
    log("Done. You can close this window and open Study Assistant. The extracted package folder is no longer needed.")


def main_uninstall():
    if "--silent" in sys.argv:
        finish_removal(*uninstall(print, lambda f: None, "--remove-files" in sys.argv))
        return
    import tkinter as tk
    from tkinter import messagebox, ttk
    root = tk.Tk()
    root.title(f"Uninstall Study Assistant {VERSION}")
    root.geometry("580x470")
    try:
        data = Path(json.loads((here() / MARKER).read_text(encoding="utf-8")).get("data") or targets()[1])
    except (OSError, ValueError):
        data = targets()[1]
    tk.Label(root, text=f"Uninstall Study Assistant {VERSION}", font=("Segoe UI", 16, "bold")).pack(pady=(14, 2))
    tk.Label(root, text=f"This removes the program from {here()}, the Desktop shortcut and the entry in the list of installed apps.\n"
                        f"Your files are in {data}. What should happen to them?", wraplength=540, justify="left").pack(pady=6)
    choice = tk.IntVar(value=0)
    tk.Radiobutton(root, text="Keep my files (recommended): the Library, notes, grades, settings and backups stay on this computer", variable=choice, value=0,
                   wraplength=520, justify="left").pack(anchor="w", padx=24)
    tk.Radiobutton(root, text="Remove everything, including my files (clean uninstall): this cannot be undone", variable=choice, value=1,
                   fg="#b00020", wraplength=520, justify="left").pack(anchor="w", padx=24)
    bar = ttk.Progressbar(root, length=500, maximum=1.0)
    bar.pack(pady=6)
    box = tk.Text(root, height=8, width=68, state="disabled")
    box.pack(padx=10)
    btn = tk.Button(root, text="Uninstall", width=14)
    btn.pack(pady=8)
    result = {}

    def log(msg):
        box.config(state="normal")
        box.insert("end", msg + "\n")
        box.see("end")
        box.config(state="disabled")

    def close():
        finish_removal(*result["done"]) if "done" in result else None
        root.destroy()

    def work():
        try:
            result["done"] = uninstall(lambda m: root.after(0, log, m), lambda f: root.after(0, lambda: bar.config(value=f)), bool(choice.get()))
            root.after(0, lambda: btn.config(text="Close", state="normal", command=close))
        except Exception as e:
            msg = str(e)
            root.after(0, lambda: (log(f"Stopped: {msg}"), messagebox.showerror("Uninstall Study Assistant", msg), btn.config(text="Close", state="normal", command=root.destroy)))

    def start():
        if choice.get():
            ask = (f"Remove Study Assistant AND delete all of your files in\n{data}?\n\nThe Library copies, grades, notes, settings and backups there are "
                   "deleted for good. Your original files in your own folders and OneDrive are not touched.")
        else:
            ask = "Remove Study Assistant from this computer?\nYour own files are kept."
        if messagebox.askyesno("Uninstall Study Assistant", ask, icon="warning" if choice.get() else "question", default="no" if choice.get() else "yes"):
            btn.config(state="disabled")
            threading.Thread(target=work, daemon=True).start()

    btn.config(command=start)
    root.protocol("WM_DELETE_WINDOW", close)
    root.mainloop()


def main():
    if "--uninstall" in sys.argv:
        main_uninstall()
        return
    if "--silent" in sys.argv:
        install(print, lambda f: None)
        return
    import tkinter as tk
    from tkinter import messagebox, ttk
    root = tk.Tk()
    root.title(f"Study Assistant {VERSION} Installer")
    root.geometry("580x400")
    program, data = targets()
    full = (here() / "payload" / "data").is_dir()
    tk.Label(root, text=f"Study Assistant {VERSION}", font=("Segoe UI", 16, "bold")).pack(pady=(14, 2))
    tk.Label(root, text=("This installs the program and brings all of your files along." if full
                         else "This installs a clean copy of the program, without any personal files."), wraplength=540).pack()
    tk.Label(root, text=f"Program folder:  {program}\nYour files:  {data if full else '(created empty on first run: ' + str(data) + ')'}",
             justify="left", fg="#444", wraplength=540).pack(pady=6)
    tk.Label(root, text="Existing folders are never overwritten: they are renamed first. Study Assistant will be listed under Settings > Apps, where it can be uninstalled.",
             fg="#444", wraplength=540).pack()
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
