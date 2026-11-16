# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""
Type definitions for licenseid.
"""

from typing import Literal, TypedDict

from typing_extensions import Required

from licenseid.resolvertypes import ListInfo

# How a match was found: an SPDX-License-Identifier tag, a manifest's license
# field, a license ID (given, the whole input, or a deprecated ID in a few
# words), a license name (or an ID it is only like), or the license text.
Method = Literal["tag", "field", "id", "name", "text"]

# Where `licenseid update` gets the SPDX License List (see
# licenseid.releasesource): "compact" (our bundle, about 1 MB), "upstream"
# (SPDX's release tarball), "packaged" (the snapshot shipped in the wheel), or
# each in turn.
UpdateSource = Literal["auto", "compact", "upstream", "packaged"]


# What detect() does where a licence has an -only and an -or-later form and
# the input does not say which: see licenseid.variants.
Variant = Literal["auto", "as-written", "only", "or-later"]


class Detection(TypedDict):
    """A match as detect() returns it: the same keys for every method.

    ``score`` is 0-1: each method's ranking key, capped to 1, so scores from
    different methods are not on one scale; the list is in ranking order,
    which also orders results that share a score of 1. ``exact`` says
    the answer was found exactly: declared (a tag, a field, an ID; a whole
    value is not exact when a rewrite rule read it, ``Apache License, Version
    2.0``: ``resolve()`` category ``separator``, ``prose_form`` or
    ``version_spelling``), an exact name, or an input equal to the license
    text after normalisation (a filled-in copyright line is a difference); a
    look-alike name or a close text is not. ``similarity`` and ``coverage`` are
    None where nothing was measured (a tag, a field, an ID, a name
    ``resolve()`` reads; a name the name tier matches has no coverage).
    ``coverage`` is the input's words over the license's, so it passes 1 when the input
    is longer. ``expression`` is the answer: one licence ID, or an SPDX
    expression (a tag or a field may declare one), as ``resolve()`` names its
    answer; the detector's own records keep ``license_id``. ``lists`` are
    the lists the answer rests on, in the shape of ``resolve()``'s
    (:class:`licenseid.resolvertypes.ListInfo`): the SPDX License List of
    the database read, its ``source`` ``database``. ``variant_stated`` says
    whether the input states the licence's variant (``-only``, ``-or-later``):
    True for its words or an ID that states it, False for a guess (an
    ``-only`` chosen for a text, or by ``--variant``) or a bare ID kept
    (``GPL-2.0``), None where no licence of the answer has a variant to judge
    (``MIT``); for a compound, False if any operand is, else True.
    """

    expression: str
    method: Method
    exact: bool
    score: float
    similarity: float | None
    coverage: float | None
    is_spdx: bool
    is_osi_approved: bool | None
    is_fsf_libre: bool | None
    lists: list[ListInfo]
    variant_stated: bool | None


class Evidence(TypedDict, total=False):
    """Where the variant of an answer is read from: the *value* as written (a
    declared value: its own words state it) and, for a text or name match,
    whether the input's grant of later versions chose ``-or-later`` (*later*)
    or its "only" chose ``-only`` (*only*). *decided* lists the folded
    ``-only``/``-or-later`` forms licenseid chose for a declared value, which
    the value does not state, whatever else it says. No evidence states
    nothing."""

    value: str
    later: bool
    only: bool
    decided: list[str]


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
    is_osi_approved: bool | None
    is_fsf_libre: bool | None
    # The words the variant of the answer is read from (``variants.stated_of``).
    evidence: Evidence


class LicenseFlags(TypedDict):
    """What SPDX, the OSI and the FSF say of a license or expression."""

    is_spdx: bool
    is_osi_approved: bool | None
    is_fsf_libre: bool | None


class CandidateMatch(TypedDict, total=False):
    """Database record returned by LicenseDatabase.search_candidates()."""

    license_id: Required[str]
    search_text: Required[str]
    word_count: int
    is_spdx: bool
    is_osi_approved: bool | None
    is_fsf_libre: bool | None
    is_deprecated: bool
    superseded_by: str
    is_high_usage: bool
    pop_score: int
    score: float
    method: Method
    # Not exact: a variant licenseid decided, a "+" on a deprecated -with-
    # ID, or a tag a rewrite rule read (ruleread).
    decided: bool
    evidence: Evidence


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
    is_osi_approved: bool | None
    is_fsf_libre: bool | None
    evidence: Evidence


# The licence IDs of ``exclude`` and ``hint``: the kinds of collection
# ``licenseid.detectrequest`` accepts (``ID_COLLECTIONS``), of str.
IdCollection = list[str] | tuple[str, ...] | set[str] | frozenset[str]


class DetectOptions(TypedDict, total=False):
    """The keyword options of LicenseDetector.detect() and
    licenseid.detect(), checked for every input. They act only where
    licence text is matched: exclude, hint, only_spdx and only_common on the
    candidates of free text (Tier 1, markers, mixed-content windows, and for
    exclude a short text's name hit), enable_popularity on the Tier 2
    ranking and its tie-breaker. ``variant`` acts on every input: it says
    what to answer where an ``-only`` and an ``-or-later`` form are
    possible and the input does not state which (:data:`Variant`)."""

    only_spdx: bool
    only_common: bool
    exclude: IdCollection
    hint: IdCollection
    enable_popularity: bool
    variant: Variant


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
    xml_template: str | None  # always NULL
    legacy_template: str
    ignorable_metadata: str


class SpdxLicenseEntry(TypedDict, total=False):
    """Single license entry from the SPDX licenses.json file."""

    licenseId: Required[str]
    name: str
    isOsiApproved: bool
    isFsfLibre: bool
    isDeprecatedLicenseId: bool
    seeAlso: list[str]  # the licence's pages; read by listrules.listed_urls


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
    seeAlso: list[str]  # the exception's pages; read by listrules.listed_urls


class DatabaseMetadata(TypedDict, total=False):
    """Key-value metadata stored in the db_metadata table."""

    license_list_version: str
    release_date: str
    last_check_datetime: str
    last_update_datetime: str
    normalization_version: str
    build_version: str
