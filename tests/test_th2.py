import pytest
import subprocess
import importlib
from pathlib import Path
from typing import AnyStr, List

TESTS_DATA = Path(__file__).resolve().parent / "data"


def _find_script(name: str) -> str:
    spec = importlib.util.find_spec(name)
    assert spec is not None
    assert spec.origin is not None
    return spec.origin


def _non_empty_lines(buf: AnyStr) -> List[AnyStr]:
    return [line.rstrip() for line in buf.splitlines() if line]


def _assert_non_empty_lines_equal(left: AnyStr, right: AnyStr):
    assert _non_empty_lines(left) == _non_empty_lines(right)


script_th2_input = _find_script("th2_input")
script_th2_output = _find_script("th2_output")


@pytest.mark.parametrize("stem,basescale", [
    ("label-align", 1),
    ("label-scale", 0.5),
    ("label-scale", 2),
    ("create", 1),
    ("create", 2),
    ("slope", 2),
])
def test_th2_round_trip(stem, basescale, monkeypatch, executable_args):
    monkeypatch.chdir(TESTS_DATA)
    path_input = Path(f"{stem}.th2")
    svgcontent = subprocess.check_output(executable_args + [
        script_th2_input,
        f"--basescale={basescale}",
        str(path_input),
    ])
    th2content, stderr = subprocess.Popen(
        executable_args + [script_th2_output],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    ).communicate(svgcontent)
    _assert_non_empty_lines_equal(path_input.read_bytes(), th2content)
