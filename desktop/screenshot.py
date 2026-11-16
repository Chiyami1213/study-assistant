"""F2: save a picture of the app window to <data folder>\\screenshots\\.

The window that has the focus when the key is pressed is the app's (the desktop window, or the browser tab it runs in); the picture is that window as it
looks on the screen, saved as a PNG named "Study Assistant <date> <time>.png". On Windows the window is found with the Windows API; on a Mac the macOS
`screencapture` tool takes the picture (the first time, macOS asks for permission under Privacy & Security > Screen Recording; without it the picture shows only the
desktop). Nothing else is read, and nothing is sent anywhere."""
import subprocess
import sys
from datetime import datetime

from core.database import DATA_DIR

FOLDER = DATA_DIR / "screenshots"


def _window_rect():
    """(left, top, right, bottom) of the window that has the focus, in screen pixels; None when there is none."""
    import ctypes
    from ctypes import wintypes
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


def _mac_window_box():
    """(x, y, width, height) in points of the front window of the program in front, or None (pyobjc missing, or no window)."""
    try:
        from AppKit import NSWorkspace
        import Quartz
        pid = NSWorkspace.sharedWorkspace().frontmostApplication().processIdentifier()
        windows = Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements, Quartz.kCGNullWindowID)
        for w in windows:                                              # front to back: the first normal window of that program is its front window
            if w.get("kCGWindowOwnerPID") == pid and w.get("kCGWindowLayer") == 0:
                b = w["kCGWindowBounds"]
                if b["Width"] > 50 and b["Height"] > 50:
                    return int(b["X"]), int(b["Y"]), int(b["Width"]), int(b["Height"])
    except Exception:
        pass
    return None


def _new_path():
    FOLDER.mkdir(parents=True, exist_ok=True)
    path = FOLDER / f"Study Assistant {datetime.now():%Y-%m-%d %H-%M-%S}.png"
    n = 1
    while path.exists():                                                # two in the same second
        n += 1
        path = FOLDER / f"Study Assistant {datetime.now():%Y-%m-%d %H-%M-%S} ({n}).png"
    return path


def take():
    """Save the picture and return its path. Raises RuntimeError with a short reason when it cannot be made."""
    if sys.platform == "darwin":
        path = _new_path()
        box = _mac_window_box()
        cmd = ["screencapture", "-x", "-t", "png"] + (["-R", "%d,%d,%d,%d" % box] if box else []) + [str(path)]      # no window found: the whole screen
        try:
            subprocess.run(cmd, check=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            raise RuntimeError("macOS could not take the picture (allow Study Assistant under System Settings > Privacy & Security > Screen Recording).")
        if not path.exists():
            raise RuntimeError("macOS did not save the picture.")
        return path
    if sys.platform != "win32":
        raise RuntimeError("Screenshots are only available on Windows and on a Mac.")
    box = _window_rect()
    if not box:
        raise RuntimeError("No window to take a picture of.")
    from PIL import ImageGrab
    image = ImageGrab.grab(bbox=box, all_screens=True)
    path = _new_path()
    image.save(path)
    return path
