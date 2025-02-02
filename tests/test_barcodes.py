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
"""Test barcodes printing"""
# Standard imports
from pathlib import Path
from functools import partial

# Local imports
from escapy.parser import ESCParser as _ESCParser
from .misc import esc_reset, typefaces
from .misc import pdf_comparison

# Inject test typefaces
ESCParser = partial(_ESCParser, available_fonts=typefaces)


def test_ean_barcodes(tmp_path: Path):
    lines = [
        "0D 0A 0D 0A 0D 0A 0D 0A 0D 0A 0D 0A"
        # EAN-13, CD: Host, HRI: print, Flag Char.: center
        # (CD: Check digit, HRI: Human Readable character)
        "1B 28 42 13 00"  # Barcode command and data length
        "00"  # Barcode type k = EAN-13
        "02"  # Module width m = 2 dots / 180 inch
        "00"  # Space adjustment value s = +0 dots / 360 inch
        "7D 00"  # Bar length v1, v2 = 125 / 180 inch
        "00"  # Control flags c
        "30 31 32 33 34 35 36 37 38 39 30 31 32"  # Barcode Data

        "0D 0A 0D 0A 0D 0A 0D 0A 0D 0A 0D 0A"

        # EAN-13, CD: Printer, HRI: none, Flag Char.: under
        "1B 28 42 13 00"  # Barcode command and data length
        "00"  # Barcode type k = EAN-13
        "02"  # Module width m = 2 dots / 180 inch
        "00"  # Space adjustment value s = +0 dots / 360 inch
        "7D 00"  # Bar length v1, v2 = 125 / 180 inch
        "03"  # Control flags c
        "30 31 32 33 34 35 36 37 38 39 30 31 32"  # Barcode Data
        "0D 0A 0D 0A 0D 0A 0D 0A 0D 0A 0D 0A"
        #     EAN-8, CD: Host, HRI: print
        "1B 28 42 0E 00"  # Barcode command and data length
        "01"  # Barcode type k = EAN-8
        "02"  # Module width m = 2 dots / 180 inch
        "00"  # Space adjustment value s = +0 dots / 360 inch
        "7D 00"  # Bar length v1, v2 = 125 / 180 inch
        "00"  # Control flags c
        "30 31 32 33 34 35 36 35"  # Barcode Data
    ]

    code = esc_reset + bytes(bytearray.fromhex(lines[0]))
    processed_file = tmp_path / "test_ean_barcodes.pdf"
    _ = ESCParser(code, output_file=processed_file)

    pdf_comparison(processed_file)


def test_interleaved_2_of_5_barcodes(tmp_path: Path):
    lines = [
        "0D 0A 0D 0A 0D 0A 0D 0A 0D 0A 0D 0A"
        #     Interleaved 2 of 5, CD: Host, HRI: print
        "1B 28 42 1A 00"  # Barcode command and data length
        "02"  # Barcode type k = Interleaved 2 of 5
        "02"  # Module width m = 2 dots / 180 inch
        "00"  # Space adjustment value s = +0 dots / 360 inch
        "7D 00"  # Bar length v1, v2 = 125 / 180 inch
        "00"  # Control flags c
        "31 32 33 34 35 36 37 38 39 30 31 32 33 34 35 36 37 38 39 30"  # Barcode Data

        "0D 0A 0D 0A 0D 0A 0D 0A 0D 0A 0D 0A"

        #      Interleaved 2 of 5, CD: Host, HRI: print
        # Next example is that ‘0’ is added automatically, in the case that the
        # data number is odd.
        "1B 28 42 19 00"  # Barcode command and data length
        "02"  # Barcode type k = Interleaved 2 of 5
        "02"  # Module width m = 2 dots / 180 inch
        "00"  # Space adjustment value s = +0 dots / 360 inch
        "7D 00"  # Bar length v1, v2 = 125 / 180 inch
        "00"  # Control flags c
        "31 32 33 34 35 36 37 38 39 30 31 32 33 34 35 36 37 38 39"  # Barcode Data
    ]

    code = esc_reset + bytes(bytearray.fromhex(lines[0]))
    processed_file = tmp_path / "test_interleaved_2_of_5_barcodes.pdf"
    _ = ESCParser(code, output_file=processed_file)

    pdf_comparison(processed_file)


def test_upc_barcodes(tmp_path: Path):
    lines = [
        "0D 0A 0D 0A 0D 0A 0D 0A 0D 0A 0D 0A"
        #     UPC-A, CD: Host, HRI: Print, Flag Char.: center
        "1B 28 42 12 00"  # Barcode command and data length
        "03"  # Barcode type k = UPC-A
        "02"  # Module width m = 2 dots / 180 inch
        "00"  # Space adjustment value s = +0 dots / 360 inch
        "7D 00"  # Bar length v1, v2 = 125 / 180 inch
        "00"  # Control flags c
        "30 31 32 33 34 35 36 37 38 39 30 35"  # Barcode Data

        "0D 0A 0D 0A 0D 0A 0D 0A 0D 0A 0D 0A"

        #     UPC-E, CD: Host, HRI: print
        # Next example is that of barcode data compacted in accordance with
        # specifications by the printer.
        "1B 28 42 12 00"  # Barcode command and data length
        "04"  # Barcode type k = UPC-E
        "02"  # Module width m = 2 dots / 180 inch
        "00"  # Space adjustment value s = +0 dots / 360 inch
        "7D 00"  # Bar length v1, v2 = 125 / 180 inch
        "00"  # Control flags c
        "30 31 32 33 34 35 36 37 38 39 30 35"  # Barcode Data
    ]

    code = esc_reset + bytes(bytearray.fromhex(lines[0]))
    processed_file = tmp_path / "test_upc_barcodes.pdf"
    _ = ESCParser(code, output_file=processed_file)

    pdf_comparison(processed_file)


def test_code39_barcodes(tmp_path: Path):
    lines = [
        "0D 0A 0D 0A 0D 0A 0D 0A 0D 0A 0D 0A"
        #     Code 39, CD: host, HRI: print
        "1B 28 42 0D 00"  # Barcode command and data length
        "05"  # Barcode type k = Code 39
        "02"  # Module width m = 2 dots / 180 inch
        "00"  # Space adjustment value s = +0 dots / 360 inch
        "7D 00"  # Bar length v1, v2 = 125 / 180 inch
        "00"  # Control flags c
        "31 32 41 42 24 25 2E"  # Barcode Data

        "0D 0A 0D 0A 0D 0A 0D 0A 0D 0A 0D 0A"

        #     Code 39, CD: host, HRI: print
        "1B 28 42 0D 00"  # Barcode command and data length
        "05"  # Barcode type k = Code 39
        "02"  # Module width m = 2 dots / 180 inch
        "00"  # Space adjustment value s = +0 dots / 360 inch
        "7D 00"  # Bar length v1, v2 = 125 / 180 inch
        "01"  # Control flags c
        "31 32 41 42 24 25 2E"  # Barcode Data
    ]
    code = esc_reset + bytes(bytearray.fromhex(lines[0]))
    processed_file = tmp_path / "test_code39_barcodes.pdf"
    _ = ESCParser(code, output_file=processed_file)

    pdf_comparison(processed_file)


def test_code128_barcodes(tmp_path: Path):
    lines = [
        "0D 0A 0D 0A 0D 0A 0D 0A 0D 0A 0D 0A"
        #     Code 128, CD: Printer, HRI: print, using Data Character Set A
        "1B 28 42 10 00"  # Barcode command and data length
        "06"  # Barcode type k = Code 128
        "02"  # Module width m = 2 dots / 180 inch
        "00"  # Space adjustment value s = +0 dots / 360 inch
        "7D 00"  # Bar length v1, v2 = 125 / 180 inch
        "01"  # Control flags c
        "41 32 33 40 41 21 43 44 5B 5D"  # Barcode Data
        # TODO: "A23@A!CD[]" instead of "23@A!CD[]5"
        #   The checksum is not shown even if add_check_digit = True
        # NOTE: The charset is always shown before (A/B/C)

        "0D 0A 0D 0A 0D 0A 0D 0A 0D 0A 0D 0A"

        #     Code 128, CD: Printer, HRI: print, using Data Character Set B
        "1B 28 42 10 00"  # Barcode command and data length
        "06"  # Barcode type k = Code 128
        "02"  # Module width m = 2 dots / 180 inch
        "00"  # Space adjustment value s = +0 dots / 360 inch
        "7D 00"  # Bar length v1, v2 = 125 / 180 inch
        "01"  # Control flags c
        "42 32 33 40 61 42 63 44 5B 5D"  # Barcode Data

        "0D 0A 0D 0A 0D 0A 0D 0A 0D 0A 0D 0A"

        #     Code 128, CD: Host, HRI: print, using Data Character Set C
        "1B 28 42 11 00"  # Barcode command and data length
        "06"  # Barcode type k = Code 128
        "02"  # Module width m = 2 dots / 180 inch
        "00"  # Space adjustment value s = +0 dots / 360 inch
        "7D 00"  # Bar length v1, v2 = 125 / 180 inch
        "00"  # Control flags c
        "43 30 31 32 33 34 35 36 37 38 39"  # Barcode Data
    ]
    code = esc_reset + bytes(bytearray.fromhex(lines[0]))
    processed_file = tmp_path / "test_code128_barcodes.pdf"
    _ = ESCParser(code, output_file=processed_file)

    pdf_comparison(processed_file)


def test_postnet_barcode(tmp_path: Path):
    lines = [
        "0D 0A 0D 0A 0D 0A 0D 0A 0D 0A 0D 0A"
        #     POSTNET, CD: Host
        "1B 28 42 10 00"  # Barcode command and data length
        "07"  # Barcode type k = POSTNET
        "02"  # Module width m = 2 dots / 180 inch
        "00"  # Space adjustment value s = +0 dots / 360 inch
        "00 00"  # Bar length value v1 and v2 are ignored. POSTNET
        # uses the fixed bar length.
        "00"  # Control flags c
        "31 32 33 34 35 2D 36 37 38 39"  # Barcode Data
        # NOTE: No, 0 is not allowed at the end...

        "0D 0A 0D 0A 0D 0A 0D 0A 0D 0A 0D 0A"

        # example 27: POSTNET, CD: Printer
        "1B 28 42 0F 00"  # Barcode command and data length
        "07"  # Barcode type k = POSTNET
        "02"  # Module width m = 2 dots / 180 inch
        "00"  # Space adjustment value s = +0 dots / 360 inch
        "00 00"  # Bar length value v1 and v2 are ignored. POSTNET
        # uses the fixed bar length.
        "01"  # Control flags c
        "31 32 33 34 35 36 37 38 39"  # Barcode Data
    ]
    code = esc_reset + bytes(bytearray.fromhex(lines[0]))
    processed_file = tmp_path / "test_postnet_barcode.pdf"
    _ = ESCParser(code, output_file=processed_file)

    pdf_comparison(processed_file)
