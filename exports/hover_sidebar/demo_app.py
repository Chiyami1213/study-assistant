"""Demo for hover_sidebar.py:  streamlit run demo_app.py"""
import streamlit as st

from hover_sidebar import MenuItem, Section, render_sidebar

st.set_page_config(page_title="Hover Sidebar Demo", page_icon=":material/menu:", layout="wide")

# Example data. In a real app these lists could come from a database; the order you pass in is the order shown.
if "active" not in st.session_state:
    st.session_state["active"] = ["AE 6009", "AE 6451", "PHYS 6105"]
    st.session_state["done"] = ["AAE 333", "AAE 334", "ECON 251"]

SVG_ICONS = {  # optional custom drawings: 24x24 viewBox, black strokes (they are tinted by the theme)
    "wave": "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.6' "
            "stroke-linecap='round'><path d='M2 8c3-3 5 3 8 0s5 3 8 0 3 0 4-1M2 16c3-3 5 3 8 0s5 3 8 0 3 0 4-1'/></svg>",
}

items = [
    MenuItem("Home", ":material/home:"),
    MenuItem("Calendar", ":material/calendar_month:"),
    MenuItem("Library", ":material/library_books:"),
    MenuItem("Courses", ":material/folder:", sections=[
        Section("Active", [MenuItem(c, "svg:wave" if c == "AE 6009" else ":material/rocket_launch:")
                           for c in st.session_state["active"]]),
        Section("Completed", [MenuItem(c, ":material/inventory_2:") for c in st.session_state["done"]]),
    ]),
]


def save_order(section: str, ids: list) -> None:
    st.session_state["active" if section == "Active" else "done"] = ids


page = render_sidebar(
    items,
    bottom_items=[MenuItem("Settings", ":material/settings:")],
    svg_icons=SVG_ICONS,
    reorderable=True,
    on_reorder=save_order,
)

st.title(page)
st.write("Hover the rail on the left. Click an item and it folds again. "
         "Drag the items under Courses to reorder them. The mouse back button returns to the previous item.")
