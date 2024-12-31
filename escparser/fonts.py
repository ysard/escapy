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
"""Font search & runtime preconfiguration"""
# Standard imports
import itertools as it
from operator import itemgetter
from pathlib import Path
import configparser
from collections import defaultdict
from functools import partial, lru_cache

# Custom imports
from PIL import ImageFont

# Local imports
from escparser.commons import logger, TYPEFACE_NAMES, DIR_FONTS

LOGGER = logger()
STRETCH_DICT = {
    "ultracondensed": 100,
    "extracondensed": 200,
    "condensed": 300,
    "semicondensed": 400,
    "normal": 500,
}
WEIGHT_DICT = {
    "ultralight": 100,
    "thin": 100,
    "extralight": 200,
    "light": 300,
    "normal": 400,
    "regular": 400,
    "book": 400,
    "retina": 450,
    "medium": 500,
    "roman": 500,
    "semibold": 600,
    "demibold": 600,
    "demi": 600,
    "bold": 700,
    "heavy": 800,
    "extrabold": 800,
    "black": 900,
}


def rptlab_times(condensed: bool, italic: bool, bold: bool) -> str:
    """Configure internal reportlab fallback font (proportional)"""
    return (
        f"Times-{'Bold' if bold else ''}{'Italic' if italic else ''}"
        if bold or italic
        else "Times-Roman"
    )


def rptlab_courier(condensed: bool, italic: bool, bold: bool) -> str:
    """Configure internal reportlab fallback font (fixed)"""
    return (
        f"Courier-{'Bold' if bold else ''}{'Oblique' if italic else ''}"
        if any((bold, italic))
        else "Courier"
    )


def setup_fonts(config: configparser.ConfigParser) -> dict:
    """Build a structure that stores preconfigured methods to find fonts
     on the system according to dynamic styles in use.

    Structure example::

        {
            typeface_id: {
                fixed: Callable,
                proportional: None,
            },
        }

    :param config: Opened ConfigParser object
    :type config: configparser.ConfigParser
    :return: Dict of typefaces ids as keys.
        Values are dicts with always 2 keys: `fixed` & `proportional`.
        Their values are None or a callable choosen for an optimal font search.
    """
    typefaces_config = defaultdict(dict)
    for typeface_id, typeface in TYPEFACE_NAMES.items():
        path = config[typeface]["path"]
        typeface_config = {}
        typefaces_config[typeface_id] = typeface_config
        # Define the 2 default (and mandatory) font types
        # /!\ FOR NOW no None value is allowed
        for field in ("fixed", "proportional"):
            fontname = config[typeface][field]

            if fontname == "Times":
                func = rptlab_times
            elif fontname == "Courier":
                func = rptlab_courier
            else:
                # Preconfigure the search method, the styles are the only
                # remaining arguments that are filled up dynamically at runtime
                func = partial(find_font, fontname, path=path)

            typeface_config[field] = func

    return dict(typefaces_config)


@lru_cache
def find_font(
    name, condensed, italic, bold, best=True, path=DIR_FONTS
) -> list[Path] | Path | None:
    """Find the path to the font file most closely matching the given font properties

    Perform a nearest neighbor search inspired from:

        - https://www.w3.org/TR/CSS21/fonts.html#algorithm
        - https://matplotlib.org/stable/api/font_manager_api.html#matplotlib.font_manager.findfont

    ... but improved for the stretch font attribute and with more complete lists
    of stretch and weight values.

    :param name: Use the given name as a pattern to match the font filename
        found in `path` kwarg.
    :param condensed: Search condensed font.
    :param italic: Search italic or oblique font.
    :param bold: Search bold font.
    :key best: If True return only the best font path, otherwise return multiple Paths.
    :key path: (Optional) Path where the fonts are recursively searched
        (default: See :meth:`DIR_FONTS`).
    :type name: str
    :type condensed: bool
    :type italic: bool
    :type bold: bool
    :type best: bool
    :type path: str
    :return: A unique Path object or a list of Paths if best kwarg is False.
        In this last case, Paths are sorted by their score (best first).
        Return None if no font has been found.
    """
    # def clean_font_name(font_name: str):
    #     return font_name.translate(str.maketrans({"_": "", "-": "", " ": ""}))

    searched_condensed = 300 if condensed else 500
    searched_italic = 500 if italic else 0
    searched_bold = 700 if bold else 400

    scored_paths = []
    for filepath in it.chain(
        Path(path).rglob(f"{name}*.ttf"), Path(path).rglob(f"{name}*.otf")
    ):
        try:
            font = ImageFont.truetype(str(filepath))
        except OSError:  # pragma: no cover
            LOGGER.error("Error while opening <%s>", filepath)
            continue
        font_family, styles = font.getname()

        # Filter unwanted font names
        # Assume that the searched name doesn't have spaces and is similar
        # to the font family name stored in the font metadata.
        # if clean_font_name(font_family) != clean_font_name(name):
        #     continue

        styles = frozenset(styles.lower().replace("-", "").split())

        # Extract styles from the current font
        stretch_found = STRETCH_DICT.keys() & styles
        stretch_found = None if not stretch_found else stretch_found.pop()

        weight_found = WEIGHT_DICT.keys() & styles
        weight_found = None if not weight_found else weight_found.pop()

        italic_found = 500 if ({"italic", "oblique"} & styles) else 0

        s_score = abs(STRETCH_DICT.get(stretch_found, 500) - searched_condensed)
        w_score = abs(WEIGHT_DICT.get(weight_found, 400) - searched_bold)
        i_score = abs(italic_found - searched_italic)
        score = s_score + w_score + i_score

        LOGGER.debug("Current font tested: %s", filepath)
        # LOGGER.debug("Styles: %s", styles)
        LOGGER.debug(
            "Scores: stretch:%d, weight:%d, italic:%d = %d",
            s_score,
            w_score,
            i_score,
            score,
        )

        if score == 0:
            # Full match
            return filepath if best else [filepath]
        if score > 900:
            # Cutoff
            continue

        scored_paths.append((filepath, score))

    if not scored_paths:
        LOGGER.error("No font found!")
        return
    # Sort by scores, get rid of scores
    paths = list(zip(*sorted(scored_paths, key=itemgetter(1))))[0]
    if best:
        return paths[0]
    return paths
