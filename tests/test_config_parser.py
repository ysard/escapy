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
"""Test config parser module"""

# Standard imports
import configparser

# Custom imports
import pytest

# Local imports
from escparser.__main__ import build_parser_params
from escparser.commons import log_level, LOG_LEVEL, DIR_FONTS
from escparser.config_parser import parse_config, load_config


def default_config():
    """Get default settings for different sections of the expected config file"""
    misc_section = {
        "loglevel": LOG_LEVEL,
        "default_font_path": DIR_FONTS,
        "page_size": "A4",
        "automatic_linefeed": "false",
        "single_sheets": "true",
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
    """Test the loading of the default config file embedded with the application"""
    sample_config = load_config()
    expected_misc_section, expected_roman_section = default_config()

    # Transtype for easier debugging (original object has a different string rep)
    found_misc_section = dict(sample_config["misc"])
    found_roman_section = dict(sample_config["Roman"])
    found_sansserif_section = dict(sample_config["Sans serif"])

    assert found_misc_section == expected_misc_section
    assert found_roman_section == expected_roman_section
    assert found_sansserif_section == expected_roman_section


@pytest.mark.parametrize(
    "sample_config",
    [
        # Configs that will raise a SystemExit
        (
            # sample0:
            """
            [misc]
            pins = 472
            """
        ),
        (
            # sample1:
            """
            [misc]
            pins = aaa
            """
        ),
        (
            # sample2:
            """
            [misc]
            printable_area_margins_mm = aaa
            """
        ),
        (
            # sample3:
            """
            [misc]
            printable_area_margins_mm = 2, 3, 4
            """
        ),
        (
            # sample4:
            """
            [misc]
            printable_area_margins_mm = 1.0, 2.0, 3.0, a.b
            """
        ),
        (
            # sample5:
            """
            [misc]
            page_size = A30
            """
        ),
        (
            # sample6:
            """
            [misc]
            page_size = 3.0
            """
        ),
        (
            # sample7:
            """
            [misc]
            page_size = a, b
            """
        ),
        (
            # sample8:
            """
            [misc]
            single_sheets = xxx
            """
        ),
        (
            # sample9:
            """
            [misc]
            automatic_linefeed = xxx
            """
        ),
    ],
    ids=[""] * 10,
)
def test_erroneous_settings(sample_config):
    """Test settings that should raise a SystemExit exception with an error msg

    :param sample_config: Tested configuration string that will be parsed.
    """
    # PS: can't use the fixture here, the SystemExit will be captured by it
    # not by the context manager here...
    config = configparser.ConfigParser()
    config.read_string(sample_config)

    with pytest.raises(SystemExit):
        _ = parse_config(config)


@pytest.mark.parametrize(
    "sample_config, expected_settings",
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
            [Courier]
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
                # For not mandatory typefaces, variants can be left empty
                "Courier": {
                    "fixed": "FiraCode",
                    "proportional": "",
                }
            },
        ),
    ],
    ids=["sample1"],
    indirect=["sample_config"],  # Send sample_config val to the fixture
)
def test_specific_settings(sample_config, expected_settings):
    """Test user settings vs parsed ones

    .. note:: Roman & Sans serif sections are mandatory and created if not in the
        config file.
    """
    for section, params in expected_settings.items():
        for param, value in params.items():
            assert (
                sample_config[section][param] == value
            ), f"Fault key: {section}:{param}"


@pytest.mark.parametrize(
    "sample_config, expected",
    [
        # Config with user settings vs expected kwargs
        # All settings have an empty string value
        (
            """
            [misc]
            loglevel =
            pins =
            printable_area_margins_mm =
            page_size =
            single_sheets =
            automatic_linefeed =
            """,
            {
                "pins": None,
                "printable_area_margins_mm": None,
                "page_size": (595.2755905511812, 841.8897637795277),
                "single_sheets": True,
                "automatic_linefeed": False,
            },
        ),
        # floats for printable_area_margins_mm & page_size
        (
            """
            [misc]
            loglevel = warning
            pins = 9
            printable_area_margins_mm = 6.35, 6.35, 6.35, 6.35
            page_size = 595.0,841.0
            single_sheets = false
            automatic_linefeed = false
            """,
            {
                "pins": 9,
                "printable_area_margins_mm": (6.35, 6.35, 6.35, 6.35),
                "page_size": (595.0, 841.0),
                "single_sheets": False,
                "automatic_linefeed": False,
            },
        ),
        # ints for printable_area_margins_mm, alias for page_size
        (
            """
            [misc]
            pins = 48
            printable_area_margins_mm = 6, 6, 6, 6
            page_size = A4
            single_sheets = true
            automatic_linefeed = true
            """,
            {
                "pins": 48,
                "printable_area_margins_mm": (6.0, 6.0, 6.0, 6.0),
                "page_size": (595.2755905511812, 841.8897637795277),
                "single_sheets": True,
                "automatic_linefeed": True,
            },
        ),
    ],
    ids=[""] * 3,
    indirect=["sample_config"],  # Send sample_config val to the fixture
)
def test_build_parser_params(sample_config, expected):
    """Test legit settings verified by the configparser and prepared as kwargs for ESCParser

    .. seealso:: :meh:`build_parser_params`.
    """
    found = build_parser_params(sample_config)
    assert found == expected
