"""Checks for the section-by-section breakdown's validation of model output.

explain_code_sections makes a network call, so these exercise the parsing and
clamping logic through a stubbed _chat rather than hitting NIM.
"""
import json

from utils import genai_utils

CODE = "\n".join("line_%d = %d" % (i, i) for i in range(1, 21))


def _run(reply):
    original = genai_utils._chat
    genai_utils._chat = lambda *a, **k: reply
    try:
        return genai_utils.explain_code_sections("key", CODE, "Topic")
    finally:
        genai_utils._chat = original


def test_valid_json_becomes_sections():
    reply = json.dumps([
        {"title": "Setup", "start_line": 1, "end_line": 10, "explanation": "Sets things up."},
        {"title": "Rest", "start_line": 11, "end_line": 20, "explanation": "Does the rest."},
    ])
    sections = _run(reply)
    assert len(sections) == 2
    assert sections[0]["code"].startswith("line_1 = 1")
    # every quoted snippet must really come from the program
    assert all(s["code"] in CODE for s in sections)


def test_out_of_range_lines_are_clamped():
    reply = json.dumps([
        {"title": "A", "start_line": -5, "end_line": 3, "explanation": "x"},
        {"title": "B", "start_line": 4, "end_line": 9999, "explanation": "y"},
    ])
    sections = _run(reply)
    assert sections[0]["start_line"] == 1
    assert sections[1]["end_line"] == 20
    assert all(s["code"] in CODE for s in sections)


def test_prose_around_the_json_is_tolerated():
    reply = 'Sure, here you go:\n[{"title":"A","start_line":1,"end_line":20,"explanation":"all"},' \
            '{"title":"B","start_line":2,"end_line":5,"explanation":"some"}]\nHope that helps.'
    assert len(_run(reply)) == 2


def test_sections_returned_in_line_order():
    reply = json.dumps([
        {"title": "Second", "start_line": 11, "end_line": 20, "explanation": "b"},
        {"title": "First", "start_line": 1, "end_line": 10, "explanation": "a"},
    ])
    assert [s["title"] for s in _run(reply)] == ["First", "Second"]


def test_unusable_replies_degrade_to_empty():
    for reply in ("not json at all", "[]", None, "[{}]",
                  json.dumps([{"title": "A", "start_line": 1, "end_line": 5, "explanation": ""}])):
        assert _run(reply) == [], reply


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok", name)
    print("all code-section checks passed")
