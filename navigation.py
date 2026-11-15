"""In-app page history shared by the mouse buttons and the on-screen back buttons.

The history (st.session_state["nav_history"]) holds the views in the order they were visited; "nav_forward" holds the views left by going back. A view is
(page, open course, open file, inside): `inside` is where the student was within the page, so Back returns to that very place and not only to the page: the Calendar or
the Task List, the Library's tile (a type or a course) and how it is sorted. Views stored by an older version have three parts and are still understood.
"""
import streamlit as st


def inside_state():
    """Where the student is within the current page, as something that can be compared and stored (None when the page has no inside)."""
    page = st.session_state.get("page")
    if page == "Calendar":
        return ("page", st.session_state.get("cal_page") or "Calendar")
    if page == "Library":
        lib = st.session_state.get("_lib") or {}
        if st.session_state.get("open_book"):
            return None                                                    # a file is open: the file is the place
        return ("lib", lib.get("sort", "Type"), lib.get("tile"), (lib.get("inner") or {}).get(lib.get("sort", "Type")))
    return None


def restore_inside(page, inside):
    """Put the inside of a page back (before the page is drawn)."""
    if not inside:
        return
    if inside[0] == "page" and page == "Calendar":
        st.session_state["cal_page"] = inside[1]
    elif inside[0] == "lib" and page == "Library":
        _, sort, tile, inner = inside
        lib = st.session_state.setdefault("_lib", {"sort": "Type", "tile": None, "inner": {}, "desc": True, "view": "Cards"})
        lib["sort"], lib["tile"] = sort, tile
        if inner:
            lib.setdefault("inner", {})[sort] = inner
            st.session_state[f"library_inner_{sort}"] = inner
        st.session_state["library_sort"] = sort


def restore_view(view):
    """Show a stored view again (and rerun). The view is already in the history, so it is not recorded twice."""
    page, open_course, open_book = view[:3]
    inside = view[3] if len(view) > 3 else None
    st.session_state["page"] = page
    st.session_state["open_course"] = open_course
    st.session_state["open_book"] = open_book
    if open_course:
        st.session_state["course_id"] = open_course
    restore_inside(page, inside)
    st.session_state["_going_back"] = True
    st.rerun()


def current_view():
    return (st.session_state["page"], st.session_state.get("open_course"), st.session_state.get("open_book"), inside_state())


def record_view():
    """Called on every run: a new place is added to the history (and clears what Forward would have reached); a Back or a Forward that was just made is not recorded again."""
    view = current_view()
    if st.session_state.pop("_going_back", False):
        return view
    hist = st.session_state.setdefault("nav_history", [])
    if not hist or hist[-1] != view:
        hist.append(view)
        del hist[:-50]
        st.session_state["nav_forward"] = []
    return view


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
