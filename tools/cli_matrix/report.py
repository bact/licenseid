# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""What a run leaves behind: the ledger, the coverage checklist, the data.

``ledger.md`` is for reading: every FLAG and every OBSERVE spelled out, then
a table of everything that ran. ``coverage.md`` answers the other question --
not "did it pass" but "did anything even try this flag". ``results.json`` is
the machine-readable record the baseline and any later diff are built from.
"""

from __future__ import annotations

import itertools
from collections import Counter
from pathlib import Path
from typing import Any

from tools.cli_matrix.judge import norm
from tools.cli_matrix.model import PREDS, Cell
from tools.cli_matrix.runner import Skipped

Row = dict[str, Any]

#: Every flag of every subcommand, so the checklist can show the gaps too.
UNIVERSE: dict[str, list[str]] = {
    "global": ["--db", "--clear-cache", "--help", "(no subcommand)"],
    "update": ["--version", "--force", "--cache", "--no-cache", "--help"],
    "match": [
        "--text",
        "--id",
        "--json",
        "--threshold",
        "--top",
        "--pop",
        "--no-pop",
        "--diff",
        "--bold",
        "--help",
    ],
}
for _pred in PREDS:
    UNIVERSE[_pred] = ["--text", "--id", "--help"]

SOURCES = ["arg-id", "arg-file", "--text", "--id", "stdin", "none"]

MATCH_FLAGS = [
    "--text",
    "--id",
    "--json",
    "--threshold",
    "--top",
    "--pop",
    "--no-pop",
    "--diff",
    "--bold",
]

ENV_AXES = (
    ("E1", "shell x python"),
    ("E2", "locale / encoding"),
    ("E3", "stdin kind"),
    ("E4", "stdout kind and colour"),
    ("E5", "stderr kind"),
    ("E6", "cwd"),
    ("E7", "HOME / default db path"),
    ("E8", "input size and content"),
    ("E9", "concurrency"),
    ("E10", "signals"),
    ("E11", "process environment"),
)


def write_ledger(
    path: Path,
    rows: list[Row],
    out_dir: str,
    skipped: list[Skipped],
    missing_shells: list[str],
) -> None:
    """Write the human-readable ledger of one run."""
    lines = [
        "# CLI matrix ledger",
        "",
        f"{len(rows)} executions, {len({r['id'] for r in rows})} cells.",
        "",
    ]
    lines += _family_table(rows)
    lines += _skip_section(skipped, missing_shells)
    for verdict in ("FLAG", "OBSERVE"):
        lines += [f"## {verdict}", ""]
        lines += [
            _detail_line(row, out_dir) for row in rows if row["verdict"] == verdict
        ]
        lines.append("")
    lines += [
        "## All cells",
        "",
        "| id | shell | py | description | exit | verdict |",
        "|---|---|---|---|---|---|",
    ]
    lines += [
        f"| {r['id']} | {r['shell']} | {r['py']} |"
        f" {r['desc'].replace('|', '/')} | {r['rc']} | {r['verdict']} |"
        for r in rows
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _family_table(rows: list[Row]) -> list[str]:
    """A verdict count per family."""
    counts = Counter((r["fam"], r["verdict"]) for r in rows)
    families = sorted({r["fam"] for r in rows})
    return (
        ["| family | PASS | OBSERVE | FLAG |", "|---|---|---|---|"]
        + [
            f"| {fam} | {counts[(fam, 'PASS')]} |"
            f" {counts[(fam, 'OBSERVE')]} | {counts[(fam, 'FLAG')]} |"
            for fam in families
        ]
        + [""]
    )


def _skip_section(skipped: list[Skipped], missing_shells: list[str]) -> list[str]:
    """What did not run, and why -- a skip is never a pass."""
    lines = ["## Skipped", ""]
    if missing_shells:
        lines.append(
            f"- shells not installed on this machine: {', '.join(missing_shells)}"
        )
    by_reason: dict[str, list[str]] = {}
    for item in skipped:
        by_reason.setdefault(item.reason, []).append(
            f"{item.id} [{item.shell}/{item.py}]"
        )
    for reason, ids in sorted(by_reason.items()):
        lines.append(
            f"- {reason}: {len(ids)} executions ({', '.join(ids[:8])}"
            + (", ..." if len(ids) > 8 else "")
            + ")"
        )
    if len(lines) == 2:
        lines.append("- nothing skipped")
    lines.append("")
    return lines


def _detail_line(row: Row, out_dir: str) -> str:
    """One bullet describing a single flagged or observed run."""
    err_lines = row["err"].strip().splitlines()
    first_err = err_lines[0] if err_lines else ""
    notes = f"; **{'; '.join(row['notes'])}**" if row["notes"] else ""
    return (
        f"- `{row['id']}` [{row['shell']}/{row['py']}] {row['desc']}"
        f" -> exit {row['rc']};"
        f" out={norm(row['out'], row['work'], out_dir)[:70]!r};"
        f" err={norm(first_err, row['work'], out_dir)[:90]!r}{notes}"
    )


def write_coverage(path: Path, rows: list[Row], cells: dict[str, Cell]) -> None:
    """Write the checklist of what the run actually exercised."""
    ran = {row["id"] for row in rows}
    lines = [
        "# Coverage checklist (computed from the cells that ran)",
        "",
        "| subcommand | flag | cells | shells | pythons |",
        "|---|---|---|---|---|",
    ]
    for sub, flags in UNIVERSE.items():
        for flag in flags:
            ids = [
                c.id
                for c in cells.values()
                if f"{sub}:{flag}" in c.tags and c.id in ran
            ]
            shells = sorted({r["shell"] for r in rows if r["id"] in ids})
            pythons = sorted({r["py"] for r in rows if r["id"] in ids})
            lines.append(
                f"| {sub} | {flag} | {len(ids)} |"
                f" {','.join(shells)} | {','.join(pythons)} |"
            )
    lines += _source_table(ran, cells)
    lines += _flag_pair_table(ran, cells)
    lines += ["", "## Environment axes exercised", ""]
    lines += [
        f"- {fam} {what}:"
        f" {sum(1 for c in cells.values() if c.fam == fam and c.id in ran)} cells"
        for fam, what in ENV_AXES
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _source_table(ran: set[str], cells: dict[str, Cell]) -> list[str]:
    """How many cells fed each command from each input source."""
    lines = [
        "",
        "## Input sources per command (cells)",
        "",
        "| command | " + " | ".join(SOURCES) + " |",
        "|---|" + "---|" * len(SOURCES),
    ]
    for cmd in ["match"] + PREDS:
        counts = [
            str(sum(1 for c in cells.values() if _feeds(c, ran, cmd, src)))
            for src in SOURCES
        ]
        lines.append(f"| {cmd} | " + " | ".join(counts) + " |")
    return lines


def _feeds(cell: Cell, ran: set[str], cmd: str, src: str) -> bool:
    """True when *cell* ran and fed *cmd* from input source *src*."""
    if cell.id not in ran or f"src:{src}" not in cell.tags:
        return False
    if f"{cmd}:" in " ".join(cell.tags):
        return True
    return cmd in cell.cmd.split("$L")[-1].split()[:4]


def _flag_pair_table(ran: set[str], cells: dict[str, Cell]) -> list[str]:
    """Which pairs of ``match`` flags were ever used together."""
    lines = [
        "",
        "## Pairs of `match` flags exercised together",
        "",
        "| a | b | cells |",
        "|---|---|---|",
    ]
    uncovered: list[tuple[str, str]] = []
    for first, second in itertools.combinations(MATCH_FLAGS, 2):
        count = sum(
            1
            for c in cells.values()
            if c.id in ran
            and f"match:{first}" in c.tags
            and f"match:{second}" in c.tags
        )
        lines.append(f"| {first} | {second} | {count} |")
        if count == 0:
            uncovered.append((first, second))
    lines += ["", f"Uncovered pairs: {uncovered or 'none'}"]
    return lines
