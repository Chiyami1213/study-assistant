"""Cut the exact part of a homework solution that answers one lettered part, the implications, or a whole problem.

The solutions are typed PDFs, so the left-margin markers "a)", "b)", ... and the "Implications" heading can be found by search; the
part runs from its marker to the next marker (or the heading "Implications", or the end of the problem's pages)."""
from functools import lru_cache

import pymupdf

TOP, BOTTOM = 62, 28          # the solution's running header and its page margin (points)


def _left(page, text):
    W = page.rect.width
    return sorted((r for r in page.search_for(text) if r.x0 < W * 0.22 and r.y0 > TOP - 8), key=lambda r: r.y0)


def _first_after(doc, pages, text, page_i, y):
    """(page index in `pages`, y) of the first left-margin hit of `text` after a position, or None."""
    for i in range(page_i, len(pages)):
        for r in _left(doc[pages[i] - 1], text):
            if i > page_i or r.y0 > y + 6:
                return i, r.y0
    return None


@lru_cache(maxsize=256)
def crops(path, mtime, pages, target):
    """[(page number, PNG bytes)] for the target: a letter "a".."e", "implications" or "analysis" (the problem without its implications).
    Empty when the marker cannot be found."""
    doc = pymupdf.open(path)
    pages = list(pages)
    start = None
    ana = _first_after(doc, pages, "Analysis", 0, TOP - 7) or (0, TOP - 7)         # the parts of the answer come after "Analysis:"
    if target in ("implications",):
        start = _first_after(doc, pages, "Implications", 0, TOP - 7)
    elif target == "analysis":
        start = (ana[0], ana[1] - 2)
    else:
        start = _first_after(doc, pages, f"{target})", ana[0], ana[1])
    if not start:
        return []
    si, sy = start
    end = None
    if target == "analysis":
        end = _first_after(doc, pages, "Implications", si, sy)
    elif target == "implications":
        end = None
    else:
        end = _first_after(doc, pages, f"{chr(ord(target) + 1)})", si, sy)
        late = _first_after(doc, pages, "Implications", si, sy)
        if late and (not end or late < end):
            end = late
    out = []
    last = end[0] if end else len(pages) - 1
    for i in range(si, last + 1):
        page = doc[pages[i] - 1]
        W, H = page.rect.width, page.rect.height
        top = sy - 3 if i == si else TOP
        bottom = (end[1] - 4) if end and i == end[0] else H - BOTTOM
        if bottom - top < 24:
            continue
        pix = page.get_pixmap(matrix=pymupdf.Matrix(1.9, 1.9), clip=pymupdf.Rect(W * 0.04, top, W * 0.96, bottom))
        out.append((pages[i], pix.tobytes("png")))
    return out
