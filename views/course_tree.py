"""The Courses page as a tree of knowledge (Courses > All > Tree): every course is a leaf on a branch, and similar fields grow from the same branch.

Levels, like the levels of the tree of life: Domain (Engineering, Natural Sciences, ...) > Field (Aerospace Engineering, Physics, ...) > Topic (Fluids and Aerodynamics,
Propulsion and Energy, ...) > Course. The field comes from the course's category when it has one, else from the letters of its course number (AE, PHYS, MATH ...); the topic from
words in its name. `build_tree` is pure; `tree_html` draws it (branches fold and unfold with a CSS animation, see app.py)."""
import html
import re

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
        tree.setdefault(domain_of(field), {}).setdefault(field, {}).setdefault(topic_of(c) if field != SELF_STUDY else GENERAL, []).append(c)
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


def _branch(label, n, body, hue, level, open_=True, path=""):
    sat, light = 62, 58 - 4 * level
    return (f'<div class="tk-branch{" open" if open_ else ""}" data-level="{level}" style="--bc:hsl({hue},{sat}%,{light}%)">'
            f'<button type="button" class="tk-head" data-tree-toggle="{html.escape(path)}"><span class="tk-chev">&#9656;</span><span class="tk-name">{html.escape(label)}</span>'
            f'<span class="tk-n">{n}</span></button><div class="tk-body"><div class="tk-inner">{body}</div></div></div>')


def _leaf(c, status, color, selected):
    code = html.escape(c.get("code") or c.get("name") or "Course")
    name = "" if (not c.get("code") or c.get("name") == c.get("code")) else html.escape(c.get("name") or "")
    term = html.escape(c.get("semester") or "")
    return (f'<div class="tk-leaf{" sel" if selected else ""}" data-tree-course="{c["id"]}" style="--c:{color}" title="open {code}"><b>{code}</b>'
            f'<span>{name}</span><i>{term}{" · " if term else ""}{html.escape(status)}</i></div>')


def tree_html(courses, status_of, color_of, selected=None, root_label="All Courses"):
    """The tree as one block of HTML. `status_of(course)` / `color_of(course)`: the status text and the color of a leaf; `selected`: the id of the course to mark."""
    tree = build_tree(courses)
    parts = []
    for i, (domain, fields) in enumerate(tree):
        hue = _hue(i, len(tree))
        field_html = ""
        for j, (field, topics) in enumerate(fields):
            topic_html = ""
            for topic, cs in topics:
                leaves = "".join(_leaf(c, status_of(c), color_of(c), c["id"] == selected) for c in cs)
                topic_html += _branch(topic, len(cs), f'<div class="tk-leaves">{leaves}</div>', (hue + 8 * j + 4) % 360, 3, True, f"{domain}/{field}/{topic}")
            field_html += _branch(field, count(topics), topic_html, (hue + 8 * j) % 360, 2, True, f"{domain}/{field}")
        parts.append(_branch(domain, sum(count(t) for _, t in fields), field_html, hue, 1, True, domain))
    if not parts:
        return ""
    return (f'<div class="tk-tree"><div class="tk-top"><span class="tk-root">{html.escape(root_label)}<i>{len(courses)}</i></span>'
            f'<span class="tk-actions"><button type="button" data-tree-all="open">Expand All</button><button type="button" data-tree-all="close">Collapse All</button></span></div>'
            f'<div class="tk-trunk">{"".join(parts)}</div></div>')
