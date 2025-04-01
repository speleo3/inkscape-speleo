#!/usr/bin/env python
'''
Copyright (C) 2025 Thomas Holder
Distributed under the terms of the GNU General Public License v2 or later
'''

from typing import Dict, List, Tuple

import th2ex
from th2ex import (
    EtreeElement,
    Th2Effect,
    get_props,
    parse_options,
    set_props,
    th2pref_load_from_xml,
    inkscape_original_d,
    WILDCARD,
)

from inkex0 import cubicsuperpath
from inkex0.cubicsuperpath import SuperPath
import inkex


def split_csp(csp: SuperPath, spidx: int,
              ptidx: int) -> Tuple[SuperPath, SuperPath]:
    csp_pre = csp[:spidx + 1]
    csp_post = csp[spidx:]
    csp_pre[-1] = csp_pre[-1][:ptidx + 1]
    csp_post[0] = csp_post[0][ptidx:]
    return csp_pre, csp_post


class Th2SetLinePoint(Th2Effect):

    def __init__(self):
        super().__init__()
        self.arg_parser.add_argument("--options", default="-altitude .")

    def effect(self) -> None:
        if len(self.selected) == 0:
            inkex.errormsg('warning: nothing selected')
            return

        # th2ex prefs
        th2pref_load_from_xml(self.document.getroot())

        new_options = parse_options(self.options.options)

        selegrouped: Dict[str, List[Tuple[int, int]]] = {}

        # iterate over elements in selection order
        for sn in self.options.selected_nodes:
            eid, spidx, ptidx = sn.split(":")
            selegrouped.setdefault(eid, []).append((int(spidx), int(ptidx)))

        for eid in selegrouped:
            node = self.selected[eid]
            parent: EtreeElement = node.getparent()
            pos: int = parent.index(node)

            role_parent, _, _ = get_props(parent)
            _, type, options = get_props(node)

            if role_parent != "line":
                pathgroup: EtreeElement = parent.makeelement(th2ex.svg_g)
                parent.insert(pos, pathgroup)
                pathgroup.append(node)
                set_props(pathgroup, "line", type, options)
                set_props(node, WILDCARD, WILDCARD, {})
                parent = pathgroup
                pos = 0

            for d_attrib in [inkscape_original_d, "d"]:
                d = node.get(d_attrib)
                if d:
                    break
            else:
                inkex.errormsg(f"Unsupported shape: {node.tag}")
                continue

            csp = cubicsuperpath.parsePath(d)
            node.attrib.pop(th2ex.sodipodi_nodetypes, None)

            for spidx, ptidx in sorted(selegrouped[eid], reverse=True):
                csp, csp_post = split_csp(csp, spidx, ptidx)
                attrib = dict(node.attrib)
                attrib.pop("id", None)
                attrib[d_attrib] = cubicsuperpath.formatPath(csp_post)
                node_post: EtreeElement = parent.makeelement(
                    node.tag, attrib, inkex.NSS)
                parent.insert(pos, node_post)
                set_props(node_post, WILDCARD, WILDCARD, new_options)
                pos += 1
                # TODO track subtype and (1) update class, (2) update LPE

            node.attrib[d_attrib] = cubicsuperpath.formatPath(csp)


if __name__ == '__main__':
    e = Th2SetLinePoint()
    e.run()
