#!/usr/bin/env python3
# dutree -- a quick and memory efficient disk usage scanner
# Copyright (C) 2017  Walter Doekes, OSSO B.V.
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
# dutree lists disk usage in the path you specify, but instead of giving
# a grand total, or a detailed tree, it gives something in between: it
# shows in which paths the big files/directories can be found.
#
# Example usage:
#
#     $ dutree /srv
#
# Annotated output, where only paths of >4G are shown:
#
#      12.1 G  /srv/data/audiofiles/
#               ^-- audiofiles contains files/dirs with a total of 12.1G
#                   but it does NOT contain a single dir or file larger
#                   than 4G.
#       4.3 G  /srv/data/callrecordings/unmatched/
#       4.5 G  /srv/data/fax/
#      17.5 G  /srv/data/playlists/
#      34.4 G  /srv/data/twinfield_invoices/1/
#       7.8 G  /srv/data/*
#                ^-- data contains more files/directories than shown above
#                    but those that don't total above 4G are merged into
#                    this "leftover" node. That includes /twinfield_invoices/
#                    except for the /1/ subdirectory which already has its
#                    individual listing.
#      32   B  /srv/*
#                ^-- there was only /data/ in /srv/, but the directory itself
#                    also takes up a tiny bit of space
#       -----
#      80.6 G  TOTAL (86558511658)
#
# NOTE: The directories do not count the size of themselves, only of their
# contents. This explains any discrepancies with `du -sb` output.
#
import sys

from os import listdir, lstat
from stat import S_ISDIR, S_ISREG


class DuNode:
    "Disk Usage Tree node"

    @classmethod
    def new_dir(cls, path, filesize=None):
        return cls(path, isdir=True, filesize=filesize)

    @classmethod
    def new_file(cls, path, filesize):
        return cls(path, isdir=False, filesize=filesize)

    @classmethod
    def new_leftovers(cls, path, filesize):
        # An FF for better sorting, since we sort by pathname at the end.
        return cls(path + '/\xff*', isdir=None, filesize=filesize)

    def __init__(self, path, isdir=True, filesize=None):
        self._path = path
        self._isdir = isdir  # false=file, true=dir, none=mixed
        self._filesize = filesize

        # Only nodes without filesize can be non-leaf nodes.
        if filesize is None:
            self._nodes = []

    def add_branches(self, *nodes):
        "Add a branches to a non-leaf node."
        self._nodes.extend(nodes)

    def count(self):
        "Return how many nodes this contains, including self."
        if self._filesize is None:
            return sum(i.count() for i in self._nodes)
        return 1

    def name(self):
        if self._isdir is None:
            return self._path.split('\xff')[0] + '*'  # remove sorting FF
        elif self._isdir:
            return self._path + '/'
        return self._path

    def size(self):
        "Return the total size, including children."
        if self._filesize is None:
            return sum(i.size() for i in self._nodes)
        return self._filesize

    def prune_if_smaller_than(self, small_size):
        "Prune/merge all nodes that are smaller than small_size."

        if self._filesize is not None:
            return

        total_size = self.size()
        if total_size < small_size:
            self._filesize = total_size
            del self._nodes
            return

        for node in self._nodes:
            node.prune_if_smaller_than(small_size)

        # Loop over the still existing nodes and check if we can merge
        # *some* of the nodes, while keeping others.

        # Assert that we're not messing things up.
        prev_size = self.size()

        keep_nodes = []
        prune_size = 0
        for node in self._nodes:
            size = node.size()
            if size < small_size:
                prune_size += size
            else:
                keep_nodes.append(node)
        if prune_size:
            if keep_nodes and keep_nodes[-1]._isdir is None:
                keep_nodes[-1]._filesize += prune_size
            else:
                keep_nodes.append(DuNode.new_leftovers(self._path, prune_size))

        # Update nodes and do the actual assertion.
        self._nodes = keep_nodes
        assert prev_size == self.size(), (prev_size, self.size())

    def merge_upwards_if_smaller_than(self, small_size):
        """After prune_if_smaller_than is run, we may still have excess
        nodes.

        For example, with a small_size of 609710690:

                     7  /*
              28815419  /data/*
                    32  /data/srv/*
                925746  /data/srv/docker.bak/*
                    12  /data/srv/docker.bak/shared/*
             682860348  /data/srv/docker.bak/shared/standalone/*

        This is reduced to:

              31147487  /*
             682860355  /data/srv/docker.bak/shared/standalone/*

        Run this only when done with the scanning."""

        # Assert that we're not messing things up.
        prev_size = self.size()

        small_nodes = self._find_small_nodes(small_size, ())
        for node, parents in small_nodes:
            # Check immediate grandparent for isdir=None and if it
            # exists, move this there. The isdir=None node is always
            # last.
            if len(parents) >= 2:
                tail = parents[-2]._nodes[-1]
                if tail._isdir is None:
                    assert tail._filesize is not None, tail
                    tail._filesize += node.size()
                    parents[-1]._nodes.remove(node)
                    assert len(parents[-1]._nodes)

        # The actual assertion.
        assert prev_size == self.size(), (prev_size, self.size())

    def _find_small_nodes(self, small_size, parents):
        if self._filesize is not None:
            if self._filesize < small_size:
                return [(self, parents)]
            return []

        ret = []
        for node in self._nodes:
            ret.extend(node._find_small_nodes(small_size, parents + (self,)))
        return ret

    def get_leaves(self):
        "Return a sorted leaves: only items with fixed file size."
        leaves = self._get_leaves()
        leaves.sort(key=(lambda x: x._path))
        return leaves

    def _get_leaves(self):
        if self._filesize is not None:
            return [self]

        ret = []
        if self._filesize is None:
            for node in self._nodes:
                ret.extend(node._get_leaves())
        return ret

    def __repr__(self):
        name = self._path
        if self._isdir:
            name += '/'
        return '  {:12d}  {}'.format(self.size(), name)


class DuScan:
    "Disk Usage Tree scanner"

    def __init__(self, path):
        assert not path.endswith('/'), path
        self._path = path
        self._tree = None

    def scan(self):
        assert self._tree is None
        self._tree = DuNode.new_dir(self._path)
        new_total, new_fraction, keep_node, leftover_bytes = self._scan(
            self._tree, self._path, 0)
        assert keep_node and not leftover_bytes, (keep_node, leftover_bytes)

        # Do another prune run, since the fraction size has grown during the
        # scan. Then merge nodes that couldn't get merged sooner.
        self._tree.prune_if_smaller_than(new_fraction)
        self._tree.merge_upwards_if_smaller_than(new_fraction)
        return self._tree

    def _scan(self, parent_node, path, subtotal):
        self_scan = self._scan      # local cache
        fraction = subtotal // 20   # initialize fraction
        children = []               # large separate child nodes
        pruned_one = False          # did we prune at least one dir
        mixed_total = 0             # "rest of the dir", add to this node

        for file_ in listdir(path):
            fn = path + '/' + file_
            st = lstat(fn)

            if S_ISREG(st.st_mode):
                size = st.st_size
                if size >= fraction:
                    child_node = DuNode.new_file(fn, size)
                    children.append(child_node)
                    subtotal += child_node.size()
                else:
                    # The file is too small and it doesn't get its own
                    # node. Count it on this node.
                    mixed_total += size
                    subtotal += size

            elif S_ISDIR(st.st_mode):
                child_node = DuNode.new_dir(fn)

                subtotal, fraction, keep_node, leftover_bytes = self_scan(
                    child_node, fn, subtotal)
                if keep_node:
                    assert not leftover_bytes, leftover_bytes
                    children.append(child_node)
                else:
                    pruned_one = True
                    mixed_total += leftover_bytes

                # Also count the directory listing size to get the same
                # total as `du -sb`. Note that du is about 1/3 faster,
                # probably because it (a) keeps less stuff in memory and
                # (b) because it uses a path relative fstatat which
                # consumes less system time, and (c) it has no python
                # overhead.
                mixed_total += st.st_size
                subtotal += st.st_size

            else:
                # Also count the whatever-file-this-may-be size (symlink?).
                mixed_total += st.st_size
                subtotal += st.st_size

            # Recalculate fraction based on updated subtotal.
            fraction = subtotal // 20

        if children or mixed_total >= fraction:
            parent_node.add_branches(*children)
            if children and pruned_one:
                child_node = DuNode.new_leftovers(path, mixed_total)
            else:
                child_node = DuNode.new_dir(path, mixed_total)
            parent_node.add_branches(child_node)
            mixed_total = 0
            keep_node = True
        else:
            keep_node = False

        return subtotal, fraction, keep_node, mixed_total


def human(value):
    "If val>=1000 return val/1024+KiB, etc."
    if value >= 1073741824000:
        return '{:.1f} T'.format(value / 1099511627776.0)
    if value >= 1048576000:
        return '{:.1f} G'.format(value / 1073741824.0)
    if value >= 1024000:
        return '{:.1f} M'.format(value / 1048576.0)
    if value >= 1000:
        return '{:.1f} K'.format(value / 1024.0)
    return '{}   B'.format(value)


def main():
    if len(sys.argv) != 2:
        sys.stderr.write('Usage: dutree PATH\n')
        sys.exit(1)

    path = sys.argv[1]
    if path == '/':
        path = '/.'
    elif path.endswith('/'):
        path = path[:-1]

    scanner = DuScan(path)
    tree = scanner.scan()
    items = tree.get_leaves()
    for item in items:
        sys.stdout.write(
            ' {0:>7s}  {1}\n'.format(human(item.size()), item.name()))
    sys.stdout.write('   -----\n')
    size = tree.size()
    sys.stdout.write(' {0:>7s}  TOTAL ({1})\n'.format(human(size), size))


if __name__ == '__main__':
    main()
