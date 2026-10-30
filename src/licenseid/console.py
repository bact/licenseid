# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
Diagnostic output shared by the library and the CLI.

Progress and warnings go to standard error so they never mix with a
command's result on standard output. Stdlib-only: ``database.py`` imports
this on the match path. :func:`emit` is the one writer of both streams.
"""

import os
import sys
from typing import TextIO

# Whether the last status() call left a partial line open (end="", e.g. a
# row of progress dots). error() and warn() close it first, so every
# diagnostic starts at column 0 and `grep '^ERROR'` still finds it.
_state: dict[str, bool] = {"line_open": False}


def emit(stream: TextIO, text: str, encoding: str | None = None) -> None:
    """Write *text* to *stream* as it is and flush: each line ends in a line
    feed on every platform, as Windows' text streams would write ``\\r\\n``
    (P123). It goes to the bytes under the stream, in *encoding* (the
    stream's own when None), a character the encoding cannot hold as a
    backslash escape (``\\xHH``, ``\\uHHHH``, ``\\UHHHHHHHH``) whatever the
    stream's error handler: one rule on every locale. A stream with no bytes
    under it, or an encoding Python does not know, gets the text.

    Raises what the stream raises: OSError, and ValueError when closed."""
    buffer = getattr(stream, "buffer", None)
    name = encoding or getattr(stream, "encoding", None)
    if not isinstance(name, str) or not name:  # a stream that names none
        name = "utf-8"
    try:
        data = text.encode(name, "backslashreplace")
    except LookupError:
        buffer = None
    if buffer is None:
        stream.write(text)
        stream.flush()
        return
    stream.flush()  # what was written as text comes first
    buffer.write(data)
    buffer.flush()


def _write(text: str, end: str = "\n") -> None:
    """Write to standard error (:func:`emit`). A closed or failing standard
    error (`2>&-`, a full disk) has nowhere to report its own failure, and
    must not turn a result into a crash, so it is skipped."""
    if sys.stderr is None:
        return
    try:
        emit(sys.stderr, text + end)
    except ValueError:  # closed
        return
    except OSError:
        # The text stays buffered, and the flush at exit would fail again
        # and turn every exit status into 120.
        _discard(sys.stderr)


def _diagnostic(level: str, message: str) -> None:
    if _state["line_open"]:
        _write("")
        _state["line_open"] = False
    _write(f"{level}: {message}")


def error(message: str) -> None:
    """Print *message* to standard error, prefixed ``ERROR:``."""
    _diagnostic("ERROR", message)


def write(text: str) -> None:
    """Write *text* to standard error as it is: the help shown for a
    missing subcommand, which is no diagnostic."""
    _write(text, end="")


def warn(message: str) -> None:
    """Print *message* to standard error, prefixed ``WARNING:``."""
    _diagnostic("WARNING", message)


def status(message: str, *, end: str = "\n") -> None:
    """Print progress *message* to standard error, flushed at once so partial
    lines (``end=""``) show live."""
    _write(message, end)
    if message + end:
        _state["line_open"] = not (message + end).endswith("\n")


def end_line() -> None:
    """Close a partial progress line, if one is open. Call it when a step that
    printed with ``status(..., end="")`` stops early, so whatever the caller
    writes to standard error next starts on a fresh line."""
    if _state["line_open"]:
        _write("")
    _state["line_open"] = False


def discard_stdout() -> None:
    """Point standard output at the null device after a write to it failed,
    so the flush at exit does not fail a second time (the Python manual's
    advice for SIGPIPE)."""
    _discard(sys.stdout)


def _discard(stream: TextIO | None) -> None:
    if stream is None:
        return
    try:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, stream.fileno())
        os.close(devnull)
    except (OSError, ValueError):  # not a real file
        pass
