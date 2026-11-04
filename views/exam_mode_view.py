"""Condensed high-yield exam study hub."""
import streamlit as st

import crud


def render():
    cid = st.session_state.get("course_id")
    if not cid:
        st.warning("Select or create a course first."); return
    course = crud.get_course(cid)

    core = crud.list_notes(cid, core_only=True)
    open_err = crud.list_errata(cid, status="open")
    due = crud.due_cards(cid)
    s = crud.course_stats(cid)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Syllabus done", f"{s['pct']:.0%}")
    m2.metric("Core concepts", len(core))
    m3.metric("Open errata", len(open_err))
    m4.metric("Cards due", len(due))

    tab_f, tab_c, tab_e = st.tabs(["📄 Formula sheet", "⭐ High-yield concepts", "🐞 Known errata"])
    with tab_f:
        formulas = [n for n in core if n["key_formula"]]
        if not formulas:
            st.info("Add a key formula to a core note to populate the sheet.")
        for n in formulas:
            with st.container(border=True):
                st.caption(n["title"])
                st.markdown(n["key_formula"])
    with tab_c:
        for n in core:
            with st.expander(n["title"]):
                if n["key_formula"]:
                    st.markdown(n["key_formula"])
                if n["derivation_md"]:
                    with st.expander("Derivation"):
                        st.markdown(n["derivation_md"])
                if n["ref_page"]:
                    st.caption(f"Textbook p.{n['ref_page']}")
    with tab_e:
        for e in open_err:
            st.markdown(f"🔴 **{e['note_title'] or 'General'}**: {e['description']}")
            if e["correction"]:
                st.markdown(f"✅ {e['correction']}")
        if not open_err:
            st.success("No open errata.")
