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
Python Character Mapping Codec iscii (Indian Script Code for Information Interchange)

https://en.wikipedia.org/wiki/Indian_Script_Code_for_Information_Interchange

.. warning:: Unsure mapping for "Special code points": ATR, EXT.
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
    0x2a: "\u002a",  # * ASTERISK
    0x2b: "\u002b",  # + PLUS SIGN
    0x2c: "\u002c",  # , COMMA
    0x2d: "\u002d",  # - HYPHEN-MINUS
    0x2e: "\u002e",  # . FULL STOP
    0x2f: "\u002f",  # / SOLIDUS
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
    0x3a: "\u003a",  # : COLON
    0x3b: "\u003b",  # ; SEMICOLON
    0x3c: "\u003c",  # < LESS-THAN SIGN
    0x3d: "\u003d",  # = EQUALS SIGN
    0x3e: "\u003e",  # > GREATER-THAN SIGN
    0x3f: "\u003f",  # ? QUESTION MARK
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
    0x4a: "\u004a",  # J LATIN CAPITAL LETTER J
    0x4b: "\u004b",  # K LATIN CAPITAL LETTER K
    0x4c: "\u004c",  # L LATIN CAPITAL LETTER L
    0x4d: "\u004d",  # M LATIN CAPITAL LETTER M
    0x4e: "\u004e",  # N LATIN CAPITAL LETTER N
    0x4f: "\u004f",  # O LATIN CAPITAL LETTER O
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
    0x5a: "\u005a",  # Z LATIN CAPITAL LETTER Z
    0x5b: "\u005b",  # [ LEFT SQUARE BRACKET
    0x5c: "\u005c",  # \ REVERSE SOLIDUS
    0x5d: "\u005d",  # ] RIGHT SQUARE BRACKET
    0x5e: "\u005e",  # ^ CIRCUMFLEX ACCENT
    0x5f: "\u005f",  # _ LOW LINE
    0x60: "\u0027",  # ' APOSTROPHE
    0x61: "\u0061",  # a LATIN SMALL LETTER A
    0x62: "\u0062",  # b LATIN SMALL LETTER B
    0x63: "\u0063",  # c LATIN SMALL LETTER C
    0x64: "\u0064",  # d LATIN SMALL LETTER D
    0x65: "\u0065",  # e LATIN SMALL LETTER E
    0x66: "\u0066",  # f LATIN SMALL LETTER F
    0x67: "\u0067",  # g LATIN SMALL LETTER G
    0x68: "\u0068",  # h LATIN SMALL LETTER H
    0x69: "\u0069",  # i LATIN SMALL LETTER I
    0x6a: "\u006a",  # j LATIN SMALL LETTER J
    0x6b: "\u006b",  # k LATIN SMALL LETTER K
    0x6c: "\u006c",  # l LATIN SMALL LETTER L
    0x6d: "\u006d",  # m LATIN SMALL LETTER M
    0x6e: "\u006e",  # n LATIN SMALL LETTER N
    0x6f: "\u006f",  # o LATIN SMALL LETTER O
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
    0x7a: "\u007a",  # z LATIN SMALL LETTER Z
    0x7b: "\u007b",  # { LEFT CURLY BRACKET
    0x7c: "\u007c",  # | VERTICAL LINE
    0x7d: "\u007d",  # } RIGHT CURLY BRACKET
    0x7e: "\u007e",  # ~ TILDE

    0xa1: "\u0901",  # DEVANAGARI SIGN CANDRABINDU
    0xa2: "\u0902",  # DEVANAGARI SIGN ANUSVARA
    0xa3: "\u0903",  # DEVANAGARI SIGN VISARGA
    0xa4: "\u0905",  # DEVANAGARI LETTER A
    0xa5: "\u0906",  # DEVANAGARI LETTER AA
    0xa6: "\u0907",  # DEVANAGARI LETTER I
    0xa7: "\u0908",  # DEVANAGARI LETTER II
    0xa8: "\u0909",  # DEVANAGARI LETTER U
    0xa9: "\u090a",  # DEVANAGARI LETTER UU
    0xaa: "\u090b",  # DEVANAGARI LETTER VOCALIC R
    0xab: "\u090e",  # DEVANAGARI LETTER SHORT E
    0xac: "\u090f",  # DEVANAGARI LETTER E
    0xad: "\u0910",  # DEVANAGARI LETTER AI
    0xae: "\u090d",  # DEVANAGARI LETTER CANDRA E
    0xaf: "\u0912",  # DEVANAGARI LETTER SHORT O

    0xb0: "\u0913",  # DEVANAGARI LETTER O
    0xb1: "\u0914",  # DEVANAGARI LETTER AU
    0xb2: "\u0911",  # DEVANAGARI LETTER CANDRA O
    0xb3: "\u0915",  # DEVANAGARI LETTER KA
    0xb4: "\u0916",  # DEVANAGARI LETTER KHA
    0xb5: "\u0917",  # DEVANAGARI LETTER GA
    0xb6: "\u0918",  # DEVANAGARI LETTER GHA
    0xb7: "\u0919",  # DEVANAGARI LETTER NGA
    0xb8: "\u091a",  # DEVANAGARI LETTER CA
    0xb9: "\u091b",  # DEVANAGARI LETTER CHA
    0xba: "\u091c",  # DEVANAGARI LETTER JA
    0xbb: "\u091d",  # DEVANAGARI LETTER JHA
    0xbc: "\u091e",  # DEVANAGARI LETTER NYA
    0xbd: "\u091f",  # DEVANAGARI LETTER TTA
    0xbe: "\u0920",  # DEVANAGARI LETTER TTHA
    0xbf: "\u0921",  # DEVANAGARI LETTER DDA

    0xc0: "\u0922",  # DEVANAGARI LETTER DDHA
    0xc1: "\u0923",  # DEVANAGARI LETTER NNA
    0xc2: "\u0924",  # DEVANAGARI LETTER TA
    0xc3: "\u0925",  # DEVANAGARI LETTER THA
    0xc4: "\u0926",  # DEVANAGARI LETTER DA
    0xc5: "\u0927",  # DEVANAGARI LETTER DHA
    0xc6: "\u0928",  # DEVANAGARI LETTER NA
    0xc7: "\u0929",  # DEVANAGARI LETTER NNNA
    0xc8: "\u092a",  # DEVANAGARI LETTER PA
    0xc9: "\u092b",  # DEVANAGARI LETTER PHA
    0xca: "\u092c",  # DEVANAGARI LETTER BA
    0xcb: "\u092d",  # DEVANAGARI LETTER BHA
    0xcc: "\u092e",  # DEVANAGARI LETTER MA
    0xcd: "\u092f",  # DEVANAGARI LETTER YA
    0xce: "\u095f",  # DEVANAGARI LETTER YYA
    0xcf: "\u0930",  # DEVANAGARI LETTER RA

    0xd0: "\u0931",  # DEVANAGARI LETTER RRA
    0xd1: "\u0932",  # DEVANAGARI LETTER LA
    0xd2: "\u0933",  # DEVANAGARI LETTER LLA
    0xd3: "\u0934",  # DEVANAGARI LETTER LLLA
    0xd4: "\u0935",  # DEVANAGARI LETTER VA
    0xd5: "\u0936",  # DEVANAGARI LETTER SHA
    0xd6: "\u0937",  # DEVANAGARI LETTER SSA
    0xd7: "\u0938",  # DEVANAGARI LETTER SA
    0xd8: "\u0939",  # DEVANAGARI LETTER HA
    0xd9: "\u200e",  # LEFT-TO-RIGHT MARK
    0xda: "\u093e",  # DEVANAGARI VOWEL SIGN AA
    0xdb: "\u093f",  # DEVANAGARI VOWEL SIGN I
    0xdc: "\u0940",  # DEVANAGARI VOWEL SIGN II
    0xdd: "\u0941",  # DEVANAGARI VOWEL SIGN U
    0xde: "\u0942",  # DEVANAGARI VOWEL SIGN UU
    0xdf: "\u0943",  # DEVANAGARI VOWEL SIGN VOCALIC R

    0xe0: "\u0946",  # DEVANAGARI VOWEL SIGN SHORT E
    0xe1: "\u0947",  # DEVANAGARI VOWEL SIGN E
    0xe2: "\u0948",  # DEVANAGARI VOWEL SIGN AI
    0xe3: "\u0945",  # DEVANAGARI VOWEL SIGN CANDRA E
    0xe4: "\u094a",  # DEVANAGARI VOWEL SIGN SHORT O
    0xe5: "\u094b",  # DEVANAGARI VOWEL SIGN O
    0xe6: "\u094c",  # DEVANAGARI VOWEL SIGN AU
    0xe7: "\u0949",  # DEVANAGARI VOWEL SIGN CANDRA O
    0xe8: "\u094d",  # DEVANAGARI SIGN VIRAMA
    0xe9: "\u093c",  # DEVANAGARI SIGN NUKTA
    0xea: "\u0964",  # DEVANAGARI DANDA

    0xef: "\xef",    # ATR character—code point EF (239)
    0xf0: "\ufffe",  # EXT character—code point F0 (240), no direct Unicode equivalent

    0xf1: "\u0966",  # DEVANAGARI DIGIT ZERO
    0xf2: "\u0967",  # DEVANAGARI DIGIT ONE
    0xf3: "\u0968",  # DEVANAGARI DIGIT TWO
    0xf4: "\u0969",  # DEVANAGARI DIGIT THREE
    0xf5: "\u096a",  # DEVANAGARI DIGIT FOUR
    0xf6: "\u096b",  # DEVANAGARI DIGIT FIVE
    0xf7: "\u096c",  # DEVANAGARI DIGIT SIX
    0xf8: "\u096d",  # DEVANAGARI DIGIT SEVEN
    0xf9: "\u096e",  # DEVANAGARI DIGIT EIGHT
    0xfa: "\u096f",  # DEVANAGARI DIGIT NINE
}

register_codec_func = partial(
    getregentry,
    effective_encoding="iscii",
    mapping_charset=CHARSET,
)
codecs.register(register_codec_func)
