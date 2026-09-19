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

import sys

# Whether the last status() call left a partial line open (end="", e.g. a
# row of progress dots). error() and warn() close it first, so every
# diagnostic starts at column 0 and `grep '^ERROR'` still finds it.
_state: dict[str, bool] = {"line_open": False}


def _diagnostic(level: str, message: str) -> None:
    if sys.stderr is None:  # closed (`2>&-`); print() would fall back to stdout
        return
    if _state["line_open"]:
        print(file=sys.stderr)
        _state["line_open"] = False
    print(f"{level}: {message}", file=sys.stderr)


def error(message: str) -> None:
    """Print *message* to standard error, prefixed ``ERROR:``."""
    _diagnostic("ERROR", message)


def warn(message: str) -> None:
    """Print *message* to standard error, prefixed ``WARNING:``."""
    _diagnostic("WARNING", message)


def status(message: str, *, end: str = "\n") -> None:
    """Print progress *message* to standard error, flushed at once so partial
    lines (``end=""``) show live."""
    if sys.stderr is None:  # closed (`2>&-`); print() would fall back to stdout
        return
    print(message, end=end, file=sys.stderr, flush=True)
    if message + end:
        _state["line_open"] = not (message + end).endswith("\n")


def end_line() -> None:
    """Close a partial progress line, if one is open. Call it when a step that
    printed with ``status(..., end="")`` stops early, so whatever the caller
    writes to standard error next starts on a fresh line."""
    if _state["line_open"] and sys.stderr is not None:
        print(file=sys.stderr, flush=True)
    _state["line_open"] = False
