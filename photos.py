"""Course photos.

Every photo is stored in four ready-made resolutions (HD, Full HD, 2K, 4K) the moment it is added, even when the
original is smaller (it is scaled up). Choosing a different quality in Settings then only picks another stored file,
so nothing has to be generated at that point.
"""
import re
from io import BytesIO

from PIL import Image, ImageOps

import settings
from database import BASE_DIR

PHOTO_DIR = BASE_DIR / "data" / "course_photos"

# key -> (name, width, height). Each version is scaled (keeping the aspect ratio) so it covers this frame.
TIERS = {
    "hd": ("HD", 1280, 720),
    "fullhd": ("Full HD", 1920, 1080),
    "2k": ("2K", 2560, 1440),
    "4k": ("4K", 3840, 2160),
}
DEFAULT_TIER = "fullhd"
JPEG_QUALITY = 90

# Every common photo format (no documents such as PDF or HTML). HEIC/HEIF are phone camera formats.
PHOTO_TYPES = ["png", "jpg", "jpeg", "jpe", "jfif", "webp", "gif", "bmp", "tif", "tiff", "heic", "heif"]

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:  # HEIC photos just won't open without the optional package
    pass


def tier_label(key):
    name, w, h = TIERS[key]
    return f"{name} ({w} × {h})"


def _tier_path(course_id, tier):
    return PHOTO_DIR / f"course_{course_id}_{tier}.jpg"


def _legacy_path(course_id):
    return PHOTO_DIR / f"course_{course_id}.jpg"


def photo_path(course_id, tier=None):
    """The course's photo at the chosen quality (default: the Settings choice), or None if it has no photo."""
    tier = tier or settings.get_photo_quality()
    for candidate in (_tier_path(course_id, tier), *(_tier_path(course_id, t) for t in TIERS), _legacy_path(course_id)):
        if candidate.exists():
            return candidate
    return None


def photo_size(course_id, tier=None):
    """(width, height) in pixels of the stored photo at the chosen quality, or None."""
    p = photo_path(course_id, tier)
    if not p:
        return None
    with Image.open(p) as img:
        return img.size


def _cover(img, width, height):
    """Scale up or down so the image covers width x height, keeping its aspect ratio."""
    scale = max(width / img.width, height / img.height)
    size = (max(1, round(img.width * scale)), max(1, round(img.height * scale)))
    return img.resize(size, Image.Resampling.LANCZOS)


def save_photo(course_id, data):
    """Store an uploaded image (any common format) in every quality tier. Returns False if it can't be read."""
    try:
        img = ImageOps.exif_transpose(Image.open(BytesIO(data))).convert("RGB")
    except Exception:
        return False
    PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    for key, (_, w, h) in TIERS.items():
        _cover(img, w, h).save(_tier_path(course_id, key), "JPEG", quality=JPEG_QUALITY, optimize=True)
    if _legacy_path(course_id).exists():
        _legacy_path(course_id).unlink()
    return True


def remove_photo(course_id):
    for p in [_legacy_path(course_id), *(_tier_path(course_id, t) for t in TIERS)]:
        if p.exists():
            p.unlink()


def upgrade_legacy_photos():
    """Photos saved before quality tiers existed (course_<id>.jpg) get all four versions generated once."""
    if not PHOTO_DIR.exists():
        return
    for p in PHOTO_DIR.glob("course_*.jpg"):
        m = re.fullmatch(r"course_(\d+)\.jpg", p.name)
        if m:
            save_photo(int(m.group(1)), p.read_bytes())
