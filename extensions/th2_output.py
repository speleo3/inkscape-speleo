#!/usr/bin/env python
'''
Copyright (C) 2008 Thomas Holder, http://sf.net/users/speleo3/
Distributed under the terms of the GNU General Public License v2 or later

This program was inspired by http://www.cavediving.de/svg2th2.py
'''

import th2ex
from th2ex import (
    AffineType,
    EtreeElement,
    OptionsDict,
    as_unicode,
    th2pref,
    th2pref_load_from_xml,
    svg_polygon,
    svg_text,
    svg_textPath,
    svg_tspan,
    svg_g,
    therion_role,
    therion_options,
    xlink_href,
    inkscape_groupmode,
    inkscape_label,
    inkscape_original_d,
    sodipodi_role,
    sodipodi_nodetypes,
    name_survex2therion,
    parse_options,
    format_options,
    get_props,
    align2anchor_default_out,
    align2baseline_default_out,
    text_keys_output,
    descrim,
    parsePath,
    convert_unit,
    Th2Effect,
)

from typing import (
    Dict,
    Iterator,
    List,
    Sequence,
    Tuple,
)
from lxml import etree
import inkex
import simpletransform
import simplestyle
import math
import re
import collections
import os

print_utf8 = print


def parse_options_node(node: EtreeElement):
    options = node.get(therion_options, '')
    return parse_options(options)


def transformParams(mat: AffineType, params: Sequence[float]):
    new: List[float] = []
    for i in range(0, len(params), 2):
        if i + 1 == len(params):
            inkex.errormsg('params index skewd!!!')
            inkex.errormsg(str(params))
            break
        new.append(mat[0][0] * params[i] + mat[0][1] * params[i + 1] + mat[0][2])
        new.append(mat[1][0] * params[i] + mat[1][1] * params[i + 1] + mat[1][2])
    return new


def orientation(mat: AffineType) -> float:
    '''Orientation of a (0.0, 1.0) vector after rotation with "mat"'''
    try:
        deg = -math.degrees(math.atan2(mat[0][1], -mat[1][1]))
    except Exception:
        return 0.0
    deg = deg % 360
    deg = round(deg, 3)
    return deg


def fstr(x: float) -> str:
    """
    Format float with 4 digits after the period
    """
    s = "%.4f" % x
    return fstr_trim_zeros(s)


def fstr2(x: float, dbl_dig=15, max_dig=20) -> str:
    """
    Format float with a maximum of max_dig digits after the period, and taking
    the number of significant digits (dbl_dig) into account.
    """
    try:
        digits = dbl_dig - math.ceil(math.log10(abs(x)))
    except ValueError:
        digits = 0
    digits = max(1, min(digits, max_dig))
    s = f"{x:.{digits}f}"
    return fstr_trim_zeros(s)


def fstr_trim_zeros(s: str) -> str:
    """
    Strip trailing zeros from a string that represents a floating point number.
    """
    assert '.' in s
    i = len(s) - 1
    while s[i] == '0':
        i -= 1
    if s[i] == '.':
        i += 1
    s = s[:i + 1]
    return "0.0" if s == "-0.0" else s


def optquote(x: str) -> str:
    """
    Add quotes around `x` if necessary, e.g. if it contains spaces.
    """
    if re.search(r"\s", x) is None:
        return x
    return f'"{x}"'


def format_options_leading_space(options):
    """
    Like format_options() but with a leading space if non-empty.
    """
    formatted = format_options(options)
    if formatted:
        return " " + formatted
    return ""


class Th2Line:
    def __init__(self, type: str = 'wall'):
        self.type = type
        self.options: OptionsDict = {}
        self.points: List[str] = []
        self._last: Sequence[str] = []

    @staticmethod
    def _format_params(params: Sequence[float]) -> List[str]:
        return [fstr(i) for i in params]

    def append(self, params):
        self._last = self._format_params(params)
        self.points.append(" ".join(self._last))

    def append_point_options(self, point_options: OptionsDict):
        # point options follow points, so there must be at least one
        assert self.points
        self.points.extend(th2ex.format_options_iter(point_options, prefix=""))

    def ends_with_point(self, params: Sequence[float]) -> bool:
        assert len(params) == 2
        return self._last[-2:] == self._format_params(params)

    def close(self):
        self.options['close'] = 'on'
        if self.points and self.points[0].split() != self._last[-2:]:
            self._last = self.points[0].split()
            self.points.append(self.points[0])

    def output(self):
        formatted_options = format_options_leading_space(self.options)
        print_utf8(f"line {self.type}{formatted_options}")
        print("  " + "\n  ".join(self.points))
        print("endline\n")


class Th2Area:
    count: Dict[str, int] = collections.defaultdict(int)

    def __init__(self, type):
        self.type = type
        self.options = {}
        self._lines = []

    def current_line(self):
        return self._lines[-1]

    def append_line(self):
        self._lines.append(Th2Line('border'))

    def output(self, prefix):
        ids = []

        # if only one line, assume it must be closed
        if len(self._lines) == 1:
            self._lines[0].close()

        for line in self._lines:
            if not line.options.get('id'):
                id_prefix = "%s_%s_" % (prefix, self.type.replace(':', '_'))
                Th2Area.count[id_prefix] += 1
                line.options['id'] = id_prefix + str(Th2Area.count[id_prefix])
            ids.append(line.options['id'])
            line.output()

        # output area
        formatted_options = format_options_leading_space(self.options)
        print_utf8(f"area {self.type}{formatted_options}")
        for lineid in ids:
            print_utf8("  " + lineid)
        print("endarea\n")


class Th2Output(Th2Effect):
    doc_x = 0
    doc_y = 0
    doc_width = 0  # viewBox width
    doc_height = 0  # viewBox height
    doc_width_m = 0  # width in meters
    doc_height_m = 0  # height in meters

    def __init__(self):
        inkex.Effect.__init__(self)
        self.OptionParser.add_option("--scale", type="int", dest="scale", default=100)
        self.OptionParser.add_option("--dpi", type="int", dest="dpi", default=0)
        self.OptionParser.add_option("--layers", type="string", dest="layers", default="all")
        self.OptionParser.add_option("--images", type="inkbool", dest="images", default=True)
        self.OptionParser.add_option("--nolpe", type="inkbool", dest="nolpe", default=True)
        self.OptionParser.add_option("--lay2scr", type="inkbool", dest="lay2scr", default=True)
        self.OptionParser.add_option("--xyascenter", type="inkbool", dest="xyascenter", default=True)
        self.OptionParser.add_option("--projection", type="string", dest="projection", default="")
        self.OptionParser.add_option("--author", type="string", dest="author", default="")
        self.OptionParser.add_option("--options", type="string", dest="options", default="")
        if th2pref.textonpath:
            self.textpath_dict = dict()
        self.current_scrap_id = 'none'

    def get_m_per_dots(self) -> float:
        """
        Get drawing meters per user unit
        """
        m_per_dots_width = self.doc_width_m / self.doc_width
        m_per_dots_height = self.doc_height_m / self.doc_height
        assert 0.9 < (m_per_dots_width / m_per_dots_height) < 1.1
        return (m_per_dots_width + m_per_dots_height) / 2

    def get_style(self, node):
        return simplestyle.parseStyle(node.get('style', ''))

    def get_style_attr(self, node, style, key, d=''):
        d = node.get(key, d)
        return style.get(key, d)

    def print_scrap_begin(self, id: str, test: bool, options=None):
        options = dict(options or {})

        self.current_scrap_id = id

        if test:
            if 'scale' not in options and self.options.scale > 0:
                if self.options.dpi:
                    inkex.errormsg("--dpi is deprecated, use viewBox and width in cm")
                    options['scale'] = '[%d %d inch]' % (
                        self.options.dpi,
                        self.options.scale,
                    )
                elif self.doc_width_m:
                    options['scale'] = '[%g %g m]' % (
                        self.doc_width / self.doc_width_m,
                        self.options.scale,
                    )
            if 'projection' not in options and self.options.projection:
                options['projection'] = self.options.projection
            if 'author' not in options and self.options.author:
                options['author'] = as_unicode(self.options.author)
            options.update(parse_options(as_unicode(self.options.options)))
            print_utf8('\nscrap %s %s\n' % (id, format_options(options)))

    def print_scrap_end(self, test):
        if test:
            print("endscrap\n\n")

    def setdefault_doc_dims(self):
        """
        If document dimensions (width, height) are unknown, set them to default values.
        """
        if self.doc_width_m and self.doc_width:
            m_per_dots = self.doc_width_m / self.doc_width
        elif self.doc_height_m and self.doc_height:
            m_per_dots = self.doc_height_m / self.doc_height
        else:
            m_per_dots = 0.0254 / 96  # SVG default
        if not self.doc_width_m:
            self.doc_width_m = (self.doc_width or 300) * m_per_dots
        if not self.doc_width:
            self.doc_width = self.doc_width_m / m_per_dots
        if not self.doc_height_m:
            self.doc_height_m = (self.doc_height or 150) * m_per_dots
        if not self.doc_height:
            self.doc_height = self.doc_height_m / m_per_dots
        if not (0.9 < (m_per_dots / self.get_m_per_dots()) < 1.1):
            inkex.errormsg(
                f"doc_width:  {self.doc_width}     doc_width_m:  {self.doc_width_m}\n"
                f"doc_height: {self.doc_height}    doc_height_m: {self.doc_height_m}\n"
                f"m_per_dots: {self.get_m_per_dots()}\n")

    def output(self):
        root = self.document.getroot()
        self.doc_width_m = convert_unit(root.get('width') or '', "m")
        self.doc_height_m = convert_unit(root.get('height') or '', "m")

        # load prefs from file
        th2pref_load_from_xml(root)
        th2pref.xyascenter = self.options.xyascenter

        viewBox = root.get('viewBox')
        if viewBox:
            self.doc_x, self.doc_y, self.doc_width, self.doc_height = map(float, viewBox.split())

        self.setdefault_doc_dims()

        self.classes = {}
        stylenodes = self.document.xpath('//svg:style', namespaces=inkex.NSS)
        pattern = re.compile(r'\.(\w+)\s*\{(.*?)\}')
        for stylenode in stylenodes:
            if isinstance(stylenode.text, str):
                for x in pattern.finditer(stylenode.text):
                    self.classes[x.group(1)] = simplestyle.parseStyle(x.group(2).strip())

        print('encoding  utf-8')
        if self.doc_width and self.doc_height:
            params = [
                self.doc_x,
                self.doc_y + self.doc_height,
                self.doc_x + self.doc_width,
                self.doc_y,
            ]
            print('##XTHERION## xth_me_area_adjust %s %s %s %s' %
                  tuple(map(fstr2, transformParams(self.r2d, params))))
        print('##XTHERION## xth_me_area_zoom_to 100')

        # text on path
        if th2pref.textonpath:
            textpaths = self.document.xpath('//svg:textPath', namespaces=inkex.NSS)
            for node in textpaths:
                href = node.get(xlink_href).split('#', 1)[-1]
                options = {'text': self.get_point_text(node)}
                self.guess_text_scale(node, self.get_style(node.getparent()), options, self.i2d_affine(node))
                self.textpath_dict[href] = options

        if self.options.images:
            images = self.document.xpath('//svg:image', namespaces=inkex.NSS) + \
                self.document.xpath('//svg:g[@therion:type="xth_me_image_insert"]', namespaces=inkex.NSS)
            # for node in reversed(images):
            for node in images:
                params = [self.unittouu(node.get('x', '0')), self.unittouu(node.get('y', '0'))]
                mat = self.i2d_affine(node)
                href = node.get(xlink_href, '')
                XVIroot = '{}'
                if href == '':  # xvi image (svg:g)
                    options = parse_options(node.get(therion_options, ''))
                    href = options.get('href', '')
                    XVIroot = options.get('XVIroot', '{}')
                elif href.startswith('data:'):
                    inkex.errormsg('Embedded images not supported!')
                    continue
                paramsTrans = transformParams(mat, params)
                mat = simpletransform.composeTransform(mat, [[1, 0, params[0]], [0, 1, params[1]]])
                w = node.get('width', '100%')
                h = node.get('height', '100%')
                if th2pref.image_inkscape:
                    print('##INKSCAPE## image %s %s %s %s' % (w, h, simpletransform.formatTransform(mat), href))
                    continue
                if href.startswith('file://'):
                    href = href[7:]
                document_path = os.getenv("DOCUMENT_PATH")
                if document_path:
                    href = os.path.relpath(href, os.path.dirname(document_path))
                print('##XTHERION## xth_me_image_insert {%s 1 1.0} {%s %s} %s 0 {}' %
                      (fstr2(paramsTrans[0]), fstr2(paramsTrans[1]), XVIroot, optquote(href)))

        print('\n')

        self.print_scrap_begin('scrap1', not self.options.lay2scr)

        if self.options.layers == 'current':
            layer = self.current_layer
            while layer.get(inkscape_groupmode, '') != "layer" and layer.getparent():
                layer = layer.getparent()
            self.output_scrap(layer)
        else:
            layers = self.document.xpath('/svg:svg/svg:g[@inkscape:groupmode="layer"]', namespaces=inkex.NSS)
            if len(layers) == 0:
                inkex.errormsg("Document has no layers!\nFallback to single scrap")
                layers = [root]
            for layer in layers:
                if layer.get(therion_role) == 'none':
                    continue
                if layer.get(therion_role) == 'input':
                    self.output_input(layer)
                    continue
                if self.options.layers == 'visible':
                    style = self.get_style(layer)
                    if style.get('display') == 'none':
                        continue
                self.output_scrap(layer)

        self.print_scrap_end(not self.options.lay2scr)

    def output_g(self, node):
        for child in reversed(node):
            if isinstance(child, etree._Comment):
                if child.text.startswith('#therion'):
                    print_utf8(child.text.split('\n', 1)[1])
                continue

            role, type, options = get_props(child)

            if role == 'none':
                continue

            if self.options.layers == 'visible':
                style = self.get_style(child)
                if style.get('display') == 'none':
                    continue

            if role == 'textblock':
                self.output_textblock(child)
            elif role == 'point':
                self.output_point(child)
            elif role == 'line':
                self.output_line(child)
            elif role == 'area':
                self.output_area(child)
            elif child.tag == svg_g:
                self.output_g(child)

    def output_scrap(self, layer):
        id = layer.get(inkscape_label)
        if not id:
            id = layer.get('id')
        if not id:
            id = 'scrapX'
        id = id.replace(' ', '_')
        options = parse_options_node(layer)
        self.print_scrap_begin(id, self.options.lay2scr, options)
        self.output_g(layer)
        self.print_scrap_end(self.options.lay2scr)

    def get_d(self, node: EtreeElement, *, recursive: bool = True):
        d = node.get(inkscape_original_d)
        if not d or not self.options.nolpe:
            d = node.get('d')
        if not d:
            if node.tag == svg_g:
                if not recursive:
                    return ''
                # TODO: i2d_affine of children
                d = ' M 0,0 '.join(self.get_d(child) for child in reversed(node))
            elif 'points' in node.attrib:
                d = 'M' + node.get('points')
                if node.tag == svg_polygon:
                    d += ' z'
            elif 'x1' in node.attrib:
                d = 'M' + node.get('x1') + ',' + node.get('y1') + 'L' + node.get('x2') + ',' + node.get('y2')
            elif 'width' in node.attrib and 'height' in node.attrib:
                width = node.get('width')
                height = node.get('height')
                d = 'M{0},{1}h{2}v{3}h-{2}v-{3}z'.format(node.get('x', '0'), node.get('y', '0'), width, height)
        return d or ''

    def get_line_data(
        self,
        node: EtreeElement,
        *,
        inner=False,
    ) -> Iterator[Tuple[str, Sequence[float], OptionsDict]]:
        """
        Get line data and line options.


        """
        if node.tag == svg_g:
            for child in reversed(node):
                yield from self.get_line_data(child, inner=True)
            return

        d = self.get_d(node, recursive=False)
        if not d:
            return

        point_options = get_props(node)[2] if inner else {}
        mat = self.i2d_affine(node)
        p = [(cmd, transformParams(mat, params)) for (cmd, params) in parsePath(d)]
        nodetypes = node.get(sodipodi_nodetypes, "") + "?" * len(p)

        for ((cmd, params), nodetype) in zip(p, nodetypes):
            if len(params) == 6 and nodetype == "c":
                point_options["smooth"] = "off"
            yield (cmd, params, point_options)
            point_options = {}


    def output_line(self, node):
        # get therion attributes
        role, type, options = get_props(node)

        # text on path
        if th2pref.textonpath:
            node_id = node.get('id')
            if node_id in self.textpath_dict:
                type = 'label'
                options.update(self.textpath_dict[node_id])

        th2line = None
        for (cmd, params, point_options) in self.get_line_data(node):
            join_lines = False
            if cmd == 'M':
                if th2line is not None:
                    if th2line.ends_with_point(params):
                        join_lines = True
                    else:
                        th2line.output()
                if not join_lines:
                    th2line = Th2Line(type)
                    th2line.options.update(options)
            if cmd == 'Z':
                th2line.close()
            elif not join_lines:
                th2line.append(params)
            th2line.append_point_options(point_options)
        if th2line is not None:
            th2line.output()
        else:
            inkex.errormsg('no path data for element <{} id="{}">'.format(
                node, node.get('id')))

    def output_textblock(self, node):
        line = self.get_point_text(node)
        a = line.split()
        if a:
            print_utf8(line)
        desc = node.xpath('svg:desc', namespaces=inkex.NSS)
        if len(desc) > 0:
            print_utf8(desc[0].text.rstrip())
        if a:
            print('end' + a[0] + '\n')

    def get_point_text(self, node):
        text = ''
        if isinstance(node.text, str) and len(node.text.strip()) > 0:
            text = node.text.replace('\n', ' ')
        for child in node:
            if child.tag == svg_tspan or \
                    not th2pref.textonpath and child.tag == svg_textPath:
                if len(text) > 0 and child.get(sodipodi_role, '') == 'line':
                    text += '<br>'
                text += self.get_point_text(child)
            if isinstance(child.tail, str) and len(child.tail.strip()) > 0:
                text += child.tail.replace('\n', ' ')
        # strip newlines between language alternatives
        text = text.replace("<br><lang:", "<lang:")
        return text

    align_rl = {
        'start': 'r',
        # 'middle': '',  # 'c'
        'end': 'l',
    }

    align_tb = {
        'auto': 't',
        'alphabetic': 't',
        'ideographic': 't',
        # 'middle': '',
        # 'central': '',
        'hanging': 'b',
    }

    def guess_text_align(self, node, style, options):
        textanchor = self.get_style_attr(node, style, 'text-anchor', align2anchor_default_out)
        baseline = self.get_style_attr(node, style, 'dominant-baseline', align2baseline_default_out)
        align = self.align_tb.get(baseline, options.get('align', ''))
        align = align[0] if align[:1] in ['t', 'b'] else ''
        align += self.align_rl.get(textanchor, '')
        if align:
            options['align'] = align
        else:
            options.pop('align', None)

    def guess_text_scale(self, node, style, options, mat):
        """
        Guess closest text scale (e.g. "xl") from actual font size and set it in
        options if it's not the default scale.
        """
        fontsize = self.get_style_attr(node, style, 'font-size', '12')
        if fontsize[-1] == '%':
            fontsize = float(fontsize[:-1]) / 100.0 * 12
        else:
            fontsize = self.unittouu(fontsize)
        if mat is not None:
            fontsize *= descrim(mat)
        fontsize /= th2pref.basescale
        fontsize_pt = th2ex.convert_unit((fontsize * self.get_m_per_dots(), "m"), "pt")
        fonts_setup_default = th2ex.get_fonts_setup_default()
        scale = min(fonts_setup_default.items(),
                    key=lambda item: abs(item[1] - fontsize_pt))[0]
        if scale != 'm':
            options['scale'] = scale

    def output_point(self, node):
        mat = self.i2d_affine(node)

        # get x/y
        params = self.node_center(node)
        params = transformParams(mat, params)

        # get therion attributes
        role, type, options = get_props(node)

        if node.tag == svg_text:
            # restore text for labels etc.
            key = text_keys_output.get(type, 'text')
            text = self.get_point_text(node).strip()

            if type == "station" and "." in text and "@" not in text:
                text = name_survex2therion(text)

            options[key] = text
            if options[key] == "":
                # inkex.errormsg("dropping empty text element (point %s)" % (type))
                return

            if type not in ['station', 'dimensions']:
                style = self.get_style(node)
                self.guess_text_align(node, style, options)
                self.guess_text_scale(node, style, options, mat)

            if type == 'altitude' and options[key].isdigit():
                options[key] = "[fix " + options[key] + "]"

            if type in ('altitude', 'label') and text == '{ALTITUDE}':
                type = 'altitude'
                del options[key]

            if type in ('station-name', 'label') and text == '{STATION-NAME}':
                type = 'station-name'
                del options[key]

        # restore orientation from transform
        if type not in ['station']:
            orient = orientation(mat)
            if orient > 0.05:
                options['orientation'] = orient

        # output in therion format
        formatted_options = format_options_leading_space(options)
        print_utf8("point %s %s %s%s\n" % (fstr(params[0]), fstr(params[1]), type, formatted_options))

    def output_area(self, node):
        mat = self.i2d_affine(node)

        # get therion attributes
        role, type, options = get_props(node)

        # get path data
        d = self.get_d(node)
        if not d:
            inkex.errormsg('no path data for element %s' % (node))
            return
        p = parsePath(d)

        th2area = Th2Area(type)

        line_options = {}
        for key, value in options.items():
            if key.startswith("line-"):
                line_options[key[5:]] = value
            else:
                th2area.options[key] = value

        for cmd, params in p:
            if cmd == 'M':
                th2area.append_line()
                th2area.current_line().options.update(line_options)
            if cmd == 'Z':
                th2area.current_line().close()
            else:
                th2area.current_line().append(transformParams(mat, params))
        th2area.output(self.current_scrap_id)

    def output_input(self, node):
        label = node.get(inkscape_label)
        file_name = label.removeprefix('input ')
        inkex.errormsg(f"Info: input {file_name!r}")
        print_utf8(f"input {file_name}")


if __name__ == '__main__':
    e = Th2Output()
    e.affect()
