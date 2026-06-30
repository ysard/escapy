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
"""Printer profile related functions

Class: PrinterProfile
Functions:
    - load_printer_profile
    - get_printer_profile
"""

# Standard imports
from pathlib import Path
import configparser
from dataclasses import dataclass

# Custom imports
from reportlab.lib.colors import PCMYKColorSep

# Local imports
from escapy.commons import CONFIG_FILES, logger

LOGGER = logger()


@dataclass(slots=True)
class PrinterProfile:
    """Store various physical attributes defining a printer model"""

    name: str
    color_names: dict[int, str]
    RGB_colors: dict[int, str]
    CMYK_colors: dict[int, PCMYKColorSep]
    nozzle_offsets: dict[int, float | int]
    nozzle_offsets_monochrome: dict[int, float | int]


def load_printer_profile(config: configparser.ConfigParser, profile_dir: Path) -> None:
    """Read a printer profile file, check and set default values

    :param config: The current configuration that will be updated by the
        currently selected printer profile. The section `[printer]` and the
        `profile` key are used to load a specific profile.
    :param profile_dir: The directory from which the current configuration file
        has been read. The printer profiles are first searched for in this
        folder. Then they are searched in a `profiles` directory in the same
        directory, then in usual system directories.
    :raises: SystemExit: If the generic profile hasn't been found.
    """
    # First, search for profiles in the same folder as the currently used
    # configuration file;
    # Then, search for in standard folders.
    dirs = [profile_dir, profile_dir / "profiles"] + [
        file.parent / "profiles" for file in CONFIG_FILES
    ]

    profile_name = config.get("printer", "profile", fallback="generic")
    LOGGER.debug("Expect the printer profile: %s in %s", profile_name, dirs)

    # Always read the default profile first
    profile_path_found = config.read([d / "generic.conf" for d in dirs])
    if not profile_path_found:
        LOGGER.error("Couldn't find the 'generic' profile")
        raise SystemExit(1)
    if profile_name == "generic":
        return

    # More specific values override the previous ones
    profile_path_found = config.read([d / f"{profile_name}.conf" for d in dirs])
    if not profile_path_found:
        LOGGER.error("Printer profile was not found: %s", profile_name)
    else:
        LOGGER.debug("Use the printer profile at <%s>", profile_path_found[0])


def get_printer_profile(config: configparser.ConfigParser) -> PrinterProfile:
    """Build printer color profile from the given config

    Expected keys in each color section:

    - rgb: RGB color code (starting with a #);
    - cmyk: CMYK channels (4 coma separated values).

    Optional keys:

    - display: Human readable name;
    - offset: Nozzle position adjustement offset.

    :raises SystemExit: If required keys are not found.
    """
    color_names = {}
    RGB_colors = {}
    CMYK_colors = {}
    nozzle_offsets = {}
    nozzle_offsets_monochrome = {}

    if not config.has_section("colors"):
        LOGGER.error("colors section was not found!")
        raise SystemExit(1)

    colors_section = config["colors"]
    for color_id_str, logical_name in colors_section.items():

        section = f"color:{logical_name}"
        if not config.has_section(section):
            LOGGER.error(
                "Color <%s:%s> is not available in the profile!",
                color_id_str,
                logical_name,
            )
            raise SystemExit(1)

        color_id = int(color_id_str, 0)

        # Monochrome mode: search an eventual color definition
        mono = f"{section}:mono"
        if config.has_section(mono):
            offset = config.getint(mono, "offset", fallback=0)
            nozzle_offsets_monochrome[color_id] = offset / 180

        # Color mode
        display = config.get(
            section,
            "display",
            fallback=logical_name.replace("_", " ").title(),
        )

        offset = config.getint(section, "offset", fallback=0)

        try:
            cmyk = tuple(int(x.strip()) for x in config.get(section, "cmyk").split(","))
            rgb = config.get(section, "rgb")
        except configparser.NoOptionError as e:
            LOGGER.exception(e)
            raise SystemExit(1) from e
        except ValueError as e:
            LOGGER.error("Couldn't parse 'cmyk' values in section: '%s'", section)
            raise SystemExit(1) from e

        color_names[color_id] = display

        nozzle_offsets[color_id] = offset / 180

        CMYK_colors[color_id] = PCMYKColorSep(
            *cmyk,
            spotName=display.upper(),
        )

        RGB_colors[color_id] = rgb

    # Note: inherit all offsets from the color mode
    nozzle_offsets_monochrome = nozzle_offsets | nozzle_offsets_monochrome

    return PrinterProfile(
        name=config.get("printer", "profile", fallback="generic"),
        color_names=color_names,
        RGB_colors=RGB_colors,
        CMYK_colors=CMYK_colors,
        nozzle_offsets=nozzle_offsets,
        nozzle_offsets_monochrome=nozzle_offsets_monochrome,
    )
