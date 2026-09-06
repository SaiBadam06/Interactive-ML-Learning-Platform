"""Checks that generate_quiz never ships a question with a broken answer key.

generate_quiz makes a network call, so these exercise the parsing and validation
through a stubbed _chat rather than hitting NIM.
"""
import json

from utils import genai_utils

GOOD = {
    "question": "What does alpha control?",
    "options": ["learning rate", "discount", "epsilon", "reward"],
    "answer": 0,
    "explanation": "Alpha scales how much a new estimate replaces the old one.",
}


def _run(reply):
    original = genai_utils._chat
    genai_utils._chat = lambda *a, **k: reply
    try:
        return genai_utils.generate_quiz("key", "Q-Learning", "some context", "Beginner")
    finally:
        genai_utils._chat = original


def test_valid_json_becomes_questions():
    result = _run(json.dumps({
        "questions": [GOOD, dict(GOOD, question="And gamma?", answer=3)],
        "key_terms": [{"term": "Q-table", "definition": "A table of state-action values."}],
    }))
    assert len(result["questions"]) == 2
    assert result["questions"][0]["answer"] == 0
    assert result["key_terms"][0]["term"] == "Q-table"


def test_wrong_option_count_is_rejected():
    assert _run(json.dumps({"questions": [dict(GOOD, options=["a", "b", "c"])]})) == \
        {"questions": [], "key_terms": []}


def test_out_of_range_answer_is_rejected():
    assert _run(json.dumps({"questions": [dict(GOOD, answer=7)]}))["questions"] == []


def test_non_integer_answer_is_rejected():
    for bad in ("0", None, 1.5, True):
        assert _run(json.dumps({"questions": [dict(GOOD, answer=bad)]}))["questions"] == [], bad


def test_prose_around_the_json_is_tolerated():
    reply = "Sure, here you go:\n" + json.dumps({"questions": [GOOD]}) + "\nHope that helps."
    assert len(_run(reply)["questions"]) == 1


def test_blank_option_is_rejected():
    assert _run(json.dumps({"questions": [dict(GOOD, options=["a", "", "c", "d"])]}))["questions"] == []


def test_at_most_six_questions_and_eight_terms():
    result = _run(json.dumps({
        "questions": [GOOD] * 10,
        "key_terms": [{"term": "t%d" % i, "definition": "d"} for i in range(12)],
    }))
    assert len(result["questions"]) == 6
    assert len(result["key_terms"]) == 8


def test_key_terms_are_optional():
    assert _run(json.dumps({"questions": [GOOD]}))["key_terms"] == []


def test_unusable_replies_degrade_to_empty():
    for reply in ("not json at all", "{}", None, "", '{"questions": []}',
                  '{"questions": "nope"}', json.dumps({"questions": [{}, "x", None]})):
        assert _run(reply) == {"questions": [], "key_terms": []}, reply


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok", name)
    print("all quiz checks passed")
