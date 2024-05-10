#!/usr/bin/env python3
#
# PocketTopo file writer
#
# Based on Andrew Atkinson's "TopParser"
#
# Copyright (C) 2018-2022 Thomas Holder
# Copyright (C) 2011-2012 Andrew Atkinson ("TopParser")
#
# --------------------------------------------------------------------
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# --------------------------------------------------------------------

import io
import copy
import sys
import struct
import time
from typing import List, Iterable, Callable
from pathlib import Path
from collections import defaultdict
from pytest import approx

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

TOP_EMPTY = {
    'version': 3,
    'trips': [{
        'date': time.struct_time((2005, 7, 9, 23, 0, 0, 5, 190, 0)),
        'comment': '',
        'dec': 0.0
    }],
    'shots': [],
    'ref': [],
    'transform': {
        'center': (0.001, -10.8),
        'scale': 14400
    },
    'outline': {
        'polys': [],
        'xsec': [],
        'transform': {
            'center': (2.0, 0.001),
            'scale': -36938
        }
    },
    'sideview': {
        'polys': [],
        'xsec': [],
        'transform': {
            'center': (76.8, 65.536),
            'scale': -171311104
        }
    },
}

EMPTY_SHOT = {
    'from': "",
    'to': "",
    'tape': 0.0,
    'compass': 0.0,
    'clino': 0.0,
    'rollangle': 0.0,
    'trip': 0,
    'direction': '>',
}


def distmm(mm: int) -> float:
    '''convert millimeters to meters'''
    assert isinstance(mm, int)
    return mm / 1000.0


def distmm_inv(m: float) -> int:
    '''convert meters to millimeters'''
    return int(m * 1000)


def test_distmm():
    mm = 1234567
    m = 1234.567
    assert distmm(mm) == m
    assert distmm_inv(m) == approx(mm)


def adegrees(angle: int, divisor=0xFFFF) -> float:
    '''convert angle from internal units to degrees'''
    return float(angle) / divisor * 360.0


def adegrees_inv(degrees: float, divisor=0xFFFF) -> int:
    '''convert angle from degrees to internal units'''
    return int((degrees * divisor) / 360.0)


def test_adegrees():
    angle = 1234
    angle_deg = adegrees(angle)
    assert adegrees_inv(angle_deg) == angle


def _make_Point(x: int, y: int) -> tuple:
    return distmm(x), distmm(y)


def _make_Point_inv(x: float, y: float) -> tuple:
    return distmm_inv(x), distmm_inv(y)


def test_make_Point():
    x, y = _make_Point(2, 3)
    inv = _make_Point_inv(x, y)
    assert inv == (2, 3)


# Need to convert this date from .NET
NANOSEC = 10000000

# Number of python tick since 1/1/1 00:00
PTICKS = 62135596800


def _read_date(F) -> time.struct_time:
    ticks = struct.unpack('<Q', F.read(8))
    tripdate = time.gmtime((ticks[0] / NANOSEC) - PTICKS)
    return tripdate


def _write_date(tripdate: time.struct_time) -> Iterable[bytes]:
    ticks = int((time.mktime(tripdate) + PTICKS) * NANOSEC)
    yield struct.pack('<Q', ticks)


def _read_comments(F):
    commentlength = struct.unpack('<B', F.read(1))[0]
    if commentlength >= 0x80:
        commentlength2 = struct.unpack('<B', F.read(1))[0]
        if commentlength2 >= 0x80:
            raise NotImplementedError('comment is rediculously long')
        commentlength += 0x80 * (commentlength2 - 1)
    C = F.read(commentlength)
    return C.decode('utf-8')


def _write_comment(comment) -> Iterable[bytes]:
    commentlength = 0
    yield struct.pack('<B', commentlength)


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


def _write_trip(trip) -> Iterable[bytes]:
    yield from _write_date(trip["date"])
    yield from _write_comment(trip["comment"])
    yield struct.pack('<H', adegrees_inv(trip[KEY_DECLINATION]))


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


def _write_shot(shot) -> Iterable[bytes]:
    yield _write_station(shot["from"])
    yield _write_station(shot["to"])

    Dist = distmm_inv(shot[KEY_TAPE])
    yield struct.pack('<L', Dist)

    azimuth = adegrees_inv(shot['compass'])
    yield struct.pack('<H', azimuth)

    inclination = adegrees_inv(shot['clino'])
    yield struct.pack('<h', inclination)

    flags = 0

    if shot.get('direction', '>') == '<':
        flags |= 0b00000001

    comment = shot.get('comment', '')
    if comment:
        # flags |= 0b00000010
        pass

    yield struct.pack('<B', flags)

    rawroll = adegrees_inv(shot['rollangle'], 0xFF)
    yield struct.pack('<B', rawroll)

    tripindex = shot['trip']
    yield struct.pack('<h', tripindex)

    if comment:
        # yield from _write_comments(comment)
        pass


def _read_reference(F) -> list:
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


def _write_reference(ref: list) -> Iterable[bytes]:
    raise NotImplementedError


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


def _read_station(F) -> str:
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


def _write_station(shot: str) -> bytes:
    idm, dot, idd = shot.rpartition(".")
    if dot:
        iidd, iidm = int(idd), int(idm)
    elif shot:
        iidd, iidm = int(idd) + 1, 0x8000
    else:
        assert not (idd or idm)
        iidd, iidm = 0, 0x8000
    return struct.pack('<HH', iidd, iidm)


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


def _read_mapping(F) -> dict:
    x, y, scale = struct.unpack('<iii', F.read(12))
    return {
        'center': _make_Point(x, y),
        'scale': scale,
    }


def _write_mapping(mapping: dict) -> Iterable[bytes]:
    x, y = _make_Point_inv(*mapping['center'])
    yield struct.pack('<iii', x, y, mapping['scale'])


def _read_drawing(F) -> dict:
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


def _write_drawing(drawing: dict) -> Iterable[bytes]:
    yield from _write_mapping(drawing["transform"])
    # TODO
    yield struct.pack('<B', 0)


def _read_fsection(F, readfun) -> list:
    count = struct.unpack('<L', F.read(4))[0]
    return [readfun(F) for _ in range(count)]


def _write_one(fp, sec, writefunc: Callable):
    for chunk in writefunc(sec):
        fp.write(chunk)


def _write_fsection(fp, section: list, writefunc: Callable):
    fp.write(struct.pack('<L', len(section)))
    for sec in section:
        _write_one(fp, sec, writefunc)


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


def dump(top: dict, fp):
    fp.write(b"Top")
    fp.write(struct.pack('B', top['version']))
    _write_fsection(fp, top["trips"], _write_trip)
    _write_fsection(fp, top["shots"], _write_shot)
    _write_fsection(fp, top["ref"], _write_reference)
    _write_one(fp, top["transform"], _write_mapping)
    _write_one(fp, top["outline"], _write_drawing)
    _write_one(fp, top["sideview"], _write_drawing)
    fp.write(b'\x00\x00\x00\x00')


def dumps(top: dict) -> bytes:
    fp = io.BytesIO()
    dump(top, fp)
    return fp.getvalue()


def dim_to_float(dim: str) -> float:
    dim = dim.strip()
    return 0.0 if dim in ("", "*") else float(dim)


def parse_tro_data_line(line: str) -> dict:
    try:
        return {
            "from": line[0:11].strip(),
            "to": line[11:22].strip(),
            "tape": float(line[33:41]),
            "compass": float(line[41:49]),
            "clino": float(line[49:57]),
            "left": dim_to_float(line[57:64]),
            "right": dim_to_float(line[64:71]),
            "up": dim_to_float(line[71:78]),
            "down": dim_to_float(line[78:85]),
        }
    except:
        print(line)
        raise


class StationRemapper:
    def __init__(self):
        self.used_surveys = set()
        self.used_stations = set()
        self.next_remapped_idm = 1000
        self.next_remapped_idd = defaultdict(int)
        self.remapped_surveys = defaultdict(self.get_unused_idm)
        self.remapped_stations = {}

    def get_unused_idm(self) -> str:
        while self.next_remapped_idm in self.used_surveys:
            self.next_remapped_idm += 1
        return str(self.next_remapped_idm)

    def get_unused_station_for_idm(self, idm: str) -> str:
        while (idm, self.next_remapped_idd[idm]) in self.used_stations:
            self.next_remapped_idd[idm] += 1

        idd = str(self.next_remapped_idd[idm])

        return f"{idm}.{idd}" if idm else str(idd)

    def register_used(self, station: str):
        assert station
        idm, dot, idd = station.rpartition(".")
        if idm.isdigit():
            self.used_surveys.add(int(idm))
            if idd.isdigit():
                self.used_stations.add((idm, int(idd)))

    def __call__(self, station: str) -> str:
        assert station

        if station == "*":
            return ""

        idm, dot, idd = station.rpartition(".")

        if idm and not idm.isdigit():
            idm = self.remapped_surveys[idm]
            station = f"{idm}.{idd}"

        if idd and not idd.isdigit():
            try:
                station = self.remapped_stations[station]
            except KeyError:
                newstation = self.get_unused_station_for_idm(idm)
                self.remapped_stations[station] = newstation
                station = newstation

        return station


def tro_data_line_to_shot(data: dict) -> dict:
    return EMPTY_SHOT | data


def get_survey_from_station(station: str) -> str:
    idm, dot, idd = station.rpartition(".")
    assert idm
    return idm


def fake_splay_shots(shots: List[dict]) -> Iterable[dict]:
    for shot in shots:
        yield shot

        station = shot["to"]
        if not station:
            continue

        # FIXME hard-coded
        if get_survey_from_station(station) not in ["7", "8", "9"]:
            continue

        if shot["left"] > 0.1:
            yield EMPTY_SHOT | {
                "from": station,
                "compass": (shot["compass"] - 90) % 360,
                "tape": shot["left"]
            }

        if shot["right"] > 0.1:
            yield EMPTY_SHOT | {
                "from": station,
                "compass": (shot["compass"] + 90) % 360,
                "tape": shot["right"]
            }

        if shot["up"] > 0.1:
            yield EMPTY_SHOT | {
                "from": station,
                "clino": 90,
                "tape": shot["up"]
            }

        if shot["down"] > 0.1:
            yield EMPTY_SHOT | {
                "from": station,
                "clino": -90,
                "tape": shot["down"]
            }


def read_tro_shots(filename: Path) -> List[dict]:
    in_param = False

    shots = []

    with open(filename) as handle:
        for line in handle:
            if line.startswith("[Configuration"):
                break

            if not line.rstrip():
                continue

            if line.startswith("Param "):
                in_param = True
            elif in_param:
                data = parse_tro_data_line(line)
                shot = tro_data_line_to_shot(data)
                shots.append(shot)

    remapper = StationRemapper()

    for shot in shots:
        for key in ["from", "to"]:
            remapper.register_used(shot[key])

    for shot in shots:
        for key in ["from", "to"]:
            shot[key] = remapper(shot[key])

    shots = list(fake_splay_shots(shots))

    return shots


def shots_to_top(shots: list) -> dict:
    top = copy.deepcopy(TOP_EMPTY)
    top["shots"] = list(shots)
    return top


def read_tro(filename: Path) -> dict:
    shots = read_tro_shots(filename)

    surveys = defaultdict(list)

    for shot in shots:
        idm = get_survey_from_station(shot["from"])
        surveys[idm].append(shot)

    for idm, idmshots in surveys.items():
        top = shots_to_top(idmshots)
        with open(f"/tmp/janima-{idm}.top", "wb") as handle:
            dump(top, handle)

    return shots_to_top(shots)


def main():
    top = read_tro("/Users/thomas/Survex/Janima/Daniel/Janima 1 sep 2020.tro")

    with open("/tmp/janima.top", "wb") as handle:
        dump(top, handle)

    with open("/tmp/janima.top", "rb") as handle:
        load(handle)


if __name__ == "__main__":
    main()
