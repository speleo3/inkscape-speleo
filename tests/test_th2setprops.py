import th2setprops as m
import os
import pytest
import subprocess
from pathlib import Path
from lxml import etree

TESTS_DATA = Path(__file__).resolve().parent / "data"

ns = {
    "svg": "http://www.w3.org/2000/svg",
    "xlink": "http://www.w3.org/1999/xlink",
}


@pytest.mark.parametrize("ioencoding", [
    "utf-8",
    "cp1252",
])
def test_th2setprops(ioencoding, tmp_path, executable_args):
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = ioencoding
    env["PYTHONUTF8"] = "1" if ioencoding == "utf-8" else "0"
    env["LC_ALL"] = f"C.{ioencoding}"
    path_input = TESTS_DATA / "ink2.svg"
    path_output = tmp_path / "output.svg"
    args = executable_args + [
        m.__file__,
        "--role=point",
        "--type=height",
        "--dropstyle=true",
        "--id=rect1",
        "--output=" + str(path_output),
        str(path_input),
    ]
    subprocess.check_call(args, env=env)
    tree = etree.fromstring(path_output.read_bytes())

    texts = tree.xpath("//svg:symbol[@id='point-height']/svg:text//text()",
                       namespaces=ns)
    assert "".join(texts) == "±X"

    nodes = tree.xpath("//svg:use[@xlink:href='#point-height']", namespaces=ns)
    assert len(nodes) == 1
    assert nodes[0].attrib["x"].rstrip(".0") == "35"


def test_th2setprops__align(tmp_path, executable_args):
    path_input = TESTS_DATA / "ink1.svg"
    args = executable_args + [
        m.__file__,
        "--options=-align left",
        "--id=multiline",
        str(path_input),
    ]
    bytes_output = subprocess.check_output(args)
    tree = etree.fromstring(bytes_output)
    style: str = tree.xpath("//svg:text[@id='multiline']/@style",
                            namespaces=ns,
                            smart_strings=False)[0]  # type: ignore
    assert "text-anchor:end" in style
    assert "dominant-baseline:middle" in style
