#  ESCParser is a software allowing to convert EPSON ESC/P, ESC/P2
#  printer control language files into PDF files.
#  Copyright (C) 2024-2026  Ysard
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
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.*
"""Test commands involved in graphics printing.

Tested mode:

- ESC . 3; Raster TIFF/Delta Row compression
"""

# Standard imports
from pathlib import Path

# Local imports
from .misc import pdf_comparison
from .misc import graphics_mode
from .misc import ESCParser


def get_raster_delta_row_command():
    """Get raster delta row init command - ESC . 3

    The expected resolution is 720p.
    """
    raster_graphics_delta_row = b"\x1b.\x03"
    v_res_h_res = b"\x05\x05"  # 720 dpi
    v_dot_count_m = b"\x01"  # height of the band: 1 dot
    h_dot_count = b"\x00\x00"
    set_unit_720p = b"\x1b(U\x01\x00\x05"

    code = [
        graphics_mode,
        set_unit_720p,
        raster_graphics_delta_row,
        v_res_h_res + v_dot_count_m + h_dot_count,
    ]
    return b"".join(code)


def test_populate_seed_row(tmp_path: Path):
    """Test TIFF raster Delta Row data & seedrows - ESC . 3

    # 80 E1 72 37  01 80 51 6F  26 00 1F D8  FF 00 FC 52  25 01 24 00  07 D7 FF E2
    # ^black          ^black    ^  ^data              ^ hpos 293
    #    ^clear          ^ hpos 111                             ^  ^ data
    #                       ^ vpos 311

    Tree view::

        print_tiff_raster_graphics
            b'\x1b'
            b'\x03\x05\x05\x01\x00\x00'
        set_movx_unit_8dots       b'\xe4'
        set_printing_color_ex     b'\x80'
        clear_seed_row    b'\xe1'
        set_relative_vertical_position
            b'r'
            311
        set_relative_horizontal_position
            b'Q'
            111
        transfer_raster_graphics_data
            b'&'
            b'\x00\x1f\xd8\xff\x00\xfc'
        carriage_return   b'\xe2'
        set_printing_color_ex     b'\x81'
        clear_seed_row    b'\xe1'
        set_relative_vertical_position
            b'a'
            1
        set_relative_horizontal_position
            b'Q'
            111
        transfer_raster_graphics_data
            b'&'
            b'\x00\x1f\xd8\xff\x00\xfc'
        clear_seed_row    b'\xe1'
        set_printing_color_ex     b'\x81'
        set_relative_horizontal_position
            b'Q'
            111
        transfer_raster_graphics_data
            b'&'
            b'\x00\x1f\xd8\xff\x00\xfc'
        set_relative_vertical_position
            b'a'
            1
        clear_seed_row    b'\xe1'
        carriage_return   b'\xe2'
        set_printing_color_ex     b'\x80'
        set_relative_horizontal_position
            b'Q'
            111
        transfer_raster_graphics_data
            b'&'
            b'\x00\x1f\xd8\xff\x00\xfc'
        set_relative_horizontal_position
            b'R'
            293
        transfer_raster_graphics_data
            b'$'
            b'\x00\x07\xd7\xff'
        exit_tiff_raster_graphics b'\xe3'
    """
    clear_seed_row = b"\xe1"
    carriage_return = b"\xe2"
    exit_cmd = b"\xe3"
    set_movx_unit_8dots = b"\xe4"

    set_printing_color_black = b"\x80"
    set_printing_color_magenta = b"\x81"
    set_printing_color_cyan = b"\x82"
    set_printing_color_yellow = b"\x84"

    processed_file = tmp_path / "test_populate_seed_row.pdf"

    raster_delta_row = get_raster_delta_row_command()
    escapy = ESCParser(raster_delta_row + exit_cmd, pdf=False)

    assert escapy.delta_row_graphics_mode, "Delta Row mode not initialized"
    assert escapy.seed_rows, "Seed rows not initialized"

    assert all(
        (
            bytearray() == escapy.seed_rows[color_idx]
            for color_idx in range(len(escapy.CMYK_colors))
        )
    ), "Expects as many seed rows as there are colors"

    # <MOVY> + 1 offset (0x01)
    # 0b0110 Count Transfer 1–15 bytes of graphics data
    # 0b0110_0001:
    movy_cmd_bc0_1offset = b"\x61"

    # <MOVY> + 311 offset (0x0137)
    # 0b0111 Count is inside the 2 next bytes
    # 0b0111_0010: 0x72
    movy_cmd_bc2_311offset = b"\x72\x37\x01"

    # <XFER>
    # 0b0010 Count Transfer 1–15 bytes of graphics data
    # Count is inside the nibble of cmd
    # 0b0010_0000 (0x20) + 0b0110 (6 bytes) = 0b0010_0110 (0x26)
    xfer_cmd_bc0_6bytes = b"\x26"
    # 0b0010_0000 (0x20) + 0b0100 (4 bytes) = 0b0010_0100 (0x24)
    xfer_cmd_bc0_4bytes = b"\x24"

    # <MOVX> + 111 offset
    # Count is inside the next byte nL
    # 0b0101_0000 (0x50) + 1 = 0b0101_0001
    movx_cmd_bc1_111offset = b"\x51\x6f"

    # <MOVX> + 293 offset (0x0125)
    # Count is inside the 2 next bytes
    # 0b0101_0000 (0x50) + 2 = 0b0101_0001
    movx_cmd_bc2_293offset = b"\x52\x25\x01"

    xfer_seed_row = xfer_cmd_bc0_6bytes + b"\x00\x1f\xd8\xff\x00\xfc"
    code = [
        raster_delta_row,
        set_movx_unit_8dots,
        set_printing_color_black,
        clear_seed_row,
        movy_cmd_bc2_311offset,
        movx_cmd_bc1_111offset,
    ]
    # NOTE: Can't test h/v positions since <EXIT> is mandatory
    # and flushes out the buffers.

    # setup black & cyan seed rows (cyan is 1 indent below black)
    code += [
        xfer_seed_row,  # fill black seedrow
        carriage_return,
        set_printing_color_magenta,  # switch to magenta
        clear_seed_row,
        movy_cmd_bc0_1offset,  # print black seedrow, color is reset to black
        movx_cmd_bc1_111offset,
        xfer_seed_row,  # fill black seedrow with the same data at the same pos
    ]

    # NOTE: exit_cmd triggers buffer printing
    escapy = ESCParser(b"".join(code) + exit_cmd, output_file=processed_file)

    expected_seed_row = bytearray(
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x1f\xff\xff\xff\xff\xff\xff\xff"
        b"\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff"
        b"\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff"
        b"\xfc"
    )
    print(escapy.seed_rows)
    assert escapy.seed_rows[0] == expected_seed_row
    assert not escapy.seed_rows[1], "Magenta should be untouched"

    code += [
        clear_seed_row,  # clear black
        set_printing_color_magenta,  # switch to magenta
        movx_cmd_bc1_111offset,
        xfer_seed_row,  # fill magenta seedrow
    ]

    # NOTE: exit_cmd triggers buffer printing
    escapy = ESCParser(b"".join(code) + exit_cmd, output_file=processed_file)

    assert not escapy.seed_rows[0], "Black should be empty"
    assert escapy.seed_rows[1] == expected_seed_row

    # Send delta patch only for black
    xfer_delta_patch = xfer_cmd_bc0_4bytes + b"\x00\x07\xd7\xff"
    code += [
        movy_cmd_bc0_1offset,
        clear_seed_row,  # clear magenta
        carriage_return,
        set_printing_color_black,  # switch to black
        movx_cmd_bc1_111offset,
        xfer_seed_row,
        movx_cmd_bc2_293offset,  # set patch pos
        xfer_delta_patch,  # send patch
    ]

    escapy = ESCParser(b"".join(code) + exit_cmd, output_file=processed_file)

    expected_delta_row = bytearray(
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x1f\xff\xff\xff\xff\xff\xff\xff"
        b"\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff"
        b"\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff"
        b"\xfc\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x07\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff"
        b"\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff"
        b"\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff"
    )

    print(escapy.seed_rows)
    assert escapy.seed_rows[0] == expected_delta_row
    assert not escapy.seed_rows[1]

    pdf_comparison(processed_file)
