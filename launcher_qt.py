"""Launcher of the native (Qt) Study Assistant:

    python launcher_qt.py         the same as python run_qt.py
    StudyAssistantNative.exe      the same, packaged by tools/build_exe_qt.py

Like the classic launcher it bundles Python and the libraries only: the program's own folders (core, library, study, planner, views, qtui ...) are read from the project folder, so code edits and saved data
are shared. The pages that are not native yet are shown by the classic app, which runs as a hidden child process of this program (the same exe, started with --server).
"""
import importlib
import os
import sys


def _bundled_libraries():
    """Never called: it only lets the build see which Qt modules the native interface uses (qtui itself is read from the project folder, so the build cannot see its imports)."""
    from PySide6 import QtCore, QtGui, QtNetwork, QtPdf, QtPdfWidgets, QtWebChannel, QtWebEngineCore, QtWebEngineWidgets, QtWidgets  # noqa: F401


import launcher  # noqa: E402  (find_project, run_server, stop_server: the same server as the classic app)


def main():
    argv = sys.argv
    if len(argv) > 2 and argv[1] == "--server":
        launcher.run_server(int(argv[2]), int(argv[4]) if len(argv) > 4 and argv[3] == "--parent" else None)
        return
    if len(argv) > 2 and argv[1] == "--render":                       # page renderer for the scrolling PDF view
        sys.path.insert(0, str(launcher.find_project()))
        importlib.import_module("library.pagerender").main(argv[2:])
        return
    project = launcher.find_project()
    sys.path.insert(0, str(project))
    os.chdir(project)
    sys.exit(importlib.import_module("qtui.main").run())              # by name: PyInstaller must not bundle the program's own packages


if __name__ == "__main__":
    main()
