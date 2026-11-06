"""Study Assistant - Streamlit entry point."""
import streamlit as st
import streamlit.components.v1 as components

import crud
import importlib
import sys

import icons

# The dev server caches imported modules between reruns; reload ours so edits apply without a restart.
for _m in ("database", "notesfs", "crud", "settings", "icons", "pdfmeta", "covers", "reader", "macros", "unitex", "outline", "htmlnotes", "quizzes", "quizgen", "quizhtml", "hwassist", "gradereport", "syllabus", "photos", "views.notes_view", "views.courses_view", "views.home_view",
           "navigation", "views.homework_view", "views.exam_mode_view", "views.recall_view", "views.library_view", "views.quiz_view", "views.calendar_view", "views.file_view", "views.lab_view",
           "views.settings_view"):
    if _m in sys.modules:
        importlib.reload(sys.modules[_m])
import navigation
import photos
import settings
from database import init_db
from views import calendar_view, courses_view, file_view, home_view, lab_view, library_view, settings_view

st.set_page_config(page_title="Study Assistant", page_icon=":material/book:", layout="wide",
                   initial_sidebar_state="expanded")
init_db()
photos.organize_photos()

# (label, material icon, renderer)
NAV_TOP = {
    "Home": (":material/home:", home_view.render),
    "File": (":material/folder:", file_view.render),
    "Calendar": (":material/calendar_month:", calendar_view.render),
    "Library": (":material/library_books:", library_view.render),
    "Note Builder": (":material/edit_note:", lab_view.render),
    "Courses": ("svg:course_cap", courses_view.render),
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
[data-testid="stPopoverButton"] > div > div[aria-hidden="true"] {{display: none !important;}}   /* no gap left where the arrow was */
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
.ol-leaf.ol-l3 {{padding-left: 34px; font-size: 0.9rem; opacity: 0.92;}}
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
.syl-open {{font-size: 0.95rem; font-weight: 600;}}
.syl-table {{border-collapse: collapse; margin: 6px 0 10px; width: 100%; max-width: 640px; font-size: 0.92rem;}}
.syl-table th, .syl-table td {{border-bottom: 1px solid var(--border); padding: 6px 10px; text-align: left;}}
.syl-table th {{font-weight: 600; opacity: 0.8; font-size: 0.82rem;}}
.syl-table .n {{text-align: right;}} .syl-table .none {{opacity: 0.6;}}
.dl-grade {{font-size: 0.85rem; margin-top: 3px;}} .dl-grade b {{color: #2f9e5f;}} .dl-grade.none {{opacity: 0.6;}}
.dl-sub {{opacity: 0.75; font-size: 0.85rem; margin-top: 3px;}}
.dl-pill {{justify-self: end; font-size: 0.78rem; border-radius: 999px; padding: 1px 12px; border: 1px solid var(--border);}}
.dl-pill.done {{border-color: #2f9e5f; color: #2f9e5f; background: rgba(47, 158, 95, 0.12);}}
.dl-pill.open {{border-color: var(--accent); color: var(--accent); background: rgba(76, 141, 255, 0.10);}}
.dl-pill.late {{border-color: #d14343; color: #d14343; background: rgba(209, 67, 67, 0.12);}}
.dl-pill.none {{opacity: 0.7;}}
.up-row {{display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 10px 16px;
    border-bottom: 1px solid var(--border);}}
.up-row:last-child {{border-bottom: none;}}
.up-meta {{display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 4px;}}
.up-meta .book-badge {{margin: 0;}}

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
.rd-spread {{display: flex; justify-content: center; align-items: flex-start; gap: 6px;}}
.rd-spread img {{margin: 0;}}

/* Note Builder: the tabs share a row with Rename and Export (the toolbar ignores clicks except on its buttons) */
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
/* Note Builder and File page */
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
[class*="st-key-lab_view_scroll"] {{height: calc(100vh - 300px); overflow-y: auto;}}
[class*="st-key-lab_view_scroll"] iframe {{height: calc(100vh - 310px) !important;}}
.st-key-lab_chat_box {{height: calc(100vh - 360px); overflow-y: auto;}}
[class*="st-key-lab_pane_"] textarea {{height: calc(100vh - 330px) !important; min-height: 280px;}}
.rd-cont {{position: relative; scroll-behavior: auto;}}
.rd-pg {{margin: 0 auto 14px; background: #fff; box-shadow: 0 2px 10px #0008; overflow: hidden;}}
.rd-pg img {{display: block; width: 100%; height: 100%; object-fit: contain; margin: 0; box-shadow: none; max-width: 100%;}}
.rd-row {{display: flex; justify-content: center; align-items: flex-start; gap: 6px; margin-bottom: 14px;}}
.rd-row .rd-pg {{margin: 0;}}
.rd-pagewrap {{position: relative; line-height: 0;}}
.rd-pg {{position: relative;}}
.rd-err {{position: absolute; border: 2px solid #e5484d; background: rgba(229, 72, 77, 0.14); border-radius: 4px; z-index: 2; cursor: help;}}
.rd-err.rd-sent {{border-color: #d9a21b; background: rgba(217, 162, 27, 0.2);}}
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
.file-head {{display: flex; align-items: center; gap: 10px; margin-top: 1.2rem;}}
.file-head {{display: block !important;}}
.file-dot {{width: 12px; height: 12px; border-radius: 50%; display: inline-block; margin-right: 12px; vertical-align: middle; position: relative; top: -2px;}}
.file-count {{font-weight: 400; opacity: 0.6; font-size: 1rem;}}

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
    inp.focus(); set.call(inp, a.dataset.olBook + ',' + a.dataset.olPage + (a.dataset.olTab ? ',' + a.dataset.olTab : '') + '|' + Date.now());
    inp.dispatchEvent(new win.Event('input', {bubbles: true}));
    inp.dispatchEvent(new win.KeyboardEvent('keydown', {key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true}));
    inp.blur();
  }, true);
}
// 20-20-20 rule: after every 20 minutes of using the app, ask for a 20-second look at something 20 feet away.
// Turning that down is allowed, but after 2 refusals in a row there is a warning, and the 3rd prompt (1 hour of
// non-stop use) becomes a required 5-minute rest.
if (!win.__eyeRestV2) {
  win.__eyeRestV2 = true;
  const KEY = 'sa_eye_rest', num = (k, d) => +localStorage.getItem(k) || d;
  const load = () => { try { return JSON.parse(localStorage.getItem(KEY)) || null; } catch (e) { return null; } };
  const save = v => { try { localStorage.setItem(KEY, JSON.stringify(v)); } catch (e) {} };
  const interval = () => num('sa_study_interval', 1200) * 1000;       // 20 minutes
  const restLen = () => num('sa_rest_seconds', 20);                   // 20 seconds
  const forceLen = () => num('sa_force_seconds', 300);                // 5 minutes
  const idleReset = () => num('sa_idle_reset', 300) * 1000;           // away 5+ minutes counts as a rest
  const fmt = n => Math.floor(n / 60) + ':' + String(n % 60).padStart(2, '0');
  let st = load(), card = null, forced = null;
  const fresh = () => ({next: Date.now() + interval(), seen: Date.now(), refused: 0, forceEnd: 0});
  if (!st || Date.now() - st.seen > idleReset()) st = fresh();
  save(st);
  const beep = () => { try { const c = new (win.AudioContext || win.webkitAudioContext)(), o = c.createOscillator(), g = c.createGain();
    o.connect(g); g.connect(c.destination); o.frequency.value = 660; g.gain.value = 0.08; o.start(); o.stop(c.currentTime + 0.25); } catch (e) {} };
  function closeCard() { if (card) { card.el.remove(); card = null; } }
  function refuse() {
    closeCard(); st.refused = (st.refused || 0) + 1; save(st);
    if (st.refused === 2) warn();
  }
  function warn() {
    const el = doc.createElement('div'); el.id = 'sa-rest'; el.className = 'warn';
    el.innerHTML = '<h3>Rest Warning</h3><p>You have skipped 2 eye rests in a row. If you keep studying without a break, ' +
      'a required 5-minute rest starts after 1 hour of non-stop use.</p><button type="button">Understood</button>';
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
    el.innerHTML = '<div id="sa-rest"><h3>Required Rest</h3><p>You have used the app for 1 hour without taking an eye rest. ' +
      'Step away from the screen and rest your eyes for 5 minutes.</p><div class="count"></div><div class="bar"><i></i></div>' +
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
        if (st.refused >= 2) force(); else { closeCard(); ask(); }
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
// Note Builder window tabs: drag a tab to any place in the row; x closes a window; + adds one.
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
    doc.querySelectorAll('.rd-err.active').forEach(el => {                       // the erratum clicked in a note: bring it to the middle
      if (!el._seen) { el._seen = true; el.scrollIntoView({block: 'center', inline: 'nearest'}); }
    });
    doc.querySelectorAll('.rd-cont').forEach(c => {
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
  }, 250);
}
// Note Builder: drag the border between two windows to change their widths (remembered).
if (!win.__labResizeV1) {
  win.__labResizeV1 = true;
  const columns = () => {
    const b = doc.querySelector('[data-testid="stHorizontalBlock"]:has([class*="st-key-lab_pane_"])');
    return b ? [...b.children].filter(c => c.matches('[data-testid="stColumn"]')) : [];
  };
  const idOf = col => { const m = (col.querySelector('[class*="st-key-lab_pane_"]') || {className: ''}).className.match(/st-key-lab_pane_([A-Za-z0-9_]+)/); return m ? m[1] : null; };
  let drag = null;
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
    const sink = doc.querySelector('.st-key-lab_tab_sink input'); if (!sink) return;
    const total = d.cs.reduce((t, c) => t + c.getBoundingClientRect().width, 0) / d.cs.length;       // average width = weight 1
    const parts = d.cs.map(c => idOf(c) + '=' + (c.getBoundingClientRect().width / total).toFixed(3)).filter(x => !x.startsWith('null'));
    const set = Object.getOwnPropertyDescriptor(win.HTMLInputElement.prototype, 'value').set;
    sink.focus(); set.call(sink, 'widths:' + parts.join(',') + '|' + Date.now());
    sink.dispatchEvent(new win.Event('input', {bubbles: true}));
    sink.dispatchEvent(new win.KeyboardEvent('keydown', {key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true}));
    sink.blur();
    // the sizes are now set by the page itself: drop the temporary ones so later changes (a new window) lay out right
    [900, 2500, 6000].forEach(ms => setTimeout(() => d.cs.forEach(c => ['flex', 'width', 'min-width'].forEach(k => c.style.removeProperty(k))), ms));
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

if st.query_params.get("detached"):          # a Note Builder window dragged out into its own window
    lab_view.render_detached(st.query_params["detached"])
    st.stop()

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
