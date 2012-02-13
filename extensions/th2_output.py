#!/usr/bin/env python 
'''
Copyright (C) 2008 Thomas Holder, http://sf.net/users/speleo3/
Distributed under the terms of the GNU General Public License v2

This program was inspired by http://www.cavediving.de/svg2th2.py
'''

from th2ex import *
import simplepath, simpletransform, simplestyle, math, re

# some prefs
_pref_image_inkscape = False

def parse_options_node(node):
	options = node.get(therion_options, '')
	return parse_options(options.split())

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

def bbox_center(bbox):
	return [ (bbox[0] + bbox[1])*0.5, (bbox[2] + bbox[3])*0.5 ]

def path_center(node):
	d = node.get('d')
	p = simpletransform.cubicsuperpath.parsePath(d)
	bbox = simpletransform.roughBBox(p)
	return bbox_center(bbox)
	
def g_center(node):
	backup_transform = node.get('transform')
	if backup_transform is not None:
		del node.attrib['transform']
	bbox = simpletransform.computeBBox(node)
	if backup_transform is not None:
		node.set('transform', backup_transform)
	return bbox_center(bbox)

def orientation(mat):
	try:
		# matrix may be skewed, so averaging multiple possibilities;
		# without skew, one atan2 would be sufficient!
		at0 = math.atan2(mat[0][1], mat[0][0])
		at1 = math.atan2(mat[1][0], mat[0][0])
		at2 = math.atan2(mat[0][1], -mat[1][1])
		at3 = math.atan2(mat[1][0], -mat[1][1])
		deg = math.degrees(-1.0 * (at0 + at1 + at2 + at3) / 4.0)
		if deg < 0:
			deg += 360
		return deg
	except:
		return 0.0

def fstr(x):
	s = "%.4f" % x
	i = len(s) - 1
	while s[i] == '0': i -= 1
	if s[i] == '.': i += 1
	return s[:i+1]

class Th2Line:
	def __init__(self, type = 'wall'):
		self.type = type
		self.options = {}
		self.points = []
	def append(self, params):
		self.points.append(" ".join(fstr(i) for i in params))
	def append_node_options(self, olist):
		for o in olist:
			self.points.append(o)
	def close(self):
		self.options['close'] = 'on'
	def output(self):
		print_utf8("line %s %s" % (self.type, format_options(self.options)))
		print "  " + "\n  ".join(self.points)
		print "endline\n"

class Th2Output(inkex.Effect):
	def __init__(self):
		inkex.Effect.__init__(self)
		self.OptionParser.add_option("--scale",    type="int",     dest="scale",    default=100)
		self.OptionParser.add_option("--dpi",      type="int",     dest="dpi",      default=90)
		self.OptionParser.add_option("--linetype", type="string",  dest="linetype", default="wall")
		self.OptionParser.add_option("--layers",   type="string",  dest="layers",   default="all")
		self.OptionParser.add_option("--images",   type="inkbool", dest="images",   default=True)
		self.OptionParser.add_option("--nolpe",    type="inkbool", dest="nolpe",    default=True)
		self.OptionParser.add_option("--lay2scr",  type="inkbool", dest="lay2scr",  default=True)

	def i2d_affine(self, node):
		m2 = simpletransform.parseTransform(node.get('transform'))
		while True:
			node = node.getparent()
			if node is None:
				break
			t1 = node.get('transform')
			if not t1:
				continue
			m1 = simpletransform.parseTransform(t1)
			m2 = simpletransform.composeTransform(m1, m2)
		m2 = simpletransform.composeTransform(self.r2d, m2)
		return m2

	def print_scrap_begin(self, id, test, options = {}):
		if test:
			if not options.has_key('scale') and self.options.scale > 0:
				options['scale'] = '[0 0 %d 0 0 0 %d 0 inch]' % (self.options.dpi, self.options.scale)
			print_utf8('\nscrap %s %s\n' % (id, format_options(options)))

	def print_scrap_end(self, test):
		if test:
			print "endscrap\n"

	def output(self):
		doc_width = inkex.unittouu(self.document.getroot().get('width'))
		doc_height = inkex.unittouu(self.document.getroot().get('height'))

		self.r2d = [[1, 0, 0],[0, -1, doc_height]]
		viewBox = self.document.getroot().get('viewBox')
		if viewBox:
			viewBox = [float(i) for i in viewBox.split()]
			m1 = [[doc_width / viewBox[2], 0, -viewBox[0]], [0, doc_height / viewBox[3], -viewBox[1]]]
			self.r2d = simpletransform.composeTransform(self.r2d, m1)

		self.classes = {}
		stylenodes = self.document.xpath('//svg:style', namespaces=inkex.NSS)
		pattern = re.compile(r'\.(\w+)\s*\{(.*?)\}')
		for stylenode in stylenodes:
			if isinstance(stylenode.text, str):
				for x in pattern.finditer(stylenode.text):
					self.classes[x.group(1)] = simplestyle.parseStyle(x.group(2).strip())

		print '''encoding  utf-8
##XTHERION## xth_me_area_adjust 0 0 %f %f
##XTHERION## xth_me_area_zoom_to 100
''' % (doc_width, doc_height)

		if self.options.images:
			images = self.document.xpath('//svg:image', namespaces=inkex.NSS)
			#for node in reversed(images):
			for node in images:
				params = [ inkex.unittouu(node.get('x', '0')), inkex.unittouu(node.get('y', '0')) ]
				mat = self.i2d_affine(node)
				href = node.get(xlink_href)
				paramsTrans = transformParams(mat, params)
				mat = simpletransform.composeTransform(mat, [[1,0,params[0]],[0,1,params[1]]])
				w = node.get('width', '100%')
				h = node.get('height', '100%')
				if _pref_image_inkscape:
					print '##INKSCAPE## image %s %s %s %s' % (w, h, simpletransform.formatTransform(mat), href)
					continue
				if href.startswith('file://'):
					href = href[7:]
				print '##XTHERION## xth_me_image_insert {%f 1 1.0} {%f {}} "%s" 0 {}' % \
						(paramsTrans[0], paramsTrans[1], href)

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
				layers = [ self.document.getroot() ]
			for layer in layers:
				if layer.get(therion_role) == 'none':
					continue
				if self.options.layers == 'visible':
					style = simplestyle.parseStyle(layer.get('style', ''))
					if style.get('display') == 'none':
						continue
				self.output_scrap(layer)

		self.print_scrap_end(not self.options.lay2scr)

	def output_g(self, node):
		for child in reversed(node):
			if isinstance(child, inkex.etree._Comment):
				if child.text.startswith('#therion'):
					print_utf8(child.text.split('\n', 1)[1])
				continue

			role, type, options = get_props(child)

			if role == 'none':
				continue

			if self.options.layers == 'visible':
				style = simplestyle.parseStyle(child.get('style', ''))
				if style.get('display') == 'none':
					continue

			if role == 'textblock':
				self.output_textblock(child)
			elif role == 'point':
				self.output_point(child)
			elif role == 'line':
				self.output_line(child)
			elif child.tag == svg_g:
				self.output_g(child)

	def output_scrap(self, layer):
		id = layer.get(inkscape_label)
		if not id:
			id = layer.get('id')
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

	def output_line(self, node):
		mat = self.i2d_affine(node)

		# get therion attributes
		role, type, options = get_props(node)

		# get path data
		d = node.get(inkscape_original_d)
		if not d or not self.options.nolpe:
			d = node.get('d')
		if not d and node.attrib.has_key('points'):
			d = 'M' + node.get('points')
			if node.tag == svg_polygon:
				d += ' z'
		if not d and node.attrib.has_key('x1'):
			d = 'M' + node.get('x1') + ',' + node.get('y1') + 'L' + node.get('x2') + ',' + node.get('y2')
		if not d:
			return
		p = simplepath.parsePath(d)

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
				print "endline\n"
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
		print 'end' + a[0] + '\n'

	def get_point_text(self, node):
		text = ''
		if isinstance(node.text, basestring) and len(node.text.strip()) > 0:
			text = node.text.replace('\n', ' ')
		for child in node:
			if child.tag in [ svg_tspan, svg_textPath ]:
				if len(text) > 0 and child.get(sodipodi_role, '') == 'line':
					text += '<br>'
				text += self.get_point_text(child)
			if isinstance(child.tail, basestring) and len(child.tail.strip()) > 0:
				text += child.tail.replace('\n', ' ')
		return text
	
	align_rl = {
		# (append to b/t, single value)
		'start': ('r', 'r'),
		'middle': ('', 'c'),
		'end': ('l', 'l'),
	}

	def output_point(self, node):
		mat = self.i2d_affine(node)

		# get x/y
		if node.attrib.has_key('cx'):
			params = [ inkex.unittouu(node.get('cx')), inkex.unittouu(node.get('cy', '0')) ]
		elif node.attrib.has_key('x'):
			params = [ inkex.unittouu(node.get('x')), inkex.unittouu(node.get('y', '0')) ]
		elif node.attrib.has_key(sodipodi_cx):
			params = [ inkex.unittouu(node.get(sodipodi_cx)),
				inkex.unittouu(node.get(sodipodi_cy, '0')) ]
		elif node.tag == svg_path:
			params = path_center(node)
		elif node.tag == svg_g:
			params = g_center(node)
		else:
			params = [ 0, 0 ]
		params = transformParams(mat, params)

		# get therion attributes
		role, type, options = get_props(node)

		if node.tag == svg_text:
			# restore text for labels etc.
			key = text_keys_output.get(type, 'text')
			options[key] = self.get_point_text(node).strip()
			if options[key] == "":
				inkex.errormsg("dropping empty text element (point %s)" % (type))
				return

			if type not in ['station', 'dimensions']:
				# guess text alignment
				style = simplestyle.parseStyle(node.get('style', ''))
				textanchor = style.get('text-anchor', node.get('text-anchor', 'start'))
				if textanchor in self.align_rl:
					align = options.get('align', 't')
					if align[0] in ['t', 'b']:
						align = align[0] + self.align_rl[textanchor][0]
					else:
						align = self.align_rl[textanchor][1]
					options['align'] = align

				# guess font scale
				fontsize = style.get('font-size', node.get('font-size', '12'))
				if fontsize[-1] == '%':
					fontsize = float(fontsize[:-1]) / 100.0 * 12;
				else:
					fontsize = inkex.unittouu(fontsize)
				fontsize *= descrim(mat)
				if fontsize > 17:
					options['scale'] = 'xl'
				elif fontsize > 12:
					options['scale'] = 'l'
				elif fontsize <= 8:
					options['scale'] = 'xs'
				elif fontsize <= 9:
					options['scale'] = 's'

			if type == 'altitude' and options[key].isdigit():
				options[key] = "[fix " + options[key] + "]"

		# restore orientation from transform
		orient = orientation(mat)
		if orient > 0.05:
			options['orientation'] = orient

		# output in therion format
		print_utf8("point %s %s %s %s" % (fstr(params[0]), fstr(params[1]), type, format_options(options)))

if __name__ == '__main__':
	e = Th2Output()
	e.affect()
