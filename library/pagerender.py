"""Background worker for the scrolling PDF view: renders page JPEGs into static/pages, nearest the current page
first. It runs as its own process so rendering never slows the app down.

    python pagerender.py <pdf> <out folder> <center page index> <pixel width>
"""
import os
import sys


def render_all(pdf, out_dir, center, width):
    import pymupdf
    os.makedirs(out_dir, exist_ok=True)
    with pymupdf.open(pdf) as doc:
        total = doc.page_count
        order = [center]
        for d in range(1, total):
            order += [i for i in (center + d, center - d) if 0 <= i < total]
        for i in order:
            out = os.path.join(out_dir, f"{i + 1}.jpg")
            if os.path.exists(out):
                continue
            page = doc[i]
            zoom = width / page.rect.width
            data = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False).tobytes("jpg", jpg_quality=85)
            tmp = f"{out}.{os.getpid()}.tmp"
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, out)


def main(argv):
    pdf, out_dir, center, width = argv[0], argv[1], int(argv[2]), int(argv[3])
    render_all(pdf, out_dir, center, width)


if __name__ == "__main__":
    main(sys.argv[1:])
