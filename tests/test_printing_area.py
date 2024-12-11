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
    """Test ESC ( U command

    The given value is divided by 3600.
    """
    escparser = ESCParser(format_databytes, pdf=False)
    assert escparser.defined_unit == expected_unit
