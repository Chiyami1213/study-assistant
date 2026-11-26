"""A page that is still drawn by the classic interface: a browser view (Qt WebEngine) of the hidden local server. Each classic page keeps its own view, so what is open in it stays open when you go to another page and back."""
from PySide6.QtCore import QTimer, QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView

from qtui import server


class WebPage(QWebEngineView):
    def __init__(self, page, parent=None):
        super().__init__(parent)
        self.page_name = page
        self.course = None
        self._loaded = False

    def load(self, url):
        """Shows this address now (a classic page opened at a file, for example). While the hidden server is still starting a waiting page is shown and the address is loaded as soon as it answers."""
        self._loaded = True
        self._url = url
        if server.ready():
            self.setUrl(QUrl(url))
            return
        self.setHtml("<body style='background:#0e1117;color:#c9d1d9;font-family:Segoe UI,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh'>"
                     "<div>Starting the classic page…</div></body>")
        self._wait()

    def _wait(self):
        def check():
            if server.ready():
                self.setUrl(QUrl(self._url))
            else:
                QTimer.singleShot(500, check)
        QTimer.singleShot(500, check)

    def ensure(self, course=None):
        """Loads the page the first time it is shown (and again when another course is chosen)."""
        if not self._loaded or (self.page_name == "Courses" and course != self.course):
            self.course = course
            self.load(server.url(self.page_name, course))
