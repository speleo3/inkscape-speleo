'''
Library to handle Survex 3D files (*.3d)

Copyright (C) 2008-2012 Thomas Holder, http://sf.net/users/speleo3/
Distributed under the terms of the GNU General Public License v2

Example usage:

    load 3d file
    >>> from survex import Survex3D
    >>> survey = Survex3D('all.3d')

    number of stations
    >>> print len(survey)
    18066

    number of stations with prefix 143.
    >>> stations143 = list(survey.filter('143.'))
    >>> print len(stations143)
    383

    number of legs
    >>> print len(list(survey.iterlegs()))
    18218

    all labels of station p40a
    >>> survey['p40a'].labels
    ['laser.8_14', 'p40a', '40.eishohle.400', '40entlink2.14', '40to88.400']

    length of shortest path from p40a to p41a in meters
    >>> length, path = survey.shortestpath('p40a', 'p41a')
    >>> print length / 100.0
    1610.49206552

    station properties
    >>> survey['p40a'].is_surface()
    True

    sort stations by date
    >>> x = sorted(survey, key=lambda s: s.date)
    >>> x[0].date
    DateNone
    >>> x[-1].date
    Date(2012, 8, 29)

'''

import datetime

class Station(object):
    '''
    Survey station
    '''
    def __init__(self, xyz):
        assert isinstance(xyz, tuple)
        self.xyz = xyz
        self.labels = []
        self.connected_from = []
        self.connected_to = []
        self.flag = 0
        self.date = DateNone

    def __repr__(self):
        return '<%s %s%s>' % (self.__class__.__name__,
                ', '.join(self.labels[:3]),
                ', ...' if len(self.labels) > 3 else '')

    def connect(self, other):
        '''define a leg from other to self'''
        self.connected_from.append(other)
        other.connected_to.append(self)

    def distance(self, other):
        '''Euclidean distance to other station'''
        return sum((a-b)**2 for (a,b) in zip(self.xyz, other.xyz))**0.5

    def distance_vertical(self, other):
        '''Signed altitude difference to other station (if other is below
        self, distance is negative)'''
        return other.z - self.z

    def distance_horizontal(self, other):
        '''Horizontal distance to other station'''
        return ((self.x - other.x)**2 + (self.y - other.y)**2)**0.5

    def bearing(self, other):
        '''Compass direction to other station in degrees, 0.0 if other is
        north of self'''
        from math import atan2, degrees
        b = degrees(atan2(other.x - self.x, other.y - self.y))
        return b % 360.0

    @property
    def connected(self):
        '''Iterator over connected stations'''
        from itertools import chain
        return chain(self.connected_from, self.connected_to)

    @property
    def label(self):
        '''(First) label of this station'''
        if len(self.labels) == 0:
            return '<unnamed station>'
        return self.labels[0]

    @property
    def therionlabel(self):
        '''Therion style label, x.y.z becomes z@y.x'''
        a = self.label.split('.')
        if len(a) == 1:
            return a[0]
        a.reverse()
        return a[0] + '@' + '.'.join(a[1:])

    @property
    def x(self): return self.xyz[0]
    @property
    def y(self): return self.xyz[1]
    @property
    def z(self): return self.xyz[2]

    def is_surface(self):
        return bool(self.flag & 0x01)
    def is_underground(self):
        return bool(self.flag & 0x02)
    def is_entrance(self):
        return bool(self.flag & 0x04)
    def is_exported(self):
        return bool(self.flag & 0x08)
    def is_fixed(self):
        return bool(self.flag & 0x10)

    def shortestpath(self, other, verbose=0):
        '''
        Shortest Path between two stations. If verbose=2 then print path with
        station names.
        
        Returns tuple of the length of the path (or -1 if no path is found) and
        list of stations along the path.

        Uses A* algorithm, adapted from Wikipedia:    
        http://en.wikipedia.org/w/index.php?title=A*_search_algorithm&oldid=289896415
        '''
        def reconstruct_path(current_node):
            if came_from.has_key(current_node):
                p = reconstruct_path(came_from[current_node])
                p.append(current_node)
                return p
            return [self]
    
        came_from = {}        # Map for backtrace (reconstruct_path)
        closedset = set()     # The set of nodes already evaluated.
        openset = [ self ]    # List sorted by f_score
        g_score = { self: 0 } # Distance from self along optimal path.
        h_score = { self: self.distance(other) } # Estimated lower bound from y to other
        f_score = { self: h_score[self] }        # Estimated total distance from self to other through y.
        while len(openset) > 0:
            x = openset.pop(0)
            if x == other:
                path = reconstruct_path(other)
                if verbose > 0:
                    print 'Found path over %d stations' % (len(path))
                if verbose > 1:
                    print ' - '.join(s.label for s in path)
                return g_score[other], path
            closedset.add(x)
            for y in x.connected:
                if y in closedset:
                    continue
                tentative_g_score = g_score[x] + x.distance(y)
                tentative_is_better = False
                if y not in openset:
                    h_score[y] = y.distance(other)
                    tentative_is_better = True
                elif tentative_g_score < g_score[y]:
                    openset.remove(y)
                    tentative_is_better = True
                if tentative_is_better:
                    came_from[y] = x
                    g_score[y] = tentative_g_score
                    f_score[y] = tentative_g_score + h_score[y]
                    for i in xrange(len(openset)):
                        if f_score[y] < f_score[openset[i]]:
                            openset.insert(i, y)
                            break
                    else:
                        openset.append(y)
        if verbose:
            print 'No path from %s to %s' % (self.label, other.label)
        return -1, []

class Survex3D(object):
    '''
    Datastructure to represent a "Survex 3D Image File".

    http://trac.survex.com/browser/trunk/doc/3dformat.htm

    Properties:
     * Map of coords to stations (one station per unique xyz)
     * Map of labels to stations (multiple labels per station possible)
     * Iterator over stations

    For each xyz position there is only one unique station, but a station
    can have multiple labels.

    It's in principle possible to load multiple 3d files into the same
    instance, but only makes sense if there are no overlapping station
    names.
    '''
    def __init__(self, filename=None):
        self.clear()
        if filename is None:
            pass
        elif isinstance(filename, basestring):
            self.load(filename)
        else:
            # assume iterable with stations
            for station in filename:
                self.xyz2sta[station.xyz] = station
            self.reindex()

    def clear(self):
        '''Remove all stations'''
        self.title = '<unnamed survey>'
        self.xyz2sta = {} # Map of xyz to stations
        self.lab2sta = {} # Map of labels to stations
        self.passages = [] # passages with LRUD data
        self._prev = None
        self._curr_label = ''
        self._curr_date = DateNone

    def reindex(self):
        '''Update label to station mapping'''
        self.lab2sta = {}
        for station in self:
            for label in station.labels:
                self.lab2sta[label] = station

    def __len__(self):
        return len(self.xyz2sta)

    def __repr__(self):
        return '<%s "%s" %d stations>' % (self.__class__.__name__, self.title, len(self))

    def __getitem__(self, key):
        if isinstance(key, str):
            return self.lab2sta[key]
        if isinstance(key, tuple):
            return self.xyz2sta[key]
        raise TypeError('indices must be str or tuple')

    def _move(self, xyz):
        self._prev = self._get_or_new(xyz)

    def _line(self, xyz):
        assert self._prev != None
        station = self._get_or_new(xyz)
        station.connect(self._prev)
        self._prev = station

    def _label(self, xyz, flag=0):
        station = self._get_or_new(xyz)
        station.labels.append(self._curr_label)
        self.lab2sta[self._curr_label] = station
        if flag > 0:
            station.flag = flag

    def _lrud(self, lrud, flag=0):
        self.passages.append((self._curr_label, lrud))
        if flag & 0x01:
            self.passages.append(None)
 
    def extent(self):
        '''
        Get the boundig box of all stations as [[xmin, ymin, zmin], [xmax, ymax, zmax]]
        '''
        return [
            [min(station.xyz[i] for station in self) for i in range(3)],
            [max(station.xyz[i] for station in self) for i in range(3)],
        ]

    def length(self):
        '''Total length of survey shots (warning: does not consider duplicate
        or splay flags)'''
        return sum(s1.distance(s2) for (s1, s2) in self.iterlegs())

    def depth(self):
        '''Vertical range of all stations in this survey'''
        zmax = max(station.z for station in self)
        zmin = min(station.z for station in self)
        return zmax - zmin

    def filter(self, prefix):
        '''
        Iterator over stations that have a label starting with prefix.
        '''
        for station in self:
            if any(label.startswith(prefix) for label in station.labels):
                yield station

    def _get_or_new(self, xyz):
        '''Like self.xyz2sta.setdefault(xyz, Station(xyz))'''
        station = self.xyz2sta.get(xyz)
        if station is None:
            station = self.xyz2sta[xyz] = Station(xyz)
            station.date = self._curr_date
        return station

    def iterstations(self):
        '''Iterator over all stations'''
        return self.xyz2sta.itervalues()
 
    __iter__ = iterstations

    def iterlegs(self, dosort=False):
        '''Iterator over tuples of stations that are connected by a leg'''
        for station in self:
            for other in station.connected_from:
                # station could be connected to another one that is not
                # member of this instance, so better check
                if other.xyz in self.xyz2sta:
                    yield station, other

    def iterlabels(self):
        '''Iterator over all station labels'''
        return iter(self.lab2sta)

    def sortedlabels(self):
        '''Naturally sorted list of labels'''
        return sorted(self.lab2sta, key=natkey)

    def print_points(self):
        '''
        Print stations as coords with station name to stdout, sorted by station
        names.
        '''
        for label in self.sortedlabels():
            station = self[label]
            print '%6d %6d %6d ' % station.xyz, label

    def print_lrud(self):
        '''Print LRUD data'''
        for xsect in self.passages:
            if xsect is None:
                print 'END'
            else:
                print xsect[0], xsect[1]

    def shortestpath(self, key1, key2):
        '''Shortest Path between two stations (see Station.shortestpath)'''
        return self[key1].shortestpath(self[key2])

    def neareststations(self, other):
        '''
        Finds the two nearest stations between two surveys.
        Returns a tuple of (distance, station1, station2).

        If "numpy" is not available this might be very slow.
        '''
        X = list(self.xyz2sta)
        Y = list(other.xyz2sta)

        if set(X).intersection(Y):
            raise ValueError('self and other must not have stations in common')

        try:
            from scipy import inf, spatial
        except ImportError:
            return self._neareststations_no_scipy(other, X, Y)

        tree = spatial.cKDTree(X)
        d, i = tree.query(Y)

        j = d.argmin()
        return d[j], self[X[i[j]]], other[Y[j]]

    def _neareststations_no_scipy(self, other, X, Y):
        try:
            from numpy import array
        except ImportError:
            print 'Warning: no numpy available, calculation might be very slow'
            return min((s1.distance(s2), s1, s2) for s1 in self for s2 in other)

        Y = array(Y, int)

        # calculate rows of the distance matrix as trade-off between speed
        # and memory (full distance matrix at once would be fastest, but can
        # blow your memory for large surveys)
        im, jm, m = 0, 0, 1e300
        for i in xrange(len(X)):
            d_sq = ((Y - X[i])**2).sum(1)
            j = d_sq.argmin()
            if d_sq[j] < m:
                im, jm, m = i, j, d_sq[j]

        return m**0.5, self[tuple(X[im])], other[tuple(Y[jm])]

    def load(self, filename):
        '''
        Load 3d file
        '''
        from struct import unpack

        f = open(filename, 'rb')
        line = f.readline() # File ID
        if not line.startswith('Survex 3D Image File'):
            raise IOError('not a Survex 3D File, aborting')

        line = f.readline() # File format version
        assert line[0] == 'v'
        ff_version = int(line[1:])

        self.title = unicode(f.readline().rstrip(), 'latin1') # Survex title
        self.timestamp = f.readline().rstrip() # Timestamp

        def read_xyz():
            return unpack('<iii', f.read(12))

        def read_len():
            length = ord(f.read(1))
            if length == 0xfe:
                length += unpack('<H', f.read(2))[0]
            elif length == 0xff:
                length += unpack('<I', f.read(4))[0]
            return length

        def read_label():
            length = read_len()
            if length > 0:
                self._curr_label += skip_bytes(length)

        def skip_bytes(n):
            return f.read(n)

        while True:
            byte = f.read(1)
            if byte == '':
                break

            byte = ord(byte)

            if byte == 0x00:
                # STOP
                self._curr_label = ''
            elif byte <= 0x0e:
                # TRIM
                # FIXME: according to doc, trim 16 bytes, but img.c does 17!
                (i,n) = (-17,0)
                while n < byte:
                    i -= 1
                    if self._curr_label[i] == '.': n += 1
                self._curr_label = self._curr_label[:i + 1]
            elif byte <= 0x0f:
                # MOVE
                xyz = read_xyz()
                self._move(xyz)
            elif byte <= 0x1f:
                # TRIM
                self._curr_label = self._curr_label[:15 - byte]
            elif byte <= 0x20:
                # DATE
                if ff_version < 7:
                    self._curr_date = Date.fromseconds(*unpack('<L', f.read(4)))
                else:
                    self._curr_date = Date.fromdays(*unpack('<H', f.read(2)))
            elif byte <= 0x21:
                # DATE
                if ff_version < 7:
                    self._curr_date = Date.fromseconds(*unpack('<LL', f.read(8)))
                else:
                    self._curr_date = Date.fromdaysspan(*unpack('<HB', f.read(3)))
            elif byte <= 0x22:
                # Error info
                skip_bytes(5 * 4)
            elif byte <= 0x23:
                # DATE
                self._curr_date = Date.fromdays(*unpack('<HH', f.read(4)))
            elif byte <= 0x24:
                # DATE
                self._curr_date = DateNone
            elif byte <= 0x2f:
                # Reserved
                continue
            elif byte <= 0x31:
                # XSECT
                read_label()
                lrud = unpack('<hhhh', f.read(8))
                self._lrud(lrud, byte & 0x01)
            elif byte <= 0x33:
                # XSECT
                read_label()
                lrud = unpack('<iiii', f.read(16))
                self._lrud(lrud, byte & 0x01)
            elif byte <= 0x3f:
                # Reserved
                continue
            elif byte <= 0x7f:
                # LABEL
                read_label()
                xyz = read_xyz()
                self._label(xyz, byte & 0x3f)
            elif byte <= 0xbf:
                # LINE
                read_label()
                xyz = read_xyz()
                self._line(xyz)
            elif byte <= 0xff:
                # Reserved
                continue

class Date(datetime.date):
    '''
    Survey date range
    '''
    @classmethod
    def fromdays(cls, date1, date2=None):
        self = cls.fromordinal(693596 + date1)
        self.end = cls.fromdays(date2) if date2 else self
        return self

    @classmethod
    def fromdaysspan(cls, date1, datespan):
        return cls.fromdays(date1, date1 + datespan)

    @classmethod
    def fromseconds(cls, date1, date2=None):
        self = cls.fromtimestamp(date1)
        self.end = cls.fromtimestamp(date2) if date2 else self
        return self

class DateNone(Date):
    '''
    Singleton for missing date information.
    '''
    __nonzero__ = lambda s: False
    __repr__ = lambda s: s.__class__.__name__
    __str__ = __repr__
Date.end = DateNone = DateNone(1, 1, 1)

def natkey(s):
    '''
    Key function for "natural sorting" of strings.

    Example:
    >>> L = ['1', '10', '2', '1a']
    >>> sorted(L, key=natkey)
    ['1', '1a', '2', '10']
    '''
    L = len(s)
    if L == 0:
        return tuple()
    r, i, d = [], 0, s[0].isdigit()
    for j in range(L):
        if d != s[j].isdigit():
            r.append(int(s[i:j]) if d else s[i:j].lower())
            i, d = j, not d
    r.append(int(s[i:]) if d else s[i:].lower())
    return r

# vi:expandtab:smarttab
