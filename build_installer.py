"""Build the installer program:  python build_installer.py   ->   dist/installer/Install Study Assistant.exe

The installer (installer.py) is one small exe. build_release.py puts it next to a payload folder in the zip that people download."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
NAME = "Install Study Assistant"
OUT = ROOT / "dist" / "installer"


def exe_path():
    return OUT / f"{NAME}.exe"


def build():
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed", "--name", NAME,
           "--distpath", str(OUT), "--workpath", str(ROOT / "build" / "installer"), "--specpath", str(ROOT / "build" / "installer"),
           str(ROOT / "installer.py")]
    subprocess.run(cmd, check=True, cwd=ROOT)
    return exe_path()


if __name__ == "__main__":
    print("Built:", build())
