"""Smallest checks for the image-prompt contract the app depends on."""
import base64
import io

from PIL import Image

from utils.image_utils import _enhance_educational_prompt, _ink_fraction, STYLE


def test_style_always_appended():
    # The old code skipped styling when the prompt already said "diagram" or
    # "background" - exactly the case that produced blank white images.
    out = _enhance_educational_prompt("a decision tree diagram on a white background")
    assert STYLE in out


def test_topic_prefixed_when_missing():
    out = _enhance_educational_prompt("a flowchart of the update step", topic="Q-Learning")
    assert out.startswith("Q-Learning: a flowchart")


def test_topic_not_duplicated():
    out = _enhance_educational_prompt("Q-Learning flowchart", topic="Q-Learning")
    assert out.count("Q-Learning") == 1


def _jpeg(colour):
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), colour).save(buf, format="JPEG")
    return buf.getvalue()


def test_blank_image_detected():
    assert _ink_fraction(_jpeg((255, 255, 255))) < 0.04


def test_inked_image_passes():
    assert _ink_fraction(_jpeg((10, 20, 60))) > 0.04


if __name__ == "__main__":
    test_style_always_appended()
    test_topic_prefixed_when_missing()
    test_topic_not_duplicated()
    test_blank_image_detected()
    test_inked_image_passes()
    print("image prompt + blank-detection checks passed")
