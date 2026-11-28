# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Read result folders and group their cases by input kind."""

import json
import statistics
from pathlib import Path
from typing import Any, NamedTuple

Cases = dict[str, dict[str, Any]]


def load_folder(folder: Path) -> dict[str, dict[str, Any]]:
    """The result of each set in a folder, by set name (``meta`` too)."""
    out: dict[str, dict[str, Any]] = {}
    for path in sorted(folder.glob("*.json")):
        out[path.stem] = json.loads(path.read_text("utf-8"))
    return out


def kind_of(key: str) -> str:
    """The input kind of a case key: what a time is grouped by."""
    head, _, rest = key.partition(":")
    if head == "long":
        return f"long:{key.rsplit(':', 1)[1]}"
    if head in ("many", "hdr"):
        return f"{head}:{rest.split(':')[0]}"
    if head in ("real", "short", "readme", "notice", "mixed", "cjk", "options"):
        return head
    if head == "stress":
        return key
    return f"roadmap:{head.split()[0]}" if head else key


def cases_of(result: dict[str, Any] | None) -> Cases:
    """The cases of a set result, or none."""
    if not result:
        return {}
    cases: Cases = result.get("cases", {})
    return cases


class KindTime(NamedTuple):
    """CPU of the cases of one kind: how many, seconds, median milliseconds."""

    count: int
    seconds: float
    median_ms: float


def kind_times(cases: Cases) -> dict[str, KindTime]:
    """CPU time of each kind (cases that failed to run are left out)."""
    groups: dict[str, list[float]] = {}
    for key, case in cases.items():
        cpu = case.get("cpu_ms")
        if cpu is not None:
            groups.setdefault(kind_of(key), []).append(float(cpu))
    return {
        kind: KindTime(len(v), sum(v) / 1e3, statistics.median(v))
        for kind, v in sorted(groups.items())
    }


def total_seconds(cases: Cases) -> float:
    """All CPU of a set in seconds."""
    return sum(t.seconds for t in kind_times(cases).values())
