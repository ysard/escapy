# Standard imports
from pathlib import Path

# Custom imports
import pytest

# Local imports
from escparser.parser import ESCParser
from .misc import format_databytes
from escparser.fonts import open_font, find_font, setup_fonts, rptlab_times, rptlab_courier
from .test_config_parser import sample_config
from escparser.commons import TYPEFACE_NAMES


@pytest.mark.parametrize(
    "func, arguments, expected",
    [  # args order: condensed, italic, bold
        (rptlab_times, (True, True, True), "Times-BoldItalic"),
        (rptlab_times, (False, False, False), "Times-Roman"),
        (rptlab_times, (True, False, False), "Times-Roman"),
        (rptlab_times, (True, True, False), "Times-Italic"),
        (rptlab_times, (True, False, True), "Times-Bold"),
        (rptlab_times, (False, True, True), "Times-BoldItalic"),
        (rptlab_times, (False, True, False), "Times-Italic"),
        (rptlab_times, (False, False, True), "Times-Bold"),
        (rptlab_courier, (True, True, True), "Courier-BoldOblique"),
        (rptlab_courier, (False, False, False), "Courier"),
        (rptlab_courier, (False, True, False), "Courier-Oblique"),
    ],
    ids=[
        "Times-BoldItalic",
        "Times-Roman",
        "Times-Roman",
        "Times-Italic",
        "Times-Bold",
        "Times-BoldItalic",
        "Times-Italic",
        "Times-Bold",
        "Courier-BoldOblique",
        "Courier",
        "Courier-Oblique",
    ],
)
def test_reportlab_fallbacks(func, arguments, expected):
    """Test the font selection routines that produce reportlab font names

    .. seealso:: :meth:`rptlab_times`, :meth:`rptlab_courier`.
    """
    found = func(*arguments)
    assert found == expected


@pytest.mark.parametrize(
    "arguments, expected",
    [   # args order: condensed, italic, bold
        (("NotoSans-", True, True, True), Path("/usr/share/fonts/truetype/noto/NotoSans-CondensedBoldItalic.ttf")),
        (("NotoSans-", False, False, False), Path("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf")),
        (("NotoSans-", True, False, False), Path("/usr/share/fonts/truetype/noto/NotoSans-Condensed.ttf")),
        (("NotoSans-", True, True, False), Path("/usr/share/fonts/truetype/noto/NotoSans-CondensedItalic.ttf")),
        (("NotoSans-", True, False, True), Path("/usr/share/fonts/truetype/noto/NotoSans-CondensedBold.ttf")),
        (("NotoSans-", False, True, True), Path("/usr/share/fonts/truetype/noto/NotoSans-BoldItalic.ttf")),
        (("NotoSans-", False, True, False), Path("/usr/share/fonts/truetype/noto/NotoSans-Italic.ttf")),
        (("NotoSans-", False, False, True), Path("/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf")),
        # kwarg 'best' set to False: expect a list of Paths
        # only 1 match (the best font is found)
        (("NotoSans-", False, False, False, False), [Path("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf")]),
        # same but multiple matchs are expected => content is not tested
        (("FiraCode", True, True, False, False), [0] * 2),
        # Non-existing font
        (("NONE_FAKE", False, False, False), None),
        # Non-existing font in the given path
        (("NotoSans-", False, False, True, True, "/usr/share/fonts/truetype/firacode/"), None),
        # Approximate result: condensed & italic are not available
        (("FiraCode", True, True, True), Path("/usr/share/fonts/truetype/firacode/FiraCode-Bold.ttf")),

    ],
    ids=[
        "NotoSans-CondensedBoldItalic",
        "NotoSans-Regular",
        "NotoSans-Condensed",
        "NotoSans-CondensedItalic",
        "NotoSans-CondensedBold",
        "NotoSans-BoldItalic",
        "NotoSans-Italic",
        "NotoSans-Bold.",
        "best_list",
        "best_list_2",
        "not_found",
        "not_found_in_path",
        "approximate",
    ],
)
def test_find_font(arguments, expected):
    """Test the expected accuracy of the algorithm used to search a font on
    the basis of the fontname (font file name)

    .. seealso:: :meth:`find_font`.
    """
    found = find_font(*arguments)

    if isinstance(expected, list):
        print(found)
        assert len(found) >= 1
    else:
        assert found == expected


@pytest.mark.parametrize(
    "font_path, expected_attrs",
    [   # args order: condensed, italic, bold
        (
                Path("/usr/share/fonts/truetype/noto/NotoSans-CondensedBoldItalic.ttf"),
                ("Noto Sans", "Condensed Bold Italic")
        ),
        (Path("/usr/share/fonts/truetype/noto/NONE_FAKE"), (None, None)),
    ],
    ids=[
        "NotoSans-CondensedBoldItalic",
        "not_found",
    ],
)
def test_open_font(font_path, expected_attrs):
    """Test font file opening and family & styles attributes return"""
    expected_family, expected_styles = expected_attrs
    found_family, found_styles = open_font(font_path)

    assert found_family == expected_family
    assert found_styles == expected_styles


@pytest.mark.parametrize(
    "sample_config,expected",
    [
        # Config with user settings vs expected parsed settings
        (
            # sample1:
            """
            [misc]
            [Roman]
            fixed = FiraCode
            [Courier]
            fixed =
            """,
            # For now, we test only the typefaces ids
            # Mandatory typefaces are expected
            {0, 1, 2},
        ),
    ],
    ids=["sample1"],
    indirect=["sample_config"],  # Send sample_config val to the fixture
)
def test_setup_fonts(sample_config, expected):
    """Test the font structure used by the ESC parser to switch the typefaces"""

    found = setup_fonts(sample_config)
    assert found.keys() == expected

    # We expect that all keys in the dict structure have a dict with
    # fixed & proportional keys.
    for typeface_id, typeface_defs in found.items():
        assert typeface_defs.keys() == {"fixed", "proportional"}

        # We want callables or None in the definitions
        for font_type in typeface_defs.values():
            assert callable(font_type)


@pytest.fixture()
def erroneous_fonts():
    """Fixture that generates a badly formed font struct"""
    fonts = {
        0: {
            "fixed": (lambda *args: Path("/usr/share/fonts/truetype/firacode/FiraCode-Bold.ttf")),
            # Not expected type
            "proportional": "foo",
        },
        2: {
            "fixed": (lambda *args: Path("/usr/share/fonts/truetype/firacode/FiraCode-Regular.ttf")),
            # Missing proportional key
        }
    }
    return fonts


@pytest.mark.parametrize(
    "format_databytes",
    [
        # Typeface ID 1: font_type 'proportional' has not the expected type
        # => TypeError
        b"\x1bk\x00" b"\x1bp\x01" b"\x1bk\x00",
        # Typeface ID 2: font_type 'proportional' is not defined.
        # This situation must not happen since these keys are set by the
        # configparser.
        # => KeyError
        b"\x1bk\x02" b"\x1bp\x01" b"\x1bk\x02",
    ],
    # First param goes in the 'request' param of the fixture format_databytes
    indirect=["format_databytes"],
    ids=[
        "bad_type",
        "missing_key",
    ],
)
def test_not_expected_font_struct_format(tmp_path, erroneous_fonts, format_databytes):
    """If the font structure generated by setup_fonts has missing keewords/bad types,
    exception should be raised.
    """
    output_file = tmp_path / "output.pdf"
    with pytest.raises((KeyError, TypeError)):
        _ = ESCParser(format_databytes, available_fonts=erroneous_fonts, output_file=output_file)
        print(_.typeface, _.proportional_spacing, _.current_pdf._fontname)
