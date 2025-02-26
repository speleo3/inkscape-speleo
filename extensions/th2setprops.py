#!/usr/bin/env python
'''
Copyright (C) 2008 Thomas Holder, http://sf.net/users/speleo3/
Distributed under the terms of the GNU General Public License v2 or later

Annotate SVG elements for therion export.
'''

from th2ex import (
    Th2Effect,
    get_props,
    get_template_svg_path,
    inkscape_original_d,
    inkscape_path_effect,
    parse_options,
    set_props,
    svg_path,
    svg_use,
    th2pref_load_from_xml,
    xlink_href,
)

import inkex
import sys
from lxml import etree


def asunicode(s):
    if isinstance(s, bytes):
        return s.decode('utf-8')
    return s


class Th2SetProps(Th2Effect):
    def __init__(self):
        super().__init__()
        self.arg_parser.add_argument("--role", type=str, dest="role", default="")
        self.arg_parser.add_argument("--type", type=str, dest="type", default="")
        self.arg_parser.add_argument("--options", type=str, dest="options", default="")
        self.arg_parser.add_argument("--merge", type=inkex.Boolean, dest="merge", default=True)
        self.arg_parser.add_argument("--dropstyle", type=inkex.Boolean, dest="dropstyle", default=False)

    def update_options(self, options):
        '''Subclasses can update options here'''
        pass

    def getdocids(self):
        self.doc_ids = self.document.xpath("//*/@id", smart_strings=False)

    def effect(self):
        if len(self.selected) == 0:
            inkex.errormsg('warning: nothing selected')
            sys.exit(1)

        # th2ex prefs
        th2pref_load_from_xml(self.document.getroot())

        new_options = parse_options(asunicode(self.options.options))

        self.getdocids()

        if self.options.dropstyle and 'th2style' not in self.doc_ids:
            with open(get_template_svg_path(), encoding="utf-8") as template:
                doc_temp = etree.parse(template)
            defs_temp = doc_temp.find(inkex.addNS('defs', 'svg'))
            defs_self = self.document.find(inkex.addNS('defs', 'svg'))
            if defs_self is None:
                doc_temp.getroot().remove(defs_temp)
                self.document.getroot().insert(0, defs_temp)
            else:
                children = defs_temp.getchildren()
                defs_temp.clear()
                defs_self.extend(children)
            self.getdocids()

        # iterate over elements in selection order
        for id in self.options.ids:
            node = self.selected[id]

            # current props
            role, type, options = get_props(node)

            # new props
            if not self.options.merge:
                options = dict()
            options.update(new_options)

            if len(self.options.role) > 0 and self.options.role != '_none_':
                role = self.options.role

            if len(self.options.type) > 0:
                type = self.options.type
                if self.options.type == 'section' and 'direction' not in options:
                    options['direction'] = 'begin'

            # fallback default props
            if role == '':
                inkex.errormsg('warning: empty role')
                role = 'line'
            if type == '':
                inkex.errormsg('warning: empty type')
                type = 'wall'

            self.update_options(options)

            type_ = type

            if ':' in type:
                type, subtype = type.split(':', 1)
            else:
                subtype = options.get('subtype', '')

            # update symbols
            if role == 'point':
                for href in [role + '-' + type + '_' + subtype, role + '-' + type]:
                    if href in self.doc_ids:
                        break
                else:
                    href = None

                # convert arbitrary shape to clone (only with dropstyle=True)
                if href and node.tag != svg_use and self.options.dropstyle:
                    bbox = self.compute_bbox(node, False)
                    if bbox is not None:
                        parent = node.getparent()
                        parent.remove(node)
                        node = etree.SubElement(parent, svg_use, {
                            "x": str((bbox[0] + bbox[1]) / 2.0),
                            "y": str((bbox[2] + bbox[3]) / 2.0),
                            "id": id,
                        })
                        self.selected[id] = node

                if href and node.tag == svg_use:
                    node.set(xlink_href, '#' + href)

            # update path effects
            elif node.tag == svg_path and role in ['line', 'area', '']:
                node.set('class', '%s %s %s' % (role or 'line', type, subtype))
                if self.options.dropstyle:
                    node.set('style', '')
                for href in ['LPE-' + type + '_' + subtype, 'LPE-' + type]:
                    if role == 'line' and href in self.doc_ids:
                        node.set(inkscape_path_effect, '#' + href)
                        if inkscape_original_d not in node.attrib:
                            node.set(inkscape_original_d, node.get('d'))
                        node.attrib.pop('d', None)
                        break
                else:
                    if self.options.dropstyle and \
                            inkscape_path_effect in node.attrib:
                        del node.attrib[inkscape_path_effect]
                        if inkscape_original_d in node.attrib:
                            node.set('d', node.get(inkscape_original_d))
                            del node.attrib[inkscape_original_d]

            set_props(node, role, type_, options)


if __name__ == '__main__':
    e = Th2SetProps()
    e.run()
