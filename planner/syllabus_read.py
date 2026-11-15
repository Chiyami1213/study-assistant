"""Reads the work and the class times out of the text of a syllabus. Pure: no database, no UI.

`find_items(text, first, last)` returns the dated work it finds (homework, quizzes, exams, projects) as ImportItems, `find_meetings(text)` the weekly class times.
It is a reader of plain text, so it guesses: every row it returns is shown to the student to check and change before anything is saved."""
import re
from dataclasses import dataclass
from datetime import date, timedelta

MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
_MONTH = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
NAME_DATE = re.compile(rf"\b(?P<month>{_MONTH})\.?\s+(?P<day>\d{{1,2}})(?:st|nd|rd|th)?\b(?:,?\s*(?P<year>20\d\d))?", re.I)
DAY_FIRST = re.compile(rf"\b(?P<day>\d{{1,2}})(?:st|nd|rd|th)?\s+(?P<month>{_MONTH})\b\.?(?:,?\s*(?P<year>20\d\d))?", re.I)
NUM_DATE = re.compile(r"(?<![\d/])(?P<month>\d{1,2})/(?P<day>\d{1,2})(?:/(?P<year>\d{2,4}))?(?![\d/])")
TIME = re.compile(r"\b(?P<h>\d{1,2})(?::(?P<m>\d{2}))?\s*(?P<ap>[ap])\.?m\b\.?", re.I)

# what counts as work, by category; the first pattern that matches a piece of text names the item
KEYWORDS = (
    ("Exam", re.compile(r"\b(final\s+exam|midterm(?:\s+exam)?|mid-term(?:\s+exam)?|exam|test)(?:\s*#?\s*(\d+))?\b", re.I)),
    ("Quiz", re.compile(r"\b(quiz(?:zes)?)(?:\s*#?\s*(\d+))?\b", re.I)),
    ("Homework", re.compile(r"\b(homework|hw|problem\s+set|pset|assignment|ps)(?:\s*#?\s*(\d+))?\b", re.I)),
    ("Project", re.compile(r"\b(project(?:\s+(?:proposal|report|presentation|milestone))?|lab\s+report|term\s+paper|paper|presentation|proposal)(?:\s*#?\s*(\d+))?\b", re.I)),
)
SKIP = re.compile(r"\b(no\s+class|holiday|break|office\s+hours?|policy|policies|grading|grade\s+breakdown|weighted|percent|%)\b", re.I)
DEFAULT_TIME = {"Exam": "09:00"}
END_OF_DAY = "23:59"


@dataclass(frozen=True)
class ImportItem:
    title: str
    category: str
    due: date
    time: str = ""             # "HH:MM" or "" (the usual time of the category is used)
    source: str = ""           # the text it was read from, to check it

    @property
    def due_time(self):
        return self.time or DEFAULT_TIME.get(self.category, END_OF_DAY)


@dataclass(frozen=True)
class MeetingGuess:
    days: tuple                # Monday = 0
    start: str
    end: str
    location: str = ""
    source: str = ""


def _clock(h, m, ap):
    h, m = int(h), int(m or 0)
    ap = (ap or "").lower()
    if ap == "p" and h < 12:
        h += 12
    if ap == "a" and h == 12:
        h = 0
    return f"{h:02d}:{m:02d}"


def _year_for(month, day, year, first, last):
    """The year of a date written without one: the one that puts it in or nearest to the term (first..last)."""
    if year:
        year = int(year)
        return year + 2000 if year < 100 else year
    best = None
    for y in (first.year - 1, first.year, first.year + 1, last.year, last.year + 1):
        try:
            d = date(y, month, day)
        except ValueError:
            continue
        gap = 0 if first - timedelta(days=21) <= d <= last + timedelta(days=21) else min(abs((d - first).days), abs((d - last).days))
        if best is None or gap < best[0]:
            best = (gap, y)
    return best[1] if best else first.year


def _dates(text, first, last):
    """[(position, date)] of the dates written in the text."""
    found = []
    taken = []
    for rx in (NAME_DATE, DAY_FIRST, NUM_DATE):
        for m in rx.finditer(text):
            if any(a < m.end() and m.start() < b for a, b in taken):
                continue
            raw = m.group("month")
            month = int(raw) if raw.isdigit() else MONTHS[raw[:3].lower()]
            day = int(m.group("day"))
            if not (1 <= month <= 12 and 1 <= day <= 31):
                continue
            try:
                found.append((m.start(), date(_year_for(month, day, m.group("year"), first, last), month, day)))
            except ValueError:
                continue
            taken.append((m.start(), m.end()))
    return sorted(found)


def _title(category, word, number):
    word = re.sub(r"\s+", " ", word).strip()
    small = {"hw": "HW", "pset": "Problem Set", "ps": "PS"}
    word = small.get(word.lower()) or " ".join(w.capitalize() for w in word.replace("mid-term", "midterm").split())
    if category == "Exam" and word.lower() == "test":
        word = "Test"
    return f"{word} {number}".strip() if number else word


def find_items(text, first, last):
    """The dated work in a syllabus text. A date and what is due on it may be on one line or on neighboring lines (a table row split by the PDF): every date takes the
    words up to the next date. `first`/`last`: the term, to give a date written without a year its year. Items are in date order, once each."""
    lines = [re.sub(r"\s+", " ", l).strip() for l in text.splitlines()]
    lines = [l for l in lines if l]
    out, seen = [], set()
    i = 0
    while i < len(lines):
        if not _dates(lines[i], first, last):
            i += 1
            continue
        segment = [lines[i]]
        j = i + 1
        while j < len(lines) and j < i + 4 and not _dates(lines[j], first, last):
            segment.append(lines[j])
            j += 1
        block = " ".join(segment)
        dated = _dates(block, first, last)
        day = dated[0][1]
        words = block
        times = TIME.findall(block)
        when = _clock(*times[0]) if times else ""
        hit = False
        for category, rx in KEYWORDS:
            for m in rx.finditer(words):
                if SKIP.search(words[max(0, m.start() - 25):m.end() + 25]) and category in ("Project", "Exam") and not re.search(r"\bdue|exam\s*\d|midterm|final", words, re.I):
                    continue
                title = _title(category, m.group(1), m.group(2))
                key = (title.lower(), day)
                if key in seen:
                    continue
                seen.add(key)
                out.append(ImportItem(title, category, day, when, block[:140]))
                hit = True
            if hit and category == "Exam":
                break                                    # "Midterm Exam 1" is one exam, not also a test and a quiz
        i = j
    out.sort(key=lambda x: (x.due, x.title))
    return out


# ---------------------------------------------------------------- class times
_DAYS = {"mon": 0, "tue": 1, "tues": 1, "wed": 2, "thu": 3, "thur": 3, "thurs": 3, "fri": 4, "sat": 5, "sun": 6}
_DAY_WORD = re.compile(r"\b(mon|tues?|wed|thu(?:rs?)?|fri|sat|sun)(?:day|sday|nesday|rsday|urday)?s?\b", re.I)
_CODE = re.compile(r"\b(?P<code>[MTWRFSU]{1,5})\b")
_CODE_DAY = {"M": 0, "T": 1, "W": 2, "R": 3, "F": 4, "S": 5, "U": 6}
_RANGE = re.compile(r"(?P<h1>\d{1,2})(?::(?P<m1>\d{2}))?\s*(?P<a1>[ap]\.?m\.?)?\s*(?:-|–|—|to)\s*(?P<h2>\d{1,2})(?::(?P<m2>\d{2}))?\s*(?P<a2>[ap]\.?m\.?)", re.I)
_CLASSY = re.compile(r"\b(lecture|class|meets?|meeting|time|schedule|section|lab|recitation)\b", re.I)
_ROOM = re.compile(r"\b(?:Room|Rm\.?|Location|Where)[: ]+(?P<room>[A-Z0-9][\w .-]{1,24}?)(?=[,;]| \d{1,2}[:\s]| [A-Z][a-z]+day|$)")


def find_meetings(text):
    """The weekly class times named in a syllabus text: days (words such as Tuesday and Thursday, or codes such as MWF and TR) and a time range, on a line that speaks of a
    lecture, a class or a meeting. Each pair is returned once."""
    out, seen = [], set()
    for line in (re.sub(r"\s+", " ", l).strip() for l in text.splitlines()):
        rng = _RANGE.search(line)
        if not rng or not _CLASSY.search(line):
            continue
        days = {_DAYS.get(m.group(1).lower()) if m.group(1).lower() in _DAYS else _DAYS[m.group(1).lower()[:3]] for m in _DAY_WORD.finditer(line)}
        if not days:
            code = next((m.group("code") for m in _CODE.finditer(line) if len(m.group("code")) >= 2 and set(m.group("code")) <= set("MTWRF")), None)
            if code:
                days = {_CODE_DAY[c] for c in code}
        if not days:
            continue
        a2 = rng.group("a2")
        a1 = rng.group("a1") or a2
        start = _clock(rng.group("h1"), rng.group("m1"), a1[0] if a1 else "")
        end = _clock(rng.group("h2"), rng.group("m2"), a2[0])
        if end <= start:
            start = _clock(rng.group("h1"), rng.group("m1"), "a")
        room = _ROOM.search(line)
        key = (tuple(sorted(days)), start, end)
        if key not in seen:
            seen.add(key)
            out.append(MeetingGuess(key[0], start, end, room.group("room").strip() if room else "", line[:140]))
    return out
