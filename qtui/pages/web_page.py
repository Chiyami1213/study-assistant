"""A page that is still drawn by the classic interface: a browser view (Qt WebEngine) of the hidden local server. Each classic page keeps its own view, so what is open in it stays open when you go to another page and back."""
from PySide6.QtCore import QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView

from qtui import server


class WebPage(QWebEngineView):
    def __init__(self, page, parent=None):
        super().__init__(parent)
        self.page_name = page
        self.course = None
        self._loaded = False

    def load(self, url):
        """Shows this address now (a classic page opened at a file, for example)."""
        self._loaded = True
        self.setUrl(QUrl(url))

    def ensure(self, course=None):
        """Loads the page the first time it is shown (and again when another course is chosen)."""
        if not self._loaded or (self.page_name == "Courses" and course != self.course):
            self.course = course
            self._loaded = True
            self.setUrl(QUrl(server.url(self.page_name, course)))
