# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The handful of command lines every environment family is replayed against.

Keeping them in one list is the point of families E1 to E11: each family
varies a single axis over the same commands, so any difference can only
have come from the axis under test.
"""

from __future__ import annotations

import shlex

from tools.cli_matrix.model import FRAG, OTHER, licenseid

#: (description, command, kind, expected exit) -- the commands every
#: environment axis is replayed against.
CORE: list[tuple[str, str, str, int]] = [
    ("detect --id-only file", licenseid("detect --id-only $F/mit.txt"), "detect", 0),
    (
        "detect latin1 file (warning)",
        licenseid("detect --id-only $F/mit_latin1.txt"),
        "detect",
        0,
    ),
    ("detect --json --id", licenseid("detect --json --id MIT"), "detect", 0),
    (
        "detect --diff --text",
        licenseid("detect --diff --text " + shlex.quote(FRAG + " and more words here")),
        "detect",
        0,
    ),
    ("is-osi MIT", licenseid("is-osi MIT"), "predicate", 0),
    ("is-spdx unknown", licenseid("is-spdx Nope-1.0"), "predicate", 1),
    ("detect no input", licenseid("detect"), "detect", 2),
    (
        "detect missing db",
        licenseid("detect MIT", db="/nonexistent/x.db"),
        "detect",
        2,
    ),
    ("detect --help", "$L detect --help", "help", 0),
    ("detect binary file", licenseid("detect $F/logo.png"), "detect", 2),
    (
        "detect not found",
        licenseid("detect --text " + shlex.quote(OTHER)),
        "detect",
        1,
    ),
    (
        "update offline ok",
        "mkdir -p $W/x && $LU --db $W/x/licenses.db update",
        "update",
        0,
    ),
]

#: (environment prefix, name) for the locale axis. Entries that name a real
#: locale are skipped when ``locale -a`` does not list it.
