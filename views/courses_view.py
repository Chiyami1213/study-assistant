"""Courses: a summary page of square course tiles, and the per-course hub."""
import html
import re

import streamlit as st

import base64

import crud
import icons
import photos
from views import library_view

COLUMNS = 5
RESOURCE_COLUMNS = 6


@st.cache_data(show_spinner=False, max_entries=64)
def _photo_b64(path, mtime):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def _photo_url(course_id):
    p = photos.photo_path(course_id)
    return f"data:image/jpeg;base64,{_photo_b64(str(p), p.stat().st_mtime)}" if p else None


def _icon_html(icon):
    """The course icon for a tile: custom SVGs are drawn with a mask, Material icons with the icon font."""
    icon = icon or ":material/book:"
    if icons.is_custom(icon):
        url = icons.mask_url(icon)
        return (f'<span class="ct-icon svg" style="-webkit-mask:{url} center/contain no-repeat; '
                f'mask:{url} center/contain no-repeat"></span>') if url else ""
    return f'<span class="ct-icon material">{html.escape(icon.strip(":").split("/")[-1])}</span>'


def _tile_html(course, status):
    color = crud.course_color(course)
    dark = crud.darken(color)
    # Numbered courses: number on top, name below. Self-Study subjects have no number, so the name is the top row.
    code = html.escape(course["code"] or course["name"])
    name = "" if (not course["code"] or course["name"] == course["code"]) else html.escape(course["name"])
    cat = f'<div class="ct-cat">{html.escape(course["category"])}</div>' if course.get("category") else ""
    meta = "".join(f"<div>{html.escape(x)}</div>" for x in (course["semester"], course.get("school")) if x)
    photo = _photo_url(course["id"])
    if photo:  # the photo shows through a tint of the course color so the text stays readable
        bg = f"linear-gradient(150deg, {color}c4, {dark}e6), url({photo}) center/cover"
    else:
        bg = f"linear-gradient(150deg, {color}, {dark})"
    return (f'<div class="course-tile" style="background: {bg};">'
            f'<div class="ct-top"><div class="ct-code{" ct-title" if not course["code"] else ""}">{code}</div>'
            f'{_icon_html(course.get("icon"))}</div>'
            f'{"<div class=ct-name>" + name + "</div>" if name else ""}'
            f'<div class="ct-meta">{cat}{meta}</div></div>')


NEW_CATEGORY = "New Category..."


def _category_picker(key, label="Category (Optional)", current=None):
    """Select a category, or type a new one. Returns the category name or None."""
    options = ["None"] + crud.all_categories() + [NEW_CATEGORY]
    choice = st.selectbox(label, options, index=options.index(current) if current in options else 0, key=key)
    if choice == NEW_CATEGORY:
        return crud.normalize_category(st.text_input("New Category Name", key=f"{key}_new"))
    return None if choice == "None" else choice


@st.dialog("Add Course", width="large")
def _add_course_dialog():
    c1, c2 = st.columns(2)
    status = c1.selectbox("Status", list(crud.STATUSES))
    name = c2.text_input("Name")
    code = c1.text_input("Course Number (Optional for Self-Study)", placeholder="PHYS 6105")
    sem = c2.text_input("Semester", value="Fall 2026")
    school = c1.text_input("School", placeholder="Georgia Tech")
    with c1:
        category = _category_picker("add_cat")
    with c2:
        with st.container(key="photo_box_new"):
            photo = st.file_uploader("Photo (Optional)", type=photos.PHOTO_TYPES)
    ready = bool(name.strip() and (code.strip() or status == "Self-Study"))
    if st.button("Add Course", type="primary", key="add_course_submit", disabled=not ready):
        cid = crud.add_course(code.strip(), name.strip(), sem.strip(), 0, status, school.strip(), category)
        if photo and not photos.save_photo(cid, photo.getvalue()):
            st.toast("The course was added, but that photo could not be read.")
        st.session_state["courses_filter"] = status
        st.rerun()


def _hero_html(course):
    """Top of a course page: the photo (or the course color) fills the top, with the title and labels on it."""
    color = crud.course_color(course)
    photo = _photo_url(course["id"])
    if photo:
        bg = f"linear-gradient(to top, rgba(0,0,0,0.72), rgba(0,0,0,0.12)), url({photo}) center/cover"
    else:
        bg = f"linear-gradient(150deg, {color}, {crud.darken(color)})"
    pills = "".join(f'<span class="ct-cat">{html.escape(x)}</span>'
                    for x in (crud.course_status(course), course.get("category")) if x)
    meta = html.escape(crud.term_label(course))
    return (f'<div class="course-hero" style="background: {bg};"><div class="ch-body">'
            f'<div class="ch-pills">{pills}</div><div class="ch-title">{html.escape(crud.label(course))}</div>'
            f'{"<div class=ch-meta>" + meta + "</div>" if meta else ""}</div></div>')


@st.dialog("Edit Course", width="large")
def _edit_course_dialog(course):
    cid = course["id"]
    c1, c2 = st.columns(2)
    cur = crud.course_status(course)
    status = c1.selectbox("Status", list(crud.STATUSES), index=crud.STATUSES.index(cur), key=f"ec_type_{cid}")
    name = c2.text_input("Name", value=course["name"] if course["name"] != course["code"] else "", key=f"ec_name_{cid}")
    code = c1.text_input("Course Number (Optional for Self-Study)", value=course["code"] or "", key=f"ec_code_{cid}")
    sem = c2.text_input("Semester", value=course["semester"] or "", key=f"ec_sem_{cid}")
    school = c1.text_input("School", value=course.get("school") or "", key=f"ec_school_{cid}")
    with c2:
        color = st.color_picker("Tile Color", value=crud.course_color(course), key=f"ec_color_{cid}")
    with c1:
        category = _category_picker(f"ec_cat_{cid}", "Category (Optional)", course.get("category"))
    with c2:
        with st.container(key=f"photo_box_edit_{cid}"):
            photo = st.file_uploader("Photo (Optional)", type=photos.PHOTO_TYPES, key=f"ec_photo_{cid}")

    ready = bool((name.strip() or code.strip()) and (code.strip() or status == "Self-Study"))
    a, b, c, _ = st.columns([1, 1.6, 1.4, 4])
    if a.button("Save", type="primary", key=f"ec_save_{cid}", disabled=not ready):
        crud.update_course_fields(cid, code.strip(), name.strip() or code.strip(), sem.strip(), school.strip(), category)
        photos.rename_photo(cid)  # keep the photo's file name matching the course
        if status != cur:
            crud.set_course_status(cid, status)
            st.session_state["courses_filter"] = status
        crud.set_course_color(cid, color if color != crud.course_color({**course, "color": None}) else None)
        if photo and not photos.save_photo(cid, photo.getvalue()):
            st.toast("That photo could not be read.")
        st.rerun()
    if photos.photo_path(cid) and b.button("Remove Photo", key=f"ec_rmphoto_{cid}"):
        photos.remove_photo(cid)
        st.rerun()

    st.divider()
    confirm = f"confirm_delete_course_{cid}"
    if st.button("Delete Course", key=f"ec_del_{cid}"):
        st.session_state[confirm] = True
    if st.session_state.get(confirm):
        st.warning("This also deletes the course's notes, homework, flashcards and errata. It cannot be undone.")
        if st.button("Yes, Delete It", type="primary", key=f"ec_del_yes_{cid}"):
            crud.delete_course(cid)
            photos.remove_photo(cid)
            if st.session_state.get("open_course") == cid:
                st.session_state["open_course"] = None
            st.session_state[confirm] = False
            st.rerun()


SORTS = ["Default", "Course Number", "Name", "Category", "Semester", "School", "Status"]
TERM_RANK = {"winter": 0, "spring": 1, "summer": 2, "fall": 3}


def _semester_key(course):
    """Newest semester first; unrecognized and blank semesters go last."""
    m = re.match(r"\s*(winter|spring|summer|fall)\s*(\d{4})", course["semester"] or "", re.I)
    return (0, -int(m.group(2)), -TERM_RANK[m.group(1).lower()]) if m else (1, 0, 0)


def _sorted_groups(courses, sort_by):
    """[(heading, courses)] - one unlabeled group for flat sorts, headed groups for label sorts."""
    if sort_by == "Course Number":
        return [("", sorted(courses, key=lambda c: (not c["code"], crud._natural_key(c["code"] or c["name"]))))]
    if sort_by == "Name":
        return [("", sorted(courses, key=lambda c: c["name"].lower()))]
    if sort_by == "Default":
        return [("", courses)]
    if sort_by == "Category":
        order = {name: i for i, name in enumerate(crud.all_categories())}
        key = lambda c: (order.get(c.get("category"), len(order)), crud._natural_key(c["code"] or c["name"]))
        label = lambda c: c.get("category") or "No category"
    elif sort_by == "Semester":
        key = lambda c: (_semester_key(c), crud._natural_key(c["code"] or c["name"]))
        label = lambda c: c["semester"] or "No semester"
    elif sort_by == "School":
        key = lambda c: (not c.get("school"), (c.get("school") or "").lower(), crud._natural_key(c["code"] or c["name"]))
        label = lambda c: c.get("school") or "No school"
    else:  # Status
        key = lambda c: (crud.STATUSES.index(crud.course_status(c)), crud._natural_key(c["code"] or c["name"]))
        label = crud.course_status
    groups = {}
    for c in sorted(courses, key=key):
        groups.setdefault(label(c), []).append(c)
    return list(groups.items())


def render():
    open_id = st.session_state.get("open_course")
    course = crud.get_course(open_id) if open_id else None
    if course:
        if st.button("← All Courses", key="course_back"):
            st.session_state["open_course"] = None
            st.rerun()
        st.markdown(_hero_html(course), unsafe_allow_html=True)  # banner between the button row and the tabs
        _manage(course)
        return

    head, btn = st.columns([6, 1.3], vertical_alignment="center")
    head.title("Courses")
    if btn.button("Add Course", key="add_course_open"):
        _add_course_dialog()
    st.session_state.setdefault("courses_filter", "Active")
    groups = {s: crud.courses_by_status(s) for s in crud.STATUSES}
    groups = {"All": [c for s in crud.STATUSES for c in groups[s]], **groups}
    f1, f2, f3 = st.columns([3, 1.3, 1.3], vertical_alignment="center")
    with f1:
        choice = st.segmented_control(
            "Show", list(groups), key="courses_filter", label_visibility="collapsed",
            format_func=lambda s: f"{s} ({len(groups[s])})") or "Active"
    with f2:
        category = st.selectbox("Category", ["All Categories"] + crud.all_categories(), key="courses_category",
                                label_visibility="collapsed")
    with f3:
        sort_by = st.selectbox("Sort by", SORTS, key="courses_sort", label_visibility="collapsed",
                               format_func=lambda s: f"Sort: {s}")
    courses = groups[choice]
    if category != "All Categories":
        courses = [c for c in courses if c.get("category") == category]

    if not courses:
        st.info(f"No {choice.lower()} courses" + ("" if category == "All Categories" else f" in {category}") + ".")
    for title, items in _sorted_groups(courses, sort_by):
        if title:
            st.markdown(f"#### {title} ({len(items)})")
        _tile_grid(items)


def _tile_grid(courses):
    for row in range(0, len(courses), COLUMNS):
        cols = st.columns(COLUMNS)
        for col, c in zip(cols, courses[row:row + COLUMNS]):
            with col:
                with st.container(key=f"coursetile_{c['id']}"):
                    st.markdown(_tile_html(c, crud.course_status(c)), unsafe_allow_html=True)
                    if st.button(" ", key=f"tile_{c['id']}"):  # invisible button laid over the tile
                        st.session_state["course_id"] = c["id"]
                        st.session_state["open_course"] = c["id"]
                        st.rerun()
                    if st.button("...", key=f"tilemenu_{c['id']}", type="tertiary"):  # bottom-right edit menu
                        _edit_course_dialog(c)


def _resource_card(book):
    """A library file as a small tile; clicking it opens the file's preview in the Library."""
    with st.container(key=f"bookcard_res_{book['id']}"):
        st.markdown(library_view._cover_html(book), unsafe_allow_html=True)
        if st.button(" ", key=f"cover_res_{book['id']}"):  # invisible button laid over the cover
            st.session_state["page"] = "Library"
            st.session_state["open_book"] = book["id"]
            st.rerun()
    chips = "".join(f'<span class="book-badge meta">{html.escape(x)}</span>'
                    for x in (book["kind"], f"Lec {book['lecture']}" if book.get("lecture") else "",
                              book["edition"], book.get("year")) if x)
    st.markdown(f'<div class="book-badges">{chips}</div>', unsafe_allow_html=True)
    st.markdown(f"**{book['title']}**")
    if book["author"]:
        st.caption(book["author"])


def _resource_grid(books):
    for row in range(0, len(books), RESOURCE_COLUMNS):
        cols = st.columns(RESOURCE_COLUMNS)
        for col, book in zip(cols, books[row:row + RESOURCE_COLUMNS]):
            with col:
                _resource_card(book)


def _resources(course):
    """Library files linked to this course: course notes first, then textbooks."""
    files = [b for b in crud.list_books() if b["course_id"] == course["id"]]
    # Notes with a lecture number come first, in lecture order; then the rest by title.
    by_title = lambda b: ((0, crud._natural_key(b["lecture"])) if b.get("lecture") else (1, []),
                          crud._natural_key(b["title"]))
    notes = sorted((b for b in files if b["kind"] in ("Lecture Notes", "Notes")), key=by_title)
    textbooks = sorted((b for b in files if b["kind"] == "Textbook"), key=by_title)
    st.subheader("Course Notes")
    if notes:
        _resource_grid(notes)
    else:
        st.caption("No course notes yet. Add a file in the Library and choose this course.")
    st.subheader("Textbooks")
    if textbooks:
        _resource_grid(textbooks)
    else:
        st.caption("No textbooks yet. Add a file in the Library and choose this course.")


def _manage(course):
    """The course page below the banner: Overview (blank for now) and Resources."""
    overview, resources = st.tabs(["Overview", "Resources"])
    with overview:
        st.empty()
    with resources:
        _resources(course)
