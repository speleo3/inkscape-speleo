import makerock as m

import math
from pathlib import Path
import lxml.etree as etree
import th2ex
from inkex0 import cubicsuperpath

TESTS_DATA = Path(__file__).resolve().parent / "data"


def test_angleman():
    assert m.anglemean(5, 1) == 3
    assert m.anglemean(math.pi, 0) == math.pi / 2
    assert m.anglemean(math.pi / 2, -math.pi / 4) == math.pi / 8
    assert m.anglemean(math.pi / 2, math.pi / 4) == math.pi * 3 / 8


def test_mean():
    assert m.mean(5, 1) == 3
    assert m.mean(-5, 1) == -2
    assert m.mean(-5, -3) == -4


def test_make_rock():
    tree = etree.parse(str(TESTS_DATA / "raw-rock.svg"))
    pathnode = th2ex.xpath_elems(tree, "//svg:path")[0]
    assert isinstance(pathnode, etree._Element)
    m.make_rock(pathnode, True)
    assert pathnode.get("style") is None
    assert pathnode.get("class") == "line rock-border"
    d = pathnode.get("d", "")
    assert d[-1:].lower() == "z"
    superpath = cubicsuperpath.parsePath(d)
    assert len(superpath) == 1
    assert 8 < len(superpath[0]) < 11
