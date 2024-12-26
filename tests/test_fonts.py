# Standard imports
from pathlib import Path

# Custom imports
import pytest

# Local imports
from escparser.fonts import find_font


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
        # kwarg best set to False: expect a list of Paths
        # only 1 match (the best font is found)
        (("NotoSans-", False, False, False, False), [Path("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf")]),
        # multiple matchs
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
        "not_best",
        "not_bests",
        "not_found",
        "not_found_in_path",
        "approximate",
    ],
)
def test_find_font(arguments, expected):
    found = find_font(*arguments)

    if isinstance(expected, list):
        print(found)
        assert len(found) >= 1
    else:
        assert found == expected
