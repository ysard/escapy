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


def escparser_entry_point(**kwargs):
    """The main routine."""
    LOGGER.info("Libreprinter start; %s", __version__)

    # Open input file
    esc_prn_file_content = kwargs["esc_prn"].read_bytes()
    if not esc_prn_file_content:
        LOGGER.error("File is empty!")
        raise SystemExit

    # Parse the config file and preload fonts search routines
    config = load_config(config_file=kwargs["config"])
    configured_fonts = setup_fonts(config)

    ESCParser(
        esc_prn_file_content,
        available_fonts=configured_fonts,
        output_file=kwargs["output"],
        **build_parser_params(config),
    )


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
        if (page_size := misc_section["page_size"]) not in cm.PAGESIZE_MAPPING
        else cm.PAGESIZE_MAPPING[page_size]
    )
    single_sheets = misc_section.getboolean("single_sheets", True)

    return {
        "pins": pins,
        "printable_area_margins_mm": printable_area_margins_mm,
        "automatic_linefeed": automatic_linefeed,
        "page_size": page_size,
        "single_sheets": single_sheets,
    }


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
        help="ESC raw printer file.",
        type=Path
    )

    parser.add_argument(
        "-o",
        "--output",
        help="PDF output file.",
        type=Path,
        nargs="?",
        default=Path("./output.pdf"),
    )

    parser.add_argument(
        "-c",
        "--config",
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
    assert params["config"].exists(), \
        f"Configuration file <{params['config']}> not found!"

    # Do magic
    escparser_entry_point(**params)


if __name__ == "__main__":  # pragma: no cover
    main()
