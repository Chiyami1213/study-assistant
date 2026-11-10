"""Course outlines: made automatically, and editable as plain text.

A course with no outline gets one built for it, in this order:
  1. from the topics the course syllabus (or the Lec 0 slides) lists under "Course Outline", "Course Topics", "Topics Covered" ... ;
  2. otherwise from the lecture or chapter titles in the Library (Lecture Notes with lecture numbers; or the chapter Notes when the lecture
     files only have generic names such as "Week 3 Lecture").
An outline made this way is refreshed when the Library's lecture list changes, until the user edits it. Saving an edit (Courses > course >
Outline > Edit Outline) marks the outline as the user's own: it is never replaced automatically again. Whatever an outline is replaced
by (a rebuild, an edit) is first copied to <data folder>\\outlines\\.

The text form: one point per line, indented two spaces per level (main topic, sub topic, point, detail). A line may start with its marker
("I.", "A.", "1.", "a.", "Lec 3", "Week 2", "Ch 4"); markers left out are numbered for you. "[9 Hours]" at the end sets the hours and a
web address at the end sets the link; a point keeps its Library link (the file and page it opens) while its marker and title stay as they were,
and an unlinked point is linked to the lecture or chapter whose title it matches."""
import functools
import json
import re

import crud
import database
import settings

LIGATURES = {"Ɵ": "ti", "Ʃ": "tt", "ﬂ": "fl", "ﬁ": "fi", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl", " ": " "}   # as some PDFs extract them
HEADING = re.compile(r"(course\s+(outline|topics|content|contents|plan)|topics\s+(covered|to\s+be\s+covered)|tentative\s+(schedule|outline)|"
                     r"(weekly|class|lecture)\s+(schedule|outline)|syllabus\s+outline|schedule\s+of\s+topics|outline\s+of\s+topics)", re.I)
STOP = re.compile(r"^(grad(e|ing)|homework|exams?|attendance|policies|policy|textbooks?|references?|academic|honor|office\s+hours|prerequisites?|"
                  r"important\s+dates|learning\s+(outcomes|objectives)|course\s+description|disability|accommodations?|contact|instructor|teaching\s+assistants?)\b", re.I)
GENERIC_TITLE = re.compile(r"^\s*(week|lecture|lec|class|session|chapter|ch)\s*[\d.\-–]+\s*(lecture|notes?|slides?)?\s*$", re.I)
FLAT_MARKER = r"(?:Part|Lec(?:ture)?|Week|Wk|Ch(?:apter)?|Unit|Module|Session|Class|Day)\s*[\d\-–]+[a-z]?"
MARKER = re.compile(rf"^(?P<m>(?:[IVXLCDM]+|[A-Za-z]|\d+)\.|{FLAT_MARKER}[.:]?)\s+(?P<t>\S.*)$")
ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX", "XX"]
MINOR = {"a", "an", "the", "and", "but", "or", "nor", "for", "so", "yet", "as", "at", "by", "if", "in", "of", "off", "on", "per", "to", "up", "via", "vs"}
FILE_KINDS = ("Lecture Notes", "Notes")


# ---------------------------------------------------------------- titles
def apa_title(text):
    """APA title case: first and last word, the word after a colon, dash or opening parenthesis, and every word of four letters or more are capitalized."""
    def core_case(core, force):
        if any(ch.isdigit() for ch in core) or any(c.isupper() for c in core[1:]) or "," in core:
            return core                                                  # 3D, WKB, (cp,cv) ... stay as written
        if not force and core.lower() in MINOR:
            return core.lower()
        return "".join(p if p in "-/" else p[:1].upper() + p[1:] for p in re.split(r"([-/])", core))

    tokens, out, force = text.split(), [], True
    for i, tok in enumerate(tokens):
        lead, core, trail = re.match(r"^(\W*)(.*?)(\W*)$", tok).groups()
        if not core:
            out.append(tok)
            force = tok in ("-", "–", "—")
            continue
        out.append(lead + core_case(core, force or i == len(tokens) - 1 or "(" in lead) + trail)
        force = trail.endswith(":")
    return " ".join(out)


def _clean(text):
    for a, b in LIGATURES.items():
        text = text.replace(a, b)
    return text


def _words(text):
    return {w for w in re.findall(r"[a-z]{3,}", (text or "").lower()) if w not in MINOR}


def _nums(book):
    return [int(x) for x in re.findall(r"\d+", book.get("lecture") or "")]


# ---------------------------------------------------------------- the Library's lecture / chapter titles
def course_files(course_id):
    """The course's lecture and chapter files that have a lecture number, in lecture order: [(kind, book)]."""
    rows = [b for b in crud.list_books() if course_id in b["course_ids"] and b["kind"] in FILE_KINDS and _nums(b)]
    rows.sort(key=lambda b: (_nums(b), b["title"].lower()))
    return [(b["kind"], b) for b in rows]


def from_titles(course_id):
    """Items from the lecture titles (marker "Lec 4-5"), or from the chapter notes ("Ch 3") when the lecture files only have generic names. [] if neither."""
    files = course_files(course_id)
    lectures = [b for k, b in files if k == "Lecture Notes"]
    chapters = [b for k, b in files if k == "Notes" and b["pdf_path"].lower().endswith((".html", ".htm"))]
    generic = sum(bool(GENERIC_TITLE.match(b["title"])) for b in lectures)
    if lectures and not (chapters and generic * 2 >= len(lectures)):
        books, prefix = lectures, "Lec"
    elif chapters:
        books, prefix = chapters, "Ch"
    else:
        return []
    return [{"level": "L", "marker": f"{prefix} {b['lecture'].strip()}", "title": b["title"], "hours": "", "url": "", "book_id": b["id"], "page": 1} for b in books]


# ---------------------------------------------------------------- the syllabus / Lec 0 slides
def parse_topics(text):
    """Items from the topic list of a syllabus text: numbered topics with (a) (b) details, roman / lettered outlines, or "Week 3: Topic" lines.
    [] when the text has no such list (at least four points are needed)."""
    lines = [re.sub(r"\s+", " ", _clean(l)).strip() for l in text.splitlines()]
    lines = [l for l in lines if l]
    start = next((i for i, l in enumerate(lines) if HEADING.search(l) and len(l) < 60), None)
    if start is None:
        return []
    weeks_note = any("week" in l.lower() for l in lines[start:start + 4])
    items, pending = [], None
    for l in lines[start + 1:start + 140]:
        if pending and not re.match(r"^\(([A-Za-z])\)", l):                    # "(a)" on a line of its own: the next line is its title
            items.append({"level": "A", "marker": pending, "title": l, "hours": "", "url": "", "book_id": None, "page": None})
            pending = None
            continue
        alone = re.match(r"^\(([A-Za-z])\)$", l)
        if alone:
            pending = alone.group(1)
            continue
        if STOP.match(l):                                                      # the next section of the syllabus (grading, policies ...)
            if len(items) >= 2:
                break
            continue
        m = re.match(r"^(?:(Week|Wk|Lecture|Lec|Class|Session)\s*(\d+)\s*[:.\-–]\s*(.+)|(\d+)[.)]\s+(.+)|\(([a-z])\)\s*(.+)|([a-z])[.)]\s+(.+)|([IVX]+)\.\s+(.+)|([A-Z])[.)]\s+(.+))$", l)
        if not m:
            if re.fullmatch(r"\d{1,3}", l):                                       # a page number
                continue
            if items and len(l) < 100 and not l.endswith(".") and not STOP.match(l) and not HEADING.search(l):
                items[-1]["title"] += " " + l                                  # a wrapped line belongs to the point above
            elif items and len(l) >= 100 and len(items) >= 4:
                break
            continue
        g = m.groups()
        if g[0]:
            level, title = "L", g[2]
            marker = f"{'Lec' if g[0].lower() in ('lecture', 'lec') else g[0].capitalize()} {g[1]}"
        elif g[3]:
            level, marker, title = "I", g[3], g[4]
        elif g[5]:
            level, marker, title = "A", g[5], g[6]
        elif g[7]:
            level, marker, title = "A", g[7], g[8]
        elif g[9]:
            level, marker, title = "I", g[9], g[10]
        else:
            level, marker, title = "A", g[11], g[12]
        parts = re.split(r"\s+\(([A-Za-z])\)\s+", title)                            # "Topic [1] (A) one (B) two": some PDFs put the details on the topic's line
        items.append({"level": level, "marker": marker, "title": parts[0].strip(), "hours": "", "url": "", "book_id": None, "page": None})
        for j in range(1, len(parts) - 1, 2):
            items.append({"level": "A", "marker": parts[j], "title": parts[j + 1].strip(), "hours": "", "url": "", "book_id": None, "page": None})
    for it in items:
        w = re.search(r"\s*\[\s*([\d.–-]+)\s*\]\s*$", it["title"])           # "[2]": weeks (or hours) of the topic
        if w:
            it["title"] = it["title"][:w.start()].strip()
            if it["level"] == "I":
                it["hours"] = f"{w.group(1)} {'Week' if w.group(1) == '1' else 'Weeks'}" if weeks_note else f"{w.group(1)} {'Hour' if w.group(1) == '1' else 'Hours'}"
        it["title"] = apa_title(it["title"].rstrip(" ;,."))
    if items and items[0]["level"] == "A":                                          # details with no topic above them: not an outline
        return []
    return items if len(items) >= 4 else []


@functools.lru_cache(maxsize=32)
def _topics(path, mtime):
    """The topic list of one pdf (cached: the page asks for it every time it is drawn)."""
    import pymupdf
    with pymupdf.open(path) as doc:
        text = "\n".join(doc[i].get_text() for i in range(min(doc.page_count, 8)))
    return tuple(tuple(sorted(i.items())) for i in parse_topics(text))


def from_syllabus(course_id):
    """Items from the topic list of the course syllabus, or of the Lec 0 slides ("Course Overview" / "Course Information"). [] if neither lists topics."""
    books = [b for b in crud.list_books() if course_id in b["course_ids"] and b["pdf_path"].lower().endswith(".pdf")
             and (b["kind"] == "Syllabus" or (b["kind"] == "Lecture Notes" and (b.get("lecture") or "").strip() == "0"))]
    books.sort(key=lambda b: b["kind"] != "Syllabus")                              # the syllabus first
    for b in books:
        path = database.data_path(b["pdf_path"])
        try:
            items = [dict(i) for i in _topics(str(path), path.stat().st_mtime)]
        except Exception:
            continue
        if items:
            return _link(items, course_id)
    return []


def _link(items, course_id):
    """Link every point whose title clearly names one lecture or chapter (shares most of its words, and no other file does as well) to that file."""
    files = [b for _, b in course_files(course_id)]
    for it in items:
        if it.get("book_id"):
            continue
        want = _words(it["title"])
        if not want:
            continue
        scored = sorted(((len(want & _words(b["title"])) / len(want), -len(b["title"]), b["id"]) for b in files), reverse=True)
        if scored and scored[0][0] >= 0.6 and (len(scored) < 2 or scored[0][0] > scored[1][0]):
            it["book_id"], it["page"] = scored[0][2], 1
    return items


def auto_items(course_id):
    """(items, source) for a course: the syllabus topics when it lists them, else the lecture / chapter titles; ([], None) when there is nothing to build from."""
    items = from_syllabus(course_id)
    if items:
        return items, "syllabus"
    items = from_titles(course_id)
    return (items, "titles") if items else ([], None)


# ---------------------------------------------------------------- keeping an automatic outline up to date
def signature(items):
    return json.dumps([[i["level"], i["marker"], i["title"], i.get("book_id")] for i in items], sort_keys=True)


def ensure(course_id):
    """Build the outline of a course that has none, and refresh an automatic one when the Library's lectures changed. An outline the user
    made or edited (or one that existed before this was added) is never touched. Returns the state {source, sig}."""
    state = settings.get_outline_state(course_id)
    current = crud.list_outline(course_id)
    if state.get("source") == "manual":
        return state
    if current and not state:                                  # an outline from before: it is the user's
        settings.set_outline_state(course_id, "manual", "")
        return {"source": "manual", "sig": ""}
    items, source = auto_items(course_id)
    if not items:
        return state
    sig = signature(items)
    if not current or state.get("sig") != sig:
        save_previous(course_id)
        crud.replace_outline(course_id, items)
        settings.set_outline_state(course_id, source, sig)
        return {"source": source, "sig": sig}
    return state


def save_previous(course_id):
    """Copy the outline as it is now to <data folder>\\outlines\\ before something replaces it."""
    rows = crud.list_outline(course_id)
    if not rows:
        return None
    course = crud.get_course(course_id)
    name = re.sub(r"[^\w .-]", "", course.get("code") or course.get("name") or str(course_id)).strip() or str(course_id)
    folder = database.DATA_DIR / "outlines"
    folder.mkdir(parents=True, exist_ok=True)
    from datetime import datetime
    path = folder / f"{name} {datetime.now():%Y%m%d-%H%M%S}.json"
    path.write_text(json.dumps([{k: r[k] for k in ("level", "marker", "title", "hours", "url", "book_id", "page")} for r in rows], ensure_ascii=False, indent=1), encoding="utf-8")
    return path


# ---------------------------------------------------------------- the text form
DEPTH = {"I": 0, "L": 0, "A": 1, "1": 2, "a": 3}


def to_text(rows):
    out = []
    for r in rows:
        marker = r["marker"] + ("." if re.fullmatch(r"[IVXLCDM]+|[A-Za-z]|\d+", r["marker"]) else "")
        line = "  " * DEPTH.get(r["level"], 0) + f"{marker}  {r['title']}"
        if r.get("hours"):
            line += f"  [{r['hours']}]"
        if r.get("url"):
            line += f"  {r['url']}"
        out.append(line)
    return "\n".join(out)


def _alpha(n, upper):
    s = ""
    n += 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s if upper else s.lower()


def from_text(text, previous=(), course_id=None):
    """Items from the text form. `previous` are the rows being edited (their Library links are kept for points that did not change)."""
    keep, known = {}, {r["title"].lower() for r in previous}
    for r in previous:
        if r.get("book_id") or r.get("url"):
            keep[(r["marker"].lower(), r["title"].lower())] = r
            keep.setdefault((None, r["title"].lower()), r)
    parsed = []
    for raw in text.splitlines():
        if not raw.strip():
            continue
        raw = raw.replace("\t", "  ")
        indent = (len(raw) - len(raw.lstrip(" "))) // 2
        line = raw.strip()
        url = ""
        u = re.search(r"\s(https?://\S+)$", line)
        if u:
            url, line = u.group(1), line[:u.start()].strip()
        hours = ""
        h = re.search(r"\s*\[([^\]]+)\]\s*$", line)
        if h:
            hours, line = h.group(1).strip(), line[:h.start()].strip()
        m = MARKER.match(line)
        marker, title = (m.group("m").rstrip(".:"), m.group("t").strip()) if m else ("", line)
        parsed.append([indent, marker, title, hours, url])
    if not parsed:
        return []
    nested = any(p[0] > 0 for p in parsed)
    items, depth_prev, counters = [], -1, [0, 0, 0, 0]
    for indent, marker, title, hours, url in parsed:
        depth = min(max(indent, 0), depth_prev + 1, 3) if items else 0
        flat = (not nested) and bool(re.fullmatch(FLAT_MARKER, marker))
        level = "L" if flat else ("I", "A", "1", "a")[depth]
        counters[depth] += 1
        for d in range(depth + 1, 4):
            counters[d] = 0
        if not marker:
            marker = (ROMAN[counters[0] - 1] if counters[0] <= len(ROMAN) else str(counters[0])) if depth == 0 else \
                _alpha(counters[1] - 1, True) if depth == 1 else str(counters[2]) if depth == 2 else _alpha(counters[3] - 1, False)
        old = keep.get((marker.lower(), title.lower())) or keep.get((None, title.lower()))
        items.append({"level": level, "marker": marker, "title": title, "hours": hours, "url": url or (old["url"] if old and not url else ""),
                      "book_id": old.get("book_id") if old else None, "page": old.get("page") if old else None})
        depth_prev = depth
    if course_id:                                                    # only the points typed new are linked by their title; the others keep what they had
        fresh = [i for i in items if i["title"].lower() not in known]
        _link(fresh, course_id)
    return items
