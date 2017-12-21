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
#
# Usage:
#
#     from dutree import Scanner
#     scanner = Scanner('/srv')
#     tree = scanner.scan()
#     print(tree.size())
#
from dutree import DuScan as Scanner

__all__ = ('Scanner',)
