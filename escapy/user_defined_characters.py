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
"""Wrapper class for RAM characters"""
# Standard imports
from pathlib import Path
from functools import partial
import codecs
import json

# Custom imports
from escparser.commons import logger, USER_DEFINED_DB_FILE, RAM_CHARACTERS_TABLE
from escparser.encodings import ram_codec
from escparser.parser import PrintMode, PrintScripting

LOGGER = logger()


class EnumsEncoder(json.JSONEncoder):
    """Properly encode the PrintMode & PrintScripting enumeration to a JSON file"""

    def default(self, o):
        if isinstance(o, (PrintMode, PrintScripting)):
            return o.value
        return json.JSONEncoder.default(self, o)  # pragma: no cover


class RAMCharacters:
    """Wrapper class for RAM characters

    This class includes methods to handle a JSON file as a database for
    manual mappings of user-defined characters (chararacter codes <=> unicode).
    """

    def __init__(self, parent=None, db_filepath=USER_DEFINED_DB_FILE):
        """

        :key parent: Instance of the ESCParser from which settings will be
            extracted and compared to decide on the reset of RAM memory.
        :key db_filepath: JSON filepath used as mappings between
            chararacter codes and unicode.
        :type parent: escparser.ESCParser
        :type db_filepath: str | Path
        """
        self.db_filepath = Path(db_filepath)
        self.register_codec_func = None

        self.encoding = None
        self._settings = None
        self.charset_mapping = {}
        self.database = {}

        self.extract_settings(parent)
        self.load_manual_mapping()
        # /!\ /!\ If you modify me, DO NOT FORGET to update mock_init()
        # in test_user_defined_characters test module.

    def __del__(self):
        """Clear the registered codec on object deletion

        Mainly for tests purposes and environment cleaning;
        codecs module's cache must be reset between tests and between printer
        resets.
        """
        self.unregister()

    def unregister(self):
        """Clear the currently registered codec

        The codecs module maintain an internal cache (list) of registered codecs.
        The first occurrence found is returned when the encode or decode function
        is used (internal lookup). Previous versions of the codec must be cleared
        before a new one is added.

        PS: An internal but unfortunately not exposed C function exists:
        `_PyCodec_Forget`.
        """
        if self.register_codec_func:
            codecs.unregister(self.register_codec_func)
            LOGGER.debug("Clear previous 'user_defined' encoding.")
            self.register_codec_func = None

    def extract_settings(self, parent):
        """Sync current settings and reset RAM characters if necessary

        i.e. if the settings of the parser do not coincide with the previous
        settings used to build user-defined characters.

        .. warning:: The encoding IS NOT updated (thus, NOT effective),
            for performance reasons, you HAVE TO call
            :meth:`update_encoding` manually after this function.

        :param parent: Instance of the ESCParser from which settings will be
            extracted and compared to decide on the reset of RAM memory.
        :type parent: escparser.ESCParser
        """
        self.settings = {
            "mode": parent.mode,
            "proportional_spacing": parent.proportional_spacing,
            "scripting": parent.scripting,
        }

    def load_manual_mapping(self):
        """Load JSON file used as mappings between chararacter codes and unicode

        Each entry in this file is made to be modified manually in order to
        assign a unicode value to the unknown character codes.
        Some metadata are also present to add some clues to the context
        at the time the character was sent.

        Example::

            "83e1a70_1": {
                "mode": 1,
                "proportional_spacing": false,
                "scripting": null,
                "1": "\ufffd"  # YOU have to MODIFY this line with an expected unicode value!
            }
        """
        if self.db_filepath.exists():
            try:
                self.database = json.loads(self.db_filepath.read_text(encoding="utf8"))
            except json.decoder.JSONDecodeError:
                self.database = {}
        else:
            self.database = {}

        LOGGER.debug("User-defined characters mapping database loaded")

    @property
    def settings(self):
        """Get the traits that define the characters in RAM

        For now: print mode, proportional spacing, scripting mode.
        """
        return self._settings

    @settings.setter
    def settings(self, settings: dict):
        """Maintain the traits that define the characters in RAM

        If user-defined characters are defined with different traits,
        the printer erases all previous characters in RAM memory.

        :param settings: Dict of settings; see :meth:`RAMCharacters.extract_settings`.
        """
        if settings != self.settings:
            LOGGER.debug(
                "Settings are different: reset user defined chars %s", self._settings
            )
            self.charset_mapping = {}
            # Reset the encoding
            # ESC & can now be sent without using an encoding previously set
            # by ESC : (copy rom to ram).
            self.encoding = None

        self._settings = settings

    def clear(self):
        """Do an explicit reset of RAM characters AND encoding

        The reset is effective right now and the "user_defined" codec is not
        available anymore.
        """
        self.settings = None
        self.unregister()
        LOGGER.debug("Explicit clear of RAM characters + user_defined codec")

    def from_rom(self, encoding: str | None, typeface: int, pins: int | None):
        """Copy the data from the ROM characters to RAM - ESC :

        ESCP2:
            Characters copied from locations 0 to 127
        9pins:
            Characters copied from locations 0 to 255;
            TODO: locations from 128 to 255 are taken from the Italic table...

        LX-series printers, ActionPrinter Apex 80, ActionPrinter T-1000, ActionPrinter 2000
            TODO: Only characters from 58 to 63 can be copied to RAM.

        Erase any characters that are currently stored in RAM.

        .. warning:: Do not forget to call :meth:`extract_settings` before.

        :param encoding: Current ROM table used (encoding).
        :param typeface: Typeface id from wich the characters are "copied".
            In this implementation, this setting IS NOT used!
            See :meth:`copy_rom_to_ram`.
        :param pins: Number of pins of the printer head (9, 24, 48, None).
            Use None for default modern ESCP2 printers with nozzles. (default: None).
        """
        LOGGER.debug(
            "Create charset mapping from ROM; encoding: %s; pins: %s", encoding, pins
        )
        self.encoding = encoding

        # Copy the ROM character mapping from the given encoding
        encoded = bytes(range(256 if pins == 9 else 128))
        decoded = encoded.decode(encoding, errors="replace")
        # assert len(encoded) == len(decoded)

        # Replace the RAM mapping
        self.charset_mapping = dict(zip(encoded, decoded))
        self.update_encoding()

    def update_encoding(self):
        """Create & register a new "user_defined" encoding with the RAM character mapping

        Previous registered encoding is unregistered before (removed from the cache).

        3 commands use this method:

        - Copy from ROM to RAM (ESC :)
        - Shift lower charset part to upper charset part (ESC t 2)
        - Add user-defined characters (ESC &)
        """
        register_codec_func = partial(
            ram_codec.getregentry,
            effective_encoding=RAM_CHARACTERS_TABLE,
            mapping_charset=self.charset_mapping,
        )
        self.unregister()
        codecs.register(register_codec_func)
        # Keep track of the codec function for the next unregister
        self.register_codec_func = register_codec_func

    def shift_upper_charset(self):
        """Shift lower charset part to upper charset part - ESC t 2

        Only for ESCP2, ESCP printers.
        """
        LOGGER.debug("Shift RAM characters")
        LOGGER.debug("Old: %s", self.charset_mapping)
        # Take the lower part of the current ROM encoding
        encoded = bytes(range(128))

        if self.encoding is None:
            # encoding can be None if copy ROM to RAM has not been called before
            decoded = "\uFFFD" * 128
        else:
            decoded = encoded.decode(self.encoding, errors="replace")
        # assert len(encoded) == len(decoded)

        # Take the lower part of the existing RAM encoding and shift it
        self.charset_mapping = {
            code + 0x80: value
            for code, value in self.charset_mapping.items()
            if code < 0x80
        }
        # Merge with the 128 codes from the ROM charset
        self.charset_mapping |= dict(zip(encoded, decoded))
        self.update_encoding()

        LOGGER.debug("New: %s", self.charset_mapping)

    def add_char(self, chr_hash: str, code: int):
        """Add a new character to the RAM - ESC &

        If the code is not already in the database, it will be added alongside
        the REPLACEMENT unicode character.
        See :meth:`RAMCharacters.load_manual_mapping`.

        .. warning:: The encoding IS NOT updated (thus, NOT effective),
            for performance reasons, you HAVE TO call
            :meth:`update_encoding` manually after this function.

        .. warning:: Do not forget to call :meth:`extract_settings` before.

        :param chr_hash: Hash of the bytes defining the dots of the character.
        :param code: Character code in the charset table.
        """
        key = f"{chr_hash}_{code}"
        # REPLACEMENT CHARACTER is used if the mapping is not found

        if key not in self.database:
            # Fill the database (context + default mapping)
            self.database[key] = self.settings | {code: "\uFFFD"}
            char = "\uFFFD"
        else:
            # Key is found
            # PS: JSON keys are always strings, not numeric values => cast code
            char = self.database[key].get(str(code), "\uFFFD")

        self.charset_mapping[code] = char

    def save(self):
        """Save the JSON database of characters mappings

        Should be saved each time ESC & (add user-defined characters) is sent
        to the printer.
        See :meth:`RAMCharacters.load_manual_mapping`.
        """
        self.db_filepath.write_text(
            json.dumps(self.database, indent=4, cls=EnumsEncoder), encoding="utf8"
        )
