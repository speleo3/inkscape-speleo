import topreader as m


def test_is_consecutive_number():
    assert m.is_consecutive_number("0", "1")
    assert m.is_consecutive_number("1.0", "1.1")
    assert not m.is_consecutive_number("0", "0")
    assert not m.is_consecutive_number("0", "2")
    assert not m.is_consecutive_number("1.0", "1.0")
    assert not m.is_consecutive_number("1.0", "1.2")
