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
"""ESCParser entry point"""

# Standard imports
import argparse
from pathlib import Path

# Custom imports
from escparser import __version__
from escparser.config_parser import load_config
from escparser.fonts import setup_fonts
from escparser.parser import ESCParser
import escparser.commons as cm

LOGGER = cm.logger()


def escparser_entry_point(config_file=None, **kwargs):
    """The main routine."""
    LOGGER.info("Libreprinter start; %s", __version__)

    config = load_config(config_file=config_file)
    configured_fonts = setup_fonts(config)

    # Open input file
    esc_prn_file_content = kwargs["esc_prn_file"].read_bytes()
    if not esc_prn_file_content:
        LOGGER.error("File is empty!")

    ESCParser(
        esc_prn_file_content,
        available_fonts=configured_fonts,
    )


def args_to_params(args):
    """Return argparse namespace as a dict {variable name: value}"""
    return dict(vars(args).items())


def main():
    """Entry point and argument parser"""
    parser = argparse.ArgumentParser(
        prog="",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "esc_prn_file",
        help="ESC raw printer file.",
        type=Path
    )

    parser.add_argument(
        "-C",
        "--config_file",
        nargs="?",
        help="Configuration file to use.",
        default=cm.CONFIG_FILE,
        type=Path,
    )

    parser.add_argument(
        "-v", "--version", action="version", version=__version__
    )

    # Get program args and launch associated command
    args = parser.parse_args()

    params = args_to_params(args)
    # Quick check
    assert params["config_file"].exists(), \
        f"Configuration file <{params['config_file']}> not found!"

    # Do magic
    escparser_entry_point(**params)


if __name__ == "__main__":
    main()
