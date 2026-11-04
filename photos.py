"""Course photos: stored as small JPEGs under data/course_photos (one per course)."""
from io import BytesIO

from PIL import Image, ImageOps

from database import BASE_DIR

PHOTO_DIR = BASE_DIR / "data" / "course_photos"
MAX_SIDE = 900

# Every common photo format (no documents such as PDF or HTML). HEIC/HEIF are phone camera formats.
PHOTO_TYPES = ["png", "jpg", "jpeg", "jpe", "jfif", "webp", "gif", "bmp", "tif", "tiff", "heic", "heif"]

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:  # HEIC photos just won't open without the optional package
    pass


def photo_path(course_id):
    """Path of the course's photo if it has one, else None."""
    p = PHOTO_DIR / f"course_{course_id}.jpg"
    return p if p.exists() else None


def save_photo(course_id, data):
    """Store an uploaded image (any common format) as a resized JPEG. Returns False if it can't be read."""
    try:
        img = ImageOps.exif_transpose(Image.open(BytesIO(data))).convert("RGB")
    except Exception:
        return False
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    img.save(PHOTO_DIR / f"course_{course_id}.jpg", "JPEG", quality=85)
    return True


def remove_photo(course_id):
    p = PHOTO_DIR / f"course_{course_id}.jpg"
    if p.exists():
        p.unlink()
