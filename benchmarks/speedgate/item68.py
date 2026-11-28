# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The real files item 68 of the roadmap asks about."""

from benchmarks.speedgate.model import base_id
from benchmarks.speedgate.moved import top
from benchmarks.speedgate.results import Cases

BAR = 0.85


def item68_keys(cases: Cases) -> list[str]:
    """Real files where ``TEXTS`` names exactly one text and the top answer
    is missing (under 0.85) or another licence than that text (compared
    without ``-only``, ``-or-later`` and ``+``). On the 300 real files of
    0.9.4 these are 12 and 11 files; with the 2 files of Pillow that the
    roadmap set holds by name they are the 25 files of the roadmap item."""
    keys = []
    for key, case in cases.items():
        found = (case.get("texts_row") or [None])[0]
        if not key.startswith("real:") or not found or len(found) != 1:
            continue
        answer, _ = top(case, BAR)
        if answer is None or base_id(answer) != base_id(found[0]):
            keys.append(key)
    return sorted(keys)
