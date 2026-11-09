"""Render PDF pages to images (covers and the in-app preview) with PyMuPDF."""
import warnings

from database import DATA_DIR

warnings.filterwarnings("ignore", category=FutureWarning)
try:
    import pymupdf
except ImportError:  # older PyMuPDF versions expose it as fitz
    import fitz as pymupdf

COVER_DIR = DATA_DIR / "covers"


def page_count(pdf_path):
    with pymupdf.open(pdf_path) as doc:
        return doc.page_count


def render_page(pdf_path, page_index=0, width=900, fmt="png"):
    """Image bytes (PNG, or JPEG for fmt="jpg") of one page scaled to the given pixel width."""
    with pymupdf.open(pdf_path) as doc:
        page = doc[page_index]
        zoom = width / page.rect.width
        pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
        return pix.tobytes("jpg", jpg_quality=85) if fmt == "jpg" else pix.tobytes("png")


def render_cover(pdf_path, width=300):
    """Small JPEG of page 1: a fraction of the size of a PNG, so many covers stay light."""
    with pymupdf.open(pdf_path) as doc:
        page = doc[0]
        zoom = width / page.rect.width
        return page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False).tobytes("jpg", jpg_quality=72)


def cover_path(book_id):
    return COVER_DIR / f"book_{book_id}.jpg"


def ensure_cover(book_id, pdf_path):
    """Path of the book's cover image (page 1), created on first use; None if it can't be rendered."""
    out = cover_path(book_id)
    if not out.exists():
        try:
            COVER_DIR.mkdir(parents=True, exist_ok=True)
            out.write_bytes(render_cover(pdf_path))
        except Exception:
            return None
    return out


def remove_cover(book_id):
    for p in (cover_path(book_id), COVER_DIR / f"book_{book_id}.png"):
        if p.exists():
            p.unlink()
