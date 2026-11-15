"""The Courses page as a tree of knowledge (Courses > All > Tree): every course is a leaf on a branch, and similar fields grow from the same branch.

Levels, like the levels of the tree of life: Domain (Engineering, Natural Sciences, ...) > Field (Aerospace Engineering, Physics, ...) > Topic (Fluids and Aerodynamics,
Propulsion and Energy, ...) > Course. The field comes from the course's category when it has one, else from the letters of its course number (AE, PHYS, MATH ...); the topic from
words in its name. `build_tree` is pure; `tree_html` draws it (branches fold and unfold with a CSS animation, see app.py)."""
import html
import math
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


# ---------------------------------------------------------------- the mind map: a bubble in the middle, bubbles for the branches around it, and a white bubble for each course
RADII = {0: 112, 1: 96, 2: 82, 3: 70, 4: 60}            # center, domain, field, topic, course
MIN_WEIGHT = {1: 3.0, 2: 2.6, 3: 2.2}                    # room a branch takes on its ring, in courses (so a branch with one course is not squeezed)


def _lines(text, width):
    """Break a label into lines of about `width` characters (a long word stays whole; the last line ends with ... when the text is too long for 3 lines)."""
    words, out, cur = (text or "").split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > width:
            out.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        out.append(cur)
    if len(out) > 3:
        out = out[:3]
        out[-1] = out[-1][:max(1, width - 3)] + "..."
    return out


def layout(courses):
    """The mind map as a list of nodes, each {id, parent, level, label, x, y, r, hue, course, kids} with the center at (0, 0), and its half width and height. Branches share the circle by
    how many courses they hold; the outer ring is as far out as the courses need (one course takes a fixed arc of it)."""
    tree = build_tree(courses)
    nodes = []
    counter = [0]

    def make(level, parent, label, **extra):
        counter[0] += 1
        node = {"id": f"n{counter[0]}", "parent": parent, "level": level, "label": label, "kids": 0, "weight": 1.0, **extra}
        nodes.append(node)
        return node

    root = make(0, None, "All Courses", count=len(courses))

    def build(level, parent_node, items, hue_base):
        """The children of a node as [(node, [their children])] and the room they need."""
        total = 0.0
        out = []
        for i, item in enumerate(items):
            hue = _hue(i, len(items)) if level == 1 else (hue_base + 7 * i) % 360
            if level == 4:
                node = make(4, parent_node["id"], item.get("code") or item.get("name") or "Course", course=item, hue=hue_base)
                out.append((node, []))
                total += 1.0
                continue
            label, children = item
            if level == 3:
                node = make(3, parent_node["id"], label, hue=hue, count=len(children))
                sub, w = build(4, node, children, hue)
            elif level == 2:
                node = make(2, parent_node["id"], label, hue=hue, count=count(children))
                sub, w = build(3, node, children, hue)
            else:
                node = make(1, parent_node["id"], label, hue=hue, count=sum(count(t) for _, t in children))
                sub, w = build(2, node, children, hue)
            node["kids"] = len(sub)
            node["weight"] = max(w, MIN_WEIGHT[level])
            total += node["weight"]
            out.append((node, sub))
        return out, total

    top, total = build(1, root, tree, 210)
    root["kids"] = len(top)
    unit = 2 * RADII[4] + 12
    base4 = max(840.0, max(1.0, total) * unit / (2 * math.pi))

    def shares(weights, span, min_share):
        """Angles for siblings: proportional to their weights, none below min_share (water-filling); None when they cannot all fit in the span."""
        n = len(weights)
        if n * min_share > span:
            return None
        fixed = set()
        out = [0.0] * n
        while True:
            free = [i for i in range(n) if i not in fixed]
            room = span - sum(out[i] for i in fixed)
            whole = sum(weights[i] for i in free) or 1.0
            low = [i for i in free if room * weights[i] / whole < min_share]
            if not low:
                for i in free:
                    out[i] = room * weights[i] / whole
                return out
            for i in low:
                out[i] = min_share
                fixed.add(i)

    def place(entries, a0, a1, level, rings):
        """Put the siblings on their ring inside the arc a0..a1; False when they do not fit there (the rings are then moved outward)."""
        angles = shares([e[0]["weight"] for e in entries], a1 - a0, (2 * RADII[level] + 18) / rings[level])
        if angles is None:
            return False
        angle = a0
        for (node, sub), share in zip(entries, angles):
            mid = angle + share / 2
            node["x"], node["y"], node["r"] = rings[level] * math.cos(mid), rings[level] * math.sin(mid), RADII[level]
            if sub and not place(sub, angle, angle + share, level + 1, rings):
                return False
            angle += share
        return True

    for extra in range(0, 4000, 40):                                  # the rings move outward until every bubble has room
        ring4 = base4 + extra
        rings = {1: max(ring4 - 590, RADII[0] + RADII[1] + 60), 2: ring4 - 340, 3: ring4 - 170, 4: ring4}
        if place(top, -math.pi / 2, 3 * math.pi / 2, 1, rings):
            break
    root.update(x=0.0, y=0.0, r=RADII[0], hue=210)
    where = {n["id"]: (n["x"], n["y"]) for n in nodes}
    for n in nodes:
        n["px"], n["py"] = where.get(n["parent"], (0.0, 0.0))
    return nodes, (max(abs(n["x"]) + n["r"] for n in nodes) + 30, max(abs(n["y"]) + n["r"] for n in nodes) + 30)


def tree_html(courses, status_of, color_of, selected=None, root_label="All Courses"):
    """The mind map as one SVG. A bubble with branches folds them into itself when clicked (CSS animates every bubble to its parent and back, see app.py); a white bubble is a course and
    a click on it opens the course. `status_of(course)` / `color_of(course)`: the status text and the color of a course; `selected`: the id of the course to mark."""
    if not courses:
        return ""
    nodes, (ex, ey) = layout(courses)
    parts = []
    for n in sorted(nodes, key=lambda m: -m["level"]):              # outer bubbles first: a bubble covers the lines of the ones it holds
        r, level = n["r"], n["level"]
        dx, dy = n["px"] - n["x"], n["py"] - n["y"]
        style = f'--x:{n["x"]:.1f}px;--y:{n["y"]:.1f}px;--px:{n["px"]:.1f}px;--py:{n["py"]:.1f}px'
        line = "" if n["parent"] is None else f'<line class="mm-line" x1="0" y1="0" x2="{dx:.1f}" y2="{dy:.1f}"/>'
        if level == 4:
            c = n["course"]
            code = _lines(c.get("code") or c.get("name") or "Course", 11)[0]
            name = "" if (not c.get("code") or c.get("name") == c.get("code")) else c.get("name") or ""
            name_lines = _lines(name, 14)[:2]
            first = -8 * len(name_lines) if name_lines else 5
            text = f'<tspan x="0" dy="{first}" class="mm-code">{html.escape(code)}</tspan>'
            text += "".join(f'<tspan x="0" dy="{13 if i else 17}" class="mm-sub">{html.escape(s)}</tspan>' for i, s in enumerate(name_lines))
            parts.append(f'<g class="mm-node mm-l4{" sel" if c["id"] == selected else ""}" data-id="{n["id"]}" data-parent="{n["parent"]}" data-tree-course="{c["id"]}" style="{style};--c:{color_of(c)}">'
                         f'{line}<circle r="{r}"/><text text-anchor="middle">{text}</text>'
                         f'<title>{html.escape((c.get("code") or "") + " " + (c.get("name") or ""))} - {html.escape(status_of(c))}</title></g>')
            continue
        lines = _lines(n["label"], {0: 12, 1: 13, 2: 12, 3: 11}[level])
        size = {0: 27, 1: 21, 2: 17, 3: 14}[level]
        start = -(len(lines) - 1) * size * 0.58
        text = "".join(f'<tspan x="0" dy="{size * 1.15 if i else start + size * 0.35:.1f}">{html.escape(s)}</tspan>' for i, s in enumerate(lines))
        badge = (f'<text class="mm-count" y="{r - 14}" text-anchor="middle">{n.get("count", 0)}</text>' if level
                 else f'<text class="mm-count" y="{r - 22}" text-anchor="middle">{n.get("count", 0)} courses</text>')
        parts.append(f'<g class="mm-node mm-l{level}" data-id="{n["id"]}" data-parent="{n["parent"] or ""}" data-mm-toggle="{n["id"]}" style="{style};--h:{n["hue"]}">{line}<circle r="{r}"/>'
                     f'<text class="mm-label" text-anchor="middle" style="font-size:{size}px">{text}</text>{badge}<text class="mm-plus" y="{-r + 24}" text-anchor="middle">+</text></g>')
    return (f'<div class="mm-wrap"><div class="tk-top"><span class="tk-note">Click a bubble to fold its branches, a white bubble to open the course.</span>'
            f'<span class="tk-actions"><button type="button" data-tree-all="open">Expand All</button><button type="button" data-tree-all="close">Collapse All</button></span></div>'
            f'<svg class="mm" viewBox="{-ex:.0f} {-ey:.0f} {2 * ex:.0f} {2 * ey:.0f}" role="img" aria-label="{html.escape(root_label)}">{"".join(parts)}</svg></div>')
