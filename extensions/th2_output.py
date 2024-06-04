#!/usr/bin/env python 
'''
Copyright (C) 2008 Thomas Holder, http://sf.net/users/speleo3/
Distributed under the terms of the GNU General Public License v2 or later

This program was inspired by http://www.cavediving.de/svg2th2.py
'''

from __future__ import print_function
from __future__ import absolute_import

from th2ex import *
from lxml import etree
import simplepath, simpletransform, simplestyle, math, re
import collections
import os

def parse_options_node(node):
	options = node.get(therion_options, '')
	return parse_options(options)

def transformParams(mat, params):
	new = []
	for i in range(0, len(params), 2):
		if i+1 == len(params):
			inkex.errormsg('params index skewd!!!')
			inkex.errormsg(str(params))
			break
		new.append(mat[0][0]*params[i]+mat[0][1]*params[i+1]+mat[0][2])
		new.append(mat[1][0]*params[i]+mat[1][1]*params[i+1]+mat[1][2])
	return new

def orientation(mat):
	'''Orientation of a (0.0, 1.0) vector after rotation with "mat"'''
	try:
		deg = -math.degrees(math.atan2(mat[0][1], -mat[1][1]))
		return deg % 360.0
	except:
		return 0.0

def fstr(x):
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
	digits = max(0, min(digits, max_dig))
	s = f"{x:.{digits}f}"
	if digits == 0:
		s += ".0"
	return fstr_trim_zeros(s)


def fstr_trim_zeros(s: str) -> str:
	"""
	Strip trailing zeros from a string that represents a floating point number.
	"""
	assert '.' in s
	i = len(s) - 1
	while s[i] == '0': i -= 1
	if s[i] == '.': i += 1
	s = s[:i+1]
	return "0.0" if s == "-0.0" else s


def format_options_leading_space(options):
	"""
	Like format_options() but with a leading space if non-empty.
	"""
	formatted = format_options(options)
	if formatted:
		return " " + formatted
	return ""


class Th2Line:
	def __init__(self, type = 'wall'):
		self.type = type
		self.options = {}
		self.points = []
		self._last = None
	def append(self, params):
		self.points.append(" ".join(fstr(i) for i in params))
		self._last = self.points[-1]
	def append_node_options(self, olist):
		for o in olist:
			self.points.append(o)
	def close(self):
		self.options['close'] = 'on'
		if self._last is not None and (
				self._last.split()[-2:] != self.points[0].split()):
			self.points.append(self.points[0])
	def output(self):
		formatted_options = format_options_leading_space(self.options)
		print_utf8(f"line {self.type}{formatted_options}")
		print("  " + "\n  ".join(self.points))
		print("endline\n")

class Th2Area:
	count = collections.defaultdict(int)

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
	def __init__(self):
		inkex.Effect.__init__(self)
		self.OptionParser.add_option("--scale",    type="int",     dest="scale",    default=100)
		self.OptionParser.add_option("--dpi",      type="int",     dest="dpi",      default=0)
		self.OptionParser.add_option("--layers",   type="string",  dest="layers",   default="all")
		self.OptionParser.add_option("--images",   type="inkbool", dest="images",   default=True)
		self.OptionParser.add_option("--nolpe",    type="inkbool", dest="nolpe",    default=True)
		self.OptionParser.add_option("--lay2scr",  type="inkbool", dest="lay2scr",  default=True)
		self.OptionParser.add_option("--xyascenter", type="inkbool", dest="xyascenter", default=True)
		self.OptionParser.add_option("--projection", type="string",  dest="projection", default="")
		self.OptionParser.add_option("--author",   type="string",  dest="author",   default="")
		self.OptionParser.add_option("--options",  type="string",  dest="options",  default="")
		if th2pref.textonpath:
			self.textpath_dict = dict()
		self.current_scrap_id = 'none'

	def get_style(self, node):
		return simplestyle.parseStyle(node.get('style', ''))

	def get_style_attr(self, node, style, key, d=''):
		d = node.get(key, d)
		return style.get(key, d)

	def print_scrap_begin(self, id, test, options = {}):
		self.current_scrap_id = id

		if test:
			if 'scale' not in options and self.options.scale > 0:
				dpi = self.options.dpi or self.unittouu('1in')
				options['scale'] = '[0 0 %d 0 0 0 %d 0 inch]' % (dpi, self.options.scale)
			if 'projection' not in options and self.options.projection:
				options['projection'] = self.options.projection
			if 'author' not in options and self.options.author:
				options['author'] = as_unicode(self.options.author)
			options.update(parse_options(as_unicode(self.options.options)))
			print_utf8('\nscrap %s %s\n' % (id, format_options(options)))

	def print_scrap_end(self, test):
		if test:
			print("endscrap\n\n")

	def output(self):
		root = self.document.getroot()
		doc_width = self.unittouu(root.get('width') or '0')
		doc_height = self.unittouu(root.get('height') or '0')

		# load prefs from file
		th2pref_load_from_xml(root)
		th2pref.xyascenter = self.options.xyascenter

		viewBox = root.get('viewBox')
		if viewBox:
			doc_x, doc_y, doc_width, doc_height = [float(i) for i in viewBox.split()]
		else:
			doc_x, doc_y = 0, 0

		self.classes = {}
		stylenodes = self.document.xpath('//svg:style', namespaces=inkex.NSS)
		pattern = re.compile(r'\.(\w+)\s*\{(.*?)\}')
		for stylenode in stylenodes:
			if isinstance(stylenode.text, basestring):
				for x in pattern.finditer(stylenode.text):
					self.classes[x.group(1)] = simplestyle.parseStyle(x.group(2).strip())

		print('encoding  utf-8')
		if doc_width and doc_height:
			params = [doc_x, (doc_y + doc_height), (doc_x + doc_width), doc_y]
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
			#for node in reversed(images):
			for node in images:
				params = [ self.unittouu(node.get('x', '0')), self.unittouu(node.get('y', '0')) ]
				mat = self.i2d_affine(node)
				href = node.get(xlink_href, '')
				XVIroot = '{}'
				if href == '': # xvi image (svg:g)
					options = parse_options(node.get(therion_options, ''))
					href = options.get('href', '')
					XVIroot = options.get('XVIroot', '{}')
				elif href.startswith('data:'):
					inkex.errormsg('Embedded images not supported!')
					continue
				paramsTrans = transformParams(mat, params)
				mat = simpletransform.composeTransform(mat, [[1,0,params[0]],[0,1,params[1]]])
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
				print('##XTHERION## xth_me_image_insert {%s 1 1.0} {%s %s} "%s" 0 {}' % \
						(fstr2(paramsTrans[0]), fstr2(paramsTrans[1]), XVIroot, href))

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
				layers = [ root ]
			for layer in layers:
				if layer.get(therion_role) == 'none':
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
		id = id.replace(' ','_')
		options = parse_options_node(layer)
		self.print_scrap_begin(id, self.options.lay2scr, options)
		self.output_g(layer)
		self.print_scrap_end(self.options.lay2scr)

	def examine_insensitive_path(self, node, p_len):
		node_options = {}
		node_count = 0
		desc = node.xpath('svg:desc', namespaces=inkex.NSS)
		if len(desc) == 1:
			lines = desc[0].text.split('\n')
			for line in lines:
				a = line.split()
				if len(a) == 0:
					continue
				if a[0][0].isdigit() or a[0][0] == '-':
					node_count += 1
				else:
					if node_count not in node_options:
						node_options[node_count] = []
					node_options[node_count].append(line.strip())
			if node_count != p_len:
				inkex.errormsg('node_count = %d, p_len = %d' % (node_count, p_len))
				return [True, desc[0].text.rstrip()]
		return [False, node_options]

	def get_d(self, node):
		d = node.get(inkscape_original_d)
		if not d or not self.options.nolpe:
			d = node.get('d')
		if not d:
			if node.tag == svg_g:
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

	def output_line(self, node):
		mat = self.i2d_affine(node)

		# get therion attributes
		role, type, options = get_props(node)

		# text on path
		if th2pref.textonpath:
			node_id = node.get('id')
			if node_id in self.textpath_dict:
				type = 'label'
				options.update(self.textpath_dict[node_id])

		# get path data
		d = self.get_d(node)
		if not d:
			inkex.errormsg('no path data for element <{} id="{}">'.format(
				node, node.get('id')))
			return
		p = parsePath(d)

		# check on read-only path
		if node.get(sodipodi_insensitive, 'false') == 'true':
			p_len = len(p)
			for cmd,params in p:
				if cmd == 'Z':
					p_len -= 1
			check,ret = self.examine_insensitive_path(node, p_len)
			if check:
				print_utf8("line %s %s" % (type, format_options(options)))
				# TODO transformParams?
				print_utf8(ret)
				print("endline\n")
				return
			node_options = ret
		else:
			node_options = {}

		node_count = 0
		th2line = None
		for cmd,params in p:
			if cmd == 'M':
				if th2line != None:
					th2line.output()
				th2line = Th2Line(type)
				th2line.options.update(options)
			if cmd == 'Z':
				th2line.close()
			else:
				node_count += 1
				th2line.append(transformParams(mat, params))
				th2line.append_node_options(node_options.get(node_count, []))
		if th2line != None:
			th2line.output()
	
	def output_textblock(self, node):
		line = self.get_point_text(node)
		print_utf8(line)
		desc = node.xpath('svg:desc', namespaces=inkex.NSS)
		if len(desc) > 0:
			print_utf8(desc[0].text.rstrip())
		a = line.split()
		print('end' + a[0] + '\n')

	def get_point_text(self, node):
		text = ''
		if isinstance(node.text, basestring) and len(node.text.strip()) > 0:
			text = node.text.replace('\n', ' ')
		for child in node:
			if child.tag == svg_tspan or \
					not th2pref.textonpath and child.tag == svg_textPath:
				if len(text) > 0 and child.get(sodipodi_role, '') == 'line':
					text += '<br>'
				text += self.get_point_text(child)
			if isinstance(child.tail, basestring) and len(child.tail.strip()) > 0:
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
		fontsize = self.get_style_attr(node, style, 'font-size', '12')
		if fontsize[-1] == '%':
			fontsize = float(fontsize[:-1]) / 100.0 * 12;
		else:
			fontsize = self.unittouu(fontsize)
		if mat is not None:
			fontsize *= descrim(mat)
		fontsize /= th2pref.basescale
		if fontsize > 17:
			options['scale'] = 'xl'
		elif fontsize > 12:
			options['scale'] = 'l'
		elif fontsize <= 8:
			options['scale'] = 'xs'
		elif fontsize <= 9:
			options['scale'] = 's'

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

		visibility = options.pop('line-visibility', 'on')

		th2area = Th2Area(type)
		th2area.options.update(options)
		for cmd,params in p:
			if cmd == 'M':
				th2area.append_line()
				if visibility:
					th2area.current_line().options['visibility'] = visibility
			if cmd == 'Z':
				th2area.current_line().close()
			else:
				th2area.current_line().append(transformParams(mat, params))
		th2area.output(self.current_scrap_id)


if __name__ == '__main__':
	e = Th2Output()
	e.affect()

# vi:noexpandtab:sw=4:ts=4
