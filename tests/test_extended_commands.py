#  ESCParser is a software allowing to convert EPSON ESC/P, ESC/P2
#  printer control language files into PDF files.
#  Copyright (C) 2024-2026  Ysard
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.*
"""Test extended commands, not tested elsewhere"""

# Custom imports
import pytest

# Local imports
from escapy.parser import EscpCompatibility
from .misc import ESCParser
from .test_graphic_transfer_raster_image import raster_res_cmd, set_monochrome_cmd


def test_set_dot_size():
    """Test dot size"""
    dataset = [
        # dot size unexpected, set default 0x00
        (b"\x1b(e\x02\x00\x00\x20", 0x00),
        # VSD3
        (b"\x1b(e\x02\x00\x00\x13", 0x13),
    ]

    for code, expected_value in dataset:
        escapy = ESCParser(code, pdf=False)
        assert escapy.dot_size == expected_value


@pytest.mark.parametrize(
    "command",
    [
        # exit packet
        b"\x00\x00\x00\x1b\x01@EJL 1284.4\n@EJL     \n",
        raster_res_cmd + b"\xd0\x02" + b"\x01\x02",
        set_monochrome_cmd,
    ],
    ids=[] * 3,
)
def test_compatibility_mode(command: bytes):
    """Test commands that should trigger STRICT_MODERN compatibility"""
    escapy = ESCParser(command, pdf=False)
    assert escapy.compatibility_mode == EscpCompatibility.STRICT_MODERN
