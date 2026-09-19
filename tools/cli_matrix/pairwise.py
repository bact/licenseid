# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Greedy all-pairs (pairwise) combination generator.

Exhaustive coverage of the option space is far too large to run, but most
interaction defects show up in a *pair* of options, so covering every pair
of values at least once is the usual compromise. This is the standard
greedy construction: keep drawing random rows, keep the one that covers
most of the pairs still missing, repeat until none are missing.

The result depends only on *seed*, so the same catalogue is produced on
every machine and two runs stay comparable.
"""

from __future__ import annotations

import itertools
import random
from typing import Any

_CANDIDATES_PER_ROW = 300


def pairwise(factors: dict[str, list[Any]], seed: int = 7) -> list[dict[str, Any]]:
    """Rows covering every pair of values across the *factors* given.

    *factors* maps a factor name to its list of values; insertion order is
    part of the result, so reordering the mapping changes the rows.
    """
    names = list(factors)
    pairs = list(itertools.combinations(names, 2))
    need = {(a, x, b, y) for a, b in pairs for x in factors[a] for y in factors[b]}
    rng = random.Random(seed)
    rows: list[dict[str, Any]] = []

    def draw() -> dict[str, Any]:
        return {name: rng.choice(factors[name]) for name in names}

    def gain_of(row: dict[str, Any]) -> int:
        return sum(1 for a, b in pairs if (a, row[a], b, row[b]) in need)

    while need:
        best = draw()
        gain = gain_of(best)
        for _ in range(_CANDIDATES_PER_ROW - 1):
            row = draw()
            row_gain = gain_of(row)
            if row_gain > gain:
                best, gain = row, row_gain
        rows.append(best)
        for a, b in pairs:
            need.discard((a, best[a], b, best[b]))
    return rows
