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
Python Character Mapping Codec cp774 derived from code page 437
with specific positions modified to accommodate Lithuanian letters.

https://en.wikipedia.org/wiki/Code_page_1118
"""
# Standard imports
from functools import partial
import codecs

# Local imports
from escparser.encodings.i18n_codecs import getregentry


CHARSET = {
    0xb5: "\u0104",  # LATIN CAPITAL LETTER A WITH OGONEK
    0xb6: "\u010c",  # LATIN CAPITAL LETTER C WITH CARON
    0xb7: "\u0118",  # LATIN CAPITAL LETTER E WITH OGONEK
    0xb8: "\u0116",  # LATIN CAPITAL LETTER E WITH DOT ABOVE

    0xbd: "\u012e",  # LATIN CAPITAL LETTER I WITH OGONEK
    0xbe: "\u0160",  # LATIN CAPITAL LETTER S WITH CARON

    0xc6: "\u0172",  # LATIN CAPITAL LETTER U WITH OGONEK
    0xc7: "\u016a",  # LATIN CAPITAL LETTER U WITH MACRON

    0xcf: "\u017d",  # LATIN CAPITAL LETTER Z WITH CARON
    0xd0: "\u0105",  # LATIN SMALL LETTER A WITH OGONEK
    0xd1: "\u010d",  # LATIN SMALL LETTER C WITH CARON
    0xd2: "\u0119",  # LATIN SMALL LETTER E WITH OGONEK
    0xd3: "\u0117",  # LATIN SMALL LETTER E WITH DOT ABOVE
    0xd4: "\u012f",  # LATIN SMALL LETTER I WITH OGONEK
    0xd5: "\u0161",  # LATIN SMALL LETTER S WITH CARON
    0xd6: "\u0173",  # LATIN SMALL LETTER U WITH OGONEK
    0xd7: "\u016b",  # LATIN SMALL LETTER U WITH MACRON
    0xd8: "\u017e",  # LATIN SMALL LETTER Z WITH CARON

    0xf4: "\u201e",  # DOUBLE LOW-9 QUOTATION MARK
    0xf5: "\u201c",  # LEFT DOUBLE QUOTATION MARK
}

register_codec_func = partial(
    getregentry,
    effective_encoding="cp774",
    base_encoding="cp437",
    intl_charset=CHARSET,
)
codecs.register(register_codec_func)
