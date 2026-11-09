"""Equation sheets for exams, put together from the "Formula sheet" section of the course notes.

An exam's sheet is a printable two-column HTML page kept in the Library (kind "Equation Sheet"). Which notes it draws on is chosen per
exam and remembered in data/equation_sheets/<event id>.json: {"notes": [Library ids], "book": Library id of the built sheet}."""
import html
import json
import re
import uuid

import crud
from database import DATA_DIR, PDF_DIR, data_path, stored_path

DIR = DATA_DIR / "equation_sheets"
SHEET_TITLE = re.compile(r"formula sheet|equation sheet", re.I)


def load(event_id):
    try:
        return json.loads((DIR / f"{event_id}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save(event_id, data):
    DIR.mkdir(parents=True, exist_ok=True)
    (DIR / f"{event_id}.json").write_text(json.dumps(data), encoding="utf-8")


def _sections(text):
    """[(heading text, inner html)] of every <section> of a note."""
    out = []
    for m in re.finditer(r'<section id="([^"]+)"[^>]*>(.*?)</section>', text, re.S):
        h = re.search(r"<h2[^>]*>(.*?)</h2>", m.group(2), re.S)
        out.append((re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h.group(1)))).strip() if h else "", m.group(2)))
    return out


def sheet_of(text):
    """The formula-sheet section of a note as html, or None when the note has none. Two layouts: a list of rows (name, equation, a
    link to its derivation) or a table of concept, statement and reference."""
    for title, inner in _sections(text):
        if not SHEET_TITLE.search(title):
            continue
        body = re.sub(r"<h2[^>]*>.*?</h2>", "", inner, count=1, flags=re.S)
        grid = re.search(r'<div class="sumgrid">.*', body, re.S)
        if grid:
            rows = grid.group(0)
            rows = re.sub(r'<a class="eqn"[^>]*>(.*?)</a>', r'<span class="eqn"></span>', rows, flags=re.S)       # links go nowhere here
            rows = re.sub(r"<a [^>]*>(.*?)</a>", r"", rows, flags=re.S)
            return rows
        table = re.search(r"<table.*?</table>", body, re.S)         # the formulas; pitfalls and video lists around it are left out
        return table.group(0) if table else None
    return None


def candidates(course_id):
    """The course's html notes that have a formula sheet: [(book, sheet html)], in lecture order."""
    out = []
    for b in crud.list_books():
        if course_id in b["course_ids"] and b["kind"] == "Notes" and b["pdf_path"].endswith(".html"):
            try:
                sheet = sheet_of(data_path(b["pdf_path"]).read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
            if sheet:
                out.append((b, sheet))

    def key(item):
        nums = [int(n) for n in re.findall(r"\d+", item[0].get("lecture") or "")]
        return (nums[0] if nums else 999, item[0]["title"])

    return sorted(out, key=key)


_STYLE = """
:root{color-scheme:light dark;--bg:#fff;--ink:#16181d;--muted:#5c6475;--line:#cfd5e0;--head:#eef1f7}
@media (prefers-color-scheme:dark){:root{--bg:#10131a;--ink:#e6e9f0;--muted:#99a2b4;--line:#2b3347;--head:#182033}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:13px/1.45 system-ui,"Segoe UI",sans-serif;padding:18px 22px}
h1{font-size:19px;margin:0 0 2px}.sub{color:var(--muted);margin:0 0 14px;font-size:12px}
.cols{column-count:2;column-gap:26px}.note{break-inside:avoid-column;margin:0 0 14px}
.note h2{font-size:13px;margin:0 0 5px;padding:3px 7px;background:var(--head);border-radius:5px}
.sumgrid{display:flex;flex-direction:column}.sumrow{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:2px 10px;align-items:center;border-bottom:1px solid var(--line);padding:4px 2px}
.sumname{font-weight:600;font-size:12px;grid-column:1 / -1}.eqb{display:flex;justify-content:space-between;align-items:center;gap:8px;grid-column:1 / -1}
.eqm{overflow-x:auto;min-width:0}.eqn{color:var(--muted);font-size:11px;white-space:nowrap}mjx-container[display="true"]{margin:2px 0 !important}
table{border-collapse:collapse;width:100%;font-size:12.5px}th,td{border-bottom:1px solid var(--line);padding:3px 5px;text-align:left;vertical-align:top}
th{color:var(--muted);font-weight:600;font-size:11px}p{margin:3px 0}
@media (max-width:760px){.cols{column-count:1}}
@media print{body{padding:6mm;font-size:10.5px}.cols{column-gap:14px}:root{--bg:#fff;--ink:#000;--muted:#444;--line:#aaa;--head:#eee}}
"""


def build(course, event, notes):
    """The html page of an exam's equation sheet from [(book, sheet html)]; the first note's MathJax settings (macros) are reused."""
    first = data_path(notes[0][0]["pdf_path"]).read_text(encoding="utf-8", errors="replace") if notes else ""
    cfg = re.search(r"<script>\s*window\.MathJax\s*=.*?</script>", first, re.S)
    mathjax = cfg.group(0) if cfg else "<script>window.MathJax={tex:{inlineMath:[['\\\\(','\\\\)']],displayMath:[['\\\\[','\\\\]']]},svg:{fontCache:'global'}};</script>"
    parts = ""
    for b, sheet in notes:
        lec = f"Lec {b['lecture']} · " if b.get("lecture") else ""
        parts += f'<section class="note"><h2>{html.escape(lec + b["title"])}</h2>{sheet}</section>'
    title = f"{course['code']} {event['title']} Equation Sheet"
    return (f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{html.escape(title)}</title>{mathjax}<script src='https://cdn.jsdelivr.net/npm/mathjax@3.2.2/es5/tex-svg.js' async></script>"
            f"<style>{_STYLE}</style></head><body><h1>{html.escape(title)}</h1>"
            f"<p class='sub'>From the formula sheets of {len(notes)} notes. Print it, or use Ctrl+P and save as a PDF.</p>"
            f"<div class='cols'>{parts}</div></body></html>")


def make(course, event, book_ids):
    """Build the sheet for an exam from the chosen notes and store it in the Library (replacing the earlier one); returns the book id."""
    wanted = [(b, s) for b, s in candidates(course["id"]) if b["id"] in set(book_ids)]
    state = load(event["id"])
    title = f"{event['title']} Equation Sheet"
    page = build(course, event, wanted)
    old = crud.get_book(state.get("book") or 0)
    if old and old["kind"] == "Equation Sheet":
        data_path(old["pdf_path"]).write_text(page, encoding="utf-8")
        crud.update_book(old["id"], title, "", "", "Equation Sheet", [course["id"]], "", "")
        book_id = old["id"]
    else:
        PDF_DIR.mkdir(parents=True, exist_ok=True)
        dest = PDF_DIR / f"book_{uuid.uuid4().hex[:10]}.html"
        dest.write_text(page, encoding="utf-8")
        book_id = crud.add_book(title, "", "", stored_path(dest), 1, [course["id"]], "Equation Sheet", "2026", "")
    save(event["id"], {"notes": [b["id"] for b, _ in wanted], "book": book_id})
    return book_id
