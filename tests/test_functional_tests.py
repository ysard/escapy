#  ESCParser is a software allowing to convert EPSON ESC/P, ESC/P2
#  printer control language files into PDF files.
#  Copyright (C) 2024  Ysard
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
# Standard imports
from pathlib import Path
import pytest

# Custom imports
from reportlab.lib.pagesizes import A4
from reportlab.lib.pagesizes import landscape

# Local imports
from escparser.parser import ESCParser
from escparser.__main__ import escparser_entry_point
from .misc import DIR_DATA, pdf_comparison


@pytest.mark.parametrize(
    "code_file, expected_pdf, args",
    [
        ("test_Graphics_invoice.CP850.prn", "test_Graphics_invoice.CP850.pdf", {"pins": None}),
        ("test2.KEYBCS2.prn", "test2.KEYBCS2.pdf", {"page_size": landscape(A4)}),
        ("Test2_badcommand.prn", "Test2_badcommand.pdf", {"pins": 9}),
        ("escp2_1.prn", "escp2_1.pdf", {}),
        ("escp2_1.prn", "escp2_1_9pins.pdf", {"pins": 9}),
    ],
    ids=[
        "test_Graphics_invoice.CP850",
        "test2.KEYBCS2",
        "Test2_badcommand",
        "escp2_1",
        "escp2_1_9pins",
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
        [Roman]
        fixed = FiraCode
        """


def test_argument_parser(tmp_path: Path, minimal_config: str):
    """Almost full test from the command line to the pdf generated

    :param tmp_path: Path of temporary working dir returned by a pytest fixture.
    :param minimal_config: Minimal configuration file content.
    """
    empty_config_file = tmp_path / "config.conf"
    empty_config_file.write_text(minimal_config)

    processed_file = tmp_path / "escp2_1.pdf"
    cmdline_args = {
        "esc_prn": Path(DIR_DATA + "escp2_1.prn"),
        "config": empty_config_file,
        "output": processed_file,
    }

    # Do magic
    escparser_entry_point(**cmdline_args)

    pdf_comparison(processed_file)


def test_empty_input_file(tmp_path: Path, minimal_config: str):
    """Test an empty input file given from the command line

    :param tmp_path: Path of temporary working dir returned by a pytest fixture.
    :param minimal_config: Minimal configuration file content.
    """
    empty_config_file = tmp_path / "config.conf"
    empty_config_file.write_text(minimal_config)

    empty_input_file = tmp_path / "empty.prn"
    empty_input_file.write_bytes(b"")

    processed_file = tmp_path / "escp2_1.pdf"
    cmdline_args = {
        "esc_prn": empty_input_file,
        "config": empty_config_file,
        "output": processed_file,
    }

    # Do magic
    with pytest.raises(SystemExit):
        escparser_entry_point(**cmdline_args)
