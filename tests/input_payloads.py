# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""One table of input bytes and what licenseid must make of them.

Shared by the decoder unit tests (test_textinput.py) and the CLI/API parity
tests (test_option_matrix.py), so the two ways of reading a file are held to
the same cases.
"""

from typing import NamedTuple

from db_variants import MIT_TEXT

ACCENTED = MIT_TEXT + " (Jérôme)"


class Payload(NamedTuple):
    """Input *data*; it decodes to *text*, or is binary (*text* is None).
    *latin1* is true when the fallback decoder is used, with a warning."""

    name: str
    data: bytes
    text: str | None
    latin1: bool = False


PAYLOADS = [
    Payload("ascii", MIT_TEXT.encode(), MIT_TEXT),
    Payload("utf8", ACCENTED.encode(), ACCENTED),
    Payload("utf8_bom", b"\xef\xbb\xbf" + MIT_TEXT.encode(), MIT_TEXT),
    Payload(
        "crlf", MIT_TEXT.replace(", ", ",\r\n").encode(), MIT_TEXT.replace(", ", ",\n")
    ),
    Payload(
        "cr", MIT_TEXT.replace(", ", ",\r").encode(), MIT_TEXT.replace(", ", ",\n")
    ),
    Payload("latin1", ACCENTED.encode("latin-1"), ACCENTED, latin1=True),
    Payload(
        "latin1_crlf",
        ACCENTED.replace(", ", ",\r\n").encode("latin-1"),
        ACCENTED.replace(", ", ",\n"),
        latin1=True,
    ),
    Payload("nul", MIT_TEXT.encode() + b"\x00\x00", None),
    Payload("utf16_no_bom", MIT_TEXT.encode("utf-16-le"), None),
    Payload("utf16_bom", MIT_TEXT.encode("utf-16"), None),
    Payload("png", b"\x89PNG\r\n\x1a\n\x00\x00", None),
]
