"""The tree of knowledge on Courses > All > Tree: fields, topics, branches and the click on a course."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import crud
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


def test_rows_columns_and_branches_line_up_and_nothing_overlaps():
    names = ["Viscous Fluid Flow", "Electric Propulsion", "Quantum Mechanics", "Orbital Mechanics", "Structural Analysis", "Control Systems", "Linear Algebra", "Algorithms"]
    courses = [course(i, f"{['AE', 'PHYS', 'MA', 'CS'][i % 4]} {100 + i}", names[i % len(names)]) for i in range(1, 61)]
    nodes, (x0, y0, x1, y1) = K.layout(courses)
    by_id = {n["id"]: n for n in nodes}
    assert sum(n["level"] == 4 for n in nodes) == 60
    for level in range(5):
        column = sorted((n for n in nodes if n["level"] == level), key=lambda n: n["y"])
        assert len({n["x"] for n in column}) == 1                                                  # one column for each level
        assert all(b["y"] - a["y"] >= (a["h"] + b["h"]) / 2 for a, b in zip(column, column[1:]))   # no two pills overlap
    xs = [next(n["x"] for n in nodes if n["level"] == l) for l in range(5)]
    assert xs == sorted(xs) and all(by_id[k]["x"] > n["x"] + n["w"] for n in nodes for k in n["kids"])         # a branch grows to the right of its parent
    assert all(by_id[n["kids"][0]]["y"] <= n["y"] <= by_id[n["kids"][-1]]["y"] for n in nodes if n["kids"])  # in the middle of its rows
    assert x0 < 0 < x1 and y0 < 0 < y1


def test_text_is_large_enough_to_read_and_the_pills_are_wide_enough_for_it():
    assert min(K.SIZE.values()) >= 15 and K.HEIGHT[4] >= 30
    nodes, _ = K.layout([course(1, "AE 6765", "Kinetics & Thermodynamics of Gases")])
    leaf = next(n for n in nodes if n["level"] == 4)
    assert leaf["w"] >= K._width("AE 6765", K.SIZE[4]) + K._width("Kinetics & Thermodynamics of Gases", K.SIZE[4] - 1, False)


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
