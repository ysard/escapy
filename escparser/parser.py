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
"""Main ESC parser routines used to build PDF files"""
# Standard imports
import importlib
from pathlib import Path
from enum import Enum
import itertools as it
import codecs
from functools import lru_cache, partial
from hashlib import md5
from logging import DEBUG

# Custom imports
import numpy as np
from PIL import Image
from lark import Token
from reportlab.lib import colors
from reportlab.lib.colors import PCMYKColorSep
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Local imports
from escparser import __version__
from escparser.grammar import init_parser
from escparser.commons import (
    TYPEFACE_NAMES,
    CHARSET_NAMES_MAPPING,
    INTERNATIONAL_CHARSETS,
    CHARACTER_TABLE_MAPPING,
    LEFT_TO_RIGHT_ENCODINGS,
    RAM_CHARACTERS_TABLE,
    USER_DEFINED_DB_FILE,
    MISSING_CONTROL_CODES_MAPPING,
    CP864_MISSING_CONTROL_CODES_MAPPING,
    COMPLETE_ENCODINGS,
)
from escparser.encodings.i18n_codecs import getregentry
from escparser.fonts import open_font
from escparser.commons import logger


class PrintMode(Enum):
    """Printing modes enumeration

    .. note:: NLQ mode for 9 pin printers is considered equivalent to the LQ mode
        of 24/48 pins printers.
    """

    DRAFT = 0
    LQ = 1


class PrintCharacterStyle(Enum):
    """Character style enumeration in reportlab text render values"""

    FILL = 0
    OUTLINE = 1
    SHADOW = 2


class PrintScripting(Enum):
    """Text scripting enumeration"""

    SUP = 0
    SUB = 1


class PrintControlCodes(Enum):
    """Sections of control codes enumeration & definitions as values

    .. seealso: :meth:`set_upper_control_codes_printing`,
        :meth:`unset_upper_control_codes_printing`,
        :meth:`switch_control_codes_printing`.
    """

    UPPER = frozenset(range(128, 160))
    SELECTED = frozenset(
        it.chain(
            range(0, 7),
            (16, 17, 21, 22, 23, 25, 26),
            range(28, 32),
            range(128, 160)
        )
    )


LOGGER = logger()


class ESCParser:
    """Parser routines used to interpret ESC bytecode and build PDF files

    Epson printer control languages supported:

    - ESC/P
    - ESC/P2
    """

    default_typeface = 0  # Roman

    def __init__(
        self,
        code,
        available_fonts=None,
        pins=None,
        printable_area_margins_mm=None,
        page_size=A4,
        single_sheets=True,
        automatic_linefeed=False,
        condensed_fallback=None,
        dots_as_circles=True,
        userdef_db_filepath=USER_DEFINED_DB_FILE,
        userdef_images_path=None,
        pdf=True,
        output_file="output.pdf",
        **_,
    ):
        """

        :param code: Binary code to be parsed.
            Expected format: ESC/P, ESC/P2, ESC/P 9 Pins.
        :key available_fonts: A structure that stores preconfigured methods to
            find fonts on the system, according to dynamic styles in use.
            See :meth:`escparser.fonts.setup_fonts`.
        :key pins: Number of pins of the printer head (9, 24, 48, None).
            Use None for default modern ESCP2 printers with nozzles. (default: None).
        :key printable_area_margins_mm: Define printable margins in mm.
            No printing is mechanically possible outside this area.
            The printing area is defined inside; it can be reduced via optional
            margins setup by various ESC commands.
            Format: (top, bottom, left, right).
        :key page_size: Page size in points (width, height).
            (default: A4: 8.27 in x 11.7 in, so (595.2755905511812, 841.8897637795277).
        :key single_sheets: Single-sheet of paper if True, Continuous paper
            otherwise. (default: True).
        :key automatic_linefeed: When automatic line-feed is selected (historically
            through DIP-switch or panel setting), the CR command is accompanied
            by a LF command.
        :key dots_as_circles: Ink dots will be drawn as circles if True, or as
            rectangles otherwise. (default: True).
        :key condensed_fallback: True to force autoscaling for condensed text.
            By forcing autoscaling fallback we choose to use & scale the not
            condensed font variant instead of just using it (if it exists) without
            applying a horizontal scale coeffcient.
        :key pdf: Enable pdf generation via reportlab. (default: True).
        :key output_file: Output filepath. (default: output.pdf).
        :type code: bytes
        :type available_fonts: dict
        :type pins: int | None
        :type printable_area_margins_mm: tuple[int] | None
        :type single_sheets: bool
        :type automatic_linefeed: bool
        :type dots_as_circles: bool
        :type pdf: bool
        :type output_file: io.TextIOWrapper | str | Path
        """
        # Misc #################################################################
        # Prepare for methods search in run_esc_instruction()
        self.dir = frozenset(dir(self))

        self.mode: PrintMode = PrintMode.LQ
        # Used to postpone or suspend the print mode
        self.previous_mode = self.mode
        # Used to avoid set_font computations triggered by a chain of
        # attribute modifications; See ESC !
        self.set_font_lock = False
        # Note: There are non-ESCP2 printers that have 24, 48 pins !
        self.pins = pins
        # Render dots as circles or rectangles
        self.dots_as_circles = dots_as_circles
        self.current_pdf = None

        if automatic_linefeed:
            # CR will be accompanied by LF;
            # LF will call _carriage_return() internally.
            self.carriage_return = self.line_feed

        # Character enhancements ###############################################
        self.baseline_offset = 7 / 72 if self.pins == 9 else 20 / 180
        self.italic = False
        self.bold = False
        self._underline = False
        # Dict of scoring types as values, styles as keys
        self.scoring_types = {}
        self.scripting: None | PrintScripting = None
        # Used to postpone or suspend the scripting status
        self.previous_scripting: None | PrintScripting = None
        self.character_style: None | PrintCharacterStyle = None
        self._condensed = False
        # Used to postpone or suspend the condensed status
        self.previous_condensed = False
        self.condensed_fallback: None | bool = condensed_fallback
        self.condensed_autoscaling = False
        self.double_strike = False
        self._double_width = False
        self._double_width_multi = False
        self.double_height = False
        self._color = 0  # Black

        self.color_names = [
            "Black",
            "Magenta",
            "Cyan",
            "Violet",
            "Yellow",
            "Red",
            "Green",
        ]
        self.RGB_colors = [
            "#000000",  # Black
            "#ff00ff",  # Magenta
            "#00ffff",  # Cyan
            "#8F00FF",  # Violet
            "#ffff00",  # Yellow
            "#ff0000",  # Red
            "#00ff00",  # Green
        ]
        self.CMYK_colors = [
            PCMYKColorSep(0, 0, 0, 100),  # Black
            PCMYKColorSep(0, 100, 0, 0),  # Magenta
            PCMYKColorSep(100, 0, 0, 0),  # Cyan
            PCMYKColorSep(44, 100, 0, 0, spotName="VIOLET"),
            PCMYKColorSep(0, 0, 100, 0),  # Yellow
            PCMYKColorSep(0, 100, 100, 0, spotName="RED"),
            PCMYKColorSep(100, 0, 100, 0, spotName="GREEN"),
        ]

        # Font rendering #######################################################
        # Scalable fonts status
        self.multipoint_mode = False
        self.point_size = 10.5
        self._character_pitch = 1 / 10  # in inches: 1/10 inch = 10 cpi
        # Todo priorité sur le character_pitch de ESC X, see set_horizontal_motion_index()
        self.character_width = None  # HMI, horizontal motion index
        # Fixed character spacing
        self._proportional_spacing = False
        # Extra space set by ESC SP
        self.extra_intercharacter_space = 0
        # Init tabulations
        self.horizontal_tabulations = None
        self.reset_horizontal_tabulations()
        self.vertical_tabulations = None
        # Must be None because functions where it is used have their own default values
        self.defined_unit = None
        self.current_line_spacing = 1 / 6

        if pdf:
            # Init PDF render
            # Support of argparse file descriptor vs default str/Path used by tests
            if not isinstance(output_file, (str, Path)):
                output_file = output_file.buffer
            else:
                output_file = str(output_file)
            self.current_pdf = Canvas(
                output_file, pagesize=page_size, pageCompression=1
            )
            self.current_pdf.setLineWidth(0.3)
            self.current_pdf.setFillOverprint(True)
            self.current_pdf.setStrokeOverprint(True)
            self.current_pdf.setProducer(
                f"EscaPy {__version__} - https://github.com/ysard/escparser"
            )

        # Page configuration ###################################################
        self.page_width = page_size[0] / 72
        self.page_height = page_size[1] / 72
        self.single_sheet_paper = single_sheets

        # Default printable area (restricted with margins into the printing area)
        if not printable_area_margins_mm:
            # Todo: be sure about margins for continuous paper: None ? cf p18
            #   "Either no margin or 1-inch margin" (doc ESC N) but its for
            #   printing margins not printable margins...
            printable_area_margins_mm = (
                (6.35, 6.35, 6.35, 6.35) if self.single_sheet_paper else (9, 9, 3, 3)
            )

        # Convert printable area from mm to inches
        printable_area_margins_inch = tuple(i / 25.4 for i in printable_area_margins_mm)
        # Convert printable area to absolute positions
        top, bottom, left, right = printable_area_margins_inch
        self.printable_area = (
            self.page_height - top,
            bottom,
            left,
            self.page_width - right,
        )
        # Set default margins positions (equal printable area)
        (
            self.top_margin,
            self.bottom_margin,
            self.left_margin,
            self.right_margin,
        ) = self.printable_area

        LOGGER.debug(
            "page size, height, width: %s x %s", self.page_height, self.page_width
        )
        LOGGER.debug("printable_area_margins_inch: %s", printable_area_margins_inch)
        LOGGER.debug(
            "printable_area (default printing margins positions): %s",
            self.printable_area,
        )

        # Mechanically usable width
        # Note: Here margins are used because during initialization:
        # printable area = printing area
        # This value will NOT change during printing
        self.printable_area_width = self.right_margin - self.left_margin

        # Page length setting
        #   effective only when you are using continuous paper.
        #   Todo 9 pins + cut-sheets feeder = Single-sheets ESCP2
        if self.single_sheet_paper:
            # Single-sheets ESCP2
            self.page_length = self.top_margin - self.bottom_margin
            # 9 pins & single sheets: physical = logical
            if self.pins == 9:
                self.page_length = self.page_height
        else:
            # Continuous paper ESCP2/ESCP
            self.page_length = self.page_height

        LOGGER.debug("constructed page length: %s", self.page_length)

        # Table of (pre)loaded encodings
        self.character_tables = [
            "italic",
            "cp437",
            None,  # User-defined characters: can be reassigned but lost until reset
            "cp437",
        ]
        self.typefaces = available_fonts
        # Internal use for tests; used only for external/system fonts
        self.current_fontpath: None | Path = None
        self.character_table = 1  # PC437 by default
        self.international_charset = 0
        self.typeface = self.default_typeface
        self.copied_font = {}
        self.ram_characters = False
        from escparser.user_defined_characters import RAMCharacters

        self.userdef_db_filepath = userdef_db_filepath
        self.userdef_images_path = userdef_images_path
        self.user_defined = RAMCharacters(parent=self, db_filepath=userdef_db_filepath)

        # Allow set operations on control codes
        # This attr store the current character points that MUST NOT be printed
        # About default config:
        #   ESCP2, ESCP: Codes are treated as printable characters
        #   9pins: Codes are treated as control codes; All codes are filtered.
        #       => init with the largest set of codes
        if self.pins == 9:
            self.control_codes_filter = PrintControlCodes.SELECTED.value
        else:
            self.control_codes_filter = frozenset()

        # Graphics #############################################################
        self.graphics_mode = False
        self.microweave_mode = False
        # Get horizontal density with dot density value
        self.bit_image_horizontal_resolution_mapping = {
            0: 1 / 60,
            1: 1 / 120,
            2: 1 / 120,
            3: 1 / 240,
            4: 1 / 80,
            5: 1 / 72,
            6: 1 / 90,
            7: 1 / 144,
            32: 1 / 60,
            33: 1 / 120,
            38: 1 / 90,
            39: 1 / 180,
            40: 1 / 360,
            64: 1 / 60,
            65: 1 / 120,
            70: 1 / 90,
            71: 1 / 180,
            72: 1 / 360,
            73: 1 / 360,
        }
        # Raster resolution (ESC . 0 or 1 or 2)
        self.vertical_resolution = None
        self.horizontal_resolution = None
        # Bit image only
        self.double_speed = False

        # dot_density_m parameter reassigned by ESC ? for bit image related commands
        # (ESC K,L,Y,Z)
        self.klyz_densities = [0, 1, 2, 3]

        self.bytes_per_line = 0
        self.bytes_per_column = 0
        self.movx_unit = 1 / 360

        # Absolute position from the page left edge
        self.cursor_x = 0
        # Absolute position from the page top edge
        self.cursor_y = 0
        self.reset_cursor_x()
        self.reset_cursor_y()

        # Init the default font
        self.set_font()

        # Parse it !
        self.run_escp(code)

    @property
    def underline(self) -> bool:
        """Get the underline status

        .. seealso::
            :meth:`switch_underline`
            :meth:`master_select`
            :meth:`select_line_score`
        """
        return self._underline

    @underline.setter
    def underline(self, value: bool):
        """Set the attribute and draw an underline when underlining is just unset"""
        # Take care of the baseline offset
        cursor_y = self.cursor_y - self.baseline_offset

        if value != self._underline:
            if value:
                # underlining was not enabled: keep the cursor position
                self.underline_start = (self.cursor_x * 72, cursor_y * 72 - 1)
            else:
                # underlining is unset: terminate it by drawing it
                self.current_pdf.line(
                    *self.underline_start, self.cursor_x * 72, cursor_y * 72 - 1
                )

        self._underline = value

    @property
    def color(self) -> int:
        """Get the current color id"""
        return self._color

    @color.setter
    def color(self, color: int):
        """Set the current color id

        .. note:: Also available during graphics mode selected with the ESC ( G command.
            In this mode for ESCP2, only Black, Cyan, Magenta, Yellow are available.
            Non-ESCP2 printers can use any color.
        """
        if color >= len(self.CMYK_colors):  # pragma: no cover
            # Color doesn't exist: ignore the command
            LOGGER.error("Color id %s is unknown! Ignore.", color)
            return
        if self.graphics_mode and self.pins != 9 and color not in (0, 1, 2, 4):
            LOGGER.warning("Color id %s not allowed in ESC ( G raster graphics mode")
            return

        self._color = color
        LOGGER.debug("Update color: %d (%s)", color, self.color_names[color])

        if self.current_pdf:
            # Update PDF setting
            # self.current_pdf.setFillColor(colors.HexColor(self.RGB_colors[color]))
            self.current_pdf.setFillColor(self.CMYK_colors[color])
            self.current_pdf.setStrokeColor(self.CMYK_colors[color])

    @property
    def point_size(self) -> float:
        """Get the current font point size (in 1/72 inch)"""
        return self._point_size

    @point_size.setter
    def point_size(self, point_size: float):
        self._point_size = point_size
        if self.current_pdf:
            # Redefine the current font (can't just update the point size)
            self.current_pdf.setFont(self.current_pdf._fontname, point_size)

    @property
    def double_width(self) -> bool:
        """Get the double-width state (one line OR multiline states)"""
        return self._double_width or self._double_width_multi

    @double_width.setter
    def double_width(self, double_width: bool):
        """Set the double-width (one line) state - SO, ESC SO

        Used in combination with ESC SP that allows to double the extra space
        during double-width mode.

        .. seealso:: :meth:`set_intercharacter_space`,
            :meth:`select_double_width_printing`, :meth:`switch_double_width_printing`
        """
        self.double_width_centralized_setter(double_width)

    @property
    def double_width_multi(self) -> bool:  # pragma: no cover
        """Get the double-width multiline state"""
        return self._double_width_multi

    @double_width_multi.setter
    def double_width_multi(self, double_width: bool):
        """Set the double-width multiline state - ESC !, ESC W

        Used in combination with ESC SP that allows to double the extra space
        during double-width mode.

        .. seealso:: :meth:`set_intercharacter_space`,
            :meth:`select_double_width_printing`, :meth:`switch_double_width_printing`
        """
        self.double_width_centralized_setter(double_width, multiline=True)

    def double_width_centralized_setter(
        self, double_width: bool, multiline: bool = False
    ):
        """Centralized setter for :meth:`double_width_multi` & :meth:`double_width`

        :param double_width: Value that goes into `_double_width` (ESC SO) or
            `_double_width_multi` (ESC W) according to the multiline keyword argument.
        :key multiline: Flag used to modulate the attribute modified.
        """
        old = self.double_width
        if multiline:
            self._double_width_multi = double_width
        else:
            self._double_width = double_width

        if old != self.double_width:
            self.extra_intercharacter_space *= 2 if double_width else 0.5
            self.character_pitch *= 2 if double_width else 0.5

    def reset_cursor_y(self):
        """Move the Y cursor on top of the printing area

        .. note:: The baseline for printing characters on the first line
            is 20/180 inch BELOW the top-margin position.

        .. note:: The baseline at the bottom of the page can be 19/180 inch BELOW
            the bottom_margin position.

        .. note:: Any part of graphics is cutoff above or below the top
            or bottom margins.
            That is not the case for characters since they can be printed until
            the edges of the printable area despite the margins (edges of printing area).
        """
        self.cursor_y = self.top_margin

    def reset_cursor_x(self):
        """Move the X cursor to the left edge of the printing area (left-margin)"""
        self._carriage_return()

    def set_page_format(self, *args):
        """Set top and bottom margins - ESC ( c

        Doc: p18, p242-p244

        .. note:: ESC/P 2 only
        .. note:: This command uses values configured "from the top edge of the page".
            Here we use a bottom-up configuration, thus the values must be
            changed in accordingly (origin is at the bottom).

        default margins:
            continuous paper: no margins (see `printable_area_margins_mm`
                in constructor)
            single-sheet: top-of-form, last printable line
        """
        tL, tH, bL, bH = args[1].value
        unit = self.defined_unit if self.defined_unit else 1 / 360
        top_margin = ((tH << 8) + tL) * unit
        bottom_margin = ((bH << 8) + bL) * unit

        # Adapt absolute values to bottom-up system, relative to the page size
        # Ex: on a 11 in height paper, 1 in top margin becomes 10 in top margin.
        self.bottom_margin = self.page_height - bottom_margin
        self.top_margin = self.page_height - top_margin

        printable_top, printable_bottom, *_ = self.printable_area
        # Bottom-up
        if not self.top_margin > self.bottom_margin:
            LOGGER.warning("top margin not > to bottom margin => fix it")
            # Use printable area limits
            self.bottom_margin = printable_bottom
            self.top_margin = printable_top

        # Check limits
        if self.bottom_margin < printable_bottom or self.top_margin > printable_top:
            LOGGER.warning("set margins, raw values: %s, %s", top_margin, bottom_margin)
            LOGGER.warning(
                "set margins (top, bottom) outside printable area: %s, %s, but printable area: %s, %s",
                self.top_margin, self.bottom_margin, printable_top, printable_bottom
            )
            # Use printable area limits
            self.bottom_margin = printable_bottom
            self.top_margin = printable_top

        LOGGER.debug("set margins (top, bottom): %s ,%s", self.top_margin, self.bottom_margin)

        calculated_page_length = self.top_margin - self.bottom_margin
        LOGGER.debug("calculated page-length: %s", calculated_page_length)
        if calculated_page_length > 22:
            # Bottom margin must be less than 22 inches
            LOGGER.error("bottom margin too low (page_length > 22 in), fix it")
            self.bottom_margin = self.page_height - 22
            calculated_page_length = 22

        elif calculated_page_length > self.page_length:  # pragma: no cover
            # This section should not be reached...
            # Previous checks should cancel this case.
            LOGGER.error("set page_length > current page_length (%s)", self.page_length)
            # Todo: Fix the bottom_margin in this case. The doc is unclear
            #   with the top edge page notion for which paper.
            #   For now calculated_page_length is for ALL papers and taken from
            #   the top_margin, but it could be better to check for continuous
            #   paper only, and use top edge (page height) instead...
            # The distance from the top edge of the page to the bottom-margin
            # position must be less than the page length; otherwise, the end of
            # the page length becomes the bottom-margin position.
            self.bottom_margin = self.page_height - self.page_length

        self.reset_cursor_y()
        self.page_length = calculated_page_length

    def set_page_length_defined_unit(self, *args):
        """Set page length in defined unit - ESC ( C

        .. seealso:: see defined_unit via ESC ( U
        .. note:: The maximum page length is 22 inches.
        .. note:: ESC/P 2 only

        cancels the top and bottom-margin settings.

        .. warning:: WONTFIX :
            Set the page length before paper is loaded or when the print position
            is at the top-of-form position. Otherwise, the current print position
            becomes the top-of-form position.
        """
        mL, mH = args[1].value
        value = (mH << 8) + mL
        unit = self.defined_unit if self.defined_unit else 1 / 360
        page_length = value * unit
        LOGGER.debug("page length: %s", page_length)

        if not 0 < page_length <= 22:
            LOGGER.error(
                "(%s × (current unit: %s)) must be less than or equal to 22 inches (%s)",
                value,
                self.defined_unit,
                page_length,
            )
            page_length = 22

        self.page_length = page_length
        self.cancel_top_bottom_margins()

    def set_page_length_lines(self, *args):
        """Sets the page length to n lines in the current line spacing - ESC C

        cancels the top and bottom margin settings

        .. warning:: WONTFIX :
            Set the page length before paper is loaded or when the print position
            is at the top-of-form position. Otherwise, the current print position
            becomes the top-of-form position.
        """
        page_length_lines = args[1].value[0]
        page_length = page_length_lines * self.current_line_spacing
        LOGGER.debug("page length: %s", page_length)

        if not 0 < page_length <= 22:
            LOGGER.error(
                "(%s × (current line spacing: %s)) must be less than or equal to 22 inches (%s)",
                page_length_lines,
                self.current_line_spacing,
                page_length,
            )
            page_length = 22

        self.page_length = page_length
        self.cancel_top_bottom_margins()

    def set_page_length_inches(self, *args):
        """Sets the page length to n inches - ESC C NUL

        cancels the top and bottom margin settings

        .. warning:: WONTFIX :
            Set the page length before paper is loaded or when the print position
            is at the top-of-form position. Otherwise, the current print position
            becomes the top-of-form position.
        """
        page_length = args[1].value[0]
        LOGGER.debug("page length: %s", page_length)

        if not 0 < page_length <= 22:  # pragma: no cover
            LOGGER.error(
                "page_length must be less than 22 inches (%s)",
                page_length,
            )
            page_length = 22

        self.page_length = page_length
        self.cancel_top_bottom_margins()

    def set_bottom_margin(self, *args):
        """Set the bottom margin on continuous paper to n lines (in the current line spacing) - ESC N

        Sets a bottom margin in inch (n lines * line spacing) above the next page’s
        top-of-form position.
        On continuous paper, top-of-form = top edge (physical page top).
        assumes that perforation between pages = top-of-form (0 margins in continuous mode)

        cancels the top-margin setting (ps: top_margin is not configurable in 9pins)

        .. note:: This command uses values configured "from the top-of-form of the page".
            Here we use a bottom-up configuration, thus the values must be
            changed in accordingly (origin is at the bottom).

        .. tip::  When using continuous paper: move the print position to
            top-of-form when :

            - FF command is received
            - print position moves below the bottom_margin position

        .. warning:: Important and not implemented nuance:
            bottom margin set with the ESC N command is ignored when printing on
            single sheets.
            => This doesn't mean that the command is ignored !
        """
        if self.single_sheet_paper:
            return

        self.cancel_top_bottom_margins()

        # from the top-of-form position (1st printable line ) of the NEXT page
        # PS: No need to do bottom-up calculations with self.page_height
        value = args[1].value[0] * self.current_line_spacing
        self.bottom_margin = value

        LOGGER.debug("bottom margin: %s; page_length: %s", self.bottom_margin, self.page_length)

        # In continuous paper, physical page length = logical page length (page_length attribute)
        # In bottom-up system, we do not want that the bottom_margin goes
        # above the top of the current page...
        if self.bottom_margin >= self.page_length:
            LOGGER.error(
                "bottom margin is outside the current page_length (measures: %s vs %s)",
                self.bottom_margin,
                self.page_length,
            )
            # The distance from the top edge of the page to the bottom-margin
            # position must be less than the page length; otherwise, the end of
            # the page length becomes the bottom-margin position.
            self.bottom_margin = 0

    def cancel_top_bottom_margins(self, *_):
        """Cancel the top and bottom margin settings

        Set margins to default settings (printable area)

        Todo: do not change the cursors ?
        """
        self.top_margin, self.bottom_margin, *_ = self.printable_area

    def set_right_margin(self, *args):
        """Set the right margin to n columns in the current character pitch,
        as measured from the left-most printable column - ESC Q

        from the left-most mechanically printable position, in the current character pitch

        Todo: the printer ignores any data preceding this command on the same line
            in the buffer (see also set_left_margin).

        Always set the right margin to be at least one column (at 10 cpi) larger
        than the left.
        The printer calculates the left margin based on 10 cpi if proportional
        spacing is selected with the ESC p command.

        default: The right-most column
        """
        # from the left-most mechanically printable position, in the current character pitch
        character_pitch = 1 / 10 if self.proportional_spacing else self.character_pitch
        left = self.printable_area[2]
        right_margin = args[1].value[0] * character_pitch + left

        LOGGER.debug(
            "left margin, right margin, printable area limit (in): %s, %s, %s",
            self.left_margin,
            right_margin,
            self.printable_area_width + left,
        )
        if (
            not self.left_margin + 0.1
            <= right_margin
            <= self.printable_area_width + left
        ):
            LOGGER.error(
                "right margin outside printing area or before left margin! => ignored"
            )
            return
        self.right_margin = right_margin

        # ignores any data preceding this command on the same line in the buffer
        # => this will not ignore data but just put the cursor at the correct pos
        self.reset_cursor_x()

    def set_left_margin(self, *args):
        """Set the left margin to n columns in the current character pitch,
        as measured from the left-most printable column - ESC l

        from the left-most mechanically printable position, in the current character pitch

        Todo: the printer ignores any data preceding this command on the same line
            in the buffer (see also set_right_margin).

        Always set the left margin to be at least one column (at 10 cpi) less
        than the right.

        The printer calculates the left margin based on 10 cpi if proportional
        spacing is selected with the ESC p command.

        Moving the left-margin position moves the tab settings by the same distance.
        See :meth:`h_tab`.

        .. note:: For ESC/P2 printers:

            80-column printers: 0 ≤ (left margin) ≤ 4.50 inches
            110-column printers: 0 ≤ (left margin) ≤ 7.00 inches
            136-column printers: 0 ≤ (left margin) ≤ 8.00 inches

        default: The left-most column (column 1) (0 value can be received...)
        """
        character_pitch = 1 / 10 if self.proportional_spacing else self.character_pitch
        left = self.printable_area[2]
        left_margin = args[1].value[0] * character_pitch + left

        if not 0 <= left_margin <= self.right_margin - 0.1:
            LOGGER.error(
                "right margin outside printing area or before left margin !! => ignored"
            )
            return

        self.left_margin = left_margin
        # ignores any data preceding this command on the same line in the buffer
        # => this will not ignore data but just put the cursor at the correct pos
        self.reset_cursor_x()

    def set_absolute_horizontal_print_position(self, _, nL, nH):
        """Move the horizontal print position to the position specified - ESC $

        default defined unit setting for this command is 1/60 inch
        Todo: fixed On non-ESC/P 2 printers to 1/60 (currently only on 9 pins)
        ignore this command if the specified position is to the right of the
        right margin.
        """
        nL, nH = nL.value[0], nH.value[0]
        value = (nH << 8) + nL

        # Should be 1/60 on non ESCP2 (not just 9 pins)
        unit = 1 / 60 if not self.defined_unit or self.pins == 9 else self.defined_unit
        cursor_x = value * unit + self.left_margin

        LOGGER.debug("set absolute cursor_x: %s", cursor_x)

        if cursor_x > self.right_margin:
            LOGGER.error("set absolute cursor_x outside right margin! => ignored")
            return
        self.cursor_x = cursor_x

    def set_relative_horizontal_print_position(self, _, nL, nH):
        r"""Move the horizontal print position left or right from the current position - ESC \

        Use the defined unit set by ESC ( U command.
        Default defined unit for this command is 1/120 inch in draft mode,
        and 1/180 inch in LQ mode.
        Fixed to 1/120 on 9 pins.

        ignore this command if it would move the print position outside the printing area.
        """
        nL, nH = nL.value[0], nH.value[0]
        value = (nH << 8) + nL

        # Test bit sign
        if nH & 0x80:
            # left movement
            value -= 2**16

        if self.pins == 9:
            unit = 1 / 120
        else:
            unit = (
                self.defined_unit
                if self.defined_unit
                else (1 / 180 if self.mode == PrintMode.LQ else 1 / 120)
            )
        cursor_x = value * unit + self.cursor_x
        LOGGER.debug("set relative cursor_x: %s", cursor_x)

        if not self.left_margin <= cursor_x < self.right_margin:
            LOGGER.error("set relative cursor_x outside defined margins! => ignored")
            return

        self.cursor_x = cursor_x

    def set_absolute_vertical_print_position(self, _, mL, mH):
        """Moves the vertical print position to the position specified - ESC ( V

        .. note:: ESCP2 only

        default defined unit for this command is 1/360 inch.
        The new position is measured in defined units from the current top-margin position.

        Moving the print position below the bottom-margin:

            - continuous paper: move vertical to top margin of next page
            - single-sheet paper: eject

        Ignore this command under the following conditions:

            - move the print position more than 179/360 inch in the negative direction
            - Todo: move the print position in the negative direction after a
              graphics command is sent on the current line, or above the point
              where graphics have previously been printed

        .. note::
            Here we use a bottom-up configuration, thus the values must be
            changed in accordingly (origin is at the bottom => signs are inverted!).
        """
        mL, mH = mL.value[0], mH.value[0]
        value = (mH << 8) + mL

        unit = self.defined_unit if self.defined_unit else 1 / 360
        # sign inverted due to bottom-up
        cursor_y = -value * unit + self.top_margin

        if cursor_y < self.bottom_margin:
            self.next_page()
            return

        movement_amplitude = self.cursor_y - cursor_y
        if movement_amplitude < 0 and -movement_amplitude > 179 / 360:
            LOGGER.error(
                "set absolute cursor_y movement upwards too big (%s)! => ignored",
                movement_amplitude,
            )
            return

        self.cursor_y = cursor_y

    def set_relative_vertical_print_position(self, _, mL, mH):
        """Moves the vertical print position up or down from the current position - ESC ( v

        .. note:: ESCP2 only

        default defined unit for this command is 1/360 inch.

        Ignore this command under the following conditions:

            - move the print position more than 179/360 inch in the negative direction
            - Todo: move the print position in the negative direction after a
            graphics command is sent on the current line, or above the point where graphics
            have previously been printed
            - would move the print position above the top-margin position

        .. note::
            Here we use a bottom-up configuration, thus the values must be
            changed in accordingly (origin is at the bottom => signs are inverted!).
            From the original doc: positive = down movement, negative = up movement.
        """
        mL, mH = mL.value[0], mH.value[0]
        value = (mH << 8) + mL
        # Test bit sign
        if mH & 0x80:
            # up movement sent
            value -= 2**16

        unit = self.defined_unit if self.defined_unit else 1 / 360
        movement_amplitude = value * unit

        if movement_amplitude < 0 and -movement_amplitude > 179 / 360:
            LOGGER.error(
                "set relative cursor_y movement upwards too big (%s)! => ignored",
                movement_amplitude,
            )
            return

        # sign inverted due to bottom-up
        cursor_y = -movement_amplitude + self.cursor_y

        if cursor_y > self.top_margin:
            LOGGER.error("set relative cursor_y above top-margin! => ignored")
            return

        if cursor_y < self.bottom_margin:
            self.next_page()
            return

        self.cursor_y = cursor_y

    def advance_print_position_vertically(self, *args):
        """Advance the vertical print position n/180 inch - ESC J

        On non-ESC/P 2 printers:

            - 9pins: n / 216
            - Todo: Prints all data in the line buffer

        .. seealso:: :meth:`end_page_paper_handling` for implementation checks
        """
        # sign inverted due to bottom-up
        self.cursor_y -= args[1].value[0] / (216 if self.pins == 9 else 180)
        self.end_page_paper_handling()

    def set_unit(self, *args):
        r"""Set the unit to m/3600 inch - ESC ( U

        The default unit varies depending on the command and print quality:

            ESC ( V            1/360 inch
            ESC ( v            1/360 inch
            ESC ( C            1/360 inch
            ESC ( c            1/360 inch
            ESC \ (LQ mode)    1/180 inch
            ESC \ (draft mode) 1/120 inch
            ESC $              1/60 inch
            <MOVX> (dot)       1/360 inch
            <MOVY>             1/360 inch

        Values: 5, 10, 20, 30, 40, 50, 60

        .. note:: ESC/P 2 only
        """
        value = args[1].value[0]

        self.defined_unit = value / 3600

    def set_18_line_spacing(self, *_):
        """Set the line spacing to 1/8 inch - ESC 0

        default: 1/6
        """
        self.current_line_spacing = 1 / 8

    def set_16_line_spacing(self, *_):
        """Set the line spacing to 1/6 inch - ESC 2

        default: 1/6
        """
        self.current_line_spacing = 1 / 6

    def set_n180_line_spacing(self, *args):
        """Set the line spacing to n/180 inch - ESC 3

        default: 1/6

        9pins: n/216 inch
        """
        value = args[1].value[0]
        coef = 216 if self.pins == 9 else 180
        self.current_line_spacing = value / coef

    def set_n360_line_spacing(self, *args):
        """Set the line spacing to n/360 inch - ESC +

        default: 1/6

        .. note:: available only on 24/48-pin printers.
        """
        value = args[1].value[0]
        self.current_line_spacing = value / 360

    def set_n60_line_spacing(self, *args):
        """Set the line spacing to n/60 inch - ESC A

        default: 1/6

        9pins: n/72 inch
        """
        value = args[1].value[0]
        self.current_line_spacing = value / (72 if self.pins == 9 else 60)

    def set_772_line_spacing(self, *_):
        """Set the line spacing to 7/72 inch - ESC 1

        default: 1/6

        .. note:: available only on 9-pin printers.
        """
        self.current_line_spacing = 7 / 72

    def h_v_skip(self, *args):
        """Move the print position depending on the value of m - ESC f

        m = 0: horizontally
        m = 1: vertically

        Horizontally:

            Underline is performed between the current and final print positions
            when this command is used to move the print position horizontally
            => not interrupted

        Vertically:

            cancel double-width printing selected with the SO or ESC SO command.
        """
        m, n = args[1].value[0], args[2].value[0]

        if m == 0:
            # horizontally
            # using this function should allow to perform an eventual character scoring
            self.binary_blob(Token("ANYTHING", b" " * n))
        elif m == 1:
            # vertically
            _ = [self.line_feed() for _ in range(n)]
            self._carriage_return()
            self.double_width = False

    def backspace(self, *_):
        """Move the print position to the left a distance equal to one character
        in the current character pitch plus any additional intercharacter space - BS

        ignored if it would move the print position to the left of the left margin.

        .. warning:: The original implementation doesn't care about text scripting
            since it doesn't modify the character width.
            Since we use point size on modern fonts, it now must be considered.

            Idem about the double-height option, we must apply a factor of 0.5
            since it is obtained by doubling the point size.

        """
        # Original (printer) implementation
        # cursor_x = self.cursor_x - self.character_pitch - self.extra_intercharacter_space

        # Custom implementation: approximatation
        # Compute coef only if double-height is enabled
        # We USE character_pitch here, witch is updated via the standard implementation
        # (like the intercharacter space).
        # horizontal_scale_coef = 1 if not self.double_height else 0.5
        # scripting_coef = 2/3 if self.scripting and self._point_size > 8 else 1
        # cursor_x = self.cursor_x - (self.character_pitch * scripting_coef * horizontal_scale_coef + self.extra_intercharacter_space)

        # Custom implementation: precise, using text width from the pdf renderer
        horizontal_scale_coef = self.compute_horizontal_scale_coef()
        point_size = self._point_size
        # See binary_blob()
        point_size = (
            round(point_size * 2 / 3)
            if self.scripting and point_size > 8
            else point_size
        )

        # Scale is applied only on the string part, not intercharacter space
        # that is already updated via the standard implementation.
        text_width = self.current_pdf.stringWidth(" ", fontSize=point_size)
        # use inches: convert pixels to inch
        text_width /= 72
        cursor_x = (
            self.cursor_x
            - text_width * horizontal_scale_coef
            - self.extra_intercharacter_space
        )

        # Alternative: print a space with binary blob, measure the diff
        # of the cursor_x: after - before...

        if cursor_x < self.left_margin:
            return
        self.cursor_x = cursor_x

    @property
    def encoding(self) -> str:
        """Get the encoding in use according to the current character table and
        international charset (National Replacement Character Set) loaded.

        Whatever the encoding, if the RAM characters are activated,
        "user_defined" is returned.

        This function ensures that the correct encoding is loaded in the cache
        of codecs and built on the fly if necessary.

        Some Python character mapping codecs need to be patched to embed the
        first 32 characters points and the character point 0x0f of the table as
        printable characters.

        See:
        https://stackoverflow.com/questions/46942721/is-cp437-decoding-broken-for-control-characters

        .. warning:: Italic is currently not supported.
        """
        if self.ram_characters:
            # See ESC %
            return RAM_CHARACTERS_TABLE

        # Decode the text according to the current character table
        encoding = self.character_tables[self.character_table]

        if encoding in (None, "italic"):
            # Encoding not supported (yet), fall back to cp437;
            # See select_character_table()
            # PS: This has nothing to do with user-defined characters!
            # Their table can't be selected like that.
            return "cp437"

        # Try to load the base encoding;
        # First from Python, then from the local package.
        try:
            codecs.lookup(encoding)
        except LookupError:
            LOGGER.debug("Load local encoding: %s", encoding)
            try:
                importlib.import_module(f"escparser.encodings.{encoding}")
            except ModuleNotFoundError as exc:  # pragma: no cover
                # For developpers only: CHARACTER_TABLE_MAPPING is updated
                # with a missing/bad encoding
                LOGGER.error(
                    "Encoding <%s> was not found in Python stdlib nor in current project."
                )
                raise ModuleNotFoundError from exc

        if self.international_charset == 0 and encoding in COMPLETE_ENCODINGS:
            # Nothing to do
            return encoding

        charset = {}
        encoding_variant = encoding
        if encoding not in COMPLETE_ENCODINGS:
            # Inject the first 32 characters of the table + 0x7f (127)
            # Tables embedded in Python encodings are incomplete for these points
            encoding_variant += "_mod"
            charset.update(
                MISSING_CONTROL_CODES_MAPPING
                # Specific patch for this encoding. May move in future update...
                if encoding != "cp864"
                else CP864_MISSING_CONTROL_CODES_MAPPING
            )

        if self.international_charset:
            # i18n variant is required
            encoding_variant += f"_{CHARSET_NAMES_MAPPING[self.international_charset]}"
            charset.update(INTERNATIONAL_CHARSETS[self.international_charset])

        # Build a new codec
        try:
            codecs.lookup(encoding_variant)
        except LookupError:
            register_codec_func = partial(
                getregentry,
                effective_encoding=encoding_variant,
                base_encoding=encoding,
                intl_charset=charset,
            )
            codecs.register(register_codec_func)

        return encoding_variant

    def compute_horizontal_scale_coef(self) -> float:
        """Get a scale coefficient used to simulate double-width, double-height
        condensed printing and all character pitch changes (internal use).

        Since that only the point-size is modifiable on modern fonts, we must
        play with this parameter and with a horizontal scale coefficient
        to stretch the text and obtain the rendering of the old days.

        .. seealso:: :meth:`binary_blob`, :meth:`backspace`.

        :return: A numeric value ([0, 1]) used in the `setHorizScale` methods of
            the reportlab textobjects.
        """
        if self.multipoint_mode and self.proportional_spacing:
            return 1

        if self.double_height:
            # The point size is already multiplied by 2, we must reduce the pitch
            horizontal_scale_coef = 0.5
        else:
            horizontal_scale_coef = 1

        # Get the coefficient currently applied on the default character pitch;
        # which is 1/10 by default (condensed mode applies a variable coef).
        if self.condensed and not self.condensed_autoscaling:
            # Prefer to use an already condensed ttf font version;
            # => disable the character_pitch change related to this mode
            character_pitch = 1 / 10
        else:
            character_pitch = self.character_pitch

        horizontal_scale_coef *= 10 * character_pitch

        return horizontal_scale_coef

    def apply_text_scoring(self, cursor_y, horizontal_scale_coef, text):
        """Apply scoring on top of the given text (internal use)

        For now common characters (EQUALS SIGN, EM DASH (cadratin), HYPHEN-MINUS
        (quarter cadratin) are used for scoring instead of real lines.
        That allows to use the current point size and bold settings instead of
        modifying linewidth locally.
        That may change later.

        .. seealso:: :meth:`binary_blob`.

        :param cursor_y: Vertical position of the text (the baseline offset is included).
        :param horizontal_scale_coef: Numeric value used in the `setHorizScale`
            methods of the reportlab textobjects.
        :param text: Text that will be scored across its entire width.
        :type cursor_y: float
        :type horizontal_scale_coef: float
        :type text: str
        """
        if not self.current_pdf:
            return

        scoring_types = {
            1: cursor_y - self.point_size / 3 / 72 - 1 / 72,  # below
            2: cursor_y,  # middle
            3: cursor_y + self.point_size / 3 / 72,  # above
        }
        scoring_styles = {
            1: "—",
            2: "=",  # "＝", FULLWIDTH EQUALS SIGN, not available on various fonts
            5: "-",
            6: "=",
        }
        g = (
            (scoring_type, style)
            for scoring_type, style in self.scoring_types.items()
            if style  # Skip 0 (turn off the scoring)
        )
        for scoring_type, style in g:
            offset_y = scoring_types[scoring_type]
            char = scoring_styles[style]
            textobject = self.current_pdf.beginText(self.cursor_x * 72, offset_y * 72)
            textobject.setCharSpace(self.extra_intercharacter_space)
            textobject.setHorizScale(horizontal_scale_coef * 100)
            textobject.textOut(char * len(text))
            textobject.setHorizScale(100)
            self.current_pdf.drawText(textobject)

    def apply_text_style(self, cursor_y, horizontal_scale_coef, text_object, text):
        """Add outline & shadow styles to the given textobject (internal use)

        Basically adding shadow consists of adding one text on top of the
        other with a slight offset.

        .. note:: The linewidth for strokes due to outline style is fixed
            in :meth:`__init__` during the pdf object initialization.
            Should be ~0.3 for normal text, ~0.1 for scripting text.

        .. seealso:: :meth:`binary_blob`.

        :param cursor_y: Vertical position of the text (the baseline offset is included).
        :param horizontal_scale_coef: Numeric value used in the `setHorizScale`
            methods of the reportlab textobjects.
        :param text_object: The text object that will be modified.
        :param text: Decoded text that will be written.
        :type cursor_y: float
        :type horizontal_scale_coef: float
        :type text_object: reportlab.pdfgen.textobject.PDFTextObject
        :type text: str
        """
        match self.character_style:
            # Fill only, Shadow only
            # Fill then stroke, Outline and shadow
            case PrintCharacterStyle.FILL | PrintCharacterStyle.SHADOW:
                text_object.textOut(text)
                text_object.setTextRenderMode(self.character_style.value)
                text_object.setFillColorRGB(1, 1, 1)  # Fill with white
                # Empirical offset value (~1 to 1.2 at 10.5 point size)
                offset = horizontal_scale_coef * self.point_size * 0.5 / 10
                # The white text will be on top and above the legit text
                text_object.setTextOrigin(
                    self.cursor_x * 72 - offset, cursor_y * 72 + offset
                )
                text_object.textOut(text)
                text_object.setFillColorRGB(0, 0, 0)
            # Stroke only, Outline only
            case PrintCharacterStyle.OUTLINE:
                text_object.setTextRenderMode(self.character_style.value)
                text_object.textOut(text)

        text_object.setTextRenderMode(0)

    def binary_blob(self, arg):
        """Print text characters

        .. tip:: A point equals 1/72 of an inch, we need to convert this to pixels
             by multiplying by 72.

        .. note:: About the printing baseline:
            The baseline for printing characters is 20/180 inch
            (7/72 inch for 9-pin printers) below the vertical print position.

            This offset is for characters only, not graphics !

            For graphics printing, the print position is the top printable
            row of dots (see in concerned functions).

        .. warning:: The horizontal move should be according to the selected pitch
            (or the width of each character if proportional spacing is selected).
            Since we use modern fonts, we must use an accurate width which is not
            based on fixed character spacing, but on the point size.

            This will generate positionning errors compared to the old fonts
            especially if the new font is not strictly the same.
        """
        raw_text = arg.value
        cursor_y = self.cursor_y - self.baseline_offset

        horizontal_scale_coef = self.compute_horizontal_scale_coef()

        # Decode the text according to the current character table
        encoding = self.character_tables[self.character_table]
        if encoding == "italic":
            LOGGER.warning(
                "Italic table is partially supported: map all italic chars to normal chars"
            )
            # Remap the upper table part to the lower part
            raw_text = bytearray(i if i < 0x80 else i - 0x80 for i in raw_text)
        elif self.control_codes_filter:
            # Handle control codes
            # no effect when the italic character table is selected; no characters
            # are defined for these codes in the italic character table.
            raw_text = bytes(i for i in raw_text if i not in self.control_codes_filter)

        # Get the encoding according to an enventually international charset set
        encoding_variant = self.encoding
        # LOGGER.debug("Encoding variant in use: %s", encoding_variant)

        # Fallback if character is not in the code page
        # Use any of: replace, backslashreplace, ignore
        text = raw_text.decode(encoding_variant, errors="replace")

        if encoding in LEFT_TO_RIGHT_ENCODINGS:
            text = text[::-1]

        # print(raw_text)
        # print(text)
        if not text:
            return

        if self.scripting:
            # See ESC S command for more documentation of what is done here
            # Compute the position of the scripting text
            point_size = self._point_size
            rise = point_size * 1 / 3
            if self.scripting == PrintScripting.SUB:
                # Lower third of the normal character height
                rise *= -1
            # Modify point size only if it's greater than 8
            if point_size > 8:
                self.point_size = round(point_size * 2 / 3)

            if self.current_pdf:
                text_width = self.current_pdf.stringWidth(text)
                line_width_backup = self.current_pdf._lineWidth

                # Print text
                textobject = self.current_pdf.beginText(
                    self.cursor_x * 72, cursor_y * 72
                )
                textobject.setRise(rise)
                textobject.setCharSpace(self.extra_intercharacter_space)
                textobject.setHorizScale(horizontal_scale_coef * 100)

                if self.character_style is not None:
                    self.current_pdf.setLineWidth(0.1)
                    self.apply_text_style(
                        cursor_y, horizontal_scale_coef, textobject, text
                    )
                else:
                    textobject.textOut(text)

                textobject.setRise(0)
                textobject.setHorizScale(100)
                self.current_pdf.drawText(textobject)
                self.current_pdf.setLineWidth(line_width_backup)

            # Restore original point size
            self.point_size = point_size

        elif self.current_pdf:
            text_width = self.current_pdf.stringWidth(text)

            # Print text
            textobject = self.current_pdf.beginText(self.cursor_x * 72, cursor_y * 72)
            textobject.setCharSpace(self.extra_intercharacter_space)
            textobject.setHorizScale(horizontal_scale_coef * 100)

            if self.character_style is not None:
                self.apply_text_style(cursor_y, horizontal_scale_coef, textobject, text)
            else:
                textobject.textOut(text)

            textobject.setHorizScale(100)
            self.current_pdf.drawText(textobject)

        self.apply_text_scoring(cursor_y, horizontal_scale_coef, text)

        # Actualize the x cursor with the apparent width of the written text
        if not self.current_pdf:
            # Fallback
            text_width = len(text) / self.character_pitch

        # Add intercharacter space which is not used by stringWidth()
        # PS: not `len(text) - 1`, because there is a trailing space.
        text_width += len(text) * self.extra_intercharacter_space
        # use inches: convert pixels to inch
        text_width /= 72

        # Handle all character pitch changes
        # (double width/height, condensed, select_*_cpi)
        text_width *= horizontal_scale_coef
        self.cursor_x += text_width

    def carriage_return(self, *_):
        """Move the print position to the left-margin position

        Todo: non-ESC/P 2 printers: The printer prints all data in the line buffer
        - When automatic line-feed is selected (through DIP-switch or panel setting),
          the CR command is accompanied by a LF command.
          See the `automatic_linefeed` setting.
        """
        self._carriage_return()

    def _carriage_return(self):
        """Move the print position to the left-margin position

        Internal use only. Exists to support the `automatic_linefeed` setting.

        .. seealso:: :meth:`carriage_return`.
        """
        if self.pins == 9:
            self.double_width = False

        # Workaround to temporary interrupt underline see also line_feed()
        if self._underline:
            self.underline = False

            self.cursor_x = self.left_margin

            self.underline = True
            return

        self.cursor_x = self.left_margin

    def line_feed(self, *_):
        """Advance the vertical print position one line (in the currently set line spacing) - LF

        Move the horizontal print position to the left-margin position.
        Cancel one-line double-width printing selected with the SO or ESC SO commands.

        continuous paper:

            test if cursor_y below bottom_margin: top-of-form/top printable (!!) next page
            => confusion in doc, follow p294 directives (ESC J & LF behave together)

        single-sheet paper:

            test if cursor_y below bottom_margin or beyond the end of the
            printable area the printer ejects the paper.

        Todo: non-ESC/P 2 printers: The printer prints all data in the line buffer

        doc p34, p294

        .. seealso:: :meth:`end_page_paper_handling` for implementation checks
        """
        self.double_width = False

        # Workaround to temporary interrupt underline: see also carriage_return()
        underline = self._underline
        if underline:
            self.underline = False

        self._carriage_return()
        self.cursor_y -= self.current_line_spacing

        if underline:
            self.underline = True

        self.end_page_paper_handling()

    def end_page_paper_handling(self):
        """Tear down for ESC J & LF commands

        p34, p294

        ESCP2 + ESC/P:

            => continuous and pos < bottom margin => top margin (!!!) next page
            => single-sheet: ejects

        9 pins:

            If the ESC J command moves the print position on continuous paper
            below the bottom-margin position set with the ESC N command, the
            printer advances to the top-of-form position on the next page.
            => continuous and pos < bottom margin => top printable next page

            If ESC J moves the print position on single-sheet paper below the
            end of the printable area, the printer ejects the paper
            (if loaded by cut-sheet feeder) or ejects paper and then feeds next
            sheet remaining distance (if loaded manually).
            => single-sheet + cut-sheet feeder and below bottom printable => ejects
            => single-sheet + loaded manually and below bottom printable
                => ejects + report remaining distance on next sheet (Todo)
        """
        # ESCP & 9 pins (Todo: distingo)
        printable_bottom_margin = self.printable_area[1]
        if self.pins == 9 and self.single_sheet_paper:
            if self.cursor_y < printable_bottom_margin:
                # ejects the paper
                LOGGER.info("outside printable area => NEXT PAGE required!")
                self.next_page()
                # Todo: if loaded manually: report the remaining distance on the new page
                return
            return

        if self.cursor_y < self.bottom_margin:
            self.next_page()
            # ESCP/9 pins
            # Todo: if continuous: Go to the top-of-form, not the top_margin
            # See form_feed() similar implementation

    def form_feed(self, *_):
        """Advance the vertical print position on continuous paper to the top
        position of the next page - FF

        On continuous paper:

            ESCP2: top-margin position
            9pins: top-of-form

        .. note:: Complete each page with a FF command. Also send a FF command
            at the end of each print job.

        - Ejects single-sheet paper
        - Moves the horizontal print position to the left-margin position
        Todo: Prints all data in the buffer
        """
        self.double_width = False
        self.next_page()

        if self.pins == 9 and not self.single_sheet_paper:
            # Move to top-of-form
            # Note: In any case on old printers, top_margin is not configurable...
            self.top_margin = self.printable_area[0]
            # Update the cursor according to the new top_margin
            # self.reset_cursor_y()
            # shorter, all routines are already made in previous next_page() call
            self.cursor_y = self.top_margin

    def next_page(self):
        """Initiate a new page and reset cursors"""
        LOGGER.debug("NEXT PAGE! at y offset %s", self.cursor_y)

        self.reset_cursor_y()
        self._carriage_return()

        if self.current_pdf:
            # stop drawing on the current page and any further
            # operations will draw on a subsequent page
            self.current_pdf.showPage()

            # With showPage(), all state changes (
            # font changes, color settings, geometry transforms, etcetera) are FORGOTTEN
            self.set_font()
            self.color = self._color

    def h_tab(self, *_):
        """Move the horizontal print position to the next tab to the right of the current print position - HT

        Add a horizontal tabulation

        Ignore this command if no tab is set to the right of the current position
        or if the next tab is to the right of the right margin.

        Todo: Character scoring (underline, overscore, and strikethrough) is not
            printed between the current print position and the next tab when this
            command is sent.
            => temp disable before cursor_x set and enabled after
        """
        # Guess the tab position
        # We search the first tab pos AFTER the current cursor_x
        g = (
            tab_pos
            for tab_width in self.horizontal_tabulations
            if tab_width and ((tab_pos := self.left_margin + tab_width) > self.cursor_x)
        )

        try:
            tab_pos = next(g)
            LOGGER.debug("Choosen tab position: %s", tab_pos)
        except StopIteration:
            tab_pos = None

        if not tab_pos:
            LOGGER.warning("No tab available after the current cursor_x position")
            return

        if tab_pos > self.right_margin:
            LOGGER.error("Tab outside right margin: ignored")
            return

        self.cursor_x = tab_pos

    def v_tab(self, *_):
        """Move the vertical print position to the next vertical tab below the current print position - VT

        - Move the horizontal print position to the left-margin position
        - Same as an FF (form feed) if the next tab is below the bottom-margin
          position, or if no tab is set below the current position.
        - Same as a CR command if all tabs have been canceled with the ESC B NUL
        - Same as an LF command if no tabs have been set since the printer was
          turned on or was reset with the ESC @

        doc p52

        Double-width handling:
            - ESCP2:
            Do NOT cancel double-width when VT functions the same as a CR command
            (normal behavior).
            - non-ESC/P 2 printers:
            Cancel double-width when VT functions the same as a CR command.
            (normal behavior).

        Non-ESCP2 printers:
            - Vertical tabs are measured from the top-of-form position.
              => WONTFIX: on these printers the top-margin is not modifiable
              so the top-of-form IS the top-margin.
            - advances to the top-of-form position on the next page if the
              next tab is beyond the currently set page length.
              => WONTFIX: In bottom-up, "beyond the page length" is below 0,
              thus, below the bottom-margin position, which is already handled.
            - ignored if the print position inside the bottom-margin
              (ed.: between bottom-margin and page-length).
              => WONTFIX: doc unclear p53 (next-page if beyond the bottom margin).
        """
        if self.vertical_tabulations is None:
            # No tab is configured since turn on or reset => just a LF
            # PS: triggers a double-width cancelation
            self.line_feed()
            return

        # PS: triggers a double-width cancelation if 9pins
        # PS2: We want to use underline checks routines in carriage_return
        # but this will trigger double_width reset in 9pins.
        # However, this reset is not legit if the cmd is not the same as a true
        # CR cmd; thus, we must restore it later.
        double_width_backup = self._double_width
        self._carriage_return()

        if not any(self.vertical_tabulations):
            # No tab is configured following a tab cancelation => just a CR
            return
        self.double_width = double_width_backup

        # Guess the tab position
        # We search the first tab pos BELOW the current cursor_y
        # PS: Use bottom-up coordinates (top value > bottom value)
        g = (
            tab_pos
            for tab_height in self.vertical_tabulations
            if tab_height and ((tab_pos := self.top_margin - tab_height) < self.cursor_y)
        )

        try:
            tab_pos = next(g)
            LOGGER.debug(
                "Choosen tab position: %s, %s",
                tab_pos,
                (self.top_margin - tab_pos) / self.current_line_spacing,
            )
        except StopIteration:
            tab_pos = None

        if not tab_pos or tab_pos < self.bottom_margin:
            # => like a FF
            LOGGER.warning(
                "No tab available below the current cursor_y position, "
                "or tab is below bottom margin."
            )
            # PS: triggers a double-width cancelation
            self.form_feed()
            return

        self.cursor_y = tab_pos

    def reset_horizontal_tabulations(self):
        """Set tabulation widths in character pitch

        default: 1 tab position every 8 characters (8, 16, 24, 32, ...)
        """
        character_pitch = 1 / 10 if self.proportional_spacing else self.character_pitch
        self.horizontal_tabulations = [8 * i * character_pitch for i in range(1, 33)]

    def set_horizontal_tabs(self, *args):
        """Set horizontal tab positions (in the current character pitch) at the columns
        specified by n1 to nk, as measured from the left-margin position - ESC D

        Default: Every eight characters
            => 1 tab = 8 chars

        The tab settings move to match any movement in the left margin.

        The printer does not move the print position to any tabs beyond the
        right-margin position. However, all tab settings are stored in the printer’s
        memory; if you move the right margin, you can access previously ignored tabs.

        .. seealso:: :meth:`h_tab`.

        Calculate tab positions based on 10 cpi if proportional spacing is
        selected with the ESC p command.
        Clears any previous tab settings.
        A maximum of 32 horizontal tabs can be set.
        Send an ESC D NUL command to cancel all tab settings.

        Todo: one tab is specified in the current character_pitch but what about
            the interspace character like in BS command (see backspace())
        """
        # Limited to 32 tabs by lark
        column_ids = args[1].value

        # Cancel previous tabs
        self.horizontal_tabulations = [0] * 32

        if not column_ids[0]:
            # No data: Just cancel all tabs
            return

        prev = column_ids[0]
        character_pitch = 1 / 10 if self.proportional_spacing else self.character_pitch
        for tab_idx, tab_width in enumerate(column_ids):
            if tab_width < prev:
                # a value of n less than the previous n ends tab setting (just like the NUL code).
                break

            self.horizontal_tabulations[tab_idx] = tab_width * character_pitch

            prev = tab_width
            LOGGER.debug(
                "tab set at column %s: %s",
                tab_idx,
                self.horizontal_tabulations[tab_idx],
            )

    def set_vertical_tabs(self, *args):
        """Set vertical tab positions (in the current line spacing) at the lines
        specified by n1 to nk, as measured from the top-margin position - ESC B

        Todo: Is the same as setting the vertical tabs in VFU channel 0.
        """
        # Limited to 16 tabs by lark
        line_ids = args[1].value

        # Cancel previous tabs
        self.vertical_tabulations = [0] * 16

        if not line_ids[0]:
            # No data: Just cancel all tabs
            return

        prev = line_ids[0]
        for tab_idx, tab_height in enumerate(line_ids):
            if tab_height < prev:
                # a value of n less than the previous n ends tab setting (just like the NUL code).
                break

            self.vertical_tabulations[tab_idx] = tab_height * self.current_line_spacing

            prev = tab_height
            LOGGER.debug(
                "tab %d set at line %s: %s",
                tab_idx,
                tab_height,
                self.vertical_tabulations[tab_idx],
            )

    def set_italic(self, *_):
        """Enable italic style - ESC 4"""
        self.italic = True
        self.set_font()

    def unset_italic(self, *_):
        """Disable italic style - ESC 5"""
        self.italic = False
        self.set_font()

    def set_bold(self, *_):
        """Set the weight attribute of the font to bold - ESC E"""
        self.bold = True
        self.set_font()

    def unset_bold(self, *_):
        """Unset the weight attribute of the font to normal - ESC F"""
        self.bold = False
        self.set_font()

    def switch_underline(self, *args):
        r"""Turn on/off printing of a line below all characters and spaces - ESC -

        Todo: printed with the following characteristics: draft, LQ, bold, or double-strike.
        Todo: not printed across the distance the horizontal print position is moved
            ESC $, ESC \ (when the print position is moved to the left), HT
        Todo: Graphics characters are not underlined.
        """
        value = args[1].value[0]
        self.underline = value in (1, 49)

    @staticmethod
    @lru_cache
    def register_fonts(*fontnames: str, fontpath: Path | str = None):
        """Register fonts available on the filesystem to the reportlab context (internal usage)

        The function is cached in order to avoid to register a font twice.
        """
        _ = [
            pdfmetrics.registerFont(TTFont(fontname, fontpath))
            for fontname in fontnames
        ]

    def set_font(self) -> bool:
        """Configure the current font (internal usage)

        Use bold, italic, condensed styles, and fixed or proportional spacing
        to choose the font.
        The font is configured with the current point_size.

        Example of filenames for a font:

            "NotoSans-Regular",
            "NotoSans-Bold",
            "NotoSans-CondensedBoldItalic",
            "NotoSans-CondensedBold",
            "NotoSans-CondensedItalic",
            "NotoSans-Condensed",
            "NotoSans-Italic"

        .. warning:: If a font is not found in the given system path, the current
            font in use is NOT updated.

        :return: True if the font is found and correctly loaded, False otherwise.
        """
        if self.set_font_lock:
            # See master_select() (avoid multiple useless calls)
            return False

        font_type = "proportional" if self.proportional_spacing else "fixed"
        # Get typefaces definitions
        func = self.typefaces[self.typeface][font_type]
        font = func(
            self.condensed and not self.condensed_fallback, self.italic, self.bold
        )
        if font is None:
            # Font is not found
            LOGGER.warning(
                "System font <%s> is not available in <%s> mode; do nothing",
                TYPEFACE_NAMES[self.typeface],
                font_type,
            )
            return False

        if not self.current_pdf:
            return True

        if isinstance(font, Path):
            # Not a font embedded in reportlab
            fontname = font.stem
            self.register_fonts(fontname, fontpath=font)

            # Enable autoscaling only if forced or if auto and the current font
            # is not a condensed variant.
            if self.condensed_fallback:
                self.condensed_autoscaling = True
            else:
                styles = open_font(font)[1]
                self.condensed_autoscaling = not (
                    styles and "condensed" in styles.lower()
                )

            self.current_fontpath = font
            LOGGER.debug("Loaded & used system font: %s", fontname)
        else:
            fontname = font
            self.current_fontpath = None
            LOGGER.debug("Loaded & used reportlab font: %s", fontname)
            self.condensed_autoscaling = True

        self.current_pdf.setFont(fontname, self.point_size)
        return True

    def assign_character_table(self, *args):
        """Assign a registered character table to a character table - ESC ( t

        doc p80

        Decides which encoding must be used to decipher the bytes received.

        .. tip:: Do not assign a registered table to Table 2 if you plan to use
            it for user-defined characters. Once you assign a registered table
            to Table 2, you must reset the printer (with the ESC @ command)
            before you can use it for user-defined characters.

        .. warning::
            d1 should be in [0, 1, 2, 3] for ESCP2,
            d1 should be in [0, 1] for ESCP (24/48 pins), 9 pins.
        """
        d1, d2, d3 = args[1].value
        selected_table = CHARACTER_TABLE_MAPPING[d2, d3]

        # Remap d1 if character code ("0", "1", ...) is used instead of an integer
        if d1 >= 0x30:
            d1 -= 0x30

        if d1 > 1 and self.pins in (9, 24, 48):
            LOGGER.error(
                "Table id %d is NOT expected for the printer's pins mode (%s)",
                d1,
                self.pins,
            )
            return

        # Replace the old table
        self.character_tables[d1] = selected_table

        LOGGER.debug("Assign %s to table %d", selected_table, d1)
        if not selected_table:
            LOGGER.error(
                "Character table %s is not supported (code page not available) "
                "=> will use cp437, do not expect anything good !",
                d1,
            )

    def select_character_table(self, *args):
        """Select the character table to be used for printing from among the four tables 0-3 - ESC t

        Default tables & actions are listed below:

            ESCP2/ESCP:

                0      Italic
                1      PC437
                2      User-defined characters (can shift them under some conditions).
                3      PC437

            9, 24, 48 pins:

                0       Italic
                1       Graphic character table or PC437 (US) according to the doc.

            24, 48 pins:
                2       Shift user-defined characters unconditionally.

        .. note:: Using table means using graphics characters (also called
            bitmap font). At the time, these characters are fixed for a
            graphical & size points of view. For example, they CAN NOT be
            italicized, they CAN NOT be used as super/subscript characters.

            The mapping between bytes and displayable characters is called
            encoding nowadays; thus the tables are only used as an encoding
            setting here.
        """
        value = args[1].value[0]
        match value:
            case 0 | 48:
                character_table = 0
            case 1 | 49:
                character_table = 1
            case (2 | 50) if (
                self.pins in (24, 48)
                or self.pins is None
                and self.character_tables[2] is None
            ):
                # - ESC/P 2 printers:
                #   cannot shift user-defined characters if you have previously
                #   assigned another character table to table 2 using
                #   the ESC ( t command. Once you have assigned a registered
                #   table to Table 2, you cannot use it for user-defined characters
                #   (until you reset the printer with the ESC @ command).
                # - 24/48-pin printers, non-ESC/P 2 printers:
                #   shift user-defined characters unconditionally
                LOGGER.debug(
                    "Shift user-defined characters "
                    "from positions 0 to 127 to positions 128 to 255"
                )
                self.user_defined.shift_upper_charset()
                return
            case (2 | 50):
                # PS: Not available on 9 pins printers; ESCP2 only
                character_table = 2
            case 3 | 51:
                character_table = 3
            case _:  # pragma: no cover
                # Not reachable: filtered in the grammar
                return

        encoding = self.character_tables[character_table]
        if not encoding:
            LOGGER.error(
                "Character table %d is not supported (code page not available) "
                "=> will use cp437, do not expect anything good !",
                character_table,
            )

        self.character_table = character_table

        LOGGER.debug("Select character table %d (%s)", value, encoding)

    def select_international_charset(self, *args):
        """Select the set of characters printed for specific character codes - ESC R

        Allow to change up to 12 of the characters in the current character table
        """
        value = args[1].value[0]
        self.international_charset = value

        LOGGER.debug(
            "Select international charset variant %s (%s)",
            value,
            CHARSET_NAMES_MAPPING[value],
        )

    def select_letter_quality_or_draft(self, *args):
        """Select either LQ or draft printing - ESC x

        Todo: If Draft quality is enabled:
            - Typeface: Draft typeface only => not a concern for us
            - Point size: 10.5 and 21-point sizes only

        If Letter Quality is enabled:

            - Select LQ print quality for ESC/P 2 and ESC/P
            - Select NLQ print quality for 9-Pin ESC/P

        If you select proportional spacing with the ESC p command during draft
        printing, the printer prints an LQ font instead. When you cancel
        proportional spacing with the ESC p command, the printer returns to draft
        printing.

        .. note:: Here and for now, LQ is synonym of NLQ for 9 pins printers.
        """
        value = args[1].value[0]
        match value:
            case 0 | 48:
                self.mode = PrintMode.DRAFT
            case 1 | 49:
                # LQ: ESCP2/ESCP
                # NLQ: 9 pins
                # Todo: 9 pins: Double-strike printing is not possible when NLQ printing is selected
                self.mode = PrintMode.LQ

        # Keep the current value in case switch_proportional_mode is called
        # with a disable order before ESC x (ESC p 0)
        self.previous_mode = self.mode

        LOGGER.debug("Set print quality: %s", self.mode)

    def select_typeface(self, *args):
        """Select the typeface for LQ printing - ESC k

        - Ignored if the user-defined character set is selected.
        - Todo: If draft mode is selected when this command is sent,
            the new LQ typeface will be selected when the printer returns to LQ printing.
        - The Roman typeface is selected if the selected typeface is not available.
        - Ignored if typeface is not available in scalable/multipoint mode.
            => For now this IS NOT honored (we use scalable fonts everywhere).

        .. note:: At the time, the ESC/P 2 command language implements four
            scalable multipoint fonts:
            Roman, Sans Serif, Roman T, and Sans Serif H not available
            to ESC/P printers.

        ESCP2:
            0: Roman*
            1: Sans serif*
            2: Courier
            3: Prestige
            4: Script
            5: OCR-B
            6: OCR-A
            7: Orator
            8: Orator-S
            9: Script C
            10: Roman T*
            11: Sans serif H*
            30: SV Busaba
            31: SV Jittra

        *: also available in multipoint mode

        9 pins:
            0 Roman
            1 Sans serif
        """
        if self.ram_characters:
            return

        value = args[1].value[0]
        previous_value = self.typeface
        if value == previous_value:
            # do nothing if no change
            return

        if value not in self.typefaces:
            LOGGER.error("Typeface selected doesn't exist. Switch to default.")
            self.typeface = self.default_typeface
        else:
            self.typeface = value

        LOGGER.debug("Select printer typeface %s", TYPEFACE_NAMES[self.typeface])

        if not self.set_font():
            # Something bad happened: keep the old value
            self.typeface = previous_value

    def define_user_defined_ram_characters(self, _, header, *data_tokens):
        """Receive user-defined characters - ESC &

        Printer memories:

            - ROM: Built-in character sets
            - RAM: Characters copied from ROM or user-defined characters

        Usage:

        To copy user-defined characters (that have been created with the
        ESC & or ESC : commands) to the upper half of the character table,
        send the ESC % 0 command, followed by the ESC t 2 command.
        However, you cannot copy user-defined characters using ESC t 2 if you
        have previously assigned another character table to table 2 using the
        ESC ( t command.

        Send the ESC % 1 command to switch to user-defined characters.
        Use the ESC ( ^ command to print characters between 0 and 32.

        Description:

        Defining characters when the following attributes are set results in the
        user-defined characters having those attributes: superscript, subscript,
        proportional spacing, draft mode, and LQ mode.

        User-defined characters with differing attributes cannot exist at the same
        time. For example, if normal-size user-defined characters have already
        been defined, and you use this command to define subscript characters,
        the previous normal-size characters are lost.

        Characters in RAM can only be printed as 10.5 or 21-point characters,
        even if you select a different point size with the ESC X command.

        The amount of data expected depends on:

        − The number of dots in the print head (9 or 24/48)
        − The space you specify on the left and right of each character
        − Character spacing (10 cpi, 12 cpi, 15 cpi, or proportional)
        − The size of your characters (normal or super/subscript)
        − The print quality of your characters (draft, LQ, or NLQ mode)

        Doc p263, ESCP2: p91, 9pins: p93.

        :param header: Header of the command, stores the first & the last
            character codes. Allows to calculate the number of characters set.
        :param data_tokens: Iterable of DATA tokens; 1 token for each character.
            The values of the tokens are tuples and follow the type
            `tuple[tuple[int, int, int], bytes]`.

            Example::

                (space_left_a0, char_width_a1, space_right_a2), data
        """
        first_char_code_n, _ = header.value

        # Sync current settings and reset RAM characters if necessary
        self.user_defined.extract_settings(self)

        LOGGER.debug("Current PrintMode: %s", self.mode)
        LOGGER.debug("Current Proportional status: %s", self._proportional_spacing)
        LOGGER.debug("Current Scripting status: %s", self.scripting)

        # Number of bytes in a column
        # Normal characters: 24/48 and 9 pins NLQ
        # k = 3 × a1
        # Super/subscript characters: 24/48 (not possible for 9 pins)
        # k = 2 × a1
        # Draft 9 pins characters:
        # k = a1
        if self.pins == 9:
            colum_bytes_size = 3 if self.mode == PrintMode.LQ else 1
        else:
            column_bytes_size = 2 if self.scripting else 3

        bitmasks = tuple(range(8))
        for char_code, token in enumerate(data_tokens, first_char_code_n):
            (space_left_a0, char_width_a1, space_right_a2), data = token.value
            # Debugging block: print raw data
            # array = np.frombuffer(data, np.uint8)
            # 2D array: isolate each column in the master array
            # array = np.reshape(array, (char_width_a1, column_bytes_size))
            # print(array.shape)
            # print(array)
            # Pillow accept a list of lines, not a list of columns;
            # We need to transpose the 2D array (90° rotation + updown flip)
            # print(array.T)
            # input("pause")

            md5_digest = md5(data).hexdigest()[:7]
            self.user_defined.add_char(md5_digest, char_code)

            LOGGER.debug("Received char; code %s (%d)", format(char_code, '#04x'), char_code)

            if not self.userdef_images_path:
                continue
            # Extract the pixels (dots) from the bits of every byte
            # 0: black color; 0xFF: white color
            # Flatten the 2D array we obtain (list of lists of dots for each byte)
            array = np.array(
                [
                    [0 if (0x80 & (i << mask)) else 0xff for mask in bitmasks]
                    for i in data
                ],
                np.uint8,
            ).flatten()
            # 2D array/matrix: isolate each column in the master array (vector)
            array = np.reshape(array, (char_width_a1, column_bytes_size * 8))
            # Pillow accepts a list of lines, not a list of columns;
            # We need to transpose the matrix (90° rotation + updown flip)
            array = array.T

            LOGGER.debug("Received char; size: %s", array.shape)

            # Save the image for later investigations
            data = Image.fromarray(array)
            # data = data.resize((34, int(24*1.5)))
            data.save(f"{self.userdef_images_path}/char_{md5_digest}.png")

        self.user_defined.update_encoding()
        self.user_defined.save()

    def copy_rom_to_ram(self, *args):
        """Copy the data for the ROM characters to RAM - ESC :

        The following attributes are reflected in the copied font: typeface,
        international character set, size (super/subscript or normal),
        and quality (draft/LQ).

        Doc is unclear:

            When you send the ESC : command, the printer copies all the characters
            from locations 0 to 127 in the currently selected typeface.

            On some printers, you can specify which typeface to copy to RAM memory.

        So, ESC : 0 can mean "keep current typeface whatever it is",
        or "select typeface 0 (Roman)"...

        .. note:: In the current implementation, typeface & international character
            set are not used; respectively, for an implementation choice
            and because already applied to the current encoding.

            Indeed, if typeface is used, it must be used in the settings dict
            that detects a change and decide to clear the RAM content.
            If the typeface here, is not the typeface in use when ESC & is sent,
            the RAM content will be cleared.
            For now we do not expect that the typeface change can be postponed
            until the ESC & use.

        ESCP2:
            Characters copied from locations 0 to 127
        9pins:
            Characters copied from locations 0 to 255;
            Todo: locations from 128 to 255 are taken from the Italic table...

        LX-series printers, ActionPrinter Apex 80, ActionPrinter T-1000, ActionPrinter 2000
            Todo: Only characters from 58 to 63 can be copied to RAM.

        - Erase any characters that are currently stored in RAM.
        - Ignored during multipoint mode (p255).
        - Ignore this command if the specified typeface is not available in ROM.

        Doc p255,p96
        """
        # Get typeface id
        # /!\ If typeface is used (not at the moment),
        # the font change is delayed until RAM characters are activated with ESC %
        typeface = args[1].value[0]

        if self.multipoint_mode:
            # Used in place of @multipoint_mode_ignore (for logging purposes)
            LOGGER.error("You cannot copy ROM characters to RAM during multipoint mode.")
            return

        if typeface not in self.typefaces:
            LOGGER.error("Typeface selected doesn't exist. Ignored.")
            return

        # Use the original ROM encoding, including an eventual international charset
        # (using the property "encoding" is mandatory).
        # We need to bypass RAM encoding (user_defined) if already set;
        # the encoding property must be fooled temporary to return it.
        # => Use the encoding property but temporary disable ram_characters attr.
        ram_characters_backup = self.ram_characters
        self.ram_characters = False
        # Sync current settings
        self.user_defined.extract_settings(self)
        self.user_defined.from_rom(self.encoding, typeface, self.pins)
        self.ram_characters = ram_characters_backup

    def select_user_defined_set(self, *args):
        """Switch between normal and user-defined characters - ESC %

        .. seealso:: :meth:`encoding` where the attribute `ram_character` is used.
        """
        value = args[1].value[0]
        self.ram_characters = value in (1, 49)

        LOGGER.debug("User-defined (RAM) characters: %s", self.ram_characters)

    def select_cpi(self, _, cmd_letter: Token):
        """Selects 10.5-point, *-cpi character printing - ESC P, ESC M, ESC g

        Used by ESC/P-level printers, as well as ESC/P 2 printers that are not in
        multipoint mode, to adjust the character pitch.

        cancels the HMI set with the ESC c command.
        cancels multipoint mode.

        Todo: If you change the pitch with this command during proportional mode
            (selected with the ESC p command), the change takes effect when the
            printer exits proportional mode.

        9 pins: character pitch only, no modification of the point size;
            see explanations at :meth:`cancel_multipoint_mode`.

        :param _: ESC byte command
        :param cmd_letter: ESC letter in ESC P, ESC M, ESC g commands,
            respectively for 10, 12, 15 cpi character printing.
        """
        match cmd_letter.value:
            case b"P":
                # 10-cpi character printing
                self.character_pitch = 1 / 10
            case b"M":
                # 12-cpi character printing
                self.character_pitch = 1 / 12
            case b"g":
                # 15-cpi character printing
                self.character_pitch = 1 / 15

        self.cancel_multipoint_mode()

    def select_font_by_pitch_and_point(self, *args):
        """Put the printer in multipoint (scalable font) mode, and select the
        pitch and point attributes of the font - ESC X

        Pitch:
            m = 0 No change in pitch (allow to change only the point size)
            m = 1 Selects proportional spacing
            m ≥ 5 Selects fixed pitch equal to 360/m cpi

        Point size (height of the characters):
            1 point equals 1/72 inch. If nL & nH are equal to zero, the point
            size will not be modified.
            Only the following point sizes are available:
            8, 10 (10.5), 12, 14, 16, 18, 20 (21), 22, 24, 26, 28, 30, 32

        Default settings:
            Pitch = 10 cpi (m = 36)
            Point = 10.5 (nH = 0, nL = 21)

        .. note:: Use multipoint_mode to select a scalable version of the selected font.
            Not all typefaces are available in multipoint mode; see the Command Table
            for the typefaces available in multipoint mode on each printer.
            => For now this IS NOT honored (we use scalable fonts everywhere).

        The ESC/P 2 command language implements four scalable multipoint fonts:
        Roman, Sans Serif, Roman T, and Sans Serif H not available to ESC/P printers.

        - ESC/P 2 only
        Todo:
            Selecting a combination of 15 cpi and 10 or 20-point characters results
            in 15-cpi ROM characters being chosen; the height of these characters
            is about 2/3 that of normal characters.
            Select the pitch with the ESC c command to obtain normal height 10
            or 20-point characters at 15 cpi.

        During multipoint mode the printer ignores the ESC W, ESC w, ESC SP,
        DC2, DC4, SI, ESC SI, SO, and ESC SO commands.
        ESC k is ignored if typeface is not available in scalable/multipoint mode.
        See the decorator :meth:`multipoint_mode_ignore`.

        .. seealso:: A second method to change the pitch can be :meth:`set_horizontal_motion_index` (ESC c).
        """
        m, nL, nH = args[1].value

        # Allow the use of scalable fonts
        self.multipoint_mode = True

        # Character pitch
        if m == 1:
            # Proportional spacing
            self.proportional_spacing = True
        elif m:
            # Fixed spacing: 360/m cpi = m/360 inch
            self.character_pitch = m / 360

        # Point size
        point_size = ((nH << 8) + nL) / 2

        if point_size:
            self.point_size = point_size

        # Cancel HMI set_horizontal_motion_index() ESC c command
        self.character_width = None

    def cancel_multipoint_mode(self):
        """Cancel multipoint mode & HMI

        Characters normally have a size of 10.5 points. You can also print 21-point
        characters as shown below (p278).

        ESC P, ESC M, ESC g, ESC p, ESC !, ESC @, and
        HMI :meth:`set_horizontal_motion_index` ESC c.
        """
        # Cancel select_font_by_pitch_and_point() ESC X command
        self.multipoint_mode = False
        # Cancel HMI set_horizontal_motion_index() ESC c command
        self.character_width = None
        # Return to 10.5-point (in theory for ESCP2/ESCP printers only)
        # PS: In fact on 9pins printers, point size can only
        # be 10.5 or 21 (in double-height mode only) (so always 10.5).
        # The implementation should not touch double-height, but my
        # implementation of double-height multiplies the point size by 2;
        # in this case it must be preserved, so overall it doesn't differ
        # from 9pins implementation where nothing is changed...
        # self.point_size = 10.5  # From the manual's implementation for ESCP2 only
        self.point_size = 21 if self.double_height else 10.5

    @staticmethod
    def multipoint_mode_ignore(func):
        """Decorator used to ignore the function if the multipoint mode is enabled

        Multipoint mode is the use of a scalable version of the current font.
        """

        def modified_func(self, *args, **kwargs):
            """Returned modified function"""
            if self.multipoint_mode:
                return
            return func(self, *args, **kwargs)

        return modified_func

    def set_horizontal_motion_index(self, *args):
        """Fixes the character width (HMI) - ESC c

        HMI: determine the fixed distance to move the horizontal position when
        printing characters in inches per character (instead of character per inch).

        .. warning::
            - Seems to be used only during multipoint mode ?????.
            - In multipoint mode, the character width depends ONLY on the
              selected point-size (and values stored in tables).
              See :meth:`compute_horizontal_scale_coef` that should return 1
              in this situation.

        - ESP2 only
        - Cancel additional character space set with the ESC SP command
        - Canceled by: ESC P, ESC M, ESC g, ESC SP, ESC p, ESC !, SO, SI, DC2,
          DC4, ESC W, (via :meth:`cancel_multipoint_mode`), ESC w, ESC X, and ESC @.
        - The HMI set cancels the pitch set with the ESC X command.

        Todo:
            Use this command to set the pitch if you want to print normal-height 10 or 20-point
            characters at 15 cpi during multipoint mode. Selecting 15 cpi for 10 or 20-point
            characters with the ESC X command results in characters being printed at 2/3 their
            normal height.

        """
        nL, nH = args[1].value
        value = (nH << 8) + nL
        hmi = value / 360

        if not 0 < hmi <= 3:
            LOGGER.warning(
                "HMI should be > to 0 and <= to 3 inches (%s) => ignored", hmi
            )
            return

        self.character_width = hmi
        # Cancel extra space set_intercharacter_space ESC SP command
        self.extra_intercharacter_space = 0

    @property
    def character_pitch(self) -> float:
        """Get the character pitch

        :return: The character pitch in inches per character unit (not cpi).
            Note that the HMI (Horizontal Motion Index) has priority over
            the character pitch legacy setting.
            See :meth:`set_horizontal_motion_index`.
        """
        return self.character_width or self._character_pitch

    @character_pitch.setter
    def character_pitch(self, value: float):
        """Set the character pitch (in inches per character unit)"""
        self._character_pitch = value

    @property
    def proportional_spacing(self) -> bool:
        """Get the proportional spacing status"""
        return self._proportional_spacing

    @proportional_spacing.setter
    def proportional_spacing(self, proportional_spacing: bool):
        """Enable proportional spacing or fixed spacing

        On ESCP2/ESCP printers, when multipoint mode is DISABLED,
        if you select proportional spacing with the ESC p
        command during draft printing, the printer prints an LQ font instead.
        When you cancel proportional spacing with the ESC p command,
        the printer returns to draft printing.

        .. seealso:: :meth:`switch_proportional_mode`, :meth:`master_select`.
        """
        self._proportional_spacing = proportional_spacing in (1, 49)

        self.set_font()

        if self.multipoint_mode or self.pins == 9:
            # ESC X (multipoint mode), or 9pins printers
            return
        # Not multipoint mode and ESCP2
        if self._proportional_spacing:
            # Force LQ mode if in Draft mode
            self.previous_mode = self.mode
            self.mode = PrintMode.LQ
        else:
            # Restore previous mode (set Draft or keep LQ in other case)
            self.mode = self.previous_mode

    def switch_proportional_mode(self, *args):
        """Select either proportional or fixed character spacing - ESC p

        Proportional spacing:

            In this type of spacing, the character width varies by character.
            => Almost "like" multipoint mode (scalable) but using tables to obtain
            the spaces required by each character.

        - cancel the HMI set with the ESC c command
        - cancel multipoint mode

        .. note:: ESCP2/ESCP only: If you select proportional spacing with the ESC p
            command during draft printing, the printer prints an LQ font instead.
            When you cancel proportional spacing with the ESC p
            command, the printer returns to draft printing.

            An equivalent command is ESC ! 2, note that although ESC X also
            activates the proportional mode it's a different behavior with
            respect to the PrintMode status (it behaves in multipoint mode).
        """
        self.cancel_multipoint_mode()
        self.proportional_spacing = args[1].value[0]

    @multipoint_mode_ignore
    def set_intercharacter_space(self, *args):
        """Increase the space between characters by n/180 inch in LQ mode
        and n/120 inch in draft mode - ESC SP

        Add a fixed amount of space to the right of every character.
        This additional space is added to both fixed-pitch and proportional characters.

        TL;DR: new character width = (previous character width) + (extra space)

        - cancels the HMI (horizontal motion unit) set with the ESC c command.
        - The extra space set with this command doubles during double-width mode.

        9 pins:
            Increases the space between characters by n/120 inch
        """
        # 3rd argument, see the terminal independant def in the grammar (SP is a control code)
        value = args[2].value[0]

        coef = 180 if self.mode == PrintMode.LQ and self.pins != 9 else 120
        self.extra_intercharacter_space = value / coef
        # Cancel HMI set_horizontal_motion_index() ESC c command
        self.character_width = None

    def master_select(self, *args):
        """Select any combination of several font attributes and enhancements - ESC !

        - cancel multipoint mode
        - cancel the HMI selected with the ESC c command
        - cancel any attributes or enhancements that are not selected

        bitmasks :
            1,  # 12 cpi vs 10 cpi,  ESC M vs ESC P
            2,  # proportional ESC p
            4,  # condensed DC2, SI
            8,  # bold ESC F, ESC E
            16,  # double-strike ESC H, ESC G
            32,  # double-with multiline ESC W
            64,  # italics ESC 5, ESC 4
            128,  # underline ESC -
        """
        value = args[1].value[0]

        # Temporary block set_font refresh (must be called once at the end)
        self.set_font_lock = True

        # NOTE: do not use if ESC P/M methods are called later when
        # character_pitch is changed (these functions is already call it)
        # For now, the implementation doesn't call select_cpi() method.
        self.cancel_multipoint_mode()  # can trigger set_font

        self.character_pitch = 1 / 12 if value & 1 else 1 / 10
        # /!\ Use setter, make sure that multipoint mode is canceled before.
        self.proportional_spacing = bool(value & 2)  # can trigger set_font
        self.condensed = bool(value & 4)  # can trigger set_font
        self.bold = bool(value & 8)
        self.double_strike = bool(value & 16)
        self.double_width_multi = bool(value & 32)
        self.italic = bool(value & 64)
        self.underline = bool(value & 128)

        # Mandatory for bold & italic that are not properties that trigger
        # set_font()
        self.set_font_lock = False
        self.set_font()

    def set_double_strike_printing(self, *_):
        """Print each dot twice, with the second slightly below the first, creating bolder characters - ESC G

        Todo: 9 pins:
            LQ/NLQ mode overrides double-strike printing;
            double-strike printing resumes when LQ/NLQ mode is canceled.
            => only available in Draft

        .. note:: We use bold setting for now.
        """
        self.set_bold()

    def unset_double_strike_printing(self, *_):
        """Cancel double-strike printing selected with the ESC G command - ESC H"""
        self.unset_bold()

    def select_line_score(self, *args):
        r"""Turn on/off scoring of all characters and spaces following this command - ESC ( -

        - Only ESCP2/ESCP 24/48 pins
        - Todo: does not affect graphics characters
        - Each type of scoring is independent of other types; any combination of
          scoring methods may be set simultaneously.
        - The position and thickness of scoring depends on the current point
          size setting.
        - Printed with the following characteristics: draft, LQ, bold, or
          double-strike.
          => We assume that double-height and double-width are also followed!!!
        - Not printed across the distance the horizontal print position is moved
          ESC $, ESC \ (when the print position is moved to the left), HT.
          => only printed with characters.

        .. note:: For now, it's not the same scoring as the underline obtained
            with ESC - which is traced with a line.
            This should be; and may be implemented later.

            See :meth:`apply_text_scoring`.
        """
        scoring_type_d1, scoring_style_d2 = args[1].value
        scoring_types = {
            1: "Underline",  # below
            2: "Strikethrough",  # middle
            3: "Overscore",  # above
        }
        scoring_styles = {
            0: "Turn off scoring",
            1: "Single continuous line",
            2: "Double continuous line",
            5: "Single broken line",
            6: "Double broken line",
        }
        LOGGER.debug(
            "Scoring: %s, %s",
            scoring_types[scoring_type_d1],
            scoring_styles[scoring_style_d2],
        )

        # if scoring_type_d1 == 1:
        #     # Handle underline
        #     self.underline = scoring_style_d2 == 1
        self.scoring_types[scoring_type_d1] = scoring_style_d2

    def set_script_printing(self, *args):
        """Print characters that follow at about 2/3 their normal height - ESC S

        - Does not affect graphics characters.
        - The underline strikes through the descenders on subscript characters
        - ESC T command cancels super/subscript printing.

        The printing location depends on the given value.
        Superscript characters are printed in the upper two-thirds of the normal
        character space; subscript characters are printed in the lower two-thirds.

        .. note:: Script printing + proportional mode:
            For ESCP2, at the time,
            the width of super/subscript characters when using proportional spacing
            differs from that of normal characters; see the super/subscript
            character proportional width table in the Appendix.

            For 9 pins : the width is the same as that of normal characters
            (Todo: Not implemented).

        Prints characters that follow at about 2/3 their normal height.
        When point sizes other than 10 (10.5) and 20 (21) are selected in
        multipoint mode, super/subscript characters are printed at the nearest
        point size less than or equal to 2/3 the current size.
        => so they are always in 2/3 size.

        PS: not for 9 pins on doc p136 but about all printers in final doc p285:
        When 8-point characters are selected, super/subscript characters are
        also 8-point characters.

        FX-850, FX-1050 and more generally for 9 pins printers:
            Selecting double-height printing overrides super/subscript printing;
            super/subscript printing resumes when double-height printing is canceled.
        """
        value = args[1].value[0]
        scripting = PrintScripting.SUB if value in (1, 49) else PrintScripting.SUP

        if self.double_height and self.pins == 9:
            # Will be enabled at the exit of double-height
            self.previous_scripting = scripting
            return

        self.scripting = scripting
        LOGGER.debug("Scripting status: %s", self.scripting)

    def unset_script_printing(self, *_):
        """Cancel super/subscript printing selected by the ESC S command - ESC T"""
        self.scripting = None
        # Force to not restore disabled scripting at the exit of double-height
        # In non 9 pins mode this has no effect on double-height
        self.previous_scripting = None
        LOGGER.debug("Scripting status: %s", self.scripting)

    def select_character_style(self, *args):
        """Turn on/off outline and shadow printing - ESC q

        - only ESCP2/ESCP 24/48 pins
        - Todo: does not affect graphics characters
        """
        value = args[1].value[0]
        # Map character style ids with reportlab text render modes
        character_style_mapping = {
            0: None,
            1: PrintCharacterStyle.OUTLINE,
            2: PrintCharacterStyle.FILL,
            3: PrintCharacterStyle.SHADOW,
        }
        # We use reportlab text render modes in this attribute! Not the ESC style id!
        self.character_style = character_style_mapping.get(value)

        if LOGGER.level != DEBUG:  # pragma: no cover
            return
        character_style_names = {
            0: "Turn off outline/shadow printing",
            1: "Turn on outline printing",
            2: "Turn on shadow printing",
            3: "Turn on outline and shadow printing",
        }
        LOGGER.debug(
            "Set character style: %s; text render: %s",
            character_style_names.get(value),
            self.character_style,
        )

    @property
    def condensed(self) -> bool:
        """Get condensed printing mode status"""
        return self._condensed

    @condensed.setter
    @multipoint_mode_ignore
    def condensed(self, condensed: bool):
        """Switch condensed printing mode and update character pitch

        9 pins only:
            - Ignored ("not available" ?!) when proportional spacing is selected.

        ESCP2 only:
            - Reduces character width by about 50% when proportional spacing is selected;
            - Ignored on multipoint (no multipoint mode on 9pins);
            - Ignored if character pitch is selected by ESC g.

        Called by :meth:`select_condensed_printing`, :meth:`unset_condensed_printing`,
        :meth:`master_select` (SI, ESC SI, DC2, ESC ! commands).
        """
        if self.character_pitch == 1 / 15 and self.pins != 9:
            # Ignore due to ESC g action for ESCP2 only
            return
        if self.pins == 9 and self.proportional_spacing:
            return

        # Cancel HMI set_horizontal_motion_index() ESC c command
        # Note: the position is OK: ESC c is only used on ESCP2 printers,
        # thus, here the command can't be ignored.
        self.character_width = None

        if condensed == self._condensed:
            # Do not modify settings twice
            LOGGER.warning("Condensed printing already configured: %s", condensed)
            return

        if self.double_height and self.pins == 9:
            # Postpone modification at the exit of double-height
            self.previous_condensed = condensed
            return

        self._condensed = condensed
        LOGGER.debug("Set condensed printing: %s", condensed)

        # Update character pitch
        if condensed:
            if self.proportional_spacing:
                self.character_pitch *= 0.5
            elif self.character_pitch == 1 / 10:
                self.character_pitch = 1 / 17.14
            elif self.character_pitch == 1 / 12:
                self.character_pitch = 1 / 20
        else:
            if self.proportional_spacing:
                self.character_pitch *= 2
            elif self.character_pitch == 1 / 17.14:
                self.character_pitch = 1 / 10
            elif self.character_pitch == 1 / 20:
                self.character_pitch = 1 / 12

        self.set_font()

    @multipoint_mode_ignore
    def select_condensed_printing(self, *_):
        """Enter condensed mode, in which character width is reduced - SI, ESC SI

        Ignored if 15-cpi printing has been selected with the ESC g command
        (ignored for ESCP2 and not for 9pins).

        Change character pitch values according to the current pitch:

            - 1/10 : 1/17.14
            - 1/12 : 1/20
        """
        self.condensed = True

        # Cancel HMI set_horizontal_motion_index() ESC c command
        self.character_width = None

    @multipoint_mode_ignore
    def unset_condensed_printing(self, *_):
        """Cancel condensed printing selected by the SI or ESC SI commands - DC2

        Equivalent to ESC !

        Restore previous character pitch values (before SI command):

            - 1/17.14 : 1/10
            - 1/20 : 1/12
        """
        # Reset character pitch
        self.condensed = False

        # Cancel HMI set_horizontal_motion_index() ESC c command
        self.character_width = None

    @multipoint_mode_ignore
    def select_double_width_printing(self, *_):
        """Double the width of all characters, spaces, and intercharacter spacing
        (set with the ESC SP command) following this command ON THE SAME LINE. - SO, ESC SO

        Canceled when the buffer is full, or the printer receives the following commands:
        LF, FF, VT, DC4, ESC W 0.

        .. seealso:: :meth:`unset_double_width_printing`,
            :meth:`switch_double_width_printing`, :meth:`v_tab`.

        Double-width handling:
            - ESCP2:
            Do NOT cancel double-width when VT functions the same as a CR command
            (normal behavior).
            - non-ESC/P 2 printers:
            Cancel double-width when VT functions the same as a CR command,
            and with a CR command.
            (normal behavior).
        """
        self.double_width = True

        # Cancel HMI set_horizontal_motion_index() ESC c command
        self.character_width = None

        LOGGER.debug("Double-width one line status: %s", self.double_width)

    @multipoint_mode_ignore
    def unset_double_width_printing(self, *_):
        """Cancels double-width printing selected by the SO or ESC SO commands - DC4

        .. seealso:: :meth:`select_double_width_printing`,
            :meth:`switch_double_width_printing`

        Does not cancel double-width printing selected with the ESC W command.
        => distinction between 1-line and multiline.
        """
        self.double_width = False

        # Cancel HMI set_horizontal_motion_index() ESC c command
        self.character_width = None

        LOGGER.debug("Double-width one line status: %s", self.double_width)

    @multipoint_mode_ignore
    def switch_double_width_printing(self, *args):
        """Turn on/off double-width printing of all characters, spaces,
        and intercharacter spacing (set with the ESC SP command) - ESC W

        .. warning:: Action on MULTIPLE lines! Not like ESC SO, SO
            Does not cancel double-width printing selected with the SO, ESC SO commands.
            => distinction between 1-line and multiline.

            Also cancels double-width selected by ESC ! (equivalent command).

        .. seealso:: :meth:`select_double_width_printing`,
            :meth:`unset_double_width_printing`
        """
        value = args[1].value[0]
        self.double_width_multi = value in (1, 49)

        # Cancel HMI set_horizontal_motion_index() ESC c command
        self.character_width = None

        LOGGER.debug("Double-width multiline status: %s", self.double_width)

    @multipoint_mode_ignore
    def switch_double_height_printing(self, *args):
        """Turns on/off double-height printing of all characters - ESC w

        doc p278

        On Non-ESC/P 2 AND in ESCP2 typefaces not available in multipoint mode,
        ESC w is the only way to modify the point size:

            - ESC w 1: Selects double-height (21-point) characters
            - ESC w 0: Selects normal (10.5-point) characters

        Todo: The first line of a page is not doubled if ESC w is sent on the first
            printable line; all following lines are printed at double-height.

        9 pins: Double-height printing overrides:

            - super/subscript,
            - condensed,
            - Todo: and high-speed draft printing;
            They all resume when double-height printing is canceled.
        """
        value = args[1].value[0]
        double_height = value in (1, 49)

        if double_height != self.double_height:
            self.point_size *= 2 if double_height else 0.5

        if self.pins == 9:
            if double_height:
                # Disable scripting temporarly
                # When scripting is modified, double-height is checked and
                # previous_mode is updated so that ESC S takes precedence at the exit
                # of the double-height mode.
                self.previous_scripting = self.scripting
                self.scripting = None

                # Disable condensed mode temporarly
                self.previous_condensed = self.condensed
                self.condensed = False
            else:
                self.scripting = self.previous_scripting

                # Set before modifying condensed value
                # (if not, the inner test will modify previous_condensed instead)
                self.double_height = double_height
                self.condensed = self.previous_condensed

        self.double_height = double_height

        # Cancel HMI set_horizontal_motion_index() ESC c command
        self.character_width = None

        LOGGER.debug("Double-height status: %s", self.double_height)
        LOGGER.debug("scripting status: %s", self.scripting)

    def print_data_as_characters(self, *args):
        """Print data as characters - ESC ( ^

        - only ESCP2

        .. warning:: Should ignore data if no character is assigned to that
            character code in the currently selected character table.

            Since we redirect the data content to :meth:`binary_blob`.
            The data will be decoded there.
            For now it use `replace` or `backslashreplace` not `ignore`.

        .. todo:: Control codes meaning varies according the context (graphical
            or not). Many(all?) tables should have graphics caracters but they not.
            Ex: cp437 has no graphic character under in the interval 0x01-0x1f,
            0x7f.
            These characters should be injected after the decoding process.
            See: `Stackoverflow question <https://stackoverflow.com/questions/46942721/is-cp437-decoding-broken-for-control-characters>`_

        doc p157
        """
        self.binary_blob(Token("DATA", args[2].value))

    def set_upper_control_codes_printing(self, *_):
        """Treat codes from 128 to 159 as PRINTABLE CHARACTERS instead of control codes - ESC 6, ESC m

        Has no effect when the italic character table is selected; no characters
        are defined for these codes in the italic character table.

        Interval: 0x80-0x9f

        Remains in effect even if you change the character table

        .. note:: About default config:
            ESCP2, ESCP: Codes 128 to 159 are treated as printable characters
            9pins: Codes 128 to 159 are treated as control codes

        .. seealso:: :meth:`unset_upper_control_codes_printing`

        p159
        """
        # Remove the codes from the filter => they will be printed
        self.control_codes_filter -= PrintControlCodes.UPPER.value

    def unset_upper_control_codes_printing(self, *_):
        """Treat codes from 128 to 159 as CONTROL CODES instead of printable characters - ESC 7, ESC m

        .. seealso:: :meth:`set_upper_control_codes_printing`
        """
        self.control_codes_filter |= PrintControlCodes.UPPER.value

    def switch_control_codes_printing(self, *args):
        """Treat codes 0-6, 16, 17, 21-23, 25, 26, 28-31, and 128-159 as printable
         characters according to the given setting - ESC I

        Intervals: shaded codes in table in manual (A-30).

        - 0-6, 16: None of them are used alone in ESC commands;
        - 17 (DC1: 0x11): Select printer command!! See :meth:`select_printer`;
        - 21-23 (NAK: 0x15, SYN: 0x16, ETB: 0x17): None of them are used alone
            in ESC commands;
        - 25, 26, 28-31: None of them are used alone in ESC commands.

        Has no effect when the italic character table is selected; no characters
        are defined for these codes in the italic character table.

        Remains in effect even if you change the character table

        .. note:: Function for 9pins only; About default config:
            Codes are treated as control codes

        :param args: Value at index 1:
            If 1: process codes as printable characters
            If 0: do NOT process codes as printable characters => discarded
        """
        value = args[1].value[0]

        if value:
            # Remove the codes from the filter => they will be printed
            self.control_codes_filter -= PrintControlCodes.SELECTED.value
        else:
            self.control_codes_filter |= PrintControlCodes.SELECTED.value

    def select_printer(self, *_):
        """Select the printer after it has been deselected with the DC3 command - DC1

        This is a nonrecommended command. The SLCT IN signal on the interface must
        be high to use this command. This command is nearly always unnecessary.

        .. warning:: This is the only command for which the code can be printable.
            Its status is configured by :meth:`switch_control_codes_printing`.
        """
        if b"\x11" not in self.control_codes_filter:
            # The command is not considered as a control code => print it!
            self.binary_blob(Token("DATA", b"\x11"))

    def control_paper_loading_ejecting(self, *args):
        """Control feeding of continuous and single-sheet paper - ESC EM

        0   Exits cut-sheet feeder mode; nonrecommended on escp2
        1   Selects loading from bin 1 of the cut-sheet feeder
        2   Selects loading from bin 2 of the cut-sheet feeder
        4   Enters cut-sheet feeder mode; nonrecommended on escp2
        B   Loads paper from the rear tractor
        F   Loads paper from the front tractor
        R   Ejects one sheet of single-sheet paper

        Todo R (ESCP2):
            ejects the currently loaded single-sheet paper without printing data
            from the line buffer; this is not the equivalent of the FF command
            (which does print line-buffer data).
        """
        # 3rd argument, see the terminal independent definitions in the grammar
        value = chr(args[2].value[0])

        if self.single_sheet_paper and value == "R":
            self.next_page()

    ## GRAPHIIICSSSss !!! (òÓ,)_\,,/

    def set_graphics_mode(self, *_):
        r"""Select graphics mode (allowing to print raster graphics) - ESC ( G

        .. note:: only ESCP2

        - exit by ESC @
        - turn MicroWeave printing off
        - clear tab settings
        - clear all user-defined characters

        Only available commands:
            LF          Line feed
            FF          Form feed
            CR          Carriage return
            ESC EM      Control paper loading/ejecting
            ESC @       Initialize printer (exit graphics mode)
            ESC .       Print raster graphics
            ESC . 2     Enter TIFF compressed mode*
            ESC ( i     Select MicroWeave print mode*
            ESC ( c     Set page format
            ESC ( C     Set page length in defined unit
            ESC ( V     Set absolute vertical print position
            ESC ( v     Set relative vertical print position
            ESC \       Set relative vertical print position
            ESC $       Set absolute horizontal print position
            ESC r       Select printing color
            ESC U       Turn unidirectional mode on/off
            ESC +       Set n/360-inch line spacing
            ESC ( U     Set unit

            *: available only with the Stylus COLOR and later inkjet printer models

        Todo:
            You cannot move the print position in a negative direction (up) while in graphics mode.
            Also, the printer ignores commands moving the vertical print position in a negative
            direction if the final position would be above any graphics printed with this command.

        Todo: Text printing should not be possible; DO NOT MIX text/graphics on the same page.

        .. tip:: The print position is the top printable row of dots.
        """
        self.graphics_mode = True
        self.microweave_mode = False

        # Clear tab settings
        self.horizontal_tabulations = [0] * 32
        self.vertical_tabulations = [0] * 16

        # Clear all user-defined characters
        self.user_defined.clear()

    def switch_microweave_mode(self, *args):
        """Turn MicroWeave print mode off and on - ESC ( i

        .. note:: MicroWeave increases printing time, but it completely eliminates
            banding and yields sharp, near photographic-quality color images.

            => It's a purely mechanically related setting. Not used here.

        Todo: only available during raster graphics printing.

        Sending an ESC @ or ESC ( G command turns MicroWeave printing off.
        """
        value = args[1].value[0]
        self.microweave_mode = value in (1, 49)

    def print_raster_graphics(self, *args):
        """Print raster graphics - ESC .

        Doc p179, p304, examples p335

        Graphics modes supported:

            - 0: Full graphics mode
            - 1: RLE compressed raster graphics mode

        - ESCP2 only !!
        - Todo: available in graphics mode only via ESC ( G
        - Todo: Print data that exceeds the right margin is ignored.
        - When MicroWeave is selected, the image height m must be set to 1.
        - Use only one image density and do not change this setting once in raster
          graphics mode.

        Todo:
            You cannot move the print position in a negative direction (up) while in graphics mode.
            Also, the printer ignores commands moving the vertical print position in a negative
            direction if the final position would be above any graphics printed with this command.
        """
        # v_dot_count_m (number of rows of dots): 1, 8, or 24
        graphics_mode, v_res, h_res, v_dot_count_m, nL, nH = args[1].value
        if self.microweave_mode and v_dot_count_m != 1:
            # In these settings, one raster line printed at a time
            # However we assume that the data is formatted for the given
            # resolution, and since Microweave technology has no impact on
            # peration, we let the printing process take its course.
            LOGGER.warning(
                "To use MicroWeave, the band height (m) in the ESC . command "
                "must be set to 1 (one line) => value NOT corrected"
            )

        # Convert dpi to inches: 1/180, 1/360 or 1/720 inches, (180, 360 or 720 dpi)
        self.vertical_resolution = v_res / 3600
        self.horizontal_resolution = h_res / 3600

        # Number of columns of dots
        h_dot_count = (nH << 8) + nL
        # Used by print_raster_graphics_dots() to chunk data stream
        self.bytes_per_line = int((h_dot_count + 7) / 8)

        if LOGGER.level == DEBUG:
            expected_bytes = v_dot_count_m * self.bytes_per_line

            LOGGER.debug(
                "expect %s bytes (%s dots = %s byte(s) per line)",
                expected_bytes,
                h_dot_count,
                h_dot_count / 8,
            )
            LOGGER.debug(
                "vertical x horizontal resolution: %s/360 x %s/360",
                v_res // 10,
                h_res // 10,
            )
            LOGGER.debug("height x width: %sx%s", v_dot_count_m, h_dot_count)
            # LOGGER.debug("microweave_mode: %s", self.microweave_mode)
            LOGGER.debug("line spacing: %s", self.current_line_spacing)
            LOGGER.debug("start coord: %s, %s", self.cursor_x, self.cursor_y)

        data = args[2].value
        if graphics_mode == 1:
            # Decompress RLE compressed data
            data = self.decompress_rle_data(data)

        # Print dots on the canvas
        self.print_raster_graphics_dots(data, h_dot_count=h_dot_count)

    def print_raster_graphics_dots(self, data, h_dot_count=None):
        """Print the dots in the given bytes

        Unlike bitimage printing, raster mode prints the bytes received from
        left to right on the same line, line after line.

        - You can specify the horizontal dot count in 1-dot increments.
          If the dot count is not a multiple of 8, the remaining data in the data
          byte at the far right of each row is ignored
          (the bits in it should be 0!?).

        - The final print position is the dot after the far right dot on the top
          row of the graphics printed with this command.

        .. note:: About the radius of circle dots.
            See explanations on :meth:`print_bit_image_dots`.

        :param data: Decompressed data bytes (1 byte for 8 dots).
        :key h_dot_count: (default: None) Total number of dots for the given line(s)
            Used to move the cursor_x after the data has been printed.
            Can be None if the number is unknown (See ESC . 2 TIFF mode).
        :type data: bytearray
        :type h_dot_count: int
        """
        code = self.current_pdf._code
        horizontal_resolution = self.horizontal_resolution
        vertical_resolution = self.vertical_resolution
        cursor_x = self.cursor_x
        cursor_y = self.cursor_y
        dots = self.dots_as_circles

        def chunk_this(iterable, length):
            """Split iterable in chunks of equal sizes"""
            iterator = iter(iterable)
            for _ in range(0, len(iterable), length):
                yield tuple(it.islice(iterator, length))

        mask = 0x80
        overflow_mask = 0xff
        y_pos = cursor_y
        column_offset = i = 0

        if dots:
            # Configure setlinecap: round
            # Configure linewidth
            # No noop to end previous path (useless here)
            linewidth = round(horizontal_resolution * 72 * 1.28, 2)
            code.append(f"1 J {linewidth} w")
        else:
            h_res = "{:.2f}".format(horizontal_resolution * 72).rstrip("0")
            v_res = "{:.2f}".format(vertical_resolution * 72).rstrip("0")
            rect_suffix = f" {h_res} {v_res} re"

        # Iterate on bytes inside lines
        # Iterate on lines first
        for line_bytes in chunk_this(data, self.bytes_per_line):
            # Keep track of the x position in the current line
            column_offset = 0
            cy = "{:.2f}".format(y_pos * 72).rstrip("0")
            for col_int in line_bytes:
                # Consume all bits of the current byte
                # at each loop the current byte is shifted to the left with an offset of 1.
                # This avoids testing the remaining bits if their value is zero.
                i = 0
                while col_int:
                    if col_int & mask:
                        x_pos = cursor_x + (column_offset + i) * horizontal_resolution
                        # print("offset, i: x,y", column_offset, i, x_pos, y_pos)
                        cx = "{:.2f}".format(x_pos * 72).rstrip("0")
                        code.append(
                            f"{cx} {cy} m {cx} {cy} l"
                            if dots
                            else (f"{cx} {cy}" + rect_suffix),
                        )
                    # Consume the MSB
                    col_int = overflow_mask & (col_int << 1)
                    i += 1
                column_offset += 8

            # Print the next line below
            y_pos -= vertical_resolution

            # Close path and stroke or fill
            # => can be at the upper level, but breaks 1dot_v_band test
            code.append("S" if dots else "f")

        # Get rid of the last bits of potentially, partially used last byte
        # (just use the number of expected dots).
        # If horizontal expected dot count is not provided (as it is the case
        # when the function is called by <XFER> in tiff compressed mode),
        # just use the x offset on the unique line (column_offset)
        # adjusted to reflect the number of the set bits in the last byte.
        printed_dots = h_dot_count if h_dot_count else column_offset - 8 + i
        self.cursor_x = printed_dots * horizontal_resolution

    @staticmethod
    def decompress_rle_data(compressed_data: bytearray) -> bytearray:
        """Decompress the given data bytes (TIFF decompression)

        During compressed mode, the first byte of data must be a counter.
        If the counter is positive, it is treated as a data-length counter.
        If the counter is negative (as determined by two’s complement),
        it is treated as a repeat counter.

        In the first case, the printer read as is the number of bytes specified.
        In the last case, the printer repeats the following byte of data the
        specified number of times.

        :return: Decompressed data.
        """
        decompressed_data = bytearray()
        iter_data = iter(compressed_data)
        for counter in iter_data:
            if counter & 0x80:
                # Repeat counters: number of times to repeat data
                repeat = 256 - counter + 1
                decompressed_data += (next(iter_data)).to_bytes(1) * repeat
            else:
                # Data-length counters: number of data bytes to follow
                block_length = counter + 1
                decompressed_data += bytearray(it.islice(iter_data, block_length))

        return decompressed_data

    def print_tiff_raster_graphics(self, *args):
        """Enter TIFF raster graphics compressed mode (extended graphics mode) - ESC . 2

        The following commands are available in TIFF mode (all other codes are ignored):
            Graphics commands:
            <XFER>      Transfer raster graphics data
            <COLR>      Select printing color

            Movement commands:
            <MOVX>      Set relative horizontal position
            <MOVY>      Set relative vertical position

            System level commands:
            <CR>        Carriage return to left-most print position
            <EXIT>      Exit TIFF mode
            <MOVXBYTE>  Set <MOVX> unit to 8 dots
            <MOVXDOT>   Set <MOVX> unit to 1 dot

        In graphics mode only via ESC ( G.
        Here, the band height (vertical dot count) is equal to 1. Thus, all the
        received data bytes are for 1 unique line.

        .. note:: Only binary commands can be used after entering TIFF compressed mode.

        .. warning:: Only one image density should be used, and do not change this
         setting after entering raster graphics mode.

        Doc p182, p223, p314, p333.
        """
        # PS: Here v_dot_count_m is equal to 1 (filtered by the grammar)
        # Because data is sent 1 line at a time
        graphics_mode, v_res, h_res, v_dot_count_m, *_ = args[1].value
        # Convert dpi to inches: 1/180, 1/360 or 1/720 inches, (180, 360 or 720 dpi)
        self.vertical_resolution = v_res / 3600
        self.horizontal_resolution = h_res / 3600

        if LOGGER.level == DEBUG:
            LOGGER.debug(
                "vertical x horizontal resolution: %s/360 x %s/360",
                v_res // 10,
                h_res // 10,
            )
            LOGGER.debug("height x width: %s x <unknown h dots>", v_dot_count_m)
            # LOGGER.debug("microweave_mode: %s", self.microweave_mode)
            LOGGER.debug("line spacing: %s", self.current_line_spacing)
            LOGGER.debug("start coord: %s, %s", self.cursor_x, self.cursor_y)

    def transfer_raster_graphics_data(self, *args):
        """Transfer raster graphics data - <XFER>

        - Does not affect the vertical print position.
        - Horizontal print position is moved to the next dot after this command
          is received.
        - Todo: Print data that exceeds the right margin is ignored.

        .. note:: TIFF format:
            - Moves raster data to the band buffer of the selected color.
            - Current data does not affect next raster data.
        """
        data = self.decompress_rle_data(args[1].value)
        # Do not chunk the data: all bytes are printed in the same line of 1 dot
        # (v_dot_count_m should be equal to 1)
        self.bytes_per_line = len(data)
        LOGGER.debug("expect %s bytes", self.bytes_per_line)
        self.print_raster_graphics_dots(data)

    def set_relative_horizontal_position(self, *args):
        """Set relative horizontal position - <MOVX>

        - The new horizontal position = current position + (parameter) × <MOVX> unit.
        <MOVX> unit is set by the <MOVXDOT> or <MOVXBYTE> command.
        - If #BC has a negative value, it is described with two’s complement.
        - The unit for this command is determined by the ESC ( U set unit command.

        Todo: Settings that exceed the right or left margin will be ignored.

        .. note:: For MOVX/MOVY: 0, 1, or 2 bytes are expected (nL and nH are optional...)
        """
        dot_offset = args[1].value
        self.cursor_x += dot_offset * self.movx_unit

    def set_relative_vertical_position(self, *args):
        """Move relative vertical position by dot - <MOVY>

        - Move the horizontal print position to 0 (left-most print position).
        Positive value only is allowed. The print position cannot be moved in a
        negative direction (up).
        - The unit for this command is determined by the ESC ( U set unit command .

        Todo: - After the vertical print position is moved, all seed row(s) are
            copied to the band buffer.
            - Settings beyond 22 inches are ignored.

        .. note:: For MOVX/MOVY: 0, 1, or 2 bytes are expected (nL and nH are optional...)
        """
        dot_offset = args[1].value

        self._carriage_return()

        unit = self.defined_unit if self.defined_unit else 1 / 360
        self.cursor_y -= dot_offset * unit

    def set_movx_unit_8dots(self, *_):
        """Set the increment of <MOVX> unit to 8 - <MOVXBYTE>

        - Move the horizontal print position to 0 (left-most print position).
        - Do not move the vertical print position.
        - The unit for this command is determined by the ESC ( U set unit command.

        Todo: Start printing of stored data.

        .. seealso:: :meth:`set_movx_unit`
        """
        self._carriage_return()
        self.set_movx_unit(8)

    def set_movx_unit_1dot(self, *_):
        """Set the increment of <MOVX> unit to 1 - <MOVXDOT>

        - Move the horizontal print position to 0 (left-most print position).
        - Do not move the vertical print position.
        - The unit for this command is determined by the ESC ( U set unit command.

        Todo: Start printing of stored data.

        .. seealso:: :meth:`set_movx_unit`
        """
        self._carriage_return()
        self.set_movx_unit(1)

    def set_movx_unit(self, dot_unit):
        """Set the increment of <MOVX> unit - wrapper for <MOVXDOT> & <MOVXBYTE>

        .. seealso:: :meth:`set_movx_unit_8dots` & :meth:`set_movx_unit_1dot`

        .. warning:: This command is/must be sent immediately after entering raster
            graphics mode.
            THUS, we can use the ESC ( U setting here (and not in the MOVX command),
            since it can't be changed in the meantime (the command is not allowed).
        """
        unit = self.defined_unit if self.defined_unit else 1 / 360
        self.movx_unit = dot_unit * unit

    def set_printing_color_ex(self, *args):
        """Select printing color - <COLR>

        1000 0000B  0x80    Black
        1000 0001B  0x80    Magenta
        1000 0010B  0x82    Cyan
        1000 0100B  0x84    Yellow

        Todo: (TIFF format):  Select the band buffer color.

        - Move the horizontal print position to 0 (left-most print position).
        - Parameters other than those listed above are ignored.
        - Combinations of colors are not available and will be ignored.
        """
        self.color = args[0].value[0] & 0x0f
        self._carriage_return()

    def exit_tiff_raster_graphics(self, *_):
        """Exit TIFF compressed raster graphics mode - <EXIT>

        Todo: Start printing of stored data.

        - Move the horizontal print position to 0 (left-most print position).
        """
        self._carriage_return()

    ## bit image
    def select_bit_image(self, *args):
        """Print dot-graphics in 8, 24, or 48-dot columns - ESC *

        .. tip:: A vertical print density of 360 dpi can be achieved on 24-pin
            printers that feature the ESC + command.
            Advance the paper 1/360 inch (using the ESC + command) and then
            overprint the previous graphics line.

        Original print position: top left corner of the graphics line.

        The printing speed depends on the printing of adjacent horizontal dots;
        by not allowing the printing of adjacent dots, you increase the printing
        speed.

        => If the mode you select does not allow adjacent dot printing,
        the printer ignores the second of two consecutive horizontal dots.
        Double speed is enabled for the following dot densities: 2, 3, 40, 72.

        .. note:: dot_density_m has the same meaning in ESC ? command,
            see :meth:`reassign_bit_image_mode`.

        doc p184, p298 (full table)
        """
        dot_density_m, nL, nH = args[1].value
        dot_columns_nb = (nH << 8) + nL

        # Configure the bit image printing mode according to the given dot density
        self.configure_bit_image(dot_density_m)

        if LOGGER.level == DEBUG:
            expected_bytes = self.bytes_per_column * dot_columns_nb

            # 8 for 8 dots height
            LOGGER.debug(
                "expect %s bytes (%s dots = %s byte(s) per column)",
                expected_bytes,
                8 * self.bytes_per_column,
                self.bytes_per_column,
            )
            LOGGER.debug("Choosen dot density m: %s", dot_density_m)
            LOGGER.debug("Columns number: %s", dot_columns_nb)
            LOGGER.debug("line spacing: %s", self.current_line_spacing)
            LOGGER.debug("start coord: %s, %s", self.cursor_x, self.cursor_y)

        data = args[2].value
        self.print_bit_image_dots(data)

    def print_bit_image_dots(self, data, extended_dots=False):
        """Print dots in bit image data for 9, 24, 48 pins printers

        Unlike raster printing, bitimage mode prints the bytes received column
        after column, from left to right. Each column is 1 dot large and covers
        multiple lines (8 per byte).

        The final print position is the dot after the far right dot on the top
        row of the graphics printed with this command.
        So, cursor_y is NOT incremented; when the function ends, the print position
        is at top-right (y start, x end).

        .. note:: About the radius of circle dots.
            The circle is inscribed in the square of the pixel it is supposed to
            represent. Thus, the surface on the circle is ~78% of the surface of
            the square. Uncovered white surfaces alter the perception of color
            nuances.
            To compensate this, we increase the diameter of the circle by
            approximately 28% (empirical value vs the theoritical value of
            100-78=22%). The radius is thus obtained as follows:

                max(self.horizontal_resolution, self.vertical_resolution) / 2 \
                * 72 * 1.28

            We use the maximum of the 2 axis resolutions to compensate low
            resolutions used most often for reasons of printing speed and more
            rarely for the purpose of actually leaving empty spaces between dots
            or lines of dots (especially for 9pins printer that are limited by
            a vertical resolution of 1/72). Circles therefore overlap each other
            and it's a deliberate choice.

        :param data: Bytes of graphics data.
        :key extended_dots: Optional, enable support of print heads with 9 pins
            (Default: False).
            For 9pins print heads, only the 1st bit of the 2nd byte of a column
            in a line is used.
        :type data: bytearray | bytes
        :type extended_dots: bool
        """
        if not self.current_pdf:
            return

        # For a function called hundreds of thousands or even millions of times,
        # local variables are preferable as they reduce the indirection level.
        double_speed = self.double_speed
        code = self.current_pdf._code
        horizontal_resolution = self.horizontal_resolution
        vertical_resolution = self.vertical_resolution
        cursor_x = self.cursor_x
        cursor_y = self.cursor_y
        dots = self.dots_as_circles

        def chunk_this(iterable, length):
            """Split iterable in chunks of equal sizes

            .. todo:: Update this with itertools.batched for the 3.12 migration;
                this is twice as fast.
            """
            iterator = iter(iterable)
            for _ in range(0, len(iterable), length):
                yield int.from_bytes(it.islice(iterator, length), "big")

        # Consume all bits of the current value (can be multiple bytes)
        # at each loop the current byte is shifted to the left with an offset of 1.
        # This avoids testing the remaining bits if their value is zero.
        mask = 1 << (self.bytes_per_column * 8 - 1)
        overflow_mask = 2 ** (8 * self.bytes_per_column) - 1
        prev_col_int = 0

        if dots:
            # Circles: Bézier curves are not used in order to avoid heavy
            # memory, CPU & disk overload. Instead, for a point, we use a line with
            # two semicircular arcs around the end points with a diameter equal to
            # the width of the line drawn.
            # We use a stroke directive here.
            # Configure setlinecap: round (1 J)
            # Configure linewidth (w)
            # No noop to end previous path (n) (useless here)
            linewidth = round(
                max(horizontal_resolution, vertical_resolution) * 72 * 1.28, 2
            )
            code.append(f"1 J {linewidth} w")
        else:
            # Rectangles: width and height are the current H/V resolutions.
            # The prefix including the coordinates is added in the loop.
            # We use a fill directive here.
            h_res = "{:.2f}".format(horizontal_resolution * 72).rstrip("0")
            v_res = "{:.2f}".format(vertical_resolution * 72).rstrip("0")
            rect_suffix = f" {h_res} {v_res} re"

        # Iterate on bytes inside columns
        for col_int in chunk_this(data, self.bytes_per_column):
            # if cursor_x >= self.right_margin:
            #     continue

            if double_speed:
                # Clear bits using the previous column as a bitmask
                col_int &= ~prev_col_int
                prev_col_int = col_int

            if extended_dots:
                # For 9pins print heads, only the 1st bit of the 2nd byte is used
                col_int &= 0xff80

            # Do not search further, it IS the most efficient way to
            # round & strip trailing zeroes (to save space).
            cx = "{:.2f}".format(cursor_x * 72).rstrip("0")
            i = 0
            while col_int:
                if col_int & mask:
                    # At each bit, move the local cursor_y down
                    y_pos = cursor_y - i * vertical_resolution
                    cy = "{:.2f}".format(y_pos * 72).rstrip("0")
                    code.append(
                        f"{cx} {cy} m {cx} {cy} l"
                        if dots
                        else (f"{cx} {cy}" + rect_suffix)
                    )
                i += 1
                # Consume the MSB
                col_int = (col_int << 1) & overflow_mask

            # Increment global cursor_x
            cursor_x += horizontal_resolution

        # Close path and stroke or fill
        code.append("S" if dots else "f")

        self.cursor_x = cursor_x

    def configure_bit_image(self, dot_density_m):
        """Configure the bit image printing mode according to the given dot density (internal usage)

        Set the following attributes used in :meth:`print_bit_image_dots`:

            - horizontal_resolution
            - vertical_resolution
            - bytes_per_column
            - double_speed

        doc p298 (full table)

        .. seealso:: :meth:`select_bit_image`, :meth:`select_xdpi_graphics`.

        :param dot_density_m: Dot density used as an entry in horizontal &
            vertical resolutions, and bytes per column tables.
            Adjacent printing (double speed) value is also configured.
        """
        # Get horizontal resolution via a mapping
        self.horizontal_resolution = self.bit_image_horizontal_resolution_mapping[dot_density_m]

        # Get vertical resolution & expected bytes per column (influences the number of dots per column)
        if dot_density_m < 32:
            # For 9 pins, fixed resolution
            self.vertical_resolution = 1 / 72 if self.pins == 9 else 1 / 60
            self.bytes_per_column = 1
        elif dot_density_m < 64:
            # Should not be available to 9 pins printers
            self.vertical_resolution = 1 / 180
            self.bytes_per_column = 3
        else:
            # Values under 73 (included)
            # Should not be available for 9 & 24 pins printers
            self.vertical_resolution = 1 / 360
            self.bytes_per_column = 6

        # Get speed (adjacent dot printing not enabled for the following densities)
        self.double_speed = dot_density_m in (2, 3, 40, 72)

    def reassign_bit_image_mode(self, _, cmd_letter: Token, dot_density_m: Token):
        """Assign the dot density used during the ESC K, L, Y, Z commands to the
        density specified by the same parameter m of the ESC * command - ESC ?

        Allow to redefine default densities for the next calls of the ESC KLYZ commands

        - ESC K is assigned density 0
        - ESC L is assigned density 1
        - ESC Y is assigned density 2
        - ESC Z is assigned density 3

        doc p188

        .. note:: non-recommended command; use the ESC * command

        :param _: ESC byte command
        :param cmd_letter: ESC letter in K,L,Y,Z.
        :param dot_density_m:
            - ESCP2: 0, 1, 2, 3, 4, 6, 32, 33, 38, 39, 40, 71, 72, 73 ;
            - 9 pins: 0, 1, 2, 3, 4, 5, 6, 7.
        """
        dot_density_m = dot_density_m.value[0]

        match cmd_letter.value:
            case b"K":
                # Similar to ESC * 0
                self.klyz_densities[0] = dot_density_m
            case b"L":
                # Similar to ESC * 1
                self.klyz_densities[1] = dot_density_m
            case b"Y":
                # Similar to ESC * 2
                self.klyz_densities[2] = dot_density_m
            case b"Z":
                # Similar to ESC * 3
                self.klyz_densities[3] = dot_density_m

    def select_xdpi_graphics(self, esc, cmd_code, header, data, *_):
        """Print bit-image graphics in 8-dot columns at various densities - ESC K, L, Y, Z

        - ESC K: density of 60 horizontal, p190
        - ESC L: density of 120 horizontal, p192
        - ESC Y: density of 120 horizontal at double speed, p194
        - ESC Z: density of 240 horizontal, p196

        .. seealso:: :meth:`reassign_bit_image_mode`, :meth:`configure_bit_image`,
            :meth:`print_bit_image_dots`.
        """
        nL, nH = header.value
        expected_bytes = (nH << 8) + nL
        cmd_code = cmd_code.value
        data = data.value
        if len(data) != expected_bytes:  # pragma: no cover
            LOGGER.error(
                "expected_bytes not available !!! expect: %s, found: %s",
                expected_bytes, len(data)
            )

        cmd_codes_idx_mapping = {
            b"K": 0,
            b"L": 1,
            b"Y": 2,
            b"Z": 3,
        }

        # Get the corresponding density (potentially modified by ESC ?)
        dot_density_m = self.klyz_densities[cmd_codes_idx_mapping[cmd_code]]
        # Configure & print data
        self.configure_bit_image(dot_density_m)
        self.print_bit_image_dots(data)

    def select_bit_image_9pins(self, *args):
        """Print dot-graphics in 9-dot columns - ESC ^

        - 9-pins only

        Each dot column requires two bytes of data. The first byte represents
        the top 8 dots in the print head.
        Bit 0 (the LSB) in the second byte represents the ninth (bottom) dot in
        the print head; the remaining 7 bits are ignored.

        .. seealso:: :meth:`configure_bit_image`, :meth:`print_bit_image_dots`.

        doc p198

        Todo: Graphics data that would print beyond the right-margin position is ignored.
        """
        dot_density_m, nL, nH = args[1].value
        expected_bytes = (nH << 8) + nL

        data = args[2].value
        if len(data) != expected_bytes:  # pragma: no cover
            LOGGER.error(
                "expected_bytes not available !!! expect: %s, found: %s",
                expected_bytes, len(data)
            )

        self.configure_bit_image(dot_density_m)

        # Enable support of print head with 9 dots per column (2 bytes per column)
        self.bytes_per_column = 2
        self.print_bit_image_dots(data, extended_dots=True)

    def set_printing_color(self, *args):
        """Select the color of printing - ESC r

        Available colors:

            0   Black
            1   Magenta
            2   Cyan
            3   Violet
            4   Yellow
            5   Red
            6   Green

        .. note:: Also available during graphics mode selected with the ESC ( G command.
            In this mode for ESCP2, only Black, Cyan, Magenta, Yellow are available.
            Non-ESCP2 printers can use any color.

        Todo:
            If you change the selected colors after entering raster graphics mode,
            the data buffer will be flushed.

        """
        self.color = args[1].value[0]

    ## barcode
    def barcode(self, esc, header, data, *_):
        """Print bar codes - ESC ( B

        doc p202, p315

        .. note:: About Code128 barcode:
            A kind of Code 128 character sets (A, B or C) is identified by the
            first data of Code 128.
            The first data must be a hexadecimal 41 (A), 42 (B) and 43 (C).

        .. note:: About checksum:
            When Code 128 Character Set C and Interleaved 2 of 5 is selected and
            the number of characters are ODD, “0” is added to the data string.
            => see the keyword `checksum`.

        .. note:: About human-readable characters and Code39:
            Start/stop characters of Code39 are generated automatically by the
            printer, and added to human-readable characters.

        Limitations of bar length:

            45/180 inch ≤ bar length ≤ 22 inch : 24-pin printer
            18/72 inch ≤ bar length ≤ 22 inch  : 9-pin printer

            Long bar length of POSTNET is always 0.125 inch.
            Short bar length of POSTNET is always 0.050 inch.

        .. warning:: UPCE codes are currently NOT supported.

        - Printing position after the printing of a bar code
          returns to the print position before bar code printing.

        Todo: The bar code is not printed when part of the bar code is past
            the right margin.

        PS: It's not a BASIC script & my customers may need it ><.
        """
        barcode_types = {
            0: "EAN13",
            1: "EAN8",
            2: "I2of5",  # "Interleaved 2 of 5",
            3: "UPCA",
            4: "UPCE",  # Not supported
            5: "Standard39",
            6: "Code128",
            7: "POSTNET",
        }
        not_supported_types = (4,)

        (
            nL,
            nH,
            barcode_type_k,
            module_width_m,
            space_adjustment_s,
            v1,
            v2,
            control_flag_c,
        ) = header.value
        expected_bytes = (nH << 8) + nL - 6

        data = data.value
        if len(data) != expected_bytes:  # pragma: no cover
            LOGGER.error(
                "expected_bytes not available !!! expect: %s, found: %s",
                expected_bytes, len(data)
            )

        if barcode_type_k in not_supported_types:
            LOGGER.error("Barcode type %s is NOT supported (yet)!", barcode_types[barcode_type_k])
            return

        # PS: Bar length is ignored when POSTNET is selected
        unit = 1 / 72 if self.pins == 9 else 1 / 180
        bar_length = ((v2 << 8) + v1) * unit
        # Limit invalid data
        bar_length = min(max(bar_length, 18 / 72 if self.pins == 9 else 45 / 180), 22)

        if barcode_type_k == 7:
            # Limit long bar length of POSTNET codes
            bar_length = 0.125

        # Control flags
        # Printer generates and prints the check digit
        add_check_digit = bool(1 & control_flag_c)
        # Show code text
        human_readable = not 2 & control_flag_c
        # EAN-13 and UPC-A only; left flag center or under the bars
        # Todo: not supported by reportlab ?
        flag_char_under = bool(3 & control_flag_c)

        if LOGGER.level == DEBUG:
            LOGGER.debug("Barcode type: %s", barcode_types[barcode_type_k])
            LOGGER.debug("Barcode height: %s", bar_length)
            LOGGER.debug("Barcode humanreadable: %s", human_readable)
            LOGGER.debug("Barcode flag under: %s", flag_char_under)
            LOGGER.debug("Barcode module width: %s", module_width_m)
            LOGGER.debug("Barcode add_check_digit: %s", add_check_digit)

        import reportlab.graphics.barcode as bc

        color = colors.HexColor(self.RGB_colors[self.color])
        barcode = bc.createBarcodeDrawing(
            barcode_types[barcode_type_k],
            value=data.decode(),
            barHeight=bar_length * 72,
            barStrokeWidth=(module_width_m / 180) * 72,
            humanReadable=human_readable,
            checksum=add_check_digit,
            textColor=color,
            barFillColor=color,
        )
        barcode.drawOn(self.current_pdf, self.cursor_x * 72, self.cursor_y * 72)

    def reset_printer(self, *_):
        """Reset printer configuration

        Should be called at the beginning and at the end of each print job.

        Todo: call it in the constructor to lighten it?

        - does not affect user-defined characters
        """
        self.graphics_mode = False
        self.microweave_mode = False

        # Cancel HMI set_horizontal_motion_index() ESC c command,
        # Cancel multipoint mode,
        # Reset point_size to 10.5 Todo: use default point size instead
        # self.cancel_multipoint_mode()

    def run_esc_instruction(self, tree):
        """Recursive call of methods from the given parse tree

        Todo: do not emit ESC token: avoid to always have it at the first pos of *args

        :param tree: Lark tree of tokens, we use aliases as method names.
        :type tree: <lark.lexer.Tree>
        """
        if tree.data in ("start", "instruction", "tiff_compressed_rule"):
            # Recursive call
            _ = [
                self.run_esc_instruction(child)
                for child in tree.children
                if not isinstance(child, Token)
            ]
        elif tree.data in self.dir:
            # Call the method and send the tokens as arguments
            getattr(self, tree.data)(*tree.children)
        else:
            LOGGER.error("Command not implemented: %s; value: %s", tree, tree.data)

    def run_escp(self, program):
        """Parse the printer data bytestream & build a pdf file

        This function is the entry point of the parser.
        """
        parse_tree = init_parser(program)  # ambiguity='explicit'

        # Parse the tree (Note: The first tree token is Token('RULE', 'start'))
        self.run_esc_instruction(parse_tree)

        # Save the pdf file
        if self.current_pdf:
            self.current_pdf.save()
