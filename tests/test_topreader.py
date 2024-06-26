import topreader as m

import io
from lxml import etree
from pathlib import Path
from pytest import approx
import pytest
import sys

TESTS_DATA = Path(__file__).resolve().parent / "data"


def assert_stripped_lines_equal(lhs: str, rhs = "", path = None):
    if path is not None:
        assert not rhs
        rhs = Path(path).read_text()
    lines_lhs = [line.strip() for line in lhs.splitlines()]
    lines_rhs = [line.strip() for line in rhs.splitlines()]
    assert lines_lhs == lines_rhs


@pytest.mark.skipif(sys.version_info < (3, 10), reason="Python version")
@pytest.mark.parametrize("s, suffix", [
    ("foobar", "bar"),
    ("foobar", "foo"),
    ("foobar", "foobar"),
    ("foobar", ""),
])
def test_removesuffix(s, suffix):
    assert m.removesuffix(s, suffix) == s.removesuffix(suffix)


def test_distmm():
    mm = 1234567
    meter = 1234.567
    assert m.distmm(mm) == meter
    assert m.distmm_inv(meter) == approx(mm)


@pytest.mark.parametrize("angle", [1234, 1])
def test_adegrees(angle: int):
    angle_deg = m.adegrees(angle)
    assert m.adegrees_inv(angle_deg) == angle


def test_posdeg():
    assert m.posdeg(0.0) == approx(0.0)
    assert m.posdeg(12.3) == approx(12.3)
    assert m.posdeg(-12.3) == approx(347.7)


def test_avgdeg():
    assert m.avgdeg([]) == approx(0.0)
    assert m.avgdeg([1.2]) == approx(1.2)
    assert m.avgdeg([1.2, 3.4]) == approx(2.3)
    assert m.avgdeg([1, 2, 3, 8]) == approx(3.5, abs=1e-3)
    assert m.avgdeg([10, 350]) == approx(0.0)
    assert m.avgdeg([20, 350]) == approx(5.0)
    assert m.avgdeg([20, -10]) == approx(5.0)
    assert m.avgdeg([-20, 350]) == approx(-15.0)
    assert m.avgdeg([1, 179]) == approx(90)
    assert m.avgdeg([1, 179 - 4]) == approx(88)
    assert m.avgdeg([1, 179 + 4]) == approx(-88)


def test_is_consecutive_number():
    assert m.is_consecutive_number("0", "1")
    assert m.is_consecutive_number("1.0", "1.1")
    assert not m.is_consecutive_number("0", "0")
    assert not m.is_consecutive_number("0", "2")
    assert not m.is_consecutive_number("1.0", "1.0")
    assert not m.is_consecutive_number("1.0", "1.2")


def test_make_Point():
    x, y = m._make_Point(2, 3)
    inv = m._make_Point_inv(x, y)
    assert inv == (2, 3)


def _assert_top_test1(top: dict):
    assert top["version"] == 3
    assert top["trips"][0]["date"][:3] == (2020, 1, 30)
    assert top["trips"][0]["comment"] == "\r\n".join([
        "A123456789012345678901234567", "B123456789012345678901234567",
        "C123456789012345678901234567", "D123456789012345678901234567",
        "E123456789012345678901234567", "F123456789012345678901234567",
        "G123456789012345678901234567", "H123456789012345678901234567",
        "I123456789012345678901234567", "J123456789012345678901234567", ""
    ])
    assert top["trips"][0]["dec"] == approx(1.23, abs=1e-3)
    assert top["shots"][2] == {
        "from": "16.29",
        "to": "16.33",
        "tape": 13.105,
        "compass": approx(33.26710917830167),
        "clino": approx(2.2192721446555277),
        "rollangle": approx(1.4117647058823528),
        "trip": 0,
        "direction": ">",
        "comment": "Shot comment\r\nSC Line two",
    }
    assert top["ref"][0] == ["16.29", 1.2, 3.4, 5.6, ""]
    assert top["transform"] == {"center": (10.75, -9.9), "scale": 750}
    assert top["outline"]["polys"][0]["colour"] == "blue"
    assert top["outline"]["polys"][0]["coord"][2] == (2.657, -11.998)
    assert top["outline"]["xsec"] == [
        {
            "position": (9.817, -18.888),
            "station": "16.35",
            "compass": approx(71.70885786221103),
        },
        {
            "position": (3.137, -13.908),
            "station": "16.33",
            "compass": approx(36.6179903868162),
        },
    ]


def test_load():
    with open(TESTS_DATA / "test1.top", "rb") as handle:
        top = m.load(handle)
    _assert_top_test1(top)
    content = m.dumps(top)
    top = m.loads(content)
    _assert_top_test1(top)


def test_dump_svg():
    with open(TESTS_DATA / "test1.top", "rb") as handle:
        top = m.load(handle)
    out = io.StringIO()
    m.dump_svg(top, file=out)
    content = out.getvalue()
    xml = etree.fromstring(content)
    assert xml is not None


def test_dump_th2():
    with open(TESTS_DATA / "test1.top", "rb") as handle:
        top = m.load(handle)
    out = io.StringIO()
    m.dump_th2(top, file=out)
    content = out.getvalue()
    assert "line u:black" in content
    assert "scrap s_plan_unknown -projection plan" in content


def test_dump_th2__sideview():
    with open(TESTS_DATA / "test1.top", "rb") as handle:
        top = m.load(handle)
    top["filename"] = "test1.top"
    out = io.StringIO()
    m.dump_th2(top, file=out, view="sideview")
    content = out.getvalue()
    assert "scrap s_extended_test1 -projection extended" in content


def test_dump_svx():
    with open(TESTS_DATA / "test1.top", "rb") as handle:
        top = m.load(handle)
    out = io.StringIO()
    m.dump_svx(top, file=out)
    content = out.getvalue()
    assert "*data normal " in content


def test_dump_tro():
    with open(TESTS_DATA / "test1.top", "rb") as handle:
        top = m.load(handle)
    out = io.StringIO()
    m.dump_tro(top, file=out)
    content = out.getvalue()
    assert "Param Deca Degd Clino Degd" in content


def test_dump_xvi():
    with open(TESTS_DATA / "test1.top", "rb") as handle:
        top = m.load(handle)
    out = io.StringIO()
    m.dump_xvi(top, file=out)
    content = out.getvalue()
    assert_stripped_lines_equal(content, path=TESTS_DATA / "test1.top.outline.xvi")


def test_dump_xvi__sideview():
    with open(TESTS_DATA / "test1.top", "rb") as handle:
        top = m.load(handle)
    out = io.StringIO()
    m.dump_xvi(top, file=out, view="sideview")
    content = out.getvalue()
    assert_stripped_lines_equal(content, path=TESTS_DATA / "test1.top.sideview.xvi")
