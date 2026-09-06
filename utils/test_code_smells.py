"""Static checks that catch the two ways generated programs broke in testing."""
from utils.genai_utils import _code_smells


def test_clean_code_has_no_smells():
    assert _code_smells("import numpy as np\nx = np.zeros(3)\nprint(x)\n") == []


def test_undefined_function_flagged():
    # Observed on "Decision Trees": NameError: name 'print_tree' is not defined
    problems = _code_smells("x = 1\nprint_tree(x)\n")
    assert any("print_tree" in p for p in problems), problems


def test_defined_function_not_flagged():
    assert _code_smells("def print_tree(x):\n    print(x)\n\nprint_tree(1)\n") == []


def test_while_true_without_break_flagged():
    assert any("while True" in p for p in _code_smells("while True:\n    x = 1\n"))


def test_while_true_with_break_ok():
    assert _code_smells("i = 0\nwhile True:\n    i += 1\n    if i > 5:\n        break\n") == []


def test_conditional_loop_without_exit_flagged():
    # Observed on "K-Means Clustering": the request hung
    assert _code_smells("s = 0\nwhile s != 10:\n    s += 0\n") != []


def test_syntax_error_reported():
    assert _code_smells("def f(:\n") == ["does not parse: '(' was never closed"] or \
        _code_smells("def f(:\n")[0].startswith("does not parse")


def test_imported_and_builtin_names_not_flagged():
    assert _code_smells("import math\nfrom os import getcwd\nprint(math.sqrt(len(str(getcwd()))))\n") == []


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok", name)
    print("all code-smell checks passed")
