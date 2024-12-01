# Standard imports
from pathlib import Path
from enum import Enum
import itertools as it

# Custom imports
from lark import Lark, Token
from PIL import ImageFont
from reportlab.lib import colors
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.pagesizes import A4

# Local imports
from escparser.grammar import esc_grammar, init_parser
from escparser.commons import charset_mapping, international_charsets, character_table_mapping
from escparser.commons import logger

# Debug imports
from pycallgraph import PyCallGraph
from pycallgraph.output import GraphvizOutput
from pycallgraph import Config
from pycallgraph import GlobbingFilter

config = Config(max_depth=10)
config.trace_filter = GlobbingFilter(include=[
    "escparser.*",
    "reportlab.*",
])


PrintMode = Enum("PrintMode", [("DRAFT", 0), ("LQ", 1)])
PrintScripting = Enum("PrintScripting", [("SUP", 0), ("SUB", 1)])
PrintCharacterStyle = Enum("PrintCharacterStyle", [("OUTLINE", 1), ("SHADOW", 2)])

LOGGER = logger()

class ESCParser:
    """
    https://support2.epson.net/manuals/english/page/epl_5800/ref_g/APCOM_3.HTM
    ESC/P2 mode
    FX mode (FX and LQ commands)

    """

    def __init__(self, code, pins=9, printable_area_margins_mm=None, page_size=A4, single_sheets=True, pdf=True):
        """

        :param code: Binary code to be parsed.
            Expected format: ESC/P, ESC/P2, ESC/P 9 Pins.
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
        :key pdf: Enable pdf generation via reportlab. (default: True).
        :type pins: int | None
        :type printable_area_margins_mm: tuple[int] | None
        :type single_sheets: bool
        :type pdf: bool
        """
        self.mode = PrintMode.LQ
        # Note: There are non-ESCP2 printers that have 24, 48 pins !
        self.pins = pins
        self.current_pdf = None

        # Character enhancements ###############################################
        self.italic = False
        self.bold = False
        self._underline = False
        self.scripting = None  # cf PrintScripting
        self.character_style = None  # cf PrintCharacterStyle
        self.condensed = False
        self.double_strike = False
        self.double_width = False
        self._color = 0  # Black

        self.RGB_colors = [
            "#000000",  # Black
            "#ff00ff",  # Magenta
            "#00ffff",  # Cyan
            "#aa00ff",  # Violet
            "#ffff00",  # Yellow
            "#ff0000",  # Red
            "#00ff00",  # Green
        ]

        # Font rendering #######################################################
        self.point_size = 10.5
        self.character_pitch = 1 / 10  # in inches: 1/10 inch = 10 cpi
        # TODO priorité sur le character_pitch de ESC X, see set_horizontal_motion_index()
        self.character_width = None  # HMI, horizontal motion index
        # Fixed character spacing
        self.proportional_spacing = False
        # Extra space set by ESC SP
        self.extra_intercharacter_space = 0
        # Init tabulations
        self.horizontal_tabulations = None
        self.reset_horizontal_tabulations()
        self.vertical_tabulations = [0] * 16
        # Must be None because functions where it is used have their own default values
        self.defined_unit = None
        self.current_line_spacing = 1 / 6

        if pdf:
            # Init PDF render
            self.current_pdf = Canvas("output.pdf", pagesize=page_size, pageCompression=1)
            self.current_pdf.setFont("Times-Roman", self.point_size)


        # Page configuration ###################################################
        self.page_width = page_size[0] / 72
        self.page_height = page_size[1] / 72
        self.single_sheet_paper = single_sheets

        # Default printable area (restricted with margins into the printing area)
        if not printable_area_margins_mm:
            # TODO: be sure about margins for continuous paper: None ?
            printable_area_margins_mm = (
                (6.35, 6.35, 6.35, 6.35) if self.single_sheet_paper else (9, 9, 3, 3)
            )

        # Convert printable area from mm to inches
        printable_area_margins_inch = tuple(
            [i / 25.4 for i in printable_area_margins_mm]
        )
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

        LOGGER.debug("page size, height, width: %s x %s", self.page_height, self.page_width)
        LOGGER.debug("printable_area_margins_inch: %s", printable_area_margins_inch)
        LOGGER.debug("printable_area (default printing margins positions): %s", self.printable_area)

        # Mechanically usable width
        # Note: Here margins are used because during initialization:
        # printable area = printing area
        # This value will NOT change during printing
        self.printable_area_width = self.right_margin - self.left_margin

        # Page length setting
        #   effective only when you are using continuous paper.
        #   TODO 9 pins + cut-sheets feeder = Single-sheets ESCP2
        if self.single_sheet_paper:
            # Single-sheets ESCP2
            self.page_length = self.top_margin - self.bottom_margin
            # 9 pins & single sheets: physical = logical
            if self.pins == 9:
                self.page_length = self.page_height
        else:
            # Continuous paper ESCP2/ESCP
            self.page_length = self.page_height

        self.character_tables = [
            "Italic",
            "PC437",
            "User-defined characters",
            "PC437",
        ]
        self.typefaces = {
                0: "Roman", # Times New Roman
                1: "Sans serif", # /usr/share/fonts/truetype/freefont/FreeSans*
                2: "Courier",
                3: "Prestige", # https://en.wikipedia.org/wiki/Prestige_Elite
            4: "Script",
                5: "OCR-B",
                6: "OCR-A",
                7: "Orator",
            8: "Orator-S",
                9: "Script C",
                10: "Roman T",
            11: "Sans serif H",
            30: "SV Busaba",
            31: "SV Jittra",
        }
        self.character_table = 1  # PC437 by default
        self.international_charset = 0
        self.typeface = 0  # Roman
        self.copied_font = {}
        self.user_defined_RAM_characters = False
        # scalable fonts possibility
        self.multipoint_mode = False

        # Graphics #############################################################
        self.graphics_mode = False
        self.microweave_mode = False
        # Get horizontal density with dot density value
        self.bit_image_horizontal_resolution_mapping = {
            0:  1/60 ,
            1:  1/120,
            2:  1/120,
            3:  1/240,
            4:  1/80 ,
            5:  1/72 ,
            6:  1/90 ,
            7:  1/144,
            32: 1/60 ,
            33: 1/120,
            38: 1/90 ,
            39: 1/180,
            40: 1/360,
            64: 1/60 ,
            65: 1/120,
            70: 1/90 ,
            71: 1/180,
            72: 1/360,
            73: 1/360,
        }

        # dot_density_m parameter reassigned by ESC ? for bit image related commands
        # (ESC K,L,Y,Z)
        self.KLYZ_densities = [0, 1, 2, 3]

        self.bytes_per_line = 0
        self.bytes_per_column = 0
        self.movx_unit = 1/360

        # Absolute position from the page left edge
        self.cursor_x = 0
        # Absolute position from the page top edge
        self.cursor_y = 0
        self.reset_cursor_x()
        self.reset_cursor_y()

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
        cursor_y = self.cursor_y - 20 / 180

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
        return self._color

    @color.setter
    def color(self, color: int):
        """Get the current color ID"""
        if color >= len(self.RGB_colors):
            # Color doesn't exist: ignore the command
            return

        self._color = color

        if self.current_pdf:
            # Update PDF setting
            self.current_pdf.setFillColor(colors.HexColor(self.RGB_colors[self.color]))

    @property
    def point_size(self) -> float:
        """Get the current font point size (in cpi)"""
        return self._point_size

    @point_size.setter
    def point_size(self, point_size: float):
        self._point_size = point_size

        if self.current_pdf:
            # Redefine the current font (can't just update the point size)
            self.current_pdf.setFont(self.current_pdf._fontname, point_size)

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
        self.carriage_return()

    def set_page_format(self, *args):
        """Measure both top and bottom margins from the top edge of the page. - ESC ( c

        Doc: p 244

        TODO: default:
            continuous paper: no margins
            single-sheet: top-of-form, last printable line
        TODO: ESC/P 2 only
        """
        tL, tH, bL, bH = args[1].value

        # print("settings:", tL, tH, bL, bH)
        unit = self.defined_unit if self.defined_unit else 1 / 360
        top_margin = ((tH << 8) + tL) * unit
        bottom_margin = ((bH << 8) + bL) * unit

        # TODO: check that margins stay within printable area
        # self.top_margin, self.bottom_margin, *_ = self.printable_area

        # Adapt absolute values to bottom-up system, relative to the page size
        # PS: on a 11 inch height paper, 1 inch top margin becomes 10 inch top margin
        # but it's not 11 inch: ~11.69inch, so top margin becomes 10.69 inch
        self.bottom_margin = self.page_height - bottom_margin
        self.top_margin = self.page_height - top_margin

        print("top, bottom:", self.top_margin, self.bottom_margin)
        print("page length:", self.page_length)

        if self.top_margin - self.bottom_margin > self.page_length:
            print("set page_length > current page_length")
            # End of the page length becomes bottom_margin position
            # => actualize page_length
            self.page_length = self.top_margin - self.bottom_margin

        self.reset_cursor_y()

        # assert self.top_margin < self.bottom_margin
        # assert self.bottom_margin <= 22, \
        #     f"Bottom margin must be less than 22 inches ({self.bottom_margin})"
        # Bottom-up
        assert self.top_margin > self.bottom_margin
        assert (
            self.top_margin <= 22
        ), f"Top margin must be less than 22 inches ({self.top_margin})"

    def set_page_length_defined_unit(self, *args):
        """- ESC ( C

        see defined_unit ESC ( U

        cancels the top and bottom-margin settings.
        TODO: ESC/P 2 only
        The maximum page length is 22 inches.
        """
        mL, mH = args[1].value

        unit = self.defined_unit if self.defined_unit else 1 / 360
        self.page_length = ((mH << 8) + mL) * unit
        print("page length:", self.page_length)

        assert (
            0 < self.page_length <= 22
        ), f"(n × (current line spacing)) must be less than 22 inches ({self.page_length})"

        self.cancel_top_bottom_margins()

    def set_page_length_lines(self, *args):
        """Sets the page length to n lines in the current line spacing - ESC C

        cancels the top and bottom margin settings
        TODO:
        Set the page length before paper is loaded or when the print position is at the top-of-
        form position. Otherwise, the current print position becomes the top-of-form position.
        """
        page_length_lines = args[1].value[0]

        assert 1 <= page_length_lines <= 127, page_length_lines
        self.page_length = page_length_lines * self.current_line_spacing
        assert (
            0 < self.page_length <= 22
        ), f"(n × (current line spacing)) must be less than 22 inches ({self.page_length})"

        self.cancel_top_bottom_margins()

    def page_length_inches(self, *args):
        """Sets the page length to n inches - ESC C NUL

        cancels the top and bottom margin settings
        TODO:
        Set the page length before paper is loaded or when the print position is at the top-of-
        form position. Otherwise, the current print position becomes the top-of-form position.
        """
        self.page_length = args[1].value[0]
        print(self.page_length)

        assert (
            1 <= self.page_length <= 22
        ), f"(page_length) must be less than 22 inches ({self.page_length})"

        self.cancel_top_bottom_margins()

    def set_bottom_margin(self, *args):
        """Sets the bottom margin on continuous paper to n lines (in the current line spacing)
        from the top-of-form position on the next page. - ESC N

        Sets a bottom margin x inch (n lines * line spacing) above the next page’s top-of-form position.
        On continuous paper, top-of-form = top edge (physical page top).
        assumes that perforation between pages = top-of-form (0 margins in continuous mode)

        TODO:
        When using continuous paper: move the print position to top-of-form when :
            - FF command is received
            - print position moves below the bottom_margin position

        TODO: default: Either no margin or 1-inch margin, depending on the DIP-switch setting

        ignored when printing on single sheets
        cancels the top-margin setting,  mais pas en 9 pins (top_margin non configurable en 9 pins)
        """
        if self.single_sheet_paper:
            return

        value = args[1].value[0] * self.current_line_spacing

        # Get top-of-form: 1st printable line & reset the top-margin setting to default
        # self.top_margin = self.printable_area[0]
        # Prefer to use page_height because printable area have minimal margins

        # from the top-of-form position of the next page
        # PS: No need to do bottom-up calculations with self.page_height
        self.bottom_margin = value

        print("bottom", self.bottom_margin, "page_length", self.page_length, "(inches)")

        _, printable_bottom, *_ = self.printable_area
        if self.bottom_margin < printable_bottom:
            print(self.bottom_margin, "<", printable_bottom)
            print(
                "bottom margin: outside printablea area (of a non continuous paper) !"
            )

        # In continuous paper, physical page length = logical page length (page_length attribute)
        calculated_page_length = self.page_height - self.bottom_margin
        if calculated_page_length >= self.page_length:
            print(
                "dist top page - bottom margin >= current page_length",
                calculated_page_length,
            )

    def cancel_top_bottom_margins(self, *args):
        """Cancels the top and bottom margin settings

        Return to default settings

        NOTE: do not change the cursors ?
        TODO: actualize page_length ? /!\ ESCP2/continuous
        """
        self.top_margin, self.bottom_margin, *_ = self.printable_area

    def set_right_margin(self, *args):
        """Sets the right margin to n columns in the current character pitch, as measured from the
        left-most printable column - ESC Q

        TODO: Set the right margin at the beginning of a line; the printer ignores any data preceding
            this command on the same line in the buffer.
        TODO: Always set the right margin to be at least one column (at 10 cpi) larger than the left.
        The printer calculates the left margin based on 10 cpi if proportional spacing is selected
        with the ESC p command
        TODO: default: The right-most column
        """
        # from the left-most mechanically printable position, in the current character pitch
        character_pitch = 1 / 10 if self.proportional_spacing else self.character_pitch
        *_, left, _ = self.printable_area
        right_margin = args[1].value[0] * character_pitch + left

        print(
            "left",
            self.left_margin,
            "recv right",
            right_margin,
            "area_width",
            self.printable_area_width,
            "area right limit",
            self.printable_area_width + left,
            "(inches)",
        )
        if not self.left_margin < right_margin <= self.printable_area_width + left:
            print("outside printing area !! => ret")
            return
        self.right_margin = right_margin

    def set_left_margin(self, *args):
        """Sets the left margin to n columns in the current character pitch,
        as measured from the left-most printable column - ESC l

        from the left-most mechanically printable position, in the current character pitch

        TODO: the printer ignores any data preceding this command on the same line in the buffer.
        TODO default: The left-most column (column 1)
            => receive 0 value !!! (debian)

        TODO: Always set the left margin to be at least one column (at 10 cpi) less than the right.

        The printer calculates the left margin based on 10 cpi if proportional spacing is selected
        with the ESC p command
        Moving the left-margin position moves the tab settings by the same distance.
        => see h_tab()

        Defaultf
        The left-most column (column 1)
        """
        # from the left-most mechanically printable position, in the current character pitch
        character_pitch = 1 / 10 if self.proportional_spacing else self.character_pitch
        *_, left, _ = self.printable_area
        left_margin = args[1].value[0] * self.character_pitch + left

        assert 0 <= left_margin < self.right_margin
        self.left_margin = left_margin

        # TODO ESCP2:
        # 80-column printers: 0 ≤ (left margin) ≤ 4.50 inches
        # 110-column printers: 0 ≤ (left margin) ≤ 7.00 inches
        # 136-column printers: 0 ≤ (left margin) ≤ 8.00 inches

        self.reset_cursor_x()

    def set_absolute_horizontal_print_position(self, *args):
        """Moves the horizontal print position to the position specified - ESC $

        default defined unit setting for this command is 1/60 inch
        TODO: fixed On non-ESC/P 2 printers to 1/60
        ignores this command if the specified position is to the right of the right margin.
        """
        nL, nH = args[1].value

        assert 0 <= nH <= 127
        # assert 0 <= nL <= 255

        print(nL, nH)
        value = (nH << 8) + nL
        unit = self.defined_unit if self.defined_unit else 1 / 60  # 1/60: non ESCP2
        cursor_x = value * unit + self.left_margin
        print("set cursor x:", cursor_x)

        if cursor_x > self.right_margin:
            return
        self.cursor_x = cursor_x

    def set_relative_horizontal_print_position(self, *args):
        """Moves the horizontal print position left or right from the current position - ESC \


        Set the defined unit with the ESC ( U command.
        default defined unit for this command is 1/120 inch in draft mode, and 1/180 inch in LQ mode.
        On non-ESC/P 2 printers, the unit of movement is fixed at 1/120 inch in draft mode and
        1/180 inch in LQ mode.

        ignores this command if it would move the print position outside the printing area.
        """
        nL, nH = args[1].value

        # assert 0 <= nH <= 127
        # assert 0 <= nL <= 255

        print(nL, nH)
        value = (nH << 8) + nL

        # Test bit sign
        if nH & 0x80:
            # left movement
            value -= 2**16

        unit = (
            self.defined_unit
            if self.defined_unit
            else (1 / 180 if self.mode == PrintMode.LQ else 1 / 120)
            # TODO: 9-pin printers should be always 1/120 inch
        )
        cursor_x = value * unit + self.cursor_x
        print("set cursor x:", cursor_x)

        if not self.left_margin <= cursor_x < self.right_margin:
            return
        self.cursor_x = cursor_x

    def set_absolute_vertical_print_position(self, *args):
        """Moves the vertical print position to the position specified - ESC ( V

        TODO: ESCP2 only
        default defined unit for this command is 1/360 inch.
        The new position is measured in defined units from the current top-margin position.

        Moving the print position below the bottom-margin
            continuous paper:
                move vertical to top margin of next page
            single-sheet paper:
                eject

        TODO:  ignores this command under the following conditions:
            - [x] move the print position more than 179/360 inch in the negative direction
            - move the print position in the negative direction after a
            graphics command is sent on the current line, or above the point where graphics
            have previously been printed
        NOTE:
            Here, the top values are bigger than the bottom values (0) !
            => signs are inverted !!
        """
        mL, mH = args[1].value
        value = (mH << 8) + mL

        unit = self.defined_unit if self.defined_unit else 1 / 360
        # sign inverted !
        cursor_y = -value * unit + self.top_margin

        if cursor_y < self.bottom_margin or cursor_y > self.top_margin:
            self.next_page()
            return

        movement_amplitude = self.cursor_y - cursor_y
        if movement_amplitude < 0 and -movement_amplitude > 179 / 360:
            print("TOO much !!")
            return

        self.cursor_y = cursor_y

    def set_relative_vertical_print_position(self, *args):
        """Moves the vertical print position up or down from the current position - ESC ( v

        TODO: only on printers featuring ESC/P 2.
        default defined unit for this command is 1/360 inch.
        TODO:  ignores this command under the following conditions:
            - [x] move the print position more than 179/360 inch in the negative direction
            - move the print position in the negative direction after a
            graphics command is sent on the current line, or above the point where graphics
            have previously been printed
            - [x] would move the print position above the top-margin position.
        NOTE:
            doc: positive = down movement, negative = up movement
            Here, the top values are bigger than the bottom values (0) !
            => signs are inverted !!
        """
        mL, mH = args[1].value
        # Test bit sign
        if mH & 0x80:
            # up movement sent
            value -= 2**16

        unit = self.defined_unit if self.defined_unit else 1 / 360
        movement_amplitude = value * unit

        if movement_amplitude < 0 and -movement_amplitude > 179 / 360:
            print("TOO much !!")
            return

        # sign inverted !
        cursor_y = -movement_amplitude + self.cursor_y
        print("set cursor y:", cursor_y)

        if cursor_y < self.bottom_margin or cursor_y > self.top_margin:
            self.next_page()
            return

        self.cursor_y = cursor_y

    def advance_print_position_vertically(self, *args):
        """Advances the vertical print position n/180 inch - ESC J

        TODO: non-ESC/P 2 printers:
            - [x] 9pins: n / 216
            - Prints all data in the line buffer

        => cf end_page_paper_handling() implementation checks
        """
        self.cursor_y += args[1].value[0] / (216 if self.pins == 9 else 180)

        self.end_page_paper_handling()

    def set_unit(self, *args):
        """Sets the unit to m/3600 inch - ESC ( U

        The default unit varies depending on the command and print quality, as follows
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
        TODO: only on printers featuring ESC/P 2
        """
        value = args[1].value[0]

        self.defined_unit = value / 3600

    def set_18_line_spacing(self, *args):
        """Sets the line spacing to 1/8 inch
        default: 1/6
        """
        self.current_line_spacing = 1 / 8

    def unset_18_line_spacing(self, *args):
        """Sets the line spacing to 1/6 inch
        default: 1/6
        """
        self.current_line_spacing = 1 / 6

    def set_n180_line_spacing(self, *args):
        """Sets the line spacing to n/180 inch - ESC 3
        default: 1/6

        9pins: n/216 inch
        """
        value = args[1].value[0]
        coef = 216 if self.pins == 9 else 180
        self.current_line_spacing = value / coef

    def set_n360_line_spacing(self, *args):
        """Sets the line spacing to n/360 inch - ESC +
        default: 1/6

        TODO: available only on 24/48-pin printers.
        """
        value = args[1].value[0]
        self.current_line_spacing = value / 360

    def set_n60_line_spacing(self, *args):
        """Sets the line spacing to n/60 inch - ESC A
        default: 1/6

        9pins: n/72 inch
        """
        value = args[1].value[0]
        self.current_line_spacing = value / (72 if self.pins == 9 else 60)

    def set_772_line_spacing(self, *args):
        """Sets the line spacing to 7/72 inch - ESC 1
        default: 1/6

        TODO: available only on 9-pin printers.
        """
        self.current_line_spacing = 7 / 72

    def h_v_skip(self, *args):
        """Moves the print position depending on the value of m
        m = 0: horizontally
        m = 1: vertically

        Horizontally:
            Underline is performed between the current and final print positions when this
            command is used to move the print position horizontally
            => not interrupted

        Vertically:
            cancels double-width printing selected with the SO or ESC SO command.
        """
        m, n = args[1].value

        if m == 0:
            # horizontally
            text = b" " * n
            # using this function should allow the perform of an eventual character scoring
            self.binary_blob(Token("ANYTHING", text))
        elif m == 1:
            # vertically
            [self.line_feed() for _ in range(n)]
            self.carriage_return()
            self.double_width = False
        else:
            raise ValueError

    def backspace(self, *args):
        """Moves the print position to the left a distance equal to one character in the current character
        pitch plus any additional intercharacter space. - BS

        ignores this command if it would move the print position to the left of the left margin.
        """
        cursor_x = self.cursor_x - (self.character_pitch + self.extra_intercharacter_space)

        if cursor_x < self.left_margin:
            return
        self.cursor_x = cursor_x

    def binary_blob(self, arg):
        """
        a point equals 1/72 of an inch

        The baseline for printing characters on the first line
        is 20/180 inch below the top-margin position.
        on 9-pin printers, 7/72 inch below the print position.

        The baseline of the character is printed 20/180 inch
        (7/72 inch for 9-pin printers) below the vertical print
        position;
        NOTE: the x/180 offset if for characters only, not graphics !

        NOTE: horizontal move: according to the pitch you select (or the width of each character if you
            select proportional spacing).

        TODO: Graphics printing:
            The print position is the top printable row of dots.
        """
        value = arg.value
        print(value.decode())

        baseline_offset = 7 / 72 if self.pins == 9 else 20 / 180
        cursor_y = self.cursor_y - baseline_offset
        point_size = self._point_size

        # map self.current_pdf._fontname to filesystem filename ...
        fontnames_mapping = {
            'Times-Bold': "timesbd",
            'Times-BoldItalic': "timesbi",
            'Times-Italic': "timesi",
            'Times-Roman': "times",
        }
        fontname = fontnames_mapping.get(self.current_pdf._fontname, "times")
        f = ImageFont.truetype(fontname, self.point_size)

        if self.current_pdf:
            text = value.decode()
            if self.scripting:
                rise = point_size * 1/3
                if self.scripting == PrintScripting.SUB:
                    rise *= -1
                if point_size != 8:
                    self.point_size *= 2/3

                f = ImageFont.truetype(fontname, self.point_size)

                textobject = self.current_pdf.beginText()
                textobject.setTextOrigin(self.cursor_x * 72, cursor_y * 72)
                textobject.setRise(rise)
                textobject.textOut(text)
                textobject.setRise(0)
                self.current_pdf.drawText(textobject)
                # Restore previous poitn size
                self.point_size = point_size

            else:

                # col, row in 1/72 inch
                # distance from the left edge, distance from the bottom edge
                # convert inches to pixels/points
                self.current_pdf.drawString(self.cursor_x * 72, cursor_y * 72, text)
                # print(self.current_pdf._code)
                # print("y:", cursor_y, "line spacing:", self.current_line_spacing)



            # !!! use inches: convert pixels to inch
            # print("before x:", self.cursor_x)
            self.cursor_x += f.getlength(text) / 72
            # print("after x:", self.cursor_x)

    def carriage_return(self, *args):
        """Moves the print position to the left-margin position

        TODO:  non-ESC/P 2 printers: The printer prints all data in the line buffer
            after receiving a CR command.
        """
        # Workaround to temporary interrupt underline see also line_feed()
        if self._underline:
            self.underline = False

            self.cursor_x = self.left_margin

            self.underline = True
            return

        self.cursor_x = self.left_margin

    def line_feed(self, *args):
        """Advances the vertical print position one line (in the currently set line spacing) - LF
        Moves the horizontal print position to the left-margin position
        cancels one-line double-width printing selected with the SO or ESC SO commands.

            continuous paper:
                test if cursor_y below bottom_margin: top-of-form/top printable (!!) next page
                => confusion in doc, follow p294 directives (ESC J & LF behave together)
            single-sheet paper:
                test if cursor_y below bottom_margin
                or beyond the end of the printable area
                the printer ejects the paper.

        TODO:  non-ESC/P 2 printers:
            Prints all data in the line buffer

        doc p34
        doc p294

        => cf end_page_paper_handling() implementation checks
        """
        self.double_width = False

        # Workaround to temporary interrupt underline: see also carriage_return()
        underline = self._underline
        if underline:
            self.underline = False

        self.carriage_return()
        self.cursor_y -= self.current_line_spacing

        if underline:
            self.underline = True

        print()

        self.end_page_paper_handling()

    def end_page_paper_handling(self):
        """for ESC J & LF tear downs
        p34
        p294

        ESCP2 + ESC/P:
            => continuous and pos < bottom margin => top margin (!!!) next page
            => single-sheet: ejects

        9 pins
            If the ESC J command moves the print position on continuous paper below the bottom-
            margin position set with the ESC N command, the printer advances to the top-of-form
            position on the next page.
            => continuous and pos < bottom margin => top printable next page

            If ESC J moves the print position on single-sheet paper below the end of the printable
            area, the printer ejects the paper (if loaded by cut-sheet feeder) or ejects paper and then
            feeds next sheet remaining distance (if loaded manually).
            => single-sheet + cut-sheet feeder and below bottom printable => ejects
            => single-sheet + loaded manually and below bottom printable
                => ejects + report remaining distance on next sheet (TODO)
        """
        # ESCP & 9 pins (TODO: distingo)
        printable_bottom_margin = self.printable_area[1]
        if self.pins == 9 and self.single_sheet_paper:
            if self.cursor_y < printable_bottom_margin:
                # ejects the paper
                print("outside printable area")
                self.next_page()
                # TODO: if loaded manually: report the remaining distance on the new page
                return
            return

        if self.cursor_y < self.bottom_margin:
            self.next_page()
            # ESCP/9 pins
            # TODO: if continuous: Go to the top-of-form, not the top_margin
            return

    def form_feed(self, *args):
        """Advances the vertical print position on continuous paper to the top-margin position of
        the next page - FF

        NOTE: Complete each page with a FF command. Also send a FF command at the end
        of each print job.

        TODO: Ejects single-sheet paper
        Moves the horizontal print position to the left-margin position
        TODO: Prints all data in the buffer
        """
        self.double_width = False
        self.next_page()

    def next_page(self):
        print("NEXT PAGE!!! at y offset", self.cursor_y)
        # input("pause")
        # raise Exception
        self.reset_cursor_y()
        self.carriage_return()

        if self.current_pdf:
            # stop drawing on the current page and any further
            # operations will draw on a subsequent page
            self.current_pdf.showPage()

    def h_tab(self, *args):
        """Moves the horizontal print position to the next tab to the right of the current print position - HT
        => adds a tabulation

        ignores this command if no tab is set to the right of the current position
        or if the next tab is to the right of the right margin.

        TODO:
            Character scoring (underline, overscore, and strikethrough) is not printed between the
            current print position and the next tab when this command is sent.
            => temp disable
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
        except StopIteration:
            tab_pos = None

        print("choosen tab:", tab_pos)
        if not tab_pos:
            print("No more tab available")
            return

        if tab_pos > self.right_margin:
            return

        self.cursor_x = tab_pos

    def v_tab(self, *args):
        """Moves the vertical print position to the next vertical tab below the current print position - VT

        Moves the horizontal print position to the left-margin position
        TODO: see doc p52

        """
        self.double_width = False

        self.carriage_return()
        raise NotImplementedError

    def reset_horizontal_tabulations(self):
        """Set tabulation widths

        default: 1 tab position every 8 characters (8, 16, 24, 32, ...)
        """
        character_pitch = 1 / 10 if self.proportional_spacing else self.character_pitch
        self.horizontal_tabulations = [8 * i * character_pitch for i in range(1, 33)]

    def set_horizontal_tabs(self, *args):
        """Sets horizontal tab positions (in the current character pitch) at the columns specified by n1
        to nk, as measured from the left-margin position - ESC D

        Default : Every eight characters
            => 1 tab = 8 chars

        The tab settings move to match any movement in the left margin.
            => actualisé à chaque maj de left_margin...
            => cf h_tab()
        The printer does not move the print position to any tabs beyond the right-margin
        position. However, all tab settings are stored in the printer’s memory; if you move the
        right margin, you can access previously ignored tabs.
            => cf h_tab()

        calculates tab positions based on 10 cpi if proportional spacing is selected with the ESC p command.
        clears any previous tab settings.
        A maximum of 32 horizontal tabs can be set.
        Send an ESC D NUL command to cancel all tab settings.

        TODO: one tab is specified in the current character_pitch but what about the
            interspace character like in BS command (see backspace())
        """
        # Limited to 32 tabs by lark
        column_ids = args[1].value

        # Cancel previous tabs
        self.horizontal_tabulations = [0] * 32

        if not column_ids:
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
            print(f"tab set at column {tab_idx}: {self.horizontal_tabulations[tab_idx]}")

    def set_vertical_tabs(self, *args):
        """Sets vertical tab positions (in the current line spacing) at the lines specified by
        n1 to nk, as measured from the top-margin position - ESC B

        TODO:
        On non-ESC/P 2 printers:
            Vertical tabs are measured from the top-of-form position.
            is the same as setting the vertical tabs in VFU channel 0.
        """
        # Limited to 16 tabs by lark
        line_ids = args[1].value

        # Cancel previous tabs
        self.vertical_tabulations = [0] * 16

        if not line_ids:
            # No data: Just cancel all tabs
            return

        prev = line_ids[0]
        for tab_idx, tab_height in enumerate(line_ids):
            if tab_height < prev:
                # a value of n less than the previous n ends tab setting (just like the NUL code).
                break

            self.vertical_tabulations[tab_idx] = tab_height * self.current_line_spacing

            prev = tab_height
            print(f"tab set at line {tab_idx}: {self.vertical_tabulations[tab_idx]}")

    def set_italic(self, *args):
        print("=> italic ON")
        self.italic = True
        self.set_font()

    def unset_italic(self, *args):
        print("=> italic OFF")
        self.italic = False
        self.set_font()

    def set_bold(self, *args):
        print("=> bold ON")
        self.bold = True
        self.set_font()

    def unset_bold(self, *args):
        print("=> bold OFF")
        self.bold = False
        self.set_font()

    def switch_underline(self, *args):
        """Turns on/off printing of a line below all characters and spaces

        TODO: printed with the following characteristics: draft, LQ, bold, or double-strike.
        TODO: not printed across the distance the horizontal print position is moved
            ESC $, ESC \ (when the print position is moved to the left), HT
        TODO: Graphics characters are not underlined.
        """
        # print(args[1])
        value = args[1].value[0]
        match value:
            case 0 | 48:
                print("=> underline OFF")
                self.underline = False
            case 1 | 49:
                print("=> underline ON")
                self.underline = True

    def set_font(self):
        if not self.current_pdf:
            return

        bold = "Bold" if self.bold else ""
        italic = "Italic" if self.italic else ""

        font = f"Times-{bold}{italic}" if bold or italic else "Times-Roman"
        self.current_pdf.setFont(font, self.point_size)

    def assign_character_table(self, *args):
        """Assigns a registered character table to a character table - ESC ( t

        NOTE: Do not assign a registered table to Table 2 if you plan to use it for user-
        defined characters. Once you assign a registered table to Table 2, you must
        reset the printer (with the ESC @ command) before you can use it for user-
        defined characters.

        doc p80

        """
        d1, d2, d3 = args[1].value
        # d1 should be in [0, 1, 2, 3] for ESCP2/ESCP
        # d1 should be in [0, 1] for 9 pins
        selected_table = character_table_mapping[d2, d3]
        # Replace the old table
        self.character_tables[int(d1)] = selected_table

        print(f"Assign {selected_table} to {d1}")

    def select_character_table(self, *args):
        """Selects the character table to be used for printing from among the four character tables 0-3 - ESC t

        doc p

        ESCP2/ESCP:
            0      Italic
            1      PC437
            2      User-defined characters
            3      PC437
        9pins:
            0       Italic
            1       Graphic character table
        """
        value = args[1].value[0]
        match value:
            case 0 | 48:
                self.character_table = 0
            case 1 | 49:
                self.character_table = 1
            case (2 | 50) if self.pins in (24, 48):
                # TODO: On 24/48-pin printers, non-ESC/P 2 printers:
                print(
                    "copies the user-defined characters from positions 0 to 127 to positions 128 to 255"
                )
                raise NotImplementedError
            case (2 | 50):
                # TODO: ESCP2 only (so not only non 9 pins !!)
                self.character_table = 2
                assert (
                    self.user_defined_RAM_characters
                ), "ROM characters should be previously selected"
                # TODO:
                # En fait cette table peut être utilisée pour des caractères non personnalisés
                # mais une fois cela fait, l'utilisation de caractères personnalisés ne peut se faire
                # qu'après un reset ESC @.
            case 3 | 51:
                self.character_table = 3

        print(f"Select character table {self.character_table}")

    def select_international_charset(self, *args):
        """Selects the set of characters printed for specific character codes - ESC R

        Allows to change up to 12 of the characters in the current character table

        TODO: implement char mapping code before printing them
        """
        value = args[1].value[0]
        print(f"Select {charset_mapping[value]}")
        self.international_charset = value

    def select_letter_quality_or_draft(self, *args):
        """Selects either LQ or draft printing

        TODO: ESCP2/ESCP:
        If you select proportional spacing with the ESC p command during draft printing, the
        printer prints an LQ font instead. When you cancel proportional spacing with the ESC p
        command, the printer returns to draft printing.
        """
        value = args[1].value[0]
        match value:
            case 0 | 48:
                print("=> Draft printing")
                self.mode = PrintMode.DRAFT
            case 1 | 49:
                print("=> LQ Letter-quality printing")
                # LQ: ESCP2/ESCP
                # NLQ: 9 pins
                # TODO: Double-strike printing is not possible when NLQ printing is selected
                self.mode = PrintMode.LQ

    def select_typeface(self, *args):
        """Selects the typeface for LQ printing - ESC k

        TODO:
        The printer ignores this command if the user-defined character set is selected.
        => celui de la RAM ou celui de la table ? select_user_defined_set() ?
        - [x] The Roman typeface is selected if the selected typeface is not available.
        If draft mode is selected when this command is sent, the new LQ typeface will be
        selected when the printer returns to LQ printing.
        - Ignored if typeface is not available in multipoint_mode
            During multipoint mode the printer ignores ESC k
            (for ESC k: if typeface not available in scalable/multipoint mode)

        9 pins: only:
            0 Roman
            1 ans serif
        """
        value = args[1].value[0]
        self.typeface = 0 if value not in self.typefaces else value

        print(f"Select typeface: {self.typefaces[value]}")

    def define_user_defined_ram_characters(self, *args):
        """Sets the parameters for user-defined characters and then sends the data for those characters - ESC &

        To copy user-defined characters (that have been created with the ESC & or ESC :
        commands) to the upper half of the character table, send the ESC % 0 command,
        followed by the ESC t 2 command. However, you cannot copy user-defined characters
        using ESC t 2 if you have previously assigned another character table to table 2 using
        the ESC ( t command.

        Send the ESC % 1 command to switch to user-defined characters.
        Use the ESC ( ^ command to print characters between 0 and 32.

        TODO ?
        Defining characters when the following attributes are set results in the user-defined
        characters having those attributes: superscript, subscript, proportional spacing, draft
        mode, and LQ mode.
        !!!! => pour évaluer la taille du paquet il faut garder le statut normal vs super/subscript accessible !!!


        TODO:
        You can only print user-defined characters as 10.5-point characters (or 21-point
        characters when double-height printing is selected). Even if you select a different
        point size with the ESC X command, characters in RAM can only be printed as
        10.5 or 21-point characters.

        ???:
        Do not define continuous horizontal dots on the same row; the printer ignores the
        second of two continuous dots.

        TODO: 9 pins
            NLQ: structure similaire, sauf que a0 et a2 sont NULL, seul a1 est utilisé
            Draft: structure différente !!! a0 et a2 n'existent plus !!!

        Amount of data depends on:
            − The number of dots in the print head (9 or 24/48)
            − The space you specify on the left and right of each character
            − Character spacing (10 cpi, 12 cpi, 15 cpi, or proportional)
            − The size of your characters (normal or super/subscript)
            − The print quality of your characters (draft, LQ, or NLQ mode)
        """
        print(args)
        first_char_code_n, last_char_code_m = args[1].value
        proportional_left_space_a0, width_a1, proportional_right_space_a2 = args[
            2
        ].value
        data = args[3].value

        # For each character in data
        # Normal chars TODO
        expected_bytes = 3 * width_a1
        # Super/subscript chars TODO
        expected_bytes = 2 * width_a1

        raise NotImplementedError

    def copy_ROM_to_RAM(self, *args):
        """Copies the data for the characters between 0 and 126 of the n typeface from ROM to RAM - ESC :

        9 pins: only:
            Copies the data for the characters between 0 and 255 of the Roman or Sans Serif typeface
            Characters from 128 to 255 are copied from the italic character table
            0: Roman
            1: Sans serif
        """
        value = args[1].value[0]

        # Save typeface, international character set, size (super/subscript or normal), and quality (draft/LQ)
        self.copied_font = {
            "typeface": value,
            "int_charset": self.international_charset,
            "size": None,
            "mode": self.mode,
        }

    def select_user_defined_set(self, *args):
        """Switches between normal and user-defined characters

        NOTE/TODO: cf model spec:
            Draft user-defined characters are converted to LQ characters during LQ mode.
        """
        value = args[1].value[0]
        self.user_defined_RAM_characters = value in (1, 49)

        text = (
            "=> User-defined (RAM) characters"
            if self.user_defined_RAM_characters
            else "=> Normal (ROM) characters"
        )
        print(text)

    def select_10cpi(self, *args):
        """Selects 10.5-point, 10-cpi character printing - ESC P

        cancels the HMI set with the ESC c command.
        cancels multipoint mode.
        TODO: If you change the pitch with this command during proportional mode (selected with
        the ESC p command), the change takes effect when the printer exits proportional mode.
        => attr previous character pitch à mettre en places

        TODO: 9 pins: 10-cpi characters only (pas notion point)
        """
        self.character_pitch = 1 / 10
        self.cancel_multipoint_mode()

    def select_12cpi(self, *args):
        """Selects 10.5-point, 12-cpi character printing - ESC M

        cancels the HMI set with the ESC c command.
        cancels multipoint mode.
        TODO: If you change the pitch with this command during proportional mode (selected with
        the ESC p command), the change takes effect when the printer exits proportional mode.

        TODO: 9 pins: Selects 12-cpi character pitch only (pas notion point)
        """
        self.character_pitch = 1 / 12
        self.cancel_multipoint_mode()

    def select_15cpi(self, *args):
        """Selects 10.5-point, 15-cpi character printing - ESC g

        cancels the HMI set with the ESC c command.
        cancels multipoint mode.
        TODO: If you change the pitch with this command during proportional mode (selected with
        the ESC p command), the change takes effect when the printer exits proportional mode.

        TODO: 9 pins: Selects 15-cpi character printing only (pas notion point)
        """
        self.character_pitch = 1 / 15
        self.cancel_multipoint_mode()

    def select_font_by_pitch_and_point(self, *args):
        """Puts the printer in multipoint (scalable font) mode, and selects the pitch and point
        attributes of the font - ESC X

        Pitch:
            m = 0 No change in pitch
            m = 1 Selects proportional spacing
            m ≥ 5 Selects fixed pitch equal to 360/m cpi
        Point size (height):
            1 point equals 1/72 inch
            Only the following point sizes are available:
            8, 10 (10.5), 12, 14, 16, 18, 20 (21), 22, 24, 26, 28, 30, 32

        Default
            Pitch = 10 cpi (m = 36)
            Point = 10.5 (nH = 0, nL = 21)

        TODO: ESC/P 2 only
        TODO: override self.character_pitch mais en scalable font non ?
        TODO:
            Selecting a combination of 15 cpi and 10 or 20-point characters results in 15-cpi ROM
            characters being chosen; the height of these characters is about 2/3 that of normal
            characters. Select the pitch with the ESC C command to obtain normal height 10 or 20-
            point characters at 15 cpi.

        TODO: During multipoint mode the printer ignores the ESC W, ESC w, ESC SP, SI, ESC SI, SO,
            and ESC SO commands.
            + DC2, DC4, ESC k (for ESC k: if typeface not available in scalable/multipoint mode)
            => décorateur ??
        """
        m, nL, nH = args[1].value

        self.multipoint_mode = True

        # Character pitch
        if m == 1:
            # Select proportional spacing
            self.proportional_spacing = True
        elif m:
            # 360/m cpi = m/360 inch
            self.character_pitch = m / 360

        # Point size
        point_size = ((nH << 8) + nL) / 2

        if point_size:
            self.point_size = point_size

    def cancel_multipoint_mode(self):
        """Cancel multipoint mode, returning the printer to 10.5-point
        ESC P, ESC M, ESC g, ESC p, ESC !
        TODO: and ESC @

        Also cancel HMI set_horizontal_motion_index() ESC c c
        """
        # Cancel select_font_by_pitch_and_point() ESC X command
        self.multipoint_mode = False
        self.point_size = 10.5
        # Cancel HMI set_horizontal_motion_index() ESC c command
        self.character_width = None

    def multipoint_mode_ignore(func):
        """Decorator used to ignore the function if the multipoint mode is enabled"""

        def modified_func(self, *args, **kwargs):
            """Returned modified function"""
            if self.multipoint_mode:
                return
            return func(self, *args, **kwargs)

        return modified_func

    def set_horizontal_motion_index(self, *args):
        """Fixes the character width (HMI) - ESC c

        TODO: ESP2 only
        cancels additional character space set with the ESC SP command
        canceled by: ESC P, ESC M, ESC g, ESC SP, ESC p, ESC !, SO, SI, DC2, DC4, ESC W,
            (via cancel_multipoint_mode())
        TODO:     and ESC @

        NOTE:
        Use this command to set the pitch if you want to print normal-height 10 or 20-point
        characters at 15 cpi during multipoint mode. Selecting 15 cpi for 10 or 20-point
        characters with the ESC X command results in characters being printed at 2/3 their
        normal height.
        """
        nL, nH = args[1].value
        value = (nH << 8) + nL
        hmi = value / 360

        assert 0 < value <= 1080
        assert hmi <= 3, "HMI should be less than 3 inches ({hmi})"
        self.character_width = hmi
        # Cancel extra space set_intercharacter_space ESC SP command
        self.extra_intercharacter_space = 0

    def switch_proportional_mode(self, *args):
        """Selects either proportional or fixed character spacing - ESC p

        cancels the HMI set with the ESC c command
        cancels multipoint mode

        If you select proportional spacing with the ESC p command during draft printing, the
        printer prints an LQ font instead. When you cancel proportional spacing with the ESC p
        command, the printer returns to draft printing.
        TODO: quand le mode proportional_spacing est activé par ESC X ou ESC !, le passage au mode LQ est-il activé comme ici ?
            => dans ce cas passer sur un attr property comme underline et bouger ce code

        TODO: 9 pins:
            Condensed mode is not available when proportional spacing is selected.
        """
        self.cancel_multipoint_mode()
        value = args[1].value[0]

        if value in (1, 49):
            # Selects proportional spacing
            self.proportional_spacing = True

            # Force LQ mode if in Draft mode
            self.previous_mode = self.mode
            self.mode = PrintMode.LQ
        else:
            # Returns to current fixed character pitch
            self.proportional_spacing = False
            # Restore previous mode (Draft for example)
            self.mode = self.previous_mode

    @multipoint_mode_ignore
    def set_intercharacter_space(self, *args):
        """Increases the space between characters by n/180 inch in LQ mode and n/120 inch in draft mode - ESC SP

        cancels the HMI (horizontal motion unit) set with the ESC c command.

        TODO: The extra space set with this command doubles during double-width mode.

        9 pins:
            Increases the space between characters by n/120 inch
        """
        value = args[1].value[0]

        coef = 180 if self.mode == PrintMode.LQ and self.pins != 9 else 120
        self.extra_intercharacter_space = value / coef
        # Cancel HMI set_horizontal_motion_index() ESC c command
        self.character_width = None

    def master_select(self, *args):
        """Selects any combination of several font attributes and enhancements by setting or clearing
        the appropriate bit in the n parameter - ESC !

        cancels multipoint mode
        cancels the HMI selected with the ESC c command
        cancels any attributes or enhancements that are not selected


        bitmasks :
            1,  # 12 cpi vs 10 cpi,  ESC M vs ESC P
            2,  # proportional ESC p
            4,  # condensed DC2, SI
            8,  # bold ESC F, ESC E
            16,  # double-strike ESC H, ESC G
            32,  # double-with ESC W
            64,  # italics ESC 5, ESC 4
            128,  # underline ESC -

        """
        value = args[1].value[0]

        self.character_pitch = 1 / 12 if value & 1 else 1 / 10
        # TODO check if self.mode must be used like in switch_proportional_mode()
        self.proportional_spacing = bool(value & 2)
        self.condensed = bool(value & 4)
        self.bold = bool(value & 8)
        self.double_strike = bool(value & 16)
        self.double_width = bool(value & 32)
        self.italic = bool(value & 64)
        self.underline = bool(value & 128)

        # NOTE: do not use if ESC P/M methods are called for character_pitch change
        # (this function is already called by them)
        self.cancel_multipoint_mode()

        self.set_font()

    def set_double_strike_printing(self, *args):
        """Prints each dot twice, with the second slightly below the first, creating bolder characters - ESC G

        TODO:
        9 pins:
            LQ/NLQ mode overrides double-strike printing; double-strike printing resumes when LQ/NLQ mode
            is canceled.
        """
        # TODO cheat
        self.set_bold()

    def unset_double_strike_printing(self, *args):
        """Cancels double-strike printing selected with the ESC G command - ESC H"""
        # TODO cheat
        self.unset_bold()

    def select_line_score(self, *args):
        """Turns on/off scoring of all characters and spaces following this command - ESC ( -

        TODO: ESCP2 only
        TODO: Each type of scoring is independent of other types; any combination of scoring methods
            may be set simultaneously.
        TODO: The position and thickness of scoring depends on the current point size setting.
        TODO: printed with the following characteristics: draft, LQ, bold, or double-strike.
        TODO: not printed across the distance the horizontal print position is moved
            ESC $, ESC \ (when the print position is moved to the left), HT
        TODO: Graphics characters are not underlined.

        TODO: Character scoring (underline, overscore, and strikethrough) is not performed
        between the current and final print positions when the ESC $ command is
        used. Scoring is also not performed if the ESC \ command moves the print
        position in the negative direction.

        Character scoring (underline, overscore, and strikethrough) is not performed
        between the current and final print positions when the HT command is sent.
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

        print(f"Scoring: {scoring_types[scoring_type_d1]}, {scoring_styles[scoring_style_d2]}")
        if scoring_type_d1 == 1:
            # Handle underline
            self.underline = scoring_style_d2 == 1
        else:
            print("NotImplementedError")

    def set_script_printing(self, *args):
        """Prints characters that follow at about 2/3 their normal height - ESC S

        the printing location depends on the value of n

        does not affect graphics characters.
        The underline strikes through the descenders on subscript characters
        ESC T command to cancel super/subscript printing.

        Superscript characters are printed in the upper two-thirds of the normal character
        space; subscript characters are printed in the lower two-thirds.

        TODO:
        The width of super/subscript characters when using proportional spacing differs from
        that of normal characters; see the super/subscript character proportional width table in
        the Appendix.
        9 pins:
             the same as that of normal characters

        When point sizes other than 10 (10.5) and 20 (21) are selected in multipoint mode,
        super/subscript characters are printed at the nearest point size less than or equal to 2/3
        the current size.

        (not 9 pins) at p136 but 9 pins included in final doc p285:
        When 8-point characters are selected, super/subscript characters are also 8-point
        characters.

        FX-850, FX-1050
        Selecting double-height printing overrides super/subscript printing; super/subscript
        printing resumes when double-height printing is canceled.

        """
        value = args[1].value[0]
        self.scripting = PrintScripting.SUB if value in (1, 49) else PrintScripting.SUP
        print("=>", self.scripting)

    def unset_script_printing(self, *args):
        """Cancels super/subscript printing selected by the ESC S command - ESC T"""
        self.scripting = None

    def select_character_style(self, *args):
        """Turns on/off outline and shadow printing

        TODO: only 24/48 pins
        does not affect graphics characters
        """
        value = args[1].value[0]

        character_style = {
            0: "Turn off outline/shadow printing",
            1: "Turn on outline printing",
            2: "Turn on shadow printing",
            3: "Turn on outline and shadow printing",
        }
        # Use PrintCharacterStyle as bit flags
        # TODO: maybe just not use None but 0 instead...
        self.character_style = None if not value else value  # cf PrintCharacterStyle

    @multipoint_mode_ignore
    def select_condensed_printing(self, *args):
        """Enters condensed mode, in which character width is reduced - SI, ESC SI

        ignored if 15-cpi printing has been selected with the ESC g command.
        """
        # Update character pitch
        if self.proportional_spacing:
            self.character_pitch *= 0.5
        elif self.character_pitch == 1 / 10:
            self.character_pitch = 1 / 17.14
        elif self.character_pitch == 1 / 12:
            self.character_pitch = 1 / 20
        elif self.character_pitch == 1 / 15:
            # Ignore due to ESC g action
            return

        self.condensed = True

        # Cancel HMI set_horizontal_motion_index() ESC c command
        self.character_width = None

    @multipoint_mode_ignore
    def unset_condensed_printing(self, *args):
        """Cancels condensed printing selected by the SI or ESC SI commands - DC2

        TODO: ne dit pas si annule le mode sélectionné par ESC ! => pense pas...
        TODO: reset du character_pitch modifié par SI ?
        """
        self.condensed = False

        # Cancel HMI set_horizontal_motion_index() ESC c command
        self.character_width = None

    @multipoint_mode_ignore
    def select_double_width_printing(self, *args):
        """Doubles the width of all characters, spaces, and intercharacter spacing
        (set with the ESC SP command) following this command ON THE SAME LINE. - SO, ESC SO

        canceled when the buffer is full, or the printer receives the following commands:
        LF, FF, VT, DC4, ESC W 0.

        TODO:
        not canceled by the VT command when it functions the same as a CR command.
        TODO: => nuance One/multiple lines !! cf DC4
        TODO:
        non-ESC/P 2 printers:
        also canceled when the printer receives the following commands: CR and
        VT (when it functions the same as a CR command).
        """
        self.double_width = True
        # Cancel HMI set_horizontal_motion_index() ESC c command
        self.character_width = None

    @multipoint_mode_ignore
    def unset_double_width_printing(self, *args):
        """Cancels double-width printing selected by the SO or ESC SO commands - DC4

        TODO: does not cancel double-width printing selected with the ESC W command.
            => nuance One/multiple lines !!
        TODO: ne dit pas si annule le mode sélectionné par ESC ! => pense pas...
        """
        self.double_width = False

        # Cancel HMI set_horizontal_motion_index() ESC c command
        self.character_width = None

    @multipoint_mode_ignore
    def switch_double_width_printing(self, *args):
        """Turns on/off double-width printing of all characters, spaces, and intercharacter spacing
        (set with the ESC SP command) - ESC W
        """
        value = args[1].value[0]
        self.double_width = value in (1, 49)

        text = "=> Double-width ON" if self.double_width else "=> Double-width OFF"
        print(text)
        # Cancel HMI set_horizontal_motion_index() ESC c command
        self.character_width = None

    @multipoint_mode_ignore
    def switch_double_height_printing(self, *args):
        """Turns on/off double-width printing of all characters, spaces, and intercharacter spacing
        (set with the ESC SP command) - ESC w

        TODO:
            The first line of a page is not doubled if ESC w is sent on the first printable line; all
            following lines are printed at double-height.

        TODO: 9 pins:
            Double-height printing overrides super/subscript, condensed, and high-speed draft printing;
            super/subscript, condensed, and high-speed draft printing resume when
            double-height printing is canceled.
        """
        value = args[1].value[0]
        if value in (1, 49):
            print("=> Double-height/point ON")
            self.point_size *= 2
        else:
            print("=> Double-height/point OFF")
            self.point_size /= 2

    def print_data_as_characters(self, *args):
        """Print data as characters - ESC ( ^

        TODO: only ESCP2
        TODO: ignores data if no character is assigned to that character code in the
        currently selected character table.
        """
        nL, nH = args[1].value
        expected_bytes = (nH << 8) + nL

        raise NotImplementedError

    def set_upper_control_codes_printing(self, *args):
        """Codes from 128 to 159 as printable characters instead of control codes - ESC 6

        TODO:
        has no effect when the italic character table is selected; no characters are
        defined for these codes in the italic character table.

        TODO:
        remains in effect even if you change the character table
        """
        raise NotImplementedError

    def control_paper_loading_ejecting(self, *args):
        """Controls feeding of continuous and single-sheet paper - ESC EM

        0   Exits cut-sheet feeder mode; nonrecommended on escp2
        1   Selects loading from bin 1 of the cut-sheet feeder
        2   Selects loading from bin 2 of the cut-sheet feeder
        4   Enters cut-sheet feeder mode; nonrecommended on escp2
        B   Loads paper from the rear tractor
        F   Loads paper from the front tractor
        R   Ejects one sheet of single-sheet paper

        TODO R (ESCP2):
        ejects the currently loaded single-sheet paper without printing data
        from the line buffer; this is not the equivalent of the FF command (which does print
        line-buffer data).
        """
        value = chr(args[1].value[0])

        if self.single_sheet_paper and value == "R":
            self.next_page()

    ## GRAPHIIICSSSss !!! (òÓ,)_\,,/

    def set_graphics_mode(self, *args):
        """Selects graphics mode (allowing you to print raster graphics) - ESC ( G

        TODO: only ESCP2
        TODO: exit by ESC @
        TODO: clears all user-defined characters and tab settings
        TODO: Text printing is not possible => DO NOT MIX text/graphics on the same page
        turns MicroWeave printing off
        TODO: Only available commands:
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

        TODO: You cannot move the print position in a negative direction (up) while in graphics mode.
            Also, the printer ignores commands moving the vertical print position in a negative
            direction if the final position would be above any graphics printed with this command.

        TODO: Graphics printing: The print position is the top printable row of dots.
        """
        self.graphics_mode = True
        self.microweave_mode = False


    def switch_microweave_mode(self, *args):
        """Turns MicroWeave print mode off and on

        TODO:
        only available during raster graphics printing.
        TODO:
        Sending an ESC @ or ESC ( G command turns MicroWeave printing off.
        """
        self.microweave_mode = True

    def print_raster_graphics(self, *args):
        """Print raster graphics - ESC .

        graphics_mode:
            0: full graphics mode
            1: RLE compressed raster graphics mode

        ESCP2 only !!

        p179
        doc p304
        cf examples: p335
        v_dot_count_m: (1, 8, or 24)

        When MicroWeave is selected, the image height m must be set to 1.
        Use only one image density and do not change this setting once in raster graphics mode.

        You can specify the horizontal dot count in 1-dot increments. If the dot count is not a
        multiple of 8, the remaining data in the data byte at the far right of each row is ignored.

        The final print position is the dot after the far right dot on the top row of the graphics
        printed with this command.

        TODO: in graphics mode only via ESC ( G
        TODO: Print data that exceeds the right margin is ignored.
        TODO:
        You cannot move the print position in a negative direction (up) while in graphics mode.
        Also, the printer ignores commands moving the vertical print position in a negative
        direction if the final position would be above any graphics printed with this command.
        """
        graphics_mode, v_res, h_res, v_dot_count_m, nL, nH = args[1].value
        # Convert dpi to inches: 1/180 or 1/360 inches, (180 or 360 dpi)
        self.vertical_resolution = v_res / 3600
        self.horizontal_resolution = h_res / 3600

        h_dot_count = (nH << 8) + nL
        self.bytes_per_line = int((h_dot_count +7) / 8)
        expected_bytes = v_dot_count_m * self.bytes_per_line
        print(f"Expect {expected_bytes} bytes ({h_dot_count} dots = {h_dot_count / 8} byte(s) per column)")

        print(f"vertical x horizontal resolution: {v_res//10}/360 x {h_res // 10}/360")
        print(f"height x width: {v_dot_count_m}x{h_dot_count}")
        print("microweave_mode:", self.microweave_mode)
        print("line spacing:", self.current_line_spacing)

        data = args[2].value

        print("start coord:", self.cursor_x, self.cursor_y)

        if self.microweave_mode or graphics_mode == 2:
            # In these settings, one raster line printed at a time
            assert v_dot_count_m == 1, \
                "To use MicroWeave, the band height (m) in the ESC . command must be set to 1 (one line)"

        # Decompress RLE compressed data
        if graphics_mode == 1:
            data = self.decompress_rle_data(data)

        self.print_raster_graphics_dots(data, h_dot_count)

    def print_raster_graphics_dots(self, data, h_dot_count=None):
        def chunk_this(iterable, length):
            """Split iterable in chunks of equal sizes"""
            iterator = iter(iterable)
            for i in range(0, len(iterable), length):
                yield tuple(it.islice(iterator, length))

        mask = 0x80
        overflow_mask = 0xff
        y_pos = self.cursor_y

        for line_idx, line_bytes in enumerate(chunk_this(data, self.bytes_per_line), 1):
            line_offset = 0
            for col_int in line_bytes:
                i = 0
                while col_int:
                    if col_int & mask:
                        x_pos = self.cursor_x + (line_offset + i) * self.horizontal_resolution
                        # print("offset, i: x,y", line_offset, i, x_pos, y_pos)
                        self.current_pdf.circle(
                            x_pos * 72,
                            y_pos * 72,
                            self.horizontal_resolution * 72,
                            stroke=0,
                            fill=1,
                        )
                    col_int = (col_int << 1) & overflow_mask
                    i += 1
                line_offset += 8

            y_pos -= self.vertical_resolution

        # Through out the last bits of partially used last byte (juste use the number of expected dots)
        # If horizontal expected dot count is not provided (as it is the case when the function
        # is called by <XFER> in tiff compressed mode), just use the y offset.
        # TODO: use v_dot_count_m that is always set, which is 1 in case of tiff
        printed_dots = h_dot_count if h_dot_count else line_offset
        self.cursor_x = printed_dots * self.horizontal_resolution

    def decompress_rle_data(self, compressed_data):
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
                # TODO: next(islice(si, 2, 3))
                [decompressed_data.append(next(iter_data)) for _ in range(block_length)]

        return decompressed_data

    def print_tiff_raster_graphics(self, *args):
        """Enters TIFF raster graphics compressed mode (extended graphics mode) - ESC . 2

        The following commands are availiable in TIFF mode (all other codes are ignored):
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

        in graphics mode only via ESC ( G

        TODO: Only binary commands can be used after entering TIFF compressed mode.

        NOTE: only one image density and do not change this setting after entering raster graphics mode.
        doc p182
            p223
        doc p314
        doc p333
        """
        graphics_mode, v_res, h_res, *_ = args[1].value
        # Convert dpi to inches: 1/180 or 1/360 inches, (180 or 360 dpi)
        self.vertical_resolution = v_res / 3600
        self.horizontal_resolution = h_res / 3600

        print(f"vertical x horizontal resolution: {v_res//10}/360 x {h_res // 10}/360")
        print("microweave_mode:", self.microweave_mode)
        print("line spacing:", self.current_line_spacing)

    def transfer_raster_graphics_data(self, *args):
        """ - XFER
        does not affect the vertical print position.
        Horizontal print position is moved to the next dot after this command is received
        TODO:
        Print data that exceeds the right margin is ignored.

        TODO:
        (TIFF format)
        • Moves raster data to the band buffer of the selected color.
        • Current data does not affect next raster data.
        """
        data = self.decompress_rle_data(args[1].value)
        # print(data)
        # Do not chunk the data: all bytes are printed in the same line
        # see v_dot_count_m == 1
        self.bytes_per_line = len(data)
        self.print_raster_graphics_dots(data)

    def set_relative_horizontal_position(self, *args):
        """Sets relative horizontal position - MOVX

        The new horizontal position = current position + (parameter) × <MOVX> unit.
        <MOVX> unit is set by the <MOVXDOT> or <MOVXBYTE> command.

        If #BC has a negative value, it is described with two’s complement.

        The unit for this command is determined by the ESC ( U set unit command.

        TODO:
        Settings that exceed the right or left margin will be ignored.

        NOTE: MOVX/MOVY: 0, 1, or 2 bytes (nL and nH are optional...)
        """
        dot_offset = args[1].value

        self.cursor_x += dot_offset * self.movx_unit

    def set_relative_vertical_position(self, *args):
        """Moves relative vertical position by dot - MOVY


        Moves the horizontal print position to 0 (left-most print position).
        Positive value only is allowed. The print position cannot be moved in a negative
        direction (up).
        The unit for this command is determined by the ESC ( U set unit command .

        TODO:
        After the vertical print position is moved, all seed row(s) are copied to the band buffer.
        Settings beyond 22 inches are ignored.

        TODO:
        compressMode == 3) _print_seedRows(hPixelWidth, vPixelWidth);

        NOTE: MOVX/MOVY: 0, 1, or 2 bytes (nL and nH are optional...)
        """
        dot_offset = args[1].value

        self.carriage_return()

        unit = self.defined_unit if self.defined_unit else 1/360
        self.cursor_y -= dot_offset * unit

    def set_movx_unit_8dots(self, *args):
        """Sets the increment of <MOVX> unit to 8. - <MOVXBYTE>

        Moves the horizontal print position to 0 (left-most print position).
        Does not move the vertical print position.
        The unit for this command is determined by the ESC ( U set unit command.

        TODO:
        Starts printing of stored data.

        .. seealso:: :meth:`set_movx_unit`
        """
        self.carriage_return()
        self.set_movx_unit(8)

    def set_movx_unit_1dot(self, *args):
        """Sets the increment of <MOVX> unit to 1 - <MOVXDOT>

        Moves the horizontal print position to 0 (left-most print position).
        Does not move the vertical print position.
        The unit for this command is determined by the ESC ( U set unit command.

        TODO:
        Starts printing of stored data.

        .. seealso:: :meth:`set_movx_unit`
        """
        self.carriage_return()
        self.set_movx_unit(1)

    def set_movx_unit(self, dot_unit):
        """Set the increment of <MOVX> unit - wrapper for MOVXDOT & MOVXBYTE

        .. seealso:: :meth:`set_movx_unit_8dots` & :meth:`set_movx_unit_1dot`

        .. warning:: This command is sent immediately after entering raster
            graphics mode.
            THUS, we use the ESC ( U setting here (and not in the MOVX command),
            since it can't be changed in the meantime.
        """
        unit = self.defined_unit if self.defined_unit else 1/360
        self.movx_unit = dot_unit * unit

    def set_printing_color_ex(self, *args):
        """
        1000 0000B  0x80
        Black
        1000 0001B
        Magenta
        1000 0010B
        Cyan
        1000 0100B  0x84
        Yellow

        TODO:
        (TIFF format)
        Selects the band buffer color.

        Moves the horizontal print position to 0 (left-most print position).
        Parameters other than those listed above are ignored.
        Combinations of colors are not available and will be ignored.
        """
        print(args)
        self.color = args[0].value[0] & 0x0f

        self.carriage_return()

    def exit_tiff_raster_graphics(self, *args):
        """Exits TIFF compressed raster graphics mode.


        Moves the horizontal print position to 0 (left-most print position).
        TODO:
        Starts printing of stored data.
        """
        self.carriage_return()

    ## bit image
    def select_bit_image(self, *args):
        """Prints dot-graphics in 8, 24, or 48-dot columns - ESC *

        NOTE:
        A vertical print density of 360 dpi can be achieved on 24-pin printers that feature the ESC +
        command. Advance the paper 1/360 inch (using the ESC + command) and then overprint
        the previous graphics line.

        Positions: the vertical and horizontal print position to the top left corner of the graphics line.

        The printing speed depends on the printing of adjacent horizontal dots;
        by not allowing the printing of adjacent dots, you increase the printing speed.
            => If the mode you select does not allow adjacent dot printing, the printer ignores
            the second of two consecutive horizontal dots as shown below:

            Double speed:
                2, 3, 40, 72

        NOTE: dot_density_m has the same meaning in ESC ? command

        doc p184
        doc p298 (table complète)
        """
        # print(args)
        # print("bytes indexes: start:", args[0].start_pos, "end:", args[2].end_pos)
        dot_density_m, nL, nH = args[1].value
        dot_columns_nb = (nH << 8) + nL

        self.configure_bit_image(dot_density_m)

        expected_bytes = self.bytes_per_column * dot_columns_nb
        # 8 for 8 dots height
        print(f"Expect {expected_bytes} bytes ({8 * self.bytes_per_column} dots = {self.bytes_per_column} byte(s) per column)")
        print(f"Choosen dot density m: {dot_density_m}")
        print(f"Columns number: {dot_columns_nb}")
        print(f"Current line spacing: {self.current_line_spacing}")

        # self.color = 5
        # self.double_speed = True

        data = args[2].value
        # assert len(data) == expected_bytes, "expected_bytes not available !!!"

        self.print_bit_image_dots(data)

    def print_bit_image_dots(self, data, extended_dots=False):
        """Print dots for 9, 24, 48 pins

        NOTE: cursor_y is NOT incremented; when the function ends the print position is at
            top-right (y start, x end).

        :key extended_dots: Optional, enable support of print heads with 9 pins (Default: False).
        :type extended_dots: bool
        """

        # def chunk_this(iterable, length):
        #     """Split iterable in chunks of equal sizes"""
        #     iterator = iter(iterable)
        #     for i in range(0, len(iterable), length):
        #         yield tuple(it.islice(iterator, length))



        # # Iterate on columns
        # prev_col_int = 0
        # for col_bytes in chunk_this(data, self.bytes_per_column):
        #
        #     if self.double_speed:
        #         # Clear bits using the previous column as a bitmask
        #         col_int = int.from_bytes(col_bytes, 'big')
        #         col_int &= ~(prev_col_int)
        #         prev_col_int = col_int
        #         col_bytes = col_int.to_bytes(self.bytes_per_column, byteorder='big')
        #
        #     # Iterate on bytes inside columns
        #     for byte_idx, col_byte in enumerate(col_bytes):
        #     # for col_byte in col_bytes:
        #         # skip if no dots
        #         if col_byte == 0:
        #             continue
        #
        #         # For 9pins print heads, only the 1st bit of the 2nd byte is used
        #         start = 0 if extended_dots and byte_idx else 7
        #
        #         for i in range(start, -1, -1):
        #
        #             # bit not set for this dot
        #             if not col_byte & (1 << i):
        #                 continue
        #
        #             # print("PIX ON byte_idx, bit_idx", byte_idx, i)
        #
        #             # Increment local y
        #             y_pos = self.cursor_y - ((7-i) * self.vertical_resolution)
        #             # print("y", y_pos)
        #             self.current_pdf.circle(
        #                 self.cursor_x * 72,
        #                 y_pos * 72,
        #                 self.horizontal_resolution * 72,
        #                 stroke=0,
        #                 fill=1,
        #             )

        def chunk_this(iterable, length):
            """Split iterable in chunks of equal sizes"""
            iterator = iter(iterable)
            for i in range(0, len(iterable), length):
                yield int.from_bytes(it.islice(iterator, length), "big")

        mask = 1 << (self.bytes_per_column * 8 -1)
        overflow_mask = 2**(8*self.bytes_per_column) -1
        prev_col_int = 0
        for col_int in chunk_this(data, self.bytes_per_column):

            # col_int = int.from_bytes(col_bytes, 'big')

            if self.double_speed:
                # Clear bits using the previous column as a bitmask
                col_int &= ~(prev_col_int)
                prev_col_int = col_int

            if extended_dots:
                # For 9pins print heads, only the 1st bit of the 2nd byte is used
                col_int &= 0xff80

            i = 0
            while col_int:
                if col_int & mask:
                    y_pos = self.cursor_y - i * self.vertical_resolution
                    # print("y", y_pos)
                    self.current_pdf.circle(
                        self.cursor_x * 72,
                        y_pos * 72,
                        self.horizontal_resolution * 72,
                        stroke=0,
                        fill=1,
                    )
                i += 1
                col_int = (col_int << 1) & overflow_mask


            # g = [
            #     self.cursor_y - ((7-i) * self.vertical_resolution)
            #     for byte_idx, col_byte in enumerate(col_bytes)
            #     for i in range(0 if extended_dots and byte_idx else 7, -1, -1)
            #     if col_byte & (1 << i)
            # ]
            # for y_pos in g:
            #     self.current_pdf.circle(
            #         self.cursor_x * 72,
            #         y_pos * 72,
            #         self.horizontal_resolution * 72,
            #         stroke=0,
            #         fill=1,
            #     )

            # Increment global x
            self.cursor_x += self.horizontal_resolution
            # print(self.cursor_x)

    def configure_bit_image(self, dot_density_m):

        # Get horizontal resolution via a mapping
        self.horizontal_resolution = self.bit_image_horizontal_resolution_mapping[dot_density_m]

        # Get vertical resolution & expected bytes per column (influences the number of dots per column)
        if dot_density_m < 32:
            # For 9 pins, fixed resolution
            self.vertical_resolution = 1/72 if self.pins == 9 else 1/60
            self.bytes_per_column = 1
        elif dot_density_m < 64:
            # Should not be available to 9 pins printers
            self.vertical_resolution = 1/180
            self.bytes_per_column = 3
        else:
            # Values under 73 (included)
            # Should not be available for 9 & 24 pins printers
            self.vertical_resolution = 1/360
            self.bytes_per_column = 6

        # Get speed (adjacent dot printing)
        self.double_speed = dot_density_m in (2, 3, 40, 72)

    def reassign_bit_image_mode(self, *args):
        """Assigns the dot density used during the ESC K, ESC L, ESC Y, or ESC Z commands to the
        density specified by parameter m in the ESC * command - ESC ?

        ESC K is assigned density 0
        ESC L is assigned density 1
        ESC Y is assigned density 2
        ESC Z is assigned density 3

        doc p188
        NOTE: nonrecommended command; use the ESC * command
        NOTE: allows to redefine default densities for ESC KLYZ commands
        """
        cmd_letter = chr(args[1].value[0])
        dot_density_m = args[1].value[1]

        match cmd_letter:
            case "K":
                # Similar to ESC * 0
                self.KLYZ_densities[0] = dot_density_m
            case "L":
                # Similar to ESC * 1
                self.KLYZ_densities[1] = dot_density_m
            case "Y":
                # Similar to ESC * 2
                self.KLYZ_densities[2] = dot_density_m
            case "Z":
                # Similar to ESC * 3
                self.KLYZ_densities[3] = dot_density_m

    def select_xdpi_graphics(self, _, cmd_code, header, data, *args):
        """
        Prints bit-image graphics in 8-dot columns, at a density of 60 horizontal - ESC K
        p190
        Prints bit-image graphics in 8-dot columns, at a density of 120 horizontal - ESC L
        p192
        Prints bit-image graphics in 8-dot columns, at a density of 120 horizontal at double speed - ESC Y
        p194
        Prints bit-image graphics in 8-dot columns, at a density of 240 horizontal - ESC Z
        p196

        .. seealso:: :meth:`reassign_bit_image_mode`
        """
        nL, nH = header.value
        expected_bytes = (nH << 8) + nL

        data = data.value
        assert len(data) == expected_bytes, "expected_bytes not available !!!"

        cmd_codes_mapping = {
            b"K": 0,
            b"L": 1,
            b"Y": 2,
            b"Z": 3,
        }

        # Get the corresponding density (potentially modified by ESC ?)
        dot_density_m = self.KLYZ_densities[cmd_codes_mapping[cmd_code.value]]
        self.configure_bit_image(dot_density_m)

        self.print_bit_image_dots(data)

    def select_60_120dpi_9pins_graphics(self, *args):
        """Prints dot-graphics in 9-dot columns - ESC ^

        Each dot column requires two bytes of data. The first byte represents the top 8 dots in the
        print head. Bit 0 (the LSB) in the second byte represents the ninth (bottom) dot in the print
        head; the remaining 7 bits are ignored.

        doc p198

        TODO: Graphics data that would print beyond the right-margin position is ignored.
        """
        dot_density_m, nL, nH = args[1].value
        expected_bytes = (nH << 8) + nL

        data = args[2].value
        assert len(data) == expected_bytes, "expected_bytes not available !!!"

        self.configure_bit_image(dot_density_m)

        # Enable support of print head with 9 dots per column (2 bytes per column)
        self.bytes_per_column = 2
        self.print_bit_image_dots(data, extended_dots=True)

    def set_printing_color(self, *args):
        """Selects the color of printing

            0   Black
            1   Magenta
            2   Cyan
            3   Violet
            4   Yellow
            5   Red
            6   Green

        NOTE: also available during graphics mode selected with the ESC ( G command.
            In this mode for ESCP2, only Black, Cyan, Magenta, Yellow are available.

        TODO:
            If you change the selected colors after entering raster graphics mode, the data
            buffer will be flushed.
        """
        self.color = args[1].value[0]

    ## barcode
    def barcode(self, esc, header, data, *args):
        """Prints bar codes - ESC ( B

        doc p202
        doc p315

        NOTE: Bar code and text data are mixed in a line.

        A kind of Code 128 character sets (A, B or C) is identified by the first data of Code 128.
        The first data must be a hexadecimal 41 (A), 42 (B) and 43 (C).

        When Code 128 Character Set C and Interleaved 2 of 5 is selected and the number of
        characters are ODD, “0” is added to the data string.

        printing position after the printing of a bar code
        returns to the print position before bar code printing.

        The bar code is not printed when part of the bar code is past the right margin.

        Start/stop characters(*) of Code39 are generated automatically by the printer,
        and added to human readable characters.
        """
        barcode_types = {
            0: "EAN13",
            1: "EAN8",
            2: "I2of5", #"Interleaved 2 of 5",
            3: "UPCA",
            4: "UPCE", # Not supported
            5: "Standard39",
            6: "Code128",
            7: "POSTNET",
        }
        not_supported_types = (4, )

        nL, nH, barcode_type_k, module_width_m, space_adjustment_s, v1, v2, control_flag_c = header.value
        expected_bytes = (nH << 8) + nL - 6

        data = data.value
        assert len(data) == expected_bytes, "expected_bytes not available !!!"

        if barcode_type_k in not_supported_types:
            print(f"Barcode type {barcode_types[barcode_type_k]} is NOT supported !")
            return

        # Bar length is ignored when POSTNET is selected.
        unit = 1/72 if self.pins == 9 else 1/180
        bar_length = ((v2 << 8) + v1) * unit
        # Limit invalid data
        bar_length = min(max(bar_length, 18/72 if self.pins == 9 else 45/180), 22)

        if barcode_type_k == 7:
            bar_length = 0.125

        # Control flags
        # Printer generates and prints the check digit
        add_check_digit = bool(1 & control_flag_c)
        # Show code text
        human_readable = not (2 & control_flag_c)
        # EAN-13 and UPC-A only; left flag center or under
        # TODO: not supported by reportlab ?
        flag_char_under = bool(3 & control_flag_c)


        print(f"Barcode type {barcode_types[barcode_type_k]}")
        print(f"Barcode height {bar_length}")
        print(f"Barcode humanreadable {human_readable}")
        print(f"Barcode flag under ? {flag_char_under}")
        print(f"Barcode module width {module_width_m}")
        print(f"Barcode add_check_digit {add_check_digit}")

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
        # barcode.height = bar_length
        barcode.drawOn(self.current_pdf, self.cursor_x * 72, self.cursor_y * 72)

    # raster commands p224
    # doc p330+
    # lire p302 mix text + graphics
    def run_esc_instruction(self, t):
        """
        TODO: do not emit ESC token: avoid to always have it at the first pos of *args
        """
        # print("tok searched", t)
        if t.data in ("instruction", "tiff_compressed_rule"):
            for cmd in t.children:
                if isinstance(cmd, Token):
                    continue
                self.run_esc_instruction(cmd)

        elif t.data in self.dir:
            getattr(self, t.data)(*t.children)
            # print("OK\n")
            return

        else:
            print("\nnot found", t)

            print(t)
            print(t.data)  # , t.children)

    def run_escp(self, program):
        parse_tree = init_parser(program)

        # esc_parser = Lark(esc_grammar, use_bytes=True, parser='lalr')  # ambiguity='explicit'
        # parse_tree = esc_parser.parse(program)
        # exit()
        # print(parse_tree.pretty())
        self.dir = dir(self)

        # with PyCallGraph(output=GraphvizOutput(), config=config):

        for inst in parse_tree.children:
            self.run_esc_instruction(inst)


        if self.current_pdf:
            self.current_pdf.save()


def main():
    # Debian file start
    # TODO: ESC 3 : 1B 33 18 0D: 0D bizarre... voulu ?
    raw_data = """
        1B 40 1B 50  12 1B 78 30   1B 55 30 1B  6C 00 1B 51
        53 1B 32 1B  43 46 1B 4E   00 1B 4F 1B  33 18 0D 1B
        2A 01 A4 03  00 00 7F 00   40 00 40 00  40 00 40 00
        40 00 40 00  40 00 40 00   40 00 40 00  40 00 40 00
        40 00 40 00  40 00 40 00   40 00 40 00  40 00 40 00"""


    code = bytes(bytearray.fromhex(raw_data))

    # print(code)
    escparser = ESCParser(code)


if __name__ == "__main__":
    main()
