#  EscaPy is a software allowing to convert EPSON ESC/P, ESC/P2
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
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""Tests for printer profiles related functions"""

# Standard imports
import configparser

# Custom imports
import pytest
from reportlab.lib.colors import PCMYKColorSep

# Local imports
from escapy.printer_profile import (
    get_printer_profile,
    PrinterProfile,
)
from escapy.config_parser import load_config, debug_config_file
from escapy.commons import log_level

from .test_config_parser import tear_down
from .misc import default_printer_profile


@pytest.fixture()
def sample_profile(request):
    """Fixture to parse config string and return an initialised PrinterProfile object

    :return: Printer profile built from the given configuration string
    :rtype: Generator[PrinterProfile]
    """
    config = configparser.ConfigParser()
    config.read_string(request.param)

    yield get_printer_profile(config)


def test_default_file(tear_down):
    """Test the loading of the default config file embedded with the application

    We expect a section [colors] with color ids as keys and color names as values.

    :param tear_down: Fixture to restore the log level after the test is complete.
        (Since we load the general config via :meth:`load_config`, the default
        loglevel is applied and is not the same as in the test env).
    """
    sample_config = load_config()

    # For debugging purposes
    log_level("debug")
    debug_config_file(sample_config)

    # Test only color ids here...
    expected_color_ids = set(map(str, default_printer_profile.color_names.keys()))
    assert dict(sample_config["colors"]).keys() == expected_color_ids

    # In fine, the PrinterProfile object should be the same.
    printer_profile = get_printer_profile(sample_config)
    assert printer_profile == default_printer_profile


@pytest.mark.parametrize(
    "sample_config",
    [
        # Empty string
        """
        """,
        # Missing definition of color
        """
        [colors]
        0: black
        """,
        # Missing rgb
        """
        [colors]
        0: black
        
        [color:black]
        offset = 10
        cmyk = 0,0,0,100
        """,
        # Missing cmyk
        """
        [colors]
        0: black
        
        [color:black]
        offset = 10
        rgb = #000000
        """,
        # Wrong cmyk redaction
        """
        [colors]
        0: black

        [color:black]
        offset = 10
        rgb = #000000
        cmyk = 0,0,0,
        """,
    ],
    ids=[
        "empty_string",
        "missing_color",
        "missing_rgb",
        "missing_cmyk",
        "wrong_cmyk",
    ],
)
def test_erroneous_settings(sample_config):
    """Test settings that should raise a SystemExit exception with an error msg

    :param sample_config: Tested configuration string that will be parsed.
    """
    # PS: can't use the fixture here, the SystemExit will be captured by it
    # not by the context manager here...
    config = configparser.ConfigParser()
    config.read_string(sample_config)

    with pytest.raises(SystemExit) as pytest_wrapped_e:
        _ = get_printer_profile(config)
    assert pytest_wrapped_e.value.code == 1


@pytest.mark.parametrize(
    "sample_profile, expected",
    [
        # Config with user settings vs expected kwargs
        (
            """
            [colors]
            0 = black
            0x01 = magenta
            
            [color:black]
            offset = 10
            rgb = #000000
            cmyk = 0,0,0,100
            
            [color:black:mono]
            offset = 100
            rgb = #000000
            cmyk = 0,0,0,100
            
            [color:magenta]
            offset = 20
            rgb = #ff00ff
            cmyk = 0,100,0,0
            """,
            PrinterProfile(
                name="generic",
                color_names={0: "Black", 1: "Magenta"},
                RGB_colors={0: "#000000", 1: "#ff00ff"},
                CMYK_colors={
                    0: PCMYKColorSep(0, 0, 0, 100, spotName="BLACK"),
                    1: PCMYKColorSep(0, 100, 0, 0, spotName="MAGENTA"),
                },
                nozzle_offsets={0: 10 / 180, 1: 20 / 180},
                nozzle_offsets_monochrome={0: 100 / 180, 1: 20 / 180},
            ),
        ),
    ],
    ids=["full_config"],
    indirect=["sample_profile"],  # Send sample_profile val to the fixture
)
def test_get_printer_profile(sample_profile: PrinterProfile, expected: PrinterProfile):
    """Test the construction of PrinterProfile objects from the configuration"""
    print(sample_profile)
    assert sample_profile == expected
