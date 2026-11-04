"""Launch the app with:  python run.py"""
import subprocess
import sys
from pathlib import Path

app = Path(__file__).parent / "app.py"
try:
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(app), *sys.argv[1:]], check=False)
except KeyboardInterrupt:
    pass
