"""Study Assistant - Streamlit entry point."""
import streamlit as st
import streamlit.components.v1 as components

from core import crud
import importlib
import json
import sys

from views import icons
from views import tutorial

# The dev server caches imported modules between reruns; reload ours so edits apply without a restart.
# (exportfiles and dataimport are not reloaded: their running job and its progress live in the module.)
for _m in ("core.database", "core.crud", "library.courseoutline", "core.settings", "views.icons", "library.pdfmeta", "library.covers", "study.reader", "study.hlstore", "study.htmlnotes", "study.macros", "study.unitex", "study.outline", "study.htmlnotes", "study.quizzes", "study.quizgen", "study.hwassist", "study.gradereport", "study.solcrop", "library.syllabus", "study.eqsheet", "study.promptgen", "library.photos", "views.courses_view", "views.home_view",
           "views.navigation", "views.homework_view", "views.exam_mode_view", "views.recall_view", "views.library_view", "views.quiz_view", "views.calendar_view", "views.lab_view",
           "views.settings_view"):
    if _m in sys.modules:
        importlib.reload(sys.modules[_m])
from views import navigation
from library import photos
from core import settings
from core.database import init_db
from views import calendar_view, courses_view, home_view, lab_view, library_view, settings_view

st.set_page_config(page_title="Study Assistant", page_icon=":material/book:", layout="wide",
                   initial_sidebar_state="expanded")
init_db()
if "_quiz_linked" not in st.session_state:             # quiz records find their notes again after a note was deleted and imported anew (crud.relink_quiz_attempts)
    crud.relink_quiz_attempts()
    st.session_state["_quiz_linked"] = True
if "_backed_up" not in st.session_state:             # a safety copy of the database and settings outside the project (see backup.py)
    from datafiles import backup
    backup.run()
    st.session_state["_backed_up"] = True
if "_cal_synced" not in st.session_state:                        # the saved calendar feeds (Canvas, Brightspace, Google Calendar, Shovel) are read again, at most every few hours
    st.session_state["_cal_synced"] = True
    try:
        from views import calendar_import
        for _msg in calendar_import.auto_sync():
            st.toast(_msg)
    except Exception:
        pass
if "_titles_fixed" not in st.session_state:          # course codes in file names read "AE 333", not "AE333" or "ae 333"
    crud.fix_book_titles()
    st.session_state["_titles_fixed"] = True
photos.organize_photos()

# (label, material icon, renderer)
NAV_TOP = {
    "Home": (":material/home:", home_view.render),
    "Calendar": (":material/calendar_month:", calendar_view.render),
    "Library": (":material/library_books:", library_view.render),
    "Note Reader": (":material/auto_stories:", lab_view.render),
    "Courses": ("svg:course_cap", courses_view.render),
}
NAV_BOTTOM = {"Settings": (":material/settings:", settings_view.render)}
PAGES = {**NAV_TOP, **NAV_BOTTOM}

COLLAPSED_W, EXPANDED_W = 76, 270
CSS = f"""
<style>
{settings.css_vars(settings.get_appearance(), settings.get_color_theme())}
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
/* Streamlit's own top-right interface (Deploy, the three-dot menu, "Running...") is not part of this app */
[data-testid="stToolbar"], [data-testid="stMainMenu"], [data-testid="stAppDeployButton"], [data-testid="stToolbarActions"], [data-testid="stStatusWidget"], #MainMenu {{
    display: none !important; visibility: hidden !important;}}

/* Nav buttons (no radio dots) */
[data-testid="stSidebar"] button {{
    width: calc(100% - 20px) !important; margin: 0 10px; justify-content: flex-start; gap: 19px; padding: 0.8rem 18px;
    border-radius: 12px; border: 1px solid transparent;
    background: transparent; box-shadow: none; white-space: nowrap;}}
[data-testid="stSidebar"] button p {{font-size: 1.05rem; color: #d5d7dd; white-space: nowrap; opacity: 0; transition: opacity .15s;}}
section[data-testid="stSidebar"] > div:first-child:hover button p {{opacity: 1;}}
section[data-testid="stSidebar"].nav-collapsed > div:first-child button p {{opacity: 0 !important;}}
[data-testid="stSidebar"] button span[data-testid="stIconMaterial"] {{font-size: 1.5rem; color: #d5d7dd;}}
[data-testid="stSidebar"] button:hover {{background: #23252c;}}
[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] {{
    background: transparent; border-color: rgba(255, 255, 255, 0.9);}}
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
[class*="st-key-nav_sub"] button {{padding: 0.5rem 16px 0.5rem 36px !important;}}

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

.st-key-hl_sink, .st-key-nav_order_sink {{position: absolute !important; width: 1px; height: 1px; overflow: hidden; opacity: 0; pointer-events: none;}}
.nav-dragging {{opacity: 0.4;}}
.nav-drop-above button {{box-shadow: 0 -2px 0 0 #4c8dff !important;}}
.nav-drop-below button {{box-shadow: 0 2px 0 0 #4c8dff !important;}}

/* The sidebar stays dark in every theme: beat the Light override's text colors */
[data-testid="stSidebar"] button p, [data-testid="stSidebar"] button span[data-testid="stIconMaterial"] {{color: #d5d7dd !important;}}
[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] p,
[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] span[data-testid="stIconMaterial"] {{color: #fff !important;}}

/* Foldable section headings in the Courses submenu */
[class*="st-key-nav_sub"] [class*="st-key-nav_sec_"] button, [class*="st-key-nav_sec_"] button {{
    padding: 0.55rem 16px 0.35rem 30px !important; gap: 8px !important;}}
[class*="st-key-nav_sec_"] button p {{color: #7d8190 !important;}}
[class*="st-key-nav_sec_"] button span[data-testid="stIconMaterial"] {{font-size: 1.2rem !important; color: #7d8190 !important;}}
[class*="st-key-nav_sec_"] button:hover {{background: transparent !important;}}
[class*="st-key-nav_sec_"] button:hover p, [class*="st-key-nav_sec_"] button:hover span[data-testid="stIconMaterial"] {{color: #d5d7dd !important;}}

/* All hover tooltips are lower case (project style) */
[data-testid="stTooltipContent"] {{text-transform: lowercase;}}

/* No upload size hint ("200MB per file") in file pickers */
[data-testid="stFileUploaderDropzoneInstructions"] {{display: none;}}
/* Accepted file types shown beside the Upload button (until a file is chosen) */
[data-testid="stFileUploaderDropzone"]:not(:has([data-testid="stFileUploaderFile"]))::after {{
    color: #8b90a0; font-size: 0.9rem; margin-left: 14px; align-self: center;}}
.st-key-library_file_box [data-testid="stFileUploaderDropzone"]:not(:has([data-testid="stFileUploaderFile"]))::after {{
    content: "PDF, HTML, ZIP";}}
[class*="st-key-photo_box_"] [data-testid="stFileUploaderDropzone"]:not(:has([data-testid="stFileUploaderFile"]))::after {{
    content: "PNG, JPG, HEIC, WebP, GIF";}}

/* Library card menu button: plain "..." (opens the Edit File window) */
[class*="st-key-menu_"] button {{min-width: 34px; padding: 0 4px; min-height: 0; justify-content: flex-end;}}
[class*="st-key-menu_"] button p {{font-size: 1.5rem; font-weight: 700; line-height: 0.8; letter-spacing: 1px;}}
[class*="st-key-menu_"] button:hover p {{color: var(--accent) !important;}}

/* Library card menu: plain "..." with no box edge or chevron */
.stApp [data-testid="stPopover"] button {{border: none !important; background: transparent !important;
    box-shadow: none !important; padding: 0 4px; min-height: 0; justify-content: flex-end;}}
[data-testid="stPopoverButton"] > div > div[aria-hidden="true"] {{display: none !important;}}   /* no gap left where the arrow was */
[class*="st-key-hw"][class*="_card"] [data-testid="stPopoverButton"] span[data-testid="stIconMaterial"] {{font-size: 1.4rem !important; color: #f2b84b !important;}}
[data-testid="stPopoverButton"] > div {{gap: 0 !important; justify-content: center; width: 100%; margin: 0 !important;}}
[data-testid="stPopoverButton"] > div > div {{margin: 0 !important; padding: 0 !important;}}
[data-testid="stPopover"] button p {{font-size: 1.5rem; font-weight: 700; line-height: 0.8; letter-spacing: 1px;}}
[data-testid="stPopover"] button:hover p {{color: var(--accent) !important;}}
[data-testid="stPopover"] .stMarkdownEllipsis {{overflow: visible !important; text-overflow: clip !important;}}
[data-testid="stPopover"] button {{min-width: 34px;}}

/* Library covers: clicking the cover opens the preview */
[class*="st-key-bookcard_"] {{position: relative;}}
[class*="st-key-bookcard_"]:hover .book-cover {{filter: brightness(1.08);}}
[class*="st-key-cover_"] {{position: absolute !important; top: 0; left: 0; width: 100%; aspect-ratio: 2 / 3; z-index: 2;}}
[class*="st-key-cover_"] [data-testid="stButton"], [class*="st-key-tile_"] [data-testid="stButton"] {{width: 100%; height: 100%;}}
[class*="st-key-cover_"] button {{width: 100%; height: 100% !important; opacity: 0; cursor: pointer; min-height: 0;}}
.book-cover.has-img {{background-size: cover; background-position: top center; padding: 0;}}
.book-badge.tag {{color: #fff !important;}}
.book-badge.meta {{border-color: var(--border); color: var(--text); opacity: 0.85;}}
.book-badge.status {{border-color: var(--border); color: var(--text); opacity: 0.85;}}
.book-badge.status.active {{border-color: #2f9e5f; color: #2f9e5f; background: rgba(47, 158, 95, 0.12); opacity: 1;}}
.book-badge.status.completed {{border-color: #6a77dd; color: #6a77dd; background: rgba(106, 119, 221, 0.12); opacity: 1;}}

/* Merge Courses and Add Course: two outlined buttons of the same size, side by side at the top right */
.st-key-course_actions {{gap: 0.6rem !important; justify-content: flex-end !important;}}
/* Settings > Color Theme: three small color chips above the name of each theme */
.theme-card {{display: flex; height: 62px; border-radius: 12px; overflow: hidden; border: 1px solid rgba(160, 170, 190, 0.35); margin: 0 0 8px;}}
.theme-card span {{flex: 1 1 0; display: block;}}
.theme-card.on {{outline: 3px solid var(--accent); outline-offset: 3px;}}
/* the whole card (the colors and the name) is the button: a click on the colors chooses the theme too */
.st-key-color_themes [data-testid="stColumn"], .st-key-color_themes [data-testid="column"] {{position: relative; padding-bottom: 42px;}}
.st-key-color_themes [class*="st-key-theme_"] {{position: absolute !important; inset: 0; width: auto !important; margin: 0 !important;}}
.st-key-color_themes [data-testid="stButton"] {{width: 100%; height: 100%;}}
.st-key-color_themes button {{width: 100% !important; height: 100% !important; align-items: flex-end !important; justify-content: flex-start !important; padding: 0 !important; min-height: 0 !important; background: transparent !important; border: 0 !important; cursor: pointer;}}
.st-key-color_themes button > div {{width: 100%; justify-content: flex-start !important;}}
.st-key-color_themes button p {{font-size: 1rem; font-weight: 700; text-align: left !important; width: 100%;}}
.st-key-color_themes [data-testid="stColumn"]:hover .theme-card:not(.on), .st-key-color_themes [data-testid="column"]:hover .theme-card:not(.on) {{outline: 2px solid var(--border); outline-offset: 3px;}}
/* Getting Started (Home): the check chain (a tick in a green circle, the next step in blue, the rest grey, joined by lines) and the number or tick in front of each step */
.tut-chain {{display: flex; align-items: flex-start; margin: 0.4rem 0 0.2rem; overflow-x: auto; padding: 4px 2px 8px;}}
.tc-step {{display: flex; flex-direction: column; align-items: center; gap: 6px; flex: 0 0 auto; min-width: 76px;}}
.tc-dot {{width: 34px; height: 34px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 1rem; border: 2px solid var(--border); color: var(--text); opacity: 0.55; box-sizing: border-box;}}
.tc-done .tc-dot {{background: #2c9a5a; border-color: #2c9a5a; color: #fff; opacity: 1;}}
.tc-now .tc-dot {{background: #2f6fe0; border-color: #2f6fe0; color: #fff; opacity: 1; width: 40px; height: 40px; margin: -3px 0; box-shadow: 0 0 0 5px rgba(47, 111, 224, 0.25);}}
.tc-name {{font-size: 0.78rem; opacity: 0.6; text-align: center; white-space: nowrap;}}
.tc-now .tc-name {{opacity: 1; font-weight: 700; color: #6fb0ff;}}
.tc-done .tc-name {{opacity: 0.9;}}
.tc-line {{flex: 1 1 24px; height: 2px; background: var(--border); margin: 16px 2px 0; min-width: 16px;}}
.tc-line.tc-done {{background: #2c9a5a;}}
.tut-mark {{width: 28px; height: 28px; border-radius: 50%; border: 2px solid var(--border); display: flex; align-items: center; justify-content: center; font-size: 0.85rem; font-weight: 700; opacity: 0.85;}}
.tut-mark.tut-done {{background: #2c7a4b; border-color: #2c7a4b; color: #fff; opacity: 1;}}
.tut-why {{font-size: 0.85rem; opacity: 0.72;}}
.st-key-add_course_open, .st-key-merge_courses_open {{width: 10.5rem !important; flex: 0 0 10.5rem !important;}}
.st-key-add_course_open [data-testid="stButton"], .st-key-merge_courses_open [data-testid="stButton"] {{width: 100% !important;}}
/* The buttons at the top of every page look like Update Files: an outlined 40 px button with the icon and the text in the middle, on one line (the Import menu of the Library is the same). */
.stApp :is(.st-key-tut_reopen, .st-key-merge_courses_open, .st-key-add_course_open, .st-key-course_back, .st-key-course_update_files, .st-key-edit_schedule_open, .st-key-cal_autoplan, .st-key-tk_add_open,
           .st-key-lab_full_close, .st-key-quiz_notes_close, [class*="st-key-lab_dock_"], [class*="st-key-quiz_save_"], [class*="st-key-quiz_back_"]) button {{
  min-height: 40px !important; height: 40px; min-width: 10.5rem; padding: 0 16px !important; border-radius: 8px !important; white-space: nowrap; width: auto;
  display: flex !important; align-items: center !important; justify-content: center !important; text-align: center !important;}}
.stApp :is(.st-key-tut_reopen, .st-key-merge_courses_open, .st-key-add_course_open) button {{width: 100% !important;}}
.stApp :is(.st-key-tut_reopen, .st-key-merge_courses_open, .st-key-add_course_open, .st-key-course_back, .st-key-course_update_files, .st-key-edit_schedule_open, .st-key-lab_full_close, .st-key-quiz_notes_close,
           [class*="st-key-lab_dock_"], [class*="st-key-quiz_save_"], [class*="st-key-quiz_back_"]) button:not([data-testid="stBaseButton-primary"]) {{border: 1px solid var(--border) !important; background: var(--input) !important;}}
.stApp :is(.st-key-tut_reopen, .st-key-merge_courses_open, .st-key-add_course_open, .st-key-course_back, .st-key-course_update_files, .st-key-edit_schedule_open, .st-key-lab_full_close, .st-key-quiz_notes_close) button:hover {{border-color: var(--accent) !important;}}
/* inside: button > div > span (the row) > icon + text; every level is centered, and the text has no extra line height or margin that would sit it lower than the icon */
.stApp :is(.st-key-tut_reopen, .st-key-merge_courses_open, .st-key-add_course_open, .st-key-course_back, .st-key-course_update_files, .st-key-edit_schedule_open, .st-key-cal_autoplan, .st-key-tk_add_open,
           .st-key-lab_full_close, .st-key-quiz_notes_close, [class*="st-key-lab_dock_"], [class*="st-key-quiz_save_"], [class*="st-key-quiz_back_"]) button :is(div, span):not([data-testid="stIconMaterial"]) {{
  display: flex !important; align-items: center !important; justify-content: center !important; gap: 8px; margin: 0 !important; padding: 0 !important; line-height: 1.4 !important; overflow: visible !important; width: auto !important;}}
.stApp :is(.st-key-tut_reopen, .st-key-merge_courses_open, .st-key-add_course_open, .st-key-course_back, .st-key-course_update_files, .st-key-edit_schedule_open, .st-key-cal_autoplan, .st-key-tk_add_open,
           .st-key-lab_full_close, .st-key-quiz_notes_close, [class*="st-key-lab_dock_"], [class*="st-key-quiz_save_"], [class*="st-key-quiz_back_"]) button p {{
  font-size: 0.9rem !important; font-weight: 400 !important; line-height: 1.4 !important; overflow: visible !important; margin: 0 !important; padding: 0 !important; text-align: center !important;}}
.stApp :is(.st-key-tut_reopen, .st-key-merge_courses_open, .st-key-add_course_open, .st-key-course_back, .st-key-course_update_files, .st-key-edit_schedule_open, .st-key-cal_autoplan, .st-key-tk_add_open,
           .st-key-lab_full_close, .st-key-quiz_notes_close, [class*="st-key-lab_dock_"], [class*="st-key-quiz_save_"]) [data-testid="stIconMaterial"] {{font-size: 1.2rem !important; line-height: 1 !important; display: block;}}

/* Course summary tiles */
.course-tile {{aspect-ratio: 1 / 1; border-radius: 14px; padding: 16px; display: flex; flex-direction: column;
    color: #fff; box-shadow: 0 2px 8px #0004; overflow: hidden; margin-bottom: 0.6rem;}}
/* Course banner: sits between the "All Courses" button row and the tab row, title and labels on the photo */
.course-hero {{margin: 4px 0 18px; min-height: 230px; border-radius: 16px; display: flex; align-items: flex-end;
    padding: 26px 32px; color: #fff; box-shadow: 0 3px 12px #0003;}}
.ch-title {{font-size: 2.2rem; font-weight: 800; line-height: 1.15; margin: 8px 0 6px; text-shadow: 0 2px 8px #000a;}}
.ch-meta {{font-size: 1.05rem; opacity: 0.95; text-shadow: 0 1px 4px #000a;}}
.ch-pills {{display: flex; gap: 8px; flex-wrap: wrap;}}
.ch-pills .ct-cat {{margin-bottom: 0; font-size: 0.78rem; background: rgba(255,255,255,0.25); text-shadow: none;}}

.course-banner {{height: 150px; border-radius: 12px; background-size: cover; background-position: center;
    margin: 4px 0 12px; box-shadow: 0 2px 8px #0003;}}
.course-tile .ct-code, .course-tile .ct-name, .course-tile .ct-meta {{text-shadow: 0 1px 3px #0008;}}
.ct-top {{display: flex; justify-content: space-between; align-items: flex-start; gap: 8px;}}
.ct-icon {{flex: none; width: 30px; height: 30px; opacity: 0.92;}}
.ct-icon.svg {{background: #fff;}}
.ct-icon.material {{font-family: "Material Symbols Rounded"; font-size: 30px; line-height: 1; color: #fff;
    font-weight: normal; font-style: normal; font-feature-settings: "liga"; white-space: nowrap; overflow: hidden;}}
.ct-code {{font-weight: 800; font-size: 1.3rem; line-height: 1.1; flex: 1; min-width: 0; overflow-wrap: anywhere;}}
.ct-code.ct-title {{font-size: 1.1rem; line-height: 1.2;}}
.ct-name {{margin-top: 8px; font-size: 1rem; font-weight: 500; line-height: 1.25; display: -webkit-box;
    -webkit-line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden;}}
.ct-cat {{display: inline-block; font-size: 0.72rem; font-weight: 600; letter-spacing: 0.04em;
    background: rgba(255,255,255,0.22); border-radius: 999px; padding: 1px 10px; margin-bottom: 6px;}}
.ct-meta {{margin-top: auto; font-size: 0.85rem; opacity: 0.9; line-height: 1.35;}}
[class*="st-key-coursetile_"] {{position: relative;}}
[class*="st-key-coursetile_"]:hover .course-tile {{filter: brightness(1.1);}}
[class*="st-key-tile_"] {{position: absolute !important; top: 0; left: 0; width: 100%; aspect-ratio: 1 / 1; z-index: 2;}}
[class*="st-key-tile_"] button {{width: 100%; height: 100% !important; opacity: 0; cursor: pointer; min-height: 0;}}
[class*="st-key-tilemenu_"] {{position: absolute !important; right: 8px; bottom: 6px; z-index: 3; width: auto !important;}}
[class*="st-key-tilemenu_"] button {{min-height: 0; padding: 0 8px; background: transparent !important; border: none !important;}}
[class*="st-key-tilemenu_"] button p {{color: #fff !important; font-size: 1.5rem; font-weight: 700; line-height: 0.8;
    letter-spacing: 1px; text-shadow: 0 1px 3px #0008;}}
[class*="st-key-tilemenu_"] button:hover p {{opacity: 0.8;}}

.st-key-nav_back_hidden, .st-key-nav_forward_hidden, .st-key-menu_toggle_hidden, .st-key-refresh_hidden, .st-key-screenshot_hidden {{position: absolute !important; width: 1px; height: 1px; overflow: hidden; opacity: 0;
    pointer-events: none;}}

/* Course outline: hidden box that carries a clicked point to the app */
.st-key-outline_sink, .st-key-lib_sink, .st-key-lib_link_sink, .st-key-cal_sink, .st-key-tree_sink, .st-key-tour_sink {{position: absolute !important; width: 1px; height: 1px; overflow: hidden; opacity: 0; pointer-events: none;}}

/* Home: term stats */
.home-stats {{display: flex; gap: 12px; margin: 2px 0 18px;}}
.home-stat {{border: 1px solid var(--border); border-radius: 12px; padding: 10px 18px; display: flex; flex-direction: column; line-height: 1.25;}}
.home-stat b {{font-size: 1.5rem;}}
.home-stat span {{font-size: 0.85rem; opacity: 0.7;}}

/* Course page: outline */
.ol {{border: 1px solid var(--border); border-radius: 12px; overflow: hidden; padding-bottom: 8px;}}
.ol-main {{display: flex; align-items: baseline; gap: 10px; font-weight: 700; font-size: 1.05rem; padding: 14px 16px 6px;
    border-top: 1px solid var(--border);}}
.ol > .ol-main:first-child {{border-top: none;}}
.ol-marker {{min-width: 34px; opacity: 0.65;}}
.ol-hours {{margin-left: auto; font-size: 0.78rem; font-weight: 500; border: 1px solid var(--border); border-radius: 999px;
    padding: 1px 10px; white-space: nowrap;}}
.ol-sub {{display: flex; gap: 10px; padding: 3px 16px 3px 44px;}}
.ol-sub .ol-marker {{min-width: 30px; white-space: nowrap;}}
.ol-flat {{display: flex; gap: 10px; padding: 5px 16px;}}
.ol-flat:first-child {{padding-top: 12px;}}
.ol-wide .ol-main .ol-marker {{min-width: 74px; white-space: nowrap;}}
.ol-wide .ol-sub .ol-marker {{min-width: 52px;}}
.ol-wide .ol-flat .ol-marker {{min-width: 64px; opacity: 0.65; white-space: nowrap;}}
.ol-sub.ol-fold {{display: block;}}
.ol-fold > summary {{display: flex; gap: 10px; cursor: pointer; list-style: none; position: relative;}}
.ol-fold > summary::-webkit-details-marker {{display: none;}}
.ol-fold > summary::before {{content: "›"; position: absolute; left: -22px; top: -3px; font-size: 1.35rem; line-height: 1.25;
    opacity: 0.7; transition: transform .15s;}}
.ol-fold[open] > summary::before {{transform: rotate(90deg);}}
.ol-count {{margin-left: 8px; font-size: 0.72rem; opacity: 0.6; align-self: center;}}
.ol-kids {{padding: 4px 0 6px 32px;}}
.ol-leaf {{display: flex; gap: 10px; padding: 2px 0; font-size: 0.95rem;}}
.ol-leaf .ol-marker {{min-width: 22px; text-align: right;}}
.ol-leaf.ol-l3 {{padding-left: 34px; font-size: 0.9rem; opacity: 0.92;}}
.ol a {{color: var(--accent) !important; text-decoration: none;}}
.ol a:hover {{text-decoration: underline;}}

/* Course page: links */
.res-link {{font-weight: 600; text-decoration: none; color: var(--accent) !important;}}
.res-link:hover {{text-decoration: underline;}}
[class*="st-key-link_open_"], [class*="st-key-link_rm_"], [class*="st-key-outline_toggle_"] {{width: 100% !important;}}
[class*="st-key-link_open_"] [data-testid="stButton"], [class*="st-key-link_rm_"] [data-testid="stButton"],
[class*="st-key-outline_toggle_"] [data-testid="stButton"] {{width: 100%; display: flex; justify-content: flex-end;}}
[class*="st-key-link_open_"] [data-testid="stButton"] {{justify-content: flex-start;}}
[class*="st-key-link_open_"] button, [class*="st-key-link_rm_"] button, [class*="st-key-outline_toggle_"] button {{
    min-height: 0; padding: 0.3rem 0.8rem; width: auto !important;}}

/* Course page: deadline lists */
.dl-list {{border: 1px solid var(--border); border-radius: 12px; overflow: hidden; margin-bottom: 1rem;}}
.dl-row {{display: grid; grid-template-columns: 1fr 190px 90px; gap: 12px; align-items: center; padding: 9px 16px;
    border-bottom: 1px solid var(--border);}}
.dl-row:last-child {{border-bottom: none;}}
.dl-title {{font-weight: 600;}}
.dl-when {{opacity: 0.8; font-size: 0.92rem;}}
/* Quiz cards: the same look as the Self-check in the notes (navy cards, outlined pill options) */
[class*="st-key-qcard_"] {{background: var(--qcard); border: 1px solid var(--qline); border-radius: 12px; padding: 1.1rem 1.3rem; gap: 0.9rem;}}
[class*="st-key-qcard_"] [data-testid="stMarkdownContainer"] p {{font-size: 1.02rem;}}
[class*="st-key-qopts_"] {{gap: 0.8rem !important;}}
.stApp [class*="st-key-qopts_"] button[data-testid^="stBaseButton"] {{background: transparent !important; border: 1px solid var(--qline) !important;
    border-radius: 10px !important; min-height: 2.7rem; padding: 0.35rem 1.1rem !important; box-shadow: none !important;}}
.stApp [class*="st-key-qopts_"] button[data-testid^="stBaseButton"] p {{font-size: 1.02rem; line-height: 1.35;}}
.stApp [class*="st-key-qopts_"] button[data-testid^="stBaseButton"]:hover {{border-color: var(--accent) !important; background: rgba(76, 141, 255, 0.08) !important;}}
/* quiz with the notes open: the note stays in view on the right while the questions scroll on the left */
[data-testid="stColumn"]:has(.st-key-quiz_notes_pane) {{position: sticky; top: 3.8rem; align-self: flex-start; height: fit-content;}}
.st-key-quiz_notes_pane iframe {{height: calc(100vh - 12rem) !important; min-height: 320px;}}
.st-key-quiz_notes_pane [data-testid="stElementContainer"]:has(iframe) {{height: calc(100vh - 12rem) !important; min-height: 320px;}}
[class*="st-key-qcard_"] [data-testid="stCaptionContainer"] {{margin-top: -0.4rem;}}
.qtag {{font-size: 0.76rem; letter-spacing: 0.04em; text-transform: uppercase; opacity: 0.55; margin-top: -0.3rem;}}
.und-row {{display: grid; grid-template-columns: minmax(0, 3fr) minmax(80px, 2fr) 3rem 7.8rem; gap: 14px; align-items: center;
    padding: 6px 16px; border-bottom: 1px solid var(--border);}}
.und-row:last-child {{border-bottom: none;}}
.und-name {{font-weight: 600;}}
.und-detail {{font-weight: 400; font-size: 0.82rem; opacity: 0.7; margin-top: 2px;}}
.und-bar {{height: 8px; border-radius: 4px; background: var(--border); overflow: hidden;}}
.und-bar i {{display: block; height: 100%; border-radius: 4px; background: var(--accent);}}
.und-bar i.done {{background: #2f9e5f;}} .und-bar i.open {{background: #d9a21b;}} .und-bar i.late {{background: #d14343;}}
.und-pct {{text-align: right; font-variant-numeric: tabular-nums; font-size: 0.9rem;}}
.und-row .dl-pill {{justify-self: end; width: 100%; text-align: center; padding: 1px 6px;}}
.und-score {{display: flex; align-items: center; gap: 16px; padding: 10px 0 6px;}}
.und-score b {{font-size: 2rem;}} .und-score span:not(.dl-pill) {{font-size: 1.3rem; opacity: 0.8;}}
.dl-solution {{font-size: 0.78rem; font-weight: 500; margin-left: 8px; opacity: 0.85;}}
.st-key-lib_sort_box {{width: 150px; max-width: 100%; margin-left: auto;}}
.stApp [class*="st-key-gpi_"] button {{justify-content: flex-start !important; text-align: left !important; height: auto; min-height: 0; padding: 2px 4px;}}
.stApp [class*="st-key-gpi_"] button p {{text-align: left !important;}}
.syl-info td:first-child {{font-weight: 600; width: 120px; opacity: 0.85;}} .syl-mail {{opacity: 0.7; font-size: 0.85rem; margin-left: 8px;}}
/* while the page or a tab is switching, the old content disappears at once instead of squeezing as the new one arrives */
.stApp.switching [data-testid="stMain"] [data-stale="true"] {{display: none !important;}}
.stApp.switching [data-testid="stMain"] [data-stale="true"] * {{transition: none !important;}}
.syl-stack {{display: flex; flex-direction: column; align-items: center; gap: 10px;}} .syl-stack .syl-table {{margin: 0; width: 100%;}}
.syl-row {{display: flex; align-items: center; gap: 28px; flex-wrap: wrap; margin: 6px 0 10px;}}
.syl-row .syl-table {{flex: 1 1 340px; margin: 0;}}
.syl-pie {{flex: none; width: 180px; height: 180px;}} .syl-slice {{transition: opacity 0.12s;}} .syl-pie:hover .syl-slice {{opacity: 0.55;}} .syl-pie .syl-slice:hover {{opacity: 1;}}
.syl-c1 {{font-size: 26px; font-weight: 700; fill: var(--text);}} .syl-c2 {{font-size: 11px; fill: var(--text); opacity: 0.7;}}
.syl-sw {{display: inline-block; width: 11px; height: 11px; border-radius: 3px; margin-right: 9px; vertical-align: -1px;}}
.syl-open {{font-size: 0.95rem; font-weight: 600;}}
.syl-table {{border-collapse: collapse; margin: 6px 0 10px; width: 100%; max-width: 640px; font-size: 0.92rem;}}
.syl-table th, .syl-table td {{border-bottom: 1px solid var(--border); padding: 6px 10px; text-align: left;}}
.syl-table th {{font-weight: 600; opacity: 0.8; font-size: 0.82rem;}}
.syl-table .n {{text-align: right;}} .syl-table .none {{opacity: 0.6;}}
/* the "to finish with" table is as wide as its text needs (one line per cell); a very narrow window scrolls it */
.syl-scroll {{overflow-x: auto;}}
.syl-goals {{width: auto; min-width: 100%; max-width: none;}}
.syl-goals th, .syl-goals td {{white-space: nowrap;}}
.syl-goals td:first-child, .syl-goals th:first-child {{padding-right: 24px;}}
.dl-grade {{font-size: 0.85rem; margin-top: 3px;}} .dl-grade b {{color: #2f9e5f;}} .dl-grade.none {{opacity: 0.6;}}
.dl-sub {{opacity: 0.75; font-size: 0.85rem; margin-top: 3px;}}
.dl-pill {{justify-self: end; white-space: nowrap; font-size: 0.78rem; border-radius: 999px; padding: 1px 12px; border: 1px solid var(--border);}}
.dl-pill.done {{border-color: #2f9e5f; color: #2f9e5f; background: rgba(47, 158, 95, 0.12);}}
.dl-pill.open {{border-color: var(--accent); color: var(--accent); background: rgba(76, 141, 255, 0.10);}}
.dl-pill.late {{border-color: #d14343; color: #d14343; background: rgba(209, 67, 67, 0.12);}}
.dl-pill.none {{opacity: 0.7;}}
.up-row {{display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 10px 16px;
    border-bottom: 1px solid var(--border);}}
.up-row:last-child {{border-bottom: none;}}
.up-meta {{display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 4px;}}
.up-meta .book-badge {{margin: 0;}}
/* Home: upcoming list, one row per item with a check button that marks it complete */
.st-key-up_list [data-testid="stVerticalBlock"] {{gap: 0;}}
.st-key-up_list [data-testid="stHorizontalBlock"] {{align-items: center; gap: 0.5rem; padding: 12px 8px 12px 10px !important; border-bottom: 1px solid var(--border);}}
.st-key-up_list [data-testid="stMarkdownContainer"] p {{margin: 0;}}
.st-key-up_list [data-testid="stMarkdownContainer"], .st-key-up_list [data-testid="stMarkdown"], .st-key-up_list [data-testid="stElementContainer"] {{margin: 0 !important;}}
.st-key-up_list [data-testid="stElementContainer"]:last-child [data-testid="stHorizontalBlock"] {{border-bottom: none;}}
.st-key-up_list .dl-pill {{display: inline-block;}}
.st-key-up_list [data-testid="stColumn"]:nth-child(2) {{text-align: right;}}
.st-key-up_list button {{min-height: 2rem; padding: 0 0.6rem; border: 1px solid var(--border); border-radius: 999px;}}
.st-key-up_list button:hover {{border-color: #2f9e5f; color: #2f9e5f;}}


/* Settings: the bar that jumps to a section */
.st-key-settings_nav {{padding: 0; border-bottom: 1px solid var(--border);}}
.st-key-settings_nav, .st-key-settings_nav * {{min-height: 0;}}
.st-key-settings_nav [data-testid="stElementContainer"], .st-key-settings_nav [data-testid="stMarkdown"], .st-key-settings_nav [data-testid="stMarkdown"] > div {{height: auto !important; overflow: visible;}}
.st-key-settings_nav [data-testid="stMarkdownContainer"] {{margin-bottom: 0 !important;}}   /* Streamlit pulls a markdown block up by a line: the bar's box was a line too short and its bottom line crossed the pills */
.st-key-settings_nav nav {{margin-bottom: 0;}}
div:has(> .st-key-settings_nav) {{position: sticky; top: 2.75rem; z-index: 60; background: var(--bg);}}   /* the wrapper sticks: a sticky box stays inside its parent, so the parent must be the whole page */
/* the bar looks like the tabs of a course page: plain text, a red line under the one you are at, a thin line under the row */
.set-nav {{display: flex; flex-wrap: wrap; gap: 6px 26px;}}
.set-nav a {{color: var(--text); text-decoration: none; font-size: 1rem; padding: 10px 2px 9px; border-bottom: 2px solid transparent; margin-bottom: -1px; white-space: nowrap; opacity: 0.85;
  transition: border-color .15s, opacity .15s;}}
.set-nav a:hover {{opacity: 1; border-bottom-color: #ffffff40;}}
.set-nav a.on {{opacity: 1; border-bottom-color: var(--primary, #ff4b4b); font-weight: 600;}}
h2[id], h3[id] {{scroll-margin-top: 7rem;}}


/* Planner calendar: the panel of draggable blocks, free time, drop targets */
.pl-panel {{display: flex; flex-direction: column; gap: 6px; max-height: 70vh; overflow-y: auto; padding-right: 4px;}}
.pl-title {{font-size: 0.78rem; opacity: 0.65;}}
.pl-head {{font-size: 0.8rem; font-weight: 700; opacity: 0.8; margin-top: 8px;}}
.pl-item {{border: 1px solid var(--border); border-left: 5px solid var(--accent); border-radius: 8px; padding: 6px 10px; font-size: 0.85rem; cursor: grab; user-select: none; touch-action: none; line-height: 1.25;}}
.pl-item b {{display: block; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}}
.pl-item span {{display: block; font-size: 0.72rem; opacity: 0.75;}}
.pl-item .wk-dot {{margin-top: 4px;}}
.pl-item.pl-event {{background: transparent; color: var(--text); border: 1px dashed var(--accent); border-left: 1px dashed var(--accent); font-weight: 600;}}
.pl-grip {{display: inline-block !important; margin-right: 8px; opacity: 0.7; font-size: 1rem !important;}}
.pl-item:hover {{filter: brightness(1.12);}}
.pl-empty {{font-size: 0.8rem; opacity: 0.6;}}
body.pl-dragging, body.pl-dragging * {{cursor: grabbing !important; user-select: none !important;}}
.wk-preview {{position: absolute; left: 2px; right: 2px; z-index: 6; pointer-events: none; border: 2px dashed var(--c, var(--accent)); border-radius: 6px; padding: 3px 6px;
  background: color-mix(in srgb, var(--c, var(--accent)) 35%, transparent); color: #fff; font-size: 0.74rem; line-height: 1.25; overflow: hidden; box-shadow: 0 4px 12px #0005;}}
.wk-col.drop-hover {{outline: 2px solid var(--accent); outline-offset: -2px; transition: outline-color .1s;}}
.wk-used {{position: absolute; left: 0; bottom: 0; height: 4px; background: #2f9e5f; border-radius: 0 2px 2px 0; opacity: 0.9;}}
.st-key-timer_bar {{border-color: var(--accent) !important;}}
.wk-free {{position: absolute; left: 0; right: 0; background: rgba(124, 106, 255, 0.12); display: flex; align-items: center; justify-content: center; pointer-events: none; z-index: 0;}}
.wk-free span {{color: #8f86ff; font-size: 0.8rem; font-weight: 600;}}
.wk-block {{z-index: 1;}}


/* The warning banner of the Calendar: an x at the right end of the box */
.st-key-cal_banner {{position: relative;}}
.st-key-cal_banner .st-key-cal_banner_x {{position: absolute; right: 10px; top: 50%; transform: translateY(-50%); width: auto; z-index: 3;}}
.st-key-cal_banner .st-key-cal_banner_x button {{min-height: 32px; width: 32px; padding: 0; border-radius: 50%; opacity: 0.75;}}
.st-key-cal_banner .st-key-cal_banner_x button:hover {{opacity: 1; background: #ffffff1f;}}
.st-key-cal_banner [data-testid="stAlert"] {{padding-right: 52px;}}
.st-key-cal_banner .st-key-cal_banner_never {{position: absolute; right: 52px; top: 50%; transform: translateY(-50%); width: auto; z-index: 3;}}
.st-key-cal_banner .st-key-cal_banner_never button {{min-height: 30px; padding: 0 10px; font-size: 0.82rem; opacity: 0.8; text-decoration: underline;}}
.st-key-cal_banner [data-testid="stAlert"] {{padding-right: 190px;}}
/* Calendar: the two buttons at the right edge line up; the Task List header row */
.st-key-cal_autoplan, .st-key-edit_schedule_open {{display: flex; justify-content: flex-end; width: 100% !important;}}
.tl-head {{font-size: 0.78rem; font-weight: 700; opacity: 0.65; text-transform: none;}}
/* Task List: the course boxes on the left look like the blocks of the Calendar panel */
.st-key-tl_side button {{justify-content: flex-start; text-align: left; border: 0; border-left: 4px solid #6b7280; border-radius: 8px; padding: 10px 12px; font-weight: 700; color: var(--text);
  transition: filter .12s, box-shadow .12s;}}
.st-key-tl_side button:hover {{filter: brightness(1.25);}}
.st-key-tl_side button[data-testid="stBaseButton-primary"] {{box-shadow: inset 0 0 0 2px var(--accent); filter: brightness(1.15);}}
.st-key-tl_side button p {{text-align: left; width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;}}
body.nav-switching [data-stale="true"] {{display: none !important;}}
/* Import From Syllabus: the line under a course's tick box sits close to it */
.stElementContainer[class*="st-key-si_pick_"] + .stElementContainer {{margin-top: -0.85rem; margin-bottom: 0.2rem;}}
/* Light (faster) mode, for slow devices: no animations, no transitions, no shadows, no blur. */
html.lite *, html.lite *::before, html.lite *::after {{transition: none !important; animation: none !important; scroll-behavior: auto !important;
  box-shadow: none !important; text-shadow: none !important; filter: none !important; backdrop-filter: none !important; will-change: auto !important;}}
html.lite .mm-node:hover circle {{filter: none !important;}}
/* Calendar: the width of the left panel, its splitter, the zoom bar of the time scale */
div[data-testid="stColumn"]:has(.pl-wrap) {{flex: 0 0 var(--pl-w, 260px) !important; width: var(--pl-w, 260px) !important; min-width: 0 !important; overflow: visible;
  transition: flex-basis .3s cubic-bezier(.4, 0, .2, 1), width .3s cubic-bezier(.4, 0, .2, 1), margin .3s cubic-bezier(.4, 0, .2, 1), opacity .22s ease;}}
div[data-testid="stColumn"]:has(.pl-wrap[data-open="0"]) {{flex-basis: 0 !important; width: 0 !important; margin-right: -1rem; opacity: 0; overflow: hidden; pointer-events: none;}}
html.pl-resizing div[data-testid="stColumn"]:has(.pl-wrap) {{transition: none !important;}}
div[data-testid="stColumn"]:has(.pl-wrap) + div[data-testid="stColumn"] {{flex: 1 1 0 !important; width: auto !important; min-width: 0 !important;}}
.pl-wrap {{position: relative;}}
.pl-split {{position: absolute; top: 0; bottom: 0; right: -14px; width: 12px; cursor: col-resize; z-index: 6; touch-action: none;}}
.pl-split::after {{content: ""; position: absolute; left: 5px; top: 8px; bottom: 8px; width: 2px; border-radius: 2px; background: var(--border); transition: background .12s, width .12s, left .12s;}}
.pl-split:hover::after, .pl-split.on::after {{background: var(--accent); width: 4px; left: 4px;}}
.pl-item[data-pick] {{cursor: pointer;}}
.pl-pick {{display: flex; align-items: center; gap: 10px; padding: 10px 12px; border-radius: 8px; background: #ffffff14; border: 1px solid var(--border); cursor: pointer;
  transition: filter .12s, box-shadow .12s;}}
.pl-pick b {{flex: 1; font-size: 0.92rem;}}
.pl-pick:hover {{filter: brightness(1.25);}}
.pl-pick.pl-selected {{box-shadow: inset 0 0 0 2px var(--accent);}}
.pl-rule {{height: 1px; background: var(--border); margin: 8px -4px;}}
.pl-item.pl-selected {{color: #0b1220;}}
.pl-item.pl-selected .pl-name, .pl-item.pl-selected .pl-count, .pl-item.pl-selected .pl-more {{color: #0b1220; opacity: 1;}}
.tl-title {{margin: 0; padding: 0; font-size: 1.9rem;}}
[class*="st-key-tl_h_"] button {{padding-left: 0; font-weight: 700; opacity: 0.8;}}
[class*="st-key-tl_h_"] button:hover {{opacity: 1;}}
.pl-main:has(.pl-count) {{display: flex; justify-content: space-between; align-items: center; gap: 8px;}}
.pl-count {{opacity: 0.7; font-size: 0.8rem; font-weight: 600;}}
.pl-main > span {{opacity: 0.7; font-size: 0.8rem;}}
.wk-zoom {{position: absolute; right: -1px; top: 0; bottom: 0; width: 10px; cursor: ns-resize; z-index: 4; touch-action: none;}}
.wk-zoom i {{position: absolute; right: 3px; top: 0; bottom: 0; width: 2px; border-radius: 2px; background: var(--border); transition: background .12s, width .12s;}}
.wk-zoom:hover i, .wk-zoom.on i {{background: var(--accent); width: 4px; right: 2px;}}
/* The compact dialogs of a tile on the schedule: a title bar in the color of the course, the date and times in one row, a footer */
.dlg-banner {{border-left: 4px solid var(--c); background: color-mix(in srgb, var(--c) 22%, transparent); color: var(--c); font-weight: 700; font-size: 1.05rem; border-radius: 8px;
  padding: 14px 16px; margin-bottom: 6px;}}
/* Calendar panel: blocks with a menu */
.pl-item {{display: flex; align-items: center; gap: 6px;}}
.pl-main {{flex: 1; min-width: 0;}}
.pl-panel {{padding-left: 26px;}}
.pl-item {{position: relative;}}
.pl-handle {{position: absolute; left: -26px; top: 0; bottom: 0; width: 26px; display: flex; align-items: center; justify-content: center; cursor: grab; color: var(--text);
  opacity: 0; touch-action: none; user-select: none; transition: opacity .12s;}}
.pl-item:hover .pl-handle, .pl-item.pl-moving .pl-handle {{opacity: 0.85;}}
.pl-handle:hover {{opacity: 1 !important;}}
.pl-handle:active {{cursor: grabbing;}}
.pl-handle svg {{position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); display: block;}}
.pl-item.pl-moving {{opacity: 0.6; outline: 2px dashed var(--accent); box-shadow: 0 6px 16px #0007; z-index: 5;}}
.pl-item {{will-change: transform;}}
.pl-more, .pl-show {{border: 0; background: transparent; color: var(--text); cursor: pointer; border-radius: 6px; padding: 0 7px; font-size: 1.2rem; line-height: 1.3; opacity: 0.6;}}
.pl-show {{font-size: 0.75rem; border: 1px solid var(--border); opacity: 0.85;}}
.pl-more:hover, .pl-show:hover {{opacity: 1; background: #ffffff1c;}}
.pl-name[contenteditable="true"] {{outline: 2px solid var(--accent); border-radius: 4px; background: #00000040; padding: 0 4px; cursor: text; text-overflow: clip;}}
.pl-menu {{position: fixed; z-index: 99999; min-width: 190px; background: var(--card); color: var(--text); border: 1px solid var(--border); border-radius: 10px; box-shadow: 0 10px 28px #0009; padding: 4px;}}
.pl-menu button {{display: block; width: 100%; text-align: left; background: transparent; border: 0; color: inherit; padding: 8px 12px; border-radius: 6px; cursor: pointer; font-size: 0.9rem;}}
.pl-menu button {{display: flex; align-items: center; gap: 12px;}}
.pl-menu button svg {{flex: none; opacity: 0.8;}}
.pl-menu button.danger {{color: #f87171;}}
.pl-menu button:hover {{background: #ffffff1c;}}
.pl-fold {{margin-top: 10px; border-top: 1px solid var(--border); padding-top: 6px;}}
.pl-fold summary {{cursor: pointer; font-size: 0.82rem; font-weight: 700; opacity: 0.85; padding: 2px 0;}}
.pl-fold .pl-item {{margin-top: 6px;}}

/* Calendar: week view */
.st-key-edit_schedule_open {{width: 100% !important;}}
.st-key-edit_schedule_open [data-testid="stButton"] {{width: 100%; display: flex; justify-content: flex-end;}}
.st-key-edit_schedule_open button {{min-height: 0; padding: 0.3rem 0.8rem; width: auto !important;}}
.wk {{border: 1px solid var(--border); border-radius: 12px; overflow: hidden; margin: 6px 0 4px;}}
.wk-row {{display: grid; grid-template-columns: 56px repeat(var(--n, 7), 1fr);}}
.wk-top {{border-bottom: 1px solid var(--border);}}
.wk-head {{text-align: center; padding: 8px 0 6px; line-height: 1.2;}}
.wk-head span {{display: block; font-size: 0.85rem; opacity: 0.75;}}
.wk-head b {{font-size: 1.25rem;}}
.wk-head.today b {{background: var(--accent); color: #fff; border-radius: 999px; padding: 1px 9px;}}
.wk-strip {{border-bottom: 1px solid var(--border); min-height: 30px;}}
.wk-allday-label {{font-size: 0.7rem; opacity: 0.6; padding: 6px 4px; text-align: right;}}
.wk-allday {{padding: 3px 2px; border-left: 1px solid var(--border); min-width: 0;}}
.wk-pill {{color: #fff; font-size: 0.72rem; border-radius: 999px; padding: 1px 8px; margin-bottom: 2px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}}
.wk-gutter {{position: relative;}}
.wk-hour {{position: absolute; right: 6px; transform: translateY(-50%); font-size: 0.72rem; opacity: 0.65;}}
.wk-col {{position: relative; border-left: 1px solid var(--border); min-width: 0;
    background-image: repeating-linear-gradient(to bottom, transparent 0, transparent 55px, var(--border) 55px, var(--border) 56px);}}
.wk-col.today {{background-color: rgba(76, 141, 255, 0.07);}}
.wk-col.holiday {{background-image: repeating-linear-gradient(135deg, rgba(128,128,128,0.16) 0, rgba(128,128,128,0.16) 6px, transparent 6px, transparent 14px),
    repeating-linear-gradient(to bottom, transparent 0, transparent 55px, var(--border) 55px, var(--border) 56px);}}
.wk-block {{position: absolute; border-radius: 8px; padding: 4px 7px; color: #fff; overflow: hidden; line-height: 1.25;
    box-shadow: 0 1px 4px #0004; box-sizing: border-box;}}
.wk-time {{font-size: 0.72rem; opacity: 0.92;}}
.wk-code {{font-weight: 700; font-size: 0.9rem;}}
.wk-loc {{font-size: 0.76rem; opacity: 0.92; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}}
.wk-block.wk-exam {{outline: 2px solid #ef4444; outline-offset: -2px; padding-bottom: 22px;}}
.wk-code {{white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}}
.wk-block.wk-exam .wk-code {{font-size: 0.8rem;}}
.wk-block.wk-exam .wk-time {{font-size: 0.68rem;}}
.wk-exam-tag {{position: absolute; left: 0; right: 0; bottom: 0; background: #e0392b; color: #fff; font-size: 0.72rem;
    font-weight: 700; padding: 1px 7px;}}
.wk-now {{position: absolute; left: 0; right: 0; height: 2px; background: #ef4444; z-index: 2;}}
.wk-now::before {{content: ""; position: absolute; left: -4px; top: -3px; width: 8px; height: 8px; border-radius: 50%; background: #ef4444;}}


/* Planner calendar: study sessions, travel time, dragging */
.wk-block.wk-session {{border: 2px dashed; color: var(--text); box-shadow: none;}}
.wk-block.wk-session.wk-manual {{border-style: solid;}}
.wk-session .wk-time, .wk-session .wk-code, .wk-session .wk-loc {{color: var(--text);}}
.wk-dot {{display: inline-block; width: 10px; height: 10px; border-radius: 50%; float: right; margin: 3px 0 0 4px;}}
.wk-block.wk-commute {{border: 1px dashed var(--c); color: var(--text); box-shadow: none; padding: 1px 5px; opacity: 0.85;
    background: repeating-linear-gradient(45deg, color-mix(in srgb, var(--c) 30%, transparent) 0, color-mix(in srgb, var(--c) 30%, transparent) 6px, transparent 6px, transparent 12px);}}
.wk-commute .wk-time {{font-size: 0.68rem; opacity: 0.85; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}}
.wk-block.wk-activity {{border-left: 4px solid #ffffff99;}}
.wk-block.wk-openable {{cursor: pointer;}}
.wk-moved {{position: absolute; right: 4px; top: 3px; font-size: 0.62rem; background: #0007; border-radius: 3px; padding: 0 4px;}}
.wk-block[data-edit] {{cursor: grab; user-select: none; touch-action: none;}}
.wk-block.dragging {{opacity: 0.9; z-index: 6; box-shadow: none; outline: 2px solid #ffffffaa; outline-offset: -2px; cursor: grabbing;}}
.wk-del {{position: absolute; right: 5px; top: 4px; z-index: 3; cursor: pointer; opacity: 0; padding: 2px; border-radius: 6px; line-height: 0; transition: opacity .12s, background .12s;}}
.wk-block:hover .wk-del {{opacity: 0.85;}}
.wk-del:hover {{opacity: 1 !important; background: #ffffff26;}}
.wk-loc {{display: flex; align-items: center; gap: 4px;}}
.wk-pin {{flex: none; opacity: 0.9;}}
.wk-resize-top {{position: absolute; left: 0; right: 0; top: 0; height: 9px; cursor: ns-resize; z-index: 2;}}
.wk-resize-top::after {{content: ""; position: absolute; left: 50%; top: 2px; width: 22px; margin-left: -11px; height: 3px; border-radius: 2px; background: currentColor; opacity: 0.45;}}
.wk-block:hover .wk-resize-top::after, .wk-block:hover .wk-resize::after {{opacity: 0.9;}}
.wk-resize {{position: absolute; left: 0; right: 0; bottom: 0; height: 9px; cursor: ns-resize; z-index: 2;}}
.wk-resize::after {{content: ""; position: absolute; left: 50%; bottom: 2px; width: 22px; margin-left: -11px; height: 3px; border-radius: 2px; background: currentColor; opacity: 0.45;}}
.wk-ghost {{position: absolute; left: 2px; right: 2px; background: rgba(76, 141, 255, 0.28); border: 2px solid var(--accent); border-radius: 6px; z-index: 5; pointer-events: none;}}
.wk-col {{user-select: none;}}
.cu-pill {{display: inline-block; color: #fff; border-radius: 999px; padding: 2px 11px; font-size: 0.8rem; font-weight: 600; white-space: nowrap;}}

/* Calendar */
.cal-head {{text-align: center; font-weight: 600; font-size: 0.85rem; opacity: 0.7; padding-bottom: 4px;}}
.cal-cell {{border: 1px solid var(--border); border-radius: 8px; min-height: 112px; padding: 6px; overflow: hidden;}}
.cal-cell.blank {{border-color: transparent; background: transparent;}}
.cal-cell.today {{border: 2px solid var(--accent);}}
.cal-day {{font-weight: 600; font-size: 0.9rem; margin-bottom: 3px;}}
.cal-chip {{color: #fff; font-size: 0.72rem; border-radius: 4px; padding: 1px 6px; margin-top: 3px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}}
.cal-more {{font-size: 0.72rem; opacity: 0.7; margin-top: 3px;}}

/* 20-20-20 eye rest prompt (built by the script below) */
#sa-rest {{position: fixed; top: 22px; left: 50%; transform: translateX(-50%); z-index: 99995; width: min(440px, 92vw);
    background: var(--card); color: var(--text); border: 1px solid var(--accent); border-radius: 12px;
    padding: 18px 22px; box-shadow: 0 8px 30px #0007; text-align: center;}}
#sa-force {{position: fixed; inset: 0; z-index: 99999; background: rgba(0, 0, 0, 0.72); display: flex; align-items: center; justify-content: center;}}
#sa-force #sa-rest {{position: static; transform: none;}}
#sa-rest.warn {{border-color: #e0a030;}}
#sa-rest button:disabled {{opacity: 0.4; cursor: not-allowed;}}
#sa-rest h3 {{margin: 0 0 6px; font-size: 1.15rem; color: var(--text);}}
#sa-rest p {{margin: 0 0 10px; opacity: 0.85; font-size: 0.95rem;}}
#sa-rest .count {{font-size: 2.6rem; font-weight: 700; line-height: 1.1; color: var(--accent);}}
#sa-rest .bar {{height: 5px; background: var(--border); border-radius: 3px; margin: 10px 0 14px; overflow: hidden;}}
#sa-rest .bar i {{display: block; height: 100%; width: 0; background: var(--accent); transition: width 1s linear;}}
#sa-rest button {{background: var(--input); color: var(--text); border: 1px solid var(--border); border-radius: 8px;
    padding: 6px 18px; cursor: pointer; font-size: 0.9rem;}}
#sa-rest button:hover {{border-color: var(--accent);}}

/* Compact PDF reader */
[class*="st-key-reader_"] {{border-bottom: 1px solid var(--border); padding: 6px 4px 8px; margin-bottom: 8px;}}
[class*="st-key-reader_"] [data-testid="stHorizontalBlock"] {{gap: 0.3rem; align-items: center;}}
[class*="st-key-reader_"] button {{min-height: 2rem; padding: 0 0.5rem; font-size: 0.9rem; border: none; background: transparent; box-shadow: none;}}
[class*="st-key-reader_"] button:hover {{background: var(--hover); color: var(--accent);}}
[class*="st-key-reader_"] [class*="st-key-"][class*="_prev"] button, [class*="st-key-reader_"] [class*="st-key-"][class*="_next"] button {{background: var(--card);}}
[class*="st-key-reader_"] [data-testid="stNumberInput"] input {{text-align: right; padding: 0 0.2rem; min-height: 2rem; font-size: 0.95rem; background: transparent; border: none;}}
[class*="st-key-reader_"] [data-testid="stNumberInput"] [data-baseweb="input"], [class*="st-key-reader_"] [data-testid="stNumberInput"] [data-baseweb="base-input"],
[class*="st-key-reader_"] [data-testid="stNumberInputContainer"] {{background: transparent !important; border: none !important;}}
[class*="st-key-reader_"] [data-testid="stNumberInputStepUp"], [class*="st-key-reader_"] [data-testid="stNumberInputStepDown"] {{display: none;}}
.rd-total, .rd-zoom {{height: 1.9rem; display: flex; align-items: center; justify-content: center; margin: 0; padding: 0; line-height: 1;
    white-space: nowrap; font-size: 0.9rem;}}
.rd-total {{justify-content: flex-start; font-size: 0.95rem;}}
.rd-zoom {{font-size: 0.9rem; background: var(--card); border-radius: 8px;}}
[class*="st-key-reader_"] [data-testid="stColumn"] {{display: flex; flex-direction: column; justify-content: center;}}
[class*="st-key-reader_"] [data-testid="stElementContainer"], [class*="st-key-reader_"] [data-testid="stMarkdownContainer"],
[class*="st-key-reader_"] [data-testid="stNumberInput"] {{margin: 0 !important; padding: 0;}}
[class*="st-key-reader_"] [data-testid="stNumberInput"] [data-baseweb="input"] {{height: 1.9rem; align-items: center;}}
.rd-scroll {{overflow: auto; background: #3a3d45; border-radius: 8px; padding: 12px; text-align: center;}}
.rd-scroll img {{display: block; margin: 0 auto; max-width: none; box-shadow: 0 2px 10px #0008; background: #fff;}}
.rd-spread {{display: flex; justify-content: safe center; align-items: flex-start; gap: 6px;}}      /* safe: a zoomed page that is wider than the window starts at the left edge, so all of it can be reached */
.rd-spread img {{margin: 0;}}

/* Note Reader: the tabs share a row with Rename and Export (the toolbar ignores clicks except on its buttons) */
.st-key-lab_toolbar [data-testid="stColumn"]:first-child {{min-width: 0;}}
.st-key-lab_toolbar .lab-heading {{margin: 0;}}
.lab-heading {{white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}}
[class*="st-key-lab_pane_"] [data-testid="stHorizontalBlock"] button {{display: flex; align-items: center; justify-content: center;
    padding-top: 0; padding-bottom: 0; text-align: center;}}
[class*="st-key-lab_pane_"] [data-testid="stHorizontalBlock"] button > div {{display: flex; align-items: center; justify-content: center; width: 100%;}}
[class*="st-key-lab_pane_"] [data-testid="stHorizontalBlock"] button p {{margin: 0 !important; padding: 0 !important; line-height: 1.2 !important;}}
[class*="st-key-lab_pane_"] [data-testid="stHorizontalBlock"] button [data-testid="stMarkdownContainer"] {{display: flex; align-items: center;
    justify-content: center; height: auto !important; min-height: 0 !important; margin: 0 !important; padding: 0 !important; line-height: 1.2 !important;}}
.st-key-lab_toolbar button {{min-height: 1.9rem !important; padding: 0.1rem 0.5rem !important; font-size: 0.8rem !important;}}
.st-key-lab_toolbar button p {{font-size: 0.8rem !important;}}
[class*="st-key-lab_refname_"] [data-testid="stPopover"] button {{border: none !important; background: transparent !important; justify-content: flex-start;
    padding: 0.2rem 0.4rem; min-height: 0; width: 100%;}}
[class*="st-key-lab_refname_"] [data-testid="stPopover"] button p {{font-size: 1.45rem; font-weight: 700; line-height: 1.25; letter-spacing: 0;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; text-align: left; max-width: 100%;}}
[class*="st-key-lab_refname_"] [data-testid="stPopover"] button:hover p {{color: var(--accent);}}
[data-testid="stPopoverBody"]:has([data-testid="stSelectbox"]) {{min-width: min(560px, 92vw);}}
.st-key-lab_tab_sink {{position: absolute !important; width: 1px; height: 1px; overflow: hidden; opacity: 0; pointer-events: none;}}
.lab-tabs {{display: grid; gap: 1rem; padding: 4px 0 0; background: var(--bg2); border-radius: 10px 10px 0 0; position: relative;}}
.lab-tab {{display: flex; align-items: center; gap: 9px; padding: 8px 14px; border-radius: 9px 9px 0 0; background: var(--card);
    color: var(--text); font-size: 0.9rem; cursor: grab; user-select: none; min-width: 0;}}
[data-testid="stElementContainer"]:has(.lab-tabs) {{min-height: 46px;}}
.lab-tab span {{overflow: hidden; text-overflow: ellipsis; white-space: nowrap;}}
.lab-tab svg {{flex: none; opacity: 0.8;}}
.lab-tab:hover {{background: var(--hover);}}
.lab-x {{margin-left: auto; padding: 0 6px; border-radius: 5px; font-size: 1.05rem; line-height: 1.2; opacity: 0.6; cursor: pointer;}}
.lab-x:hover {{background: var(--input); opacity: 1;}}
.lab-add {{position: absolute; right: -2.4rem; top: 8px; width: 30px; height: 30px; display: flex; align-items: center; justify-content: center;
    border-radius: 8px; font-size: 1.3rem; cursor: pointer;}}
.lab-add:hover {{background: var(--hover);}}
/* the popover button of the notes window looks like the other buttons */
[class*="st-key-lab_pane_"] [data-testid="stPopover"] button {{border: 1px solid var(--border) !important; background: var(--card) !important;
    padding: 0.25rem 0.75rem; min-height: 2.5rem; justify-content: center;}}
[class*="st-key-lab_pane_"] [data-testid="stPopover"] button p {{font-size: 0.95rem; font-weight: 400; letter-spacing: 0; line-height: 1.4;}}
/* the Restore Database popover in Settings looks like the other buttons of its row */
.st-key-backup_db_pop [data-testid="stPopover"] button {{border: 1px solid var(--border) !important; background: var(--bg) !important;
    padding: 0.25rem 0.75rem; min-height: 2.5rem; justify-content: center;}}
.st-key-backup_db_pop [data-testid="stPopover"] button p {{font-size: 0.875rem; font-weight: 400; letter-spacing: 0; line-height: 1.4;}}
/* The Remove buttons of the class times and the holidays (a popover with a word, not the three dots): normal text */
[class*="st-key-meeting_pop_"] [data-testid="stPopover"] button p, [class*="st-key-hol_pop_"] [data-testid="stPopover"] button p {{font-size: 0.9rem; font-weight: 400; letter-spacing: 0; line-height: 1.4;}}
[class*="st-key-meeting_pop_"] [data-testid="stPopover"] button > div, [class*="st-key-hol_pop_"] [data-testid="stPopover"] button > div {{gap: 6px !important; align-items: center;}}
[class*="st-key-meeting_pop_"], [class*="st-key-hol_pop_"] {{display: flex !important; justify-content: flex-end !important; width: 100% !important;}}
[class*="st-key-meeting_pop_"] [data-testid="stPopover"], [class*="st-key-hol_pop_"] [data-testid="stPopover"] {{width: auto !important;}}
/* Clear Auto-Plan (a popover with a word): normal text, at the right of the Show Free Time row */
.st-key-clear_plan_pop {{display: flex !important; justify-content: flex-end !important; width: 100% !important;}}
.st-key-clear_plan_pop [data-testid="stPopover"] {{width: auto !important;}}
.st-key-clear_plan_pop [data-testid="stPopover"] button p {{font-size: 0.9rem; font-weight: 400; letter-spacing: 0; line-height: 1.4;}}
.st-key-clear_plan_pop [data-testid="stPopover"] button > div {{gap: 6px !important; align-items: center;}}
.lab-tab.dragging {{opacity: 0.45;}}
.lab-tab.drop-target {{box-shadow: inset 0 -3px 0 var(--accent);}}
[class*="st-key-lab_pane_"] {{flex: none; height: calc(100vh - 62px); overflow-y: auto; overflow-x: hidden; padding: 0 12px; background: var(--bg);}}
[data-testid="stHorizontalBlock"]:has([class*="st-key-lab_pane_"]) > div:not(:last-child) {{border-right: 1px solid var(--border);}}
/* draggable dividers between the windows: a double arrow shows when the mouse is over the border */
[data-testid="stHorizontalBlock"]:has([class*="st-key-lab_pane_"]) > [data-testid="stColumn"] {{position: relative;}}
[data-testid="stHorizontalBlock"]:has([class*="st-key-lab_pane_"]) > [data-testid="stColumn"]:not(:last-child)::after {{
    content: ""; position: absolute; top: 0; bottom: 0; right: -17px; width: 21px; cursor: col-resize; z-index: 6;}}
[data-testid="stHorizontalBlock"]:has([class*="st-key-lab_pane_"]) > [data-testid="stColumn"]:not(:last-child):hover::after {{
    background: linear-gradient(to right, transparent 8px, var(--accent) 8px, var(--accent) 10px, transparent 10px); opacity: 0.55;}}
.lab-resizing, .lab-resizing * {{cursor: col-resize !important; user-select: none !important;}}
.lab-resizing iframe {{pointer-events: none !important;}}
.lab-detached-title {{font-weight: 600; padding: 8px 4px; opacity: 0.9;}}
.lab-heading {{font-size: 1.45rem; margin: 6px 0 6px; padding: 0;}}
[class*="st-key-lab_html_"], [class*="st-key-lab_html_"] [data-testid="stElementContainer"], [class*="st-key-lab_html_"] iframe {{
    height: calc(100vh - 145px) !important; width: 100% !important; min-height: 300px; flex: none !important;}}
[class*="st-key-lab_view_scroll"] h1 {{font-size: 1.6rem;}}
[class*="st-key-lab_view_scroll"] h2 {{font-size: 1.3rem;}}
[class*="st-key-lab_view_scroll"] h3 {{font-size: 1.1rem;}}
[class*="st-key-lab_view_scroll"] {{height: calc(100vh - 252px); overflow-y: auto;}}
[class*="st-key-lab_view_scroll"] [data-testid="stElementContainer"], [class*="st-key-lab_view_scroll"] iframe {{height: calc(100vh - 262px) !important;}}
.st-key-lab_chat_box {{height: calc(100vh - 360px); overflow-y: auto;}}
[class*="st-key-lab_pane_"] textarea {{height: calc(100vh - 330px) !important; min-height: 280px;}}
.rd-cont {{position: relative; scroll-behavior: auto;}}
.rd-pg {{margin: 0 auto 14px; background: #fff; box-shadow: 0 2px 10px #0008; overflow: hidden;}}
.rd-pg img {{display: block; width: 100%; height: 100%; object-fit: contain; margin: 0; box-shadow: none; max-width: 100%;}}
.rd-row {{display: flex; justify-content: safe center; align-items: flex-start; gap: 6px; margin-bottom: 14px;}}
.rd-row .rd-pg {{margin: 0; flex: none;}}
.rd-pagewrap {{position: relative; line-height: 0; flex: none;}}                                   /* flex none: the page keeps the zoomed width instead of shrinking to the window */
.rd-pg {{position: relative;}}
.rd-err {{position: absolute; border: 2px solid #e5484d; background: rgba(229, 72, 77, 0.14); border-radius: 4px; z-index: 2; cursor: help;}}
.rd-err.rd-sent {{border-color: #d9a21b; background: rgba(217, 162, 27, 0.2);}}
/* drawing on a homework or exam PDF: a layer over each page, a small toolbar at the top left of the reader */
.an-layer {{position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; z-index: 4; overflow: visible;}}
.an-on .an-layer {{pointer-events: auto; cursor: crosshair; touch-action: pan-x pan-y pinch-zoom;}}
.an-layer path {{fill: none; stroke-linecap: round; stroke-linejoin: round; vector-effect: non-scaling-stroke;}}
.an-layer path.hl {{mix-blend-mode: multiply; opacity: 0.45; stroke-linecap: butt;}}
.an-layer g.hl {{mix-blend-mode: multiply; opacity: 0.45;}}
.an-barwrap {{position: sticky; top: 0; height: 0; z-index: 9; overflow: visible;}}
.an-bar {{position: absolute; left: 10px; top: 8px; display: flex; gap: 3px; align-items: center; padding: 3px 5px; border-radius: 10px;
    background: rgba(24, 26, 32, 0.92); border: 1px solid var(--border); box-shadow: 0 4px 14px #0006; color: #e8e9ec; font-size: 0.8rem; user-select: none;}}
.an-bar button {{background: transparent; border: 1px solid transparent; color: inherit; border-radius: 7px; padding: 3px 7px; cursor: pointer; font-size: 0.8rem; line-height: 1.2;
    display: inline-flex; align-items: center; gap: 4px; min-height: 0 !important;}}
.an-bar button:hover {{background: #ffffff1c;}}
.an-bar button.act {{border-color: var(--accent); background: #4c8dff33;}}
.an-bar .sw {{width: 15px; height: 15px; border-radius: 50%; padding: 0; border: 2px solid #ffffff55;}}
.an-bar .sw.act {{border-color: #fff; box-shadow: 0 0 0 1px #000a;}}
.an-bar .sep {{width: 1px; height: 18px; background: #ffffff33; margin: 0 3px;}}
.an-bar svg {{width: 15px; height: 15px; fill: none; stroke: currentColor; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round;}}
.st-key-annot_sink {{position: absolute !important; width: 1px; height: 1px; overflow: hidden; opacity: 0; pointer-events: none;}}
.rd-find {{position: absolute; background: rgba(255, 213, 0, 0.42); border-radius: 2px; z-index: 2; pointer-events: none;}}
.rd-find.active {{background: rgba(255, 140, 0, 0.55); outline: 2px solid #ff8c00; z-index: 4;}}
.rd-err.active {{border-width: 3px; box-shadow: 0 0 0 4px rgba(229, 72, 77, 0.35); animation: rd-pulse 1.2s ease-in-out 3; z-index: 4;}}
.rd-err.rd-sent.active {{box-shadow: 0 0 0 4px rgba(217, 162, 27, 0.4);}}
@keyframes rd-pulse {{50% {{box-shadow: 0 0 0 9px rgba(229, 72, 77, 0.12);}}}}
.rd-err b {{position: absolute; left: -2px; top: -11px; min-width: 20px; height: 20px; padding: 0 5px; border-radius: 10px; background: #e5484d; color: #fff;
    font: 700 12px/20px system-ui, sans-serif; text-align: center;}}
.rd-err::after {{content: attr(data-tip); position: absolute; left: 0; top: 100%; margin-top: 4px; white-space: nowrap; background: #1b1c20; color: #fff;
    font: 12px/1.3 system-ui, sans-serif; padding: 4px 8px; border-radius: 6px; display: none; z-index: 5;}}
.rd-err:hover::after {{display: block;}}
.rd-live {{position: sticky; top: 0; z-index: 3; width: fit-content; margin: 0 0 -26px auto; font-size: 0.8rem; padding: 3px 10px;
    border-radius: 999px; background: rgba(20, 22, 28, 0.85); color: #e8e9ec; pointer-events: none;}}
.rd-scroll.rd-fill {{height: calc(100vh - 175px);}}
.lab-heading {{font-size: 1.5rem; margin: 0 0 4px; padding: 0;}}

/* Library */
/* Library grid: one HTML block, cards are clickable through data-lib-act */
.st-key-lib_inner_box {{width: 150px; max-width: 100%; margin-left: auto;}}
/* Courses > All > Tree: a map of circles. Every bubble sits at --x/--y; a folded one slides into its parent (--px/--py), shrinks and fades. No fill for the bubbles of topics and courses. */
.mm-wrap {{position: relative; margin: 0.4rem 0 0.5rem; overflow: hidden; border: 0; padding: 4px 0 0;}}
.tk-top {{display: flex; align-items: center; gap: 10px; margin-bottom: 8px;}}
.tk-note {{font-size: 0.85rem; opacity: 0.7; flex: 1 1 0; min-width: 0;}}                     /* the hint wraps; the buttons never do */
.tk-top button, .tk-zoom button {{white-space: nowrap; flex: 0 0 auto;}}
.tk-btn {{cursor: pointer; border: 1px solid var(--border); color: var(--text); border-radius: 8px; padding: 5px 16px; font-size: 0.85rem; user-select: none; background: var(--input); transition: border-color .15s, color .15s;}}
.tk-btn:hover {{border-color: var(--accent); color: var(--accent);}}
svg.mm {{width: 100%; height: calc(100vh - 330px); min-height: 520px; display: block; user-select: none;}}   /* the whole map fits the window; wheel and + / - zoom it */
.mm-node {{transform: translate(var(--x), var(--y)); transition: transform .55s cubic-bezier(.4, 0, .2, 1), opacity .4s ease; cursor: pointer;}}
.mm-node.mm-hidden {{transform: translate(var(--px), var(--py)) scale(0); opacity: 0; pointer-events: none;}}
.mm-line {{stroke: #3b8fd4; stroke-width: 5; stroke-linecap: round; opacity: 0.85;}}
.mm-l0 .mm-line {{display: none;}}
.mm-l3 .mm-line, .mm-l4 .mm-line {{stroke-width: 3;}}
.mm-node circle {{transition: filter .2s, fill .2s;}}
.mm-node:hover circle {{filter: brightness(1.18) drop-shadow(0 6px 10px #0008);}}
.mm-l0 circle {{fill: #0b9be3; stroke: #8fd3ff; stroke-width: 4;}}
.mm-l1 circle {{fill: hsl(var(--h), 100%, 32%); stroke: hsl(var(--h), 90%, 60%); stroke-width: 3;}}
.mm-l2 circle {{fill: hsl(var(--h), 80%, 40%); stroke: hsl(var(--h), 85%, 68%); stroke-width: 3;}}
.mm-l3 circle {{fill: var(--bg, #0e1117); stroke: hsl(var(--h), 80%, 62%); stroke-width: 4;}}
.mm-l4 circle {{fill: var(--bg, #0e1117); stroke: var(--c); stroke-width: 5;}}
.mm-l4.mm-photo circle {{fill: transparent;}}
.mm-l4.mm-photo text {{paint-order: stroke; stroke: #0e1117cc; stroke-width: 3.5px; stroke-linejoin: round;}}
.mm-l4.sel circle {{fill: color-mix(in srgb, var(--c) 30%, var(--bg, #0e1117)); stroke-width: 6;}}
.mm-l4.sel.mm-photo circle {{fill: color-mix(in srgb, var(--c) 18%, transparent);}}
.mm-l4.mm-study circle {{stroke-dasharray: 9 5;}}
.mm-label, .mm-l0 text, .mm-l1 text, .mm-l2 text {{fill: #fff; font-weight: 700; pointer-events: none;}}
.mm-l3 text, .mm-l4 text {{fill: var(--text); font-weight: 700; pointer-events: none;}}
.mm-count {{font-size: 13px !important; font-weight: 600 !important; opacity: 0.75;}}
.mm-plus {{font-size: 26px !important; opacity: 0; transition: opacity .3s;}}
.mm-collapsed .mm-plus {{opacity: 0.9;}}
.mm-code {{font-size: 15px; font-weight: 800;}}
.mm-sub {{font-size: 11px; font-weight: 500; opacity: 0.85;}}
.tk-zoom {{margin-left: auto; display: inline-flex; gap: 4px; margin-right: 8px;}}
.tk-zoom button {{min-width: 34px; background: var(--input); border: 1px solid var(--border); color: var(--text); border-radius: 8px; padding: 4px 10px; cursor: pointer; font-size: 0.95rem; line-height: 1.2;}}
.tk-zoom button:hover {{border-color: var(--accent); color: var(--accent);}}
svg.mm {{cursor: grab; touch-action: none;}}
/* Dragging a bubble: it follows the pointer at once (no slide), lifts with a shadow while it is held, and settles back with a small bounce when it is dropped. */
.mm-node.mm-moving, svg.mm.mm-holding .mm-node {{transition: opacity .4s ease !important;}}               /* every bubble follows at once while one is held, so no line is left behind its circle */
.mm-node:not([data-parent=""]) {{cursor: grab;}}
svg.mm.mm-holding, svg.mm.mm-holding .mm-node {{cursor: grabbing;}}
.mm-node > circle, .mm-node > text, .mm-node > image {{transition: transform .2s cubic-bezier(.3, 1.4, .5, 1), filter .2s;}}
.mm-node.mm-dragging > circle, .mm-node.mm-dragging > text, .mm-node.mm-dragging > image {{transform: scale(1.14);}}
.mm-node.mm-dragging > circle {{filter: drop-shadow(0 14px 14px #000b) brightness(1.18);}}
.mm-node.mm-settle > circle, .mm-node.mm-settle > text, .mm-node.mm-settle > image {{animation: mm-settle .4s cubic-bezier(.3, 1.5, .5, 1);}}
@keyframes mm-settle {{0% {{transform: scale(1.14);}} 45% {{transform: scale(0.93);}} 100% {{transform: scale(1);}}}}
html.lite .mm-node.mm-dragging > circle {{filter: none; stroke-width: 4px;}}
svg.mm.panning {{cursor: grabbing;}}
/* Library, by course: the tiles of the Courses page */
.lib-ctiles {{display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 1rem; margin: 0.5rem 0 1.2rem;}}
.lib-ctile {{position: relative; cursor: pointer; transition: transform .12s ease, filter .12s;}}
.lib-ctile:hover {{transform: translateY(-2px); filter: brightness(1.1);}}
.lib-ctcount {{position: absolute; right: 14px; bottom: 14px; font-size: 0.8rem; font-weight: 700; color: #fff; text-shadow: 0 1px 3px #0009; background: #00000040; border-radius: 999px; padding: 1px 10px;}}
@media (max-width: 1100px) {{.lib-ctiles {{grid-template-columns: repeat(3, minmax(0, 1fr));}}}}
/* Library views: Tiles (a small cover with the details beside it) and Details (a table) */
.lib-tilegrid {{display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0.8rem; margin-bottom: 1rem;}}
.lib-tilecard {{display: flex; gap: 12px; align-items: flex-start; border: 1px solid var(--border); border-radius: 10px; padding: 10px; background: var(--card); cursor: pointer; min-width: 0;
  transition: filter .12s, transform .12s;}}
.lib-tilecard:hover {{filter: brightness(1.12);}}
.lib-thumb {{flex: none; width: 64px;}}
.lib-thumb .book-cover {{width: 100%;}}
.lib-tilemeta {{flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px; font-size: 0.82rem;}}
.lib-tilemeta strong {{font-size: 0.95rem; line-height: 1.25;}}
.lib-dim {{opacity: 0.6;}}
.lib-chips {{display: flex; flex-wrap: wrap; gap: 4px;}}
.lib-chip {{border: 1px solid; border-radius: 999px; padding: 0 8px; font-size: 0.75rem; white-space: nowrap;}}
.lib-tileadd {{align-items: stretch; justify-content: center; min-height: 100px;}}
.lib-tileadd .lib-add {{aspect-ratio: auto; width: 100%; min-height: 80px;}}
.lib-table {{display: flex; flex-direction: column; margin-bottom: 1rem; border: 1px solid var(--border); border-radius: 10px; overflow: hidden;}}
.lib-row {{display: grid; grid-template-columns: 3.4fr 1.3fr 1.7fr 0.8fr 1fr 1.1fr 1.4fr 40px; gap: 10px; align-items: center; padding: 7px 12px; border-top: 1px solid var(--border); cursor: pointer;
  font-size: 0.85rem;}}
.lib-row:first-child {{border-top: 0;}}
.lib-row:hover {{background: #ffffff10;}}
.lib-head {{cursor: default; font-weight: 700; opacity: 0.75; background: #ffffff08;}}
.lib-head:hover {{background: #ffffff08;}}
.lib-cell {{overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0;}}
.lib-cell.lib-chips {{overflow: hidden; flex-wrap: nowrap;}}
.lib-name {{font-weight: 600;}}
.lib-row .lib-menu {{white-space: nowrap; letter-spacing: 0; padding: 0; text-align: center; justify-self: end; font-size: 1.3rem; line-height: 1;}}
.lib-row-add {{display: block; cursor: default;}}
.lib-row-add .lib-add {{display: inline-block; aspect-ratio: auto; border: 0; padding: 2px 4px; font-size: 0.9rem; cursor: pointer; opacity: 0.8;}}
@media (max-width: 1100px) {{.lib-tilegrid {{grid-template-columns: repeat(2, minmax(0, 1fr));}}}}
/* Library, Date Added: a chain of bullets on a vertical line */
.tl-actions {{display: flex; gap: 8px; margin: 2px 0 14px 38px;}}
.tl-actions button {{background: transparent; border: 1px solid var(--border); color: var(--text); border-radius: 8px; padding: 5px 14px; cursor: pointer; font-size: 0.85rem;}}
.tl-actions button:hover {{border-color: var(--accent); color: var(--accent);}}
.tl-group {{position: relative; padding-left: 38px; margin-bottom: -1rem; padding-bottom: 2.3rem;}}
.tl-group::before {{content: ""; position: absolute; left: 8px; top: 18px; bottom: -1rem; width: 2px; background: var(--border);}}
.tl-group.tl-last::before {{bottom: 2.3rem;}}
summary.tl-head {{display: flex; align-items: center; gap: 10px; min-height: 34px; margin-bottom: 1.1rem; font-size: 1.05rem; cursor: pointer; list-style: none; user-select: none;}}
summary.tl-head::-webkit-details-marker {{display: none;}}
.tl-chev {{margin-left: 4px; opacity: 0.6; transition: transform .15s;}}
details[open] > summary .tl-chev {{transform: rotate(90deg);}}
details.tl-group:not([open]) {{padding-bottom: 2.3rem;}}
details.tl-group:not([open]) > summary {{margin-bottom: 0;}}
summary.tl-head:hover b {{color: var(--accent);}}
.tl-dot {{position: absolute; left: 0; top: 8px; width: 18px; height: 18px; border-radius: 50%; background: var(--bg, #0e1117); border: 3px solid var(--accent); box-sizing: border-box;}}
.tl-count {{opacity: 0.6; font-size: 0.8rem; border: 1px solid var(--border); border-radius: 999px; padding: 0 8px;}}
/* Library: the Import menu is a button like the others (the sort box next to it is 40 px high; icon and text sit in the middle) */
.st-key-lib_import_box [data-testid="stPopover"] button {{min-height: 40px !important; height: 40px; padding: 0 16px !important; border: 1px solid var(--border) !important; border-radius: 8px !important;
  background: var(--input) !important; width: 100%; display: flex !important; align-items: center !important; justify-content: center !important;}}
.st-key-lib_import_box [data-testid="stPopover"] button:hover {{border-color: var(--accent) !important;}}
/* Courses > Outline: the Auto Build popover looks like the button next to it (Edit Outline): same size, same text */
.st-key-outline_auto_box [data-testid="stPopover"] button {{min-height: 40px !important; height: 40px; padding: 0 16px !important; border: 1px solid var(--border) !important; border-radius: 8px !important;
  background: var(--bg) !important; width: 100%; display: flex !important; align-items: center !important; justify-content: center !important;}}
.st-key-outline_auto_box [data-testid="stPopover"] button:hover {{border-color: var(--accent) !important;}}
.st-key-outline_auto_box [data-testid="stPopover"] button > div {{display: flex !important; align-items: center !important; justify-content: center !important; gap: 8px !important; width: auto !important;}}
.st-key-outline_auto_box [data-testid="stPopover"] button p {{font-size: 0.9rem !important; font-weight: 400 !important; line-height: 1 !important; letter-spacing: 0 !important; margin: 0 !important;}}
.st-key-outline_auto_box [data-testid="stPopover"] button [data-testid="stIconMaterial"] {{font-size: 1.2rem !important; color: var(--text) !important;}}
/* The Import menu closes behind the window it opened (a popover cannot be closed from the program) */
body:has([data-testid="stDialog"]) [data-testid="stPopoverBody"]:has([class*="st-key-imp_menu_"]) {{display: none !important;}}
/* the items of the Import menu: icons in one column, texts starting at the same place */
[class*="st-key-imp_menu_"] button {{justify-content: flex-start !important; padding-left: 18px !important;}}
[class*="st-key-imp_menu_"] button > div {{justify-content: flex-start !important; width: 100% !important;}}
[class*="st-key-imp_menu_"] button p {{text-align: left !important;}}
/* the items of the ⋯ menu of a task: icons in one column, texts starting at the same place */
[class*="st-key-tl_edit_"] button, [class*="st-key-tl_start_"] button, [class*="st-key-tl_log_"] button, [class*="st-key-tl_unplan_"] button, [class*="st-key-tl_del_"] button {{justify-content: flex-start !important; padding-left: 18px !important;}}
[class*="st-key-tl_edit_"] button > div, [class*="st-key-tl_start_"] button > div, [class*="st-key-tl_log_"] button > div, [class*="st-key-tl_unplan_"] button > div, [class*="st-key-tl_del_"] button > div {{justify-content: flex-start !important; width: 100% !important;}}
[class*="st-key-tl_edit_"] button p, [class*="st-key-tl_start_"] button p, [class*="st-key-tl_log_"] button p, [class*="st-key-tl_unplan_"] button p, [class*="st-key-tl_del_"] button p {{text-align: left !important;}}
.st-key-lib_import_box [data-testid="stPopover"] button > div {{display: flex !important; align-items: center !important; justify-content: center !important; gap: 8px !important; width: auto !important;}}
.st-key-lib_import_box [data-testid="stPopover"] button p {{font-size: 0.9rem !important; font-weight: 400 !important; line-height: 1 !important; letter-spacing: 0 !important; margin: 0 !important;}}
.st-key-lib_import_box [data-testid="stPopover"] button [data-testid="stIconMaterial"] {{font-size: 1.2rem !important; color: var(--text) !important;}}
.lib-tiles {{display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 1rem; margin: 0.5rem 0 1.2rem;}}
.lib-tile {{cursor: pointer; border: 1px solid var(--border); border-left: 5px solid var(--accent); border-radius: 12px; padding: 22px 20px; background: var(--card);
  display: flex; flex-direction: column; gap: 6px; transition: transform .12s ease, box-shadow .12s ease, filter .12s;}}
.lib-tile:hover {{transform: translateY(-2px); box-shadow: 0 8px 20px #0006; filter: brightness(1.12);}}
.lib-tile b {{font-size: 1.15rem;}}
.lib-tile span {{opacity: 0.7; font-size: 0.85rem;}}
@media (max-width: 1100px) {{.lib-tiles {{grid-template-columns: repeat(2, minmax(0, 1fr));}}}}
.lib-grid {{display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 1.2rem 1rem; align-items: start; margin-bottom: 1rem;}}
.lib-cover {{cursor: pointer;}}
.lib-cover:hover .book-cover {{filter: brightness(1.08);}}
.lib-name-row {{display: flex; justify-content: space-between; align-items: flex-start; gap: 4px; margin: 2px 0 6px; line-height: 1.35;}}
.lib-menu {{cursor: pointer; font-size: 1.5rem; font-weight: 700; line-height: 0.8; letter-spacing: 1px; padding: 0 4px; user-select: none;}}
.lib-menu:hover {{color: var(--accent);}}
.lib-author {{font-size: 0.875rem; opacity: 0.6;}}
.lib-add {{aspect-ratio: 2 / 3; border: 2px dashed rgba(140, 146, 160, 0.6); border-radius: 6px; display: flex;
    align-items: center; justify-content: center; font-size: 2.2rem; cursor: pointer;}}
.lib-add:hover, .lib-add.drop {{border-color: var(--accent);}}
.lib-add.drop {{background: rgba(76, 141, 255, 0.12);}}
@media (max-width: 1100px) {{.lib-grid {{grid-template-columns: repeat(4, minmax(0, 1fr));}}}}
.lib-title {{font-family: Georgia, "Roboto Slab", serif; font-weight: 700;}}
.book-cover {{aspect-ratio: 2 / 3; border-radius: 6px; display: flex; align-items: flex-end; padding: 14px;
    box-shadow: 0 2px 8px #0005; margin-bottom: 0.6rem; color: #fff;}}
.book-cover span {{font-family: Georgia, serif; font-weight: 700; font-size: 1.15rem; line-height: 1.2;}}
.book-badges {{display: flex; flex-wrap: wrap; gap: 6px; margin: 2px 0 6px;}}
.book-badge {{display: inline-block; border: 1px solid var(--accent); color: var(--accent); border-radius: 999px;
    padding: 1px 11px; font-size: 0.8rem; white-space: nowrap;}}
.stApp [class*="st-key-add_book_tile"] button[data-testid^="stBaseButton"] {{aspect-ratio: 2 / 3; height: auto !important; min-height: 0; width: 100%;
    border-style: dashed !important; border-width: 2px !important; border-color: rgba(140, 146, 160, 0.6) !important; border-radius: 6px; background: transparent !important;}}
[class*="st-key-add_book_tile"] button:hover {{border-color: var(--accent) !important;}}
[class*="st-key-add_book_tile"] button span[data-testid="stIconMaterial"] {{font-size: 2.2rem; color: var(--text);}}
[class*="st-key-add_book_tile"] button p {{display: none;}}

/* Appearance cards */
.st-key-appearance button {{height: 130px; border-radius: 12px; border: 1px solid var(--border); background: transparent;}}
.st-key-appearance button > div > span {{flex-direction: column; gap: 10px;}}
.st-key-appearance button[data-testid="stBaseButton-primary"] {{background: var(--active); border-color: var(--accent);}}
.st-key-appearance button span[data-testid="stIconMaterial"] {{font-size: 2rem; color: var(--text) !important;}}
.st-key-appearance button[data-testid="stBaseButton-primary"] span[data-testid="stIconMaterial"] {{color: var(--active-text) !important;}}
</style>
"""
NAV_ICON_CSS = "".join(icons.css_for_nav(f"nav_{label}", icon) for label, (icon, _) in NAV_TOP.items()
                       if icons.is_custom(icon))
COURSE_ICON_CSS = NAV_ICON_CSS + "".join(icons.css_for_course(c["id"], c["icon"]) for c in crud.list_courses(section=None) if icons.is_custom(c["icon"]))
st.markdown(CSS + f"<style>{COURSE_ICON_CSS}</style>", unsafe_allow_html=True)
# The menu bar is hidden (key m, or Settings): only a thin edge is left, and pointing at it shows the menu above the page. The same element is always drawn
# (empty when the menu is shown), so the page scripts below are not rebuilt when it changes.
HIDDEN_MENU_CSS = f"""<style>
section[data-testid="stSidebar"], section[data-testid="stSidebar"] > div:first-child:not(:hover) {{
    width: 8px !important; min-width: 8px !important; max-width: 8px !important;}}
section[data-testid="stSidebar"] > div:first-child:not(:hover) {{background: transparent !important; border-right: none !important; box-shadow: none !important;}}
section[data-testid="stSidebar"] > div:first-child:not(:hover) button {{opacity: 0; pointer-events: none;}}
</style>"""
st.markdown(HIDDEN_MENU_CSS if settings.get_menu_hidden() else "<style></style>", unsafe_allow_html=True)

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
// Mouse "back" and "forward" buttons (and the browser's back) move through the pages visited inside the app.
if (!window.parent.__navBackHooked) {
  window.parent.__navBackHooked = true;
  // Mouse presses wait until the app has been idle for a moment before clicking the hidden button. Streamlit can lose
  // a request that lands while it is finishing a page change and then stays "running" until the page is reloaded.
  let pending = false;
  const press = sel => {
    if (pending) return;                       // a press is already waiting
    pending = true;
    const t0 = Date.now(); let idleSince = null;
    const tick = () => {
      const now = Date.now();
      if (doc.querySelector('[data-testid="stStatusWidget"]')) idleSince = null;
      else if (idleSince === null) idleSince = now;
      if (idleSince !== null && now - idleSince >= 450) {
        pending = false;
        const b = doc.querySelector(sel); if (b) b.click();
      } else if (now - t0 < 5000) setTimeout(tick, 100);
      else pending = false;
    };
    tick();
  };
  const goBack = () => press('.st-key-nav_back_hidden button');
  const goForward = () => press('.st-key-nav_forward_hidden button');
  doc.addEventListener('mouseup', e => {
    if (e.button === 3) { e.preventDefault(); e.stopPropagation(); goBack(); }
    else if (e.button === 4) { e.preventDefault(); e.stopPropagation(); goForward(); }
  }, true);
  doc.addEventListener('mousedown', e => { if (e.button === 3 || e.button === 4) e.preventDefault(); }, true);
  window.parent.history.pushState({app: true}, '', window.parent.location.href);
  window.parent.addEventListener('popstate', () => {
    window.parent.history.pushState({app: true}, '', window.parent.location.href);  // stay inside the app
    goBack();
  });
}
</script>""", height=0)

components.html("""
<script>
const win = window.parent, doc = win.document;
// Speed: on a slow device the animations, shadows and blur are turned off ("lite"). Settings can force it (light) or forbid it (full); automatic decides from the hardware and from how fast the screen
// draws (the result is remembered, so the next start is light from the first moment).
(() => {
  const mode = __PERF__, root = doc.documentElement;
  let remembered = null; try { remembered = win.localStorage.getItem('sa_lite'); } catch (e) {}
  const weak = (win.navigator.hardwareConcurrency || 8) <= 4 || (win.navigator.deviceMemory || 8) <= 4 || win.matchMedia('(prefers-reduced-motion: reduce)').matches || remembered === '1';
  const apply = lite => root.classList.toggle('lite', lite);
  apply(mode === 'light' || (mode === 'auto' && weak));
  if (mode !== 'auto' || win.__perfProbe) return;
  win.__perfProbe = true;
  win.setTimeout(() => {                                             // a short measurement of the frame time, once the page has settled
    let frames = 0, t0 = 0, last = 0;
    const step = now => { if (!t0) t0 = now; frames += 1; last = now; if (frames < 45) win.requestAnimationFrame(step); else {
      const mean = (last - t0) / (frames - 1), slow = mean > 24;
      try { win.localStorage.setItem('sa_lite', slow ? '1' : '0'); } catch (e) {}
      if (slow) apply(true); else if (remembered !== '1') apply(false);
    } };
    win.requestAnimationFrame(step);
  }, 4000);
})();
if (!win.__navDragV2) {
  win.__navDragV2 = true;
  let dragged = null;
  const SEL = '[class*="st-key-nav_course_"]';
  const course = el => (el && el.closest) ? el.closest(SEL) : null;
  const idOf = c => (c.className.match(/st-key-nav_course_([0-9]+)/) || [])[1];
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
// Outline points that link to a page of a Library file: pass "book,page" to the hidden box, which opens the preview.
if (!win.__olNavV1) {
  win.__olNavV1 = true;
  doc.addEventListener('click', e => {
    const a = e.target.closest && e.target.closest('a[data-ol-page]');
    if (!a) return;
    e.preventDefault();
    const inp = doc.querySelector('.st-key-outline_sink input'); if (!inp) return;
    const set = Object.getOwnPropertyDescriptor(win.HTMLInputElement.prototype, 'value').set;
    inp.focus(); set.call(inp, a.dataset.olBook + ',' + a.dataset.olPage + (a.dataset.olTab ? ',' + a.dataset.olTab : '') + '|' + Date.now());
    inp.dispatchEvent(new win.Event('input', {bubbles: true}));
    inp.dispatchEvent(new win.KeyboardEvent('keydown', {key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true}));
    inp.blur();
  }, true);
}
// Planner calendar: drag a study session or an event to move it, drag its bottom edge to change its length, drag over empty time to make a new one,
// click one to open it, and swipe sideways over the day names to go to the next or the previous period. What happened goes to the hidden box (cal_sink) as
// 'action|what|day|minutes|stamp' and the page answers it.
if (!win.__calDragV1) {
  win.__calDragV1 = true;
  const sendCal = text => {
    const inp = doc.querySelector('.st-key-cal_sink input'); if (!inp) return;
    const set = Object.getOwnPropertyDescriptor(win.HTMLInputElement.prototype, 'value').set;
    inp.focus(); set.call(inp, text + '|' + Date.now());
    inp.dispatchEvent(new win.Event('input', {bubbles: true}));
    inp.dispatchEvent(new win.KeyboardEvent('keydown', {key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true}));
    inp.blur();
  };
  doc.addEventListener('click', e => {
    const bin = e.target.closest && e.target.closest('.wk-del'); if (!bin) return;
    e.preventDefault(); e.stopPropagation(); sendCal('delete|' + bin.dataset.del);
  }, true);
  let drag = null;
  // A block that was dragged or resized keeps its new place on the screen until the page is drawn again. When the change is cancelled in the dialog (or refused), the page is not
  // drawn again, so the block is put back by hand: as soon as the dialog is gone and the same block is still there, it gets its old place, size and time back.
  const bounceBack = d => {
    const tm = d.block.querySelector('.wk-time'), orig = d.orig; let seen = false; const t0 = Date.now();
    const timer = win.setInterval(() => {
      if (!d.block.isConnected || Date.now() - t0 > 30000) { win.clearInterval(timer); return; }
      const open = !!doc.querySelector('[role="dialog"], [data-testid="stDialog"]');
      if (open) { seen = true; return; }
      if (seen || Date.now() - t0 > 2500) {
        win.clearInterval(timer);
        const col = d.block.closest('.wk-col');
        if (+d.block.dataset.start !== d.start || +d.block.dataset.end !== d.end || !col || col.dataset.day !== d.day) return;       // the change was made: the page shows the new place itself
        if (orig.style === null) d.block.removeAttribute('style'); else d.block.setAttribute('style', orig.style);
        d.block.classList.remove('dragging');
        if (tm && orig.time !== null) tm.textContent = orig.time;
      }
    }, 150);
  };
  const snapMin = (grid, px) => { const per = +grid.dataset.hourPx / 60, s = +grid.dataset.snap; return Math.round(px / per / s) * s; };
  doc.addEventListener('pointerdown', e => {
    if (e.target.closest && e.target.closest('.wk-del')) return;                  // the trash bin is a button, not a place to drag from
    const grid = e.target.closest && e.target.closest('.wk'); if (!grid || e.button !== 0) return;
    const col = e.target.closest('.wk-col'); if (!col) return;
    const block = e.target.closest('.wk-block');
    if (block && block.dataset.edit) {
      drag = {mode: e.target.closest('.wk-resize-top') ? 'resizetop' : e.target.closest('.wk-resize') ? 'resize' : 'move', block, grid, col, startX: e.clientX, startY: e.clientY, moved: false,
              start: +block.dataset.start, end: +block.dataset.end, day: col.dataset.day, dMin: 0,
              orig: {style: block.getAttribute('style'), time: block.querySelector('.wk-time') ? block.querySelector('.wk-time').textContent : null}};
    } else if (block && block.dataset.open) {
      drag = {mode: 'open', block, grid, col, startX: e.clientX, startY: e.clientY, moved: false};
    } else if (!block && e.target === col) {
      const lo = +col.dataset.lo;
      drag = {mode: 'create', grid, col, startY: e.clientY, lo, anchor: snapMin(grid, e.clientY - col.getBoundingClientRect().top) + lo * 60, day: col.dataset.day, moved: false, ghost: null, range: null};
    } else return;
    e.preventDefault();
  }, true);
  doc.addEventListener('pointermove', e => {
    if (!drag) return;
    const dy = e.clientY - drag.startY, dx = e.clientX - (drag.startX || 0);
    if (!drag.moved && Math.abs(dy) < 4 && Math.abs(dx) < 4) return;
    drag.moved = true;
    const showTime = (a, b) => { const tm = drag.block.querySelector('.wk-time'); const hm = m => String(Math.floor(m / 60) % 24).padStart(2, '0') + ':' + String(m % 60).padStart(2, '0'); if (tm) tm.textContent = hm(a) + ' - ' + hm(b); };
    if (drag.mode === 'open') return;                       // a class or an activity is opened by a click, not moved by a drag
    const per = +drag.grid.dataset.hourPx / 60;
    if (drag.mode === 'move') {
      drag.dMin = snapMin(drag.grid, dy);
      showTime(drag.start + drag.dMin, drag.end + drag.dMin);
      drag.block.classList.add('dragging');
      drag.block.style.transform = 'translate(' + dx + 'px,' + (drag.dMin * per) + 'px)';
      drag.target = [...drag.grid.querySelectorAll('.wk-col')].find(c => { const r = c.getBoundingClientRect(); return e.clientX >= r.left && e.clientX < r.right; }) || drag.col;
    } else if (drag.mode === 'resizetop') {
      drag.newStart = Math.min(drag.end - 15, drag.start + snapMin(drag.grid, dy));
      const lo = +drag.col.dataset.lo;
      showTime(drag.newStart, drag.end);
      drag.block.style.top = ((drag.newStart - lo * 60) * per) + 'px';
      drag.block.style.height = ((drag.end - drag.newStart) * per - 2) + 'px';
    } else if (drag.mode === 'resize') {
      drag.newEnd = Math.max(drag.start + 15, drag.end + snapMin(drag.grid, dy));
      showTime(drag.start, drag.newEnd);
      drag.block.style.height = ((drag.newEnd - drag.start) * per - 2) + 'px';
    } else {
      const y = snapMin(drag.grid, e.clientY - drag.col.getBoundingClientRect().top) + drag.lo * 60;
      const a = Math.min(drag.anchor, y), b = Math.max(drag.anchor, y);
      if (!drag.ghost) { drag.ghost = doc.createElement('div'); drag.ghost.className = 'wk-ghost'; drag.col.appendChild(drag.ghost); }
      drag.ghost.style.top = ((a - drag.lo * 60) * per) + 'px'; drag.ghost.style.height = Math.max((b - a) * per, 2) + 'px';
      drag.range = [a, b];
    }
  }, true);
  doc.addEventListener('pointerup', e => {
    const d = drag; drag = null; if (!d) return;
    if (d.mode === 'create') {
      if (d.ghost) d.ghost.remove();
      if (d.moved && d.range && d.range[1] - d.range[0] >= 15) sendCal('create|' + d.day + '|' + d.range[0] + '|' + d.range[1]);
      return;
    }
    if (d.mode === 'open') { if (!d.moved) sendCal('click|' + d.block.dataset.open); return; }
    if (!d.moved) { sendCal('click|' + d.block.dataset.ref); return; }
    bounceBack(d);
    if (d.mode === 'move') sendCal('move|' + d.block.dataset.ref + '|' + (d.target || d.col).dataset.day + '|' + (d.start + d.dMin));
    else if (d.mode === 'resizetop') sendCal('resizetop|' + d.block.dataset.ref + '|' + d.day + '|' + (d.newStart === undefined ? d.start : d.newStart));
    else sendCal('resize|' + d.block.dataset.ref + '|' + d.day + '|' + (d.newEnd || d.end));
  }, true);
  let swipe = null;
  doc.addEventListener('touchstart', e => {
    const top = e.target.closest && e.target.closest('.wk-top, .wk-strip'); if (!top || !e.touches.length) { swipe = null; return; }
    swipe = {x: e.touches[0].clientX, y: e.touches[0].clientY};
  }, {passive: true, capture: true});
  doc.addEventListener('touchend', e => {
    if (!swipe || !e.changedTouches.length) return;
    const dx = e.changedTouches[0].clientX - swipe.x, dy = e.changedTouches[0].clientY - swipe.y; swipe = null;
    if (Math.abs(dx) > 60 && Math.abs(dy) < 50) { const b = doc.querySelector(dx < 0 ? '.st-key-cal_next button' : '.st-key-cal_prev button'); if (b) b.click(); }
  }, {passive: true, capture: true});
}
// A hover note (the "add files to the library" of the Import button) is closed by the pointer leaving its button. When a window opens and the button disappears under the pointer, the note
// would stay on top of the window; so when a window opens, the notes that are open then are hidden.
if (!win.__dialogTipV1) {
  win.__dialogTipV1 = true;
  let open = false;
  const hideTips = () => doc.querySelectorAll('[data-testid="stTooltipContent"]').forEach(t => { const box = t.closest('[data-baseweb="popover"]') || t.parentElement; if (box) box.style.display = 'none'; });
  new win.MutationObserver(() => {
    const now = !!doc.querySelector('[data-testid="stDialog"]');
    if (now && !open) { hideTips(); win.setTimeout(hideTips, 120); win.setTimeout(hideTips, 400); }
    open = now;
  }).observe(doc.body, {childList: true, subtree: true});
}
// Settings: the bar at the top jumps to a section (the page scrolls inside the app, so the link scrolls that heading into view itself).
if (!win.__setNavV1) {
  win.__setNavV1 = true;
  doc.addEventListener('click', e => {
    const a = e.target.closest && e.target.closest('.set-nav a[data-jump]'); if (!a) return;
    e.preventDefault();
    const h = doc.getElementById(a.dataset.jump); if (!h) return;
    h.scrollIntoView({behavior: 'smooth', block: 'start'});
    doc.querySelectorAll('.set-nav a').forEach(x => x.classList.toggle('on', x === a));
  }, true);
}
// Switching pages: Streamlit keeps the old page's elements (faded) above the new ones until the new page is drawn, so the new page started low and jumped up when the old
// elements went. While a page is being switched the old elements are hidden, so the new page is built from the top and nothing jumps.
if (!win.__navSwitchV1) {
  win.__navSwitchV1 = true;
  doc.addEventListener('click', e => {
    const b = e.target.closest && e.target.closest('[class*="st-key-nav_"] button'); if (!b) return;
    const body = doc.body; body.classList.add('nav-switching');
    let quiet = 0, tries = 0;
    const timer = win.setInterval(() => {
      tries += 1;
      quiet = doc.querySelector('[data-stale="true"]') ? 0 : quiet + 1;
      if (quiet >= 3 || tries > 60) { win.clearInterval(timer); body.classList.remove('nav-switching'); }
    }, 100);
  }, true);
}
// Planner calendar: drag a block from the left panel onto the grid. The block follows the pointer; where it is let go the day and the time (to 15 minutes) go to the hidden box.
if (!win.__calPanelV1) {
  win.__calPanelV1 = true;
  let pd = null;
  const sendDrop = text => {
    const inp = doc.querySelector('.st-key-cal_sink input'); if (!inp) return;
    const set = Object.getOwnPropertyDescriptor(win.HTMLInputElement.prototype, 'value').set;
    inp.focus(); set.call(inp, text + '|' + Date.now());
    inp.dispatchEvent(new win.Event('input', {bubbles: true}));
    inp.dispatchEvent(new win.KeyboardEvent('keydown', {key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true}));
    inp.blur();
  };
  const colAt = (x, y) => { for (const el of doc.elementsFromPoint(x, y)) { const c = el.closest && el.closest('.wk-col'); if (c) return c; } return null; };
  doc.addEventListener('pointerdown', e => {
    const item = e.target.closest && e.target.closest('.pl-item[data-drag]'); if (!item || e.button !== 0 || item.closest('.pl-nodrop')) return;
    if (e.target.closest('.pl-more, .pl-show, .pl-handle') || (e.target.closest('.pl-name') || {}).isContentEditable) return;
    pd = {item, what: item.dataset.drag, x: e.clientX, y: e.clientY, ghost: null, col: null};
    e.preventDefault();
  }, true);
  doc.addEventListener('pointermove', e => {
    if (!pd) return;
    if (!pd.started) {
      if (Math.abs(e.clientX - pd.x) < 5 && Math.abs(e.clientY - pd.y) < 5) return;
      pd.started = true; doc.body.classList.add('pl-dragging');                  // no copy of the block follows the pointer: only the preview on the schedule shows
    }
    const c = colAt(e.clientX, e.clientY);
    if (pd.col && pd.col !== c) pd.col.classList.remove('drop-hover');
    if (c) c.classList.add('drop-hover');
    pd.col = c;
    // the block as it will be placed: one hour tall (a study session: its own length), snapped to the grid, in the color of the dragged block
    if (!c) { if (pd.prev) pd.prev.style.display = 'none'; return; }
    const grid = c.closest('.wk'), per = +grid.dataset.hourPx / 60, snap = +grid.dataset.snap, len = +(pd.item.dataset.minutes || 60);
    const start = Math.max(0, Math.min(1440 - len, Math.round((e.clientY - c.getBoundingClientRect().top) / per / snap) * snap + (+c.dataset.lo) * 60));
    if (!pd.prev) { pd.prev = doc.createElement('div'); pd.prev.className = 'wk-preview'; pd.prev.style.setProperty('--c', getComputedStyle(pd.item).borderLeftColor); pd.prevText = doc.createElement('div'); pd.prev.appendChild(pd.prevText); }
    if (pd.prev.parentElement !== c) c.appendChild(pd.prev);
    const hm = m => String(Math.floor(m / 60) % 24).padStart(2, '0') + ':' + String(m % 60).padStart(2, '0');
    pd.prev.style.display = ''; pd.prev.style.top = ((start - (+c.dataset.lo) * 60) * per) + 'px'; pd.prev.style.height = (len * per - 2) + 'px';
    pd.prevText.innerHTML = '<b>' + hm(start) + ' - ' + hm(start + len) + '</b><br>' + ((pd.item.querySelector('.pl-name') || pd.item).textContent || '').trim();
  }, true);
  doc.addEventListener('pointerup', e => {
    const d = pd; pd = null; if (!d) return;
    doc.body.classList.remove('pl-dragging');
    if (d.prev) d.prev.remove();
    doc.querySelectorAll('.wk-col.drop-hover').forEach(c => c.classList.remove('drop-hover'));
    if (!d.started) return;
    const c = colAt(e.clientX, e.clientY); if (!c) return;
    const grid = c.closest('.wk'), per = +grid.dataset.hourPx / 60, snap = +grid.dataset.snap;
    const minutes = Math.max(0, Math.min(1425, Math.round((e.clientY - c.getBoundingClientRect().top) / per / snap) * snap + (+c.dataset.lo) * 60));
    sendDrop('drop|' + d.what + '|' + c.dataset.day + '|' + minutes);
  }, true);
}
// Calendar panel: drag a block by its grip to change the order of its group (tasks, courses, activities); the new order goes to the hidden box.
if (!win.__calOrderV1) {
  win.__calOrderV1 = true;
  let od = null;
  const sendOrder = text => {
    const inp = doc.querySelector('.st-key-cal_sink input'); if (!inp) return;
    const set = Object.getOwnPropertyDescriptor(win.HTMLInputElement.prototype, 'value').set;
    inp.focus(); set.call(inp, text + '|' + Date.now());
    inp.dispatchEvent(new win.Event('input', {bubbles: true}));
    inp.dispatchEvent(new win.KeyboardEvent('keydown', {key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true}));
    inp.blur();
  };
  const kindOf = el => (el.dataset.drag || '').split(':')[0];
  doc.addEventListener('pointerdown', e => {
    const h = e.target.closest && e.target.closest('.pl-handle'); if (!h || e.button !== 0) return;
    const item = h.closest('.pl-item[data-drag]'); if (!item) return;
    od = {item, kind: kindOf(item), moved: false}; item.classList.add('pl-moving'); e.preventDefault(); e.stopPropagation();
  }, true);
  doc.addEventListener('pointermove', e => {
    if (!od) return;
    const sibs = [...od.item.parentElement.children].filter(x => x.matches('.pl-item[data-drag]') && kindOf(x) === od.kind && x !== od.item);
    for (const s of sibs) {
      const r = s.getBoundingClientRect();
      if (e.clientY >= r.top && e.clientY <= r.bottom) {
        const after = e.clientY > r.top + r.height / 2;
        if ((after && s.nextElementSibling !== od.item) || (!after && s.previousElementSibling !== od.item)) {
          const all = [...od.item.parentElement.children].filter(x => x.matches('.pl-item[data-drag]') && x !== od.item);
          const first = new Map(all.map(x => [x, x.getBoundingClientRect().top]));
          if (after) s.after(od.item); else s.before(od.item);
          od.moved = true;
          all.forEach(x => {
            const dy = first.get(x) - x.getBoundingClientRect().top; if (!dy) return;
            x.style.transition = 'none'; x.style.transform = 'translateY(' + dy + 'px)';
            win.requestAnimationFrame(() => { x.style.transition = 'transform .16s ease'; x.style.transform = ''; });
          });
        }
        break;
      }
    }
  }, true);
  doc.addEventListener('pointerup', () => {
    const d = od; od = null; if (!d) return;
    d.item.classList.remove('pl-moving');
    if (!d.moved) return;
    const refs = [...d.item.parentElement.children].filter(x => x.matches('.pl-item[data-drag]') && kindOf(x) === d.kind).map(x => x.dataset.drag);
    sendOrder('panel|order|' + d.item.dataset.drag + '|' + refs.join(','));
  }, true);
}
// Library, Date Added: one button folds every group of the timeline, or opens them all when they are folded.
if (!win.__tlAllV2) {
  win.__tlAllV2 = true;
  doc.addEventListener('click', e => {
    const b = e.target.closest && e.target.closest('[data-tl-all]'); if (!b) return;
    const groups = [...doc.querySelectorAll('details.tl-group')];
    const open = !groups.some(d => d.open);
    groups.forEach(d => { d.open = open; });
    b.textContent = open ? 'Collapse All' : 'Expand All';
  }, true);
}
// Courses > All > Tree: a click on a bubble folds or unfolds that bubble only: its branches slide into it (or back out) and the view stays exactly as it is. One button folds every branch into its
// domain, or unfolds all. A click on a course sends its id to the hidden box.
if (!win.__treeV4) {
  win.__treeV4 = true;
  const refresh = svg => {
    const nodes = new Map(); svg.querySelectorAll('.mm-node').forEach(n => nodes.set(n.dataset.id, n));
    nodes.forEach(n => {
      let p = n.dataset.parent, hide = false;
      while (p && nodes.has(p)) { const pn = nodes.get(p); if (pn.classList.contains('mm-collapsed')) { hide = true; break; } p = pn.dataset.parent; }
      n.classList.toggle('mm-hidden', hide);
    });
  };
  doc.addEventListener('click', e => {
    const t = e.target.closest && e.target.closest('[data-mm-toggle], [data-tree-course], [data-mm-all]'); if (!t) return;
    if (win.__mmDragged) { e.stopPropagation(); e.preventDefault(); return; }                  // the end of a drag of a bubble is not a click on it
    if (t.dataset.treeCourse) {
      const inp = doc.querySelector('.st-key-tree_sink input'); if (!inp) return;
      const set = Object.getOwnPropertyDescriptor(win.HTMLInputElement.prototype, 'value').set;
      inp.focus(); set.call(inp, t.dataset.treeCourse + '|' + Date.now());
      inp.dispatchEvent(new win.Event('input', {bubbles: true}));
      inp.dispatchEvent(new win.KeyboardEvent('keydown', {key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true}));
      inp.blur(); return;
    }
    const svg = (t.closest('.mm-wrap') || doc).querySelector('svg.mm'); if (!svg) return;
    if (t.dataset.mmAll) {
      const close = t.dataset.mmAll === 'close';
      svg.querySelectorAll('.mm-node[data-mm-toggle]').forEach(n => n.classList.toggle('mm-collapsed', close && n.dataset.parent !== ''));
      t.dataset.mmAll = close ? 'open' : 'close'; t.textContent = close ? 'Expand All' : 'Collapse All';
    } else t.classList.toggle('mm-collapsed');
    refresh(svg);
  }, true);
}
// Courses > All > Tree: zoom with the + and - buttons or the mouse wheel, move the map by dragging an empty place, Fit shows all of it again. The map is an SVG: zooming changes its viewBox.
if (!win.__treeZoomV2) {
  win.__treeZoomV2 = true;
  const home = svg => { if (!svg.__home) { const v = svg.viewBox.baseVal; svg.__home = [v.x, v.y, v.width, v.height]; } return svg.__home; };
  const setBox = (svg, b, animate) => {
    if (!animate) { svg.setAttribute('viewBox', b.join(' ')); return; }
    const from = [svg.viewBox.baseVal.x, svg.viewBox.baseVal.y, svg.viewBox.baseVal.width, svg.viewBox.baseVal.height], t0 = win.performance.now();
    const step = now => { const k = Math.min(1, (now - t0) / 220), e = 1 - Math.pow(1 - k, 3); svg.setAttribute('viewBox', from.map((v, i) => v + (b[i] - v) * e).join(' ')); if (k < 1) win.requestAnimationFrame(step); };
    win.requestAnimationFrame(step);
  };
  const zoomAt = (svg, factor, fx, fy, animate) => {
    const h = home(svg), v = svg.viewBox.baseVal;
    const w = Math.max(h[2] / 8, Math.min(h[2] * 1.5, v.width / factor)), k = w / v.width, hh = v.height * k;
    setBox(svg, [v.x + (v.width - w) * fx, v.y + (v.height - hh) * fy, w, hh], animate);
  };
  doc.addEventListener('click', e => {
    const b = e.target.closest && e.target.closest('[data-mm-zoom]'); if (!b) return;
    const svg = (b.closest('.mm-wrap') || doc).querySelector('svg.mm'); if (!svg) return;
    if (b.dataset.mmZoom === 'reset') { setBox(svg, home(svg), true); doc.dispatchEvent(new win.CustomEvent('mm-reset', {detail: svg})); }          // the view and the places of the bubbles
    else if (b.dataset.mmZoom === 'fit') setBox(svg, home(svg), true); else zoomAt(svg, b.dataset.mmZoom === 'in' ? 1.35 : 1 / 1.35, 0.5, 0.5, true);
  }, true);
  doc.addEventListener('wheel', e => {
    const svg = e.target.closest && e.target.closest('svg.mm'); if (!svg) return;
    e.preventDefault();
    const r = svg.getBoundingClientRect();
    zoomAt(svg, e.deltaY < 0 ? 1.15 : 1 / 1.15, (e.clientX - r.left) / r.width, (e.clientY - r.top) / r.height, false);
  }, {passive: false, capture: true});
  let pan = null;
  doc.addEventListener('pointerdown', e => {
    const svg = e.target.closest && e.target.closest('svg.mm'); if (!svg || e.button !== 0 || e.target.closest('.mm-node')) return;
    const v = svg.viewBox.baseVal; pan = {svg, x: e.clientX, y: e.clientY, box: [v.x, v.y, v.width, v.height]}; svg.classList.add('panning'); e.preventDefault();
  }, true);
  doc.addEventListener('pointermove', e => {
    if (!pan) return;
    const r = pan.svg.getBoundingClientRect(), k = pan.box[2] / r.width;
    setBox(pan.svg, [pan.box[0] - (e.clientX - pan.x) * k, pan.box[1] - (e.clientY - pan.y) * k, pan.box[2], pan.box[3]], false);
  }, true);
  doc.addEventListener('pointerup', () => { if (pan) { pan.svg.classList.remove('panning'); pan = null; } }, true);
}
// Courses > All > Tree: drag a bubble to move it (the branches and courses that hang on it move with it, its line stretches). The bubble lifts while it is held and settles when it is dropped. The
// places are kept while the page is redrawn (not after a reload); a double-click on the empty map puts every bubble back.
if (!win.__treeDragV1) {
  win.__treeDragV1 = true;
  const offsets = win.__mmOffsets = win.__mmOffsets || {};
  const keyOf = n => {                                              // the same on every redraw: the course id, or the labels of the bubble and of every bubble above it (two "General" bubbles are two keys)
    if (n.__key) return n.__key;
    const own = n.dataset.treeCourse ? 'c' + n.dataset.treeCourse : 'b' + (n.querySelector('.mm-label') ? n.querySelector('.mm-label').textContent : n.dataset.id);
    const par = n.dataset.parent && n.parentNode ? n.parentNode.querySelector('.mm-node[data-id="' + n.dataset.parent + '"]') : null;
    return (n.__key = (par ? keyOf(par) + '/' : '') + own);
  };
  const base = n => {
    if (!n.__b) {
      const s = n.style, f = v => parseFloat(s.getPropertyValue(v)) || 0, c = n.querySelector('circle');
      n.__b = {x: f('--x'), y: f('--y'), px: f('--px'), py: f('--py'), r: c ? parseFloat(c.getAttribute('r')) || 0 : 0};
    }
    return n.__b;
  };
  // the two ends of a line between circle centers (dx, dy from the first to the second), both pulled back to the borders of their circles; null when the circles touch
  const trimmed = (dx, dy, r1, r2) => {
    const len = Math.hypot(dx, dy); if (len <= r1 + r2 + 1) return null;
    const ux = dx / len, uy = dy / len; return [ux * r1, uy * r1, dx - ux * r2, dy - uy * r2];
  };
  const setLine = (ln, ends, ox = 0, oy = 0) => {
    if (!ends) { ln.style.visibility = 'hidden'; return; }
    ln.style.visibility = '';
    ln.setAttribute('x1', ends[0] + ox); ln.setAttribute('y1', ends[1] + oy); ln.setAttribute('x2', ends[2] + ox); ln.setAttribute('y2', ends[3] + oy);
  };
  const place = svg => {
    const nodes = [...svg.querySelectorAll('.mm-node')], byId = new Map(nodes.map(n => [n.dataset.id, n]));
    nodes.forEach(n => {
      const b = base(n), o = offsets[keyOf(n)] || [0, 0], par = byId.get(n.dataset.parent), po = par ? (offsets[keyOf(par)] || [0, 0]) : [0, 0];
      n.style.setProperty('--x', (b.x + o[0]) + 'px'); n.style.setProperty('--y', (b.y + o[1]) + 'px');
      n.style.setProperty('--px', (b.px + po[0]) + 'px'); n.style.setProperty('--py', (b.py + po[1]) + 'px');
      const ln = n.querySelector('.mm-line');
      if (ln && par) {
        const dx = b.px + po[0] - (b.x + o[0]), dy = b.py + po[1] - (b.y + o[1]), ends = trimmed(dx, dy, b.r, base(par).r);
        setLine(ln, ends);
        if (hold && hold.ghost && hold.node === n) setLine(hold.ghost, ends, b.x + o[0], b.y + o[1]);        // the held bubble's line is drawn under every bubble, so it never crosses its parent
      }
    });
  };
  let hold = null;
  // Bubbles and lines never overlap: what the held bubble (with the branches that hang on it) comes near is pushed away, bubbles from bubbles, and bubbles from lines (a line that the held
  // bubble touches swings aside, because the bubble at its end is pushed sideways). The center bubble does not move; the held bubble stops at it.
  const GAP = 10, LINE_GAP = 8, STEP = 18, PASSES = 12, MAX_MOVE = 260;
  const field = svg => {                                                                        // the rectangle of the map as it was drawn (the view may be zoomed or moved; the field is not)
    if (!svg.__field) { const h = (svg.dataset.home || '').split(' ').map(Number); const v = svg.viewBox.baseVal; svg.__field = h.length === 4 && h.every(isFinite) ? h : [v.x, v.y, v.width, v.height]; }
    return svg.__field;
  };
  const repel = (svg, group, held) => {
    const info = [...svg.querySelectorAll('.mm-node')].filter(n => !n.classList.contains('mm-hidden')).map(n => {
      const b = base(n), o = offsets[keyOf(n)] || [0, 0];
      return {n, b, key: keyOf(n), r: parseFloat(n.querySelector('circle').getAttribute('r')) || 0, x: b.x + o[0], y: b.y + o[1], fixed: group.has(n) || n.dataset.parent === '', moved: false};
    });
    const byId = new Map(info.map(i => [i.n.dataset.id, i]));
    const H = info.find(i => i.n === held), R = info.find(i => i.n.dataset.parent === '');
    const shiftGroup = (sx, sy) => { group.forEach(n => { const o = offsets[keyOf(n)]; if (o) { o[0] += sx; o[1] += sy; } }); info.forEach(i => { if (group.has(i.n)) { i.x += sx; i.y += sy; } }); };
    const segDist = (px, py, ax, ay, bx, by) => {
      const sx = bx - ax, sy = by - ay, l2 = sx * sx + sy * sy; if (l2 < 1) return [Math.hypot(px - ax, py - ay), ax, ay];
      const u = Math.max(0, Math.min(1, ((px - ax) * sx + (py - ay) * sy) / l2)), qx = ax + sx * u, qy = ay + sy * u; return [Math.hypot(px - qx, py - qy), qx, qy];
    };
    // walls: the held bubble cannot be pushed into the center bubble, and it slides along the lines of other bubbles instead of crossing them
    for (let k = 0; k < 4 && H; k++) {
      if (R) { const d = Math.hypot(H.x - R.x, H.y - R.y), min = H.r + R.r + GAP; if (d < min && d > 0) shiftGroup((H.x - R.x) / d * (min - d), (H.y - R.y) / d * (min - d)); }
      info.forEach(L => {
        const P = byId.get(L.n.dataset.parent); if (!P || group.has(L.n) || P === H || L === H) return;
        const [d, qx, qy] = segDist(H.x, H.y, L.x, L.y, P.x, P.y), min = H.r + LINE_GAP; if (d >= min) return;
        let dx = H.x - qx, dy = H.y - qy, dd = Math.hypot(dx, dy); if (dd < 0.01) { dx = -(P.y - L.y); dy = P.x - L.x; dd = Math.hypot(dx, dy) || 1; }
        shiftGroup(dx / dd * (min - d), dy / dd * (min - d));
      });
    }
    const fld = field(svg);
    const inside = i => { i.x = Math.max(fld[0] + i.r, Math.min(fld[0] + fld[2] - i.r, i.x)); i.y = Math.max(fld[1] + i.r, Math.min(fld[1] + fld[3] - i.r, i.y)); };
    {                                                                                           // the held bubbles (with their branches) stay inside the field
      const g = info.filter(i => group.has(i.n)); if (g.length) {
        const lo = [Math.min(...g.map(i => i.x - i.r)), Math.min(...g.map(i => i.y - i.r))], hi = [Math.max(...g.map(i => i.x + i.r)), Math.max(...g.map(i => i.y + i.r))];
        const sx = lo[0] < fld[0] ? fld[0] - lo[0] : hi[0] > fld[0] + fld[2] ? fld[0] + fld[2] - hi[0] : 0, sy = lo[1] < fld[1] ? fld[1] - lo[1] : hi[1] > fld[1] + fld[3] ? fld[1] + fld[3] - hi[1] : 0;
        if (sx || sy) shiftGroup(sx, sy);
      }
    }
    const start = info.map(i => [i.x, i.y]);
    const shove = (i, dx, dy) => {
      if (i.fixed) return;
      const m = Math.hypot(dx, dy); if (m > STEP) { dx *= STEP / m; dy *= STEP / m; }
      i.x += dx; i.y += dy; inside(i); i.moved = true;
    };
    for (let pass = 0; pass < PASSES; pass++) {
      let any = false;
      for (let a = 0; a < info.length; a++) for (let c = a + 1; c < info.length; c++) {                 // bubble from bubble
        const A = info[a], B = info[c]; if (A.fixed && B.fixed) continue;
        let dx = B.x - A.x, dy = B.y - A.y, d = Math.hypot(dx, dy); const min = A.r + B.r + GAP; if (d >= min) continue;
        if (d < 0.01) { dx = 1; dy = 0; d = 1; }
        const push = min - d, ux = dx / d, uy = dy / d; any = true;
        if (A.fixed) shove(B, ux * push, uy * push); else if (B.fixed) shove(A, -ux * push, -uy * push); else { shove(A, -ux * push / 2, -uy * push / 2); shove(B, ux * push / 2, uy * push / 2); }
      }
      info.forEach(L => {                                                                               // bubble from line: a bubble that a line crosses is moved off it
        const P = byId.get(L.n.dataset.parent); if (!P) return;
        info.forEach(C => {
          if (C === L || C === P || C.fixed) return;
          const [d, qx, qy] = segDist(C.x, C.y, L.x, L.y, P.x, P.y), min = C.r + LINE_GAP; if (d >= min) return;
          let dx = C.x - qx, dy = C.y - qy, dd = Math.hypot(dx, dy); if (dd < 0.01) { dx = -(P.y - L.y); dy = P.x - L.x; dd = Math.hypot(dx, dy) || 1; }
          any = true; shove(C, dx / dd * (min - d), dy / dd * (min - d));
        });
      });
      if (!any) break;
    }
    if (info.some((i, k) => i.moved && Math.hypot(i.x - start[k][0], i.y - start[k][1]) > MAX_MOVE) || info.some(i => !isFinite(i.x) || !isFinite(i.y))) return;     // a push that runs away is not applied
    info.forEach(i => { if (i.moved) offsets[i.key] = [i.x - i.b.x, i.y - i.b.y]; });
  };
  // How many bubbles overlap another bubble, and how many lines cross a bubble that is not at their ends.
  const violations = svg => {
    const nodes = [...svg.querySelectorAll('.mm-node')].filter(n => !n.classList.contains('mm-hidden')).map(n => {
      const b = base(n), o = offsets[keyOf(n)] || [0, 0]; return {x: b.x + o[0], y: b.y + o[1], r: b.r, id: n.dataset.id, par: n.dataset.parent};
    });
    const by = new Map(nodes.map(i => [i.id, i]));
    let v = 0;
    for (let a = 0; a < nodes.length; a++) for (let c = a + 1; c < nodes.length; c++) if (Math.hypot(nodes[a].x - nodes[c].x, nodes[a].y - nodes[c].y) < nodes[a].r + nodes[c].r) v++;
    nodes.forEach(L => {
      const P = by.get(L.par); if (!P) return;
      const sx = P.x - L.x, sy = P.y - L.y, l2 = sx * sx + sy * sy; if (l2 < 1) return;
      nodes.forEach(C => {
        if (C === L || C === P) return;
        const u = Math.max(0, Math.min(1, ((C.x - L.x) * sx + (C.y - L.y) * sy) / l2));
        if (Math.hypot(C.x - (L.x + sx * u), C.y - (L.y + sy * u)) < C.r) v++;
      });
    });
    return v;
  };
  // One step of a drag. The held bubbles go to the wanted place only when nothing overlaps there; else they stop at the furthest place on the way where nothing does (what was wrong
  // before the drag began is not held against it).
  const tryMove = (tx, ty) => {
    const group = new Set(hold.group), from = hold.last || [0, 0], keyH = keyOf(hold.node);
    if (hold.viol === undefined) hold.viol = violations(hold.svg);
    for (const f of [1, 0.66, 0.4, 0.2, 0.08, 0]) {
      const snap = JSON.parse(JSON.stringify(offsets));
      const cx = from[0] + (tx - from[0]) * f, cy = from[1] + (ty - from[1]) * f;
      hold.start.forEach((o, k) => { offsets[k] = [o[0] + cx, o[1] + cy]; });
      repel(hold.svg, group, hold.node);
      const v = violations(hold.svg);
      if (v <= hold.viol || f === 0) {
        hold.viol = Math.min(hold.viol, v);
        const o = offsets[keyH], s = hold.start.get(keyH); hold.last = [o[0] - s[0], o[1] - s[1]];
        break;
      }
      Object.keys(offsets).forEach(k => delete offsets[k]); Object.assign(offsets, snap);
    }
    place(hold.svg);
  };
  const subtree = (svg, root) => {
    const nodes = [...svg.querySelectorAll('.mm-node')], out = new Set([root.dataset.id]);
    let grew = true;
    while (grew) { grew = false; nodes.forEach(n => { if (!out.has(n.dataset.id) && out.has(n.dataset.parent)) { out.add(n.dataset.id); grew = true; } }); }
    return nodes.filter(n => out.has(n.dataset.id));
  };
  doc.addEventListener('pointerdown', e => {
    const node = e.target.closest && e.target.closest('.mm-node'); if (!node || e.button !== 0 || node.classList.contains('mm-hidden') || node.dataset.parent === '') return;
    const svg = node.closest('svg.mm'); if (!svg) return;
    const v = svg.viewBox.baseVal, r = svg.getBoundingClientRect();
    hold = {svg, node, x: e.clientX, y: e.clientY, scale: Math.min(r.width / v.width, r.height / v.height), moved: false, group: null, start: null};
  }, true);
  doc.addEventListener('pointermove', e => {
    if (!hold) return;
    const dx = e.clientX - hold.x, dy = e.clientY - hold.y;
    if (!hold.moved) {
      if (Math.abs(dx) < 5 && Math.abs(dy) < 5) return;
      hold.moved = true; hold.group = subtree(hold.svg, hold.node);
      hold.start = new Map(hold.group.map(n => [keyOf(n), (offsets[keyOf(n)] || [0, 0]).slice()]));
      hold.group.forEach(n => n.classList.add('mm-moving'));
      hold.node.classList.add('mm-dragging'); hold.node.classList.remove('mm-settle');
      hold.next = hold.node.nextSibling;
      const own = hold.node.querySelector('.mm-line');
      if (own) {                                                                          // its line moves out of the bubble and under all bubbles while it is held
        hold.ghost = doc.createElementNS('http://www.w3.org/2000/svg', 'line'); hold.ghost.setAttribute('class', 'mm-line mm-ghost');
        hold.svg.insertBefore(hold.ghost, hold.svg.firstChild); own.style.display = 'none';
      }
      hold.svg.appendChild(hold.node);                                                   // the held bubble is drawn over the others
      hold.svg.classList.add('mm-holding');
    }
    tryMove(dx / hold.scale, dy / hold.scale);
  }, true);
  const drop = () => {
    if (!hold) return;
    const h = hold; hold = null;
    if (!h.moved) return;
    win.__mmDragged = true; win.setTimeout(() => { win.__mmDragged = false; }, 80);
    h.svg.classList.remove('mm-holding');
    if (h.ghost) { h.ghost.remove(); const own = h.node.querySelector('.mm-line'); if (own) own.style.display = ''; }
    h.svg.insertBefore(h.node, h.next || null);                                          // back in its place in the drawing order: a parent bubble covers the lines that end in it
    h.node.classList.remove('mm-dragging'); h.node.classList.add('mm-settle');
    win.setTimeout(() => { h.group.forEach(n => n.classList.remove('mm-moving')); h.node.classList.remove('mm-settle'); }, 420);
  };
  doc.addEventListener('pointerup', drop, true);
  doc.addEventListener('pointercancel', drop, true);
  const putBack = svg => { Object.keys(offsets).forEach(k => delete offsets[k]); place(svg); };
  doc.addEventListener('dblclick', e => {
    const svg = e.target.closest && e.target.closest('svg.mm'); if (!svg || e.target.closest('.mm-node')) return;
    putBack(svg);
  }, true);
  doc.addEventListener('mm-reset', e => putBack(e.detail), true);
  // a page that is drawn again (a filter, a switch of the view) gets the places the bubbles were given
  new win.MutationObserver(() => {
    doc.querySelectorAll('svg.mm').forEach(svg => { if (svg.__placed || !Object.keys(offsets).length) { svg.__placed = true; return; } svg.__placed = true; place(svg); });
  }).observe(doc.body, {childList: true, subtree: true});
}
// Calendar: drag the splitter at the right edge of the left panel to change its width (double-click: back to the usual width), drag the line next to the hours to
// zoom the time scale (double-click: back to the usual height), and a click on a block of the Task List bar picks that course.
if (!win.__calSizeV1) {
  win.__calSizeV1 = true;
  const sendSize = text => {
    const inp = doc.querySelector('.st-key-cal_sink input'); if (!inp) return;
    const set = Object.getOwnPropertyDescriptor(win.HTMLInputElement.prototype, 'value').set;
    inp.focus(); set.call(inp, text + '|' + Date.now());
    inp.dispatchEvent(new win.Event('input', {bubbles: true}));
    inp.dispatchEvent(new win.KeyboardEvent('keydown', {key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true}));
    inp.blur();
  };
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const zoomTo = (grid, px) => {
    const f = px / +grid.dataset.renderPx;
    grid.dataset.hourPx = px;
    grid.querySelectorAll('.wk-col, .wk-gutter, .wk-col > .wk-block, .wk-col > .wk-free, .wk-col > .wk-now, .wk-hour').forEach(el => {
      if (el.dataset.t0 === undefined) { el.dataset.t0 = parseFloat(el.style.top) || 0; el.dataset.h0 = parseFloat(el.style.height) || 0; }
      if (el.style.top) el.style.top = (el.dataset.t0 * f) + 'px';
      if (el.style.height) el.style.height = (el.dataset.h0 * f) + 'px';
    });
  };
  let sd = null;
  doc.addEventListener('pointerdown', e => {
    if (e.button !== 0 || !e.target.closest) return;
    const split = e.target.closest('.pl-split');
    if (split) {
      const col = split.closest('[data-testid="stColumn"]');
      sd = {kind: 'w', el: split, x: e.clientX, w: col.getBoundingClientRect().width, value: null}; split.classList.add('on'); doc.documentElement.classList.add('pl-resizing'); e.preventDefault(); e.stopPropagation(); return;
    }
    const zoom = e.target.closest('.wk-zoom');
    if (zoom) {
      const grid = zoom.closest('.wk');
      sd = {kind: 'z', el: zoom, grid, y: e.clientY, px: +grid.dataset.hourPx, value: null}; zoom.classList.add('on'); e.preventDefault(); e.stopPropagation();
    }
  }, true);
  doc.addEventListener('pointermove', e => {
    if (!sd) return;
    if (sd.kind === 'w') {
      sd.value = Math.round(clamp(sd.w + e.clientX - sd.x, 180, 520));
      doc.documentElement.style.setProperty('--pl-w', sd.value + 'px');
    } else {
      sd.value = Math.round(clamp(sd.px + (e.clientY - sd.y) * 0.4, 32, 140));
      if (!sd.raf) sd.raf = win.requestAnimationFrame(() => { sd.raf = 0; zoomTo(sd.grid, sd.value); });
    }
  }, true);
  doc.addEventListener('pointerup', () => {
    const d = sd; sd = null; if (!d) return;
    d.el.classList.remove('on'); doc.documentElement.classList.remove('pl-resizing');
    if (d.value === null) return;
    sendSize((d.kind === 'w' ? 'panelw|' : 'zoom|') + d.value);
  }, true);
  doc.addEventListener('dblclick', e => {
    if (!e.target.closest) return;
    if (e.target.closest('.pl-split')) { doc.documentElement.style.removeProperty('--pl-w'); sendSize('panelw|0'); e.preventDefault(); }
    else if (e.target.closest('.wk-zoom')) { sendSize('zoom|0'); e.preventDefault(); }
  }, true);
  doc.addEventListener('click', e => {
    const item = e.target.closest && e.target.closest('[data-pick]'); if (!item) return;
    if (e.target.closest('.pl-handle, .pl-more, .pl-show, .pl-menu') || (e.target.closest('.pl-name') || {}).isContentEditable) return;
    sendSize('tl|pick|' + item.dataset.pick);
  }, true);
}
// Calendar panel: the menu of a block (details, rename, change color, hide), a rename by double-clicking its name, and Show in the hidden list.
if (!win.__calMenuV1) {
  win.__calMenuV1 = true;
  const sendMenu = text => {
    const inp = doc.querySelector('.st-key-cal_sink input'); if (!inp) return;
    const set = Object.getOwnPropertyDescriptor(win.HTMLInputElement.prototype, 'value').set;
    inp.focus(); set.call(inp, text + '|' + Date.now());
    inp.dispatchEvent(new win.Event('input', {bubbles: true}));
    inp.dispatchEvent(new win.KeyboardEvent('keydown', {key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true}));
    inp.blur();
  };
  const closeMenu = () => { const m = doc.querySelector('.pl-menu'); if (m) m.remove(); };
  doc.addEventListener('click', e => {
    const more = e.target.closest && e.target.closest('.pl-more');
    if (more) {
      e.preventDefault(); e.stopPropagation(); closeMenu();
      const ref = more.dataset.menu, r = more.getBoundingClientRect(), m = doc.createElement('div'); m.className = 'pl-menu';
      const icons = {
        details: 'M11 7h2v2h-2zm0 4h2v6h-2zm1-9C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8z',
        rename: 'M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04a.996.996 0 0 0 0-1.41l-2.34-2.34a.996.996 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z',
        color: 'M12 3a9 9 0 0 0 0 18c.83 0 1.5-.67 1.5-1.5 0-.39-.15-.74-.39-1.01-.23-.26-.38-.61-.38-.99 0-.83.67-1.5 1.5-1.5H16c2.76 0 5-2.24 5-5 0-4.42-4.03-8-9-8zm-5.5 9c-.83 0-1.5-.67-1.5-1.5S5.67 9 6.5 9 8 9.67 8 10.5 7.33 12 6.5 12zm3-4C8.67 8 8 7.33 8 6.5S8.67 5 9.5 5s1.5.67 1.5 1.5S10.33 8 9.5 8zm5 0c-.83 0-1.5-.67-1.5-1.5S13.67 5 14.5 5s1.5.67 1.5 1.5S15.33 8 14.5 8zm3 4c-.83 0-1.5-.67-1.5-1.5S16.67 9 17.5 9s1.5.67 1.5 1.5-.67 1.5-1.5 1.5z',
        hide: 'M12 7c2.76 0 5 2.24 5 5 0 .65-.13 1.26-.36 1.83l2.92 2.92c1.51-1.26 2.7-2.89 3.43-4.75-1.73-4.39-6-7.5-11-7.5-1.4 0-2.74.25-3.98.7l2.16 2.16C10.74 7.13 11.35 7 12 7zM2 4.27l2.28 2.28.46.46A11.804 11.804 0 0 0 1 12c1.73 4.39 6 7.5 11 7.5 1.55 0 3.03-.3 4.38-.84l.42.42L19.73 22 21 20.73 3.27 3 2 4.27zM7.53 9.8l1.55 1.55c-.05.21-.08.43-.08.65 0 1.66 1.34 3 3 3 .22 0 .44-.03.65-.08l1.55 1.55c-.67.33-1.41.53-2.2.53-2.76 0-5-2.24-5-5 0-.79.2-1.53.53-2.2zm4.31-.78 3.15 3.15.02-.16c0-1.66-1.34-3-3-3l-.17.01z',
        delete: 'M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z'};
      [['details', 'Details'], ['rename', 'Rename'], ['color', 'Change Color'], ['hide', 'Hide'], ['delete', 'Delete']].forEach(([act, label]) => {
        const b = doc.createElement('button'); b.type = 'button';
        b.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true"><path d="' + icons[act] + '"/></svg><span>' + label + '</span>';
        if (act === 'delete') b.classList.add('danger');
        b.addEventListener('click', ev => { ev.stopPropagation(); closeMenu(); sendMenu('panel|' + act + '|' + ref + '|'); });
        m.appendChild(b);
      });
      doc.body.appendChild(m);
      m.style.left = Math.min(r.right - 4, win.innerWidth - 210) + 'px'; m.style.top = Math.min(r.bottom + 2, win.innerHeight - 240) + 'px';
      return;
    }
    const show = e.target.closest && e.target.closest('.pl-show');
    if (show) { e.preventDefault(); sendMenu('panel|show|' + show.dataset.show + '|'); return; }
    if (!(e.target.closest && e.target.closest('.pl-menu'))) closeMenu();
  }, true);
  doc.addEventListener('dblclick', e => {
    const name = e.target.closest && e.target.closest('.pl-name'); if (!name) return;
    e.preventDefault(); closeMenu();
    const old = name.textContent; name.contentEditable = 'true'; name.focus();
    const range = doc.createRange(); range.selectNodeContents(name); const sel = win.getSelection(); sel.removeAllRanges(); sel.addRange(range);
    let done = false;
    const finish = save => {
      if (done) return; done = true; name.contentEditable = 'false';
      const now = name.textContent.trim();
      if (!save) { name.textContent = old; return; }
      if (now !== old) sendMenu('panel|name|' + name.dataset.ref + '|' + encodeURIComponent(now));
    };
    name.addEventListener('keydown', ev => { if (ev.key === 'Enter') { ev.preventDefault(); finish(true); } else if (ev.key === 'Escape') { ev.preventDefault(); finish(false); } });
    name.addEventListener('blur', () => finish(true));
  }, true);
}
// 20-20-20 rule: after every 20 minutes of using the app, ask for a 20-second look at something 20 feet away.
// Turning that down is allowed, but after 2 refusals in a row there is a warning, and the 3rd prompt (1 hour of
// non-stop use) becomes a required 5-minute rest.
win.__keys = __KEYS__;                           // the key bindings from Settings (one group per reader)
win.__keyOf = e => {                               // a key press as a binding: 'd', 'ctrl+z', 'esc'
  let k = (e.key || '').toLowerCase(); if (k === 'escape') k = 'esc'; if (k === ' ') k = 'space';
  const m = []; if (e.ctrlKey || e.metaKey) m.push('ctrl'); if (e.altKey) m.push('alt'); if (e.shiftKey) m.push('shift');
  return m.concat(k).join('+');
};
win.__keyIs = (e, group, action, dflt) => win.__keyOf(e) === (((win.__keys || {})[group] || {})[action] || dflt);
win.__eyeCfg = __EYE_CFG__;                      // from Settings; a change reloads this script, the running timer reads the new values
if (!win.__eyeRestV2) {
  win.__eyeRestV2 = true;
  const KEY = 'sa_eye_rest', num = (k, d) => +localStorage.getItem(k) || d;
  const cfg = () => win.__eyeCfg;
  const load = () => { try { return JSON.parse(localStorage.getItem(KEY)) || null; } catch (e) { return null; } };
  const save = v => { try { localStorage.setItem(KEY, JSON.stringify(v)); } catch (e) {} };
  const interval = () => num('sa_study_interval', 1200) * 1000;       // 20 minutes
  const restLen = () => cfg().rest_seconds;                           // seconds of rest each time
  const forceLen = () => cfg().required_minutes * 60;                 // the required rest
  const maxSkips = () => cfg().max_skips;                             // skips allowed in a row
  const idleReset = () => num('sa_idle_reset', 300) * 1000;           // away 5+ minutes counts as a rest
  const fmt = n => Math.floor(n / 60) + ':' + String(n % 60).padStart(2, '0');
  let st = load(), card = null, forced = null;
  const fresh = () => ({next: Date.now() + interval(), seen: Date.now(), refused: 0, forceEnd: 0});
  if (!st || Date.now() - st.seen > idleReset()) st = fresh();
  save(st);
  const beep = () => { if (!cfg().sound) return; try { const c = new (win.AudioContext || win.webkitAudioContext)(), o = c.createOscillator(), g = c.createGain();
    o.connect(g); g.connect(c.destination); o.frequency.value = 660; g.gain.value = 0.08; o.start(); o.stop(c.currentTime + 0.25); } catch (e) {} };
  function closeCard() { if (card) { card.el.remove(); card = null; } }
  function refuse() {
    closeCard(); st.refused = (st.refused || 0) + 1; save(st);
    if (st.refused === maxSkips() && maxSkips() > 0) warn();
  }
  function warn() {
    const el = doc.createElement('div'); el.id = 'sa-rest'; el.className = 'warn';
    el.innerHTML = '<h3>Rest Warning</h3><p>You have skipped ' + maxSkips() + ' eye rest' + (maxSkips() === 1 ? '' : 's') + ' in a row. If you keep studying without a break, ' +
      'a required ' + cfg().required_minutes + '-minute rest starts at the next reminder.</p><button type="button">Understood</button>';
    doc.body.appendChild(el); card = {el, phase: 'warn'};
    el.querySelector('button').onclick = closeCard;
    setTimeout(() => { if (card && card.el === el) closeCard(); }, 15000);
  }
  function ask() {
    const el = doc.createElement('div'); el.id = 'sa-rest';
    el.innerHTML = '<h3>Eye Rest</h3><p>You have been studying for 20 minutes. Look at something 20 feet (6 meters) away for ' +
      restLen() + ' seconds?</p><div class="count" style="display:none"></div><div class="bar" style="display:none"><i></i></div>' +
      '<button type="button" class="go">Start Rest</button> <button type="button" class="no">Not Now</button>';
    doc.body.appendChild(el);
    card = {el, phase: 'ask', end: 0, done: false};
    el.querySelector('.no').onclick = () => { if (card.done) closeCard(); else refuse(); };   // Skip mid-rest counts as a refusal too
    el.querySelector('.go').onclick = () => {
      card.phase = 'rest'; card.end = Date.now() + restLen() * 1000; st.refused = 0; save(st);
      el.querySelector('p').textContent = 'Look at something 20 feet (6 meters) away.';
      el.querySelector('.count').style.display = ''; el.querySelector('.bar').style.display = '';
      el.querySelector('.go').remove(); el.querySelector('.no').textContent = 'Skip'; tick();
    };
    beep();
  }
  function force() {
    if (!st.forceEnd || st.forceEnd < Date.now() - 1000) { st.forceEnd = Date.now() + forceLen() * 1000; save(st); }
    closeCard();
    const el = doc.createElement('div'); el.id = 'sa-force';
    el.innerHTML = '<div id="sa-rest"><h3>Required Rest</h3><p>You have used the app for ' + Math.round((maxSkips() + 1) * interval() / 60000) + ' minutes without taking an eye rest. ' +
      'Step away from the screen and rest your eyes for ' + cfg().required_minutes + ' minutes.</p><div class="count"></div><div class="bar"><i></i></div>' +
      '<button type="button" disabled>Resume Studying</button></div>';
    doc.body.appendChild(el); forced = {el, done: false}; beep();
    el.querySelector('button').onclick = () => {          // the 20 minutes start again from the moment studying resumes
      el.remove(); forced = null; st = Object.assign(fresh(), {seen: Date.now()}); save(st);
    };
  }
  function tick() {
    const now = Date.now();
    if (now - st.seen > idleReset() && !card && !forced) st = fresh();          // away or asleep long enough = rested
    st.seen = now; save(st);
    if (forced) {
      const left = Math.max(0, Math.ceil((st.forceEnd - now) / 1000)), total = forceLen();
      forced.el.querySelector('.count').textContent = left ? fmt(left) : 'Done';
      forced.el.querySelector('.bar i').style.width = ((total - left) / total * 100) + '%';
      if (!left && !forced.done) {
        forced.done = true; beep(); st = Object.assign(fresh(), {seen: now}); save(st);
        forced.el.querySelector('button').disabled = false;
        forced.el.querySelector('p').textContent = 'Nice work. Your eyes are rested.';
      }
      return;
    }
    if (st.forceEnd > now) { force(); return; }                                 // a reload cannot skip the required rest
    if (!card || card.phase === 'warn') {
      if (now >= st.next) {
        st.next = now + interval(); save(st);                                  // the next prompt is 20 minutes after this one
        if (st.refused >= maxSkips()) force(); else { closeCard(); ask(); }
      }
    }
    if (card && card.phase === 'rest') {
      const left = Math.max(0, Math.ceil((card.end - now) / 1000)), total = restLen();
      card.el.querySelector('.count').textContent = card.done ? 'Done' : left;
      card.el.querySelector('.bar i').style.width = (card.done ? 100 : (total - left) / total * 100) + '%';
      if (!card.done && left === 0) {
        card.done = true; beep();
        card.el.querySelector('p').textContent = 'Nice work. Your eyes are rested.';
        card.el.querySelector('.no').textContent = 'Back to Studying';
        setTimeout(closeCard, 15000);
      }
    }
  }
  setInterval(tick, 1000);
}
// Note Reader window tabs: drag a tab to any place in the row; x closes a window; + adds one.
if (!win.__findV1) {
  win.__findV1 = true;
  let px = 0, py = 0;
  doc.addEventListener('mousemove', e => { px = e.clientX; py = e.clientY; }, true);
  doc.addEventListener('keydown', e => {
    if (!win.__keyIs(e, 'notes', 'find', 'ctrl+f')) return;
    const tag = (e.target && e.target.tagName || '').toLowerCase();
    const readers = [...doc.querySelectorAll('[class*="st-key-reader_"]')].filter(r => r.getBoundingClientRect().width > 0);
    const frames = [...doc.querySelectorAll('iframe')].filter(f => f.getBoundingClientRect().height > 200);
    const inX = r => { const b = r.getBoundingClientRect(); return px >= b.left && px <= b.right; };
    const reader = readers.find(inX), frame = frames.find(inX);
    if (!reader && !frame && !readers.length && !frames.length) return;            // nothing to search here: the browser's own find
    e.preventDefault(); e.stopPropagation();
    if (frame && (!reader || py > reader.getBoundingClientRect().bottom)) {
      frame.contentWindow.postMessage({study: 'find-open'}, '*');
    } else if (reader || readers.length) {
      const box = (reader || readers[0]).querySelector('[class*="_findbox"] button');
      if (box) { box.click(); setTimeout(() => { const i = doc.querySelector('[data-testid="stPopoverBody"] input'); if (i) { i.focus(); i.select(); } }, 250); }
    } else if (frames.length) {
      frames[0].contentWindow.postMessage({study: 'find-open'}, '*');
    }
  }, true);
}
if (!win.__switchV1) {
  win.__switchV1 = true;
  // a click on the sidebar menu or on a tab starts a switch; it ends once nothing is stale any more
  let timer = null;
  const app = () => doc.querySelector('.stApp');
  const end = () => { const a = app(); if (a) a.classList.remove('switching'); timer = null; };
  const watch = () => {
    const a = app();
    if (!a) return;
    const started = Date.now();
    const tick = () => {
      const stale = doc.querySelector('[data-testid="stMain"] [data-stale="true"]');
      if (!stale && Date.now() - started > 350 || Date.now() - started > 6000) { end(); return; }
      timer = setTimeout(tick, 120);
    };
    if (timer) clearTimeout(timer);
    timer = setTimeout(tick, 120);
  };
  doc.addEventListener('click', e => {
    const hit = e.target.closest('[class*="st-key-nav_"] button, [role="tab"]');
    const a = app();
    if (hit && a) { a.classList.add('switching'); watch(); }
  }, true);
}
if (!win.__labTabsV2) {
  win.__labTabsV2 = true;
  let dragged = null;
  const send = text => {
    const inp = doc.querySelector('.st-key-lab_tab_sink input'); if (!inp) return;
    const set = Object.getOwnPropertyDescriptor(win.HTMLInputElement.prototype, 'value').set;
    inp.focus(); set.call(inp, text + '|' + Date.now());
    inp.dispatchEvent(new win.Event('input', {bubbles: true}));
    inp.dispatchEvent(new win.KeyboardEvent('keydown', {key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true}));
    inp.blur();
  };
  doc.addEventListener('click', e => {
    const x = e.target.closest && e.target.closest('[data-lab-close]');
    if (x) { e.preventDefault(); send('close:' + x.dataset.labClose); return; }
    if (e.target.closest && e.target.closest('[data-lab-add]')) send('add:');
  }, true);
  doc.addEventListener('dragstart', e => {
    const t = e.target.closest && e.target.closest('.lab-tab'); if (!t) return;
    dragged = t; t.classList.add('dragging'); e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', t.dataset.labTab);
  });
  doc.addEventListener('dragover', e => {
    const t = e.target.closest && e.target.closest('.lab-tab'); if (!t || !dragged) return;
    e.preventDefault(); doc.querySelectorAll('.lab-tab.drop-target').forEach(x => x.classList.remove('drop-target'));
    if (t !== dragged) t.classList.add('drop-target');
  });
  doc.addEventListener('drop', e => {
    const t = e.target.closest && e.target.closest('.lab-tab'); if (!t || !dragged) return;
    e.preventDefault();
    const from = dragged; dragged = null;             // one drop = one move
    if (t === from) return;
    const order = [...doc.querySelectorAll('.lab-tab')].map(x => x.dataset.labTab);
    const i = order.indexOf(from.dataset.labTab), j = order.indexOf(t.dataset.labTab);
    order.splice(i, 1); order.splice(j, 0, from.dataset.labTab);      // the dragged tab takes the place it is dropped on
    send('order:' + order.join(','));
  });
  doc.addEventListener('dragend', e => {
    const t = dragged; dragged = null;
    doc.querySelectorAll('.lab-tab').forEach(x => x.classList.remove('dragging', 'drop-target'));
    if (!t || doc.querySelectorAll('.lab-tab').length < 2) return;
    // dropped outside this window (screen coordinates beyond its frame) = tear the tab off into a new window
    const out = e.screenX < win.screenX - 4 || e.screenY < win.screenY - 4 ||
                e.screenX > win.screenX + win.outerWidth + 4 || e.screenY > win.screenY + win.outerHeight + 4;
    if (!out || (e.screenX === 0 && e.screenY === 0)) return;
    const wid = t.dataset.labTab;
    send('detach:' + wid);
    setTimeout(() => {
      const url = win.location.origin + win.location.pathname + '?detached=' + encodeURIComponent(wid);
      if (win.pywebview && win.pywebview.api && win.pywebview.api.open_window) win.pywebview.api.open_window(url);
      else win.open(url, '_blank', 'popup=yes,width=1000,height=820');
    }, 900);
  });
}
// The menu bar: the key set in Settings (m) hides it, or shows it again. Notes are in frames: they call this too.
if (!win.__menuV1) {
  win.__menuV1 = true;
  win.__saMenuToggle = () => { const b = doc.querySelector('.st-key-menu_toggle_hidden button'); if (b) b.click(); };
  doc.addEventListener('keydown', e => {
    const t = e.target, tag = (t && t.tagName || '').toLowerCase();
    if (tag === 'input' || tag === 'textarea' || tag === 'select' || (t && t.isContentEditable)) return;      // not while typing in a box
    if (!win.__keyIs(e, 'app', 'menu', 'm')) return;
    e.preventDefault(); win.__saMenuToggle();
  }, true);
}
// F2: a screenshot of the app window is saved in the data folder (screenshots). Notes call this too.
if (!win.__shotV1) {
  win.__shotV1 = true;
  win.__saScreenshot = () => { const b = doc.querySelector('.st-key-screenshot_hidden button'); if (b) b.click(); };
  doc.addEventListener('keydown', e => {
    if (e.key !== 'F2' || e.ctrlKey || e.altKey || e.shiftKey || e.metaKey) return;
    e.preventDefault(); win.__saScreenshot();
  }, true);
}
// F5: the page is drawn again with fresh data and you stay where you are; Ctrl + F5 (or Shift + F5) loads the whole page again. Notes call this too.
if (!win.__refreshV1) {
  win.__refreshV1 = true;
  win.__saRefresh = () => { const b = doc.querySelector('.st-key-refresh_hidden button'); if (b) b.click(); };
  win.__saReload = () => win.location.reload();
  doc.addEventListener('keydown', e => {
    if (e.key !== 'F5' || e.altKey) return;
    e.preventDefault();
    if (e.ctrlKey || e.shiftKey || e.metaKey) win.__saReload(); else win.__saRefresh();
  }, true);
}
// Menu keys: while the menu bar is shown, a letter opens a page: H Home, A Calendar, L Library, N Note Reader, C Courses, S Settings.
// Not while typing, not with a modifier key, and not in drawing mode (d p h e are the pen keys there).
if (!win.__menuKeysV1) {
  win.__menuKeysV1 = true;
  const PAGE_OF = {h: 'Home', a: 'Calendar', l: 'Library', n: 'Note Reader', c: 'Courses', s: 'Settings'};
  win.__saMenuKey = e => {
    if (e.ctrlKey || e.altKey || e.metaKey || e.shiftKey || !e.key || e.key.length !== 1) return false;
    const page = PAGE_OF[e.key.toLowerCase()]; if (!page) return false;
    const t = e.target, tag = (t && t.tagName || '').toLowerCase();
    if (tag === 'input' || tag === 'textarea' || tag === 'select' || (t && t.isContentEditable)) return false;
    if (doc.querySelector('.an-on')) return false;
    const rail = doc.querySelector('section[data-testid="stSidebar"] > div:first-child');
    if (!rail || rail.getBoundingClientRect().width < 30) return false;                      // the menu bar is hidden
    const nameOf = b => ([...((b.closest('[class*="st-key-"]') || {}).classList || [])].find(c => c.startsWith('st-key-nav_')) || '').slice(11).replace(/-/g, ' ');     // "Note Reader"
    const button = [...rail.querySelectorAll('button')].find(b => nameOf(b) === page);
    if (!button) return false;
    button.click();
    return true;
  };
  doc.addEventListener('keydown', e => { if (win.__saMenuKey(e)) e.preventDefault(); }, true);
}
// F11: full screen on and off in the desktop window (in a browser, F11 is the browser's own). Notes are in frames: they call this too.
if (!win.__fsV1) {
  win.__fsV1 = true;
  const can = () => !!(win.pywebview && win.pywebview.api && win.pywebview.api.toggle_fullscreen);
  win.__saFullscreen = () => { if (can()) win.pywebview.api.toggle_fullscreen(); };
  doc.addEventListener('keydown', e => {
    if (e.key !== 'F11' || e.ctrlKey || e.altKey || e.shiftKey || e.metaKey || !can()) return;
    e.preventDefault(); win.__saFullscreen();
  }, true);
}
// PDF reader, every view: drag the page to move around, Ctrl + wheel (or pinch) to zoom, and keep the place when the zoom changes.
if (!win.__rdPanV1) {
  win.__rdPanV1 = true;
  const POS = win.__rdPos = win.__rdPos || {};
  const css = doc.createElement('style');
  css.textContent = '.rd-scroll.rd-pannable{cursor:grab}.rd-panning,.rd-panning *{cursor:grabbing !important;user-select:none !important}';
  doc.head.appendChild(css);
  // a reader whose zoom has just changed (the page element is updated in place, or drawn again): scroll so the same point stays in the middle
  win.__rdPanInit = c => {
    if (!c.dataset.key) return;
    const key = c.dataset.key;
    const rec = () => { POS[key] = {zoom: c._zoom, mode: c.dataset.mode, goto: c.dataset.goto,
                  fx: (c.scrollLeft + c.clientWidth / 2) / (c.scrollWidth || 1), fy: (c.scrollTop + c.clientHeight / 2) / (c.scrollHeight || 1)}; };
    const fresh = !c._pan;
    if (fresh) {                                                            // first time this element is seen
      c._pan = true; c._zoom = null; c._quiet = 0;
      c.addEventListener('scroll', () => { if (c._zoom === c.dataset.zoom && Date.now() > c._quiet) rec(); });
    }
    if (c._zoom === c.dataset.zoom) return;
    const s = POS[key], dz = c.dataset.zoom;
    if (s && s.mode === c.dataset.mode && s.goto === c.dataset.goto && (s.zoom !== dz || (fresh && s.at && Date.now() - s.at < 6000))) {
      c.scrollLeft = s.fx * c.scrollWidth - c.clientWidth / 2;
      c.scrollTop = s.fy * c.scrollHeight - c.clientHeight / 2;
      c._applied = c.dataset.token + ':' + c.dataset.goto;               // the scrolling view must not jump back to the top of the page
      c._zoom = dz;
      c._quiet = Date.now() + 1200;                                         // the scrolling this causes is not the user's
      POS[key] = {zoom: dz, mode: s.mode, goto: s.goto, fx: s.fx, fy: s.fy, at: Date.now()};     // the reader may be drawn a second time while it updates: restore again
      setTimeout(() => { if (c.isConnected) rec(); }, 1300);
    } else c._zoom = dz;
  };
  setInterval(() => {
    doc.querySelectorAll('.rd-scroll').forEach(c => {
      win.__rdPanInit(c);
      c.classList.toggle('rd-pannable', c.scrollWidth > c.clientWidth + 2 || c.scrollHeight > c.clientHeight + 2);
    });
  }, 250);
  let pan = null, swallow = false;
  doc.addEventListener('mousedown', e => { if (e.button === 1 && e.target.closest && e.target.closest('.rd-scroll')) e.preventDefault(); }, true);   // no auto-scroll circle
  doc.addEventListener('dragstart', e => { if (e.target.closest && e.target.closest('.rd-scroll')) e.preventDefault(); }, true);      // the page image is moved by panning, not dragged away
  doc.addEventListener('pointerdown', e => {
    if (e.button !== 0 && e.button !== 1) return;
    const c = e.target.closest && e.target.closest('.rd-scroll'); if (!c) return;
    if (e.target.closest('.an-barwrap, .an-bar, button, input, textarea, select, a, .rd-live')) return;
    if (e.button === 0 && c.classList.contains('an-on')) return;           // drawing mode: the pen has the left button (the middle button still moves the page)
    if (c.scrollWidth <= c.clientWidth + 2 && c.scrollHeight <= c.clientHeight + 2) return;
    pan = {c, x: e.clientX, y: e.clientY, l: c.scrollLeft, t: c.scrollTop, moved: false};
  }, true);
  doc.addEventListener('pointermove', e => {
    if (!pan) return;
    const dx = e.clientX - pan.x, dy = e.clientY - pan.y;
    if (!pan.moved && Math.hypot(dx, dy) < 5) return;
    if (!pan.moved) { pan.moved = true; pan.c.classList.add('rd-panning'); }
    pan.c.scrollLeft = pan.l - dx; pan.c.scrollTop = pan.t - dy;
    e.preventDefault();
  }, true);
  const endPan = () => {
    if (!pan) return;
    pan.c.classList.remove('rd-panning');
    if (pan.moved) { swallow = true; setTimeout(() => { swallow = false; }, 0); }       // the click that ends a drag is not a click on what is under the pointer
    pan = null;
  };
  doc.addEventListener('pointerup', endPan, true);
  doc.addEventListener('pointercancel', endPan, true);
  doc.addEventListener('click', e => { if (swallow) { e.stopPropagation(); e.preventDefault(); } }, true);
  doc.addEventListener('wheel', e => {
    if (!(e.ctrlKey || e.metaKey)) return;                                   // Ctrl + wheel, and a trackpad pinch (which arrives as Ctrl + wheel)
    const c = e.target.closest && e.target.closest('.rd-scroll'); if (!c || !c.dataset.key) return;
    e.preventDefault();
    const now = Date.now(); if (now - (win.__rdWheel || 0) < 250) return; win.__rdWheel = now;
    const k = c.dataset.key.replace(/[^A-Za-z0-9_-]/g, '-');
    const b = doc.querySelector('[class*="st-key-' + k + (e.deltaY < 0 ? '_zin' : '_zout') + '"] button'); if (b) b.click();
  }, {passive: false, capture: true});
}
// Scrolling PDF view: jump to the requested page, keep the page badge current, retry page images that are not ready.
if (!win.__rdScrollV1) {
  win.__rdScrollV1 = true;
  doc.addEventListener('error', e => {
    const im = e.target;
    if (!im || im.tagName !== 'IMG' || !im.closest || !im.closest('.rd-pg')) return;
    const n = (+im.dataset.retry || 0) + 1;
    if (n < 80) { im.dataset.retry = n; setTimeout(() => { im.src = im.src.split('?')[0] + '?r=' + n; }, 600); }
  }, true);
  const current = c => {
    const pgs = c.querySelectorAll('.rd-pg'), line = c.scrollTop + c.clientHeight * 0.3;
    let n = 1; for (let i = 0; i < pgs.length; i++) { if (pgs[i].offsetTop + pgs[i].offsetHeight > line) { n = i + 1; break; } n = i + 1; }
    return n;
  };
  setInterval(() => {
    doc.querySelectorAll('.rd-cont').forEach(c => {
      if (win.__rdPanInit) win.__rdPanInit(c);                                        // restores the place after a zoom before the page jump below can run
      if (!c._hooked) {
        c._hooked = true;
        c.addEventListener('scroll', () => {
          if (c._raf) return;
          c._raf = requestAnimationFrame(() => { c._raf = 0; const b = c.querySelector('.rd-live');
            if (b) b.textContent = 'Page ' + current(c) + ' / ' + c.dataset.total; });
        });
      }
      if (c._applied !== c.dataset.token + ':' + c.dataset.goto) {
        const t = c.querySelector('#rdp-' + c.dataset.key + '-' + c.dataset.goto);
        if (t) { c.scrollTop = t.offsetTop - 12; c._applied = c.dataset.token + ':' + c.dataset.goto; }
      }
    });
    doc.querySelectorAll('.rd-err.active, .rd-find.active').forEach(el => {                       // the place clicked in a note, a helper or an explanation: bring it to the middle
      if (!el._seen) { el._seen = true; el.scrollIntoView({block: 'center', inline: 'nearest'}); }   // after the page jump above, which would undo it
    });
  }, 250);
}
// Note Reader: drag the border between two windows to change their widths (remembered); double click a border to share the width equally.
// The widths live in the browser (localStorage, keyed by the windows' ids) and are applied here on every tick, so they do not depend on how fast
// the app redraws; the app gets a copy too (hidden box) as a fallback.
if (!win.__labResizeV2) {
  win.__labResizeV2 = true;
  const STORE = 'sa_lab_widths';
  const columns = () => {
    const b = doc.querySelector('[data-testid="stHorizontalBlock"]:has([class*="st-key-lab_pane_"])');
    return b ? [...b.children].filter(c => c.matches('[data-testid="stColumn"]')) : [];
  };
  const idOf = col => { const m = (col.querySelector('[class*="st-key-lab_pane_"]') || {className: ''}).className.match(/st-key-lab_pane_([A-Za-z0-9_]+)/); return m ? m[1] : null; };
  const load = () => { try { return JSON.parse(localStorage.getItem(STORE)) || null; } catch (e) { return null; } };
  const save = v => { try { if (v) localStorage.setItem(STORE, JSON.stringify(v)); else localStorage.removeItem(STORE); } catch (e) {} };
  const CSS = ['flex', 'width', 'min-width'];
  let drag = null, applied = '';
  // keep the remembered widths on the windows (the app redraws them with its own widths from time to time)
  const apply = () => {
    if (drag) return;
    const cs = columns(); if (!cs.length) return;
    const ids = cs.map(idOf), st = load();
    const strip = doc.querySelector('.lab-tabs');
    if (!st || st.ids.join() !== ids.join()) {                       // other windows than the remembered ones: the app's widths apply
      if (st) save(null);
      cs.forEach(c => CSS.forEach(k => c.style.removeProperty(k))); applied = '';
      return;
    }
    cs.forEach((c, k) => { const f = st.w[k] + ' 1 0px';
      if (c.style.flex !== f) { c.style.flex = f; c.style.width = '0'; c.style.minWidth = '0'; } });
    if (strip) { const g = st.w.map(w => 'minmax(0,' + w + 'fr)').join(' '); if (strip.style.gridTemplateColumns !== g) strip.style.gridTemplateColumns = g; }
  };
  setInterval(apply, 120);
  // send the relative widths to the app (kept as a copy)
  const send = (cs, ws) => {
    const sink = doc.querySelector('.st-key-lab_tab_sink input'); if (!sink) return;
    const parts = cs.map((c, k) => idOf(c) + '=' + ws[k].toFixed(3)).filter(x => !x.startsWith('null'));
    const set = Object.getOwnPropertyDescriptor(win.HTMLInputElement.prototype, 'value').set;
    sink.focus(); set.call(sink, 'widths:' + parts.join(',') + '|' + Date.now());
    sink.dispatchEvent(new win.Event('input', {bubbles: true}));
    sink.dispatchEvent(new win.KeyboardEvent('keydown', {key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true}));
    sink.blur();
  };
  const remember = (cs, widths) => {
    const avg = widths.reduce((t, w) => t + w, 0) / widths.length, ws = widths.map(w => Math.round(w / avg * 1000) / 1000);
    save({ids: cs.map(idOf), w: ws}); apply(); setTimeout(() => send(cs, ws), 60);
  };
  doc.addEventListener('mousedown', e => {
    const cs = columns();
    for (let i = 0; i < cs.length - 1; i++) {
      const r = cs[i].getBoundingClientRect(), n = cs[i + 1].getBoundingClientRect();
      if (e.clientX >= r.right - 4 && e.clientX <= n.left + 4 && e.clientY >= r.top && e.clientY <= r.bottom) {
        drag = {i, x: e.clientX, wl: r.width, wr: n.width, cs};
        doc.documentElement.classList.add('lab-resizing'); e.preventDefault(); return;
      }
    }
  }, true);
  doc.addEventListener('mousemove', e => {
    if (!drag) return;
    const total = drag.wl + drag.wr, min = total * 0.12;
    const nl = Math.min(total - min, Math.max(min, drag.wl + e.clientX - drag.x)), nr = total - nl;
    const set = (el, w) => { el.style.flex = '0 0 ' + w + 'px'; el.style.width = w + 'px'; el.style.minWidth = '0'; };
    set(drag.cs[drag.i], nl); set(drag.cs[drag.i + 1], nr);
    const strip = doc.querySelector('.lab-tabs');                      // the tabs above follow the windows
    if (strip) strip.style.gridTemplateColumns = drag.cs.map(c => 'minmax(0,' + c.getBoundingClientRect().width + 'fr)').join(' ');
  }, true);
  doc.addEventListener('mouseup', () => {
    if (!drag) return;
    const d = drag; drag = null; doc.documentElement.classList.remove('lab-resizing');
    remember(d.cs, d.cs.map(c => c.getBoundingClientRect().width));
  }, true);
  // a double click on the border between two windows shares the width equally between all of them
  doc.addEventListener('dblclick', e => {
    const cs = columns();
    for (let i = 0; i < cs.length - 1; i++) {
      const r = cs[i].getBoundingClientRect(), n = cs[i + 1].getBoundingClientRect();
      if (e.clientX >= r.right - 6 && e.clientX <= n.left + 6 && e.clientY >= r.top && e.clientY <= r.bottom) {
        e.preventDefault(); drag = null; doc.documentElement.classList.remove('lab-resizing');
        remember(cs, cs.map(() => 1));
        return;
      }
    }
  }, true);
}
// Note Reader full screen: Esc leaves it (the note's own page does the same while the pointer or focus is inside the note).
if (!win.__fullEscV1) {
  win.__fullEscV1 = true;
  doc.addEventListener('keydown', e => {
    if (e.defaultPrevented || !win.__keyIs(e, 'notes', 'leave_full', 'esc')) return;
    const b = doc.querySelector('.st-key-lab_full_close button'); if (b) b.click();
  });
}
// Drawing on a homework or exam PDF (pages with data-annot): pen, highlighter and eraser over each page, saved as they are drawn, Clear All.
// Strokes are kept as fractions of the page, so they stay in place at any zoom (see annotations.py).
if (!win.__annotV1) {
  win.__annotV1 = true;
  const S = {on: false, tool: 'pen', col: {pen: '#e5484d', hl: '#ffd500'}, undo: []};
  const PEN = ['#e5484d', '#2f6fe0', '#1baf7a', '#111111', '#f08a24'], HL = ['#ffd500', '#7ee08a', '#ff8fd0', '#6fd3ff'];
  const WID = {pen: 0.0028, hl: 0.019}, ERASE_PX = 14;
  const ICON = {
    pen: '<svg viewBox="0 0 24 24"><path d="M4 20l1-4L16 5l3 3L8 19z"/><path d="M14 7l3 3"/></svg>',
    hl: '<svg viewBox="0 0 24 24"><path d="M9 14l6-9 4 3-6 9z"/><path d="M9 14l-1 4 4-1"/><path d="M4 21h7"/></svg>',
    er: '<svg viewBox="0 0 24 24"><path d="M7 21h12"/><path d="M5 16l8-9 6 5-6 7H8z"/></svg>',
    undo: '<svg viewBox="0 0 24 24"><path d="M9 14L4 9l5-5"/><path d="M4 9h10a6 6 0 0 1 0 12h-3"/></svg>',
    draw: '<svg viewBox="0 0 24 24"><path d="M4 20l1-4L16 5l3 3L8 19z"/></svg>'};
  const mk = (tag, cls, html) => { const e = doc.createElement(tag); if (cls) e.className = cls; if (html) e.innerHTML = html; return e; };
  const send = text => {
    const inp = doc.querySelector('.st-key-annot_sink input'); if (!inp) return;
    const set = Object.getOwnPropertyDescriptor(win.HTMLInputElement.prototype, 'value').set;
    inp.focus(); set.call(inp, text + '|' + Date.now());
    inp.dispatchEvent(new win.Event('input', {bubbles: true}));
    inp.dispatchEvent(new win.KeyboardEvent('keydown', {key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true}));
    inp.blur();
  };
  const save = (c, pn) => send('annot:' + c.dataset.annot + ':' + pn + ':' + JSON.stringify(c._st[pn] || []));
  const pathOf = pts => pts.map((p, i) => (i ? 'L' : 'M') + p[0].toFixed(4) + ' ' + p[1].toFixed(4)).join('');
  const NS = 'http://www.w3.org/2000/svg';
  function boxes(s) {                               // a highlighter stroke: one box per line of text
    const g = doc.createElementNS(NS, 'g'); g.setAttribute('class', 'hl'); g.style.fill = s.c;
    s.r.forEach(q => {
      const e = doc.createElementNS(NS, 'rect');
      e.setAttribute('x', q[0]); e.setAttribute('y', q[1]); e.setAttribute('width', Math.max(0, q[2] - q[0])); e.setAttribute('height', Math.max(0, q[3] - q[1]));
      g.appendChild(e);
    });
    return g;
  }
  function paint(layer, c) {                       // draw the strokes of a page into its layer
    const pn = layer.dataset.pn, w = layer.parentElement.clientWidth || 1;
    layer.innerHTML = '';
    (c._st[pn] || []).forEach(s => {
      if (s.t === 'hr') { layer.appendChild(boxes(s)); return; }
      const p = doc.createElementNS(NS, 'path');
      p.setAttribute('d', pathOf(s.p) + (s.p.length === 1 ? 'l0.0001 0' : '')); p.setAttribute('class', s.t);
      p.style.stroke = s.c; p.style.strokeWidth = Math.max(1, s.w * w) + 'px'; layer.appendChild(p);
    });
    layer._w = w; layer._n = (c._st[pn] || []).length;
  }
  function wordsOf(c, pn) {                        // the words of a page as boxes (fractions of the page), in reading order
    if (!c._wd) { try { c._wd = JSON.parse(c.dataset.words || '{}'); } catch (e) { c._wd = {}; } c._wc = {}; }
    if (!c._wc[pn]) {
      const out = [];
      (c._wd[pn] || []).forEach((ln, li) => { for (let k = 0; k + 1 < ln[2].length; k += 2) out.push({x0: ln[2][k], x1: ln[2][k + 1], y0: ln[0], y1: ln[1], li}); });
      c._wc[pn] = out;
    }
    return c._wc[pn];
  }
  function pick(words, x, y, r) {                  // the word nearest to a point (within 40 px): its index, or -1
    let best = -1, bd = 40;
    words.forEach((w, i) => {
      const d = Math.hypot(Math.max(w.x0 - x, 0, x - w.x1) * r.width, Math.max(w.y0 - y, 0, y - w.y1) * r.height);
      if (d < bd) { bd = d; best = i; }
    });
    return best;
  }
  function follow(words, a, b) {                   // from word a to word b: one box per line of text, as wide as the words on that line
    const lo = Math.min(a, b), hi = Math.max(a, b), rows = [];
    for (let i = lo; i <= hi; i++) {
      const w = words[i], last = rows[rows.length - 1];
      if (last && last.li === w.li) { last.x1 = Math.max(last.x1, w.x1); last.x0 = Math.min(last.x0, w.x0); }
      else rows.push({li: w.li, x0: w.x0, x1: w.x1, y0: w.y0, y1: w.y1});
    }
    return rows.map(q => [q.x0, q.y0, q.x1, q.y1]);
  }
  function wire(layer, c) {
    let cur = null, live = null, changed = false;
    const at = e => { const r = layer.getBoundingClientRect(); return [(e.clientX - r.left) / r.width, (e.clientY - r.top) / r.height, r]; };
    layer.addEventListener('pointerdown', e => {
      if (!S.on || e.pointerType === 'touch' || e.button > 0) return;
      e.preventDefault(); layer.setPointerCapture(e.pointerId);
      const [x, y, r] = at(e), pn = layer.dataset.pn;
      if (S.tool === 'er') { cur = {erase: true}; changed = false; erase(layer, c, x, y, r); return; }
      if (S.tool === 'hl') {                       // the highlighter follows the lines of text
        const words = wordsOf(c, pn), from = pick(words, x, y, r);
        if (words.length && from < 0) return;      // not near any text: nothing to highlight
        cur = {t: 'hr', c: S.col.hl, from, words, x0: x, y0: y, r: []};
        return;
      }
      cur = {t: S.tool, c: S.col[S.tool], w: WID[S.tool], p: [[x, y]]};
      live = doc.createElementNS(NS, 'path'); live.setAttribute('class', cur.t);
      live.style.stroke = cur.c; live.style.strokeWidth = Math.max(1, cur.w * r.width) + 'px'; layer.appendChild(live);
    });
    layer.addEventListener('pointermove', e => {
      if (!cur) return;
      const [x, y, r] = at(e);
      if (cur.erase) { erase(layer, c, x, y, r); return; }
      if (cur.t === 'hr') {
        if (cur.words.length) { const to = pick(cur.words, x, y, r); if (to < 0) return; cur.r = follow(cur.words, cur.from, to); }
        else { const h = WID.hl * r.width / r.height; cur.r = [[Math.min(cur.x0, x), cur.y0 - h / 2, Math.max(cur.x0, x), cur.y0 + h / 2]]; }   // a scan: a straight band
        if (live) live.remove();
        live = boxes({c: cur.c, r: cur.r}); live.style.opacity = 0.45; layer.appendChild(live);
        return;
      }
      const last = cur.p[cur.p.length - 1];
      if (Math.hypot((x - last[0]) * r.width, (y - last[1]) * r.height) < 1.2) return;
      cur.p.push([x, y]); live.setAttribute('d', pathOf(cur.p));
    });
    const up = () => {
      if (!cur) return;
      const pn = layer.dataset.pn;
      if (cur.erase) { if (changed) save(c, pn); cur = null; return; }
      const rnd = v => Math.round(v * 10000) / 10000;
      let stroke = null;
      if (cur.t === 'hr') { if (cur.r.length) stroke = {t: 'hr', c: cur.c, r: cur.r.map(q => q.map(rnd))}; }
      else stroke = {t: cur.t, c: cur.c, w: cur.w, p: cur.p.map(p => [rnd(p[0]), rnd(p[1])])};
      cur = null; live = null;
      if (!stroke) { paint(layer, c); return; }
      (c._st[pn] = c._st[pn] || []).push(stroke); S.undo.push({c, pn, add: stroke});
      paint(layer, c); save(c, pn);
    };
    layer.addEventListener('pointerup', up); layer.addEventListener('pointercancel', up);
    function erase(layer, c, x, y, r) {            // remove every drawing that has a point (or a highlighted box) near the eraser
      const pn = layer.dataset.pn, keep = [], gone = [], pad = ERASE_PX / 2;
      const hit = s => s.t === 'hr'
        ? s.r.some(q => x * r.width >= q[0] * r.width - pad && x * r.width <= q[2] * r.width + pad && y * r.height >= q[1] * r.height - pad && y * r.height <= q[3] * r.height + pad)
        : s.p.some(p => Math.hypot((p[0] - x) * r.width, (p[1] - y) * r.height) < ERASE_PX);
      (c._st[pn] || []).forEach(s => (hit(s) ? gone : keep).push(s));
      if (gone.length) { c._st[pn] = keep; S.undo.push({c, pn, del: gone}); changed = true; paint(layer, c); }
    }
  }
  const DEF = {draw: 'd', pen: 'p', highlighter: 'h', eraser: 'e', undo: 'ctrl+z', leave: 'esc'};
  const kb = a => ((win.__keys || {}).reader || {})[a] || DEF[a];
  const syncAll = () => doc.querySelectorAll('[data-annot]').forEach(c => c._sync && c._sync());
  doc.addEventListener('keydown', e => {           // shortcuts (set in Settings); not while typing in a box
    if (!doc.querySelector('[data-annot]')) return;
    const t = e.target, tag = (t && t.tagName || '').toLowerCase();
    if (tag === 'input' || tag === 'textarea' || tag === 'select' || (t && t.isContentEditable)) return;
    const is = a => win.__keyIs(e, 'reader', a, DEF[a]);
    if (is('draw')) { e.preventDefault(); S.on = !S.on; syncAll(); }
    else if (S.on && is('leave')) { e.preventDefault(); S.on = false; syncAll(); }
    else if (S.on && is('undo')) { e.preventDefault(); undoLast(); }
    else if (S.on && is('pen')) { S.tool = 'pen'; syncAll(); }
    else if (S.on && is('highlighter')) { S.tool = 'hl'; syncAll(); }
    else if (S.on && is('eraser')) { S.tool = 'er'; syncAll(); }
  }, true);
  function bar(c) {                                // the toolbar at the top left of the reader
    const wrap = mk('div', 'an-barwrap'), b = mk('div', 'an-bar'); wrap.appendChild(b);
    const btn = (html, title, fn, cls) => { const e = mk('button', cls || '', html); e.type = 'button'; e.title = title; e.onclick = ev => { ev.stopPropagation(); fn(); sync(); }; return e; };
    const toggle = btn(ICON.draw + '<span>Draw</span>', 'draw on the pages (' + kb('draw') + '). drawings are saved automatically', () => { S.on = !S.on; });
    const tools = mk('span', ''); tools.style.display = 'contents';
    const pen = btn(ICON.pen + '<span>Pen</span>', 'pen (' + kb('pen') + ')', () => { S.tool = 'pen'; });
    const hl = btn(ICON.hl + '<span>Highlighter</span>', 'highlighter (' + kb('highlighter') + '): drag across text and it highlights the lines', () => { S.tool = 'hl'; });
    const er = btn(ICON.er + '<span>Eraser</span>', 'eraser (' + kb('eraser') + '): rub over a drawing to remove it', () => { S.tool = 'er'; });
    const sw = mk('span', ''); sw.style.display = 'contents';
    const undo = btn(ICON.undo + '<span>Undo</span>', 'undo the last drawing or erase (' + kb('undo') + ')', () => undoLast());
    const clear = btn('<span>Clear All</span>', 'remove every drawing from this pdf', () => clearAll(c));
    [pen, hl, er, mk('span', 'sep'), sw, mk('span', 'sep'), undo, clear].forEach(e => tools.appendChild(e));
    b.appendChild(toggle); b.appendChild(tools);
    function sync() {
      c.classList.toggle('an-on', S.on); toggle.classList.toggle('act', S.on); tools.style.display = S.on ? 'contents' : 'none';
      pen.classList.toggle('act', S.tool === 'pen'); hl.classList.toggle('act', S.tool === 'hl'); er.classList.toggle('act', S.tool === 'er');
      sw.innerHTML = ''; sw.style.display = S.tool === 'er' ? 'none' : 'contents';
      (S.tool === 'hl' ? HL : PEN).forEach(col => {
        const s = mk('button', 'sw' + (S.col[S.tool] === col ? ' act' : '')); s.type = 'button'; s.style.background = col; s.title = 'color';
        s.onclick = ev => { ev.stopPropagation(); S.col[S.tool] = col; sync(); }; sw.appendChild(s);
      });
    }
    c._sync = sync; sync(); c.insertBefore(wrap, c.firstChild);
  }
  function undoLast() {
    const op = S.undo.pop(); if (!op || !op.c.isConnected) return;
    const list = op.c._st[op.pn] = op.c._st[op.pn] || [];
    if (op.add) { const i = list.indexOf(op.add); if (i >= 0) list.splice(i, 1); } else list.push(...op.del);
    op.c.querySelectorAll('.an-layer').forEach(l => { if (l.dataset.pn === op.pn) paint(l, op.c); });
    send('annot:' + op.c.dataset.annot + ':' + op.pn + ':' + JSON.stringify(list));
  }
  function clearAll(c) {
    if (!win.confirm('Clear all drawings on this PDF? This cannot be undone.')) return;
    c._st = {}; S.undo = S.undo.filter(o => o.c !== c);
    c.querySelectorAll('.an-layer').forEach(l => paint(l, c));
    send('annotclear:' + c.dataset.annot);
  }
  setInterval(() => {
    doc.querySelectorAll('[data-annot]').forEach(c => {
      if (!c._st) {                                 // a new reader: load its drawings and add the toolbar
        try { c._st = JSON.parse(c.dataset.strokes || '{}'); } catch (e) { c._st = {}; }
        bar(c);
      } else if (!c.querySelector('.an-barwrap')) bar(c);
      c.querySelectorAll('.rd-pg, .rd-pagewrap').forEach(pg => {
        let layer = pg.querySelector(':scope > .an-layer');
        if (!layer) {
          if (getComputedStyle(pg).position === 'static') pg.style.position = 'relative';
          layer = doc.createElementNS('http://www.w3.org/2000/svg', 'svg');
          layer.setAttribute('class', 'an-layer'); layer.setAttribute('viewBox', '0 0 1 1'); layer.setAttribute('preserveAspectRatio', 'none');
          layer.dataset.pn = pg.dataset.pn; pg.appendChild(layer); wire(layer, c); paint(layer, c);
        } else if (layer._w !== pg.clientWidth) paint(layer, c);       // zoomed: stroke widths follow the page
      });
    });
  }, 400);
}
// Library: drop a pdf or html file on the + tile to add it. The Add File window opens as it does on a click and the file is handed to its uploader.
if (!win.__libDropV1) {
  win.__libDropV1 = true;
  const tile = e => e.target.closest && e.target.closest('.lib-add');
  const hasFiles = e => e.dataTransfer && [...(e.dataTransfer.types || [])].includes('Files');
  doc.addEventListener('dragover', e => { const t = tile(e); if (t && hasFiles(e)) { e.preventDefault(); t.classList.add('drop'); } });
  doc.addEventListener('dragleave', e => { const t = tile(e); if (t) t.classList.remove('drop'); });
  doc.addEventListener('drop', e => {
    const t = tile(e); if (!t) return;
    e.preventDefault(); t.classList.remove('drop');
    const file = [...e.dataTransfer.files].find(f => /[.](pdf|html?)$/i.test(f.name)); if (!file) return;
    t.click();                                           // opens the Add File window
    let tries = 0;
    const timer = setInterval(() => {
      const inp = doc.querySelector('[role="dialog"] input[type="file"]');
      if (!inp && ++tries < 80) return;
      clearInterval(timer); if (!inp) return;
      const dt = new win.DataTransfer(); dt.items.add(file);
      inp.files = dt.files; inp.dispatchEvent(new win.Event('change', {bubbles: true}));
    }, 150);
  });
}
// Library cards: pass "action:id" to the hidden box (open the file, its Edit window, or the add window).
if (!win.__libNavV1) {
  win.__libNavV1 = true;
  doc.addEventListener('click', e => {
    const a = e.target.closest && e.target.closest('[data-lib-act]');
    if (!a) return;
    const inp = doc.querySelector('.st-key-lib_sink input'); if (!inp) return;
    const set = Object.getOwnPropertyDescriptor(win.HTMLInputElement.prototype, 'value').set;
    inp.focus(); set.call(inp, a.dataset.libAct + '|' + Date.now());
    inp.dispatchEvent(new win.Event('input', {bubbles: true}));
    inp.dispatchEvent(new win.KeyboardEvent('keydown', {key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true}));
    inp.blur();
  }, true);
}
</script>""".replace("__PERF__", json.dumps(settings.get_performance())).replace("__EYE_CFG__", json.dumps(settings.get_eye_rest())).replace("__KEYS__", json.dumps(settings.get_keys())), height=0)

if st.query_params.get("detached"):          # a Note Reader window dragged out into its own window
    lab_view.render_detached(st.query_params["detached"])
    st.stop()

st.session_state.setdefault("page", "Home")
tutorial.tour_before()                          # the guided tour: its Back / Next / Skip, and the page of its step (before the menu is drawn)
st.session_state.setdefault("mode", "Detailed")
st.session_state.setdefault("pdf_page", 1)

# ---- Back / forward navigation: the app keeps its own history of (page, open course, open file) ----
st.session_state.setdefault("nav_history", [])
st.session_state.setdefault("nav_forward", [])       # pages left by going back, newest last
if st.button("Screenshot", key="screenshot_hidden"):  # clicked by F2 (hidden by CSS): a picture of the app window is saved in the data folder
    from desktop import screenshot
    try:
        st.toast(f"Screenshot saved in {screenshot.FOLDER}", icon=":material/photo_camera:")
        screenshot.take()
    except Exception as e:
        st.toast(f"The screenshot could not be saved: {e}", icon=":material/error:")
if st.button("Refresh", key="refresh_hidden"):        # clicked by F5 (hidden by CSS): the page is drawn again with fresh data, where you are
    st.cache_data.clear()
    st.rerun()
if st.button("Menu", key="menu_toggle_hidden"):       # clicked by the key set in Settings (m): hides or shows the menu bar (hidden by CSS)
    settings.set_menu_hidden(not settings.get_menu_hidden())
    st.rerun()
if st.button("Back", key="nav_back_hidden"):          # clicked by the mouse back button (hidden by CSS)
    navigation.go_back()
if st.button("Forward", key="nav_forward_hidden"):    # clicked by the mouse forward button (hidden by CSS)
    navigation.go_forward()


def nav_button(label, icon):
    active = st.session_state["page"] == label
    shown = ":material/circle:" if icons.is_custom(icon) else icon      # custom drawings replace this glyph (see CSS)
    if st.button(label, icon=shown, key=f"nav_{label}", type="primary" if active else "tertiary"):
        st.session_state["page"] = label
        if label == "Library":
            st.session_state["open_book"] = None        # the Library icon always leads to the main page of the Library, not the open file
            st.session_state.pop("lib_goto", None)
        if label == "Courses":
            st.session_state["open_course"] = None  # top-level Courses shows the summary tiles
            st.session_state.pop("course_tab", None)
        st.rerun()


def _open_course(c):
    st.session_state.pop("course_tab", None)
    st.session_state["page"] = "Courses"
    st.session_state["course_id"] = c["id"]
    st.session_state["open_course"] = c["id"]
    st.session_state["courses_filter"] = crud.course_status(c)
    st.session_state["_courses_filter_kept"] = crud.course_status(c)
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
                if st.button(crud.show_code(c["code"]) or c["name"], icon=icon, key=f"nav_course_{c['id']}",
                             type="primary" if selected else "tertiary"):
                    _open_course(c)


with st.sidebar:
    # Hidden channel: the drag script writes "id,id,...|stamp" here and we persist the new order.
    sink = st.text_input("order", key="nav_order_sink", label_visibility="collapsed")
    if sink and sink != st.session_state.get("_order_saved"):
        st.session_state["_order_saved"] = sink
        crud.set_course_order([int(i) for i in sink.split("|")[0].split(",") if i.isdigit()])
    # Hidden channel: a study guide open in a window reports its highlights here, and they are kept inside the stored page (study/hlstore.py).
    hl = st.text_input("highlights", key="hl_sink", label_visibility="collapsed")
    if hl and hl != st.session_state.get("_hl_saved"):
        st.session_state["_hl_saved"] = hl
        from study import hlstore
        hlstore.handle_message(hl)
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

# Record where we are (skipped right after a Back, which already restored the stored view).
if st.session_state["page"] not in PAGES:           # a page that no longer exists (an open window on the removed File page)
    st.session_state["page"] = "Home"
navigation.record_view()

PAGES[st.session_state["page"]][1]()
tutorial.tour_after()                           # the guided tour: the dim, the box, the arrow and the helper card of the present step
