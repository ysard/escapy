# Standard imports
from pathlib import Path
import pytest
from unittest.mock import patch

# Custom imports
from lark.exceptions import UnexpectedToken

# Local imports
import escparser.commons as cm
from .misc import format_databytes, pdf_comparison
from .misc import DIR_DATA, esc_reset, cancel_bold
from .helpers.diff_pdf import is_similar_pdfs
from escparser.parser import ESCParser, PrintMode, PrintScripting


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
    cpi_8 = b"\x1bX\x00\x10\x00"  # ESC X
    # left_margin = b"\x1bl\x03"  # ESC l
    cancel_left_margin = b"\x1bl\x00"  # ESC l

    lines = [
        esc_reset,
        cancel_left_margin,
        cpi_8,
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
        table_1 + b"\x1b(t\x03\x00\x01\x04\x00" + greek_pangram,
    ]

    code = b"\r\n".join(lines)
    processed_file = tmp_path / "test_charset_tables.pdf"
    _ = ESCParser(code, output_file=str(processed_file))

    pdf_comparison(processed_file)


def test_international_charsets(tmp_path: Path):
    """Test injection of 12 characters in the current character table - ESC R

    Custom encoding/decoding codecs are tested here.
    """
    cpi_8 = b"\x1BX\x00\x10\x00" # 0x10 => 16 / 2 = 8
    roman = b"\x1B\x6B\x00"
    select_international_charset_prefix = b"\x1bR"
    lines = [
        esc_reset + cpi_8 + roman + "cp437 table with international mods".encode("cp437"),
    ]
    # Select intl
    for intl_id, charset in cm.international_charsets.items():
        print(intl_id)
        lines.append((cm.charset_mapping[intl_id] + ":").encode("ascii"))
        # Send the ESC command + the bytes to be encoded
        lines.append(select_international_charset_prefix + intl_id.to_bytes() + bytes(bytearray(charset.keys())))
        # lines.append(select_international_charset_prefix + b"\x00")

    code = b"\r\n".join(lines)
    processed_file = tmp_path / "test_international_charset_tables.pdf"
    _ = ESCParser(code, output_file=str(processed_file))

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
    cpi_8 = b"\x1BX\x00\x10\x00"  # ESC X: 0x10 => 16 / 2 = 8 cpi
    roman = b"\x1Bk\x00"  # ESC k
    # Test typefaces
    lines = [
        esc_reset + cancel_left_margin + cpi_8,
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

    .. todo:: test pitch
    """
    # Change point size
    # ESC X: 8 cpi (m, nL, nH)
    # The nL value is divided by 2 later
    cancel_left_margin = b"\x1bl\x00"  # ESC l
    cpi_8 = b"\x1bX\x00\x10\x00"  # ESC X: 0x10 => 16 / 2 = 8 cpi
    alphabet = b"abcdefghijklmnopqrstuvwxz"
    sans_serif = b"\x1bk\x01"
    lines = [
        esc_reset + cancel_left_margin + cpi_8,
        # Use Sans Serif
        sans_serif,
        cpi_8 + b"Font size 8",
        b"\x1bX\x00\x10\x00" + alphabet,  # 8
        cpi_8 + b"Font size 10 (10.5)",
        b"\x1bX\x00\x15\x00" + alphabet,  # 10 (10.5)
        cpi_8 + b"Font size 12",
        b"\x1bX\x00\x18\x00" + alphabet,  # 12
        cpi_8 + b"Font size 14",
        b"\x1bX\x00\x1c\x00" + alphabet,  # 14
        cpi_8 + b"Font size 16",
        b"\x1bX\x00\x20\x00" + alphabet,  # 16
        cpi_8 + b"Font size 18",
        b"\x1bX\x00\x24\x00" + alphabet,  # 18
        cpi_8 + b"Font size 20 (21)",
        b"\x1bX\x00\x28\x00" + alphabet,  # 20 (21)
        cpi_8 + b"Font size 22",
        b"\x1bX\x00\x2c\x00" + alphabet,  # 22
        cpi_8 + b"Font size 24",
        b"\x1bX\x00\x30\x00" + alphabet,  # 24
        cpi_8 + b"Font size 26",
        b"\x1bX\x004\x00" + alphabet,  # 26
        cpi_8 + b"Font size 30",
        b"\x1bX\x00\x3c\x00" + alphabet,  # 30
        cpi_8 + b"Font size 40",
        b"\x1bX\x00\x40\x00" + alphabet,  # 40
    ]

    code = b"\r\n".join(lines)
    processed_file = tmp_path / "test_select_font_by_pitch_and_point.pdf"
    _ = ESCParser(code, output_file=str(processed_file))

    pdf_comparison(processed_file)


def test_set_intercharacter_space(tmp_path: Path):
    """Test intercharacter space size - ESC SP

    Also tests text scripting which should support the setting.
    """
    intercharacter_space_prefix = b"\x1b\x20"
    # Disable multipoint mode used by cpi_8 because it ignores the
    # intercharacter_space command => ESC p 0
    reset_intercharacter_space = b"\x1bp\x00"
    enable_upperscripting = b"\x1bS\x00"
    disable_upperscripting = b"\x1bT"
    cpi_8 = b"\x1bX\x00\x10\x00"  # ESC X: 0x10 => 16 / 2 = 8 cpi
    alphabet = b"abcdefghijklmnopqrstuvwxz"
    lines = [
        esc_reset,
        cpi_8 + b"Intercharacter space from 0 to 128 (steps 20)"
        + reset_intercharacter_space
    ]
    for i in range(0, 128, 20):
        lines.append(intercharacter_space_prefix + i.to_bytes() + alphabet)

    # Same thing but with upper scripting text
    lines.append(
        cpi_8 + b"Intercharacter space from 0 to 128 (steps 20) for scripting text"
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
    # Disable multipoint mode due to cpi_8 => ESC p 0
    reset_intercharacter_space = b"\x1bp\x00"
    cpi_8 = b"\x1bX\x00\x10\x00"  # ESC X: 0x10 => 16 / 2 = 8 cpi
    cpi_21 = b"\x1BX\x00\x2a\x00"  # ESC X: 0x2a => 42 / 2 = 21 cpi
    # double-width
    double_width = b"\x1BW\x01"
    reset_double_width = b"\x1BW\x00"
    # double-height
    double_height = b"\x1Bw\x01"
    reset_double_height = b"\x1Bw\x00"

    pangram = b"The quick brown fox jumps over the lazy dog"

    lines = [
        esc_reset,
        cpi_8 + b"Normal width (10.5 cpi)" + reset_intercharacter_space,
        pangram,
        cpi_8 + b"Double point-size (21 cpi)" + reset_intercharacter_space,
        cpi_21 + pangram,
        cpi_8 + b"Double width (ESC W) (horizontal scale * 2)" + reset_intercharacter_space,
        double_width + pangram + reset_double_width,
        cpi_8 + b"Double height (ESC w) (point-size * 2 + horizontal scale / 2)" + reset_intercharacter_space,
        double_height + pangram + reset_double_height,
        # Should more or less correspond to 2 x 10.5 cpi
        cpi_8 + b"Double height + width (point-size * 2 + horizontal scale * 2)" + reset_intercharacter_space,
        double_width + double_height + pangram + reset_double_height + reset_double_width,
        cpi_8 + b"Back to normal width (10.5 cpi)" + reset_intercharacter_space,
        pangram,
        b"\r\n"
    ]

    # Mix with scripting with various interlaced commands
    enable_upperscripting = b"\x1bS\x00"
    disable_upperscripting = b"\x1bT"
    lines += [
        cpi_8 + b"NOTE: In 9 pins mode, double-height should temporarily stop " +
        b"upper/subscripting, condensed font and Draft printing.",
        cpi_8 + b"upperscripting enabled for ref" + reset_intercharacter_space,
        enable_upperscripting + pangram + disable_upperscripting,
        cpi_8 + b"double-height enabled for ref" + reset_intercharacter_space,
        double_height + pangram + reset_double_height,
        cpi_8 + b"upperscripting should have no effect in 9pins mode" + reset_intercharacter_space,
        enable_upperscripting + double_height + pangram + reset_double_height + disable_upperscripting,
        # Handle the risk to reactivate scripting while it was disabled by a legit
        # command before exiting double-height
        cpi_8 + b"in 9pins mode make sure scripting is enabled, then disabled by double-height, then disabled,",
        b"then not set anymore when exiting double-height" + reset_intercharacter_space,
        enable_upperscripting + b"The quick " + double_height + b"brown fox jumps " + disable_upperscripting + reset_double_height + b"over the lazy dog",
        cpi_8 + b"upperscripting should have no effect in 9pins mode" + reset_intercharacter_space,
        double_height + enable_upperscripting + pangram + reset_double_height + disable_upperscripting,
        cpi_8 + b"upperscripting should have no effect on the first part in 9pins mode" + reset_intercharacter_space,
        double_height + enable_upperscripting + pangram + reset_double_height + pangram + disable_upperscripting,
        # TODO: same for condensed
    ]

    code = b"\r\n".join(lines)
    processed_file = tmp_path / expected_filename
    _ = ESCParser(code, pins=pins, output_file=str(processed_file))

    pdf_comparison(processed_file)


def test_select_character_style(tmp_path: Path):
    """Test character styles: outline + shadow - ESC q"""
    cpi_8 = b"\x1BX\x00\x10\x00"
    # Disable multipoint mode due to cpi_8 => ESC p 0
    reset_intercharacter_space = b"\x1Bp\x00"
    # double-width
    double_width = b"\x1BW\x01"
    reset_double_width = b"\x1BW\x00"
    # double-height
    double_height = b"\x1Bw\x01"
    reset_double_height = b"\x1Bw\x00"

    pangram = b"The quick brown fox jumps over the lazy dog"
    esc_q0 = b"\x1bq\x00"
    esc_q1 = b"\x1bq\x01"
    esc_q2 = b"\x1bq\x02"
    esc_q3 = b"\x1bq\x03"

    lines = [
        esc_reset,
        cpi_8 + b'Character style - outline - ESC q 1' + reset_intercharacter_space,
        esc_q1 + pangram + esc_q0,
        cpi_8 + b'Character style - shadow - ESC q 2' + reset_intercharacter_space,
        esc_q2 + pangram + esc_q0,
        cpi_8 + b'Character style - outline + shadow - ESC q 3' + reset_intercharacter_space,
        esc_q3 + pangram + esc_q0,
        cpi_8 + b'Character style - off - ESC q 0' + reset_intercharacter_space,
        esc_q0 + pangram + esc_q0,
        b"\r\n",

        cpi_8 + b'Double-width + Character style - outline - ESC q 1' + reset_intercharacter_space,
        double_width + esc_q1 + pangram + esc_q0 + reset_double_width,
        cpi_8 + b'Double-width + Character style - shadow - ESC q 2' + reset_intercharacter_space,
        double_width + esc_q2 + pangram + esc_q0 + reset_double_width,
        cpi_8 + b'Double-width + Character style - outline + shadow - ESC q 3' + reset_intercharacter_space,
        double_width + esc_q3 + pangram + esc_q0 + reset_double_width,
        cpi_8 + b'Double-width + Character style - off - ESC q 0' + reset_intercharacter_space,
        double_width + esc_q0 + pangram + esc_q0 + reset_double_width,
        b"\r\n",

        cpi_8 + b'Double-height + Character style - outline - ESC q 1' + reset_intercharacter_space,
        double_height + esc_q1 + pangram + esc_q0 + reset_double_height,
        cpi_8 + b'Double-height + Character style - shadow - ESC q 2' + reset_intercharacter_space,
        double_height + esc_q2 + pangram + esc_q0 + reset_double_height,
        cpi_8 + b'Double-height + Character style - outline + shadow - ESC q 3' + reset_intercharacter_space,
        double_height + esc_q3 + pangram + esc_q0 + reset_double_height,
        cpi_8 + b'Double-height + Character style - off - ESC q 0' + reset_intercharacter_space,
        double_height + esc_q0 + pangram + esc_q0 + reset_double_height,
        b"\r\n",

    ]

    code = b"\r\n".join(lines)
    processed_file = tmp_path / "test_select_character_style.pdf"
    _ = ESCParser(code, output_file=str(processed_file))

    pdf_comparison(processed_file)
