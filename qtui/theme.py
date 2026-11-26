"""Colors and the Qt style sheet of the native interface. PURE (no Qt import): the same palettes as the web interface (`core.settings.theme_colors`), so the Light / Dark choice and the color theme of Settings look the same in both."""
from core import settings

SIDEBAR = {"bg": "#1b1c20", "hover": "#23252c", "text": "#d5d7dd", "muted": "#7d8190", "line": "#3a3d46", "border": "#2a2c33"}     # the menu stays dark in every theme
RAIL_W, MENU_W = 76, 270


def resolve_mode(appearance, system_dark):
    """'dark' or 'light': the choice of Settings, or the device's setting for 'device'."""
    if appearance in ("light", "dark"):
        return appearance
    return "dark" if system_dark else "light"


def colors(appearance=None, theme=None, system_dark=True):
    """The palette of a mode and a color theme as a dict: bg, bg2, input, border, text, hover, active, card, accent, primary, mode."""
    mode = resolve_mode(appearance or settings.get_appearance(), system_dark)
    c = settings.theme_colors(theme or settings.get_color_theme(), mode)
    c["mode"] = mode
    return c


def stylesheet(c):
    """The Qt style sheet for a palette."""
    return f"""
* {{ font-family: "Segoe UI", "Source Sans 3", "Helvetica Neue", Arial, sans-serif; font-size: 14px; }}
QWidget {{ color: {c['text']}; }}
QMainWindow, QWidget#content, QWidget#page, QScrollArea, QScrollArea > QWidget > QWidget {{ background: {c['bg']}; border: none; }}
QLabel {{ background: transparent; }}
QLabel#h1 {{ font-size: 26px; font-weight: 700; }}
QLabel#h2 {{ font-size: 20px; font-weight: 700; padding-top: 14px; }}
QLabel#caption {{ color: {c['text']}; font-size: 12px; }}
QLabel#muted {{ color: {c['text']}; font-size: 12px; }}
QPushButton {{ background: {c['bg']}; border: 1px solid {c['border']}; border-radius: 8px; padding: 7px 16px; }}
QPushButton:hover {{ border-color: {c['accent']}; }}
QPushButton:checked {{ border: 2px solid {c['primary']}; color: {c['primary']}; }}
QPushButton#primary {{ background: {c['primary']}; border-color: {c['primary']}; color: #ffffff; }}
QSpinBox, QDoubleSpinBox, QLineEdit, QComboBox {{ background: {c['input']}; border: 1px solid {c['border']}; border-radius: 8px; padding: 7px 10px; min-height: 22px; }}
QSpinBox:disabled {{ color: {c['border']}; }}
QFrame#card {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 10px; }}
QFrame#card[chosen="true"] {{ border: 2px solid {c['primary']}; }}
QToolTip {{ background: {c['bg2']}; color: {c['text']}; border: 1px solid {c['border']}; padding: 4px 8px; }}
QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{ background: {c['border']}; border-radius: 5px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QFrame#sidebar {{ background: {SIDEBAR['bg']}; border-right: 1px solid {SIDEBAR['border']}; }}
QFrame#sidebar QWidget {{ color: {SIDEBAR['text']}; }}
QFrame#sidebar QScrollArea, QFrame#sidebar QScrollArea > QWidget > QWidget {{ background: {SIDEBAR['bg']}; border: none; }}
QPushButton#nav {{ background: transparent; border: 1px solid transparent; border-radius: 10px; text-align: left; padding: 11px 0 11px 0; font-size: 15px; }}
QPushButton#nav:hover {{ background: {SIDEBAR['hover']}; }}
QPushButton#nav[current="true"] {{ border: 1px solid rgba(255,255,255,0.9); }}
QPushButton#navsec {{ background: transparent; border: none; text-align: left; color: {SIDEBAR['muted']}; padding: 8px 0 4px 0; font-size: 13px; }}
QPushButton#navsec:hover {{ color: {SIDEBAR['text']}; }}
QPushButton#navsub {{ background: transparent; border: 1px solid transparent; border-radius: 10px; text-align: left; padding: 9px 0; font-size: 14px; }}
QPushButton#navsub:hover {{ background: {SIDEBAR['hover']}; }}
QPushButton#navsub[current="true"] {{ border: 1px solid rgba(255,255,255,0.9); }}
"""
