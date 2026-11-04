"""Library: PDF books and notes as a cover grid (first page = cover) with a dashed add tile and a page preview."""
import base64
import hashlib
import uuid

import streamlit as st
import streamlit.components.v1 as components

import covers
import crud
import pdfmeta
from database import BASE_DIR, PDF_DIR

COLUMNS = 6
KINDS = ["Textbook", "Notes"]
PLURAL = {"Textbook": "Textbooks"}


@st.cache_data(show_spinner=False, max_entries=256)
def _cover_b64(path, mtime):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


@st.cache_data(show_spinner=False, max_entries=48)
def _page_png(path, mtime, page_index, width):
    return covers.render_page(path, page_index, width)


def _cover_html(book):
    """First page of the PDF as the cover; a generated gradient with the title if it can't be rendered."""
    img = covers.ensure_cover(book["id"], BASE_DIR / book["pdf_path"])
    if img:
        b64 = _cover_b64(str(img), img.stat().st_mtime)
        return f'<div class="book-cover has-img" style="background-image:url(data:image/png;base64,{b64});"></div>'
    hue = int(hashlib.md5(book["title"].encode()).hexdigest()[:6], 16) % 360
    title = book["title"].replace("<", "&lt;")
    return (f'<div class="book-cover" style="background: linear-gradient(155deg, hsl({hue},45%,38%), '
            f'hsl({(hue + 40) % 360},50%,24%));"><span>{title}</span></div>')


def _course_options():
    return {0: "None"} | {c["id"]: crud.label(c) for c in crud.list_courses(section=None)}


@st.dialog("Add File", width="large")
def _add_dialog():
    up = st.file_uploader("File", type=["pdf", "html", "htm"])
    info = {"title": "", "author": "", "edition": "", "pages": None, "source": ""}
    if up:
        cache = st.session_state.setdefault("_pdf_info", {})
        if up.file_id not in cache:
            with st.spinner("Reading PDF details..."):
                cache[up.file_id] = (pdfmeta.extract_info if up.name.lower().endswith('.pdf')
                                          else pdfmeta.extract_html_info)(up.getvalue(), up.name)
        info = cache[up.file_id]
        found = [n for n in ("title", "author", "edition") if info[n]]
        st.caption("Detected " + (", ".join(found) if found else "nothing") +
                   f" from {info['source']} - edit anything that looks wrong.")
    k = up.file_id if up else "none"  # reset the fields whenever a different file is chosen
    kind = st.segmented_control("Type", KINDS, default="Textbook", key=f"bk_kind_{k}") or "Textbook"
    title = st.text_input("Title", value=info["title"], key=f"bk_title_{k}")
    c1, c2 = st.columns(2)
    author = c1.text_input("Author", value=info["author"], key=f"bk_author_{k}")
    edition = c2.text_input("Edition / year", value=info["edition"], key=f"bk_edition_{k}",
                            placeholder="7th Edition (2019)")
    courses = _course_options()
    course_id = st.selectbox("Course (optional)", list(courses), format_func=courses.get, key=f"bk_course_{k}")
    if st.button("Add to library", type="primary", disabled=not (up and title.strip())):
        PDF_DIR.mkdir(parents=True, exist_ok=True)
        ext = ".pdf" if up.name.lower().endswith(".pdf") else ".html"
        dest = PDF_DIR / f"book_{uuid.uuid4().hex[:10]}{ext}"
        dest.write_bytes(up.getvalue())
        crud.add_book(title.strip(), author.strip(), edition.strip(), str(dest.relative_to(BASE_DIR)),
                      info["pages"], course_id or None, kind)
        st.rerun()


def _viewer(book):
    """Preview: pages rendered as images, with prev/next, page jump and zoom."""
    if st.button("← Back to library"):
        st.session_state["open_book"] = None
        st.rerun()
    st.header(book["title"])
    path = BASE_DIR / book["pdf_path"]
    if not path.exists():
        st.error("The stored PDF file is missing."); return
    if path.suffix.lower() in (".html", ".htm"):
        components.html(path.read_text(encoding="utf-8", errors="replace"), height=900, scrolling=True)
        return
    try:
        total = covers.page_count(path)
    except Exception:
        st.error("This PDF could not be opened for preview."); return

    key = f"view_page_{book['id']}"
    st.session_state.setdefault(key, 1)
    c1, c2, c3, c4 = st.columns([1, 1, 2, 4])
    if c1.button("◀ Prev", key=f"prev_{book['id']}"):
        st.session_state[key] = max(1, st.session_state[key] - 1)
    if c2.button("Next ▶", key=f"next_{book['id']}"):
        st.session_state[key] = min(total, st.session_state[key] + 1)
    page = c3.number_input(f"Page (of {total})", 1, total, key=key)
    width = c4.select_slider("Zoom", [600, 800, 1000, 1300], value=1000, key=f"zoom_{book['id']}")
    st.image(_page_png(str(path), path.stat().st_mtime, page - 1, width * 2), width=width)


def _book_card(book):
    with st.container(key=f"bookcard_{book['id']}"):
        st.markdown(_cover_html(book), unsafe_allow_html=True)
        if st.button(" ", key=f"cover_{book['id']}"):  # invisible button laid over the cover
            st.session_state["open_book"] = book["id"]
            st.rerun()

    tag = f'<span class="book-badge tag">{book["course_code"]}</span>' if book["course_code"] else ""
    st.markdown(f'<div class="book-badges"><span class="book-badge">{book["kind"]}</span>{tag}</div>',
                unsafe_allow_html=True)
    t_col, m_col = st.columns([4, 1], vertical_alignment="top")
    t_col.markdown(f"**{book['title']}**")
    with m_col.popover("..."):
        if st.button("Preview", key=f"open_book_{book['id']}"):
            st.session_state["open_book"] = book["id"]; st.rerun()
        t = st.text_input("Title", value=book["title"], key=f"et_{book['id']}")
        au = st.text_input("Author", value=book["author"] or "", key=f"ea_{book['id']}")
        ed = st.text_input("Edition / year", value=book["edition"] or "", key=f"ee_{book['id']}")
        kd = st.selectbox("Type", KINDS, index=KINDS.index(book["kind"]) if book["kind"] in KINDS else 0,
                          key=f"ek_{book['id']}")
        courses = _course_options()
        ids = list(courses)
        cur = book["course_id"] if book["course_id"] in courses else 0
        cs = st.selectbox("Course", ids, index=ids.index(cur), format_func=courses.get, key=f"ec_{book['id']}")
        if st.button("Save details", key=f"save_book_{book['id']}"):
            crud.update_book(book["id"], t.strip() or book["title"], au.strip(), ed.strip(), kd, cs or None)
            st.rerun()
        st.caption("Removing deletes the stored copy in data/pdfs.")
        if st.button("Remove from library", key=f"del_book_{book['id']}"):
            p = BASE_DIR / book["pdf_path"]
            crud.delete_book(book["id"])
            covers.remove_cover(book["id"])
            if p.exists():
                p.unlink()
            st.rerun()
    sub = " · ".join(x for x in (book["author"], book["edition"]) if x)
    if sub:
        st.caption(sub)


def render():
    st.session_state.setdefault("open_book", None)
    open_book = crud.get_book(st.session_state["open_book"]) if st.session_state["open_book"] else None
    if open_book:
        _viewer(open_book); return

    all_books = crud.list_books()
    st.markdown("<h1 class='lib-title'>Library</h1>", unsafe_allow_html=True)
    st.session_state.setdefault("library_filter", "All")
    options = ["All"] + KINDS
    counts = {"All": len(all_books), **{k: sum(b["kind"] == k for b in all_books) for k in KINDS}}
    choice = st.segmented_control("Show", options, key="library_filter", label_visibility="collapsed",
                                  format_func=lambda o: f"{PLURAL.get(o, o)} ({counts[o]})") or "All"
    books = all_books if choice == "All" else [b for b in all_books if b["kind"] == choice]
    st.caption(f"{len(books)} {'Title' if len(books) == 1 else 'Titles'}")

    # Books fill rows of six; the dashed "+" add tile follows the last book.
    tiles = list(books) + ["add"]
    for row in range(0, len(tiles), COLUMNS):
        cols = st.columns(COLUMNS)
        for col, tile in zip(cols, tiles[row:row + COLUMNS]):
            with col:
                if tile == "add":
                    with st.container(key="add_book_tile"):
                        if st.button(" ", icon=":material/add:", key="add_book", width="stretch",
                                     help=None if all_books else "click to add pdf"):
                            _add_dialog()
                else:
                    _book_card(tile)
