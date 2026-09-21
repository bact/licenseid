# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Shared by the ordering tests: a ranked candidate, its IDs."""
# pylint: disable=missing-function-docstring

from licenseid.types import InternalMatch

HEADER_OR_LATER = "either version 2, or (at your option) any later version"


def im(
    license_id: str, score: float, *, deprecated: bool = False, pop: int = 0
) -> InternalMatch:
    """A ranked candidate, as _rank_candidates builds it."""
    return InternalMatch(
        license_id=license_id,
        score=score,
        similarity=score,
        coverage=score,
        base_score=score,
        pop_score=pop,
        is_deprecated=deprecated,
        best_window="",
    )


def ids(ranked: list[InternalMatch]) -> list[str]:
    return [r["license_id"] for r in ranked]
