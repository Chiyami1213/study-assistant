"""Grade explanations of graded homework and exams.

A Gradescope grade report (PDF) is read into {total, problems, comments}; Canvas-only grades are stored the same way with fewer
details. The explanation of one graded file is kept in data/grading/<book id>.json and shown beside the file in the Library."""
import json
import re

import pymupdf

from database import BASE_DIR

DIR = BASE_DIR / "data" / "grading"


def load(book_id):
    try:
        return json.loads((DIR / f"{book_id}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def save(book_id, data):
    DIR.mkdir(parents=True, exist_ok=True)
    (DIR / f"{book_id}.json").write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")


def lost(item_text):
    """True for a rubric line that cost points: "+ 0 pts ..." or a partial credit line that names its maximum, "(/1.5)"."""
    return bool(re.match(r"0 pts?\b", item_text) or re.search(r"\(/\s*[\d.]+\)", item_text))


def from_report(path, solution_pages=None):
    """{source, total, problems: [{n, title, score, max, page, solution_page, items: [{text, lost, comment}]}],
    comments: [{id, text, page, problem}]} from a Gradescope grade report PDF."""
    doc = pymupdf.open(path)
    first = next(i for i, p in enumerate(doc) if "Question assigned to the following page" in p.get_text())
    text = re.sub(r"[-]", "", "\n".join(doc[i].get_text() for i in range(first)))
    total = re.search(r"([\d.]+) / ([\d.]+) pts", text)
    problems, cur, comments = [], None, {}
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        ln = lines[i].strip()
        m = re.fullmatch(r"Question (\d+)", ln)
        if m:
            cur = {"n": int(m.group(1)), "title": lines[i + 1].strip(), "items": []}
            problems.append(cur)
            i += 2
            continue
        m = re.fullmatch(r"([\d.]+) / ([\d.]+) pts", ln)
        if m and cur is not None and "score" not in cur:
            cur["score"], cur["max"] = float(m.group(1)), float(m.group(2))
        elif ln.startswith("+ ") and cur is not None:
            body = ln[2:].strip()
            cur["items"].append({"text": body, "lost": lost(body), "comment": None})
        elif re.fullmatch(r"\d+", ln) and cur is not None and cur["items"]:
            body = []
            i += 1
            while i < len(lines) and lines[i].strip() and not lines[i].strip().startswith("+ ") \
                    and not re.fullmatch(r"Question \d+", lines[i].strip()):
                body.append(lines[i].strip())
                i += 1
            comments[int(ln)] = " ".join(body)
            cur["items"][-1]["comment"] = int(ln)
            continue
        i += 1
    page_of, question_of, first_page = {}, {}, {}
    for pi in range(first, doc.page_count):
        page = doc[pi]
        mq = re.search(r"Question assigned to the following page: (\d+)", page.get_text())
        if mq:
            question_of[pi - first + 1] = int(mq.group(1))
            first_page.setdefault(int(mq.group(1)), pi - first + 1)
        for b in page.get_text("dict")["blocks"]:
            for ln in b.get("lines", []):
                for sp in ln["spans"]:
                    if sp["text"].strip().isdigit() and sp["size"] < 6:
                        page_of[int(sp["text"])] = pi - first + 1
    out_comments = [{"id": cid, "text": t, "page": page_of.get(cid), "problem": question_of.get(page_of.get(cid))}
                    for cid, t in sorted(comments.items())]
    for pr in problems:
        pr["page"] = first_page.get(pr["n"])
        pr["solution_page"] = (solution_pages or {}).get(pr["n"])
    return {"source": "Gradescope grade report", "total": [float(total.group(1)), float(total.group(2))] if total else None,
            "problems": problems, "comments": out_comments, "general": []}
