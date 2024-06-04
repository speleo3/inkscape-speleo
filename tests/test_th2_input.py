import th2_input as m


def test_distance():
    assert m.distance((1, 0), (0, 0)) == 1
    assert m.distance((0, 2), (0, 0)) == 2
    assert m.distance((0, 0), (3, 0)) == 3
    assert m.distance((0, 0), (0, 4)) == 4
    assert m.distance((0, 3), (4, 0)) == 5


def test_parse_scrap_scale_m_per_dots():
    assert m.parse_scrap_scale_m_per_dots("1") == 1
    assert m.parse_scrap_scale_m_per_dots("2") == 2
    assert m.parse_scrap_scale_m_per_dots("2 m") == 2
    assert m.parse_scrap_scale_m_per_dots("10 2 m") == 0.2
    assert m.parse_scrap_scale_m_per_dots("10 2 meters") == 0.2
    assert m.parse_scrap_scale_m_per_dots("[0 0 0 10 0 0 0 2]") == 0.2
    assert m.parse_scrap_scale_m_per_dots("[0 0 0 10 0 0 0 2 m]") == 0.2
    assert m.parse_scrap_scale_m_per_dots("[0 0 0 10 0 0 0 10 inch]") == 0.0254
