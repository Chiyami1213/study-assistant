"""Build the native (Qt) desktop app:  python tools/build_exe_qt.py   ->   dist/StudyAssistantNative/StudyAssistantNative.exe

Like build_exe.py the exe bundles Python and the libraries only (and here Qt with its web engine, which is why it is much larger than the classic app): the program's own folders are read from the project
folder at run time. The classic pages that are not native yet run in the same exe, started as a hidden server (launcher_qt.py --server), so Streamlit is bundled too.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))                    # version.py
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_exe                                  # the lists of what the program imports at run time

NAME = "StudyAssistantNative"
# Qt modules the program does not use: they would add hundreds of megabytes (the Qt build of a developer machine has all of them).
EXCLUDE_QT = ["PySide6.Qt3DAnimation", "PySide6.Qt3DCore", "PySide6.Qt3DExtras", "PySide6.Qt3DInput", "PySide6.Qt3DLogic", "PySide6.Qt3DRender", "PySide6.QtCharts", "PySide6.QtDataVisualization",
              "PySide6.QtGraphs", "PySide6.QtGraphsWidgets", "PySide6.QtQuick3D", "PySide6.QtQuick3DRuntimeRender", "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets", "PySide6.QtBluetooth",
              "PySide6.QtNfc", "PySide6.QtPositioning", "PySide6.QtLocation", "PySide6.QtSensors", "PySide6.QtSerialPort", "PySide6.QtSerialBus", "PySide6.QtRemoteObjects", "PySide6.QtSql",
              "PySide6.QtTest", "PySide6.QtDesigner", "PySide6.QtHelp", "PySide6.QtScxml", "PySide6.QtSpatialAudio", "PySide6.QtStateMachine", "PySide6.QtTextToSpeech", "PySide6.QtVirtualKeyboard",
              "PySide6.QtWebSockets", "PySide6.QtWebView", "PySide6.QtHttpServer", "PySide6.QtPdfQuick", "PySide6.QtQuick", "PySide6.QtQuickControls2", "PySide6.QtQuickWidgets", "PySide6.QtQml",
              "PySide6.QtShaderTools",
              "PySide6.QtWebEngineQuick", "PySide6.QtNetworkAuth", "PySide6.QtUiTools"]


def main():
    icon = ROOT / "build" / "app.ico"
    icon.parent.mkdir(exist_ok=True)
    build_exe.make_icon(icon)
    import buildinfo
    version_file = buildinfo.write_version_file(ROOT / "build" / "version_info_qt.txt", "Study Assistant (native)", NAME)
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--windowed", "--noupx",
           "--name", NAME, "--icon", str(icon), "--version-file", str(version_file),
           "--collect-all", "streamlit", "--copy-metadata", "streamlit", "--collect-data", "tzdata",
           "--collect-all", "pymupdf", "--collect-all", "pillow_heif",
           "--collect-submodules", "pypdf", "--collect-submodules", "PIL"]
    for m in build_exe.STDLIB + build_exe.LIBS:
        cmd += ["--hidden-import", m]
    for m in [x for x in build_exe.EXCLUDE if x not in ("PySide6", "shiboken6")] + ["webview"] + EXCLUDE_QT:
        cmd += ["--exclude-module", m]
    cmd += ["--distpath", str(ROOT / "dist"), "--workpath", str(ROOT / "build" / "qt"), "--specpath", str(ROOT / "build" / "qt"), str(ROOT / "launcher_qt.py")]
    subprocess.run(cmd, check=True, cwd=ROOT)
    out = ROOT / "dist" / NAME
    (out / "project_path.txt").unlink(missing_ok=True)
    print("Built:", out / f"{NAME}.exe")
    import build_installer
    print("Built:", build_installer.build())


if __name__ == "__main__":
    main()
