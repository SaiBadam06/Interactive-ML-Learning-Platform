"""Checks for the chat's mode inference and its package reader.

The composer no longer asks the learner to pick a mode, so route_mode() decides
what happens on every message. Nothing here touches the network: routing is
keyword work and describe_packages() reads the imports with ast.
"""
from utils.code_executor import describe_packages

# app.py loads .env and builds the Flask app at import time, which is fine here -
# nothing below starts a server or calls out.
import app


PROGRAM = """import numpy as np
from sklearn.linear_model import LinearRegression
import matplotlib.pyplot as plt

X = np.array([[1], [2], [3]])
y = np.array([2, 4, 6])
model = LinearRegression().fit(X, y)
plt.plot(X, model.predict(X))
plt.show()
"""


# ---------------------------------------------------------------- mode routing

def test_a_plain_question_is_explained():
    for question in ("What is gradient descent?",
                     "Why does my model overfit?",
                     "Say that again in simpler words."):
        assert app.route_mode(question) == "explain", question


def test_asking_for_a_program_gets_code():
    for question in ("Write the code for k-means",
                     "Show me an implementation of PCA",
                     "Can I get a python script for logistic regression?"):
        assert app.route_mode(question) == "code", question


def test_asking_to_listen_gets_audio():
    for question in ("Read it aloud please",
                     "I want to listen to this one",
                     "Explain backpropagation out loud"):
        assert app.route_mode(question) == "audio", question


def test_asking_for_a_picture_gets_images():
    for question in ("Draw me a diagram of a transformer",
                     "Can you visualise how attention works?",
                     "Show a flowchart of the training loop"):
        assert app.route_mode(question) == "images", question


def test_fenced_code_is_walked_through():
    message = "what does this do?\n```python\n" + PROGRAM + "```"
    assert app.route_mode(message) == "walkthrough"
    assert app.extract_pasted_code(message).strip() == PROGRAM.strip()


def test_bare_pasted_code_is_walked_through():
    assert app.route_mode(PROGRAM) == "walkthrough"
    assert app.extract_pasted_code(PROGRAM).strip() == PROGRAM.strip()


def test_an_unclosed_fence_still_reads_as_code():
    # The paste is the last thing typed, so the closing fence is often missing.
    assert app.route_mode("look at this\n```python\n" + PROGRAM) == "walkthrough"


def test_prose_about_code_is_not_mistaken_for_code():
    """The trap: sentences that mention code words but are not a program."""
    for question in ("if the loss is high then the model is underfitting, right?",
                     "My accuracy = 0.94 but the recall is poor. What do I check?",
                     "I import my data from a CSV and then what?"):
        assert app.extract_pasted_code(question) == "", question
        assert app.route_mode(question) != "walkthrough", question


def test_pasted_code_still_yields_to_an_explicit_ask():
    assert app.route_mode("read this aloud\n```python\n" + PROGRAM + "```") == "audio"
    assert app.route_mode("draw a diagram of it\n```python\n" + PROGRAM + "```") == "images"


def test_routing_never_raises():
    for question in ("", None, "```", "\n\n\n", "?" * 500):
        assert app.route_mode(question) in app.VALID_MODES


def test_every_route_has_a_quota_bucket_and_a_label():
    for mode in app.VALID_MODES:
        assert mode in app.MODE_QUOTA, mode
        assert app.MODE_QUOTA[mode] in ("text", "code", "audio", "images", "sections")
        assert app.MODE_LABEL.get(mode), mode


# ------------------------------------------------------------------- packages

def test_packages_are_named_as_they_are_installed():
    found = {pkg["name"]: pkg for pkg in describe_packages(PROGRAM)}
    assert found["sklearn"]["pip"] == "scikit-learn"     # not "sklearn"
    assert found["numpy"]["pip"] == "numpy"
    assert found["matplotlib"]["pip"] == "matplotlib"
    assert all(pkg["role"] for pkg in found.values())


def test_the_standard_library_needs_no_install():
    packages = {pkg["name"]: pkg for pkg in describe_packages(
        "import os\nimport json\nfrom collections import deque\n")}
    assert set(packages) == {"os", "json", "collections"}
    assert all(pkg["stdlib"] and pkg["pip"] is None for pkg in packages.values())


def test_what_must_be_installed_comes_first():
    packages = describe_packages("import os\nimport torch\nimport json\nimport numpy\n")
    assert [pkg["name"] for pkg in packages] == ["numpy", "torch", "json", "os"]


def test_imports_are_parsed_not_matched():
    code = ('"""This docstring says import tensorflow, which is not an import."""\n'
            "def load():\n"
            "    import pandas as pd\n"
            "    return pd\n")
    assert [pkg["name"] for pkg in describe_packages(code)] == ["pandas"]


def test_a_fragment_that_will_not_parse_still_lists_its_imports():
    # Half a file is a normal thing to paste, and it must not come back empty.
    names = [pkg["name"] for pkg in describe_packages(
        "import numpy as np\nfor row in rows(   # cut off here")]
    assert names == ["numpy"]


def test_relative_and_duplicate_imports_are_handled():
    names = [pkg["name"] for pkg in describe_packages(
        "from . import helpers\nimport numpy\nimport numpy.linalg\n")]
    assert names == ["numpy"]                   # nothing to install for `from .`


def test_no_imports_is_empty_not_an_error():
    assert describe_packages("x = 1\nprint(x)\n") == []
    assert describe_packages("") == []
    assert describe_packages(None) == []


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok", name)
    print("all chat-routing checks passed")
