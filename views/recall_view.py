"""Active recall: Leitner-box flashcards."""
import streamlit as st

import crud


def render():
    cid = st.session_state.get("course_id")
    if not cid:
        st.warning("Select or create a course first."); return
    course = crud.get_course(cid)

    cards, due = crud.list_cards(cid), crud.due_cards(cid)
    right = sum(c["times_right"] for c in cards)
    wrong = sum(c["times_wrong"] for c in cards)
    a, b, c = st.columns(3)
    a.metric("Total cards", len(cards))
    b.metric("Due now", len(due))
    c.metric("Accuracy", f"{right / (right + wrong):.0%}" if right + wrong else "–")

    tab_study, tab_manage = st.tabs(["Study", "Manage cards"])
    with tab_study:
        if not due:
            st.success("🎉 Nothing due. Come back later.")
        else:
            card = due[0]
            with st.container(border=True):
                st.caption(f"Box {card['box']} · {len(due)} remaining")
                st.markdown(f"### {card['question']}")
                show = st.toggle("Reveal answer", key=f"rev_{card['id']}")
                if show:
                    st.markdown(card["answer"])
            if show:
                x, y, _ = st.columns([1, 1, 3])
                if x.button("✅ Got it", key=f"ok_{card['id']}"):
                    crud.grade_card(card["id"], True); st.rerun()
                if y.button("❌ Missed", key=f"no_{card['id']}"):
                    crud.grade_card(card["id"], False); st.rerun()

    with tab_manage:
        notes = {0: "(none)", **{n["id"]: n["title"] for n in crud.list_notes(cid)}}
        with st.form("add_card", clear_on_submit=True):
            q = st.text_area("Question", height=70)
            ans = st.text_area("Answer", height=70)
            nid = st.selectbox("Linked note", list(notes), format_func=notes.get)
            if st.form_submit_button("Add card") and q and ans:
                crud.add_card(cid, q, ans, nid or None); st.rerun()
        for card in cards:
            x, y = st.columns([6, 1])
            x.markdown(f"**{card['question']}**  \n<small>Box {card['box']} · next {card['next_review']}</small>",
                       unsafe_allow_html=True)
            if y.button("🗑", key=f"dc_{card['id']}"):
                crud.delete_card(card["id"]); st.rerun()
