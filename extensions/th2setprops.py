#!/usr/bin/env python
'''
Copyright (C) 2008 Thomas Holder, http://sf.net/users/speleo3/
Distributed under the terms of the GNU General Public License v2 or later

Annotate SVG elements for therion export.
'''

from th2ex import *
from lxml import etree
import re

def asunicode(s):
	if isinstance(s, bytes):
		return s.decode('utf-8')
	return s

class Th2SetProps(Th2Effect):
	def __init__(self):
		inkex.Effect.__init__(self)
		self.OptionParser.add_option("--role", type="string", dest="role", default="")
		self.OptionParser.add_option("--type", type="string", dest="type", default="")
		self.OptionParser.add_option("--options", type="string", dest="options", default="")
		self.OptionParser.add_option("--merge", type="inkbool", dest="merge", default=True)
		self.OptionParser.add_option("--dropstyle", type="inkbool", dest="dropstyle", default=False)

	def update_options(self, options):
		'''Subclasses can update options here'''
		pass

	def effect(self):
		if len(self.selected) == 0:
			inkex.errormsg('warning: nothing selected')
			sys.exit(1)

		# th2ex prefs
		th2pref_load_from_xml(self.document.getroot())

		new_options = parse_options(asunicode(self.options.options))

		if self.options.dropstyle and 'th2style' not in self.doc_ids:
			template = open_in_pythonpath('th2_template.svg')
			doc_temp = etree.parse(template)
			template.close()
			defs_temp = doc_temp.find(inkex.addNS('defs', 'svg'))
			defs_self = self.document.find(inkex.addNS('defs', 'svg'))
			if defs_self is None:
				doc_temp.getroot().remove(defs_temp)
				self.document.getroot().insert(0, defs_temp)
			else:
				children = defs_temp.getchildren()
				defs_temp.clear()
				defs_self.extend(children)
			self.getdocids()

		# iterate over elements in selection order
		for id in self.options.ids:
			node = self.selected[id]

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

			self.update_options(options)

			type_ = type

			if ':' in type:
				type, subtype = type.split(':', 1)
			else:
				subtype = options.get('subtype', '')

			# update symbols
			if role == 'point':
				for href in [role + '-' + type + '_' + subtype, role + '-' + type]:
					if href in self.doc_ids:
						break
				else:
					href = None

				# convert arbitrary shape to clone (only with dropstyle=True)
				if href and node.tag != svg_use and self.options.dropstyle:
					bbox = self.compute_bbox(node, False)
					if bbox is not None:
						parent = node.getparent()
						parent.remove(node)
						node = etree.SubElement(parent, svg_use, {
							"x": str((bbox[0] + bbox[1]) / 2.0),
							"y": str((bbox[2] + bbox[3]) / 2.0),
							"id": id,
						})
						self.selected[id] = node

				if href and node.tag == svg_use:
					node.set(xlink_href, '#' + href)

			# update path effects
			elif node.tag == svg_path and role in ['line', 'area', '']:
				node.set('class', '%s %s %s' % (role or 'line', type, subtype))
				if self.options.dropstyle:
					node.set('style', '')
				for href in ['LPE-' + type + '_' + subtype, 'LPE-' + type]:
					if href in self.doc_ids:
						node.set(inkscape_path_effect, '#' + href)
						if inkscape_original_d not in node.attrib:
							node.set(inkscape_original_d, node.get('d'))
						node.attrib.pop('d', None)
						break
				else:
					if self.options.dropstyle and \
							inkscape_path_effect in node.attrib:
						del node.attrib[inkscape_path_effect]
						if inkscape_original_d in node.attrib:
							node.set('d', node.get(inkscape_original_d))
							del node.attrib[inkscape_original_d]

			set_props(node, role, type_, options)

if __name__ == '__main__':
	e = Th2SetProps()
	e.affect()

# vi:noexpandtab:ts=4
