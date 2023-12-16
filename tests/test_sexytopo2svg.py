import sexytopo2svg as m


def test_BBox():
    bbox = m.BBox()
    assert bbox.is_empty()
    bbox.add_point(3, 5)
    assert not bbox.is_empty()
    assert bbox.width() == 0
    assert bbox.height() == 0
    bbox.add_point(7, 6)
    assert not bbox.is_empty()
    assert bbox.width() == 4
    assert bbox.height() == 1
