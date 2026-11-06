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
    """Equation numbers named in a location: "Eq. 490", "Eq. (66)", "Eqs. 468-471" or "Eqs. (262)-(263)" (both ends)."""
    nums = []
    for m in re.finditer(r"Eqs?\.?\s*\(?(\d{1,4})\)?(?:\s*[–\-]\s*\(?(\d{1,4})\)?)?", where):
        nums.append(int(m.group(1)))
        if m.group(2):
            nums.append(int(m.group(2)))
    return list(dict.fromkeys(nums))


def _pages(where):
    """Printed page numbers in a location ("p. 23", "p. 32–33"), as page indexes (the lecture notes print the PDF's numbers)."""
    out = []
    for m in re.finditer(r"\bpp?\.\s*(\d{1,3})(?:\s*[–\-]\s*(\d{1,3}))?", where):
        out += [int(m.group(1)) - 1] + ([int(m.group(2)) - 1] if m.group(2) else [])
    return list(dict.fromkeys(out))


ORDINALS = {"first": 0, "second": 1, "third": 2, "fourth": 3, "fifth": 4}


def _paragraphs(page):
    """The text blocks of a page that are long enough to be paragraphs, top to bottom."""
    return sorted((b for b in page.get_text("blocks") if b[6] == 0 and len(b[4].strip()) >= 60), key=lambda b: b[1])


def _mark(it, label, page, page_index, rect):
    return {"n": it["n"], "label": label, "md": it["md"], "page": page_index,
            "size": (page.rect.width, page.rect.height), "rect": rect}


def _by_position(doc, it, pages):
    """A location that names a paragraph or a place on a page ("first paragraph", "top", a quoted heading) and no equation."""
    where, out = it["where"], []
    for pg in pages:
        if not 0 <= pg < doc.page_count:
            continue
        page = doc[pg]
        W, H = page.rect.width, page.rect.height
        quoted = re.search(r"“([^”]{4,80})”", where)
        word = next((w for w in ORDINALS if re.search(r"\b" + w + r"\s+paragraph", where, re.I)), None)
        if quoted and page.search_for(quoted.group(1)):
            r = page.search_for(quoted.group(1))[0]
            out.append(_mark(it, where, page, pg, (r.x0 - 3, r.y0 - 2, r.x1 + 3, r.y1 + 2)))
        elif word or re.search(r"\blast\s+paragraph", where, re.I):
            paras = _paragraphs(page)
            if paras:
                b = paras[-1] if not word else paras[min(ORDINALS[word], len(paras) - 1)]
                out.append(_mark(it, where, page, pg, (b[0] - 3, b[1] - 3, b[2] + 3, b[3] + 3)))
        elif re.search(r"\btop\b", where, re.I):
            out.append(_mark(it, where, page, pg, (W * 0.08, H * 0.04, W * 0.92, H * 0.16)))
        if out and out[-1]["page"] == pg:
            break
    if not out and pages and 0 <= pages[0] < doc.page_count:               # only the page is known: a bar down its left margin
        page = doc[pages[0]]
        out.append(_mark(it, where, page, pages[0], (6, 8, 22, page.rect.height - 8)))
    return out


def _near_equation(doc, it, page_index, tag_rect, size):
    """"paragraph before/after Eq. (68)", "margin under Eq. (148)": the paragraph above or below the equation, else its row."""
    page = doc[page_index]
    W = size[0]
    where = it["where"]
    paras = _paragraphs(page)
    if re.search(r"\b(before|above)\b", where, re.I):
        above = [b for b in paras if b[3] <= tag_rect[1] + 6]
        if above:
            b = above[-1]
            return _mark(it, where, page, page_index, (b[0] - 3, b[1] - 3, b[2] + 3, b[3] + 3))
    if re.search(r"\b(after|below|under)\b", where, re.I):
        below = [b for b in paras if b[1] >= tag_rect[3] - 6]
        if below:
            b = below[0]
            return _mark(it, where, page, page_index, (b[0] - 3, b[1] - 3, b[2] + 3, b[3] + 3))
    return _mark(it, where, page, page_index, (W * 0.1, tag_rect[1] - 16, tag_rect[2] + 4, tag_rect[3] + 12))


def _typos(item):
    """[(quoted text, page number or None)] from a "Typos" erratum, e.g. “cofficients” (p. 106)."""
    found = []
    for m in re.finditer(r"[“\"]([^”\"]{3,60})[”\"](?:\s*\(p\.?\s*(\d+)\))?", item["md"]):
        found.append((m.group(1), int(m.group(2)) if m.group(2) else None))
    return found


def _sentence_marks(doc, item, pages):
    """Marks for the sentences an erratum quotes (“...”): found by their first words on the given pages; the mark covers the
    lines from the start of the quote to its end."""
    out = []
    for quote in re.findall(r"“([^”]{18,240})”", item["md"]):
        if "$" in quote:
            continue
        start, end = quote[:42].strip(), quote[-28:].strip()
        for pg in pages:
            if not 0 <= pg < doc.page_count:
                continue
            page = doc[pg]
            hits = page.search_for(start) or page.search_for(start[:24])
            if not hits:
                continue
            r = hits[0]
            tail = [x for x in page.search_for(end) if x.y0 >= r.y0 - 1]
            block = next((b for b in page.get_text("blocks") if b[0] - 2 <= r.x0 <= b[2] and b[1] - 2 <= r.y0 <= b[3]), None)
            x0, x1 = (block[0], block[2]) if block else (r.x0, page.rect.width * 0.9)
            y1 = tail[0].y1 if tail else r.y1 + 12
            out.append({"n": item["n"], "label": f"{item['where']}: “{start}…”", "md": item["md"], "page": pg,
                        "size": (page.rect.width, page.rect.height), "rect": (x0 - 2, r.y0 - 1, x1 + 2, y1 + 1), "sentence": True})
            break
    return out


_STOP = set("""about above after again against because before being below between cannot could does doing during each from have having
here into itself just more most must only other over same should some such than that their them then there these they this those
through under until very were what when where which while with without would your note notes text page pages equation equations
slide slides handout chapter section should says say said""".split())


def _words(text):
    """Distinctive words of a piece of text (lower case, no math)."""
    text = re.sub(r"\$[^$]*\$", " ", text)
    return [w for w in re.findall(r"[a-z][a-z\-]{4,}", text.lower()) if w not in _STOP]


def _quoted(item):
    """Text fragments an erratum quotes or calls out, without math: “...” and the words it flags as typos."""
    out = [re.sub(r"[$\{}]", "", q).strip() for q in re.findall(r"“([^”]{4,120})”", item["md"] + " " + item["where"])]
    out += [q.strip() for q in re.findall(r"\"([^\"$]{4,80})\"", item["md"])]
    return [q for q in dict.fromkeys(out) if len(q) >= 4]


def _fuzzy(doc, it):
    """Last resort for an erratum whose location cannot be read: find the place in this PDF that its text is about.
    First its quoted words anywhere in the PDF; otherwise the paragraph that shares the most distinctive words with it."""
    marks = []
    where = it["where"].lower()
    for words, index, band in (("first page|start of the pdf|beginning", 0, (0.04, 0.2)), ("end of|last page|last lines", doc.page_count - 1, (0.7, 0.96))):
        if re.search(words, where) and doc.page_count:
            page = doc[index]
            W, H = page.rect.width, page.rect.height
            return [{"n": it["n"], "label": it["where"], "md": it["md"], "page": index, "size": (W, H),
                     "rect": (W * 0.08, H * band[0], W * 0.92, H * band[1])}]
    for q in _quoted(it):
        for pg in range(doc.page_count):
            hits = doc[pg].search_for(q)
            if hits:
                page = doc[pg]
                r = hits[0]
                marks.append({"n": it["n"], "label": f"“{q[:50]}”", "md": it["md"], "page": pg, "sentence": True,
                              "size": (page.rect.width, page.rect.height), "rect": (r.x0 - 2, r.y0 - 1, r.x1 + 2, r.y1 + 1)})
                break
        if marks:
            return marks
    want = set(_words(it["md"] + " " + it["where"]))
    if len(want) < 3:
        return []
    best = None
    for pg in range(doc.page_count):
        page = doc[pg]
        for b in page.get_text("blocks"):
            if b[6] != 0 or len(b[4].strip()) < 40:
                continue
            have = set(_words(b[4]))
            score = len(want & have)
            if score >= 3 and (best is None or score > best[0]):
                best = (score, pg, b)
    if best:
        _, pg, b = best
        page = doc[pg]
        marks.append({"n": it["n"], "label": it["where"], "md": it["md"], "page": pg,
                      "size": (page.rect.width, page.rect.height), "rect": (b[0] - 3, b[1] - 3, b[2] + 3, b[3] + 3)})
    return marks


def locate(path, mtime, items):
    """Marks for the errata that can be placed in this PDF: {n, label, md, page, rect, size, [sentence]}."""
    path = str(path)
    marks = []
    tags = None
    doc = None
    try:
        for it in items:
            where = it["where"]
            nums, pages = _numbers(where), _pages(where)
            doc = doc or pymupdf.open(path)
            placed = []
            if nums:
                tags = tags if tags is not None else _equation_tags(path, mtime)
                for k in nums:
                    found = tags.get(k, [])
                    pick = next((t for t in found if t[0] in pages), found[0] if found else None)    # the tag on the named page, if any
                    if pick:
                        page_index, r, size = pick
                        marks.append(_near_equation(doc, it, page_index, r, size))
                        placed.append(page_index)
            elif re.search(r"§\s*\d+\.\d+", where):
                sec = re.search(r"§\s*(\d+\.\d+)", where).group(1)
                for i in range(doc.page_count):                              # the heading "14.2 ..." at the left margin
                    hit = next((r for r in doc[i].search_for(sec) if r.x0 < doc[i].rect.width * 0.25), None)
                    if hit:
                        W = doc[i].rect.width
                        marks.append(_mark(it, where, doc[i], i, (hit.x0 - 4, hit.y0 - 3, W * 0.9, hit.y1 + 3)))
                        placed.append(i)
                        break
            elif "typo" in where.lower():
                for text, pg in _typos(it):
                    for i in ([pg - 1] if pg and 0 < pg <= doc.page_count else range(doc.page_count)):
                        hits = doc[i].search_for(text)
                        if hits:
                            r = hits[0]
                            marks.append(_mark(it, f"{where}: {text}", doc[i], i, (r.x0 - 2, r.y0 - 2, r.x1 + 2, r.y1 + 2)))
                            placed.append(i)
                            break
            if not placed and pages:                                             # "p. 22, second paragraph", "p. 25, top"
                found = _by_position(doc, it, pages)
                marks += found
                placed += [m["page"] for m in found]
            if not placed:                                                       # cannot be read from its label: search the text
                found = _fuzzy(doc, it)
                marks += found
                placed += [m["page"] for m in found]
            if placed:                                                           # and the sentence the erratum quotes
                near = pages or sorted({q for pg in placed for q in (pg - 1, pg, pg + 1)})   # the page it names, else around the equation
                marks += _sentence_marks(doc, it, sorted(set(near) | set(placed)))
    finally:
        if doc:
            doc.close()
    by_n = {it["n"]: it for it in items}
    for m in marks:                                                               # where each mark came from (for clicks in the notes)
        m["src"], m["idx"] = by_n[m["n"]].get("src"), by_n[m["n"]].get("idx")
    return marks
