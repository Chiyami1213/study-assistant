"""The main window: the menu on the left (it floats over the page when it opens) and the page beside it."""
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QLabel, QMainWindow, QStackedWidget, QVBoxLayout, QWidget

from core import crud, settings
from qtui import server, theme
from qtui.eyerest import EyeRestController
from qtui.pages.settings_page import SettingsPage
from qtui.pages.web_page import WebPage
from qtui.sidebar import Sidebar
from qtui.theme import RAIL_W

CLASSIC = ["Home", "Calendar", "Library", "Note Reader", "Courses"]            # the pages still drawn by the classic interface


class MainWindow(QMainWindow):
    def __init__(self, use_server=True):
        super().__init__()
        self.setWindowTitle("Study Assistant")
        self.resize(1440, 900)
        self.setMinimumSize(900, 600)
        self.use_server = use_server
        self.page, self.course = "Home", None
        central = QWidget()
        self.setCentralWidget(central)
        self.content = QWidget(central)
        self.content.setObjectName("content")
        lay = QVBoxLayout(self.content)
        lay.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        lay.addWidget(self.stack)
        self.pages = {}
        for name in CLASSIC:
            self.pages[name] = WebPage(name) if use_server else QLabel(f"{name} (classic page)")
            self.stack.addWidget(self.pages[name])
        self.settings_page = SettingsPage(self._colors())
        self.settings_page.appearance_changed.connect(self.apply_theme)
        self.settings_page.classic_requested.connect(lambda: self.show_page("Classic Settings"))
        self.pages["Settings"] = self.settings_page
        self.stack.addWidget(self.settings_page)
        self.pages["Classic Settings"] = WebPage("Settings") if use_server else QLabel("Settings (classic page)")
        self.stack.addWidget(self.pages["Classic Settings"])
        self.sidebar = Sidebar(central)
        self.sidebar.navigate.connect(self.show_page)
        self.sidebar.course_chosen.connect(self.choose_course)
        self.rest = EyeRestController(self, settings.get_eye_rest)
        self.sidebar.rest_now.connect(self.rest.rest_now)
        first = crud.courses_by_status("Active")
        self.course = first[0]["id"] if first else None
        self.apply_theme()
        self.show_page("Home")

    def _colors(self):
        dark = QGuiApplication.styleHints().colorScheme().name == "Dark"
        return theme.colors(system_dark=dark)

    def apply_theme(self):
        c = self._colors()
        self.setStyleSheet(theme.stylesheet(c))
        self.settings_page.refresh(c)

    def resizeEvent(self, e):
        c = self.centralWidget()
        self.content.setGeometry(RAIL_W, 0, c.width() - RAIL_W, c.height())
        self.sidebar.setGeometry(0, 0, self.sidebar.width(), c.height())
        self.sidebar.raise_()
        self.rest.overlay.reposition()
        super().resizeEvent(e)

    def show_page(self, name):
        self.page = name
        view = self.pages[name]
        if isinstance(view, WebPage):
            view.ensure(self.course if name == "Courses" else None)
        self.stack.setCurrentWidget(view)
        self.sidebar.set_current("Settings" if name == "Classic Settings" else name, self.course)

    def choose_course(self, cid):
        self.course = cid
        self.show_page("Courses")
