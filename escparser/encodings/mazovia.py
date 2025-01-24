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
"""
Python Character Mapping Codec mazovia derived from code page 437
with specific positions modified to accommodate Polish letters.

https://en.wikipedia.org/wiki/Mazovia_encoding
"""
# Standard imports
from functools import partial
import codecs

# Local imports
from escparser.encodings.i18n_codecs import getregentry


CHARSET = {
    0x86: "\u0105",  # ą LATIN SMALL LETTER A WITH OGONEK
    0x8D: "\u0107",  # ć LATIN SMALL LETTER C WITH ACUTE
    0x8F: "\u0104",  # Ą LATIN CAPITAL LETTER A WITH OGONEK
    0x90: "\u0118",  # Ę LATIN CAPITAL LETTER E WITH OGONEK
    0x91: "\u0119",  # ę LATIN SMALL LETTER E WITH OGONEK
    0x92: "\u0142",  # ł LATIN SMALL LETTER L WITH STROKE
    0x95: "\u0106",  # Ć LATIN CAPITAL LETTER C WITH ACUTE
    0x98: "\u015a",  # Ś LATIN CAPITAL LETTER S WITH ACUTE
    0x9C: "\u0141",  # Ł LATIN CAPITAL LETTER L WITH STROKE
    0x9E: "\u015b",  # ś LATIN SMALL LETTER S WITH ACUTE
    0xA0: "\u017b",  # Ż LATIN CAPITAL LETTER Z WITH DOT ABOVE
    0xA1: "\u00f3",  # ó LATIN SMALL LETTER O WITH ACUTE
    0xA3: "\u00d3",  # Ó LATIN CAPITAL LETTER O WITH ACUTE
    0xA4: "\u0144",  # ń LATIN SMALL LETTER N WITH ACUTE
    0xA5: "\u0143",  # Ń LATIN CAPITAL LETTER N WITH ACUTE
    0xA6: "\u017a",  # ź LATIN SMALL LETTER Z WITH ACUTE
    0xA7: "\u017c",  # ż LATIN SMALL LETTER Z WITH DOT ABOVE
}

register_codec_func = partial(
    getregentry,
    effective_encoding="mazovia",
    base_encoding="cp437",
    intl_charset=CHARSET,
)
codecs.register(register_codec_func)
