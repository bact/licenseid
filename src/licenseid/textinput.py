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

Stdlib and ``licenseid.errors``/``urlkey``/``warning`` only, so importing it
does not pull in ``requests``.
"""

import os
import re
import stat

from licenseid.errors import InvalidInputError, one_line, shown
from licenseid.urlkey import SCHEMELESS_HOST
from licenseid.warning import warn

# A file name's extension at the end of a word: "LICENSE.txt", "COPYING.LESSER".
# No SPDX ID ends so: each ends in a version ("Apache-2.0", "LPPL-1.3c") or
# a word after a hyphen.
_RE_FILE_EXTENSION = re.compile(r"\.[A-Za-z][A-Za-z0-9]*\Z")


def looks_like_path(value: str) -> bool:
    """Whether a command-line argument that names no file is shaped like a
    path: one word, no URL (with or without its scheme), with a directory
    separator or a file name's extension ("docs/LICENSE", "LICENSE.txt").
    Matched as text, a mistyped path answers some licence with confidence,
    so the CLI refuses it; ``--text`` matches such a value as text."""
    if not value or "://" in value or any(c.isspace() for c in value):
        return False
    if SCHEMELESS_HOST.match(value):
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
        raise InvalidInputError(f"input: binary file: {shown(source)}")


def lone_surrogate_at(text: str) -> int | None:
    """The index of the first lone surrogate in *text*, or None. A lone
    surrogate (``\\ud800``, or the ``\\udcXX`` an argument of invalid UTF-8
    decodes to) is the one thing no UTF-8 encoder takes, so this is where
    the check is made, for the detector and the resolver alike."""
    try:
        text.encode("utf-8")
    except UnicodeEncodeError as exc:
        return exc.start
    return None


def has_lone_surrogate(text: str) -> bool:
    """Whether *text* has a lone surrogate (see :func:`lone_surrogate_at`)."""
    return lone_surrogate_at(text) is not None


def reject_lone_surrogate(text: str) -> None:
    """Raise InvalidInputError if *text* has a lone surrogate: SQLite's
    parameter binding would raise a raw UnicodeEncodeError."""
    position = lone_surrogate_at(text)
    if position is not None:
        raise InvalidInputError(
            f"input: invalid: text: lone surrogate at character {position}"
        )


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
        warn("input", "not UTF-8, read as Latin-1", shown(source))
        text = data.decode("latin-1")
    return normalize_newlines(text)


def _check_file_path(path: str) -> None:
    """Raise InvalidInputError unless *path* names a regular file: a missing
    path, a directory, a named pipe (opening one blocks for ever) or a device
    is no text to read. The CLI exits 2 for all of them."""
    if not path:
        raise InvalidInputError("input: invalid: file path: empty")
    try:
        mode = os.stat(path).st_mode
    except FileNotFoundError:
        if has_lone_surrogate(path):  # Windows takes it and finds nothing
            raise InvalidInputError(
                "input: invalid: file path: lone surrogate"
            ) from None
        raise InvalidInputError(f"input: not found: {shown(path)}") from None
    except ValueError as exc:  # an embedded NUL, a lone surrogate
        raise InvalidInputError(
            f"input: invalid: file path: {one_line(str(exc))}"
        ) from None
    except OSError as exc:
        raise _unreadable(path, exc) from None
    if not stat.S_ISREG(mode):
        raise InvalidInputError(f"input: unreadable: {shown(path)}: not a regular file")


def _unreadable(path: str, exc: OSError) -> InvalidInputError:
    """The error for *path* that the OS refused, with its reason."""
    return InvalidInputError(
        f"input: unreadable: {shown(path)}: {one_line(exc.strerror or str(exc))}"
    )


def read_text_file(path: str) -> str:
    """Read the file at *path* as text (see decode_input).

    Raises InvalidInputError (``input: not found``, ``input: unreadable``,
    ``input: invalid``, ``input: binary file``) if it is no readable text
    file; never a bare OSError. A path the OS cannot encode (an embedded NUL,
    a lone surrogate) is ``invalid``.
    """
    _check_file_path(path)
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError as exc:  # permission denied, or a change since the stat
        raise _unreadable(path, exc) from None
    return decode_input(data, path)
