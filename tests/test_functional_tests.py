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
"""Test real-life file rendering"""
# Standard imports
import sys
from pathlib import Path
from functools import partial
from unittest.mock import patch

# Custom imports
import pytest
from reportlab.lib.pagesizes import A4
from reportlab.lib.pagesizes import landscape

# Local imports
from escapy.parser import ESCParser as _ESCParser
from escapy.__main__ import escapy_entry_point, choose_config_file
from .misc import DIR_DATA, pdf_comparison, typefaces

# Inject test typefaces
ESCParser = partial(_ESCParser, available_fonts=typefaces)


@pytest.mark.parametrize(
    "code_file, expected_pdf, args",
    [
        ("test_Graphics_invoice.CP850.prn", "test_Graphics_invoice.CP850.pdf", {"pins": None}),
        ("test2.KEYBCS2.prn", "test2.KEYBCS2.pdf", {}),
        ("Test2_badcommand.prn", "Test2_badcommand.pdf", {"pins": 9}),
        ("Test2_badcommand.prn", "Test2_badcommand_landscape.pdf", {"pins": 9, "page_size": landscape(A4)}),
        ("escp2_1.prn", "escp2_1.pdf", {}),
        ("escp2_1.prn", "escp2_1_9pins.pdf", {"pins": 9}),
        ("escp2_1.prn", "escp2_1.pdf", {"automatic_linefeed": True}),
        ("TDS420A_epson_9_24_c_page4_patched.prn", "TDS420A_epson_9_24_c_page4_patched.pdf", {}),
    ],
    ids=[
        "test_Graphics_invoice.CP850",
        "test2.KEYBCS2",
        "Test2_badcommand",
        "Test2_badcommand_landscape",
        "escp2_1",
        "escp2_1_9pins",
        "escp2_1_auto_linefeed",
        "TDS420A_escp",
    ],
)
def test_full_file_conversion(
    tmp_path: Path, code_file: str, expected_pdf: str, args: dict
):
    """Convert ESC code to PDF files and check the result

    :param tmp_path: Path of temporary working dir returned by a pytest fixture.
    :param code_file: Filename of ESC code sent by a computer to a printer.
    :param expected_pdf: Filename of the expected PDF file.
    :param args: Tuple of arguments passed to the ESCParser object.
    """
    code = Path(DIR_DATA + code_file).read_bytes()

    if args.get("automatic_linefeed"):
        # CR is replaced by CR + LF internally: delete all LF for simulation
        code = code.replace(b"\n", b"")

    processed_file = tmp_path / expected_pdf
    _ = ESCParser(code, output_file=processed_file, **args)

    pdf_comparison(processed_file)


@pytest.fixture()
def minimal_config() -> str:
    """Generate a minimal configuration

    - misc section is mandatory
    - fonfigure the default font
    """
    return """[misc]
        loglevel = debug
        [Roman]
        fixed = FiraCode
        """


def test_stdin_stdout(capsysbinary, tmp_path: Path, minimal_config: str):
    """Test the produced data written on stdout

    :param tmp_path: Path of temporary working dir returned by a pytest fixture.
    :param minimal_config: Fixture with minimal configuration file content.
    """
    empty_config_file = tmp_path / "config.conf"
    empty_config_file.write_text(minimal_config)

    processed_file = tmp_path / "escp2_1.pdf"

    cmdline_args = {
        # Need to use a _io.TextIOWrapper object like the one given by argparse
        "esc_prn": open(DIR_DATA + "escp2_1.prn", encoding="utf8"),
        "config": empty_config_file,
        "output": sys.stdout,
    }

    # Do magic
    escapy_entry_point(**cmdline_args)

    captured = capsysbinary.readouterr()
    processed_file.write_bytes(captured.out)

    pdf_comparison(processed_file)


def test_argument_parser(tmp_path: Path, minimal_config: str):
    """Almost full test from the command line to the pdf generated

    :param tmp_path: Path of temporary working dir returned by a pytest fixture.
    :param minimal_config: Fixture with minimal configuration file content.
    """
    empty_config_file = tmp_path / "config.conf"
    empty_config_file.write_text(minimal_config)

    processed_file = tmp_path / "escp2_1.pdf"
    cmdline_args = {
        # Need to use a _io.TextIOWrapper object like the one given by argparse
        "esc_prn": open(DIR_DATA + "escp2_1.prn", encoding="utf8"),
        "config": empty_config_file,
        "output": processed_file,
    }

    # Do magic
    escapy_entry_point(**cmdline_args)

    pdf_comparison(processed_file)


def test_empty_input_file(tmp_path: Path, minimal_config: str):
    """Test an empty input file given from the command line

    :param tmp_path: Path of temporary working dir returned by a pytest fixture.
    :param minimal_config: Fixture with minimal configuration file content.
    """
    empty_config_file = tmp_path / "config.conf"
    empty_config_file.write_text(minimal_config)

    empty_input_file = tmp_path / "empty.prn"
    empty_input_file.write_bytes(b"")

    processed_file = tmp_path / "escp2_1.pdf"
    cmdline_args = {
        # Need to use a _io.TextIOWrapper object like the one given by argparse
        "esc_prn": open(empty_input_file, encoding="utf8"),
        "config": empty_config_file,
        "output": processed_file,
    }

    # Do magic
    with pytest.raises(SystemExit):
        escapy_entry_point(**cmdline_args)


def test_choose_config_file(tmp_path: Path, minimal_config: str):
    """Test CONFIG_FILES, USER_CONFIG_FILE, EMBEDDED_CONFIG_FILE variables
    from :meth:`escapy.commons` and their usage during the program start phase.

    :param tmp_path: Path of temporary working dir returned by a pytest fixture.
    :param minimal_config: Fixture with minimal configuration file content.
    """
    # Block similar to the one found in escapy.commons
    config_file = Path("config.conf")
    user_config_file = tmp_path / "user" / config_file
    embedded_config_file = tmp_path / "embedded" / config_file
    config_files = [tmp_path / config_file, user_config_file]

    # Setup files
    for file in config_files + [embedded_config_file]:
        print("created file:", file)
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(minimal_config)

    with patch.multiple(
        "escapy.__main__",
        CONFIG_FILES=config_files,
        USER_CONFIG_FILE=user_config_file,
        EMBEDDED_CONFIG_FILE=embedded_config_file,
    ):
        # Expect the file passed as an argument from the cli
        found = choose_config_file(tmp_path / config_file)
        assert found == tmp_path / config_file

        # Expect the file in the current directory (CONFIG_FILE)
        found = choose_config_file(None)
        assert found == tmp_path / config_file

        # Delete the file in the current directory
        (tmp_path / config_file).unlink()
        # Expect the user file (USER_CONFIG_FILE)
        found = choose_config_file(None)
        assert found == user_config_file

        # Delete the user file
        user_config_file.unlink()
        # Expect the user file copied from the embedded file (EMBEDDED_CONFIG_FILE)
        found = choose_config_file(None)
        assert found == user_config_file

        # Test deletion of ALL files, that should not happen...
        with pytest.raises(FileNotFoundError):
            # Delete the user AND the embedded files
            user_config_file.unlink()
            embedded_config_file.unlink()
            # Expect the user file copied from the embedded file (EMBEDDED_CONFIG_FILE)
            _ = choose_config_file(None)

        # Test not existing input file from cli
        with pytest.raises(SystemExit):
            # Expect the user file copied from the embedded file (EMBEDDED_CONFIG_FILE)
            _ = choose_config_file(tmp_path / "xxx.conf")
