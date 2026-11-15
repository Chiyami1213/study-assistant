"""Courses: a summary page of square course tiles, and the per-course hub."""
import html
import re
from datetime import date

import streamlit as st

import base64

import crud
import eqsheet
import settings
import syllabus
import icons
import photos
from views import course_tree, library_view, quiz_view

COLUMNS = 5
RESOURCE_COLUMNS = 6


@st.cache_data(show_spinner=False, max_entries=64)
def _photo_b64(path, mtime, width):
    """The photo scaled down to `width` pixels (a 3000 px photo decoded for every tile made the Courses page slow); the scaled copy is kept
    under data/course_photos/thumbs so it is made once."""
    import pathlib
    src = pathlib.Path(path)
    thumb = src.parent / "thumbs" / f"{src.stem}_{width}_{int(mtime)}.jpg"
    if not thumb.exists():
        from PIL import Image
        with Image.open(src) as im:
            im = im.convert("RGB")
            if im.width > width:
                im = im.resize((width, max(1, round(im.height * width / im.width))), Image.LANCZOS)
            thumb.parent.mkdir(exist_ok=True)
            for old in thumb.parent.glob(f"{src.stem}_{width}_*.jpg"):      # an earlier version of this photo
                old.unlink(missing_ok=True)
            im.save(thumb, "JPEG", quality=82, optimize=True)
    return base64.b64encode(thumb.read_bytes()).decode()


def _photo_url(course_id, width=640):
    p = photos.photo_path(course_id)
    return f"data:image/jpeg;base64,{_photo_b64(str(p), p.stat().st_mtime, width)}" if p else None


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
    code = html.escape(crud.show_code(course["code"]) or course["name"])
    name = "" if (not crud.show_code(course["code"]) or course["name"] == course["code"]) else html.escape(course["name"])
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
    code = c1.text_input("Course Number (Optional for Self-Study)", placeholder="MATH 101")
    sem = c2.text_input("Semester", value="Fall 2026")
    school = c1.text_input("School", placeholder="Your University")
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
        st.session_state["_courses_filter_kept"] = status
        st.rerun()


def _hero_html(course):
    """Top of a course page: the photo (or the course color) fills the top, with the title and labels on it."""
    color = crud.course_color(course)
    photo = _photo_url(course["id"], 1800)
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
            st.session_state["_courses_filter_kept"] = status
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
        return [("", sorted(courses, key=lambda c: (not c["code"], crud._natural_key(crud.show_code(c["code"]) or c["name"]))))]
    if sort_by == "Name":
        return [("", sorted(courses, key=lambda c: c["name"].lower()))]
    if sort_by == "Default":
        return [("", courses)]
    if sort_by == "Category":
        order = {name: i for i, name in enumerate(crud.all_categories())}
        key = lambda c: (order.get(c.get("category"), len(order)), crud._natural_key(crud.show_code(c["code"]) or c["name"]))
        label = lambda c: c.get("category") or "No category"
    elif sort_by == "Semester":
        key = lambda c: (_semester_key(c), crud._natural_key(crud.show_code(c["code"]) or c["name"]))
        label = lambda c: c["semester"] or "No semester"
    elif sort_by == "School":
        key = lambda c: (not c.get("school"), (c.get("school") or "").lower(), crud._natural_key(crud.show_code(c["code"]) or c["name"]))
        label = lambda c: c.get("school") or "No school"
    else:  # Status
        key = lambda c: (crud.STATUSES.index(crud.course_status(c)), crud._natural_key(crud.show_code(c["code"]) or c["name"]))
        label = crud.course_status
    groups = {}
    for c in sorted(courses, key=key):
        groups.setdefault(label(c), []).append(c)
    return list(groups.items())


def render():
    open_id = st.session_state.get("open_course")
    course = crud.get_course(open_id) if open_id else None
    if course:
        if st.session_state.get("_recent_touched") != course["id"]:          # opened now: remember it for the Recent list
            st.session_state["_recent_touched"] = course["id"]
            settings.touch_course(course["id"])
        if st.session_state.get("lib_toast"):
            st.toast(st.session_state.pop("lib_toast"))
        back_col, update_col, _gap = st.columns([1.4, 2.2, 6])
        if back_col.button("← All Courses", key="course_back"):
            st.session_state["open_course"] = None
            st.session_state.pop("course_tab", None)
            st.rerun()
        if update_col.button("Update Files", key="course_update_files", icon=":material/sync:", help="reads the folder your files are kept in and lists the new and the changed ones for this course"):
            from views import library_import
            library_import.folder_dialog(course["id"])
        st.markdown(_hero_html(course), unsafe_allow_html=True)  # banner between the button row and the tabs
        _manage(course)
        return

    st.session_state.pop("_recent_touched", None)
    head, btn = st.columns([6, 1.3], vertical_alignment="center")
    head.title("Courses")
    if btn.button("Add Course", key="add_course_open"):
        _add_course_dialog()
    # The filter, category and sort are remembered apart from their widgets (a widget's value is dropped while a course or a file is open), so Back
    # from a course, or from a file opened in it, returns to the same tab, for example Completed.
    for key in ("courses_filter", "courses_category", "courses_sort"):
        st.session_state.setdefault(key, st.session_state.get(f"_{key}_kept") or ("Active" if key == "courses_filter" else None))
        if st.session_state[key] is None:
            del st.session_state[key]
    groups = {s: crud.courses_by_status(s) for s in crud.STATUSES}
    everyone = [c for s in crud.STATUSES for c in groups[s]]
    opened = settings.get_recent_courses()
    recent = sorted((c for c in everyone if str(c["id"]) in opened), key=lambda c: opened[str(c["id"])], reverse=True)   # opened most lately first
    groups = {"Recent": recent, "All": everyone, **groups}
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
    for key, value in (("courses_filter", choice), ("courses_category", category), ("courses_sort", sort_by)):
        st.session_state[f"_{key}_kept"] = value
    courses = groups[choice]
    if category != "All Categories":
        courses = [c for c in courses if c.get("category") == category]

    if not courses:
        st.info("No courses opened yet." if choice == "Recent" and category == "All Categories"
                else f"No {choice.lower()} courses" + ("" if category == "All Categories" else f" in {category}") + ".")
    if choice == "All":                                          # the All tab can also be read as a tree of knowledge
        st.session_state.setdefault("courses_view", st.session_state.get("_courses_view_kept", "Tiles"))
        v1, _gap = st.columns([2, 6])
        with v1:
            view = st.segmented_control("View", ["Tiles", "Tree"], key="courses_view", label_visibility="collapsed",
                                        format_func=lambda v: ":material/grid_view: Tiles" if v == "Tiles" else ":material/account_tree: Tree") or "Tiles"
        st.session_state["_courses_view_kept"] = view
        if view == "Tree" and courses:
            _tree(courses)
            return
    if choice == "Recent":                                       # one list, the course opened most lately first
        _tile_grid(courses)
        return
    for title, items in _sorted_groups(courses, sort_by):
        if title:
            st.markdown(f"#### {title} ({len(items)})")
        _tile_grid(items)


def _tree(courses):
    """The courses as a tree of knowledge: a click on a leaf opens the course; the branches fold and unfold (script and CSS in app.py)."""
    sink = st.text_input("Tree Click", key="tree_sink", label_visibility="collapsed")
    if sink and sink != st.session_state.get("_tree_sink_done"):
        st.session_state["_tree_sink_done"] = sink
        try:
            cid = int(sink.split("|")[0])
        except ValueError:
            cid = None
        if cid and crud.get_course(cid):
            st.session_state["course_id"] = cid
            st.session_state["open_course"] = cid
            st.session_state.pop("course_tab", None)
            st.rerun()
    st.caption("Similar fields grow from the same branch of the map.")
    st.markdown(course_tree.tree_html(courses, crud.course_status, crud.course_color, st.session_state.get("course_id")), unsafe_allow_html=True)


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
                        st.session_state.pop("course_tab", None)
                        st.rerun()
                    if st.button("...", key=f"tilemenu_{c['id']}", type="tertiary"):  # bottom-right edit menu
                        _edit_course_dialog(c)


def _resource_card(book):
    """A library file as a small tile; clicking it opens the file's preview in the Library."""
    with st.container(key=f"bookcard_res_{book['id']}"):
        st.markdown(library_view._cover_html(book), unsafe_allow_html=True)
        if st.button(" ", key=f"cover_res_{book['id']}"):  # invisible button laid over the cover
            st.session_state["course_tab"] = (st.session_state.get("open_course"), "Resources")
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
    """The web links of the course first, then the Library files linked to it (Course Notes, Notes, Textbooks, and what else there is). Every section folds."""
    files = [b for b in crud.list_books() if course["id"] in b["course_ids"] and crud.in_part(b["title"], course.get("part"))]
    # Notes with a lecture number come first, in lecture order; then the rest by title.
    order = lambda b: ((0, crud._natural_key(b["lecture"])) if b.get("lecture") else (1, []),
                       crud._natural_key(b["title"]))
    _links(course)
    sections = [
        ("Course Notes", ("Lecture Notes",), "No course notes yet."),
        ("Notes", ("Notes",), "No notes yet."),
        ("Textbooks", ("Textbook",), "No textbooks yet."),
    ]
    for heading, kinds, empty in sections:
        items = sorted((b for b in files if b["kind"] in kinds), key=order)
        with st.expander(f"{heading} ({len(items)})", expanded=bool(items)):
            if items:
                _resource_grid(items)
            else:
                st.caption(f"{empty} Add a file in the Library and choose this course.")


@st.dialog("Add Link", width="large")
def _add_link_dialog(course):
    url = st.text_input("URL", placeholder="https://")
    title = st.text_input("Title (Optional)", placeholder="Class Page")
    bad = bool(url.strip()) and not crud.normalize_url(url)
    if bad:
        st.caption("That does not look like a web address.")
    if st.button("Add Link", type="primary", key=f"link_add_{course['id']}", disabled=not url.strip() or bad):
        crud.add_link(course["id"], title, url)
        st.rerun()


def _links(course):
    """Web links of the course (class page, syllabus ...), opened in a new tab."""
    links = crud.list_links(course["id"])
    with st.expander(f"Links ({len(links)})", expanded=True):
        if st.button("Add Link", key=f"link_open_{course['id']}", icon=":material/add_link:"):
            _add_link_dialog(course)
        if not links:
            st.caption("No links yet.")
        for ln in links:
            a, b = st.columns([8, 1], vertical_alignment="center")
            a.markdown(f'<a class="res-link" href="{html.escape(ln["url"], quote=True)}" target="_blank" '
                       f'rel="noopener noreferrer" title="{html.escape(ln["url"], quote=True)}">'
                       f'{html.escape(ln["title"])}</a>', unsafe_allow_html=True)
            if b.button("Remove", key=f"link_rm_{ln['id']}"):
                crud.delete_link(ln["id"]); st.rerun()


def _when(day, time):
    """'Mon, Nov 9 · 22:00' (the year is added only when it is not the current year)."""
    if not day:
        return "No date"
    d = date.fromisoformat(day)
    text = f"{d.strftime('%a, %b')} {d.day}" + (f", {d.year}" if d.year != date.today().year else "")
    return text + (f" · {time}" if time else "")


def _homework_book(course_id, hw_title, kind="Homework"):
    """The Library homework file whose number matches this homework ("HW 4" -> the file numbered 4), or None."""
    num = re.search(r"\d+", crud.strip_part(hw_title))
    if not num:
        return None
    for b in crud.list_books():
        if b["kind"] == kind and course_id in b["course_ids"] and crud.part_tag(b["title"]) == crud.part_tag(hw_title):      # the same part of a merged course
            n = re.search(r"\d+", b.get("lecture") or crud.strip_part(b["title"]))
            if n and int(n.group()) == int(num.group()):
                return b
    return None


def _exam_book(course_id, event_title, kind="Exam", word=None):
    """The Library exam file of this course for an event like "Midterm 2" or "Final Exam" (same kind of exam, same number);
    with `word`, only a file whose title contains it ("Reflection", "Statistics")."""
    def key(text):
        t = crud.strip_part(text).lower()
        kind = "midterm" if re.search(r"mid[\s_\-]*term", t) else "final" if "final" in t else "exam"
        n = re.search(r"\d+", t)
        return kind, (n.group() if n else None), crud.part_tag(text)

    want = key(event_title)
    for b in crud.list_books():
        if (b["kind"] == kind and course_id in b["course_ids"] and key(b["title"]) == want and "practice" not in b["title"].lower()
                and (word is None or word.lower() in b["title"].lower())):
            return b
    return None


def _grade_html(item):
    """"Grade 95/100" and the grader's comments, as small lines under a row; empty when the item has no grade."""
    if item.get("score") is None or not item.get("points"):
        return '<div class="dl-grade none">Not graded</div>'
    num = lambda x: f"{x:g}"
    out = f'<div class="dl-grade">Grade <b>{num(item["score"])}/{num(item["points"])}</b> ({item["score"] / item["points"]:.0%})</div>'
    for line in (item.get("grade_note") or "").splitlines():
        if line.strip():
            out += f'<div class="dl-sub">{html.escape(line.strip())}</div>'
    return out


def _row_html(title, when, status, css, detail=None, book=None, solution=None, extra="", graded=None, tab="Overview", guide=None, reflection=None, stats=None):
    sub = (f'<div class="dl-sub">{html.escape(detail).replace(chr(10), "<br>")}</div>' if detail else "") + extra
    name = html.escape(title)
    if book:                                              # opens the homework PDF, and Back returns to the Overview
        name = f'<a href="#" data-ol-book="{book["id"]}" data-ol-page="1" data-ol-tab="{tab}" title="open the pdf">{name}</a>'
    if solution:                                          # a second link when the solution file is in the Library
        name += (f' <a class="dl-solution" href="#" data-ol-book="{solution["id"]}" data-ol-page="1" data-ol-tab="{tab}" '
                 f'title="open the solution">Solution</a>')
    if guide:                                             # how to prepare for an upcoming exam
        name += (f' <a class="dl-solution" href="#" data-ol-book="{guide["id"]}" data-ol-page="1" data-ol-tab="{tab}" '
                 f'title="open the preparation document">Preparation</a>')
    if stats:                                             # the class's results, as the professor released them
        name += (f' <a class="dl-solution" href="#" data-ol-book="{stats["id"]}" data-ol-page="1" data-ol-tab="{tab}" '
                 f'title="open the class statistics">Class Stats</a>')
    if reflection:                                        # what a finished exam teaches for the next one
        name += (f' <a class="dl-solution" href="#" data-ol-book="{reflection["id"]}" data-ol-page="1" data-ol-tab="{tab}" '
                 f'title="open the reflection document">Reflection</a>')
    if graded:                                            # my own submission with the grading marked on it
        name += (f' <a class="dl-solution" href="#" data-ol-book="{graded["id"]}" data-ol-page="1" data-ol-tab="{tab}" '
                 f'title="open my graded submission">Graded</a>')
    return (f'<div class="dl-row"><div><div class="dl-title">{name}</div>{sub}</div>'
            f'<div class="dl-when">{html.escape(when)}</div><span class="dl-pill {css}">{status}</span></div>')


def _percent(items):
    """Average percentage of the graded items (score/points), or None when none is graded."""
    marks = [i["score"] / i["points"] for i in items if i.get("score") is not None and i.get("points")]
    return sum(marks) / len(marks) if marks else None


def _homework_status(h, today):
    if h["status"] == "verified":
        return "Done", "done"
    if not h["due_date"]:
        return "No Date", "none"
    if h["due_date"] < today:
        return "Overdue", "late"
    return "Open", "open"


def _homework_items(course):
    return sorted((h for h in crud.list_homework(course["id"]) if crud.in_part(h["title"], course.get("part"))),
                  key=lambda h: (h["due_date"] or "9999-12-31", crud._natural_key(h["title"])))


def _exam_items(course):
    return sorted((e for e in crud.list_events("2000-01-01", "2100-12-31")
                   if e["course_id"] == course["id"] and re.search(r"midterm|final|exam", e["title"], re.I) and crud.in_part(e["title"], course.get("part"))),
                  key=lambda e: (e["date"], e.get("time") or ""))


def _pie(rows, center_top, center_bottom):
    """A donut of what each part of the grade is worth (the syllabus weights), in the chart colors of the theme.
    Hovering a slice names it; the table beside it carries the numbers."""
    import math
    total = sum(r["percent"] for r in rows) or 1
    cx = cy = 90
    outer, inner = 84, 54
    angle = -math.pi / 2
    paths = ""
    for i, r in enumerate(rows):                       # every part of the grade gets its own slice and color (eight colors, then they repeat)
        sweep = r["percent"] / total * 2 * math.pi
        a0, a1 = angle, angle + sweep - 1e-4
        angle += sweep
        pt = lambda rad, a: (cx + rad * math.cos(a), cy + rad * math.sin(a))
        (x0, y0), (x1, y1), (x2, y2), (x3, y3) = pt(outer, a0), pt(outer, a1), pt(inner, a1), pt(inner, a0)
        big = 1 if sweep > math.pi else 0
        paths += (f'<path class="syl-slice" d="M{x0:.2f},{y0:.2f} A{outer},{outer} 0 {big} 1 {x1:.2f},{y1:.2f} '
                  f'L{x2:.2f},{y2:.2f} A{inner},{inner} 0 {big} 0 {x3:.2f},{y3:.2f} Z" fill="var(--s{i % 8 + 1})" stroke="var(--bg)" '
                  f'stroke-width="2.5"><title>{html.escape(r["item"])}: {r["percent"]:g}% of the grade</title></path>')
    return (f'<svg class="syl-pie" viewBox="0 0 180 180" role="img" aria-label="What each part of the grade is worth">{paths}'
            f'<text x="90" y="88" text-anchor="middle" class="syl-c1">{html.escape(center_top)}</text>'
            f'<text x="90" y="108" text-anchor="middle" class="syl-c2">{html.escape(center_bottom)}</text></svg>')


def _weights(course, data):
    """What each part of the grade is worth: the donut chart and, under it, the table with your score so far."""
    rows = data.get("rows") or []
    if not rows:
        return
    homework, events = _homework_items(course), _exam_items(course)
    body = ""
    for i, r in enumerate(rows):
        got = syllabus.score(r.get("kind"), homework, events)
        mine = f"{got:.0%}" if got is not None else ("Not graded" if r.get("kind") else "None")
        body += (f"<tr><td><span class='syl-sw' style='background:var(--s{i % 8 + 1})'></span>{html.escape(r['item'])}</td>"
                 f"<td class='n'>{r['percent']:g}%</td><td class='n{' none' if got is None else ''}'>{mine}</td></tr>")
    est = syllabus.standing(data, homework, events)
    top, bottom = ("100%", "of the grade") if not est else (syllabus.letter(est[0], data)[0], f"{est[0]:.1f}% now")
    st.markdown(f"<div class='syl-stack'>{_pie(rows, top, bottom)}<table class='syl-table'><thead><tr><th>Part of the Grade</th>"
                f"<th class='n'>Weight</th><th class='n'>Your Score So Far</th></tr></thead><tbody>{body}</tbody></table></div>",
                unsafe_allow_html=True)


def _syllabus_data(course):
    """The syllabus data of the course, or of the chosen part of a merged course (none while all parts are shown: each part has its own grading)."""
    if course.get("parts") and not course.get("part"):
        return None
    return syllabus.load(course["id"], course.get("part"))


@st.dialog("Add Syllabus", width="large")
def _syllabus_add_dialog(course):
    """The syllabus pdf goes to the Library as this course's Syllabus and is read at once; everything read can be changed with Edit Syllabus."""
    from views import library_import
    up = st.file_uploader("Syllabus", type=["pdf"], key=f"syl_up_{course['id']}")
    st.caption("The file is added to the Library as the Syllabus of this course. It is read: what each part of the grade is worth, the letter-grade cutoffs and the instructor are kept here, "
               "and the outline is built from its topic list. Nothing is final: Edit Syllabus changes any of it, and the Outline has its own editor.")
    if st.button("Add and Read", key=f"syl_go_{course['id']}", type="primary", disabled=not up):
        _book, data = library_import.add_syllabus(course["id"], up.name, up.getvalue(), course.get("part"))
        rows = (data or {}).get("rows") or []
        st.session_state["lib_toast"] = (f"Syllabus added. {len(rows)} part{'s' if len(rows) != 1 else ''} of the grade found." if rows else
                                         "Syllabus added. The grading could not be read from it: use Edit Syllabus to type it in.")
        st.rerun()


@st.dialog("Edit Syllabus", width="large")
def _syllabus_edit_dialog(course):
    """What was read from the syllabus, as plain boxes and two small tables. Saving keeps it as the student's own."""
    import pandas as pd
    cid, part = course["id"], course.get("part")
    data = dict(syllabus.load(cid, part) or {})
    k = f"syl_{cid}_{part}_"
    a, b = st.columns(2)
    instructor = a.text_input("Instructor", data.get("instructor", ""), key=k + "ins")
    email = b.text_input("E-mail", data.get("email", ""), key=k + "mail")
    st.markdown("**Parts of the Grade**")
    st.caption("Counts From says where your score so far comes from: homework, midterms, final, exams, or event:Midterm 1 (the title of one exam). Leave it empty for anything else.")
    rows = pd.DataFrame([{"Item": r.get("item", ""), "Percent": r.get("percent"), "Counts From": r.get("kind") or ""} for r in data.get("rows") or []], columns=["Item", "Percent", "Counts From"])
    got = st.data_editor(rows, key=k + "rows", num_rows="dynamic", hide_index=True, width="stretch",
                         column_config={"Item": st.column_config.TextColumn("Item", required=True), "Percent": st.column_config.NumberColumn("Percent", min_value=0, max_value=100, step=1, required=True),
                                        "Counts From": st.column_config.TextColumn("Counts From")})
    total = float(sum(v for v in got["Percent"] if v == v and v is not None))
    st.caption(f"The parts add up to {total:g}%." + ("" if abs(total - 100) < 0.5 else " They usually add up to 100%."))
    st.markdown("**Letter Grades**")
    scale = pd.DataFrame([{"Grade": r.get("grade", ""), "Score Needed": r.get("rule", "")} for r in data.get("scale") or []], columns=["Grade", "Score Needed"])
    got_scale = st.data_editor(scale, key=k + "scale", num_rows="dynamic", hide_index=True, width="stretch",
                               column_config={"Grade": st.column_config.TextColumn("Grade", required=True), "Score Needed": st.column_config.TextColumn("Score Needed", help="for example 90-100 or 80% and above")})
    curve = st.text_area("Curving", data.get("curve", ""), key=k + "curve", height=70)
    note = st.text_area("Note", data.get("note", ""), key=k + "note", height=70)
    s, c = st.columns(2)
    if s.button("Save", key=k + "save", type="primary"):
        data["instructor"], data["email"], data["curve"], data["note"] = instructor.strip(), email.strip(), curve.strip(), note.strip()
        data["rows"] = [{"item": str(r["Item"]).strip(), "percent": int(r["Percent"]) if float(r["Percent"]) == int(float(r["Percent"])) else float(r["Percent"]),
                         "kind": (str(r["Counts From"]).strip() or None)} for r in got.to_dict("records") if str(r.get("Item") or "").strip() and r.get("Percent") == r.get("Percent") and r.get("Percent") is not None]
        data["scale"] = []
        for r in got_scale.to_dict("records"):
            grade, rule = str(r.get("Grade") or "").strip(), str(r.get("Score Needed") or "").strip()
            low = re.search(r"\d+(?:\.\d+)?", rule)
            if grade and low:
                value = float(low.group())
                data["scale"].append({"grade": grade, "rule": rule, "min": int(value) if value == int(value) else value})
        data["scale"].sort(key=lambda r: -r["min"])
        data["manual"] = True
        syllabus.save(cid, data, part)
        st.rerun()
    if c.button("Cancel", key=k + "cancel"):
        st.rerun()


def _syllabus(course):
    """The syllabus file, what each part of the grade is worth, and the letter-grade scale (from the syllabus)."""
    data = _syllabus_data(course)
    if course.get("parts") and not course.get("part"):
        st.caption("This course has more than one syllabus. Choose a part above to see its syllabus and what each part of the grade is worth.")
        return
    add_col, edit_col, _gap = st.columns([1.5, 1.5, 6])
    if add_col.button("Add Syllabus", key=f"syl_add_{course['id']}", icon=":material/upload_file:", help="add the syllabus pdf to the Library and read it: grading, letter grades, instructor and outline"):
        _syllabus_add_dialog(course)
    if edit_col.button("Edit Syllabus", key=f"syl_edit_{course['id']}", icon=":material/edit:", disabled=not data, help="change anything that was read from the syllabus, or type it in"):
        _syllabus_edit_dialog(course)
    if not data:
        st.caption("No syllabus yet. Add the syllabus pdf here and it is read: what each part of the grade is worth, the letter-grade cutoffs, the instructor and the outline.")
        return
    info = ""
    if data.get("instructor"):
        who = html.escape(data["instructor"]) + (f' <span class="syl-mail">{html.escape(data["email"])}</span>' if data.get("email") else "")
        info += f"<tr><td>Instructor</td><td>{who}</td></tr>"
    meetings = crud.list_meetings(course["id"])
    if meetings:
        def clock(t):
            h, m = int(t[:2]), t[3:5]
            return f"{(h - 1) % 12 + 1}:{m} {'AM' if h < 12 else 'PM'}"
        times = "<br>".join(f"{html.escape(crud.meeting_days_label(m))}, {clock(m['start_time'])} to {clock(m['end_time'])}" for m in meetings)
        info += f"<tr><td>Class Time</td><td>{times}</td></tr>"
        places = ", ".join(dict.fromkeys(m["location"] for m in meetings if m["location"]))
        if places:
            info += f"<tr><td>Location</td><td>{html.escape(places)}</td></tr>"
    if info:
        st.markdown(f"<table class='syl-table syl-info'><tbody>{info}</tbody></table>", unsafe_allow_html=True)
    book = crud.get_book(data.get("book") or 0)
    if book:
        page = data.get("page") or 1
        st.markdown(f'<a class="syl-open" href="#" data-ol-book="{book["id"]}" data-ol-page="{page}" data-ol-tab="Overview" '
                    f'title="open the syllabus at its grading policy">{html.escape(book["title"])}</a>', unsafe_allow_html=True)
    rows = data.get("rows") or []
    scale = data.get("scale") or []
    if scale:
        body = "".join(f"<tr><td>{html.escape(r['grade'])}</td><td>{html.escape(r['rule'])}</td></tr>" for r in scale)
        st.markdown(f"<table class='syl-table'><thead><tr><th>Letter Grade</th><th>Score Needed</th></tr></thead>"
                    f"<tbody>{body}</tbody></table>", unsafe_allow_html=True)
    elif rows and not data.get("note"):
        st.caption("The syllabus lists no letter-grade cutoffs.")
    if data.get("note"):
        st.caption(data["note"])
    if data.get("curve"):
        st.caption("Curving: " + data["curve"])


def _goals(data, homework, events, assumed):
    """What the work still to come must average to finish with an A or a B (the cutoffs of the syllabus)."""
    scale = {r["grade"]: r["min"] for r in data.get("scale") or [] if r.get("min") is not None} or dict(syllabus.DEFAULT_SCALE)
    left_hw = sum(1 for h in homework if h.get("score") is None)
    left_ex = sum(1 for e in events if e.get("score") is None)
    rows, hw_avg = "", None
    for grade in ("A", "B"):
        if grade not in scale:
            continue
        got = syllabus.needed(data, homework, events, scale[grade] / 100)
        if not got:
            return
        every, exams_only, hw_avg = got

        def show(x):
            if x is None:
                return "None"
            if x <= 0:
                return "Already secured"
            return f"{x:.0%}" if x <= 1 else f"Not reachable ({x:.0%} needed)"

        rows += (f"<tr><td>{grade} ({scale[grade]:g}% or more)</td><td class='n'>{show(every)}</td>"
                 f"<td class='n'>{show(exams_only)}</td></tr>")
    if not rows:
        return
    st.markdown(f"<div class='syl-scroll'><table class='syl-table syl-goals'><thead><tr><th>To Finish With</th><th class='n'>Least on Every Remaining Item</th>"
                f"<th class='n'>Least on Remaining Exams{f' if Homework Stays at {hw_avg:.0%}' if hw_avg is not None else ''}</th></tr></thead>"
                f"<tbody>{rows}</tbody></table></div>", unsafe_allow_html=True)
    st.caption(f"Still to come: {left_hw} homework, {left_ex} exam{'' if left_ex == 1 else 's'}, and any other part of the grade not yet graded. "
               "Each remaining item counts the same within its part."
               + (" The syllabus lists no cutoffs, so 90 / 80 is assumed." if assumed else ""))


def coming_up(course, today=None, limit=8):
    """What is due next in a course, from all three places it is kept: homework not yet graded, exams still ahead, and the Task List's open tasks.
    [(date text 'YYYY-MM-DD', time or '', title, kind)] in date order; a task that is the same work as a homework or an exam (same title) is listed once."""
    today = (today or date.today()).isoformat()
    rows, seen = [], set()
    norm = lambda s: re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()
    for h in _homework_items(course):
        if h["due_date"] and h["due_date"] >= today and h.get("score") is None and h["status"] != "verified":
            rows.append((h["due_date"], h.get("due_time") or "", h["title"], "Homework"))
            seen.add(norm(h["title"]))
    for e in _exam_items(course):
        if e["date"] >= today and e.get("score") is None:
            rows.append((e["date"], e.get("time") or "", e["title"], "Exam"))
            seen.add(norm(e["title"]))
    try:
        from planner import store as planner_store, task_store, timeutil
        zone = planner_store.get_term().zone
        for k in task_store.list_tasks(course_id=course["id"], include_done=False):
            if k.due is None:
                continue
            local = timeutil.to_local(k.due, zone)
            if local.date().isoformat() >= today and norm(k.title) not in seen:
                rows.append((local.date().isoformat(), local.strftime("%H:%M"), k.title, "Task"))
    except Exception:
        pass
    return sorted(rows, key=lambda r: (r[0], r[1], r[2]))[:limit]


def _coming_up(course, rows):
    """The next homework, exams and tasks."""
    if not rows:
        st.caption("Nothing is due soon.")
        return
    st.markdown('<div class="dl-list">' + "".join(_row_html(title, _when(day, time), kind, "none") for day, time, title, kind in rows) + "</div>", unsafe_allow_html=True)


def _glance(course, rows, homework, exams, data):
    """The row at the top of the Overview: what is next, how much is open, how much is graded, and the grade so far."""
    try:
        from planner import task_store
        open_tasks = len(task_store.list_tasks(course_id=course["id"], include_done=False))
    except Exception:
        open_tasks = 0
    graded = sum(1 for h in homework if h.get("score") is not None) + sum(1 for e in exams if e.get("score") is not None)
    est = syllabus.standing(data, homework, exams) if data else None
    cols = st.columns(4)
    nxt = rows[0] if rows else None
    cols[0].metric("Next Due", (_when(nxt[0], nxt[1]).split(" · ")[0]) if nxt else "Nothing", help=nxt[2] if nxt else "nothing is due soon")
    cols[1].metric("Open Tasks", open_tasks, help="tasks of this course in the Task List that are not done")
    cols[2].metric("Graded", f"{graded} of {len(homework) + len(exams)}", help="homework and exams with a score")
    cols[3].metric("Grade So Far", f"{syllabus.letter(est[0], data)[0]}  ({est[0]:.1f}%)" if est else "None", help="weighted by the syllabus, from what is graded so far")


def _overview(course):
    """The Overview in a fixed order, every section foldable: the row of numbers at the top, Coming Up, Grades (what you have and what is needed, and what each part is worth), the
    Syllabus (the file, its grading and letter grades, with Add and Edit), and how well the materials are understood (quiz scores)."""
    homework, exams = _homework_items(course), _exam_items(course)
    data = _syllabus_data(course)
    finished = crud.course_status(course) == "Completed"
    rows = [] if finished else coming_up(course)
    _glance(course, rows, homework, exams, data)
    if not finished:
        with st.expander(f"Coming Up ({len(rows)})", expanded=True):
            _coming_up(course, rows)
    with st.expander("Grades", expanded=True):
        hw_avg, ex_avg = _percent(homework), _percent(exams)
        left, right = st.columns([3, 2], gap="large")
        with right:
            if data:
                _weights(course, data)
        with left:
            if hw_avg is None and ex_avg is None:
                st.caption("No grades yet. Homework and exam grades appear here.")
            else:
                est = syllabus.standing(data, homework, exams) if data else None
                cols = st.columns(3 if est else 2)
                cols[0].metric("Homework Average", f"{hw_avg:.0%}" if hw_avg is not None else "None",
                               help=f"{sum(1 for h in homework if h.get('score') is not None)} of {len(homework)} graded")
                cols[1].metric("Exam Average", f"{ex_avg:.0%}" if ex_avg is not None else "None",
                               help=f"{sum(1 for e in exams if e.get('score') is not None)} of {len(exams)} graded")
                if est:
                    percent, share = est
                    grade, assumed = syllabus.letter(percent, data)
                    cols[2].metric("Estimated Letter Grade", f"{grade}  ({percent:.1f}%)",
                                   help=f"weighted by the syllabus, from the {share:.0%} of the course graded so far"
                                        + ("; the syllabus lists no cutoffs, so 90 / 80 / 70 / 60 is assumed" if assumed else ""))
                    _goals(data, homework, exams, assumed)
    with st.expander("Syllabus", expanded=True):
        _syllabus(course)
    with st.expander("How Well You Know the Material", expanded=False):
        quiz_view.understanding(course)


def _homework(course):
    """Homework in two lists, upcoming (due today or later, or no date) and past, each in date order: the problem file, its
    solution, my graded submission and the grade with comments."""
    today = date.today().isoformat()
    homework = _homework_items(course)
    if not homework:
        st.subheader("Homework")
        st.caption("No homework yet.")
        return
    finished = crud.course_status(course) == "Completed"               # a completed course has nothing upcoming, dated or not
    upcoming = [] if finished else [h for h in homework if not h["due_date"] or h["due_date"] >= today]
    past = list(homework) if finished else [h for h in homework if h["due_date"] and h["due_date"] < today]

    def rows(items):
        out = ""
        for h in items:
            status, css = _homework_status(h, today)
            out += _row_html(h["title"], _when(h["due_date"], h.get("due_time")), status, css,
                             detail=(h.get("problem_md") or "").strip() or None,                 # the instructor's notes on this homework
                             book=_homework_book(course["id"], h["title"]),
                             solution=_homework_book(course["id"], h["title"], "Homework Solution"),
                             graded=_homework_book(course["id"], h["title"], "Graded Homework"),
                             extra=_grade_html(h), tab="Homework")
        return out

    if not finished:
        st.subheader(f"Upcoming Homework ({len(upcoming)})")
        if upcoming:
            st.markdown(f'<div class="dl-list">{rows(upcoming)}</div>', unsafe_allow_html=True)
        else:
            st.caption("Nothing due.")
    st.subheader(f"Past Homework ({len(past)})")
    if past:
        st.markdown(f'<div class="dl-list">{rows(list(reversed(past)))}</div>', unsafe_allow_html=True)      # the most recent first
    else:
        st.caption("None yet.")


def _practice_exams(course):
    """Practice exams of the course in the Library, each with its solution next to it (the file opens, and Back returns to this tab)."""
    books = crud.list_books()
    files = [b for b in books if b["kind"] == "Practice Exam" and course["id"] in b["course_ids"] and crud.in_part(b["title"], course.get("part"))]
    if not files:
        return
    solutions = [b for b in books if b["kind"] == "Exam Solution" and course["id"] in b["course_ids"] and "practice" in b["title"].lower()]

    def solution_of(b):
        n = re.search(r"\d+", b["title"])
        return next((x for x in solutions if n and re.search(r"\d+", x["title"]) and re.search(r"\d+", x["title"]).group() == n.group()), None)

    st.subheader(f"Practice Exams ({len(files)})")
    rows = ""
    for b in sorted(files, key=lambda b: crud._natural_key(b["title"])):
        rows += _row_html(b["title"], "", "", "none", book=b, solution=solution_of(b), tab="Exams").replace('<span class="dl-pill none"></span>', "")
    st.markdown(f'<div class="dl-list">{rows}</div>', unsafe_allow_html=True)


def _build_sheet(course, event, key):
    st.session_state[f"eqs_done_{event['id']}"] = eqsheet.make(course, event, st.session_state.get(key) or [])


def _equation_sheets(course, exams):
    """One equation sheet per exam (midterms and the final, upcoming or past): pick the notes the exam covers; their formula sheets are put
    together on one printable page."""
    if not exams:
        return
    st.subheader("Equation Sheets")
    cands = eqsheet.candidates(course["id"], course.get("part"))
    if not cands:
        st.caption("No notes with a formula sheet yet. A sheet is built from the Formula Sheet section of the course notes.")
        return
    labels = {b["id"]: (f"Lec {b['lecture']} · " if b.get("lecture") else "") + b["title"] for b, _ in cands}
    st.caption("Choose the notes each exam covers, then build the sheet. It uses the formula sheet of each chosen note.")
    for e in exams:
        state = eqsheet.load(e["id"])
        chosen = [i for i in (state.get("notes") or list(labels)) if i in labels]
        with st.container(border=True, key=f"eqs_{e['id']}"):
            head, pick, go = st.columns([2, 6, 2], vertical_alignment="center")
            head.markdown(f"**{e['title']}**")
            key = f"eqs_sel_{e['id']}"
            pick.multiselect("Notes this exam covers", list(labels), default=chosen, format_func=labels.get, key=key, label_visibility="collapsed")
            built = crud.get_book(state.get("book") or 0)
            go.button("Update Sheet" if built else "Build Sheet", key=f"eqs_go_{e['id']}", icon=":material/functions:",
                      on_click=_build_sheet, args=(course, e, key), width="stretch")
            if built:
                st.markdown(f'<a class="dl-solution" href="#" data-ol-book="{built["id"]}" data-ol-page="1" data-ol-tab="Exams" '
                            f'title="open the equation sheet">Open {html.escape(built["title"])}</a>', unsafe_allow_html=True)


def _exams(course):
    """Midterms and finals in two lists. Upcoming: date, what it covers, the exam file and the preparation document. Past: the exam,
    its solution, my graded paper, the score and the reflection document."""
    today = date.today().isoformat()
    exams = _exam_items(course)
    finished = crud.course_status(course) == "Completed"
    upcoming = [] if finished else [e for e in exams if e["date"] >= today and not e.get("done")]
    past = list(exams) if finished else [e for e in exams if e["date"] < today or e.get("done")]          # an exam marked complete on the Home page counts as past

    def row(e, done):
        return _row_html(e["title"], _when(e["date"], e.get("time")), "Done" if done else "Upcoming", "done" if done else "open",
                         f"Covers {e['covers']}" if e.get("covers") else None,
                         book=_exam_book(course["id"], e["title"]), solution=_exam_book(course["id"], e["title"], "Exam Solution"),
                         graded=_exam_book(course["id"], e["title"], "Graded Exam"), extra=_grade_html(e), tab="Exams",
                         guide=_exam_book(course["id"], e["title"], "Exam Preparation"),           # for a past exam too: what the preparation said
                         reflection=_exam_book(course["id"], e["title"], "Exam Reflection", "Reflection") if done else None,
                         stats=_exam_book(course["id"], e["title"], "Exam Reflection", "Statistics") if done else None)

    if not exams:
        st.subheader("Exams")
        st.caption("No midterms or finals yet.")
    else:
        if not finished:
            st.subheader(f"Upcoming Exams ({len(upcoming)})")
            if upcoming:
                st.markdown(f'<div class="dl-list">{"".join(row(e, False) for e in upcoming)}</div>', unsafe_allow_html=True)
            else:
                st.caption("No exams left this term.")
        st.subheader(f"Past Exams ({len(past)})")
        if past:
            st.markdown(f'<div class="dl-list">{"".join(row(e, True) for e in reversed(past))}</div>', unsafe_allow_html=True)
        else:
            st.caption("None yet.")
    _practice_exams(course)
    _equation_sheets(course, exams)                    # every exam, past ones too (a sheet can be built or rebuilt for a midterm that is over)


def _open_pdf_from_outline():
    """A clicked outline point with a page writes 'book,page|stamp' into a hidden box; open that file at that page."""
    sink = st.text_input("Outline Navigation", key="outline_sink", label_visibility="collapsed")
    if sink and sink != st.session_state.get("_outline_sink_done"):
        st.session_state["_outline_sink_done"] = sink
        fields = sink.split("|")[0].split(",")
        try:
            book_id, page = int(fields[0]), int(fields[1])
        except (ValueError, IndexError):
            return
        if crud.get_book(book_id):
            tab = fields[2] if len(fields) > 2 and fields[2] in ("Overview", "Homework", "Exams", "Outline", "Resources", "Quiz") else "Outline"
            st.session_state["course_tab"] = (st.session_state.get("open_course"), tab)   # reopen here on Back
            st.session_state["page"] = "Library"
            st.session_state["open_book"] = book_id
            st.session_state[f"view_page_{book_id}"] = page
            st.session_state[f"view_{book_id}_page"] = page
            st.rerun()


def _auto_build(course_id, part=None):
    """Build the outline from the syllabus topics, else the lecture titles; it then follows the Library again until it is edited."""
    import courseoutline
    items, source = courseoutline.auto_items(course_id, part)
    if not items:
        st.toast("There is nothing to build from yet: add the lectures, or a syllabus with a topic list, to the Library.", icon=":material/info:")
        return
    courseoutline.save_previous(course_id, part)
    crud.replace_outline(course_id, items, part)
    settings.set_outline_state(course_id, source, courseoutline.signature(items), part)


def _fill_outline(key, items):
    import courseoutline
    st.session_state[key] = courseoutline.to_text(items)


def _read_pasted(key, paste_key):
    import courseoutline
    text = courseoutline.normalize_text(st.session_state.get(paste_key, ""))
    if text:
        st.session_state[key] = text


def _outline_rows_to_table(key_rows, key_ver, items):
    import courseoutline
    st.session_state[key_rows] = courseoutline.rows_from_items(items)
    st.session_state[key_ver] = st.session_state.get(key_ver, 0) + 1


@st.dialog("Edit Outline", width="large")
def _outline_dialog(course):
    """The outline written the way the course is organized: lecture by lecture, chapter by chapter (a table: the number and the title), or free text with levels. Save keeps it as the student's own
    (it is no longer rebuilt); the one it replaces is copied to the outlines folder."""
    import courseoutline
    import pandas as pd
    import settings
    cid, part = course["id"], course.get("part")
    key = f"outline_text_{cid}_{part}"
    rows_key, ver_key, mode_key = f"outline_rows_{cid}_{part}", f"outline_ver_{cid}_{part}", f"outline_mode_{cid}_{part}"
    current = crud.list_outline(cid, part)
    if mode_key not in st.session_state:
        st.session_state[mode_key] = courseoutline.flat_kind(current) or ("Lectures" if not current else "Free Text")
    mode = st.segmented_control("How is this course organized?", ["Lectures", "Chapters", "Free Text"], key=mode_key) or "Free Text"
    syllabus, titles = courseoutline.from_syllabus(cid, part), courseoutline.from_titles(cid, part)
    prefix = "Ch" if mode == "Chapters" else "Lec"
    if mode == "Free Text":
        st.caption("One point per line, indented two spaces for each level (topic, sub topic, point, detail). A line may start with its marker (I. A. 1. a. or Lec 3); "
                   "markers left out are numbered for you. Put [9 Hours] or a web address at the end of a line. Points keep the file they open.")
        st.text_area("Outline", key=key, height=330, label_visibility="collapsed")
        with st.expander("Paste an Outline From Somewhere Else"):
            st.text_area("Pasted Outline", key=f"outline_paste_{cid}_{part}", height=140, label_visibility="collapsed",
                         placeholder="Paste a topic list: bullets, 1.1 numbering, I. A. 1. a. markers or Part 2 lines are all understood")
            st.button("Read the Pasted Outline", key=f"outline_read_{cid}", icon=":material/auto_fix_high:", on_click=_read_pasted, args=(key, f"outline_paste_{cid}_{part}"),
                      help="puts it in the box above in the form the editor uses; nothing is saved until you press Save")
    else:
        word = "Lecture" if mode == "Lectures" else "Chapter"
        st.caption(f"One row for each {word.lower()}: type its number ({word.lower()} 3, or 4-5 when one covers two) and its title. Leave the number empty to number the rows in order. "
                   f"Hours are optional. A {word.lower()} that has notes in the Library opens them from the outline.")
        if rows_key not in st.session_state:
            st.session_state[rows_key] = courseoutline.rows_from_items(current)
            if current and not courseoutline.flat_kind(current):
                st.session_state["_outline_flat_warning"] = True
        if st.session_state.pop("_outline_flat_warning", False):
            st.warning("This outline has sub topics. A table keeps only the top level; use Free Text to keep all of it.", icon=":material/warning:")
        table = pd.DataFrame(st.session_state[rows_key], columns=["number", "title", "hours"])
        edited = st.data_editor(table, key=f"outline_table_{cid}_{part}_{st.session_state.get(ver_key, 0)}_{mode}", num_rows="dynamic", hide_index=True, width="stretch", height=330,
                                column_config={"number": st.column_config.TextColumn(f"{word} Number", help="for example 3, or 4-5", width="small"),
                                               "title": st.column_config.TextColumn("Title", required=True, width="large"),
                                               "hours": st.column_config.TextColumn("Hours (Optional)", width="small")})
        st.session_state["_outline_table_now"] = edited.fillna("").to_dict("records")
    a, b, c, d = st.columns(4)
    if mode == "Free Text":
        a.button("Use Syllabus Topics", key=f"outline_use_syl_{cid}", disabled=not syllabus, width="stretch", on_click=_fill_outline, args=(key, syllabus),
                 help="fills the box with the topics listed in the syllabus or the lec 0 slides; nothing is saved until you press save")
        b.button("Use Lecture Titles", key=f"outline_use_titles_{cid}", disabled=not titles, width="stretch", on_click=_fill_outline, args=(key, titles),
                 help="fills the box with the lecture or chapter titles in the library; nothing is saved until you press save")
    else:
        a.button("Use Syllabus Topics", key=f"outline_use_syl_{cid}", disabled=not syllabus, width="stretch", on_click=_outline_rows_to_table, args=(rows_key, ver_key, syllabus),
                 help="fills the table with the topics listed in the syllabus or the lec 0 slides; nothing is saved until you press save")
        b.button("Use Lecture Titles", key=f"outline_use_titles_{cid}", disabled=not titles, width="stretch", on_click=_outline_rows_to_table, args=(rows_key, ver_key, titles),
                 help="fills the table with the lecture or chapter titles in the library; nothing is saved until you press save")
    if c.button("Save", key=f"outline_save_{cid}", type="primary", width="stretch", help="keeps this outline; the one it replaces is copied to the outlines folder"):
        text = st.session_state[key] if mode == "Free Text" else courseoutline.rows_to_text(st.session_state.get("_outline_table_now", []), prefix)
        items = courseoutline.from_text(text, current, cid, part)
        courseoutline.save_previous(cid, part)
        crud.replace_outline(cid, items, part)
        settings.set_outline_state(cid, "manual", "", part)
        for k in (rows_key, ver_key, mode_key):
            st.session_state.pop(k, None)
        st.rerun()
    if d.button("Cancel", key=f"outline_cancel_{cid}", width="stretch"):
        for k in (rows_key, ver_key, mode_key):
            st.session_state.pop(k, None)
        st.rerun()


def _outline(course):
    """The course outline: main topics (I., II., ...), their sub topics (A., B., ...), and under each sub topic a
    folded list of its numbered points (1., 2., ...)."""
    import courseoutline
    part = course.get("part")
    state = courseoutline.ensure(course["id"], part)         # builds it when there is none (syllabus topics, else lecture titles) and keeps an automatic one current
    items = crud.list_outline(course["id"], part)
    made = {"syllabus": "Built from the syllabus", "titles": "Built from the lecture and chapter titles"}.get(state.get("source"))
    note = (f"{made}. It follows your Library until you edit it." if made else "Edited by you." if items else
            "No outline yet: add lectures or a syllabus with a topic list to the Library, or build one with Edit Outline.")
    cap, auto, edit = st.columns([5, 1.7, 1.4], vertical_alignment="center")
    cap.caption(note)
    built, source = courseoutline.auto_items(course["id"], part)
    mine = bool(items) and state.get("source") in ("manual", None)
    if mine:                                                  # an outline of the user's own is only replaced after they confirm
        with auto.popover("Auto Build", icon=":material/auto_fix_high:", width="stretch", disabled=not built,
                          help="builds the outline again from the syllabus topics or the lecture titles"):
            st.caption("Replace your outline with one built from the " + ("syllabus topics" if source == "syllabus" else "lecture titles")
                       + "? Your current outline is copied to the outlines folder first.")
            st.button("Replace and Build", key=f"outline_auto_yes_{course['id']}", type="primary", on_click=_auto_build, args=(course["id"], part))
    else:
        auto.button("Auto Build", icon=":material/auto_fix_high:", key=f"outline_auto_{course['id']}", width="stretch", disabled=not built,
                    on_click=_auto_build, args=(course["id"], part), help="builds the outline from the syllabus topics or, if it lists none, the lecture titles")
    if edit.button("Edit Outline", icon=":material/edit:", key=f"outline_edit_{course['id']}", width="stretch",
                   help="write your own outline, or start from the syllabus topics or the lecture titles"):
        st.session_state[f"outline_text_{course['id']}_{part}"] = courseoutline.to_text(items)
        _outline_dialog(course)
    if not items:
        return

    def label(it):
        text = html.escape(it["title"])
        if it.get("book_id") and it.get("page"):     # opens the Library preview of the notes at that page
            text = (f'<a href="#" data-ol-book="{it["book_id"]}" data-ol-page="{it["page"]}">{text}</a>')
        elif it["url"]:
            text = f'<a href="{html.escape(it["url"], quote=True)}" target="_blank" rel="noopener noreferrer">{text}</a>'
        marker = it["marker"] + ("." if re.fullmatch(r"[IVXLCDM]+|[A-Z]|\d+|[a-z]", it["marker"]) else "")   # I. A. 1. a. / Part 1 / Lec 2
        return f'<span class="ol-marker">{html.escape(marker)}</span><span>{text}</span>'

    # One button opens or closes every folded list at once (they start folded).
    key = f"outline_open_{course['id']}"
    opened = st.session_state.get(key, False)
    if any(it["level"] == "1" for it in items):
        _, btn = st.columns([6, 1.4], vertical_alignment="center")
        if btn.button("Collapse All" if opened else "Expand All", key=f"outline_toggle_{course['id']}", width="stretch"):
            st.session_state[key] = not opened
            st.rerun()
    open_attr = " open" if opened else ""

    rows, i = "", 0
    while i < len(items):
        it = items[i]
        i += 1
        if it["level"] == "I":
            rows += f'<div class="ol-main">{label(it)}</div>'
            continue
        if it["level"] == "L":                 # a plain list of lectures (no parts)
            rows += f'<div class="ol-flat">{label(it)}</div>'
            continue
        kids = []
        if it["level"] == "A":
            while i < len(items) and items[i]["level"] in ("1", "a"):     # points, and the a. b. c. details under them
                kids.append(items[i])
                i += 1
        if kids:
            leaves = "".join(f'<div class="ol-leaf{" ol-l3" if k["level"] == "a" else ""}">{label(k)}</div>' for k in kids)
            count = sum(k["level"] == "1" for k in kids)
            rows += (f'<details class="ol-sub ol-fold"{open_attr}><summary>{label(it)}'
                     f'<span class="ol-count">{count}</span></summary><div class="ol-kids">{leaves}</div></details>')
        else:
            rows += f'<div class="ol-sub">{label(it)}</div>'
    wide = any(not re.fullmatch(r"[IVXLCDM]+|[A-Z]|\d+|[\d.\u2013]+", it["marker"]) for it in items)   # Part / Lec markers
    st.markdown(f'<div class="ol{" ol-wide" if wide else ""}">{rows}</div>', unsafe_allow_html=True)


def _part_name(course, tag):
    """"MA266" -> "MA 266" (the code as the titles of that part wrote it)."""
    for b in crud.list_books():
        if course["id"] in b["course_ids"]:
            m = crud._PART.search(b["title"])
            if m and crud.part_tag(b["title"]) == tag:
                return m.group(1).upper()
    return tag


def _manage(course):
    """The course page below the banner: Overview (deadlines), Outline (blank for now) and Resources."""
    _open_pdf_from_outline()                     # the hidden box every file link of the course page (homework, exams, outline ...) writes into
    parts = crud.course_parts(course["id"])
    if parts:                                    # a merged course (MA 266 / 303, Calculus): one part at a time on every tab
        names = {t: _part_name(course, t) for t in parts}
        choice = st.segmented_control("Part of This Course", parts + ["ALL"], default=parts[0], key=f"course_part_{course['id']}",
                                      format_func=lambda t: "All Parts" if t == "ALL" else names[t], selection_mode="single",
                                      help="the course is made of several courses: choose which one the tabs below show")
        course = {**course, "parts": parts, "part": choice if choice in parts else None}
    remembered = st.session_state.get("course_tab")          # (course id, tab) set when a PDF was opened from here
    start = remembered[1] if remembered and remembered[0] == course["id"] else None
    overview, homework, exams, outline, resources, quiz = st.tabs(
        ["Overview", "Homework", "Exams", "Outline", "Resources", "Quiz"], default=start)
    with overview:
        _overview(course)
    with homework:
        _homework(course)
    with exams:
        _exams(course)
    with outline:
        _outline(course)
    with resources:
        _resources(course)
    with quiz:
        quiz_view.render(course)
