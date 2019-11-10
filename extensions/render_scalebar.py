# -*- coding: utf-8 -*-
'''
Copyright (C) 2008 Thomas Holder, http://sf.net/users/speleo3/
Distributed under the terms of the GNU General Public License v2 or later
'''

import math
try:
	import inkex
except:
	import speleoex
	import inkex
import simpletransform

def i2d_affine(self, node):
    m2 = simpletransform.parseTransform(node.get('transform'))
    while True:
        node = node.getparent()
        if node is None:
            break
        viewBox = node.get('viewBox')
        t1 = node.get('transform')
        if viewBox:
            viewBox = [float(i) for i in viewBox.split()]
            doc_width = self.unittouu(node.get('width', viewBox[2]))
            doc_height = self.unittouu(node.get('height', viewBox[3]))
            m1 = [[doc_width / viewBox[2], 0, -viewBox[0]], [0, doc_height / viewBox[3], -viewBox[1]]]
        elif t1:
            m1 = simpletransform.parseTransform(t1)
        else:
            continue
        m2 = simpletransform.composeTransform(m1, m2)
    return m2

def det(mat):
    return mat[0][0] * mat[1][1] - mat[0][1] * mat[1][0]

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

class Scalebar:
	def __init__(self, scale, dpi = 96, text = "Scale", docunit = 1.0):
		mag = int(math.log10(scale))

		if mag < 2:
			units = 'cm'
			factor = 10 ** mag
		elif mag < 5:
			units = 'm'
			factor = 10 ** (mag - 2)
		else:
			units = 'km'
			factor = 10 ** (mag - 5)

		step = scale / (10 ** mag)

		if step < 2:
			step = 1
		elif step < 5:
			step = 2
		else:
			step = 5

		steplength = dpi / 2.54 / scale * step * 10 ** mag / docunit;

		d = "m%f,0 h-%f v%f h%f z " % (2 * steplength, steplength, 7 / docunit, steplength) * 3
		d = d.replace(' ', ' m-%f,0 ' % steplength, 1)

		self.g = inkex.etree.Element('g')
		self.g.set('style', 'font-size:10px;text-anchor:middle;font-family:sans-serif')
		self.g.set(inkex.addNS('label', 'inkscape'), 'none scalebar')

		node = inkex.etree.Element('path')
		node.set('d', d)
		node.set('style', 'fill:black;stroke:none')
		self.g.append(node)

		node = inkex.etree.Element('path')
		node.set('d', 'M0,0 h%f M0,%f h%f' % (steplength * 5, 7 / docunit, steplength * 5))
		node.set('style', 'fill:none;stroke:black;stroke-width:' + str(0.5 / docunit))
		self.g.append(node)

		for i in range(6):
			node = inkex.etree.Element('text')
			node.set('x', str(steplength * i * docunit))
			node.set('y', str(18))
			node.set('transform', 'scale(' + str(1 / docunit) + ')')
			node.text = str(step * i * factor)
			if i == 5:
				node.text += units
			self.g.append(node)

		if len(text):
			if isinstance(text, bytes):
				text = text.decode('utf-8')
			node = inkex.etree.Element('text')
			node.set('y', str(-5))
			node.set('style', 'text-anchor:start')
			node.set('transform', 'scale(' + str(1 / docunit) + ')')
			node.text = text + " 1:" + str(scale)
			self.g.append(node)
	
	def get_tree(self):
		return self.g
	
	def get_xml(self):
		return inkex.etree.tostring(self.g)

class InsertScalebar(inkex.Effect):

	try:
		inkex.Effect.unittouu
	except AttributeError:
		unittouu = inkex.unittouu

	def __init__(self):
		inkex.Effect.__init__(self)
		self.OptionParser.add_option("--scale",
						action="store", type="int",
						dest="scale", default=100,
						help="Scale")
		self.OptionParser.add_option("--dpi",
						action="store", type="int",
						dest="dpi", default=96,
						help="DPI")
		self.OptionParser.add_option("--text",
				action="store", type="string", 
				dest="text", default="")

	
	def get_current_layer(self):
		layer = self.current_layer
		while True:
			groupmode = layer.get(inkex.addNS('groupmode', 'inkscape'))
			if groupmode == 'layer':
				break
			parent = layer.getparent()
			if parent is None:
				break
			layer = parent
		return layer

	# TODO verify height is correct in case of viewBox
	def dt2doc(self, xy):
		root = self.document.getroot()
		height = root.get('height', '100%')
		if height[-1] == '%':
			height = 1052.36 # assume default A4 height
		else:
			height = self.unittouu(height)
		y = height - xy[1]
		return (xy[0], y)
	
	def effect(self):
		layer = self.get_current_layer()
		affine = inverse(i2d_affine(self, layer))
		transform = simpletransform.formatTransform(affine) + \
			' translate' + str(self.view_center)

		g = Scalebar(self.options.scale, self.options.dpi, self.options.text, self.uutounit(1, 'px')).get_tree()
		g.set('transform', transform)
		layer.append(g)

if __name__ == '__main__':
	e = InsertScalebar()
	e.affect()

#vi:noexpandtab:ts=4:sw=4:sw=4
