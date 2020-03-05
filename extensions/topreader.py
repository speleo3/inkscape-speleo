#!/usr/bin/env python
#
# PocketTopo file parser and converter
#
# Based on Andrew Atkinson's "TopParser"
#
# Copyright (C) 2018 Thomas Holder
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
        }


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
        shot['direction'] = '<'
    else:
        shot['direction'] = '>'

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
        file=sys.stdout,
        end=os.linesep):
    '''Write a Survex (.svx) data file

    :param surveyname: Add *begin and *end with surveyname
    :param prefixadd: Prefix to add
    :param prefixstrip: Prefix to strip (e.g. "1.")
    :param doavg: Average redundant shots
    :param dosep: Separate blocks for legs and splays
    '''
    if 'filename' in top:
        file.write('; ' + os.path.basename(top['filename']))
        file.write(end * 2)

    if surveyname:
        file.write('*begin ' + surveyname)
        file.write(end * 2)

    file.write('*data default')
    file.write(end)

    tripidx = [None] # list as mutable pointer in function scope

    allhaveprefixstrip = prefixstrip and (
            all(s['from'].startswith(prefixstrip) for s in top['shots']) and
            all(s['to'].startswith(prefixstrip) for s in top['shots'] if s['to']))

    nstrip = len(prefixstrip) if allhaveprefixstrip else 0

    sname = lambda n: n.replace('.', '_')

    def write_shot(s):
        # ignore "1.0  .. 0.0 0.0 0.0" line
        if not s[KEY_TAPE] and not s['to']:
            return

        if tripidx[0] != s['trip']:
            tripidx[0] = s['trip']
            trip = top['trips'][tripidx[0]]

            file.write(end)
            file.write('*date {0.tm_year}.{0.tm_mon:02}.{0.tm_mday:02}'.format(trip['date']))
            file.write(end * 2)

        from_ = prefixadd + sname(s['from'][nstrip:])
        to = (prefixadd + sname(s['to'][nstrip:])) if s['to'] else '..'

        fmt = '{0}\t{1}\t{' + KEY_TAPE + ':6.3f} {compass:5.1f} {clino:5.1f}'
        if not s[KEY_TAPE]:
            fmt = '*equate {0} {1}'
        file.write(fmt.format(from_, to, **s))

        if s.get('comment'):
            file.write(' ; {comment}'.format(**s))

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
        file.write(end + '; passage data' + end)
        for s in top['shots']:
            if not s['to']:
                write_shot(s)

    if surveyname:
        file.write(end)
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


def dump_svg(top, hidesideview=False, file=sys.stdout, showbbox=True):
    '''Dump drawing as SVG in 1:100 scale.
    Plan and side views go into separate layers.
    '''

    def get_bbox(polys):
        return [
            min(pnt[KEY_X] for poly in polys for pnt in poly['coord']),
            min(pnt[KEY_Y] for poly in polys for pnt in poly['coord']),
            max(pnt[KEY_X] for poly in polys for pnt in poly['coord']),
            max(pnt[KEY_Y] for poly in polys for pnt in poly['coord']),
        ]

    def reverse_shot(s):
        return {
            'from': s['to'],
            'to': s['from'],
            'compass': s['compass'] + 180.0,
            'clino': -s['clino'],
            KEY_TAPE: s[KEY_TAPE],
        }

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

            if sideview:
                compass_delta = 1.0

                if not is_splay:
                    compass_from[s['from']].append(s['compass'])
                    compass_to[s['to']].append(s['compass'])
                else:
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
                    compass_splay_rel = posdeg(s['compass'] - compass_in)
                    compass_out_rel = posdeg(compass_out - compass_in)

                    if compass_splay_rel > compass_out_rel:
                        compass_splay_rel = 360 - compass_splay_rel
                        compass_out_rel = 360 - compass_out_rel

                    if compass_out_rel:
                        compass_delta = compass_splay_rel / compass_out_rel * 2 - 1
                        # I would expect sin transformation, but looks like PocketTopo doesn't do that
                        # compass_delta = math.sin(math.radians(compass_delta * 90))

                delta_x = length_proj * compass_delta
                delta_y = s[KEY_TAPE] * math.sin(math.radians(s['clino']))
            else:
                delta_x = length_proj * math.sin(math.radians(s['compass']))
                delta_y = length_proj * math.cos(math.radians(s['compass']))

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

        def write_legs(legs, style):
            file.write('<path style="{}" d="'.format(style))
            for (pnt_from, pnt_to) in legs:
                file.write('M {0[0]},{0[1]} {1[0]},{1[1]} '.format(pnt_from, pnt_to))
            file.write('" />\n')

        write_legs(splays, 'stroke:#fc0;stroke-width:0.02')
        write_legs(legs, 'stroke:#f00;stroke-width:0.03')

        return frompoints

    def write_xsections(frompoints, drawing):
        for xsec in drawing['xsec']:
            pnt_stn = frompoints[xsec[2]]
            file.write('<path class="xsecconnector" '
                    'd="M {0[0]} {0[1]} {1[0]} {1[1]}" />\n'.format(pnt_stn, xsec))

    def write_stationlabels(frompoints):
        for key, pnt in frompoints.items():
            file.write('<text x="{0[0]}" y="{0[1]}">{1}</text>\n'.format(pnt, key))

    def write_layer(top, view, label=None, display='inline'):
        file.write('<g inkscape:groupmode="layer" inkscape:label="{}" '
                'style="display:{}">\n'.format(label or view, display))

        drawing = top[view]

        file.write('<g inkscape:label="drawing">\n')

        for poly in drawing['polys']:
            coord = poly['coord']

            # repeat single points to make line visible
            if len(coord) == 1:
                coord = coord + coord

            file.write('<path style="stroke:{}" d="M'.format(poly[KEY_COLOR]))

            for pnt in coord:
                file.write(' {},{}'.format(pnt[KEY_X], pnt[KEY_Y]))

            file.write('" />\n')

        file.write('</g>\n')
        file.write('<g inkscape:label="shots">\n')

        stations = write_shots(top, view == 'sideview')

        write_xsections(stations, drawing)
        write_stationlabels(stations)

        file.write('</g>\n')

        if showbbox:
            try:
                min_x, min_y, max_x, max_y = get_bbox(drawing['polys'])
            except ValueError:
                pass
            else:
                color = '#f0f'
                padding = 1.0
                file.write('<rect x="{x}" y="{y}" width="{w}" height="{h}" '
                        'style="fill:none;stroke:{color};stroke-width:0.04" />\n'.format(
                            x=min_x - padding, w=max_x - min_x + padding * 2,
                            y=min_y - padding, h=max_y - min_y + padding * 2,
                            color=color))

                if 'filename' in top:
                    file.write('<text x="{x}" y="{y}" style="fill:{color}">{}</text>\n'.format(
                        os.path.basename(top['filename']), color=color,
                        x=min_x - 0.7, y=min_y - 0.2))

        file.write('</g>\n')

    for view in ('outline', 'sideview'):
        try:
            min_x, min_y, max_x, max_y = get_bbox(top[view]['polys'])
            break
        except ValueError:
            min_x, min_y, max_x, max_y = 0, 0, 0, 0

    padding = 5.0

    file.write('<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n')
    file.write('<svg xmlns="http://www.w3.org/2000/svg" '
            'xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd" '
            'xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
            'width="{width}cm" height="{height}cm" '
            'viewBox="{minx} {miny} {width} {height}">\n'.format(
                minx=min_x - padding,
                miny=min_y - padding,
                width=max_x - min_x + padding * 2,
                height=max_y - min_y + padding * 2))

    file.write('<defs>'
            '<style type="text/css">\n'
            'path {fill:none;stroke-width:0.05;'
            'stroke-linecap:round;stroke-linejoin:round}\n'
            'text {font: 0.5px sans-serif;fill:#999}\n'
            '.xsecconnector {stroke-dasharray:0.05,0.15;stroke:#bbb}\n'
            '</style>'
            '</defs>\n')

    file.write('<sodipodi:namedview inkscape:document-units="cm" units="cm" />\n')

    write_layer(top, 'sideview', display='none' if hidesideview else 'inline')
    write_layer(top, 'outline', 'planview')

    file.write('</svg>')


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
    argparser.add_argument("--dump", help="dump file to stdout", choices=('json', 'svg', 'svx', 'tro'))
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
            elif args.dump == 'svx':
                dump_svx(top,
                        doavg=not args.no_avg,
                        dosep=args.do_sep,
                        prefixstrip=args.prefixstrip,
                        prefixadd=args.prefixadd)
            elif args.dump == 'svg':
                dump_svg(top)
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
