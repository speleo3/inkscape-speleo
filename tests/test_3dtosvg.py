import shutil
import sys
import subprocess
from pathlib import Path
from lxml import etree

TESTS_DATA = Path(__file__).absolute().parent / "data"
PATH_UMLAUT_3D = TESTS_DATA / "3d/umlaut-utf8-v8.3d"

script_3dtosvg = Path(__file__).absolute().parents[1] / "extensions/3dtosvg.py"


def test_3dtosvg():
    svgcontent = subprocess.check_output([
        sys.executable,
        str(script_3dtosvg),
        str(PATH_UMLAUT_3D),
    ])
    root = etree.fromstring(svgcontent)
    d_attrib = root.xpath("svg:g/svg:path/@d",
                          namespaces={"svg": "http://www.w3.org/2000/svg"})
    assert d_attrib[0].strip() == "M 0,120 L 0,0 L 340,0"


def test_3dtosvg_extend(tmp_path):
    shutil.copy(PATH_UMLAUT_3D, tmp_path)
    path_input = tmp_path / PATH_UMLAUT_3D.name
    svgcontent = subprocess.check_output([
        sys.executable,
        str(script_3dtosvg),
        "--scalebar=false",
        "--stationnames=false",
        "--view=2",
        str(path_input),
    ])
    root = etree.fromstring(svgcontent)
    d_attrib = root.xpath("svg:g/svg:path/@d",
                          namespaces={"svg": "http://www.w3.org/2000/svg"})
    assert d_attrib[0].strip() == "M 0,0 L 340,0 L 460,0"


def test_3dtosvg_extend_espec(tmp_path):
    shutil.copy(PATH_UMLAUT_3D, tmp_path)
    path_input = tmp_path / PATH_UMLAUT_3D.name
    (tmp_path / f"{PATH_UMLAUT_3D.stem}.espec").write_text("*start 2\n")
    svgcontent = subprocess.check_output([
        sys.executable,
        str(script_3dtosvg),
        "--scalebar=false",
        "--stationnames=false",
        "--view=2",
        str(path_input),
    ])
    root = etree.fromstring(svgcontent)
    d_attrib = root.xpath("svg:g/svg:path/@d",
                          namespaces={"svg": "http://www.w3.org/2000/svg"})
    assert d_attrib[0].strip() == "M 0,0 L 340,0 M 0,0 L 120,0"
