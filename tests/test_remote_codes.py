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
"""Test remote commands"""

# Standard imports
from struct import pack
from pathlib import Path
from functools import partial

# Custom imports
import pytest

# Local imports
from escapy.parser import ESCParser as _ESCParser
from escapy.parser import EscpCompatibility
from .misc import typefaces

# Inject test typefaces
ESCParser = partial(_ESCParser, available_fonts=typefaces)


def remote_cmd(cmd: str, args: bytes) -> bytes:
    """Generate a Remote Mode command"""
    if len(cmd) != 2:
        raise ValueError("Command should be exactly 2 characters")
    return cmd.encode() + pack("<H", len(args)) + args


INITIALIZE_PRINTER = b"\x1b@"
EXIT_PACKET_MODE = b"\x00\x00\x00\x1b\x01@EJL 1284.4\n@EJL     \n"
ENTER_D4 = b"\x00\x00\x00\x1b\x01@EJL 1284.4\n@EJL\n@EJL\n"
REMOTE_MODE = b"\x1b" + remote_cmd("(R", b"\x00REMOTE1")
# Initialize printer and enter Epson Remote Command mode.
ENTER_REMOTE_MODE = (
    INITIALIZE_PRINTER
    + INITIALIZE_PRINTER
    + REMOTE_MODE
    + remote_cmd("RS", b"\x01")  # reset_printer
)
EXIT_REMOTE_MODE = b"\x1b\x00\x00\x00"
JOB_END = remote_cmd("JE", b"\x00")


def build_remote_program(databytes: bytes) -> bytes:
    """Wrap the commands with the commands required for entering and exiting remote mode"""
    commands = [
        EXIT_PACKET_MODE,  # Exit packet mode
        ENTER_D4,
        ENTER_REMOTE_MODE,  # Engage remote mode commands
    ]
    commands.append(databytes)
    commands += [
        EXIT_REMOTE_MODE,  # Disengage remote control
    ]
    return b"".join(commands)


@pytest.mark.parametrize(
    "databytes, expected_offset",
    [
        # Left margin offset: +1inch: 360/360th
        (remote_cmd("FP", b"\x00" + pack("<h", 360)), 1),
        # Suppress horizontal left margin: -80 (~5.6mm): 0xB0FF
        (remote_cmd("FP", b"\x00" + pack("<h", -80)), -80 / 360),
        # Outside page bounds
        (remote_cmd("FP", b"\x00" + pack("<h", -360)), 0),
    ],
    # First param goes in the 'request' param of the fixture format_databytes
    # indirect=["format_databytes"],
    ids=[
        "unit_default",
        "borderless",
        "out_page_bounds",
    ],
)
def test_set_relative_left_margin(databytes: bytes, expected_offset: float | int):
    """Test set relative left margin - FP

    :param databytes: Applied command(s).
    :param expected_offset: Expected offset in character_pitch unit.
    """
    code = build_remote_program(databytes)
    escapy = ESCParser(code, pdf=False)
    # Use the mechanic left margin as reference
    # right margin position is expressed as a function of the leftmost pos
    expected = escapy.printable_area[2] + expected_offset
    assert escapy.left_margin == expected


def test_set_job_name(tmp_path: Path):
    """Test set job name - JH"""
    commands = [
        # Job name set: m1=0: Hostname; Job ID: 0x01020304;
        remote_cmd("JH", b"\x00\x00\x01\x02\x03\x04Hostname"),
        # Job name set: m1=1: Product ID; Job ID: 0x01020304;
        remote_cmd("JH", b"\x00\x01\x01\x02\x03\x04Product ID"),
        # Job name set: m1=2: Document name; Job ID: 0x01020304;
        remote_cmd("JH", b"\x00\x02\x01\x02\x03\x04Document name"),
        # Job name set: m1=2: Username; Job ID: 0x01020304;
        remote_cmd("JH", b"\x00\x03\x01\x02\x03\x04Username"),
    ]
    code = build_remote_program(b"".join(commands))
    processed_file = tmp_path / "test_set_job_name.pdf"
    escapy = ESCParser(code, output_file=processed_file)

    pdf_info = escapy.current_pdf._doc.info
    assert pdf_info.creator == "Hostname"
    assert pdf_info.title == "Document name"
    assert pdf_info.author == "Username"


def test_start_job(tmp_path: Path):
    """Test start job - JS"""
    commands = [
        # Job start with empty name
        remote_cmd("JS", b"\x00\x00"),
        # Job start with name
        remote_cmd("JS", b"\x00Hello World Job\x00"),
    ]
    code = build_remote_program(b"".join(commands))
    processed_file = tmp_path / "test_start_job.pdf"
    escapy = ESCParser(code, output_file=processed_file)

    pdf_info = escapy.current_pdf._doc.info
    assert pdf_info.title == "Hello World Job"
