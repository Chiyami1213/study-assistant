"""Help and problem reports (Settings > Help, Settings > Report an Issue).

A report goes to the project's GitHub Issues: the app opens a pre-filled "new issue" page in the browser and the user reads it and presses Submit
there. Nothing is sent by the app itself, no e-mail address or password is kept in the program, and nothing personal is added: the technical details are the
version and the kind of computer only, and the log excerpt (off by default) has the user's name and folders replaced."""
import os
import platform
import re
import sys
import urllib.parse
from pathlib import Path

from version import VERSION

REPO_URL = "https://github.com/Chiyami1213/study-assistant"
HELP_URL = REPO_URL + "/blob/main/docs/HELP.md"
ISSUES_URL = REPO_URL + "/issues"
KINDS = {                                   # label shown -> (GitHub label, title prefix)
    "Something Is Not Working": ("bug", "Bug: "),
    "I Have an Idea": ("enhancement", "Idea: "),
    "I Have a Question": ("question", "Question: "),
}
MAX_URL_BODY = 5500                         # GitHub refuses very long addresses: the body is cut to this many characters


def mac_or_windows():
    return {"darwin": "macOS", "win32": "Windows"}.get(sys.platform, sys.platform)


def diagnostics():
    """Non-personal facts that help to reproduce a problem: the app, how it runs, and the kind of computer."""
    lines = [f"- Study Assistant: {VERSION} ({'installed app' if getattr(sys, 'frozen', False) else 'run from source'})",
             f"- System: {mac_or_windows()} {platform.release()} {platform.version() if sys.platform == 'win32' else platform.mac_ver()[0] or ''}".rstrip(),
             f"- Computer: {platform.machine()}"]
    return "\n".join(lines)


def scrub(text):
    """Replace the user's name and folders in a piece of text with placeholders (so a log excerpt can be shared)."""
    home = str(Path.home())
    text = text.replace(home, "~").replace(home.replace("\\", "/"), "~")
    user = os.environ.get("USERNAME") or os.environ.get("USER") or ""
    if len(user) > 2:
        text = re.sub(re.escape(user), "<user>", text, flags=re.I)
    return text


def log_tail(lines=40):
    """The last lines of the installed app's server log (scrubbed), or "" when there is none."""
    try:
        from database import DATA_DIR
        path = DATA_DIR / "logs" / "server.log"
        text = path.read_text(encoding="utf-8", errors="replace")
        return scrub("\n".join(text.strip().splitlines()[-lines:]))
    except OSError:
        return ""


def build_report(kind, summary, details, steps="", include_system=True, include_log=False):
    """(title, body) of the report as Markdown."""
    label, prefix = KINDS.get(kind, ("bug", "Bug: "))
    title = (prefix + summary.strip())[:140]
    parts = [f"**What happened / what I would like**\n{details.strip() or '(not filled in)'}"]
    if steps.strip():
        parts.append(f"**Steps to reproduce**\n{steps.strip()}")
    if include_system:
        parts.append("**Technical details**\n" + diagnostics())
    if include_log and log_tail():
        parts.append("**Last lines of the app's log**\n```\n" + log_tail() + "\n```")
    return title, "\n\n".join(parts) + "\n"


def issue_url(kind, title, body):
    label = KINDS.get(kind, ("bug", ""))[0]
    if len(body) > MAX_URL_BODY:
        body = body[:MAX_URL_BODY] + "\n\n(cut here: the report was too long for a web address; paste the rest as a comment)"
    return f"{REPO_URL}/issues/new?" + urllib.parse.urlencode({"title": title, "body": body, "labels": label}, quote_via=urllib.parse.quote)


def where_files():
    from database import DATA_DIR
    return str(DATA_DIR)


FAQ = [
    ("How do I install or update Study Assistant?",
     "**Windows:** download the Windows installer zip from the [Releases page](" + REPO_URL + "/releases), extract it, and run *Install Study Assistant.exe*. "
     "If Study Assistant is already installed, the installer offers to update it, to uninstall the older version first, or to keep both. Your files are never replaced.\n\n"
     "**macOS:** download the macOS disk image (`.dmg`), open it and drag *Study Assistant* into *Applications*. To update, drag the new one over the old one and choose Replace."),
    ("Windows or my antivirus warns about the app",
     "A new, unsigned app can trigger *Windows protected your PC* (SmartScreen) or an antivirus warning. It is a false alarm: choose *More info*, then *Run anyway*, "
     "or allow the app in your antivirus. On a Mac, if it says the app cannot be opened because the developer cannot be verified, right-click (or Control-click) "
     "the app, choose *Open*, then *Open* again. You only need to do this once."),
    ("Where are my files?",
     "Everything you add (the Library, notes, grades, settings, backups) is kept apart from the program, so updating or reinstalling never touches it. "
     "On Windows it is in `%APPDATA%\\Study Assistant`; on a Mac it is in `~/Library/Application Support/Study Assistant`. On this computer: `{files}`."),
    ("How do I back up my files or move them to another computer?",
     "Settings > Backup keeps a copy of your Library. *Export My Files* makes one zip of your files; on the other computer install Study Assistant and use *Import* in the same place."),
    ("The window says Connection error, or stopped responding",
     "Close the window and open Study Assistant again; your files are safe. The installed app keeps a log in the `logs` folder of your data folder: include its last lines when you report the problem."),
    ("Keyboard shortcuts",
     "F2 saves a screenshot, F5 refreshes the page, F11 turns full screen on and off, **m** hides the menu bar, and with the menu bar shown a letter opens a page. "
     "On a Mac laptop hold the **fn** key with F2, F5 and F11 (or turn on *Use F1, F2, etc. keys as standard function keys* in System Settings). All of them are listed under Keyboard Shortcuts above."),
    ("How do I uninstall it?",
     "**Windows:** Settings > Apps > Installed apps > Study Assistant > Uninstall. It asks whether to keep your files (the default) or remove everything. "
     "**macOS:** drag *Study Assistant* from Applications to the Bin. Your files stay in the data folder until you delete it."),
]
