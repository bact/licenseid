# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Small operations on the candidates a marker reader gives (moved out
of :mod:`licenseid.markers`, which is at its line ceiling)."""

import re
from collections.abc import Iterable, Iterator
from typing import Final

from licenseid.types import CandidateMatch, Method, RawMatch

# Bounds of the loose License: reader. Each distinct value costs a lookup
# (about 25 us), so 256 are read: 5 was the most in any of 6,455 licence
# texts, and a notice file lists one per package. Each licence that resolves
# is a candidate that Tier 1 and 2 then score at about 18 ms (10,000 lines of
# real IDs took 14 s), so at most 48 licences are kept: about 0.9 s at worst.
FIELD_VALUES_READ: Final = 256
FIELD_LICENSES_KEPT: Final = 48


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


def license_sections(text: str) -> list[str]:
    """The sections of *text* that likely contain license information: the
    120 words round each word with "licens" in it."""
    sections: list[str] = []
    words = text.split()
    for i, word in enumerate(words):
        if "licens" in word.lower():
            start = max(0, i - 20)
            end = min(len(words), i + 100)
            sections.append(" ".join(words[start:end]))
    return sections


def as_matches(
    exact: list[CandidateMatch], method: Method | None = None
) -> list[RawMatch]:
    """Convert certain candidates to results: each found by its own method (a
    tag or a field), or by *method*. Nothing is measured."""
    # The detector keeps one candidate per license_id (first_per_license).
    return [
        RawMatch(
            license_id=c["license_id"],
            method=method or c["method"],
            exact=not c.get("narrowed", False),
            variant_guessed=c.get("variant_guessed", False),
            score=1.0,
            similarity=None,
            coverage=None,
            is_spdx=c.get("is_spdx", False),
            is_osi_approved=c.get("is_osi_approved", False),
            is_fsf_libre=c.get("is_fsf_libre", False),
        )
        for c in exact
    ]
