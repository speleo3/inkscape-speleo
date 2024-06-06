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

from __future__ import print_function
from __future__ import absolute_import

try:
	basestring
except NameError:
	basestring = str

from lxml import etree
from typing import Sequence
import sys, os, math, re, optparse
import inkex
import warnings

warnings.simplefilter("ignore", DeprecationWarning)

PY3 = sys.version_info[0] > 2


def as_unicode(s):
	return s.decode('utf-8') if isinstance(s, bytes) else s


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


def parse_scrap_scale_m_per_dots(scale: str) -> float:
	"""
	Parse the value of a scrap's `-scale` option
	"""
	if scale.startswith("["):
		assert scale.endswith("]")
		scale = scale[1:-1]
	dots = 1
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
class th2pref:
	def __init__(self):
		self.howtostore = 'inkscape_label'
		self.textonpath = True
		self.image_inkscape = False
		self.basescale = 1.0
		self.xyascenter = True

# fix Python 3 mappingproxy issue
th2pref = th2pref()


class InkOption(optparse.Option):
    TYPES = optparse.Option.TYPES + ("inkbool", )
    TYPE_CHECKER = dict(optparse.Option.TYPE_CHECKER)
    TYPE_CHECKER["inkbool"] = lambda _1, _2, v: str(v).capitalize() == "True"


# command line options and hook to th2pref
oparser = optparse.OptionParser(option_class=InkOption)
oparser.defaults = th2pref.__dict__
def th2pref_reload():
	_values, th2pref.argv = oparser.parse_args()
	oparser.set_defaults(**_values.__dict__)

# load prefs from file
def th2pref_load_from_xml(root):
	x = root.get(therion_basescale)
	if x is not None:
		th2pref.basescale = float(x)
	th2pref.howtostore = root.get(therion_howtostore, th2pref.howtostore)

# store prefs
def th2pref_store_to_xml(root):
	root.set(therion_basescale, '%.4f' % th2pref.basescale)
	root.set(therion_howtostore, th2pref.howtostore)

# prepare names with namespace
inkex.NSS['therion'] = 'http://therion.speleo.sk/therion'
svg_svg              = inkex.addNS('svg', 'svg')
svg_use              = inkex.addNS('use', 'svg')
svg_circle           = inkex.addNS('circle', 'svg')
svg_rect             = inkex.addNS('rect', 'svg')
svg_path             = inkex.addNS('path', 'svg')
svg_line             = inkex.addNS('line', 'svg')
svg_polyline         = inkex.addNS('polyline', 'svg')
svg_polygon          = inkex.addNS('polygon', 'svg')
svg_text             = inkex.addNS('text','svg')
svg_textPath         = inkex.addNS('textPath','svg')
svg_tspan            = inkex.addNS('tspan','svg')
svg_g                = inkex.addNS('g', 'svg')
svg_title            = inkex.addNS('title', 'svg')
svg_ellipse          = inkex.addNS('ellipse', 'svg')
svg_image            = inkex.addNS('image', 'svg')
svg_symbol           = inkex.addNS('symbol', 'svg')
therion_role         = inkex.addNS('role', 'therion')
therion_type         = inkex.addNS('type', 'therion')
therion_options      = inkex.addNS('options', 'therion')
therion_basescale    = inkex.addNS('basescale', 'therion')
therion_howtostore   = inkex.addNS('howtostore', 'therion')
therion_xvi_dx       = inkex.addNS('xvi-dx', 'therion')
therion_xvi_dy       = inkex.addNS('xvi-dy', 'therion')
xlink_href           = inkex.addNS('href', 'xlink')
xml_space            = inkex.addNS('space', 'xml')
inkscape_groupmode   = inkex.addNS('groupmode', 'inkscape')
inkscape_label       = inkex.addNS('label', 'inkscape')
inkscape_original_d  = inkex.addNS('original-d', 'inkscape')
inkscape_path_effect = inkex.addNS('path-effect', 'inkscape')
sodipodi_cx          = inkex.addNS('cx', 'sodipodi')
sodipodi_cy          = inkex.addNS('cy', 'sodipodi')
sodipodi_role        = inkex.addNS('role','sodipodi')
sodipodi_insensitive = inkex.addNS('insensitive', 'sodipodi')

def title_node(parent):
	title = parent.find(svg_title)
	if title is None:
		title = etree.SubElement(parent, svg_title)
		title.text = ""
		# if <title> is last child of <text>, Inkscape screws up when
		# appending lines and inserts <title> instead of <tspan> elements.
		parent.insert(0, title)
	return title

def get_style(node):
	import simplestyle
	return simplestyle.parseStyle(node.get('style', ''))

def get_style_attr(node, style, key, d=''):
	if style is None:
		style = get_style(node)
	d = node.get(key, d)
	return style.get(key, d)

##########################################
# station name stuff

def name_survex2therion(name):
	x = name.split('.')
	if len(x) == 1:
		return name
	return x[-1] + '@' + '.'.join(reversed(x[:-1]))

def name_therion2survex(name, prefix=''):
	x = name.replace('@','.',1).split('.')
	return prefix + '.'.join(reversed(x))

##########################################
# options stuff

option_value_count = {
	'attr' : 2,
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

def is_numeric(s):
	try:
		float(s)
	except:
		return False
	return True


def maybe_key(s):
	return re.match(r'-\S+$', s) != None and not is_numeric(s)


def splitquoted(ustr, comments=False):
	'''
	Unicode safe shlex.split() drop-in.

	Only uses double quotes, not single quotes.

	Returns "[foo bar]" as one string.
	'''

	if sys.version_info[0] > 2:
		assert not isinstance(ustr, bytes)
		return(_splitquoted(ustr, comments))
	elif isinstance(ustr, bytes):
		return(_splitquoted(ustr, comments))

	import re

	def myencode(ustr):
		return re.sub(
			u'[#\x7F-\U000FFFFF]',  #
			lambda m: u'#%05X' % ord(m.group(0)),
			ustr,
			flags=re.U).encode('ascii')

	def mydecode(bstr):
		return re.sub(
			u'#([0-9A-F]{5})',  #
			lambda m: unichr(int(m.group(1), 16)),
			bstr.decode('ascii'))

	return [mydecode(b) for b in _splitquoted(myencode(ustr), comments)]


def _splitquoted(s, comments=False):
	import shlex
	lex = shlex.shlex(s, posix=True)
	lex.whitespace_split = True
	if not comments:
		lex.commenters = ''
	lex.quotes = '"'
	def gen():
		values = iter(lex)
		for value in values:
			if value.startswith('['):
				while not value.endswith(']'):
					value += ' ' + next(values)
			yield value
	return list(gen())


def quote(value):
	'''
	Add quotes around value, if needed
	'''
	assert isinstance(value, basestring)
	if not value:
		return '""'
	if needquote.search(value) is None:
		return value
	if value.startswith('[') and value.endswith(']'):
		return value
	return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


def _skipunexpected(s):
	inkex.errormsg(s)


def parse_options_new(a):
	'''
	Parses therion options string or sequence of strings.
	New: Uses shlex class (quote parsing).

	Known issues:
	 * detection of zero-arg-keys is heuristical
	'''
	options = {}
	if not isinstance(a, basestring):
		a = ' '.join(a)
	a = splitquoted(a)
	n = len(a)
	i = 0
	while i < n:
		try:
			assert a[i][0] == '-'
		except:
			_skipunexpected('assertion failed on ' + a[i])
			return options

		key = a[i][1:]
		i += 1

		value_count = option_value_count.get(key)

		if value_count is None:
			value_count = 0
			while (value_count + i) != n and not maybe_key(a[value_count + i]):
				value_count += 1

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

parse_options = parse_options_new


def key_options_item(item: tuple) -> tuple:
	"""
	Sort key for options. Alphabetic with some exceptions.
	"""
	if item[0] == 'id':
		return '0' + item[0], item[1]
	return item


# TODO this fails for -text "[foo bar]" (will be -text [foo bar], no quotes)
def format_options(options):
	'''
	Format options dictionary as therion options string.
	'''
	def format_option(key, value):
		# legacy (might come from SVG file)
		for two_arg_key in two_arg_keys:
			if key.startswith(two_arg_key + '-'):
				ret = '-' + key.replace('-', ' ', 1)
				value_count = 1
				break
		else:
			ret = '-' + key
			value_count = option_value_count.get(key)

		if value == True:
			assert value_count in (None, 0)
		elif isinstance(value, (tuple, list)):
			# multi-value string
			assert value_count in (None, len(value))
			ret += ''.join(' ' + quote(v) for v in value)
		elif not isinstance(value, basestring):
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
			ret += ' <error>' * value_count

		return ret

	ret = []
	for key,value in sorted(options.items(), key=key_options_item):
		if key in repeatable_options and isinstance(value, list):
			for v in value:
				ret.append(format_option(key, v))
		else:
			ret.append(format_option(key, value))

	return ' '.join(ret)

def maybe_point(node):
	return node.tag == svg_text or \
			node.tag == svg_use or \
			node.tag == svg_circle

def maybe_line(node):
	return node.tag == svg_path or \
			node.tag == svg_line or \
			node.tag == svg_polyline or \
			node.tag == svg_rect or \
			node.tag == svg_polygon

def is_closed_line(node):
	if node.tag in (svg_polygon, svg_rect):
		return True
	d = node.get('d', '')
	return d.rstrip()[-1:].lower() == 'z'

def set_props(e, role, type, options={}):
	'''
	Annotate SVG element with role, type and options.
	'''
	assert role != 'scrap', 'Cannot use set_props for scraps'
	options_str = format_options(options)
	if th2pref.howtostore != 'therion_attribs':
		for key in [therion_role, therion_type, therion_options]:
			if key in e.attrib:
				del e.attrib[key]
	if th2pref.howtostore in ['inkscape_label', 'title']:
		if role == '': role = '_unknown_'
		if type == '': type = 'u:unknown'
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

def get_props(e):
	'''
	Get list of (str role, str type, dict options) from annotated SVG element.
	'''
	assert e.get(therion_role) != 'scrap', 'Cannot use get_props for scraps'

	if th2pref.howtostore == 'inkscape_label':
		label = e.get(inkscape_label) or title_node(e).text or ''
	else:
		label = title_node(e).text or e.get(inkscape_label) or ''

	label = label.split(None, 2) + [''] * 3
	role = e.get(therion_role, label[0])
	type = e.get(therion_type, label[1])
	options = e.get(therion_options, label[2])
	options = parse_options(options)
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
	return [role, type, options]

def get_props_dict(e):
	role, type, options = get_props(e)
	return {
		'role': role,
		'type': type,
		'options': options
	}

##########################################
# property translation stuff

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

##########################################
# geom stuff

def det(mat):
	return mat[0][0] * mat[1][1] - mat[0][1] * mat[1][0]

def descrim(mat):
	return math.sqrt(abs(det(mat)))

def inverse(mat):
	d = [[1,0,0],[0,1,0]]
	determ = det(mat)
	if abs(determ) > 0.0001:
		ideterm = 1.0 / determ
		d[0][0] =  mat[1][1] * ideterm
		d[0][1] = -mat[0][1] * ideterm
		d[1][0] = -mat[1][0] * ideterm
		d[1][1] =  mat[0][0] * ideterm
		d[0][2] = -mat[0][2] * d[0][0] - mat[1][2] * d[1][0]
		d[1][2] = -mat[0][2] * d[0][1] - mat[1][2] * d[1][1]
	return d

def parsePath(d):
	'''
	Parse line and replace quadratic bezier segments and arcs by
	cubic bezier segments.
	'''
	import simplepath
	p = simplepath.parsePath(d)
	if any(cmd not in 'MLCZ' for (cmd,params) in p):
		import cubicsuperpath
		csp = cubicsuperpath.CubicSuperPath(p)
		p = cubicsuperpath.unCubicSuperPath(csp)
	return p

def parseViewBox(viewBox, width, height):
	'''
	Returns the 2x3 transformation matrix that a viewBox defines
	'''
	if isinstance(viewBox, basestring):
		viewBox = [float(i) for i in viewBox.split()]
	return [[float(width) / viewBox[2], 0, -viewBox[0]], [0, float(height) / viewBox[3], -viewBox[1]]]

######################################
# IO stuff

def find_in_pwd(filename, path=[]):
	for dirname in ['', os.getcwd()] + path:
		candidate = os.path.join(dirname, filename)
		if os.path.exists(candidate):
			return candidate
	raise IOError("Can't find file '" + filename + "'")

def find_in_pythonpath(filename):
	for dirname in [os.path.dirname(__file__)]:
		candidate = os.path.join(dirname, filename)
		if os.path.exists(candidate):
			return candidate
	raise IOError("Can't find file '" + filename + "' in PYTHONPATH")

def open_in_pythonpath(filename):
	return open(find_in_pythonpath(filename))

def print_utf8(x, file=sys.stdout):
	print(x.encode('UTF-8'), file=file)

if PY3:
	print_utf8 = print


######################################
# transitional inkex functions

try:
	inkex.errormsg
except:
	import sys
	inkex.errormsg = lambda msg: sys.stderr.write((str(msg) + "\n").encode("UTF-8"))

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


def convert_unit(value: str, to_unit: str) -> float:
	"""
	Returns value in requested unit

	>>> convert_unit("3m", "m") == 3.0
	>>> convert_unit("3m", "cm") == 300.0
	"""
	m = re.fullmatch(r'(.*?)([a-z]+)', value.rstrip())
	if m is None:
		return 0.0

	val, unit = m.groups()
	try:
		return float(val) * UUCONV[unit] / UUCONV[to_unit]
	except (ValueError, KeyError):
		return 0.0


class Th2Effect(inkex.Effect):

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

	def getDocumentUnit(self):
		'''Override inkex.Effect.getDocumentUnit'''
		return 'px'

	@property
	def r2d(self) -> list:
		return [
			[th2pref.basescale, 0.0, 0.0],
			[0.0, -th2pref.basescale, 0.0],
		]

	bbox_cache = {}
	i2d_cache = {}

	def i2d_affine(self, node, use_cache=True):
		'''
		Get the "item to document" transformation matrix.

		Note: use_cache showed 20% speed improvement for a big SVG document
		'''
		if use_cache and node in self.i2d_cache:
			return self.i2d_cache[node]

		import simpletransform
		m2 = simpletransform.parseTransform(node.get('transform'))

		parent = node.getparent()
		if parent is not None:
			m1 = self.i2d_affine(parent, use_cache)
			m2 = simpletransform.composeTransform(m1, m2)
		else:
			m2 = simpletransform.composeTransform(self.r2d, m2)

		self.i2d_cache[node] = m2
		return m2

	def node_center(self, node):
		'''
		Get the bounding box center, or for some particular cases x/y (like
		for text to support alignment). Does not take the "transform" attibute
		into account.
		'''
		# Text and Clones
		if th2pref.xyascenter and node.tag in [ svg_text, 'text', svg_use, 'use' ]:
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

	def compute_bbox(self, node, transform=True, use_cache=False):
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
		import cubicsuperpath
		from simpletransform import boxunion, parseTransform, applyTransformToPath, formatTransform
		try:
			from simpletransform import refinedBBox
		except:
			from simpletransform import roughBBox as refinedBBox

		d = None
		recurse = False
		node_bbox = None

		if transform:
			transform = node.get('transform', '')
		else:
			transform = ''

		if use_cache and node in self.bbox_cache:
			node_bbox = self.bbox_cache[node]
		elif node.tag in [ svg_use, 'use' ]:
			x, y = float(node.get('x', 0)), float(node.get('y', 0))
			refid = node.get(xlink_href)
			refnode = self.getElementById(refid[1:])

			if refnode is None:
				return None

			if 'width' in node.attrib and 'height' in node.attrib and 'viewBox' in refnode.attrib:
				mat = parseViewBox(refnode.get('viewBox'), node.get('width'), node.get('height'))
				transform += ' ' + formatTransform(mat)

			refbbox = self.compute_bbox(refnode, True, True)
			if refbbox is not None:
				node_bbox = [refbbox[0] + x, refbbox[1] + x, refbbox[2] + y, refbbox[3] + y]

		elif node.get('d'):
			d = node.get('d')
		elif node.get('points'):
			d = 'M' + node.get('points')
		elif node.tag in [ svg_rect, 'rect', svg_image, 'image' ]:
			d = 'M' + node.get('x', '0') + ',' + node.get('y', '0') + \
				'h' + node.get('width') + 'v' + node.get('height') + \
				'h-' + node.get('width')
		elif node.tag in [ svg_line, 'line' ]:
			d = 'M' + node.get('x1') + ',' + node.get('y1') + \
				' ' + node.get('x2') + ',' + node.get('y2')
		elif node.tag in [ svg_circle, 'circle', svg_ellipse, 'ellipse' ]:
			rx = node.get('r')
			if rx is not None:
				ry = rx
			else:
				rx = node.get('rx')
				ry = node.get('ry')
			rx, ry = float(rx), float(ry)
			cx = float(node.get('cx', '0'))
			cy = float(node.get('cy', '0'))
			node_bbox = [cx - rx, cx + rx, cy - ry, cy + ry]
			'''
			a = 0.555
			d = 'M %f %f C' % (cx-rx, cy) + ' '.join('%f' % c for c in [
				cx-rx,   cy-ry*a, cx-rx*a, cy-ry,   cx,    cy-ry,
				cx+rx*a, cy-ry,   cx+rx,   cy-ry*a, cx+rx, cy,
				cx+rx,   cy+ry*a, cx+rx*a, cy+ry,   cx,    cy+ry,
				cx-rx*a, cy+ry,   cx-rx,   cy+ry*a, cx-rx, cy,
				])
			'''
		elif node.tag in [ svg_text, 'text', svg_tspan, 'tspan' ]:
			# very rough estimate of text bounding box
			x = node.get('x', '0').split()
			y = node.get('y', '0').split()
			if len(x) == 1 and len(y) > 1:
				x = x * len(y)
			elif len(y) == 1 and len(x) > 1:
				y = y * len(x)
			d = 'M' + ' '.join('%f' % self.unittouu(c) for xy in zip(x, y) for c in xy)
			recurse = True
		elif node.tag in [ svg_g, 'g', svg_symbol, 'symbol', svg_svg, 'svg' ]:
			recurse = True

		if d is not None:
			p = cubicsuperpath.parsePath(d)
			node_bbox = refinedBBox(p)

		if recurse:
			for child in node:
				child_bbox = self.compute_bbox(child, True, use_cache)
				node_bbox = boxunion(child_bbox, node_bbox)

		self.bbox_cache[node] = node_bbox

		if transform.strip() != '' and node_bbox != None:
			mat = parseTransform(transform)
			p = [[[	[node_bbox[0], node_bbox[2]],
					[node_bbox[0], node_bbox[3]],
					[node_bbox[1], node_bbox[2]],
					[node_bbox[1], node_bbox[3]]]]]
			applyTransformToPath(mat, p)
			x, y = zip(*p[0][0])
			node_bbox = [min(x), max(x), min(y), max(y)]

		return node_bbox

# vi:noexpandtab:sw=4:ts=4
