# -*- coding: utf-8 -*-
'''
Copyright (C) 2008 Thomas Holder, http://sf.net/users/speleo3/
Distributed under the terms of the GNU General Public License v2
'''

import math
try:
	import inkex
except:
	import speleoex
	import inkex
import simpletransform

def i2d_affine(node):
    m2 = simpletransform.parseTransform(node.get('transform'))
    while True:
        node = node.getparent()
        if node is None:
            break
        viewBox = node.get('viewBox')
        t1 = node.get('transform')
        if viewBox:
            viewBox = [float(i) for i in viewBox.split()]
            doc_width = inkex.unittouu(node.get('width', viewBox[2]))
            doc_height = inkex.unittouu(node.get('height', viewBox[3]))
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
	def __init__(self, scale, dpi = 90):
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

		steplength = dpi / 2.54 / scale * step * 10 ** mag

		d = "m%f,0 h-%f v7 h%f z " % (2 * steplength, steplength, steplength) * 3
		d = d.replace(' ', ' m-%f,0 ' % steplength, 1)

		self.g = inkex.etree.Element('g')
		self.g.set('style', 'font-size:10px;text-anchor:middle;font-family:sans-serif')
		self.g.set(inkex.addNS('label', 'inkscape'), 'none scalebar')

		node = inkex.etree.Element('path')
		node.set('d', d)
		node.set('style', 'fill:black;stroke:none')
		self.g.append(node)

		node = inkex.etree.Element('path')
		node.set('d', 'M0,0 h%f M0,7 h%f' % (steplength * 5, steplength * 5))
		node.set('style', 'fill:none;stroke:black;stroke-width:0.5')
		self.g.append(node)

		for i in range(6):
			node = inkex.etree.Element('text')
			node.set('x', str(steplength * i))
			node.set('y', '18')
			node.text = str(step * i * factor)
			if i == 5:
				node.text += units
			self.g.append(node)

		node = inkex.etree.Element('text')
		node.set('y', '-5')
		node.set('style', 'text-anchor:start')
		node.text = u"Maßstab 1:" + str(scale)
		self.g.append(node)
	
	def get_tree(self):
		return self.g
	
	def get_xml(self):
		return inkex.etree.tostring(self.g)

class InsertScalebar(inkex.Effect):
	def __init__(self):
		inkex.Effect.__init__(self)
		self.OptionParser.add_option("--scale",
						action="store", type="int",
						dest="scale", default=100,
						help="Scale")
		self.OptionParser.add_option("--dpi",
						action="store", type="int",
						dest="dpi", default=90,
						help="DPI")
	
	def get_current_layer(self):
		layer = self.current_layer
		while True:
			groupmode = layer.get(inkex.addNS('groupmode', 'inkscape'))
			if groupmode == 'layer':
				break
			parent = layer.getparent()
			if parent == None:
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
			height = inkex.unittouu(height)
		y = height - xy[1]
		return (xy[0], y)
	
	def effect(self):
		layer = self.get_current_layer()
		affine = inverse(i2d_affine(layer))
		transform = simpletransform.formatTransform(affine) + \
			' translate' + str(self.view_center)

		g = Scalebar(self.options.scale, self.options.dpi).get_tree()
		g.set('transform', transform)
		layer.append(g)

if __name__ == '__main__':
	e = InsertScalebar()
	e.affect()

