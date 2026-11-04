"""Best-effort detection of a PDF's title, author, edition/year and page count."""
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
    info = {"title": "", "author": "", "edition": "", "pages": None, "source": "filename"}
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
    if year:
        info["edition"] = f"{info['edition']} ({year})" if info["edition"] else year

    if not info["title"]:
        info["title"] = _clean_title(filename.rsplit(".", 1)[0] if filename else "")
    return info
