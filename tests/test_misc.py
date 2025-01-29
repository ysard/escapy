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
"""Miscellaneous tests (global loglevel settings, grammar behaviour)"""
# Standard imports
from pathlib import Path
from functools import partial

# Custom imports
import pytest

# Local imports
from escparser.commons import log_level
from escparser.parser import ESCParser as _ESCParser
from .misc import DIR_DATA, esc_reset, typefaces

# Inject test typefaces
ESCParser = partial(_ESCParser, available_fonts=typefaces)


@pytest.fixture
def set_loglevel():
    """Fixture to safely test NONE loglevel

    DEBUG loglevel is restored in the tear down for further tests
    """
    log_level("NONE")

    yield None

    # Restore loglevel
    log_level("debug")


def test_no_loglevel(tmp_path: Path, capsys, set_loglevel: None):
    """Test loglevel NONE

    No output on stdout is expected.

    :param tmp_path: Path of temporary working dir returned by a pytest fixture.
    :param capsys: pytest capsys-fixture
    :type capsys: _pytest.capture.CaptureFixture
    """
    code = Path(DIR_DATA + "escp2_1.prn").read_bytes()
    processed_file = tmp_path / "escp2_1.pdf"
    _ = ESCParser(code, output_file=processed_file)

    captured = capsys.readouterr()
    print(captured)
    assert not (
        captured.out or captured.err
    ), "stdout,stderr should be empty in loglevel None"


def test_not_implemented_command(tmp_path: Path, caplog):
    """Test ESC command defined into the grammar but not implemented in the parser

    A simple output in the LOGGER at the level ERROR should be observed.

    :param tmp_path: Path of temporary working dir returned by a pytest fixture.
    :param caplog: pytest caplog-fixture
    :type caplog: _pytest.logging.LogCaptureFixture
    """
    set_unidirectional_mode_cmd = b"\x1b<"

    lines = [esc_reset, set_unidirectional_mode_cmd]

    code = b"".join(lines)
    _ = ESCParser(code, pdf=False)

    print("records:", caplog.records)
    assert "Command not implemented: Tree('set_unidirectional_mode'" in caplog.text
