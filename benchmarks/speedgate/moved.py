# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Answers that moved between two runs, and the weak-label counts."""

from collections import Counter
from typing import Any, Final, NamedTuple

from benchmarks.speedgate.model import base_id
from benchmarks.speedgate.results import Cases

FIELDS: Final = ("rows", "texts_row", "texts")
THRESHOLDS: Final = (0.85, 0.7, 0.5)


class Moved(NamedTuple):
    """A case whose answer differs: where, which field, both values."""

    set: str
    key: str
    field: str
    base: Any
    cand: Any


def moved_answers(set_name: str, base: Cases, cand: Cases) -> list[Moved]:
    """Every field of every case that differs, and every case one side lacks
    (as field ``missing``). Times are never compared here."""
    out: list[Moved] = []
    for key in sorted(base.keys() | cand.keys()):
        if key not in base or key not in cand:
            out.append(Moved(set_name, key, "missing", key in base, key in cand))
            continue
        a, b = base[key], cand[key]
        if a.get("error") != b.get("error"):
            out.append(Moved(set_name, key, "error", a.get("error"), b.get("error")))
        for field in FIELDS:
            if field in a and field in b and a[field] != b[field]:
                out.append(Moved(set_name, key, field, a[field], b[field]))
    return out


def top(case: dict[str, Any], threshold: float) -> tuple[str | None, float]:
    """The top answer of a case at or above the bar: ``(expression, score)``
    or ``(None, 0.0)``."""
    rows = case.get("rows") or []
    if rows and rows[0][1] is not None and rows[0][1] >= threshold:
        return rows[0][0], float(rows[0][1])
    return None, 0.0


def label_counts(
    cases: Cases, labels: dict[str, Any], threshold: float
) -> Counter[str]:
    """Agree, other and none of the real files that declare one licence."""
    counts: Counter[str] = Counter()
    for key, ids in labels.items():
        if not ids or len(ids) != 1 or key not in cases:
            continue
        answer, _ = top(cases[key], threshold)
        if answer is None:
            counts["none"] += 1
        elif base_id(answer) == base_id(ids[0]):
            counts["agree"] += 1
        else:
            counts["other"] += 1
    return counts


def fixture_counts(cases: Cases, threshold: float) -> Counter[str]:
    """Right, wrong and none of the long and short fixtures (the ID is in the
    key: ``long:<ID>:<level>``, ``short:<ID>:<field>``)."""
    counts: Counter[str] = Counter()
    for key, case in cases.items():
        if not key.startswith(("long:", "short:")):
            continue
        answer, _ = top(case, threshold)
        if answer is None:
            counts["none"] += 1
        else:
            counts["right" if answer == key.split(":")[1] else "wrong"] += 1
    return counts
