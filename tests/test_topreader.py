import topreader as m

import io
from lxml import etree
from pathlib import Path
from pytest import approx
import pytest

TESTS_DATA = Path(__file__).resolve().parent / "data"


def test_distmm():
    mm = 1234567
    meter = 1234.567
    assert m.distmm(mm) == meter
    assert m.distmm_inv(meter) == approx(mm)


@pytest.mark.parametrize("angle", [1234, 1])
def test_adegrees(angle: int):
    angle_deg = m.adegrees(angle)
    assert m.adegrees_inv(angle_deg) == angle


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
    assert "set XVIshots {" in content
