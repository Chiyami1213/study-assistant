"""Turn a Claude-generated HTML note (Library) into the Note Builder's standard starting format:
a Notes outline (one block per section) and an Exercises skeleton, ready to be tailored."""
import re


def _math(text):
    """MathJax \\( ... \\) -> Markdown $ ... $ ; tidy spaces."""
    text = re.sub(r"\\\((.+?)\\\)", lambda m: f"${m.group(1).strip()}$", text, flags=re.S)
    return re.sub(r"\s+", " ", text).strip()


def outline_from_html(html_text):
    """(title, notes_markdown, exercises_markdown) for a Claude-generated HTML note."""
    body = re.sub(r"<(script|style)\b.*?</\1>", "", html_text, flags=re.S | re.I)
    sections = []                  # [title, [subheadings]]
    title = ""
    pos_titles = []        # (kind, text) in page order
    for m in re.finditer(r"<(h1|h2|h3|h4)[^>]*>(.*?)</\1>|<div class=\"deriv-head\".*?<b>(.*?)</b>", body, re.S):
        if m.group(1):
            inner = m.group(2)
            inner = re.sub(r'<span class="num">.*?</span>', "", inner, flags=re.S)
            text = _math(re.sub(r"<[^>]+>", "", inner))
            text = re.sub(r"&amp;", "&", text)
            pos_titles.append((m.group(1), text))
        else:
            text = _math(re.sub(r"<[^>]+>", "", m.group(3)))
            pos_titles.append(("deriv", re.sub(r"&amp;", "&", text)))
    for kind, text in pos_titles:
        if not text:
            continue
        if kind == "h1" and not title:
            title = text
        elif kind == "h2":
            sections.append([text, []])
        elif kind in ("h3", "h4", "deriv") and sections:
            sections[-1][1].append(("Derivation: " + text) if kind == "deriv" else text)
    notes, exercises = [], []         # the chapter title is the page heading, so the bodies start at the sections
    for i, (name, subs) in enumerate(sections, 1):
        notes += [f"## {i}. {name}", "", "**Key Idea:** ", "", "**Equations**", "", "$$  $$", ""]
        for s in subs:
            notes += [f"### {s}", "", "- ", ""]
        notes += ["**Example:** ", ""]
        exercises += [f"## {i}. {name}", "", "**Problem:** ", "", "**Solution:** ", ""]
    return title, "\n".join(notes).rstrip() + "\n", "\n".join(exercises).rstrip() + "\n"
