"""Encoding/decoding codecs for international codepage support"""
# Standard imports
import codecs
import importlib
from functools import partial

# Local imports
from escparser.commons import logger

LOGGER = logger()


class Codec(codecs.Codec):
    """Custom code page encoding/decoding codec"""

    def __init__(self, base_encoding, intl_charset):
        """

        .. warning:: Some encodings have an implementation that is not in pure
            Python; thus, their decoding table is not reachable and can not be
            used to build a new encoding here.
            For example, latin_1 is implemented in C but has a pure Python
            implementation: iso8859_1. This is not the case for cp932 (Japanese).
            For this last one, we rebuild the decoding table with a bytes range
            from 0 to 256. If characters are not in the original table, they will
            be replaced with a symbol '?'. There could be a loss of information!!

        :param base_encoding: Encoding used as a base for the new codec.
        :param intl_charset: Mapping injected in the base codec.
            Numeric values as keys, letters as values.
        """
        super()

        if base_encoding == "latin_1":
            # This codec is implemented in C for optimizations purposes
            # => switch to iso8859_1 to get the decoding table
            base_encoding = "iso8859_1"

        module = importlib.import_module(f"encodings.{base_encoding}")
        if "decoding_table" not in dir(module):
            LOGGER.warning(
                "Encoding <%s> not compatible with international charset injection"
            )
            # /!\ Errors will be masked with a '?' symbol !!
            decoding_table = list(bytes(range(256)).decode(base_encoding, errors="replace"))
        else:
            # Convert the decoding table (str) to a mutable type (list)
            decoding_table = list(module.decoding_table)

        # Replace the mappings of the given charset
        for position, letter in intl_charset.items():
            decoding_table[position] = letter

        # Rebuild the decoding table, build an encoding table
        self.decoding_table = "".join(decoding_table)
        # Note: if characters are present multiple times (multiple bytes for
        # the same chr), the last one is always used by encode();
        # like unique keys in a dict.
        self.encoding_table = codecs.charmap_build(self.decoding_table)

    def encode(self, input, errors="strict"):
        """unicode str to bytes

        .. seealso:: https://docs.python.org/3/library/codecs.html#codecs.Codec.encode
        """
        return codecs.charmap_encode(input, errors, self.encoding_table)

    def decode(self, input, errors="strict"):
        """bytes to unicode str

        .. seealso:: https://docs.python.org/3/library/codecs.html#codecs.Codec.decode
        """
        return codecs.charmap_decode(input, errors, self.decoding_table)


def getregentry(
    encoding: str,
    effective_encoding: str = "",
    base_encoding: str = "",
    intl_charset: dict | None = None,
) -> None | codecs.CodecInfo:
    """Used to register a custom codec

    .. seealso:: :meth:`codecs.register`.

    :param base_encoding: Encoding name passed by the lookup function.
    :key effective_encoding: Encoding name that will be used to register the new
        codec.
    :key base_encoding: Encoding used as a base for the new codec.
    :key intl_charset: Mapping injected in the base codec.
        Numeric values as keys, letters as values.
    :return: Return the CodecInfo object if there is a match with the keyword
        parameter base_encoding, None otherwise.
    """
    if encoding != effective_encoding:
        return
    new_codec = Codec(base_encoding, intl_charset)
    codec_info = codecs.CodecInfo(
        name=effective_encoding,
        encode=new_codec.encode,
        decode=new_codec.decode,
    )
    codec_info.basename = base_encoding
    return codec_info


# Add brascii codec
# https://en.wikipedia.org/wiki/BraSCII almost 8859-1 except 2 chars
register_codec_func = partial(
    getregentry,
    effective_encoding="brascii",
    base_encoding="iso8859_1",
    intl_charset={0xD7: "Œ", 0xF7: "œ"},
)
codecs.register(register_codec_func)
