# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Two small operations on the candidates a marker reader gives (moved out
of :mod:`licenseid.markers`, which is at its line ceiling)."""

from licenseid.types import CandidateMatch, Method


def first_per_license(*groups: list[CandidateMatch]) -> list[CandidateMatch]:
    """The candidates of *groups* in order, the first of each license only."""
    found: dict[str, CandidateMatch] = {}
    for group in groups:
        for candidate in group:
            found.setdefault(candidate["license_id"], candidate)
    return list(found.values())


def found_by(method: Method, candidates: list[CandidateMatch]) -> list[CandidateMatch]:
    """*candidates*, each marked as found by *method*."""
    for candidate in candidates:
        candidate["method"] = method
    return candidates
