"""Helpers for writing conceptual check questions for the sections of the HTML notes.

`sections_of(html)` lists the content sections of a note with a suggested number of questions (1 to 3, from the
section's length and how much it contains). The questions themselves are written into
quizzes/<course code>/<note title>.json (plain files, so Claude in VS Code can write them):

    {"book": 16, "title": "Complex Numbers Review",
     "sections": [{"id": "euler", "title": "Euler's formula and polar form",
                   "questions": [{"q": "...", "o": ["...", "..."], "a": 1, "e": "why"}]}]}

Text uses $...$ for math. Write the right answer first: the Quiz tab shuffles the options (the same way each time).
The Quiz tab adds these questions to the note's own Self-check questions."""
import html as _html
import json
import random
import re

import macros
from database import BASE_DIR

ROOT = BASE_DIR / "quizzes"
SKIP = re.compile(r"notes check|errata|self-check|quiz", re.I)       # not content sections


def _text(fragment):
    fragment = re.sub(r"<(script|style)\b.*?</\1>", "", fragment, flags=re.S | re.I)
    fragment = re.sub(r"</?[A-Za-z][^>]*>", " ", fragment)
    return re.sub(r"\s+", " ", _html.unescape(fragment)).strip()


def suggested(chars, derivs, equations):
    """1 to 3 questions: more for long sections and for those with many derivations or equations."""
    score = chars / 2200 + derivs * 0.6 + equations / 12
    return 1 if score < 1.4 else 2 if score < 2.6 else 3


def sections_of(html_text):
    """[{id, title, text, chars, derivs, equations, suggested}] for the content sections of a note."""
    out = []
    for m in re.finditer(r'<section id="([^"]+)"[^>]*>(.*?)</section>', html_text, re.S):
        h = re.search(r"<h2[^>]*>(.*?)</h2>", m.group(2), re.S)
        title = _text(re.sub(r'<span class="(?:num|slides|sn)">.*?</span>', "", h.group(1), flags=re.S)) if h else m.group(1)
        num = re.search(r"§\s*(\d+)", _text(h.group(1))) if h else None
        sn = re.search(r'<span class="sn">\s*(\d+)\.(\d+)', h.group(1)) if h else None      # "4.1 · Lec 4-2": lecture.section
        if sn and not num:
            num = type("N", (), {"group": lambda self, i: sn.group(2)})()
        if SKIP.search(title) or m.group(1).lower() in ("check", "quiz", "errata", "selfcheck"):
            continue
        body = m.group(2)
        derivs = len(re.findall(r'class="deriv"', body))
        equations = len(re.findall(r"\\\[", body))
        text = _text(body)
        out.append({"id": m.group(1), "num": int(num.group(1)) if num else len(out) + 1, "title": title,
                    "label": f"{sn.group(1)}.{sn.group(2)}" if sn else None, "text": text, "chars": len(text), "derivs": derivs,
                    "equations": equations, "suggested": suggested(len(text), derivs, equations)})
    return out


_STOP = set("that this with from have does what which when where there their then than into only each both about "
            "would could should these those equals equal also because while after before over under must same other more most".split())


def _tokens(text):
    return {w for w in re.findall(r"[a-z]{4,}", text.lower()) if w not in _STOP}


def match_section(question_text, sections):
    """The section of a note that a question most likely belongs to (shared rare words weigh most), or None."""
    import math
    if not sections:
        return None
    sets = [_tokens(x["text"]) for x in sections]
    q = _tokens(question_text)
    best, best_score = None, 0.0
    for sec, toks in zip(sections, sets):
        score = sum(math.log(1 + len(sets) / sum(w in t for t in sets)) for w in q & toks)
        if score > best_score:
            best, best_score = sec, score
    return best if best_score >= 3.0 else None


def path_for(course_code, title):
    safe = lambda s: re.sub(r"[^A-Za-z0-9 _.-]+", "", s).strip() or "note"
    return ROOT / safe(course_code) / f"{safe(title)}.json"


def load(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def questions(data):
    """Flat list of questions from a quiz file, each tagged with its section title."""
    out = []
    for sec in (data or {}).get("sections", []):
        for q in sec.get("questions", []):
            if isinstance(q.get("o"), list) and isinstance(q.get("a"), int) and 0 <= q["a"] < len(q["o"]):
                order = list(range(len(q["o"])))
                random.Random(q["q"]).shuffle(order)                     # the right answer is not always first
                fix = macros.expand
                out.append({"kind": "mc", "q": fix(q["q"]), "o": [fix(q["o"][i]) for i in order], "a": order.index(q["a"]),
                            "e": fix(q.get("e", "")), "h": fix(q.get("h", "")),
                            "tag": f"§ {sec['title']}", "sec": sec.get("id")})
    return out
