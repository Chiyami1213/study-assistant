"""Courses: a summary page of square course tiles, and the per-course hub."""
import html
import re

import streamlit as st

import base64

import crud
import icons
import photos
from views import exam_mode_view, homework_view, notes_view, recall_view

COLUMNS = 5


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
    status = c1.selectbox("Type", list(crud.STATUSES))
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


SORTS = ["Default", "Course Number", "Name", "Category", "Semester", "School", "Type"]
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
    else:  # Type
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
        if st.button("← All Courses"):
            st.session_state["open_course"] = None
            st.rerun()
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


def _manage(course):
    cid = course["id"]
    st.header(crud.label(course))
    sub = " · ".join(x for x in (course.get("category"), crud.term_label(course)) if x)
    if sub:
        st.caption(sub)
    banner = _photo_url(cid)
    if banner:
        st.markdown(f'<div class="course-banner" style="background-image:url({banner})"></div>', unsafe_allow_html=True)
    t_syl, t_notes, t_hw, t_exam, t_rec = st.tabs(["Syllabus", "Notes", "Homework", "Exam Hub", "Recall"])
    with t_notes:
        notes_view.render()
    with t_hw:
        homework_view.render()
    with t_exam:
        exam_mode_view.render()
    with t_rec:
        recall_view.render()
    with t_syl:
        _syllabus(course)


def _syllabus(course):
    cid = course["id"]
    left, right = st.columns([3, 2])

    with left:
        for t in crud.list_topics(cid):
            done = st.checkbox(f"Week {t['week'] or '–'}: {t['title']}", value=bool(t["completed"]),
                               key=f"topic_{t['id']}")
            if done != bool(t["completed"]):
                crud.set_topic_done(t["id"], done)
                st.rerun()
        with st.form(f"add_topic_{cid}", clear_on_submit=True):
            a, b = st.columns([1, 4])
            week = a.number_input("Week", 1, 52, 1)
            title = b.text_input("New Topic")
            if st.form_submit_button("Add Topic") and title:
                crud.add_topic(cid, week, title)
                st.rerun()

    with right:
        st.subheader("Log Study Time")
        with st.form(f"log_{cid}", clear_on_submit=True):
            h = st.number_input("Hours", 0.25, 12.0, 1.0, 0.25)
            note = st.text_input("What Did You Study?")
            if st.form_submit_button("Log"):
                crud.log_hours(cid, h, note)
                st.rerun()
        for l in crud.recent_logs(cid):
            st.caption(f"{l['logged_on']} · {l['hours']}h · {l['note'] or ''}")

        with st.expander("Semester, School, and Color"):
            sem = st.text_input("Semester", value=course["semester"] or "", key=f"sem_{cid}")
            sch = st.text_input("School", value=course.get("school") or "", key=f"sch_{cid}")
            cat = _category_picker(f"cat_{cid}", "Category", course.get("category"))
            color = st.color_picker("Tile Color", value=crud.course_color(course), key=f"color_{cid}")
            with st.container(key=f"photo_box_{cid}"):
                up = st.file_uploader("Course Photo", type=photos.PHOTO_TYPES, key=f"photo_{cid}")
            if photos.photo_path(cid) and st.button("Remove Photo", key=f"rm_photo_{cid}"):
                photos.remove_photo(cid)
                st.rerun()
            a, b, _ = st.columns([1, 2, 3])
            if a.button("Save", key=f"save_term_{cid}"):
                if up and not photos.save_photo(cid, up.getvalue()):
                    st.toast("That photo could not be read.")
                crud.update_course_info(cid, sem.strip(), sch.strip())
                crud.set_course_color(cid, color)
                crud.set_course_category(cid, cat)
                st.rerun()
            if b.button("Default Color", key=f"reset_color_{cid}"):
                crud.set_course_color(cid, None)
                st.rerun()

        cur = crud.course_status(course)
        status = st.radio("Type", list(crud.STATUSES), index=crud.STATUSES.index(cur), horizontal=True,
                          key=f"status_{cid}")
        if status != cur:
            crud.set_course_status(cid, status)
            st.session_state["courses_filter"] = status
            st.rerun()
