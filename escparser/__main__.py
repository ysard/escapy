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
"""EscaPy entry point"""

# Standard imports
import argparse
from pathlib import Path
import sys
import shutil

# Custom imports
from escparser import __version__
from escparser.config_parser import load_config, build_parser_params
from escparser.fonts import setup_fonts
from escparser.parser import ESCParser
import escparser.commons as cm
from escparser.commons import CONFIG_FILES, USER_CONFIG_FILE, EMBEDDED_CONFIG_FILE

LOGGER = cm.logger()


def choose_config_file(config_file: [Path | None]) -> Path:
    """Get an existing configuration file

    Search the config file in the current directory, then in `~/.local/share/escapy`.
    If none has been found: create a config file from the embedded one, in the
    user configuration folder and use it.
    The filename is defined in :meth:`escparser.commons.CONFIG_FILE`.

    :param config_file: Configuration file path from the cli. Can be None if the
        argument is not used.
    :return: A Path for a valid configuration file, ready to be loaded in the
        ConfigParser.
    """
    if isinstance(config_file, Path):
        # Config file from command line
        if not config_file.exists():
            LOGGER.critical(f"Configuration file <%s> not found!", config_file)
            raise SystemExit
        return config_file

    # Search the config file in the current directory, then in ~/.local/share/
    g = [path for path in CONFIG_FILES if path.exists()]
    if not g:
        # If none has been found: create the config file from the embedded one
        LOGGER.info("Initialize new default config at <%s>", USER_CONFIG_FILE)
        USER_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(EMBEDDED_CONFIG_FILE, USER_CONFIG_FILE)
        return USER_CONFIG_FILE
    else:
        # Use the first file found
        config_file = g[0]
        LOGGER.info("Use config at <%s>", config_file)
        return config_file


def escparser_entry_point(**kwargs):
    """The main routine."""
    # Open input file
    esc_prn_file_content = kwargs["esc_prn"].buffer.read()
    if not esc_prn_file_content:
        LOGGER.critical("Input file is empty!")
        raise SystemExit

    # Parse the config file and preload fonts search routines
    config = load_config(config_file=kwargs["config"])
    configured_fonts = setup_fonts(config)

    params = build_parser_params(config)
    params.update(kwargs)

    LOGGER.info("EscaPy start; %s", __version__)
    ESCParser(
        esc_prn_file_content,
        available_fonts=configured_fonts,
        output_file=kwargs["output"],
        **params,
    )


def args_to_params(args):  # pragma: no cover
    """Return argparse namespace as a dict {variable name: value}"""
    return dict(vars(args).items())


def main():  # pragma: no cover
    """Entry point and argument parser"""
    parser = argparse.ArgumentParser(
        prog="",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "esc_prn",
        help="ESC raw printer file. - to read from stdin.",
        type=argparse.FileType("r"),
        default=sys.stdin
    )

    parser.add_argument(
        "--pins",
        nargs="?",
        help="Number of needles of the print head (9, 24, 48). "
            "Leave it unset for ESCP2 modern printers. (default: unset)",
        default=argparse.SUPPRESS,  # Absent by default (handled later)
        type=int,
    )

    parser.add_argument(
        "--single_sheets",
        help="Single-sheets or continuous paper. (default: single-sheets)",
        default=argparse.SUPPRESS,  # Absent by default (handled later)
        action=argparse.BooleanOptionalAction
    )

    parser.add_argument(
        "-o",
        "--output",
        help="PDF output file. - to write on stdout.",
        type=argparse.FileType("w"),
        nargs="?",
        default="output.pdf",
    )

    parser.add_argument(
        "-c",
        "--config",
        nargs="?",
        help="Configuration file to use. "
            "(default: ./escapy.conf, ~/.local/share/escapy/escapy.conf)",
        default=argparse.SUPPRESS,  # Absent by default (handled later)
        type=Path,
    )

    parser.add_argument(
        "-db",
        "--userdef_db_filepath",
        nargs="?",
        help="Mappings between user-defined chararacter codes and unicode. "
            "(default: ./user_defined_mapping.json)",
        default=argparse.SUPPRESS,  # Absent by default (handled later)
        type=Path,
    )

    parser.add_argument(
        "-v", "--version", action="version", version=__version__
    )

    # Get program args and launch associated command
    args = parser.parse_args()

    params = args_to_params(args)

    # Handle configuration file
    params["config"] = choose_config_file(params.get("config"))

    # Do magic
    escparser_entry_point(**params)


if __name__ == "__main__":  # pragma: no cover
    main()
