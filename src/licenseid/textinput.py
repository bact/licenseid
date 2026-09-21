# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
How input bytes become match text.

The one place a user's file, standard input or ``file_path`` is decoded, so the
CLI and the Python API read the same bytes the same way. Other files this
package opens (SPDX release data in ``database.py`` and ``spdx_source.py``)
are trusted and stay strict UTF-8: a Latin-1 fallback there would hide a
corrupt download.

Stdlib and ``licenseid.console``/``errors`` only, so importing it does not
pull in ``requests``.
"""

from licenseid.console import warn
from licenseid.errors import InvalidInputError


def normalize_newlines(text: str) -> str:
    """Turn CRLF and CR line ends into LF."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def decode_input(data: bytes, source: str) -> str:
    """Decode input *data* from *source* (a path or ``stdin``) into text.

    Bytes with a NUL are binary and raise InvalidInputError, whether or not
    they happen to be valid UTF-8 (UTF-16 text is binary here too). Otherwise
    UTF-8 first, with a leading BOM dropped, then Latin-1 (older license files
    use it; every byte decodes) with a warning.
    CRLF and CR then become LF, as text-mode reading did before, so matching
    sees the same text whichever way the input arrived.
    """
    if b"\x00" in data:
        raise InvalidInputError(f"input: binary file: {source}")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        warn(f"input: not UTF-8, read as Latin-1: {source}")
        text = data.decode("latin-1")
    return normalize_newlines(text)


def read_text_file(path: str) -> str:
    """Read the file at *path* as text (see decode_input).

    Raises OSError if it cannot be read and InvalidInputError if it is binary.
    """
    with open(path, "rb") as f:
        data = f.read()
    return decode_input(data, path)
