"""Hover-expanding icon sidebar for Streamlit (copy this one file into any project).

A narrow dark icon rail that widens when the mouse is over it and narrows again after you click an item.

  - icons from Material Symbols (":material/home:") or your own SVG drawings ("svg:name")
  - the selected item gets a thin white outline (no filled box)
  - bottom items (for example Settings) pinned to the bottom of the rail
  - optional hover submenu under an item, split into foldable sections
  - optional drag-and-drop reordering of submenu items
  - optional mouse "back" button / browser back that goes to the previous menu selection
  - the rail stays dark in Streamlit's light and dark themes

Usage:

    from hover_sidebar import MenuItem, Section, render_sidebar

    page = render_sidebar(
        items=[
            MenuItem("Home", ":material/home:"),
            MenuItem("Courses", ":material/folder:", sections=[
                Section("Active", [MenuItem("AE 6009", ":material/rocket_launch:")]),
                Section("Completed", [MenuItem("AAE 333", ":material/science:")]),
            ]),
        ],
        bottom_items=[MenuItem("Settings", ":material/settings:")],
    )
    st.title(page)          # `page` is the id of the selected item (its key, or its label)

Call render_sidebar() once per run, near the top of your script (after st.set_page_config).
Tested with Streamlit 1.66; it relies on `st.button(icon=...)` and `st.container(key=...)` (Streamlit 1.40+).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Sequence
from urllib.parse import quote

import streamlit as st
import streamlit.components.v1 as components


@dataclass
class MenuItem:
    label: str
    icon: str = ":material/circle:"       # ":material/<name>:" or "svg:<name>" (see svg_icons)
    key: Optional[str] = None             # unique id kept in session_state; defaults to the label
    sections: Sequence["Section"] = ()    # optional hover submenu

    @property
    def id(self) -> str:
        return self.key or self.label


@dataclass
class Section:
    title: str
    items: Sequence[MenuItem]


@dataclass
class Theme:
    bg: str = "#1b1c20"                   # rail background
    border: str = "#2a2c33"               # right edge of the rail
    text: str = "#d5d7dd"                 # labels and icons
    text_active: str = "#ffffff"          # selected item
    muted: str = "#7d8190"                # section headings
    hover: str = "#23252c"                # hovered item background
    active_edge: str = "rgba(255, 255, 255, 0.9)"   # outline around the selected item
    drop_line: str = "#4c8dff"            # line shown while dragging an item
    shadow: str = "#00000066"             # shadow of the expanded rail


# ---------------------------------------------------------------------------------------------------------------
# CSS (placeholders: @@P@@ key prefix, @@CW@@ / @@EW@@ rail widths, @@BG@@ ... theme colors)
# ---------------------------------------------------------------------------------------------------------------
_CSS = """
[data-testid="stSidebarHeader"], [data-testid="stSidebarCollapseButton"],
[data-testid="stSidebarCollapsedControl"], [data-testid="stSidebarResizeHandle"] {display: none !important;}
section[data-testid="stSidebar"] {
    width: @@CW@@px !important; min-width: @@CW@@px !important; max-width: @@CW@@px !important;
    transform: none !important; overflow: visible !important; border: none; z-index: 1000; background: @@BG@@ !important;}
section[data-testid="stSidebar"] > div:first-child {
    position: absolute; top: 0; left: 0; height: 100vh; width: @@CW@@px !important;
    overflow-x: hidden; overflow-y: auto; scrollbar-width: none; background: @@BG@@; border-right: 1px solid @@BORDER@@;
    transition: width .2s ease, box-shadow .2s ease;}
section[data-testid="stSidebar"] > div:first-child:hover {width: @@EW@@px !important; box-shadow: 8px 0 24px @@SHADOW@@;}
section[data-testid="stSidebar"].hs-collapsed > div:first-child {width: @@CW@@px !important; box-shadow: none;}
[data-testid="stSidebarContent"] {padding: 0 !important;}
[data-testid="stSidebarUserContent"] {padding: 1rem 0 !important; width: @@EW@@px;}
header[data-testid="stHeader"] {z-index: 1; background: transparent;}

/* Buttons are the menu items */
[data-testid="stSidebar"] [data-testid="stElementContainer"], [data-testid="stSidebar"] .stButton {width: 100% !important;}
[data-testid="stSidebar"] button {
    width: calc(100% - 20px) !important; margin: 0 10px; justify-content: flex-start; gap: 19px; padding: 0.8rem 18px;
    border-radius: 12px; border: 1px solid transparent; background: transparent; box-shadow: none; white-space: nowrap;}
[data-testid="stSidebar"] button > div {justify-content: flex-start; width: 100%;}
[data-testid="stSidebar"] button > div > span {justify-content: flex-start; gap: 19px;}
[data-testid="stSidebar"] button p {font-size: 1.05rem; white-space: nowrap; opacity: 0; transition: opacity .15s;}
section[data-testid="stSidebar"] > div:first-child:hover button p {opacity: 1;}
section[data-testid="stSidebar"].hs-collapsed > div:first-child button p {opacity: 0 !important;}
[data-testid="stSidebar"] button span[data-testid="stIconMaterial"] {font-size: 1.5rem;}
[data-testid="stSidebar"] button:hover {background: @@HOVER@@;}
/* colors win over a light Streamlit theme: the rail is dark in every theme */
[data-testid="stSidebar"] button p, [data-testid="stSidebar"] button span[data-testid="stIconMaterial"] {color: @@TEXT@@ !important;}
[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] {background: transparent; border-color: @@EDGE@@;}
[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] p,
[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] span[data-testid="stIconMaterial"] {color: @@ACTIVE@@ !important;}

/* Bottom items pinned to the bottom of the rail */
[data-testid="stSidebarUserContent"] > div {min-height: calc(100vh - 2rem); display: flex; flex-direction: column;}
[data-testid="stLayoutWrapper"]:has(> .st-key-@@P@@_spacer), .st-key-@@P@@_spacer {flex: 1 1 auto;}

/* Folded rail: centered icon blocks with even edge spacing */
section[data-testid="stSidebar"] > div:first-child:not(:hover) button,
section[data-testid="stSidebar"].hs-collapsed > div:first-child button {
    width: calc(@@CW@@px - 20px) !important; margin: 0 10px !important; padding-left: 0 !important; padding-right: 0 !important;}
section[data-testid="stSidebar"] > div:first-child:not(:hover) button > div,
section[data-testid="stSidebar"].hs-collapsed > div:first-child button > div {justify-content: center;}
section[data-testid="stSidebar"] > div:first-child:not(:hover) button > div > span,
section[data-testid="stSidebar"].hs-collapsed > div:first-child button > div > span {gap: 0;}
section[data-testid="stSidebar"] > div:first-child:not(:hover) button [data-testid="stMarkdownContainer"],
section[data-testid="stSidebar"].hs-collapsed > div:first-child button [data-testid="stMarkdownContainer"] {display: none;}

/* « / » toggle icons: » in the folded rail, « (top right) when expanded */
.st-key-@@P@@_head {margin-bottom: 0.4rem;}
.st-key-@@P@@_head [data-testid="stButton"] {display: flex; justify-content: flex-end;}
.st-key-@@P@@_head button {width: 44px !important; padding: 0.5rem 0 !important; justify-content: center; margin: 0 7px 0 0 !important;}
.st-key-@@P@@_head button > div {justify-content: center;}
.st-key-@@P@@_head button p {display: none;}
.st-key-@@P@@_expand {display: block;} .st-key-@@P@@_collapse {display: none;}
.st-key-@@P@@_expand [data-testid="stButton"] {justify-content: flex-start;}
.st-key-@@P@@_expand button {margin: 0 0 0 10px !important;}
section[data-testid="stSidebar"] > div:first-child:hover .st-key-@@P@@_expand {display: none;}
section[data-testid="stSidebar"] > div:first-child:hover .st-key-@@P@@_collapse {display: block;}
section[data-testid="stSidebar"].hs-collapsed .st-key-@@P@@_expand {display: block !important;}
section[data-testid="stSidebar"].hs-collapsed .st-key-@@P@@_collapse {display: none !important;}

/* Hover submenu: opens while the mouse is over the item's group */
[class*="st-key-@@P@@_group_"] {gap: 0;}
[class*="st-key-@@P@@_sub_"] {gap: 0; max-height: 0; overflow: hidden; transition: max-height .25s ease;}
[class*="st-key-@@P@@_group_"]:hover [class*="st-key-@@P@@_sub_"] {max-height: 2400px;}
section[data-testid="stSidebar"].hs-collapsed [class*="st-key-@@P@@_sub_"] {max-height: 0 !important;}
[class*="st-key-@@P@@_child_"] button {padding: 0.5rem 16px 0.5rem 36px !important;}
.hs-label {font-size: 1.05rem; color: @@MUTED@@; padding: 0.9rem 0 0.4rem 44px; margin-bottom: 1rem; line-height: 1.2; white-space: nowrap;}

/* Foldable section headings */
[class*="st-key-@@P@@_sec_"] button {padding: 0.55rem 16px 0.35rem 30px !important; gap: 8px !important;}
[class*="st-key-@@P@@_sec_"] button p {color: @@MUTED@@ !important;}
[class*="st-key-@@P@@_sec_"] button span[data-testid="stIconMaterial"] {font-size: 1.2rem !important; color: @@MUTED@@ !important;}
[class*="st-key-@@P@@_sec_"] button:hover {background: transparent !important;}
[class*="st-key-@@P@@_sec_"] button:hover p, [class*="st-key-@@P@@_sec_"] button:hover span[data-testid="stIconMaterial"] {color: @@TEXT@@ !important;}

/* Hidden helper widgets (mouse back button, drag-and-drop channel) */
.st-key-@@P@@_back, .st-key-@@P@@_sink {position: absolute !important; width: 1px; height: 1px; overflow: hidden; opacity: 0; pointer-events: none;}

/* Drag and drop */
.hs-dragging {opacity: 0.4;}
.hs-drop-above button {box-shadow: 0 -2px 0 0 @@DROP@@ !important;}
.hs-drop-below button {box-shadow: 0 2px 0 0 @@DROP@@ !important;}
"""

# ---------------------------------------------------------------------------------------------------------------
# JavaScript, run once per browser tab from a zero-height component iframe
# ---------------------------------------------------------------------------------------------------------------
_JS_COLLAPSE = r"""
if (!win.__hsCollapse_@@P@@) {
  win.__hsCollapse_@@P@@ = true;
  // after a click on a menu button the rail folds until the mouse leaves it
  doc.addEventListener('click', e => {
    const sb = doc.querySelector('section[data-testid="stSidebar"]');
    if (sb && sb.contains(e.target) && e.target.closest('button') && !e.target.closest('[class*="st-key-@@P@@_sec_"]'))
      sb.classList.add('hs-collapsed');
  }, true);
  doc.addEventListener('mouseover', e => {
    const sb = doc.querySelector('section[data-testid="stSidebar"]');
    if (sb && !sb.contains(e.target)) sb.classList.remove('hs-collapsed');
  });
}
"""

_JS_BACK = r"""
if (!win.__hsBack_@@P@@) {
  win.__hsBack_@@P@@ = true;
  const goBack = () => { const b = doc.querySelector('.st-key-@@P@@_back button'); if (b) b.click(); };
  doc.addEventListener('mouseup', e => { if (e.button === 3) { e.preventDefault(); e.stopPropagation(); goBack(); } }, true);
  doc.addEventListener('mousedown', e => { if (e.button === 3 || e.button === 4) e.preventDefault(); }, true);
  win.history.pushState({hs: true}, '', win.location.href);
  win.addEventListener('popstate', () => { win.history.pushState({hs: true}, '', win.location.href); goBack(); });
}
"""

_JS_DRAG = r"""
if (!win.__hsDrag_@@P@@) {
  win.__hsDrag_@@P@@ = true;
  let dragged = null;
  const SEL = '[class*="st-key-@@P@@_child_"]', SEC = '[class*="st-key-@@P@@_sec_"], .hs-label';
  const child = el => (el && el.closest) ? el.closest(SEL) : null;
  const num = c => (c.className.match(/st-key-@@P@@_child_([0-9]+)/) || [])[1];
  const sectionOf = c => { for (let e = c.previousElementSibling; e; e = e.previousElementSibling) if (e.matches(SEC) || e.querySelector('.hs-label')) return e; return null; };
  const members = head => { const out = []; for (let e = head.nextElementSibling; e && !(e.matches(SEC) || e.querySelector('.hs-label')); e = e.nextElementSibling) if (e.matches(SEL)) out.push(e); return out; };
  const clear = () => doc.querySelectorAll('.hs-drop-above,.hs-drop-below,.hs-dragging').forEach(e => e.classList.remove('hs-drop-above', 'hs-drop-below', 'hs-dragging'));
  doc.addEventListener('mouseover', () => doc.querySelectorAll(SEL + ' button').forEach(b => b.setAttribute('draggable', 'true')));
  doc.addEventListener('dragstart', e => { const c = child(e.target); if (!c) return; dragged = c; c.classList.add('hs-dragging'); e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', num(c)); });
  doc.addEventListener('dragover', e => {
    if (!dragged) return; const t = child(e.target);
    if (!t || t === dragged || sectionOf(t) !== sectionOf(dragged)) return;
    e.preventDefault(); const r = t.getBoundingClientRect();
    doc.querySelectorAll('.hs-drop-above,.hs-drop-below').forEach(x => x.classList.remove('hs-drop-above', 'hs-drop-below'));
    t.classList.add(e.clientY > r.top + r.height / 2 ? 'hs-drop-below' : 'hs-drop-above');
  });
  doc.addEventListener('drop', e => {
    if (!dragged) return; const t = child(e.target);
    if (!t || t === dragged || sectionOf(t) !== sectionOf(dragged)) { clear(); dragged = null; return; }
    e.preventDefault(); const r = t.getBoundingClientRect(), below = e.clientY > r.top + r.height / 2;
    const ids = members(sectionOf(dragged)).map(num).filter(i => i !== num(dragged));
    let at = ids.indexOf(num(t)); if (below) at += 1; ids.splice(at, 0, num(dragged)); clear(); dragged = null;
    const inp = doc.querySelector('.st-key-@@P@@_sink input'); if (!inp) return;
    const set = Object.getOwnPropertyDescriptor(win.HTMLInputElement.prototype, 'value').set;
    inp.focus(); set.call(inp, ids.join(',') + '|' + Date.now());
    inp.dispatchEvent(new win.Event('input', {bubbles: true}));
    inp.dispatchEvent(new win.KeyboardEvent('keydown', {key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true}));
    inp.blur();
  });
  doc.addEventListener('dragend', () => { clear(); dragged = null; });
}
"""


def _fill(template: str, **values: str) -> str:
    for name, value in values.items():
        template = template.replace(f"@@{name}@@", str(value))
    return template


def _svg_icon_css(css_class: str, svg: str, theme: Theme) -> str:
    """Draw an SVG (black strokes on transparent) in place of the Material icon, tinted like the other icons."""
    url = f"url('data:image/svg+xml,{quote(svg)}')"
    return (f'.st-key-{css_class} span[data-testid="stIconMaterial"] {{color: transparent !important; width: 1.5rem; '
            f'height: 1.5rem; display: inline-block; flex: none; background: {theme.text}; '
            f'-webkit-mask: {url} center/contain no-repeat; mask: {url} center/contain no-repeat;}}'
            f'.st-key-{css_class} button[data-testid="stBaseButton-primary"] span[data-testid="stIconMaterial"] '
            f'{{background: {theme.text_active};}}')


def _run_script(js: str) -> None:
    """Run JavaScript in the page from a tiny iframe (st.iframe on current Streamlit, components.html on older)."""
    html = f"<script>{js}</script>"
    if hasattr(st, "iframe"):
        st.iframe(html, height=1)
    else:
        components.html(html, height=0)


def render_sidebar(
    items: Sequence[MenuItem],
    bottom_items: Sequence[MenuItem] = (),
    state_key: str = "page",
    default: Optional[str] = None,
    *,
    theme: Optional[Theme] = None,
    collapsed_width: int = 76,
    expanded_width: int = 270,
    svg_icons: Optional[dict] = None,
    fold_sections: bool = True,
    collapsed_sections: Optional[set] = None,
    on_fold: Optional[Callable[[set], None]] = None,
    reorderable: bool = False,
    on_reorder: Optional[Callable[[str, list], None]] = None,
    mouse_back: bool = True,
    key_prefix: str = "hs",
) -> str:
    """Draw the sidebar and return the id of the selected item (also stored in st.session_state[state_key]).

    svg_icons          {"name": "<svg ...>"} for items whose icon is "svg:name" (24x24 viewBox, black strokes).
    collapsed_sections ids of sections that start folded, as "<parent id>/<section title>".
    on_fold(set)       called with all folded sections after the user folds or unfolds one (to save them).
    on_reorder(section_title, ids)  called after a drag; ids are the submenu item ids in their new order.
    """
    p, ss, theme, svg_icons = key_prefix, st.session_state, theme or Theme(), svg_icons or {}
    top = list(items)
    ss.setdefault(state_key, default if default is not None else top[0].id)
    ss.setdefault(f"_{p}_collapsed", set(collapsed_sections or ()))
    folded: set = ss[f"_{p}_collapsed"]

    # Number every item so widget keys are safe CSS class names whatever the labels contain.
    numbers, child_map, svg_css, n = {}, {}, [], 0
    for item in [*top, *bottom_items]:
        n += 1
        numbers[id(item)] = n
        for section in item.sections:
            for child in section.items:
                n += 1
                numbers[id(child)] = n
                child_map[n] = (section.title, child.id)

    def icon_for(item: MenuItem, css_class: str) -> str:
        if item.icon.startswith("svg:"):
            if item.icon[4:] in svg_icons:
                svg_css.append(_svg_icon_css(css_class, svg_icons[item.icon[4:]], theme))
            return ":material/circle:"       # placeholder glyph, replaced by the drawing
        return item.icon

    # ---- hidden helpers and the style/scripts ----
    hist_key = f"_{p}_history"
    ss.setdefault(hist_key, [])
    if mouse_back and st.button("Back", key=f"{p}_back"):    # clicked by the mouse back button (hidden)
        hist = ss[hist_key]
        if len(hist) > 1:
            hist.pop()
            ss[state_key] = hist[-1]
            ss[f"_{p}_going_back"] = True
            st.rerun()

    if reorderable:
        with st.sidebar:
            sink = st.text_input("order", key=f"{p}_sink", label_visibility="collapsed")
        if sink and sink != ss.get(f"_{p}_sink_done"):
            ss[f"_{p}_sink_done"] = sink
            picked = [child_map[int(x)] for x in sink.split("|")[0].split(",") if x.isdigit() and int(x) in child_map]
            if picked and on_reorder:
                on_reorder(picked[0][0], [pid for _, pid in picked])
                st.rerun()

    # ---- the menu ----
    selected = ss[state_key]

    def select(item_id: str) -> None:
        ss[state_key] = item_id
        st.rerun()

    def draw_item(item: MenuItem) -> None:
        num = numbers[id(item)]
        child_ids = {c.id for s in item.sections for c in s.items}
        active = selected == item.id or selected in child_ids
        if st.button(item.label, icon=icon_for(item, f"{p}_item_{num}"), key=f"{p}_item_{num}",
                     type="primary" if active else "tertiary"):
            select(item.id)

    def draw_submenu(item: MenuItem) -> None:
        with st.container(key=f"{p}_sub_{numbers[id(item)]}"):
            for section in item.sections:
                fold_id = f"{item.id}/{section.title}"
                closed = fold_sections and fold_id in folded
                if fold_sections:
                    if st.button(section.title, icon=":material/chevron_right:" if closed else ":material/expand_more:",
                                 key=f"{p}_sec_{numbers[id(item)]}_{section.title}", type="tertiary"):
                        folded.symmetric_difference_update({fold_id})
                        if on_fold:
                            on_fold(set(folded))
                        st.rerun()
                else:
                    st.markdown(f'<div class="hs-label">{section.title}</div>', unsafe_allow_html=True)
                if closed:
                    continue
                for child in section.items:
                    num = numbers[id(child)]
                    if st.button(child.label, icon=icon_for(child, f"{p}_child_{num}"), key=f"{p}_child_{num}",
                                 type="primary" if selected == child.id else "tertiary"):
                        select(child.id)

    with st.sidebar:
        with st.container(key=f"{p}_head"):
            st.button(" ", icon=":material/keyboard_double_arrow_right:", key=f"{p}_expand", type="tertiary")
            st.button(" ", icon=":material/keyboard_double_arrow_left:", key=f"{p}_collapse", type="tertiary")
        for item in top:
            if item.sections:
                with st.container(key=f"{p}_group_{numbers[id(item)]}"):
                    draw_item(item)
                    draw_submenu(item)
            else:
                draw_item(item)
        with st.container(key=f"{p}_spacer"):
            st.markdown("&nbsp;", unsafe_allow_html=True)     # empty containers are not rendered
        for item in bottom_items:
            draw_item(item)

    css = _fill(_CSS, P=p, CW=collapsed_width, EW=expanded_width, BG=theme.bg, BORDER=theme.border, TEXT=theme.text,
                ACTIVE=theme.text_active, MUTED=theme.muted, HOVER=theme.hover, EDGE=theme.active_edge,
                DROP=theme.drop_line, SHADOW=theme.shadow)
    st.markdown(f"<style>{css}{''.join(svg_css)}</style>", unsafe_allow_html=True)
    js = _JS_COLLAPSE + (_JS_BACK if mouse_back else "") + (_JS_DRAG if reorderable else "")
    _run_script("const win = window.parent, doc = win.document;" + _fill(js, P=p))

    # ---- history for the mouse back button (skipped right after a Back, which already restored the view) ----
    if not ss.pop(f"_{p}_going_back", False):
        hist = ss[hist_key]
        if not hist or hist[-1] != ss[state_key]:
            hist.append(ss[state_key])
            del hist[:-50]
    return ss[state_key]
