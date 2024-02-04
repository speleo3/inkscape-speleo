import th2_output as m
import pytest


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
    with pytest.raises(Exception):
        m.fstr_trim_zeros("123")
