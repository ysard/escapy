#  ESCParser is a software allowing to use the Centronics and serial printing
#  functions of vintage computers on modern equipement through a tiny hardware
#  interface.
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
# Standard imports
import subprocess
from pathlib import Path

# Custom imports
from escapy.commons import logger

LOGGER = logger()


def is_similar_pdfs(ref_pdf_path: Path | str, tested_pdf_path: Path | str):
    """Visually compare 2 pdf files for test purposes

    :param ref_pdf_path: Reference file path.
    :param tested_pdf_path: Tested file path.
    :return: True if the files are similar; otherwise, a diff file is placed
        next to the problematic file in `/tmp`.
    :rtype: bool
    """
    ref_file_name = Path(ref_pdf_path).stem
    tested_file_name = Path(tested_pdf_path).stem

    diff_output_file = Path(f"/tmp/diff_{ref_file_name}_vs_{tested_file_name}.pdf")
    diffpdf_cmd = [
        "/usr/bin/diff-pdf",
        f"--output-diff={diff_output_file}",
        # f"--dpi=720",
        ref_pdf_path,
        tested_pdf_path,
    ]

    # We are in a child thread, we can have blocking calls like run()
    # Capture all outputs from the command in case of error with PIPE
    ps = subprocess.Popen(diffpdf_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    ps.wait()
    # diff-pdf returns 0 if the files are the same
    returncode = not bool(ps.returncode)

    LOGGER.info("Similarity <%s> vs <%s>: %s", ref_pdf_path, tested_pdf_path, returncode)
    if not returncode:
        LOGGER.error("Diff is saved at <%s> for further study.", diff_output_file)
    else:
        diff_output_file.unlink()

    return returncode
