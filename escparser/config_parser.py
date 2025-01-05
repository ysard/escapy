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
"""Load configuration file, check and set default values"""

# Standard imports
import configparser
from logging import DEBUG

# Local imports
from escparser.commons import (
    logger,
    log_level,
    CONFIG_FILE,
    LOG_LEVEL,
    DIR_FONTS,
    TYPEFACE_NAMES,
    PAGESIZE_MAPPING,
)

LOGGER = logger()


def load_config(config_file=CONFIG_FILE):
    """Load configuration file and set default settings

    :param config_file: Path of the configuration file to load.
        Default: CONFIG_FILE from commons module.
    :type config_file: Path
    :return: Configuration updated object.
    :rtype: configparser.ConfigParser
    """
    config = configparser.ConfigParser(allow_no_value=True)
    config.read(config_file)
    return parse_config(config)


def parse_config(config: configparser.ConfigParser):
    """Read config file, check and set default values

    .. note:: All values are of type string; they must be cast
        (with dedicated methods) if necessary.

        The syntax `if not xxx:` handles None and '' data retrieved from file.

    Defines default values for fixed & proportional fonts (Courier, Times).
    These fonts are embedded in ReportLab.

    :param config: Opened ConfigParser object
    :type config: configparser.ConfigParser
    :return: Processed ConfigParser object
    :rtype: configparser.ConfigParser
    """
    # rb = parser.getint('section', 'rb') if parser.has_option('section', 'rb') else None

    def to_tuple(config_str) -> str | None:
        """Get a tuple of values if the given param is not empty and not None"""
        return config_str.split(",") if config_str else ""

    def isfloat(string):
        """Return True if the str can be cast to float"""
        try:
            float(string)
            return True
        except ValueError:
            return False

    ## Misc section
    misc_section = config["misc"]
    loglevel = misc_section.get("loglevel")
    if not loglevel:
        misc_section["loglevel"] = LOG_LEVEL
    log_level(misc_section["loglevel"])


    default_font_path = misc_section.get("default_font_path")
    if not default_font_path:
        default_font_path = DIR_FONTS
        misc_section["default_font_path"] = default_font_path


    pins = misc_section.get("pins")
    if pins not in ("9", "24", "48", "", None):
        LOGGER.error("pins: The number of pins is not expected (%s).", pins)
        raise SystemExit


    printable_area_margins_mm = misc_section.get("printable_area_margins_mm")
    cleaned_data = to_tuple(printable_area_margins_mm)
    if printable_area_margins_mm:

        if len(cleaned_data) != 4 or not all(isfloat(i) for i in cleaned_data):
            LOGGER.error(
                "printable_area_margins_mm: 4 values are expected "
                "(top, bottom, left, right) (%s).",
                printable_area_margins_mm,
            )
            raise SystemExit


    automatic_linefeed = misc_section.get("automatic_linefeed")
    if not automatic_linefeed:
        misc_section["automatic_linefeed"] = "false"
    else:
        try:
            automatic_linefeed = misc_section.getboolean("automatic_linefeed")
        except ValueError as exc:
            LOGGER.error(
                "automatic_linefeed: expect false or true (%s)", automatic_linefeed
            )
            raise SystemExit from exc

    # page_size: We expect a default value A4 here
    page_size = misc_section.get("page_size")
    cleaned_data = to_tuple(page_size)
    print(cleaned_data)
    if page_size:
        if page_size not in PAGESIZE_MAPPING:
            if  len(cleaned_data) == 1:
                LOGGER.error(
                    "page_size: A known alias or 2 values are expected (width, height) (%s).",
                    page_size,
                )
                raise SystemExit

            elif len(cleaned_data) != 2 or not all(isfloat(i) for i in cleaned_data):
                LOGGER.error(
                    "page_size: 2 values are expected (width, height) (%s).",
                    page_size,
                )
                raise SystemExit
    else:
        misc_section["page_size"] = "A4"


    single_sheets = misc_section.get("single_sheets")
    if not single_sheets:
        misc_section["single_sheets"] = "true"
    else:
        try:
            single_sheets = misc_section.getboolean("single_sheets")
        except ValueError as exc:
            LOGGER.error("single_sheets: expect false or true (%s)", single_sheets)
            raise SystemExit from exc


    ## Fonts sections
    mandatory_typefaces = ("Roman", "Sans serif")
    for typeface in TYPEFACE_NAMES.values():
        # Create the section if not already defined
        if not config.has_section(typeface):
            if typeface not in mandatory_typefaces:
                continue
            config.add_section(typeface)
        font_section = config[typeface]

        path = font_section.get("path")
        if not path:
            font_section["path"] = default_font_path

        # Define default fallback fonts
        fixed_font = font_section.get("fixed")
        if not fixed_font:
            font_section["fixed"] = "Courier"

        proportional_font = font_section.get("proportional")
        if not proportional_font:
            font_section["proportional"] = "Times"

    debug_config_file(config)
    return config


def debug_config_file(config: configparser.ConfigParser):
    """Display sections, keys and values of config file

    :param config: Opened ConfigParser object
    :type config: configparser.ConfigParser
    """
    if LOGGER.level > DEBUG:
        return
    for section in config.sections():
        LOGGER.debug("[%s]", section)

        for key, value in config[section].items():
            LOGGER.debug("%s : %s", key, value)

        LOGGER.debug("")
