"""The tree of knowledge on Courses > All > Tree: fields, topics, branches and the click on a course."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from core import crud
from views import course_tree as K

pytestmark = pytest.mark.usefixtures("fresh_data")
APP = str(Path(__file__).resolve().parent.parent / "app.py")


def course(i, code, name, category=None, semester="Fall 2026"):
    return {"id": i, "code": code, "name": name, "category": category, "semester": semester}


def test_the_field_comes_from_the_category_else_from_the_letters_of_the_course_number():
    assert K.field_of(course(1, "AE 6765", "Kinetics")) == "Aerospace Engineering" and K.field_of(course(2, "AAE 333", "Fluid Mechanics")) == "Aerospace Engineering"
    assert K.field_of(course(3, "PHYS 6105", "Quantum Mechanics I")) == "Physics" and K.field_of(course(4, "MA 266", "Differential Equations")) == "Mathematics"
    assert K.field_of(course(5, "AE 1", "x", category="Aerospace")) == "Aerospace Engineering"                    # the typed category names the known field
    assert K.field_of(course(6, "AE 1", "x", category="Astrophotography")) == "Astrophotography"                   # an unknown category is its own field
    assert K.field_of(course(7, "", "Orbital Mechanics")) == "Aerospace Engineering" and K.field_of(course(9, "", "Zzz")) == K.SELF_STUDY and K.field_of(course(8, "XYZ 1", "x")) == "XYZ"
    assert K.domain_of("Aerospace Engineering") == "Engineering" and K.domain_of("Physics") == "Natural Sciences" and K.domain_of("XYZ") == K.OTHER_DOMAIN


def test_the_topic_comes_from_words_in_the_name():
    topic = lambda name: K.topic_of(course(1, "AE 1", name))
    assert topic("Viscous Fluid Flow") == "Fluids and Aerodynamics" and topic("Electric Propulsion") == "Propulsion and Energy"
    assert topic("Kinetics & Thermodynamics of Gases") == "Propulsion and Energy" and topic("Orbital Mechanics") == "Space and Orbits"
    assert topic("Quantum Mechanics I") == "Quantum and Modern Physics" and topic("Something Else") == K.GENERAL


def test_similar_fields_grow_from_the_same_branch_in_a_fixed_order():
    courses = [course(1, "PHYS 6105", "Quantum Mechanics I"), course(2, "AE 6765", "Kinetics & Thermodynamics of Gases"), course(3, "AE 6009", "Viscous Fluid Flow"),
               course(4, "AE 6451", "Electric Propulsion"), course(5, "", "Zzz hobby"), course(6, "MA 266", "Differential Equations")]
    tree = K.build_tree(courses)
    assert [d for d, _ in tree] == ["Engineering", "Mathematics and Computing", "Natural Sciences", K.SELF_STUDY]                  # the unnamed ones last
    fields = dict(tree)["Engineering"]
    assert [f for f, _ in fields] == ["Aerospace Engineering"]
    topics = dict(fields[0][1])
    assert [c["code"] for c in topics["Propulsion and Energy"]] == ["AE 6451", "AE 6765"] and [c["code"] for c in topics["Fluids and Aerodynamics"]] == ["AE 6009"]
    assert sum(len(cs) for _, fs in tree for _, ts in fs for _, cs in ts) == 6                                                     # every course is on exactly one branch


def test_the_map_has_a_pill_for_the_whole_each_branch_and_each_course():
    courses = [course(1, "AE 6009", "Viscous Fluid Flow"), course(2, "PHYS 6105", "Quantum Mechanics I")]
    html = K.tree_html(courses, lambda c: "Active", lambda c: "#336699", selected=2)
    assert html.count('class="mm-node') == 1 + 2 + 2 + 2 + 2                                   # the whole, 2 domains, 2 fields, 2 topics, 2 courses
    assert 'class="mm-node mm-l4 sel"' in html and 'data-tree-course="1"' in html and 'data-tree-course="2"' in html
    assert html.count("data-mm-toggle=") == 7 and 'data-mm-all="close"' in html and "<svg" in html and html.count(chr(99)+"lass=\"mm-line") == 8
    assert K.tree_html([], lambda c: "", lambda c: "") == ""
    assert "&lt;" in K.tree_html([course(1, "AE <1>", "x")], lambda c: "Active", lambda c: "#000")                # escaped
    study = K.tree_html([course(3, "", "Zzz hobby")], lambda c: "Self-Study", lambda c: "#000")
    assert "mm-study" in study and "this is a self-study course" in study and "mm-tag" not in study               # a dashed outline and a hover box, no label


def test_every_part_of_a_merged_course_is_written_out():
    html = K.tree_html([course(1, "MA 266 / 303", "Differential Equations")], lambda c: "Active", lambda c: "#000")
    assert "MA 266 / MA 303" in html


def test_the_bubbles_do_not_overlap_however_many_courses_there_are():
    import math
    names = ["Viscous Fluid Flow", "Electric Propulsion", "Quantum Mechanics", "Orbital Mechanics", "Structural Analysis", "Control Systems", "Linear Algebra", "Algorithms"]
    courses = [course(i, f"{['AE', 'PHYS', 'MA', 'CS'][i % 4]} {100 + i}", names[i % len(names)]) for i in range(1, 61)]
    nodes, (ex, ey) = K.layout(courses)
    assert sum(n["level"] == 4 for n in nodes) == 60 and ex > 800
    by_level = {}
    for n in nodes:
        by_level.setdefault(n["level"], []).append(n)
    for level, items in by_level.items():
        for i, a in enumerate(items):
            for b in items[i + 1:]:
                assert math.hypot(a["x"] - b["x"], a["y"] - b["y"]) >= a["r"] + b["r"] - 1, (level, a["label"], b["label"])
    root = next(n for n in nodes if n["level"] == 0)
    assert root["y"] == max(n["y"] for n in nodes) and root["x"] == 0                                            # the root is at the bottom, in the middle: the tree grows upward
    assert all(n["y"] < root["y"] for n in nodes if n["level"] > 0)
    assert all(n["px"] == root["x"] and n["py"] == root["y"] for n in nodes if n["level"] == 1)                  # a branch folds into the root


def test_branch_bubbles_are_larger_than_course_bubbles_and_the_map_is_spread_out():
    assert K.RADII[1] > K.RADII[2] > K.RADII[3] > K.RADII[4] and K.RADII[0] > K.RADII[1]
    nodes, _ = K.layout([course(1, "AE 6009", "Viscous Fluid Flow"), course(2, "PHYS 6105", "Quantum Mechanics I")])
    root = next(n for n in nodes if n["level"] == 0)
    ring = {}
    for n in nodes:
        if n["level"] >= 1:
            ring.setdefault(n["level"], (n["x"] - root["x"]) ** 2 + (n["y"] - root["y"]) ** 2)
    ring = {k: v ** 0.5 for k, v in ring.items()}
    assert ring[1] > K.RADII[0] + K.RADII[1] + 60                                                                   # room between the rings
    assert all(ring[b] - ring[a] > K.RADII[a] + K.RADII[b] for a, b in ((1, 2), (2, 3), (3, 4)) if a in ring and b in ring)


def test_the_all_tab_offers_a_tree_view_and_a_click_on_a_leaf_opens_the_course():
    a = crud.add_course("AE 6009", "Viscous Fluid Flow", "Fall 2026", 0, "Active")
    crud.add_course("PHYS 6105", "Quantum Mechanics I", "Fall 2026", 0, "Active")
    at = AppTest.from_file(APP, default_timeout=90)
    at.session_state["page"] = "Courses"
    at.session_state["courses_filter"] = "All"
    at.session_state["courses_view"] = "Tree"
    at.run()
    assert not at.exception and any('class="mm-wrap"' in m.value for m in at.markdown)
    at.text_input(key="tree_sink").set_value(f"{a}|1"); at.run()
    assert not at.exception and at.session_state["open_course"] == a
    at2 = AppTest.from_file(APP, default_timeout=90)
    at2.session_state["page"] = "Courses"
    at2.session_state["courses_filter"] = "Active"
    at2.run()
    assert not any('class="mm-wrap"' in m.value for m in at2.markdown)                                                        # the other tabs keep the tiles


def test_a_course_photo_is_the_background_of_its_bubble_and_the_map_is_wider_than_tall():
    courses = [course(1, "AE 6009", "Viscous Fluid Flow"), course(2, "PHYS 6105", "Quantum Mechanics I")]
    with_photo = K.tree_html(courses, lambda c: "Active", lambda c: "#336699", photo_of=lambda c: "data:image/jpeg;base64,AAAA" if c["id"] == 1 else None)
    assert with_photo.count("<image ") == 1 and "clip-path=" in with_photo and with_photo.count("mm-photo") == 1
    assert "<image " not in K.tree_html(courses, lambda c: "Active", lambda c: "#336699")
    nodes, (ex, ey) = K.layout(courses)
    assert ex > ey * 1.5                                                                                            # it fills a wide window instead of gathering in the middle


def test_a_field_with_only_the_unnamed_topic_has_no_general_bubble_and_a_name_only_course_shows_its_whole_name():
    nodes, _ = K.layout([course(1, "CHEM 110", "Pyrochemistry"), course(2, "PHYS 6105", "Quantum Mechanics I"), course(3, "PHYS 6200", "Optics")])
    by_id = {n["id"]: n for n in nodes}
    assert not [n for n in nodes if n["label"] == K.GENERAL and n["level"] == 3 and n["kids"] and by_id[n["parent"]]["level"] == 2 and by_id[n["parent"]]["kids"] == 1]
    chem = next(n for n in nodes if n["level"] == 2 and n["label"] == "Chemistry")
    assert [by_id[k["id"]]["level"] for k in nodes if k["parent"] == chem["id"]] == [4]                     # the course hangs on the field
    assert all(n["r"] == K.RADII[4] for n in nodes if n["level"] == 4)
    html = K.tree_html([course(1, "", "Tonal Harmony")], lambda c: "Self-Study", lambda c: "#888")
    assert "Tonal" in html and "Harmony" in html
    assert 'data-mm-zoom="reset"' in html and 'data-mm-zoom="fit"' in html                              # Reset View puts the view and every bubble back
