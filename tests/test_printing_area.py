# Standard imports
import os
from pathlib import Path
import pytest
from unittest.mock import patch

# Custom imports
from lark.exceptions import UnexpectedToken
from reportlab.lib.pagesizes import A4

# Local imports
import escparser.commons as cm
from .misc import format_databytes
from .misc import esc_reset, cancel_bold
from .helpers.diff_pdf import is_similar_pdfs
from escparser.parser import ESCParser


@pytest.mark.parametrize(
    "format_databytes",
    [
        # ESC ( U - 70/3600 is a not allowed value
        b"\x1b(U\x01\x00\x46" + cancel_bold,
        # Set page length in the current line spacing exceeding 0x7f - ESC C
        b"\x1bC\x80",
        # page length in the current line spacing, exceeding 22inch - ESC C NUL
        b"\x1bC\x00\x20",
    ],
    # First param goes in the 'databytes' param of the fixture format_databytes
    indirect=["format_databytes"],
    ids=[
        "unit_70/3600",
        "page_length_lines",
        "page_length_inches",
    ],
)
def test_wrong_commands(format_databytes: bytes):
    """Test various commands with wrong parameters that will raise a Lark exception"""
    with pytest.raises(UnexpectedToken, match=r"Unexpected token Token.*"):
        _ = ESCParser(format_databytes)


@pytest.mark.parametrize(
    "format_databytes, expected_unit",
    [
        (b"" + cancel_bold, None),
        (b"\x1b(U\x01\x00\x05" + cancel_bold, 5 / 3600),
        (b"\x1b(U\x01\x00\x14" + cancel_bold, 20 / 3600),
    ],
    # First param goes in the 'request' param of the fixture format_databytes
    indirect=["format_databytes"],
    ids=[
        "unit_default",
        "unit_5/3600",
        "unit_20/3600",
    ],
)
def test_set_unit(format_databytes: bytes, expected_unit: float):
    """Test ESC ( U

    The given value is divided by 3600.
    """
    escparser = ESCParser(format_databytes, pdf=False)
    assert escparser.defined_unit == expected_unit


@pytest.mark.parametrize(
    "format_databytes, expected_offset",
    [
        (b"", 0),
        # 3 characters wide
        (b"\x1bl\x03" + cancel_bold, 3 / 10),
        # left margin can't be equal to right margin => ignored
        (b"\x1bQ\x03\x1bl\x03" + cancel_bold, 0),
        # Test the carriage return: the text before increases the cursor_x;
        # set_left_margin should reset it.
        (b"aaa\x1bl\x03" + cancel_bold, 3 / 10),
    ],
    # First param goes in the 'request' param of the fixture format_databytes
    indirect=["format_databytes"],
    ids=["default", "3chars_width", "equal_right_margin", "carriage_return"],
)
def test_set_left_margin(format_databytes: bytes, expected_offset: float):
    """Test ESC l

    :param expected_offset: Expected offset in character_pitch unit.
    """
    escparser = ESCParser(format_databytes, pdf=False)
    # Use the mechanic left margin as reference
    # right margin position is expressed as a function of the leftmost pos
    expected = escparser.printable_area[2] + expected_offset
    assert escparser.left_margin == expected
    assert escparser.cursor_x == expected, "A carriage return must be done"


@pytest.mark.parametrize(
    "format_databytes, expected_offset",
    [
        (b"", 0),
        # 3 characters wide
        (b"\x1bQ\x03" + cancel_bold, 3 / 10),
        # left margin can't be equal to right margin => ignored
        (b"\x1bl\x03\x1bQ\x03" + cancel_bold, 0),
        # Test the carriage return: the text before increases the cursor_x;
        # set_right_margin should reset it.
        (b"aaa\x1bQ\x03" + cancel_bold, 3 / 10),
    ],
    # First param goes in the 'request' param of the fixture format_databytes
    indirect=["format_databytes"],
    ids=["default", "3chars_width", "equal_left_margin", "carriage_return"],
)
def test_set_right_margin(format_databytes: bytes, expected_offset: float):
    """Test ESC Q

    :param expected_offset: Expected offset in character_pitch unit.
    """
    escparser = ESCParser(format_databytes, pdf=False)
    if expected_offset == 0:
        # Margin is untouched or ignored
        expected = escparser.printable_area[3]  # Get the mechanic right margin
        assert escparser.right_margin == expected
    else:
        # Use the mechanic left margin as reference
        # right margin position is expressed as a function of the leftmost pos
        expected = escparser.printable_area[2] + expected_offset
        assert escparser.right_margin == expected
        assert escparser.cursor_x == escparser.left_margin, "A carriage return must be done"


@pytest.mark.parametrize(
    "format_databytes, single_sheet, expected_bottom_margin",
    [
        # Default value for single-sheets
        (b"\x1bN\x06", True, None),
        # 6 lines: 1inch
        (b"\x1bN\x06", False, 6 / 6),
        # 78 lines: 13inch: outside the current page_length: reset to 0
        (b"\x1bN\x4e", False, 0),
        # Observe the linespacing unit changed with ESC 1 (for example) (only 9 pins)
        (b"\x1b1\x1bN\x06", False, 6 * 7 / 72),
    ],
    # First param goes in the 'request' param of the fixture format_databytes
    indirect=["format_databytes"],
    ids=["single-sheets", "default", "outside_page_length", "7/72_linespacing"]
)
def test_set_bottom_margin(format_databytes, single_sheet, expected_bottom_margin):
    """Test ESC N

    Set the bottom margin on continuous paper to n lines (in the current line spacing)
    from the top-of-form position on the NEXT page.
    """
    escparser = ESCParser(format_databytes, single_sheets=single_sheet, pdf=False)
    if single_sheet:
        # Command is ignored
        assert escparser.bottom_margin == escparser.printable_area[1]
    else:
        # Continuous paper
        assert escparser.bottom_margin == expected_bottom_margin


@pytest.mark.parametrize(
    "format_databytes, page_size, expected_margins",
    [
        # hex(11*360): 0xf78
        # Send bottom margin 11inch, so 11.69-11 = 0.69 in bottom-up system: Correct values
        (b"\x1b(c\x04\x00\x08\x02\x78\x0f", A4, (10.24846894138233, 0.692913385826774)),
        # Prepend ESC ( U to set defined unit to 2 / 360
        # hex(11*360/2): 0x7bc
        (b"\x1b(U\x01\x00\x14\x1b(c\x04\x00\x08\x02\xbc\x07", A4, (8.804024496937885, 0.692913385826774)),
        # top margin >= bottom margin: error, fixed with printable area values
        (b"\x1b(c\x04\x00\x00\x02\x00\x01", A4, (11.442913385826774, 0.25)),
        (b"\x1b(c\x04\x00\x08\x02\x08\x02", A4, (11.442913385826774, 0.25)),
        # hex(14*360): 0x13b0
        # Bottom 14inch: outside printable area => reset values to printable area
        (b"\x1b(c\x04\x00\x08\x02\xb0\x13", A4, (11.442913385826774, 0.25)),
        # (b"\x1b(c\x04\x00\x08\x01\x58\x20", A4, (11.442913385826774, 0.25)),
        # hex(23*360): 0x2058
        # Send a 23inch bottom margin on a 23inch height page
        # This value is outside the printable area,
        # The printable margins will set the default bottom_margin to 23 - 0.25 = 22.75
        # But 22.75 is > to the 22inch absolute limit and will not pass this check!
        # Bottom margin should be fixed to 22inch, thus 1 inch,
        # and 22.75 inch for top margin in bottom-up system.
        (b"\x1b(c\x04\x00\x08\x01\x58\x20", (A4[0], (72 * 23)), (22.75, 1)),
    ],
    # First param goes in the 'request' param of the fixture format_databytes
    indirect=["format_databytes"],
    ids=[
        "accepted_values",
        "accepted_values+defined_unit",
        "top>bottom",
        "top=bottom",
        "bottom_margin_outside_printable_area",
        "23inch_bottom_23inch_height",
    ],
)
def test_set_page_format(format_databytes, page_size, expected_margins):
    """Test ESC ( c

    Equation used to calculate the bottom margin position:

    For A4 (11.69inch) page we want a 0.69inch reserved at the bottom of the page.
    We must send a bottom margin of 11inch.

    The default unit is 1/360 inch.

    So:
        0.69 = 11.69 - x * 1/360
        x = (11.69 - 0.69) * 360
        x = 3960
    In hex: 0xf78

    The same value in little endian: 0x780f
    """
    expected_top_margin, expected_bottom_margin = expected_margins
    escparser = ESCParser(format_databytes, page_size=page_size, pdf=False)
    print("Page height:", escparser.page_height)
    print("Found margins (top, bottom):", escparser.top_margin, escparser.bottom_margin)
    print("Page length:", escparser.page_length)
    assert escparser.top_margin == expected_top_margin
    assert escparser.bottom_margin == expected_bottom_margin


@pytest.mark.parametrize(
    "format_databytes, expected",
    [
        # hex(11*360): 0xf78
        # Send bottom margin 11inch, so 11.69-11 = 0.69: Correct values
        (b"\x1b(C\x02\x00\x78\x0f", 11),
        # Prepend ESC ( U to set defined unit to 2 / 360
        # hex(11*360/2): 0x7bc
        (b"\x1b(U\x01\x00\x14\x1b(C\x02\x00\xbc\x07", 11),
        # hex(23*360): 0x2058
        # Send a 23inch page length: > 22 inch
        # This value is outside the accepted area, the value will be set to 22.
        (b"\x1b(C\x02\x00\x58\x20", 22),
        # Test the reset of top/bottom margins, see test_set_page_format
        # for the explanations about the value.
        (b"\x1b(c\x04\x00\x08\x02\x78\x0f\x1b(C\x02\x00\x78\x0f", 11),
    ],
    # First param goes in the 'request' param of the fixture format_databytes
    indirect=["format_databytes"],
    ids=[
        "accepted_value",
        "accepted_value+defined_unit",
        "23inches",
        "reset_top_bottom_margins",
    ],
)
def test_set_page_length_defined_unit(format_databytes, expected):
    """Set page length in defined unit - ESC ( C

    .. note:: default unit is 1 / 360.
    """
    escparser = ESCParser(format_databytes, pdf=False)
    assert escparser.page_length == expected
    top_margin, bottom_margin = escparser.printable_area[0:2]
    assert escparser.top_margin == top_margin
    assert escparser.bottom_margin == bottom_margin

@pytest.mark.parametrize(
    "format_databytes, expected",
    [
        # hex(11*360): 0xf78
        # Send bottom margin 11inch, so 11.69-11 = 0.69: Correct values
        (b"\x1bC\x42", 11),
        # Prepend ESC ( U to set defined unit to 2 / 360
        # hex(11*72/7): ~113 = 0x71
        (b"\x1b1C\x71", 11.192913385826774),
        # hex(23): 0x17
        # PS: if we keep the current linespacing (1/60), the value for 23inch
        # is 138, buch is > to the max expected value: 127.
        # Set the linespacing before to 1inch (60/60) with ESC A.
        # Send a 23inch page length: > 22 inch
        # This value is outside the accepted area, the value will be set to 22.
        (b"\x1bA\x3c\x1bC\x17", 22),
        # Test the reset of top/bottom margins, see test_set_page_format
        # for the explanations about the value.
        (b"\x1b(c\x04\x00\x08\x02\x78\x0f\x1bC\x42", 11),
    ],
    # First param goes in the 'request' param of the fixture format_databytes
    indirect=["format_databytes"],
    ids=[
        "accepted_value",
        "accepted_value+defined_unit",
        "23inches",
        "reset_top_bottom_margins",
    ],
)
def test_set_page_length_lines(format_databytes, expected):
    """Set page length in the current line spacing - ESC C

    .. note:: default linespacing is 1 / 6.
    """
    escparser = ESCParser(format_databytes, pdf=False)
    assert escparser.page_length == expected
    top_margin, bottom_margin = escparser.printable_area[0:2]
    assert escparser.top_margin == top_margin
    assert escparser.bottom_margin == bottom_margin


@pytest.mark.parametrize(
    "format_databytes, expected",
    [
        # 1inch
        (b"\x1bC\x00\x01", 1),
        # 22inch
        (b"\x1bC\x00\x16", 22),
    ],
    # First param goes in the 'request' param of the fixture format_databytes
    indirect=["format_databytes"],
    ids=[
        "1inch",
        "22inch",
    ],
)
def test_set_page_length_inches(format_databytes, expected):
    """Set page length in the current line spacing - ESC C NUL"""
    escparser = ESCParser(format_databytes, pdf=False)
    assert escparser.page_length == expected
    top_margin, bottom_margin = escparser.printable_area[0:2]
    assert escparser.top_margin == top_margin
    assert escparser.bottom_margin == bottom_margin
