#!/usr/bin/env python
'''
Copyright (C) 2008 Thomas Holder, http://sf.net/users/speleo3/
Distributed under the terms of the GNU General Public License v2 or later
'''

import th2ex
from th2ex import (
    ParsedPath,
    parse_scrap_scale_m_per_dots,
    th2pref,
    oparser,
    th2pref_reload,
    th2pref_store_to_xml,
    therion_role,
    therion_type,
    therion_options,
    therion_xvi_dx,
    xlink_href,
    xml_space,
    inkscape_groupmode,
    inkscape_label,
    inkscape_original_d,
    inkscape_path_effect,
    sodipodi_role,
    sodipodi_insensitive,
    sodipodi_nodetypes,
    parse_options,
    format_options,
    set_props,
    get_props,
    align_shortcuts,
    align2anchor_default_in,
    align2anchor,
    align2baseline_default_in,
    align2baseline,
    text_keys_input,
    find_in_pwd,
    get_template_svg_path,
)

import sys
import os
import re
from typing import (
    Dict,
    List,
    Sequence,
    Tuple,
)

from lxml import etree
import inkex

EtreeElement = etree._Element

pointtype2layer = {
    'altitude': 'labe',
    'blocks': 'rock',
    'breakdown-choke': 'rock',
    'continuation': 'labe',
    'debris': 'rock',
    'gradient': 'cont',
    'height': 'labe',
    'passage-height': 'labe',
    'pebbles': 'rock',
    'station': 'stat',
    'station-name': 'stat',
    'label': 'labe',
    'dimensions': 'labe',
}

linetype2layer = {
    'border': 'wall',
    'ceiling-meander': 'cont',
    'ceiling-step': 'cont',
    'chimney': 'cont',
    'contour': 'cont',
    'floor-meander': 'cont',
    'floor-step': 'cont',
    'gradient': 'cont',
    'label': 'labe',
    'overhang': 'cont',
    'pit': 'cont',
    'rock-border': 'rock',
    'rock-edge': 'rock',
    'slope': 'cont',
    'survey': 'stat',
    'wall': 'wall',
}

point_colors = {
    'station-name': 'orange',
    'altitude': '#f0f',
    'u': 'red',
}

default_line_opts = {
    'section': {'direction': 'begin'},
}

# some prefs
oparser.add_option('--sublayers', action='store', type='inkbool', dest='sublayers', default=False)
oparser.add_option('--basescale', action='store', type='float', dest='basescale', default=1.0)
oparser.add_option('--howtostore', action='store', type='choice', dest='howtostore',
                   choices=('inkscape_label', 'title', 'therion_attribs'))
oparser.add_option('--lock-stations', action='store', type='inkbool', dest='lock_stations', default=False)


class this:
    line_nr = 0
    id_count = 0
    textblock_count = 0

    borders: Dict[str, EtreeElement] = {}  # for areas
    sublayers: Dict[str, EtreeElement] = {}

    doc_x = 0
    doc_y = 0
    doc_width = 0
    doc_height = 0

    m_per_dots = 0.0254
    m_per_dots_set = False

    encoding = 'UTF-8'
    file_stack: List["FileRecord"] = []

    LPE_symbols: List[str]

    @classmethod
    def getcurrentlayer(this):
        return this.layer_stack[-1] if this.layer_stack else this.root


def to_user_units(value: float, unit: str) -> float:
    """
    Convert a physical print dimension (e.g. 12pt or 2mm) to local user units.
    """
    return th2ex.convert_unit((value, unit), "cm") / this.m_per_dots


def scale_to_fontsize(scale: str) -> float:
    """
    Convert a scale value ("xs" ... "xl", or numeric) to font size in user units
    """
    fonts_setup_default = th2ex.get_fonts_setup_default()
    fontsize_pt = (
        fonts_setup_default.get(scale) or  #
        fonts_setup_default["m"] * float(scale))
    return to_user_units(fontsize_pt, "pt")


def populate_legend():
    layer_legend = this.root.xpath('svg:g[@id="layer-legend"]', namespaces=inkex.NSS)[0]

    # points legend
    spacing = 40
    max_x = 800
    x = spacing
    y = 0
    for type in this.point_symbols:
        node = etree.SubElement(layer_legend, 'text')
        node.set('transform', 'translate(%d,%d)' % (x, -(y + 0.25) * spacing))
        node.text = type
        node = etree.SubElement(layer_legend, 'use')
        set_props(node, 'point', type)
        node.set('transform', 'translate(%d,%d)' % (x, -(y + 1) * spacing))
        node.set(xlink_href, '#point-' + type)
        x += spacing
        if x > max_x:
            x = spacing
            y += 2

    node = etree.SubElement(layer_legend, 'rect', {'style': 'fill:none;stroke:black', 'transform': 'scale(1,-1)'})
    node.set('height', '%d' % ((2 + y) * spacing))
    if y > 0:
        node.set('width', '%d' % (max_x + spacing))
    else:
        node.set('width', '%d' % (x))

    # lines legend
    x = spacing
    for type in this.LPE_symbols:
        type_uscore = type
        type = type.replace('_', ':')
        node = etree.SubElement(layer_legend, 'text')
        node.set('transform', 'translate(%d,%d)' % (-spacing, x + 0.4 * spacing))
        node.text = type
        node = etree.SubElement(layer_legend, 'path')
        set_props(node, 'line', type, default_line_opts.get(type, {}))
        node.set(inkscape_original_d, 'M%f,%fh%f' % (-1.5 * spacing, x, spacing))
        node.set(inkscape_path_effect, '#LPE-' + type_uscore)
        node.set('class', 'line ' + type.replace(':', ' '))
        x += spacing
    for type in ('arrow', 'map-connection', 'gradient', 'chimney', 'section'):
        node = etree.SubElement(layer_legend, 'text')
        node.set('transform', 'translate(%d,%d)' % (-spacing, x + 0.4 * spacing))
        node.text = type
        node = etree.SubElement(layer_legend, 'path')
        set_props(node, 'line', type, default_line_opts.get(type, {}))
        node.set('d', 'M%f,%fh%f' % (-1.5 * spacing, x, spacing))
        node.set('class', 'line ' + type)
        x += spacing

    node = etree.SubElement(layer_legend, 'rect', {'y': '0', 'style': 'fill:none;stroke:black'})
    node.set('x', '%d' % (-2 * spacing))
    node.set('height', '%d' % (x))
    node.set('width', '%d' % (2 * spacing))


def getlayer(role: str, type: str):
    if not th2pref.sublayers:
        return this.getcurrentlayer()
    if role == 'point':
        key = pointtype2layer.get(type, 'misc')
    else:
        key = linetype2layer.get(type, 'misc')
    return this.sublayers.get(key, this.getcurrentlayer())


class FileRecord:
    def __init__(self, patharg: str):
        searchpath: List[str] = [this.file_stack[-1].dirname] if this.file_stack else []
        self.filename: str = find_in_pwd(patharg, searchpath)
        self.dirname: str = os.path.dirname(self.filename)
        self.f_handle = open(self.filename, 'rb')
        self.f_enum = enumerate(self.f_handle)

    def __del__(self):
        self.f_handle.close()


def set_m_per_dots(value: float, overwrite: bool = False):
    if this.m_per_dots_set and not (0.9 < (value / this.m_per_dots) < 1.1):
        errormsg(f"Warning: m/dots {value} vs {this.m_per_dots}")
    if overwrite or not this.m_per_dots_set:
        this.m_per_dots = value
        this.m_per_dots_set = True


def floatscale(x: str) -> float:
    """
    Scale input coordinate to base-scale
    """
    return float(x) / th2pref.basescale


def flipY(a: List[str]) -> List[str]:
    """
    Transform th2 coordinates to SVG user units, in-place.

    - Scale to base-scale
    - Invert y

    Args:
      a: Flat 2D coordinate list

    Returns:
      Modified input list
    """
    # TODO %f rounds to 6 digits, check if sufficient
    a[0::2] = ['%f' % (floatscale(i)) for i in a[0::2]]
    a[1::2] = ['%f' % (-floatscale(i)) for i in a[1::2]]
    return a


def formatPath(a: ParsedPath) -> str:
    """Format SVG path data from an array

    Copied from simplepath
    """
    return "".join([cmd + " ".join([str(p) for p in params]) for (cmd, params) in a])


def reverseP(p: ParsedPath) -> ParsedPath:
    prevcmd = p[-1][0]
    prevparams = p[-1][1]
    retval: ParsedPath = [('M', prevparams[-2:])]
    for cmd, params in reversed(p[:-1]):
        newparams = []
        if len(prevparams) == 6:
            newparams = [
                prevparams[2],
                prevparams[3],
                prevparams[0],
                prevparams[1],
            ]
        newparams.extend(params[-2:])
        retval.append((prevcmd, newparams))
        prevparams = params
        prevcmd = cmd
    return retval


def f_readline():
    try:
        this.line_nr, line = next(this.file_stack[-1].f_enum)
    except StopIteration:
        this.file_stack.pop()
        this.layer_stack.pop()
        return f_readline() if this.file_stack else ''
    line = line.rstrip(b'\r\n')
    line = line.decode(this.encoding)
    if line.endswith('\\'):
        line = line[:-1] + f_readline()
    return line + '\n'


def errormsg(x):
    print('[line %d]' % (this.line_nr + 1), x, file=sys.stderr)


def parse(a):
    function = parsedict.get(a[0])
    if function:
        function(a)
    elif a[0].startswith('#'):
        parse_LINE2COMMENT(a)
    else:
        errormsg('skipped: ' + a[0])


def parse_encoding(a):
    this.encoding = a[1]


def parse_INKSCAPE(a):
    if a[1] == 'image':
        img = etree.Element('image')
        img.set('width', a[2])
        img.set('height', a[3])
        img.set('transform', a[4])
        img.set(xlink_href, ' '.join(a[5:]))
        this.root.xpath('svg:g[@id="layer-scan"]', namespaces=inkex.NSS)[0].append(img)


def parse_XTHERION(a):
    if a[1] == 'xth_me_image_insert':
        href, XVIroot = '', ''
        try:
            # xth_me_image_insert {xx yy fname iidx imgx}
            # xx = {xx vsb igamma}
            # yy = {yy XVIroot}
            # XVIroot is the station name which defines (0,0)
            me_image_str = ' '.join(a[2:])
            import tkinter
            tk_instance = tkinter.Tcl().tk.eval
            tk_instance('set xth_me_image {' + me_image_str + '}')
            href = tk_instance('lindex $xth_me_image 2')
            x = tk_instance('lindex $xth_me_image 0 0')
            y = tk_instance('expr (-1 * [lindex $xth_me_image 1 0])')
            XVIroot = tk_instance('lindex $xth_me_image 1 1')
        except BaseException as e:
            errormsg('tk parsing failed, fallback to regex (%s)' % str(e))
            # TODO: Warning: poor expression, might fail
            m = re.match(r'\{([-.0-9]+) [01] [-.0-9]+\} \{?([-.0-9]+)(?: (?:\{\}|[-.0-9]+)\})? (\S+)', ' '.join(a[2:]))
            if m:
                href = m.group(3)
                if href[0] == '"':
                    href = href[1:-1]
                x = m.group(1)
                y = str(-1 * float(m.group(2)))
        if href != '':
            try:
                href = find_in_pwd(href, [this.file_stack[-1].dirname])
            except IOError:
                errormsg('image not found: ' + repr(href[:128]))
        if href.endswith('.xvi'):
            try:
                import xvi_input
                with open(href) as handle:
                    g_xvi = xvi_input.xvi2svg(handle, False, 6, XVIroot)
                img = etree.Element('g')
                img.append(g_xvi)
                img.set('transform', 'scale(1,-1) translate(%s,%s)' % (x, y))
                img.set(therion_type, 'xth_me_image_insert')
                img.set(therion_options, format_options({'href': href,
                                                         'XVIroot': XVIroot}))
                this.root.xpath('svg:g[@id="layer-scan"]', namespaces=inkex.NSS)[0].append(img)

                dx = g_xvi.get(therion_xvi_dx)
                if dx:
                    set_m_per_dots(1 / float(dx), overwrite=True)

            except BaseException as e:
                errormsg('xvi2svg failed ({})'.format(e))
        elif href != '':
            img = etree.Element('image')
            img.set(xlink_href, href)
            img.set('x', x)
            img.set('y', y)
            img.set('transform', 'scale(1,-1)')
            this.root.xpath('svg:g[@id="layer-scan"]', namespaces=inkex.NSS)[0].append(img)
        else:
            errormsg('skipped: ' + a[1])

    if a[1] == 'xth_me_area_adjust':
        this.doc_x = floatscale(a[2])
        this.doc_y = floatscale(a[5])
        this.doc_width = floatscale(a[4]) - this.doc_x
        this.doc_height = this.doc_y - floatscale(a[3])


def parse_scrap(a):
    e = etree.Element('g')
    e.set(inkscape_groupmode, "layer")

    # e.set(inkscape_label, ' '.join(a))
    e.set(inkscape_label, a[1])
    e.set(therion_role, 'scrap')
    e.set(therion_options, ' '.join(a[2:]))

    options = parse_options(a[2:])
    if "scale" in options:
        set_m_per_dots(parse_scrap_scale_m_per_dots(options["scale"]))

    if th2pref.sublayers:
        this.sublayers = {
            'wall': etree.SubElement(e, 'g', {inkscape_groupmode: 'layer', inkscape_label: u'Walls'}),
            'cont': etree.SubElement(e, 'g', {inkscape_groupmode: 'layer', inkscape_label: u'Contours'}),
            'rock': etree.SubElement(e, 'g', {inkscape_groupmode: 'layer', inkscape_label: u'Boulders'}),
            'stat': etree.SubElement(e, 'g', {inkscape_groupmode: 'layer', inkscape_label: u'Stations'}),
            'misc': etree.SubElement(e, 'g', {inkscape_groupmode: 'layer', inkscape_label: u'Misc'}),
            'labe': etree.SubElement(e, 'g', {inkscape_groupmode: 'layer', inkscape_label: u'Labels'}),
        }

    this.getcurrentlayer().append(e)
    this.layer_stack.append(e)

    while True:
        line = f_readline()
        assert line != ''
        a = line.split()
        if len(a) == 0:
            continue
        if a[0] == 'endscrap':
            break
        parse(a)

    this.layer_stack.pop()


def preserve_literal(a: Sequence[str], lines: Sequence[str] = ()):
    """
    Preserve literal lines.

    Args:
      a: Optional first line as sequence of words
      lines: Lines, including the line feed.
    """
    chunks = ['#therion\n']
    assert a  # seems to be true (subject to change?)
    chunks.append(' '.join(a) + '\n')
    chunks.extend(lines)
    text = ''.join(chunks)
    assert text.endswith("\n")
    e = etree.Comment()
    e.text = text
    this.getcurrentlayer().insert(0, e)


def read_block_lines(sentinel: str, *, skip_blank: bool = False) -> List[str]:
    """
    Read lines up to and including the given sentinel word.
    """
    lines = []
    while True:
        line = f_readline()
        assert line != ''
        a = line.split()
        if skip_blank and not a:
            continue
        lines.append(line)
        if a[0] == sentinel:
            break
    return lines


def parse_area(a_in):
    lines = read_block_lines('endarea', skip_blank=True)

    # we can only handle areas with one border line
    if len(lines) != 2 or lines[0].strip() not in this.borders:
        preserve_literal(a_in, lines)
        return

    # update border line
    e = this.borders[lines[0].strip()]
    role, type, options = get_props(e)
    assert (role, type) == ('line', 'border')
    options = {f"line-{key}": value for (key, value) in options.items()}
    options.update(parse_options(a_in[2:]))
    type_subtype = a_in[1]
    if ':' in type_subtype:
        type, subtype = type_subtype.split(':', 1)
    else:
        type = type_subtype
        subtype = options.get('subtype', '')
    e.set('class', 'area %s %s' % (type, subtype))
    set_props(e, 'area', type_subtype, options)


def parse_BLOCK2COMMENT(a):
    lines = read_block_lines("end" + a[0])
    preserve_literal(a, lines)


def parse_LINE2COMMENT(a):
    preserve_literal(a)


def parse_BLOCK2TEXT(a):
    '''
    Currently unused
    '''
    lines = read_block_lines("end" + a[0])
    preserve_literal_as_textblock(a, lines)


def preserve_literal_as_textblock(a: Sequence[str], lines: Sequence[str] = ()):
    """
    Preserve literal lines as <text> element.

    First line is displayed text, block body is <desc>.

    Args:
      a: First line as sequence of words
      lines: Lines, including the line feed. Last line must be "end...".
    """
    assert lines[-1].split()[0] == f"end{a[0]}"
    e = etree.Element('text')
    e.set(therion_role, 'textblock')
    e.set('style', 'font-size:8;fill:#900')
    e.set('x', str(this.doc_width + 20))
    e.set('y', str(this.textblock_count * 10 + 20))
    e.set(xml_space, 'preserve')
    desc = etree.SubElement(e, 'desc')
    desc.tail = ' '.join(a)
    desc.text = ''.join(lines[:-1])
    this.getcurrentlayer().insert(0, e)
    this.textblock_count += 1


class LineSegment:
    def __init__(self) -> None:
        self.options: Dict[str, str] = {}
        self.nodetypes: List[str] = []
        self.x_list: ParsedPath[str] = []

    def is_empty(self) -> bool:
        return len(self.x_list) < 2

    def set_nodetype(self, nodetype: str):
        assert self.nodetypes
        self.nodetypes[-1] = nodetype

    def last_nodetype(self) -> str:
        return self.nodetypes[-1]

    def last_point(self) -> Sequence[str]:
        return self.x_list[-1][1][-2:]

    def get_d(self) -> str:
        return formatPath(self.x_list)

    def reverse(self):
        self.x_list = reverseP(self.x_list)
        self.nodetypes.reverse()

    def add_coords(self, a: List[str]):
        a = flipY(a)
        if not self.x_list:
            assert len(a) == 2
            self.x_list.append(('M', a))
            self.nodetypes.append("c")
        elif len(a) == 2:
            self.x_list.append(('L', a))
            self.nodetypes.append("c")
        elif len(a) == 6:
            self.x_list.append(('C', a))
            self.nodetypes.append("s")
        else:
            errormsg('error: length = %d' % len(a))


class SegmentedLine:
    def __init__(self) -> None:
        self.segments: List[LineSegment] = [LineSegment()]

    def last_seg(self):
        return self.segments[-1]

    def add_option(self, a: List[str]):
        seg = self.last_seg()
        if not seg.is_empty():
            seg_new = LineSegment()
            seg_new.x_list.append(("M", seg.last_point()))
            seg_new.nodetypes.append(seg.nodetypes[-1])
            self.segments.append(seg_new)
            seg = seg_new
        seg.options[a[0]] = " ".join(a[1:])

    def is_empty(self) -> bool:
        return all(seg.is_empty() for seg in self.segments)

    def reverse(self):
        for seg in self.segments:
            seg.reverse()
        self.segments.reverse()
        # TODO
        # Options like "altitude" which affect only one point need to be moved
        # to the previous segment


def parse_line(a: List[str]):
    assert a[0] == "line"
    options = parse_options(a[2:])
    type_subtype = a[1]
    if ':' in type_subtype:
        type, subtype = type_subtype.split(':', 1)
    else:
        type = type_subtype
        subtype = options.get('subtype', '')

    segline = SegmentedLine()

    while True:
        line = f_readline()
        assert line != ''
        a = line.split()
        if len(a) == 0:
            continue
        if a[0] == 'endline':
            break
        if a[0] == 'smooth':
            segline.last_seg().set_nodetype("c" if a[1] == "off" else "s")
        elif a[0][0].isdigit() or a[0][0] == '-':
            segline.last_seg().add_coords(a)
        else:
            segline.add_option(a)

    if segline.is_empty():
        errormsg('warning: empty line')
        return

    this.id_count += 1
    e_id = 'line_%s_%d' % (type, this.id_count)

    if not any(seg.options for seg in segline.segments):
        assert len(segline.segments) == 1

        if options.pop('reverse', 'off') == 'on':
            segline.reverse()

        if options.pop('close', 'off') == 'on':
            segline.last_seg().x_list.append(("Z", ()))

        e = None
    else:
        if options.get('reverse', 'off') == 'on':
            errormsg(f'cannot reverse path with point options ({e_id})')

        if options.get('close', 'off') == 'on':
            errormsg(f'cannot close path with point options ({e_id})')

        e = etree.Element('g')

    for seg in segline.segments:
        d = seg.get_d()
        subtype = seg.options.get('subtype', subtype)

        e_path = etree.Element('path')
        e_path.set('class', 'line %s %s' % (type, subtype))

        if type + '_' + subtype in this.LPE_symbols:
            e_path.set(inkscape_path_effect, '#LPE-%s_%s' % (type, subtype))
            e_path.set(inkscape_original_d, d)
        elif type in this.LPE_symbols:
            e_path.set(inkscape_path_effect, '#LPE-%s' % (type))
            e_path.set(inkscape_original_d, d)
        else:
            e_path.set('d', d)

        e_path.set(sodipodi_nodetypes, "".join(seg.nodetypes))

        if e is None:
            e = e_path
        else:
            e.insert(0, e_path)
            set_props(e_path, '@', '@', seg.options)

    assert e is not None

    e.set('id', e_id)

    if th2pref.textonpath and type == 'label':
        e_text = etree.Element('text')
        e_textPath = etree.SubElement(e_text, 'textPath', {
            xlink_href: '#' + e_id,
        })
        fontsize = scale_to_fontsize(options.pop("scale", "m"))
        e_text.set('style', "font-size:%s" % (fontsize))
        e_textPath.text = options.pop('text', '')
        if not e_textPath.text:
            errormsg('line label without text')
        getlayer('line', type).insert(0, e_text)

    # for areas
    if type == 'border' and 'id' in options:
        this.borders[options['id']] = e

    set_props(e, 'line', type_subtype, options)
    getlayer('line', type).insert(0, e)


def parse_point(a):
    options = parse_options(a[4:])
    type = a[3].split(':')[0]

    as_text = False
    if type in text_keys_input:
        key = text_keys_input[type]
        if key in options:
            as_text = True
    if as_text:
        e = etree.Element('text')
        y = 0
        for line in options[key].split('<br>'):
            t = etree.SubElement(e, 'tspan', {sodipodi_role: 'line', 'x': '0', 'y': '%dem' % (y)})
            t.text = line
            y += 1
        del options[key]
        fontsize = scale_to_fontsize(options.pop("scale", "m"))
        align = options.pop('align', '')
        align = align_shortcuts.get(align, align)
        textanchor = align2anchor.get(align.strip('tb'), align2anchor_default_in)
        baseline = align2baseline.get(align.strip('lr'), align2baseline_default_in)
        e.set('style', "font-size:%s;text-anchor:%s;text-align:%s;dominant-baseline:%s" % (fontsize,
                                                                                           textanchor, textanchor, baseline))
        e.set(xml_space, 'preserve')
    elif type in this.point_symbols:
        e = etree.Element('use')
        e.set(xlink_href, "#point-" + type)
        if type == "station" and th2pref.lock_stations:
            e.set(sodipodi_insensitive, "true")
    else:
        e = etree.Element('circle')
        e.set('r', '2')
        color = point_colors.get(type, "blue")
        e.set('style', f'stroke:none;fill:{color};fill-opacity:0.8')

    # position and orientation
    transform = 'translate(%s,%s)' % tuple(flipY(a[1:3]))
    if 'orientation' in options:
        transform += ' rotate(%s)' % (options['orientation'])
        del options['orientation']
    e.set('transform', transform)

    this.id_count += 1
    e.set('id', 'point_%s_%d' % (type, this.id_count))

    set_props(e, 'point', a[3], options)
    getlayer('point', type).insert(0, e)


def parse_input(a):
    assert a[0] == "input"
    assert len(a) == 2
    this.file_stack.append(FileRecord(a[1]))

    e = etree.Element('g')
    e.set(inkscape_groupmode, "layer")
    e.set(inkscape_label, ' '.join(a))
    e.set(therion_role, "input")

    this.getcurrentlayer().append(e)
    this.layer_stack.append(e)


parsedict = {
    '##XTHERION##': parse_XTHERION,
    '##INKSCAPE##': parse_INKSCAPE,
    'scrap': parse_scrap,
    'line': parse_line,
    'point': parse_point,
    'encoding': parse_encoding,
    'area': parse_area,
    'map': parse_BLOCK2COMMENT,
    'centerline': parse_BLOCK2COMMENT,
    'centreline': parse_BLOCK2COMMENT,
    'input': parse_input,
}


def main():
    th2pref_reload()

    with open(get_template_svg_path()) as template:
        this.document = etree.parse(template)

    this.root = this.document.getroot()
    this.layer_stack = [this.root]

    # save input prefs to file
    th2pref_store_to_xml(this.root)

    ids = this.root.xpath('/svg:svg/svg:defs/*[starts-with(@id, "point-")]/@id', namespaces=inkex.NSS)
    this.point_symbols = [id[6:] for id in ids]

    ids = this.root.xpath('/svg:svg/svg:defs/*[starts-with(@id, "LPE-")]/@id', namespaces=inkex.NSS)
    this.LPE_symbols = [id[4:] for id in ids]

    populate_legend()

    # open th2 file
    this.file_stack.append(FileRecord(th2pref.argv[0]))

    while True:
        line = f_readline()
        if len(line) == 0:
            break

        a = line.split()

        if len(a) == 0:
            continue

        parse(a)

    assert not this.file_stack

    if this.doc_width and this.doc_height:
        this.root.set('width', f"{this.doc_width * this.m_per_dots}cm")
        this.root.set('height', f"{this.doc_height * this.m_per_dots}cm")
        this.root.set('viewBox', f"{this.doc_x} {-this.doc_y} {this.doc_width} {this.doc_height}")

    e = this.root.xpath('svg:g[@id="layer-scan"]', namespaces=inkex.NSS)[0]
    e.set('transform', ' scale(1,-1) scale(%f)' % (1. / th2pref.basescale))

    e = this.root.xpath('svg:g[@id="layer-legend"]', namespaces=inkex.NSS)[0]
    e.set('transform', f'translate({this.doc_x} {-this.doc_y})')

    # scrap0:
    # Mostly obsolete, we currently don't populate it.
    # Keep it when opening an empty file.
    e = this.root.xpath('svg:g[@id="layer-scrap0"]', namespaces=inkex.NSS)[0]
    others = this.root.xpath('/svg:svg/g[not(@therion:role="none")]', namespaces=inkex.NSS)
    if len(e) == 0 and others:
        this.root.remove(e)
    else:
        e.set(therion_role, "scrap")

    out = sys.stdout.buffer
    this.document.write(out)


if __name__ == "__main__":
    main()
