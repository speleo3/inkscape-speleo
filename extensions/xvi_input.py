#!/usr/bin/env python
'''
Convert XVI file to SVG

Copyright (C) Thomas Holder
Distributed under the terms of the GNU General Public License v2 or later
'''

from __future__ import print_function
from __future__ import absolute_import

import sys
import th2ex

if sys.version_info[0] < 3:
	import Tkinter
	binarystdout = sys.stdout
else:
	import tkinter as Tkinter
	binarystdout = sys.stdout.buffer

from lxml import etree
from inkex import NSS

NSS[None] = NSS["svg"]


def xvi2svg(handle, fullsvg=True, strokewidth=3, XVIroot=''):
	# file contents
	filecontents = ''.join(handle)
	tk_instance = Tkinter.Tcl().tk.eval
	tk_instance(filecontents)

	# methods
	def str_tcl2py(name):
		if tk_instance('info exists ' + name) == '0':
			return ''
		return tk_instance('lindex $%s' % (name))
	def list_tcl2py(name):
		if tk_instance('info exists ' + name) == '0':
			return []
		L = int(tk_instance('llength $%s' % (name)))
		return [tk_instance('lindex $%s %d' % (name, i)) for i in range(L)]
	def invert_str(x):
		if x[0] == '-':
			return x[1:]
		return '-' + x

	# parse into python objects
	stations = list_tcl2py('XVIstations')
	shots = list_tcl2py('XVIshots')
	sketchlines = list_tcl2py('XVIsketchlines')
	grid = list_tcl2py('XVIgrid')
	root_translate = None

	if fullsvg:
		root = etree.Element('svg', nsmap=NSS)
	else:
		root = etree.Element('g', nsmap=NSS)

	for line in sketchlines:
		color, coords_str = line.split(None, 1)
		coords = coords_str.split()
		coords[1::2] = map(invert_str, coords[1::2])
		coords_str = ' '.join(coords)
		if len(coords) == 2:
			e = etree.SubElement(root, 'circle', {
				'cx': coords[0],
				'cy': coords[1],
				'r': str(strokewidth),
				'style': 'fill:%s;stroke:none' % (color),
			})
		elif len(coords) > 2:
			e = etree.SubElement(root, 'path', {
				'd': 'M ' + coords_str,
				'style': 'fill:none;stroke:%s;stroke-width:%f' % (color, strokewidth),
			})

	g_shots = etree.SubElement(root, 'g', {th2ex.inkscape_label: 'Shots'})
	for line in shots:
		coords = line.split()
		coords[1::2] = map(invert_str, coords[1::2])
		coords_str = ' '.join(coords)
		e = etree.SubElement(g_shots, 'path', {
			'd': 'M ' + coords_str,
			'style': 'fill:none;stroke:#999;stroke-width:%f' % (strokewidth),
		})

	g_stations = etree.SubElement(root, 'g', {th2ex.inkscape_label: 'Stations'})
	for line in stations:
		x, y, label = line.split()
		y = invert_str(y)
		e = etree.SubElement(g_stations, 'text', {
			'x': x,
			'y': y,
		})
		e.text = label
		if XVIroot == label:
			root_translate = -float(x), -float(y)
	
	if not XVIroot:
		x, y, dx, _, _, dy, nx, ny = grid
		height = float(dy) * float(ny)
		if fullsvg:
			root.set('viewBox', '%s %f %f %f' % (x, -float(y)-height,
				float(dx) * float(nx), height))
		else:
			root.set('transform', 'translate(%f,%f)' % (-float(x), -float(y)))
	elif root_translate is not None:
		root.set('transform', 'translate(%f,%f)' % root_translate)

	return root

if __name__ == '__main__':
	if len(sys.argv) > 1:
		handle = open(th2ex.find_in_pwd(sys.argv[-1]))
	else:
		handle = sys.stdin
	root = xvi2svg(handle)
	handle.close()
	binarystdout.write(etree.tostring(root, encoding='utf-8', xml_declaration=True))
	binarystdout.write(b'\n')

# vi:noexpandtab
