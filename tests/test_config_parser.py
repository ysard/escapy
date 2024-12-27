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
"""Test config parser module"""

# Standard imports
import configparser

# Custom imports
import pytest

# Local imports
from escparser.commons import log_level, LOG_LEVEL, DIR_FONTS
from escparser.config_parser import parse_config, load_config


def default_config():
    """Get default settings for different sections of the expected config file"""
    misc_section = {
        "loglevel": LOG_LEVEL,
        "default_font_path": DIR_FONTS,
    }

    roman_section = {
        "path": DIR_FONTS,
        "fixed": "Courier",
        "proportional": "Times",
    }
    return misc_section, roman_section


@pytest.fixture()
def sample_config(request):
    """Fixture to parse config string and return initialised ConfigParser object

    :return: Parsed configuration
    :rtype: configparser.ConfigParser
    """
    config = configparser.ConfigParser()
    config.read_string(request.param)

    # Set default values
    # Default sections are expected from the given string
    yield parse_config(config)

    # Restore previous loglevel for further tests
    log_level("debug")


def test_empty_file():
    """Test empty config file"""
    sample_config = ""

    config = configparser.ConfigParser()
    config.read_string(sample_config)

    with pytest.raises(KeyError, match=r".*misc.*"):
        # Raises KeyError on not found section
        _ = parse_config(config)


def test_default_file():
    """Test default config file loading"""
    sample_config = load_config()
    misc_section, roman_section = default_config()

    # Transtype for easier debugging (original object has a different string rep)
    found_misc_section = dict(sample_config["misc"])
    found_roman_section = dict(sample_config["Roman"])

    assert misc_section == found_misc_section
    assert roman_section == found_roman_section


@pytest.mark.parametrize(
    "sample_config,expected_settings",
    [
        # Config with user settings vs expected parsed settings
        (
            # sample1:
            """
            [misc]
            loglevel=info
            default_font_path=/one_path/
            [Roman]
            fixed = FiraCode
            """,
            {
                "misc": {
                    "loglevel": "info",
                    "default_font_path": "/one_path/",
                },
                "Roman": {
                    "fixed": "FiraCode",
                    "proportional": "Times",  # default font is set
                },
                # Missing font sections must be added by default
                "Sans serif": {
                    "fixed": "Courier",
                    "proportional": "Times",
                },
            },
        ),
    ],
    ids=["sample1"],
    indirect=["sample_config"],  # Send sample_config val to the fixture
)
def test_specific_settings(sample_config, expected_settings):
    """Test user settings vs parsed ones"""
    for section, params in expected_settings.items():
        for param, value in params.items():
            assert (
                sample_config[section][param] == value
            ), f"Fault key: {section}:{param}"
