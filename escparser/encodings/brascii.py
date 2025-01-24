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
Python Character Mapping Codec brascii derived from code page latin1 / iso8859_1
with 2 specific characters.

https://en.wikipedia.org/wiki/BraSCII
"""
# Standard imports
from functools import partial
import codecs

# Local imports
from escparser.encodings.i18n_codecs import getregentry


register_codec_func = partial(
    getregentry,
    effective_encoding="brascii",
    base_encoding="iso8859_1",
    intl_charset={0xD7: "Œ", 0xF7: "œ"},
)
codecs.register(register_codec_func)
