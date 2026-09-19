# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Family B: the predicate subcommands (``is-osi`` and friends).

``B1`` every input source, ``B2`` which input wins when several are given,
``B3`` flags that belong to ``match`` only, ``B4`` argument syntax,
``B5`` one identifier asked of all five predicates, so their answers can be
checked against each other.
"""

from __future__ import annotations

import shlex

from tools.cli_matrix.model import (
    FRAG,
    IDS,
    OTHER,
    PREDS,
    SRC,
    CellSet,
    licenseid,
    source,
)

#: (description, arguments) pairs where more than one input is supplied.
PRECEDENCE = [
    ("--id + --text", "--id MIT --text {o}"),
    ("--id + arg", "--id MIT Nope-1.0"),
    ("--text + arg", "--text {f} Nope-1.0"),
    ("arg + stdin", "MIT"),
    ("--text + stdin", "--text {f}"),
    ("--id + stdin", "--id MIT"),
    ("--id + --text + arg + stdin", "--id MIT --text {o} Nope-1.0"),
    ("--id wrong + --text right", "--id Nope-1.0 --text {f}"),
    ("--id twice", "--id Nope-1.0 --id MIT"),
    ("--text twice", "--text {o} --text {f}"),
]

#: Flags that only ``match`` accepts: a predicate must reject each of them.
MATCH_ONLY = (
    "--json",
    "--bold",
    "--diff",
    "--pop",
    "--no-pop",
    "--top 1",
    "--threshold 0.5",
)

#: (description, arguments) for predicate argument syntax.
SYNTAX = (
    ("--id=MIT", "--id=MIT"),
    ("--text=MIT", "--text=MIT"),
    ("blank --id", "--id ''"),
    ("blank --text", "--text ''"),
    ("blank arg", "''"),
    ("--id missing value", "--id"),
    ("expression id", "--id 'MIT WITH Font-exception-2.0'"),
    ("deprecated +", "--id 'GPL-2.0+'"),
    ("LicenseRef", "--id LicenseRef-x"),
    ("lowercase", "--id mit"),
)


def add_cells(cells: CellSet) -> None:
    """Add families B1 to B5 to *cells*."""
    _add_sources(cells)
    _add_precedence(cells)
    _add_match_only_flags(cells)
    _add_syntax(cells)
    _add_identifier_consistency(cells)


def _add_sources(cells: CellSet) -> None:
    """B1: every predicate against every input source."""
    for cmd in PREDS:
        for found in (True, False):
            for name in SRC:
                pre, args, tag = source(name, found)
                kind_of_source = (
                    "text" if name in ("arg_file", "text", "stdin") else name
                )
                cell = cells.add(
                    "B1",
                    f"{cmd} src={name} {'found' if found else 'not-found'}",
                    f"{pre}{licenseid(f'{cmd} {args}')}",
                    kind="predicate",
                    exp_exit=2 if name == "none" else (0 if found else 1),
                    group=(
                        None if name == "none" else f"B1-{cmd}-{found}-{kind_of_source}"
                    ),
                )
                cell.tags.add(f"src:{tag}")


def _add_precedence(cells: CellSet) -> None:
    """B2: which input wins when several are supplied at once."""
    for cmd in PREDS:
        for desc, template in PRECEDENCE:
            args = template.format(o=shlex.quote(OTHER), f=shlex.quote(FRAG))
            pre = "printf 'The quick brown fox jumps' | " if "stdin" in desc else ""
            cells.add(
                "B2",
                f"{cmd} precedence: {desc}",
                f"{pre}{licenseid(f'{cmd} {args}')}",
                kind="predicate",
            )


def _add_match_only_flags(cells: CellSet) -> None:
    """B3: a predicate given a flag only ``match`` has must be a usage error."""
    for cmd in PREDS:
        for flag in MATCH_ONLY:
            cells.add(
                "B3",
                f"{cmd} with match-only flag {flag}",
                licenseid(f"{cmd} MIT {flag}"),
                kind="predicate",
                exp_exit=2,
                exp_out="",
            )


def _add_syntax(cells: CellSet) -> None:
    """B4: predicate argument syntax."""
    for cmd in PREDS:
        for desc, args in SYNTAX:
            cells.add(
                "B4",
                f"{cmd} syntax: {desc}",
                licenseid(f"{cmd} {args}"),
                kind="predicate",
            )


def _add_identifier_consistency(cells: CellSet) -> None:
    """B5: every predicate asked about the same identifier.

    Judged relationally: ``is-open`` must agree with ``is-osi or is-fsf``,
    and ``is-free`` must agree with ``is-open``.
    """
    for ident in IDS:
        for cmd in PREDS:
            cells.add(
                "B5",
                f"{cmd} --id '{ident}' (consistency group)",
                licenseid(f"{cmd} --id {shlex.quote(ident)}"),
                kind="predicate",
            )
