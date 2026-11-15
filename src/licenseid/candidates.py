# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Small operations on the candidates a marker reader gives (moved out
of :mod:`licenseid.markers`, which is at its line ceiling)."""

import re
from collections.abc import Iterable, Iterator
from typing import Final

from licenseid.types import CandidateMatch, Method

# Bounds of the loose License: reader. Each distinct value costs a lookup
# (about 25 us), so 256 are read: 5 was the most in any of 6,455 licence
# texts, and a notice file lists one per package. Each licence that resolves
# is a candidate that Tier 1 and 2 then score at about 18 ms (10,000 lines of
# real IDs took 14 s), so at most 32 licences are kept.
FIELD_VALUES_READ: Final = 256
FIELD_LICENSES_KEPT: Final = 32


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


def first_distinct(matches: Iterable[re.Match[str]], limit: int) -> Iterator[str]:
    """The stripped first group of each of *matches*, each value once, up to
    *limit* values. Lazy: the scan ends at the last value it yields."""
    seen: set[str] = set()
    for match in matches:
        value = match.group(1).strip()
        if value not in seen:
            seen.add(value)
            yield value
            if len(seen) >= limit:
                return
