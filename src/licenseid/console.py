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


def error(message: str) -> None:
    """Print *message* to standard error, prefixed ``ERROR:``."""
    print(f"ERROR: {message}", file=sys.stderr)


def warn(message: str) -> None:
    """Print *message* to standard error, prefixed ``WARNING:``."""
    print(f"WARNING: {message}", file=sys.stderr)


def status(message: str, *, end: str = "\n") -> None:
    """Print progress *message* to standard error, flushed at once so partial
    lines (``end=""``) show live."""
    print(message, end=end, file=sys.stderr, flush=True)
