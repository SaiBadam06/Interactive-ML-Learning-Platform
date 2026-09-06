"""Smallest check that the two output contracts the app parses still hold."""
from utils.image_utils import _enhance_educational_prompt


def test_enhance_always_names_ink_colour():
    # A prompt that already mentions "diagram"/"background" must still get the
    # contrast styling - the old code skipped it and produced white-on-white.
    out = _enhance_educational_prompt("a decision tree diagram on a white background")
    assert "dark navy" in out and "strong contrast" in out


def test_enhance_appends_to_bare_prompt():
    out = _enhance_educational_prompt("a neural network")
    assert out.startswith("a neural network,") and "flat vector infographic" in out


if __name__ == "__main__":
    test_enhance_always_names_ink_colour()
    test_enhance_appends_to_bare_prompt()
    print("image prompt checks passed")
