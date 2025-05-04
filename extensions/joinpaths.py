#!/usr/bin/env python
'''
Join termini of all selected paths, yields a single non-closed path.

Copyright (C) 2025 Thomas Holder
'''

import th2ex
from th2ex import (
    EtreeElement,
    Th2Effect,
)

from dataclasses import dataclass
from typing import List, Tuple
from inkex0 import cubicsuperpath
from inkex0.cubicsuperpath import SuperPath, HandledPoint
from inkex import errormsg  # type: ignore[reportPrivateImportUsage]
from math import sqrt


def distance(h1: HandledPoint, h2: HandledPoint) -> float:
    (x1, y1) = h1[1]
    (x2, y2) = h2[1]
    return sqrt((x2 - x1)**2 + (y2 - y1)**2)


def make_center(h1: HandledPoint, h2: HandledPoint) -> HandledPoint:
    (x1, y1) = h1[1]
    (x2, y2) = h2[1]
    center = [(x1 + x2) / 2, (y1 + y2) / 2]
    return [center, center, center]


def reverse_csp(csp: SuperPath) -> SuperPath:
    return [[list(reversed(handled)) for handled in reversed(sub)]
            for sub in reversed(csp)]


@dataclass
class TerminalPoint:
    csp: "SuperPath | None"
    is_end: bool
    partner: "TerminalPoint | None" = None

    @property
    def handled(self):
        assert self.csp is not None
        return self.csp[-1][-1] if self.is_end else self.csp[0][0]

    def reverse_in_place(self):
        assert self.csp is not None
        self.csp[:] = reverse_csp(self.csp)
        self.is_end = not self.is_end
        assert self.partner is not None
        self.partner.is_end = not self.partner.is_end

    def distance(self, other: "TerminalPoint") -> float:
        return distance(self.handled, other.handled)


def make_partners(t1: TerminalPoint, t2: TerminalPoint):
    t1.partner = t2
    t2.partner = t1


def extend_csp(csp1: SuperPath, csp2: SuperPath):
    """
    Extend csp1 by csp2 and drop overlapping nodes in the fuse region.
    """
    sub1 = csp1[-1]
    sub2 = csp2[0]

    center = make_center(sub1[-1], sub2[0])
    radius = distance(sub1[-1], sub2[0]) * 0.6

    for i in range(len(sub1) - 1, -1, -1):
        if distance(center, sub1[i]) > radius:
            sub1[i + 1:] = []
            break

    for i in range(len(sub2)):
        if distance(center, sub2[i]) > radius:
            sub2[:i] = []
            break

    sub1.append(center)
    sub1.extend(sub2)
    csp1.extend(csp2[1:])


def join_csps(csps: List[SuperPath]) -> SuperPath:
    """
    Join all given paths by connecting the closest endpoints and dropping
    overlapping nodes in the fuse regions.
    """
    terminals: List[TerminalPoint] = []

    for csp in csps:
        terminals.append(TerminalPoint(csp, False))
        terminals.append(TerminalPoint(csp, True))
        make_partners(terminals[-1], terminals[-2])

    dists: List[Tuple[float, TerminalPoint, TerminalPoint]] = []

    for ti in terminals:
        for tj in terminals:
            dists.append((ti.distance(tj), ti, tj))

    for dist in sorted(dists, key=lambda dist: dist[0]):
        ti = dist[1]
        tj = dist[2]
        if ti.csp is tj.csp or ti.csp is None or tj.csp is None:
            continue
        if tj.is_end == ti.is_end:
            tj.reverse_in_place()
        if tj.is_end:
            ti, tj = tj, ti
        assert ti.csp is not None
        assert tj.csp is not None
        extend_csp(ti.csp, tj.csp)
        assert tj.partner is not None
        assert ti.partner is not None
        assert ti.partner.csp is ti.csp
        tj.partner.csp = ti.csp
        make_partners(tj.partner, ti.partner)
        ti.csp = None
        tj.csp = None

    for ti in terminals:
        csp = ti.csp
        if csp is not None:
            return csp

    raise AssertionError("unreachable")


class JoinPaths(Th2Effect):

    def effect(self) -> None:
        nodes: List[EtreeElement] = []
        csps: List[SuperPath] = []

        for eid, node in self.selected.items():
            d = node.get("d")
            if not d:
                errormsg(f'warning: no d for id={eid}')
                continue

            csp = cubicsuperpath.parsePath(d)
            csps.append(csp)
            nodes.append(node)

        if not nodes:
            errormsg('warning: nothing selected')
            return

        for node in nodes[1:]:
            node.getparent().remove(node)

        csp = join_csps(csps)

        nodes[0].attrib.pop(th2ex.sodipodi_nodetypes, None)
        nodes[0].attrib["d"] = cubicsuperpath.formatPath(csp)


if __name__ == '__main__':
    e = JoinPaths()
    e.run()
