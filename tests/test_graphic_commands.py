# Standard imports
import os
from pathlib import Path
import pytest
from unittest.mock import patch

# Custom imports
from lark.exceptions import UnexpectedToken

# Local imports
import escparser.commons as cm
from .misc import format_databytes
from .misc import esc_reset, cancel_bold
from .helpers.diff_pdf import is_similar_pdfs
from escparser.parser import ESCParser


# Test data path depends on the current package name
DIR_DATA = os.path.dirname(os.path.abspath(__file__)) + "/../test_data/"


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
        - Line if magenta, yellow, cyan patterns
        - Line in red
        - Line in green
        - Line in blue

    """
    select_bit_image_cmd = b'\x1b*'
    dot_density_m_1 = b'\x01'
    dot_density_m_2 = b'\x02'
    expect_44_columns = b'\x2c\x00'
    data_44_columns = b'\x00\x00\x7f\x7f@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00@\x00'
    magenta_cmd = b"\x1br\x01"
    cyan_cmd = b"\x1br\x02"
    yellow_cmd = b"\x1br\x04"

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

        b"\r\n",

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

    # comparaison of PDFs
    # Keep track of the generated file in /tmp in case of error
    backup_file = Path("/tmp/" + processed_file.name)
    backup_file.write_bytes(processed_file.read_bytes())

    ret = is_similar_pdfs(processed_file, Path(DIR_DATA + processed_file.name))
    assert ret, f"Problematic file is saved at <{backup_file}> for further study."
    # All is ok => delete the generated file
    backup_file.unlink()
