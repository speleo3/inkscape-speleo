#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Copyright (C) 2008-2023 Thomas Holder, https://github.com/speleo3
Distributed under the terms of the GNU General Public License v2 or later

Converts Survex 3D files (*.3d) to SVG.

If you select extend view and there is a *.espec file with same
basename as the *.3d file, it will be passed to the extend binary
with the --specfile option. See "extend" manpage for details.

Related:
 * https://survex.com/docs/3dformat.htm
'''

import argparse
import math
import os
import sys
from struct import unpack


def boolchoice(choices=()) -> dict:
    """
    Helper for boolean or choice arguments which is compatible with Inkscape's
    boolean inx type.

    Args:
            choices: Values which are accepted in addition to the standard boolean
            values.
    """
    mapper = {
        "0": False,
        "1": True,
        "false": False,
        "true": True,
    }
    mapper.update({
        key: key
        for key in choices
    })

    meta = "{" + ",".join(("0", "1") + tuple(choices)) + "}"

    return {"metavar": meta, "type": mapper.__getitem__}


STATIONNAMES_FULL = "full"

argparser = argparse.ArgumentParser(epilog=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
argparser.add_argument("--scale", type=int, default=100, help="Import with a scale of 1:ARG (default %(default)s)")
argparser.add_argument("--view", type=int, default=0, choices=(0, 1, 2), help="0: Plan (default), 1: Profile, 2: Extend")
argparser.add_argument("--bearing", metavar="[0-359]", type=int, default=0, help="Bearing in degrees north (default %(default)s)")
argparser.add_argument("--markers", type=int, default=1, choices=(0, 1, 2, 3), help="0: No station markers, "
                       "1: Display stations as small circles (default), 2: ditto as triangles, 3: triangles as clones")
argparser.add_argument(
    "--extend-cmd",
    default="extend",
    help='The "extend" program is part of Survex and required for --view=2. '
    'If it is not found inside PATH, you may specify the absolute path for the binary with ARG.\n'
    'Example: --extend-cmd="C:\\Programme\\Survex\\extend.exe"\n'
    'Example: --extend-cmd="/usr/local/bin/extend"')
argparser.add_argument("--scalebar", default=True, **boolchoice(), help="1: Draw scalebar")
argparser.add_argument("--annotate", default=True, **boolchoice(), help="1: Annotate for Therion Export")
argparser.add_argument("--filter", metavar="prefix", default='', help="Filter by label prefix and trim prefix off (TODO: implement and check therion book)")
argparser.add_argument("--stationnames", default=True, **boolchoice([STATIONNAMES_FULL]), help="Draw station names")
argparser.add_argument("--use_inkscape_label", default=True, **boolchoice(), help="Use inkscape:label for therion annotation")
argparser.add_argument("--use_therion_attribs", default=True, **boolchoice(), help="Use therion:... attributes for annotation")
argparser.add_argument("--surveys", default="create", choices=("create", "ignore"))
argparser.add_argument("infile", help="Input .3d file")
args = vars(argparser.parse_args())

infile = args["infile"]

# from th2ex


def name_survex2therion(name):
    if args['surveys'] == 'ignore':
        return name
    x = name.split('.')
    if len(x) == 1:
        return name
    return x[-1] + '@' + '.'.join(reversed(x[:-1]))


def die(msg):
    sys.stderr.write(msg + "\n")
    sys.stderr.write(argparser.format_help())
    sys.exit(1)


args['use_inkscape_label'] *= args['annotate']
args['use_therion_attribs'] *= args['annotate']
filter_len = len(args['filter'])

if args['view'] == 2:
    if not infile.endswith('_extend.3d'):
        command = args['extend_cmd'] + ' "' + infile + '"'
        if os.path.exists(infile[:-3] + '.espec'):
            command += ' --specfile="' + infile[:-3] + '.espec"'
        pipe = os.popen(command)
        if pipe.close() != None:
            die("extend failed")
        infile = infile[:-3] + '_extend.3d'
    args['bearing'] = 0

if not os.path.exists(infile):
    infile = os.path.join(os.environ['PWD'], infile)
f = open(infile, 'rb')

line = f.readline()  # File ID
if not line.startswith(b'Survex 3D Image File'):
    die("not a Survex 3D File, aborting")

line = f.readline()  # File format version
assert line.startswith(b'v')
ff_version = int(line[1:])

line = f.readline()  # Survex title
if line.rstrip().endswith(b' (extended)'):
    args['view'] = 2
    args['bearing'] = 0

line = f.readline()  # Timestamp

_cos = math.cos(math.radians(args['bearing']))
_sin = math.sin(math.radians(args['bearing']))

coords = []
coords_splay = []
curr_label = ''
labels = {}


def read_xyz():
    x, y, z = unpack('<iii', f.read(12))
    if args['bearing']:
        [x, y] = [x * _cos - y * _sin, x * _sin + _cos * y]
    if args['view'] > 0:
        [y, z] = [z, y]
    return [x, -y, z]


def read_len():
    length = read_byte()
    if length == 0xfe:
        length += unpack('<H', f.read(2))[0]
    elif length == 0xff:
        length += unpack('<I', f.read(4))[0]
    return length


def _read_label(n):
    return f.read(n).decode('utf-8', errors='replace')


def read_label():
    len = read_len()
    if len > 0:
        global curr_label
        curr_label += _read_label(len)


def read_len_v8():
    byte = read_byte()
    if byte != 0xFF:
        return byte
    return unpack('<I', f.read(4))[0]


def read_label_v8():
    global curr_label
    byte = read_byte()
    if byte != 0x00:
        ndel = byte >> 4
        nadd = byte & 0x0F
    else:
        ndel = read_len_v8()
        nadd = read_len_v8()
    oldlen = len(curr_label)
    # TODO ndel is byte count, not unicode character count
    curr_label = curr_label[:oldlen - ndel] + _read_label(nadd)


def skip_bytes(n):
    return f.read(n)


def read_byte():
    byte = f.read(1)
    if len(byte) != 1:
        return -1
    return ord(byte)


def _label(xyz, flags):
    if filter_len == 0:
        labels[curr_label] = xyz[0:2]
    elif curr_label.startswith(args['filter']):
        tmp_label = curr_label[filter_len:]
        labels[tmp_label] = xyz[0:2]


if ff_version >= 8:
    flags = read_byte()

    style = -1
    xyz_move = None

    while True:
        byte = read_byte()
        if byte == -1:
            break

        if byte <= 0x05:
            # STYLE_*
            if byte == 0x00 and style == 0x00:
                break
            style = byte
        elif byte <= 0x0e:
            # Reserved
            continue
        elif byte == 0x0f:
            # MOVE
            xyz_move = read_xyz()
        elif byte == 0x10:
            # DATE
            pass
        elif byte == 0x11:
            # DATE
            skip_bytes(2)
        elif byte == 0x12:
            # DATE
            skip_bytes(3)
        elif byte == 0x13:
            # DATE
            skip_bytes(4)
        elif byte <= 0x1e:
            # Reserved
            continue
        elif byte == 0x1f:
            # Error info
            skip_bytes(5 * 4)
        elif byte <= 0x2f:
            # Reserved
            continue
        elif byte <= 0x31:
            # XSECT
            read_label_v8()
            skip_bytes(4 * 2)
        elif byte <= 0x33:
            # XSECT
            read_label_v8()
            skip_bytes(4 * 4)
        elif byte <= 0x3f:
            # Reserved
            continue
        elif byte <= 0x7f:
            # LINE
            flag = byte & 0x3f
            if not (flag & 0x20):
                read_label_v8()
            coords_ = coords_splay if (flag & 0x04) else coords
            assert xyz_move
            if xyz_move != coords_[-3:]:
                coords_.append('M')
                coords_.extend(xyz_move)
            xyz_move = read_xyz()
            coords_.append('L')
            coords_.extend(xyz_move)
        elif byte <= 0xff:
            # LABEL
            flag = byte & 0x7f
            read_label_v8()
            xyz = read_xyz()
            _label(xyz, byte & 0x7f)

while ff_version < 8:
    byte = read_byte()

    if byte == -1:
        break

    if byte == 0x00:
        # STOP
        curr_label = ''
    elif byte <= 0x0e:
        # TRIM
        (i, n) = (-16, 0)
        while n < byte:
            i -= 1
            if curr_label[i] == '.':
                n += 1
        curr_label = curr_label[:i + 1]
    elif byte <= 0x0f:
        # MOVE
        xyz = read_xyz()
        coords.append('M')
        coords.extend(xyz)
    elif byte <= 0x1f:
        # TRIM
        curr_label = curr_label[:15 - byte]
    elif byte <= 0x20:
        # DATE
        if ff_version < 7:
            skip_bytes(4)
        else:
            skip_bytes(2)
    elif byte <= 0x21:
        # DATE
        if ff_version < 7:
            skip_bytes(8)
        else:
            skip_bytes(3)
    elif byte <= 0x22:
        # Error info
        skip_bytes(5 * 4)
    elif byte <= 0x23:
        # DATE
        skip_bytes(4)
    elif byte <= 0x24:
        # DATE
        continue
    elif byte <= 0x2f:
        # Reserved
        continue
    elif byte <= 0x31:
        # XSECT
        read_label()
        skip_bytes(4 * 2)
    elif byte <= 0x33:
        # XSECT
        read_label()
        skip_bytes(4 * 4)
    elif byte <= 0x3f:
        # Reserved
        continue
    elif byte <= 0x7f:
        # LABEL
        read_label()
        xyz = read_xyz()
        _label(xyz, 0x0)
    elif byte <= 0xbf:
        # LINE
        read_label()
        xyz = read_xyz()
        coords.append('L')
        coords.extend(xyz)
    elif byte <= 0xff:
        # Reserved
        continue

f.close()

# find min/max
min_x = coords[1]
max_x = coords[1]
min_y = coords[2]
max_y = coords[2]
for coords_ in (coords, coords_splay):
    for i in range(4, len(coords_), 4):
        if (min_x > coords_[i + 1]):
            min_x = coords_[i + 1]
        if (max_x < coords_[i + 1]):
            max_x = coords_[i + 1]
        if (min_y > coords_[i + 2]):
            min_y = coords_[i + 2]
        if (max_y < coords_[i + 2]):
            max_y = coords_[i + 2]

# extend
width = max_x - min_x
height = max_y - min_y

scale = 1.0 / args['scale']

marker = {
    1: 'url(#StationCircle)',
    2: 'url(#StationTriangle)',
}.get(args['markers'], 'none')


def print_path(coords, style, scale=1.0, marker=marker):
    if not coords:
        return

    style = style + [
        'fill:none',
        'stroke-width:' + str(max(0.1, scale * args['scale'] / 50)),
        'stroke-linecap:round',
        'stroke-linejoin:round',
        'marker-start:' + marker,
        'marker-mid:' + marker,
        'marker-end:' + marker,
    ]

    print('<path style="%s"' % (';'.join(style)))
    if args['use_therion_attribs']:
        print('  therion:type="survey"')
    if args['use_inkscape_label']:
        print('  inkscape:label="line survey"')
    sys.stdout.write('d="')
    for i in range(0, len(coords), 4):
        sys.stdout.write(coords[i] + " " +
                         str(coords[i + 1] - min_x) + "," +
                         str(coords[i + 2] - min_y) + " ")
    sys.stdout.write('"')
    print(' />')


def print_points():
    prev = [-1, -1]
    for label, xy in labels.items():
        if xy == prev:
            continue
        label = name_survex2therion(label)
        print('<use transform="translate(%f,%f)" xlink:href="#point-station"'
              % (xy[0] - min_x, xy[1] - min_y))
        if args['use_therion_attribs']:
            print('  therion:role="point" therion:type="station"')
        if args['use_inkscape_label']:
            print('  inkscape:label="point station -name %s" />' % (label))
        else:
            print('  inkscape:label="%s" />' % (label))
        prev = xy


def print_stationnames():
    for label, xy in labels.items():
        if args['stationnames'] != STATIONNAMES_FULL:
            label = label.rsplit('.', 1)[-1]
        print('<text transform="translate(%f,%f)"'
              % (xy[0] - min_x, xy[1] - min_y))
        if args['use_therion_attribs']:
            print('  therion:role="point" therion:type="station-name"')
        if args['use_inkscape_label']:
            print('  inkscape:label="point station-name"')
        print('  >%s</text>' % (label))


print("""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg"
  xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
  xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd"
  xmlns:xlink="http://www.w3.org/1999/xlink"
  xmlns:therion="http://therion.speleo.sk/therion"
  style="overflow:visible"
  viewBox="0 0 %d %d"
  width="%fcm"
  height="%fcm">
<sodipodi:namedview
  inkscape:document-units="mm">
  <inkscape:grid
    type="xygrid"
    units="cm"
    spacingx="100"
    spacingy="100"
    empspacing="10" />
</sodipodi:namedview>
<defs>
  <symbol id="point-station-0">
    <path
      d="M -1.8,1 1.8,1 0,-2 -1.8,1 z"
      style="fill:white;stroke-width:0.4;stroke-linejoin:miter;fill-opacity:0.5" />
    <path
      d="M 0,0 0,0"
      style="fill:none;stroke-width:0.7;stroke-linecap:round" />
  </symbol>
  <marker style="overflow:visible" id="StationCircle">
    <circle r="2"
      style="fill:none;stroke:#666;stroke-width:0.7" />
  </marker>
  <marker style="overflow:visible" id="StationTriangle">
    <use xlink:href="#point-station-0" style="stroke:#666" transform="scale(1.5)" />
  </marker>
  <symbol id="point-station" transform="scale(%f)">
    <use xlink:href="#point-station-0" style="stroke:black" />
  </symbol>
</defs>
<g
  style="font-size:%f"
  >
  <!-- imported with scale 1:%d from %s -->
""" % (
    width,
    height,
    width * scale,
    height * scale,
    0.1 / scale,
    args['scale'] / 2.3622,
    args['scale'],
    infile,
))

print_path(coords_splay, ['stroke:#990'], 0.5, "none")
print_path(coords, ['stroke:#900'])

if args['markers'] == 3:
    print_points()
if args['stationnames']:
    print_stationnames()

print('</g>')

if args['scalebar']:
    try:
        from render_scalebar import Scalebar
        scalebar = Scalebar(args['scale'], 3 * 25.4, docunit=scale * 10 * 3)
        scalebar_xml = scalebar.get_xml()
        if not isinstance(scalebar_xml, str):
            scalebar_xml = scalebar_xml.decode("utf-8")
        print(scalebar_xml)
    except Exception as e:
        print("<text>Scalebar import failed ({})</text>".format(e))

print("</svg>")
