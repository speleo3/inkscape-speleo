import th2ex
import th2ex as m
import pytest
from pytest import approx


def _skipunexpected(s):
    raise UserWarning(s)


multival = lambda *a: tuple(a)


def test_distance():
    assert m.distance((1, 0), (0, 0)) == 1
    assert m.distance((0, 2), (0, 0)) == 2
    assert m.distance((0, 0), (3, 0)) == 3
    assert m.distance((0, 0), (0, 4)) == 4
    assert m.distance((0, 3), (4, 0)) == 5


def test_convert_unit():
	assert m.convert_unit("3unknown", "m") == 0.0
	assert m.convert_unit("3m", "m") == approx(3.0)
	assert m.convert_unit("3m", "cm") == approx(300.0)
	assert m.convert_unit("3pt", "px") == approx(4.0)
	assert m.convert_unit("4px", "pt") == approx(3.0)
	assert m.convert_unit("4", "pt") == approx(3.0)


def test_unittouu():
    assert m.Th2Effect.unittouu("3m") == m.convert_unit("3m", "px")
    assert m.Th2Effect.unittouu("3px") == m.convert_unit("3px", "px")
    assert m.Th2Effect.unittouu("3") == m.convert_unit("3", "px")


def test_parse_scrap_scale_m_per_dots():
    assert m.parse_scrap_scale_m_per_dots("1") == 1
    assert m.parse_scrap_scale_m_per_dots("2") == 2
    assert m.parse_scrap_scale_m_per_dots("2 m") == 2
    assert m.parse_scrap_scale_m_per_dots("10 2 m") == 0.2
    assert m.parse_scrap_scale_m_per_dots("10 2 meters") == 0.2
    assert m.parse_scrap_scale_m_per_dots("[0 0 0 10 0 0 0 2]") == 0.2
    assert m.parse_scrap_scale_m_per_dots("[0 0 0 10 0 0 0 2 m]") == 0.2
    assert m.parse_scrap_scale_m_per_dots("[0 0 0 10 0 0 0 10 inch]") == 0.0254


def test_quote():
    assert '""' == th2ex.quote("")
    assert "foo" == th2ex.quote("foo")
    assert '"foo bar"' == th2ex.quote('foo bar')
    assert '"foo"" bar"' == th2ex.quote('foo" bar')
    assert '"""foo bar"""' == th2ex.quote('"foo bar"')
    assert '[foo bar]' == th2ex.quote('[foo bar]')


def test_splitquoted():
    assert ["foo"] == th2ex.splitquoted("foo")
    assert ["foo", "bar"] == th2ex.splitquoted("foo bar")
    assert ["foo bar"] == th2ex.splitquoted('"foo bar"')
    assert ["[foo bar]"] == th2ex.splitquoted('[foo bar]')
    assert ['[foo " bar]'] == th2ex.splitquoted('[foo " bar]')
    assert ['[foo "" bar]'] == th2ex.splitquoted('[foo "" bar]')
    assert ['foo " bar'] == th2ex.splitquoted('"foo "" bar"')
    assert ['foo"bar'] == th2ex.splitquoted('"foo""bar"')
    assert ["foo", "bar"] == th2ex.splitquoted('"foo" "bar"')
    assert ['"foo bar"'] == th2ex.splitquoted('"""foo bar"""')


def test_parse_options():
    parse_options = th2ex.parse_options

    # spaced argument
    expected = {'foo': 'bar', 'bar': "Thomas Höhle"}
    assert expected == parse_options('-foo bar -bar "Thomas Höhle"')

    # spaced argument with quote
    expected = {'foo': 'bar', 'bar': 'Thomas" Höhle'}
    assert expected == parse_options('-foo bar -bar "Thomas"" Höhle"')

    # spaced argument with escaped quote
    expected = {'foo': 'bar', 'bar': 'Thomas\\" Höhle'}
    assert expected == parse_options(r'-foo bar -bar "Thomas\"" Höhle"')

    # spaced argument with backslash
    expected = {'foo': 'bar', 'bar': 'Thomas Höhle\\'}
    assert expected == parse_options('-foo bar -bar "Thomas Höhle\\"')

    # spaced argument with quote-backslash
    expected = {'foo': 'bar', 'bar': 'Thomas Höhle"\\'}
    assert expected == parse_options('-foo bar -bar "Thomas Höhle""\\"')

    # parse_options with list (needed?)
    expected = {'foo': 'bar', 'com': 'bla'}
    assert expected == parse_options(['-foo', 'bar', '-com', 'bla'])

    # simple multi-value
    expected = {'foo': multival('bar', 'com'), 'bla': True}
    assert expected == parse_options('-foo bar com -bla')

    # spaced multi-value
    expected = {'author': [multival('2001', 'Thomas Höhle')]}
    assert expected == parse_options('-author 2001 "Thomas Höhle"')

    # brackated value
    expected = {'foo': '[1 2 3]', 'bla': True}
    assert expected == parse_options('-foo [1 2 3] -bla')

    # brackated multi-arg value
    expected = {'foo': multival('xxx', '[1 2 3]', 'yyy')}
    assert expected == parse_options('-foo xxx [1 2 3] yyy')

    # known multi-arg
    expected = {'attr': [multival('foo', '-bar'), multival('x', '123')]}
    assert expected == parse_options('-attr foo -bar -attr x 123')


def test_format_options():
    assert th2ex.format_options({'foo': 'bar', 'bla': '1 2 3'}) == '-bla "1 2 3" -foo bar'
    assert th2ex.format_options({'foo': True, 'bla': '[1 2 3]'}) == '-bla [1 2 3] -foo'
    assert th2ex.format_options({'author': "2000 Max"}) == '-author 2000 Max'
    assert th2ex.format_options({'author': ("2000 Max")}) == '-author 2000 Max'
    assert th2ex.format_options({'author': ["2000 Max"]}) == '-author 2000 Max'
    assert th2ex.format_options({'author': [("2000 Max")]}) == '-author 2000 Max'
    assert th2ex.format_options({'author': [("2000", "Max Foo"), ("2000", "Jane Bar")]}) == '-author 2000 "Max Foo" -author 2000 "Jane Bar"'
    assert m.format_options(m.parse_options('-align b -orientation 25.723')) == '-orientation 25.723 -align b'


def test_format_options__legacy(capsys):
    assert th2ex.format_options({'author-2000': "Max"}) == '-author 2000 Max'
    captured = capsys.readouterr()
    assert "Legacy two-arg key: author-2000" in captured.err


def test_name_survex2therion():
    assert th2ex.name_survex2therion('3') == '3'
    assert th2ex.name_survex2therion('ab.cd.3') == '3@cd.ab'


def test_name_therion2survex():
    assert th2ex.name_therion2survex('3') == '3'
    assert th2ex.name_therion2survex('3@cd.ab') == 'ab.cd.3'
    assert th2ex.name_therion2survex('3.4@cd.ab') == 'ab.cd.4.3'


def test_is_numeric():
    assert th2ex.is_numeric('abc') is False
    assert th2ex.is_numeric('123') is True
    assert th2ex.is_numeric('-1e10') is True


def test_maybe_key():
    assert th2ex.maybe_key('-foo') is True
    assert th2ex.maybe_key('foo') is False
    assert th2ex.maybe_key('-a b') is False
    assert th2ex.maybe_key('-e10') is True
    assert th2ex.maybe_key('-1e10') is False


def test_parse_options__unexpected(monkeypatch):
    monkeypatch.setattr(th2ex, '_skipunexpected', _skipunexpected)
    # unexpected "foo", expect key
    with pytest.raises(UserWarning):
        th2ex.parse_options('foo')
    # unexpected "com" because -attr takes two values
    with pytest.raises(UserWarning):
        th2ex.parse_options('-attr foo -bar com')
    with pytest.raises(UserWarning, match="assertion failed on $"):
        m.parse_options(['-text', 'bar', '""'])


def test_get_fonts_setup_default():
    assert m.get_fonts_setup_default(10) == m.fonts_setup_defaults[100]
    assert m.get_fonts_setup_default(200) == m.fonts_setup_defaults[200]
    assert m.get_fonts_setup_default(250) == m.fonts_setup_defaults[500]
    assert m.get_fonts_setup_default(999) == m.fonts_setup_defaults[float("inf")]


def test_parseViewBox():
    mat = m.parseViewBox("0 0 15 10", "30", "20")
    assert mat == [[2, 0, 0], [0, 2, 0]]
    mat = m.parseViewBox("12 34 15 10", "30", "20")
    assert mat == [[2, 0, -12], [0, 2, -34]]
