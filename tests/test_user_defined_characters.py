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
"""Group of tests related to user-defined RAM characters"""
# Standard imports
from pathlib import Path
import codecs
from functools import partial, partialmethod
from unittest.mock import patch

# Custom imports
import pytest

# Local imports
from escparser.commons import RAM_CHARACTERS_TABLE
from escparser.parser import ESCParser, PrintMode, PrintScripting
from escparser.user_defined_characters import RAMCharacters
from escparser import ram_codec
from .misc import esc_reset, pdf_comparison


def normal_char_data() -> bytes:
    """Return a character data including space definitions and dots

    .. seealso:: See the fixture with the SAME name :meth:`indirect_normal_char_data`.

    Configuration:

    - ESCP2
    - 34x24: 34 columns of 24 lines (3 bytes per column)
    - Fixed spacing (no left/right extra spaces)
    - Normal height (no sub/super scripting)

    Character data is taken from the doc p263.
    A typo was present at byte 32: 0xf4 (244) instead of \xe0 (224).
    It is kept as an indicator of the image's direction (left side, bottom).
    """
    space_left_a0 = b"\x00"  # No proportional mode
    space_right_a2 = b"\x00"  # No proportional mode
    char_width_a1 = (34).to_bytes()  # Nb columns

    # \xf4 should be 0xe0
    data = (
        b"\x00\x00\x00 "
        b"\x00\x10\x00\x00\x00 \x00\x10\x00\x00\x00 \x00\x10\x00\x00\x00 "
        b"\x00\x10\x1f\xff\xe0 \x00\x10\x1f\xff\xf4 \x00\x10\x00\x00\x00 "
        b"\x00\x10\x00\x00\x00 \x00\x10\x00\x00\x00 \x00\x10\x00\x00\x00 "
        b"\x00\x10\x00\x00\x00 \x00\x10\x00\x00\x00 \x00\x10\x1f\xff\xe0 "
        b"\x00\x10\x1f\xff\xe0 \x00\x10\x00\x00\x00 \x00\x10\x00\x00\x00 "
        b"\x00\x10\x00\x00\x00 \x00\x10"
    )
    assert 0 <= space_left_a0[0] + char_width_a1[0] + space_right_a2[0] <= 42
    return space_left_a0 + char_width_a1 + space_right_a2 + data


@pytest.fixture(name="normal_char_data")
def indirect_normal_char_data():
    """Fixture wrapper over :meth:`normal_char_data`"""
    return normal_char_data()


def script_char():
    """Return a script character data including space definitions and dots

    Configuration:

    - ESCP2
    - 8x16: 8 columns of 16 lines (2 bytes per column)
    - Fixed spacing (no left/right extra spaces)
    - Script text height (sub or super scripting)
    """
    space_left_a0 = b"\x00"  # No proportional mode
    space_right_a2 = b"\x00"  # No proportional mode
    char_width_a1 = (8).to_bytes()  # Nb columns
    data_script = b"\x03\xe0\x04\x10\x05P\x04P\x05P\x04\x10\x03\xe0\x00\x00"

    return space_left_a0 + char_width_a1 + space_right_a2 + data_script


@pytest.mark.parametrize(
    "scripting, char_data",
    [
        (False, normal_char_data()),
        (True, script_char()),
    ],
    ids=[
        "normal_height",
        "subscript_height",
    ],
)
def test_user_defined_chars(scripting, char_data):
    """Test the definition of RAM user characters in ESCP2 mode - ESC &

    Test mapping from scratch (no base encoding like in :meth:`test_copy_rom_to_ram`).

    Test normal & script characters: 3 & 2 bytes per column for ESCP2 printers.

    Also tests that the RAM characters are erased if the settings
    (character traits) are modified.
    """
    define_user_char_cmd_prefix = b"\x1b&\x00"
    first_code_n = b"\x01"
    last_code_m = b"\x02"
    subscript_cmd = b"\x1bS\x01" if scripting else b""

    lines = [
        subscript_cmd,
        define_user_char_cmd_prefix + first_code_n + last_code_m
        + char_data
        + char_data,
    ]
    code = esc_reset + b"".join(lines)
    escparser = ESCParser(code, pdf=False)

    # REPLACEMENT CHARACTER is used if the mapping is not found
    expected_mapping = {1: "\ufffd", 2: "\ufffd"}
    found_charset = escparser.user_defined.charset_mapping
    assert found_charset == expected_mapping

    # No encoding has been used as a reference (no copy rom to ram)
    assert escparser.user_defined.encoding is None

    ############################################################################
    # Changing 1 of the settings should reset the charset of RAM characters
    lines = [
        subscript_cmd,
        define_user_char_cmd_prefix + first_code_n + last_code_m
        + char_data
        + char_data,
        # setting change: switch to proportional mode, should reset all chars
        b"\x1bp\x01",
        # Define only 1 char
        define_user_char_cmd_prefix + first_code_n + first_code_n
        + char_data
    ]
    code = esc_reset + b"".join(lines)
    escparser = ESCParser(code, pdf=False)

    # 1 REPLACEMENT CHARACTER only
    expected = {1: "\ufffd"}
    found_charset = escparser.user_defined.charset_mapping
    assert found_charset == expected

    # No encoding has been used as a reference (no copy rom to ram)
    assert escparser.user_defined.encoding is None
    # RAM settings must reflect the proportional spacing status
    assert escparser.user_defined.settings["proportional_spacing"] is True


def mocked_init(self: RAMCharacters, parent: ESCParser = None, db_filepath: str = None):
    """Mock function used to inject a custom db_filepath attr in the object RAMCharacters

    .. warning:: DO NOT FORGET to update this code (copy/paste from sources).
    """
    self.db_filepath = Path(db_filepath)
    self.register_codec_func = None

    self.encoding = None
    self._settings = None
    self.charset_mapping = {}
    self.database = {}

    self.extract_settings(parent)
    self.load_manual_mapping()


@pytest.mark.parametrize(
    "database_file_content, expected_mapping",
    [
        # Legit file
        (
            """
            {
                "83e1a70_1": {
                    "mode": 1,
                    "proportional_spacing": false,
                    "scripting": null,
                    "1": "Ắ"
                },
                "83e1a70_2": {
                    "mode": 1,
                    "proportional_spacing": false,
                    "scripting": null,
                    "2": "Ệ"
                }
            }
            """,
            {1: "Ắ", 2: "Ệ"},
        ),
        # Empty file
        ("", {1: "\ufffd", 2: "\ufffd"}),
        # Not existing file (tested in the test func) => file must be created
        (None, {1: "\ufffd", 2: "\ufffd"}),
    ],
    ids=[
        "default",
        "empty",
        "not_existing",
    ],
)
def test_database_file(
    tmp_path, normal_char_data, database_file_content, expected_mapping
):
    """Test the use of a pre-filled (but incomplete) mapping file - ESC &

    Also tests decoding functionality of the "user_defined" codec.
    """
    # Build custom mapping file
    # If the content is None, we test the not existing file case
    mocked_db_file = tmp_path / "file.json"
    if database_file_content is not None:
        mocked_db_file.write_text(database_file_content)

    # Send 3 chars
    define_user_char_cmd_prefix = b"\x1b&\x00"
    first_code_n = b"\x01"
    last_code_m = b"\x03"

    lines = [
        define_user_char_cmd_prefix + first_code_n + last_code_m
        + normal_char_data
        + normal_char_data
        + normal_char_data,  # Test the case where the mapping is not in the database
    ]
    code = esc_reset + b"".join(lines)

    func = partialmethod(mocked_init, db_filepath=mocked_db_file)
    with patch.object(RAMCharacters, "__init__", func):
        escparser = ESCParser(code, pdf=False)

        # The code 3 must be a REPLACEMENT CHARACTER
        expected_mapping |= {3: "\ufffd"}
        found_charset = escparser.user_defined.charset_mapping
        assert found_charset == expected_mapping

    # A JSON mapping file should have been created
    assert mocked_db_file.exists()

    # Test the decoding using the codec created
    found = b"\x01\x02\x03".decode(RAM_CHARACTERS_TABLE, errors="replace")
    expected = "".join(expected_mapping.values())
    assert found == expected


@pytest.mark.parametrize(
    "multipoint, typeface_id",
    [
        # cmd ok
        (False, b"\x00"),
        # Enable multipoint/scalable font mode => cmd ignored
        (True, b"\x00"),
        # Typeface id 31: not defined in test dataset => cmd ignored
        (False, b"\x1f"),
    ],
    ids=[
        "default",
        "multipoint_enabled",
        "ukn_typeface",
    ],
)
def test_copy_rom_to_ram(normal_char_data, multipoint, typeface_id):
    """Test the encoding copy from ROM to RAM - ESC :

    The ROM table (current encoding) is used as a base from the user-defined
    characters mapping.

    The command is ignored if multipoint is enabled or typeface not available.

    ESCP2:
        Characters copied from locations 0 to 127
    9pins: (TODO)
        Characters copied from locations 0 to 255;
        TODO: locations from 128 to 255 are taken from the Italic table...
    """
    define_user_char_cmd_prefix = b"\x1b&\x00"
    first_code_n = b"\x01"
    last_code_m = b"\x02"
    cpy_rom_to_ram_cmd_prefix = b"\x1b:\x00"
    multipoint_cmd = b"\x1bX\x00\x10\x00" if multipoint else b""  # ESC X, point_8
    # ESC : is ignored if multipoint is enabled or typeface not available
    is_cmd_ignored = multipoint or typeface_id != b"\x00"

    lines = [
        multipoint_cmd,
        # copy_rom_to_ram using current encoding
        cpy_rom_to_ram_cmd_prefix + typeface_id + b"\x00",
        define_user_char_cmd_prefix + first_code_n + last_code_m
        + normal_char_data
        + normal_char_data,
    ]
    code = esc_reset + b"".join(lines)
    escparser = ESCParser(code, pdf=False)

    # Validate the encoding
    if is_cmd_ignored:
        # If the command is ignored (multipoint & unknown typeface),
        # the base encoding should not be defined => no copy of the current table
        expected_encoding = None
    else:
        # The CURRENT encoding has been used as a reference (no copy rom to ram)
        expected_encoding = escparser.encoding

    assert escparser.user_defined.encoding == expected_encoding

    # Validate the charset mapping size
    if is_cmd_ignored:
        expected = 2
    else:
        expected = 128  # ESCP2/ESCP; TODO 256; 9 pins

    mapping_size = len(escparser.user_defined.charset_mapping)
    assert mapping_size == expected

    # Validate the charset mapping content
    expected_mapping = {1: "\ufffd", 2: "\ufffd"}
    for char_code, unicode_val in expected_mapping.items():
        assert escparser.user_defined.charset_mapping[char_code] == unicode_val


def test_copy_rom_to_ram_settings():
    """The settings (print mode, proportional spacing, scripting)
    must be copied by the command ESC : as well as the command ESC &.
    """
    typeface_id = b"\x00"
    cpy_rom_to_ram_cmd_prefix = b"\x1b:\x00"
    draft_mode_cmd = b"\x1bx\x00"
    proportional_spacing_cmd = b"\x1bp\x01"
    subscript_cmd = b"\x1bS\x01"

    lines = [
        # proportional mode, Draft mode, scripting mode
        # should be reflected in RAM settings
        proportional_spacing_cmd,
        draft_mode_cmd,
        subscript_cmd,
        cpy_rom_to_ram_cmd_prefix + typeface_id + b"\x00",
    ]
    code = esc_reset + b"".join(lines)
    escparser = ESCParser(code, pdf=False)

    # RAM settings must be updated to the parser settings
    assert escparser.user_defined.settings["proportional_spacing"] is True
    assert escparser.user_defined.settings["mode"] == PrintMode.DRAFT
    assert escparser.user_defined.settings["scripting"] == PrintScripting.SUB


def test_shift_upper_charset(normal_char_data):
    """Test select_character_table for table 2 in ESCP2,24/48 pins mode

    .. warning:: Only test shift user-defined characters
        from positions 0 to 127 to positions 128 to 255.

        See also :meth:`test_select_character_table`.
    """
    define_user_char_cmd_prefix = b"\x1b&\x00"
    first_code_n = b"\x01"
    last_code_m = b"\x02"
    cpy_rom_to_ram_cmd_prefix = b"\x1b:\x00"
    # Act on user-defined characters
    select_character_table_cmd = b"\x1bt\x02"

    lines = [
        # copy_rom_to_ram using current encoding
        cpy_rom_to_ram_cmd_prefix + b"\x01\x00",  # typeface 1 (not used)
        define_user_char_cmd_prefix + first_code_n + last_code_m
        + normal_char_data
        + normal_char_data,
        # Shift ram to upper table & use rom for the lower table
        select_character_table_cmd,
        # Set a RAM character at position 1
        # /!\ Not sure if this is OK but the doc doesn't mention anything about it!
        define_user_char_cmd_prefix + first_code_n + first_code_n
        + normal_char_data
    ]
    code = esc_reset + b"".join(lines)
    escparser = ESCParser(code, pdf=False)

    # User-defined chars should be moved to the upper part of the charset
    expected_mapping = {1: "\ufffd", 2: "☻", 129: "\ufffd", 130: "\ufffd"}
    for char_code, unicode_val in expected_mapping.items():
        assert escparser.user_defined.charset_mapping[char_code] == unicode_val


@pytest.mark.parametrize(
    "pins",
    [
        # Table 2 is assigned, user_defined characters are not reachable with ESC t 2
        None,
        # Default table is still in use since table 2 is not reachable.
        24,
        48,
    ],
    ids=[
        "escp2_default",
        "escp_24pins",
        "escp_48pins",
    ],
)
def test_select_character_table(pins):
    """Test the behavior of the ESC t 2 command when a table has been
    assigned (or tried to be) to table 2.


    - ESC/P 2 printers:
        cannot shift user-defined characters if you have previously
        assigned another character table to table 2 using
        the ESC ( t command. Once you have assigned a registered
        table to Table 2, you cannot use it for user-defined characters
        (until you reset the printer with the ESC @ command).
    - 24/48-pin printers, non-ESC/P 2 printers:
        shift user-defined characters unconditionally

    .. seealso:: :meth:`test_shift_upper_charset`.
    """
    # Assign French, cp863 table to table 2
    assign_table2_cmd = b"\x1b(t\x03\x00\x02\x08\x00"
    # Select table 2 or act on user-defined characters
    select_character_table_cmd = b"\x1bt\x02"

    lines = [
        assign_table2_cmd,
        select_character_table_cmd,
    ]
    code = esc_reset + b"".join(lines)
    escparser = ESCParser(code, pins=pins, pdf=False)

    if pins in (24, 48):
        # User-defined character table has been shifted
        # => see test_shift_upper_charset()
        # Default table is still in use since table 2 is not reachable.
        assert escparser.character_table == 1
        assert escparser.character_tables[2] is None
    else:
        # ESCP2 only: table 2 is updated
        assert escparser.character_table == 2
        assert "cp863" == escparser.character_tables[2]


def test_ram_codec():
    """Test encoding/decoding capacity of the "user_defined" codec

    Test the :meth:`ram_codec` module.
    """
    # Create custom encoding
    charset_mapping = {1: "S", 2: "T", 3: "A", 4: "R", 5: "G", 6: "ᐰ", 8: "Ệ"}

    register_codec_func = partial(
        ram_codec.getregentry,
        effective_encoding=RAM_CHARACTERS_TABLE,
        intl_charset=charset_mapping,
    )
    codecs.register(register_codec_func)

    # Test conversions methods
    expected_unicode = "STARGᐰTỆ"
    expected_bytes = b"\x01\x02\x03\x04\x05\x06\x02\x08"

    found_bytes = expected_unicode.encode(RAM_CHARACTERS_TABLE)
    assert found_bytes == expected_bytes

    found_unicode = expected_bytes.decode(RAM_CHARACTERS_TABLE)
    assert found_unicode == expected_unicode

    # Clean environment for further tests
    codecs.unregister(register_codec_func)


def test_select_user_defined_set(tmp_path: Path, normal_char_data: bytes):
    """Test real end-to-end example with user-defined char

    Tested char: \u1430 / ᐰ

    - default encoding
    - user_defined encoding copied from ROM + mapping
    - user_defined encoding copied from ROM without mapping
    """
    # Build custom mapping file
    mocked_db_file = tmp_path / "file.json"
    mocked_db_file.write_text(
        """
        {
            "83e1a70_65": {
                "mode": 1,
                "proportional_spacing": false,
                "scripting": null,
                "65": "ᐰ"
            }
        }
        """
    )

    # Inject font that support the char: FreeSans
    fonts = {
        0: {
            "fixed": (lambda *args: Path("/usr/share/fonts/truetype/firacode/FiraCode-Bold.ttf")),
            "proportional": lambda *_: None,
        },
        1: {
            "fixed": (lambda *args: Path("/usr/share/fonts/truetype/freefont/FreeSans.ttf")),
            "proportional": lambda *_: None,
        },
    }

    # Send 3 chars
    define_user_char_cmd_prefix = b"\x1b&\x00"
    first_code_n = b"\x41"  # Replace 'A'
    # Act on user-defined characters
    select_character_table_cmd = b"\x1bt\x02"
    cpy_rom_to_ram_cmd_prefix = b"\x1b:\x00"
    # Select user-defined characters
    select_user_defined_chars = b"\x1b%\x01"

    # Note: typeface pre-selection by ESC : is not implemented now
    # Manual change is made
    select_typeface_cmd = b"\x1bk\x01"

    lines = [
        select_typeface_cmd,
        # copy_rom_to_ram using current encoding
        cpy_rom_to_ram_cmd_prefix + b"\x01\x00",  # typeface 1 (not used for now)
        define_user_char_cmd_prefix + first_code_n + first_code_n
        + normal_char_data,
        # Shift ram to upper table & use rom for the lower table:
        # 'A' is shifted to code 0xc1 (0x41 + 128);
        # => the 1st 'A' should NOT be modified in the final render
        select_character_table_cmd,
        # Show default string from ROM charset
        b"STARG\xc1TE",
        select_user_defined_chars,
        # Show user-defined string from RAM charset
        b"\r\n" b"STARG\xc1TE",
        # Test the reset of the RAM charset
        # \xc1 (193) is outside the 128 copied characters from the ROM encoding
        # => so, undefined
        cpy_rom_to_ram_cmd_prefix + b"\x01\x00",
        b"\r\n" b"STARG\xc1TE",
    ]
    code = esc_reset + b"".join(lines)

    processed_file = tmp_path / "test_select_user_defined_set.pdf"
    func = partialmethod(mocked_init, db_filepath=mocked_db_file)
    with patch.object(RAMCharacters, "__init__", func):
        _ = ESCParser(
            code, pins=None, available_fonts=fonts, output_file=processed_file
        )

    pdf_comparison(processed_file)
