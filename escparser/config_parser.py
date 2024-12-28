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
    typeface_names,
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
    config = configparser.ConfigParser()
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

    ## Fonts sections
    for typeface in typeface_names.values():
        # Create the section if not already defined
        if not config.has_section(typeface):
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
