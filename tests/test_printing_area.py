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


@pytest.mark.parametrize(
    "format_databytes",
    [
        # ESC ( U - 70/3600 is a not allowed value
        b"\x1b(U\x01\x00\x46" + cancel_bold,
    ],
    # First param goes in the 'databytes' param of the fixture format_databytes
    indirect=["format_databytes"],
    ids=[
        "unit_70/3600",
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
def test_set_unit(format_databytes, expected_unit):
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
    ids=[
        "default",
        "3chars_width",
        "equal_right_margin",
        "carriage_return"
    ],
)
def test_set_left_margin(format_databytes, expected_offset: float):
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
    ids=[
        "default",
        "3chars_width",
        "equal_left_margin",
        "carriage_return"
    ],
)
def test_set_right_margin(format_databytes, expected_offset: float):
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



