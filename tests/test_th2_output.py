import th2_output as m
import re
import pytest
import subprocess
import sys
from pathlib import Path

TESTS_DATA = Path(__file__).resolve().parent / "data"


def test_fstr():
    assert m.fstr(1.23456) == "1.2346"
    assert m.fstr(1.2) == "1.2"
    assert m.fstr(1) == "1.0"
    assert m.fstr(-1e-9) == "0.0"


def test_fstr2():
    assert m.fstr2(1.23456789) == "1.23456789"
    assert m.fstr2(1.23456789, dbl_dig=5) == "1.2346"
    assert m.fstr2(123.456789, dbl_dig=5) == "123.46"
    assert m.fstr2(1.23456789, max_dig=2) == "1.23"
    assert m.fstr2(1, dbl_dig=5) == "1.0"
    assert m.fstr2(1, max_dig=2) == "1.0"
    assert m.fstr2(-1e-9, max_dig=7) == "0.0"


def test_fstr_trim_zeros():
    assert m.fstr_trim_zeros("1.23") == "1.23"
    assert m.fstr_trim_zeros("1.2300") == "1.23"
    assert m.fstr_trim_zeros("1.0000") == "1.0"
    assert m.fstr_trim_zeros("1.0") == "1.0"
    assert m.fstr_trim_zeros("-0.000") == "0.0"
    with pytest.raises(AssertionError):
        m.fstr_trim_zeros("123")


TH2_LINE_SMOOTH_OFF = """
line u:unknown
  10.0 -70.0
  10.0 -70.0 20.0 -90.0 30.0 -90.0
  40.0 -90.0 40.0 -80.0 50.0 -70.0
  smooth off
  60.0 -80.0 60.0 -90.0 70.0 -90.0
  80.0 -90.0 90.0 -70.0 90.0 -70.0
  smooth off
endline
"""


def test_th2_output(tmp_path):
    path_input = TESTS_DATA / "ink1.svg"
    th2content = subprocess.check_output(
        [sys.executable, m.__file__, str(path_input)], encoding="utf-8")
    assert re.search(r"point .* altitude", th2content) is not None
    assert re.search(
        r'point .* label .* -text "<lang:de>German<lang:en>English<lang:fr>French"',
        th2content) is not None
    assert TH2_LINE_SMOOTH_OFF in th2content


def test_th2_output__options():
    path_input = TESTS_DATA / "ink1.svg"
    th2content = subprocess.check_output([sys.executable, m.__file__, "--options", '-author 1984 "Mäx Groß"', str(path_input)], encoding="utf-8")
    assert 'scrap scrap1 -author 1984 "Mäx Groß"' in th2content
    th2content = subprocess.check_output([sys.executable, m.__file__, "--options", '-author 1984 Mäx', str(path_input)], encoding="utf-8")
    assert 'scrap scrap1 -author 1984 "Mäx"' in th2content
