# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
Type definitions for licenseid.
"""

from typing import Literal, TypedDict

from typing_extensions import Required

# How a match was found: an SPDX-License-Identifier tag, a manifest's license
# field, a license ID (given, the whole input, or a deprecated ID in a few
# words), a license name (or an ID it is only like), or the license text.
Method = Literal["tag", "field", "id", "name", "text"]


class LicenseMatch(TypedDict):
    """A match as match() returns it: the same keys for every method.

    ``score`` is 0-1: each method's ranking key, capped to 1, so scores from
    different methods are not on one scale; the list is in ranking order,
    which also orders results that share a score of 1. ``exact`` says
    the answer was found exactly: declared (a tag, a field, an ID), an exact
    name, or an input equal to the license text after normalisation (a
    filled-in copyright line is a difference); a look-alike name or a close
    text is not. ``similarity`` and ``coverage`` are None where nothing was
    measured (a tag, a field, an ID; a name has no coverage). ``coverage``
    is the input's words over the license's, so it passes 1 when the input
    is longer.
    """

    license_id: str
    method: Method
    exact: bool
    score: float
    similarity: float | None
    coverage: float | None
    is_spdx: bool
    is_osi_approved: bool
    is_fsf_libre: bool


class RawMatch(TypedDict, total=False):
    """A match as a tier builds it, with its raw ranking score (above 1 for
    a name or ID hit, or a close text with its bonuses). Not part of the
    public API."""

    license_id: Required[str]
    method: Required[Method]
    exact: Required[bool]
    score: Required[float]
    similarity: Required[float | None]
    coverage: Required[float | None]
    is_spdx: bool
    is_osi_approved: bool
    is_fsf_libre: bool


class LicenseFlags(TypedDict):
    """What SPDX, the OSI and the FSF say of a license or expression."""

    is_spdx: bool
    is_osi_approved: bool
    is_fsf_libre: bool


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
    method: Method


class InternalMatch(TypedDict, total=False):
    """Intermediate ranking state. Not part of the public API."""

    license_id: Required[str]
    method: Required[Method]
    exact: Required[bool]
    score: Required[float]
    similarity: Required[float]
    coverage: Required[float]
    base_score: Required[float]
    pop_score: Required[int]
    is_deprecated: bool
    superseded_by: str
    best_window: Required[str]
    is_spdx: bool
    is_osi_approved: bool
    is_fsf_libre: bool


class MatchRequest(TypedDict, total=False):
    """Input to AggregatedLicenseMatcher.match()."""

    text: str
    license_id: str
    file_path: str
    only_spdx: bool
    only_common: bool
    exclude: list[str]
    hint: list[str]
    enable_popularity: bool


class LicenseNameId(TypedDict):
    """License ID and display name pair."""

    license_id: str
    name: str
    is_deprecated: bool
    norm_license_id: str
    norm_name: str
    is_spdx: bool
    is_osi_approved: bool
    is_fsf_libre: bool


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
