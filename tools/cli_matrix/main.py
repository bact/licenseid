# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Putting a run together: check, plan, execute, judge, report."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

from tools.cli_matrix import baseline as baseline_mod
from tools.cli_matrix.cells import build_cells
from tools.cli_matrix.config import (
    ConfigError,
    RunConfig,
    build_parser,
    configure_args,
    snapshot_protected,
)
from tools.cli_matrix.judge import (
    SLOW_SECONDS,
    differential,
    judge,
    relational,
)
from tools.cli_matrix.model import Cell
from tools.cli_matrix.report import write_coverage, write_ledger
from tools.cli_matrix.runner import DEAD_PROXY, Result, Skipped, execute, plan

#: What the offline launcher must say when the network is scripted down.
SELF_CHECK_MARKER = "fake: connection refused"


def main(argv: list[str] | None = None) -> int:
    """Run the matrix. Returns the process exit status."""
    args = build_parser().parse_args(argv)
    cells = build_cells()
    if args.list:
        # Listing needs no database, no interpreter and no workspace.
        for cell in cells.cells:
            print(f"{cell.id}\t{cell.fam}\t{cell.desc}")
        return 0
    try:
        config = configure_args(args)
    except ConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    try:
        self_check(config)
    except ConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if os.geteuid() == 0:
        print(
            "ERROR: user: invalid: root; several cells create directories under"
            " odd HOME values (/nonexistent, /.local), so run as a normal user",
            file=sys.stderr,
        )
        return 2
    before = snapshot_protected()
    rows, skipped = run(config, cells.cells)
    write_outputs(config, cells.by_id(), rows, skipped)
    after = snapshot_protected()
    changed = sorted(
        path
        for path in before.keys() | after.keys()
        if before.get(path) != after.get(path)
    )
    if changed:
        print(
            "ERROR: real cache: changed during the run; a cell reached it:"
            f" {', '.join(changed)}",
            file=sys.stderr,
        )
        return 2
    return report(config, rows)


def self_check(config: RunConfig) -> None:
    """Prove that ``update`` really goes through the scripted fake.

    If the launcher ever stopped replacing ``requests.get``, every update
    cell would quietly start talking to the real SPDX servers. Scripting
    the network down and insisting on the fake's own wording is the cheapest
    way to keep that from happening unnoticed.
    """
    for interpreter in config.interpreters:
        work = config.workspace.work / f"selfcheck-{interpreter.label}"
        work.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run(
            [
                str(interpreter.launcher),
                "--db",
                str(work / "licenses.db"),
                "update",
            ],
            env={
                "PATH": f"{interpreter.python.parent}:/usr/bin:/bin",
                "HOME": str(config.workspace.home),
                "FAKE_NET": "down",
                "HTTPS_PROXY": DEAD_PROXY,
                "HTTP_PROXY": DEAD_PROXY,
            },
            capture_output=True,
            check=False,
            timeout=120,
        )
        text = proc.stderr.decode("utf-8", "replace")
        if SELF_CHECK_MARKER not in text:
            raise ConfigError(
                f"launcher: invalid: the offline launcher for {interpreter.label}"
                f" did not replace requests.get (no {SELF_CHECK_MARKER!r} in"
                " its output); update cells would reach the network"
            )


def run(config: RunConfig, cells: list[Cell]) -> tuple[list[Result], list[Skipped]]:
    """Execute the planned jobs and attach a verdict to every result."""
    by_id = {cell.id: cell for cell in cells}
    jobs, skipped = plan(config, cells)
    started = time.monotonic()
    results = execute(config, jobs)
    elapsed = time.monotonic() - started
    print(
        f"ran {len(results)} executions of"
        f" {len({r['id'] for r in results})} cells in {elapsed:.0f}s"
        f" ({len(skipped)} skipped)"
    )
    out_dir = str(config.workspace.out)
    disagreements = differential(by_id, results, out_dir)
    rows: list[Result] = []
    for result in results:
        cell = by_id[result["id"]]
        verdict, notes = judge(cell, result)
        extra = disagreements.get((result["id"], result["shell"], result["py"]), [])
        if extra:
            verdict, notes = "FLAG", notes + extra
        rows.append(
            {
                **result,
                "verdict": verdict,
                "notes": notes,
                "fam": cell.fam,
                "desc": cell.desc,
            }
        )
    relational(rows, by_id)
    _mark_slow(rows)
    return rows, skipped


def _mark_slow(rows: list[Result]) -> None:
    """A run that took this long is worth a human's eye even when clean."""
    for row in rows:
        if row["dur"] > SLOW_SECONDS:
            if row["verdict"] == "PASS":
                row["verdict"] = "OBSERVE"
            row["notes"].append(f"slow: {row['dur']}s")


def write_outputs(
    config: RunConfig,
    by_id: dict[str, Cell],
    rows: list[Result],
    skipped: list[Skipped],
) -> None:
    """Write results.json, ledger.md and coverage.md into the output dir."""
    out = config.workspace.out
    (out / "results.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    write_ledger(
        out / "ledger.md",
        rows,
        str(out),
        skipped,
        config.missing_shells,
    )
    write_coverage(out / "coverage.md", rows, by_id)


def report(config: RunConfig, rows: list[Result]) -> int:
    """Print the verdict counts, and the baseline diff when asked for it."""
    counts = Counter(row["verdict"] for row in rows)
    print(f"PASS={counts['PASS']} OBSERVE={counts['OBSERVE']} FLAG={counts['FLAG']}")
    print(f"OUT={config.workspace.out}")
    if config.update_baseline:
        baseline_mod.write_baseline(baseline_mod.BASELINE_PATH, rows)
        print(f"BASELINE_WRITTEN={baseline_mod.BASELINE_PATH}")
        return 0
    if not config.compare:
        return 0
    return _print_diff(rows, baseline_mod.BASELINE_PATH, config.check)


def _print_diff(rows: list[Result], path: Path, check: bool) -> int:
    """Print NEW and FIXED flags; return 1 on a new flag under ``--check``."""
    known = baseline_mod.read_baseline(path)
    new, fixed = baseline_mod.compare(rows, known)
    for key in new:
        print(f"NEW_FLAG {' '.join(key)}")
    for key in fixed:
        print(f"FIXED_FLAG {' '.join(key)}")
    print(f"NEW={len(new)} FIXED={len(fixed)}")
    if new and check:
        return 1
    return 0
