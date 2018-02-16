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
    maxDiff = None

    @staticmethod
    def debug(self, *args):
        # print(*args)
        pass

    @staticmethod
    def duscan_tree(fs, path):
        # Mock.
        dutree.listdir = fs.listdir
        dutree.lstat = fs.stat

        # Scan.
        scanner = dutree.DuScan(path)
        tree = scanner.scan()
        return tree

    @staticmethod
    def leaves_as_list(tree):
        ret = []
        items = tree.get_leaves()
        for item in items:
            ret.append((item.name(), item.size()))
        return ret

    @staticmethod
    def tree_as_list(tree):
        def _as_list(it):
            if isinstance(it, list):
                return [_as_list(i) for i in it]
            return (it.name(), it.size())
        return _as_list(tree.as_tree())


class DuScanSeed1Depth4Test(DuScanTestMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fs = GeneratedFilesystem(seed=1, maxdepth=4)
        cls.tree = cls.duscan_tree(cls.fs, '/')

    def test_filesize(self):
        fs_size = self.fs.get_content_size('/')
        dutree_size = self.tree.size()

        self.debug('DuScanSeed1Depth4Test.test_filesize', fs_size)
        self.assertEqual(dutree_size, fs_size)
        self.assertEqual(dutree_size, 2053393838542)
        self.assertEqual(dutree.human(dutree_size), '1.9 T')

    def test_leaves(self):
        expected = [
            ('/0.d/02.d/', 106577108100),  # not "/0.d/02.d/*"
            ('/0.d/05.d/', 113273338762),
            ('/0.d/15.d/', 122711365675),
            ('/0.d/*', 687973286945),
            ('/1.d/00.d/', 125037824539),
            ('/1.d/11.d/', 106972774810),
            ('/1.d/13.d/', 115990023563),
            ('/1.d/*', 672920941814),
            ('/*', 1937174334)]
        self.assertEquals(self.leaves_as_list(self.tree), expected)

    def test_tree(self):
        expected = [
            ('/', 2053393838542),
            [('/0.d/', 1030535099482),
             [('/0.d/02.d/', 106577108100)],
             [('/0.d/05.d/', 113273338762)],
             [('/0.d/15.d/', 122711365675)],
             [('/0.d/*', 687973286945)]],
            [('/1.d/', 1020921564726),
             [('/1.d/00.d/', 125037824539)],
             [('/1.d/11.d/', 106972774810)],
             [('/1.d/13.d/', 115990023563)],
             [('/1.d/*', 672920941814)]],
            [('/*', 1937174334)]]
        self.assertEquals(self.tree_as_list(self.tree), expected)

    def test_leaf_size(self):
        self.assertEquals(self.fs.get_content_size('/0.d/05.d'), 113273338762)

    def test_sample_file(self):
        self.assertEquals(self.fs.stat('/1.d/13.d/15.txt').size, 22344)


class DuScanCopeWithDeletionTest(DuScanTestMixin, TestCase):
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


class DuScanNoLonelyStarTest(DuScanTestMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fs = GeneratedFilesystem(seed=6, maxdepth=4)
        cls.tree = cls.duscan_tree(cls.fs, '/')

    def test_leaves(self):
        expected = [
            ('/00.d/', 962283588169),
            ('/01.d/', 609253676265),
            ('/02.d/', 1154398475211),  # not "/02.d/*"
            ('/03.d/', 581440911832),
            ('/04.d/', 644318151446),
            ('/05.d/', 762422243930),
            ('/06.d/', 707913056679),
            ('/07.d/', 531731374526),
            ('/08.d/', 891915794716),
            ('/14.d/', 449450186015),
            ('/*', 1050999789708)]
        self.assertEquals(self.leaves_as_list(self.tree), expected)

    def test_tree(self):
        expected = [
            ('/', 8346127248497),
            [('/00.d/', 962283588169)],
            [('/01.d/', 609253676265)],
            [('/02.d/', 1154398475211)],
            [('/03.d/', 581440911832)],
            [('/04.d/', 644318151446)],
            [('/05.d/', 762422243930)],
            [('/06.d/', 707913056679)],
            [('/07.d/', 531731374526)],
            [('/08.d/', 891915794716)],
            [('/14.d/', 449450186015)],
            [('/*', 1050999789708)]]
        self.assertEquals(self.tree_as_list(self.tree), expected)


class DuScanNoSlashAndStarTest(DuScanTestMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fs = GeneratedFilesystem(seed=206, maxdepth=2)
        cls.tree = cls.duscan_tree(cls.fs, '/')

    def test_leaves(self):
        expected = [
            # not first a ('/', 54139),
            ('/00.txt', 55182),
            ('/01.txt', 63709),
            ('/03.txt', 42615),
            ('/04.txt', 48615),
            ('/05.txt', 44506),
            ('/07.txt', 44861),
            ('/11.txt', 45615),
            ('/14.txt', 53575),
            ('/17.txt', 49326),
            ('/18.txt', 53280),
            ('/20.txt', 65273),
            ('/23.txt', 45433),
            ('/*', 166955)]
        self.assertEquals(self.leaves_as_list(self.tree), expected)


class DuScanFindBadExamplesTest(DuScanTestMixin, TestCase):
    def is_flawed(self, dirs):
        lastdir = None
        for dir_ in dirs:
            if dir_.endswith('/'):
                lastdir = dir_
                continue
            if not lastdir or not dir_.startswith(lastdir):
                lastdir = None
                continue
            return True
        return False

    def test_is_not_flawed(self):
        good_example = (
            '/var/lib/apt/lists/somelist',
            '/var/lib/apt/lists/*',
            '/var/lib/mysql/ib_logfile0',
            '/var/lib/mysql/*',
            '/var/lib/smartmontools/',
            '/var/lib/*',
        )
        self.assertFalse(self.is_flawed(good_example))

    def test_is_flawed(self):
        bad_example = (
            'data/mysql/fri/',
            'data/mysql/mon/',  # this should not be here..
            'data/mysql/mon/export_statistieken.ibd.qp',
            'data/mysql/mon/log_vacaturegegevens.ibd.qp',
            'data/mysql/mon/*',
            'data/*',
        )
        self.assertTrue(self.is_flawed(bad_example))

    def test_find_something(self):
        if False:
            # depth=4: 57, 176
            # depth=3: 28, 57, 176, 206(!)
            for seed in range(1, 1000):
                print(seed)
                fs = GeneratedFilesystem(seed=seed, maxdepth=1)
                tree = self.duscan_tree(fs, '/')
                dirs = [dir_ for (dir_, size) in self.leaves_as_list(tree)]
                if self.is_flawed(dirs):
                    print(seed, dirs)
                    break


if __name__ == '__main__':
    main()
