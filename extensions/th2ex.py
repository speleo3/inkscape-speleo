'''
Copyright (C) 2008 Thomas Holder, http://sf.net/users/speleo3/
Distributed under the terms of the GNU General Public License v2 or later

Stuff for parsing and annotating therion 2D files, using inkscape.

Annotations are stored in inkscape:label attribute. Exceptions are:
 * Scraps, their therion-id is stored in inkscape:label, other information
   is stored in therion:role and therion:options
 * For stations, if they are annotated with therion:role/type and inkscape:label
   holds a single words, this is considered as the station name, for
   compatibility with previous version of Inkscape *.3d import filter.

Elements with role annotation "none" are excluded from export.

Text alignment guess for export is not perfect, but covers the most use cases.
'''

import argparse
import sys
from lxml import etree
from pathlib import Path
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Optional,
    Sequence,
    Tuple,
    TypeVar,
    Union,
)
import functools
import os
import math
import re
import inkex
import warnings

warnings.simplefilter("ignore", DeprecationWarning)

_StrOrFloat = TypeVar("_StrOrFloat", bound=Union[str, float])
ParsedPath = List[Tuple[str, Sequence[_StrOrFloat]]]

EtreeElement = etree._Element
BBoxType = List[float]
AffineType = List[List[float]]

StyleDict = Dict[str, str]

OptionValue = Any
OptionsDict = Dict[str, OptionValue]


def distance(lhs: Sequence[float], rhs: Sequence[float]) -> float:
    '''
    Euclidean distance
    '''
    return sum((a - b)**2 for (a, b) in zip(lhs, rhs))**0.5


METERS_PER = {
    'in': 0.0254,
    'inch': 0.0254,
    'inches': 0.0254,
    'cm': 0.01,
    'centimeter': 0.01,
    'centimeters': 0.01,
    'm': 1.0,
    'meter': 1.0,
    'meters': 1.0,
    'yd': 0.9144,
    'yard': 0.9144,
    'yards': 0.9144,
    'ft': 0.3048,
    'feet': 0.3048,
    'feets': 0.3048,
}


def xpath_elems(node: Union[etree._ElementTree, EtreeElement], elemexpr: str):
    elems: Sequence[EtreeElement] = node.xpath(elemexpr, namespaces=inkex.NSS)  # type: ignore[assignment]
    return elems


def xpath_attrs(node: Union[etree._ElementTree, EtreeElement], attrexpr: str):
    attrs: Sequence[str] = node.xpath(attrexpr, namespaces=inkex.NSS, smart_strings=False)  # type: ignore[assignment]
    return attrs


def parse_scrap_scale_m_per_dots(scale: str) -> float:
    """
    Parse the value of a scrap's `-scale` option
    """
    if scale.startswith("["):
        assert scale.endswith("]")
        scale = scale[1:-1]
    dots = 1.0
    unit = "m"
    a = scale.split()
    if len(a) in (1, 2, 3):
        if len(a) == 3:
            dots = float(a.pop(0))
        reality_units = float(a[0])
        if len(a) == 2:
            unit = a[1]
    elif len(a) in (8, 9):
        dots = distance((float(a[0]), float(a[1])), (float(a[2]), float(a[3])))
        reality_units = distance((float(a[4]), float(a[5])), (float(a[6]), float(a[7])))
        if len(a) == 9:
            unit = a[8]
    else:
        raise ValueError(a)
    meters = reality_units * METERS_PER[unit]
    return meters / dots


# some prefs
class _th2pref:
    def __init__(self):
        self.howtostore = 'inkscape_label'
        self.textonpath = True
        self.image_inkscape = False
        self.basescale = 1.0
        self._scale_real_m_per_th2 = 0.0  # from scrap or xvi
        self.xyascenter = True

    def _get_u(self) -> float:
        if self.basescale <= 1:
            return 14
        elif self.basescale <= 2:
            return 12
        elif self.basescale <= 5:
            return 10
        else:
            return 7

    @property
    def scale_paper_cm_per_uu(self) -> float:
        """
        Print/paper centimeters per user units.

        This is the viewBox scaling factor.
        """
        # 9 is (maybe?) for 90dpi
        # 254 is (maybe?) for cm/100in
        # 12 is default u at 1:200
        return 9 / 254 * self._get_u() / 12

    @property
    def scale_real_per_paper(self) -> float:
        """
        Scaling factor from paper to real world.

        This is the map scale.
        """
        return self.basescale * 100

    @property
    def scale_th2_per_uu(self) -> float:
        """
        Scaling factor from th2 "pixels" to SVG user units.
        """
        return self.basescale * self._secondary_basescale

    def set_scale_uu_per_th2(self, value: float):
        self.set_basescale(value / self._secondary_basescale)

    def set_basescale(self, value: float):
        self.basescale = value
        get_fonts_setup_default.cache_clear()

    @property
    def scale_real_m_per_th2(self) -> float:
        """
        Scaling factor from th2 "pixels" to real world meters (scrap scale).

        Therion Book: "meters per drawing unit"
        """
        return self._scale_real_m_per_th2 or self.scale_paper_cm_per_uu

    def set_scale_real_m_per_th2(self, value: float):
        self._scale_real_m_per_th2 = value

    @property
    def _secondary_basescale(self) -> float:
        """
        Same as scale_th2_per_uu at 1:100
        """
        return self.scale_paper_cm_per_uu / self.scale_real_m_per_th2


# fix Python 3 mappingproxy issue
th2pref = _th2pref()


# load prefs from file


def th2pref_load_from_xml(root: EtreeElement):
    x = root.get(therion_basescale)
    if x is not None:
        th2pref.set_basescale(float(x))
    x = root.get(therion_scrapscale)
    if x is not None:
        th2pref.set_scale_real_m_per_th2(float(x))
    th2pref.howtostore = root.get(therion_howtostore, th2pref.howtostore)

# store prefs


def th2pref_store_to_xml(root: EtreeElement):
    root.set(therion_basescale, str(th2pref.basescale))
    root.set(therion_scrapscale, str(th2pref.scale_real_m_per_th2))
    root.set(therion_howtostore, th2pref.howtostore)


# prepare names with namespace
inkex.NSS['therion'] = 'http://therion.speleo.sk/therion'
svg_svg = inkex.addNS('svg', 'svg')
svg_use = inkex.addNS('use', 'svg')
svg_circle = inkex.addNS('circle', 'svg')
svg_rect = inkex.addNS('rect', 'svg')
svg_path = inkex.addNS('path', 'svg')
svg_line = inkex.addNS('line', 'svg')
svg_polyline = inkex.addNS('polyline', 'svg')
svg_polygon = inkex.addNS('polygon', 'svg')
svg_text = inkex.addNS('text', 'svg')
svg_textPath = inkex.addNS('textPath', 'svg')
svg_tspan = inkex.addNS('tspan', 'svg')
svg_g = inkex.addNS('g', 'svg')
svg_title = inkex.addNS('title', 'svg')
svg_ellipse = inkex.addNS('ellipse', 'svg')
svg_image = inkex.addNS('image', 'svg')
svg_symbol = inkex.addNS('symbol', 'svg')
therion_role = inkex.addNS('role', 'therion')
therion_type = inkex.addNS('type', 'therion')
therion_options = inkex.addNS('options', 'therion')
therion_area_zoom_to = inkex.addNS('area-zoom-to', 'therion')
therion_basescale = inkex.addNS('basescale', 'therion')
therion_scrapscale = inkex.addNS('scrapscale', 'therion')
therion_howtostore = inkex.addNS('howtostore', 'therion')
therion_xvi_dx = inkex.addNS('xvi-dx', 'therion')
therion_xvi_dy = inkex.addNS('xvi-dy', 'therion')
xlink_href = inkex.addNS('href', 'xlink')
xml_space = inkex.addNS('space', 'xml')
inkscape_groupmode = inkex.addNS('groupmode', 'inkscape')
inkscape_label = inkex.addNS('label', 'inkscape')
inkscape_original_d = inkex.addNS('original-d', 'inkscape')
inkscape_path_effect = inkex.addNS('path-effect', 'inkscape')
sodipodi_cx = inkex.addNS('cx', 'sodipodi')
sodipodi_cy = inkex.addNS('cy', 'sodipodi')
sodipodi_role = inkex.addNS('role', 'sodipodi')
sodipodi_insensitive = inkex.addNS('insensitive', 'sodipodi')
sodipodi_nodetypes = inkex.addNS('nodetypes', 'sodipodi')


def title_node(parent: EtreeElement) -> EtreeElement:
    title = parent.find(svg_title)
    if title is None:
        title = etree.SubElement(parent, svg_title)
        title.text = ""
        # if <title> is last child of <text>, Inkscape screws up when
        # appending lines and inserts <title> instead of <tspan> elements.
        parent.insert(0, title)
    return title


# TODO same as th2_output.Th2Output.get_style_nocascade
def get_style(node: EtreeElement) -> StyleDict:
    from inkex0 import simplestyle
    return simplestyle.parseStyle(node.get('style', ''))


def get_style_attr(node: EtreeElement, style: Optional[StyleDict], key: str, d=''):
    if style is None:
        style = get_style(node)
    d = node.get(key, d)
    return style.get(key, d)

##########################################
# station name stuff


def name_survex2therion(name: str) -> str:
    x = name.split('.')
    if len(x) == 1:
        return name
    return x[-1] + '@' + '.'.join(reversed(x[:-1]))


def name_therion2survex(name: str, prefix=''):
    x = name.replace('@', '.', 1).split('.')
    return prefix + '.'.join(reversed(x))

##########################################
# options stuff


option_value_count = {
    'attr': 2,
    'author': 2,
    'context': 2,
    'text': 1,
    'value': 1,
}

repeatable_options = [
    'attr',
    'author',
]

# legacy
two_arg_keys = ['attr', 'context', 'author']
needquote = re.compile(r'[^-._@a-z0-9]', re.I)

RE_MAYBEQUOTED = re.compile(r'\[.*?\]|"(?:[^"]|"")*"(?!")|\S+')


def is_numeric(s: str) -> bool:
    try:
        float(s)
    except Exception:
        return False
    return True


def maybe_key(s: str) -> bool:
    return re.match(r'-\S+$', s) is not None and not is_numeric(s)


def splitquoted(ustr: str, comments=False):
    '''
    Only uses double quotes, not single quotes.

    Returns "[foo bar]" as one string.
    '''
    assert not comments
    assert not isinstance(ustr, bytes)

    def popquotes(s: str) -> str:
        if s.startswith('"') and s.endswith('"'):
            return s[1:-1].replace('""', '"')
        return s

    return [popquotes(v) for v in RE_MAYBEQUOTED.findall(ustr)]


def quote(value: str) -> str:
    '''
    Add quotes around value, if needed
    '''
    assert isinstance(value, str)
    if not value:
        return '""'
    if needquote.search(value) is None:
        return value
    if value.startswith('[') and value.endswith(']'):
        return value
    return '"' + value.replace('"', '""') + '"'


def _skipunexpected(s):
    inkex.errormsg(s)


def parse_options(a: Union[str, Sequence[str]]):
    '''
    Parses therion options string or sequence of strings.

    Known issues:
     * detection of zero-arg-keys is heuristical
    '''
    options: OptionsDict = {}
    if not isinstance(a, str):
        a = ' '.join(a)
    a = splitquoted(a)
    n = len(a)
    i = 0
    while i < n:
        try:
            assert a[i][0] == '-'
        except (AssertionError, IndexError):
            _skipunexpected('assertion failed on ' + a[i])
            return options

        key = a[i][1:]
        i += 1

        value_count = option_value_count.get(key)

        if value_count is None:
            value_count = 0
            while (value_count + i) != n and not maybe_key(a[value_count + i]):
                value_count += 1

        value: OptionValue
        if value_count == 0:
            value = True
        elif value_count == 1:
            value = a[i]
        else:
            value = tuple(a[i:i + value_count])

        if key in repeatable_options:
            options.setdefault(key, []).append(value)
        else:
            options[key] = value

        i += value_count

    return options


def key_options_item(item: Tuple[str, OptionValue]) -> tuple:
    """
    Sort key for options. Alphabetic with some exceptions.
    """
    if item[0] == 'id':
        return '0' + item[0], item[1]
    if item[0] == 'close':
        return '1' + item[0], item[1]
    if item[0] == 'orientation':  # point
        return '1' + item[0], item[1]
    if item[0] == 'projection':  # scrap
        return '1' + item[0], item[1]
    return item


# TODO this fails for -text "[foo bar]" (will be -text [foo bar], no quotes)
def format_options(options: OptionsDict) -> str:
    '''
    Format options dictionary as therion options string.
    '''
    return ' '.join(format_options_iter(options))


def format_option(key: str, value: OptionValue, *, prefix="-") -> str:
    value_count: Union[int, None]

    # legacy (might come from SVG file)
    for two_arg_key in two_arg_keys:
        if key.startswith(two_arg_key + '-'):
            inkex.errormsg(f"Legacy two-arg key: {key}")
            ret = '-' + key.replace('-', ' ', 1)
            value_count = 1
            break
    else:
        ret = prefix + key
        value_count = option_value_count.get(key)

    if value is True:
        assert value_count in (None, 0)
    elif isinstance(value, (tuple, list)):
        # multi-value string
        assert value_count in (None, len(value))
        ret += ''.join(' ' + quote(v) for v in value)
    elif not isinstance(value, str):
        # number
        assert value_count in (None, 1)
        ret += ' ' + str(value)
    elif value_count == 0:
        _skipunexpected('error: -{} must have value True, got {}'.format(key, repr(value)))
    elif value_count in (None, 1):
        ret += ' ' + quote(value)
    elif len(splitquoted(value)) == value_count:
        # pre-quoted multi-value string
        ret += ' ' + value
    else:
        _skipunexpected('error: -{} needs {} values, got {}'.format(key, value_count, repr(value)))
        ret += ' <error>' * (value_count or 1)

    return ret


def format_options_iter(options: OptionsDict, *, prefix="-"):
    for key, value in sorted(options.items(), key=key_options_item):
        if key in repeatable_options and isinstance(value, list):
            for v in value:
                yield format_option(key, v, prefix=prefix)
        else:
            yield format_option(key, value, prefix=prefix)


def maybe_point(node: EtreeElement) -> bool:
    return node.tag == svg_text or \
        node.tag == svg_use or \
        node.tag == svg_circle


def maybe_line(node: EtreeElement) -> bool:
    return node.tag == svg_path or \
        node.tag == svg_line or \
        node.tag == svg_polyline or \
        node.tag == svg_rect or \
        node.tag == svg_polygon


def is_closed_line(node: EtreeElement) -> bool:
    if node.tag in (svg_polygon, svg_rect):
        return True
    d = node.get('d', '')
    return d.rstrip()[-1:].lower() == 'z'


def set_props(e, role: str, type: str, options: Optional[OptionsDict] = None):
    '''
    Annotate SVG element with role, type and options.
    '''
    if options is None:
        options = {}
    assert role != 'scrap', 'Cannot use set_props for scraps'
    options_str = format_options(options)
    if th2pref.howtostore != 'therion_attribs':
        for key in [therion_role, therion_type, therion_options]:
            if key in e.attrib:
                del e.attrib[key]
    if th2pref.howtostore in ['inkscape_label', 'title']:
        if role == '':
            role = '_unknown_'
        if type == '':
            type = 'u:unknown'
        label = "%s %s %s" % (role, type, options_str)
        if th2pref.howtostore == 'inkscape_label':
            e.set(inkscape_label, label)
        else:
            title_node(e).text = label
    elif th2pref.howtostore == 'therion_attribs':
        e.set(therion_role, role)
        e.set(therion_type, type)
        e.set(therion_options, options_str)
    else:
        raise Exception('unknown th2pref.howtostore')


def get_props(e: EtreeElement) -> Tuple[str, str, OptionsDict]:
    '''
    Get list of (str role, str type, dict options) from annotated SVG element.
    '''
    assert e.get(therion_role) != 'scrap', 'Cannot use get_props for scraps'

    if th2pref.howtostore == 'inkscape_label':
        label = e.get(inkscape_label) or title_node(e).text or ''
    else:
        label = title_node(e).text or e.get(inkscape_label) or ''

    role, type, optionsstr = (label.split(None, 2) + [''] * 3)[:3]
    role = e.get(therion_role, role)
    type = e.get(therion_type, type)
    optionsstr = e.get(therion_options, optionsstr)
    options = parse_options(optionsstr)
    if role == '':
        if maybe_point(e):
            role = 'point'
        elif maybe_line(e):
            role = 'line'
    if type == '':
        type = 'u:unknown'
        # fallback values
        if role == 'line':
            fill = get_style_attr(e, None, 'fill', 'none')
            if fill != 'none' and is_closed_line(e):
                type = fill2type.get(fill.lower(), 'u:area')
        elif role == 'point':
            if e.tag == svg_text:
                type = 'label'
            elif e.tag == svg_use:
                # guess from reference id
                m = re.match(r'#point-(.*)', e.get(xlink_href, ''))
                if m is not None:
                    type = m.group(1)
    return role, type, options


##########################################
# property translation stuff

scale_aliases = {
    "L": "l",
    "M": "m",
    "S": "s",
    "XL": "xl",
    "XS": "xs",
    "huge": "xl",
    "large": "l",
    "normal": "m",
    "small": "s",
    "tiny": "xs",
}

align_shortcuts = {
    'center': 'c',
    'top': 't',
    'bottom': 'b',
    'left': 'l',
    'right': 'r',
    'top-left': 'tl',
    'top-right': 'tr',
    'bottom-left': 'bl',
    'bottom-right': 'br',
}

align2anchor_default_in = 'middle'
align2anchor_default_out = 'start'
align2anchor = {
    'l': 'end',
    'r': 'start',
}

align2baseline_default_in = 'middle'
align2baseline_default_out = 'auto'
align2baseline = {
    't': 'auto',  # 'alphabetic'
    'b': 'hanging',
}

text_keys = {
    'label': 'text',
    'remark': 'text',
    'station-name': 'text',

    'dimensions': 'value',
    'height': 'value',
    'passage-height': 'value',
    'altitude': 'value',
    'date': 'value',
}
text_keys_input = text_keys
text_keys_output = {
    'station': 'name',
    'section': 'scrap',
}
text_keys_output.update(text_keys)

# line fill to type mapping
fill2type = {
    'blue': 'u:water',
    '#0000ff': 'u:water',
    'yellow': 'u:sand',
    '#ffff00': 'u:sand',
}

tag2style = {
    "it": {
        "font-family": "serif",
        "font-style": "italic",
    },
    "si": {
        "font-family": "sans-serif",
        "font-style": "italic",
    },
    "rm": {
        "font-family": "serif",
    },
    "bf": {
        "font-weight": "bold",
    },
    "ss": {
        "font-family": "sans-serif",
    },
}

##########################################
# font stuff

# fonts-setup defaults in "pt" for scales up to 1:N
fonts_setup_defaults = {
    100: {'xs': 8, 's': 10, 'm': 12, 'l': 16, 'xl': 24},
    200: {'xs': 7, 's': 8, 'm': 10, 'l': 14, 'xl': 20},
    500: {'xs': 6, 's': 7, 'm': 8, 'l': 10, 'xl': 14},
    math.inf: {'xs': 5, 's': 6, 'm': 7, 'l': 8, 'xl': 10},
}


@functools.lru_cache(maxsize=None)
def get_fonts_setup_default(map_scale: int = 0):
    """
    Get equivalents for the "fonts-setup" layout command default value.
    """
    if not map_scale:
        map_scale = round(th2pref.scale_real_per_paper)
    key = min((s for s in fonts_setup_defaults if (map_scale <= s)),
              key=lambda s: s - map_scale)
    return fonts_setup_defaults[key]


##########################################
# geom stuff


def det(mat: AffineType) -> float:
    return mat[0][0] * mat[1][1] - mat[0][1] * mat[1][0]


def descrim(mat: AffineType) -> float:
    return math.sqrt(abs(det(mat)))


def inverse(mat: AffineType) -> AffineType:
    d: AffineType = [[1, 0, 0], [0, 1, 0]]
    determ = det(mat)
    if abs(determ) > 0.0001:
        ideterm = 1.0 / determ
        d[0][0] = mat[1][1] * ideterm
        d[0][1] = -mat[0][1] * ideterm
        d[1][0] = -mat[1][0] * ideterm
        d[1][1] = mat[0][0] * ideterm
        d[0][2] = -mat[0][2] * d[0][0] - mat[1][2] * d[1][0]
        d[1][2] = -mat[0][2] * d[0][1] - mat[1][2] * d[1][1]
    return d


def parsePath(d: str) -> ParsedPath[float]:
    '''
    Parse line and replace quadratic bezier segments and arcs by
    cubic bezier segments.
    '''
    from inkex0 import simplepath
    p = simplepath.parsePath(d)
    if any(cmd not in 'MLCZ' for (cmd, params) in p):
        from inkex0 import cubicsuperpath
        csp = cubicsuperpath.CubicSuperPath(p)
        p = cubicsuperpath.unCubicSuperPath(csp)
    return p


def parseViewBox(viewBox: Union[str, Sequence[float]], width: Union[str, float],
                 height: Union[str, float]) -> AffineType:
    '''
    Returns the 2x3 transformation matrix that a viewBox defines
    '''
    if isinstance(viewBox, str):
        viewBox = [float(i) for i in viewBox.split()]
    return [[float(width) / viewBox[2], 0, -viewBox[0]], [0, float(height) / viewBox[3], -viewBox[1]]]

######################################
# IO stuff


def find_in_pwd(filename, path: Iterable[str] = ()):
    """
    Look up filename first in $PWD, then (if not found) in `path`.
    """
    for dirname in ['', os.getcwd()] + list(path):
        candidate = os.path.join(dirname, filename)
        if os.path.exists(candidate):
            return candidate
    raise IOError("Can't find file '" + filename + "'")


def get_template_svg_path() -> Path:
    """
    Get the filename of the th2_template.svg file.
    """
    return Path(__file__).parent / 'th2_template.svg'


######################################
# inkex (and similar) fixed or enhanced functions

PX_PER_IN = 96.0
PX_PER_CM = PX_PER_IN / 2.54
UUCONV = {
    'in': PX_PER_IN,
    'pt': (4.0 / 3.0),
    'px': 1.0,
    'mm': PX_PER_CM / 10,
    'cm': PX_PER_CM,
    'm': PX_PER_CM * 1e2,
    'km': PX_PER_CM * 1e5,
    'pc': 16.0,
    'yd': 3456.0,
    'ft': 1152.0,
}


def convert_unit(value: Union[str, Tuple[float, str]], to_unit: str) -> float:
    """
    Returns value in requested unit

    >>> convert_unit("3m", "m") == 3.0
    >>> convert_unit("3m", "cm") == 300.0
    """
    assert to_unit in UUCONV
    val: Union[float, str]

    if isinstance(value, tuple):
        val, unit = value
    else:
        m = re.fullmatch(r'(.*?)([a-z]*)', value.rstrip())
        assert m is not None
        val, unit = m.groups()

    try:
        return float(val) * UUCONV[unit or 'px'] / UUCONV[to_unit]
    except (ValueError, KeyError):
        return 0.0


class Th2Effect:
    document: etree._ElementTree

    def __init__(self) -> None:
        self.arg_parser = argparse.ArgumentParser()
        self.arg_parser.add_argument("--id", action="append", dest="ids")
        self.arg_parser.add_argument("--selected-nodes")
        self.arg_parser.add_argument("--output")
        self.arg_parser.add_argument("input_file", nargs="?")

    @property
    def current_layer(self):
        layerattr = xpath_attrs(self.document, '//sodipodi:namedview/@inkscape:current-layer')
        if layerattr:
            layer = xpath_elems(self.document, f'//svg:g[@id="{layerattr[0]}"]')
            if layer:
                return layer[0]
        return self.document.getroot()

    def _get_selected(self) -> Dict[str, EtreeElement]:
        selected = {}
        if self.options.ids:
            ids = set(self.options.ids)
            for node in xpath_elems(self.document, "//*[@id]"):
                eid = node.get("id")
                if eid in ids:
                    selected[eid] = node
        return selected

    def run(self, args=None) -> None:
        self.options = self.arg_parser.parse_args(args)

        if self.options.input_file and self.options.input_file != "-":
            with open(self.options.input_file, "rb") as handle:
                self.document = etree.parse(handle)
        else:
            self.document = etree.parse(sys.stdin.buffer)

        self.selected = self._get_selected()
        self.effect()
        self.output()

    def effect(self) -> None:
        pass

    def get_output_bytes(self) -> bytes:
        return etree.tostring(self.document, encoding="utf-8")

    def output(self) -> None:
        xmlstr = self.get_output_bytes()
        if self.options.output and self.options.output != "-":
            with open(self.options.output, "wb") as handle:
                handle.write(xmlstr)
        else:
            sys.stdout.buffer.write(xmlstr)

    def getElementById(self, eid: str) -> Optional[EtreeElement]:
        elements = xpath_elems(self.document, f"//*[@id='{eid}']")
        if not elements:
            return None
        if len(elements) > 1:
            inkex.errormsg(f"{len(elements)} with id '{eid}'")
        return elements[0]

    @staticmethod
    def unittouu(string):
        """Returns userunits given a string representation of units in another system"""
        m = re.match(r'((?:[-+]?[0-9]+(?:\.[0-9]*)?|[-+]?\.[0-9]+)(?:[eE][-+]?[0-9]+)?)(.*)$', string)
        if m is None:
            return 0.0

        val, unit = m.groups()

        try:
            unitfactor = UUCONV[unit.strip()]
        except KeyError:
            unitfactor = 1.0

            if unit:
                inkex.errormsg("unittouu: unknown unit: " + unit)

        return float(val) * unitfactor

    @staticmethod
    def uutounit(val, unit):
        return val / UUCONV[unit]

    @property
    def r2d(self) -> list:
        """
        Transformation from SVG user units to th2 drawing units.
        """
        return [
            [th2pref.scale_th2_per_uu, 0.0, 0.0],
            [0.0, -th2pref.scale_th2_per_uu, 0.0],
        ]

    bbox_cache: Dict[EtreeElement, Optional[BBoxType]] = {}
    i2d_cache: Dict[EtreeElement, AffineType] = {}

    def i2d_affine(self, node: EtreeElement, use_cache: bool = True) -> AffineType:
        '''
        Get the "item to th2 drawing units" transformation matrix.

        Note: use_cache showed 20% speed improvement for a big SVG document
        '''
        if use_cache and node in self.i2d_cache:
            return self.i2d_cache[node]

        from inkex0 import simpletransform
        m2 = simpletransform.parseTransform(node.get('transform'))

        parent = node.getparent()
        if parent is not None:
            m1 = self.i2d_affine(parent, use_cache)
            m2 = simpletransform.composeTransform(m1, m2)
        else:
            m2 = simpletransform.composeTransform(self.r2d, m2)

        self.i2d_cache[node] = m2
        return m2

    def node_center(self, node: EtreeElement) -> Sequence[float]:
        '''
        Get the bounding box center, or for some particular cases x/y (like
        for text to support alignment). Does not take the "transform" attibute
        into account.
        '''
        # Text and Clones
        if th2pref.xyascenter and node.tag in [svg_text, 'text', svg_use, 'use']:
            return [self.unittouu(node.get(key, '0')) for key in ('x', 'y')]
        # Circles
        if 'cx' in node.attrib:
            return [self.unittouu(node.get(key, '0')) for key in ('cx', 'cy')]
        if sodipodi_cx in node.attrib:
            return [self.unittouu(node.get(key, '0')) for key in (sodipodi_cx, sodipodi_cy)]
        # Others
        bbox = self.compute_bbox(node, False)
        if bbox is None:
            inkex.errormsg('Warning: bbox is None, id=' + node.get('id', 'NONE'))
            return [0, 0]
        return [(bbox[0] + bbox[1]) * 0.5, (bbox[2] + bbox[3]) * 0.5]

    def compute_bbox(self,
                     node: EtreeElement,
                     transform=True,
                     use_cache=False) -> Optional[BBoxType]:
        '''
        Compute the bounding box of a element in its parent coordinate system,
        or in its own coordinate system if "transform" is False.

        Uses a cache to not compute the bounding box multiple times for
        elements like referenced symbols.

        Returns [xmin, xmax, ymin, ymax]

        Enhanced version of simpletransform.computeBBox()

        Warning: Evaluates "transform" attribute for symbol tags, which is
        wrong according to SVG spec, but matches Inkscape's behaviour.
        '''
        from inkex0 import cubicsuperpath
        from inkex0.simpletransform import boxunion, parseTransform, applyTransformToPath, formatTransform
        from inkex0.simpletransform import refinedBBox

        d = None
        recurse = False
        node_bbox = None

        if transform:
            transformattr = node.get('transform') or ''
        else:
            transformattr = ''

        if use_cache and node in self.bbox_cache:
            node_bbox = self.bbox_cache[node]
        elif node.tag in [svg_use, 'use']:
            x, y = float(node.get('x', 0)), float(node.get('y', 0))
            refid = node.get(xlink_href)
            if refid is None or not refid.startswith("#"):
                return None
            refnode = self.getElementById(refid[1:])

            if refnode is None:
                return None

            parse_viewbox_args = (
                refnode.get('viewBox', ''),
                node.get('width', ''),
                node.get('height', ''),
            )
            if all(parse_viewbox_args):
                mat = parseViewBox(*parse_viewbox_args)
                transformattr += ' ' + formatTransform(mat)

            refbbox = self.compute_bbox(refnode, True, True)
            if refbbox is not None:
                node_bbox = [refbbox[0] + x, refbbox[1] + x, refbbox[2] + y, refbbox[3] + y]

        elif node.get('d'):
            d = node.get('d', '')
        elif node.get('points'):
            d = 'M' + node.get('points', '')
        elif node.tag in [svg_rect, 'rect', svg_image, 'image']:
            d = 'M' + node.get('x', '0') + ',' + node.get('y', '0') + \
                'h' + node.get('width', '99') + 'v' + node.get('height', '99') + \
                'h-' + node.get('width', '99')
        elif node.tag in [svg_line, 'line']:
            d = 'M' + node.get('x1', '0') + ',' + node.get('y1', '0') + \
                ' ' + node.get('x2', '99') + ',' + node.get('y2', '99')
        elif node.tag in [svg_circle, 'circle', svg_ellipse, 'ellipse']:
            rxs = node.get('r', '')
            if rxs:
                rys = rxs
            else:
                rxs = node.get('rx', '99')
                rys = node.get('ry', '99')
            rx, ry = float(rxs), float(rys)
            cx = float(node.get('cx', '0'))
            cy = float(node.get('cy', '0'))
            node_bbox = [cx - rx, cx + rx, cy - ry, cy + ry]
        elif node.tag in [svg_text, 'text', svg_tspan, 'tspan']:
            # very rough estimate of text bounding box
            xs = node.get('x', '0').split()
            ys = node.get('y', '0').split()
            if len(xs) == 1 and len(ys) > 1:
                xs = xs * len(ys)
            elif len(ys) == 1 and len(xs) > 1:
                ys = ys * len(xs)
            d = 'M' + ' '.join('%f' % self.unittouu(c) for xy in zip(xs, ys) for c in xy)
            recurse = True
        elif node.tag in [svg_g, 'g', svg_symbol, 'symbol', svg_svg, 'svg']:
            recurse = True

        if d is not None:
            p = cubicsuperpath.parsePath(d)
            node_bbox = refinedBBox(p)

        if recurse:
            for child in node:
                child_bbox = self.compute_bbox(child, True, use_cache)
                if node_bbox is None:
                    node_bbox = child_bbox
                    continue
                node_bbox = boxunion(child_bbox, node_bbox)

        self.bbox_cache[node] = node_bbox

        if transformattr.strip() != '' and node_bbox is not None:
            mat = parseTransform(transformattr)
            p = [[[
                [node_bbox[0], node_bbox[2]],
                [node_bbox[0], node_bbox[3]],
                [node_bbox[1], node_bbox[2]],
                [node_bbox[1], node_bbox[3]],
            ]]]
            applyTransformToPath(mat, p)
            fxs, fys = zip(*p[0][0])
            node_bbox = [min(fxs), max(fxs), min(fys), max(fys)]

        return node_bbox
