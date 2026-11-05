"""Study Assistant - Streamlit entry point."""
import streamlit as st
import streamlit.components.v1 as components

import crud
import importlib
import sys

import icons

# The dev server caches imported modules between reruns; reload ours so edits apply without a restart.
for _m in ("database", "crud", "settings", "icons", "pdfmeta", "covers", "photos", "views.notes_view", "views.courses_view", "views.home_view",
           "navigation", "views.homework_view", "views.exam_mode_view", "views.recall_view", "views.library_view", "views.calendar_view", "views.file_view",
           "views.settings_view"):
    if _m in sys.modules:
        importlib.reload(sys.modules[_m])
import navigation
import photos
import settings
from database import init_db
from views import calendar_view, courses_view, file_view, home_view, library_view, settings_view

st.set_page_config(page_title="Study Assistant", page_icon=":material/book:", layout="wide",
                   initial_sidebar_state="expanded")
init_db()
photos.organize_photos()

# (label, material icon, renderer)
NAV_TOP = {
    "Home": (":material/home:", home_view.render),
    "Calendar": (":material/calendar_month:", calendar_view.render),
    "Library": (":material/library_books:", library_view.render),
    "Courses": ("svg:course_cap", courses_view.render),
    "File": (":material/folder:", file_view.render),
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
    content: "PDF, HTML";}}
[class*="st-key-photo_box_"] [data-testid="stFileUploaderDropzone"]:not(:has([data-testid="stFileUploaderFile"]))::after {{
    content: "PNG, JPG, HEIC, WebP, GIF";}}

/* Library card menu button: plain "..." (opens the Edit File window) */
[class*="st-key-menu_"] button {{min-width: 34px; padding: 0 4px; min-height: 0; justify-content: flex-end;}}
[class*="st-key-menu_"] button p {{font-size: 1.5rem; font-weight: 700; line-height: 0.8; letter-spacing: 1px;}}
[class*="st-key-menu_"] button:hover p {{color: var(--accent) !important;}}

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
[class*="st-key-cover_"] [data-testid="stButton"], [class*="st-key-tile_"] [data-testid="stButton"] {{width: 100%; height: 100%;}}
[class*="st-key-cover_"] button {{width: 100%; height: 100% !important; opacity: 0; cursor: pointer; min-height: 0;}}
.book-cover.has-img {{background-size: cover; background-position: top center; padding: 0;}}
.book-badge.tag {{color: #fff !important;}}
.book-badge.meta {{border-color: var(--border); color: var(--text); opacity: 0.85;}}
.book-badge.status {{border-color: var(--border); color: var(--text); opacity: 0.85;}}
.book-badge.status.active {{border-color: #2f9e5f; color: #2f9e5f; background: rgba(47, 158, 95, 0.12); opacity: 1;}}
.book-badge.status.completed {{border-color: #6a77dd; color: #6a77dd; background: rgba(106, 119, 221, 0.12); opacity: 1;}}

/* Add Course button: plain outlined button at the top right */
.st-key-add_course_open {{width: 100% !important;}}
.st-key-add_course_open [data-testid="stButton"] {{width: 100%; display: flex; justify-content: flex-end;}}
.st-key-add_course_open button {{min-height: 0; padding: 0.3rem 0.8rem; width: auto !important;}}

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

.st-key-nav_back_hidden, .st-key-nav_forward_hidden {{position: absolute !important; width: 1px; height: 1px; overflow: hidden; opacity: 0;
    pointer-events: none;}}

/* Course outline: hidden box that carries a clicked point to the app */
.st-key-outline_sink, .st-key-lib_sink {{position: absolute !important; width: 1px; height: 1px; overflow: hidden; opacity: 0; pointer-events: none;}}

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
.ol a {{color: var(--accent) !important; text-decoration: none;}}
.ol a:hover {{text-decoration: underline;}}

/* Course page: links */
.res-link {{font-weight: 600; text-decoration: none; color: var(--accent) !important;}}
.res-link:hover {{text-decoration: underline;}}
[class*="st-key-link_open_"], [class*="st-key-link_rm_"], [class*="st-key-outline_toggle_"] {{width: 100% !important;}}
[class*="st-key-link_open_"] [data-testid="stButton"], [class*="st-key-link_rm_"] [data-testid="stButton"],
[class*="st-key-outline_toggle_"] [data-testid="stButton"] {{width: 100%; display: flex; justify-content: flex-end;}}
[class*="st-key-link_open_"] button, [class*="st-key-link_rm_"] button, [class*="st-key-outline_toggle_"] button {{
    min-height: 0; padding: 0.3rem 0.8rem; width: auto !important;}}

/* Course page: deadline lists */
.dl-list {{border: 1px solid var(--border); border-radius: 12px; overflow: hidden; margin-bottom: 1rem;}}
.dl-row {{display: grid; grid-template-columns: 1fr 190px 90px; gap: 12px; align-items: center; padding: 9px 16px;
    border-bottom: 1px solid var(--border);}}
.dl-row:last-child {{border-bottom: none;}}
.dl-title {{font-weight: 600;}}
.dl-when {{opacity: 0.8; font-size: 0.92rem;}}
.dl-pill {{justify-self: end; font-size: 0.78rem; border-radius: 999px; padding: 1px 12px; border: 1px solid var(--border);}}
.dl-pill.done {{border-color: #2f9e5f; color: #2f9e5f; background: rgba(47, 158, 95, 0.12);}}
.dl-pill.open {{border-color: var(--accent); color: var(--accent); background: rgba(76, 141, 255, 0.10);}}
.dl-pill.late {{border-color: #d14343; color: #d14343; background: rgba(209, 67, 67, 0.12);}}
.dl-pill.none {{opacity: 0.7;}}

/* Calendar: week view */
.st-key-edit_schedule_open {{width: 100% !important;}}
.st-key-edit_schedule_open [data-testid="stButton"] {{width: 100%; display: flex; justify-content: flex-end;}}
.st-key-edit_schedule_open button {{min-height: 0; padding: 0.3rem 0.8rem; width: auto !important;}}
.wk {{border: 1px solid var(--border); border-radius: 12px; overflow: hidden; margin: 6px 0 4px;}}
.wk-row {{display: grid; grid-template-columns: 56px repeat(7, 1fr);}}
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

/* Calendar */
.cal-head {{text-align: center; font-weight: 600; font-size: 0.85rem; opacity: 0.7; padding-bottom: 4px;}}
.cal-cell {{border: 1px solid var(--border); border-radius: 8px; min-height: 112px; padding: 6px; overflow: hidden;}}
.cal-cell.blank {{border-color: transparent; background: transparent;}}
.cal-cell.today {{border: 2px solid var(--accent);}}
.cal-day {{font-weight: 600; font-size: 0.9rem; margin-bottom: 3px;}}
.cal-chip {{color: #fff; font-size: 0.72rem; border-radius: 4px; padding: 1px 6px; margin-top: 3px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}}
.cal-more {{font-size: 0.72rem; opacity: 0.7; margin-top: 3px;}}

/* Library */
/* Library grid: one HTML block, cards are clickable through data-lib-act */
.lib-grid {{display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 1.2rem 1rem; align-items: start; margin-bottom: 1rem;}}
.lib-cover {{cursor: pointer;}}
.lib-cover:hover .book-cover {{filter: brightness(1.08);}}
.lib-name-row {{display: flex; justify-content: space-between; align-items: flex-start; gap: 4px; margin: 2px 0 6px; line-height: 1.35;}}
.lib-menu {{cursor: pointer; font-size: 1.5rem; font-weight: 700; line-height: 0.8; letter-spacing: 1px; padding: 0 4px; user-select: none;}}
.lib-menu:hover {{color: var(--accent);}}
.lib-author {{font-size: 0.875rem; opacity: 0.6;}}
.lib-add {{aspect-ratio: 2 / 3; border: 2px dashed rgba(140, 146, 160, 0.6); border-radius: 6px; display: flex;
    align-items: center; justify-content: center; font-size: 2.2rem; cursor: pointer;}}
.lib-add:hover {{border-color: var(--accent);}}
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
    inp.focus(); set.call(inp, a.dataset.olBook + ',' + a.dataset.olPage + '|' + Date.now());
    inp.dispatchEvent(new win.Event('input', {bubbles: true}));
    inp.dispatchEvent(new win.KeyboardEvent('keydown', {key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true}));
    inp.blur();
  }, true);
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
</script>""", height=0)

st.session_state.setdefault("page", "Home")
st.session_state.setdefault("mode", "Detailed")
st.session_state.setdefault("pdf_page", 1)

# ---- Back / forward navigation: the app keeps its own history of (page, open course, open file) ----
st.session_state.setdefault("nav_history", [])
st.session_state.setdefault("nav_forward", [])       # pages left by going back, newest last
if st.button("Back", key="nav_back_hidden"):          # clicked by the mouse back button (hidden by CSS)
    navigation.go_back()
if st.button("Forward", key="nav_forward_hidden"):    # clicked by the mouse forward button (hidden by CSS)
    navigation.go_forward()


def nav_button(label, icon):
    active = st.session_state["page"] == label
    shown = ":material/circle:" if icons.is_custom(icon) else icon      # custom drawings replace this glyph (see CSS)
    if st.button(label, icon=shown, key=f"nav_{label}", type="primary" if active else "tertiary"):
        st.session_state["page"] = label
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

# Record where we are (skipped right after a Back, which already restored the stored view).
_view = (st.session_state["page"], st.session_state.get("open_course"), st.session_state.get("open_book"))
if not st.session_state.pop("_going_back", False):
    _hist = st.session_state["nav_history"]
    if not _hist or _hist[-1] != _view:
        _hist.append(_view)
        del _hist[:-50]
        st.session_state["nav_forward"] = []          # going somewhere new clears what "forward" would have reached

PAGES[st.session_state["page"]][1]()
