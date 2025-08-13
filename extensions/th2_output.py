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
    StyleDict,
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
    xpath_elems,
)

from typing import (
    Dict,
    Iterator,
    List,
    Optional,
    Sequence,
    Tuple,
)
from lxml import etree
import inkex
from inkex0 import simpletransform
from inkex0 import simplestyle
import math
import re
import os
import uuid
from pathlib import Path


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


def get_id(options: OptionsDict) -> str:
    """
    Get the ID or insert a new unique ID if missing.
    """
    if not options.get('id'):
        options['id'] = uuid.uuid4().hex
    return options['id']


def format_options_leading_space(options: OptionsDict):
    """
    Like format_options() but with a leading space if non-empty.
    """
    formatted = format_options(options)
    if formatted:
        return " " + formatted
    return ""


def scrap_options_updater(
    options: OptionsDict,
    *,
    scrap_id: str = "",
    dots_per_scale_m: float = 0.0,
):
    """
    Like options.update(new_options) but warn about overwriting existing keys.
    """

    def scale_from_m_per_dots(m_per_dots: str) -> float:
        return m_per_dots * dots_per_scale_m

    def set_kv(key: str, value: th2ex.OptionValue):
        if key in options:
            if key == "projection":
                pass
            elif key == "scale":
                value_old = th2ex.parse_scrap_scale_m_per_dots(options[key])
                value_new = th2ex.parse_scrap_scale_m_per_dots(value)
                if not (0.9 < (value_old / value_new) < 1.1):
                    inkex.errormsg(  #
                        f"Scrap {scrap_id} has -{key} {value}"
                        f" (1:{scale_from_m_per_dots(value_new):g}) which is different from"
                        f" 1:{scale_from_m_per_dots(value_old):g}")
            elif options[key] != value:
                inkex.errormsg(f"Overwriting -{key} {options[key]!r} with {value!r}")
        options[key] = value

    def inner(new_options: OptionsDict):
        for key, value in new_options.items():
            set_kv(key, value)

    return inner


class Th2Line:
    def __init__(self, type: str = 'wall'):
        self.type = type
        self.options: OptionsDict = {}
        self.points: List[str] = []
        self._last: Sequence[str] = []

    @staticmethod
    def _format_params(params: Sequence[float]) -> List[str]:
        return [fstr(i) for i in params]

    def append(self, params: Sequence[float]):
        self._last = self._format_params(params)
        self.points.append(" ".join(self._last))

    def append_point_options(self, point_options: OptionsDict):
        # point options follow points, so there must be at least one
        assert self.points
        self.points.extend(th2ex.format_options_iter(point_options, prefix=""))

    def ends_with_point(self, params: Sequence[float]) -> bool:
        assert len(params) == 2
        return self._last[-2:] == self._format_params(params)

    def close(self) -> None:
        self.options['close'] = 'on'
        if self.points and self.points[0].split() != self._last[-2:]:
            self._last = self.points[0].split()
            self.points.append(self.points[0])

    def output(self) -> List[str]:
        formatted_options = format_options_leading_space(self.options)
        return [
            f"line {self.type}{formatted_options}",
            "  " + "\n  ".join(self.points),
            "endline\n",
        ]


class Th2Area:
    def __init__(self, type: str):
        self.type = type
        self.options: OptionsDict = {}
        self._lines: List[Th2Line] = []

    def has_lines(self) -> bool:
        return bool(self._lines)

    def current_line(self) -> Th2Line:
        return self._lines[-1]

    def append_line(self) -> None:
        self._lines.append(Th2Line('border'))

    def output(self) -> Iterator[str]:
        ids = []

        # if only one line, assume it must be closed
        if len(self._lines) == 1:
            self._lines[0].close()

        for line in self._lines:
            ids.append(get_id(line.options))
            yield from line.output()

        # output area
        formatted_options = format_options_leading_space(self.options)
        yield f"area {self.type}{formatted_options}"
        for lineid in ids:
            yield "  " + lineid
        yield "endarea\n"


class Th2Output(Th2Effect):
    doc_x = 0.0
    doc_y = 0.0
    doc_width = 0.0  # viewBox width
    doc_height = 0.0  # viewBox height
    doc_width_m = 0.0  # width in meters
    doc_height_m = 0.0  # height in meters

    def __init__(self) -> None:
        super().__init__()
        self.arg_parser.add_argument("--scale", type=int, default=0, help="Scale, e.g. 200 for 1:200")
        self.arg_parser.add_argument("--dpi", type=int, default=0, help="deprecated")
        self.arg_parser.add_argument("--layers", type=str, default="all")
        self.arg_parser.add_argument("--images", type=inkex.Boolean, default=True)
        self.arg_parser.add_argument("--nolpe", type=inkex.Boolean, default=True)
        self.arg_parser.add_argument("--lay2scr", type=inkex.Boolean, default=True)
        self.arg_parser.add_argument("--xyascenter", type=inkex.Boolean, default=True)
        self.arg_parser.add_argument("--projection", type=str, default="")
        self.arg_parser.add_argument("--author", type=str, default="", help='deprecated, use --options="-author ..." instead')
        self.arg_parser.add_argument("--options", type=str, default="")
        self.textpath_dict: Dict[str, OptionsDict] = {}
        self.outbuf: List[str] = []

    def get_output_bytes(self) -> bytes:
        if not self.outbuf:
            return b""
        return b"\n".join(s.encode("utf-8") for s in self.outbuf + [""])

    def println(self, s: str):
        self.outbuf.append(str(s))

    def get_m_per_uu(self) -> float:
        """
        Get drawing (print/paper) meters per user unit
        """
        m_per_dots_width = self.doc_width_m / self.doc_width
        m_per_dots_height = self.doc_height_m / self.doc_height
        assert 0.9 < (m_per_dots_width / m_per_dots_height) < 1.1
        return (m_per_dots_width + m_per_dots_height) / 2

    def get_style(self, node: Optional[EtreeElement]):
        """
        Get the cascaded style from the style attributes. Does not consider class attributes.
        """
        style: StyleDict = {}
        stack: List[EtreeElement] = []
        while node is not None:
            stack.append(node)
            node = node.getparent()
        for node in reversed(stack):
            style.update(self.get_style_nocascade(node))
        return style

    def get_style_nocascade(self, node: EtreeElement) -> Dict[str, str]:
        return simplestyle.parseStyle(node.get('style', ''))

    def get_style_attr(self, node: EtreeElement, style: StyleDict, key: str, d=''):
        d = node.get(key, d)
        return style.get(key, d)

    def print_scrap_begin(self, id: str, test: bool, options: Optional[OptionsDict] = None):
        """
        Args:
          id: Scrap name
          test: If false, don't actually print anything
          options: Options from the layer element, they have the highest
            priority and overwrite global command line scrap options.
        """
        if test:
            options_elem = options or {}
            options = {}

            dots_per_scale_m = th2pref.scale_th2_per_uu * self.doc_width / self.doc_width_m

            if self.options.scale > 0:
                if self.options.dpi:
                    inkex.errormsg("--dpi is deprecated, use viewBox and width in cm")
                    options['scale'] = '[%d %d inch]' % (
                        self.options.dpi,
                        self.options.scale,
                    )
                elif self.doc_width_m:
                    options['scale'] = '[%g %g m]' % (
                        dots_per_scale_m,
                        self.options.scale,
                    )
            if self.options.projection:
                options['projection'] = self.options.projection
            if self.options.author:
                options['author'] = self.options.author
            options_update = scrap_options_updater(
                options,
                scrap_id=id,
                dots_per_scale_m=dots_per_scale_m,
            )
            options_update(parse_options(self.options.options))
            options_update(options_elem)
            self.println('\nscrap %s %s\n' % (id, format_options(options)))

    def print_scrap_end(self, test: bool):
        if test:
            self.println("endscrap\n\n")

    def setdefault_doc_dims(self) -> None:
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
        if not (0.9 < (m_per_dots / self.get_m_per_uu()) < 1.1):
            inkex.errormsg(
                f"doc_width:  {self.doc_width}     doc_width_m:  {self.doc_width_m}\n"
                f"doc_height: {self.doc_height}    doc_height_m: {self.doc_height_m}\n"
                f"m_per_dots: {self.get_m_per_uu()}\n")

    def effect(self) -> None:
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
        stylenodes = xpath_elems(self.document, '//svg:style')
        pattern = re.compile(r'\.(\w+)\s*\{(.*?)\}')
        for stylenode in stylenodes:
            if isinstance(stylenode.text, str):
                for x in pattern.finditer(stylenode.text):
                    self.classes[x.group(1)] = simplestyle.parseStyle(x.group(2).strip())

        self.println('encoding  utf-8')
        if self.doc_width and self.doc_height:
            params = [
                self.doc_x,
                self.doc_y + self.doc_height,
                self.doc_x + self.doc_width,
                self.doc_y,
            ]
            self.println('##XTHERION## xth_me_area_adjust %s %s %s %s' %
                  tuple(map(fstr2, transformParams(self.r2d, params))))

        area_zoom_to = root.get(th2ex.therion_area_zoom_to)
        if area_zoom_to:
            self.println(f'##XTHERION## xth_me_area_zoom_to {area_zoom_to}')

        # text on path
        if th2pref.textonpath:
            textpaths = xpath_elems(self.document, '//svg:textPath')
            for node in textpaths:
                href = node.get(xlink_href).split('#', 1)[-1]
                text = self.get_point_text(node)
                options = {'text': text} if text else {}
                self.guess_text_scale(node, self.get_style(node.getparent()), options, self.i2d_affine(node))
                self.textpath_dict[href] = options

        if self.options.images:
            images = list(xpath_elems(self.document, '//svg:image')) + \
                     list(xpath_elems(self.document, '//svg:g[@therion:type="xth_me_image_insert"]'))
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
                    # inkex.errormsg('Embedded images not supported!')
                    continue
                paramsTrans = transformParams(mat, params)
                mat = simpletransform.composeTransform(mat, [[1, 0, params[0]], [0, 1, params[1]]])
                w = node.get('width', '100%')
                h = node.get('height', '100%')
                if th2pref.image_inkscape:
                    self.println('##INKSCAPE## image %s %s %s %s' % (w, h, simpletransform.formatTransform(mat), href))
                    continue
                if href.startswith('file://'):
                    href = href[7:]
                document_path = os.getenv("DOCUMENT_PATH")
                if document_path:
                    href = os.path.relpath(href, os.path.dirname(document_path))
                path = Path(href)
                self.println('##XTHERION## xth_me_image_insert {%s 1 1.0} {%s %s} %s 0 {}' %
                      (fstr2(paramsTrans[0], 6), fstr2(paramsTrans[1], 6), XVIroot, optquote(path.as_posix())))

        self.println('\n')

        self.print_scrap_begin('scrap1', not self.options.lay2scr)

        if self.options.layers == 'current':
            layer = self.current_layer
            while layer.get(inkscape_groupmode, '') != "layer" and layer.getparent():
                layer = layer.getparent()
            self.output_scrap(layer)
        else:
            layers = xpath_elems(self.document, '/svg:svg/svg:g[@inkscape:groupmode="layer"]')
            if len(layers) == 0:
                inkex.errormsg("Document has no layers!\nFallback to single scrap")
                layers = [root]
            else:
                rootshapes = xpath_elems(self.document, ' | '.join([
                    '/svg:svg/svg:path',
                    '/svg:svg/svg:text',
                    '/svg:svg/svg:use',
                ]))
                if rootshapes:
                    inkex.errormsg(f"Warning: {len(rootshapes)} shapes not in a layer")
            for layer in reversed(layers):
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

    def output_g(self, node: EtreeElement):
        for child in reversed(node):
            if isinstance(child, etree._Comment):
                if child.text and child.text.startswith('#therion'):
                    self.println(child.text.split('\n', 1)[1])
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

    def output_scrap(self, layer: EtreeElement):
        id = layer.get(inkscape_label)
        if not id:
            id = layer.get('id')
        if not id:
            id = 'scrapX'
        name, sep, optionstail = id.partition(' -')
        name = name.rstrip().replace(' ', '_')
        assert name, f"scrap name missing for layer {id!r}"
        options = parse_options_node(layer)
        options.update(parse_options(sep + optionstail))
        self.print_scrap_begin(name, self.options.lay2scr, options)
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
                return d
            value = node.get('points')
            if value:
                d = 'M' + value
                if node.tag == svg_polygon:
                    d += ' z'
                return d
            x1 = node.get('x1')
            if x1:
                return ''.join([
                    'M', x1, ',',
                    node.get('y1', '0'), 'L',
                    node.get('x2', '0'), ',',
                    node.get('y2', '0')
                ])
            width = node.get('width')
            height = node.get('height')
            if width and height:
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


    def output_line(self, node: EtreeElement):
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
                        for line in th2line.output():
                            self.println(line)
                if not join_lines:
                    th2line = Th2Line(type)
                    th2line.options.update(options)
            assert th2line is not None
            if cmd == 'Z':
                th2line.close()
            elif not join_lines:
                th2line.append(params)
            th2line.append_point_options(point_options)
        if th2line is not None:
            for line in th2line.output():
                self.println(line)
        else:
            inkex.errormsg('no path data for element <{} id="{}">'.format(
                node, node.get('id')))

    def output_textblock(self, node: EtreeElement):
        line = self.get_point_text(node)
        a = line.split()
        if a:
            self.println(line)
        desc = xpath_elems(node, 'svg:desc')
        if len(desc) > 0:
            self.println(desc[0].text.rstrip())
        if a:
            self.println('end' + a[0])
        self.println('')

    def get_point_text(self, node: EtreeElement):
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

    def guess_text_align(self, node: EtreeElement, style: StyleDict, options: OptionsDict):
        textanchor = self.get_style_attr(node, style, 'text-anchor', align2anchor_default_out)
        baseline = self.get_style_attr(node, style, 'dominant-baseline', align2baseline_default_out)
        align = self.align_tb.get(baseline, options.get('align', ''))
        align = align[0] if align[:1] in ['t', 'b'] else ''
        align += self.align_rl.get(textanchor, '')
        if align:
            options['align'] = align
        else:
            options.pop('align', None)

    def guess_text_scale(self, node: EtreeElement, style: StyleDict, options: OptionsDict, mat: Optional[AffineType]):
        """
        Guess closest text scale (e.g. "xl") from actual font size and set it in
        options if it's not the default scale.

        Args:
          mat: Affine from item local coordinates to th2 drawing units
        """
        fontsize = self.get_style_attr(node, style, 'font-size', '12')
        if fontsize[-1] == '%':
            fontsize = float(fontsize[:-1]) / 100.0 * 12
        else:
            fontsize = self.unittouu(fontsize)
        if mat is not None:
            fontsize *= descrim(mat)
        fontsize /= th2pref.scale_th2_per_uu
        fontsize_pt = th2ex.convert_unit((fontsize * self.get_m_per_uu(), "m"), "pt")
        fonts_setup_default = th2ex.get_fonts_setup_default()
        if (  #
                fontsize_pt < fonts_setup_default['xs'] * 0.8 or  #
                fontsize_pt > fonts_setup_default['xl'] * 1.5):
            scale = f'{fontsize_pt / fonts_setup_default["m"]:g}'
        else:
            scale = min(fonts_setup_default.items(),
                        key=lambda item: abs(item[1] - fontsize_pt))[0]
        if scale != 'm':
            options['scale'] = scale

    def output_point(self, node: EtreeElement):
        mat = self.i2d_affine(node)

        # get x/y
        params = self.node_center(node)
        params = transformParams(mat, params)

        # get therion attributes
        role, type, options = get_props(node)

        key = text_keys_output.get(type) if node.tag == svg_text else None

        if key is not None:
            # restore text for labels etc.
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
        self.println("point %s %s %s%s\n" % (fstr(params[0]), fstr(params[1]), type, formatted_options))

    def output_area(self, node: EtreeElement) -> None:
        # get therion attributes
        role, type, options = get_props(node)

        th2area = Th2Area(type)

        line_options: OptionsDict = {}
        for key, value in options.items():
            if key.startswith("line-"):
                line_options[key[5:]] = value
            else:
                th2area.options[key] = value

        for (cmd, params, point_options) in self.get_line_data(node):
            if cmd == 'M':
                th2area.append_line()
                th2area.current_line().options.update(line_options)
            if cmd == 'Z':
                th2area.current_line().close()
            else:
                th2area.current_line().append(params)
            th2area.current_line().append_point_options(point_options)

        if not th2area.has_lines():
            inkex.errormsg('no path data for element <{} id="{}">'.format(
                node, node.get('id')))

        for line in th2area.output():
            self.println(line)

    def output_input(self, node: EtreeElement):
        label = node.get(inkscape_label, "")
        file_name = label.removeprefix('input ')
        inkex.errormsg(f"Info: input {file_name!r}")
        self.println(f"input {file_name}")


if __name__ == '__main__':
    e = Th2Output()
    e.run()
