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
"""Test commands involved in graphics printing.

Tested mode:

- ESC i; Transfer raster image
"""

# Standard imports
from pathlib import Path
from functools import partial
import pytest

# Local imports
from escapy.parser import ESCParser as _ESCParser
from .misc import pdf_comparison
from .misc import graphics_mode, esc_reset, typefaces

# Inject test typefaces
ESCParser = partial(_ESCParser, available_fonts=typefaces)

raster_res_cmd = b"\x1b(D\x04\x00"


@pytest.mark.parametrize(
    "base_unit, hv_dividers, expected_resolutions",
    [
        # 1/720, 1/360, vertical, horizontal
        (720, b"\x01\x02", (1 / 720, 1 / 360)),
        # 1/666, 2/666, vertical, horizontal, (not allowed): default values
        (666, b"\x01\x02", (None, None)),
        # 1/720, 1/1080, vertical, horizontal (not allowed): default values
        (720, b"\x01\x03", (None, None)),
    ],
    ids=[
        "720_360dpi",
        "666_333dpi_refused",
        "666_333dpi_refused",
    ],
)
def test_set_raster_resolution(
    base_unit: int, hv_dividers: bytes, expected_resolutions
):
    """Test ESC ( D vertical & horizontal resolutions

    .. seealso:: For ESC . (raster image) related resolutions, see
        :meth:`.test_graphic_commands.test_raster_graphics_resolutions`.
    """
    expected_v_res, expected_h_res = expected_resolutions

    # The resolutions are send BEFORE any graphic data command, but in graphics mode
    code = raster_res_cmd + int(base_unit).to_bytes(2, byteorder="little") + hv_dividers

    escapy = ESCParser(esc_reset + code, pdf=False)
    assert escapy.vertical_resolution == expected_v_res
    assert escapy.horizontal_resolution == expected_h_res
