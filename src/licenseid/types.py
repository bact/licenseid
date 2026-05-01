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


class CandidateMatch(TypedDict, total=False):
    """Database record returned by LicenseDatabase.search_candidates()."""

    license_id: Required[str]
    search_text: Required[str]
    word_count: int
    is_spdx: bool
    is_osi_approved: bool
    is_fsf_libre: bool
    is_deprecated: bool
    superseded_by: str
    is_high_usage: bool
    pop_score: int
    score: float


class InternalMatch(TypedDict, total=False):
    """Intermediate ranking state. Not part of the public API."""

    license_id: Required[str]
    score: Required[float]
    similarity: Required[float]
    coverage: Required[float]
    base_score: Required[float]
    pop_score: Required[int]
    is_deprecated: bool
    superseded_by: str
    best_window: Required[str]
    java_verified: bool


class MatchRequest(TypedDict, total=False):
    """Input to AggregatedLicenseMatcher.match()."""

    text: str
    license_id: str
    file_path: str
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
    is_deprecated: bool
    superseded_by: str
    pop_score: Required[int]
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
    isDeprecatedLicenseId: bool


class ExceptionDetails(TypedDict, total=False):
    """Full exception record from LicenseDatabase.get_exception_details()."""

    exception_id: Required[str]
    name: Required[str]
    is_deprecated: Required[bool]
    superseded_by: str


class SpdxExceptionEntry(TypedDict, total=False):
    """Single exception entry from the SPDX exceptions.json file."""

    licenseExceptionId: Required[str]
    name: str
    isDeprecatedLicenseId: bool


class DatabaseMetadata(TypedDict, total=False):
    """Key-value metadata stored in the db_metadata table."""

    license_list_version: str
    release_date: str
    last_check_datetime: str
    last_update_datetime: str
