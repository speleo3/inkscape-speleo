import th2enumeratestations
import th2ex
import subprocess
import sys
from pathlib import Path
from lxml import etree

TESTS_DATA = Path(__file__).resolve().parent / "data"


def test_th2setprops():
    path_input = TESTS_DATA / "ink2.svg"
    args = [
        sys.executable,
        th2enumeratestations.__file__,
        "--role=point",
        "--type=station",
        "--id=rect1",
        "--id=rect2",
        "--stationname=5",
        str(path_input),
    ]
    output = subprocess.check_output(args)
    tree = etree.fromstring(output)
    props = th2ex.get_props(tree.find(".//*[@id='rect1']"))
    assert props == ("point", "station", {"name": "5"})
    props = th2ex.get_props(tree.find(".//*[@id='rect2']"))
    assert props == ("point", "station", {"name": "6"})


def test_StationName():
    stationName = th2enumeratestations.StationName("0")
    assert('0') == stationName.next()
    assert('1') == stationName.next()
    stationName = th2enumeratestations.StationName("000")
    assert('000') == stationName.next()
    assert('001') == stationName.next()
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
    stationName = th2enumeratestations.StationName("1.9")
    assert('1.9') == stationName.next()
    assert('1.10') == stationName.next()
    stationName = th2enumeratestations.StationName("A.9")
    assert('A.9') == stationName.next()
    assert('A.10') == stationName.next()
    stationName = th2enumeratestations.StationName("1/9")
    assert('1/9') == stationName.next()
    assert('1/10') == stationName.next()
    stationName = th2enumeratestations.StationName("1_9")
    assert('1_9') == stationName.next()
    assert('1_10') == stationName.next()
    stationName = th2enumeratestations.StationName("9@1")
    assert('9@1') == stationName.next()
    assert('10@1') == stationName.next()
    stationName = th2enumeratestations.StationName("9@A")
    assert('9@A') == stationName.next()
    assert('10@A') == stationName.next()
    stationName = th2enumeratestations.StationName("abc123@def")
    assert('abc123@def') == stationName.next()
    assert('abc124@def') == stationName.next()
    stationName = th2enumeratestations.StationName("123abc@def")
    assert('123abc@def') == stationName.next()
    assert('123abd@def') == stationName.next()
    stationName = th2enumeratestations.StationName("Aa")
    assert('Aa') == stationName.next()
    assert('Ab') == stationName.next()
    stationName = th2enumeratestations.StationName("aA")
    assert('aA') == stationName.next()
    assert('aB') == stationName.next()


def test_StationName__Z():
    stationName = th2enumeratestations.StationName("Z")
    assert('Z') == stationName.next()
    assert('AA') == stationName.next()
    stationName = th2enumeratestations.StationName("AAAZZ")
    assert('AAAZZ') == stationName.next()
    assert('AABAA') == stationName.next()
