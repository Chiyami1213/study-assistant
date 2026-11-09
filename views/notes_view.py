"""Study notes (LaTeX, collapsible derivations) beside a reference PDF viewer, plus errata logger."""
import base64
from pathlib import Path

import streamlit as st

import crud
from database import BASE_DIR, PDF_DIR, data_path, stored_path


def render_note(note, mode):
    """Render one note according to the study mode. Shared with the exam hub."""
    st.subheader(note["title"])
    if note["ref_page"] and st.button(f"📖 Jump to p.{note['ref_page']}", key=f"jump_{note['id']}"):
        st.session_state["pdf_page"] = note["ref_page"]
        st.rerun()

    if mode == "Exam":
        if note["key_formula"]:
            st.markdown(note["key_formula"])
        if note["derivation_md"]:
            with st.expander("Derivation", expanded=False):
                st.markdown(note["derivation_md"])
    else:
        st.markdown(note["body_md"])
        if note["key_formula"]:
            st.markdown(note["key_formula"])
        if note["derivation_md"]:
            with st.expander("Step-by-Step Derivation", expanded=True):
                st.markdown(note["derivation_md"])


def pdf_viewer(ref):
    path = data_path(ref["pdf_path"]) if ref["pdf_path"] else None
    page = st.session_state["pdf_page"]
    c1, c2, c3 = st.columns([1, 2, 1])
    if c1.button("◀ Prev"):
        st.session_state["pdf_page"] = max(1, page - 1); st.rerun()
    st.session_state["pdf_page"] = c2.number_input(
        "Page", 1, ref["total_pages"] or 9999, page, label_visibility="collapsed")
    if c3.button("Next ▶"):
        st.session_state["pdf_page"] = page + 1; st.rerun()

    if path and path.exists():
        b64 = base64.b64encode(path.read_bytes()).decode()
        p = st.session_state["pdf_page"]
        st.markdown(f'<iframe src="data:application/pdf;base64,{b64}#page={p}" width="100%" '
                    f'height="700" style="border:0;border-radius:8px"></iframe>', unsafe_allow_html=True)
    else:
        st.info(f"No PDF attached to “{ref['title']}” yet. Upload one below to enable page jumping.")
    up = st.file_uploader("Attach / Replace PDF", type="pdf", key=f"up_{ref['id']}")
    if up:
        dest = PDF_DIR / f"ref_{ref['id']}.pdf"
        dest.write_bytes(up.getvalue())
        crud.set_reference_pdf(ref["id"], stored_path(dest))
        st.rerun()


def _errata_panel(cid, notes, refs):
    st.markdown("### 🐞 Errata")
    note_map = {0: "(none)", **{n["id"]: n["title"] for n in notes}}
    with st.form("add_erratum", clear_on_submit=True):
        desc = st.text_area("What's Wrong?", height=70)
        fix = st.text_input("Correction (Optional, LaTeX OK)")
        a, b = st.columns(2)
        nid = a.selectbox("Note", list(note_map), format_func=note_map.get)
        page = b.number_input("Page (0 = N/A)", 0, 9999, 0)
        if st.form_submit_button("Log Erratum") and desc:
            crud.add_erratum(cid, desc, fix, nid or None, refs[0]["id"] if refs and page else None, page or None)
            st.rerun()

    for e in crud.list_errata(cid):
        icon = "🟢" if e["status"] == "resolved" else "🔴"
        with st.container(border=True):
            st.markdown(f"{icon} **{e['note_title'] or 'General'}**" + (f" · p.{e['page']}" if e["page"] else ""))
            st.markdown(e["description"])
            if e["correction"]:
                st.markdown(f"✅ {e['correction']}")
            a, b, _ = st.columns([1, 1, 3])
            new = "open" if e["status"] == "resolved" else "resolved"
            if a.button("Reopen" if new == "open" else "Resolve", key=f"es_{e['id']}"):
                crud.set_erratum_status(e["id"], new); st.rerun()
            if b.button("Delete", key=f"ed_{e['id']}"):
                crud.delete_erratum(e["id"]); st.rerun()


def _new_note_form(cid):
    with st.expander("New Note"):
        with st.form("new_note", clear_on_submit=True):
            title = st.text_input("Title")
            body = st.text_area("Prose (Markdown + $LaTeX$)", height=100)
            deriv = st.text_area("Derivation (Collapsible)", height=100)
            formula = st.text_input("Key Formula (e.g., $$E=mc^2$$)")
            a, b = st.columns(2)
            imp = a.selectbox("Importance", ["core", "detail"], format_func=str.title)
            page = b.number_input("Reference Page (0 = None)", 0, 9999, 0)
            if st.form_submit_button("Save Note") and title:
                crud.add_note(cid, title, body, deriv, formula, imp, page or None)
                st.rerun()


def render():
    cid = st.session_state.get("course_id")
    if not cid:
        st.warning("Select or create a course first."); return
    course, mode = crud.get_course(cid), st.session_state["mode"]
    notes, refs = crud.list_notes(cid), crud.list_references(cid)

    left, right = st.columns(2) if refs else (st.container(), None)

    with left:
        tab_notes, tab_err = st.tabs(["Notes", "Errata"])
        with tab_notes:
            q = st.text_input("Search notes", placeholder="Search…", label_visibility="collapsed")
            shown = [n for n in notes if q.lower() in (n["title"] + n["body_md"]).lower()]
            if mode == "Exam":
                shown = [n for n in shown if n["importance"] == "core"]
                st.caption("Exam mode: core notes only, prose hidden, derivations collapsed.")
            for n in shown:
                render_note(n, mode)
                st.divider()
            _new_note_form(cid)
        with tab_err:
            _errata_panel(cid, notes, refs)

    if right is not None:
        with right:
            st.markdown(f"### 📖 {refs[0]['title']}")
            pdf_viewer(refs[0])
