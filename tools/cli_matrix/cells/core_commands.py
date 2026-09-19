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
    ("match --bold file", licenseid("match --bold $F/mit.txt"), "match", 0),
    (
        "match latin1 file (warning)",
        licenseid("match --bold $F/mit_latin1.txt"),
        "match",
        0,
    ),
    ("match --json --id", licenseid("match --json --id MIT"), "match", 0),
    (
        "match --diff --text",
        licenseid("match --diff --text " + shlex.quote(FRAG + " and more words here")),
        "match",
        0,
    ),
    ("is-osi MIT", licenseid("is-osi MIT"), "predicate", 0),
    ("is-spdx unknown", licenseid("is-spdx Nope-1.0"), "predicate", 1),
    ("match no input", licenseid("match"), "match", 2),
    (
        "match missing db",
        licenseid("match MIT", db="/nonexistent/x.db"),
        "match",
        2,
    ),
    ("match --help", "$L match --help", "help", 0),
    ("match binary file", licenseid("match $F/logo.png"), "match", 2),
    (
        "match not found",
        licenseid("match --text " + shlex.quote(OTHER)),
        "match",
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
