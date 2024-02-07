#!/usr/bin/env python
'''
Copyright (C) 2008 Thomas Holder, http://sf.net/users/speleo3/
Distributed under the terms of the GNU General Public License v2 or later

Enumerate therion station names
'''

import inkex
import re

from th2setprops import Th2SetProps

therion_laststationname = inkex.addNS('laststationname', 'therion')

BS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def to_base(n, b=len(BS)):
    return "0" if not n else to_base(n // b, b).lstrip("0") + BS[n % b]


class StationName:
    def __init__(self, name):
        name = name.strip()
        m = re.match(r'([0-9a-zA-Z]+)($|@.*)', name)
        if m is None:
            raise ValueError("can't increment station name '{}'".format(name))

        stationName = m.group(1)
        self.post = m.group(2)

        self.pre, incrementingPart = SeparateStationNameParts(stationName)

        if incrementingPart.isdigit():
            self.base = 10
            self.convertToLower = False
        else:
            self.base = 36
            self.convertToLower = incrementingPart.islower()
        self.number = int(incrementingPart, self.base)

    def __str__(self):
        incrementingPart = to_base(self.number, self.base)
        if self.convertToLower:
            incrementingPart = incrementingPart.lower()
        return self.pre + incrementingPart + self.post

    def __iter__(self):
        return self

    def __next__(self):
        s = str(self)
        self.number += 1
        return s

    next = __next__

def SeparateStationNameParts(s):
    part1, part2 = '', ''

    # Check if the string is entirely alphabetic or numeric
    if s.isalpha() or s.isdigit():
        return '', s

    # Start from the end of the string and look for the transition point
    for i in range(len(s) - 1, 0, -1):
        if (s[i].isdigit() and s[i-1].isalpha()) or (s[i].isalpha() and s[i-1].isdigit()):
            part1 = s[:i]
            part2 = s[i:]
            break

    return part1, part2


class Th2EnumerateStations(Th2SetProps):
    def __init__(self):
        Th2SetProps.__init__(self)
        self.arg_parser.add_argument(
            "--stationname", type=str, dest="stationname")

    def update_options(self, options):
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
    e.affect()

# vi:expandtab:sw=4
