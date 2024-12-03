from lark import *
from lark.lexer import Lexer, LexerState, LexerThread

# TODO : order by Command List by Function p9
esc_grammar = r"""
    start: instruction+

    instruction:  tiff_compressed_rule
        | ANYTHING               -> binary_blob
        | INIT                   -> reset_printer
        # | ESC CMD              -> esc_cmd
        # | ESC ARG_CMD BIN_ARG  -> esc_bin_arg
        # | ESC ARG_CMD ARG      -> esc_arg_cmd

        # Useless: do not implement
        | ESC "U" BIN_ARG_EX    -> switch_unidirectional_mode
        | ESC "<"               -> set_unidirectional_mode
        | BEL                   -> beeper
        | ESC "9"               -> enable_paperout_detector
        | ESC "8"               -> disable_paperout_detector
        | ESC "s" BIN_ARG_EX    -> switch_low_speed_mode
        | DC1                   -> select_printer
        | DC3                   -> deselect_printer

        # Paper feeding
        | ESC EM /[0124BFR]/    -> control_paper_loading_ejecting
        | CR                    -> carriage_return
        | LF                    -> line_feed
        | FF                    -> form_feed
        | BS                    -> backspace
        | HT                    -> h_tab
        # not implemented
        | VT                    -> v_tab
        | ESC "0"               -> set_18_line_spacing
        | ESC "1"               -> set_772_line_spacing
        | ESC "2"               -> unset_18_line_spacing
        | ESC "3" DATA          -> set_n180_line_spacing
        | ESC "+" DATA          -> set_n360_line_spacing
        | ESC "A" /[\x00-\x55]/ -> set_n60_line_spacing
        | ESC "f" BIN_ARG HALF_BYTE_ARG -> h_v_skip

        # Page format
        | ESC "(C\x02\x00" /.{2}/ -> set_page_length_defined_unit
        | ESC "(c\x04\x00" /.{4}/ -> set_page_format
        | ESC "C" ARG           -> set_page_length_lines
        | ESC "C" NUL ARG       -> set_page_length_inches
        | ESC "N" HALF_BYTE_ARG -> set_bottom_margin
        | ESC "O"               -> cancel_top_bottom_margins
        | ESC "l" BYTE_ARG      -> set_left_margin
        | ESC "Q" BYTE_ARG      -> set_right_margin

        # Print position motion
        | ESC "$" ARG ARG                   -> set_absolute_horizontal_print_position
        | ESC "\\" ARG ARG                  -> set_relative_horizontal_print_position
        | ESC "(V\x02\x00" ARG ARG          -> set_absolute_vertical_print_position
        | ESC "(v\x02\x00" ARG ARG          -> set_relative_vertical_print_position
        # Variable command but limited by a NUL char
        | ESC "D" /[\x01-\xff]{0,32}\x00/   -> set_horizontal_tabs
        # Variable command but limited by a NUL char
        | ESC "B" /[\x01-\xff]{0,16}\x00/   -> set_vertical_tabs
        # not implemented - k = {1,16} ?
        | ESC "b" /[\x00-\x07][\x01-\xff]{0,16}\x00/ -> set_vertical_tabs_vfu
        # not implemented
        | ESC "/" /[\x00-\x07]/             -> select_vertical_tab_channel
        # not implemented
        | ESC "e" BIN_ARG ARG               -> set_fixed_tab_increment
        # not implemented
        | ESC "a" /[0-3\x00-\x03]/          -> select_justification
        | ESC "J" ARG                       -> advance_print_position_vertically
        # not implemented: deleted command
        | ESC "j" BYTE_ARG                  -> reverse_paper_feed
        # not implemented: deleted command
        | ESC "i" BIN_ARG                   -> set_immediate_print_mode


        # Font selection
        # 0-9 10 11 30 31
        | ESC "k" /[\x00-\x0b\x1e\x1f]/     -> select_typeface
        | ESC "X" /[\x00\x01\x05-\x7f].{2}/ -> select_font_by_pitch_and_point
        # TODO: group these 3 commands
        | ESC "P"                           -> select_10cpi
        | ESC "M"                           -> select_12cpi
        | ESC "g"                           -> select_15cpi
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
        | ESC "S" BIN_ARG_EX                -> set_script_printing
        | ESC "T"                           -> unset_script_printing
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
        | ESC "(t\x03\x00" /[0-3\x00-\x03].{2}/ -> assign_character_table
        | ESC "t" /[0-3\x00-\x03]/          -> select_character_table
        # 0-13, 64
        | ESC "R" /[\x00-\x0d\x40]/         -> select_international_charset
        # not implemented: TODO/ERROR: data can be any bytes including ESC !!!
        # NOTE: Variable size
        # les nb de bytes fixes sont a coder en .{x} mais les tailles dynamiques
        | ESC "&" NUL /[\x00-\x7f]{2}/ /[^\x1b]{3}/ /[^\x1b]+/ -> define_user_defined_ram_characters
        # TODO/ERROR: parsing ???
        # | ESC ":" NUL HALF_BYTE_ARG NUL   -> copy_ROM_to_RAM
        | ESC "%" BIN_ARG_EX                -> select_user_defined_set
        | ESC "6"                           -> set_upper_control_codes_printing
        # Not implemented
        | ESC "7"                           -> unset_upper_control_codes_printing
        | ESC "(^" PRINT_DATA_AS_CHARACTERS_HEADER DATA+ -> print_data_as_characters
        # Not implemented
        | ESC "I" BIN_ARG                   -> set_control_codes_printing
        | ESC "m\x00"                       -> set_upper_control_codes_printing
        | ESC "m\x04"                       -> unset_upper_control_codes_printing


        # Graphics
        # NOTE: Variable size
        # /[^\x1b]{1,49146}
        | ESC "*" SELECT_BIT_IMAGE_HEADER DATA+     -> select_bit_image
        # 75, 76, 89, 90 = KLYZ
        # 2nd byte can be more precise
        | ESC "?" /[KLYZ]./                         -> reassign_bit_image_mode
        | ESC "(G\x01\x00" /[1\x01]/                -> set_graphics_mode
        | ESC "(i\x01\x00" BIN_ARG_EX               -> switch_microweave_mode
        # Variable
        | ESC "." PRINT_RASTER_GRAPHICS_HEADER DATA+ -> print_raster_graphics
        # Variable
        | ESC SELECT_XDPI_GRAPHICS_CMD SELECT_XDPI_GRAPHICS_HEADER DATA+ -> select_xdpi_graphics

        # Similar to ESC * 0
        # | ESC "K" SELECT_XDPI_GRAPHICS_HEADER DATA+ -> select_60dpi_graphics
        # Similar to ESC * 1
        # | ESC "L" SELECT_XDPI_GRAPHICS_HEADER DATA+ -> select_120dpi_graphics
        # Similar to ESC * 2
        # | ESC "Y" SELECT_XDPI_GRAPHICS_HEADER DATA+ -> select_120dpi_double_speed_graphics
        # Similar to ESC * 3
        # | ESC "Z" SELECT_XDPI_GRAPHICS_HEADER DATA+ -> select_240dpi_graphics
        | ESC "^" SELECT_XDPI_GRAPHICS_9PIN_HEADER DATA+ -> select_60_120dpi_9pins_graphics

        # Barcode
        | ESC "(B" BARCODE_HEADER DATA+ -> barcode

    tiff_compressed_rule.2: tiff_enter tiff_instruction+ exit_ex

    # Not variable
    tiff_enter: ESC "." PRINT_TIFF_RASTER_GRAPHICS_HEADER -> print_tiff_raster_graphics
    exit_ex.2: EXIT_EX -> exit_tiff_raster_graphics
    tiff_instruction.2: XFER_HEADER DATA+ -> transfer_raster_graphics_data
        | COLR_EX -> set_printing_color_ex
        | CR_EX -> carriage_return
        # Not implemented
        | CLR_EX -> clear_ex
        | MOVXBYTE_EX -> set_movx_unit_8dots
        | MOVXDOT_EX -> set_movx_unit_1dot
        # DATA can be 0,1 or 2 bytes but lark doesn't accept
        # empty (0) terminal, thus we build the DATA token in the grammar between the lexer and the parser
        | MOVX_HEADER DATA+ -> set_relative_horizontal_position
        | MOVY_HEADER DATA+ -> set_relative_vertical_position


    # Everything but ESC
    # TODO exclude control codes
    ANYTHING.-1: /[^\x1b\t\n\r\x08\x09\x0b\x0c\x0e\x0f\x12\x14\x18\x7f]+/

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
    SELECT_BIT_IMAGE_HEADER: /[\x00\x01\x02\x03\x04\x05\x06\x07\x20\x21\x26\x27\x28\x40\x41\x46\x47\x48\x49].[\x00-\x1f]/
    PRINT_DATA_AS_CHARACTERS_HEADER: /.[\x00-\x7f]/
    PRINT_RASTER_GRAPHICS_HEADER: /[\x00\x01][\x05\x0A\x14]{2}[\x01\x08\x18].[\x00-\x1f]/
    PRINT_TIFF_RASTER_GRAPHICS_HEADER: /\x02[\x05\x0A\x14]{2}\x01\x00\x00/
    SELECT_XDPI_GRAPHICS_HEADER: /.[\x00-\x1f]/
    SELECT_XDPI_GRAPHICS_9PIN_HEADER: /[\x00\x01].[\x00-\x1f]/
    BARCODE_HEADER: /.[\x00-\x1f][\x00-\x07][\x02-\x05]..[\x00-\x1f]./


    #0b00100000-0b00101111
    #0b00110001,0b00110010
    # [\x00-\xff] used to allow \n character ???
    # use [\x00-\xff]/ instead of /./
    XFER_HEADER: /([\x20-\x2f]|[\x31\x32])/ DATA
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

    ARG: /[^\x1b]/
    BIN_ARG: /[\x00\x01]/
    BIN_ARG_EX: /[01\x00\x01]/
    HALF_BYTE_ARG: /[\x00-\x7f]/
    BYTE_ARG: /./
    # TODO: test: use [\x00-\xff] instead .
    DATA: /[\x00-\xff]/


    %import common.LETTER
    %import common.INT -> NUMBER
    %import common.ESCAPED_STRING   -> STRING
"""

def decompress_rle_data(iter_data, expected_decompressed_bytes):
    decompressed_data = bytearray()
    # iter_data = iter(compressed_data)
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
            [decompressed_data.append(next(iter_data)) for _ in range(block_length)]
            bytes_read += block_length

        bytes_read += 1

        # print(len(decompressed_data), bytes_read)
        if len(decompressed_data) >= expected_decompressed_bytes:
            break

    return decompressed_data, bytes_read

def parse_from_stream(parser, code, start=None, *args, **kwargs):
    """
    Parses iteratively from a potentially huge stream, throwing away text that is no longer needed.
    Uses the interactive parser interface, as well as implementation details of the LexerState objects.

    parser is a Lark instance
    provider is a string producer with the signature `() -> str`, for example via `partial(file.read, 64)`
    start get's passed to the Lark instance
    """
    interactive = parser.parse_interactive(code, start)
    bit_image_flag = False
    expected_bytes = 0
    rewind_offset = 0
    while True:
        interactive.lexer_thread.state.line_ctr.char_pos -= rewind_offset
        rewind_offset = 0
        try:
            token = next(interactive.lexer_thread.lex(interactive.parser_state))
        except StopIteration:
            break
        else:
            print(token.type, token.value)

            if token.type == "SELECT_BIT_IMAGE_HEADER":
                dot_density_m, nL, nH = token.value
                dot_columns_nb = (nH << 8) + nL

                if dot_density_m < 32:
                    bytes_per_column = 1
                elif dot_density_m < 64:
                    bytes_per_column = 3
                else:
                    bytes_per_column = 6

                expected_bytes = bytes_per_column * dot_columns_nb
                print(f"Expect {expected_bytes} bytes ({8 * bytes_per_column} dots per column)")

                bit_image_flag = True

            if token.type in (
                "PRINT_DATA_AS_CHARACTERS_HEADER", "SELECT_XDPI_GRAPHICS_HEADER", "SELECT_XDPI_GRAPHICS_9PIN_HEADER"):
                nL, nH = token.value
                expected_bytes = (nH << 8) + nL
                bit_image_flag = True

            elif token.type == "PRINT_RASTER_GRAPHICS_HEADER":
                # b"\x01\x14\x14\x18\xa0\x01"
                graphics_mode, v_res, h_res, v_dot_count_m, nL, nH = token.value
                h_dot_count = (nH << 8) + nL
                expected_decompressed_bytes = v_dot_count_m * int((h_dot_count +7) / 8)
                print(f"Expect {expected_decompressed_bytes} bytes")
                if graphics_mode == 1:
                    token_start_pos = interactive.lexer_thread.state.line_ctr.char_pos
                    iter_data = iter(interactive.lexer_thread.state.text[token_start_pos:])
                    data, expected_bytes = decompress_rle_data(iter_data, expected_decompressed_bytes)
                    print(data, "ret expected", expected_bytes, "curr", len(data))
                else:
                    expected_bytes = expected_decompressed_bytes
                # input("pause")
                bit_image_flag = True

            elif token.type == "BARCODE_HEADER":
                nL, nH, *_ = token.value
                expected_bytes = (nH << 8) + nL - 6
                print(f"Expect {expected_bytes} bytes")
                bit_image_flag = True

            elif token.type == "XFER_HEADER":
                # p224
                # 2F 80
                # 01 02 03 04 05 06 07 08 09 0A 0B 0C 0D 0E 0F
                # #BC = Low nibble value
                cmd, nL = token.value
                # print(cmd, bin(cmd), nL)
                cmd_bc = cmd & 0x0f
                lexer_state = interactive.lexer_thread.state

                if not (cmd >> 4) & 1:
                    # #BC = number of raster image data
                    expected_decompressed_bytes = cmd_bc
                elif cmd_bc == 1:
                    # F = 1 then #BC = number of raster image data counter
                    # #BC = 1: number of raster data = n1
                    expected_decompressed_bytes = nL
                elif cmd_bc == 2:
                    # F = 1 then #BC = number of raster image data counter
                    # #BC = 2: number of raster data = n1 + n2 × 256
                    # Get the next byte as nH
                    nH = lexer_state.text[lexer_state.line_ctr.char_pos]
                    expected_decompressed_bytes = (nH << 8) + nL

                    lexer_state.line_ctr.char_pos += 1
                else:
                    raise ValueError

                print("token val", token.value)
                print(f"Expect {expected_decompressed_bytes} decompressed bytes")
                bit_image_flag = True

                token_start_pos = lexer_state.line_ctr.char_pos
                # print(lexer_state.text[token_start_pos:])
                iter_data = iter(lexer_state.text[token_start_pos:])
                data, expected_bytes = decompress_rle_data(iter_data, expected_decompressed_bytes)


                print("used bytes to decomp", expected_bytes)
                # print("result, length", data, len(data))
                # input("pause")

            elif token.type == "MOVY_HEADER":
                lexer_state = interactive.lexer_thread.state
                token_start_pos = lexer_state.line_ctr.char_pos
                iter_data = iter(lexer_state.text[token_start_pos:])

                cmd = token.value[0]
                cmd_bc = cmd & 0x0f
                if not (cmd >> 4) & 1:
                    # #BC = number of raster image data
                    dot_offset = cmd_bc
                elif cmd_bc == 1:
                    # F = 1 then #BC = number of raster image data counter: 1
                    # #BC = 1: number of raster data = n1
                    nL = next(iter_data)
                    dot_offset = nL
                    lexer_state.line_ctr.char_pos += 1
                elif cmd_bc == 2:
                    # F = 1 then #BC = number of raster image data counter: 2
                    # #BC = 2: number of raster data = n1 + n2 × 256
                    nL, nH = next(iter_data), next(iter_data)
                    dot_offset = (nH << 8) + nL
                    lexer_state.line_ctr.char_pos += 2
                else:
                    raise ValueError

                print(dot_offset)
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
                    # F = 1 then #BC = number of parameter counter: 1
                    # nL (–128 ~ 127)
                    nL = next(iter_data)
                    dot_offset = nL - 2**8 if nL & 0x80 else nL
                    lexer_state.line_ctr.char_pos += 1
                elif cmd_bc == 2:
                    # F = 1 then #BC = number of parameter counter: 2
                    # (–32768 ~ 32767)
                    nL, nH = next(iter_data), next(iter_data)
                    dot_offset = (nH << 8) + nL
                    if dot_offset & 0x8000:
                        dot_offset -= 2**16
                    lexer_state.line_ctr.char_pos += 2

                print(dot_offset)
                # Feed the token now!
                interactive.feed_token(token)
                # Build a DATA token with the FINAL built value
                token = Token("DATA", dot_offset)



            # elif bit_image_flag:
            #     rewind_offset = len(token.value) - expected_bytes
            #     # DO NOT DO THIS, internal value will not be modified !!!
            #     # token.value = xxx
            #     lexer_state = interactive.lexer_thread.state
            #     token_start_pos = lexer_state.line_ctr.char_pos - len(token.value)
            #     token_end_pos = token_start_pos + expected_bytes
            #     # print("ici", lexer_state.text, token_start_pos, token_end_pos)
            #     value = lexer_state.text[token_start_pos:token_end_pos]
            #     token = Token(token.type, value)
            #     bit_image_flag = False

            if bit_image_flag:
                interactive.feed_token(token)
                rewind_offset = -expected_bytes

                lexer_state = interactive.lexer_thread.state
                token_start_pos = lexer_state.line_ctr.char_pos
                token_end_pos = token_start_pos + expected_bytes
                # print("ici", lexer_state.text, token_start_pos, token_end_pos)
                value = lexer_state.text[token_start_pos:token_end_pos]
                token = Token("DATA", value)

                # Not mandatory but useful for debugging
                token.start_pos = token_start_pos
                token.end_pos = token_end_pos

                bit_image_flag = False
                # input("pause")


            interactive.feed_token(token)

    tree = interactive.resume_parse()
    print(tree)
    print(tree.pretty())

    # exit()
    return tree

def init_parser(code, *args, **kwargs):
    parser = Lark(esc_grammar, parser="lalr", use_bytes=True, *args, **kwargs)

    return parse_from_stream(parser, code, **kwargs)
