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


def xvi2svg(handle, fullsvg=True, strokewidth=6, XVIroot='',
			scale: float = 200.0):
	"""
	Args:
	  scale: Scale as 1:scale (ignored with XVIroot or fullsvg=False)
	"""
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
	stationcoords = set(tuple(line.split()[:2]) for line in stations)

	root = etree.fromstring("""<?xml version="1.0" ?>
<svg
   xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
   xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd"
   xmlns:therion="http://therion.speleo.sk/therion"
   xmlns="http://www.w3.org/2000/svg">
</svg>
""")

	if not fullsvg:
		root = etree.SubElement(root, th2ex.svg_g)

	g_shots = etree.SubElement(root, th2ex.svg_g, {th2ex.inkscape_label: 'Shots'})

	def process_shots(splays: bool):
		style = (f"stroke:#f00;stroke-width:{strokewidth / 2}" if (not splays) else
				 f"stroke:#fc0;stroke-width:{strokewidth / 4}")
		for line in shots:
			coords = line.split()
			is_leg = (tuple(coords[0:2]) in stationcoords and
					  tuple(coords[2:4]) in stationcoords)
			if is_leg == splays:
				continue
			coords[1::2] = map(invert_str, coords[1::2])
			coords_str = ' '.join(coords)
			etree.SubElement(g_shots, th2ex.svg_path, {
				'd': 'M ' + coords_str,
				'style': f'fill:none;' + style,
			})

	process_shots(True)
	process_shots(False)

	for line in sketchlines:
		color, coords_str = line.split(None, 1)
		coords = coords_str.split()
		coords[1::2] = map(invert_str, coords[1::2])
		coords_str = ' '.join(coords)
		if len(coords) == 2:
			e = etree.SubElement(root, th2ex.svg_circle, {
				'cx': coords[0],
				'cy': coords[1],
				'r': str(strokewidth),
				'style': 'fill:%s;stroke:none' % (color),
			})
		elif len(coords) > 2:
			e = etree.SubElement(root, th2ex.svg_path, {
				'd': 'M ' + coords_str,
				'style': 'fill:none;stroke:%s;stroke-width:%f' % (color, strokewidth),
			})

	g_stations = etree.SubElement(root, th2ex.svg_g, {th2ex.inkscape_label: 'Stations'})
	for line in stations:
		x, y, label = line.split()
		y = invert_str(y)
		e = etree.SubElement(g_stations, th2ex.svg_text, {
			'style': f'font-size: {strokewidth*10}',
			'x': x,
			'y': y,
		})
		e.text = label
		# station could exist multiple times, take first one
		if root_translate is None and XVIroot == label:
			root_translate = -float(x), -float(y)
	
	x, y, dx, _, _, dy, nx, ny = map(float, grid)
	width = dx * nx
	height = dy * ny
	y_top = -y - height

	root.set(th2ex.therion_xvi_dx, str(dx))
	root.set(th2ex.therion_xvi_dy, str(dy))

	if root_translate is not None:
		root.set('transform', 'translate(%f,%f)' % root_translate)
	elif fullsvg:
		scale /= 100  # cm
		root.set('width', f"{nx/scale}cm")
		root.set('height', f"{ny/scale}cm")
		root.set('viewBox', '%f %f %f %f' % (x, y_top, width, height))
	else:
		root.set('transform', 'translate(%f,%f)' % (-float(x), -float(y)))

	root.set("style", "stroke-linecap:round;stroke-linejoin:round")

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
