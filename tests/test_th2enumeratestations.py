import th2enumeratestations
import pytest

def test_SeparateStationNames():
    assert ('', '1') == th2enumeratestations.SeparateStationNameParts("1")
    assert ('', 'A') == th2enumeratestations.SeparateStationNameParts("A")
    assert ('abc', '123') == th2enumeratestations.SeparateStationNameParts("abc123")
    assert ('123', 'abc') == th2enumeratestations.SeparateStationNameParts("123abc")
    assert ('', '123') == th2enumeratestations.SeparateStationNameParts("123")
    assert ('', 'abc') == th2enumeratestations.SeparateStationNameParts("abc")
    assert ('a1b2c', '3') == th2enumeratestations.SeparateStationNameParts("a1b2c3")


def test_StationName():
    stationName = th2enumeratestations.StationName("1")
    assert('1') == stationName.next()
    assert('2') == stationName.next()
    stationName = th2enumeratestations.StationName("A")
    assert('A') == stationName.next()
    assert('B') == stationName.next()
    stationName = th2enumeratestations.StationName("A1")
    assert('A1') == stationName.next()
    assert('A2') == stationName.next()
    stationName = th2enumeratestations.StationName("abc123")
    assert('abc123') == stationName.next()
    assert('abc124') == stationName.next()
    stationName = th2enumeratestations.StationName("123abc")
    assert('123abc') == stationName.next()
    assert('123abd') == stationName.next()
    stationName = th2enumeratestations.StationName("123")
    assert('123') == stationName.next()
    assert('124') == stationName.next()
    stationName = th2enumeratestations.StationName("abc")
    assert('abc') == stationName.next()
    assert('abd') == stationName.next()
    stationName = th2enumeratestations.StationName("a1b2c3")
    assert('a1b2c3') == stationName.next()
    assert('a1b2c4') == stationName.next()
