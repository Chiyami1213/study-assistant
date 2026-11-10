# Hover Sidebar for Streamlit

A dark icon rail that widens on hover and folds after a click. One file, no dependencies besides Streamlit.

**Use it in another project:** copy `hover_sidebar.py` next to your app's main file.

```python
import streamlit as st
from hover_sidebar import MenuItem, Section, render_sidebar

st.set_page_config(page_title="My App", layout="wide")

page = render_sidebar(
    items=[
        MenuItem("Home", ":material/home:"),
        MenuItem("Courses", ":material/folder:", sections=[
            Section("Active", [MenuItem("MATH 301", ":material/rocket_launch:")]),
            Section("Completed", [MenuItem("MATH 101", ":material/inventory_2:")]),
        ]),
    ],
    bottom_items=[MenuItem("Settings", ":material/settings:")],
)

if page == "Home":
    st.title("Home")
```

`render_sidebar` returns the id of the selected item (its `key`, or its `label`) and keeps it in `st.session_state["page"]`.
Run `streamlit run demo_app.py` to see everything working.

## What you get

| Feature | How |
|---|---|
| Icon rail, 76 px folded and 270 px open | `collapsed_width`, `expanded_width` |
| Folds again after a click, `«` / `»` toggle icons | built in |
| Selected item: thin white outline, no filled box | built in |
| Bottom-pinned items | `bottom_items=[...]` |
| Hover submenu with foldable sections | `MenuItem(..., sections=[Section(...)])`, `fold_sections=True` |
| Remember folded sections | `collapsed_sections={"Courses/Active"}` and `on_fold=callback` |
| Your own SVG icons | `MenuItem("X", "svg:name")` plus `svg_icons={"name": "<svg ...>"}` |
| Drag items to reorder | `reorderable=True`, `on_reorder=callback(section_title, ids)` |
| Mouse back button / browser back | `mouse_back=True` (on by default) |
| Colors | `theme=Theme(bg=..., text=..., active_edge=...)` |

## Notes

- Item ids must be unique across the whole menu. Use `key=` when two labels repeat.
- Material icon names: https://fonts.google.com/icons (write them as `":material/name:"`).
- SVG icons: 24 x 24 `viewBox`, drawn with black strokes or fills; the rail tints them.
- The rail stays dark in Streamlit's light and dark themes. Change `Theme` to restyle it.
- To use two menus or avoid key clashes, pass a different `key_prefix`.
- Written for Streamlit 1.66. It needs `st.button(icon=...)` and `st.container(key=...)` (1.40+). It uses
  `st.iframe` for a small script and falls back to `components.html` on older versions.
- Reordering and fold state are only reported through the callbacks; saving them (a file, a database) is up to your app.
