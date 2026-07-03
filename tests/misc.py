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
"""Common variables, commands, fixtures & functions used in tests"""
# Standard imports
import os
from pathlib import Path
from functools import partial

# Custom imports
import pytest
from reportlab.lib.colors import PCMYKColorSep

# Local imports
from escapy.parser import ESCParser as _ESCParser
from escapy.fonts import find_font
from escapy.printer_profile import PrinterProfile
from .helpers.diff_pdf import is_similar_pdfs

# Test data path depends on the current package name
DIR_DATA = os.path.dirname(os.path.abspath(__file__)) + "/../test_data/"

esc_reset = b"\x1B\x40"  # ESC @
cancel_bold = b"\x1BF"  # ESC F
graphics_mode = b"\x1B(G\x01\x00\x01"  # ESC ( G
select_10cpi = b"\x1bP"  # ESC P
select_12cpi = b"\x1bM"  # ESC M
select_15cpi = b"\x1bg"  # ESC g
double_width = b"\x0e"  # SO
reset_double_width = b"\x14"  # DC4
double_width_m = b"\x1BW\x01"  # ESC W 1
reset_double_width_m = b"\x1bW\x00"  # ESC W 0
select_condensed_printing = b"\x0f"  # SI
unset_condensed_printing = b"\x12"  # DC2
double_height = b"\x1Bw\x01"  # ESC w 1
reset_double_height = b"\x1Bw\x00"  # ESC w 0


typefaces = {
    # FiraCode: doesn't support all languages
    0: {
        "fixed": partial(
            find_font, "FiraCode", path="/usr/share/fonts/truetype/firacode/"
        ),
        "proportional": lambda *_: None,
    },
    # Sans serif => Fixedsys Excelsior
    1: {
        "fixed": partial(find_font, "FSEX302-alt", path="./resources/"),
        "proportional": lambda *_: None,
    },
    2: {
        "fixed": partial(
            find_font, "Courier_New", path="/usr/share/fonts/truetype/msttcorefonts/"
        ),
        "proportional": lambda *_: None,
    },
    3: {
        "fixed": partial(find_font, "prestigenormal", path="./resources/"),
        "proportional": lambda *_: None,
    },
    5: {
        "fixed": partial(find_font, "ocr-b-regular", path="./resources/"),
        "proportional": lambda *_: None,
    },
    6: {
        "fixed": partial(find_font, "ocra", path="./resources/"),
        "proportional": lambda *_: None,
    },
    7: {
        "fixed": partial(find_font, "orator", path="./resources/"),
        "proportional": lambda *_: None,
    },
    9: {
        "fixed": partial(find_font, "scriptc", path="./resources/"),
        "proportional": lambda *_: None,
    },
    10: {
        "fixed": partial(find_font, "romant", path="./resources/"),
        "proportional": lambda *_: None,
    },
}


# Extra fonts ready to be inserted in typefaces at any slot
noto_font_def = {
    # Noto should allow all languages but the base name should be adapted.
    # Ex: NotoSansThai-*
    "fixed": partial(
        find_font, "NotoSansMono", path="/usr/share/fonts/truetype/noto/"
    ),
    "proportional": partial(
        find_font, "NotoSans-", path="/usr/share/fonts/truetype/noto/"
    ),
}

noto_devanagari_font_def = {
    "fixed": partial(
        find_font, "NotoSansDevanagari-", path="/usr/share/fonts/truetype/noto/"
    ),
    "proportional": lambda *_: None,
}

liberation_font_def = {
    "fixed": partial(
        find_font, "LiberationMono", path="/usr/share/fonts/truetype/liberation/"
    ),
    "proportional": partial(
        find_font, "LiberationSans", path="/usr/share/fonts/truetype/liberation/"
    ),
}

default_printer_profile = PrinterProfile(
    name='generic',
    color_names={
        0: 'Black',
        1: 'Magenta',
        2: 'Cyan',
        4: 'Yellow',
        5: 'Red',
        6: 'Green',
        17: 'Light Magenta',
        18: 'Light Cyan',
    },
    RGB_colors={
        0: '#000000',
        1: '#ff00ff',
        2: '#00ffff',
        4: '#ffff00',
        5: '#ff0000',
        6: '#00ff00',
        17: '#ff80ff',
        18: '#80ffff',
    },
    CMYK_colors={
        0: PCMYKColorSep(0,0,0,100,spotName='BLACK'),
        1: PCMYKColorSep(0,100,0,0,spotName='MAGENTA'),
        2: PCMYKColorSep(100,0,0,0,spotName='CYAN'),
        4: PCMYKColorSep(0,0,100,0,spotName='YELLOW'),
        5: PCMYKColorSep(0,100,100,0,spotName='RED'),
        6: PCMYKColorSep(100,0,100,0,spotName='GREEN'),
        17: PCMYKColorSep(0,50,0,0,spotName='LIGHT MAGENTA'),
        18: PCMYKColorSep(50,0,0,0,spotName='LIGHT CYAN')},
    nozzle_offsets={0: 0.0, 1: 0.0, 2: 0.0, 4: 0.0, 5: 0.0, 6: 0.0, 17: 0.0, 18: 0.0},
    nozzle_offsets_monochrome={0: 0.0, 1: 0.0, 2: 0.0, 4: 0.0, 5: 0.0, 6: 0.0, 17: 0.0, 18: 0.0},
)

# Inject test typefaces & printer profile
ESCParser = partial(_ESCParser, printer_profile=default_printer_profile, available_fonts=typefaces)


@pytest.fixture
def format_databytes(request):
    """
    :param request: In the param attr: bytes | bytearray
    :type request: pytest._pytest.fixtures.SubRequest
    """
    databytes = esc_reset + request.param
    return databytes


def pdf_comparison(processed_file: Path, test_id: str = ""):
    """Wrapper to compare two PDFs files

    In case of error, the wrong pdf and the diff file will be copied in /tmp/.

    :param processed_file: Test file Path object. Its name is used to make
        the comparison with an expected file with the same name, expected in
        the test_data directory.
    :key test_id: Current test id used to get the reference file from the
        processed file name.
        This prevents unwanted override accross tests (at least in the same
        parametrized test).
    """
    # Keep track of the generated file in /tmp in case of error
    if test_id:
        reference_file = Path(DIR_DATA) / processed_file.name.replace(test_id, "")
    else:
        reference_file = Path(DIR_DATA) / processed_file.name

    ret = is_similar_pdfs(reference_file, processed_file)
    if not ret:
        backup_file = Path("/tmp") / processed_file.name
        backup_file.write_bytes(processed_file.read_bytes())

    assert ret, f"Problematic file is saved at <{backup_file}> for further study."
