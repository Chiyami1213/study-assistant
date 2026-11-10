"""Course photos.

An uploaded photo is copied into data/course_photos as a JPEG named after its course (for example
MATH_101_Linear_Algebra.jpg), at the uploaded resolution. The app never keeps a link to the file you picked, so
the original can be deleted. If a course is renamed, its photo file is renamed to match.
"""
import re
from io import BytesIO

from PIL import Image, ImageOps

from database import DATA_DIR, get_conn

PHOTO_DIR = DATA_DIR / "course_photos"
MAX_SIDE = 3840      # only protects against enormous files; smaller photos are never enlarged
JPEG_QUALITY = 95

# Every common photo format (no documents such as PDF or HTML). HEIC/HEIF are phone camera formats.
PHOTO_TYPES = ["png", "jpg", "jpeg", "jpe", "jfif", "webp", "gif", "bmp", "tif", "tiff", "heic", "heif"]

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:  # HEIC photos just won't open without the optional package
    pass


def _course(course_id):
    with get_conn() as conn:
        row = conn.execute("SELECT code, name, photo_file FROM courses WHERE id=?", (course_id,)).fetchone()
    return dict(row) if row else None


def _set_file(course_id, filename):
    with get_conn() as conn:
        conn.execute("UPDATE courses SET photo_file=? WHERE id=?", (filename, course_id))
        conn.commit()


def _legacy_path(course_id):
    return PHOTO_DIR / f"course_{course_id}.jpg"   # name used by earlier versions of the app


def _logical_name(course_id, code, name):
    """MATH 101 + Linear Algebra -> MATH_101_Linear_Algebra.jpg (unique across courses)."""
    parts = [code] if code else []
    if name and name != code:
        parts.append(name)
    base = re.sub(r"[^A-Za-z0-9]+", "_", " ".join(parts)).strip("_")[:80] or "Course"
    filename = f"{base}.jpg"
    with get_conn() as conn:
        taken = conn.execute("SELECT 1 FROM courses WHERE photo_file=? AND id!=?", (filename, course_id)).fetchone()
    return f"{base}_{course_id}.jpg" if taken else filename


def photo_path(course_id):
    """The course's photo file, or None if it has none."""
    c = _course(course_id)
    if c and c["photo_file"] and (PHOTO_DIR / c["photo_file"]).exists():
        return PHOTO_DIR / c["photo_file"]
    return _legacy_path(course_id) if _legacy_path(course_id).exists() else None


def save_photo(course_id, data):
    """Copy an uploaded image (any common format) into the project as a JPEG. False if it can't be read."""
    c = _course(course_id)
    if not c:
        return False
    try:
        img = ImageOps.exif_transpose(Image.open(BytesIO(data))).convert("RGB")
    except Exception:
        return False
    img.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)  # shrinks only when larger than MAX_SIDE
    PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    filename = _logical_name(course_id, c["code"], c["name"])
    img.save(PHOTO_DIR / filename, "JPEG", quality=JPEG_QUALITY, subsampling=0, optimize=True)
    for old in (c["photo_file"], _legacy_path(course_id).name):
        if old and old != filename and (PHOTO_DIR / old).exists():
            (PHOTO_DIR / old).unlink()
    _set_file(course_id, filename)
    return True


def remove_photo(course_id):
    c = _course(course_id)
    for name in (c["photo_file"] if c else None, _legacy_path(course_id).name):
        if name and (PHOTO_DIR / name).exists():
            (PHOTO_DIR / name).unlink()
    if c:
        _set_file(course_id, None)


def rename_photo(course_id):
    """Keep the photo's file name in step with its course's number and name."""
    c = _course(course_id)
    current = photo_path(course_id)
    if not c or not current:
        return
    filename = _logical_name(course_id, c["code"], c["name"])
    if current.name != filename:
        current.rename(PHOTO_DIR / filename)
        _set_file(course_id, filename)


def organize_photos():
    """Photos saved under the old id-based names (course_<id>.jpg) get their course-based names once."""
    if not PHOTO_DIR.exists():
        return
    for p in PHOTO_DIR.glob("course_*.jpg"):
        m = re.fullmatch(r"course_(\d+)\.jpg", p.name)
        if m and _course(int(m.group(1))):
            rename_photo(int(m.group(1)))
