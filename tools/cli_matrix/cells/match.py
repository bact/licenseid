# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Family A: the ``match`` subcommand.

``A1`` every input source against every combination of output flags,
``A2`` ``--top`` against ``--threshold`` against popularity,
``A3`` an all-pairs sweep over every ``match`` factor at once,
``A4`` adversarial option syntax, where ``click`` itself is under test.
"""

from __future__ import annotations

import itertools
import shlex
from typing import Any

from tools.cli_matrix.model import (
    FRAG,
    MISSING,
    OUTS,
    SRC,
    CellSet,
    licenseid,
    source,
)
from tools.cli_matrix.pairwise import pairwise

TOPS = ["", "1", "2", "3", "5", "0", "-1", "abc", "1.5"]
THRS = ["", "0", "0.5", "0.85", "0.99", "1", "1.5", "-1", "abc", "nan"]

#: Every ``match`` factor, for the all-pairs sweep. ``pos`` is where the
#: options sit relative to the input and whether ``--opt=value`` is used.
FACTORS: dict[str, list[Any]] = {
    "src": ["arg_file", "arg_id", "text", "id", "stdin"],
    "found": [True, False],
    "out": list(range(len(OUTS))),
    "top": ["", "1", "5", "0", "-1"],
    "thr": ["", "0", "0.99", "1.5", "nan"],
    "pop": ["", "--pop", "--no-pop"],
    "pos": ["after", "before", "eq"],
}

#: (description, argument string, expected exit or None) for A4. These are
#: about the parser, not the matcher: abbreviations, repeats, ``--``, empty
#: values, and flags swallowed as the value of the option before them.
SYNTAX: list[tuple[str, str, int | None]] = [
    ("repeat --json", "--json --json MIT", 0),
    ("repeat --top (last wins?)", "--top 1 --top 2 MIT", None),
    ("--pop --no-pop", "--pop --no-pop MIT", 0),
    ("--no-pop --pop", "--no-pop --pop MIT", 0),
    ("--top=2 --threshold=0.5", "--top=2 --threshold=0.5 MIT", None),
    ("options before positional", "--json --bold MIT", 0),
    ("-- then id", "-- MIT", 0),
    ("-- then dash file", "-- -dash.txt", None),
    ("-- then --json as input", "-- --json", None),
    ("abbreviation --js", "--js MIT", 2),
    ("abbreviation --thr", "--thr 0.5 MIT", 2),
    ("-h", "-h", 2),
    ("--json=true", "--json=true MIT", 2),
    ("--text missing value", "--text", 2),
    ("--text takes --json as value", "--text --json", None),
    ("--id takes --bold as value", "--id --bold", None),
    ("--top missing value", "MIT --top", 2),
    ("--threshold= empty", "--threshold= MIT", 2),
    ("--top '' empty", "--top '' MIT", 2),
    ("--top 03", "--top 03 MIT", None),
    ("--top +2", "--top +2 MIT", None),
    ("--top ' 2'", "--top ' 2' MIT", None),
    ("--threshold 1e-1", "--threshold 1e-1 MIT", None),
    ("--threshold .5", "--threshold .5 MIT", None),
    ("--threshold 1,5", "--threshold 1,5 MIT", 2),
    ("--top 99999999999999999999", "--top 99999999999999999999 MIT", None),
    ("--threshold inf", "--threshold inf MIT", None),
    ("two positionals", "MIT Apache-2.0", 2),
    ("unknown flag", "--nope MIT", 2),
    ("short flag -j", "-j MIT", 2),
    ("--id and positional", "--id MIT Apache-2.0", None),
    ("--text= empty form", "--text= MIT", None),
    ("--id= empty form", "--id= MIT", None),
]


def add_cells(cells: CellSet) -> None:
    """Add families A1 to A4 to *cells*."""
    _add_sources(cells)
    _add_top_threshold(cells)
    _add_pairwise(cells)
    _add_syntax(cells)


def _add_sources(cells: CellSet) -> None:
    """A1: each source x each output combination, found and not found."""
    for found in (True, False):
        for out in OUTS:
            for name in SRC:
                pre, args, tag = source(name, found)
                flags = " ".join(f"--{o}" for o in out)
                cell = cells.add(
                    "A1",
                    f"match src={name} {'found' if found else 'not-found'} "
                    f"out={'+'.join(out) or 'plain'}",
                    f"{pre}{licenseid(f'match {args} {flags}')}",
                    kind="match",
                    outflags=frozenset(out),
                    exp_exit=2 if name == "none" else (0 if found else 1),
                    group=_source_group(name, found, out),
                    exp_err=_source_expected_stderr(name, found),
                )
                cell.tags.add(f"src:{tag}")


def _source_group(name: str, found: bool, out: tuple[str, ...]) -> str | None:
    """Sources that must give the same answer belong to the same group."""
    if name in ("arg_file", "text", "stdin"):
        return f"A1-text-{found}-{'+'.join(out)}"
    if name in ("arg_id", "id"):
        return f"A1-id-{found}-{'+'.join(out)}"
    return None


def _source_expected_stderr(name: str, found: bool) -> str | None:
    """The diagnostic a source is required to produce, if any."""
    if name == "none":
        return MISSING
    return None if found else r"ERROR: match: no license found"


def _add_top_threshold(cells: CellSet) -> None:
    """A2: ``--top`` x ``--threshold`` x output, then x popularity."""
    for top in TOPS:
        for thr in THRS:
            for mode in ("", "--json"):
                args = " ".join(
                    x
                    for x in (
                        f"--text {shlex.quote(FRAG)}",
                        f"--top {top}" if top else "",
                        f"--threshold {thr}" if thr else "",
                        mode,
                    )
                    if x
                )
                bad = top in ("abc", "1.5") or thr == "abc"
                cells.add(
                    "A2",
                    f"match FRAG top={top or 'default'} "
                    f"threshold={thr or 'default'} {mode or 'plain'}",
                    licenseid(f"match {args}"),
                    kind="match",
                    outflags=frozenset({"json"} if mode else ()),
                    exp_exit=2 if bad else None,
                    top=_top_bound(top),
                )
    for top, thr, pop in itertools.product(
        ["", "1", "5"], ["", "0"], ["--pop", "--no-pop"]
    ):
        args = " ".join(
            x
            for x in (
                f"--text {shlex.quote(FRAG)}",
                f"--top {top}" if top else "",
                f"--threshold {thr}" if thr else "",
                pop,
                "--json",
            )
            if x
        )
        cells.add(
            "A2",
            f"match FRAG top={top or 'default'} "
            f"threshold={thr or 'default'} {pop} json",
            licenseid(f"match {args}"),
            kind="match",
            outflags=frozenset({"json"}),
            top=int(top) if top else None,
        )


def _top_bound(top: str) -> int | None:
    """*top* as a result-count bound, or None when it is not a valid count."""
    if top.lstrip("-").isdigit() and int(top) >= 1:
        return int(top)
    return None


def _add_pairwise(cells: CellSet) -> None:
    """A3: an all-pairs sweep over every ``match`` factor at once."""
    for row in pairwise(FACTORS):
        out = OUTS[row["out"]]
        pre, args, tag = source(row["src"], row["found"])
        opts = [f"--{o}" for o in out]
        for name, val in (("top", row["top"]), ("threshold", row["thr"])):
            if val:
                opts.append(
                    f"--{name}={val}" if row["pos"] == "eq" else f"--{name} {val}"
                )
        if row["pop"]:
            opts.append(row["pop"])
        joined = " ".join(opts)
        body = f"{joined} {args}" if row["pos"] == "before" else f"{args} {joined}"
        defaults = not row["top"] and not row["thr"]
        cell = cells.add(
            "A3",
            f"pairwise src={row['src']} found={row['found']} "
            f"out={'+'.join(out) or 'plain'} top={row['top'] or '-'} "
            f"thr={row['thr'] or '-'} pop={row['pop'] or '-'} pos={row['pos']}",
            f"{pre}{licenseid(f'match {body}')}",
            kind="match",
            outflags=frozenset(out),
            exp_exit=(0 if row["found"] else 1) if defaults else None,
            top=int(row["top"]) if row["top"] not in ("", "0", "-1") else None,
        )
        cell.tags.add(f"src:{tag}")


def _add_syntax(cells: CellSet) -> None:
    """A4: adversarial option syntax, run from the fixture directory."""
    for desc, args, exit_code in SYNTAX:
        # When the flag is consumed as a value or comes after ``--`` it is
        # input, not an output flag, so the output contract does not apply.
        real = not (
            args.startswith("-- ") or "--text --json" in args or "--id --bold" in args
        )
        cells.add(
            "A4",
            f"match syntax: {desc}",
            f"cd $F && {licenseid(f'match {args}')}",
            kind="match",
            exp_exit=exit_code,
            outflags=frozenset(
                x for x in ("json", "bold") if real and f"--{x}" in args
            ),
        )
