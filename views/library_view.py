"""Library: PDF books and reference material, shown as a cover grid with an add tile."""
import base64
import hashlib
import uuid

import streamlit as st

import crud
import pdfmeta
from database import BASE_DIR, PDF_DIR

COLUMNS = 6


def _cover_html(book):
    """Generated cover: a gradient picked from the title, with the title on it."""
    h = int(hashlib.md5(book["title"].encode()).hexdigest()[:6], 16)
    hue = h % 360
    title = book["title"].replace("<", "&lt;")
    return (f'<div class="book-cover" style="background: linear-gradient(155deg, hsl({hue},45%,38%), '
            f'hsl({(hue + 40) % 360},50%,24%));"><span>{title}</span></div>')


@st.dialog("Add book or PDF", width="large")
def _add_dialog():
    up = st.file_uploader("PDF file", type="pdf")
    info = {"title": "", "author": "", "edition": "", "pages": None, "source": ""}
    if up:
        cache = st.session_state.setdefault("_pdf_info", {})
        if up.file_id not in cache:
            with st.spinner("Reading PDF details..."):
                cache[up.file_id] = pdfmeta.extract_info(up.getvalue(), up.name)
        info = cache[up.file_id]
        found = [n for n in ("title", "author", "edition") if info[n]]
        st.caption("Detected " + (", ".join(found) if found else "nothing") +
                   f" from {info['source']} - edit anything that looks wrong.")
    k = up.file_id if up else "none"  # reset the fields whenever a different file is chosen
    title = st.text_input("Title", value=info["title"], key=f"bk_title_{k}")
    c1, c2 = st.columns(2)
    author = c1.text_input("Author", value=info["author"], key=f"bk_author_{k}")
    edition = c2.text_input("Edition / year", value=info["edition"], key=f"bk_edition_{k}",
                            placeholder="7th Edition (2019)")
    courses = {0: "None"} | {c["id"]: crud.label(c) for c in crud.list_courses(section=None)}
    course_id = st.selectbox("Course (optional)", list(courses), format_func=courses.get, key=f"bk_course_{k}")
    if st.button("Add to library", type="primary", disabled=not (up and title.strip())):
        PDF_DIR.mkdir(parents=True, exist_ok=True)
        dest = PDF_DIR / f"book_{uuid.uuid4().hex[:10]}.pdf"
        dest.write_bytes(up.getvalue())
        crud.add_book(title.strip(), author.strip(), edition.strip(), str(dest.relative_to(BASE_DIR)),
                      info["pages"], course_id or None)
        st.rerun()


def _viewer(book):
    if st.button("← Back to library"):
        st.session_state["open_book"] = None
        st.rerun()
    st.header(book["title"])
    path = BASE_DIR / book["pdf_path"]
    if not path.exists():
        st.error("The stored PDF file is missing."); return
    page = st.number_input("Page", 1, book["total_pages"] or 9999, 1)
    b64 = base64.b64encode(path.read_bytes()).decode()
    st.markdown(f'<iframe src="data:application/pdf;base64,{b64}#page={page}" width="100%" height="800" '
                f'style="border:0;border-radius:8px"></iframe>', unsafe_allow_html=True)


def render():
    st.session_state.setdefault("open_book", None)
    open_book = crud.get_book(st.session_state["open_book"]) if st.session_state["open_book"] else None
    if open_book:
        _viewer(open_book); return

    books = crud.list_books()
    st.markdown("<h1 class='lib-title'>Library</h1>", unsafe_allow_html=True)
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
                                     help=None if books else "click to add pdf"):
                            _add_dialog()
                    continue
                book = tile
                st.markdown(_cover_html(book), unsafe_allow_html=True)
                a, b = st.columns([3, 1])
                a.markdown('<span class="book-badge">PDF</span>', unsafe_allow_html=True)
                with b.popover("⋯"):
                    if st.button("Open", key=f"open_book_{book['id']}"):
                        st.session_state["open_book"] = book["id"]; st.rerun()
                    t = st.text_input("Title", value=book["title"], key=f"et_{book['id']}")
                    au = st.text_input("Author", value=book["author"] or "", key=f"ea_{book['id']}")
                    ed = st.text_input("Edition / year", value=book["edition"] or "", key=f"ee_{book['id']}")
                    if st.button("Save details", key=f"save_book_{book['id']}"):
                        crud.update_book(book["id"], t.strip() or book["title"], au.strip(), ed.strip()); st.rerun()
                    st.caption("Removing deletes the stored copy in data/pdfs.")
                    if st.button("Remove from library", key=f"del_book_{book['id']}"):
                        p = BASE_DIR / book["pdf_path"]
                        crud.delete_book(book["id"])
                        if p.exists():
                            p.unlink()
                        st.rerun()
                st.markdown(f"**{book['title']}**")
                sub = " · ".join(x for x in (book["author"], book["edition"]) if x)
                if sub:
                    st.caption(sub)
