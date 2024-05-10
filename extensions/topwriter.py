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

import copy
import time
from typing import List, Iterable
from pathlib import Path
from collections import defaultdict

from topreader import (
    EXTEND_RIGHT,
    KEY_EXTEND,
    dump,
    load,
)

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
    KEY_EXTEND: EXTEND_RIGHT,
}


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
