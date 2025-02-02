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
from pathlib import Path

# Custom imports
import pytest

# Local imports
from escapy.commons import (
    log_level,
    DIR_FONTS,
    USER_DEFINED_DB_FILE,
)
from escapy.config_parser import parse_config, load_config, build_parser_params


def default_config():
    """Get default settings for different sections of the expected config file"""
    misc_section = {
        "loglevel": "info",
        "default_font_path": DIR_FONTS,
        "page_size": "A4",
        "automatic_linefeed": "false",
        "single_sheets": "true",
        "renderer": "dots",
        "condensed_fallback": "auto",
    }

    roman_section = {
        "path": DIR_FONTS,
        "fixed": "Courier",
        "proportional": "Times",
    }

    userdef_section = {
        "database_filepath": USER_DEFINED_DB_FILE,
        # Default: image creation is disabled
        # "images_path": "",
    }
    return misc_section, roman_section, userdef_section


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


@pytest.fixture()
def tear_down():
    yield None

    # Restore previous loglevel for further tests
    log_level("debug")


def test_empty_file():
    """Test empty config file, will raise an exception"""
    config = configparser.ConfigParser()
    config.read_string("")

    with pytest.raises(KeyError, match=r".*misc.*"):
        # Raises KeyError on not found section
        _ = parse_config(config)


def test_default_file(tear_down):
    """Test the loading of the default config file embedded with the application"""
    sample_config = load_config()
    (
        expected_misc_section,
        expected_roman_section,
        expected_userdef_section,
    ) = default_config()

    # Transtype for easier debugging (original object has a different string rep)
    found_misc_section = dict(sample_config["misc"])
    found_roman_section = dict(sample_config["Roman"])
    found_sansserif_section = dict(sample_config["Sans serif"])
    found_userdef_section = dict(sample_config["UserDefinedCharacters"])

    assert found_misc_section == expected_misc_section
    assert found_roman_section == expected_roman_section
    assert found_sansserif_section == expected_roman_section
    assert found_userdef_section == expected_userdef_section


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
        (
            # sample10:
            """
            [misc]
            [UserDefinedCharacters]
            images_path = /usr/bin/xxx
            """
        ),
    ],
    ids=[""] * 11,
)
def test_erroneous_settings(sample_config, tear_down):
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
            loglevel=debug
            default_font_path=/one_path/
            [Roman]
            fixed = FiraCode
            [Courier]
            fixed = FiraCode
            """,
            {
                "misc": {
                    "loglevel": "debug",
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
                },
            },
        ),
    ],
    ids=["sample1"],
    indirect=["sample_config"],  # Send sample_config val to the fixture
)
def test_specific_settings(sample_config, expected_settings, tear_down):
    """Test user settings vs parsed ones (focused on font definition)

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
            renderer =
            condensed_fallback =
            [UserDefinedCharacters]
            database_filepath =
            images_path =
            """,
            {
                "pins": None,
                "printable_area_margins_mm": None,
                "page_size": (595.2755905511812, 841.8897637795277),
                "single_sheets": True,
                "automatic_linefeed": False,
                "dots_as_circles": True,
                "condensed_fallback": None,
                "userdef_db_filepath": USER_DEFINED_DB_FILE,
                "userdef_images_path": None,
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
            renderer = rectangles
            condensed_fallback = yes
            [UserDefinedCharacters]
            database_filepath = xxx.json
            images_path = /tmp/xxx/
            """,
            {
                "pins": 9,
                "printable_area_margins_mm": (6.35, 6.35, 6.35, 6.35),
                "page_size": (595.0, 841.0),
                "single_sheets": False,
                "automatic_linefeed": False,
                "dots_as_circles": False,
                "condensed_fallback": True,
                "userdef_db_filepath": "xxx.json",
                "userdef_images_path": "/tmp/xxx/",
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
            renderer = dots
            condensed_fallback = auto
            """,
            {
                "pins": 48,
                "printable_area_margins_mm": (6.0, 6.0, 6.0, 6.0),
                "page_size": (595.2755905511812, 841.8897637795277),
                "single_sheets": True,
                "automatic_linefeed": True,
                "dots_as_circles": True,
                "condensed_fallback": None,
                # Missing section defaults
                "userdef_db_filepath": USER_DEFINED_DB_FILE,
                "userdef_images_path": None,
            },
        ),
    ],
    ids=[""] * 3,
    indirect=["sample_config"],  # Send sample_config val to the fixture
)
def test_build_parser_params(sample_config, expected, tear_down):
    """Test legit settings verified by the configparser and prepared as kwargs for ESCParser

    .. seealso:: :meh:`build_parser_params`.
    """
    found = build_parser_params(sample_config)
    assert found == expected

    # Directory cleaning
    if dirpath := expected.get("userdef_images_path"):
        Path(dirpath).rmdir()
