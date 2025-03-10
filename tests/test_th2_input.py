import th2_input as m
import pytest
from pytest import approx


@pytest.fixture(autouse=True, scope="module")
def setup_basescale():
    m.th2pref.set_basescale(4)


def test_floatscale():
    assert m.floatscale("8.0") == 2.0


def test_flipY():
    a = [c.rstrip("0") for c in m.flipY(["1", "2", "4", "6", "8", "10"])]
    assert a == ["0.25", "-0.5", "1.", "-1.5", "2.", "-2.5"]


def test_reverseP():
    assert m.formatPath(
        m.reverseP([("M", (1, 2)), ("L", (3, 4)),
                    ("C", (5, 6, 7, 8, 9, 10))])) == "M9 10C7 8 5 6 3 4L1 2"


def test_text_to_styles():
    assert m.text_to_styles("foo") == {}
    assert m.text_to_styles("<bf><rm>foo<it>") == {
        "font-family": "serif",
        "font-weight": "bold",
    }


def test_scale_to_fontsize():
    assert m.scale_to_fontsize("s") == approx(8.36319)
    assert m.scale_to_fontsize("small") == approx(8.36319)
    assert m.scale_to_fontsize("m") == approx(9.557926)
    assert m.scale_to_fontsize("normal") == approx(9.557926)
    assert m.scale_to_fontsize("xl") == approx(16.726370)
    assert m.scale_to_fontsize("huge") == approx(16.726370)
    assert m.scale_to_fontsize("1") == approx(9.557926)
    assert m.scale_to_fontsize("2") == approx(19.115852)
