"""Checks for _extract_code, the parser that pulls the runnable program out of a
model response. Every case here is a shape a NIM model actually returned."""
from utils.genai_utils import _extract_code, _strip_markdown

PROG = "import numpy as np\n" + "\n".join("x%d = %d" % (i, i) for i in range(20)) + "\nprint(x1)"


def test_doubled_fence():
    # nemotron wraps code in "```python" twice and "```" twice; pairing the
    # duplicates naively captures an empty string.
    code, rest = _extract_code("```python\n```python\n%s\n```\n```\nWhat This Program Does\nIt runs." % PROG)
    assert code.startswith("import numpy")
    assert "```" not in rest and "What This Program Does" in rest


def test_single_fence():
    code, _ = _extract_code("Intro\n```python\n%s\n```\nAfter" % PROG)
    assert code.startswith("import numpy")


def test_longest_block_wins():
    # The walkthrough may quote a line or two in its own fence; the program is
    # the longest block, not the first.
    code, _ = _extract_code("```python\n%s\n```\nlater\n```python\nx = 1\n```" % PROG)
    assert code.startswith("import numpy")


def test_unparseable_block_skipped():
    # A close-then-open fence pair must NOT be collapsed into one.
    code, _ = _extract_code("```python\ndef f(:\n```\n```python\n%s\n```" % PROG)
    assert code.startswith("import numpy")


def test_bare_fence():
    code, _ = _extract_code("```\n%s\n```" % PROG)
    assert code.startswith("import numpy")


def test_no_fence_returns_empty():
    assert _extract_code("no fences here")[0] == ""


def test_trivial_block_rejected():
    assert _extract_code("```python\nx=1\n```")[0] == ""


def test_strip_markdown_unwraps_bold():
    # The exact leak seen from the Beginner prompt.
    assert _strip_markdown("- **Algorithm**: a procedure.") == "- Algorithm: a procedure."


def test_strip_markdown_leaves_python_exponent_alone():
    # Both spellings appear in quoted walkthrough lines; neither is bold.
    for text in ("the line 'result = 2 ** 3' cubes two", "it computes x**2 and y**3 per row"):
        assert _strip_markdown(text) == text, text


def test_strip_markdown_removes_headings_but_not_comments():
    text = "### Key Terms\nx = 1  # a comment\n# a comment line"
    assert _strip_markdown(text) == "Key Terms\nx = 1  # a comment\n# a comment line"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
    print("all code-extraction checks passed")
