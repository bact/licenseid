# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The list of flags that are already known, and the diff against it.

Almost a hundred cells flag on a healthy tree: they are real findings, each
one waiting for a fix, and printing them again on every run would bury the
one new flag that a change just introduced. The baseline records the known
set so a run can answer the only question that matters in review -- what
changed?

The file is one ``<cell-id> <shell>`` per line, sorted, so a version-control
diff of it reads as "this was fixed", "this appeared". The interpreter is not
part of the key: labels are the caller's choice, and a cell that flags on
any interpreter is a known flag.
"""

from __future__ import annotations

import platform
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

#: Where the checked-in baseline lives.
BASELINE_PATH = Path(__file__).resolve().parent / "baseline.txt"

Key = tuple[str, str]
Row = dict[str, Any]


def read_baseline(path: Path) -> set[Key]:
    """The known flags recorded in *path*; empty when there is no file."""
    if not path.is_file():
        return set()
    known: set[Key] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.split("#", 1)[0].strip()
        if not stripped:
            continue
        parts = stripped.split()
        if len(parts) != 2:
            raise ValueError(f"baseline.txt: invalid: {line!r}")
        known.add((parts[0], parts[1]))
    return known


def flag_keys(rows: list[Row]) -> set[Key]:
    """The ``(cell, shell)`` keys that flagged, on any interpreter, in this run."""
    return {(row["id"], row["shell"]) for row in rows if row["verdict"] == "FLAG"}


def ran_keys(rows: list[Row]) -> set[Key]:
    """Every key this run actually executed."""
    return {(row["id"], row["shell"]) for row in rows}


def compare(rows: list[Row], known: set[Key]) -> tuple[list[Key], list[Key]]:
    """``(new, fixed)`` flags, judged only over what this run covered.

    A cell that did not run cannot be called fixed, so a filtered run never
    reports the rest of the matrix as newly clean.
    """
    flags = flag_keys(rows)
    new = sorted(flags - known)
    fixed = sorted((known - flags) & ran_keys(rows))
    return new, fixed


def _today() -> str:
    """Today's date in UTC, so two machines agree on it."""
    return datetime.now(timezone.utc).date().isoformat()


def render(rows: list[Row]) -> str:
    """The baseline file for this run, comment header included."""
    counts = Counter(row["verdict"] for row in rows)
    lines = [
        "# Known FLAG cells of the licenseid CLI matrix.",
        "#",
        "# One '<cell-id> <shell>' per line, sorted. A line",
        "# here means the matrix flags that cell today and a human has seen",
        "# it: it is an open finding, not an accepted behaviour. Remove the",
        "# line when the defect is fixed; `--check` then reports it as FIXED.",
        "#",
        (f"# Generated: {_today()} on {platform.system()} {platform.machine()}"),
        (
            f"# Run: {len(rows)} executions,"
            f" {counts['PASS']} PASS,"
            f" {counts['OBSERVE']} OBSERVE,"
            f" {counts['FLAG']} FLAG"
        ),
        "#",
    ]
    lines += [" ".join(key) for key in sorted(flag_keys(rows))]
    return "\n".join(lines) + "\n"


def write_baseline(path: Path, rows: list[Row]) -> None:
    """Rewrite *path* from this run."""
    path.write_text(render(rows), encoding="utf-8")
