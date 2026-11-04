"""Study Assistant - Streamlit entry point."""
import streamlit as st
import streamlit.components.v1 as components

import crud
import importlib
import sys

import icons

# The dev server caches imported modules between reruns; reload ours so edits apply without a restart.
for _m in ("database", "crud", "settings", "icons", "pdfmeta", "covers", "views.notes_view", "views.courses_view", "views.home_view",
           "views.homework_view", "views.exam_mode_view", "views.recall_view", "views.library_view",
           "views.settings_view"):
    if _m in sys.modules:
        importlib.reload(sys.modules[_m])
import settings
from database import init_db
from views import courses_view, home_view, library_view, settings_view

st.set_page_config(page_title="Study Assistant", page_icon=":material/book:", layout="wide",
                   initial_sidebar_state="expanded")
init_db()

# (label, material icon, renderer)
NAV_TOP = {
    "Home": (":material/home:", home_view.render),
    "Library": (":material/library_books:", library_view.render),
    "Courses": (":material/folder:", courses_view.render),
}
NAV_BOTTOM = {"Settings": (":material/settings:", settings_view.render)}
PAGES = {**NAV_TOP, **NAV_BOTTOM}

COLLAPSED_W, EXPANDED_W = 76, 270
CSS = f"""
<style>
{settings.css_vars(settings.get_appearance())}
.block-container {{padding-top: 1.5rem; max-width: 100%; padding-left: 2.5rem;}}
h1, h2, h3 {{letter-spacing: -0.01em;}}
div[data-testid="stExpander"] {{border: 1px solid var(--border); border-radius: 8px;}}
.card {{background:var(--card); border:1px solid var(--border); border-radius:10px; padding:14px 16px; margin-bottom:10px;}}

/* ---- Sidebar: icon rail that expands on hover ---- */
[data-testid="stSidebarHeader"], [data-testid="stSidebarCollapseButton"],
[data-testid="stSidebarCollapsedControl"] {{display: none !important;}}
section[data-testid="stSidebar"] {{
    width: {COLLAPSED_W}px !important; min-width: {COLLAPSED_W}px !important;
    max-width: {COLLAPSED_W}px !important; transform: none !important;
    overflow: visible !important; border: none; z-index: 1000; background: #1b1c20 !important;}}
section[data-testid="stSidebar"] > div:first-child {{
    position: absolute; top: 0; left: 0; height: 100vh; width: {COLLAPSED_W}px !important;
    overflow-x: hidden; overflow-y: auto; scrollbar-width: none; background: #1b1c20; border-right: 1px solid #2a2c33;
    transition: width .2s ease, box-shadow .2s ease;}}
section[data-testid="stSidebar"] > div:first-child:hover {{
    width: {EXPANDED_W}px !important; box-shadow: 8px 0 24px #00000066;}}
section[data-testid="stSidebar"].nav-collapsed > div:first-child {{
    width: {COLLAPSED_W}px !important; box-shadow: none;}}
[data-testid="stSidebarContent"] {{padding: 0 !important;}}
[data-testid="stSidebarUserContent"] {{padding: 1rem 0 !important; width: {EXPANDED_W}px;}}
header[data-testid="stHeader"] {{z-index: 1; background: transparent;}}

/* Nav buttons (no radio dots) */
[data-testid="stSidebar"] button {{
    width: calc(100% - 20px) !important; margin: 0 10px; justify-content: flex-start; gap: 19px; padding: 0.8rem 16px;
    border-radius: 12px; border: none; border-left: 3px solid transparent;
    background: transparent; box-shadow: none; white-space: nowrap;}}
[data-testid="stSidebar"] button p {{font-size: 1.05rem; color: #d5d7dd; white-space: nowrap; opacity: 0; transition: opacity .15s;}}
section[data-testid="stSidebar"] > div:first-child:hover button p {{opacity: 1;}}
section[data-testid="stSidebar"].nav-collapsed > div:first-child button p {{opacity: 0 !important;}}
[data-testid="stSidebar"] button span[data-testid="stIconMaterial"] {{font-size: 1.5rem; color: #d5d7dd;}}
[data-testid="stSidebar"] button:hover {{background: #23252c; border-left-color: transparent;}}
[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] {{
    background: #252d42; border-left-color: #4c8dff;}}
[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] p,
[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] span[data-testid="stIconMaterial"] {{color: #fff;}}
[data-testid="stSidebarResizeHandle"] {{display: none !important;}}
[data-testid="stSidebar"] [data-testid="stElementContainer"], [data-testid="stSidebar"] .stButton {{width: 100% !important;}}
/* Keep Settings pinned to the bottom of the rail */
[data-testid="stSidebarUserContent"] > div {{min-height: calc(100vh - 2rem); display: flex; flex-direction: column;}}
[data-testid="stLayoutWrapper"]:has(> .st-key-nav_spacer) {{flex: 1 1 auto;}}
.st-key-nav_spacer {{flex: 1 1 auto;}}
[data-testid="stSidebar"] button > div {{justify-content: flex-start; width: 100%;}}
[data-testid="stSidebar"] button > div > span {{justify-content: flex-start; gap: 19px;}}
.st-key-nav_head button > div {{justify-content: center;}}
[class*="st-key-nav_group_"] {{gap: 0;}}
[class*="st-key-nav_sub"] {{gap: 0; margin-top: 0;}}

/* Rail toggle icons: » when collapsed, « (top right) when expanded */
.st-key-nav_head {{margin-bottom: 0.4rem;}}
.st-key-nav_head button {{width: 44px !important; padding: 0.5rem 0 !important; justify-content: center; margin: 0 10px 0 auto !important;}}
.st-key-nav_head button p {{display: none;}}
.st-key-nav_expand {{display: block;}} .st-key-nav_collapse {{display: none;}}
section[data-testid="stSidebar"] > div:first-child:hover .st-key-nav_expand {{display: none;}}
section[data-testid="stSidebar"] > div:first-child:hover .st-key-nav_collapse {{display: block;}}
section[data-testid="stSidebar"].nav-collapsed .st-key-nav_expand {{display: block !important;}}
section[data-testid="stSidebar"].nav-collapsed .st-key-nav_collapse {{display: none !important;}}
.st-key-nav_head [data-testid="stButton"] {{display: flex; justify-content: flex-end;}}
.st-key-nav_expand [data-testid="stButton"] {{justify-content: flex-start;}}
.st-key-nav_head button {{margin: 0 7px 0 0 !important;}}
.st-key-nav_expand button {{margin: 0 0 0 10px !important;}}

/* Courses: sub-items revealed while hovering the Courses group */
[class*="st-key-nav_sub"] {{max-height: 0; overflow: hidden; transition: max-height .25s ease;}}
[class*="st-key-nav_group_"]:hover [class*="st-key-nav_sub"] {{max-height: 2400px;}}
[class*="st-key-nav_sub"] button {{padding: 0.5rem 16px 0.5rem 34px !important;}}

/* Folded rail: compact centered icon blocks with even edge spacing */
section[data-testid="stSidebar"] > div:first-child:not(:hover) button,
section[data-testid="stSidebar"].nav-collapsed > div:first-child button {{
    width: {COLLAPSED_W - 20}px !important; margin: 0 10px !important; padding-left: 0 !important; padding-right: 0 !important;}}
section[data-testid="stSidebar"] > div:first-child:not(:hover) button > div,
section[data-testid="stSidebar"].nav-collapsed > div:first-child button > div {{justify-content: center;}}
section[data-testid="stSidebar"] > div:first-child:not(:hover) button > div > span,
section[data-testid="stSidebar"].nav-collapsed > div:first-child button > div > span {{gap: 0;}}
section[data-testid="stSidebar"] > div:first-child:not(:hover) button [data-testid="stMarkdownContainer"],
section[data-testid="stSidebar"].nav-collapsed > div:first-child button [data-testid="stMarkdownContainer"] {{display: none;}}
section[data-testid="stSidebar"].nav-collapsed [class*="st-key-nav_sub"] {{max-height: 0 !important;}}

.nav-label {{font-size: 1.05rem; color: #7d8190; padding: 0.9rem 0 0.4rem 44px; margin-bottom: 1rem; line-height: 1.2;
    white-space: nowrap;}}

.st-key-nav_order_sink {{position: absolute !important; width: 1px; height: 1px; overflow: hidden; opacity: 0; pointer-events: none;}}
.nav-dragging {{opacity: 0.4;}}
.nav-drop-above button {{box-shadow: 0 -2px 0 0 #4c8dff !important;}}
.nav-drop-below button {{box-shadow: 0 2px 0 0 #4c8dff !important;}}

/* The sidebar stays dark in every theme: beat the Light override's text colors */
[data-testid="stSidebar"] button p, [data-testid="stSidebar"] button span[data-testid="stIconMaterial"] {{color: #d5d7dd !important;}}
[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] p,
[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] span[data-testid="stIconMaterial"] {{color: #fff !important;}}

/* Foldable section headings in the Courses submenu */
[class*="st-key-nav_sub"] [class*="st-key-nav_sec_"] button, [class*="st-key-nav_sec_"] button {{
    padding: 0.55rem 16px 0.35rem 28px !important; gap: 8px !important;}}
[class*="st-key-nav_sec_"] button p {{color: #7d8190 !important;}}
[class*="st-key-nav_sec_"] button span[data-testid="stIconMaterial"] {{font-size: 1.2rem !important; color: #7d8190 !important;}}
[class*="st-key-nav_sec_"] button:hover {{background: transparent !important;}}
[class*="st-key-nav_sec_"] button:hover p, [class*="st-key-nav_sec_"] button:hover span[data-testid="stIconMaterial"] {{color: #d5d7dd !important;}}

/* All hover tooltips are lower case (project style) */
[data-testid="stTooltipContent"] {{text-transform: lowercase;}}

/* No upload size hint ("200MB per file") in file pickers */
[data-testid="stFileUploaderDropzoneInstructions"] {{display: none;}}

/* Library card menu: plain "..." with no box edge or chevron */
.stApp [data-testid="stPopover"] button {{border: none !important; background: transparent !important;
    box-shadow: none !important; padding: 0 4px; min-height: 0; justify-content: flex-end;}}
[data-testid="stPopover"] button span[data-testid="stIconMaterial"] {{display: none;}}
[data-testid="stPopover"] button p {{font-size: 1.5rem; font-weight: 700; line-height: 0.8; letter-spacing: 1px;}}
[data-testid="stPopover"] button:hover p {{color: var(--accent) !important;}}
[data-testid="stPopover"] .stMarkdownEllipsis {{overflow: visible !important; text-overflow: clip !important;}}
[data-testid="stPopover"] button {{min-width: 34px;}}

/* Library covers: clicking the cover opens the preview */
[class*="st-key-bookcard_"] {{position: relative;}}
[class*="st-key-bookcard_"]:hover .book-cover {{filter: brightness(1.08);}}
[class*="st-key-cover_"] {{position: absolute !important; top: 0; left: 0; width: 100%; aspect-ratio: 2 / 3; z-index: 2;}}
[class*="st-key-cover_"] button {{width: 100%; height: 100% !important; opacity: 0; cursor: pointer; min-height: 0;}}
.book-cover.has-img {{background-size: cover; background-position: top center; padding: 0;}}
.book-badge.tag {{border-color: var(--border); color: var(--text);}}

/* Library */
.lib-title {{font-family: Georgia, "Roboto Slab", serif; font-weight: 700;}}
.book-cover {{aspect-ratio: 2 / 3; border-radius: 6px; display: flex; align-items: flex-end; padding: 14px;
    box-shadow: 0 2px 8px #0005; margin-bottom: 0.6rem; color: #fff;}}
.book-cover span {{font-family: Georgia, serif; font-weight: 700; font-size: 1.15rem; line-height: 1.2;}}
.book-badges {{display: flex; flex-wrap: wrap; gap: 6px; margin: 2px 0 6px;}}
.book-badge {{display: inline-block; border: 1px solid var(--accent); color: var(--accent); border-radius: 999px;
    padding: 1px 11px; font-size: 0.8rem; white-space: nowrap;}}
.stApp .st-key-add_book_tile button[data-testid^="stBaseButton"] {{aspect-ratio: 2 / 3; height: auto !important; min-height: 0; width: 100%;
    border-style: dashed !important; border-width: 2px !important; border-color: rgba(140, 146, 160, 0.6) !important; border-radius: 6px; background: transparent !important;}}
.st-key-add_book_tile button:hover {{border-color: var(--accent) !important;}}
.st-key-add_book_tile button span[data-testid="stIconMaterial"] {{font-size: 2.2rem; color: var(--text);}}
.st-key-add_book_tile button p {{display: none;}}

/* Appearance cards */
.st-key-appearance button {{height: 130px; border-radius: 12px; border: 1px solid var(--border); background: transparent;}}
.st-key-appearance button > div > span {{flex-direction: column; gap: 10px;}}
.st-key-appearance button[data-testid="stBaseButton-primary"] {{background: var(--active); border-color: var(--accent);}}
.st-key-appearance button span[data-testid="stIconMaterial"] {{font-size: 2rem; color: var(--text) !important;}}
.st-key-appearance button[data-testid="stBaseButton-primary"] span[data-testid="stIconMaterial"] {{color: var(--active-text) !important;}}
</style>
"""
COURSE_ICON_CSS = "".join(icons.css_for_course(c["id"], c["icon"]) for c in crud.list_courses(section=None) if icons.is_custom(c["icon"]))
st.markdown(CSS + f"<style>{COURSE_ICON_CSS}</style>", unsafe_allow_html=True)

# Collapse the rail after a click; re-arm when the mouse leaves it.
components.html("""
<script>
const doc = window.parent.document;
if (!window.parent.__navHooked) {
  window.parent.__navHooked = true;
  doc.addEventListener('click', e => {
    const sb = doc.querySelector('section[data-testid="stSidebar"]');
    if (sb && sb.contains(e.target) && e.target.closest('button') && !e.target.closest('[class*="st-key-nav_sec_"]')) sb.classList.add('nav-collapsed');
  }, true);
  doc.addEventListener('mouseover', e => {
    const sb = doc.querySelector('section[data-testid="stSidebar"]');
    if (sb && !sb.contains(e.target)) sb.classList.remove('nav-collapsed');
  });
}
</script>""", height=0)

components.html("""
<script>
const win = window.parent, doc = win.document;
if (!win.__navDragV2) {
  win.__navDragV2 = true;
  let dragged = null;
  const SEL = '[class*="st-key-nav_course_"]';
  const course = el => (el && el.closest) ? el.closest(SEL) : null;
  const idOf = c => (c.className.match(/st-key-nav_course_(\d+)/) || [])[1];
  const sectionOf = c => {
    for (let e = c.previousElementSibling; e; e = e.previousElementSibling)
      if (e.matches('[class*="st-key-nav_sec_"]')) return e;
    return null;
  };
  const members = label => {
    const out = [];
    for (let e = label.nextElementSibling; e && !e.matches('[class*="st-key-nav_sec_"]'); e = e.nextElementSibling)
      if (e.matches(SEL)) out.push(e);
    return out;
  };
  const clear = () => doc.querySelectorAll('.nav-drop-above,.nav-drop-below,.nav-dragging')
      .forEach(e => e.classList.remove('nav-drop-above', 'nav-drop-below', 'nav-dragging'));
  const arm = () => doc.querySelectorAll(SEL + ' button').forEach(b => b.setAttribute('draggable', 'true'));
  doc.addEventListener('mouseover', arm);
  doc.addEventListener('dragstart', e => {
    const c = course(e.target); if (!c) return;
    dragged = c; c.classList.add('nav-dragging');
    e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', idOf(c));
  });
  doc.addEventListener('dragover', e => {
    if (!dragged) return;
    const t = course(e.target);
    if (!t || t === dragged || sectionOf(t) !== sectionOf(dragged)) return;
    e.preventDefault();
    const r = t.getBoundingClientRect();
    doc.querySelectorAll('.nav-drop-above,.nav-drop-below').forEach(x => x.classList.remove('nav-drop-above', 'nav-drop-below'));
    t.classList.add(e.clientY > r.top + r.height / 2 ? 'nav-drop-below' : 'nav-drop-above');
  });
  doc.addEventListener('drop', e => {
    if (!dragged) return;
    const t = course(e.target);
    if (!t || t === dragged || sectionOf(t) !== sectionOf(dragged)) { clear(); dragged = null; return; }
    e.preventDefault();
    const r = t.getBoundingClientRect(), below = e.clientY > r.top + r.height / 2;
    const ids = members(sectionOf(dragged)).map(idOf).filter(i => i !== idOf(dragged));
    let at = ids.indexOf(idOf(t)); if (below) at += 1;
    ids.splice(at, 0, idOf(dragged));
    clear(); dragged = null;
    const inp = doc.querySelector('.st-key-nav_order_sink input'); if (!inp) return;
    const set = Object.getOwnPropertyDescriptor(win.HTMLInputElement.prototype, 'value').set;
    inp.focus(); set.call(inp, ids.join(',') + '|' + Date.now());
    inp.dispatchEvent(new win.Event('input', {bubbles: true}));
    inp.dispatchEvent(new win.KeyboardEvent('keydown', {key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true}));
    inp.blur();
  });
  doc.addEventListener('dragend', () => { clear(); dragged = null; });
}
</script>""", height=0)

st.session_state.setdefault("page", "Home")
st.session_state.setdefault("mode", "Detailed")
st.session_state.setdefault("pdf_page", 1)


def nav_button(label, icon):
    active = st.session_state["page"] == label
    if st.button(label, icon=icon, key=f"nav_{label}", type="primary" if active else "tertiary"):
        st.session_state["page"] = label
        st.rerun()


def _open_course(c):
    st.session_state["page"] = "Courses"
    st.session_state["course_id"] = c["id"]
    st.session_state["courses_filter"] = crud.course_status(c)
    st.rerun()


def course_sub_buttons():
    """Courses submenu sections (Active, Self-Study, Completed); click a heading to fold it."""
    collapsed = st.session_state.setdefault("collapsed_sections", settings.get_collapsed())
    with st.container(key="nav_sub_courses"):
        for title, status in (("Active", "Active"), ("Self-Study", "Self-Study"), ("Completed", "Completed")):
            items = crud.courses_by_status(status)
            if not items:
                continue
            closed = status in collapsed
            if st.button(title, icon=":material/chevron_right:" if closed else ":material/expand_more:",
                         key=f"nav_sec_{status}", type="tertiary"):
                collapsed.symmetric_difference_update({status})
                settings.set_collapsed(collapsed)
                st.rerun()
            if closed:
                continue
            for c in items:
                selected = st.session_state["page"] == "Courses" and st.session_state.get("course_id") == c["id"]
                icon = ":material/water:" if icons.is_custom(c.get("icon")) else c.get("icon") or ":material/book:"
                if st.button(c["code"] or c["name"], icon=icon, key=f"nav_course_{c['id']}",
                             type="primary" if selected else "tertiary"):
                    _open_course(c)


with st.sidebar:
    # Hidden channel: the drag script writes "id,id,...|stamp" here and we persist the new order.
    sink = st.text_input("order", key="nav_order_sink", label_visibility="collapsed")
    if sink and sink != st.session_state.get("_order_saved"):
        st.session_state["_order_saved"] = sink
        crud.set_course_order([int(i) for i in sink.split("|")[0].split(",") if i.isdigit()])
    with st.container(key="nav_head"):
        st.button(" ", icon=":material/keyboard_double_arrow_right:", key="nav_expand", type="tertiary")
        st.button(" ", icon=":material/keyboard_double_arrow_left:", key="nav_collapse", type="tertiary")
    for label, (icon, _) in NAV_TOP.items():
        if label == "Courses":
            with st.container(key="nav_group_Courses"):
                nav_button(label, icon)
                course_sub_buttons()
        else:
            nav_button(label, icon)
    with st.container(key="nav_spacer"):
        st.markdown("&nbsp;", unsafe_allow_html=True)  # empty containers are not rendered
    for label, (icon, _) in NAV_BOTTOM.items():
        nav_button(label, icon)

# Active course is chosen from the Courses sub-menu in the sidebar
if not crud.get_course(st.session_state.get("course_id")):
    first = crud.courses_by_status("Active")
    st.session_state["course_id"] = first[0]["id"] if first else None

PAGES[st.session_state["page"]][1]()
