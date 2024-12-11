# Standard imports
import os
from pathlib import Path
import pytest

# Custom imports
from reportlab.lib.pagesizes import A4
from reportlab.lib.pagesizes import landscape

# Local imports
from escparser.parser import ESCParser
from .misc import pdf_comparison

# Test data path depends on the current package name
DIR_DATA = os.path.dirname(os.path.abspath(__file__)) + "/../test_data/"

@pytest.mark.parametrize(
    "code_file, expected_pdf, args",
    [
        ("test_Graphics_invoice.CP850.prn", "test_Graphics_invoice.CP850.pdf", {"pins": None}),
        ("test2.KEYBCS2.prn", "test2.KEYBCS2.pdf", {"page_size": landscape(A4)}),
        ("Test2_badcommand.prn", "Test2_badcommand.pdf", {"pins": 9}),
        ("escp2_1.prn", "escp2_1.pdf", {}),

    ],
    ids=[
        "test_Graphics_invoice.CP850",
        "test2.KEYBCS2",
        "Test2_badcommand",
        "escp2_1"
    ],
)
def test_full_file_conversion(tmp_path: Path, code_file: str, expected_pdf: str, args: dict):
    """Convert ESC code to PDF files and check the result

    :param tmp_path: Path of temporary working dir returned by a pytest fixture.
    :param code_file: Filename of ESC code sent by a computer to a printer.
    :param expected_pdf: Filename of the expected PDF file.
    :param args: Tuple of arguments passed to the ESCParser object.
    """
    code = Path(DIR_DATA + code_file).read_bytes()

    processed_file = tmp_path / expected_pdf
    _ = ESCParser(code, output_file=str(processed_file), **args)

    pdf_comparison(processed_file)
