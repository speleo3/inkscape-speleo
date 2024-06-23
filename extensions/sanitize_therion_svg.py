#!/usr/bin/env python3
# Copyright (C) 2024 Thomas Holder
"""
Given an SVG or PDF (imported into Inkscape) produced by Therion, do some
"cleanup" which makes it friendlier to edit.
"""

import re
from math import log10
from pathlib import Path
from typing import Sequence
import inkex

Vec2D = tuple[float, float] | Sequence[float]
CubicNode = tuple[Vec2D, Vec2D, Vec2D] | Sequence[Vec2D]


class NotLinear(Exception):
    pass


def id_to_clip_path_value(id: str) -> str:
    """
    Format the given ID as a valid clip-path value.
    """
    return f"url(#{id})"


def round_sig(v: float, dig_sig=12, dig_min=0) -> float:
    """
    Round the given number to the given number of significant digits.
    """
    assert dig_min >= 0
    try:
        return round(v, max(dig_min, dig_sig - round(log10(abs(v)))))
    except ValueError:
        return 0.0


def is_colinear_on_axis(axis: int, node1: CubicNode, node2: CubicNode) -> bool:
    """
    True if the two given CubicSuperPath nodes form a linear line segment and
    are parallel to the given axis.
    """
    assert axis in (0, 1)
    other_axis = 1 - axis
    return all(node1[1][other_axis] == v for v in [
        node1[2][other_axis],
        node2[0][other_axis],
        node2[1][other_axis],
    ])


def rel_aavec(node1: CubicNode, node2: CubicNode) -> Vec2D:
    """
    Return the axis aligned vector from node1 to node2.

    Raises:
      NotLinear: if the two nodes don't form an axis aligned line segment
    """
    if is_colinear_on_axis(0, node1, node2):
        return (round_sig(node2[1][0] - node1[1][0]), 0)
    if is_colinear_on_axis(1, node1, node2):
        return (0, round_sig(node2[1][1] - node1[1][1]))
    raise NotLinear


def rev_vec(node: Vec2D) -> Vec2D:
    """
    Reverse a vector
    """
    return -node[0], -node[1]


def clipPath_is_aligned_rect(elem: inkex.ClipPath) -> bool:
    """
    True if the given clipPath is an axis aligned rectangle
    """
    if len(elem) != 1:
        return False
    child = elem[0]
    if not isinstance(child, inkex.ShapeElement):
        return False
    sp = child.path.to_superpath()
    if len(sp) != 1 or len(sp[0]) != 5:
        return False
    ss = sp[0]
    try:
        return (rel_aavec(ss[0], ss[1]) == rev_vec(rel_aavec(ss[2], ss[3])) and  #
                rel_aavec(ss[1], ss[2]) == rev_vec(rel_aavec(ss[3], ss[4])))
    except NotLinear:
        return False


class SanitizeTherionSvgExtension(inkex.EffectExtension):

    svg: inkex.SvgDocumentElement

    def effect(self):
        self._original_doc_content = self.svg.tostring().decode("utf-8", "replace")

        self._remove_unused_groups_from_defs()
        self._remove_clip_viewBox()
        self._unlink_exclusive_clones()
        self._consolidate_clipPaths()
        self._ungroup_trivial_groups()

    def _ungroup_trivial_groups(self):
        for elem in self.svg.findall('.//svg:g'):
            if list(elem.attrib) not in ([], ["id"]):
                continue
            if len(elem) != 1:
                continue
            child = elem[0]
            if not isinstance(child, inkex.Group):
                continue
            parent = elem.getparent()
            if parent is None:
                continue
            elem_id = elem.get("id")
            if elem_id and self.id_is_referenced(elem_id):
                continue
            parent.insert(parent.index(elem), child)
            parent.remove(elem)

    def _consolidate_clipPaths(self):
        elem_hash = {}
        remap = {}
        for elem in self.svg.findall('svg:defs/svg:clipPath'):
            hashed = elem_hash.setdefault(
                re.sub(r' id="\w*"', "",
                       elem.tostring().decode("utf-8")), [elem, "none"])
            if hashed[0] is elem and not clipPath_is_aligned_rect(elem):
                hashed[1] = id_to_clip_path_value(elem.get("id"))
            else:
                remap[id_to_clip_path_value(elem.get("id"))] = hashed[1]
                elem.getparent().remove(elem)
        for shape in self.svg.findall('.//*[@clip-path]'):
            remapped = remap.get(shape.get("clip-path"))
            if remapped == "none":
                shape.set("clip-path", None)
            elif remapped is not None:
                shape.set("clip-path", remapped)

    def id_is_referenced(self, elem_id: str) -> bool:
        assert elem_id
        if self._original_doc_content:
            fast_path_count = self._original_doc_content.count(elem_id)
            if fast_path_count == 1:
                return False
            assert fast_path_count != 0
        return bool(
            self.svg.getElementsByHref(elem_id) or  #
            self.svg.getElementsByStyleUrl(elem_id))

    def _remove_unused_groups_from_defs(self):
        for elem in self.svg.findall('svg:defs/svg:g'):
            elem_id = elem.get("id")
            if elem_id:
                if self.id_is_referenced(elem_id):
                    continue
            elem.delete()

    def _remove_clip_viewBox(self):
        clipViewBox = self.svg.getElementById("clip_viewBox", literal=True)
        if clipViewBox is not None:
            clipViewBox.delete()

        for shape in self.svg.findall('.//*[@clip-path="url(#clip_viewBox)"]'):
            shape.set("clip-path", None)

    def _unlink_exclusive_clones(self):
        for use in self.svg.findall(".//svg:use"):
            self._unlink_if_exclusive_clone(use)

    def _unlink_if_exclusive_clone(self, use: inkex.BaseElement):
        href = use.get("xlink:href")
        if not href.startswith("#"):
            inkex.errormsg(f"Unhandled href: {href!r}")
            return

        used_by = self.svg.findall(f'.//*[@xlink:href="{href}"]')
        if len(used_by) != 1:
            inkex.errormsg(f"Used by {len(used_by)} clones: {href!r}")
            return

        assert used_by[0] is use

        linked = self.svg.getElementById(href.removeprefix("#"), literal=True)
        if linked is None:
            inkex.errormsg(f"Element {href!r} not found")
            return

        # add transform
        x = use.get("x", 0)
        y = use.get("y", 0)
        linked.set("transform", f"translate({x} {y}) " + (linked.get("transform") or ""))

        # move after use
        parent = use.getparent()
        assert parent is not None
        pos = list(parent).index(use)
        parent.insert(pos, linked)
        parent.remove(use)


if __name__ == '__main__':
    SanitizeTherionSvgExtension().run()
