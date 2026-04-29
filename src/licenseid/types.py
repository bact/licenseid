# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
Type definitions for licenseid.
"""

from typing import TypedDict
from typing_extensions import Required


class LicenseMatch(TypedDict, total=False):
    """Public representation of a license match result."""

    license_id: Required[str]
    score: Required[float]
    similarity: Required[float]
    coverage: Required[float]
    is_spdx: bool
    is_osi_approved: bool
    is_fsf_libre: bool
    best_window: str


class CandidateMatch(TypedDict):
    """Database record returned by LicenseDatabase.search_candidates()."""

    license_id: str
    name: str
    norm_license_id: str
    norm_name: str
    search_text: str
    word_count: int
    is_spdx: bool
    is_high_usage: bool
    is_osi_approved: bool
    is_fsf_libre: bool
    popularity_score: int


class InternalMatch(TypedDict, total=False):
    """Intermediate ranking state. Not part of the public API."""

    license_id: Required[str]
    score: Required[float]
    similarity: Required[float]
    coverage: Required[float]
    base_score: Required[float]
    pop_score: Required[int]
    best_window: Required[str]
    java_verified: bool


class MatchRequest(TypedDict, total=False):
    """Input to AggregatedLicenseMatcher.match() when passing a dict."""

    text: Required[str]
    only_spdx: bool
    only_common: bool
    exclude: list[str]
    hint: list[str]
    enable_java: bool
    enable_popularity: bool


class LicenseNameId(TypedDict):
    """License ID and display name pair."""

    license_id: str
    name: str


class LicenseDetails(TypedDict, total=False):
    """Full license record from LicenseDatabase.get_license_details()."""

    license_id: Required[str]
    name: Required[str]
    is_spdx: Required[bool]
    is_osi_approved: Required[bool]
    is_fsf_libre: Required[bool]
    is_high_usage: Required[bool]
    popularity_score: Required[int]
    word_count: Required[int]
    xml_template: str
    legacy_template: str
    ignorable_metadata: str


class SpdxLicenseEntry(TypedDict, total=False):
    """Single license entry from the SPDX licenses.json file."""

    licenseId: Required[str]
    name: str
    isOsiApproved: bool
    isFsfLibre: bool


class DatabaseMetadata(TypedDict, total=False):
    """Key-value metadata stored in the db_metadata table."""

    license_list_version: str
    release_date: str
    last_check_datetime: str
    last_update_datetime: str
