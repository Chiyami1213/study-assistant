"""The Courses page as a tree of knowledge (Courses > All > Tree): every course is a leaf on a branch, and similar fields grow from the same branch.

Levels, like the levels of the tree of life: Domain (Engineering, Natural Sciences, ...) > Field (Aerospace Engineering, Physics, ...) > Topic (Fluids and Aerodynamics,
Propulsion and Energy, ...) > Course. The field comes from the course's category when it has one, else from the letters of its course number (AE, PHYS, MATH ...); the topic from
words in its name. `build_tree` is pure; `tree_html` draws it (branches fold and unfold with a CSS animation, see app.py)."""
import html
import math
import re

import crud

# letters of a course number -> field; a category the student typed is matched by the words in FIELD_WORDS
PREFIX_FIELD = {"AE": "Aerospace Engineering", "AAE": "Aerospace Engineering", "AERO": "Aerospace Engineering", "ASE": "Aerospace Engineering", "MAE": "Mechanical Engineering",
                "ME": "Mechanical Engineering", "NUCL": "Nuclear Engineering", "NRE": "Nuclear Engineering", "ECE": "Electrical and Computer Engineering",
                "EE": "Electrical and Computer Engineering", "CE": "Civil Engineering", "CHE": "Chemical Engineering", "CS": "Computer Science", "CSE": "Computer Science",
                "COMP": "Computer Science", "PHYS": "Physics", "PHY": "Physics", "CHEM": "Chemistry", "BIOL": "Biology", "MATH": "Mathematics", "MA": "Mathematics",
                "STAT": "Statistics", "ISYE": "Industrial Engineering", "ECON": "Economics", "ENGL": "Humanities", "HIST": "Humanities", "PHIL": "Humanities"}
FIELD_WORDS = (("aero", "Aerospace Engineering"), ("mechanical", "Mechanical Engineering"), ("nuclear", "Nuclear Engineering"), ("electr", "Electrical and Computer Engineering"),
               ("civil", "Civil Engineering"), ("chemical", "Chemical Engineering"), ("computer", "Computer Science"), ("physics", "Physics"), ("chem", "Chemistry"),
               ("bio", "Biology"), ("math", "Mathematics"), ("stat", "Statistics"), ("econ", "Economics"), ("human", "Humanities"))
FIELD_DOMAIN = {"Aerospace Engineering": "Engineering", "Mechanical Engineering": "Engineering", "Nuclear Engineering": "Engineering", "Electrical and Computer Engineering": "Engineering",
                "Civil Engineering": "Engineering", "Chemical Engineering": "Engineering", "Industrial Engineering": "Engineering", "Physics": "Natural Sciences",
                "Chemistry": "Natural Sciences", "Biology": "Natural Sciences", "Mathematics": "Mathematics and Computing", "Statistics": "Mathematics and Computing",
                "Computer Science": "Mathematics and Computing", "Economics": "Humanities and Social Sciences", "Humanities": "Humanities and Social Sciences"}
# a course without a course number (self-study) is placed by the words in its name
NAME_FIELDS = ((("anatom", "physiolog", "biolog", "genetic", "neuro", "medic", "cell "), "Biology"), (("chem", "pyro", "molecul"), "Chemistry"),
               (("econom", "financ", "accounting", "market"), "Economics"), (("calculus", "algebra", "statistic", "probab", "geometry", "topology", "math"), "Mathematics"),
               (("music", "tonal", "piano", "guitar", "violin", "harmony", "singing", "choir", "drum"), "Music"), (("quantum", "physics", "relativity", "optics", "thermodynamic"), "Physics"),
               (("orbit", "rocket", "aerodynam", "propulsion", "flight", "aerospace", "aircraft", "spacecraft"), "Aerospace Engineering"),
               (("program", "python", "algorithm", "computer", "software", "machine learning", "data science", "coding"), "Computer Science"),
               (("language", "japanese", "english", "spanish", "chinese", "french", "history", "philosoph", "psycholog", "literature", "writing"), "Humanities"))
FIELD_DOMAIN["Music"] = "Humanities and Social Sciences"
SELF_STUDY, OTHER_DOMAIN, OTHER_FIELD, GENERAL = "Self-Study", "Other Subjects", "Other", "General"

# topics inside a field, by words in the course name (the first group that matches wins)
TOPICS = (("Space and Orbits", ("orbit", "space", "astrodynamic", "satellite", "spacecraft", "planetary", "launch")),
          ("Fluids and Aerodynamics", ("fluid", "aerodynamic", "viscous", "boundary", "gas dynamic", "compressible", "hydrodynamic", "flow")),
          ("Propulsion and Energy", ("propulsion", "rocket", "engine", "combustion", "thermo", "heat", "energy", "kinetics", "plasma", "power")),
          ("Structures and Materials", ("structur", "material", "stress", "solid", "composite", "elastic")),
          ("Dynamics and Control", ("control", "dynamics", "vibration", "stability", "flight", "navigation", "guidance", "robot")),
          ("Quantum and Modern Physics", ("quantum", "relativity", "atomic", "nuclear", "particle", "optics", "electromagnet")),
          ("Mathematics and Methods", ("calculus", "differential", "linear algebra", "equation", "numerical", "statistic", "probability", "analysis", "optimization")),
          ("Computing and Data", ("comput", "program", "data", "algorithm", "software", "machine learning", "signal")),
          ("Design and Systems", ("design", "systems", "introduction", "intro ", "project", "laboratory", "lab ")))


def field_of(course):
    """The field of a course: its category when that names a known field (or else the category itself), else the field of its course number, else Self-Study / Other."""
    category = (course.get("category") or "").strip()
    if category:
        low = category.lower()
        for word, field in FIELD_WORDS:
            if word in low:
                return field
        return category
    code = (course.get("code") or "").strip()
    if not code:
        name = f" {(course.get('name') or '').lower()} "
        for words, field in NAME_FIELDS:
            if any(w in name for w in words):
                return field
        return SELF_STUDY
    letters = re.match(r"[A-Za-z]+", code)
    return PREFIX_FIELD.get(letters.group().upper(), letters.group().upper()) if letters else OTHER_FIELD


def domain_of(field):
    return FIELD_DOMAIN.get(field, SELF_STUDY if field == SELF_STUDY else OTHER_DOMAIN)


def topic_of(course):
    name = f" {(course.get('name') or '').lower()} "
    for topic, words in TOPICS:
        if any(w in name for w in words):
            return topic
    return GENERAL


def build_tree(courses):
    """[(domain, [(field, [(topic, [course])])])] with the domains, fields and topics in alphabetical order (Self-Study and the unnamed ones last), and the courses by number."""
    tree = {}
    for c in courses:
        field = field_of(c)
        tree.setdefault(domain_of(field), {}).setdefault(field, {}).setdefault(topic_of(c) if field != SELF_STUDY else GENERAL, []).append(c)   # (self-study only when no field fits)
    last = lambda name: (name in (SELF_STUDY, OTHER_DOMAIN, OTHER_FIELD, GENERAL), name.lower())
    out = []
    for domain in sorted(tree, key=last):
        fields = []
        for field in sorted(tree[domain], key=last):
            topics = [(t, sorted(cs, key=lambda c: ((c.get("code") or c.get("name") or "").lower(), c["id"]))) for t, cs in sorted(tree[domain][field].items(), key=lambda kv: last(kv[0]))]
            fields.append((field, topics))
        out.append((domain, fields))
    return out


def count(node_children):
    return sum(len(cs) for _, cs in node_children)


def _hue(i, n):
    """The colors of the domains run around the color wheel, like the levels of the tree of life."""
    return round(210 + 300 * i / max(1, n)) % 360


# ---------------------------------------------------------------- the map: a tree from left to right, a pill for the whole, each domain, field, topic and course
HEIGHT = {0: 46, 1: 40, 2: 36, 3: 34, 4: 34}          # root, domain, field, topic, course
SIZE = {0: 21, 1: 18, 2: 16, 3: 15, 4: 15}            # the size of the text of each level
PITCH = 58                                            # the distance between two rows
GAP = 120                                             # the distance between two columns


def _width(text, size, bold=True):
    return len(text) * size * (0.60 if bold else 0.53)


def layout(courses, status_of=None):
    """The map as nodes {id, parent, level, label, name, count, course, w, h, x, y, hue, kids}: x is the left edge of the node and y its middle. The levels are columns (left to right: the whole,
    domain, field, topic, course); the courses are rows in the order of the branches, and a branch is in the middle of its rows. Returns (nodes, (left, top, right, bottom)) of what is drawn."""
    tree = build_tree(courses)
    nodes = []

    def make(level, parent, label, **extra):
        node = {"id": f"n{len(nodes) + 1}", "parent": parent, "level": level, "label": label, "name": "", "count": 0, "course": None, "hue": 210, "kids": [], "y": 0.0, **extra}
        node["h"] = HEIGHT[level]
        nodes.append(node)
        if parent:
            next(n for n in nodes if n["id"] == parent)["kids"].append(node["id"])
        return node

    root = make(0, None, "All Courses", count=len(courses))
    for i, (domain, fields) in enumerate(tree):
        hue = _hue(i, len(tree))
        dn = make(1, root["id"], domain, count=sum(count(ts) for _, ts in fields), hue=hue)
        for j, (field, topics) in enumerate(fields):
            fh = (hue + 6 * j) % 360
            fn = make(2, dn["id"], field, count=count(topics), hue=fh)
            for k, (topic, cs) in enumerate(topics):
                tn = make(3, fn["id"], topic, count=len(cs), hue=(fh + 5 * k) % 360)
                for c in cs:
                    make(4, tn["id"], c.get("code") and crud.show_code(c["code"]) or c.get("name") or "Course", course=c, hue=tn["hue"],
                         name="" if (not c.get("code") or c.get("name") == c.get("code")) else c.get("name") or "")
    for n in nodes:                                                          # the width of a pill: its text and, for a branch, the number of courses behind it
        size = SIZE[n["level"]]
        text = _width(n["label"], size) + (_width(n["name"], size - 1, False) + 10 if n["name"] else 0) + (_width(str(n["count"]), size - 3) + 26 if n["level"] < 4 else 0)
        n["w"] = round(max(110, min(460, text + 38)))
    columns = {}
    for n in nodes:
        columns[n["level"]] = max(columns.get(n["level"], 0), n["w"])
    left = {0: 0.0}
    for level in range(1, 5):
        left[level] = left[level - 1] + columns.get(level - 1, 0) + GAP
    by_id = {n["id"]: n for n in nodes}
    for n in nodes:
        n["x"] = left[n["level"]]
    row = [0]

    def place(n):
        if not n["kids"]:
            n["y"] = row[0] * PITCH
            row[0] += 1
            return
        for kid in n["kids"]:
            place(by_id[kid])
        n["y"] = (by_id[n["kids"][0]]["y"] + by_id[n["kids"][-1]]["y"]) / 2

    place(root)
    box = (min(n["x"] for n in nodes) - 20, min(n["y"] - n["h"] / 2 for n in nodes) - 16, max(n["x"] + n["w"] for n in nodes) + 20, max(n["y"] + n["h"] / 2 for n in nodes) + 16)
    return nodes, box


def _curve(parent, node):
    """The line from the right edge of a branch to the left edge of what grows from it, as an SVG path."""
    x1, y1, x2, y2 = parent["x"] + parent["w"], parent["y"], node["x"], node["y"]
    mid = (x1 + x2) / 2
    return f"M {x1:.1f} {y1:.1f} C {mid:.1f} {y1:.1f}, {mid:.1f} {y2:.1f}, {x2:.1f} {y2:.1f}"


def tree_html(courses, status_of, color_of, selected=None, root_label="All Courses"):
    """The map as one SVG. A branch folds its own branches away when it is clicked (the script in app.py moves everything to its new place and the CSS slides it there); a course opens when
    it is clicked. Pills have no fill, so the page shows through. `status_of(course)` / `color_of(course)`: the status text and the color of a course; `selected`: the id of the course to mark."""
    if not courses:
        return ""
    nodes, (x0, y0, x1, y1) = layout(courses, status_of)
    by_id = {n["id"]: n for n in nodes}
    edges, shapes = [], []
    for n in nodes:
        h, w, level = n["h"], n["w"], n["level"]
        if n["parent"]:
            edges.append(f'<path class="mm-line mm-e{level}" data-for="{n["id"]}" style="--c:hsl({n["hue"]},75%,55%)" d="{_curve(by_id[n["parent"]], n)}"/>')
        style = f'--x:{n["x"]:.1f}px;--y:{n["y"]:.1f}px;--h:{n["hue"]}'
        common = f'data-id="{n["id"]}" data-parent="{n["parent"] or ""}" data-level="{level}" data-w="{w}" data-h="{h}"'
        if level == 4:
            c = n["course"]
            study = status_of(c) == "Self-Study"
            name = f'<tspan class="mm-sub" dx="9">{html.escape(n["name"])}</tspan>' if n["name"] else ""
            tag = ""
            shapes.append(f'<g class="mm-node mm-l4{" sel" if c["id"] == selected else ""}{" mm-study" if study else ""}" {common} data-tree-course="{c["id"]}" style="{style};--c:{color_of(c)}">'
                          f'<rect y="{-h / 2}" width="{w}" height="{h}" rx="{h / 2}"/><text x="{w / 2}" y="5" text-anchor="middle"><tspan class="mm-code">{html.escape(n["label"])}</tspan>{name}{tag}</text>'
                          f'<title>{html.escape(n["label"] + " " + (c.get("name") or ""))} - {"this is a self-study course" if study else html.escape(status_of(c))}</title></g>')
        else:
            shapes.append(f'<g class="mm-node mm-l{level}" {common} data-mm-toggle="{n["id"]}" style="{style}"><rect y="{-h / 2}" width="{w}" height="{h}" rx="{h / 2}"/>'
                          f'<text x="{w / 2 - (12 if level else 0)}" y="{SIZE[level] / 3:.1f}" text-anchor="middle" style="font-size:{SIZE[level]}px"><tspan>{html.escape(n["label"])}</tspan>'
                          f'<tspan class="mm-count" dx="10">{n["count"]}</tspan></text><text class="mm-chev" x="{w - 18}" y="5" text-anchor="middle">&#9656;</text></g>')
    return (f'<div class="mm-wrap"><div class="tk-top"><span class="tk-note">Click a bubble to fold or unfold its branches; click a course to open it. Scroll to zoom, drag to move.</span>'
            f'<span class="tk-zoom"><button type="button" data-mm-zoom="out" title="zoom out">&minus;</button><button type="button" data-mm-zoom="in" title="zoom in">+</button>'
            f'<button type="button" data-mm-zoom="fit" title="show the whole map">Fit</button></span>'
            f'<button type="button" class="tk-btn" data-mm-all="close">Collapse All</button></div>'
            f'<svg class="mm" data-pitch="{PITCH}" data-gap="{GAP}" viewBox="{x0:.0f} {y0:.0f} {x1 - x0:.0f} {y1 - y0:.0f}" role="img" aria-label="{html.escape(root_label)}"><g class="mm-edges">{"".join(edges)}</g>{"".join(shapes)}</svg></div>')
