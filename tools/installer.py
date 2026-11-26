"""Study Assistant installer. Built into "Install Study Assistant.exe" (see build_installer.py); it needs nothing else installed.

It sits next to a `payload` folder that holds
  payload\\program   the program (code, and the app's exe when it was included)   -> <Documents>\\study-assistant
  payload\\data      (only in a zip that carries files) your files and settings             -> %APPDATA%\\Study Assistant
It only COPIES from the payload. It looks for a Study Assistant that is already installed (the marker file in the program folder, or the installed-apps entry)
and asks what to do with it:
  Update    replace the installed program with this one (the old program folder is only removed after the new one is in place; your files are kept)
  Uninstall remove the old version first (program folder, Desktop shortcut, installed-apps entry; your files are kept), then install
  Keep both install this version into a folder of its own, with its own shortcut and installed-apps entry, and leave the old one alone. The two share
            one data folder and one address (port 8765), so the installer warns about that conflict before it goes ahead.
A folder that is not a Study Assistant install (a development copy, or something else) is never deleted: it is renamed to
"<name> (old <date and time>)" first. Your files (the data folder) are never replaced or deleted by an install. Nothing outside the program folder and the
data folder is touched, except a Study Assistant shortcut on the Desktop.

It also registers the program for the current user only (no administrator needed) in Windows' list of installed apps (Settings > Apps, Control
Panel > Programs), with an uninstaller: "Uninstall Study Assistant.exe" in the program folder (this same exe, run with --uninstall). The uninstaller
removes the program folder, the desktop shortcut and that registry entry. By default it KEEPS your files (the data folder); a tick box in its window
("also delete my files", off by default, asks again) or --remove-files makes it a clean uninstall that deletes the data folder too. It never follows a
link or junction, and refuses to touch a folder that was not made by this installer or that holds a git repository.

Command line (for tests): --silent runs without a window (--existing update|uninstall|both says what to do with an installed version, default update);
--uninstall uninstalls (with --silent: without a window; add --remove-files to delete the
data folder as well); the folders can be set with SA_INSTALL_PROGRAM_DIR and SA_INSTALL_DATA_DIR, and the registry entry's name with
SA_INSTALL_REG_KEY (a test install only registers when it is set)."""
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))     # the project folder (version.py) is one level up
from version import VERSION  # noqa: E402

APP_NAME = "Study Assistant"


def app_exe(program):
    """The exe of the installed program: the native app when this package has it, else the classic one."""
    native = program / "dist" / "StudyAssistantNative" / "StudyAssistantNative.exe"
    return native if native.exists() else program / "dist" / "StudyAssistant" / "StudyAssistant.exe"

UNINSTALL_NAME = "Uninstall Study Assistant.exe"
UNINSTALL_SCRIPT = "uninstall_study_assistant.py"                 # used instead of the exe when this runs from source
MARKER = ".study-assistant-install.json"                          # written into the program folder by the installer; the uninstaller needs it
REG_PARENT = r"Software\Microsoft\Windows\CurrentVersion\Uninstall"


def here():
    return Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent


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


def make_shortcuts(program, name="Study Assistant", places=("desktop", "start")):
    """Shortcuts to the app: "desktop" (an icon on the Desktop) and "start" (an entry in the Start menu). Returns the paths made. The real Desktop is
    asked from Windows (it can be inside OneDrive). A test install makes none unless SA_INSTALL_SHORTCUT_DIR names a scratch folder for them."""
    exe = app_exe(program)
    test_dir = os.environ.get("SA_INSTALL_SHORTCUT_DIR")
    if not exe.exists() or os.name != "nt" or (os.environ.get("SA_INSTALL_PROGRAM_DIR") and not test_dir):
        return []
    kinds = [{"desktop": "Desktop", "start": "Programs"}[p] for p in places if p in ("desktop", "start")]
    if not kinds:
        return []
    root = "'%s'" % str(test_dir).replace("'", "''") if test_dir else "$null"
    script = ("$sh=New-Object -ComObject WScript.Shell; $root=%s; $out=@(); foreach($k in @(%s)){ "
              "if($root){ $dir=Join-Path $root $k; New-Item -ItemType Directory -Force -Path $dir | Out-Null } else { $dir=[Environment]::GetFolderPath($k) }; "
              "$p=Join-Path $dir '%s.lnk'; $s=$sh.CreateShortcut($p); $s.TargetPath='%s'; $s.WorkingDirectory='%s'; $s.IconLocation='%s'; $s.Description='Study Assistant'; "
              "$s.Save(); $out+=$p }; $out -join '|'"
              % (root, ",".join("'%s'" % k for k in kinds), name.replace("'", "''"), str(exe).replace("'", "''"), str(exe.parent).replace("'", "''"), str(exe).replace("'", "''")))
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, check=True,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=90)
        return [Path(p) for p in out.stdout.strip().split("|") if p]
    except Exception:
        return []


def reg_key_name():
    return os.environ.get("SA_INSTALL_REG_KEY") or "StudyAssistant"


def wants_registry():
    """A test install (SA_INSTALL_PROGRAM_DIR set) leaves the registry alone unless a test key name is given."""
    return os.name == "nt" and (not os.environ.get("SA_INSTALL_PROGRAM_DIR") or bool(os.environ.get("SA_INSTALL_REG_KEY")))


def registered():
    """[(key name, DisplayVersion, InstallLocation)] of the Study Assistant entries in the current user's list of installed apps."""
    if not wants_registry():
        return []
    out = []
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PARENT) as parent:
            i = 0
            while True:
                try:
                    name = winreg.EnumKey(parent, i)
                except OSError:
                    break
                i += 1
                if name == reg_key_name() or name.startswith(reg_key_name() + "-"):
                    try:
                        with winreg.OpenKey(parent, name) as key:
                            out.append((name, winreg.QueryValueEx(key, "DisplayVersion")[0], winreg.QueryValueEx(key, "InstallLocation")[0]))
                    except OSError:
                        pass
    except OSError:
        pass
    return out


def register(program, data, size_bytes, key_name=None, display_name=APP_NAME):
    """Add the program to the current user's list of installed apps (HKCU, no administrator needed). Returns True when it worked."""
    if not wants_registry():
        return False
    try:
        import winreg
        exe = app_exe(program)
        if getattr(sys, "frozen", False):
            command = f'"{program / UNINSTALL_NAME}" --uninstall'
        else:
            command = f'"{Path(sys.executable).with_name("pythonw.exe")}" "{program / UNINSTALL_SCRIPT}" --uninstall'
        values = {"DisplayName": display_name, "DisplayVersion": VERSION, "Publisher": APP_NAME,
                  "InstallLocation": str(program), "InstallDate": datetime.now().strftime("%Y%m%d"),
                  "DisplayIcon": str(exe if exe.exists() else program / UNINSTALL_NAME), "UninstallString": command,
                  "QuietUninstallString": command + " --silent"}
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, REG_PARENT + "\\" + (key_name or reg_key_name()), 0, winreg.KEY_WRITE) as key:
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


def uninstall(log, progress, remove_files=False, program=None):
    """Remove the program folder, the desktop shortcut and the installed-apps entry. Your files (the data folder) are kept unless remove_files
    is set (a clean uninstall), in which case the data folder is deleted too. `program`: another install than the one this program sits in
    (the installer uses it to remove an older version first)."""
    program = program or here()
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
    links = [Path(p) for p in (info.get("shortcuts") or ([info["shortcut"]] if info.get("shortcut") else []))]
    for link in links:
        if link.exists() and shortcut_target(link).lower().startswith(str(program).lower()):         # only a shortcut that still points into this install
            link.unlink()
            log(f"The shortcut {link.name} was removed.")
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


def parse_version(text):
    return tuple(int(x) for x in re.findall(r"\d+", text or "")[:3])


def read_marker(folder):
    try:
        return json.loads((folder / MARKER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def find_existing(program):
    """The Study Assistant that is already installed, as this installer would meet it: {program, version, installed, reg_key, foreign}, or None.
    It is found by the marker in the program folder, or by an installed-apps entry that points to another folder. A non-empty program folder
    without a marker (a development copy, or something else) is reported with foreign=True: it is never removed, only renamed."""
    info = read_marker(program)
    if info:
        return {"program": program, "version": info.get("version"), "installed": info.get("installed"), "reg_key": info.get("reg_key"), "foreign": False}
    for key, version, location in registered():
        folder = Path(location) if location else None
        found = read_marker(folder) if folder and folder.is_dir() else None
        if found:
            return {"program": folder, "version": found.get("version") or version, "installed": found.get("installed"), "reg_key": key, "foreign": False}
    if program.is_dir() and any(program.iterdir()):
        return {"program": program, "version": None, "installed": None, "reg_key": None, "foreign": True}
    return None


def running_from(folder):
    """How many programs are running from `folder` (Study Assistant open: its files cannot be replaced or removed)."""
    if os.name != "nt" or not folder.exists():
        return 0
    script = "(Get-Process | Where-Object { $_.Path -and $_.Path.StartsWith('%s', [StringComparison]::OrdinalIgnoreCase) } | Measure-Object).Count" % str(folder).replace("'", "''")
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=60,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return int((out.stdout or "0").strip() or 0)
    except Exception:
        return 0


def sibling_for_both(program):
    """A program folder, a registry key and a shortcut name of their own for a second copy that stays next to the installed one."""
    n, base = 0, f"{program.name} {VERSION}"
    while True:
        folder = program.with_name(base + (f" ({n})" if n else ""))
        if not folder.exists():
            break
        n += 1
    suffix = f"-{VERSION}" + (f"-{n}" if n else "")
    label = f"{APP_NAME} {VERSION}" + (f" ({n})" if n else "")
    return folder, reg_key_name() + suffix, label


def remove_old_program(folder, log):
    """After an update: delete the old program folder that was set aside, never entering a link, and keeping any data folder inside it."""
    skipped = []
    try:
        remove_tree(folder, set(), skipped)
        folder.rmdir()
    except OSError:
        skipped.append(folder)
    if skipped:
        log(f"  the old program folder could not be removed completely and was left as {folder.name}")
    return not skipped


def install(log, progress, mode="update", places=("desktop", "start")):
    """Install the payload. `mode` says what to do with a Study Assistant that is already installed: "update" (replace it), "uninstall" (remove it
    first) or "both" (install next to it, in a folder of its own). Without an installed version it makes no difference. `places`: which shortcuts to make."""
    payload = here() / "payload"
    program_src, data_src = payload / "program", payload / "data"
    if not (program_src / "app.py").exists():
        raise RuntimeError(f"The package is incomplete: {program_src} is missing. Extract the whole zip first, then run this again from the extracted folder.")
    program, data = targets()
    existing = find_existing(program)
    key_name, display_name, link_name, drop_old = None, APP_NAME, "Study Assistant", None
    if existing:
        old = existing["program"]
        log(f"Found Study Assistant {existing['version'] or '(unknown version)'} in {old}" + (" (not made by this installer)" if existing["foreign"] else "") + ".")
        if mode == "both":
            program, key_name, display_name = sibling_for_both(old if not existing["foreign"] else program)
            link_name = display_name
            log(f"Keeping both: the new version goes to {program}. Both use the same data folder and port 8765: open one at a time.")
        else:
            if running_from(old):
                raise RuntimeError(f"Study Assistant is open (it runs from {old}). Close it, then run the installer again.")
            if mode == "uninstall" and not existing["foreign"]:
                log("Uninstalling the older version first (your files are kept):")
                _, _, clean = uninstall(lambda m: log("  " + m), lambda f: None, False, old)
                if not clean:
                    raise RuntimeError("The older version could not be removed completely (a file is in use?). Close Study Assistant and run the installer again.")
                try:
                    old.rmdir()
                except OSError:
                    pass
            elif mode == "update" and not existing["foreign"]:
                program = old                                    # replaced in the same place
                drop_old = set_aside(program)                    # moved out of the way; deleted only once the new copy is in
                log(f"Updating the installed version in {program}.")
            elif existing["foreign"]:
                log("That folder was not made by this installer, so it is kept (renamed) and not removed.")
    full = data_src.is_dir()
    steps = 2 if full else 1
    state = {"n": 0}

    def part(p):
        progress((state["n"] + p) / steps)

    log(f"Installing the program to {program}")
    old = set_aside(program)
    if old:
        log(f"  the folder that was there was kept as: {old.name}")
    try:
        log(f"  {copy_tree(program_src, program, part)} files copied")
    except Exception:
        if drop_old and not program.exists():                     # the update failed half way: put the old version back
            try:
                drop_old.rename(program)
            except OSError:
                pass
        raise
    state["n"] = 1
    if drop_old:
        log("  the older program was replaced." if remove_old_program(drop_old, log) else "")
    if full:
        log(f"Restoring your files to {data}")
        old = set_aside(data)
        if old:
            log(f"  the folder that was there was kept as: {old.name}")
        log(f"  {copy_tree(data_src, data, part)} files copied")
        state["n"] = 2
    else:
        log("This is a clean install: no personal files are brought along. The app makes its own empty data folder the first time it runs.")
    made = make_shortcuts(program, link_name, places)
    if made:
        log("Shortcuts: " + ", ".join(("on the Desktop" if "Programs" not in str(p) and "Start Menu" not in str(p) and p.parent.name != "Programs" else "in the Start menu") for p in made) + ".")
    else:
        log("No shortcut was made. Start it with: python run.py (in the program folder, after pip install -r requirements.txt)." if not places
            else "No shortcut was made (a test install, or Windows would not allow it).")
    try:                                                    # what the uninstaller needs: this program, and a marker that this folder is ours
        if getattr(sys, "frozen", False):
            shutil.copyfile(sys.executable, program / UNINSTALL_NAME)
        else:
            shutil.copyfile(Path(__file__), program / UNINSTALL_SCRIPT)
        size = sum(p.stat().st_size for p in program.rglob("*") if p.is_file())
        (program / MARKER).write_text(json.dumps({"version": VERSION, "installed": datetime.now().isoformat(timespec="seconds"), "program": str(program), "data": str(data),
                                                  "shortcuts": [str(p) for p in made],
                                                  "reg_key": key_name or reg_key_name()}, indent=1), encoding="utf-8")
        log("It can be uninstalled from Settings > Apps > Installed apps (" + display_name + ")." if register(program, data, size, key_name, display_name)
            else "It could not be added to the list of installed apps, so there is no uninstaller entry.")
    except OSError as e:
        log(f"The uninstaller could not be set up: {e}")
    progress(1.0)
    log("Done. You can close this window and open Study Assistant. The extracted package folder is no longer needed.")
    return program


# ---------------------------------------------------------------- the wizard windows (installer and uninstaller)
BLUE, BLUE_DARK, GREY, GREY_DARK = "#2f6db5", "#24558f", "#e3e6ea", "#cdd1d7"
FONT = "Segoe UI"


def enable_hidpi():
    """Tell Windows this program draws itself at the real resolution (without it Windows stretches the window and the text is blurry)."""
    if os.name != "nt":
        return
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)               # per monitor
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


class Wizard:
    """A setup window in the usual shape: a picture panel on the left, the page on the right, Back / Next / Cancel underneath. `pages` is a list of
    dicts: title, build(wiz, frame), optional show_if(wiz), on_show(wiz), on_next(wiz) -> bool, next (button text), back, cancel (False hides or disables them)."""

    def __init__(self, window_title, product, pages):
        enable_hidpi()
        import tkinter as tk
        from tkinter import messagebox
        self.tk, self.messagebox = tk, messagebox
        self.root = root = tk.Tk()
        root.title(window_title)
        dpi = root.winfo_fpixels("1i")
        root.tk.call("tk", "scaling", dpi / 72.0)                         # points follow the screen's real resolution
        self.S = dpi / 96.0
        self.pages, self.product, self.vars, self.index, self.frame = pages, product, {}, -1, None
        self.busy = False
        width, height = self.px(760), self.px(520)
        root.geometry(f"{width}x{height}+{(root.winfo_screenwidth() - width) // 2}+{(root.winfo_screenheight() - height) // 3}")
        root.resizable(False, False)
        root.configure(bg="white")
        self.banner = tk.Canvas(root, width=self.px(220), height=height, highlightthickness=0, bd=0)
        self.banner.place(x=0, y=0)
        self.draw_banner(self.px(220), height)
        right = tk.Frame(root, bg="white")
        right.place(x=self.px(220), y=0, width=width - self.px(220), height=height)
        self.body = tk.Frame(right, bg="white")
        self.body.place(x=self.px(34), y=self.px(30), width=width - self.px(220) - self.px(68), height=height - self.px(30) - self.px(92))
        tk.Frame(right, bg=GREY_DARK).place(x=0, y=height - self.px(76), width=width, height=1)
        self.back_btn = self.button(right, "< Back", lambda: self.go(-1), primary=False)
        self.next_btn = self.button(right, "Next >", self.next, primary=True)
        self.cancel_btn = self.button(right, "Cancel", self.cancel, primary=False)
        right_w = width - self.px(220)
        for btn, x in ((self.cancel_btn, right_w - self.px(34) - self.px(104)), (self.next_btn, right_w - self.px(34) - self.px(104) * 2 - self.px(12)),
                       (self.back_btn, right_w - self.px(34) - self.px(104) * 3 - self.px(24))):
            btn.place(x=x, y=height - self.px(56), width=self.px(104), height=self.px(36))
        root.protocol("WM_DELETE_WINDOW", self.cancel)

    # -- drawing helpers
    def px(self, n):
        return int(round(n * self.S))

    def checkbox(self, parent, text, variable, bold=False, size=10):
        """A check box that is easy to see on any screen: a square about 24 pixels at the screen's real resolution (the one of Tk is a few pixels), a dark outline, a blue fill with a white tick
        when it is on. A click on the square or on the words changes it."""
        tk = self.tk
        box = max(24, self.px(24))
        row = tk.Frame(parent, bg="white", cursor="hand2")
        canvas = tk.Canvas(row, width=box, height=box, bg="white", highlightthickness=0, cursor="hand2")
        canvas.pack(side="left", padx=(0, self.px(10)))
        label = tk.Label(row, text=text, font=self.font(size, bold), bg="white", anchor="w", cursor="hand2")
        label.pack(side="left", fill="x")

        def draw(*_):
            canvas.delete("all")
            on = bool(variable.get())
            canvas.create_rectangle(2, 2, box - 2, box - 2, outline="#1f2937" if on else "#4b5563", width=max(2, self.px(2)), fill="#2563eb" if on else "white")
            if on:
                w = max(3, self.px(3))
                canvas.create_line(box * 0.24, box * 0.52, box * 0.43, box * 0.72, box * 0.78, box * 0.28, fill="white", width=w, capstyle="round", joinstyle="round")

        def toggle(_event=None):
            variable.set(not variable.get())

        for widget in (canvas, label, row):
            widget.bind("<Button-1>", toggle)
        variable.trace_add("write", draw)
        draw()
        return row

    def font(self, size, bold=False):
        return (FONT, size, "bold") if bold else (FONT, size)

    def button(self, parent, text, command, primary):
        tk = self.tk
        fg, bg, hover = ("white", BLUE, BLUE_DARK) if primary else ("#1f2328", GREY, GREY_DARK)
        b = tk.Button(parent, text=text, command=command, relief="flat", bd=0, font=self.font(10), fg=fg, bg=bg, activeforeground=fg, activebackground=hover,
                      disabledforeground="#9aa0a6", cursor="hand2", takefocus=1)
        b._colors = (bg, hover)
        b.bind("<Enter>", lambda e: b.config(bg=b._colors[1]) if str(b["state"]) == "normal" else None)
        b.bind("<Leave>", lambda e: b.config(bg=b._colors[0] if str(b["state"]) == "normal" else GREY))
        return b

    def draw_banner(self, w, h):
        c = self.banner
        top, bottom = (58, 86, 160), (16, 26, 63)
        for y in range(h):                                              # a vertical blend, one line per pixel row
            k = y / max(1, h - 1)
            c.create_line(0, y, w, y, fill="#%02x%02x%02x" % tuple(int(top[i] + (bottom[i] - top[i]) * k) for i in range(3)))
        for r, shade in ((260, "#2c4585"), (200, "#26407f"), (140, "#203876")):      # soft rings behind the lower part
            rr = self.px(r)
            c.create_oval(w // 2 - rr, h - self.px(40) - rr, w // 2 + rr, h - self.px(40) + rr, outline=shade, width=self.px(2))
        size = self.px(92)
        x0, y0 = (w - size) // 2, self.px(52)
        k = size / 256.0
        pt = lambda x, y: (x0 + x * k, y0 + y * k)
        c.create_polygon(*pt(8, 8), *pt(248, 8), *pt(248, 248), *pt(8, 248), fill="#0e1117", outline="#ff4b4b", width=max(2, self.px(3)))   # the app's icon
        c.create_polygon(*pt(128, 60), *pt(222, 108), *pt(128, 156), *pt(34, 108), fill="white", outline="")
        c.create_polygon(*pt(70, 136), *pt(70, 176), *pt(128, 200), *pt(186, 176), *pt(186, 136), *pt(128, 162), fill="#dce0e8", outline="")
        c.create_text(w // 2, y0 + size + self.px(34), text=self.product, fill="white", font=self.font(16, True))
        c.create_text(w // 2, y0 + size + self.px(62), text=f"Version {VERSION}", fill="#b9c4e4", font=self.font(10))

    def label(self, parent, text, size=10, bold=False, color="#1f2328", wrap=None, pady=(0, 0), anchor="w"):
        lab = self.tk.Label(parent, text=text, font=self.font(size, bold), fg=color, bg="white", justify="left", anchor=anchor,
                            wraplength=wrap or self.px(440))
        lab.pack(fill="x", pady=tuple(self.px(p) for p in pady))
        return lab

    # -- flow
    def visible(self, i):
        page = self.pages[i]
        return page.get("show_if", lambda w: True)(self)

    def show(self, i):
        self.index = i
        page = self.pages[i]
        if self.frame:
            self.frame.destroy()
        self.frame = self.tk.Frame(self.body, bg="white")
        self.frame.pack(fill="both", expand=True)
        self.label(self.frame, page["title"], size=15, bold=True, pady=(0, 12), wrap=self.px(450))
        page["build"](self, self.frame)
        first = not any(self.visible(j) for j in range(i))
        self.set_buttons(back=page.get("back", True) and not first, next_text=page.get("next", "Next >"), next_on=True, cancel=page.get("cancel", True))
        if page.get("on_show"):
            page["on_show"](self)

    def set_buttons(self, back=True, next_text="Next >", next_on=True, cancel=True):
        for b, on in ((self.back_btn, back), (self.next_btn, next_on), (self.cancel_btn, cancel)):
            b.config(state="normal" if on else "disabled", bg=b._colors[0] if on else GREY)
        self.next_btn.config(text=next_text)
        if not next_on:
            self.next_btn.config(bg=GREY)

    def go(self, step):
        i = self.index + step
        while 0 <= i < len(self.pages) and not self.visible(i):
            i += step
        if 0 <= i < len(self.pages):
            self.show(i)

    def next(self):
        page = self.pages[self.index]
        if page.get("on_next") and not page["on_next"](self):
            return
        if self.index >= len(self.pages) - 1:
            self.root.destroy()
        else:
            self.go(1)

    def cancel(self):
        if self.busy:
            return
        last = self.index >= len(self.pages) - 1
        if last or self.messagebox.askyesno(self.root.title(), "Do you want to exit the setup now?", icon="question"):
            if last and self.pages[-1].get("on_close"):
                self.pages[-1]["on_close"](self)
            self.root.destroy()

    def run(self):
        self.go(1) if self.index < 0 and not self.visible(0) else self.show(max(self.index, 0))
        self.root.mainloop()

    # -- widgets used by several pages
    def progress_widgets(self, frame):
        tk = self.tk
        from tkinter import ttk
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("Setup.Horizontal.TProgressbar", troughcolor=GREY, background=BLUE, bordercolor=GREY, lightcolor=BLUE, darkcolor=BLUE, thickness=self.px(14))
        self.status = self.label(frame, "Preparing...", size=10, color="#444", pady=(8, 6))
        row = tk.Frame(frame, bg="white")
        row.pack(fill="x")
        self.bar = ttk.Progressbar(row, style="Setup.Horizontal.TProgressbar", orient="horizontal", mode="determinate", maximum=100)
        self.bar.pack(side="left", fill="x", expand=True)
        self.percent = tk.Label(row, text="0%", width=5, font=self.font(10, True), bg="white", fg=BLUE, anchor="e")
        self.percent.pack(side="left", padx=(self.px(8), 0))
        self.log_box = tk.Text(frame, height=9, font=("Consolas", 9), bg="#f6f7f9", fg="#333", relief="flat", bd=0, padx=self.px(8), pady=self.px(6), state="disabled",
                               wrap="word", highlightthickness=1, highlightbackground=GREY_DARK)
        self.log_box.pack(fill="both", expand=True, pady=(self.px(12), 0))

    def log(self, msg):
        def put():
            self.log_box.config(state="normal")
            self.log_box.insert("end", msg + "\n")
            self.log_box.see("end")
            self.log_box.config(state="disabled")
            if msg.strip():
                self.status.config(text=msg.strip()[:90])
        self.root.after(0, put)

    def set_progress(self, fraction):
        def put():
            value = max(0, min(100, fraction * 100))
            self.bar.config(value=value)
            self.percent.config(text=f"{int(value)}%")
        self.root.after(0, put)

    def radio(self, frame, variable, value, title, detail, color="#1f2328"):
        tk = self.tk
        tk.Radiobutton(frame, text=title, variable=variable, value=value, font=self.font(10, True), bg="white", fg=color, activebackground="white", selectcolor="white",
                       anchor="w", justify="left", wraplength=self.px(430), cursor="hand2").pack(fill="x", pady=(self.px(8), 0))
        if detail:
            lab = tk.Label(frame, text=detail, font=self.font(9), fg="#555", bg="white", justify="left", anchor="w", wraplength=self.px(410))
            lab.pack(fill="x", padx=(self.px(26), 0))


# -- the installer
REPO_URL = "https://github.com/Chiyami1213/study-assistant"
HELP_URL = REPO_URL + "/blob/main/docs/HELP.md"
ISSUES_URL = REPO_URL + "/issues/new/choose"


def link_label(wiz, frame, text, url):
    """A blue, underlined line that opens a web address in the browser."""
    import webbrowser
    lab = wiz.tk.Label(frame, text=text, font=(FONT, 10, "underline"), fg=BLUE, bg="white", cursor="hand2", anchor="w")
    lab.pack(fill="x", pady=(wiz.px(2), 0))
    lab.bind("<Button-1>", lambda e: webbrowser.open(url))
    lab.bind("<Enter>", lambda e: lab.config(fg=BLUE_DARK))
    lab.bind("<Leave>", lambda e: lab.config(fg=BLUE))
    return lab


AV_TITLE = "If your antivirus blocks this setup"
AV_TEXT = ("Windows SmartScreen or an antivirus program may warn about, or block, this installer, because it is a new program that few people have run yet. "
           "Study Assistant does not contain a virus, and its full source code is public on GitHub. If you see a warning, choose \"More info\" and then \"Run anyway\", "
           "or allow the file in your antivirus and run the setup again.")


def notice(wiz, frame, title=AV_TITLE, text=AV_TEXT):
    """A pale yellow box with a heads-up."""
    tk = wiz.tk
    box = tk.Frame(frame, bg="#fff6dd", highlightthickness=1, highlightbackground="#e6cf8f")
    box.pack(fill="x", pady=(wiz.px(12), 0))
    tk.Label(box, text=title, font=wiz.font(9, True), bg="#fff6dd", fg="#6b4b00", anchor="w", justify="left").pack(fill="x", padx=wiz.px(10), pady=(wiz.px(7), 0))
    tk.Label(box, text=text, font=wiz.font(9), bg="#fff6dd", fg="#4a3a10", anchor="w", justify="left", wraplength=wiz.px(410)).pack(fill="x", padx=wiz.px(10), pady=(0, wiz.px(8)))


def help_links(wiz, frame, intro="More information and help"):
    wiz.label(frame, intro, size=10, bold=True, pady=(18, 2))
    link_label(wiz, frame, "Study Assistant on GitHub: " + REPO_URL.replace("https://", ""), REPO_URL)
    link_label(wiz, frame, "Help: installing, updating, your files, backups, shortcuts, common problems", HELP_URL)
    link_label(wiz, frame, "Report a problem or ask a question", ISSUES_URL)


def build_install_wizard():
    program, data = targets()
    full = (here() / "payload" / "data").is_dir()
    existing = find_existing(program)
    state = {"ok": False, "error": "", "program": None}
    idx = {}

    def mode_of(wiz):
        return wiz.vars["mode"].get() if "mode" in wiz.vars else "update"

    def places_of(wiz):
        if "desktop" not in wiz.vars:
            return ("desktop", "start")
        return tuple(k for k in ("desktop", "start") if wiz.vars[k].get())

    def welcome(wiz, f):
        wiz.label(f, f"This wizard will guide you through the installation of Study Assistant {VERSION}.", size=10, pady=(0, 8))
        wiz.label(f, "Please close Study Assistant and other programs before you continue.", size=10, pady=(0, 8))
        wiz.label(f, "This installs the program and brings all of your files along." if full else
                  "This installs a clean copy of the program. Your own files (the Library, notes, grades, settings) are not touched.",
                  size=10, pady=(0, 4))
        notice(wiz, f)
        wiz.label(f, "Click Next to continue.", size=10, color="#555", pady=(14, 0))

    def existing_page(wiz, f):
        tk = wiz.tk
        wiz.vars.setdefault("mode", tk.StringVar(value="update"))
        old, version = existing["program"], existing["version"]
        if existing["foreign"]:
            wiz.label(f, f"The folder {old} already has something in it that this installer did not make (for example a development copy). It will not be deleted: "
                         "it is renamed first.", size=10, pady=(0, 6))
            wiz.radio(f, wiz.vars["mode"], "update", "Rename it and install here", "The folder is kept as 'study-assistant (old <date and time>)'.")
            wiz.radio(f, wiz.vars["mode"], "both", "Keep it and install next to it", "The new version goes to a folder of its own. You will be warned about the conflicts.", color="#8a4b00")
            return
        newer = bool(version) and parse_version(version) > parse_version(VERSION)
        same = bool(version) and parse_version(version) == parse_version(VERSION)
        wiz.label(f, f"Study Assistant {version or '(unknown version)'} is installed in\n{old}", size=10, pady=(0, 4))
        if newer:
            wiz.label(f, f"The installed version is NEWER than this one ({VERSION}). Updating would replace it with an older version.", size=10, color="#b00020", pady=(0, 2))
        elif same:
            wiz.label(f, "That is the same version as this installer.", size=10, color="#555", pady=(0, 2))
        wiz.label(f, "What do you want to do?", size=10, bold=True, pady=(6, 0))
        wiz.radio(f, wiz.vars["mode"], "update", "Update (overwrite) the installed version" + ("" if newer else " (recommended)"),
                  "Replaces the installed program with this one. Your files are kept.")
        wiz.radio(f, wiz.vars["mode"], "uninstall", "Uninstall the older version first, then install",
                  "Removes the old program, its shortcuts and its entry in Settings > Apps. Your files are kept.")
        wiz.radio(f, wiz.vars["mode"], "both", "Keep both versions",
                  "Installs this version in a folder of its own and leaves the old one alone. The two share one data folder: you will be warned.", color="#8a4b00")

    def existing_next(wiz):
        mode = mode_of(wiz)
        if mode == "both":
            return wiz.messagebox.askokcancel(
                "Keep both versions",
                "Both versions would share the same data folder:\n  " + str(data) + "\nand the same address (port 8765).\n\n"
                "- A newer version may change the database so the older one can no longer open it. Make a backup first (Settings > Backup).\n"
                "- If one version is open and you start the other, the second window shows the program of the first one.\n\n"
                "Open only one version at a time. Keep both anyway?", icon="warning")
        if mode == "update" and not existing["foreign"] and existing["version"] and parse_version(existing["version"]) > parse_version(VERSION):
            return wiz.messagebox.askokcancel("Replace a newer version", f"Study Assistant {existing['version']} is installed and is newer than {VERSION}. "
                                              "Replace it with the older version?", icon="warning")
        return True

    def shortcuts_page(wiz, f):
        tk = wiz.tk
        wiz.vars.setdefault("desktop", tk.BooleanVar(value=True))
        wiz.vars.setdefault("start", tk.BooleanVar(value=True))
        wiz.label(f, "Choose where Study Assistant gets a shortcut, so you can open it with one click.", size=10, pady=(0, 6))
        for key, text, detail in (("desktop", "Create a Desktop shortcut", "An icon on your Desktop."),
                                  ("start", "Add Study Assistant to the Start menu", "Found by typing its name after pressing the Windows key.")):
            wiz.checkbox(f, text, wiz.vars[key], bold=True).pack(fill="x", pady=(wiz.px(12), 0))
            wiz.label(f, detail, size=9, color="#555").pack_configure(padx=(wiz.px(36), 0))
        wiz.label(f, "Study Assistant is also listed in Settings > Apps, where it can be uninstalled.", size=9, color="#555", pady=(24, 0))

    def ready(wiz, f):
        mode = mode_of(wiz)
        wiz.label(f, "Setup is ready to install Study Assistant on your computer.", size=10, pady=(0, 4))
        target = str(existing["program"]) if existing and mode == "update" and not existing["foreign"] else str(program)
        places = places_of(wiz)
        rows = [("Program folder", target if mode != "both" else "a new folder next to the installed one"),
                ("Your files", str(data) if full else f"{data} (created empty the first time the app runs)")]
        if existing:
            rows.append(("Installed version", {"update": "replaced by this one", "uninstall": "removed first, then this one is installed", "both": "kept as it is"}[mode]))
        rows.append(("Shortcuts", ", ".join(n for k, n in (("desktop", "Desktop"), ("start", "Start menu")) if k in places) or "none"))
        for name, value in rows:
            wiz.label(f, name, size=9, color="#666", pady=(5, 0))
            wiz.label(f, value, size=10)
        wiz.label(f, "Click Install to continue.", size=10, color="#555", pady=(14, 0))

    def installing(wiz, f):
        wiz.progress_widgets(f)

    def start_install(wiz):
        wiz.show(idx["installing"])
        wiz.busy = True
        wiz.set_buttons(back=False, next_text="Next >", next_on=False, cancel=False)
        mode, places = mode_of(wiz), places_of(wiz)

        def work():
            try:
                state["program"] = install(wiz.log, wiz.set_progress, mode, places)
                state["ok"] = True
            except Exception as e:
                state["error"] = str(e)
                wiz.log(f"Stopped: {e}")
            wiz.busy = False
            wiz.root.after(400, lambda: wiz.show(idx["finish"]))

        threading.Thread(target=work, daemon=True).start()

    def finish(wiz, f):
        tk = wiz.tk
        if state["ok"]:
            wiz.label(f, f"Study Assistant {VERSION} has been installed.", size=10, pady=(0, 6))
            wiz.label(f, "Start it from its shortcut. The extracted package folder is no longer needed.", size=10, pady=(0, 8))
            exe = app_exe(state["program"] or program)
            wiz.vars["exe"] = exe
            wiz.vars["open"] = tk.BooleanVar(value=exe.exists() and not os.environ.get("SA_INSTALL_PROGRAM_DIR"))
            if exe.exists():
                wiz.checkbox(f, "Open Study Assistant now", wiz.vars["open"]).pack(fill="x")
        else:
            wiz.label(f, "Setup did not finish.", size=10, bold=True, color="#b00020", pady=(0, 6))
            wiz.label(f, state["error"] or "Something went wrong.", size=10, pady=(0, 6))
            wiz.label(f, "Nothing of your own was changed. Close Study Assistant if it is open, then run the installer again.", size=10, color="#555")
            notice(wiz, f, "Was it your antivirus?", "If an antivirus program removed or blocked a file, Study Assistant is not harmful (its source code is public on GitHub). "
                   "Allow it in your antivirus, extract the zip again if a file is missing, and run the setup again.")
        help_links(wiz, f, "Need help, or want to know more?")

    def finish_close(wiz):
        var = wiz.vars.get("open")
        if state["ok"] and var is not None and var.get():
            try:
                subprocess.Popen([str(wiz.vars["exe"])], cwd=str(wiz.vars["exe"].parent), creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
            except OSError:
                pass

    pages = [
        {"name": "welcome", "title": "Welcome to the Study Assistant Setup Wizard", "build": welcome},
        {"name": "existing", "title": "Study Assistant Is Already Installed", "build": existing_page, "on_next": existing_next, "show_if": lambda w: bool(existing)},
        {"name": "shortcuts", "title": "Shortcuts", "build": shortcuts_page},
        {"name": "ready", "title": "Ready to Install", "build": ready, "next": "Install", "on_next": lambda w: (start_install(w), False)[1]},
        {"name": "installing", "title": "Installing", "build": installing, "back": False, "cancel": False, "show_if": lambda w: False},
        {"name": "finish", "title": "Setup Complete", "build": finish, "back": False, "cancel": False, "next": "Finish", "show_if": lambda w: False,
         "on_next": lambda w: (finish_close(w), True)[1], "on_close": finish_close,
         "on_show": lambda w: w.set_buttons(back=False, next_text="Finish", next_on=True, cancel=False)},
    ]
    idx.update({p["name"]: i for i, p in enumerate(pages)})
    wiz = Wizard(f"Study Assistant {VERSION} Setup", APP_NAME, pages)
    wiz.state = state
    return wiz


# -- the uninstaller
def build_uninstall_wizard():
    own_dir = here()
    try:
        info = json.loads((own_dir / MARKER).read_text(encoding="utf-8"))
        data = Path(info.get("data") or targets()[1])
    except (OSError, ValueError):
        data = targets()[1]
    state = {"done": None, "error": ""}

    def welcome(wiz, f):
        wiz.label(f, f"This wizard will remove Study Assistant {VERSION} from your computer.", size=10, pady=(0, 10))
        wiz.label(f, f"It removes the program from\\n{own_dir}\\nthe Desktop shortcut and the entry in Settings > Apps.", size=10, pady=(0, 10))
        wiz.label(f, "It is recommended that you close Study Assistant first.", size=10, pady=(0, 10))
        wiz.label(f, "Click Next to continue.", size=10, color="#555", pady=(24, 0))

    def files(wiz, f):
        tk = wiz.tk
        wiz.vars.setdefault("remove", tk.IntVar(value=0))
        wiz.label(f, f"Your files are in\\n{data}\\nWhat should happen to them?", size=10, pady=(0, 6))
        wiz.radio(f, wiz.vars["remove"], 0, "Keep my files (recommended)", "The Library, notes, grades, settings and backups stay on this computer.")
        wiz.radio(f, wiz.vars["remove"], 1, "Remove everything, including my files", "A clean uninstall: your files in the data folder are deleted for good. Your original files in your own folders and OneDrive are not touched.", color="#b00020")

    def files_next(wiz):
        if wiz.vars["remove"].get():
            ok = wiz.messagebox.askyesno("Uninstall Study Assistant", f"Remove Study Assistant AND delete all of your files in\\n{data}?\\n\\nThe Library copies, grades, notes, settings and backups there are deleted for good.",
                                         icon="warning", default="no")
        else:
            ok = True
        if ok:
            start_removal(wiz)
        return False

    def running(wiz, f):
        wiz.progress_widgets(f)

    def start_removal(wiz):
        wiz.show(2)
        wiz.busy = True
        wiz.set_buttons(back=False, next_text="Next >", next_on=False, cancel=False)
        remove_files = bool(wiz.vars["remove"].get())

        def work():
            try:
                state["done"] = uninstall(wiz.log, wiz.set_progress, remove_files)
            except Exception as e:
                state["error"] = str(e)
                wiz.log(f"Stopped: {e}")
            wiz.busy = False
            wiz.root.after(400, lambda: wiz.show(3))

        threading.Thread(target=work, daemon=True).start()

    def finish(wiz, f):
        if state["done"]:
            wiz.label(f, "Study Assistant has been removed from your computer.", size=10, pady=(0, 8))
            wiz.label(f, "Your files were deleted." if wiz.vars["remove"].get() else f"Your files in {data} were kept. Delete that folder yourself if you no longer want them.", size=10, color="#555")
            link_label(wiz, f, "Study Assistant on GitHub: " + REPO_URL.replace("https://", ""), REPO_URL)
            if not state["done"][2]:
                wiz.label(f, "Some items could not be removed (a file in use?). Close Study Assistant and run the uninstaller again.", size=10, color="#b00020", pady=(8, 0))
        else:
            wiz.label(f, "The uninstall did not finish.", size=10, bold=True, color="#b00020", pady=(0, 8))
            wiz.label(f, state["error"] or "Something went wrong.", size=10)

    def close(wiz):
        if state["done"]:
            finish_removal(*state["done"])

    pages = [
        {"title": "Uninstall Study Assistant", "build": welcome},
        {"title": "Your Files", "build": files, "on_next": files_next},
        {"title": "Uninstalling", "build": running, "back": False, "cancel": False, "show_if": lambda w: False},
        {"title": "Uninstall Complete", "build": finish, "back": False, "cancel": False, "next": "Finish", "on_close": close,
         "on_show": lambda w: w.set_buttons(back=False, next_text="Finish", next_on=True, cancel=False)},
    ]
    pages[3]["on_next"] = lambda w: (close(w), True)[1]
    return Wizard(f"Uninstall Study Assistant {VERSION}", APP_NAME, pages)


def main():
    if "--uninstall" in sys.argv:
        if "--silent" in sys.argv:
            finish_removal(*uninstall(print, lambda f: None, "--remove-files" in sys.argv))
        else:
            build_uninstall_wizard().run()
        return
    if "--silent" in sys.argv:
        mode = sys.argv[sys.argv.index("--existing") + 1] if "--existing" in sys.argv and sys.argv.index("--existing") + 1 < len(sys.argv) else "update"
        places = tuple(k for k, flag in (("desktop", "--no-desktop-shortcut"), ("start", "--no-start-menu")) if flag not in sys.argv)
        install(print, lambda f: None, mode, places)
        return
    build_install_wizard().run()


if __name__ == "__main__":
    main()
