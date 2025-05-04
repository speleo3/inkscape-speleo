import joinpaths as m
from inkex0 import cubicsuperpath


def cusp(p):
    p = [float(x) for x in p]
    return [p, p, p]


def test_join_csps():
    csp1 = cubicsuperpath.parsePath("M 0,0 L 10,1")
    csp2 = cubicsuperpath.parsePath("M 12,3 L 15,20")
    csp = m.join_csps([csp1, csp2])
    assert csp == [[
        cusp([0, 0]),
        cusp([11, 2]),
        cusp([15, 20]),
    ]]


def test_join_csps__drop2():
    csp1 = cubicsuperpath.parsePath("M 0,0 L 10,1 L 11,1.5 L 11,1")
    csp2 = cubicsuperpath.parsePath("M 11,3, L 11,2.5 L 12,3 L 15,20")
    csp = m.join_csps([csp1, csp2])
    assert csp == [[
        cusp([0, 0]),
        cusp([10, 1]),
        # 2 points dropped
        cusp([11, 2]),
        # 2 points dropped
        cusp([12, 3]),
        cusp([15, 20]),
    ]]
