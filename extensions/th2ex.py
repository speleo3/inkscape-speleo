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

import sys, os, math, re

# some prefs
_pref_use_inkscape_label = True   # only considered for setting, not getting
_pref_use_therion_attribs = False # only considered for setting, not getting

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

# prepare names with namespace
inkex.NSS['therion'] = 'http://therion.speleo.sk/therion'
svg_svg              = inkex.addNS('svg', 'svg')
svg_use              = inkex.addNS('use', 'svg')
svg_circle           = inkex.addNS('circle', 'svg')
svg_path             = inkex.addNS('path', 'svg')
svg_line             = inkex.addNS('line', 'svg')
svg_polyline         = inkex.addNS('polyline', 'svg')
svg_polygon          = inkex.addNS('polygon', 'svg')
svg_text             = inkex.addNS('text','svg')
svg_textPath         = inkex.addNS('textPath','svg')
svg_tspan            = inkex.addNS('tspan','svg')
svg_g                = inkex.addNS('g', 'svg')
therion_role         = inkex.addNS('role', 'therion')
therion_type         = inkex.addNS('type', 'therion')
therion_options      = inkex.addNS('options', 'therion')
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

two_arg_keys = ['attr', 'context']
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
	options_str = format_options(options)
	if _pref_use_therion_attribs:
		e.set(therion_role, role)
		e.set(therion_type, type)
		e.set(therion_options, options_str)
	else:
		for key in [therion_role, therion_type, therion_options]:
			if key in e.attrib:
				del e.attrib[key]
	if _pref_use_inkscape_label:
		if role == '':
			role = '_unknown_'
		if type == '':
			type = 'u:unknown'
		e.set(inkscape_label, "%s %s %s" % (role, type, options_str))

def get_props(e):
	'''
	First parse inkscape:label, second therion:... attributes (so the latter
	has preference)
	'''
	role, type, options = '', '', ''
	label = e.get(inkscape_label, '').split(None, 2)
	try:
		role = label[0]
		type = label[1]
		options = label[2]
	except:
		pass
	role = e.get(therion_role, role)
	type = e.get(therion_type, type)
	options = e.get(therion_options, options)
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
	if type == 'station' and 'name' not in options and len(label) == 1:
		# fallback for old survex 3D import: label holds station name
		options['name'] = label[0]
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
