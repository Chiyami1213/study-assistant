r"""Homework helper: reads a homework PDF, splits it into problems and sub-problems, and for each one finds the section of the
course's HTML notes it draws on, with a hint built from that section (its key idea and first formulas).

A problem is a line like "2. Rotational Energies and the Rigid Rotor Model" and a sub-problem a line starting "a) ...".
Matching compares the problem's words with the words of every section of the course's notes; words that appear in few
sections count most. Hints written by hand can replace the automatic ones in homework/<course>/<homework title>.json:
    {"2a": {"hint": "Use E_J = ..."}, "2": {"hint": "..."}}"""
import html as _html
import json
import math
import re
from functools import lru_cache

import macros
import pymupdf
import quizgen
import unitex
from database import BASE_DIR

ROOT = BASE_DIR / "homework"
PROBLEM = re.compile(r"^\s*(\d{1,2})\.\s+([A-Z].{3,})$")             # "2. Rotational Energies ..."        (AE 6765)
PROBLEM_BARE = re.compile(r"^\s*(\d{1,2})\s*$")                        # "1" on its own line, the title on the next (PHYS 6105)
PROBLEM_PAREN = re.compile(r"^\s*(\d{1,2})\)\s+(\S.*)$")                 # "1) A uniform beam ..."                (AE 6451)
PART = re.compile(r"^\s*\(?([a-h])\)\s+(.*)$")                          # "a) ..." or "(a) 5 points ..."
TITLE = re.compile(r"^[A-Z0-9][A-Za-z0-9’'“”\-,:?\. ]{3,70}$")                       # a short heading line, no math
POINTS = re.compile(r"^\d+(\.\d+)?\s*points?\s*", re.I)
STOP = set("that this with from have does what which when where there their then than into only each both about would could "
           "should these those equals equal also because while after before over under must same other more most using use "
           "determine find calculate compute assuming following given show your results result number values value".split())


def _words(text):
    return {w for w in re.findall(r"[a-z]{4,}", text.lower()) if w not in STOP}


@lru_cache(maxsize=16)
def parse_problems(path, mtime):
    """[{id, title, page, text, parts: [{id, page, text}]}] read from the homework PDF. Problems are numbered in order, so a
    page number or an equation number is never taken for the next problem."""
    lines = []
    with pymupdf.open(path) as doc:
        for i, page in enumerate(doc):
            page_lines = [ln for ln in page.get_text().splitlines() if ln.strip()]
            if page_lines and page_lines[-1].strip() == str(i + 1):         # the page number at the foot
                page_lines = page_lines[:-1]
            for line in page_lines:
                lines.append((i + 1, line.rstrip()))
    problems, current, part, pending = [], None, None, False
    for at, (page, line) in enumerate(lines):
        nxt = lines[at + 1][1].strip() if at + 1 < len(lines) else ""
        want = 1 if current is None else int(current["id"]) + 1
        if pending:                                                       # the line after a bare number is the title
            current["title"] = current["text"] = line.strip()
            pending = False
            continue
        m = PROBLEM.match(line) or PROBLEM_PAREN.match(line)
        bare = PROBLEM_BARE.match(line)
        if m and int(m.group(1)) == want:
            text = m.group(2).strip()
            title = text if PROBLEM.match(line) else " ".join(text.split()[:9]).rstrip(",.;:") + "..."
            current = {"id": m.group(1), "title": title, "page": page, "text": text, "parts": []}
            problems.append(current)
            part = None
            continue
        if bare and int(bare.group(1)) == want and TITLE.match(nxt) and re.search(r"[A-Za-z]{3,}", nxt):
            # "2" then "2D WKB"; not a fraction's "2" then "d", nor a table cell "4" then "120."
            current = {"id": bare.group(1), "title": "", "page": page, "text": "", "parts": []}
            problems.append(current)
            part, pending = None, True
            continue
        if current is None:
            continue
        m = PART.match(line)
        if m and (part is None and m.group(1) == "a" or part is not None and ord(m.group(1)) == ord(part["id"]) + 1):
            part = {"id": m.group(1), "page": page, "text": POINTS.sub("", m.group(2).strip())}
            current["parts"].append(part)
            current["text"] += " " + part["text"]
            continue
        (part if part else current)["text"] += " " + line.strip()
        if part:
            current["text"] += " " + line.strip()
    for pr in problems:                                                   # "a. Determine ... b. Determine ..." written inside the text
        if not pr["parts"]:
            pr["parts"] = _inline_parts(pr)
    return problems


INLINE_PART = re.compile(r"(?:(?<=\s)|^)([a-h])[.)]\s+(?=[A-Z])")


def _inline_parts(pr):
    """Lettered parts that run on in one paragraph ("a. ... b. ... c. ..."): split at the letters, in order, when there are at least two."""
    marks, want = [], "a"
    for m in INLINE_PART.finditer(pr["text"]):
        if m.group(1) == want:
            marks.append(m)
            want = chr(ord(want) + 1)
    if len(marks) < 2:
        return []
    out = []
    for k, m in enumerate(marks):
        end = marks[k + 1].start() if k + 1 < len(marks) else len(pr["text"])
        out.append({"id": m.group(1), "page": pr["page"], "text": pr["text"][m.end():end].strip()})
    return out


# parts of a note that summarize or cross-refer instead of teaching: never offered as "where to look"
NOT_TEACHING = re.compile(r"equation sheet|formula sheet|assumptions list|cross-?reference|reference$", re.I)
SUBSECTION = re.compile(r'<h3[^>]*id="(s\d+-\d+)"[^>]*>(.*?)</h3>', re.S)


@lru_cache(maxsize=16)
def _sections(paths_key):
    """Every teaching part of the course's HTML notes: the numbered subsections (<h3 id="s2-1">) of the standard note format,
    or the whole section for a note without them: [{book, sec, title, num, ssn, label, text, html, words, defs}]."""
    out = []
    for book_id, path, mtime in paths_key:
        text = open(path, encoding="utf-8", errors="replace").read()
        defs = macros.from_html(text)
        for sec in quizgen.sections_of(text):
            m = re.search(r'<section id="' + re.escape(sec["id"]) + r'"[^>]*>(.*?)</section>', text, re.S)
            inner = m.group(1) if m else ""
            if sec["id"].lower() in ("eqsheet", "sheet", "assumptions", "cheat") or NOT_TEACHING.search(sec["title"]):
                continue
            subs = list(SUBSECTION.finditer(inner))
            if not subs:
                out.append({"book": book_id, "sec": sec["id"], "title": sec["title"], "num": sec["num"], "label": sec.get("label"), "ssn": None,
                            "text": sec["text"], "html": inner, "words": _words(sec["title"] + " " + sec["text"]), "defs": defs})
                continue
            for k, hm in enumerate(subs):
                chunk = inner[hm.start(): subs[k + 1].start() if k + 1 < len(subs) else len(inner)]
                ssn = re.search(r'class="ssn">\s*([\d.]+)', hm.group(2))
                title = re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r'<span class="ssn">.*?</span>', "", hm.group(2), flags=re.S)))).strip()
                body = quizgen._text(chunk)
                out.append({"book": book_id, "sec": hm.group(1), "title": title, "num": sec["num"], "label": None, "ssn": ssn.group(1) if ssn else None,
                            "text": body, "html": chunk, "words": _words(title + " " + body), "defs": defs})
    return out


def section_label(section, book):
    """How a part of a note is named on a button: "Lec 6 §2.1" for a subsection, "6.2" (lecture.section) for a whole section."""
    lec = book.get("lecture") if book else None
    if section.get("ssn"):
        return (f"Lec {lec} " if lec else "") + f"§{section['ssn']}"
    return section.get("label") or ((f"{lec}." if lec else "§") + str(section["num"]))


EXAMPLE = re.compile(r'<details class="example"([^>]*)>\s*<summary>(.*?)</summary>(.*?)</details>', re.S)


@lru_cache(maxsize=16)
def _examples(paths_key):
    """Every worked example of the course's HTML notes: [{book, sec (the example's id), title, num, label, words, defs}]."""
    out = []
    for book_id, path, mtime in paths_key:
        text = open(path, encoding="utf-8", errors="replace").read()
        defs = macros.from_html(text)
        for m in EXAMPLE.finditer(text):
            ident = re.search(r'id="([^"]+)"', m.group(1))
            if not ident:
                continue
            head = re.sub(r"<[^>]+>", " ", m.group(2))
            head = re.sub(r"\s+", " ", _html.unescape(head)).strip()
            body = re.sub(r"<(script|style|svg|figure)[^>]*>.*?</\1>", " ", m.group(3), flags=re.S)
            body = re.sub(r"<[^>]+>", " ", body)
            number = re.search(r"Example\s*(\d+)", head)
            title = re.sub(r"^Example\s*\d+\s*", "", head)
            title = re.sub(r"\s*(constructed|from the slides|in class)\s*$", "", title, flags=re.I).strip()
            out.append({"book": book_id, "sec": ident.group(1), "title": title, "num": int(number.group(1)) if number else 0,
                        "label": None, "defs": defs, "words": _words(title + " " + _html.unescape(body))})
    return out


def course_examples(course_id, books):
    """The worked examples of all HTML notes of a course (cached by file time); [] when the notes have none."""
    key = []
    for b in books:
        if course_id in b["course_ids"] and b["kind"] in ("Notes", "Lecture Notes") and b["pdf_path"].lower().endswith((".html", ".htm")):
            p = BASE_DIR / b["pdf_path"]
            if p.exists():
                key.append((b["id"], str(p), p.stat().st_mtime))
    return _examples(tuple(key))


def course_sections(course_id, books):
    """The sections of all HTML notes of a course (cached by file time)."""
    key = []
    for b in books:
        if course_id in b["course_ids"] and b["kind"] in ("Notes", "Lecture Notes") and b["pdf_path"].lower().endswith((".html", ".htm")):
            p = BASE_DIR / b["pdf_path"]
            if p.exists():
                key.append((b["id"], str(p), p.stat().st_mtime))
    return _sections(tuple(key))


EXAMPLE_FLOOR = 14.0          # how well a worked example must match before it is offered


def best_sections(text, sections, n=2, boost="", floor=4.0):
    """The n sections whose words best match the text (rare shared words weigh most). Words of `boost` (the problem's title)
    count three times, so a problem named "Rotational Energies and the Rigid Rotor Model" finds the rigid-rotor section."""
    words, heavy = _words(text), _words(boost)
    allw = words | heavy
    if not allw or not sections:
        return []
    docs = len(sections)
    freq = {w: max(1, sum(w in s["words"] for s in sections)) for w in allw}
    scored = []
    for s in sections:
        score = sum(math.log(1 + docs / freq[w]) * (3 if w in heavy else 1) for w in allw & s["words"])
        title_hit = sum(math.log(1 + docs / freq[w]) * 3 for w in allw & _words(s["title"]))      # a matching section title is a strong sign
        scored.append((score + title_hit, s))
    scored.sort(key=lambda x: -x[0])
    return [(round(sc, 1), s) for sc, s in scored[:n] if sc >= floor]


def _equations(section, limit=2):
    """The first display equations of a section, as TeX with the note's macros expanded."""
    eqs = []
    for m in re.finditer(r"\\\[(.+?)\\\]", section["html"], re.S):
        tex = macros.expand(_html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip(), section["defs"])
        tex = re.sub(r"\\text\{\s*\(.*?\)\s*\}", "", tex)                            # drop equation labels
        if 8 < len(tex) < 220:
            eqs.append(tex)
        if len(eqs) >= limit:
            break
    return eqs


def hint_for(section, books):
    """A hint built from a matching section: where to look, its main idea and its first formulas."""
    book = next((b for b in books if b["id"] == section["book"]), None)
    lec = book.get("lecture") if book else None
    where = section_label(section, book) + " · " + tex(section["title"], section["defs"])
    md = f"**Where to look:** {where}"
    first = re.sub(r"\s+", " ", re.sub(r"<(?!/?su[pb]\b)[^>]+>", " ", re.search(r"<p[^>]*>(.*?)</p>", section["html"], re.S).group(1))).strip() \
        if re.search(r"<p[^>]*>(.*?)</p>", section["html"], re.S) else ""
    if first:
        md += "\n\n" + tex(first, section["defs"], 260)
    eqs = _equations(section)
    if eqs:
        md += "\n\n**Start from:**\n\n" + "\n\n".join(f"$${e}$$" for e in eqs)
    return md


def written_hints(course_code, hw_title):
    """Hand-written hints for a homework: {'2a': {'hint': ...}, ...} from homework/<course>/<title>.json, if present."""
    safe = lambda s: re.sub(r"[^A-Za-z0-9 _.-]+", "", s).strip() or "hw"
    path = ROOT / safe(course_code) / f"{safe(hw_title)}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


_CUES = [
    (r"(write[^.]{0,40}(program|code|script)|programming assignment|\bnumerical|\biterat)",
     "Plan the program before coding it. Write the equation you need to solve, choose the numerical method and its stopping test, "
     "code it in small steps, check it against a case you can do by hand, then plot or tabulate the result and say what it shows."),
    (r"\b(plot|graph|sketch|draw|figure)\b",
     "Plot it. Choose the quantity for each axis and a range that shows the behaviour, compute the points (with a short program if there are "
     "many), label the axes with units, and say in a sentence what the curve shows."),
    (r"\b(derive|show that|prove|demonstrate)\b",
     "Start from the definition or the governing equation. Change one thing per line, say what you used, and stop when you reach exactly the "
     "form the problem asks for."),
    (r"\b(is it|are they|is there|can the|can it|does the|does it|would|will the)\b[^?]*\?",
     "Decide yes or no first, then support it: list each condition that has to hold, check each with the numbers given, and say which one "
     "decides the answer."),
    (r"\b(explain|explanation|why|justify|justification|discuss|comment|reason|physically|interpret|argue|convincing)\b",
     "Name the principle or condition that decides the answer, check it against the numbers you are given, and then state the conclusion "
     "in one sentence."),
    (r"\b(compare|which|greater|larger|smaller|more|less|increase|decrease|higher|lower)\b",
     "Get the same quantity for each case with the same method, so the only difference is the case; then compare the two numbers (or their "
     "signs) and say which wins and why."),
    (r"\b(implication|implications|meaning|consequence)\b",
     "Say what the result means: its size compared with something you know, its sign, how it changes with the inputs, and one limit where "
     "you can check it."),
    (r"\b(how many|how much|calculate|compute|find|determine|what is|estimate|evaluate|solve|number of)\b",
     "Write the governing equation first and list what is given and what is unknown. Solve for the unknown symbolically, then put in "
     "numbers with units and check the size of the result."),
]


def approach(text, title=""):
    """A short, answer-free first step for a problem or sub-problem, from what it asks (plot, explain, compare, derive, calculate)."""
    blob = f"{title} {text}".lower()
    for pattern, hint in _CUES:
        if re.search(pattern, blob):
            return hint
    return "Re-read what is asked, write down what is given and what is unknown, and name the equation or principle that connects them."


def with_approach(text, title, section_hint):
    """The hint shown for a problem: how to start, then where in the notes to look (when a section matches)."""
    md = f"**How to start:** {approach(text, title)}"
    if section_hint:
        md += chr(10) * 2 + section_hint
    return md


def _whole_assignment(path):
    """For a homework with no numbered problems (one programming assignment, say): the whole file as a single problem."""
    try:
        doc = pymupdf.open(path)
        text = clean("\n".join(pg.get_text() for pg in doc))
    except Exception:
        return []
    if len(text) < 40:
        return []
    first = next((ln.strip() for ln in text.split(". ") if ln.strip()), "Assignment")
    return [{"id": "1", "title": " ".join(first.split()[:8]) or "Assignment", "page": 1, "text": text[:400], "parts": []}]


def analyze(book, course, books):
    """Problems of a homework PDF with the matching note sections and hints.
    [{id, title, page, tags, hint, parts: [{id, page, text, tags, hint}]}]"""
    path = BASE_DIR / book["pdf_path"]
    problems = parse_problems(str(path), path.stat().st_mtime) or _whole_assignment(path)
    sections = course_sections(course["id"], books)
    examples = course_examples(course["id"], books)
    by_book = {b["id"]: b for b in books}

    def example_tags(text, title):
        """Up to two worked examples of the notes that look like this problem: (button label, note id, example id)."""
        out = []
        for _, ex in best_sections(text, examples, 2, boost=title, floor=EXAMPLE_FLOOR):
            b = by_book.get(ex["book"], {})
            lec = f" (Lec {b['lecture']})" if b.get("lecture") else ""
            out.append((f"Example {ex['num']} · {tex(ex['title'], ex.get('defs'))}{lec}", ex["book"], ex["sec"]))
        return out
    hand = written_hints(course["code"] or course["name"], book["title"])

    def tag(sec):
        b = by_book.get(sec["book"], {})
        return (section_label(sec, b) + " · " + tex(sec["title"], sec.get("defs")), sec["book"], sec["sec"])

    out = []
    for pr in problems:
        whole = best_sections(pr["text"], sections, 2, boost=pr["title"])
        item = {"id": pr["id"], "title": pr["title"], "page": pr["page"], "tags": [tag(s) for _, s in whole], "examples": example_tags(pr["text"], pr["title"]),
                "hint": (hand.get(pr["id"], {}).get("hint")
                         or with_approach(pr["text"], pr["title"], hint_for(whole[0][1], books) if whole else "")), "parts": []}
        for part in pr["parts"]:
            m = best_sections(part["text"], sections, 2, boost=pr["title"]) or whole
            if m and whole and m[0][1]["sec"] != whole[0][1]["sec"] or (m and whole and m[0][1]["book"] != whole[0][1]["book"]):
                # a sub-problem leaves its problem's section only when another section is clearly better on its own words
                own = dict((id(s), sc) for sc, s in best_sections(part["text"], sections, len(sections), boost=pr["title"], floor=0.0))
                if m[0][0] < 14 or own.get(id(whole[0][1]), 0) * 2.2 >= m[0][0]:       # low confidence, or not clearly better
                    m = whole
            key = pr["id"] + part["id"]
            item["parts"].append({"id": part["id"], "page": part["page"], "text": part["text"][:240],
                                  "tags": [tag(s) for _, s in m], "examples": example_tags(part["text"], pr["title"]),
                                  "hint": hand.get(key, {}).get("hint")
                                  or with_approach(part["text"], pr["title"], hint_for(m[0][1], books) if m else "")})
        out.append(item)
    return out


def clean(text):
    """Homework text for display: private-use symbol-font glyphs from the PDF dropped, spaces tidied."""
    return re.sub(r"\s+", " ", re.sub(r"[\ue000-\uf8ff\ufe00-\ufe0f]", "", text)).strip()


def _cut(text, n):
    """Text shortened to about n characters, never inside a $...$ formula."""
    if len(text) <= n:
        return text
    i = text.rfind(" ", 0, n)
    cut = text[:i if i > 0 else n].rstrip()
    while cut.count("$") % 2:                                  # an open formula: back up to before it
        cut = cut[:cut.rfind("$")].rstrip()
    return cut + "\u2026"


def tex(text, defs=None, limit=None):
    """Text for display with every formula as LaTeX between $ signs: the notes' macros expanded, Unicode math (psi, hbar,
    dagger, x squared) converted, \\( \\) turned into $ $, and sub/superscript tags into TeX."""
    text = re.sub(r"<su([pb])>(.*?)</su[pb]>", lambda m: "$" + ("^" if m.group(1) == "p" else "_") + "{" + m.group(2) + "}$", text)
    text = re.sub(r"</?(?:i|em|b|strong|span|code)[^>]*>", "", text)
    text = _html.unescape(macros.expand(text, defs or {}))
    text = re.sub(r"\\\((.+?)\\\)", lambda m: "$" + m.group(1).strip() + "$", text, flags=re.S)
    text = re.sub(r"(?<![\w/])1\s+\u221a\s+(\d+)", lambda m: "1/\u221a" + m.group(1), text)      # 1 over the square root of 2, split over lines in the PDF
    text = re.sub(r"\s*\((\d{1,3})\)(?=\s*(?:[|\u2223A-Z]|$))", "", text)           # equation numbers "(10)" copied from the PDF
    text = unitex.convert(text)
    parts = re.split(r"(\$[^$]*\$)", text)                                       # plain text outside the math: a1, a2 -> $a_1$, $a_2$
    text = "".join(x if x.startswith("$") else re.sub(r"(?<![\w\\])([a-z])([1-3])(?![\w])", r"$\1_\2$", x) for x in parts)
    return _cut(text, limit) if limit else text
