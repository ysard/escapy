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
import configparser
from pathlib import Path

# Custom imports
import pytest

# Local imports
from escapy.printer_profile import (
    load_printer_profile,
    get_printer_profile,
    PrinterProfile,
)
from escapy.commons import EMBEDDED_CONFIG_FILE
from escapy.parser import ESCParser as _ESCParser
from .misc import pdf_comparison
from .misc import graphics_mode, esc_reset
from .misc import ESCParser, typefaces

raster_res_cmd = b"\x1b(D\x04\x00"
set_monochrome_cmd = b"\x1b(K\x02\x00\x00\x01"
set_monochrome_off_cmd = b"\x1b(K\x02\x00\x00\x02"
set_monochrom_default_cmd = b"\x1b(K\x02\x00\x00\x00"


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
    base_unit: int,
    hv_dividers: bytes,
    expected_resolutions: tuple[int | None, int | None],
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


@pytest.fixture()
def profile(request):
    """Fixture to parse config string and return an initialised PrinterProfile object

    :return: Printer profile built from the given configuration string
    :rtype: Generator[PrinterProfile]
    """
    config = configparser.ConfigParser()
    config.read_string(f"""
        [printer]
        profile = {request.param}
        """)

    load_printer_profile(config, EMBEDDED_CONFIG_FILE.parent)

    yield get_printer_profile(config)


@pytest.mark.parametrize(
    # Profile: Use the available profile to fix nozzle offsets & define colors.
    # Ink dots will be drawn as circles if True, or as rectangles otherwise.
    "profile, dots_as_circles, monochrome_mode, expected_filename",
    [
        # No nozzle fix, dots
        ("generic", True, b"", "test_transfer_raster_image_no_nozzle_fix.pdf"),
        # Ink dots will be drawn according to the physical positions of the nozzles
        # Nozzle fix, dots
        ("xp410", True, set_monochrome_off_cmd, "test_transfer_raster_image.pdf"),
        # Nozzle fix, rectangles
        (
            "xp410",
            False,
            set_monochrom_default_cmd,
            "test_transfer_raster_image_rectangles.pdf",
        ),
        # Monochrome on: all black, offset is 0 for this color in this mode
        # Thus, the result is similar to no nozzle fix, but all in black.
        (
            "xp410",
            True,
            set_monochrome_cmd,
            "test_transfer_raster_image_monochrome.pdf",
        ),
    ],
    ids=[
        "no_nozzle_offset_fix",
        "nozzle_offset_fix",
        "nozzle_offset_fix_rectangles",
        "nozzle_offset_fix_monochrome",
    ],
    indirect=["profile"],  # Send profile name to the fixture
)
def test_transfer_raster_image(
    tmp_path: Path,
    profile: PrinterProfile,
    dots_as_circles: bool,
    monochrome_mode: bytes,
    expected_filename: str,
):
    """Global test for a full pdf rendered with transfer raster image - ESC i

    Reminder of the structure of the header:

        r : color of ink
        c : compression method
        b : bit length required for each pixel of image data

    - With a bit length of 2, we need to send 8 bytes to get only 32 pixels
      (2 bits are used for a pixel).
    - With compression enabled, 0xFF is a counter used to repeat the next byte
      twice. So a compressed pattern of 8*0xFF gives the same byte array once
      decompressed.
    - If bit length is 1, with disabled compression, we need only 4 bytes
      for the same result (32 pixels).

    .. note:: The original program has been taken from xp410 doc; p24.
        Additional lines after E, has been added.
        To ensure accurate rendering, this code relies on a nozzle offset
        correction algorithm (default color mode).
    """
    code = [
        esc_reset,
        graphics_mode,
        monochrome_mode,
        # Set unit(1 / 180 inch)
        b"\x1b(U\x01\x00\x14",
        # Select dot size(variable1)
        b"\x1b(e\x02\x00\x00\x10",
        # Set resolution of Raster mode (180 x 360 DPI)
        b"\x1b(D\x04\x00\xA0\x05\x08\x04",
        # A: Black 1line (b11 large size dots)
        b"\x1bi\x00\x00\x02" + b"\x08\x00\x01\x00" + b"\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF",
        b"\x0d",
        # relative vertical print position (1/180 inch)
        b"\x1b(v\x02\x00\x01\x00",
        # B: Cyan 1line
        b"\x1bi\x02\x00\x02" + b"\x08\x00\x01\x00" + b"\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF",
        b"\x0d",
        # relative vertical print position(1 / 180 inch)
        b"\x1b(v\x02\x00\x01\x00",
        # C: Magenta 1line
        b"\x1bi\x01\x00\x02" + b"\x08\x00\x01\x00" + b"\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF",
        b"\x0d",
        # relative vertical print position (1/180 inch)
        b"\x1b(v\x02\x00\x01\x00",
        # D: Yellow 1line
        b"\x1bi\x04\x00\x02" + b"\x08\x00\x01\x00" + b"\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF",
        b"\x0d",
        # relative vertical print position (1/180 inch)
        b"\x1b(v\x02\x00\x01\x00",
        # E: Black 1line, compression  (b10 medium size dots)
        b"\x1bi\x00\x01\x02" + b"\x08\x00\x01\x00" + b"\xFF\xaa\xFF\xaa\xFF\xaa\xFF\xaa",
        b"\x0d",
        # relative vertical print position (1/180 inch)
        b"\x1b(v\x02\x00\x01\x00",
        # F: Black 1line, compression  (b01 small dots)
        b"\x1bi\x00\x01\x02" + b"\x08\x00\x01\x00" + b"\xFF\x55\xFF\x55\xFF\x55\xFF\x55",
        b"\x0d",
        # relative vertical print position (1/180 inch)
        b"\x1b(v\x02\x00\x01\x00",
        # G: Black 1line, compression
        # (b00 no dot, then b01 1 small dot each last 2 bytes (repeated twice))
        b"\x1bi\x00\x01\x02" + b"\x08\x00\x01\x00" + b"\xFF\x00\xFF\x00\xFF\x00\xFF\x01",
        b"\x0d",
        # relative vertical print position (1/180 inch)
        b"\x1b(v\x02\x00\x01\x00",
        # H: Black 1line (1 bit length : not dot size control, normal raster print)
        # Send 4 bytes then white pixels to keep the same pattern since all
        # bits in all bytes sent are used.
        b"\x1bi\x00\x00\x01" + b"\x08\x00\x01\x00" + b"\xFF\xFF\xFF\xFF\x00\x00\x00\x00",
        b"\x0d",
        # relative vertical print position (1/180 inch)
        b"\x1b(v\x02\x00\x01\x00",
        # paper eject
        b"\x0c",
        esc_reset,
    ]

    print(profile)

    processed_file = tmp_path / expected_filename

    # Inject test typefaces & printer profile
    _ESCParser(
        b"".join(code),
        printer_profile=profile,
        dots_as_circles=dots_as_circles,
        output_file=processed_file,
        available_fonts=typefaces,
    )

    pdf_comparison(processed_file)
