"""The tabs of a Note Reader page. Notes are self-contained interactive HTML pages built outside the app (see CLAUDE.md); this module finds the
parts of one (Notes, Mind Map, Equation Sheet, Assumptions, Quiz, Errata) from the id or heading of each <section>."""
import re

ERRATA_WORDS = re.compile(r"errata|notes check|things to fix|clarification", re.I)


# The parts the Note Reader shows as tabs, found by the id or the heading of a section. Not every note has every part.
PARTS = [
    ("mindmap", "Mind Map", re.compile(r"mind[\s_-]*maps?", re.I)),
    ("eqsheet", "Equation Sheet", re.compile(r"equation sheet|formula sheet|cheat sheet", re.I)),
    ("assumptions", "Assumptions", re.compile(r"^\s*(summary\s+)?assumptions?(\s+list)?\s*$", re.I)),
    ("quiz", "Quiz", re.compile(r"self[\s_-]*check|\bquiz\b|^\s*(practice\s+)?exercises", re.I)),
    ("errata", "Errata", re.compile(r"errata|notes check|things to fix|corrections|clarifications?", re.I)),
]
PART_IDS = {"mindmap": "mindmap", "mind-map": "mindmap", "eqsheet": "eqsheet", "sheet": "eqsheet", "cheat": "eqsheet",
            "assumptions": "assumptions", "quiz": "quiz", "qs": "quiz", "exercises": "quiz", "selfcheck": "quiz", "errata": "errata"}


def parts(page_html):
    """[{key, label, section}] for the tabs of a note: Notes first, then one for each other part the note has, in the order they appear
    in the page. Everything that is not one of the named parts is the note itself ("Notes"), which opens at its first section.
    A note with no sections is one "Notes" tab."""
    found, seen = [], set()
    for m in re.finditer(r'<section[^>]*id="([^"]+)"[^>]*>(.*?)</section>', page_html, re.S):
        sid = m.group(1)
        h = re.search(r"<h2[^>]*>(.*?)</h2>", m.group(2), re.S)
        title = re.sub(r"</?[A-Za-z][^>]*>", " ", h.group(1)) if h else ""
        key = PART_IDS.get(sid.lower())
        if 'class="errata"' in m.group(2):
            key = "errata"
        if key is None or (key == "errata" and not ERRATA_WORDS.search(title) and 'class="errata"' not in m.group(2)):
            key = next((k for k, _, rx in PARTS if rx.search(title)), None)
        if key is None:
            key = "notes"
        if key not in seen:
            seen.add(key)
            found.append({"key": key, "label": "Notes" if key == "notes" else next(l for k, l, _ in PARTS if k == key), "section": sid})
    found.sort(key=lambda part: part["key"] != "notes")          # Notes is always the first tab; the rest keep the order of the page
    return found or [{"key": "notes", "label": "Notes", "section": None}]
