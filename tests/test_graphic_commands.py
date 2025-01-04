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
"""Test commands involved in graphics printing.

Tested modes:

- Bit-image
- ESC . 0; Raster no compression
- ESC . 1; Raster TIFF/RLE compression
- ESC . 2; Raster TIFF
"""
# Standard imports
import struct
from pathlib import Path
from unittest.mock import patch
from functools import partial

# Custom imports
import pytest
from lark.exceptions import UnexpectedToken

# Local imports
from escparser.parser import ESCParser as _ESCParser
from .misc import format_databytes, pdf_comparison
from .misc import esc_reset, cancel_bold, graphics_mode, typefaces

# Inject test typefaces
ESCParser = partial(_ESCParser, available_fonts=typefaces)


DECOMPRESSED_DATA = [
    60, 90, 30, 128, 37, 79, 42, 15, 53, 14, 99, 155, 155, 63, 97, 22, 0, 0,
    0, 0, 60, 15, 15, 15, 15, 15, 128, 32, 9, 27, 34, 173, 91, 92, 8, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 37, 14, 16, 88, 103, 77, 61, 13, 25, 155,
    155, 63, 97, 22, 31, 97, 44, 110, 109, 15, 15, 15, 15, 15, 0
]

COMPRESSED_DATA = [
    15, 60, 90, 30, 128, 37, 79, 42, 15, 53, 14, 99, 155, 155, 63, 97, 22, -3,
    0, 0, 60, -4, 15, 8, 128, 32, 9, 27, 34, 173, 91, 92, 8, -11, 0, 18, 37,
    14, 16, 88, 103, 77, 61, 13, 25, 155, 155, 63, 97, 22, 31, 97, 44, 110,
    109, -4, 15, 0, 0
]

DECOMPRESSED_DATA = bytearray(
    b"".join([struct.pack(">B", i) for i in DECOMPRESSED_DATA])
)
# Pay attention to convert negative counters into signed bytes
COMPRESSED_DATA = bytearray(
    b"".join(
        [
            struct.pack(">b", i) if i < 0 else struct.pack(">B", i)
            for i in COMPRESSED_DATA
        ]
    )
)


@pytest.mark.parametrize(
    "format_databytes",
    [
        # 0x4f (79) is not an authorized value
        b"\x1b?K\x4f" + cancel_bold,
        # unknown_color_cmd ESC r
        b"\x1br\x20",
        # ESC . 2 with a value in vertical dot (v_dot_count_m) which is not 1
        b"\x1b.\x02\x14\x14\x03\x00\x00",
        # Color 5 is not allowed in TIFF ESC . 2 mode
        b"\x1b.\x02\x14\x14\x03\x00\x00\x85",
    ],
    # First param goes in the 'databytes' param of the fixture format_databytes
    indirect=["format_databytes"],
    ids=[
        "reassign_bit_image_wrong_density",
        "unknown_color",
        "tiff_wrong_v_dot_count_m",
        "tiff_color_not_allowed",
    ],
)
def test_wrong_commands(format_databytes: bytes):
    """Test various commands with wrong parameters that will raise a Lark exception"""
    with pytest.raises(UnexpectedToken, match=r"Unexpected token Token.*"):
        _ = ESCParser(format_databytes)


# Bit-image graphics ###########################################################


def test_reassign_bit_image_mode():
    """Test reassign bit-image - ESC ?

    Test values: m = 0, 1, 2, 3, 4, 6, 32, 33, 38, 39, 40, 71, 72, 73

    Values sent should be received in klyz_densities attribute.
    """
    cmd_letters = b"KLYZ"
    dot_density_m = [0, 4, 7, 73]

    code = b"\x1b?".join(
        bytearray(cmd_density) for cmd_density in zip(cmd_letters, dot_density_m)
    )

    escparser = ESCParser(esc_reset + code)

    assert escparser.klyz_densities == dot_density_m


@pytest.mark.parametrize(
    # The dot density setting impacts horizontal & vertical resolutions,
    # bytes per column and double speed mode.
    # The number of pins can modify vertical resolution
    "format_databytes, pins, dot_density, hori, verti, bytes_per_column, double_speed",
    [
        # ESC K: cancel_bold belongs to the command, it is used to test the parsing
        (b"\x1bK\x04\x00\xff\x0a" + cancel_bold, 9, 0, 1 / 60, 1 / 72, 1, False),
        (b"\x1bK\x04\x00\xff\x0a" + cancel_bold, None, 0, 1 / 60, 1 / 60, 1, False),
        # Set dot_density to 7 via ESC ? K command, before ESC K command (cf configure_bit_image)
        (b"\x1b?K\x07\x1bK\x04\x00\xff\x0a" + cancel_bold, 9, 7, 1 / 144, 1 / 72, 1, False),
        # 40, 72 densities also, double_speed is enabled for these modes
        (b"\x1b?K\x28\x1bK\x04\x00\xff\x0a" + cancel_bold, None, 40, 1 / 360, 1 / 180, 3, True),
        (b"\x1b?K\x48\x1bK\x04\x00\xff\x0a" + cancel_bold, None, 72, 1 / 360, 1 / 360, 6, True),
    ],
    # First param goes in the 'request' param of the fixture format_databytes
    indirect=["format_databytes"],
    ids=[
        "select_xdpi_graphics_K",
        "select_xdpi_graphics_K_9pins",
        "reassign_bit_image_mode_dot7+select_xdpi_graphics_K_9pins",
        "reassign_bit_image_mode_dot40+select_xdpi_graphics_K_9pins",
        "reassign_bit_image_mode_dot72+select_xdpi_graphics_K_9pins",
    ],
)
def test_select_graphics(
    format_databytes: bytes,
    pins: int | None,
    dot_density: int,
    hori: float,
    verti: float,
    bytes_per_column: int,
    double_speed: bool,
):
    """Test select_xdpi_graphics (ESC K, L, Y, Z) & configure_bit_image function

    The tests use K command, thus, position 0 in klz_densities is updated.
    """
    escparser = ESCParser(format_databytes, pins=pins, pdf=False)

    assert escparser.klyz_densities[0] == dot_density
    assert escparser.horizontal_resolution == hori
    assert escparser.vertical_resolution == verti
    assert escparser.bytes_per_column == bytes_per_column
    assert escparser.double_speed == double_speed


def test_select_bit_image_9pins(tmp_path: Path):
    """Test print dot-graphics in 9-dot columns - ESC ^

    Similar to the other bit-image modes.

    In the test toy example, a 9th dot is set for all columns.
    See implementation details especially about the masked last byte.
    """
    select_9pins_graphics_cmd = b"\x1b^"
    dot_density_m_0 = b"\x00"
    expect_88_columns = b"\x58\x00"
    # Toy data used in test_select_bit_image
    data_44_columns = b"\x00\x00\x7f\x7f@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00"

    # Double the bytes for each column, with a MSB set on this new byte.
    # Yeah, it's ugly, but bytes-like object join's argument doesn't accept
    # an iterable of ints. Iterating over bytes-like objects returns ints.
    # https://bugs.python.org/issue24892
    # /!\ We add a full last byte at the end, this byte (like any other 2nd byte)
    # should be masked with 0x80, so, just the 1st bit is kept.
    data_88_columns = b"\x80".join(data_44_columns[i:i + 1] for i in range(len(data_44_columns))) + b"\xff"

    m0_line = select_9pins_graphics_cmd + dot_density_m_0 + expect_88_columns + data_88_columns

    processed_file = tmp_path / "test_select_bit_image_9pins.pdf"
    escparser = ESCParser(m0_line, pins=9, output_file=processed_file)
    assert escparser.horizontal_resolution == 1 / 60
    assert escparser.vertical_resolution == 1 / 72  # We are in 9 pins mode
    assert escparser.bytes_per_column == 2

    pdf_comparison(processed_file)


def test_select_bit_image(tmp_path: Path):
    """Test select_bit_image ESC *

    Show different representation of a form like the ⌐ (reversed not sign)

    About the dot densities used (ESCP2):

        - 1: h x v:  1/120 x 1/60, 1 byte per column, double speed off
        - 2: h x v:  1/120 x 1/60, 1 byte per column, double speed on

    What is printed here:

        - Normal line
        - double speed line
        - Line in magenta, yellow, cyan patterns
        - Line in red (from RGB, not allowed in raster graphics mode,
          BUT here we are in bit-image mode!)
        - Line in red (from CMYK combination)
        - Line in green (from CMYK combination)
        - Line in blue (from CMYK combination)

    """
    select_bit_image_cmd = b"\x1b*"
    dot_density_m_1 = b"\x01"
    dot_density_m_2 = b"\x02"
    expect_44_columns = b"\x2c\x00"
    data_44_columns = b"\x00\x00\x7f\x7f@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00"
    magenta_cmd = b"\x1br\x01"
    cyan_cmd = b"\x1br\x02"
    yellow_cmd = b"\x1br\x04"
    red_cmd = b"\x1br\x05"
    # unknown_color_cmd = b"\x1br\x20"

    m2_line = select_bit_image_cmd + dot_density_m_2 + expect_44_columns + data_44_columns

    lines = [
        # Look the two \x7f values, they are 2 bytes for 2 successive columns
        # Disabling adjacent dots should not print the second one
        # (like if the bytes were \x7f\x00)
        select_bit_image_cmd,
        # dot density 1: adjacent dots are ENABLED
        dot_density_m_1 + expect_44_columns,
        data_44_columns,
        b"\r\n",
        select_bit_image_cmd,
        # dot density 2: adjacent dots are DISABLED
        dot_density_m_2 + expect_44_columns,
        data_44_columns,
        b"\r\n",

        # Color in magenta
        magenta_cmd + m2_line,

        # Color in yellow
        yellow_cmd + m2_line,

        # Color in cyan
        cyan_cmd + m2_line,

        # Color in red is allowed here (bit-image mode)
        red_cmd + m2_line,

        # Color in unknown value (should not change the current color)
        # NOTE: For now, it's captured by the grammar
        # unknown_color_cmd + m2_line,

        b"\r\n",
        # Combinations
        # Color in red: merge magenta + yellow
        yellow_cmd + m2_line,
        b"\r",  # print at the same start position (just do a carriage return)
        magenta_cmd + m2_line,
        b"\r\n",

        # Color in green: merge cyan + yellow
        cyan_cmd + m2_line,
        b"\r",  # print at the same start position (just do a carriage return)
        yellow_cmd + m2_line,
        b"\r\n",

        # Color in blue: merge cyan + magenta
        cyan_cmd + m2_line,
        b"\r",  # print at the same start position (just do a carriage return)
        magenta_cmd + m2_line,
        b"\r\n",
    ]

    code = b"".join(lines)

    processed_file = tmp_path / "test_bitimage_doublespeed_and_colors.pdf"
    escparser = ESCParser(code, output_file=processed_file)

    assert escparser.horizontal_resolution == 1 / 120
    assert escparser.vertical_resolution == 1 / 60
    assert escparser.bytes_per_column == 1
    assert escparser.double_speed is True  # m2 effect

    pdf_comparison(processed_file)


# Raster graphics ##############################################################


def test_rle_decompress():
    """Test TIFF/RLE decompression

    Data examples from the doc p313.
    """
    expected_decompressed_data = DECOMPRESSED_DATA

    found = _ESCParser.decompress_rle_data(COMPRESSED_DATA)

    assert found == expected_decompressed_data


def get_raster_data_code(rle_compressed=False):
    """Generate raster data in graphics mode according to the compression level

    ESC ( G + ESC . 0 or ESC ( G + ESC . 1
    """
    raster_graphics = b"\x1b.\x00"
    raster_graphics_rle = b"\x1b.\x01"
    v_res_h_res = b"\x14\x14"  # 180 dpi
    v_dot_count_m = b"\x08"  # height of the band: 8 dots (8 lines)
    # nL, hH: Horizontal resolution: 9 bytes of 8 dots = 72 dots
    # PS: length of decompressed data: vertical * horizontal = 9 bytes * 8 lines
    #   72 bytes (vs 59 compressed)
    h_dot_count = b"\x48\x00"

    code = [
        graphics_mode,
        raster_graphics_rle if rle_compressed else raster_graphics,
        v_res_h_res + v_dot_count_m + h_dot_count,
        COMPRESSED_DATA if rle_compressed else DECOMPRESSED_DATA,
    ]
    return b"".join(code)


def get_raster_data_3bytes(microweave: bool = False):
    """Generate decompressed raster data in graphics mode mapped on 24 dots vertical size

    ESC ( G + ESC . 0

    :key microweave: If True, add the Microweave enable command after entering
        in graphics mode.
        In this case, the program should log a warning: the vertical resolution
        should be 1, not 8 or 24. But we assume that the data is formatted for
        the given resolution, and since Microweave technology has no impact on
        operation, we let the printing process take its course.
    """
    raster_graphics = b"\x1b.\x00"
    v_res_h_res = b"\x14\x14"  # 180 dpi
    v_dot_count_m = (24).to_bytes()  # height of the band: 24 dots (24 lines)
    # Triple the data (Add blank lines at the end of the original data)
    # nL, hH: Horizontal resolution: 9 bytes of 8 dots = 72 dots
    # PS: length of decompressed data: vertical * horizontal = 9 bytes * 24 lines
    #   216 bytes
    decompressed_data = DECOMPRESSED_DATA + bytes(2 * len(DECOMPRESSED_DATA))
    assert len(decompressed_data) == v_dot_count_m[0] * 9
    h_dot_count = struct.pack("<h", 9 * 8)

    enable_microweave_cmd = b"\x1b(i\x01\x001"

    code = [
        graphics_mode,
        enable_microweave_cmd if microweave else b"",
        raster_graphics,
        v_res_h_res + v_dot_count_m + h_dot_count,
        decompressed_data,
    ]
    return b"".join(code)


def get_raster_data_1dot():
    """Generate decompressed raster data in graphics mode mapped on 1 dot vertical size

    Send 8 lines with a vertical dot count of 1 dot; So, 8 lines of 9 bytes.
    But with separated commands, and a line feed between them.
    Note that the linespacing must be adjusted according to the choosen resolution.

    ESC ( G + ESC . 0
    """
    raster_graphics = b"\x1b.\x00"
    v_res_h_res = b"\x14\x14"  # 180 dpi
    v_dot_count_m = b"\x01"  # height of the band: 1 dot (1 line)
    # nL, hH: Horizontal resolution: 9 bytes of 8 dots = 72 dots
    # PS: length of decompressed data: vertical * horizontal = 9 bytes * 8 lines
    #   72 bytes
    h_dot_count = b"\x48\x00"

    line_spacing_180dpi = b"\x1b3\x01"

    code = line_spacing_180dpi + graphics_mode

    for idx in range(0, 9 * 8, 9):
        chunk = DECOMPRESSED_DATA[idx : idx + 9]
        code += (
            raster_graphics + v_res_h_res + v_dot_count_m + h_dot_count + chunk + b"\n"
        )
    return code


@pytest.mark.parametrize(
    "format_databytes",
    [
        # No RLE
        get_raster_data_code(),
        # RLE
        get_raster_data_code(rle_compressed=True),
        # Try to use color other than CMYK inside graphics mode
        # => The color should not be used
        graphics_mode + b"\x1br\x05" + get_raster_data_code(),
        # No RLE, height band of 24 dots (24 lines)
        get_raster_data_3bytes(),
        # No RLE, height band of 1 dot (8 separated commands)
        get_raster_data_1dot(),
        # No RLE microweave enabled for a height band of 24
        # => see the docstring for more info
        get_raster_data_3bytes(microweave=True),
    ],
    # First param goes in the 'databytes' param of the fixture format_databytes
    indirect=["format_databytes"],
    ids=[
        "no_rle",
        "rle",
        "no_rle_not_allowed_color_change",
        "24dots_v_band",
        "1dot_v_band",
        "24dots_v_band_microweave",
    ],
)
def test_print_raster_graphics(format_databytes: bytes, tmp_path: Path):
    """Test raster graphics 0 and 1 modes (no compress, RLE compress modes)

    Cover ESC . 0, ESC . 1 commands

    Data examples from the doc p313.
    """
    processed_file = tmp_path / "test_raster_graphics_compress_no_and_rle.pdf"
    escparser = ESCParser(format_databytes, output_file=processed_file)

    assert escparser.horizontal_resolution == 1 / 180
    assert escparser.vertical_resolution == 1 / 180
    assert escparser.bytes_per_line == int((72 + 7) / 8)
    assert escparser.double_speed is False

    pdf_comparison(processed_file)


def test_switch_microweave_mode():
    """Test MicroWeave print mode - ESC ( i"""
    dataset = [
        (b"\x1b(i\x01\x00\x00", False),
        (b"\x1b(i\x01\x00\x30", False),
        (b"\x1b(i\x01\x00\x01", True),
        (b"\x1b(i\x01\x00\x31", True),
        # Default
        (b"", False),
        # Canceled by ESC @
        (b"\x1b(i\x01\x00\x31" + b"\x1b@", False),
    ]
    for code, expected in dataset:
        escparser = ESCParser(esc_reset + code, pdf=False)
        assert escparser.microweave_mode == expected


def test_print_tiff_raster_graphics(tmp_path: Path):
    """Test TIFF raster graphics (mainly <XFER>)

    Cover ESC . 2, <MOVY>, full <XFER> command (nibble combinations), <EXIT>.

    Print 3 lines of 10*8 dots (10 bytes) with various <XFER> configurations.
    """
    raster_graphics_tiff = b"\x1b.\x02"
    v_res_h_res = b"\x14\x14"  # 180 dpi
    # HERE I CAN NOT put 2 instead of 1, this value is nonsense in TIFF mode;
    # It SHOULD be fixed automatically and set to 1.
    # THIS code section CAN'T be tested since the grammar doesn't accept such value.
    v_dot_count_m = b"\x01"  # nL, hH: height of the band: 1 dot
    trailing_bytes = b"\x00\x00"

    expected_bytes_count = 10
    # Move 10 units down used as a linefeed between the dot lines
    movy_cmd = b"r\n\x00"
    # Count is inside the nibble of cmd
    # 0b0010_0000 (0x20) + 10 bytes = 0b0010_1010
    xfer_cmd_f0_bc10 = b"*"
    # Count is inside the next byte nL
    # 0b0011_0000 (0x30) + 1 = 0b0010_0001
    xfer_cmd_f1_bc1 = b"1\x0a"
    # Count is inside the 2 next bytes
    # 0b0011_0000 (0x30) + 2 = 0b0010_0010
    xfer_cmd_f1_bc2 = b"2\x0a\x00"
    raster_data = b"\xff" * expected_bytes_count

    exit_cmd = b"\xe3"

    code = [
        graphics_mode,
        raster_graphics_tiff,
        v_res_h_res + v_dot_count_m + trailing_bytes,

        # 3 lines
        xfer_cmd_f0_bc10 + raster_data,
        movy_cmd,
        xfer_cmd_f1_bc1 + raster_data,
        movy_cmd,
        xfer_cmd_f1_bc2 + raster_data,

        exit_cmd,
    ]

    processed_file = tmp_path / "test_print_tiff_raster_graphics.pdf"
    escparser = ESCParser(b"".join(code), output_file=processed_file)

    assert escparser.horizontal_resolution == 1 / 180
    assert escparser.vertical_resolution == 1 / 180
    assert escparser.bytes_per_line == expected_bytes_count

    pdf_comparison(processed_file)


@pytest.mark.parametrize(
    "binary_cmd, set_unit_cmd, expected_unit",
    [
        # default unit from constructor
        (b"", b"", 1 / 360),
        # movxbyte_cmd: default
        (b"\xe4", b"", 8 / 360),
        # movxdot_cmd: default:
        (b"\xe5", b"", 1 / 360),
        # Redefine unit before binary commands to 60 (0x3c) / 3600 via ESC ( U
        (b"\xe4", b"\x1b(U\x01\x00\x3c", 6 * 8 / 360),
        (b"\xe5", b"\x1b(U\x01\x00\x3c", 6 / 360),
    ],
    ids=[
        "unit_default",
        "unit_movxbyte_default",
        "unit_movxdot_default",
        "unit_movxbyte_6/360",
        "unit_movxdot_6/360",
    ],
)
def test_set_movx_unit_functions(
    binary_cmd: bytes, set_unit_cmd: bytes, expected_unit: float
):
    """Test TIFF mode <MOV*> units

    Cover:

        - set_unit ESC ( U
        - set_movx_unit_8dots <MOVXBYTE>
        - set_movx_unit_1dot <MOVXDOT>
        - set_movx_unit
    """
    raster_graphics_tiff = b"\x1b.\x02"
    v_res_h_res = b"\x14\x14"  # 180 dpi
    v_dot_count_m = b"\x01"  # nL, hH: height of the band: 1 dot
    trailing_bytes = b"\x00\x00"

    exit_cmd = b"\xe3"

    code = [
        graphics_mode,

        # ESC ( U must be used before entering into the TIFF binary mode
        set_unit_cmd,

        raster_graphics_tiff,
        v_res_h_res + v_dot_count_m + trailing_bytes,

        binary_cmd,

        exit_cmd,
    ]
    escparser = ESCParser(b"".join(code), pdf=False)
    assert escparser.movx_unit == expected_unit


@pytest.mark.parametrize(
    "movx_cmd, movy_cmd, offset_cursor_x, offset_cursor_y",
    [
        # Offset is inside the SIGNED nibble of cmd
        # 0b0100_0000 (0x20) -8 = 0b0100_1000
        (b"\x48", b"", -8 * 1 / 360, 0),
        # Offset is inside the SIGNED nibble of cmd
        # 0b0100_0000 (0x20)  7 = 0b0100_0111
        (b"\x47", b"", 7 / 360, 0),
        # Offset is inside the next SIGNED byte nL
        # 0b0101_0001 (0x51)
        (b"\x51\xf8", b"", -8 / 360, 0),
        # Offset is inside the next SIGNED byte nL
        # 0b0101_0001 (0x51)
        (b"\x51\x07", b"", 7 / 360, 0),
        # Offset is inside the 2 next SIGNED short
        # 0b0101_0010 (0x52)
        (b"\x52\xf8\xff", b"", -8 / 360, 0),
        # Offset is inside the 2 next SIGNED short
        # 0b0101_0010 (0x52)
        (b"\x52\x07\x00", b"", 7 / 360, 0),
        ##
        # Offset is inside the UNSIGNED nibble of cmd
        # 0b0110_0000 (0x60) + 15 (0x0f)
        # -15 because the system is bottom up
        # (positive movement is towards the bottom of the page: so coordinates decrease)
        (b"", b"\x6f", 0, -15 / 360),
        # Offset is inside the next UNSIGNED byte nL
        # 0b0111_0001 ()
        (b"", b"\x71\x0f", 0, -15 / 360),
        # Offset is inside the 2 next bytes: next UNSIGNED short
        # 0b0111_0010 ()
        (b"", b"\x72\x0f\x00", 0, -15 / 360),
        ##
        # Using the movy command triggers a carriage return
        # => cancel the cursor_x movement of movx
        (b"\x47", b"\x6f", 0, -15 / 360),
    ],
    ids=[
        "movx_f0_negative_offset",
        "movx_f0_positive_offset",
        "movx_f1_bc1_negative_offset",
        "movx_f1_bc1_positive_offset",
        "movx_f1_bc2_negative_offset",
        "movx_f1_bc2_positive_offset",
        "movy_f0",
        "movy_f1_bc1",
        "movy_f1_bc2",
        "movx_f0_positive_offset+movy_f0",
    ],
)
# We want to measure influence on x & y cursors
# Cancel the carriage return due to <EXIT>
@patch(
    "escparser.parser.ESCParser.exit_tiff_raster_graphics",
    lambda *args: None,
)
def test_set_relative_horizontal_vertical_position(
    movx_cmd: bytes, movy_cmd: bytes, offset_cursor_x: float, offset_cursor_y: float
):
    """Test TIFF <MOVX>, <MOVX> commands

    Cover:

        - set_relative_horizontal_position <MOVX>
        - set_relative_vertical_position <MOVX>

    TODO: implement the check of cursor outside margins
        => need to check that the values are not changed in these cases
        => move current tests to an area away from the margins
    """
    raster_graphics_tiff = b"\x1b.\x02"
    v_res_h_res = b"\x14\x14"  # 180 dpi
    v_dot_count_m = b"\x01"  # nL, hH: height of the band: 1 dot
    trailing_bytes = b"\x00\x00"

    exit_cmd = b"\xe3"

    code = [
        graphics_mode,
        raster_graphics_tiff,
        v_res_h_res + v_dot_count_m + trailing_bytes,

        movx_cmd,
        movy_cmd,

        exit_cmd,
    ]
    escparser = ESCParser(b"".join(code), pdf=False)

    print("cursor_x:", escparser.cursor_x)
    print("cursor_y:", escparser.cursor_y)

    # For now: The moves are relative to the margins
    expected_cursor_x = escparser.printable_area[2] + offset_cursor_x
    expected_cursor_y = escparser.printable_area[0] + offset_cursor_y

    assert escparser.cursor_x == expected_cursor_x
    assert escparser.cursor_y == expected_cursor_y


def test_global_print_tiff_raster_graphics(tmp_path: Path):
    """Global test for a full pdf rendered in TIFF raster graphics mode

    What is printed here:

        - 1 line of 3 colored patterns: magenta, yellow, cyan
        - 1 line of cyan (bad color using the previous one)
        - 1 line of 3 colored patterns obtained by combining colors
        - 1 line of red obtained by combining yellow & magenta,
          using <CR> & <MOVX> commands.
    """
    raster_graphics_tiff = b"\x1b.\x02"
    v_res_h_res = b"\x14\x14"  # 180 dpi
    v_dot_count_m = b"\x01"  # nL, hH: height of the band: 1 dot
    trailing_bytes = b"\x00\x00"

    expected_bytes_count = 10
    # Move 10 units down used as a linefeed between the dot lines
    movy_cmd = b"r\n\x00"
    # Count is inside the nibble of cmd
    # 0b0010_0000 (0x20) + 10 bytes = 0b0010_1010
    xfer_cmd_f0_bc10 = b"*"
    raster_data = b"\xff" * expected_bytes_count
    xfer_graphics_line = xfer_cmd_f0_bc10 + raster_data

    # <EXIT>
    exit_cmd = b"\xe3"

    # <MOVXBYTE>
    movxbyte_cmd = b"\xe4"
    # movxdot_cmd = b"\xe5"

    # <COLR>
    magenta_cmd = b"\x81"
    cyan_cmd = b"\x82"
    yellow_cmd = b"\x84"
    # The grammar allows only this not existing value in the interval.
    # This permits to test the absence of effect of this command.
    unknown_color_cmd = b"\x83"

    # <MOVX> Move 20*unit = 20 * 8 dots
    movx_cmd = b"\x52\x14\x00"

    # <CR>
    cr_cmd = b"\xe2"

    code = [
        graphics_mode,
        raster_graphics_tiff,
        v_res_h_res + v_dot_count_m + trailing_bytes,
        # Move unit: 8 dots
        movxbyte_cmd,

        # Color in magenta
        magenta_cmd + xfer_graphics_line,
        # Color in yellow
        yellow_cmd + movx_cmd + movx_cmd + xfer_graphics_line,
        # Color in cyan
        cyan_cmd + movx_cmd + movx_cmd + movx_cmd + movx_cmd + xfer_graphics_line,

        movy_cmd,

        # Unknwon color => should use the previous color (cyan)
        unknown_color_cmd + xfer_graphics_line,
        movy_cmd,

        # Combinations
        # Color in red: merge magenta + yellow
        yellow_cmd + xfer_graphics_line,
        magenta_cmd + xfer_graphics_line,

        # Color in green: merge cyan + yellow
        cyan_cmd + movx_cmd + movx_cmd + xfer_graphics_line,
        yellow_cmd + movx_cmd + movx_cmd + xfer_graphics_line,

        # Color in blue: merge cyan + magenta
        cyan_cmd + movx_cmd + movx_cmd + movx_cmd + movx_cmd + xfer_graphics_line,
        magenta_cmd + movx_cmd + movx_cmd + movx_cmd + movx_cmd + xfer_graphics_line,

        movy_cmd,

        # Carriage return is made automatically after changing color
        yellow_cmd + xfer_graphics_line,
        # Move horizontally, then go to the left origin:
        # should show a unique red band
        magenta_cmd + movx_cmd + cr_cmd + xfer_graphics_line,

        exit_cmd
    ]

    processed_file = tmp_path / "test_global_print_tiff_raster_graphics.pdf"
    _ = ESCParser(b"".join(code), output_file=processed_file)

    pdf_comparison(processed_file)
