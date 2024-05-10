#!/usr/bin/env python
'''
Copyright (C) 2008 Thomas Holder, http://sf.net/users/speleo3/
Distributed under the terms of the GNU General Public License v2 or later

TODO
 * support line options between line data, for example by splitting lines and grouping
'''

from __future__ import print_function
from __future__ import absolute_import

import sys, os, re
from th2ex import *
from lxml import etree
import simplepath

# some prefs
oparser.add_option('--sublayers', action='store', type='inkbool', dest='sublayers', default=False)
oparser.add_option('--basescale', action='store', type='float', dest='basescale', default=1.0)
oparser.add_option('--howtostore', action='store', type='choice', dest='howtostore',
		choices=('inkscape_label', 'title', 'therion_attribs'))
oparser.add_option('--lock-stations', action='store', type='inkbool', dest='lock_stations', default=False)
th2pref_reload()

id_count = 0

template = open_in_pythonpath('th2_template.svg')
document = etree.parse(template)
template.close()

root = document.getroot()

# save input prefs to file
th2pref_store_to_xml(root)

ids = root.xpath('/svg:svg/svg:defs/*[starts-with(@id, "point-")]/@id', namespaces=inkex.NSS)
point_symbols = [ id[6:] for id in ids ]

ids = root.xpath('/svg:svg/svg:defs/*[starts-with(@id, "LPE-")]/@id', namespaces=inkex.NSS)
LPE_symbols = [ id[4:] for id in ids ]

currentlayer = root.xpath('svg:g[@id="layer-legend"]', namespaces=inkex.NSS)[0]

# for areas
borders = {}

if th2pref.sublayers:
	sublayers = {}
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
	def getlayer(role, type):
		if role == 'point':
			key = pointtype2layer.get(type, 'misc')
		else:
			key = linetype2layer.get(type, 'misc')
		return sublayers.get(key, currentlayer)
else:
	def getlayer(role, type):
		return currentlayer

# points legend
spacing = 40
max_x = 800
x = spacing
y = 0 
for type in point_symbols:
	node = etree.SubElement(currentlayer, 'text')
	node.set('transform', 'translate(%d,%d)' % (x, -(y + 0.25) * spacing))
	node.text = type
	node = etree.SubElement(currentlayer, 'use')
	set_props(node, 'point', type)
	node.set('transform', 'translate(%d,%d)' % (x, -(y + 1) * spacing))
	node.set(xlink_href, '#point-' + type)
	x += spacing
	if x > max_x:
		x = spacing
		y += 2

node = etree.SubElement(currentlayer, 'rect', { 'style': 'fill:none;stroke:black', 'transform': 'scale(1,-1)'  })
node.set('height', '%d' % ((2 + y) * spacing))
if y > 0:
	node.set('width', '%d' % (max_x + spacing))
else:
	node.set('width', '%d' % (x))

default_line_opts = {
	'section': {'direction': 'begin'},
}

x = spacing
for type in LPE_symbols:
	type_uscore = type
	type = type.replace('_', ':')
	node = etree.SubElement(currentlayer, 'text')
	node.set('transform', 'translate(%d,%d)' % (-spacing, x + 0.4 * spacing))
	node.text = type
	node = etree.SubElement(currentlayer, 'path')
	set_props(node, 'line', type, default_line_opts.get(type, {}))
	node.set(inkscape_original_d, 'M%f,%fh%f' % (-1.5*spacing, x, spacing))
	node.set(inkscape_path_effect, '#LPE-' + type_uscore)
	node.set('class', 'line ' + type.replace(':', ' '))
	x += spacing
for type in ('arrow','map-connection','gradient','chimney','section'):
	node = etree.SubElement(currentlayer, 'text')
	node.set('transform', 'translate(%d,%d)' % (-spacing, x + 0.4 * spacing))
	node.text = type
	node = etree.SubElement(currentlayer, 'path')
	set_props(node, 'line', type, default_line_opts.get(type, {}))
	node.set('d', 'M%f,%fh%f' % (-1.5*spacing, x, spacing))
	node.set('class', 'line ' + type)
	x += spacing

node = etree.SubElement(currentlayer, 'rect', { 'y': '0', 'style': 'fill:none;stroke:black' })
node.set('x', '%d' % (-2 * spacing))
node.set('height', '%d' % (x))
node.set('width', '%d' % (2 * spacing))

currentlayer = root
layer_stack = [currentlayer]
file_stack: list["FileRecord"] = []

class FileRecord:
	def __init__(self, patharg: str):
		searchpath = [file_stack[-1].dirname] if file_stack else []
		self.filename = find_in_pwd(patharg, searchpath)
		self.dirname = os.path.dirname(self.filename)
		self.f_handle = open(self.filename, 'rb')
		self.f_enum = enumerate(self.f_handle)
	def __del__(self):
		self.f_handle.close()

# open th2 file
file_stack.append(FileRecord(th2pref.argv[0]))

doc_x = 0
doc_y = 0
doc_width = 0
doc_height = 0
m_per_dots = 0.0254
m_per_dots_set = False
encoding = 'UTF-8'


def set_m_per_dots(value: float, overwrite: bool = False):
	global m_per_dots, m_per_dots_set
	if m_per_dots_set and not (0.9 < (value / m_per_dots) < 1.1):
		errormsg(f"Warning: m/dots {value} vs {m_per_dots}")
	if overwrite or not m_per_dots_set:
		m_per_dots = value
		m_per_dots_set = True


def flipY_old(a):
	for i in range(1, len(a), 2):
		a[i] = a[i][1:] if a[i][0] == '-' else '-' + a[i]
	return a

def strscale(x):
	return str(floatscale(x))

def floatscale(x):
	# TODO scale input coordinates to given base-scale
	return float(x) / th2pref.basescale

def flipY_scaled(a):
	scalefactor = 0.2
	a[0::2] = ['%f' % ( floatscale(i)) for i in a[0::2]]
	a[1::2] = ['%f' % (-floatscale(i)) for i in a[1::2]]
	return a

flipY = flipY_scaled

def reverseP(p):
	retval = []
	prevcmd = p[-1][0]
	prevparams = p[-1][1]
	retval = [['M', prevparams[-2:]]]
	for cmd,params in reversed(p[:-1]):
		newparams = []
		if len(prevparams) == 6:
			newparams = [
				prevparams[2],
				prevparams[3],
				prevparams[0],
				prevparams[1]
			]
		newparams.extend(params[-2:])
		retval.append([prevcmd, newparams])
		prevparams = params
		prevcmd = cmd
	return retval

def reverseD(d):
	p = simplepath.parsePath(d)
	p = reverseP(p)
	return simplepath.formatPath(p)

line_nr = 0
def f_readline():
	global line_nr
	try:
		line_nr, line = next(file_stack[-1].f_enum)
	except StopIteration:
		file_stack.pop()
		layer_stack.pop()
		global currentlayer
		currentlayer = layer_stack[-1] if layer_stack else root
		return f_readline() if file_stack else ''
	line = line.rstrip(b'\r\n')
	line = line.decode(encoding)
	if line.endswith('\\'):
		line = line[:-1] + f_readline()
	return line + '\n'

def errormsg(x):
	print('[line %d]' % (line_nr+1), x, file=sys.stderr)

def parse(a):
	function = parsedict.get(a[0])
	if function:
		function(a)
	elif a[0].startswith('#'):
		parse_LINE2COMMENT(a)
	else:
		errormsg('skipped: ' + a[0])

def parse_encoding(a):
	global encoding
	encoding = a[1]

def parse_INKSCAPE(a):
	if a[1] == 'image':
		img = etree.Element('image')
		img.set('width', a[2])
		img.set('height', a[3])
		img.set('transform', a[4])
		img.set(xlink_href, ' '.join(a[5:]))
		root.xpath('svg:g[@id="layer-scan"]', namespaces=inkex.NSS)[0].append(img)

def parse_XTHERION(a):
	global doc_width, doc_x, doc_y
	global doc_height

	if a[1] == 'xth_me_image_insert':
		href, XVIroot = '', ''
		try:
			# xth_me_image_insert {xx yy fname iidx imgx}
			# xx = {xx vsb igamma}
			# yy = {yy XVIroot}
			# XVIroot is the station name which defines (0,0)
			me_image_str = ' '.join(a[2:])
			if sys.version_info[0] < 3:
				import Tkinter
				me_image_str = me_image_str.encode('utf-8')
			else:
				import tkinter as Tkinter
			tk_instance = Tkinter.Tcl().tk.eval
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
				href = find_in_pwd(href, [file_stack[-1].dirname])
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
				root.xpath('svg:g[@id="layer-scan"]', namespaces=inkex.NSS)[0].append(img)

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
			root.xpath('svg:g[@id="layer-scan"]', namespaces=inkex.NSS)[0].append(img)
		else:
			errormsg('skipped: ' + a[1])

	if a[1] == 'xth_me_area_adjust':
		doc_x = floatscale(a[2])
		doc_y = floatscale(a[5])
		doc_width = floatscale(a[4]) - doc_x
		doc_height = doc_y - floatscale(a[3])


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

	global sublayers
	if th2pref.sublayers:
		sublayers = {
		'wall': etree.SubElement(e, 'g', {inkscape_groupmode: 'layer', inkscape_label: u'Walls'}),
		'cont': etree.SubElement(e, 'g', {inkscape_groupmode: 'layer', inkscape_label: u'Contours'}),
		'rock': etree.SubElement(e, 'g', {inkscape_groupmode: 'layer', inkscape_label: u'Boulders'}),
		'stat': etree.SubElement(e, 'g', {inkscape_groupmode: 'layer', inkscape_label: u'Stations'}),
		'misc': etree.SubElement(e, 'g', {inkscape_groupmode: 'layer', inkscape_label: u'Misc'}),
		'labe': etree.SubElement(e, 'g', {inkscape_groupmode: 'layer', inkscape_label: u'Labels'}),
	}

	global currentlayer
	currentlayer.append(e)
	currentlayer = e
	layer_stack.append(e)

	while True:
		line = f_readline()
		assert line != ''
		a = line.split()
		if len(a) == 0:
			continue
		if a[0] == 'endscrap':
			break
		parse(a)
	
	layer_stack.pop()
	currentlayer = layer_stack[-1]

def parse_area(a_in):
	lines = []
	while True:
		line = f_readline()
		assert line != ''
		a = line.split()
		if not a:
			continue
		lines.append(line)
		if a[0] == 'endarea':
			break

	# we can only handle areas with one border line
	if len(lines) != 2 or lines[0].strip() not in borders:
		e = etree.Comment('#therion\n')
		e.text += ' '.join(a_in) + '\n'
		e.text += ''.join(lines)
		currentlayer.insert(0, e)
		return

	# update border line
	e = borders[lines[0].strip()]
	role, type, options = get_props(e)
	assert (role, type) == ('line', 'border')
	options.pop('id', None) # will get a new ID on export
	vis = options.pop('visibility', None)
	if options:
		errormsg('warning: area border options not empty: ' + str(options))
	if vis:
		options['line-visibility'] = vis
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
	role = a[0]
	e = etree.Comment('#therion\n')
	e.text += ' '.join(a) + '\n'
	while True:
		line = f_readline()
		assert line != ''
		e.text += line
		a = line.split()
		if len(a) > 0 and a[0] == 'end%s' % (role):
			break
	currentlayer.insert(0, e)

def parse_LINE2COMMENT(a):
	e = etree.Comment('#therion\n')
	e.text += ' '.join(a) + '\n'
	currentlayer.insert(0, e)

textblock_count = 0

def parse_BLOCK2TEXT(a):
	'''
	Currently unused
	'''
	global textblock_count
	role = a[0]
	e = etree.Element('text')
	e.set(therion_role, 'textblock')
	e.set('style', 'font-size:8;fill:#900')
	e.set('x', str(doc_width + 20))
	e.set('y', str(textblock_count * 10 + 20))
	e.set(xml_space, 'preserve')
	desc = etree.SubElement(e, 'desc')
	desc.tail = ' '.join(a)
	while True:
		line = f_readline()
		assert line != ''
		a = line.split()
		if len(a) > 0 and a[0] == 'end%s' % (role):
			break
		if desc.text is None:
			desc.text = line
		else:
			desc.text += line
	currentlayer.insert(0, e)
	textblock_count += 1

def parse_line(a):
	global id_count

	options = parse_options(a[2:])
	type_subtype = a[1]
	if ':' in type_subtype:
		type, subtype = type_subtype.split(':', 1)
	else:
		type = type_subtype
		subtype = options.get('subtype', '')

	insensitive = False
	lossless_repr = ''

	d = ""
	started = False
	while True:
		line = f_readline()
		assert line != ''
		a = line.split()
		if len(a) == 0:
			continue
		if a[0] == 'endline':
			break
		lossless_repr += line
		if a[0] == 'smooth':
			# ignore smooth option
			continue
		if a[0][0].isdigit() or a[0][0] == '-':
			if not started:
				d += 'M'
				started = True
			elif len(a) == 2:
				d += ' L'
			elif len(a) == 6:
				d += ' C'
			else:
				insensitive = True
				errormsg('error: length = %d' % len(a))
			d += ','.join(flipY(a))
		else:
			# TODO Create multiple subpath elements, grouped
			insensitive = True
			errormsg('skipped line option: ' + ' '.join(a))

	if len(d) == 0:
		errormsg('warning: empty line')
		return

	e = etree.Element('path')
	e.set('class', 'line %s %s' % (type, subtype))

	if insensitive:
		errormsg('element not fully supported, will be read-only')
		e.set(sodipodi_insensitive, 'true')
		desc = etree.SubElement(e, 'desc')
		desc.text = lossless_repr
	
	if options.get('reverse', 'off') == 'on':
		d = reverseD(d)
		if not insensitive:
			del options['reverse']

	if options.get('close', 'off') == 'on':
		d += ' z'
		if not insensitive:
			del options['close']
	
	if type + '_' + subtype in LPE_symbols:
		e.set(inkscape_path_effect, '#LPE-%s_%s' % (type, subtype))
		e.set(inkscape_original_d, d)
	elif type in LPE_symbols:
		e.set(inkscape_path_effect, '#LPE-%s' % (type))
		e.set(inkscape_original_d, d)
	else:
		e.set('d', d)
	
	id_count += 1
	e_id = 'line_%s_%d' % (type, id_count)
	e.set('id', e_id)

	if th2pref.textonpath and type == 'label':
		e_text = etree.Element('text')
		e_textPath = etree.SubElement(e_text, 'textPath', {
			xlink_href: '#' + e_id,
		})
		fontsize = fontscale.get(options.get('scale'), '12')
		if 'scale' in options:
			del options['scale']
		e_text.set('style', "font-size:%s" % (fontsize))
		e_textPath.text = options.pop('text', '')
		if not e_textPath.text:
		    errormsg('line label without text')
		getlayer('line', type).insert(0, e_text)

	# for areas
	if type == 'border' and 'id' in options:
		borders[options['id']] = e

	set_props(e, 'line', type_subtype, options)
	getlayer('line', type).insert(0, e)

# like 1:500
fontscale = {
	'xl': '17.435',
	'l': '12.435',
	'm': '9.963',
	's': '8.717',
	'xs': '7.472',
}

point_colors = {
	'station-name': 'orange',
	'altitude': '#f0f',
	'u': 'red',
}

def parse_point(a):
	global id_count

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
			t = etree.SubElement(e, 'tspan', { sodipodi_role: 'line', 'x': '0', 'y': '%dem' % (y) })
			t.text = line
			y += 1
		del options[key]
		fontsize = fontscale.get(options.pop('scale', None), '12')
		align = options.pop('align', '')
		align = align_shortcuts.get(align, align)
		textanchor = align2anchor.get(align.strip('tb'), align2anchor_default_in)
		baseline = align2baseline.get(align.strip('lr'), align2baseline_default_in)
		e.set('style', "font-size:%s;text-anchor:%s;text-align:%s;dominant-baseline:%s" % (fontsize,
			textanchor, textanchor, baseline))
		e.set(xml_space, 'preserve')
	elif type in point_symbols:
		e = etree.Element('use')
		e.set(xlink_href, "#point-" + type)
		if type == "station" and th2pref.lock_stations:
			e.set(sodipodi_insensitive, "true")
	else:
		e = etree.Element('circle')
		e.set('r', '2')
		if type in point_colors:
			e.set('style', 'fill:' + point_colors[type])

	# position and orientation
	transform = 'translate(%s,%s)' % tuple(flipY(a[1:3]))
	if 'orientation' in options:
		transform += ' rotate(%s)' % (options['orientation'])
		del options['orientation']
	e.set('transform', transform)

	id_count += 1
	e.set('id', 'point_%s_%d' % (type, id_count))

	set_props(e, 'point', a[3], options)
	getlayer('point', type).insert(0, e)


def parse_input(a):
	assert a[0] == "input"
	assert len(a) == 2
	file_stack.append(FileRecord(a[1]))

	e = etree.Element('g')
	e.set(inkscape_groupmode, "layer")
	e.set(inkscape_label, ' '.join(a))
	e.set(therion_role, "input")

	global currentlayer
	currentlayer.append(e)
	currentlayer = e
	layer_stack.append(e)


parsedict = {
	'##XTHERION##':	parse_XTHERION,
	'##INKSCAPE##':	parse_INKSCAPE,
	'scrap':		parse_scrap,
	'line':			parse_line,
	'point':		parse_point,
	'encoding':		parse_encoding,
	'area':			parse_area,
	'map':			parse_BLOCK2COMMENT,
	'centerline':	parse_BLOCK2COMMENT,
	'centreline':	parse_BLOCK2COMMENT,
	'input':		parse_input,
}

while True:
	line = f_readline()
	if len(line) == 0:
		break
	
	a = line.split()

	if len(a) == 0:
		continue
	
	parse(a)

assert not file_stack

if doc_width and doc_height:
	root.set('width', f"{doc_width * m_per_dots}cm")
	root.set('height', f"{doc_height * m_per_dots}cm")
	root.set('viewBox', f"{doc_x} {-doc_y} {doc_width} {doc_height}")

e = root.xpath('svg:g[@id="layer-scan"]', namespaces=inkex.NSS)[0]
e.set('transform', ' scale(1,-1) scale(%f)' % (1./th2pref.basescale))

# scrap0:
# Mostly obsolete, we currently don't populate it.
# Keep it when opening an empty file.
e = root.xpath('svg:g[@id="layer-scrap0"]', namespaces=inkex.NSS)[0]
others = root.xpath('/svg:svg/g[not(@therion:role="none")]', namespaces=inkex.NSS)
if len(e) == 0 and others:
	root.remove(e)
else:
	e.set(therion_role, "scrap")

out = sys.stdout.buffer if PY3 else sys.stdout
document.write(out)

# vi:noexpandtab:sw=4:ts=4
