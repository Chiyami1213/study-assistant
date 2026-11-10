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
from views import library_view, quiz_view

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
        if st.session_state.get("_recent_touched") != course["id"]:          # opened now: remember it for the Recent list
            st.session_state["_recent_touched"] = course["id"]
            settings.touch_course(course["id"])
        if st.button("← All Courses", key="course_back"):
            st.session_state["open_course"] = None
            st.session_state.pop("course_tab", None)
            st.rerun()
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
    if choice == "Recent":                                       # one list, the course opened most lately first
        _tile_grid(courses)
        return
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
    """Library files linked to this course (Course Notes, Notes, Textbooks), then its web links."""
    files = [b for b in crud.list_books() if course["id"] in b["course_ids"]]
    # Notes with a lecture number come first, in lecture order; then the rest by title.
    order = lambda b: ((0, crud._natural_key(b["lecture"])) if b.get("lecture") else (1, []),
                       crud._natural_key(b["title"]))
    sections = [
        ("Course Notes", "Lecture Notes", "No course notes yet."),
        ("Notes", "Notes", "No notes yet."),
        ("Textbooks", "Textbook", "No textbooks yet."),
    ]
    for heading, kind, empty in sections:
        st.subheader(heading)
        items = sorted((b for b in files if b["kind"] == kind), key=order)
        if items:
            _resource_grid(items)
        else:
            st.caption(f"{empty} Add a file in the Library and choose this course.")

    _links(course)


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
    head, btn = st.columns([6, 1.2], vertical_alignment="center")
    head.subheader("Links")
    if btn.button("Add Link", key=f"link_open_{course['id']}"):
        _add_link_dialog(course)
    links = crud.list_links(course["id"])
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
    num = re.search(r"\d+", hw_title or "")
    if not num:
        return None
    for b in crud.list_books():
        if b["kind"] == kind and course_id in b["course_ids"]:
            n = re.search(r"\d+", b.get("lecture") or b["title"])
            if n and int(n.group()) == int(num.group()):
                return b
    return None


def _exam_book(course_id, event_title, kind="Exam", word=None):
    """The Library exam file of this course for an event like "Midterm 2" or "Final Exam" (same kind of exam, same number);
    with `word`, only a file whose title contains it ("Reflection", "Statistics")."""
    def key(text):
        t = (text or "").lower()
        kind = "midterm" if re.search(r"mid[\s_\-]*term", t) else "final" if "final" in t else "exam"
        n = re.search(r"\d+", t)
        return kind, (n.group() if n else None)

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
    return sorted(crud.list_homework(course["id"]),
                  key=lambda h: (h["due_date"] or "9999-12-31", crud._natural_key(h["title"])))


def _exam_items(course):
    return sorted((e for e in crud.list_events("2000-01-01", "2100-12-31")
                   if e["course_id"] == course["id"] and re.search(r"midterm|final|exam", e["title"], re.I)),
                  key=lambda e: (e["date"], e.get("time") or ""))


def _pie(rows, center_top, center_bottom):
    """A donut of what each part of the grade is worth (the syllabus weights), in the chart colours of the theme.
    Hovering a slice names it; the table beside it carries the numbers."""
    import math
    total = sum(r["percent"] for r in rows) or 1
    cx = cy = 90
    outer, inner = 84, 54
    angle = -math.pi / 2
    paths = ""
    for i, r in enumerate(rows):                       # every part of the grade gets its own slice and colour (eight colours, then they repeat)
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


def _syllabus(course):
    """The syllabus file, what each part of the grade is worth, and the letter-grade scale (from the syllabus)."""
    data = syllabus.load(course["id"])
    st.subheader("Syllabus")
    if not data:
        st.caption("No syllabus yet. Add the syllabus file to the Library as a Syllabus.")
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


def _overview(course):
    """The grades so far (metrics and what is needed for an A or a B on the left, what each part is worth at the right),
    then the syllabus, then how well the materials are understood (quiz scores)."""
    st.subheader("Grades")
    homework, exams = _homework_items(course), _exam_items(course)
    hw_avg, ex_avg = _percent(homework), _percent(exams)
    data = syllabus.load(course["id"])
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
    _syllabus(course)
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
    files = [b for b in books if b["kind"] == "Practice Exam" and course["id"] in b["course_ids"]]
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
    """One equation sheet per exam: pick the notes the exam covers; their formula sheets are put together on one printable page."""
    if not exams:
        return
    st.subheader("Equation Sheets")
    cands = eqsheet.candidates(course["id"])
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
    _equation_sheets(course, upcoming or exams)


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


def _auto_build(course_id):
    """Build the outline from the syllabus topics, else the lecture titles; it then follows the Library again until it is edited."""
    import courseoutline
    items, source = courseoutline.auto_items(course_id)
    if not items:
        st.toast("There is nothing to build from yet: add the lectures, or a syllabus with a topic list, to the Library.", icon=":material/info:")
        return
    courseoutline.save_previous(course_id)
    crud.replace_outline(course_id, items)
    settings.set_outline_state(course_id, source, courseoutline.signature(items))


def _fill_outline(key, items):
    import courseoutline
    st.session_state[key] = courseoutline.to_text(items)


@st.dialog("Edit Outline", width="large")
def _outline_dialog(course):
    """The outline as text: one point per line, two spaces of indent per level. Save keeps it as the user's own (it is no longer rebuilt)."""
    import courseoutline
    import settings
    cid = course["id"]
    key = f"outline_text_{cid}"
    st.caption("One point per line, indented two spaces for each level (topic, sub topic, point, detail). A line may start with its marker (I. A. 1. a. or Lec 3); "
               "markers left out are numbered for you. Put [9 Hours] or a web address at the end of a line. Points keep the file they open.")
    st.text_area("Outline", key=key, height=430, label_visibility="collapsed")
    syllabus, titles = courseoutline.from_syllabus(cid), courseoutline.from_titles(cid)
    a, b, c, d = st.columns(4)
    a.button("Use Syllabus Topics", key=f"outline_use_syl_{cid}", disabled=not syllabus, width="stretch", on_click=_fill_outline, args=(key, syllabus),
             help="fills the box with the topics listed in the syllabus or the lec 0 slides; nothing is saved until you press save")
    b.button("Use Lecture Titles", key=f"outline_use_titles_{cid}", disabled=not titles, width="stretch", on_click=_fill_outline, args=(key, titles),
             help="fills the box with the lecture or chapter titles in the library; nothing is saved until you press save")
    if c.button("Save", key=f"outline_save_{cid}", type="primary", width="stretch", help="keeps this outline; the one it replaces is copied to the outlines folder"):
        rows = crud.list_outline(cid)
        items = courseoutline.from_text(st.session_state[key], rows, cid)
        courseoutline.save_previous(cid)
        crud.replace_outline(cid, items)
        settings.set_outline_state(cid, "manual")
        st.rerun()
    if d.button("Cancel", key=f"outline_cancel_{cid}", width="stretch"):
        st.rerun()


def _outline(course):
    """The course outline: main topics (I., II., ...), their sub topics (A., B., ...), and under each sub topic a
    folded list of its numbered points (1., 2., ...)."""
    import courseoutline
    state = courseoutline.ensure(course["id"])               # builds it when there is none (syllabus topics, else lecture titles) and keeps an automatic one current
    items = crud.list_outline(course["id"])
    made = {"syllabus": "Built from the syllabus", "titles": "Built from the lecture and chapter titles"}.get(state.get("source"))
    note = (f"{made}. It follows your Library until you edit it." if made else "Edited by you." if items else
            "No outline yet: add lectures or a syllabus with a topic list to the Library, or build one with Edit Outline.")
    cap, auto, edit = st.columns([5, 1.7, 1.4], vertical_alignment="center")
    cap.caption(note)
    built, source = courseoutline.auto_items(course["id"])
    mine = bool(items) and state.get("source") in ("manual", None)
    if mine:                                                  # an outline of the user's own is only replaced after they confirm
        with auto.popover("Auto Build", icon=":material/auto_fix_high:", width="stretch", disabled=not built,
                          help="builds the outline again from the syllabus topics or the lecture titles"):
            st.caption("Replace your outline with one built from the " + ("syllabus topics" if source == "syllabus" else "lecture titles")
                       + "? Your current outline is copied to the outlines folder first.")
            st.button("Replace and Build", key=f"outline_auto_yes_{course['id']}", type="primary", on_click=_auto_build, args=(course["id"],))
    else:
        auto.button("Auto Build", icon=":material/auto_fix_high:", key=f"outline_auto_{course['id']}", width="stretch", disabled=not built,
                    on_click=_auto_build, args=(course["id"],), help="builds the outline from the syllabus topics or, if it lists none, the lecture titles")
    if edit.button("Edit Outline", icon=":material/edit:", key=f"outline_edit_{course['id']}", width="stretch",
                   help="write your own outline, or start from the syllabus topics or the lecture titles"):
        st.session_state[f"outline_text_{course['id']}"] = courseoutline.to_text(items)
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


def _manage(course):
    """The course page below the banner: Overview (deadlines), Outline (blank for now) and Resources."""
    _open_pdf_from_outline()                     # the hidden box every file link of the course page (homework, exams, outline ...) writes into
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
