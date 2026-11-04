"""In-app page history shared by the mouse buttons and the on-screen back buttons.

The history (st.session_state["nav_history"]) holds (page, open course, open file) views in the order they were
visited; "nav_forward" holds the views left by going back.
"""
import streamlit as st


def restore_view(view):
    """Show a stored view again (and rerun). The view is already in the history, so it is not recorded twice."""
    page, open_course, open_book = view
    st.session_state["page"] = page
    st.session_state["open_course"] = open_course
    st.session_state["open_book"] = open_book
    if open_course:
        st.session_state["course_id"] = open_course
    st.session_state["_going_back"] = True
    st.rerun()


def go_back():
    """Return to the previous view. Returns False (and does nothing) when there is no earlier view."""
    hist = st.session_state.setdefault("nav_history", [])
    if len(hist) < 2:
        return False
    st.session_state.setdefault("nav_forward", []).append(hist.pop())
    restore_view(hist[-1])


def go_forward():
    """Go forward again to the view left by the last back. Returns False when there is nothing to go forward to."""
    fwd = st.session_state.setdefault("nav_forward", [])
    if not fwd:
        return False
    view = fwd.pop()
    st.session_state.setdefault("nav_history", []).append(view)
    restore_view(view)
