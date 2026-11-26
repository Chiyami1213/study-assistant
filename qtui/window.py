"""The main window: the menu on the left (it floats over the page when it opens) and the page beside it."""
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QLabel, QMainWindow, QStackedWidget, QVBoxLayout, QWidget

from core import crud, settings
from qtui import server, theme
from qtui.eyerest import EyeRestController
from qtui.pages.courses_page import CoursesPage
from qtui.pages.home_page import HomePage
from qtui.pages.library_page import LibraryPage
from qtui.pages.pdf_page import PdfPage
from qtui.pages.quiz_page import QuizPage
from qtui.pages.settings_page import SettingsPage
from qtui.pages.web_page import WebPage
from qtui.sidebar import Sidebar
from qtui.theme import RAIL_W

CLASSIC = ["Calendar", "Note Reader"]            # the pages still drawn by the classic interface


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
        self.library = LibraryPage()
        self.library.open_book.connect(self.open_book)
        self.library.classic_requested.connect(lambda what: self.show_page("Classic Library"))
        self.pages["Library"] = self.library
        self.stack.addWidget(self.library)
        self.home = HomePage()
        self.home.course_requested.connect(self.choose_course)
        self.home.classic_requested.connect(lambda what: self.show_page("Classic Home"))
        self.pages["Home"] = self.home
        self.stack.addWidget(self.home)
        self.pages["Classic Home"] = WebPage("Home") if use_server else QLabel("Home (classic page)")
        self.stack.addWidget(self.pages["Classic Home"])
        self.courses = CoursesPage()
        self.courses.open_book.connect(self.open_book)
        self.courses.quiz_requested.connect(self.open_quiz)
        self.courses.classic_requested.connect(self.open_classic_courses)
        self.courses.changed.connect(self._courses_changed)
        self.pages["Courses"] = self.courses
        self.stack.addWidget(self.courses)
        self.pages["Classic Courses"] = WebPage("Courses") if use_server else QLabel("Courses (classic page)")
        self.stack.addWidget(self.pages["Classic Courses"])
        self.quiz = QuizPage(self._colors())
        self.pages["Quiz"] = self.quiz
        self.stack.addWidget(self.quiz)
        self.pdf = PdfPage()
        self.back_page = "Library"
        self.pdf.back_requested.connect(lambda: self.show_page(self.back_page))
        self.stack.addWidget(self.pdf)
        self.pages["Classic Library"] = WebPage("Library") if use_server else QLabel("Library (classic page)")
        self.stack.addWidget(self.pages["Classic Library"])
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
        self.quiz.set_colors(c)

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
        if name == "Quiz":
            self.quiz.set_course(self.course)
        if name == "Home":
            self.home.refresh()                              # what was done elsewhere shows at once
        self.stack.setCurrentWidget(view)
        self.sidebar.set_current({"Classic Settings": "Settings", "Classic Library": "Library", "Classic Courses": "Courses", "Classic Home": "Home"}.get(name, name), self.course)

    def open_book(self, book_id):
        """A PDF is read here; the other files (the interactive notes, helpers and grade pages) are still opened by the classic Library."""
        book = crud.get_book(book_id)
        if not book:
            return
        self.back_page = self.page if self.page in ("Library", "Courses") else "Library"
        if book["pdf_path"].lower().endswith(".pdf"):
            self.pdf.open(book)
            self.stack.setCurrentWidget(self.pdf)
            self.sidebar.set_current("Library", self.course)
        elif self.use_server:
            self.pages["Classic Library"].load(server.url("Library", book=book_id))
            self.show_page("Classic Library")

    def choose_course(self, cid):
        self.course = cid
        self.show_page("Courses")
        self.courses.open_course(cid)

    def open_quiz(self, cid):
        self.course = cid
        self.show_page("Quiz")

    def open_classic_courses(self, what, cid):
        """The parts of the Courses page that are still classic: the tree, merging, the syllabus, the outline editor, the tour (opened at the course when there is one)."""
        if not self.use_server:
            return
        self.pages["Classic Courses"].load(server.url("Courses", cid))
        self.show_page("Classic Courses")

    def _courses_changed(self):
        self.sidebar.refresh_courses()
        self.quiz.reload_courses()
