#!/usr/bin/env python
'''
Copyright (C) 2008 Thomas Holder, http://sf.net/users/speleo3/
Distributed under the terms of the GNU General Public License v2

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
        m = re.match(r'(.*?)([0-9a-zA-Z]+)($|@.*)', name)
        if m is None:
            raise ValueError("can't increment station name '{}'".format(name))

        self.pre = m.group(1)
        num = m.group(2)
        self.post = m.group(3)

        self.base = 10 if num.isdigit() else 36
        self.number = int(num, self.base)

    def __str__(self):
        return self.pre + to_base(self.number, self.base) + self.post

    def __iter__(self):
        return self

    def __next__(self):
        s = str(self)
        self.number += 1
        return s

    next = __next__


class Th2EnumerateStations(Th2SetProps):
    def __init__(self):
        Th2SetProps.__init__(self)
        self.OptionParser.add_option(
            "--stationname", type="string", dest="stationname")

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
