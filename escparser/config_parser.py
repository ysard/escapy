#  EscaPy is a software allowing to convert EPSON ESC/P, ESC/P2
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
from pathlib import Path
import configparser
from logging import DEBUG

# Local imports
from escparser.commons import (
    logger,
    log_level,
    EMBEDDED_CONFIG_FILE,
    LOG_LEVEL,
    DIR_FONTS,
    TYPEFACE_NAMES,
    PAGESIZE_MAPPING,
    USER_DEFINED_DB_FILE,
)

LOGGER = logger()


def load_config(config_file=EMBEDDED_CONFIG_FILE):
    """Load configuration file and set default settings

    :key config_file: Path of the configuration file to load.
        Default: EMBEDDED_CONFIG_FILE from commons module.
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

    Defines default values for fixed & proportional font versions, respectively
    Courier & Times; these fonts are embedded in ReportLab.
    For not mandatory typefaces, each version can be left empty to explicitely
    mark it as not available.

    Roman & Sans serif sections are mandatory and created if not in the config file.

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


    renderer = misc_section.get("renderer")
    if renderer not in ("dots", "rectangles"):
        misc_section["renderer"] = "dots"


    ## User defined characters section
    if not config.has_section("UserDefinedCharacters"):
        config.add_section("UserDefinedCharacters")

    ud_section = config["UserDefinedCharacters"]
    if not ud_section.get("database_filepath"):
        ud_section["database_filepath"] = USER_DEFINED_DB_FILE
    # Default: images path export is disabled (if not defined or empty)
    # If defined, the directory is created.
    images_path = ud_section.get("images_path")
    if images_path and not Path(images_path).exists():
        try:
            Path(images_path).mkdir(exist_ok=True)
        except Exception as exc:
            LOGGER.error(
                "UserDefinedCharacters: error accessing images_path (%s)",
                images_path
            )
            raise SystemExit from exc


    ## Fonts sections
    mandatory_typefaces = ("Roman", "Sans serif")
    for typeface in TYPEFACE_NAMES.values():
        is_mandatory = typeface in mandatory_typefaces
        # Create the section if not already defined
        if not config.has_section(typeface):
            if not is_mandatory:
                continue
            config.add_section(typeface)
        font_section = config[typeface]

        path = font_section.get("path")
        if not path:
            font_section["path"] = default_font_path

        # Define default fallback fonts
        # For not mandatory typefaces, each version can be left empty to explicitely
        # mark it as not available.
        fixed_font = font_section.get("fixed")
        if not fixed_font:
            font_section["fixed"] = "Courier" if is_mandatory else ""

        proportional_font = font_section.get("proportional")
        if not proportional_font:
            font_section["proportional"] = "Times" if is_mandatory else ""

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


def build_parser_params(config) -> dict:
    """Get dict of params that match the kwargs of ESCParser object.

    :param config: Configuration object.
    :type config: configparser.ConfigParser
    """
    def to_tuple(config_str) -> tuple[float] | None:
        """Get a tuple of numeric values if the given param is not empty and not None"""
        return tuple(map(float, config_str.split(","))) if config_str else None

    misc_section = config["misc"]
    pins = int(pins) if (pins := misc_section.get("pins")) else None
    printable_area_margins_mm = to_tuple(misc_section.get("printable_area_margins_mm"))
    automatic_linefeed = misc_section.getboolean("automatic_linefeed", False)
    page_size = (
        to_tuple(page_size)
        if (page_size := misc_section["page_size"]) not in PAGESIZE_MAPPING
        else PAGESIZE_MAPPING[page_size]
    )
    single_sheets = misc_section.getboolean("single_sheets", True)
    dots_as_circles = misc_section.get("renderer") == "dots"

    # Default: images path export is disabled (if not defined or empty)
    ud_section = config["UserDefinedCharacters"]
    images_path = ud_section.get("images_path")
    userdef_images_path = None if not images_path else images_path

    return {
        "pins": pins,
        "printable_area_margins_mm": printable_area_margins_mm,
        "automatic_linefeed": automatic_linefeed,
        "page_size": page_size,
        "single_sheets": single_sheets,
        "dots_as_circles": dots_as_circles,
        "userdef_db_filepath": ud_section["database_filepath"],
        "userdef_images_path": userdef_images_path,
    }
