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
"""
Python Character Mapping Codec abicomp

https://en.wikipedia.org/wiki/ABICOMP_character_set
"""
# Standard imports
from functools import partial
import codecs

# Local imports
from escparser.encodings.ram_codec import getregentry


CHARSET = {
    0x20: "\u0020",  #   SPACE
    0x21: "\u0021",  # ! EXCLAMATION MARK
    0x22: "\u0022",  # " QUOTATION MARK
    0x23: "\u0023",  # # NUMBER SIGN
    0x24: "\u0024",  # $ DOLLAR SIGN
    0x25: "\u0025",  # % PERCENT SIGN
    0x26: "\u0026",  # & AMPERSAND
    0x27: "\u0027",  # ' APOSTROPHE
    0x28: "\u0028",  # ( LEFT PARENTHESIS
    0x29: "\u0029",  # ) RIGHT PARENTHESIS
    0x2A: "\u002a",  # * ASTERISK
    0x2B: "\u002b",  # + PLUS SIGN
    0x2C: "\u002c",  # , COMMA
    0x2D: "\u002d",  # - HYPHEN-MINUS
    0x2E: "\u002e",  # . FULL STOP
    0x2F: "\u002f",  # / SOLIDUS
    0x30: "\u0030",  # 0 DIGIT ZERO
    0x31: "\u0031",  # 1 DIGIT ONE
    0x32: "\u0032",  # 2 DIGIT TWO
    0x33: "\u0033",  # 3 DIGIT THREE
    0x34: "\u0034",  # 4 DIGIT FOUR
    0x35: "\u0035",  # 5 DIGIT FIVE
    0x36: "\u0036",  # 6 DIGIT SIX
    0x37: "\u0037",  # 7 DIGIT SEVEN
    0x38: "\u0038",  # 8 DIGIT EIGHT
    0x39: "\u0039",  # 9 DIGIT NINE
    0x3A: "\u003a",  # : COLON
    0x3B: "\u003b",  # ; SEMICOLON
    0x3C: "\u003c",  # < LESS-THAN SIGN
    0x3D: "\u003d",  # = EQUALS SIGN
    0x3E: "\u003e",  # > GREATER-THAN SIGN
    0x3F: "\u003f",  # ? QUESTION MARK
    0x40: "\u0040",  # @ COMMERCIAL AT
    0x41: "\u0041",  # A LATIN CAPITAL LETTER A
    0x42: "\u0042",  # B LATIN CAPITAL LETTER B
    0x43: "\u0043",  # C LATIN CAPITAL LETTER C
    0x44: "\u0044",  # D LATIN CAPITAL LETTER D
    0x45: "\u0045",  # E LATIN CAPITAL LETTER E
    0x46: "\u0046",  # F LATIN CAPITAL LETTER F
    0x47: "\u0047",  # G LATIN CAPITAL LETTER G
    0x48: "\u0048",  # H LATIN CAPITAL LETTER H
    0x49: "\u0049",  # I LATIN CAPITAL LETTER I
    0x4A: "\u004a",  # J LATIN CAPITAL LETTER J
    0x4B: "\u004b",  # K LATIN CAPITAL LETTER K
    0x4C: "\u004c",  # L LATIN CAPITAL LETTER L
    0x4D: "\u004d",  # M LATIN CAPITAL LETTER M
    0x4E: "\u004e",  # N LATIN CAPITAL LETTER N
    0x4F: "\u004f",  # O LATIN CAPITAL LETTER O
    0x50: "\u0050",  # P LATIN CAPITAL LETTER P
    0x51: "\u0051",  # Q LATIN CAPITAL LETTER Q
    0x52: "\u0052",  # R LATIN CAPITAL LETTER R
    0x53: "\u0053",  # S LATIN CAPITAL LETTER S
    0x54: "\u0054",  # T LATIN CAPITAL LETTER T
    0x55: "\u0055",  # U LATIN CAPITAL LETTER U
    0x56: "\u0056",  # V LATIN CAPITAL LETTER V
    0x57: "\u0057",  # W LATIN CAPITAL LETTER W
    0x58: "\u0058",  # X LATIN CAPITAL LETTER X
    0x59: "\u0059",  # Y LATIN CAPITAL LETTER Y
    0x5A: "\u005a",  # Z LATIN CAPITAL LETTER Z
    0x5B: "\u005b",  # [ LEFT SQUARE BRACKET
    0x5C: "\u005c",  # \ REVERSE SOLIDUS
    0x5D: "\u005d",  # ] RIGHT SQUARE BRACKET
    0x5E: "\u005e",  # ^ CIRCUMFLEX ACCENT
    0x5F: "\u005f",  # _ LOW LINE
    0x60: "\u0060",  # ` GRAVE ACCENT
    0x61: "\u0061",  # a LATIN SMALL LETTER A
    0x62: "\u0062",  # b LATIN SMALL LETTER B
    0x63: "\u0063",  # c LATIN SMALL LETTER C
    0x64: "\u0064",  # d LATIN SMALL LETTER D
    0x65: "\u0065",  # e LATIN SMALL LETTER E
    0x66: "\u0066",  # f LATIN SMALL LETTER F
    0x67: "\u0067",  # g LATIN SMALL LETTER G
    0x68: "\u0068",  # h LATIN SMALL LETTER H
    0x69: "\u0069",  # i LATIN SMALL LETTER I
    0x6A: "\u006a",  # j LATIN SMALL LETTER J
    0x6B: "\u006b",  # k LATIN SMALL LETTER K
    0x6C: "\u006c",  # l LATIN SMALL LETTER L
    0x6D: "\u006d",  # m LATIN SMALL LETTER M
    0x6E: "\u006e",  # n LATIN SMALL LETTER N
    0x6F: "\u006f",  # o LATIN SMALL LETTER O
    0x70: "\u0070",  # p LATIN SMALL LETTER P
    0x71: "\u0071",  # q LATIN SMALL LETTER Q
    0x72: "\u0072",  # r LATIN SMALL LETTER R
    0x73: "\u0073",  # s LATIN SMALL LETTER S
    0x74: "\u0074",  # t LATIN SMALL LETTER T
    0x75: "\u0075",  # u LATIN SMALL LETTER U
    0x76: "\u0076",  # v LATIN SMALL LETTER V
    0x77: "\u0077",  # w LATIN SMALL LETTER W
    0x78: "\u0078",  # x LATIN SMALL LETTER X
    0x79: "\u0079",  # y LATIN SMALL LETTER Y
    0x7A: "\u007a",  # z LATIN SMALL LETTER Z
    0x7B: "\u007b",  # { LEFT CURLY BRACKET
    0x7C: "\u007c",  # | VERTICAL LINE
    0x7D: "\u007d",  # } RIGHT CURLY BRACKET
    0x7E: "\u007e",  # ~ TILDE

    0xA0: "\u00a0",  #   NO-BREAK SPACE
    0xA1: "\u00c0",  # À LATIN CAPITAL LETTER A WITH GRAVE
    0xA2: "\u00c1",  # Á LATIN CAPITAL LETTER A WITH ACUTE
    0xA3: "\u00c2",  # Â LATIN CAPITAL LETTER A WITH CIRCUMFLEX
    0xA4: "\u00c3",  # Ã LATIN CAPITAL LETTER A WITH TILDE
    0xA5: "\u00c4",  # Ä LATIN CAPITAL LETTER A WITH DIAERESIS
    0xA6: "\u00c7",  # Ç LATIN CAPITAL LETTER C WITH CEDILLA
    0xA7: "\u00c8",  # È LATIN CAPITAL LETTER E WITH GRAVE
    0xA8: "\u00c9",  # É LATIN CAPITAL LETTER E WITH ACUTE
    0xA9: "\u00ca",  # Ê LATIN CAPITAL LETTER E WITH CIRCUMFLEX
    0xAA: "\u00cb",  # Ë LATIN CAPITAL LETTER E WITH DIAERESIS
    0xAB: "\u00cc",  # Ì LATIN CAPITAL LETTER I WITH GRAVE
    0xAC: "\u00cd",  # Í LATIN CAPITAL LETTER I WITH ACUTE
    0xAD: "\u00ce",  # Î LATIN CAPITAL LETTER I WITH CIRCUMFLEX
    0xAE: "\u00cf",  # Ï LATIN CAPITAL LETTER I WITH DIAERESIS
    0xAF: "\u00d1",  # Ñ LATIN CAPITAL LETTER N WITH TILDE
    0xB0: "\u00d2",  # Ò LATIN CAPITAL LETTER O WITH GRAVE
    0xB1: "\u00d3",  # Ó LATIN CAPITAL LETTER O WITH ACUTE
    0xB2: "\u00d4",  # Ô LATIN CAPITAL LETTER O WITH CIRCUMFLEX
    0xB3: "\u00d5",  # Õ LATIN CAPITAL LETTER O WITH TILDE
    0xB4: "\u00d6",  # Ö LATIN CAPITAL LETTER O WITH DIAERESIS
    0xB5: "\u0152",  # Œ LATIN CAPITAL LIGATURE OE
    0xB6: "\u00d9",  # Ù LATIN CAPITAL LETTER U WITH GRAVE
    0xB7: "\u00da",  # Ú LATIN CAPITAL LETTER U WITH ACUTE
    0xB8: "\u00db",  # Û LATIN CAPITAL LETTER U WITH CIRCUMFLEX
    0xB9: "\u00dc",  # Ü LATIN CAPITAL LETTER U WITH DIAERESIS
    0xBA: "\u0178",  # Ÿ LATIN CAPITAL LETTER Y WITH DIAERESIS
    0xBB: "\u00a8",  # ¨ DIAERESIS
    0xBC: "\u00a3",  # £ POUND SIGN
    0xBD: "\u00a6",  # ¦ BROKEN BAR
    0xBE: "\u00a7",  # § SECTION SIGN
    0xBF: "\u00b0",  # ° DEGREE SIGN
    0xC0: "\u00a1",  # ¡ INVERTED EXCLAMATION MARK
    0xC1: "\u00e0",  # à LATIN SMALL LETTER A WITH GRAVE
    0xC2: "\u00e1",  # á LATIN SMALL LETTER A WITH ACUTE
    0xC3: "\u00e2",  # â LATIN SMALL LETTER A WITH CIRCUMFLEX
    0xC4: "\u00e3",  # ã LATIN SMALL LETTER A WITH TILDE
    0xC5: "\u00e4",  # ä LATIN SMALL LETTER A WITH DIAERESIS
    0xC6: "\u00e7",  # ç LATIN SMALL LETTER C WITH CEDILLA
    0xC7: "\u00e8",  # è LATIN SMALL LETTER E WITH GRAVE
    0xC8: "\u00e9",  # é LATIN SMALL LETTER E WITH ACUTE
    0xC9: "\u00ea",  # ê LATIN SMALL LETTER E WITH CIRCUMFLEX
    0xCA: "\u00eb",  # ë LATIN SMALL LETTER E WITH DIAERESIS
    0xCB: "\u00ec",  # ì LATIN SMALL LETTER I WITH GRAVE
    0xCC: "\u00ed",  # í LATIN SMALL LETTER I WITH ACUTE
    0xCD: "\u00ee",  # î LATIN SMALL LETTER I WITH CIRCUMFLEX
    0xCE: "\u00ef",  # ï LATIN SMALL LETTER I WITH DIAERESIS
    0xCF: "\u00f1",  # ñ LATIN SMALL LETTER N WITH TILDE
    0xD0: "\u00f2",  # ò LATIN SMALL LETTER O WITH GRAVE
    0xD1: "\u00f3",  # ó LATIN SMALL LETTER O WITH ACUTE
    0xD2: "\u00f4",  # ô LATIN SMALL LETTER O WITH CIRCUMFLEX
    0xD3: "\u00f5",  # õ LATIN SMALL LETTER O WITH TILDE
    0xD4: "\u00f6",  # ö LATIN SMALL LETTER O WITH DIAERESIS
    0xD5: "\u0153",  # œ LATIN SMALL LIGATURE OE
    0xD6: "\u00f9",  # ù LATIN SMALL LETTER U WITH GRAVE
    0xD7: "\u00fa",  # ú LATIN SMALL LETTER U WITH ACUTE
    0xD8: "\u00fb",  # û LATIN SMALL LETTER U WITH CIRCUMFLEX
    0xD9: "\u00fc",  # ü LATIN SMALL LETTER U WITH DIAERESIS
    0xDA: "\u00ff",  # ÿ LATIN SMALL LETTER Y WITH DIAERESIS
    0xDB: "\u00df",  # ß LATIN SMALL LETTER SHARP S
    0xDC: "\u00aa",  # ª FEMININE ORDINAL INDICATOR
    0xDD: "\u00ba",  # º MASCULINE ORDINAL INDICATOR
    0xDE: "\u00bf",  # ¿ INVERTED QUESTION MARK
    0xDF: "\u00b1",  # ± PLUS-MINUS SIGN
}

register_codec_func = partial(
    getregentry,
    effective_encoding="abicomp",
    mapping_charset=CHARSET,
)
codecs.register(register_codec_func)
