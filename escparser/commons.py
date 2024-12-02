# Standard imports
from logging.handlers import RotatingFileHandler
import logging
import datetime as dt
import tempfile
import os

# Paths
DIR_LOGS = tempfile.gettempdir() + "/"

typefaces = {
    # 0: (lambda condensed, bold, italic: f"Times-{'Bold' if bold else ''}{'Italic' if italic else ''}" if bold or italic else "Times-Roman", None),
    0: (lambda condensed, bold, italic: f"FiraCode-{'Bold' if bold else ''}" if bold else "FiraCode-Regular", "/usr/share/fonts/truetype/firacode/{}.ttf"),
    # 0: ("FSEX302-alt", "./resources/{}.ttf"),
    1: (lambda condensed, bold, italic: f"NotoSans-{'Condensed' if condensed else ''}{'Bold' if bold else ''}{'Italic' if italic else ''}" if any((bold, italic, condensed)) else "NotoSans-Regular", "/usr/share/fonts/truetype/noto/{}.ttf"),
    2: (lambda condensed, bold, italic: f"Courier-{'Bold' if bold else ''}{'Oblique' if italic else ''}" if any((bold, italic)) else "Courier", None),
    3: ("prestigenormal", "./resources/{}.ttf"),
    5: ("ocr-b-regular", "./resources/{}.ttf"),
    6: ("ocra", "./resources/{}.ttf"),
    7: ("orator", "./resources/{}.ttf"),
    9: ("scriptc", "./resources/{}.ttf"),
    10: ("romant", "./resources/{}.ttf"),
}


character_table_mapping = {
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

# set of up to 12 particular characters that corresponds to symbols used
# in various countries
charset_mapping = {
    0 : "USA",
    1 : "France",
    2 : "Germany",
    3 : "United Kingdom",
    4 : "Denmark I",
    5 : "Sweden",
    6 : "Italy",
    7 : "Spain I",
    8 : "Japan (English)",
    9 : "Norway",
    10: "Denmark II",
    11: "Spain II",
    12: "Latin America",
    13: "Korea",
    64: "Legal",
}

international_charsets = {
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
        35: "Pt",
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
        92:  "₩",
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
_logger.setLevel(LOG_LEVEL)

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
file_handler.setLevel(LOG_LEVEL)
file_handler.setFormatter(formatter)
_logger.addHandler(file_handler)

# terminal log
# stream_handler = logging.StreamHandler()
# formatter = logging.Formatter("%(levelname)s: %(message)s")
# stream_handler.setFormatter(formatter)
# stream_handler.setLevel(LOG_LEVEL)
# _logger.addHandler(stream_handler)


def log_level(level):
    """Set terminal/file log level to the given one.

    .. note:: Don't forget the propagation system of messages:
        From logger to handlers. Handlers receive log messages only if
        the main logger doesn't filter them.
    """
    level = level.upper()
    if level == "NONE":
        logging.disable()
        return
    # Main logger
    _logger.setLevel(level)
    # Handlers
    [
        handler.setLevel(level)
        for handler in _logger.handlers
        if handler.__class__
        in (logging.StreamHandler, logging.handlers.RotatingFileHandler)
    ]
