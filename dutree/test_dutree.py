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
# The DuScanTests herein test the dutree scanner by mocking the listdir
# and lstat filesystem calls with a bogus on from a GeneratedFilesystem.
#
from __future__ import print_function
from unittest import TestCase, main
from bogofs import GeneratedFilesystem

import dutree


class DuScanTestMixin(object):
    def debug(self, *args):
        # print(*args)
        pass

    def duscan_tree(self, fs, path):
        # Mock.
        dutree.listdir = fs.listdir
        dutree.lstat = fs.stat

        # Scan.
        scanner = dutree.DuScan(path)
        tree = scanner.scan()
        return tree

    def leaves_as_list(self, tree):
        ret = []
        items = tree.get_leaves()
        for item in items:
            ret.append([item.name(), item.size()])
        return ret


class DuScanTest15(DuScanTestMixin, TestCase):
    def setUp(self):
        self.fs = GeneratedFilesystem(seed=1, maxdepth=4)
        self.tree = self.duscan_tree(self.fs, '/')

    def test_filesize(self):
        fs_size = self.fs.get_content_size('/')
        dutree_size = self.tree.size()

        self.debug('DuScanTest15.test_filesize', fs_size)
        self.assertEqual(dutree_size, fs_size)
        self.assertEqual(dutree_size, 2053393838542)
        self.assertEqual(dutree.human(dutree_size), '1.9 T')

    def test_leaves(self):
        expected = [
            # ISSUE #2: "/0.d/02.d/*" should be without Asterisk.
            ['/0.d/02.d/*', 106577108100],
            ['/0.d/05.d/', 113273338762],
            ['/0.d/15.d/', 122711365675],
            ['/0.d/*', 687973286945],
            ['/1.d/00.d/', 125037824539],
            ['/1.d/11.d/', 106972774810],
            ['/1.d/13.d/', 115990023563],
            ['/1.d/*', 672920941814],
            ['/*', 1937174334]]
        self.assertEquals(self.leaves_as_list(self.tree), expected)

    def test_leaf_size(self):
        self.assertEquals(self.fs.get_content_size('/0.d/05.d'), 113273338762)

    def test_sample_file(self):
        self.assertEquals(self.fs.stat('/1.d/13.d/15.txt').size, 22344)


class DuScanTest15Delete(DuScanTestMixin, TestCase):
    def test_handle_deleted(self):
        fs = GeneratedFilesystem(seed=1, maxdepth=4)
        deleted_size = 0

        # Entire dir.
        deleted_size += (
            fs.get_content_size('/0.d/05.d') +
            fs.stat('/0.d/05.d').size)
        fs.hide_from_stat('/0.d/05.d')
        # Single file.
        deleted_size += fs.stat('/1.d/13.d/15.txt').size
        fs.hide_from_stat('/1.d/13.d/15.txt')

        # Scan.
        tree = self.duscan_tree(fs, '/')
        fs_size = fs.get_content_size('/') - deleted_size
        dutree_size = tree.size()

        self.assertEqual(dutree_size, fs_size)
        self.assertEqual(dutree_size, 2053393838542 - deleted_size)


if __name__ == '__main__':
    main()
