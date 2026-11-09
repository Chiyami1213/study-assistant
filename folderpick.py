"""A folder chooser: the Windows "Browse For Folder" window, opened from the app (the app runs on this computer).

It runs in a separate PowerShell process, so it also works from the built exe (which has no tkinter of its own) and
cannot freeze the app's window handling. Choosing a folder only returns its path; nothing is created, changed or removed.
"""
import subprocess
import sys
from pathlib import Path

_SCRIPT = r"""
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Windows.Forms
$owner = New-Object System.Windows.Forms.Form
$owner.TopMost = $true
$owner.ShowInTaskbar = $false
$owner.StartPosition = 'CenterScreen'
$owner.Size = New-Object System.Drawing.Size(0, 0)
$owner.Opacity = 0
$owner.Show()
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = $env:SA_PICK_TITLE
$dialog.ShowNewFolderButton = $true
if ($env:SA_PICK_START -and (Test-Path -LiteralPath $env:SA_PICK_START -PathType Container)) { $dialog.SelectedPath = $env:SA_PICK_START }
if ($dialog.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK) { [Console]::Out.Write($dialog.SelectedPath) }
$owner.Close()
"""


def pick(start="", title="Choose a Folder"):
    """The folder the user chose, or None when the window was cancelled or cannot be opened (not Windows, no PowerShell)."""
    if sys.platform != "win32":
        return None
    import os
    start = (start or "").strip()
    try:                                                    # start in the folder typed so far, or its nearest existing parent
        p = Path(start) if start else None
        while p is not None and not p.is_dir() and p != p.parent:
            p = p.parent
        start = str(p) if p is not None and p.is_dir() else ""
    except OSError:
        start = ""
    env = dict(os.environ, SA_PICK_START=start, SA_PICK_TITLE=title)
    try:
        r = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-STA", "-WindowStyle", "Hidden", "-Command", _SCRIPT],
                           capture_output=True, env=env, timeout=600, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        return None
    chosen = r.stdout.decode("utf-8", errors="replace").strip().lstrip("﻿")
    return chosen or None
