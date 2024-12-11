# Standard imports
import os
from pathlib import Path
import pytest
from unittest.mock import patch

# Custom imports
from lark.exceptions import UnexpectedToken

# Local imports
import escparser.commons as cm
from .misc import format_databytes
from .misc import esc_reset, cancel_bold
from .helpers.diff_pdf import is_similar_pdfs
from escparser.parser import ESCParser, PrintMode, PrintScripting


# Test data path depends on the current package name
DIR_DATA = os.path.dirname(os.path.abspath(__file__)) + "/../test_data/"


@pytest.mark.parametrize(
    "format_databytes",
    [
        # Test "0" as a chr (0x30) for d1; move to tb0
        b"\x1B\x28\x74\x03\x00\x30\x08\x00" + cancel_bold,
        # Test d1 as an int; move to tb0 to tb3
        b"\x1B\x28\x74\x03\x00\x00\x08\x00" + cancel_bold,
        b"\x1B\x28\x74\x03\x00\x01\x08\x00" + cancel_bold,
        b"\x1B\x28\x74\x03\x00\x02\x08\x00" + cancel_bold,
        b"\x1B\x28\x74\x03\x00\x03\x08\x00" + cancel_bold,
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

    escparser = ESCParser(format_databytes)
    d1_slot = format_databytes[5 + 2]  # +2 for the ESC reset added by the fixture
    if d1_slot >= 0x30:
        d1_slot -= 0x30

    print("table slot:", d1_slot)
    expected = "cp863"
    assert escparser.character_tables[d1_slot] == expected


@pytest.mark.parametrize(
    "format_databytes",
    [
        # Table with id 4 doesn't exist - ESC ( t
        b"\x1B\x28\x74\x03\x00\x04\x08\x00" + cancel_bold,
        # International charset id 0x0e doesn't exist - ESC R
        b"\x1BR\x0e" + cancel_bold,
        # Wrong typeface ID - ESC k
        b"\x1B[\x0b" + cancel_bold,
        # Wrong character table ID - ESC t
        b"\x1Bt\x04" + cancel_bold,
    ],
    # First param goes in the 'request' param of the fixture format_databytes
    indirect=["format_databytes"],
    ids=[
        "ukn_tb4",
        "charset_ukn",
        "typeface_ukn",
        "table_ukn",
    ],
)
def test_wrong_commands(format_databytes):
    """Test various commands with wrong parameters that will raise a Lark exception"""
    with pytest.raises(UnexpectedToken, match=r"Unexpected token Token.*"):
        _ = ESCParser(format_databytes)


@pytest.mark.parametrize(
    "format_databytes",
    [
        # Combination 0, 8 doesn't exist
        b"\x1B\x28\x74\x03\x00\x30\x00\x08" + cancel_bold,
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
        _ = ESCParser(format_databytes)


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

    escparser = ESCParser(format_databytes)
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
    """select_typeface - ESC k"""
    format_databytes = b"\x1Bk\x02"
    escparser = ESCParser(format_databytes)
    expected = format_databytes[2]
    assert escparser.typeface == expected, "Wrong typeface selected"

    # TODO: _fontname should be at FiraCode-Regular but it's Helvetica ????
    print(escparser.current_fontpath, escparser.current_pdf._fontname)
    assert escparser.current_fontpath == "truetype/firacode/FiraCode-Regular.ttf"

    # wrong typeface ID => switch to default (0) which is FiraCode-Bold
    format_databytes = b"\x1Bk\x0a"
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

    escparser = ESCParser(format_databytes)
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
        escparser = ESCParser(code, pdf=False)
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
