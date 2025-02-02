#  ESCParser is a software allowing to convert EPSON ESC/P, ESC/P2
#  printer control language files into PDF files.
#  Copyright (C) 2024-2025  Ysard
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
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""Grammar tests"""
# Standard imports
from functools import partial

# Custom imports
import pytest
from lark import UnexpectedToken

# Local imports
from escapy.parser import ESCParser as _ESCParser
from .misc import typefaces

# Inject test typefaces
ESCParser = partial(_ESCParser, available_fonts=typefaces)


@pytest.fixture()
def not_expected_param() -> bytes:
    """Generate a malformed raster graphic command

        c  v  h  m  nL nH d1 d2 . . . dk
        01 14 14 30 A0 01 81 00

    m: 0x30 = 48: not allowed for the vertical dot count (1, 8, 24 only).

    This data should generate an `UnexpectedToken` error.

    :return: Malformed raster graphic command.
    """

    graphics_mode = b"\x1B(G\x01\x00\x01"
    line_spacing = b"\x1B+\x30"  # 48/360 inch
    raster_data = b"\x1B.\x01\x14\x14\x30\xA0\x01\x81\x00"

    return graphics_mode + line_spacing + raster_data


def test_exception_handling(not_expected_param):
    """Test file badly constructed or with unknown ESC command"""

    with pytest.raises(UnexpectedToken):
        _ = ESCParser(not_expected_param, pdf=False)
