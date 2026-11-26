"""Launch the native (Qt) interface with:  python run_qt.py

The pages that are already native (Settings, the menu, Rest Now) are Qt; the others are still the classic interface, shown inside the window through a hidden local server.
    python run_qt.py --no-server    only the native parts (no classic pages), for a quick look
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from qtui.main import run

if __name__ == "__main__":
    sys.exit(run())
