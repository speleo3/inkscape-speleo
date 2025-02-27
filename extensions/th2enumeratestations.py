#!/usr/bin/env python
'''
Copyright (C) 2008 Thomas Holder, http://sf.net/users/speleo3/
Distributed under the terms of the GNU General Public License v2 or later

Enumerate therion station names
'''

from typing import Optional
import inkex
import re

from th2setprops import Th2SetProps

therion_laststationname = inkex.addNS('laststationname', 'therion')

BS_lower = "abcdefghijklmnopqrstuvwxyz"
BS_upper = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def to_str(n: int, BS: Optional[str], minwidth: int) -> str:
    if BS is None:
        return str(n).zfill(minwidth)
    b = len(BS)
    def inner(n: int) -> str:
        return ("" if n < b else inner(n // b)) + BS[n % b]
    return inner(n).rjust(minwidth, BS[0])


def to_int(s: str, BS: Optional[str]) -> int:
    if BS is None:
        return int(s)
    b = len(BS)
    return sum(BS.index(c) * b**i for (i, c) in enumerate(reversed(s)))


class StationName:
    def __init__(self, name: str):
        name = name.strip()
        m = re.match(r'(.*?)([0-9]+|[a-z]+|[A-Z]+)($|@.*)', name)
        if m is None:
            raise ValueError("can't increment station name '{}'".format(name))

        self.pre = m.group(1)
        incrementingPart = m.group(2)
        self.post = m.group(3)

        if incrementingPart.isdigit():
            self.bs = None
        elif incrementingPart.islower():
            self.bs = BS_lower
        else:
            self.bs = BS_upper
        self.number = to_int(incrementingPart, self.bs)
        self.minwidth = len(incrementingPart)

    def _get_mid(self) -> str:
        return to_str(self.number, self.bs, self.minwidth)

    def __str__(self) -> str:
        return self.pre + self._get_mid() + self.post

    def __iter__(self):
        return self

    def __next__(self) -> str:
        mid = self._get_mid()

        if self.bs is not None and mid == self.bs[-1] * self.minwidth:
            self.minwidth += 1
            self.number = 0
        else:
            self.number += 1

        return self.pre + mid + self.post

    next = __next__


class Th2EnumerateStations(Th2SetProps):
    def __init__(self):
        Th2SetProps.__init__(self)
        self.arg_parser.add_argument(
            "--stationname", type=str, dest="stationname")

    def update_options(self, options: dict):
        options['name'] = next(self.stationnames)

    def effect(self):
        root = self.document.getroot()
        stationname = self.options.stationname

        if not stationname:
            stationname = root.get(therion_laststationname)
            if not stationname:
                raise ValueError("empty station name")

        self.stationnames = StationName(stationname)

        Th2SetProps.effect(self)

        root.set(therion_laststationname, str(self.stationnames))


if __name__ == '__main__':
    e = Th2EnumerateStations()
    e.run()
