"""Launch the app with:  python run.py

Opens Study Assistant in its own desktop window (no browser tab, no address bar). Server messages and errors
print in this terminal, and saving a file in VS Code reloads the app, so debugging works as before.

    python run.py --browser    the old way: Streamlit in your web browser
"""
import subprocess
import sys
from pathlib import Path

here = Path(__file__).parent
try:
    if "--browser" in sys.argv:
        args = [a for a in sys.argv[1:] if a != "--browser"]
        subprocess.run([sys.executable, "-m", "streamlit", "run", str(here / "app.py"), *args], check=False)
    else:
        subprocess.run([sys.executable, str(here / "launcher.py")], check=False)
except KeyboardInterrupt:
    pass
