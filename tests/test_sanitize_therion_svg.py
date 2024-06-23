import sys
import pytest

if sys.version_info < (3, 9):
    pytest.skip("Python version", allow_module_level=True)

import sanitize_therion_svg as m
import inkex
from lxml import etree
from pathlib import Path

TESTS_DATA = Path(__file__).resolve().parent / "data"


def test_id_to_clip_path_value():
    assert m.id_to_clip_path_value("foo") == "url(#foo)"


def test_round_sig():
    assert m.round_sig(0.0) == 0.0
    assert m.round_sig(8.23456789, 3) == 8.23
    assert m.round_sig(823.456789, 6) == 823.457
    assert m.round_sig(-823.456789, 6) == -823.457


def test_is_colinear_on_axis():
    assert m.is_colinear_on_axis(0, [[0, 0], [0, 0], [0, 0]], [[5, 0], [5, 0], [5, 0]])
    assert m.is_colinear_on_axis(0, [[0, 0], [1, 0], [2, 0]], [[3, 0], [4, 0], [5, 0]])
    assert not m.is_colinear_on_axis(1, [[0, 0], [0, 0], [0, 0]], [[5, 0], [5, 0], [5, 0]])
    assert not m.is_colinear_on_axis(1, [[0, 0], [1, 0], [2, 0]], [[3, 0], [4, 0], [5, 0]])
    assert m.is_colinear_on_axis(1, [[0, 0], [0, 0], [0, 0]], [[0, 5], [0, 5], [0, 5]])
    assert m.is_colinear_on_axis(1, [[0, 0], [0, 1], [0, 2]], [[0, 3], [0, 4], [0, 5]])
    assert not m.is_colinear_on_axis(1, [[0, 0], [0, 0], [1, 0]], [[1, 5], [0, 5], [0, 5]])
    assert not m.is_colinear_on_axis(1, [[0, 0], [0, 1], [0, 2]], [[1, 3], [1, 4], [1, 5]])


def test_rel_aavec():
    assert m.rel_aavec([[0, 0], [0, 0], [0, 0]], [[5, 0], [5, 0], [5, 0]]) == (5, 0)
    assert m.rel_aavec([[0, 0], [0, 0], [0, 0]], [[0, 5], [0, 5], [0, 5]]) == (0, 5)
    try:
        m.rel_aavec([[0, 0], [0, 0], [0, 0]], [[5, 1], [5, 1], [5, 1]])
        raise AssertionError("did not raise")
    except m.NotLinear:
        pass
    assert m.rel_aavec([[4, 6], [4, 6], [4, 6]], [[1, 6], [1, 6], [1, 6]]) == (-3, 0)


def test_rev_vec():
    assert m.rev_vec((0.0, 0.0)) == (0.0, 0.0)
    assert m.rev_vec((1.2, 3.4)) == (-1.2, -3.4)


def test_clipPath_is_aligned_rect():
    assert m.clipPath_is_aligned_rect(inkex.ClipPath.new(inkex.Rectangle.new(1, 2, 3, 4)))
    d = "m 142.87,1.13 c 0,47.25 0,94.49 0,141.74 -47.25,0 -94.49,0 -141.74,0 0,-47.25 0,-94.49 0,-141.74 47.25,0 94.49,0 141.74,0"
    assert m.clipPath_is_aligned_rect(inkex.ClipPath.new(inkex.PathElement.new(d)))
    d = "m 0,0 h 10 v 10"
    assert not m.clipPath_is_aligned_rect(inkex.ClipPath.new(inkex.PathElement.new(d)))
    d = "M 0,0 L 10,0 L 5,5 z"
    assert not m.clipPath_is_aligned_rect(inkex.ClipPath.new(inkex.PathElement.new(d)))


def _read_xml(path: Path) -> bytes:
    tree = etree.parse(str(path), parser=etree.XMLParser(remove_blank_text=True))
    return etree.tostring(tree, encoding="utf-8").decode("utf-8")


def test_SanitizeTherionSvgExtension_run(tmp_path):
    m.SanitizeTherionSvgExtension().run(
        [str(TESTS_DATA / "sanitize_therion_svg-in.svg")], str(tmp_path / "out.svg"))
    out = _read_xml(tmp_path / "out.svg")
    ref = _read_xml(TESTS_DATA / "sanitize_therion_svg-out.svg")
    assert out == ref
