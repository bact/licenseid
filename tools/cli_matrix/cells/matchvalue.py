# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Family F: ``licenseid match``, one declared value.

``F1`` values read and refused, in every shell (quoting decides what the
command sees), ``F2`` what only ``detect`` reads, refused with exit 2,
``F3`` the list read (``--source``, ``--db``, no database), ``F4`` the
streams around it.

A value that resolves exits 0, one that does not 1, and a refusal 2 with
``; run 'licenseid detect'`` (``climatch``). The editable install the
matrix usually runs ships no bundle, so a cell with no ``--db`` reads the
database at the default path: there is none in the cell's own ``HOME``.
"""

from __future__ import annotations

import shlex

from tools.cli_matrix.model import EVERY_SHELL, CellSet, licenseid

#: (description, value, expected exit) for F1: one argument each.
VALUES: list[tuple[str, str, int]] = [
    ("exact", "MIT", 0),
    ("re-spelt", "Apache2", 0),
    ("plus", "GPL-2.0+", 0),
    ("compound", "GPLv2+ or MIT", 0),
    ("prose with comma", "Apache License, Version 2.0", 0),
    ("curly quotes", "“MIT”", 0),
    ("deprecated, kept", "GPL-3.0", 0),
    ("semicolon list", "MIT ; Apache 2", 1),
    ("dropped mark", "Apache 2.0?", 1),
    ("names nothing", "Foo", 1),
    ("glob characters", "MIT*", 1),
    ("dollar and backtick", "$HOME `x`", 1),
    ("tab inside", "Apache\t2", 0),
]

_DETECT = r"; run 'licenseid detect'\n"

#: (description, command arguments, stdin prefix, stderr regex) for F2.
REFUSED: list[tuple[str, str, str, str]] = [
    (
        "--text",
        "match --text MIT",
        "",
        r"option: invalid: --text: a licence text" + _DETECT,
    ),
    ("a file", "match $F/mit.txt", "", r"input: invalid: path: .*" + _DETECT),
    ("a directory", "match $F/adir", "", r"input: invalid: path: .*" + _DETECT),
    ("the current directory", "match .", "", r"input: invalid: path: \." + _DETECT),
    ("standard input", "match", "printf MIT | ", r"input: invalid: standard input"),
    ("stdin /dev/null", "match < /dev/null", "", r"input: invalid: standard input"),
    (
        "a line break",
        "match \"$(printf 'MIT\\nISC')\"",
        "",
        r"input: invalid: line break: MIT ISC" + _DETECT,
    ),
    (
        "over the cap",
        'match "$(printf "%2001s" x)"',
        "",
        r"input: invalid: over 2000 characters" + _DETECT,
    ),
    ("empty argument", "match ''", "", r"input: empty: argument\n"),
    (
        "invalid UTF-8",
        "match \"$(printf 'MIT\\377')\"",
        "",
        r"input: invalid: text: lone surrogate",
    ),
    ("two values", "match MIT ISC", "", r"input: invalid: extra argument: ISC"),
]

#: (description, command, expected exit, stderr regex or None) for F3.
SOURCES: list[tuple[str, str, int, str | None]] = [
    ("--db, auto", licenseid("match --json MIT"), 0, None),
    ("--db, database", licenseid("match --source database MIT"), 0, None),
    (
        "--db, packaged",
        licenseid("match --source packaged MIT"),
        2,
        r"option: invalid: --source: packaged with --db",
    ),
    ("--db missing", licenseid("match MIT", db="/nonexistent/x.db"), 2, "not found"),
    ("no --db, database", "$L match --source database MIT", 2, "database: not found"),
    ("--db=path form", "$L --db=$DB match MIT", 0, None),
    # 0 from a wheel (its bundle), 2 from an editable install (none)
    ("no --db, auto", "$L match MIT", -1, None),
]


def add_cells(cells: CellSet) -> None:
    """Add families F1 to F4 to *cells*."""
    for desc, value, exit_code in VALUES:
        for output in ("", "--json "):
            cells.add(
                "F1",
                f"match {output}{desc}",
                licenseid(f"match {output}{shlex.quote(value)}"),
                kind="match",
                outflags=frozenset({"json"} if output else ()),
                exp_exit=exit_code,
                shells=EVERY_SHELL,
            )
    for desc, args, pre, err in REFUSED:
        cells.add(
            "F2",
            f"match refuses {desc}",
            pre + licenseid(args),
            kind="match",
            exp_exit=2,
            exp_out="",
            exp_err=f"^ERROR: {err}",
        )
    for desc, cmd, exit_code, said in SOURCES:
        cells.add(
            "F3",
            f"match list: {desc}",
            cmd,
            kind="match",
            outflags=frozenset({"json"} if "--json" in cmd else ()),
            exp_exit=None if exit_code < 0 else exit_code,
            exp_err=said,
            xenv=False,  # a wheel ships a bundle, an editable install none
        )
    _add_streams(cells)


def _add_streams(cells: CellSet) -> None:
    """F4: the streams around one value."""
    cells.add(
        "F4",
        "match, stdout closed",
        licenseid("match MIT") + " >&-",
        kind="match",
        exp_exit=2,
        exp_err=r"^ERROR: output: write failed: ",
    )
    cells.add(
        "F4",
        "match, no value from a terminal",
        licenseid("match"),
        kind="match",
        tty=True,
    )
    cells.add(
        "F4",
        "match, stdin closed",
        licenseid("match") + " <&-",
        kind="match",
        exp_exit=2,
        exp_err=r"^ERROR: input: missing; pass one declared licence value\n",
    )
    cells.add(
        "F4",
        "match, reader gone",
        licenseid("match --json 'MIT ; Apache 2'") + " | head -c 1",
        kind="match",
    )
