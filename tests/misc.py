"""Common commands, fixtures & functions used in tests"""
# Standard imports
import os
from pathlib import Path
import pytest

# Local imports
from .helpers.diff_pdf import is_similar_pdfs

# Test data path depends on the current package name
DIR_DATA = os.path.dirname(os.path.abspath(__file__)) + "/../test_data/"

esc_reset = b"\x1B\x40"  # ESC @
cancel_bold = b"\x1BF"  # ESC F
graphics_mode = b"\x1B(G\x01\x00\x01"  # ESC ( G
select_10cpi = b"\x1bP"  # ESC P
select_12cpi = b"\x1bM"  # ESC M
select_15cpi = b"\x1bg"  # ESC g
double_width = b"\x0e"  # SO
select_condensed_printing = b"\x0f"  # SI
unset_condensed_printing = b"\x12"  # DC2


@pytest.fixture
def format_databytes(request):
    """
    :param request: In the param attr: bytes | bytearray
    :type request: pytest._pytest.fixtures.SubRequest
    """
    databytes = esc_reset + request.param
    return databytes


def pdf_comparison(processed_file: Path):
    """Wrapper to compare two PDFs files

    In case of error, the wrong pdf and the diff file will be copied in /tmp/.

    :param processed_file: Test file Path object. Its name is used to make
        the comparison with an expected file with the same name, expected in
        the test_data directory.
    """
    #
    # Keep track of the generated file in /tmp in case of error
    backup_file = Path("/tmp/" + processed_file.name)
    backup_file.write_bytes(processed_file.read_bytes())

    ret = is_similar_pdfs(processed_file, Path(DIR_DATA + processed_file.name))
    assert ret, f"Problematic file is saved at <{backup_file}> for further study."
    # All is ok => delete the generated file
    backup_file.unlink()
