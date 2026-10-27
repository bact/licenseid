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

import re

from licenseid.console import warn
from licenseid.errors import InvalidInputError

# A file name's extension at the end of a word: "LICENSE.txt", "COPYING.LESSER".
# No SPDX ID ends so: each ends in a version ("Apache-2.0", "LPPL-1.3c") or
# a word after a hyphen.
_RE_FILE_EXTENSION = re.compile(r"\.[A-Za-z][A-Za-z0-9]*\Z")
# A host name before the first "/": a URL written without its scheme
# ("www.apache.org/licenses/LICENSE-2.0"), not a directory.
_RE_HOST = re.compile(r"(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}(?::\d+)?/")


def looks_like_path(value: str) -> bool:
    """Whether a command-line argument that names no file is shaped like a
    path: one word, no URL (with or without its scheme), with a directory
    separator or a file name's extension ("docs/LICENSE", "LICENSE.txt").
    Matched as text, a mistyped path answers some licence with confidence,
    so the CLI refuses it; ``--text`` matches such a value as text."""
    if not value or "://" in value or any(c.isspace() for c in value):
        return False
    if _RE_HOST.match(value):
        return False
    return "/" in value or "\\" in value or bool(_RE_FILE_EXTENSION.search(value))


def normalize_newlines(text: str) -> str:
    """Turn CRLF and CR line ends into LF."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def reject_binary(data: bytes | str, source: str) -> None:
    """Raise InvalidInputError if *data* (from *source*) has a NUL: text never
    does, so it is binary, whether or not it happens to be valid UTF-8."""
    if isinstance(data, bytes):
        has_nul = b"\x00" in data
    else:
        has_nul = "\x00" in data
    if has_nul:
        raise InvalidInputError(f"input: binary file: {source}")


def reject_lone_surrogate(text: str) -> None:
    """Raise InvalidInputError if *text* has a lone surrogate (``\\ud800``, or
    the ``\\udcXX`` an argument of invalid UTF-8 decodes to): no encoder takes
    it, so SQLite's parameter binding would raise a raw UnicodeEncodeError."""
    try:
        text.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise InvalidInputError(
            f"input: invalid: text: lone surrogate at character {exc.start}"
        ) from exc


def decode_input(data: bytes, source: str) -> str:
    """Decode input *data* from *source* (a path or ``stdin``) into text.

    Bytes with a NUL are binary (reject_binary; UTF-16 text is binary here
    too). Otherwise UTF-8 first, with a leading BOM dropped, then Latin-1
    (older license files use it; every byte decodes) with a warning.
    CRLF and CR then become LF, as text-mode reading did before, so matching
    sees the same text whichever way the input arrived.
    """
    reject_binary(data, source)
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
