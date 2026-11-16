"""Prompts for the student's own AI chat (Claude, ChatGPT or Gemini): one prompt for each kind of page the app reads, built from the student's course. No Streamlit here.

The pieces are in study/prompts/: `study_guide_rules.md` and `homework_exam_pages.md` (the style and the contents of the pages) and `app_format.md` (what the app needs to recognize a page: the file
name, the section ids, the problem cards, the comment badges, the link texts). A prompt is the pieces that belong to one kind of page, with the course and the number filled in.
"""
import re
from pathlib import Path

PROMPTS = Path(__file__).resolve().parent / "prompts"

# The AI assistants a prompt can be made for. Only what differs between them is here (where the chat is, how the finished page is handed over, how a page of mine is addressed in a link);
# the contents of the prompt are the same. A new assistant is a new entry.
ASSISTANTS = {
    "Claude": {
        "chat": "a Claude chat (claude.ai)", "attach": "attach", "notes_word": "(artifacts)", "republish": "the artifacts are republished in place",
        "publish_job": "publish it as an artifact (HTML, private)",
        "delivery": "publish the page as an HTML artifact and tell me the file name. I download the file and import it in my app with Library > Import > Add a File.",
        "publish_step": "**Publish** with the Artifact tool (HTML, private) using a first-publish `icon` such as `exam` or `homework`. Do not paste the URL in your reply unless I ask; give one sentence on what the page is.",
        "update_step": "**Update in place**: when I ask for a change, publish the same file again to keep the URL. Read the artifact first when it came from an earlier conversation.",
        "link_address": "Write the address you have for my page (an artifact link on any host is fine) and keep",
        "link_example": ".../artifact/<id>#s2-2",
    },
    "ChatGPT": {
        "chat": "a ChatGPT chat (chatgpt.com)", "attach": "upload", "notes_word": "(HTML pages or their text)", "republish": "the pages are given again under the same file names",
        "publish_job": "give it to me as one downloadable `.html` file (create the file with your file tools); if you cannot create a file, put the complete page in one single code block",
        "delivery": "give me the page as one downloadable `.html` file named exactly as above (create the file with your file tools and give me its download link). If you cannot create a file, put the complete page "
                    "in one single code block with nothing else inside it, and I will save it with that name. I import the file in my app with Library > Import > Add a File.",
        "publish_step": "**Deliver** the page as one downloadable `.html` file (create it with your file tools and give me the link); if you cannot create a file, one single code block with the complete page. "
                        "Give one sentence on what the page is.",
        "update_step": "**Update**: when I ask for a change, give me the whole updated file again under the same file name (never only the changed part).",
        "link_address": "Because my notes pages are not on the web, write the address of a notes page as `https://study-assistant.local/artifact/notes-<lecture number>` (the address does not need to exist) and keep",
        "link_example": "https://study-assistant.local/artifact/notes-3#s2-2",
    },
    "Gemini": {
        "chat": "a Gemini chat (gemini.google.com)", "attach": "upload", "notes_word": "(HTML pages or their text)", "republish": "the pages are given again under the same file names",
        "publish_job": "give it to me as one HTML page (use Canvas if you have it, so I can download or copy the code); if you cannot, put the complete page in one single code block",
        "delivery": "give me the page as one complete HTML file named exactly as above (use Canvas if you have it, so I can download it or copy its code). If you cannot, put the complete page in one "
                    "single code block with nothing else inside it, and I will save it with that name. I import the file in my app with Library > Import > Add a File.",
        "publish_step": "**Deliver** the page as one complete HTML file (in Canvas if you have it; otherwise one single code block with the complete page). Give one sentence on what the page is.",
        "update_step": "**Update**: when I ask for a change, give me the whole updated file again under the same file name (never only the changed part).",
        "link_address": "Because my notes pages are not on the web, write the address of a notes page as `https://study-assistant.local/artifact/notes-<lecture number>` (the address does not need to exist) and keep",
        "link_example": "https://study-assistant.local/artifact/notes-3#s2-2",
    },
}

# kind -> (label, number kind, file name pattern, section of app_format.md, the numbered part of "Page Specifications")
KINDS = {
    "Study Guide": ("Study Guide (Notes)", "chapter", "{tag} Chapter {n} Notes", "Study Guide", None),
    "Homework Helper": ("Homework Helper", "homework", "{tag} Homework {n} Helper", "Homework Helper", "1"),
    "Homework Grade Explanation": ("Homework Grade Explanation", "homework", "{tag} Homework {n} Grades", "Homework Grade Explanation", "2"),
    "Exam Grade Explanation": ("Exam Grade Explanation", "exam", "{tag} {n} Grades", "Exam Grade Explanation", "3"),
    "Exam Reflection": ("Exam Reflection", "exam", "{tag} {n} Reflection", "Exam Reflection", "4"),
    "Exam Preparation": ("Exam Preparation", "exam", "{tag} {n} Preparation", "Exam Preparation", "5"),
}
EXAMS = ["Midterm 1", "Midterm 2", "Midterm 3", "Final Exam"]
NUMBER_LABEL = {"chapter": "Chapter or Lecture Number", "homework": "Homework Number", "exam": "Exam"}
STYLE_RULES = ("Format and Navigation", "Math", "Units and Dimensions", "Text Style", "Layout Checks (Every Guide, Before Delivery)")      # the rules of the study guides that pages of the other kinds follow too

ATTACH = {
    "Study Guide": ["the lecture slides (or chapter text) this guide is about, as PDFs", "my own lecture notes for it, if I have any (photos or a scan are fine)", "the other guides of this course I already have, so the style and the links match"],
    "Homework Helper": ["the homework PDF (the problems)", "my notes pages of this course (so you can link to them)", "my earlier graded homework and exams, if there are any (for the lessons section)"],
    "Homework Grade Explanation": ["the graded homework (a scan is fine)", "the Gradescope (or other) grade report with the grader comments, in its own order", "the posted solution, if there is one", "my notes pages of this course (so you can link to them)"],
    "Exam Grade Explanation": ["the graded exam (a scan is fine)", "the grade report with the grader comments, in its own order", "screenshots of the class statistics (mean, standard deviation, top score), if my course software shows them", "my notes pages of this course (so you can link to them)"],
    "Exam Reflection": ["the Exam Grade Explanation page of this exam", "the Exam Preparation page written for this exam, if there is one", "screenshots of the class statistics and of my course software's own reflection, if it has one"],
    "Exam Preparation": ["the list of what the exam covers (homework numbers, chapters) and its date", "the Reflection page of the last exam, if there is one", "every past exam, practice exam and homework in the covered material (with solutions where I have them)", "my notes pages of this course (so you can link to them)"],
}


def course_tag(course):
    """The course as it is written in the page names: the number without a space (AE6765); the first part of a merged course; the name when it has no number."""
    code = (course.get("code") or "").split("/")[0].strip()
    return re.sub(r"\s+", "", code) if code else re.sub(r"\s+", " ", course.get("name") or "Course").strip()


def file_name(kind, course, number):
    """The file name (and page title) of the page, without .html."""
    pattern = KINDS[kind][2]
    n = (number or "").strip() or ("1" if KINDS[kind][1] != "exam" else EXAMS[0])
    return pattern.format(tag=course_tag(course), n=n)


def sections(text, mark="## "):
    """[(heading, body)] for the headings that start with `mark` (the text before the first heading is dropped)."""
    out, name, body = [], None, []
    for line in text.split("\n"):
        if line.startswith(mark) and not line.startswith(mark + "#"):
            if name is not None:
                out.append((name, "\n".join(body).strip()))
            name, body = line[len(mark):].strip(), []
        elif name is not None:
            body.append(line)
    if name is not None:
        out.append((name, "\n".join(body).strip()))
    return out


def _read(name):
    return (PROMPTS / name).read_text(encoding="utf-8")


def _pick(items, names):
    got = dict(items)
    return [(n, got[n]) for n in names if n in got]


def _job(kind, tag, fname, n, assistant="Claude"):
    label = KINDS[kind][0]
    base = f"Build **one** single-file HTML page for my course {tag}: a **{label}**, named exactly `{fname}`, in the format and style described below, and {ASSISTANTS[assistant]['publish_job']}."
    if kind == "Study Guide":
        return base + " It covers the chapter or lecture I name in my message and uses my attached slides as the main source."
    extra = {"Homework Helper": "It is for use before the due date.",
             "Homework Grade Explanation": "It is for after the homework was graded.",
             "Exam Grade Explanation": "It is for after the exam was graded. Exams have a grade explanation only, **no helper page**.",
             "Exam Reflection": "It looks back at one exam that has been graded.",
             "Exam Preparation": "It prepares me for the exam named in the title."}[kind]
    return f"{base} {extra} Do only this page type; I will ask for the others in separate messages."


def _notes_block(notes):
    if not notes:
        return ""
    lines = [f"- Lec {n['lecture']}: {n['title']}" if n.get("lecture") else f"- {n['title']}" for n in notes]
    return ("## My Notes For This Course\n\nThese are the notes pages my app has for this course. Link to their sections with the link forms in **Links**; take the lecture number from this list.\n\n"
            + "\n".join(lines))


def _sources_block(textbooks):
    lines = ["**Lecture slides are the main source for the course.** Textbooks are for supporting explanation and for cross-checking content (equations, numbers, notation), not the backbone of the guide."]
    if textbooks:
        lines.append("\nTextbooks and references I have for this course:\n" + "\n".join(f"- {t}" for t in textbooks))
    return "## Sources\n\n" + "\n".join(lines)


def build_prompt(kind, course, number=None, *, notes=(), textbooks=(), include_rules=True, assistant="Claude"):
    """The prompt for one page. `course`: {"code", "name"}; `number`: the chapter or lecture number, the homework number, or the exam ("Midterm 1", "Final Exam"); `notes`: [{"lecture", "title"}] of
    the course's notes in the Library; `textbooks`: titles; `include_rules`: add the style rules of the study guides (pages of the other kinds follow them too); `assistant`: Claude, ChatGPT or Gemini."""
    if kind not in KINDS:
        raise ValueError(f"Unknown page type: {kind}")
    if assistant not in ASSISTANTS:
        raise ValueError(f"Unknown AI assistant: {assistant}")
    ai = ASSISTANTS[assistant]
    label, number_kind, _pattern, app_key, spec = KINDS[kind]
    tag = course_tag(course)
    n = (number or "").strip() or ("1" if number_kind != "exam" else EXAMS[0])
    fname = file_name(kind, course, n)
    rules = sections(_read("study_guide_rules.md"))
    pages = sections(_read("homework_exam_pages.md"))
    app = dict(sections(_read("app_format.md")))
    parts = [f"# Prompt: {label} for {tag}",
             f"Paste this whole prompt into {ai['chat']} and {ai['attach']} the files listed under Inputs. The style rules are included below, so no other file is needed. "
             "Replace nothing: the course, the page name and the number are already filled in."]
    parts.append("## Your Job\n\n" + _job(kind, tag, fname, n, assistant))
    inputs = "## Inputs I Will Give You\n\nAttached to this message:\n" + "\n".join(f"- {x}" for x in ATTACH[kind]) + "\n\n"
    if kind != "Study Guide":
        inputs += "In general:\n\n" + dict(pages)["Inputs I Will Give You"]
    else:
        inputs += "If a needed input is missing, say what is missing and continue with what you have. Never invent content that is not in the slides; mark anything you add yourself."
    parts.append(inputs)
    app_text = ["## App Format (Required)", app["All Pages"], "### Format of This Page\n\n" + app[KINDS[kind][3]]]
    if kind != "Study Guide":
        app_text.append("### Links\n\n" + app["Links"])
    parts.append("\n\n".join(app_text))
    if kind == "Study Guide":
        parts.append(_sources_block(textbooks))
        if include_rules:
            parts.append("## Study Guide Rules\n\n" + "\n\n".join(f"### {h}\n\n{b}" for h, b in rules))
    else:
        if notes:
            parts.append(_notes_block(notes))
        spec_body = next((b for h, b in sections(dict(pages)["Page Specifications"], "### ") if h.startswith(f"{spec}.")), "")
        spec_title = next((h for h, b in sections(dict(pages)["Page Specifications"], "### ") if h.startswith(f"{spec}.")), label)
        for h, b in _pick(pages, ("Reference Pages (Match These)", "Visual System (Use for Every Page)")):
            parts.append(f"## {h}\n\n{b}")
        parts.append(f"## Page Specification: {spec_title.split('. ', 1)[-1]}\n\n{spec_body}")
        for h, b in _pick(pages, ("Method", "Honesty Rules")):
            parts.append(f"## {h}\n\n{b}")
        if include_rules:
            parts.append("## Style Rules (From My Study Guides)\n\nThese rules apply to this page too; the page specification above adds to them.\n\n"
                         + "\n\n".join(f"### {h}\n\n{b}" for h, b in _pick(rules, STYLE_RULES)))
    text = "\n\n".join(p for p in parts if p)
    for token, value in (("{{NOTES_WORD}}", ai["notes_word"]), ("{{REPUBLISH}}", ai["republish"]), ("{{DELIVERY}}", ai["delivery"]), ("{{PUBLISH_STEP}}", ai["publish_step"]),
                         ("{{UPDATE_STEP}}", ai["update_step"]), ("{{LINK_ADDRESS}}", ai["link_address"]), ("{{LINK_EXAMPLE}}", ai["link_example"])):
        text = text.replace(token, value)
    if assistant != "Claude":                                                      # a Claude-only meta tag and the Artifact tool's words
        text = text.replace('<meta name="claude:viewport-fit-sides" content="cover">', '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">')
    text = text.replace("<COURSE>", tag).replace("<FILE>", fname).replace("<N>", re.sub(r"\D", "", n) or n)
    if number_kind == "homework":
        text = re.sub(r"\bHomework n\b", f"Homework {n}", text)
    elif number_kind == "exam":
        text = re.sub(r"\bMidterm n\b", n, text)
    return text + "\n"
