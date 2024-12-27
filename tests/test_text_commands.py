#  ESCParser is a software allowing to convert EPSON ESC/P, ESC/P2
#  printer control language files into PDF files.
#  Copyright (C) 2024  Ysard
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
# Standard imports
import itertools as it
from pathlib import Path
import pytest
from unittest.mock import patch
import struct

# Custom imports
from lark.exceptions import UnexpectedToken

# Local imports
import escparser.commons as cm
from .misc import format_databytes, pdf_comparison
from .misc import DIR_DATA, esc_reset, cancel_bold, select_10cpi, select_12cpi, select_15cpi, select_condensed_printing, unset_condensed_printing, double_width
from .helpers.diff_pdf import is_similar_pdfs
from escparser.parser import ESCParser, PrintMode, PrintScripting, PrintControlCodes


@pytest.mark.parametrize(
    "format_databytes",
    [
        # Test "0" as a chr (0x30) for d1; move to tb0
        b"\x1B(t\x03\x00\x30\x08\x00" + cancel_bold,
        # Test d1 as an int; move to tb0 to tb3
        b"\x1B(t\x03\x00\x00\x08\x00" + cancel_bold,
        b"\x1B(t\x03\x00\x01\x08\x00" + cancel_bold,
        b"\x1B(t\x03\x00\x02\x08\x00" + cancel_bold,
        b"\x1B(t\x03\x00\x03\x08\x00" + cancel_bold,
    ],
    # First param goes in the 'request' param of the fixture format_databytes
    indirect=["format_databytes"],
    ids=[
        "PC863 (Canada-French)_tb0",
        "PC863 (Canada-French)_tb0",
        "PC863 (Canada-French)_tb1",
        "PC863 (Canada-French)_tb2",
        "PC863 (Canada-French)_tb3",
    ],
)
def test_assign_character_table(format_databytes):
    """Assign character table - ESC ( t

    Play with d2, d3 to assign d1 table.
    """
    print(format_databytes)

    escparser = ESCParser(format_databytes, pdf=False)
    d1_slot = format_databytes[5 + 2]  # +2 for the ESC reset added by the fixture
    if d1_slot >= 0x30:
        d1_slot -= 0x30

    print("table slot:", d1_slot)
    expected = "cp863"
    assert escparser.character_tables[d1_slot] == expected


@pytest.mark.parametrize(
    "format_databytes",
    [
        # Assign character table; Table with id 4 doesn't exist - ESC ( t
        b"\x1B(t\x03\x00\x04\x08\x00" + cancel_bold,
        # International charset id 0x0e doesn't exist - ESC R
        b"\x1BR\x0e" + cancel_bold,
        # Wrong typeface ID - ESC k
        b"\x1B[\x0b" + cancel_bold,
        # Wrong character table ID - ESC t
        b"\x1Bt\x04" + cancel_bold,
        # More than 128 is not allowed for intercharacter space - ESC SP
        b"\x1b\x20\x80",
    ],
    # First param goes in the 'request' param of the fixture format_databytes
    indirect=["format_databytes"],
    ids=[
        "ukn_tb4",
        "charset_ukn",
        "typeface_ukn",
        "table_ukn",
        "intercharacter_space_value_not_allowed",
    ],
)
def test_wrong_commands(format_databytes):
    """Test various commands with wrong parameters that will raise a Lark exception"""
    with pytest.raises(UnexpectedToken, match=r"Unexpected token Token.*"):
        _ = ESCParser(format_databytes, pdf=False)


@pytest.mark.parametrize(
    "format_databytes",
    [
        # ESC ( t; Assign character table; Combination 0,8 for d2,d3 doesn't exist
        b"\x1B(t\x03\x00\x30\x00\x08" + cancel_bold,
    ],
    # First param goes in the 'request' param of the fixture format_databytes
    indirect=["format_databytes"],
    ids=[
        "ukn_d2_d3",
    ],
)
def test_bad_assign_character_table(format_databytes):
    """Assign character table - ESC ( t

    Play with not expected values of d2, d3.
    """
    with pytest.raises(KeyError, match=r"\([0-9], [0-9]\)"):
        _ = ESCParser(format_databytes, pdf=False)


@pytest.mark.parametrize(
    "format_databytes",
    [
        # Uk
        b"\x1BR\x03" + cancel_bold,
        # Korea
        b"\x1BR\x0d" + cancel_bold,
        # Legal
        b"\x1BR\x40" + cancel_bold,
    ],
    # First param goes in the 'request' param of the fixture format_databytes
    indirect=["format_databytes"],
    ids=[
        "charset_uk",
        "charset_korea",
        "charset_legal",
    ],
)
def test_select_international_charset(format_databytes):
    """select_international_charset - ESC R"""
    print(format_databytes)

    escparser = ESCParser(format_databytes, pdf=False)
    expected = format_databytes[2 + 2]
    charset_name = cm.charset_mapping[expected]

    assert (
        escparser.international_charset == expected
    ), f"Expected charset {charset_name}"


@patch(
    "escparser.parser.typefaces",
    {
        0: (lambda *args: "FiraCode-Bold", "truetype/firacode/{}.ttf"),
        2: ("FiraCode-Regular", "truetype/firacode/{}.ttf"),
    },
)
def test_select_typeface():
    """Test internal changes in ESCParser object due to select_typeface - ESC k

    .. seealso:: For higher-level test cf :meth:`test_fonts`.
    """
    format_databytes = b"\x1Bk\x02"
    escparser = ESCParser(format_databytes)
    expected = format_databytes[2]
    assert escparser.typeface == expected, "Wrong typeface selected"

    # TODO: _fontname should be at FiraCode-Regular but it's Helvetica ????
    print(escparser.current_fontpath, escparser.current_pdf._fontname)
    assert escparser.current_fontpath == "truetype/firacode/FiraCode-Regular.ttf"

    # wrong typeface ID => switch to default (0) which is FiraCode-Bold
    format_databytes = b"\x1Bk\x0c"
    escparser = ESCParser(format_databytes)
    expected = 0
    assert escparser.typeface == expected, "Wrong typeface selected"

    print(escparser.current_fontpath, escparser.current_pdf._fontname)
    assert escparser.current_fontpath == "truetype/firacode/FiraCode-Bold.ttf"


@pytest.mark.parametrize(
    "format_databytes",
    [
        # table 0
        b"\x1Bt\x30" + cancel_bold,
        b"\x1Bt\x00" + cancel_bold,
        # table 1
        b"\x1Bt\x31" + cancel_bold,
        b"\x1Bt\x01" + cancel_bold,
    ],
    # First param goes in the 'request' param of the fixture format_databytes
    indirect=["format_databytes"],
    ids=[
        "use_tb0_chr",
        "use_tb0_int",
        "use_tb1_chr",
        "use_tb1_int",
    ],
)
def test_select_character_table(format_databytes):
    """Select character table - ESC t 0-3\x00-\x03"""
    print(format_databytes)

    escparser = ESCParser(format_databytes, pdf=False)
    expected = format_databytes[2 + 2]

    if expected >= 0x30:
        expected -= 0x30

    assert escparser.character_table == expected


def test_horizontal_tabs(tmp_path: Path):
    """Test horizontal tabs config & cancellation - ESC D, ESC g, HT

    - default config tab
    - set config tab with similar config than default config
    - set config tab 4 char per tab: no align for the last word (next tab is the space char after it)
    - cancel all tabs
    - configure 2 tabs
    - test the use of tab 3 (no effect)

    - test expected htab list with custom self.character_pitch
    """
    coucou = b"coucou"
    pouet = b"pouet"
    tab = b"\x09"
    esc_htab = b"\x1bD"
    select_15cpi = b"\x1bg"
    lines = [
        # default: tabs of 8 columns
        tab + coucou + tab + coucou,

        # 4 tabs of 8 columns (should be aligned with the previous line)
        esc_htab + b"\x08\x10\x12\x1a\x00",

        tab + coucou + tab + coucou,
        tab + pouet  + tab + coucou,

        # 3 tabs of 4 columns
        esc_htab + b"\x04\x08\x0c\x00",

        tab + coucou + tab + coucou,
        tab + pouet + tab + tab + coucou,
        tab + pouet + tab + coucou,

        # cancel all tabs
        esc_htab + b"\x00",
        coucou,

        # 1 tab of 1 column + 1 tab of 7 columns
        esc_htab + b"\x01\x08\x00",
        tab + coucou + tab + coucou,
        # test a 3rd tab
        tab + coucou + tab + coucou + tab + b"aaa",
    ]
    processed_file = tmp_path / "test_horizontal_tabs.pdf"

    code = esc_reset + b"\r\n".join(lines)
    escparser = ESCParser(code, pins=None, output_file=str(processed_file))

    expected = [0.1, 0.8] + [0] * 30
    assert escparser.horizontal_tabulations == expected

    # comparaison of PDFs
    # Keep track of the generated file in /tmp in case of error
    backup_file = Path("/tmp/" + processed_file.name)
    backup_file.write_bytes(processed_file.read_bytes())

    ret = is_similar_pdfs(processed_file, Path(DIR_DATA + processed_file.name))
    assert ret, f"Problematic file is saved at <{backup_file}> for further study."
    # All is ok => delete the generated file
    backup_file.unlink()

    # No change expected
    escparser = ESCParser(code, pins=9, output_file=str(processed_file))
    assert escparser.horizontal_tabulations == expected

    # With a 1/15 character pitch the positions of the columns should be different
    code += b"\r\n".join(
        [
            select_15cpi,
            esc_htab + b"\x01\x08\x00",
        ]
    )
    escparser = ESCParser(code, pins=None, output_file=str(processed_file))
    expected = [1 / 15, 8 / 15] + [0] * 30
    assert escparser.horizontal_tabulations == expected

    # clean
    processed_file.unlink()


def test_select_letter_quality_or_draft():
    """ESC x Select LQ or draft"""
    dataset = [
        (b"\x1bx\x00", PrintMode.DRAFT),
        (b"\x1bx\x30", PrintMode.DRAFT),
        (b"\x1bx\x01", PrintMode.LQ),
        (b"\x1bx\x31", PrintMode.LQ),
        # LQ mode is forced on ESCP2 printers if proportional spacing is enabled
        (b"\x1bx\x00" + b"\x1bp\x01", PrintMode.LQ),
        # Mode is not touched on ESCP2 printers if proportional spacing
        # and multipoint mode are enabled
        (b"\x1bx\x00" + b"\x1bX\x01\x00\x00", PrintMode.DRAFT)
    ]
    for code, expected in dataset:
        escparser = ESCParser(esc_reset + code, pdf=False)
        assert escparser.mode == expected


def test_set_script_printing():
    """ESC S sup/subscripting, ESC T cancel scripting"""
    dataset = [
        (b"\x1bS\x00", PrintScripting.SUP),
        (b"\x1bS\x30", PrintScripting.SUP),
        (b"\x1bS\x01", PrintScripting.SUB),
        (b"\x1bS\x31", PrintScripting.SUB),
        # Default
        (b"", None),
        # ESC S is canceled by ESC T
        (b"\x1bS\x31\x1bT", None),
    ]
    for code, expected in dataset:
        escparser = ESCParser(esc_reset + code, pdf=False)
        assert escparser.scripting == expected


def test_charset_tables(tmp_path: Path):
    """Print various pangrams in various languages using their own encoding

    Cover mainly:

        - Assign character table, ESC ( t
        - Select character table, ESC t

    .. note:: Pangrams source: https://en.wikipedia.org/wiki/Pangram

    .. todo:: Support more (custom) encodings.
    """
    english_pangram = "The quick brown fox jumps over the lazy dog.".encode("cp437")
    # The Italic table is symmetric, all italic characters are in the upper part
    english_italic_pangram = bytearray(i + 0x80 for i in english_pangram)
    # 8 0; œ not supported
    french_pangram = "Portez ce vieux whisky au juge blond qui fume. Voie ambigüe d'un coeur qui au zéphyr préfère les jattes de kiwis.".encode("cp863")
    # 10 0
    czech_pangram = "Příliš žluťoučký kůň úpěl ďábelské ódy.".encode("cp852")
    # estonian_pangram = "See väike mölder jõuab rongile hüpata."
    # finnish_pangram = "Törkylempijävongahdus."
    # 1, 16; τὴν not supported
    greek_pangram = "Ξεσκεπάζω την ψυχοφθόρα βδελυγμία.".encode("cp737")
    # 15, 0; τὴν not supported
    greek_pangram_2 = "Ξεσκεπάζω την ψυχοφθόρα βδελυγμία.".encode("cp869")
    # 29, 7; τὴν not supported
    greek_pangram_3 = "Ξεσκεπάζω την ψυχοφθόρα βδελυγμία.".encode("iso8859_7")
    # 29, 16
    german_pangram = "Victor jagt zwölf Boxkämpfer quer über den großen Sylter Deich.".encode("latin_1")
    # 24, 0
    icelandic_pangram = "Kæmi ný öxi hér, ykist þjófum nú bæði víl og ádrepa.".encode("cp861")
    # 11, 0
    turkish_pangram = "Pijamalı hasta yağız şoföre çabucak güvendi.".encode("cp857")
    # 42, 0
    arabic_pangram = "نص حكيم له سر قاطع وذو شأن عظيم مكتوب على ثوب أخضر ومغلف بجلد أزرق".encode("cp720")
    # 14, 0
    russian_pangram = "Съешь ещё этих мягких французских булок, да выпей же чаю".encode("cp866")
    # 18, 0
    thai_pangram = "นายสังฆภัณฑ์ เฮงพิทักษ์ฝั่ง ผู้เฒ่าซึ่งมีอาชีพเป็นฅนขายฃวด ถูกตำรวจปฏิบัติการจับฟ้องศาล ฐานลักนาฬิกาคุณหญิงฉัตรชฎา ฌานสมาธิ".encode("iso8859_11")
    # 12, 0
    hebrew_pangram = "איש עם זקן טס לצרפת ודג בחכה".encode("cp862")
    # 25, 0
    portuguese_pangram = "Ré só que vê galã sexy pôr kiwi talhado à força em baú põe juíza má em pânico. Œœ".encode("brascii")

    # ESC ( t d1 d2 d3
    table_0 = b"\x1bt\x00"  # ESC t 0 Italic
    table_1 = b"\x1bt\x01"  # ESC t 1 cp437 (default table)
    table_3 = b"\x1bt\x03"  # ESC t 3 cp437
    point_8 = b"\x1bX\x00\x10\x00"  # ESC X
    # left_margin = b"\x1bl\x03"  # ESC l
    cancel_left_margin = b"\x1bl\x00"  # ESC l

    lines = [
        esc_reset,
        cancel_left_margin,
        point_8,
        # b"\x1bk\x00", # Roman (default)
        # b"\x1bk\x02", # Courier
        b"\x1bk\x01",  # Sans Serif
        b"English, cp437 (default)",
        english_pangram,
        table_3 + b"English table 2, cp437 (default)",
        table_1 + english_pangram,
        table_3 + b"Italic table 0, italic (default) (FOR NOW, should show only the same characters as cp437)",
        table_0 + english_italic_pangram,
        # From now, use table 1 for pangrams, table 3 (cp437) for other text
        # See the last 2 bytes of the command to know d2 & d3 values
        table_3 + b"French, cp863",
        table_1 + b"\x1b(t\x03\x00\x01\x08\x00" + french_pangram,
        table_3 + b"Czech, cp852",
        table_1 + b"\x1b(t\x03\x00\x01\x0a\x00" + czech_pangram,
        table_3 + b"Greek, cp737",
        table_1 + b"\x1b(t\x03\x00\x01\x01\x10" + greek_pangram,
        table_3 + b"Greek, cp869",
        table_1 + b"\x1b(t\x03\x00\x01\x0f\x00" + greek_pangram_2,
        table_3 + b"Greek, iso8859_7",
        table_1 + b"\x1b(t\x03\x00\x01\x1d\x07" + greek_pangram_3,
        table_3 + b"German, latin_1",
        table_1 + b"\x1b(t\x03\x00\x01\x1d\x10" + german_pangram,
        table_3 + b"Icelandic, cp861",
        table_1 + b"\x1b(t\x03\x00\x01\x18\x00" + icelandic_pangram,
        table_3 + b"Turkish, cp857",
        table_1 + b"\x1b(t\x03\x00\x01\x0b\x00" + turkish_pangram,
        table_3 + b"Arabic, cp720",
        table_1 + b"\x1b(t\x03\x00\x01\x2a\x00" + arabic_pangram,
        table_3 + b"Russian, cp866",
        table_1 + b"\x1b(t\x03\x00\x01\x0e\x00" + russian_pangram,
        table_3 + b"Thai, iso8859_11",
        table_1 + b"\x1b(t\x03\x00\x01\x12\x00" + thai_pangram,
        table_3 + b"Hebrew, cp862",
        table_1 + b"\x1b(t\x03\x00\x01\x0c\x00" + hebrew_pangram,
        table_3 + b"Portuguese, brascii",
        table_1 + b"\x1b(t\x03\x00\x01\x19\x00" + portuguese_pangram ,
        table_3 + b"Greek - Not supported charset 4,0 (should not crash)",
        # Double table selection to cover the two logger error outputs (assign + select)
        table_1 + b"\x1b(t\x03\x00\x01\x04\x00" + table_1 + greek_pangram,
    ]

    code = b"\r\n".join(lines)
    processed_file = tmp_path / "test_charset_tables.pdf"
    _ = ESCParser(code, output_file=str(processed_file))

    pdf_comparison(processed_file)


@pytest.mark.parametrize(
    "assign_table_cmd, encoding",
    [
        # table 1 is assigned
        # Force latin1 usage by simulating german encoding
        # PS: Here we use latin1 (which is a C implementation) to test the switch
        # to iso8859_1 which is a pure Python implementation.
        (b"\x1b(t\x03\x00\x01\x1d\x10", "latin_1"),
        # This encoding is implemented in C without a pure Python alternative.
        # Here, we test the fallback process that rebuilds the decoding table on the fly
        (b"\x1b(t\x03\x00\x01\x02\x00", "cp932"),
    ],
    ids=[
        "latin_1",
        "cp932",
    ],
)
def test_international_charsets(tmp_path: Path, assign_table_cmd, encoding):
    """Test injection of 12 characters in the current character table (1 by default) - ESC R

    Custom encoding/decoding codecs are tested here.
    """
    point_8 = b"\x1BX\x00\x10\x00" # 0x10 => 16 / 2 = 8
    roman = b"\x1B\x6B\x00"
    select_international_charset_prefix = b"\x1bR"

    lines = [
        esc_reset + point_8 + roman + assign_table_cmd + "table with international mods".encode(encoding),
    ]
    # Select intl
    for intl_id, charset in cm.international_charsets.items():
        print(intl_id)
        lines.append((cm.charset_mapping[intl_id] + ":").encode(encoding))
        # Send the ESC command + the bytes to be encoded
        lines.append(select_international_charset_prefix + intl_id.to_bytes() + bytes(bytearray(charset.keys())))
        # lines.append(select_international_charset_prefix + b"\x00")

    code = b"\r\n".join(lines)
    processed_file = tmp_path / "test_international_charset_tables.pdf"
    escparser = ESCParser(code, output_file=str(processed_file))

    # Check that the base encoding is in use
    found_encoding = escparser.character_tables[escparser.character_table]
    assert found_encoding == encoding

    pdf_comparison(processed_file)


def test_custom_codec():
    """Test custom encoding/decoding codecs behavior

    Test brascii codec: https://en.wikipedia.org/wiki/BraSCII almost 8859-1 except 2 chars
    """
    expected_text = "BRASCII: Œ, œ"
    binary = expected_text.encode("brascii")
    found = binary.decode("brascii")

    assert found == expected_text


def test_fonts(tmp_path: Path):
    """Print english pangram to test font switching & support

    Cover mainly:

        - Select typeface, ESC k

    .. seealso:: For lower-level test cf :meth:`test_select_typeface`.
    """
    test_phrase = b"The quick brown fox jumps over the lazy dog; THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG; 1234567890"
    cancel_left_margin = b"\x1bl\x00"  # ESC l
    point_8 = b"\x1BX\x00\x10\x00"  # ESC X: 0x10 => 16 / 2 = 8 points
    roman = b"\x1Bk\x00"  # ESC k
    # Test typefaces
    lines = [
        esc_reset + cancel_left_margin + point_8,
        b"Default font (Roman):",
        test_phrase,
        b"Roman:",
        roman + test_phrase,
        roman + b"Sans serif:",
        b"\x1Bk\x01" + test_phrase,
        roman + b"Courier:",
        b"\x1Bk\x02" + test_phrase,
        roman + b"Prestige:",
        b"\x1Bk\x03" + test_phrase,
        roman + b"OCR-B:",
        b"\x1Bk\x05" + test_phrase,
        roman + b"OCR-A:",
        b"\x1Bk\x06" + test_phrase,
        roman + b"Orator:",
        b"\x1Bk\x07" + test_phrase,
        roman + b"Script-C:",
        b"\x1Bk\x09" + test_phrase,
        roman + b"Roman T:",
        b"\x1Bk\x0a" + test_phrase,
        roman + b"SV Jittra (not available, fallback to default):",
        b"\x1Bk\x1f" + test_phrase,
    ]

    code = b"\r\n".join(lines)
    processed_file = tmp_path / "test_fonts.pdf"
    _ = ESCParser(code, output_file=str(processed_file))

    pdf_comparison(processed_file)


def test_select_font_by_pitch_and_point(tmp_path: Path):
    """Test the pitch and point attributes of the font - ESC X

    .. note:: pitch is tested in :meth:`test_character_pitch_changes`.
    """
    # Change point size
    # ESC X: 8 cpi (m, nL, nH)
    # The nL value is divided by 2 later
    cancel_left_margin = b"\x1bl\x00"  # ESC l
    point_8 = b"\x1bX\x00\x10\x00"  # ESC X: 0x10 => 16 / 2 = 8 points
    alphabet = b"abcdefghijklmnopqrstuvwxz"
    sans_serif = b"\x1bk\x01"
    lines = [
        esc_reset + cancel_left_margin + point_8,
        # Use Sans Serif
        sans_serif,
        point_8 + b"Font size 8",
        b"\x1bX\x00\x10\x00" + alphabet,  # 8
        point_8 + b"Font size 10 (10.5)",
        b"\x1bX\x00\x15\x00" + alphabet,  # 10 (10.5)
        point_8 + b"Font size 12",
        b"\x1bX\x00\x18\x00" + alphabet,  # 12
        point_8 + b"Font size 14",
        b"\x1bX\x00\x1c\x00" + alphabet,  # 14
        point_8 + b"Font size 16",
        b"\x1bX\x00\x20\x00" + alphabet,  # 16
        point_8 + b"Font size 18",
        b"\x1bX\x00\x24\x00" + alphabet,  # 18
        point_8 + b"Font size 20 (21)",
        b"\x1bX\x00\x28\x00" + alphabet,  # 20 (21)
        point_8 + b"Font size 22",
        b"\x1bX\x00\x2c\x00" + alphabet,  # 22
        point_8 + b"Font size 24",
        b"\x1bX\x00\x30\x00" + alphabet,  # 24
        point_8 + b"Font size 26",
        b"\x1bX\x004\x00" + alphabet,  # 26
        point_8 + b"Font size 30",
        b"\x1bX\x00\x3c\x00" + alphabet,  # 30
        point_8 + b"Font size 40",
        b"\x1bX\x00\x40\x00" + alphabet,  # 40
    ]

    code = b"\r\n".join(lines)
    processed_file = tmp_path / "test_select_font_by_pitch_and_point.pdf"
    _ = ESCParser(code, output_file=str(processed_file))

    pdf_comparison(processed_file)


@pytest.mark.parametrize(
    "format_databytes, expected_cpi, pins",
    [
        ## Non-multipoint mode
        (select_10cpi + double_width, 5, None),
        (select_12cpi + double_width, 6, None),
        (select_15cpi + double_width, 7.5, None),
        (select_10cpi, 10, None),
        (select_12cpi, 12, None),
        (select_15cpi, 15, None),
        (select_10cpi + select_condensed_printing, 17.14, None),
        (select_12cpi + select_condensed_printing, 20, None),
        # ESCP2: select_15cpi + condensed: condensed is ignored
        (select_15cpi + select_condensed_printing, 15, None),
        # 9 pins: select_15cpi + condensed: condensed is set
        (select_15cpi + select_condensed_printing, 15, 9),
        # Scalable fonts/multipoint then multipoint should be reset by ESC P
        # ESC X: m = 0x10: 360/16 cpi
        (b"\x1bX\x10\x00\x00" + select_10cpi, 10, None),
        # Proportional + condensed = 2*character_pitch
        # (Note: character_pitch should be dynamic in this case)
        (b"\x1bp\x01" + select_condensed_printing, 20, None),
        # Idem but exiting condensed forces to return to the original cpi
        (b"\x1bp\x01" + select_condensed_printing + unset_condensed_printing, 10, None),
        # Proportional + condensed but 9pins: condensed is ignored
        (b"\x1bp\x01" + select_condensed_printing, 10, 9),
    ],
    # First param goes in the 'request' param of the fixture format_databytes
    indirect=["format_databytes"],
    ids=[
        "select_10cpi+double_width_5cpi",
        "select_12cpi+double_width_6cpi",
        "select_15cpi+double_width_7.5cpi",
        "select_10cpi_10cpi",
        "select_12cpi_12cpi",
        "select_15cpi_15cpi",
        "select_10cpi+condensed_17.12cpi",
        "select_12cpi+condensed_20cpi",
        "select_15cpi+condensed_ignored_15cpi",
        "select_15cpi+condensed_15cpi_9pins",
        "select_10cpi_exit_multipoint",
        "proportional+condensed_20cpi",
        "proportional+condensed_set/unset_10cpi",
        "proportional+condensed_9pins"
    ],
)
def test_character_pitch_changes(format_databytes: bytes, expected_cpi: float, pins: int | None):
    """Test character pitch in NON-multipoint mode

    Cover: ESC P, ESC M, ESC g (select 10, 12, 15 cpi), double width, condensed, ESC X (pitch)
    """
    escparser = ESCParser(format_databytes, pdf=False, pins=pins)

    assert 1 / escparser.character_pitch == expected_cpi
    assert not escparser.multipoint_mode


@pytest.mark.parametrize(
    "format_databytes, expected_cpi, pins",
    [
        ## Multipoint mode
        # ESC X: m = 0x12: 360/18 = 20 cpi
        (b"\x1bX\x12\x00\x00", 20, None),
        (b"\x1bX\x12\x00\x00" + select_condensed_printing, 20, None)
    ],
    # First param goes in the 'request' param of the fixture format_databytes
    indirect=["format_databytes"],
    ids=[
        "multipoint_20cpi",
        "multipoint_condensed_ignored_20cpi",
    ],
)
def test_character_pitch_changes_multipoint(format_databytes: bytes, expected_cpi: float, pins: int | None):
    """Test character pitch in multipoint mode

    Cover: ESC X (pitch)
    """
    escparser = ESCParser(format_databytes, pdf=False, pins=pins)

    assert 1 / escparser.character_pitch == expected_cpi
    assert escparser.multipoint_mode is True
    assert not escparser.condensed  # Same as in test_condensed_mode


@pytest.mark.parametrize(
    "format_databytes, expected, pins",
    [
        # ESCP2: select_15cpi: condensed is ignored
        (select_15cpi + select_condensed_printing, False, None),
        # 9 pins: select_15cpi: condensed is set
        (select_15cpi + select_condensed_printing, True, 9),
        # Multipoint mode: condensed is ignored
        (b"\x1bX\x12\x00\x00" + select_condensed_printing, False, None),
        # Proportional spacing + 9pins: condensed is ignored
        (b"\x1bp\x01" + select_condensed_printing, False, 9),
        # Proportional spacing: condensed is set
        (b"\x1bp\x01" + select_condensed_printing, True, None),
        # ESC !, master cmd
        (b"\x1b!\x04", True, None),
    ],
    # First param goes in the 'request' param of the fixture format_databytes
    indirect=["format_databytes"],
    ids=[
        "select_15cpi",
        "select_15cpi_9pins",
        "multipoint",
        "proportional_9pins",
        "proportional",
        "master_cmd",
    ],
)
def test_condensed_mode(format_databytes: bytes, expected: float, pins: int | None):
    """Test condensed mode conditions, see :meth:`condensed` - SI, ESC SI, ESC !"""
    escparser = ESCParser(format_databytes, pdf=False, pins=pins)
    assert escparser.condensed == expected


@pytest.mark.parametrize(
    "format_databytes, expected",
    [
        # ESC X: multipoint mode
        (b"\x1bX\x01\x00\x00", True),
        (b"\x1bX\x00\x00\x00", False),
        # ESC p
        (b"\x1bp\x01", True),
        (b"\x1bp\x00", False),
        # ESC !
(       b"\x1b!\x02", True),
        (b"\x1b!\x00", False),
    ],
    # First param goes in the 'request' param of the fixture format_databytes
    indirect=["format_databytes"],
    ids=[
        "ESC_X_enable",
        "ESC_X_disable",
        "ESC_p_enable",
        "ESC_p_disable",
        "ESC_!_enable",
        "ESC_!_disable",
    ],
)
def test_proportional_mode(format_databytes: bytes, expected: bool):
    """Test proportional mode related commands - ESC X, ESC p, ESC !

    .. seealso:: :meth:`test_select_letter_quality_or_draft` for proportional
        spacing & print mode combinations.
    """
    escparser = ESCParser(format_databytes, pdf=False)
    assert escparser.proportional_spacing == expected


def test_set_intercharacter_space(tmp_path: Path):
    """Test intercharacter space size - ESC SP

    Also tests text scripting which should support the setting.
    """
    intercharacter_space_prefix = b"\x1b\x20"
    # Disable multipoint mode used by point_8 because this mode ignores the
    # ESC SP command => so use ESC p 0
    reset_intercharacter_space = b"\x1bp\x00"
    enable_upperscripting = b"\x1bS\x00"
    disable_upperscripting = b"\x1bT"
    point_8 = b"\x1bX\x00\x10\x00"  # ESC X: 0x10 => 16 / 2 = 8 points
    alphabet = b"abcdefghijklmnopqrstuvwxz"
    lines = [
        esc_reset,
        point_8 + b"Intercharacter space from 0 to 128 (steps 20)"
        + reset_intercharacter_space
    ]
    for i in range(0, 128, 20):
        lines.append(intercharacter_space_prefix + i.to_bytes() + alphabet)

    # Same thing but with upper scripting text
    lines.append(
        point_8 + b"Intercharacter space from 0 to 128 (steps 20) for scripting text"
        + reset_intercharacter_space + enable_upperscripting
    )
    for i in range(0, 128, 20):
        lines.append(intercharacter_space_prefix + i.to_bytes() + alphabet)
    lines.append(disable_upperscripting)

    code = b"\r\n".join(lines)
    processed_file = tmp_path / "test_intercharacter_space.pdf"
    _ = ESCParser(code, output_file=str(processed_file))

    pdf_comparison(processed_file)


@pytest.mark.parametrize(
    "format_databytes, pins, expected",
    [
        (b"", None, 1 / 6),
        (b"\x1b0", None, 1 / 8),
        (b"\x1b0", 9, 1 / 8),
        (b"\x1b1", 9, 7 / 72),
        # ESC 0 then ESC 2
        (b"\x1b0\x1b2", 9, 1 / 6),
        (b"\x1b3\x02", None, 2 / 180),
        (b"\x1b3\x02", 9, 2 / 216),
        (b"\x1b+\x02", None, 2 / 360),
        (b"\x1bA\x02", None, 2 / 60),
        (b"\x1bA\x02", 9, 2 / 72),
    ],
    # First param goes in the 'request' param of the fixture format_databytes
    indirect=["format_databytes"],
    ids=[
        "default",
        "set_18_line_spacing",
        "set_18_line_spacing_9pins",
        "set_772_line_spacing_9pins",
        "unset_18_line_spacing",
        "set_n180_line_spacing",
        "set_n180_line_spacing_9pins",
        "set_n360_line_spacing",
        "set_n60_line_spacing",
        "set_n60_line_spacing_9pins",
    ],
)
def test_linespacing(format_databytes, pins: int | None, expected: float):
    """Test various linespacing commands

    Cover:

        - set_18_line_spacing, ESC 0
        - unset_18_line_spacing, ESC 2
        - set_n180_line_spacing, ESC 3
        - set_n360_line_spacing, ESC +
        - set_n60_line_spacing, ESC A
        - set_772_line_spacing, ESC 1
    """
    escparser = ESCParser(format_databytes, pins=pins, pdf=False)
    assert escparser.current_line_spacing == expected


def test_backspace():
    """Test backspace - ESC SP"""
    # backspace when the cursor is already at the letfmost position is ignored
    backspace = b"\x08"
    code = esc_reset + backspace
    escparser = ESCParser(code, pdf=False)
    assert escparser.cursor_x == escparser.left_margin

    # Move cursor_x by 1 inch ESC $ 60 (60/60)
    absolute_h_pos = b"\x1b$\x3c\x00"
    code = esc_reset + absolute_h_pos + backspace
    escparser = ESCParser(code, pdf=False)
    # (x pos from ESC $) - (offset from backspace)
    expected = (1 + escparser.left_margin) - (escparser.character_pitch + escparser.extra_intercharacter_space)
    assert escparser.cursor_x == expected


@pytest.mark.parametrize(
    "pins, expected_filename",
    [
        (None, "test_double_width_height_escp2.pdf"),
        (9, "test_double_width_height_9pins.pdf"),
    ],
    ids=[
        "ESCP2",
        "9pins",
    ],
)
def test_double_width_height(tmp_path: Path, pins: int, expected_filename: str):
    """Test combinations of double-width, double-height modes

    .. note:: About 9 pins:
        In 9 pins mode, double-height should temporarily stop upper/subscripting,
        condensed font and Draft printing.

    :param pins: Configure the number of pins of the printer.
    :param expected_filename: Test pdf used as a reference.
    """
    # Disable multipoint mode used by point_8 because this mode ignores the
    # ESC SP command => so use ESC p 0
    reset_intercharacter_space = b"\x1bp\x00"
    point_8 = b"\x1bX\x00\x10\x00"  # ESC X: 0x10 => 16 / 2 = 8 points
    point_21 = b"\x1BX\x00\x2a\x00"  # ESC X: 0x2a => 42 / 2 = 21 points
    # double-width
    double_width = b"\x1BW\x01"
    reset_double_width = b"\x1BW\x00"
    # double-height
    double_height = b"\x1Bw\x01"
    reset_double_height = b"\x1Bw\x00"

    pangram = b"The quick brown fox jumps over the lazy dog"

    lines = [
        esc_reset,
        point_8 + b"Normal width (10.5 cpi)" + reset_intercharacter_space,
        pangram,
        point_8 + b"Double point-size (21 cpi)" + reset_intercharacter_space,
        point_21 + pangram,
        point_8 + b"Double width (ESC W) (horizontal scale * 2)" + reset_intercharacter_space,
        double_width + pangram + reset_double_width,
        point_8 + b"Double height (ESC w) (point-size * 2 + horizontal scale / 2)" + reset_intercharacter_space,
        double_height + pangram + reset_double_height,
        # Should more or less correspond to 2 x 10.5 cpi
        point_8 + b"Double height + width (point-size * 2 + horizontal scale * 2)" + reset_intercharacter_space,
        double_width + double_height + pangram + reset_double_height + reset_double_width,
        point_8 + b"Back to normal width (10.5 cpi)" + reset_intercharacter_space,
        pangram,
        b"\r\n"
    ]

    # Mix with scripting with various interlaced commands
    enable_upperscripting = b"\x1bS\x00"
    disable_upperscripting = b"\x1bT"
    lines += [
        point_8 + b"NOTE: In " +
        (b"9pins mode, double-height should temporarily stop " if pins else b"ESCP2, double-height can be used with ") +
        b"upper/subscripting, condensed font and Draft printing.",
        point_8 + b"upperscripting enabled for ref" + reset_intercharacter_space,
        enable_upperscripting + pangram + disable_upperscripting,
        point_8 + b"double-height enabled for ref" + reset_intercharacter_space,
        double_height + pangram + reset_double_height,
        point_8 + b"upperscripting should have " +
        (b"no effect in 9pins mode" if pins else b"effect in ESCP2") + reset_intercharacter_space,
        enable_upperscripting + double_height + pangram + reset_double_height + disable_upperscripting,
        # Handle the risk to reactivate scripting while it was disabled by a legit
        # command before exiting double-height
        point_8 +
        (b"in 9pins mode make sure scripting is enabled, then disabled by double-height,"
        b" then disabled, then not set anymore when exiting double-height"
        if pins else
        b"in ESCP2 make sure scripting is not interrupted during double-height")
        + reset_intercharacter_space,
        enable_upperscripting + b"The quick " + double_height + b"brown fox jumps " + disable_upperscripting + reset_double_height + b"over the lazy dog",
        point_8 + b"upperscripting should have " +
        (b"no effect in 9pins mode" if pins else b"effect in ESCP2") + reset_intercharacter_space,
        double_height + enable_upperscripting + pangram + reset_double_height + disable_upperscripting,
        point_8 + b"upperscripting should have " +
        (b"no effect on the first part in 9pins mode" if pins else b"effect in the first part in ESCP2") + reset_intercharacter_space,
        double_height + enable_upperscripting + pangram + reset_double_height + pangram + disable_upperscripting,
        # TODO: same for condensed
    ]

    code = b"\r\n".join(lines)
    processed_file = tmp_path / expected_filename
    _ = ESCParser(code, pins=pins, output_file=str(processed_file))

    pdf_comparison(processed_file)


def test_select_character_style(tmp_path: Path):
    """Test character styles: outline + shadow - ESC q"""
    point_8 = b"\x1BX\x00\x10\x00"
    # Disable multipoint mode used by point_8 because this mode ignores the
    # ESC SP command => so use ESC p 0
    reset_intercharacter_space = b"\x1Bp\x00"
    # double-width
    double_width = b"\x1BW\x01"
    reset_double_width = b"\x1BW\x00"
    # double-height
    double_height = b"\x1Bw\x01"
    reset_double_height = b"\x1Bw\x00"
    # scripting
    enable_upperscripting = b"\x1bS\x00"
    disable_upperscripting = b"\x1bT"

    pangram = b"The quick brown fox jumps over the lazy dog"
    esc_q0 = b"\x1bq\x00"
    esc_q1 = b"\x1bq\x01"
    esc_q2 = b"\x1bq\x02"
    esc_q3 = b"\x1bq\x03"

    lines = [
        esc_reset,
        point_8 + b'Character style - outline - ESC q 1' + reset_intercharacter_space,
        esc_q1 + pangram + esc_q0,
        point_8 + b'Character style - shadow - ESC q 2' + reset_intercharacter_space,
        esc_q2 + pangram + esc_q0,
        point_8 + b'Character style - outline + shadow - ESC q 3' + reset_intercharacter_space,
        esc_q3 + pangram + esc_q0,
        point_8 + b'Character style - off - ESC q 0' + reset_intercharacter_space,
        esc_q0 + pangram + esc_q0,
        b"\r\n",

        enable_upperscripting,
        point_8 + b'Upperscripting + Character style - outline - ESC q 1' + reset_intercharacter_space,
        esc_q1 + pangram + esc_q0,
        point_8 + b'Upperscripting + Character style - shadow - ESC q 2' + reset_intercharacter_space,
        esc_q2 + pangram + esc_q0,
        point_8 + b'Upperscripting + Character style - outline + shadow - ESC q 3' + reset_intercharacter_space,
        esc_q3 + pangram + esc_q0,
        point_8 + b'Upperscripting + Character style - off - ESC q 0' + reset_intercharacter_space,
        esc_q0 + pangram + esc_q0,
        disable_upperscripting + b"\r\n",

        point_8 + b'Double-width + Character style - outline - ESC q 1' + reset_intercharacter_space,
        double_width + esc_q1 + pangram + esc_q0 + reset_double_width,
        point_8 + b'Double-width + Character style - shadow - ESC q 2' + reset_intercharacter_space,
        double_width + esc_q2 + pangram + esc_q0 + reset_double_width,
        point_8 + b'Double-width + Character style - outline + shadow - ESC q 3' + reset_intercharacter_space,
        double_width + esc_q3 + pangram + esc_q0 + reset_double_width,
        point_8 + b'Double-width + Character style - off - ESC q 0' + reset_intercharacter_space,
        double_width + esc_q0 + pangram + esc_q0 + reset_double_width,
        b"\r\n",

        point_8 + b'Double-height + Character style - outline - ESC q 1' + reset_intercharacter_space,
        double_height + esc_q1 + pangram + esc_q0 + reset_double_height,
        point_8 + b'Double-height + Character style - shadow - ESC q 2' + reset_intercharacter_space,
        double_height + esc_q2 + pangram + esc_q0 + reset_double_height,
        point_8 + b'Double-height + Character style - outline + shadow - ESC q 3' + reset_intercharacter_space,
        double_height + esc_q3 + pangram + esc_q0 + reset_double_height,
        point_8 + b'Double-height + Character style - off - ESC q 0' + reset_intercharacter_space,
        double_height + esc_q0 + pangram + esc_q0 + reset_double_height,
        b"\r\n",

    ]

    code = b"\r\n".join(lines)
    processed_file = tmp_path / "test_select_character_style.pdf"
    _ = ESCParser(code, output_file=str(processed_file))

    pdf_comparison(processed_file)


@pytest.mark.parametrize(
    "control_codes, expected_filename",
    [
        (True, "test_print_data_as_characters.pdf"),
        # Test the full table minus the control codes
        # Can be redundant with test_control_codes_printing(), but it's another
        # and more global presentation of the data
        (False, "test_print_data_as_characters_without_control_codes.pdf"),
    ],
    ids=[
        "full_table",
        "without_ccodes",
    ],
)
def test_print_data_as_characters(tmp_path: Path, control_codes, expected_filename):
    """Test the printability of the full table from 0x00 to 0xFF

    Cover: Mainly ESC ( ^, then ESC I

    .. warning:: The test is NOT in 9pins mode, control codes ARE printable by
        default.
    """
    def chunk_this(iterable, length):
        """Split iterable in chunks of equal sizes"""
        iterator = iter(iterable)
        for _ in range(0, len(iterable), length):
            yield bytes(it.islice(iterator, length))

    data_as_chr_cmd = b"\x1b(^"
    switch_control_printing = b"\x1bI"
    disable_control_printing = switch_control_printing + b"\x00"
    # Generate all 8 bits bytes
    full_table = bytes(range(256))

    # No disable = control codes printable
    lines = [] if control_codes else [disable_control_printing]
    counter = 0
    # Chunk the table into lines of 16 characters
    for chunk in chunk_this(full_table, 16):
        data_length = struct.pack("<h", 16)
        lines.append(
            # Prepend the hex index
            format(counter, '#04x').encode("cp437") + b"  " + data_as_chr_cmd + data_length + chunk
        )
        counter += 16

    code = b"\r\n".join(lines)
    processed_file = tmp_path / expected_filename
    _ = ESCParser(esc_reset + code, output_file=str(processed_file))

    pdf_comparison(processed_file)


def test_control_codes_printing(tmp_path: Path):
    """Test all commands that configure the printing of control codes

    Cover: ESC ( ^, ESC 6, ESC 7, ESC m, ESC I commands.

    Default: Control-code data treated as control codes

    ESC ( ^: All given codes are printable.

    ESC 6, ESC 7, ESC m 0, ESC m 4: 0x80-0x9f

    ESC I:
    - 0–6, 16: None of them are used alone in ESC commands
    - 17 (DC1: 0x11): Select printer command!!
    - 21-23 (NAK: 0x15, SYN: 0x16, ETB: 0x17): None of them are used alone in ESC commands
    - 25, 26, 28-31: None of them are used alone in ESC commands
    - Interval: 0x80-0x9f

    .. warning:: The test is in 9pins mode: control codes are NOT printable by
        default.
    """
    point_8 = b"\x1BX\x00\x10\x00"  # 0x10 => 16 / 2 = 8
    roman = b"\x1B\x6B\x00"

    set_upper_print_cmd = b"\x1b6"
    unset_upper_print_cmd = b"\x1b7"
    set_upper_print_cmd2 = b"\x1bm\x00"
    unset_upper_print_cmd2 = b"\x1bm\x04"
    switch_control_printing = b"\x1bI"
    enable_control_printing = switch_control_printing + b"\x01"
    disable_control_printing = switch_control_printing + b"\x00"

    filter_table = bytes(sorted(PrintControlCodes.SELECTED.value))

    lines = [
        # Default => processed as control codes: not printed (9pins mode)
        point_8 + roman + b"default (No control codes)",
        filter_table,
        b"enable upper control codes [128-159]",
        set_upper_print_cmd + filter_table,
        b"disable upper table (No control codes)",
        unset_upper_print_cmd + filter_table,
        b"enable upper table [128-159]",
        set_upper_print_cmd2 + filter_table,
        b"disable upper table (No control codes)",
        unset_upper_print_cmd2 + filter_table,
        b"enable all intervals [0-6][16-17][21-23][25-26][28-31][128-159]",
        enable_control_printing + filter_table,
        b"disable all intervals (No control codes)",
        disable_control_printing + filter_table,
        b"only sub intervals [0-6][16-17][21-23][25-26][28-31]",
        enable_control_printing + unset_upper_print_cmd + filter_table,
    ]

    code = b"\r\n".join(lines)
    processed_file = tmp_path / "test_control_codes_printing_9pins.pdf"
    _ = ESCParser(esc_reset + code, pins=9, output_file=str(processed_file))

    pdf_comparison(processed_file)


def test_text_scripting(tmp_path: Path):
    """Test condensed, double-width, double-height on script text

    Cover:

        - sub/superscript, ESC S
        - condensed printing, ESC SI, SI
        - double width printing, ESC SO, SO, ESC W
        - double height printing, ESC w

    .. todo:: Backspace 0x08 is used to put upper text on top of sub text.
        0x08 backspace uses the current character pitch (not useful
        in reportlab since it is not used for now)
        So most of the time, the cursor_x is rewinded too much.
    """
    # Note: backspace 0x08 is used to put upper text on top of sub text
    copper_and_sulfate = b"Cu\x1bS\x002+\x1bT + SO\x1bS\x014\x08\x1bT\x1bS\x002-\x1bT"
    copper_sulfate = b"CuSO\x1bS\x014\x1bT"

    lines = [
        esc_reset,
        b'sub/superscript examples - ESC S',
        b'Default',
        b'\x09' + copper_sulfate + b' => ' + copper_and_sulfate,
        b'Try to reduce character_pitch to 1/15 in order to reduce the rewind by BS;',
        b'select_15cpi (ESC g) + <text> + select_10cpi (ESC P)',
        b'\x1bg' + b'\x09' + copper_sulfate + b' => ' + copper_and_sulfate + b'\x1bP',
        b'condensed printing - ESC SI, SI',
        b'\x09\x1b\x0f' + copper_sulfate + b' \x12=>\x0f ' + copper_and_sulfate + b' \x12',
        b'',
        b'double width printing - ESC SO, SO - ESC W',
        b'\x09\x1b\x0e' + copper_sulfate + b' \x14=>\x0e ' + copper_and_sulfate + b' \x14',
        # Test values 0 vs "0", 1 vs "1"
        b'\x09\x1bW\x01' + copper_sulfate + b' \x1bW\x00=>\x1bW\x31 ' + copper_and_sulfate + b' \x1bW\x30',
        b'',
        b'double height printing - ESC w',
        b'',
        # Test values 0 vs "0", 1 vs "1"
        b'\x09\x1bw\x01' + copper_sulfate + b' \x1bw\x00=>\x1bw\x31 ' + copper_and_sulfate + b' \x1bw\x30',
    ]

    code = b"\r\n".join(lines)
    processed_file = tmp_path / "test_text_scripting.pdf"
    _ = ESCParser(code, output_file=str(processed_file))

    pdf_comparison(processed_file)


def test_text_enhancements(tmp_path: Path):
    """Test font attributes and enhancements as available in master_select - ESC !

    Cover bitmasks:

        - 1: 12 cpi vs 10 cpi,  ESC M vs ESC P (TODO)
        - 2: proportional ESC p (TODO)
        - 4: condensed DC2, SI (TODO)
        - 8: bold ESC F, ESC E
        - 16: double-strike ESC H, ESC G (TODO)
        - 32: double-with ESC W
        - 64: italics ESC 5, ESC 4
        - 128: underline ESC -
    """
    # Select courier because this font supports almost all properties
    # except condensed & proportional
    courier = b"\x1Bk\x02"

    lines = [
        esc_reset + courier,
        b'Font enhancement - legacy ESC',
        b'\x09Hanc regionem \x1b4praestitutis celebritati\x1b5 diebus',
        b'invadere \x1bEparans\x1bF dux \x1b-\x01ante edictus\x1b-\x00 per solitudines',
        b'Aboraeque \x1b\x47amnis herbidas ripas\x1b\x48, suorum indicio',
        # Test all features on the same words
        b'proditus, \x1b4\x1bE\x1b-\x01qui admissi flagitii metu exagitati\x1b5\x1bF\x1b-\x00 ad',
        b'praesidia descivere Romana. absque ullo egressus',
        b'effectu deinde tabescebat immobilis.',
        b'',
        b'Font enhancement - ESC ! (master)',
        b'\x09Hanc regionem \x1b!\x40praestitutis celebritati\x1b!\x00 diebus',
        b'invadere \x1b!\x08parans\x1b!\x00 dux \x1b!\x80ante edictus\x1b!\x00 per solitudines',
        b'Aboraeque \x1b!\x08amnis herbidas ripas\x1b!\x00, suorum indicio',
        # Test all features on the same words (bold + underline = 2 + 128)
        b'proditus, \x1b!\x88qui admissi flagitii metu exagitati\x1b!\x00 ad',
        b'praesidia descivere Romana. absque ullo egressus',
        b'effectu deinde tabescebat immobilis.',
        b'',
        b'Font enhancement - multilines - ESC ! (master)',
        b'\x09Hanc regionem praestitutis celebritati \x1b!\x40diebus',
        b'invadere\x1b!\x00 parans dux ante edictus per \x1b!\x08solitudines',
        b'Aboraeque\x1b!\x00 amnis herbidas ripas, suorum \x1b!\x80indicio',
        b'proditus\x1b!\x00, qui admissi flagitii metu exagitati ad',
        b'praesidia descivere Romana. absque ullo egressus',
        b'effectu deinde tabescebat immobilis.',
        b''
    ]

    code = b"\r\n".join(lines)
    processed_file = tmp_path / "test_text_enhancements.pdf"
    _ = ESCParser(code, output_file=str(processed_file))

    pdf_comparison(processed_file)
