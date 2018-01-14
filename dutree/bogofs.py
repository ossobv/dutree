# dutree -- a quick and memory efficient disk usage scanner
# Copyright (C) 2018  Walter Doekes, OSSO B.V.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#
# The GeneratedFilesystem contained herein is used by the dutree test
# cases. It pesudo-randomly generates an in-memory filesystem, so the DuScan
# scanner can be tested on a consistent filesystem.
#
from __future__ import print_function
from random import Random


class Node(object):
    def __init__(self, name, size):
        self.name = name
        self.size = size

    @property
    def st_blocks(self):  # for stat
        return ((self.size + 511) >> 9)

    @property
    def st_size(self):  # for stat
        return self.size


class DirNode(Node):
    def __init__(self, name):
        size = 4096  # bogus obviously, but most common
        super(DirNode, self).__init__(name, size)
        self.dirs = []
        self.files = []

        self.st_mode = 16384  # for stat: 0o40000 S_ISDIR

    def generate(self, fs, maxdepth):
        # With the current FS generation parameters, maxdepth of 5 is
        # more than enough.
        assert 0 <= maxdepth < 6, 'invalid maxdepth value'

        # Generate dirs.
        if maxdepth > 0:
            dirs = fs.create_dirs()
            for dir_ in dirs:
                dir_.generate(fs, maxdepth - 1)
            self.dirs.extend(dirs)

        # Generate files.
        files = fs.create_files()
        self.files.extend(files)

    def __str__(self):
        return '[{:12d}] {}/'.format(self.size, self.name)


class RegularFileNode(Node):
    def __init__(self, name, size):
        super(RegularFileNode, self).__init__(name, size)

        self.st_mode = 32768  # for stat: 0o100000 S_ISREG

    def __str__(self):
        return '[{:12d}] {}'.format(self.size, self.name)


class GeneratedFilesystem:
    def __init__(self, seed=3, maxdepth=4):
        self._rand = Random(seed)
        self.choice = self._rand.choice
        self.randint = self._rand.randint

        self._root = DirNode('ROOT')
        self._root.generate(self, maxdepth)

        self._cache_dict = self.to_dict()

    def create_unique(self, n):
        fmt = '{{:0{0}d}}'.format(len(str(n)))
        return [fmt.format(i) for i in range(n)]

    def create_dirs(self):
        n = self.how_many_dirs()
        return [DirNode('{}.d'.format(i)) for i in self.create_unique(n)]

    def create_files(self):
        n = self.how_many_files()
        return [RegularFileNode('{}.txt'.format(i), self.how_large_file())
                for i in self.create_unique(n)]

    def how_many_dirs(self):
        return self.randint(0, 20)

    def how_many_files(self):
        n = self.randint(0, 80)
        if n < 70:
            return n
        n -= 70
        return self.randint(0, 2 ** n)

    def how_large_file(self):
        if self.randint(0, 80):
            return self.randint(1, 2 ** 16)  # not so large
        return self.randint(1, 2 ** 31)      # large

    def to_dict(self):
        ret = {}
        self._to_dict(ret, '', self._root)
        root_path = ret.pop('')  # for "/ROOT" hack
        assert root_path
        ret['/'] = root_path
        return ret

    def _to_dict(self, ret, prefix, node):
        prefix += '/' + node.name
        ret[prefix[5:]] = node  # drop "/ROOT"

        for dir_ in node.dirs:
            self._to_dict(ret, prefix, dir_)
        for file_ in node.files:
            ret[(prefix + '/' + file_.name)[5:]] = file_

    def _normpath(self, path):
        if path.startswith('/./'):
            path = path[2:]
        elif path == '/.':
            path = '/'
        assert path.startswith('/'), path
        return path

    def _get_node(self, path):
        try:
            node = self._cache_dict[path]
        except KeyError:
            raise OSError(2, "No such file or directory: {0!r}".format(path))
        return node

    def get_content_size(self, path):
        "Return size of files/dirs contents excluding parent node."
        node = self._get_node(path)
        return self._get_content_size(node) - node.size

    def _get_content_size(self, node):
        size = node.size
        size += sum(i.size for i in node.files)
        for dir_ in node.dirs:
            size += self._get_content_size(dir_)
        return size

    def hide_from_stat(self, path):
        """'Delete' a file, so it will turn up in the listdir, but fail
        on stat.

        This is used so check that we cope with listdir/stat races.
        """
        del self._cache_dict[path]

    def listdir(self, path):
        node = self._get_node(path)
        return (
            [i.name for i in node.dirs] +
            [i.name for i in node.files])

    def stat(self, path):
        return self._get_node(path)

    def walk(self, path):
        path = self._normpath(path)
        walker = iter(self._walk('', self._root))
        item = next(walker)
        yield item[0] or '/', item[1], item[2]  # /ROOT hack
        for item in walker:
            yield item

    def _walk(self, prefix, node):
        prefix += '/' + node.name
        yield (
            prefix[5:],  # /ROOT hack
            [i.name for i in node.dirs],
            [i.name for i in node.files])
        for dir_ in node.dirs:
            for item in self._walk(prefix, dir_):
                yield item


if __name__ == '__main__':
    from textwrap import wrap
    fs = GeneratedFilesystem(seed=3, maxdepth=2)
    print('GeneratedFilesystem:')
    print('  size =', fs.get_content_size('/'))
    for name, dirs, files in fs.walk('/'):
        print(name)
        print('  ' + '\n  '.join(wrap(' '.join(files), 70)))
