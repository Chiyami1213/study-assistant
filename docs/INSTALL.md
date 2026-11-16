# Study Assistant: Install

<p align="center"><a href="../README.md">Overview</a> &nbsp;|&nbsp; <b>Install</b> &nbsp;|&nbsp; <a href="FILES.md">Your Files</a> &nbsp;|&nbsp; <a href="SHORTCUTS.md">Shortcuts</a> &nbsp;|&nbsp; <a href="HELP.md">Help</a> &nbsp;|&nbsp; <a href="../CHANGELOG.md">Changelog</a></p>

---

Get the download for your computer from the [Releases](https://github.com/Chiyami1213/study-assistant/releases) page. Study Assistant is installed for your user only (no administrator needed), and your files are kept
apart from the program, so updating or reinstalling never touches them.

## Windows 10 and 11

Download `StudyAssistant-<version>-Windows-Installer.zip`, extract the whole zip, and run `Install Study Assistant.exe` from the extracted folder (keep the `payload` folder next
to it). The setup wizard guides you:
- **If Study Assistant is already installed**, it tells you which version and offers to **update (overwrite)** it, to **uninstall the older version first**, or to **keep both**
  (it warns that both share one data folder and one address, so only one should be open at a time).
- **Shortcuts:** you choose a Desktop shortcut and / or a Start menu entry. Study Assistant is also listed under Settings > Apps, where it can be uninstalled (your files are
  kept unless you choose to remove them).
- The last page links to this page and its [Help](HELP.md) section.

## macOS (Apple silicon and Intel)

Download `StudyAssistant-<version>-macOS-Apple-Silicon.dmg` (M1 and newer) or `StudyAssistant-<version>-macOS-Intel.dmg`, open it, and drag **Study Assistant** onto the
**Applications** folder. If it is already there, choose **Replace** (your files are kept) or **Keep Both**. The first time, right-click (or Control-click) the app in Applications,
choose **Open**, then **Open** again; if macOS still blocks it, use System Settings > Privacy & Security > **Open Anyway**. The Mac app is built by GitHub from this repository
(see `.github/workflows/build-macos.yml`).

> **Your antivirus, Windows SmartScreen or macOS may warn about the app, or block it.** It is a false alarm: **Study Assistant does not contain a virus**, and the whole source code
> is here to read. Programs that are new and not code-signed are often flagged until many people have run them. If it blocks the file, choose "More info > Run anyway"
> (Windows SmartScreen) or "Open Anyway" (macOS), or allow the file in your security software. Only download it from the [Releases](https://github.com/Chiyami1213/study-assistant/releases) page, and check the file against
> the SHA-256 checksum published next to it (`SHA256SUMS.txt` for the Windows zip, `SHA256SUMS-macOS-Apple-Silicon.txt` or `SHA256SUMS-macOS-Intel.txt` for a Mac disk image): in PowerShell `Get-FileHash <file>`, on a Mac `shasum -a 256 <file>`.

The app starts empty; add your own courses and files.
