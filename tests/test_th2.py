import sys
import pytest
import subprocess
import importlib
from pathlib import Path
from typing import AnyStr

TESTS_DATA = Path(__file__).resolve().parent / "data"


def _find_script(name: str) -> str:
    spec = importlib.util.find_spec(name)
    assert spec is not None
    assert spec.origin is not None
    return spec.origin


def _non_empty_lines(buf: AnyStr) -> list[AnyStr]:
    return [line for line in buf.splitlines() if line]


def _assert_non_empty_lines_equal(left: AnyStr, right: AnyStr):
    assert _non_empty_lines(left) == _non_empty_lines(right)


script_th2_input = _find_script("th2_input")
script_th2_output = _find_script("th2_output")


@pytest.mark.parametrize("stem", [
    ("label-align"),
])
def test_th2_round_trip(stem):
    path_input = TESTS_DATA / f"{stem}.th2"
    svgcontent = subprocess.check_output([
        sys.executable,
        script_th2_input,
        str(path_input),
    ])
    th2content, stderr = subprocess.Popen(
        [sys.executable, script_th2_output],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    ).communicate(svgcontent)
    _assert_non_empty_lines_equal(path_input.read_bytes(), th2content)
