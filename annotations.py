"""Drawings (pen and highlighter strokes) on the pages of a Library PDF, kept per file in data/annotations/<book id>.json:
{"pages": {"<page>": [{"t": "pen" | "hl", "c": "#rrggbb", "w": width as a fraction of the page width, "p": [[x, y], ...]}]}}
x and y are fractions (0 to 1) of the page's width and height, so a drawing stays on the same place at any zoom.
A highlighter stroke follows the text instead: {"t": "hr", "c": "#rrggbb", "r": [[x0, y0, x1, y1], ...]}, one box per line of text."""
import json
from functools import lru_cache

from database import BASE_DIR

DIR = BASE_DIR / "data" / "annotations"


def load(book_id):
    """{page number (str): [stroke, ...]} of a file; empty when nothing is drawn."""
    try:
        return json.loads((DIR / f"{book_id}.json").read_text(encoding="utf-8")).get("pages", {})
    except (OSError, ValueError):
        return {}


def _save(book_id, pages):
    pages = {k: v for k, v in pages.items() if v}
    f = DIR / f"{book_id}.json"
    if not pages:
        f.unlink(missing_ok=True)
        return
    DIR.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"pages": pages}, separators=(",", ":")), encoding="utf-8")


def set_page(book_id, page, strokes):
    """Replace the strokes of one page (an empty list removes them)."""
    clean = [s for s in strokes if isinstance(s, dict) and (
        (s.get("t") in ("pen", "hl") and isinstance(s.get("p"), list) and s["p"]) or (s.get("t") == "hr" and isinstance(s.get("r"), list) and s["r"]))]
    pages = load(book_id)
    pages[str(int(page))] = clean
    _save(book_id, pages)


def clear(book_id):
    """Remove every drawing of a file."""
    _save(book_id, {})


@lru_cache(maxsize=6)
def words(path, mtime):
    """{page number (str): [[y0, y1, [x0, x1, x0, x1, ...]], ...]}: the lines of text of every page, each with the left and right edge of
    its words, as fractions of the page, in reading order. The highlighter snaps to these. Pages without text (scans) are left out."""
    import pymupdf
    out = {}
    with pymupdf.open(path) as doc:
        if doc.page_count > 150:
            return out
        for i, page in enumerate(doc, 1):
            W, H = page.rect.width, page.rect.height
            lines = {}
            for w in page.get_text("words"):                      # x0, y0, x1, y1, text, block, line, word
                if w[4].strip():
                    lines.setdefault((w[5], w[6]), []).append(w)
            page_lines = []
            for ws in lines.values():
                ws.sort(key=lambda w: w[0])
                xs = []
                for w in ws:
                    xs += [round(w[0] / W, 4), round(w[2] / W, 4)]
                page_lines.append([round(min(w[1] for w in ws) / H, 4), round(max(w[3] for w in ws) / H, 4), xs])
            if page_lines:
                out[str(i)] = page_lines
    return out
