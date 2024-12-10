"""Common commands, fixtures & functions used in tests"""
# Standard imports
import pytest

esc_reset = b"\x1B\x40" # ESC @
cancel_bold = b"\x1BF" # ESC F
graphics_mode = b"\x1B(G\x01\x00\x01" # ESC ( G

@pytest.fixture
def format_databytes(request):
    """
    :param request: In the param attr: bytes | bytearray
    :type request: pytest._pytest.fixtures.SubRequest
    """
    databytes = esc_reset + request.param
    return databytes
