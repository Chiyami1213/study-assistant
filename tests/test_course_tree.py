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
    assert K.field_of(course(7, "", "Orbital Mechanics")) == K.SELF_STUDY and K.field_of(course(8, "XYZ 1", "x")) == "XYZ"
    assert K.domain_of("Aerospace Engineering") == "Engineering" and K.domain_of("Physics") == "Natural Sciences" and K.domain_of("XYZ") == K.OTHER_DOMAIN


def test_the_topic_comes_from_words_in_the_name():
    topic = lambda name: K.topic_of(course(1, "AE 1", name))
    assert topic("Viscous Fluid Flow") == "Fluids and Aerodynamics" and topic("Electric Propulsion") == "Propulsion and Energy"
    assert topic("Kinetics & Thermodynamics of Gases") == "Propulsion and Energy" and topic("Orbital Mechanics") == "Space and Orbits"
    assert topic("Quantum Mechanics I") == "Quantum and Modern Physics" and topic("Something Else") == K.GENERAL


def test_similar_fields_grow_from_the_same_branch_in_a_fixed_order():
    courses = [course(1, "PHYS 6105", "Quantum Mechanics I"), course(2, "AE 6765", "Kinetics & Thermodynamics of Gases"), course(3, "AE 6009", "Viscous Fluid Flow"),
               course(4, "AE 6451", "Electric Propulsion"), course(5, "", "Piano"), course(6, "MA 266", "Differential Equations")]
    tree = K.build_tree(courses)
    assert [d for d, _ in tree] == ["Engineering", "Mathematics and Computing", "Natural Sciences", K.SELF_STUDY]                  # the unnamed ones last
    fields = dict(tree)["Engineering"]
    assert [f for f, _ in fields] == ["Aerospace Engineering"]
    topics = dict(fields[0][1])
    assert [c["code"] for c in topics["Propulsion and Energy"]] == ["AE 6451", "AE 6765"] and [c["code"] for c in topics["Fluids and Aerodynamics"]] == ["AE 6009"]
    assert sum(len(cs) for _, fs in tree for _, ts in fs for _, cs in ts) == 6                                                     # every course is on exactly one branch


def test_the_html_has_branches_leaves_and_marks_the_selected_course():
    courses = [course(1, "AE 6009", "Viscous Fluid Flow"), course(2, "PHYS 6105", "Quantum Mechanics I")]
    html = K.tree_html(courses, lambda c: "Active", lambda c: "#336699", selected=2)
    assert html.count('class="tk-branch') == 6 and html.count("data-tree-course=") == 2                       # 2 domains, 2 fields, 2 topics
    assert 'class="tk-leaf sel" data-tree-course="2"' in html and 'class="tk-leaf" data-tree-course="1"' in html
    assert "data-tree-all=\"open\"" in html and "All Courses" in html
    assert K.tree_html([], lambda c: "", lambda c: "") == ""
    assert "&lt;" in K.tree_html([course(1, "AE <1>", "x")], lambda c: "Active", lambda c: "#000")                # escaped


def test_the_all_tab_offers_a_tree_view_and_a_click_on_a_leaf_opens_the_course():
    a = crud.add_course("AE 6009", "Viscous Fluid Flow", "Fall 2026", 0, "Active")
    crud.add_course("PHYS 6105", "Quantum Mechanics I", "Fall 2026", 0, "Active")
    at = AppTest.from_file(APP, default_timeout=90)
    at.session_state["page"] = "Courses"
    at.session_state["courses_filter"] = "All"
    at.session_state["courses_view"] = "Tree"
    at.run()
    assert not at.exception and any('class="tk-tree"' in m.value for m in at.markdown)
    at.text_input(key="tree_sink").set_value(f"{a}|1"); at.run()
    assert not at.exception and at.session_state["open_course"] == a
    at2 = AppTest.from_file(APP, default_timeout=90)
    at2.session_state["page"] = "Courses"
    at2.session_state["courses_filter"] = "Active"
    at2.run()
    assert not any('class="tk-tree"' in m.value for m in at2.markdown)                                                        # the other tabs keep the tiles
