#!/usr/bin/env python
#
# PocketTopo file parser and converter
#
# Based on Andrew Atkinson's "TopParser"
#
# Copyright (C) 2018-2021 Thomas Holder
# Copyright (C) 2011-2012 Andrew Atkinson ("TopParser")
#
# --------------------------------------------------------------------
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# --------------------------------------------------------------------

from __future__ import division as _
from __future__ import print_function as _
from __future__ import absolute_import as _

import os
import sys
import struct
import time
import collections
import math
from html import escape
from lxml import etree

CLARK_INKSCAPE_LABEL = "{http://www.inkscape.org/namespaces/inkscape}label"
CLARK_INKSCAPE_GROUPMODE = "{http://www.inkscape.org/namespaces/inkscape}groupmode"

COLOURS = (
    'black',
    'gray',
    'brown',
    'blue',
    'red',
    'green',
    'orange',
)

KEY_TAPE = 'tape'
KEY_COLOR = 'colour'
KEY_DECLINATION = 'dec'
KEY_X = 0
KEY_Y = 1
KEY_EXTEND = 'direction'

EXTEND_LEFT = "<"
EXTEND_RIGHT = ">"


def distmm(mm):
    '''convert millimeters to meters'''
    return mm / 1000.0


def adegrees(angle, divisor=0xFFFF):
    '''convert angle from internal units to degrees'''
    return float(angle) / divisor * 360.0


def posdeg(deg):
    '''positive angle
    :param deg: angle in degrees
    :return: angle in [0, 360)'''
    return deg % 360


def avgdeg(deg):
    '''average angle
    :param deg: list of angles in degrees
    :return: mean angle in [-180, 180]
    '''
    N = len(deg)
    if N == 0:
        return 0.0
    mss = sum(math.sin(math.radians(a)) for a in deg) / N
    msc = sum(math.cos(math.radians(a)) for a in deg) / N
    return math.degrees(math.atan2(mss, msc))


def reverse_shot(s):
    return s | {
        'from': s['to'],
        'to': s['from'],
        'compass': s['compass'] + 180.0,
        'clino': -s['clino'],
        KEY_TAPE: s[KEY_TAPE],
    }


def average_shots(shots, ignore_splays=True):
    '''Average duplicate legs and return a new set of legs. Ignores splay shots.
    '''
    duplicates = collections.defaultdict(list)
    order = []

    for s in shots:
        if not s['to']:
            if not ignore_splays:
                order.append((s, None))
            continue

        if (s['to'], s['from']) in duplicates:
            s = reverse_shot(s)

        key = (s['from'], s['to'])
        dups = duplicates[key]

        if not dups:
            order.append(key)

        dups.append(s)

    for key in order:
        if key[1] is None:
            yield key[0]
            continue

        dups = duplicates[key]

        yield {
            'from': key[0],
            'to': key[1],
            'compass': posdeg(avgdeg([s['compass'] for s in dups])),
            'clino': sum(s['clino'] for s in dups) / len(dups),
            KEY_TAPE: sum(s[KEY_TAPE] for s in dups) / len(dups),
            # copy from first
            'trip': dups[0]['trip'],
            'comment': dups[0].get('comment', ''),
            KEY_EXTEND: dups[0][KEY_EXTEND],
        }


def get_true_bearing(shot, top):
    """Get the direction relative to geographic "true" north which is corrected
    by magnetic declination.
    """
    tripidx = shot["trip"]

    if tripidx != -1:
        decl = top["trips"][tripidx][KEY_DECLINATION]
    else:
        decl = 0

    return shot["compass"] + decl


def is_consecutive_number(from_: str, to: str) -> bool:
    """Return true if both stations have the same survey prefix and are
    consecutively numbered.
    """
    p_from = from_.rpartition(".")
    p_to = to.rpartition(".")
    return p_from[0] == p_to[0] and abs(int(p_from[2]) - int(p_to[2])) == 1


def _make_Point(x, y):
    return distmm(x), distmm(y)


def _read_date(F):
    ticks = struct.unpack('<Q', F.read(8))
    # Need to convert this date from .NET
    NANOSEC = 10000000
    # Number of python tick since 1/1/1 00:00
    PTICKS = 62135596800
    tripdate = time.gmtime((ticks[0] / NANOSEC) - PTICKS)
    return tripdate


def _read_comments(F):
    commentlength = struct.unpack('<B', F.read(1))[0]
    if commentlength >= 0x80:
        commentlength2 = struct.unpack('<B', F.read(1))[0]
        if commentlength2 >= 0x80:
            raise NotImplementedError('comment is rediculously long')
        commentlength += 0x80 * (commentlength2 - 1)
    C = F.read(commentlength)
    return C.decode('utf-8')


def _read_trip(F):
    # First 8 (int64) is the date in ticks
    tdate = _read_date(F)
    comment = _read_comments(F)
    declination = struct.unpack('<H', F.read(2))[0]
    return {
        'date': tdate,
        'comment': comment,
        KEY_DECLINATION: adegrees(declination),
    }


def _read_shot(F):
    shot = {'from': _read_station(F)}
    shot['to'] = _read_station(F)

    Dist = struct.unpack('<L', F.read(4))
    shot[KEY_TAPE] = distmm(Dist[0])

    azimuth = struct.unpack('<H', F.read(2))
    shot['compass'] = adegrees(azimuth[0])

    inclination = struct.unpack('<h', F.read(2))
    shot['clino'] = adegrees(inclination[0])

    flags = struct.unpack('<B', F.read(1))

    rawroll = struct.unpack('<B', F.read(1))
    shot['rollangle'] = adegrees(rawroll[0], 0xFF)

    tripindex = struct.unpack('<h', F.read(2))
    shot['trip'] = tripindex[0]

    # bit 1 of flags is flip (left or right)
    if flags[0] & 0b00000001:
        shot[KEY_EXTEND] = EXTEND_LEFT
    else:
        shot[KEY_EXTEND] = EXTEND_RIGHT

    # bit 2 of flags indicates a comment
    if flags[0] & 0b00000010:
        shot['comment'] = _read_comments(F)

    return shot


def _read_reference(F):
    # Totally untested
    stnid = _read_station(F)
    east, west, altitude = struct.unpack('<QQL', F.read(20))
    comment = _read_comments(F)
    return [
        stnid,
        distmm(east),
        distmm(west),
        distmm(altitude),
        comment,
    ]


def _read_Point(F):
    x, y = struct.unpack('<ll', F.read(8))
    return _make_Point(x, y)


def _read_Polygon(F):
    numpoints = struct.unpack('<L', F.read(4))[0]
    poly = [_read_Point(F) for _ in range(numpoints)]
    colour = struct.unpack('<B', F.read(1))[0]
    return {
        KEY_COLOR: COLOURS[colour - 1],
        'coord': poly,
    }


def _read_station(F):
    # id's split into major.decimal(minor)
    idd, idm = struct.unpack('<HH', F.read(4))
    if idd == 0xffff:
        # TODO Observed (0xffff, 0x800f), what does this mean?
        print('unknown idd=0x{:04x} idm=0x{:04x}'.format(idd, idm),
              file=sys.stderr)
        return ""
    if idm != 0x8000:
        return str(idm) + "." + str(idd)
    if idd != 0:
        return str(idd - 1)
    return ""


def _read_xsection(F):
    pnt = _read_Point(F)
    stn = _read_station(F)
    # Need to look up the coordinate of the station
    direction = struct.unpack('<l', F.read(4))[0]
    # -1: horizontal, >=0; projection azimuth (internal angle units)
    if direction != -1:
        direction = adegrees(direction)
    return [
        pnt[KEY_X],
        pnt[KEY_Y],
        stn,
        direction,
    ]


def _read_mapping(F):
    x, y, scale = struct.unpack('<iii', F.read(12))
    return {
        'center': _make_Point(x, y),
        'scale': scale,
    }


def _read_drawing(F):
    transform = _read_mapping(F)
    polys = []
    xsec = []

    while True:
        element = struct.unpack('<B', F.read(1))[0]
        if element == 0:
            break
        if element == 1:
            # 1 is a standard line
            polys.append(_read_Polygon(F))
        elif element == 3:
            # 3 is location and orientation of a xsection
            xsec.append(_read_xsection(F))
        else:
            print('undefined object number: ', element, file=sys.stderr)

    return {
        'polys': polys,
        'xsec': xsec,
        'transform': transform,
    }


def _read_fsection(F, readfun):
    count = struct.unpack('<L', F.read(4))[0]
    return [readfun(F) for _ in range(count)]


def load(fp):
    '''Read PocketTopo data from `fp` (readable binary-mode file-like object)
    and return it as a dictionary.
    '''
    if fp.read(3) != b'Top':
        raise ValueError('Not a top file')

    top = {'version': struct.unpack('B', fp.read(1))[0]}
    top['trips'] = _read_fsection(fp, _read_trip)
    top['shots'] = _read_fsection(fp, _read_shot)
    top['ref'] = _read_fsection(fp, _read_reference)
    top['transform'] = _read_mapping(fp)
    top['outline'] = _read_drawing(fp)
    top['sideview'] = _read_drawing(fp)

    remaining = fp.read()
    assert remaining == b'\0\0\0\0'

    return top


def dump_json(top, file=sys.stdout):
    '''Dump JSON formatted data
    '''
    import json
    json.dump(top, file, indent=2, sort_keys=True)


def dump_svx(top,
        surveyname=None,
        prefixadd='',
        prefixstrip='',
        doavg=True,
        dosep=False,
        therion=False,
        dot='.',
        file=sys.stdout,
        end=os.linesep):
    '''Write a Survex (.svx) or Therion (.th) data file

    :param surveyname: Add *begin and *end with surveyname
    :param prefixadd: Prefix to add
    :param prefixstrip: Prefix to strip (e.g. "1.")
    :param doavg: Average redundant shots
    :param dosep: Separate blocks for legs and splays
    :param therion: Use Therion format
    :param dot: Character to use instead of '.' in station names
    '''
    if therion:
        C = '#'
        P = ''
        splayname = '-'
    else:
        C = ';'
        P = '*'
        splayname = '..'

    if 'filename' in top:
        file.write(C + ' ' + os.path.basename(top['filename']))
        file.write(end * 2)

    if surveyname:
        if therion:
            file.write('survey ' + surveyname)
        else:
            file.write('*begin ' + surveyname)
        file.write(end * 2)

    file.write(P + 'data normal from to tape compass clino')
    file.write(end)

    tripidx = [None] # list as mutable pointer in function scope

    allhaveprefixstrip = prefixstrip and (
            all(s['from'].startswith(prefixstrip) for s in top['shots']) and
            all(s['to'].startswith(prefixstrip) for s in top['shots'] if s['to']))

    nstrip = len(prefixstrip) if allhaveprefixstrip else 0

    sname = lambda n: n.replace('.', dot)

    def write_shot(s):
        # ignore "1.0  .. 0.0 0.0 0.0" line
        if not s[KEY_TAPE] and not s['to']:
            return

        if tripidx[0] != s['trip'] and s['trip'] != -1:
            tripidx[0] = s['trip']
            trip = top['trips'][tripidx[0]]

            file.write(end)
            file.write(P + 'date {0.tm_year}.{0.tm_mon:02}.{0.tm_mday:02}'.format(trip['date']))
            file.write(end)
            file.write(P + 'declination {:.2f} degrees'.format(trip[KEY_DECLINATION]))
            file.write(end * 2)

        from_ = prefixadd + sname(s['from'][nstrip:])
        to = (prefixadd + sname(s['to'][nstrip:])) if s['to'] else splayname

        fmt = '{0}\t{1}\t{' + KEY_TAPE + ':6.3f} {compass:5.1f} {clino:5.1f}'
        if not s[KEY_TAPE]:
            fmt = P + 'equate {0} {1}'
        file.write(fmt.format(from_, to, **s))

        if s.get('comment'):
            file.write(' {} {comment}'.format(C, **s))

        file.write(end)

    if doavg:
        leg_iter = average_shots(top['shots'], dosep)
    elif dosep:
        leg_iter = (s for s in top['shots'] if s['to'])
    else:
        leg_iter = iter(top['shots'])

    for s in leg_iter:
        write_shot(s)

    if dosep:
        file.write(end + C + ' passage data' + end)
        for s in top['shots']:
            if not s['to']:
                write_shot(s)

    if surveyname:
        file.write(end)
        if therion:
            file.write('endsurvey')
        else:
            file.write('*end ' + surveyname)
        file.write(end)


def dump_tro(top,
        file=sys.stdout,
        end=os.linesep):
    '''Write a Visual Topo (.tro) data file
    '''
    def write_shot(s):
        # ignore "1.0  .. 0.0 0.0 0.0" line
        if not s[KEY_TAPE] and not s['to']:
            return

        to = s['to'] if s['to'] else '*'
        fmt = '{from:10} {0:10} {' + KEY_TAPE + ':19.2f}  {compass:6.2f} {clino:7.2f}'
        file.write(fmt.format(to, **s))
        file.write(end)

    # (dummy) entrance required for processing
    entrance_name = top['shots'][0]['from']
    entrance_shot = {
        'from': entrance_name,
        'to': entrance_name,
        KEY_TAPE: 0,
        'compass': 0,
        'clino': 0
    }

    file.write('Entree ' + entrance_name + end)
    file.write('Param Deca Degd Clino Degd 0.0000 Dir,Dir,Dir' + end)
    write_shot(entrance_shot)

    leg_iter = average_shots(top['shots'], False)

    for s in leg_iter:
        write_shot(s)


def get_bbox(polys):
    return [
        min(pnt[KEY_X] for poly in polys for pnt in poly['coord']),
        min(pnt[KEY_Y] for poly in polys for pnt in poly['coord']),
        max(pnt[KEY_X] for poly in polys for pnt in poly['coord']),
        max(pnt[KEY_Y] for poly in polys for pnt in poly['coord']),
    ]


def dump_svg(top: dict,
             *,
             hidesideview: bool = False,
             file=sys.stdout,
             showbbox: bool = True,
             scale: float = 200.0):
    '''Dump drawing as SVG.

    Plan and side views go into separate layers.

    Args:
      scale: Scale as 1:scale
    '''
    scale /= 100  # cm

    leg_shots = list(average_shots(top['shots']))

    def write_shots(parent: etree.Element, shots, sideview=False) -> dict:
        suppresswarnings = sideview
        frompoints = {}
        compass_from = collections.defaultdict(list)
        compass_to = collections.defaultdict(list)
        legs = []
        splays = []
        defer = []

        for s in top['shots']:
            frompoints[s['from']] = (0, 0)
            break

        def process_shot(s, do_splays):
            is_splay = not s['to']

            if do_splays != is_splay:
                return True

            # ignore "1.0  .. 0.0 0.0 0.0" line
            if not s[KEY_TAPE] and is_splay:
                return True

            if s['from'] not in frompoints:
                if s['to'] not in frompoints:
                    return False
                s = reverse_shot(s)

            length_proj = s[KEY_TAPE] * math.cos(math.radians(s['clino']))
            true_bearing = get_true_bearing(s, top)

            if sideview:
                compass_delta = 1.0

                if not is_splay:
                    if s[KEY_TAPE] and is_consecutive_number(s["from"], s["to"]):
                        compass_from[s['from']].append(true_bearing)
                    if s[KEY_TAPE]:
                        compass_to[s['to']].append(true_bearing)
                else:
                    assert s[KEY_TAPE]
                    compass_out = compass_from.get(s['from'])
                    compass_in = compass_to.get(s['from'], compass_out)

                    if compass_in is None:
                        compass_out = []
                        compass_in = []
                    elif compass_out is None:
                        compass_out = compass_in

                    compass_in = avgdeg(compass_in)
                    compass_out = avgdeg(compass_out)

                    compass_in += 180
                    compass_splay_rel = posdeg(true_bearing - compass_in)
                    compass_out_rel = posdeg(compass_out - compass_in)

                    if compass_splay_rel > compass_out_rel:
                        compass_splay_rel = 360 - compass_splay_rel
                        compass_out_rel = 360 - compass_out_rel

                    if compass_out_rel:
                        compass_delta = compass_splay_rel / compass_out_rel * 2 - 1
                        # I would expect sin transformation, but looks like PocketTopo doesn't do that
                        # compass_delta = math.sin(math.radians(compass_delta * 90))


                if s[KEY_EXTEND] == EXTEND_LEFT:
                    compass_delta *= -1

                delta_x = length_proj * compass_delta
                delta_y = s[KEY_TAPE] * math.sin(math.radians(s['clino']))
            else:
                delta_x = length_proj * math.sin(math.radians(true_bearing))
                delta_y = length_proj * math.cos(math.radians(true_bearing))

            pnt_from = frompoints[s['from']]
            pnt_to = (pnt_from[0] + delta_x, pnt_from[1] - delta_y)

            if not is_splay:
                frompoints[s['to']] = pnt_to
                legs.append((pnt_from, pnt_to))
            else:
                splays.append((pnt_from, pnt_to))

            return True

        for s in leg_shots:
            if not process_shot(s, False):
                defer.append(s)

        while defer:
            for s in defer:
                if process_shot(s, False):
                    defer.remove(s)
                    break
            else:
                print('{} unconnected subsurveys'.format(len(defer)))
                break

        for s in top['shots']:
            process_shot(s, True)

        def write_legs(legs: list, style: str):
            path_data = " ".join(
                f"M{pnt_from[0]},{pnt_from[1]} {pnt_to[0]},{pnt_to[1]}"
                for (pnt_from, pnt_to) in legs)
            etree.SubElement(parent, "path", {
                CLARK_INKSCAPE_LABEL: "line survey",
                "style": style,
                "d": path_data,
            })

        write_legs(splays, 'stroke:#fc0;stroke-width:0.02')
        write_legs(legs, 'stroke:#f00;stroke-width:0.03')

        return frompoints

    def write_xsections(parent: etree.Element, frompoints, drawing):
        for xsec in drawing['xsec']:
            pnt_stn = frompoints[xsec[2]]
            etree.SubElement(
                parent, "path", {
                    CLARK_INKSCAPE_LABEL: "line section",
                    "class": "xsecconnector",
                    "d": f"M{pnt_stn[0]} {pnt_stn[1]} {xsec[0]} {xsec[1]}",
                })

    def write_stationlabels(parent: etree.Element, frompoints: dict):
        for key, pnt in frompoints.items():
            survey, _, station = key.rpartition(".")
            name = "{}@{}".format(station, survey) if survey else key
            assert name == escape(name)
            elem_text = etree.SubElement(
                parent, "text", {
                    "x": str(pnt[0]),
                    "y": str(pnt[1]),
                    CLARK_INKSCAPE_LABEL: f"point station -name {name}",
                })
            elem_text.text = key

    outer_padding = 5.0

    def write_layer(parent: etree.Element,
                    top: dict,
                    view: str,
                    label: str = "",
                    *,
                    xoffset: int = 0,
                    display: str = 'inline',
                    padding: float = 1.0) -> tuple:
        """
        Returns:
          Width and height of the bounding box
        """
        drawing = top[view]

        if not label:
            label = view

        try:
            min_x, min_y, max_x, max_y = get_bbox(drawing['polys'])
        except ValueError:
            min_x, min_y, max_x, max_y = 0, 0, 0, 0

        width = max_x - min_x
        height = max_y - min_y

        xoffset += -min_x + outer_padding
        yoffset = -min_y + outer_padding

        g_layer = etree.SubElement(
            parent, "g", {
                CLARK_INKSCAPE_GROUPMODE: "layer",
                CLARK_INKSCAPE_LABEL: label,
                "style": f"display:{display}",
                "transform": f"translate({xoffset},{yoffset})",
            })

        g_drawing = etree.SubElement(g_layer, "g", {
            CLARK_INKSCAPE_LABEL: "drawing",
        })

        for poly in drawing['polys']:
            coord = poly['coord']

            # repeat single points to make line visible
            if len(coord) == 1:
                coord = coord + coord

            path_data = "M" + " ".join(f" {pnt[KEY_X]},{pnt[KEY_Y]}"
                                       for pnt in coord)

            etree.SubElement(g_drawing, "path", {
                "style": f"stroke:{poly[KEY_COLOR]}",
                "d": path_data,
            })

        g_shots = etree.SubElement(g_layer, "g", {
            CLARK_INKSCAPE_LABEL: "shots",
        })

        stations = write_shots(g_shots, top, view == 'sideview')

        write_xsections(g_shots, stations, drawing)
        write_stationlabels(g_shots, stations)

        if showbbox:
            if width or height:
                color = '#f0f'
                etree.SubElement(
                    g_layer, "rect", {
                        "x": f"{min_x - padding}",
                        "y": f"{min_y - padding}",
                        "width": f"{width + padding * 2}",
                        "height": f"{height + padding * 2}",
                        "style": f"fill:none;stroke:{color};stroke-width:0.04",
                    })
                if 'filename' in top:
                    elem_text = etree.SubElement(
                        g_layer, "text", {
                            "x": f"{min_x - 0.7}",
                            "y": f"{min_y - 0.2}",
                            "style": f"fill:{color}",
                        })
                    elem_text.text = f"{os.path.basename(top['filename'])} ({label})"

        return width, height

    root = etree.fromstring(f"""<?xml version="1.0" ?>
<svg
   xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd"
   xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
   xmlns="http://www.w3.org/2000/svg">
<defs>
<style type="text/css">
path {{
    fill:none;
    stroke-width:{scale*0.05};
    stroke-linecap:round;
    stroke-linejoin:round;
}}
text {{
    font: {scale*1.27/3} sans-serif;
    fill:#999;
}}
.xsecconnector {{
    stroke-dasharray:0.05,0.15;
    stroke:#bbb;
}}
</style>
</defs>
<sodipodi:namedview
   inkscape:document-units="cm"
   pagecolor="#ffffff">
  <inkscape:grid type="xygrid" empspacing="10"
     spacingx="1"
     spacingy="1"
     units="cm" />
</sodipodi:namedview>
</svg>
""")

    width1, height1 = write_layer(root, top, 'outline', 'planview')

    if width1:
        width1 += outer_padding

    width2, height2 = write_layer(root, top, 'sideview', display='none' if hidesideview else 'inline', xoffset=width1)

    width = width1 + width2 + 2 * outer_padding
    height = max(height1, height2) + 2 * outer_padding

    root.set("width", f"{width/scale}cm")
    root.set("height", f"{height/scale}cm")
    root.set("viewBox", f"0 0 {width} {height}")

    file.write(etree.tostring(root).decode("utf-8"))


def dump_xvi(top, *, file=sys.stdout):
    '''Dump drawing as XVI.
    '''
    # Default XTherion PocketTopo Import Settings
    SCALE = 200
    RESOLUTION_DPI = 200
    METER_PER_INCH = 0.0254
    FACTOR = RESOLUTION_DPI / METER_PER_INCH / SCALE

    def pnt2xvi(pnt):
        return FACTOR * pnt[KEY_X], -FACTOR * pnt[KEY_Y]

    leg_shots = list(average_shots(top['shots']))

    def write_shots(shots, sideview=False):
        suppresswarnings = sideview
        frompoints = {}
        compass_from = collections.defaultdict(list)
        compass_to = collections.defaultdict(list)
        legs = []
        splays = []
        defer = []

        for s in top['shots']:
            frompoints[s['from']] = (0, 0)
            break

        def process_shot(s, do_splays):
            is_splay = not s['to']

            if do_splays != is_splay:
                return True

            # ignore "1.0  .. 0.0 0.0 0.0" line
            if not s[KEY_TAPE] and is_splay:
                return True

            if s['from'] not in frompoints:
                if s['to'] not in frompoints:
                    return False
                s = reverse_shot(s)

            length_proj = s[KEY_TAPE] * math.cos(math.radians(s['clino']))
            true_bearing = get_true_bearing(s, top)

            delta_x = length_proj * math.sin(math.radians(true_bearing))
            delta_y = length_proj * math.cos(math.radians(true_bearing))

            pnt_from = frompoints[s['from']]
            pnt_to = (pnt_from[0] + delta_x, pnt_from[1] - delta_y)

            if not is_splay:
                frompoints[s['to']] = pnt_to
                legs.append((pnt_from, pnt_to))
            else:
                splays.append((pnt_from, pnt_to))

            return True

        for s in leg_shots:
            if not process_shot(s, False):
                defer.append(s)

        while defer:
            for s in defer:
                if process_shot(s, False):
                    defer.remove(s)
                    break
            else:
                print('{} unconnected subsurveys'.format(len(defer)))
                break

        for s in top['shots']:
            process_shot(s, True)

        def write_legs(legs):
            file.write('set XVIshots {\n')
            for (pnt_from, pnt_to) in legs:
                file.write('    {{{0[0]:g} {0[1]:g} {1[0]:g} {1[1]:g}}}\n'.format(pnt2xvi(pnt_from), pnt2xvi(pnt_to)))
            file.write('}\n')

        write_legs(splays + legs)

        return frompoints

    def write_stationlabels(frompoints):
        file.write('set XVIstations {\n')
        for key, pnt in frompoints.items():
            file.write('    {{{0[0]:g} {0[1]:g} {1}}}\n'.format(pnt2xvi(pnt), key))
        file.write('}\n')

    def write_shots_and_stations(top, view="outline"):
        stations = write_shots(top, view == 'sideview')

        write_stationlabels(stations)

    def write_sketchlines(top, view="outline"):
        file.write('set XVIsketchlines {\n')

        for poly in top[view]['polys']:
            coord = poly['coord']

            file.write('    {' + poly[KEY_COLOR])

            for pnt in coord:
                file.write(' {:g} {:g}'.format(*pnt2xvi(pnt)))

            file.write('}\n')

        file.write('}\n')

    def write_grid(top, view="outline"):
        min_x, min_y, max_x, max_y = get_bbox(top[view]['polys'])
        min_x, min_y = pnt2xvi([min_x, min_y])
        max_x, max_y = pnt2xvi([max_x, max_y])

        dx = FACTOR
        dy = FACTOR

        nx = int(1.5 + (max_x - min_x) / dx)
        ny = int(1.5 + (min_y - max_y) / dy)

        file.write(f'set XVIgrid {{{min_x-dx/2:g} {max_y-dy/2:g} {dx} 0 0 {dy} {nx} {ny}}}\n')

    def write_grid_spacing():
        file.write('set XVIgrids {1.0 m}\n')

    write_grid_spacing()
    write_shots_and_stations(top)
    write_sketchlines(top)
    write_grid(top)


def dump_info(top):
    '''Print some stats
    '''
    stations = set(s['from'] for s in top['shots'])
    stations.update(s['to'] for s in top['shots'] if s['to'])

    print('{} trip(s), {} shots, {} named stations'.format(
        len(top['trips']),
        len(top['shots']),
        len(stations)))

    for i, trip in enumerate(top['trips']):
        date = '{0.tm_year}.{0.tm_mon:02}.{0.tm_mday:02}'.format(trip['date'])
        print('trip #{}: {} {}'.format(i + 1, date, trip.get('comment', '')))


def view_aven(top, tmpname='', exe='aven', _dump=dump_svx, _ext='.svx'):
    '''View survey data in aven
    '''
    import tempfile
    import shutil
    import subprocess

    d = tempfile.mkdtemp()

    try:
        svxfilename = os.path.join(d,
                os.path.basename(tmpname or 'temp') + _ext)

        with open(svxfilename, 'w') as handle:
            _dump(top, file=handle)

        subprocess.check_call([exe, svxfilename])
    finally:
        shutil.rmtree(d)


def view_inkscape(top, tmpname='', exe='inkscape'):
    '''View drawings in inkscape
    '''
    return view_aven(top, tmpname, exe, dump_svg, '.svg')


def main(argv=None):
    import argparse
    argparser = argparse.ArgumentParser()
    argparser.add_argument("--dump", help="dump file to stdout", choices=('json', 'svg', 'svx', 'th', 'tro', 'xvi'))
    argparser.add_argument("--view", help="open viewer application", choices=('aven', 'inkscape'))
    argparser.add_argument("--surveyname", help="survey name for survex dump", default="")
    argparser.add_argument("--prefixadd", help="station name prefix to add", default="")
    argparser.add_argument("--prefixstrip", help="station name prefix to strip", default="")
    argparser.add_argument("--no-avg", help="don't average repeated legs", action='store_true', default=False)
    argparser.add_argument("--do-sep", help="separate legs from splays", action='store_true', default=False)
    argparser.add_argument('filenames', metavar='FILENAME', nargs='+', help='one or more .top files')
    args = argparser.parse_args(argv)

    for filename in args.filenames:
        if not filename.endswith('.top'):
            raise Exception('not a .top file: ' + filename)

        try:
            with open(filename, "rb") as handle:
                top = load(handle)

            top['filename'] = filename

            if args.dump == 'json':
                dump_json(top)
            elif args.dump in ('svx', 'th'):
                dump_svx(top,
                        therion=args.dump == 'th',
                        doavg=not args.no_avg,
                        dosep=args.do_sep,
                        prefixstrip=args.prefixstrip,
                        prefixadd=args.prefixadd)
            elif args.dump == 'svg':
                dump_svg(top)
            elif args.dump == 'xvi':
                dump_xvi(top)
            elif args.dump == 'tro':
                dump_tro(top)
            elif not args.view:
                dump_info(top)

            if args.view == 'aven':
                view_aven(top, filename[:-4])
            elif args.view == 'inkscape':
                view_inkscape(top, filename[:-4])

        finally:
            pass
        '''
        except Exception as e:
            print(filename, file=sys.stderr)
            print(e, file=sys.stderr)
        '''


if __name__ == '__main__':
    main()
