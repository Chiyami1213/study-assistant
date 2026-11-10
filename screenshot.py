"""F2: save a picture of the app window to <data folder>\\screenshots\\.

The window that has the focus when the key is pressed is the app's (the desktop window, or the browser tab it runs in); the picture is that window as it
looks on the screen, saved as a PNG named "Study Assistant <date> <time>.png". Windows only. Nothing else is read, and nothing is sent anywhere."""
import ctypes
import sys
from ctypes import wintypes
from datetime import datetime

from database import DATA_DIR

FOLDER = DATA_DIR / "screenshots"


def _window_rect():
    """(left, top, right, bottom) of the window that has the focus, in screen pixels; None when there is none."""
    try:
        ctypes.windll.user32.SetProcessDPIAware()                      # so the rectangle is in real pixels, the same as the picture
    except Exception:
        pass
    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    rect = wintypes.RECT()
    try:                                                                # the visible frame, without the invisible resize border of Windows 10 and 11
        ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(rect), ctypes.sizeof(rect))     # DWMWA_EXTENDED_FRAME_BOUNDS
    except Exception:
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
    if rect.right - rect.left < 50 or rect.bottom - rect.top < 50:
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect.left, rect.top, rect.right, rect.bottom


def take():
    """Save the picture and return its path. Raises RuntimeError with a short reason when it cannot be made."""
    if sys.platform != "win32":
        raise RuntimeError("Screenshots are only available on Windows.")
    box = _window_rect()
    if not box:
        raise RuntimeError("No window to take a picture of.")
    from PIL import ImageGrab
    image = ImageGrab.grab(bbox=box, all_screens=True)
    FOLDER.mkdir(parents=True, exist_ok=True)
    path = FOLDER / f"Study Assistant {datetime.now():%Y-%m-%d %H-%M-%S}.png"
    n = 1
    while path.exists():                                                # two in the same second
        n += 1
        path = FOLDER / f"Study Assistant {datetime.now():%Y-%m-%d %H-%M-%S} ({n}).png"
    image.save(path)
    return path
