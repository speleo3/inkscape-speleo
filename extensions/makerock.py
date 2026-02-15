#!/usr/bin/env python
'''
Turn circular drawings into rocks

Copyright (C) 2025 Thomas Holder
'''

import th2ex
from th2ex import (
    EtreeElement,
    Th2Effect,
)

from inkex0 import cubicsuperpath
from inkex0.cubicsuperpath import SuperPath, Point
from inkex import errormsg  # type: ignore[reportPrivateImportUsage]
import math
import numpy as np
from typing import List, Tuple

Radians = float
Length = float
CircleCoord = Tuple[Radians, Length]

FULLCIRCLE_RADIANS = 2 * math.pi


def make_circle_coords(x: float, y: float) -> CircleCoord:
    angle = math.atan2(y, x)
    length = (x**2 + y**2)**0.5
    return angle, length


def anglesub(a: float, b: float) -> float:
    return (a - b) % FULLCIRCLE_RADIANS


def anglemean(a: float, b: float) -> float:
    m = (b + anglesub(a, b) / 2) % FULLCIRCLE_RADIANS
    return m


def mean(a: float, b: float) -> float:
    return (a + b) / 2


def pop_small_angles_in_place(circlecoords: List[CircleCoord],
                              angle_min: Radians = math.radians(20)):
    circlecoords.sort()
    while len(circlecoords) > 4:
        deltas = [(anglesub(cc[0], circlecoords[i - 1][0]), i)
                  for (i, cc) in enumerate(circlecoords)]
        angle, i = min(deltas)
        if angle > angle_min:
            break
        cc = circlecoords.pop(i)
        cp = circlecoords[i - 1]
        circlecoords[i - 1] = (
            anglemean(cc[0], cp[0]),
            mean(cc[1], cp[1]),  # length
        )


def csp_from_circlecoords(circlecoords: List[CircleCoord],
                          center: np.ndarray) -> SuperPath:
    cx, cy = center
    points: List[Point] = []
    for angle, length in circlecoords:
        x = cx + length * math.cos(angle)
        y = cy + length * math.sin(angle)
        points.append([x, y])
    return [[[p, p, p] for p in points]]


def make_rock(node: EtreeElement, dropstyle: bool):
    d = node.get("d")
    if not d:
        errormsg(f'warning: no d for id={node.get("id")}')
        return

    csp = cubicsuperpath.parsePath(d)

    flatpoints = np.array(
        [handledpoint[1] for subpath in csp for handledpoint in subpath])
    assert flatpoints.shape[1:] == (2, )
    center: np.ndarray = flatpoints.mean(0)
    assert center.shape == (2, )
    circlecoords = [make_circle_coords(*p) for p in (flatpoints - center)]
    pop_small_angles_in_place(circlecoords)
    csp = csp_from_circlecoords(circlecoords, center)
    d = cubicsuperpath.formatPath(csp)
    if d and not d[-1].lower() == 'z':
        d += 'z'
    node.attrib["d"] = d
    node.attrib.pop(th2ex.sodipodi_nodetypes, "")
    th2ex.set_props(node, "line", "rock-border")

    if dropstyle:
        node.attrib.pop("style", "")
        node.attrib["class"] = "line rock-border"


class MakeRocks(Th2Effect):

    def effect(self) -> None:
        dropstyle = self.getElementById("th2style") is not None

        for eid, node in self.selected.items():
            make_rock(node, dropstyle)


if __name__ == '__main__':
    e = MakeRocks()
    e.run()
