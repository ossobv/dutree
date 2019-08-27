#!/usr/bin/env python3
# dutree -- a quick and memory efficient disk usage scanner
# Copyright (C) 2017,2018,2019  Walter Doekes, OSSO B.V.
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
# *dutree* shows a summary of the directories/files which take up the most
# space.
#
# Instead of showing *only the root of the files* with sizes, or the
# details of *every file*, it shows *only the paths taking up the most
# space*.
#
# Example usage::
#
#     $ dutree /srv
#
# Annotated output, where only paths of >5% of the total size are shown
# (which is about 4GB for this dataset)::
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
#                    this "leftover" node. that includes everything in
#                    /twinfield_invoices/ except for the /1/ subdirectory
#                    which has its individual listing above.
#      32   B  /srv/*
#                ^-- only /data/ is in /srv/, but the directory itself also
#                    takes up a tiny bit of space
#       -----
#      80.6 G  TOTAL (86558511658)
#
# **NOTE**: The directories do not count the size of themselves, only of
# their contents. This explains any discrepancies with ``du -sb`` output.
#
# **NOTE**: On filesystems with built-in compression (like ZFS) or with many
# sparse files, you may want to check the --count-blocks option.
#
import sys
import warnings

from os import listdir, lstat, path
from stat import S_ISDIR, S_ISREG


class OsWarning(UserWarning):
    pass


class DuNode:
    "Disk Usage Tree node"

    @classmethod
    def new_dir(cls, pathname):
        return cls(pathname, isdir=True, app_size=None, use_size=None)

    @classmethod
    def new_file(cls, pathname, app_size, use_size):
        return cls(pathname, isdir=False, app_size=app_size, use_size=use_size)

    @classmethod
    def new_leftovers(cls, pathname, app_size, use_size):
        # An FF for better sorting, since we sort by pathname at the end.
        return cls(
            pathname + '/\xff*',
            isdir=None, app_size=app_size, use_size=use_size)

    def __init__(self, pathname, isdir, app_size, use_size):
        self._path = pathname
        self._isdir = isdir  # false=file, true=dir, none=mixed
        self._app_size = app_size  # "apparent" size
        self._use_size = use_size  # real used size (from st_blocks)
        assert (
            (None, None) == (app_size, use_size) or   # both None
            None not in (app_size, use_size))         # none None

        # Only nodes without filesize can be non-leaf nodes.
        if app_size is None:
            self._nodes = []
        else:
            self._nodes = None

    def add_branches(self, *nodes):
        "Add a branches to a non-leaf node."
        self._nodes.extend(nodes)

    def count(self):
        "Return how many nodes this contains, including self."
        if self._nodes is None:
            return 1
        return sum(i.count() for i in self._nodes)

    def name(self):
        if self._isdir is None:
            return self._path.split('\xff')[0] + '*'  # remove the sorting FF
        elif self._isdir:
            return self._path + '/'
        return self._path

    def app_size(self):
        "Return the total apparent size, including children."
        if self._nodes is None:
            return self._app_size
        return sum(i.app_size() for i in self._nodes)
    size = app_size  # noqa: backward compatibility

    def use_size(self):
        "Return the total used size, including children."
        if self._nodes is None:
            return self._use_size
        return sum(i.use_size() for i in self._nodes)

    def _add_size(self, app_size, use_size):
        self._app_size += app_size
        self._use_size += use_size

    def _set_size(self, app_size, use_size):
        assert self._nodes is not None
        self._app_size = app_size
        self._use_size = use_size
        self._nodes = None

    def prune_if_smaller_than(self, small_size, a_or_u):
        "Prune/merge all nodes that are smaller than small_size."
        if self._prune_all_if_small(small_size, a_or_u):
            return

        for node in self._nodes:
            node.prune_if_smaller_than(small_size, a_or_u)

        self._prune_some_if_small(small_size, a_or_u)

    def _prune_all_if_small(self, small_size, a_or_u):
        "Return True and delete children if small enough."
        if self._nodes is None:
            return True

        total_size = (self.app_size() if a_or_u else self.use_size())
        if total_size < small_size:
            if a_or_u:
                self._set_size(total_size, self.use_size())
            else:
                self._set_size(self.app_size(), total_size)
            return True

        return False

    def _prune_some_if_small(self, small_size, a_or_u):
        "Merge some nodes in the directory, whilst keeping others."
        # Assert that we're not messing things up.
        prev_app_size = self.app_size()
        prev_use_size = self.use_size()

        keep_nodes = []
        prune_app_size = 0
        prune_use_size = 0
        for node in self._nodes:
            node_size = node.app_size() if a_or_u else node.use_size()
            if node_size < small_size:
                if a_or_u:
                    prune_app_size += node_size
                    prune_use_size += node.use_size()
                else:
                    prune_app_size += node.app_size()
                    prune_use_size += node_size
            else:
                keep_nodes.append(node)

        # Last "leftover" node? Merge with parent.
        if len(keep_nodes) == 1 and keep_nodes[-1]._isdir is None:
            prune_app_size += keep_nodes[-1]._app_size
            prune_use_size += keep_nodes[-1]._use_size
            keep_nodes = []

        if prune_app_size or prune_use_size:
            if not keep_nodes:
                # The only node to keep, no "leftovers" here. Move data
                # to the parent.
                keep_nodes = None
                assert self._isdir and self._nodes is not None
                self._set_size(prune_app_size, prune_use_size)
            elif keep_nodes and keep_nodes[-1]._isdir is None:
                # There was already a leftover node. Add the new leftovers.
                keep_nodes[-1]._add_size(prune_app_size, prune_use_size)
            else:
                # Create a new leftover node.
                keep_nodes.append(DuNode.new_leftovers(
                    self._path, prune_app_size, prune_use_size))

        # Update nodes and do the actual assertion.
        self._nodes = keep_nodes
        assert prev_app_size == self.app_size(), (
            prev_app_size, self.app_size())
        assert prev_use_size == self.use_size(), (
            prev_use_size, self.use_size())

    def merge_upwards_if_smaller_than(self, small_size, a_or_u):
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
        prev_app_size = self.app_size()
        prev_use_size = self.use_size()

        small_nodes = self._find_small_nodes(small_size, (), a_or_u)
        for node, parents in small_nodes:
            # Check immediate grandparent for isdir=None and if it
            # exists, move this there. The isdir=None node is always
            # last.
            if len(parents) >= 2:
                tail = parents[-2]._nodes[-1]
                if tail._isdir is None:
                    assert tail._app_size is not None, tail
                    tail._add_size(node.app_size(), node.use_size())
                    parents[-1]._nodes.remove(node)
                    assert len(parents[-1]._nodes)

        # The actual assertion.
        assert prev_app_size == self.app_size(), (
            prev_app_size, self.app_size())
        assert prev_use_size == self.use_size(), (
            prev_use_size, self.use_size())

    def _find_small_nodes(self, small_size, parents, a_or_u):
        if self._nodes is None:
            if (self._use_size, self._app_size)[a_or_u] < small_size:
                return [(self, parents)]
            return []

        ret = []
        for node in self._nodes:
            ret.extend(
                node._find_small_nodes(small_size, parents + (self,), a_or_u))
        return ret

    def as_tree(self):
        "Return the nodes as a list of lists."
        if self._nodes is None:
            return [self]
        ret = [self]
        for node in self._nodes:
            ret.append(node.as_tree())
        return ret

    def get_leaves(self):
        "Return a sorted leaves: only nodes with fixed file size."
        leaves = self._get_leaves()
        leaves.sort(key=(lambda x: x._path))  # FF sorts "mixed" last
        return leaves

    def _get_leaves(self):
        if self._nodes is None:
            return [self]

        ret = []
        for node in self._nodes:
            ret.extend(node._get_leaves())
        return ret

    def __repr__(self):
        name = self._path
        if self._isdir:
            name += '/'
        return '  {:12d}  {}'.format(self.app_size(), name)


class DuScan:
    "Disk Usage Tree scanner"

    def __init__(self, pathname):
        self._path = self._normpath(pathname)
        self._tree = None
        self._check_path()

    def _normpath(self, pathname):
        "Return path normalized for duscan usage: no trailing slash."
        if pathname == '/':
            pathname = ''
        elif pathname.endswith('/'):
            pathname = pathname[:-1]
        assert not pathname.endswith('/'), pathname
        return pathname

    def _check_path(self):
        "Immediately check if we can access path. Otherwise bail."
        if not path.isdir(self._path or '/'):
            raise OSError('Path {!r} is not a directory'.format(self._path))

    def scan(self, use_apparent_size=True):
        assert self._tree is None
        self._tree = DuNode.new_dir(self._path)
        self._app_subtotal = self._use_subtotal = 0
        app_leftover_bytes, use_leftover_bytes, new_fraction, keep_node = (
            self._scan(self._path, self._tree, use_apparent_size))
        assert keep_node and not app_leftover_bytes, (
            keep_node, app_leftover_bytes, use_leftover_bytes)

        # Do another prune run, since the fraction size has grown during the
        # scan. Then merge nodes that couldn't get merged sooner.
        self._tree.prune_if_smaller_than(
            new_fraction, use_apparent_size)
        self._tree.merge_upwards_if_smaller_than(
            new_fraction, use_apparent_size)
        return self._tree

    def _scan(self, pathname, parent_node, a_or_u):
        fraction = (  # initialize fraction
            (self._use_subtotal, self._app_subtotal)[a_or_u] // 20)
        children = []                        # large separate child nodes

        try:
            files = listdir(pathname or '/')
        except OSError as e:
            # PermissionError: [Errno 13] Permission denied:
            #   '/sys/fs/fuse/connections/85'
            warnings.warn(str(e), OsWarning)
            app_mixed_total = 0
            use_mixed_total = 0
        else:
            files = [pathname + '/' + file_ for file_ in files]
            app_mixed_total, use_mixed_total, fraction = (
                self._scan_inner(files, children, fraction, a_or_u))

        # Do we have children or a total that's large enough: keep this
        # node.
        if children or (use_mixed_total, app_mixed_total)[a_or_u] >= fraction:
            parent_node.add_branches(*children)
            if children:
                child_node = DuNode.new_leftovers(
                    pathname, app_mixed_total, use_mixed_total)
                parent_node.add_branches(child_node)
            else:
                parent_node._set_size(app_mixed_total, use_mixed_total)
            app_mixed_total = use_mixed_total = 0
            keep_node = True
        else:
            keep_node = False

        # Leftovers, the new fraction and whether to keep the child.
        return app_mixed_total, use_mixed_total, fraction, keep_node

    def _scan_inner(self, files, children, fraction, a_or_u):
        app_mixed_total = 0  # "rest of the dir", add to this node
        use_mixed_total = 0

        for file_ in files:
            try:
                st = lstat(file_)
            except OSError as e:
                # Could be deleted:
                #   [Errno 2] No such file or directory: '/proc/14532/fdinfo/3'
                # Could be EPERM:
                #   [Errno 13] Permission denied: '/run/user/1000/gvfs'
                warnings.warn(str(e), OsWarning)
                continue

            if S_ISREG(st.st_mode):
                if st.st_blocks == 0:
                    # Pseudo-files, like the one in /proc have 0-block
                    # files. We definitely don't want to count those,
                    # like /proc/kcore. This does mean that we won't
                    # count sparse files of 0 non-zero blocks either
                    # anymore. I think we can live with that.
                    app_size = use_size = 0
                else:
                    # Count both apparent and block size.
                    app_size = st.st_size
                    use_size = st.st_blocks << 9

                if (use_size, app_size)[a_or_u] >= fraction:
                    child_node = DuNode.new_file(file_, app_size, use_size)
                    children.append(child_node)
                    self._app_subtotal += child_node.app_size()
                    self._use_subtotal += child_node.use_size()
                else:
                    # The file is too small and it doesn't get its own
                    # node. Count it on this node.
                    app_mixed_total += app_size
                    use_mixed_total += use_size
                    self._app_subtotal += app_size
                    self._use_subtotal += use_size

            elif S_ISDIR(st.st_mode):
                child_node = DuNode.new_dir(file_)

                app_leftover_bytes, use_leftover_bytes, fraction, keep_node = (
                    self._scan(file_, child_node, a_or_u))
                if keep_node:
                    assert not app_leftover_bytes, (
                        app_leftover_bytes, use_leftover_bytes)
                    children.append(child_node)
                else:
                    app_mixed_total += app_leftover_bytes
                    use_mixed_total += use_leftover_bytes

                # Also count the directory listing size to get the same
                # total as `du -sb`. Note that du is about 1/3 faster,
                # probably because it (a) keeps less stuff in memory and
                # (b) because it uses a path relative fstatat which
                # consumes less system time, and (c) it has no python
                # overhead.
                app_mixed_total += st.st_size
                use_mixed_total += st.st_blocks << 9
                self._app_subtotal += st.st_size
                self._use_subtotal += st.st_blocks << 9

            else:
                # Also count the whatever-file-this-may-be size (symlink?).
                app_mixed_total += st.st_size
                use_mixed_total += st.st_blocks << 9
                self._app_subtotal += st.st_size
                self._use_subtotal += st.st_blocks << 9

            # Recalculate fraction based on updated subtotal.
            fraction = (
                (self._use_subtotal, self._app_subtotal)[a_or_u] // 20)

        return app_mixed_total, use_mixed_total, fraction


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
    pathname = None
    if len(sys.argv) == 2:
        def getsize(node):
            return node.app_size()

        pathname = sys.argv[1]
        use_apparent_size = True

    elif len(sys.argv) == 3:
        def getsize(node):
            return node.use_size()

        if sys.argv[1] == '--count-blocks':
            pathname = sys.argv[2]
        elif sys.argv[2] == '--count-blocks':
            pathname = sys.argv[1]
        use_apparent_size = False

    if pathname is None:
        sys.stderr.write('Usage: dutree [--count-blocks] PATH\n')
        sys.exit(1)

    run(pathname, use_apparent_size, getsize)


def run(pathname, use_apparent_size, getsize):
    verbose = True and not use_apparent_size
    scanner = DuScan(pathname)
    tree = scanner.scan(use_apparent_size=use_apparent_size)
    for leaf in tree.get_leaves():
        sys.stdout.write(' {0:>7s}  {1}{2}\n'.format(
            human(getsize(leaf)), leaf.name(),
            (' (app={})'.format(human(leaf.app_size())) if verbose else '')))
    sys.stdout.write('   -----\n')
    size = getsize(tree)
    sys.stdout.write(' {0:>7s}  TOTAL ({1}{2})\n'.format(
        human(size), size,
        ', app={}'.format(human(tree.app_size())) if verbose else ''))


def formatwarning(message, category, filename, lineno, line=None):
    """
    Override default Warning layout, from:

        /PATH/TO/dutree.py:326: UserWarning:
            [Errno 2] No such file or directory: '/0.d/05.d'
          warnings.warn(str(e))

    To:

        dutree.py:330: UserWarning:
            [Errno 2] No such file or directory: '/0.d/05.d'
    """
    return '{basename}:{lineno}: {category}: {message}\n'.format(
        basename=path.basename(filename), lineno=lineno,
        category=category.__name__, message=message)
warnings.formatwarning = formatwarning  # noqa


if __name__ == '__main__':
    main()
