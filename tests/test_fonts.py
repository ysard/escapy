# Standard imports
import configparser
from pathlib import Path

# Custom imports
import pytest

# Local imports
from escparser.fonts import find_font, setup_fonts
from .test_config_parser import sample_config
from escparser.commons import typeface_names


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
    """
    found = find_font(*arguments)

    if isinstance(expected, list):
        print(found)
        assert len(found) >= 1
    else:
        assert found == expected


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
            """,
            # For now, we test only the typefaces ids
            typeface_names.keys(),
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
            assert callable(font_type) or font_type is None
