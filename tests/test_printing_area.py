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
"""Test page configuration and movements in the printing area"""
# Standard imports
from struct import pack
from pathlib import Path
from functools import partial

# Custom imports
import pytest
from lark.exceptions import UnexpectedToken
from reportlab.lib.pagesizes import A4

# Local imports
from escapy.parser import ESCParser as _ESCParser
from .misc import format_databytes, typefaces
from .misc import esc_reset, cancel_bold

# Inject test typefaces
ESCParser = partial(_ESCParser, available_fonts=typefaces)


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
    escapy = ESCParser(format_databytes, pdf=False)
    assert escapy.defined_unit == expected_unit


@pytest.mark.parametrize(
    "format_databytes, expected_offset",
    [
        (b"", 0),
        # 3 characters wide
        (b"\x1bl\x03" + cancel_bold, 3 / 10),
        # left margin can't be equal to right margin => ignored
        (b"\x1bQ\x03" + b"\x1bl\x03" + cancel_bold, 0),
        # Test the carriage return: the text before increases the cursor_x;
        # set_left_margin should reset it.
        (b"aaa" + b"\x1bl\x03" + cancel_bold, 3 / 10),
    ],
    # First param goes in the 'request' param of the fixture format_databytes
    indirect=["format_databytes"],
    ids=["default", "3chars_width", "equal_right_margin", "carriage_return"],
)
def test_set_left_margin(format_databytes: bytes, expected_offset: float):
    """Test ESC l

    :param expected_offset: Expected offset in character_pitch unit.
    """
    escapy = ESCParser(format_databytes, pdf=False)
    # Use the mechanic left margin as reference
    # right margin position is expressed as a function of the leftmost pos
    expected = escapy.printable_area[2] + expected_offset
    assert escapy.left_margin == expected
    assert escapy.cursor_x == expected, "A carriage return must be done"


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
    escapy = ESCParser(format_databytes, pdf=False)
    if expected_offset == 0:
        # Margin is untouched or ignored
        expected = escapy.printable_area[3]  # Get the mechanic right margin
        assert escapy.right_margin == expected
    else:
        # Use the mechanic left margin as reference
        # right margin position is expressed as a function of the leftmost pos
        expected = escapy.printable_area[2] + expected_offset
        assert escapy.right_margin == expected
        assert (
            escapy.cursor_x == escapy.left_margin
        ), "A carriage return must be done"


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
        (b"\x1b1" + b"\x1bN\x06", False, 6 * 7 / 72),
    ],
    # First param goes in the 'request' param of the fixture format_databytes
    indirect=["format_databytes"],
    ids=["single-sheets", "default", "outside_page_length", "7/72_linespacing"],
)
def test_set_bottom_margin(format_databytes, single_sheet, expected_bottom_margin):
    """Test ESC N

    Set the bottom margin on continuous paper to n lines (in the current line spacing)
    from the top-of-form position on the NEXT page.
    """
    escapy = ESCParser(format_databytes, single_sheets=single_sheet, pdf=False)
    if single_sheet:
        # Command is ignored
        assert escapy.bottom_margin == escapy.printable_area[1]
    else:
        # Continuous paper
        assert escapy.bottom_margin == expected_bottom_margin


@pytest.mark.parametrize(
    "format_databytes, page_size, expected_margins",
    [
        # hex(11*360): 0xf78
        # Send bottom margin 11inch, so 11.69-11 = 0.69 in bottom-up system: Correct values
        (b"\x1b(c\x04\x00\x08\x02\x78\x0f", A4, (10.24846894138233, 0.692913385826774)),
        # Prepend ESC ( U to set defined unit to 2 / 360
        # hex(11*360/2): 0x7bc
        (b"\x1b(U\x01\x00\x14" + b"\x1b(c\x04\x00\x08\x02\xbc\x07", A4, (8.804024496937885, 0.692913385826774)),
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
    escapy = ESCParser(format_databytes, page_size=page_size, pdf=False)
    print("Page height:", escapy.page_height)
    print("Found margins (top, bottom):", escapy.top_margin, escapy.bottom_margin)
    print("Page length:", escapy.page_length)
    assert escapy.top_margin == expected_top_margin
    assert escapy.bottom_margin == expected_bottom_margin


@pytest.mark.parametrize(
    "format_databytes, expected",
    [
        # hex(11*360): 0xf78
        # Send bottom margin 11inch, so 11.69-11 = 0.69: Correct values
        (b"\x1b(C\x02\x00\x78\x0f", 11),
        # Prepend ESC ( U to set defined unit to 2 / 360
        # hex(11*360/2): 0x7bc
        (b"\x1b(U\x01\x00\x14" + b"\x1b(C\x02\x00\xbc\x07", 11),
        # hex(23*360): 0x2058
        # Send a 23inch page length: > 22 inch
        # This value is outside the accepted area, the value will be set to 22.
        (b"\x1b(C\x02\x00\x58\x20", 22),
        # Test the reset of top/bottom margins, see test_set_page_format
        # for the explanations about the value.
        (b"\x1b(c\x04\x00\x08\x02\x78\x0f" + b"\x1b(C\x02\x00\x78\x0f", 11),
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
    escapy = ESCParser(format_databytes, pdf=False)
    assert escapy.page_length == expected
    top_margin, bottom_margin = escapy.printable_area[0:2]
    assert escapy.top_margin == top_margin
    assert escapy.bottom_margin == bottom_margin


@pytest.mark.parametrize(
    "format_databytes, expected",
    [
        # hex(11*360): 0xf78
        # Send bottom margin 11inch, so 11.69-11 = 0.69: Correct values
        (b"\x1bC\x42", 11),
        # Prepend ESC 1 to set the linespacing to 7 /72
        # hex(11*72/7): ~113 = 0x71
        (b"\x1b1C\x71", 11.192913385826774),
        # hex(23): 0x17
        # PS: if we keep the current linespacing (1/60), the value for 23inch
        # is 138, buch is > to the max expected value: 127.
        # Set the linespacing before to 1inch (60/60) with ESC A.
        # Send a 23inch page length: > 22 inch
        # This value is outside the accepted area, the value will be set to 22.
        (b"\x1bA\x3c" + b"\x1bC\x17", 22),
        # Test the reset of top/bottom margins, see test_set_page_format
        # for the explanations about the value.
        (b"\x1b(c\x04\x00\x08\x02\x78\x0f" + b"\x1bC\x42", 11),
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
    escapy = ESCParser(format_databytes, pdf=False)
    assert escapy.page_length == expected
    top_margin, bottom_margin = escapy.printable_area[0:2]
    assert escapy.top_margin == top_margin
    assert escapy.bottom_margin == bottom_margin


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
    escapy = ESCParser(format_databytes, pdf=False)
    assert escapy.page_length == expected
    top_margin, bottom_margin = escapy.printable_area[0:2]
    assert escapy.top_margin == top_margin
    assert escapy.bottom_margin == bottom_margin


@pytest.mark.parametrize(
    "format_databytes, pins, x_offset, y_offset",
    [
        # Absolute horizontal position - ESC $
        # 1 inch (60/60) for default unit: 1/60
        (b"\x1b$\x3c\x00", None, 1, 0),
        (b"\x1b$\x3c\x00", 9, 1, 0),
        # Prepend ESC ( U to set defined unit to 2/360
        # hex(1*360//2): 0xb4 = 180
        (b"\x1b(U\x01\x00\x14" + b"\x1b$\xb4\x00", None, 1, 0),
        # Prepend ESC ( U to set defined unit to 2/360
        # Outside right margin hex(60*360//2) 60.25inch: ignored
        (b"\x1b(U\x01\x00\x14" + b"\x1b$\x30\x2a", None, 0, 0),
        # defined unit is ignored on 9 pins printers:
        # => same value as it is with a 1/6 unit
        (b"\x1b(U\x01\x00\x14" + b"\x1b$\x3c\x00", 9, 1, 0),
        #
        # Relative horizontal position - ESC \
        # +2inch absolute, then -1inch relative (-180/180) = 1inch
        # default unit: 1/180
        (b"\x1b$\x78\x00" + b"\x1b\\" + pack("<h", -180), None, 1, 0),
        # 9 pins default unit: 1/120
        # +2inch absolute, then -120/120
        (b"\x1b$\x78\x00" + b"\x1b\\" + pack("<h", -120), 9, 1, 0),
        # Prepend ESC ( U to set defined unit to 2/360
        # +2inch absolute, then -180/180
        (b"\x1b$\x78\x00" + b"\x1b(U\x01\x00\x14" + b'\x1b\\' + pack("<h", -180), None, 1, 0),
        # Outside right margin -400/180inch ~ 2.22: ignored
        # +2inch absolute, then -2.22inch
        (b"\x1b$\x78\x00" + b"\x1b\\" + pack("<h", -400), None, 2, 0),
        #
        # Absolute vertical position - ESC ( V
        # 1 inch below top margin 360 (360/360) for default unit: 1/360
        (b"\x1b(V\x02\x00" + pack("<H", 360), None, 0, -1),
        # Prepend ESC ( U to set defined unit to 2/360
        # 1 inch below top margin 180 (180/180)
        (b"\x1b(U\x01\x00\x14" + b"\x1b(V\x02\x00" + pack("<H", 180), None, 0, -1),
        # 12 inch below top margin: next page
        (b"\x1b(V\x02\x00" + pack("<H", 12 * 360), None, 0, 0),
        # 1 inch below top margin, then 1/360 inch below top margin:
        # movement amplitude too large (359/360 inch): ignored
        (b"\x1b(V\x02\x00" + pack("<H", 360) + b"\x1b(V\x02\x00" + pack("<H", 1), None, 0, -1),
        #
        # Relative vertical position - ESC ( v
        # 1 inch down (360/360) for default unit: 1/360
        (b"\x1b(v\x02\x00" + pack("<h", 360), None, 0, -1),
        # 179/360 inch up: outside top margin: ignored
        (b"\x1b(v\x02\x00" + pack("<h", -179), None, 0, 0),
        # 12 inch down: outside bottom margin: next page
        (b"\x1b(v\x02\x00" + pack("<h", 12 * 360), None, 0, 0),
        # 1 inch up (>179/360): movement amplitude too large: ignored
        (b"\x1b(v\x02\x00" + pack("<h", -360), None, 0, 0),
        # Prepend ESC ( U to set defined unit to 2/360
        # 1 inch down
        (b"\x1b(U\x01\x00\x14" + b"\x1b(v\x02\x00" + pack("<h", 180), None, 0, -1),
        #
        # Advance the vertical print position n/180 inch - ESC J
        # down (255/180)
        (b"\x1bJ" + pack("<B", 255), None, 0, -1.4166666666666667),
        # Idem: but below bottom_margin and bottom_printable area: eject
        # See the tear down end_page_paper_handling()
        # Here we set the cursor_y just enough to trigger a next page event
        # from the ESC J command (66*1.66 = 11 inch).
        # 255/216 ~ 1.18 inch down: 11 + 1.18 > 11.69 inch of A4 page
        (b"\n" * 66 + b"\x1bJ" + pack("<B", 255), 9, 0, 0),
        # 1 inch down (180/180)
        (b"\x1bJ" + pack("<B", 180), None, 0, -1),
        # 1 inch down (216/216)
        (b"\x1bJ" + pack("<B", 216), 9, 0, -1),
    ],
    # First param goes in the 'request' param of the fixture format_databytes
    indirect=["format_databytes"],
    ids=[
        # Absolute horizontal position - ESC $
        "AH_1inch",
        "AH_1inch_9pins",
        "AH_1inch+defined_unit",
        "AH_60inch_ignored+defined_unit",
        "AH_not_ignored_9pins+defined_unit",
        # Relative horizontal position - ESC \
        "RH_-1inch",
        "RH_-1inch_9pins",
        "RH_-1inch+defined_unit",
        "RH_-60inch_ignored+defined_unit",
        # Absolute vertical position - ESC ( V
        "AV_1inch",
        "AV_1inch+defined_unit",
        "AV_12inch",
        "AV_amplitude_too_large",
        # Relative vertical position - ESC ( v
        "RV_1inch",
        "RV_-179/360_outside_top_margin",
        "RV_12inch_outside_bottom_margin",
        "RV_-1inch_amplitude_too_large",
        "RV_1inch+defined_unit",
        # Advance the vertical print position n/180 inch - ESC J
        "AdV_maxoffset",
        "AdV_maxoffset_9pins",
        "AdV_1inch",
        "AdV_1inch_9pins",
    ],
)
def test_set_print_position(
    format_databytes, pins: int, x_offset: int | float, y_offset: int | float
):
    """Test relative & absolute position movements

    Cover:

        - Absolute horizontal position - ESC $
        - Relative horizontal position - ESC \
        - Absolute vertical position - ESC ( V
        - Relative vertical position - ESC ( v
        - Advance the vertical print position n/180 inch - ESC J

    .. warning:: In theory ESC ( U, ESC ( v, ESC ( V are not available
        on non ESCP2 printers.

    :param pins: Number of pins supported by the printer. None for ESCP2.
    :param x_offset: Expected offset from the top-margin.
    :param y_offset: Expected offset from the left-margin.
    """
    escapy = ESCParser(format_databytes, pins=pins, pdf=False)
    assert escapy.cursor_x == escapy.left_margin + x_offset
    assert escapy.cursor_y == escapy.top_margin + y_offset


def test_h_v_skip():
    """Test horizontal/vertical skip - ESC f"""
    # n = 10
    horizontal_skip = b"\x1bf\x00\x0a"
    vertical_skip = b"\x1bf\x01\x0a"

    escapy = ESCParser(esc_reset + horizontal_skip, pins=9, pdf=False)
    # default character pitch is 1/10
    # Since the modern font don't use this setting, we expect at least 10 * 1/10
    print(escapy.character_pitch * 10)
    assert escapy.cursor_x >= 1

    escapy = ESCParser(esc_reset + vertical_skip, pins=9, pdf=False)
    print(escapy.current_line_spacing * 10)  # 1/6 * 10
    # We need to round the values... rounding errors seem to accumulate
    expected = round(escapy.printable_area[0] - escapy.current_line_spacing * 10, 5)
    found = round(escapy.cursor_y, 5)
    assert found == expected


def test_form_feed():
    """Test form feed - FF"""
    double_width_cmd = b"\x0e"
    formfeed_cmd = b"\x0c"
    top_margin_cmd = b"\x1b(c\x04\x00\x08\x02\x78\x0f"
    code = esc_reset + top_margin_cmd + double_width_cmd + formfeed_cmd

    # In 9 pins mode + continuous paper, the top_margin is not used
    # (and not configurable in 9 pins BTW...)
    # so the printable area margin is used after the new_page event.
    escapy = ESCParser(code, pins=9, single_sheets=False, pdf=False)
    expected = escapy.printable_area[0]
    assert escapy.cursor_y == expected
    assert not escapy.double_width

    # ESCP2 & 9 pins (single-sheets)
    escapy = ESCParser(code, pdf=False)
    expected = escapy.top_margin
    assert escapy.top_margin != escapy.printable_area[0]
    assert escapy.cursor_y == expected
    assert not escapy.double_width


def test_control_paper_loading_ejecting(tmp_path: Path):
    """ESC EM R: next page

    Test the creation of a new page.

    .. warning:: For now, DO NOT test buffer shenanigans. See the
        :meth:`control_paper_loading_ejecting` docstring.
    """
    eject_paper_cmd = b"\x1b\x19R"
    code = esc_reset + eject_paper_cmd
    processed_file = tmp_path / "test_2pages.pdf"
    escapy = ESCParser(code, output_file=processed_file)

    # Yeah... 3... but there are 2 pages... (the save method increments the count)
    assert escapy.current_pdf.getPageNumber() == 3
