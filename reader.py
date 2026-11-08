"""A compact PDF reader: one slim toolbar (Prev, page box, Next, zoom - / % / +) above a scrolling page.

Page flipping is kept quick three ways: pages are drawn as small JPEGs, the pages next to the current one are
rendered in the background, and the reader is a fragment, so Prev / Next / zoom redraw only the reader."""
import base64
import pathlib
import hashlib
import html
import json
import os
import threading
from collections import OrderedDict
from functools import lru_cache

import pymupdf
import streamlit as st

import covers
from database import BASE_DIR

ZOOMS = [50, 75, 100, 125, 150, 175, 200, 250, 300]
_cache = OrderedDict()                 # (path, mtime, page_index, width) -> JPEG bytes
_lock = threading.Lock()
CACHE_PAGES = 60
PAGES_DIR = BASE_DIR / "static" / "pages"      # served at /app/static/pages (Streamlit static serving)
SCROLL_WIDTH = 1200                            # pixel width of the page images in the scrolling view
_inflight = {}


def scroll_available():
    """The scrolling view needs Streamlit's static file serving (enabled in .streamlit/config.toml)."""
    try:
        return bool(st.get_option("server.enableStaticServing"))
    except Exception:
        return False


@lru_cache(maxsize=16)
def _page_sizes(path, mtime):
    with covers.pymupdf.open(path) as doc:
        return [(round(pg.rect.width), round(pg.rect.height)) for pg in doc]


def _doc_dir(path, mtime):
    return hashlib.md5(f"{path}|{mtime}|{SCROLL_WIDTH}".encode()).hexdigest()[:12]


def _write_page(path, mtime, index):
    out = PAGES_DIR / _doc_dir(path, mtime) / f"{index + 1}.jpg"
    if out.exists():
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_bytes(covers.render_page(path, index, SCROLL_WIDTH, fmt="jpg"))
    os.replace(tmp, out)


def _render_files(path, mtime, center, total):
    """Start a background process that renders every page file, nearest `center` first (one per document)."""
    import subprocess
    import sys
    out_dir = PAGES_DIR / _doc_dir(path, mtime)
    token = (path, mtime)
    proc = _inflight.get(token)
    if proc and proc.poll() is None:
        return
    args = [str(path), str(out_dir), str(center), str(SCROLL_WIDTH)]
    cmd = [sys.executable, "--render", *args] if getattr(sys, "frozen", False)         else [sys.executable, str(BASE_DIR / "pagerender.py"), *args]
    flags = (getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0))         if os.name == "nt" else 0
    _inflight[token] = subprocess.Popen(cmd, creationflags=flags, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                        stdin=subprocess.DEVNULL)


def _render(path, mtime, page_index, width):
    key = (path, mtime, page_index, width)
    with _lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]
    data = covers.render_page(path, page_index, width, fmt="jpg")
    with _lock:
        _cache[key] = data
        while len(_cache) > CACHE_PAGES:
            _cache.popitem(last=False)
    return data


def page_image(path, mtime, page_index, width):
    """JPEG bytes of one page (cached)."""
    return _render(str(path), mtime, page_index, width)


def _prefetch(path, mtime, pages, width):
    def work():
        for i in pages:
            try:
                _render(str(path), mtime, i, width)
            except Exception:
                return
    threading.Thread(target=work, daemon=True).start()


def _boxes(marks, active=None):
    """Red boxes with the erratum number over the marked places (positions in % of the page, so any zoom fits)."""
    out = ""
    for m in marks or []:
        W, H = m["size"]
        x0, y0, x1, y1 = m["rect"]
        label = m["label"].replace('"', "'")
        if m.get("find"):                                         # a search hit: a yellow highlight, the current one orange
            cls, badge = "rd-find" + (" active" if m.get("active") else ""), ""
        else:
            cls = "rd-err" + (" rd-sent" if m.get("sentence") else "") + (" active" if active and m["n"] in active else "")
            badge = f"<b>{m['n']}</b>"
        out += (f'<span class="{cls}" data-tip="{label}" style="left:{x0 / W * 100:.2f}%;top:{y0 / H * 100:.2f}%;'
                f'width:{(x1 - x0) / W * 100:.2f}%;height:{(y1 - y0) / H * 100:.2f}%">{badge}</span>')
    return out


@lru_cache(maxsize=24)
def find_matches(path, mtime, query):
    """Every place the text occurs in the PDF (any case): [(page index, (x0, y0, x1, y1), (page width, page height))], at most 400."""
    out = []
    if not query.strip():
        return out
    doc = pymupdf.open(path)
    try:
        for i, page in enumerate(doc):
            for r in page.search_for(query.strip()):
                out.append((i, (r.x0, r.y0, r.x1, r.y1), (page.rect.width, page.rect.height)))
                if len(out) >= 400:
                    return out
    finally:
        doc.close()
    return out


def _find_go(key, page_key, path, mtime, delta):
    """Callback: the first hit when the text changes (delta 0), else the next or previous hit; shows its page."""
    hits = find_matches(path, mtime, st.session_state.get(f"{key}_fq", ""))
    if not hits:
        st.session_state[f"{key}_fi"] = 0
        return
    i = 0 if delta == 0 else (st.session_state.get(f"{key}_fi", 0) + delta) % len(hits)
    st.session_state[f"{key}_fi"] = i
    st.session_state[page_key] = hits[i][0] + 1
    _bump(key)


def _find_marks(key, path, mtime):
    """The search hits as marks for the page images; the current one is emphasised."""
    q = st.session_state.get(f"{key}_fq", "")
    hits = find_matches(str(path), mtime, q)
    cur = st.session_state.get(f"{key}_fi", 0)
    return [{"n": "", "label": q, "md": "", "page": pg, "size": size, "rect": rect, "find": True, "active": k == cur}
            for k, (pg, rect, size) in enumerate(hits)], len(hits)


def _find_box(key, page_key, path, mtime):
    """The search tool in the toolbar: a magnifier button (Ctrl+F opens it) with a text box, the hit count and previous / next."""
    with st.container(key=f"{key}_findbox"):
        with st.popover("", icon=":material/search:", width="stretch", help="find text in this file (ctrl+f)"):
            st.text_input("Find in this file", key=f"{key}_fq", placeholder="Find in this file", label_visibility="collapsed",
                          on_change=_find_go, args=(key, page_key, str(path), mtime, 0))
            q = st.session_state.get(f"{key}_fq", "")
            hits = find_matches(str(path), mtime, q) if q else []
            c1, c2, c3 = st.columns([2.2, 1, 1], vertical_alignment="center")
            if q and hits:
                c1.caption(f"{st.session_state.get(f'{key}_fi', 0) + 1} of {len(hits)}")
            elif q:
                c1.caption("No matches (a scanned file has no text to search)" if not covers_has_text(str(path), mtime) else "No matches")
            c2.button("", key=f"{key}_fprev", icon=":material/keyboard_arrow_up:", width="stretch", disabled=not hits,
                      on_click=_find_go, args=(key, page_key, str(path), mtime, -1), help="previous match")
            c3.button("", key=f"{key}_fnext", icon=":material/keyboard_arrow_down:", width="stretch", disabled=not hits,
                      on_click=_find_go, args=(key, page_key, str(path), mtime, 1), help="next match")


@lru_cache(maxsize=24)
def covers_has_text(path, mtime):
    """True when the PDF has a text layer on at least one of its first pages."""
    doc = pymupdf.open(path)
    try:
        return any(len(doc[i].get_text().strip()) > 20 for i in range(min(doc.page_count, 6)))
    finally:
        doc.close()


def _go(page_key, page, key):
    st.session_state[page_key] = page
    _bump(key)


def _errata_list(marks, key, page_key):
    """A button that lists the errata placed in this PDF, each with a way to jump to its page."""
    with st.popover(f"Errata ({len({m['n'] for m in marks})})", width="content"):
        st.caption("Corrections from the open notes, marked in red on the pages.")
        for i, m in enumerate(sorted(marks, key=lambda m: (m["page"], m["n"]))):
            st.markdown(f"**{m['n']}. {m['label']}** · page {m['page'] + 1}")
            st.markdown(m["md"])
            st.button("Go To Page", key=f"{key}_err_{i}", on_click=_go, args=(page_key, m["page"] + 1, key))


def _annot_attrs(annot, path):
    """Attributes that tell the page script a file can be drawn on: the drawings made so far, and the lines of text of each page (the
    highlighter follows them)."""
    if not annot:
        return ""
    import annotations
    lines = annotations.words(str(path), pathlib.Path(path).stat().st_mtime)
    return (f' data-annot="{int(annot)}" data-strokes="{html.escape(json.dumps(annotations.load(annot), separators=(",", ":")), quote=True)}"'
            f' data-words="{html.escape(json.dumps(lines, separators=(",", ":")), quote=True)}"')


@st.fragment
def _annot_sink():
    """The page script writes 'annot:<file>:<page>:<strokes of the page as json>|<time>' (or 'annotclear:<file>|<time>') here as a drawing is made;
    it is a fragment, so saving a stroke does not redraw the reader."""
    import annotations
    sink = st.text_input("Drawing", key="annot_sink", label_visibility="collapsed")
    if not sink or sink == st.session_state.get("_annot_done"):
        return
    st.session_state["_annot_done"] = sink
    action, _, rest = sink.rsplit("|", 1)[0].partition(":")
    try:
        if action == "annot":
            book_id, page, strokes = rest.split(":", 2)
            annotations.set_page(int(book_id), int(page), json.loads(strokes))
        elif action == "annotclear":
            annotations.clear(int(rest))
    except (ValueError, TypeError):
        pass


def _bump(key):
    st.session_state[f"{key}_tok"] = st.session_state.get(f"{key}_tok", 0) + 1       # tells the scrolling view to jump


def _step_page(page_key, delta, total):
    double = st.session_state.get(f"{page_key[:-5]}_view") in ("double", "scroll2")     # a spread turns two pages at a time
    st.session_state[page_key] = min(total, max(1, st.session_state[page_key] + delta * (2 if double else 1)))
    _bump(page_key[:-5])


MODES = {"page": ("single page", ":material/crop_portrait:"), "double": ("double page", ":material/auto_stories:"),
         "scroll": ("continuous scrolling", ":material/view_day:"),
         "scroll2": ("continuous double page", ":material/view_column_2:")}


def _modes():
    return ["page", "double", "scroll", "scroll2"] if scroll_available() else ["page", "double"]


def _toggle_mode(mode_key):
    modes = _modes()
    cur = st.session_state.get(mode_key, "page")
    st.session_state[mode_key] = modes[(modes.index(cur) + 1) % len(modes)] if cur in modes else "page"


def _set_zoom(zoom_key, value):
    st.session_state[zoom_key] = value
    _bump(zoom_key[:-5])


def _step_zoom(zoom_key, delta):
    z = st.session_state[zoom_key]
    i = ZOOMS.index(z) if z in ZOOMS else ZOOMS.index(100)
    st.session_state[zoom_key] = ZOOMS[min(len(ZOOMS) - 1, max(0, i + delta))]
    _bump(zoom_key[:-5])


@st.fragment
def pdf_reader(path, key, height=640, start=1, title=None, on_page=None, marks=None, active=None, marks_list=True, view="page", annot=None):
    """Draw the reader for a PDF file. 100% fits the width of the window; height None fills the window (page CSS).
    `title` is drawn above the toolbar with the page number; `on_page(page)` is told whenever the page changes.
    `marks` are errata to draw on the pages (see errata.py); the numbers in `active` are drawn emphasised and scrolled to.
    `view` is the view a file first opens in: "page", "double", "scroll" (continuous) or "scroll2".
    `annot` is the Library id of the file when it can be drawn on (pen and highlighter, saved as they are drawn: see annotations.py)."""
    marks = list(marks or [])
    path = pathlib.Path(path)
    found, _n = _find_marks(key, path, path.stat().st_mtime)          # the text searched for (Ctrl+F) is highlighted on the pages
    by_page = {}
    for m in marks + found:
        by_page.setdefault(m["page"], []).append(m)
    try:
        total = covers.page_count(path)
    except Exception:
        st.error("This PDF could not be opened for preview."); return
    page_key, zoom_key, mode_key = f"{key}_page", f"{key}_zoom", f"{key}_view"
    st.session_state.setdefault(page_key, min(max(1, start), total))
    st.session_state.setdefault(zoom_key, 100)
    st.session_state.setdefault(mode_key, view if view in _modes() else "page")        # the view a file opens in; the button still changes it
    st.session_state[page_key] = min(max(1, st.session_state[page_key]), total)
    heading = st.empty()
    if annot:
        _annot_sink()                                                   # the hidden box the drawings are saved through
    drawn = _annot_attrs(annot, path)

    with st.container(key=f"reader_{key}"):
        # fit width | Prev  14/280  Next | zoom chip, magnifier + (zoom in), magnifier - (zoom out)
        cols = st.columns([0.55, 1.1, 1.15, 0.75, 0.9, 1.15, 1.1, 1.0, 0.55, 0.55, 0.55], vertical_alignment="center", gap="small")
        cols[0].button("", key=f"{key}_fit", icon=":material/fit_width:", width="stretch", on_click=_set_zoom,
                       args=(zoom_key, 100), help="fit to width")
        with cols[6]:
            _find_box(key, page_key, path, path.stat().st_mtime)
        cols[2].button("‹  Prev", key=f"{key}_prev", width="stretch", on_click=_step_page, args=(page_key, -1, total))
        cols[3].number_input("Page", 1, total, key=page_key, label_visibility="collapsed", on_change=_bump, args=(key,))
        cols[4].markdown(f'<div class="rd-total">/{total}</div>', unsafe_allow_html=True)
        cols[5].button("Next  ›", key=f"{key}_next", width="stretch", on_click=_step_page, args=(page_key, 1, total))
        cols[7].markdown(f'<div class="rd-zoom">{st.session_state[zoom_key]}%</div>', unsafe_allow_html=True)
        cols[8].button("", key=f"{key}_zin", icon=":material/zoom_in:", width="stretch", on_click=_step_zoom, args=(zoom_key, 1), help="zoom in")
        cols[9].button("", key=f"{key}_zout", icon=":material/zoom_out:", width="stretch", on_click=_step_zoom, args=(zoom_key, -1), help="zoom out")
        modes = _modes()
        cur = st.session_state.get(mode_key, "page")
        cur = cur if cur in modes else "page"
        nxt = modes[(modes.index(cur) + 1) % len(modes)]
        cols[10].button("", key=f"{key}_mode", icon=MODES[cur][1], width="stretch", on_click=_toggle_mode,
                        args=(mode_key,), help=f"{MODES[cur][0]} view. click for {MODES[nxt][0]} view")

        if marks and marks_list:
            _errata_list(marks, key, page_key)

    page, zoom = st.session_state[page_key], st.session_state[zoom_key]
    if title:
        heading.markdown(f"<h3 class='lab-heading'>{html.escape(title)} · Page {page}</h3>", unsafe_allow_html=True)
    mtime = path.stat().st_mtime
    mode = st.session_state.get(mode_key, "page")
    if mode in ("scroll", "scroll2") and scroll_available():
        _scrolling_view(path, key, page, zoom, total, height, mtime, per_row=2 if mode == "scroll2" else 1, by_page=by_page, active=active, drawn=drawn)
        if on_page:
            on_page(page)
        return
    shown = [page, page + 1] if mode == "double" and page < total else [page]
    width = min(3000, int(1400 * zoom / 100 / len(shown) + 200))
    imgs = "".join(
        f'<div class="rd-pagewrap" data-pn="{n}" style="width:{zoom / len(shown):g}%">'
        f'<img src="data:image/jpeg;base64,{base64.b64encode(page_image(path, mtime, n - 1, width)).decode()}" '
        f'style="width:100%" alt="Page {n}">{_boxes(by_page.get(n - 1), active)}</div>' for n in shown)
    box = f' style="height:{height}px"' if height else ""
    st.markdown(f'<div class="rd-scroll{"" if height else " rd-fill"}"{box}{drawn}><div class="rd-spread">{imgs}</div></div>',
                unsafe_allow_html=True)
    step = len(shown)
    neighbours = [i for i in (page - 1 + step, page - 1 + 2 * step, page - 1 - step) if 0 <= i < total]   # next spread, then back
    _prefetch(path, mtime, neighbours, width)
    if on_page:
        on_page(page)


def _scrolling_view(path, key, page, zoom, total, height, mtime, per_row=1, by_page=None, active=None, drawn=""):
    """Every page stacked in one scrolling window. Images are page files under static/pages, drawn in the
    background around the current page; the page script retries any that are not ready yet."""
    sizes = _page_sizes(str(path), mtime)
    folder = _doc_dir(str(path), mtime)
    _write_page(str(path), mtime, page - 1)                 # the page you land on is ready at once
    _render_files(str(path), mtime, page - 1, total)
    cells = [
        f'<div class="rd-pg" id="rdp-{key}-{n}" data-pn="{n}" style="aspect-ratio:{w}/{h};width:{zoom / per_row:g}%">'
        f'<img loading="lazy" decoding="async" alt="" src="/app/static/pages/{folder}/{n}.jpg">'
        f'{_boxes((by_page or {}).get(n - 1), active)}</div>'
        for n, (w, h) in enumerate(sizes, 1)]
    if per_row == 1:
        pages = "".join(cells)
    else:                                                   # spreads: pages 1-2, 3-4, ... side by side
        pages = "".join(f'<div class="rd-row">{"".join(cells[i:i + per_row])}</div>' for i in range(0, len(cells), per_row))
    box = f' style="height:{height}px"' if height else ""
    token = st.session_state.get(f"{key}_tok", 0)
    st.markdown(f'<div class="rd-scroll rd-cont{"" if height else " rd-fill"}" data-key="{key}" data-goto="{page}" '
                f'data-token="{token}" data-total="{total}"{box}{drawn}><div class="rd-live">Page {page} / {total}</div>{pages}</div>',
                unsafe_allow_html=True)
