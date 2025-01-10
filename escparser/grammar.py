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
"""Grammar definition and pre-parsing of commands with a variable number of bytes"""
# Standard imports
from logging import DEBUG
from itertools import islice
# Custom imports
from lark import *
# Local imports
from escparser.commons import logger


LOGGER = logger()

# TODO : order by Command List by Function p9
esc_grammar = r"""
    start: instruction+

    instruction:  tiff_compressed_rule
        | ANYTHING               -> binary_blob
        | INIT                   -> reset_printer

        # Useless: do not implement
        | ESC "U" BIN_ARG_EX    -> switch_unidirectional_mode
        | ESC "<"               -> set_unidirectional_mode
        | BEL                   -> beeper
        | ESC "9"               -> enable_paperout_detector
        | ESC "8"               -> disable_paperout_detector
        | ESC "s" BIN_ARG_EX    -> switch_low_speed_mode
        # Implemented nethertheless (it's a control code that can be printable)
        | DC1                   -> select_printer
        | DC3                   -> deselect_printer

        # Paper feeding
        | ESC EM /[0124BFR]/    -> control_paper_loading_ejecting
        | CR                    -> carriage_return
        | LF                    -> line_feed
        | FF                    -> form_feed
        | BS                    -> backspace
        | HT                    -> h_tab
        | VT                    -> v_tab
        | ESC "0"               -> set_18_line_spacing
        | ESC "1"               -> set_772_line_spacing
        | ESC "2"               -> unset_18_line_spacing
        | ESC "3" DATA          -> set_n180_line_spacing
        | ESC "+" DATA          -> set_n360_line_spacing
        | ESC "A" /[\x00-\x55]/ -> set_n60_line_spacing
        | ESC "f" BIN_ARG HALF_BYTE_ARG -> h_v_skip

        # Page format
        # TODO: see extended standard with nl = 4
        | ESC "(C\x02\x00" /.{2}/   -> set_page_length_defined_unit
        | ESC "(c\x04\x00" /.{4}/   -> set_page_format
        | ESC "C" HALF_BYTE_ARG     -> set_page_length_lines
        | ESC "C\x00" /[\x01-\x16]/ -> set_page_length_inches
        | ESC "N" HALF_BYTE_ARG     -> set_bottom_margin
        | ESC "O"                   -> cancel_top_bottom_margins
        | ESC "l" BYTE_ARG          -> set_left_margin
        | ESC "Q" BYTE_ARG          -> set_right_margin

        # Print position motion
        | ESC "$" BYTE_ARG HALF_BYTE_ARG            -> set_absolute_horizontal_print_position
        | ESC "\\" BYTE_ARG BYTE_ARG                -> set_relative_horizontal_print_position
        # TODO: see extended standard with nl = 4
        | ESC "(V\x02\x00" BYTE_ARG HALF_BYTE_ARG   -> set_absolute_vertical_print_position
        | ESC "(v\x02\x00" BYTE_ARG BYTE_ARG        -> set_relative_vertical_print_position
        # Variable command but limited by a NUL char
        | ESC "D" /[\x01-\xff]{0,32}\x00/   -> set_horizontal_tabs
        # Variable command but limited by a NUL char
        | ESC "B" /[\x01-\xff]{0,16}\x00/   -> set_vertical_tabs
        # not implemented
        # Variable command but limited by a NUL char
        | ESC "b" /[\x00-\x07][\x01-\xff]{0,16}\x00/ -> set_vertical_tabs_vfu
        # not implemented
        | ESC "/" /[\x00-\x07]/             -> select_vertical_tab_channel
        # not implemented
        | ESC "e" BIN_ARG HALF_BYTE_ARG     -> set_fixed_tab_increment
        # not implemented
        | ESC "a" /[0-3\x00-\x03]/          -> select_justification
        | ESC "J" BYTE_ARG                  -> advance_print_position_vertically
        # not implemented: deleted command
        | ESC "j" BYTE_ARG                  -> reverse_paper_feed
        # not implemented: deleted command
        | ESC "i" BIN_ARG                   -> set_immediate_print_mode


        # Font selection
        # 0-9 10 11 30 31; add 12 (0x0c) for tests purpose
        | ESC "k" /[\x00-\x0c\x1e\x1f]/     -> select_typeface
        | ESC "X" /[\x00\x01\x05-\x7f].{2}/ -> select_font_by_pitch_and_point
        # P: 10cpi, M: 12cpi, g: 15cpi
        | ESC /[PMg]/                       -> select_cpi
        | ESC "p" BIN_ARG_EX                -> switch_proportional_mode
        | ESC "x" BIN_ARG_EX                -> select_letter_quality_or_draft
        | ESC "c" /.[\x00-\x04]/            -> set_horizontal_motion_index

        # Spacing
        | ESC SP HALF_BYTE_ARG              -> set_intercharacter_space
        # 5, 10, 20, 30, 40, 50, 60
        | ESC "(U\x01\x00" /[\x05\x0a\x14\x1e\x28\x32\x3c]/ -> set_unit


        # Font enhancement
        | ESC "!" BYTE_ARG                  -> master_select
        | ESC "4"                           -> set_italic
        | ESC "5"                           -> unset_italic
        | ESC "E"                           -> set_bold
        | ESC "F"                           -> unset_bold
        | ESC "-" BIN_ARG_EX                -> switch_underline
        | SI                                -> select_condensed_printing
        | ESC SI                            -> select_condensed_printing
        | DC2                               -> unset_condensed_printing
        | SO                                -> select_double_width_printing
        | ESC SO                            -> select_double_width_printing
        | DC4                               -> unset_double_width_printing
        | ESC "W" BIN_ARG_EX                -> switch_double_width_printing
        | ESC "w" BIN_ARG_EX                -> switch_double_height_printing
        | ESC "G"                           -> set_double_strike_printing
        | ESC "H"                           -> unset_double_strike_printing
        | ESC "(-\x03\x00\x01" /[\x01-\x03][\x00-\x02\x05-\x06]/ -> select_line_score
        | ESC _SCRIPT BIN_ARG_EX            -> set_script_printing
        | ESC _UNSCRIPT                     -> unset_script_printing
        | ESC "q" /[\x00-\x03]/             -> select_character_style
        # Also available in graphics
        | ESC "r" /[\x00-\x06]/             -> set_printing_color


        # check
        # Not implemented
        # TODO: use save/restore state at each LF to be able to purge buffer ?
        | CAN                               -> cancel_line
        # Not implemented
        | DEL                               -> delete_last_char_in_buffer
        # Not implemented => already processed in libreprinter
        | ESC "#"                           -> cancel_msb_control
        # Not implemented => already processed in libreprinter
        | ESC "="                           -> clear_msb
        # Not implemented => already processed in libreprinter
        | ESC ">"                           -> set_msb


        # Character handling
        | ESC "(t\x03\x00" /[0-3\x00-\x03][\x00-\xff]{2}/ -> assign_character_table
        | ESC "t" /[0-3\x00-\x03]/          -> select_character_table
        # 0-13, 64
        | ESC "R" /[\x00-\x0d\x40]/         -> select_international_charset
        # Variable
        | ESC "&\x00" USER_CHARACTERS_HEADER DATA+ -> define_user_defined_ram_characters
        | ESC ":\x00" HALF_BYTE_ARG NUL     -> copy_rom_to_ram
        | ESC "%" BIN_ARG_EX                -> select_user_defined_set
        # Variable
        | ESC "(^" PRINT_DATA_AS_CHARACTERS_HEADER DATA+ -> print_data_as_characters
        | ESC "6"                           -> set_upper_control_codes_printing
        | ESC "7"                           -> unset_upper_control_codes_printing
        | ESC "I" BIN_ARG                   -> switch_control_codes_printing
        | ESC "m\x00"                       -> set_upper_control_codes_printing
        | ESC "m\x04"                       -> unset_upper_control_codes_printing


        # Graphics
        # Variable
        | ESC "*" SELECT_BIT_IMAGE_HEADER DATA+       -> select_bit_image
        # Variable
        | ESC "^" SELECT_BIT_IMAGE_9PINS_HEADER DATA+ -> select_bit_image_9pins
        # 2nd byte can be: m = 0, 1, 2, 3, 4, 6, 32, 33, 38, 39, 40, 71, 72, 73 ; 0, 1, 2, 3, 4, 5, 6, 7
        | ESC "?" SELECT_XDPI_GRAPHICS_CMD /[\x00\x01\x02\x03\x04\x06\x07\x20\x21\x26\x27\x28\x47\x48\x49]/ -> reassign_bit_image_mode
        | ESC "(G\x01\x00" /[1\x01]/                 -> set_graphics_mode
        | ESC "(i\x01\x00" BIN_ARG_EX                -> switch_microweave_mode
        # Variable
        | ESC "." PRINT_RASTER_GRAPHICS_HEADER DATA+ -> print_raster_graphics
        # Variable
        | ESC SELECT_XDPI_GRAPHICS_CMD SELECT_XDPI_GRAPHICS_HEADER DATA -> select_xdpi_graphics
        # Variable
        # Similar to ESC * 0
        # | ESC "K" SELECT_XDPI_GRAPHICS_HEADER DATA+ -> select_60dpi_graphics
        # Similar to ESC * 1
        # | ESC "L" SELECT_XDPI_GRAPHICS_HEADER DATA+ -> select_120dpi_graphics
        # Similar to ESC * 2
        # | ESC "Y" SELECT_XDPI_GRAPHICS_HEADER DATA+ -> select_120dpi_double_speed_graphics
        # Similar to ESC * 3
        # | ESC "Z" SELECT_XDPI_GRAPHICS_HEADER DATA+ -> select_240dpi_graphics

        # Barcode
        | ESC "(B" BARCODE_HEADER DATA+               -> barcode

    tiff_compressed_rule.2: tiff_enter tiff_instruction* exit_ex
    # Not variable
    tiff_enter: ESC "." PRINT_TIFF_RASTER_GRAPHICS_HEADER -> print_tiff_raster_graphics
    exit_ex.2: EXIT_EX      -> exit_tiff_raster_graphics
    tiff_instruction.2: XFER_HEADER DATA+ -> transfer_raster_graphics_data
        | COLR_EX           -> set_printing_color_ex
        | CR_EX             -> carriage_return
        # Not implemented
        | CLR_EX            -> clear_ex
        | MOVXBYTE_EX       -> set_movx_unit_8dots
        | MOVXDOT_EX        -> set_movx_unit_1dot
        # DATA can be 0,1 or 2 bytes but lark doesn't accept empty (0) terminal,
        # thus we build the DATA token in the grammar between the lexer and the parser
        | MOVX_HEADER DATA+ -> set_relative_horizontal_position
        | MOVY_HEADER DATA+ -> set_relative_vertical_position

    # Everything but ESC
    # TODO exclude control codes
    ANYTHING.-1: /[^\x1b\t\n\r\x08\x09\x0b\x0c\x0e\x0f\x12\x14\x18\x7f]+/

    # For user defined characters handling in ESCP2 mode
    _SCRIPT: "S"
    _UNSCRIPT: "T"

    # ASCII Control codes
    NUL: "\x00"
    SOH: "\x01"
    STX: "\x02"
    ETX: "\x03"
    EOT: "\x04"
    ENQ: "\x05"
    ACK: "\x06"
    BEL: "\x07"
    BS:  "\x08"
    # HT / TAB
    HT:  "\x09"
    LF:  "\x0a"
    VT:  "\x0b"
    FF:  "\x0c"
    CR:  "\x0d"
    SO:  "\x0e"
    SI:  "\x0f"
    DLE: "\x10"
    DC1: "\x11"
    DC2: "\x12"
    DC3: "\x13"
    DC4: "\x14"
    NAK: "\x15"
    SYN: "\x16"
    ETB: "\x17"
    CAN: "\x18"
    EM:  "\x19"
    SUB: "\x1a"
    ESC: "\x1b"
    FS:  "\x1c"
    GS:  "\x1d"
    RS:  "\x1e"
    US:  "\x1f"
    SP:  "\x20"
    DEL: "\x7f"

    INIT: ESC "@"
    SELECT_XDPI_GRAPHICS_CMD: /[KLYZ]/

    # 0 1 2 3 4 5 6 7 32 33 38 39 40 71 72 73 + 64 65 70
    SELECT_BIT_IMAGE_HEADER: /[\x00\x01\x02\x03\x04\x05\x06\x07\x20\x21\x26\x27\x28\x40\x41\x46\x47\x48\x49][\x00-\xff][\x00-\x1f]/
    SELECT_BIT_IMAGE_9PINS_HEADER: /[\x00\x01].[\x00-\x1f]/
    PRINT_DATA_AS_CHARACTERS_HEADER: /.[\x00-\x7f]/
    PRINT_RASTER_GRAPHICS_HEADER: /[\x00\x01][\x05\x0A\x14]{2}[\x01\x08\x18].[\x00-\x1f]/
    PRINT_TIFF_RASTER_GRAPHICS_HEADER: /\x02[\x05\x0A\x14]{2}\x01\x00\x00/
    SELECT_XDPI_GRAPHICS_HEADER: /.[\x00-\x1f]/
    BARCODE_HEADER: /.[\x00-\x1f][\x00-\x07][\x02-\x05]..[\x00-\x1f]./

    USER_CHARACTERS_HEADER: /[\x00-\x7f]{2}/

    #0b00100000-0b00101111
    #0b00110001,0b00110010
    XFER_HEADER: /([\x20-\x2f]|[\x31\x32])/
    MOVY_HEADER: /([\x60-\x6f]|[\x71\x72])/
    MOVX_HEADER: /([\x40-\x4f]|[\x51\x52])/
    # 0b1000_0000-0b1000_0100
    COLR_EX: /[\x80-\x84]/
    # TODO: new command : CLR 1110 0001
    CLR_EX: "\xe1"
    CR_EX: "\xe2"
    EXIT_EX: "\xe3"
    MOVXBYTE_EX: "\xe4"
    MOVXDOT_EX: "\xe5"

    BIN_ARG: /[\x00\x01]/
    BIN_ARG_EX: /[01\x00\x01]/
    HALF_BYTE_ARG: /[\x00-\x7f]/
    BYTE_ARG: /[\x00-\xff]/
    # use [\x00-\xff] instead .
    DATA: /[\x00-\xff]/


    %import common.LETTER
    %import common.INT -> NUMBER
    %import common.ESCAPED_STRING   -> STRING
"""

def decompress_rle_data(iter_data, expected_decompressed_bytes) -> tuple[bytearray, int]:
    """Decompress the given data bytes (TIFF decompression)

    During compressed mode, the first byte of data must be a counter.
    If the counter is positive, it is treated as a data-length counter.
    If the counter is negative (as determined by two’s complement),
    it is treated as a repeat counter.

    In the first case, the printer read as is the number of bytes specified.
    In the last case, the printer repeats the following byte of data the
    specified number of times.

    :param iter_data: Iterator over the data stream.
    :param expected_decompressed_bytes: The number of bytes that should be
        decompressed. Iterating on iter_data stops when this number is reached.
    :type iter_data: Iterator[bytearray]
    :type expected_decompressed_bytes: int
    :return: Tuple of decompressed data, and number of bytes read.
    """
    decompressed_data = bytearray()
    bytes_read = 0
    for counter in iter_data:
        if counter & 0x80:
            # Repeat counters: number of times to repeat data
            repeat = 256 - counter + 1
            decompressed_data += (next(iter_data)).to_bytes(1) * repeat
            bytes_read += 1
        else:
            # Data-length counters: number of data bytes to follow
            block_length = counter + 1
            decompressed_data += bytearray(islice(iter_data, block_length))
            bytes_read += block_length

        bytes_read += 1

        if len(decompressed_data) >= expected_decompressed_bytes:
            # We have all the data we needed
            break

    return decompressed_data, bytes_read

def parse_from_stream(parser, code, start=None, *args, **kwargs):
    """Parse interatively the given ESC code and build DATA tokens for commands
    that expect a variable (not predicted) number of bytes.


    Uses the interactive parser interface, as well as implementation details
    of the LexerState objects.

    :param parser: A Lark instance
    :param code: ESC code to be parsed
    :type parser: lark.lark.Lark
    :type code: bytearray
    :return: Lark tree.
    :rtype: lark.tree.Tree
    """
    interactive = parser.parse_interactive(code, start)
    data_token_flag = False  # Used to trigger DATA token build
    expected_bytes = 0
    scripting_status = None
    while True:
        try:
            token = next(interactive.lexer_thread.lex(interactive.parser_state))
        except StopIteration:
            break
        else:
            # print(token.type, token.value)

            if token.type in ("SELECT_BIT_IMAGE_HEADER", "SELECT_BIT_IMAGE_9PINS_HEADER"):
                dot_density_m, nL, nH = token.value
                dot_columns_nb = (nH << 8) + nL

                if dot_density_m < 32:
                    bytes_per_column = 1
                elif dot_density_m < 64:
                    bytes_per_column = 3
                else:
                    bytes_per_column = 6

                expected_bytes = bytes_per_column * dot_columns_nb

                LOGGER.debug("Expect %d bytes (%d dots per column)", expected_bytes, 8 * bytes_per_column)
                data_token_flag = True

            if token.type in ("PRINT_DATA_AS_CHARACTERS_HEADER", "SELECT_XDPI_GRAPHICS_HEADER"):
                nL, nH = token.value
                expected_bytes = (nH << 8) + nL
                data_token_flag = True

            elif token.type == "PRINT_RASTER_GRAPHICS_HEADER":
                # b"\x01\x14\x14\x18\xa0\x01"
                graphics_mode, v_res, h_res, v_dot_count_m, nL, nH = token.value
                h_dot_count = (nH << 8) + nL
                expected_decompressed_bytes = v_dot_count_m * int((h_dot_count +7) / 8)
                # print(f"Expect {expected_decompressed_bytes} bytes")
                if graphics_mode == 1:
                    # RLE/TIFF compression
                    token_start_pos = interactive.lexer_thread.state.line_ctr.char_pos
                    iter_data = iter(interactive.lexer_thread.state.text[token_start_pos:])
                    data, expected_bytes = decompress_rle_data(iter_data, expected_decompressed_bytes)
                    # print(data, "ret expected", expected_bytes, "curr", len(data))
                else:
                    # No compression
                    expected_bytes = expected_decompressed_bytes

                LOGGER.debug("Expect %d bytes", expected_bytes)
                data_token_flag = True

            elif token.type == "BARCODE_HEADER":
                nL, nH, *_ = token.value
                expected_bytes = (nH << 8) + nL - 6

                LOGGER.debug("Expect %d bytes", expected_bytes)
                data_token_flag = True

            elif token.type == "XFER_HEADER":
                cmd = token.value[0]
                cmd_bc = cmd & 0x0f
                lexer_state = interactive.lexer_thread.state

                token_start_pos = lexer_state.line_ctr.char_pos
                if not (cmd >> 4) & 1:
                    # #BC = number of raster image data
                    expected_decompressed_bytes = cmd_bc
                elif cmd_bc == 1:
                    # F = 1 then #BC = number of next bytes to read
                    # #BC = 1: number of raster data = n1
                    nL = lexer_state.text[token_start_pos]
                    expected_decompressed_bytes = nL

                    token_start_pos += 1
                elif cmd_bc == 2:
                    # F = 1 then #BC = number of next bytes to read
                    # #BC = 2: number of raster data = n1 + n2 × 256
                    # Get the next bytes as nL and nH
                    nL = lexer_state.text[token_start_pos]
                    nH = lexer_state.text[token_start_pos+1]
                    expected_decompressed_bytes = (nH << 8) + nL

                    token_start_pos += 2
                else:  # pragma: no cover
                    raise ValueError("<XFER> F or BC (nibble) value not expected!")

                LOGGER.debug("Expect %d decompressed bytes", expected_decompressed_bytes)
                data_token_flag = True

                lexer_state.line_ctr.char_pos = token_start_pos
                iter_data = iter(lexer_state.text[token_start_pos:])
                data, expected_bytes = decompress_rle_data(iter_data, expected_decompressed_bytes)

                # print(lexer_state.text[token_start_pos:])
                # print("used bytes to decomp", expected_bytes)
                # print("result, length", data, len(data))
                # input("pause")

            elif token.type == "MOVY_HEADER":
                lexer_state = interactive.lexer_thread.state
                token_start_pos = lexer_state.line_ctr.char_pos
                iter_data = iter(lexer_state.text[token_start_pos:])

                cmd = token.value[0]
                cmd_bc = cmd & 0x0f
                if not (cmd >> 4) & 1:
                    # #BC = interval of values: 0-15
                    dot_offset = cmd_bc
                elif cmd_bc == 1:
                    # F = 1 then
                    # #BC = 1: nL = interval of values 16-255
                    nL = next(iter_data)
                    dot_offset = nL
                    lexer_state.line_ctr.char_pos += 1
                elif cmd_bc == 2:
                    # F = 1 then
                    # #BC = 2: interval of values = nL + nH × 256
                    nL, nH = next(iter_data), next(iter_data)
                    dot_offset = (nH << 8) + nL
                    lexer_state.line_ctr.char_pos += 2
                else:  # pragma: no cover
                    raise ValueError("<MOVY> F or BC (nibble) value not expected!")

                # print("MOVY dot_offset:", dot_offset)

                # Feed the token now!
                interactive.feed_token(token)
                # Build a DATA token with the FINAL built value
                token = Token("DATA", dot_offset)

            elif token.type == "MOVX_HEADER":
                lexer_state = interactive.lexer_thread.state
                token_start_pos = lexer_state.line_ctr.char_pos
                iter_data = iter(lexer_state.text[token_start_pos:])

                cmd = token.value[0]
                # Here we get signed values
                cmd_bc = cmd & 0x0f
                if not (cmd >> 4) & 1:
                    #BC = parameter where –8 ≤ #BC ≤ 7
                    dot_offset = cmd_bc - 2**4 if cmd_bc & 0x08 else cmd_bc
                elif cmd_bc == 1:
                    # F = 1 then #BC = 1: number of next bytes to read
                    # nL (–128 ~ 127)
                    nL = next(iter_data)
                    dot_offset = nL - 2**8 if nL & 0x80 else nL
                    lexer_state.line_ctr.char_pos += 1
                elif cmd_bc == 2:
                    # F = 1 then #BC = 2: number of next bytes to read
                    # nL, nH (–32768 ~ 32767)
                    nL, nH = next(iter_data), next(iter_data)
                    dot_offset = (nH << 8) + nL
                    if dot_offset & 0x8000:
                        dot_offset -= 2**16
                    lexer_state.line_ctr.char_pos += 2
                else:  # pragma: no cover
                    raise ValueError("<MOVX> F or BC (nibble) value not expected!")

                # print("MOVX dot_offset:", dot_offset)

                # Feed the token now!
                interactive.feed_token(token)
                # Build a DATA token with the FINAL built value
                token = Token("DATA", dot_offset)

            elif token.type == "USER_CHARACTERS_HEADER":
                first_char_code_n, last_char_code_m = token.value

                lexer_state = interactive.lexer_thread.state
                token_start_pos = lexer_state.line_ctr.char_pos

                expected_char_nb = last_char_code_m - first_char_code_n + 1
                LOGGER.debug("Expected char nb %d", expected_char_nb)

                # For ESCP2 printers
                nb_space_bytes = 3
                # Number of bytes in a column
                # Normal characters: 24/48 and 9 pins NLQ
                # k = 3 × a1
                # Super/subscript characters: 24/48 (not possible for 9 pins)
                # k = 2 × a1
                # Draft 9 pins characters:
                # k = a1
                column_bytes_size = 2 if scripting_status else 3

                # expected_bytes = 0
                # while expected_char_nb:
                #     char_width_a1 = lexer_state.text[token_start_pos+expected_bytes+1]
                #
                #     char_expected_bytes = column_bytes_size * char_width_a1
                #     expected_bytes += char_expected_bytes + nb_space_bytes
                #
                #     expected_char_nb -= 1
                #
                # data_token_flag = True
                # LOGGER.debug("Total expect %d bytes", expected_bytes)

                expected_bytes = 0
                iter_data = iter(lexer_state.text[token_start_pos:])
                while expected_char_nb:
                    interactive.feed_token(token)
                    space_left_a0, char_width_a1, space_right_a2 = islice(iter_data, 0, 3)

                    char_expected_bytes = column_bytes_size * char_width_a1
                    expected_bytes += char_expected_bytes + nb_space_bytes

                    expected_char_nb -= 1

                    char_data = bytes(islice(iter_data, 0, char_expected_bytes))

                    token = Token("DATA", (
                        (space_left_a0, char_width_a1, space_right_a2),
                        char_data
                        )
                    )
                    LOGGER.debug("Expect %d bytes", char_expected_bytes)
                lexer_state.line_ctr.char_pos += expected_bytes

            elif token.type in ("_SCRIPT", "_UNSCRIPT"):
                # Follow the script status to handle user defined characters
                # variable data size (ESCP2)
                scripting_status = token.type == "_SCRIPT"

            if data_token_flag:
                # For commands with variable size.
                # We need to accept the current token and build a DATA token.
                # The limits of the DATA token are built in previous conditions.
                interactive.feed_token(token)
                rewind_offset = -expected_bytes

                lexer_state = interactive.lexer_thread.state
                token_start_pos = lexer_state.line_ctr.char_pos
                token_end_pos = token_start_pos + expected_bytes
                # print(lexer_state.text, token_start_pos, token_end_pos)

                # Build the new token
                # NOTE: DO NOT DO THIS, internal value will not be modified !!!
                # token.value = ...
                value = lexer_state.text[token_start_pos:token_end_pos]
                token = Token("DATA", value)

                # Not mandatory but useful for debugging
                token.start_pos = token_start_pos
                token.end_pos = token_end_pos

                # Repositioning the lexer head for the next tokens
                lexer_state.line_ctr.char_pos -= rewind_offset

                data_token_flag = False

            interactive.feed_token(token)

    tree = interactive.resume_parse()
    if LOGGER.level == DEBUG:
        LOGGER.debug("\n" + tree.pretty())
    return tree

def init_parser(code, *args, **kwargs):
    """Call Lark to parse the given code

    .. note:: All arguments and keyword arguments are sent to Lark and to
        the interactive parser that handles variable size commands.

    :param code: ESC code to be parsed
    :type code: bytearray
    :return: Lark tree.
    :rtype: lark.tree.Tree
    """
    parser = Lark(esc_grammar, parser="lalr", use_bytes=True, **kwargs)

    return parse_from_stream(parser, code, *args, **kwargs)
