# Standard imports
import os
import struct
from pathlib import Path
import pytest
from unittest.mock import patch

# Custom imports
from lark.exceptions import UnexpectedToken

# Local imports
import escparser.commons as cm
from .misc import format_databytes
from .misc import esc_reset, cancel_bold, graphics_mode
from .helpers.diff_pdf import is_similar_pdfs
from escparser.parser import ESCParser


# Test data path depends on the current package name
DIR_DATA = os.path.dirname(os.path.abspath(__file__)) + "/../test_data/"

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

DECOMPRESSED_DATA = bytearray(b"".join([struct.pack('>B', i) for i in DECOMPRESSED_DATA]))
# Pay attention to convert negative counters into signed bytes
COMPRESSED_DATA = bytearray(b"".join([struct.pack('>b', i) if i < 0 else struct.pack('>B', i) for i in COMPRESSED_DATA]))

def pdf_comparison(processed_file: Path):
    """Wrapper to compare two PDFs files

    In case of error, the wrong pdf and the diff file will be copied in /tmp/.

    :param processed_file: Test file Path object. Its name is used to make
        the comparison with an expected file with the same name, expected in
        the test_data directory.
    """
    #
    # Keep track of the generated file in /tmp in case of error
    backup_file = Path("/tmp/" + processed_file.name)
    backup_file.write_bytes(processed_file.read_bytes())

    ret = is_similar_pdfs(processed_file, Path(DIR_DATA + processed_file.name))
    assert ret, f"Problematic file is saved at <{backup_file}> for further study."
    # All is ok => delete the generated file
    backup_file.unlink()

################################################################################

@pytest.mark.parametrize(
    "format_databytes",
    [
        # 0x4f (79) is not an authorized value
        b"\x1b?K\x4f" + cancel_bold,
        # unknown_color_cmd ESC r
        b"\x1br\x20",
    ],
    # First param goes in the 'databytes' param of the fixture format_databytes
    indirect=["format_databytes"],
    ids=[
        "reassign_bit_image_wrong_density",
        "unknown_color",
    ],
)
def test_wrong_commands(format_databytes):
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

    code = b"\x1b?".join(bytearray(cmd_density) for cmd_density in zip(cmd_letters, dot_density_m))

    escparser = ESCParser(esc_reset + code)

    assert escparser.klyz_densities == dot_density_m


@pytest.mark.parametrize(
    # The dot density impacts horizontal & vertical resolutions + bytes per column and double speed mode
    # The number of pins can modify vertical resolution
    "format_databytes, pins, dot_density, hori, verti, bytes_per_column, double_speed",
    [
        # ESC K: cancel_bold belongs to the command, it is used to test the parsing
        (b"\x1bK\x04\x00\xff\x0a" + cancel_bold, 9, 0, 1/60, 1/72, 1, False),
        (b"\x1bK\x04\x00\xff\x0a" + cancel_bold, None, 0, 1/60, 1/60, 1, False),
        # Set dot_density to 7 via ESC ? K command, before ESC K command
        (b"\x1b?K\x07\x1bK\x04\x00\xff\x0a" + cancel_bold, 9, 7, 1/144, 1/72, 1, False),
        # Test other densities (cf configure_bit_image), also, double_speed is enabled for these modes
        (b"\x1b?K\x28\x1bK\x04\x00\xff\x0a" + cancel_bold, None, 40, 1/360, 1/180, 3, True),
        (b"\x1b?K\x48\x1bK\x04\x00\xff\x0a" + cancel_bold, None, 72, 1/360, 1/360, 6, True),
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
def test_select_graphics(format_databytes, pins, dot_density, hori, verti, bytes_per_column, double_speed):
    """Test select_xdpi_graphics (ESC K, L, Y, Z) & configure_bit_image function

    The tests use K command, thus, position 0 in klz_densities is updated.
    """
    escparser = ESCParser(format_databytes, pins=pins)

    assert escparser.klyz_densities[0] == dot_density
    assert escparser.horizontal_resolution == hori
    assert escparser.vertical_resolution == verti
    assert escparser.bytes_per_column == bytes_per_column
    assert escparser.double_speed == double_speed


def test_select_bit_image(tmp_path):
    """Test select_bit_image ESC *

    Show different representation of a form like the ⌐ (reversed not sign)

    About the dot densities used:

        - 1: h x v:  1/120 x 1/60, 1 byte per column, double speed off
        - 2: h x v:  1/120 x 1/60, 1 byte per column, double speed on

    What is printed here:

        - Normal line
        - double speed line
        - Line in magenta, yellow, cyan patterns
        - Line in red (from RGB, not allowed in raster graphics mode, BUT here we are in bit-image mode!)
        - Line in red (from CMYK combination)
        - Line in green (from CMYK combination)
        - Line in blue (from CMYK combination)

    """
    select_bit_image_cmd = b'\x1b*'
    dot_density_m_1 = b'\x01'
    dot_density_m_2 = b'\x02'
    expect_44_columns = b'\x2c\x00'
    data_44_columns = b'\x00\x00\x7f\x7f@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00'
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
    escparser = ESCParser(code, output_file=str(processed_file))

    assert escparser.horizontal_resolution == 1/120
    assert escparser.vertical_resolution == 1/60
    assert escparser.bytes_per_column == 1
    assert escparser.double_speed == True  # m2 effect

    pdf_comparison(processed_file)


# Raster graphics ##############################################################

def test_rle_decompress():
    """Test TIFF/RLE decompression

    Data examples from the doc p313.
    """
    expected_decompressed_data = DECOMPRESSED_DATA

    found = ESCParser.decompress_rle_data(COMPRESSED_DATA)

    assert found == expected_decompressed_data


def get_raster_data_code(rle_compressed=False):
    """Generate raster data in graphics mode according to the compression level

    ESC ( G + ESC . 0 or ESC ( G + ESC . 1
    """
    raster_graphics = b"\x1b.\x00"
    raster_graphics_rle = b"\x1b.\x01"
    v_res_h_res = b"\x14\x14"  # 180 dpi
    v_dot_count_m = b"\x08"  # nL, hH: height of the band: 8 dots
    bytes_count = b"\x48\x00"  # length of decompressed data: 72 bytes (vs 59 compressed)

    code = [
        graphics_mode,
        raster_graphics_rle if rle_compressed else raster_graphics,
        v_res_h_res + v_dot_count_m + bytes_count,
        COMPRESSED_DATA if rle_compressed else DECOMPRESSED_DATA
    ]
    return b"".join(code)


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
    ],
    # First param goes in the 'databytes' param of the fixture format_databytes
    indirect=["format_databytes"],
    ids=[
        "no_rle",
        "rle",
        "no_rle_not_allowed_color_change"
    ],
)
def test_print_raster_graphics(format_databytes, tmp_path):
    """Test raster graphics 0 and 1 modes (no compress, RLE compress modes)

    Cover ESC . 0, ESC . 1 commands

    Data examples from the doc p313.
    """
    processed_file = tmp_path / "test_raster_graphics_compress_no_and_rle.pdf"
    escparser = ESCParser(format_databytes, output_file=str(processed_file))

    assert escparser.horizontal_resolution == 1/180
    assert escparser.vertical_resolution == 1/180
    assert escparser.bytes_per_line == int((72 + 7) / 8)
    assert escparser.double_speed == False

    pdf_comparison(processed_file)


def test_print_tiff_raster_graphics(tmp_path):
    """Test TIFF raster graphics

    Cover ESC . 2, <MOVY>, full <XFER> command (nibble combinations), <EXIT>.

    Print 3 lines of 10*8 dots (10 bytes) with various <XFER> configurations.
    """
    raster_graphics_tiff = b"\x1b.\x02"
    v_res_h_res = b"\x14\x14"  # 180 dpi
    v_dot_count_m = b"\x01"  # nL, hH: height of the band: 8 dots
    trailing_bytes = b"\x00\x00"  # length of decompressed data: 72 bytes (vs 59 compressed)

    expected_bytes_count = 10
    # Move 10 units down used as a linefeed between the dot lines
    movy_cmd = b"r\n\x00"
    # Count is inside the nibble of cmd
    # 0b0010_0000 (0x20) + 10 bytes = 0b0010_1010
    xfer_cmd_f0_bc10 = b'*'
    # Count is inside the next byte nL
    # 0b0011_0000 (0x30) + 1 = 0b0010_0001
    xfer_cmd_f1_bc1 = b'1\x0a'
    # Count is inside the 2 next bytes
    # 0b0011_0000 (0x30) + 2 = 0b0010_0010
    xfer_cmd_f1_bc2 = b'2\x0a\x00'
    raster_data = b'\xff' * expected_bytes_count

    exit_cmd = b"\xe3"

    code = [
        graphics_mode,
        raster_graphics_tiff,
        v_res_h_res + v_dot_count_m + trailing_bytes,

        xfer_cmd_f0_bc10 + raster_data,
        movy_cmd,
        xfer_cmd_f1_bc1 + raster_data,
        movy_cmd,
        xfer_cmd_f1_bc2 + raster_data,

        exit_cmd
    ]

    processed_file = tmp_path / "test_print_tiff_raster_graphics.pdf"
    escparser = ESCParser(b"".join(code), output_file=str(processed_file))

    assert escparser.horizontal_resolution == 1 / 180
    assert escparser.vertical_resolution == 1 / 180
    assert escparser.bytes_per_line == expected_bytes_count

    pdf_comparison(processed_file)
