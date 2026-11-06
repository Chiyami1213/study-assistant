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
            for line in page.get_text().splitlines():
                if line.strip():
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
        if bare and int(bare.group(1)) == want and TITLE.match(nxt):      # "2" then "2D WKB"; not a fraction's "2" then "d"
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
    return problems


@lru_cache(maxsize=16)
def _sections(paths_key):
    """Every content section of the course's HTML notes: [{book, note, sec, title, num, text, html}]."""
    out = []
    for book_id, path, mtime in paths_key:
        text = open(path, encoding="utf-8", errors="replace").read()
        for sec in quizgen.sections_of(text):
            m = re.search(r'<section id="' + re.escape(sec["id"]) + r'"[^>]*>(.*?)</section>', text, re.S)
            out.append({"book": book_id, "sec": sec["id"], "title": sec["title"], "num": sec["num"], "label": sec.get("label"),
                        "text": sec["text"],
                        "html": m.group(1) if m else "", "words": _words(sec["title"] + " " + sec["text"]),
                        "defs": macros.from_html(text)})
    return out


def course_sections(course_id, books):
    """The sections of all HTML notes of a course (cached by file time)."""
    key = []
    for b in books:
        if course_id in b["course_ids"] and b["kind"] in ("Notes", "Lecture Notes") and b["pdf_path"].lower().endswith((".html", ".htm")):
            p = BASE_DIR / b["pdf_path"]
            if p.exists():
                key.append((b["id"], str(p), p.stat().st_mtime))
    return _sections(tuple(key))


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
    where = (section.get("label") or ((f"{lec}." if lec else "§") + str(section["num"]))) + " · " + section["title"]
    md = f"**Where to look:** {where}"
    first = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.search(r"<p[^>]*>(.*?)</p>", section["html"], re.S).group(1))).strip() \
        if re.search(r"<p[^>]*>(.*?)</p>", section["html"], re.S) else ""
    if first:
        first = unitex.convert(macros.expand(_html.unescape(first), section["defs"]))
        first = re.sub(r"\\\((.+?)\\\)", lambda m: "$" + m.group(1).strip() + "$", first)
        md += f"\n\n{first[:260]}{'…' if len(first) > 260 else ''}"
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


def analyze(book, course, books):
    """Problems of a homework PDF with the matching note sections and hints.
    [{id, title, page, tags, hint, parts: [{id, page, text, tags, hint}]}]"""
    path = BASE_DIR / book["pdf_path"]
    problems = parse_problems(str(path), path.stat().st_mtime)
    sections = course_sections(course["id"], books)
    by_book = {b["id"]: b for b in books}
    hand = written_hints(course["code"] or course["name"], book["title"])

    def tag(sec):
        b = by_book.get(sec["book"], {})
        return ((sec.get("label") or ((f"{b.get('lecture')}." if b.get("lecture") else "§") + str(sec["num"])))
                + " · " + sec["title"], sec["book"], sec["sec"])

    out = []
    for pr in problems:
        whole = best_sections(pr["text"], sections, 2, boost=pr["title"])
        item = {"id": pr["id"], "title": pr["title"], "page": pr["page"], "tags": [tag(s) for _, s in whole],
                "hint": (hand.get(pr["id"], {}).get("hint") or (hint_for(whole[0][1], books) if whole else "")), "parts": []}
        for part in pr["parts"]:
            m = best_sections(part["text"], sections, 2, boost=pr["title"]) or whole
            if m and whole and m[0][1]["sec"] != whole[0][1]["sec"] or (m and whole and m[0][1]["book"] != whole[0][1]["book"]):
                # a sub-problem leaves its problem's section only when another section is clearly better on its own words
                own = dict((id(s), sc) for sc, s in best_sections(part["text"], sections, len(sections), boost=pr["title"], floor=0.0))
                if m[0][0] < 14 or own.get(id(whole[0][1]), 0) * 2.2 >= m[0][0]:       # low confidence, or not clearly better
                    m = whole
            key = pr["id"] + part["id"]
            item["parts"].append({"id": part["id"], "page": part["page"], "text": part["text"][:240],
                                  "tags": [tag(s) for _, s in m],
                                  "hint": hand.get(key, {}).get("hint") or (hint_for(m[0][1], books) if m else "")})
        out.append(item)
    return out


def clean(text):
    """Homework text for display: private-use symbol-font glyphs from the PDF dropped, spaces tidied."""
    return re.sub(r"\s+", " ", re.sub(r"[\ue000-\uf8ff]", "", text)).strip()
