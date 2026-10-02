# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
Diagnostic output shared by the library and the CLI.

Progress and warnings go to standard error so they never mix with a
command's result on standard output. Stdlib-only: ``database.py`` imports
this on the match path.
"""

import os
import sys

# Whether the last status() call left a partial line open (end="", e.g. a
# row of progress dots). error() and warn() close it first, so every
# diagnostic starts at column 0 and `grep '^ERROR'` still finds it.
_state: dict[str, bool] = {"line_open": False}


def _write(text: str, end: str = "\n") -> None:
    """Write to standard error, flushed. A closed or failing standard error
    (`2>&-`, a full disk) has nowhere to report its own failure, and must not
    turn a result into a crash, so it is skipped."""
    if sys.stderr is None:  # print() would fall back to standard output
        return
    try:
        print(text, end=end, file=sys.stderr, flush=True)
    except OSError:
        pass


def _diagnostic(level: str, message: str) -> None:
    if _state["line_open"]:
        _write("")
        _state["line_open"] = False
    _write(f"{level}: {message}")


def error(message: str) -> None:
    """Print *message* to standard error, prefixed ``ERROR:``."""
    _diagnostic("ERROR", message)


def warn(message: str) -> None:
    """Print *message* to standard error, prefixed ``WARNING:``."""
    _diagnostic("WARNING", message)


def status(message: str, *, end: str = "\n") -> None:
    """Print progress *message* to standard error, flushed at once so partial
    lines (``end=""``) show live."""
    if sys.stderr is None:
        return
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
    try:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        os.close(devnull)
    except (AttributeError, OSError, ValueError):  # closed or not a real file
        pass
