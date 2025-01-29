#  Libreprinter is a software allowing to use the Centronics and serial printing
#  functions of vintage computers on modern equipement through a tiny hardware
#  interface.
#  Copyright (C) 2020-2025  Ysard
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
"""Define a codec based on a given mapping - intended to be used as encoding for RAM characters"""
# Standard imports
import codecs

# Local imports
from escparser.commons import logger

LOGGER = logger()


class Codec(codecs.Codec):
    """Custom code page encoding/decoding codec based only on a given mapping"""

    def __init__(self, mapping_charset):
        """

        :param mapping_charset: Mapping on which the codec is built.
            Numeric values as keys, letters as values.
            Missing values are fulfilled with the UNDEFINED unicode symbol `\ufffe`.
        """
        super()

        # Fill the table with UNDEFINED symbol
        decoding_table = ["\ufffe"] * 256

        # Replace with the mappings of the given charset
        for position, letter in mapping_charset.items():
            decoding_table[position] = letter

        # Rebuild the decoding table, build an encoding table
        self.decoding_table = "".join(decoding_table)
        # Note: if characters are present multiple times (multiple bytes for
        # the same chr), the last one is always used by encode();
        # like unique keys in a dict.
        self.encoding_table = codecs.charmap_build(self.decoding_table)

    def encode(self, input, errors="strict"):
        """Unicode str to bytes

        .. seealso:: https://docs.python.org/3/library/codecs.html#codecs.Codec.encode
        """
        return codecs.charmap_encode(input, errors, self.encoding_table)

    def decode(self, input, errors="strict"):
        """Bytes to unicode str

        .. seealso:: https://docs.python.org/3/library/codecs.html#codecs.Codec.decode
        """
        return codecs.charmap_decode(input, errors, self.decoding_table)


def getregentry(
    encoding: str,
    effective_encoding: str = "",
    mapping_charset: dict | None = None,
) -> None | codecs.CodecInfo:
    """Used to register a custom codec

    .. seealso:: :meth:`codecs.register`.

    :param encoding: Encoding name passed by the lookup function.
    :key effective_encoding: Encoding name that will be used to register the new
        codec.
    :key mapping_charset: Mapping on which the codec is built.
            Numeric values as keys, letters as values.
    :return: Return the CodecInfo object if there is a match with the keyword
        parameter base_encoding, None otherwise.
    """
    if encoding != effective_encoding:  # pragma: no cover
        return
    new_codec = Codec(mapping_charset)
    codec_info = codecs.CodecInfo(
        name=effective_encoding,
        encode=new_codec.encode,
        decode=new_codec.decode,
    )
    return codec_info
