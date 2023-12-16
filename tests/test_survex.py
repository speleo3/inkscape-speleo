import survex as m

from pathlib import Path

TESTS_DATA = Path(__file__).resolve().parent / "data"


def test_Survex3D_umlaut():
    for path3d in (TESTS_DATA / "3d").glob("umlaut-*.3d"):
        s = m.Survex3D(path3d)
        assert s.length() == 460.0
        assert list(s.sortedlabels()) == ["1", "2", "3"]
        assert s.title == "Höhle mit Umlaut"
