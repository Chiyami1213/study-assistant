"""Best-effort detection of a PDF's title, author, edition/year and page count."""
import html as _html
import io
import re
from datetime import datetime

JUNK_TITLES = re.compile(r"^(untitled|microsoft word|document\d*|slide|presentation|\.?pdf|scan|print)\b", re.I)
EDITION_RE = re.compile(r"\b(\d{1,2})\s?(?:st|nd|rd|th)\s+(?:ed\.?|edition)\b|\bedition\s*(\d{1,2})\b", re.I)
WORD_EDITIONS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7,
                 "eighth": 8, "ninth": 9, "tenth": 10, "eleventh": 11, "twelfth": 12}
WORD_EDITION_RE = re.compile(r"\b(" + "|".join(WORD_EDITIONS) + r")\s+edition\b", re.I)
YEAR_RE = re.compile(r"(?:\u00a9|copyright|\(c\))\s*(?:by\s+)?(?:[A-Za-z .,&]+?\s)?((?:19|20)\d{2})", re.I)


def _ordinal(n):
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _clean_title(text):
    text = re.sub(r"\.pdf$", "", text or "", flags=re.I)
    text = re.sub(r"[_]+", " ", text).strip()
    return text


def extract_info(data, filename=""):
    """Return dict(title, author, edition, pages, source) from raw PDF bytes; fields may be empty."""
    info = {"title": "", "author": "", "edition": "", "year": "", "pages": None, "source": "filename"}
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
    except Exception:
        info["title"] = _clean_title(filename.rsplit(".", 1)[0] if filename else "")
        return info

    try:
        info["pages"] = len(reader.pages)
    except Exception:
        pass

    meta = {}
    try:
        meta = reader.metadata or {}
    except Exception:
        pass
    title = (meta.get("/Title") or "").strip() if meta else ""
    author = (meta.get("/Author") or "").strip() if meta else ""
    if title and not JUNK_TITLES.match(title) and len(title) > 2:
        info["title"], info["source"] = _clean_title(title), "PDF metadata"
    if author and author.lower() not in ("unknown", "admin", "user"):
        info["author"] = author

    # Look for an edition / copyright year in the first few pages
    text = ""
    try:
        for page in list(reader.pages)[:4]:
            text += (page.extract_text() or "") + "\n"
    except Exception:
        pass
    m = EDITION_RE.search(text)
    if m:
        info["edition"] = f"{_ordinal(int(m.group(1) or m.group(2)))} Edition"
    else:
        w = WORD_EDITION_RE.search(text)
        if w:
            info["edition"] = f"{_ordinal(WORD_EDITIONS[w.group(1).lower()])} Edition"
    year = ""
    y = YEAR_RE.search(text)
    if y:
        year = y.group(1)
    elif meta and meta.get("/CreationDate"):
        cd = re.search(r"D:(\d{4})", str(meta.get("/CreationDate")))
        year = cd.group(1) if cd and 1900 < int(cd.group(1)) <= datetime.now().year else ""
    info["year"] = year

    if not info["title"]:
        info["title"] = _clean_title(filename.rsplit(".", 1)[0] if filename else "")
    return info


def extract_html_info(data, filename=""):
    """Title / author / edition / year from an HTML file (title tag, meta tags, visible text)."""
    text = data.decode("utf-8", errors="replace")
    info = {"title": "", "author": "", "edition": "", "year": "", "pages": None, "source": "filename"}
    m = re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S)
    if m and m.group(1).strip():
        info["title"], info["source"] = _clean_title(re.sub(r"\s+", " ", _html.unescape(m.group(1))).strip()), "HTML title"
    a = re.search(r"<meta[^>]+name=[\"']author[\"'][^>]*content=[\"']([^\"']*)", text, re.I) or         re.search(r"<meta[^>]+content=[\"']([^\"']*)[\"'][^>]*name=[\"']author[\"']", text, re.I)
    if a and a.group(1).strip():
        info["author"] = _html.unescape(a.group(1)).strip()
    visible = re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>", " ", text[:200000], flags=re.I | re.S)
    visible = _html.unescape(visible)
    ed = EDITION_RE.search(visible)
    if ed:
        info["edition"] = f"{_ordinal(int(ed.group(1) or ed.group(2)))} Edition"
    elif WORD_EDITION_RE.search(visible):
        info["edition"] = f"{_ordinal(WORD_EDITIONS[WORD_EDITION_RE.search(visible).group(1).lower()])} Edition"
    y = YEAR_RE.search(visible)
    if y:
        info["year"] = y.group(1)
    if not info["title"]:
        info["title"] = _clean_title(filename.rsplit(".", 1)[0] if filename else "")
    return info


LECTURE_RE = re.compile(r"^\s*Lec(?:ture)?s?\.?\s*(\d+)(?:\s*[-\u2013\u2014]\s*(\d+))?\s*[:\-\u2013\u2014.]*\s*", re.I)


def split_lecture(title):
    """('3-4', 'Rest of title') for 'Lec 3-4 Rest of title'; ('', title) when there is no leading lecture number."""
    m = LECTURE_RE.match(title or "")
    if not m:
        return "", (title or "").strip()
    lecture = m.group(1) + (f"-{m.group(2)}" if m.group(2) else "")
    return lecture, (title[m.end():].strip() or title.strip())


CHAPTER_RE = re.compile(r"(?<![A-Za-z])(?:chapter|chap|ch)\.?[\s_\-]*(\d+)(?!\d)", re.I)


def guess_lecture(*texts):
    """The lecture (chapter) number a file name or title names: 'Lec 3-4 ...' -> '3-4', 'AE6765 Chapter 3 Notes' -> '3', 'Ch2' -> '2'; '' if none.
    The notes of a course are found by this number (a note link 'Lec 3 s2.1' or 'Ch3', the Notes tab order), so an imported note should have it."""
    for text in texts:
        text = (text or "").replace("_", " ")
        lec = split_lecture(text)[0]
        if lec:
            return lec
        m = CHAPTER_RE.search(text)
        if m:
            return m.group(1)
    return ""


NOTES_PREFIX_RE = re.compile(r"^\s*Notes?\s*[:\-–—]?\s+", re.I)


def strip_notes_prefix(title):
    """'Notes Fundamentals' -> 'Fundamentals'. A title that is only 'Notes' is left as it is."""
    stripped = NOTES_PREFIX_RE.sub("", title or "", count=1).strip()
    return stripped or (title or "").strip()
