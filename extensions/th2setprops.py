#!/usr/bin/python
'''
Copyright (C) 2008 Thomas Holder, http://sf.net/users/speleo3/
Distributed under the terms of the GNU General Public License v2

Annotate SVG elements for therion export.
'''

from th2ex import *
import re

class Th2SetProps(inkex.Effect):
	def __init__(self):
		inkex.Effect.__init__(self)
		self.OptionParser.add_option("--role", type="string", dest="role", default="")
		self.OptionParser.add_option("--type", type="string", dest="type", default="")
		self.OptionParser.add_option("--options", type="string", dest="options", default="")
		self.OptionParser.add_option("--merge", type="inkbool", dest="merge", default=True)
		self.OptionParser.add_option("--dropstyle", type="inkbool", dest="dropstyle", default=False)

	def effect(self):
		new_options = parse_options(self.options.options.decode('UTF-8'))

		for id, node in self.selected.iteritems():
			# current props
			role, type, options = get_props(node)
			
			# new props
			if not self.options.merge:
				options = dict()
			options.update(new_options)

			if len(self.options.role) > 0 and self.options.role != '_none_':
				role = self.options.role

			if len(self.options.type) > 0:
				type = self.options.type
				if self.options.type == 'section' and 'direction' not in options:
					options['direction'] = 'begin'

			# fallback default props
			if role == '':
				inkex.errormsg('warning: empty role')
				role = 'line'
			if type == '':
				inkex.errormsg('warning: empty type')
				type = 'wall'

			set_props(node, role, type, options)

			if ':' in type:
				type, subtype = type.split(':', 1)

			# update symbols
			if node.tag == svg_use:
				href = role + '-' + type
				if href in self.doc_ids:
					node.set(xlink_href, '#' + href)

			# update path effects
			elif node.tag == svg_path and role in ['line', '']:
				node.set('class', 'line ' + type)
				if self.options.dropstyle:
					node.set('style', '')
				href = 'LPE-' + type
				if href in self.doc_ids:
					node.set(inkscape_path_effect, '#' + href)
					if not node.attrib.has_key(inkscape_original_d):
						node.set(inkscape_original_d, node.get('d'))

e = Th2SetProps()
e.affect()

