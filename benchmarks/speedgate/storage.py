# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The gate "Storage alone" (plan section 6.2): a change of storage alone,
such as task T7's plain table of texts, moves no answer of any set and no
core CPU beyond the noise of two runs of the base.

``compare --storage-alone BASE CAND --twin TWIN``: BASE and TWIN are two runs
of the tree before the change, CAND one of the tree after it."""

import math
from typing import Final

from benchmarks.speedgate.gates import NA, TIMED_SETS, Gate, Sets, _gate
from benchmarks.speedgate.moved import moved_answers
from benchmarks.speedgate.results import cases_of, total_seconds

#: The least spread of CPU taken as noise, whatever the twin gives: two runs
#: of one tree on a shared machine differ by about this much.
NOISE_FLOOR: Final = 0.03


def moved_fields(base: Sets, cand: Sets) -> dict[str, int]:
    """The fields that differ in each timed set and each damage kind both
    runs have."""
    found = {
        name: len(moved_answers(name, cases_of(base[name]), cases_of(cand[name])))
        for name in TIMED_SETS
        if base.get(name) and cand.get(name)
    }
    kinds_a = (base.get("damage") or {}).get("kinds") or {}
    kinds_b = (cand.get("damage") or {}).get("kinds") or {}
    for kind in kinds_a.keys() & kinds_b.keys():
        a, b = cases_of(kinds_a[kind]), cases_of(kinds_b[kind])
        found[f"damage: {kind}"] = len(moved_answers(kind, a, b))
    return found


def cpu_spread(base: Sets, other: Sets) -> float:
    """``|ln(other / base)|`` of the core set's CPU seconds."""
    a = total_seconds(cases_of(base.get("core")))
    b = total_seconds(cases_of(other.get("core")))
    return abs(math.log(b / a)) if a and b else math.inf


def storage_alone(base: Sets, cand: Sets, twin: Sets | None) -> Gate:
    """No field moved in any set both runs have; core CPU of the candidate
    within the spread of the base's twin (at least :data:`NOISE_FLOOR`)."""
    if not twin or not base.get("core") or not cand.get("core"):
        return Gate("Storage alone", NA, "needs the core set of base, twin, cand")
    moved = moved_fields(base, cand)
    differ = {name: n for name, n in moved.items() if n}
    noise = max(cpu_spread(base, twin), math.log(1 + NOISE_FLOOR))
    spread = cpu_spread(base, cand)
    detail = (
        f"{sum(differ.values())} fields differ over {len(moved)} sets and kinds"
        + (f" ({differ})" if differ else "")
        + f"; core CPU off by {math.exp(spread):.3f}x, noise {math.exp(noise):.3f}x"
    )
    return _gate("Storage alone", not differ and spread <= noise, detail)
