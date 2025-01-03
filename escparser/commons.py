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
"""Logger settings and project constants"""

# Standard imports
from logging.handlers import RotatingFileHandler
import logging
import datetime as dt
import tempfile

# Custom imports
from reportlab.lib import pagesizes


# Paths
DIR_LOGS = tempfile.gettempdir() + "/"
CONFIG_FILE = "./escparser.conf"
DIR_FONTS = "/usr/share/fonts/truetype/"

# Page sizes should be in points (1/72 inch)
PAGESIZE_MAPPING = {
    "US-12": (597.6, 864.0),
    "L-US-12": (864.0, 597.6),
    "F-12": (597.6, 864.0),
    "ANSI-4": (612.0, 792.0),
    "L-ANSI-4": (792.0, 612.0),
    "P-24": (1728.0, 2592.0),  # Plotter 24" x 36"
    "P-36": (2592.0, 3024.0),  # Plotter 36" x 42"
}
IMPORTED_PAPERSIZES = {
    name: paper_size
    for name, paper_size in vars(pagesizes).items()
    if name[0].isupper()
}
IMPORTED_LANDSCAPE_PAPERSIZES = {
    "L-" + name: pagesizes.landscape(paper_size)
    for name, paper_size in IMPORTED_PAPERSIZES.items()
}

PAGESIZE_MAPPING |= IMPORTED_PAPERSIZES | IMPORTED_LANDSCAPE_PAPERSIZES

# Typefaces / fonts
TYPEFACE_NAMES = {
    0: "Roman",  # Times New Roman
    1: "Sans serif",  # /usr/share/fonts/truetype/freefont/FreeSans*
    2: "Courier",
    3: "Prestige",  # https://en.wikipedia.org/wiki/Prestige_Elite
    4: "Script",
    5: "OCR-B",
    6: "OCR-A",
    7: "Orator",
    8: "Orator-S",
    9: "Script C",
    10: "Roman T",
    11: "Sans serif H",
    30: "SV Busaba",
    31: "SV Jittra",
}

# Character tables / encodings
RAM_CHARACTERS_TABLE = "user_defined"

CHARACTER_TABLENAMES_MAPPING = {
    (0, 0): "Italic",
    (1, 0): "PC437 (US)",
    (1, 16): "PC437 Greek",
    (2, 0): "PC932 (Japanese)",
    (3, 0): "PC850 (Multilingual)",
    (4, 0): "PC851 (Greek)",
    (5, 0): "PC853 (Turkish)",
    (6, 0): "PC855 (Cyrillic)",
    (7, 0): "PC860 (Portugal)",
    (8, 0): "PC863 (Canada-French)",
    (9, 0): "PC865 (Norway)",
    (10, 0): "PC852 (East Europe)",
    (11, 0): "PC857 (Turkish)",
    (12, 0): "PC862 (Hebrew)",
    (13, 0): "PC864 (Arabic)",
    (13, 32): "PC AR864",
    (14, 0): "PC866 (Russian)",
    (14, 16): "(Bulgarian ASCII****)",
    (14, 32): "PC866 LAT. (Latvian)",
    (15, 0): "PC869 (Greek)",
    (16, 0): "USSR GOST (Russian)",
    (17, 0): "ECMA-94-1",
    (18, 0): "KU42 (K.U. Thai)",
    (19, 0): "TIS11 (TS 988 Thai)",
    (20, 0): "TIS18 (GENERAL Thai)",
    (21, 0): "TIS17 (SIC STD. Thai)",
    (22, 0): "TIS13 (IBM STD. Thai)",
    (23, 0): "TIS16 (SIC OLD Thai)",
    (24, 0): "PC861 (Iceland)",
    (25, 0): "BRASCII",
    (26, 0): "Abicomp",
    (27, 0): "MAZOWIA (Poland)",
    (28, 0): "Code MJK (CSFR)",
    (29, 7): "ISO8859-7 (Latin/Greek)",
    (29, 16): "ISO8859-1 (Latin 1)",
    (30, 0): "TSM/WIN (Thai system manager)",
    (31, 0): "ISO Latin 1T (Turkish)",
    (32, 0): "Bulgaria",
    (33, 0): "Hebrew 7",
    (34, 0): "Hebrew 8",
    (35, 0): "Roman 8",
    (36, 0): "PC774 (Lithuania)",
    (37, 0): "Estonia (Estonia)",
    (38, 0): "ISCII",
    (39, 0): "PC-ISCII",
    (40, 0): "PC APTEC",
    (41, 0): "PC708",
    (42, 0): "PC720",
    (112, 0): "OCR-B",
    (127, 1): "ISO Latin 1",
    (127, 2): "ISO 8859-2 (ISO Latin 2)",
    (127, 7): "ISO Latin 7 (Greek)",
}

# Codecs mapping
CHARACTER_TABLE_MAPPING = {
    (0, 0): "italic",  # Not existing code page but special processing; see binary_blob()
    (1, 0): "cp437",
    (1, 16): "cp737",
    (2, 0): "cp932",
    (3, 0): "cp850",
    (4, 0): None,  # "PC851 (Greek)",  # Superseeded by cp869
    (5, 0): None,  # "PC853 (Turkish)", # more complete than https://en.wikipedia.org/wiki/Code_page_853
    (6, 0): "cp855",
    (7, 0): "cp860",
    (8, 0): "cp863",
    (9, 0): "cp865",
    (10, 0): "cp852",  # Latin-2 Central European languages
    (11, 0): "cp857",
    (12, 0): "cp862",
    (13, 0): "cp864",
    (13, 32): None,  # "PC AR864",
    (14, 0): "cp866",
    (14, 16): None,  # "(Bulgarian ASCII****)",
    (14, 32): None,  # "PC866 LAT. (Latvian)", # code page 3012, https://en.wikipedia.org/wiki/Code_page_866#Latvian_variant
    (15, 0): "cp869",
    (16, 0): None,  # "USSR GOST (Russian)",
    (17, 0): None,  # "ECMA-94-1",
    (18, 0): "iso8859_11", #KU42 (K.U. Thai)", # https://en.wikipedia.org/wiki/ISO/IEC_8859-11#Vendor_extensions
    (19, 0): None,  # "TIS11 (TS 988 Thai)",
    (20, 0): None,  # "TIS18 (GENERAL Thai)",
    (21, 0): None,  # "TIS17 (SIC STD. Thai)",
    (22, 0): None,  # "TIS13 (IBM STD. Thai)",
    (23, 0): None,  # "TIS16 (SIC OLD Thai)",
    (24, 0): "cp861",
    (25, 0): "brascii",  # https://en.wikipedia.org/wiki/BraSCII almost 8859-1 except 2 chars
    (26, 0): None,  # "Abicomp",
    (27, 0): None,  # "MAZOWIA (Poland)",
    (28, 0): None,  # "Code MJK (CSFR)",
    (29, 7): "iso8859_7",
    (29, 16): "latin_1",
    (30, 0): None,  # "TSM/WIN (Thai system manager)",
    (31, 0): "iso8859_9",
    (32, 0): None,  # "Bulgaria",
    (33, 0): None,  # "Hebrew 7",
    (34, 0): None,  # "Hebrew 8",
    (35, 0): "hp_roman8",  # https://github.com/python/cpython/blob/main/Lib/encodings/hp_roman8.py
    (36, 0): None,  # "PC774 (Lithuania)", # https://en.wikipedia.org/wiki/Code_page_1118
    (37, 0): None,  # "Estonia (Estonia)",
    (38, 0): None,  # "ISCII", # https://en.wikipedia.org/wiki/Indian_Script_Code_for_Information_Interchange
    (39, 0): None,  # "PC-ISCII",
    (40, 0): None,  # "PC APTEC", # cp715
    (41, 0): None,  # "PC708", # https://en.wikipedia.org/wiki/Code_page_708
    (42, 0): "cp720",
    (112, 0): None,  # "OCR-B", # code page 877 https://en.wikipedia.org/wiki/OCR-B
    (127, 1): "latin_1",
    (127, 2): "iso8859_2",
    (127, 7): "iso8859_7",
}

LEFT_TO_RIGHT_LANGUAGES = ("cp720", "cp862")

# set of up to 12 particular characters that corresponds to symbols used
# in various countries
CHARSET_MAPPING = {
    0 : "us",  # "USA",
    1 : "fr",  # "France",
    2 : "de",  # "Germany",
    3 : "uk",  # "United Kingdom",
    4 : "dk1", # "Denmark I",
    5 : "se",  # "Sweden",
    6 : "it",  # "Italy",
    7 : "es1", # "Spain I",
    8 : "jp",  # "Japan (English)",
    9 : "no",  # "Norway",
    10: "dk2", # "Denmark II",
    11: "es2", # "Spain II",
    12: "sa",  # "Latin America",
    13: "kr",  # "Korea",
    64: "legal",  # "Legal",
}

INTERNATIONAL_CHARSETS = {
    0: {
        35: "#",
        36: "$",
        64: "@",
        91: "[",
        92: "\\",
        93: "]",
        94: "^",
        96: "`",
        123: "{",
        124: "|",
        125: "}",
        126: "~",
    },
    1: {
        35: "#",
        36: "$",
        64: "à",
        91: "°",
        92: "ç",
        93: "§",
        94: "^",
        96: "`",
        123: "é",
        124: "ù",
        125: "è",
        126: "¨",
    },
    2: {
        35: "#",
        36: "$",
        64: "§",
        91: "Ä",
        92: "Ö",
        93: "Ü",
        94: "^",
        96: "`",
        123: "ä",
        124: "ö",
        125: "ü",
        126: "ß",
    },
    3: {
        35: "£",
        36: "$",
        64: "@",
        91: "[",
        92: "\\",
        93: "]",
        94: "^",
        96: "`",
        123: "{",
        124: "|",
        125: "}",
        126: "~",
    },
    4: {
        35: "#",
        36: "$",
        64: "@",
        91: "Æ",
        92: "Ø",
        93: "Å",
        94: "^",
        96: "`",
        123: "æ",
        124: "ø",
        125: "å",
        126: "~",
    },
    5: {
        35: "#",
        36: "¤",
        64: "É",
        91: "Ä",
        92: "Ö",
        93: "Å",
        94: "Ü",
        96: "é",
        123: "ä",
        124: "ö",
        125: "å",
        126: "ü",
    },
    6: {
        35: "#",
        36: "$",
        64: "@",
        91: "°",
        92: "\\",
        93: "é",
        94: "^",
        96: "ù",
        123: "à",
        124: "ò",
        125: "è",
        126: "ì",
    },
    7: {
        35: "₧",  # 20a7 -> PESETA SIGN (Currency symbol)
        36: "$",
        64: "@",
        91: "¡",
        92: "Ñ",
        93: "¿",
        94: "^",
        96: "`",
        123: "¨",
        124: "ñ",
        125: "}",
        126: "~",
    },
    8: {
        35: "#",
        36: "$",
        64: "@",
        91: "[",
        92: "¥",
        93: "]",
        94: "^",
        96: "`",
        123: "{",
        124: "|",
        125: "}",
        126: "~",
    },
    9: {
        35: "#",
        36: "¤",
        64: "É",
        91: "Æ",
        92: "Ø",
        93: "Å",
        94: "Ü",
        96: "é",
        123: "æ",
        124: "ø",
        125: "å",
        126: "ü",
    },
    10: {
        35: "#",
        36: "$",
        64: "É",
        91: "Æ",
        92: "Ø",
        93: "Å",
        94: "Ü",
        96: "é",
        123: "æ",
        124: "ø",
        125: "å",
        126: "ü",
    },
    11: {
        35: "#",
        36: "$",
        64: "á",
        91: "¡",
        92: "Ñ",
        93: "¿",
        94: "é",
        96: "`",
        123: "í",
        124: "ñ",
        125: "ó",
        126: "ú",
    },
    12: {
        35: "#",
        36: "$",
        64: "á",
        91: "¡",
        92: "Ñ",
        93: "¿",
        94: "é",
        96: "ü",
        123: "í",
        124: "ñ",
        125: "ó",
        126: "ú",
    },
    13: {
        35:  "#",
        36:  "$",
        64:  "@",
        91:  "[",
        92:  "₩",  # 20a9 -> WON SIGN (Currency symbol)
        93:  "]",
        94:  "^",
        96:  "`",
        123: "{",
        124: "|",
        125: "}",
        126: "~",
    },
    64: {
        35:  "#",
        36:  "$",
        64:  "§",
        91:  "°",
        92:  "’",
        93:  "”",
        94:  "¶",
        96:  "`",
        123: "©",
        124: "®",
        125: "†",
        126: "™"
    }
}

# Logging
LOGGER_NAME = "src"
LOG_LEVEL = "DEBUG"

################################################################################


def logger(name=LOGGER_NAME):
    """Return logger of given name, without initialize it.

    Equivalent of logging.getLogger() call.
    """
    logger_obj = logging.getLogger(name)
    fmt_str = "%(levelname)s: [%(filename)s:%(lineno)s:%(funcName)s()] %(message)s"
    logging.basicConfig(format=fmt_str)
    return logger_obj


_logger = logging.getLogger(LOGGER_NAME)


# log file
formatter = logging.Formatter(
    "%(asctime)s :: %(levelname)s :: [%(filename)s:%(lineno)s:%(funcName)s()] :: %(message)s"
)
file_handler = RotatingFileHandler(
    DIR_LOGS
    + LOGGER_NAME
    + "_"
    + dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    + ".log",
    "a",
    100_000_000,
    1,
)
file_handler.setFormatter(formatter)
_logger.addHandler(file_handler)

# terminal log
# stream_handler = logging.StreamHandler()
# formatter = logging.Formatter("%(levelname)s: %(message)s")
# stream_handler.setFormatter(formatter)
# _logger.addHandler(stream_handler)


def log_level(level):
    """Set terminal/file log level to the given one.

    .. note:: Don't forget the propagation system of messages:
        From logger to handlers. Handlers receive log messages only if
        the main logger doesn't filter them.
    """
    level = level.upper()
    if level == "NONE":
        # Override all severity levels under CRITICAL
        logging.disable()
        return
    else:
        # Remove the overriding level
        logging.disable(logging.NOTSET)
    # Main logger
    _logger.setLevel(level)
    # Handlers
    _ = [
        handler.setLevel(level)
        for handler in _logger.handlers
        if handler.__class__
        in (logging.StreamHandler, logging.handlers.RotatingFileHandler)
    ]


log_level(LOG_LEVEL)
