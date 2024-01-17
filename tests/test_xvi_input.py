import xvi_input

import sys
import subprocess
from pathlib import Path
from lxml import etree

TESTS_DATA = Path(__file__).resolve().parent / "data"


def test_xvi_input_script():
    svgcontent = subprocess.check_output([
        sys.executable,
        xvi_input.__file__,
        str(TESTS_DATA / "create.xvi"),
    ])
    root = etree.fromstring(svgcontent)
    assert root.tag == "{http://www.w3.org/2000/svg}svg"
    assert root.get("width") == "13.0cm"
    assert root.get("height") == "12.0cm"
    assert root.get("viewBox") == "-254.921000 -233.660000 511.810000 472.440000"
    assert root.get("{http://therion.speleo.sk/therion}xvi-dx") == "19.685"
    assert root.get("{http://therion.speleo.sk/therion}xvi-dy") == "19.685"
    assert root[0].tag == "{http://www.w3.org/2000/svg}g"
    assert root[0].get("{http://www.inkscape.org/namespaces/inkscape}label") == "Shots"
    assert root[0][0].tag == "{http://www.w3.org/2000/svg}path"
    assert root[0][0].get("d") == "M 197.83 179.72 174.41 103.15"


def test_xvi2svg():
    with open(TESTS_DATA / "create.xvi") as handle:
        root = xvi_input.xvi2svg(handle, fullsvg=False)
    assert root.tag == "{http://www.w3.org/2000/svg}g"
    assert root[0].tag == "{http://www.w3.org/2000/svg}g"
    assert root[0].get("{http://www.inkscape.org/namespaces/inkscape}label") == "Shots"
    assert root[0][0].tag == "{http://www.w3.org/2000/svg}path"
    assert root[0][0].get("d") == "M 197.83 179.72 174.41 103.15"
