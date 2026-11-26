"""A PDF of the Library, read natively (Qt PDF): page by page or scrolling, zoom to the width of the window or any size."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSpinBox, QVBoxLayout, QWidget

from core.database import data_path


class PdfPage(QWidget):
    back_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("page")
        self.doc = QPdfDocument(self)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 16, 24, 8)
        bar = QHBoxLayout()
        back = QPushButton("‹ Back")
        back.clicked.connect(self.back_requested.emit)
        bar.addWidget(back)
        self.title = QLabel()
        self.title.setStyleSheet("font-size: 17px; font-weight: 700; background: transparent;")
        bar.addWidget(self.title, 1)
        self.page = QSpinBox()
        self.page.setMinimum(1)
        self.page.setFixedWidth(90)
        self.total = QLabel("/ 1")
        self.page.valueChanged.connect(self._go)
        zoom_out, zoom_in, fit = QPushButton("−"), QPushButton("+"), QPushButton("Fit Width")
        zoom_out.setFixedWidth(40)
        zoom_in.setFixedWidth(40)
        zoom_out.clicked.connect(lambda: self._zoom(1 / 1.15))
        zoom_in.clicked.connect(lambda: self._zoom(1.15))
        fit.clicked.connect(self._fit)
        for w in (QLabel("Page"), self.page, self.total, zoom_out, zoom_in, fit):
            bar.addWidget(w)
        lay.addLayout(bar)
        self.view = QPdfView()
        self.view.setDocument(self.doc)
        self.view.setPageMode(QPdfView.PageMode.MultiPage)
        self.view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        self.view.pageNavigator().currentPageChanged.connect(self._shown)
        lay.addWidget(self.view, 1)

    def open(self, book):
        self.title.setText(book["title"])
        self.doc.load(str(data_path(book["pdf_path"])))
        n = max(1, self.doc.pageCount())
        self.page.blockSignals(True)
        self.page.setMaximum(n)
        self.page.setValue(1)
        self.page.blockSignals(False)
        self.total.setText(f"/ {n}")
        self.view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        self.view.pageNavigator().jump(0, self.view.pageNavigator().currentLocation(), 0)

    def _go(self, n):
        self.view.pageNavigator().jump(n - 1, self.view.pageNavigator().currentLocation(), 0)

    def _shown(self, index):
        self.page.blockSignals(True)
        self.page.setValue(index + 1)
        self.page.blockSignals(False)

    def _zoom(self, factor):
        self.view.setZoomMode(QPdfView.ZoomMode.Custom)
        self.view.setZoomFactor(self.view.zoomFactor() * factor)

    def _fit(self):
        self.view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
