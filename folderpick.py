"""Folder and file choosers: the Windows "Browse" windows, opened from the app (the app runs on this computer).

They run in a separate PowerShell process, so they also work from the built exe (which has no tkinter of its own) and
cannot freeze the app's window handling. Choosing only returns a path; nothing is created, changed or removed.
"""
import os
import subprocess
import sys
from pathlib import Path

_OWNER = r"""
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Windows.Forms
$owner = New-Object System.Windows.Forms.Form
$owner.TopMost = $true
$owner.ShowInTaskbar = $false
$owner.StartPosition = 'CenterScreen'
$owner.Size = New-Object System.Drawing.Size(0, 0)
$owner.Opacity = 0
$owner.Show()
"""

_SCRIPT = _OWNER + r"""
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = $env:SA_PICK_TITLE
$dialog.ShowNewFolderButton = $true
if ($env:SA_PICK_START -and (Test-Path -LiteralPath $env:SA_PICK_START -PathType Container)) { $dialog.SelectedPath = $env:SA_PICK_START }
if ($dialog.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK) { [Console]::Out.Write($dialog.SelectedPath) }
$owner.Close()
"""

_FILE_SCRIPT = _OWNER + r"""
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Title = $env:SA_PICK_TITLE
$dialog.Filter = $env:SA_PICK_FILTER
$dialog.CheckFileExists = $true
if ($env:SA_PICK_START -and (Test-Path -LiteralPath $env:SA_PICK_START -PathType Container)) { $dialog.InitialDirectory = $env:SA_PICK_START }
if ($dialog.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK) { [Console]::Out.Write($dialog.FileName) }
$owner.Close()
"""


def _start_folder(start):
    """The folder typed so far, or its nearest existing parent ('' when there is none)."""
    start = (start or "").strip()
    try:
        p = Path(start) if start else None
        while p is not None and not p.is_dir() and p != p.parent:
            p = p.parent
        return str(p) if p is not None and p.is_dir() else ""
    except OSError:
        return ""


def _run(script, start, title, filter=""):
    if sys.platform != "win32":
        return None
    env = dict(os.environ, SA_PICK_START=_start_folder(start), SA_PICK_TITLE=title, SA_PICK_FILTER=filter)
    try:
        r = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-STA", "-WindowStyle", "Hidden", "-Command", script],
                           capture_output=True, env=env, timeout=600, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.decode("utf-8", errors="replace").strip().lstrip("﻿") or None


def pick(start="", title="Choose a Folder"):
    """The folder the user chose, or None when the window was cancelled or cannot be opened (not Windows, no PowerShell)."""
    return _run(_SCRIPT, start, title)


def pick_file(start="", title="Choose a File", filter="Zip files (*.zip)|*.zip|All files (*.*)|*.*"):
    """The file the user chose, or None. `start` may be a file or folder path typed so far."""
    return _run(_FILE_SCRIPT, start, title, filter)
