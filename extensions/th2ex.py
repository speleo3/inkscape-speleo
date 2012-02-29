#!/usr/bin/env python 
'''
Copyright (C) 2008 Thomas Holder, http://sf.net/users/speleo3/
Distributed under the terms of the GNU General Public License v2

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

import sys, os, math, re, optparse

# some prefs
class th2pref:
	howtostore = 'inkscape_label'
	textonpath = True
	image_inkscape = False
	basescale = 1.0

# first try to assure that the inkscape extensions dir in in PYTHONPATH
# obsolete for inkscape-0.47
try:
	import inkex
except:
	programfiles = os.getenv('PROGRAMFILES')
	if programfiles:
		sys.path.append(programfiles + '\\Inkscape\\share\\extensions')
	try:
		import commands
		statusoutput = commands.getstatusoutput('inkscape -x')
		assert statusoutput[0] == 0
		sys.path.append(statusoutput[1])
	except:
		sys.path.append('/usr/share/inkscape/extensions')
		sys.path.append('/Applications/Inkscape.app/Contents/Resources/extensions')
	import inkex

# command line options and hook to th2pref
oparser = optparse.OptionParser(option_class=inkex.InkOption)
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
therion_role         = inkex.addNS('role', 'therion')
therion_type         = inkex.addNS('type', 'therion')
therion_options      = inkex.addNS('options', 'therion')
therion_basescale    = inkex.addNS('basescale', 'therion')
therion_howtostore   = inkex.addNS('howtostore', 'therion')
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
		title = inkex.etree.SubElement(parent, svg_title)
		title.text = ""
	return title

def get_style(node):
	return simplestyle.parseStyle(node.get('style', ''))

def get_style_attr(node, style, key, d=''):
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

two_arg_keys = ['attr', 'context', 'author']
needquote = re.compile(r'[^-._@a-z0-9]', re.I)

def is_numeric(s):
	try:
		float(s)
	except:
		return False
	return True

def parse_options_new(a):
	'''
	Parses therion options string or sequence of strings.
	New: Uses shlex class (quote parsing).

	Known issues:
	 * shlex does not support unicode (so not usable so far!)
	 * detection of zero-arg-keys is heuristical
	'''
	import shlex
	options = {}
	if not isinstance(a, basestring):
		a = ' '.join(a)
	a = shlex.split(a)
	n = len(a)
	i = 0
	while i < n:
		try:
			assert a[i][0] == '-'
		except:
			inkex.errormsg('assertion failed on ' + a[i])
		key = a[i][1:]
		if i + 1 == n or a[i + 1][0] == '-' and \
				not is_numeric(a[i + 1]) and \
				key not in ['value', 'text']: # TODO: hack!!!
			options[key] = True
		else:
			i += 1
			if key in two_arg_keys:
				key += '-' + a[i]
				i += 1
			value = a[i]
			if value[0] == '[':
				while value[-1:] != ']':
					i += 1
					value += ' ' + a[i]
			options[key] = value
		i += 1
	return options

# DONE: this fails for -text "foo \"bar\" com"
# DONE: this fails for -text " "
# DONE: this fails for -context role type (2 arguments)
# DONE: negative number values are recognized as option (leading hyphen)
# NOTE: result is the same for -text "[foo bar]" and -text [foo bar], but should be no problem
def parse_options_old(a):
	'''
	Parses therion options string or sequence of strings.
	Old: Does not use the shlex class, parses quotes manually.
	'''
	options = {}
	if isinstance(a, basestring):
		a = a.split()
	n = len(a)
	i = 0
	while i < n:
		try:
			assert a[i][0] == '-'
		except:
			inkex.errormsg('assertion failed on ' + a[i])
		key = a[i][1:]
		if i + 1 == n or a[i + 1][0] == '-' and \
				not is_numeric(a[i + 1]) and \
				key not in ['value', 'text']: # TODO: hack!!!
			options[key] = True
		else:
			i += 1
			if key in two_arg_keys:
				key += '-' + a[i]
				i += 1
			value = a[i]
			if value[0] == '"':
				while len(value) == 1 or value[-1] != '"' or value[-2] == r'\\':
					i += 1
					value += ' ' + a[i]
				value = value[1:-1].replace('\\"', '"')
			elif value[0] == '[':
				while value[-1:] != ']':
					i += 1
					value += ' ' + a[i]
			options[key] = value
		i += 1
	return options

parse_options = parse_options_old

# TODO this fails for -text "[foo bar]" (will be -text [foo bar], no quotes)
def format_options(options):
	'''
	Format options dictionary as therion options string.
	'''
	ret = ''
	for key,value in options.iteritems():
		if len(ret) > 0:
			ret += ' '
		for two_arg_key in two_arg_keys:
			if key.startswith(two_arg_key + '-'):
				ret += '-' + key.replace('-', ' ', 1)
				break
		else:
			ret += '-' + key
		if value == True:
			continue
		if not isinstance(value, basestring):
			ret += ' ' + str(value)
		elif len(value) == 0:
			inkex.errormsg('error: empty value: -' + key);
		elif value[0] == '[' or needquote.search(value) is None:
			ret += ' ' + value
		else:
			ret += ' "' + value.replace('"', '\\"') + '"'
	return ret

def maybe_point(node):
	return node.tag == svg_text or \
			node.tag == svg_use or \
			node.tag == svg_circle

def maybe_line(node):
	return node.tag == svg_path or \
			node.tag == svg_line or \
			node.tag == svg_polyline or \
			node.tag == svg_polygon

def set_props(e, role, type, options={}):
	'''
	Set both, inkscape:label and therion:... attributes
	'''
	assert role != 'scrap', 'Cannot use set_props for scraps'
	options_str = format_options(options)
	if th2pref.howtostore != 'therion_attribs':
		for key in [therion_role, therion_type, therion_options]:
			if key in e.attrib:
				del e.attrib[key]
	if role == '':
		role = '_unknown_'
	if type == '':
		type = 'u:unknown'
	if th2pref.howtostore == 'inkscape_label':
		e.set(inkscape_label, "%s %s %s" % (role, type, options_str))
	elif th2pref.howtostore == 'title':
		title_node(e).text = "%s %s %s" % (role, type, options_str)
	elif th2pref.howtostore == 'therion_attribs':
		e.set(therion_role, role)
		e.set(therion_type, type)
		e.set(therion_options, options_str)
	else:
		raise Exception, 'unknown th2pref.howtostore'

def get_props(e):
	'''
	First parse inkscape:label, second therion:... attributes (so the latter
	has preference)
	'''
	assert e.get(therion_role) != 'scrap', 'Cannot use get_props for scraps'
	role, type, options, label = '', '', '', []
	if th2pref.howtostore == 'inkscape_label':
		label = e.get(inkscape_label, '').split(None, 2)
	elif th2pref.howtostore == 'title':
		title = title_node(e).text
		if title is None:
			title = ''
		label = title.split(None, 2)
	elif th2pref.howtostore == 'therion_attribs':
		label = [e.get(therion_role, ''),
				e.get(therion_type, ''),
				e.get(therion_options, '')]
	else:
		raise Exception, 'unknown th2pref.howtostore'
	try:
		role = label[0]
		type = label[1]
		options = label[2]
	except IndexError:
		pass
	options = parse_options(options)
	if role == '':
		if maybe_point(e):
			role = 'point'
		elif maybe_line(e):
			role = 'line'
	if type == '':
		if role == 'line':
			type = 'wall' # fallback for unannotated files
		elif role == 'point' and e.tag == svg_text:
			type = 'label' # fallback for unannotated files
		else:
			type = 'u:unknown'
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

align2anchor = {
	'c': 'middle',
	't': 'middle',
	'b': 'middle',
	'l': 'end',
	'r': 'start',
	'tl': 'end',
	'tr': 'start',
	'bl': 'end',
	'br': 'start',
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


######################################
# IO stuff

def find_in_pwd(filename, path=[]):
	for dirname in ['', os.environ['PWD']] + path:
		candidate = os.path.join(dirname, filename)
		if os.path.exists(candidate):
			return candidate
	raise IOError("Can't find file '" + filename + "'")

def find_in_pythonpath(filename):
	for dirname in sys.path:
		candidate = os.path.join(dirname, filename)
		if os.path.exists(candidate):
			return candidate
	raise IOError("Can't find file '" + filename + "' in PYTHONPATH")

def open_in_pythonpath(filename):
	return open(find_in_pythonpath(filename))

def print_utf8(x, file=sys.stdout):
	print >> file, x.encode('UTF-8')


######################################
# transitional inkex functions

try:
	inkex.errormsg
except:
	import sys
	inkex.errormsg = lambda msg: sys.stderr.write((str(msg) + "\n").encode("UTF-8"))
