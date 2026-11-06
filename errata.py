"""Errata from the Claude-generated HTML notes ("Notes check": <ol class="errata">), placed on the PDF they correct.

Each erratum has a location label ("Eq. 490 (signs)", "Eqs. 468-471", "Typos"). Equation numbers are found in the PDF
as right-aligned tags such as "(490)"; typos are found by searching their quoted text. The result is a list of marks
(page + rectangle) the reader draws over the page."""
import html as _html
import re
from functools import lru_cache

import macros
import unitex

try:
    import pymupdf
except ImportError:  # older PyMuPDF versions expose it as fitz
    import fitz as pymupdf


def _plain(inner, defs=None):
    """Markdown for an erratum body: TeX delimiters for Streamlit, italics kept, other tags dropped."""
    text = re.sub(r"</?i>", "*", macros.expand(inner, defs))
    text = re.sub(r"</?[A-Za-z][^>]*>", "", text)
    text = _html.unescape(text)
    text = re.sub(r"\\\((.+?)\\\)", lambda m: f"${m.group(1).strip()}$", text, flags=re.S)
    text = re.sub(r"\\\[(.+?)\\\]", lambda m: f"$${m.group(1).strip()}$$", text, flags=re.S)
    text = text.replace(chr(92) + ",'", chr(92) + ",{}'").replace(chr(92) + ",^", chr(92) + ",{}^")   # KaTeX needs a base here
    return unitex.convert(re.sub(r"\s+", " ", text).strip())


def parse(html_text):
    """[{n, where, md}] from the errata list of an HTML note (empty if it has none)."""
    m = re.search(r'<ol class="errata">(.*?)</ol>', html_text or "", re.S)
    if not m:
        return []
    out, defs = [], macros.from_html(html_text)
    for i, li in enumerate(re.findall(r"<li>(.*?)</li>", m.group(1), re.S), 1):
        w = re.search(r'<span class="where">(.*?)</span>', li, re.S)
        where = _plain(w.group(1), defs) if w else ""
        body = _plain(li[w.end():] if w else li, defs)
        out.append({"n": i, "where": where, "md": body})
    return out


@lru_cache(maxsize=8)
def _equation_tags(path, mtime):
    """{equation number: [(page index, rect, page size)]} from right-aligned "(123)" tags on every page."""
    tags = {}
    with pymupdf.open(path) as doc:
        for i, page in enumerate(doc):
            W, H = page.rect.width, page.rect.height
            for w in page.get_text("words"):
                m = re.fullmatch(r"\((\d{1,4})\)", w[4])
                if m and w[0] > W * 0.65:
                    tags.setdefault(int(m.group(1)), []).append((i, (w[0], w[1], w[2], w[3]), (W, H)))
    return tags


def _numbers(where):
    """Equation numbers named in a location: "Eq. 490", "Eqs. 468-471" (both ends), "Below Eq. 438"."""
    nums = []
    for m in re.finditer(r"Eqs?\.?\s*(\d{1,4})(?:\s*[–\-]\s*(\d{1,4}))?", where):
        nums.append(int(m.group(1)))
        if m.group(2):
            nums.append(int(m.group(2)))
    return list(dict.fromkeys(nums))


def _typos(item):
    """[(quoted text, page number or None)] from a "Typos" erratum, e.g. “cofficients” (p. 106)."""
    found = []
    for m in re.finditer(r"[“\"]([^”\"]{3,60})[”\"](?:\s*\(p\.?\s*(\d+)\))?", item["md"]):
        found.append((m.group(1), int(m.group(2)) if m.group(2) else None))
    return found


def locate(path, mtime, items):
    """Marks for the errata that can be placed in this PDF: {n, label, md, page, rect, size}."""
    path = str(path)
    marks = []
    tags = None
    doc = None
    try:
        for it in items:
            nums = _numbers(it["where"])
            if nums:
                tags = tags if tags is not None else _equation_tags(path, mtime)
                for k in nums:
                    for page, r, size in tags.get(k, [])[:1]:                     # the first tag with that number
                        W = size[0]
                        marks.append({"n": it["n"], "label": it["where"], "md": it["md"], "page": page, "size": size,
                                      "rect": (W * 0.1, r[1] - 16, r[2] + 4, r[3] + 12)})
            elif re.search(r"§\s*\d+\.\d+", it["where"]):
                sec = re.search(r"§\s*(\d+\.\d+)", it["where"]).group(1)
                doc = doc or pymupdf.open(path)
                for i in range(doc.page_count):                              # the heading "14.2 ..." at the left margin
                    hit = next((r for r in doc[i].search_for(sec) if r.x0 < doc[i].rect.width * 0.25), None)
                    if hit:
                        W = doc[i].rect.width
                        marks.append({"n": it["n"], "label": it["where"], "md": it["md"], "page": i,
                                      "size": (W, doc[i].rect.height), "rect": (hit.x0 - 4, hit.y0 - 3, W * 0.9, hit.y1 + 3)})
                        break
            elif "typo" in it["where"].lower():
                doc = doc or pymupdf.open(path)
                for text, pg in _typos(it):
                    pages = [pg - 1] if pg and 0 < pg <= doc.page_count else range(doc.page_count)
                    for i in pages:
                        hits = doc[i].search_for(text)
                        if hits:
                            r = hits[0]
                            marks.append({"n": it["n"], "label": f"{it['where']}: {text}", "md": it["md"], "page": i,
                                          "size": (doc[i].rect.width, doc[i].rect.height),
                                          "rect": (r.x0 - 2, r.y0 - 2, r.x1 + 2, r.y1 + 2)})
                            break
    finally:
        if doc:
            doc.close()
    return marks
