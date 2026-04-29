# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
Type definitions for licenseid.
"""

from typing import TypedDict


class LicenseMatch(TypedDict, total=False):
    """Public representation of a license match result."""

    license_id: str
    score: float
    similarity: float
    coverage: float
    is_spdx: bool
    is_osi_approved: bool
    is_fsf_libre: bool
    best_window: str


class CandidateMatch(TypedDict, total=False):
    """Database record for a license candidate."""

    license_id: str
    search_text: str
    word_count: int
    is_spdx: bool
    is_high_usage: bool
    is_osi_approved: bool
    is_fsf_libre: bool
    popularity_score: int


class InternalMatch(TypedDict, total=False):
    """Intermediate state for ranking matches."""

    license_id: str
    score: float
    similarity: float
    coverage: float
    base_score: float
    pop_score: int
    best_window: str
    is_spdx: bool
    is_osi_approved: bool
    is_fsf_libre: bool
    java_verified: bool
