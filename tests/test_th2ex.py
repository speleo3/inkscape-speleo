import th2ex
import pytest


def _skipunexpected(s):
    raise UserWarning(s)


th2ex._skipunexpected = _skipunexpected

multival = lambda *a: tuple(a)


def test_quote():
    assert "foo" == th2ex.quote("foo")
    assert '"foo bar"' == th2ex.quote('foo bar')
    assert '"foo\\" bar"' == th2ex.quote('foo" bar')
    assert '[foo bar]' == th2ex.quote('[foo bar]')


def test_splitquoted():
    assert ["foo"] == th2ex.splitquoted("foo")
    assert ["foo", "bar"] == th2ex.splitquoted("foo bar")
    assert ["foo bar"] == th2ex.splitquoted('"foo bar"')
    assert ["[foo bar]"] == th2ex.splitquoted('[foo bar]')


def test_parse_options():
    parse_options = th2ex.parse_options

    # spaced argument
    expected = {'foo': 'bar', 'bar': "Thomas Höhle"}
    assert expected == parse_options('-foo bar -bar "Thomas Höhle"')

    # spaced argument with quote
    expected = {'foo': 'bar', 'bar': 'Thomas" Höhle'}
    assert expected == parse_options('-foo bar -bar "Thomas\\" Höhle"')

    # spaced argument with escaped quote
    expected = {'foo': 'bar', 'bar': 'Thomas\\" Höhle'}
    assert expected == parse_options(r'-foo bar -bar "Thomas\\\" Höhle"')

    # spaced argument with backslash
    expected = {'foo': 'bar', 'bar': 'Thomas Höhle\\'}
    assert expected == parse_options('-foo bar -bar "Thomas Höhle\\\\"')

    # spaced argument with quote-backslash
    expected = {'foo': 'bar', 'bar': 'Thomas Höhle"\\'}
    assert expected == parse_options('-foo bar -bar "Thomas Höhle\\"\\\\"')

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


def test_name_survex2therion():
    assert th2ex.name_survex2therion('ab.cd.3') == '3@cd.ab'


def test_name_therion2survex():
    assert th2ex.name_therion2survex('3@cd.ab') == 'ab.cd.3'


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


def test_zero_division():
    # unexpected "foo", expect key
    with pytest.raises(UserWarning):
        th2ex.parse_options('foo')
    # unexpected "com" because -attr takes two values
    with pytest.raises(UserWarning):
        th2ex.parse_options('-attr foo -bar com')
