# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The rows of the ``licenses``, ``license_index`` and ``exceptions`` tables,
built in memory from one :class:`licenseid.spdxdata.SpdxData`.

No database access and no network: whatever the source of the data (an
upstream tarball, a bundle), the same input gives the same rows. The text of
every licence is normalised once, here, into the fingerprint that is indexed.
"""

from typing import NamedTuple

from licenseid.console import status
from licenseid.normalize import normalize_text
from licenseid.spdxdata import SpdxData
from licenseid.types import SpdxExceptionEntry, SpdxLicenseEntry

# Version of the rules that turn a release into rows. A database stores the
# version it was built with; `update` rebuilds one built with older rules.
# Version 2: a renamed deprecated ID records its successor (StandardML-NJ).
BUILD_VERSION = "2"

# (license_id, name, xml_template, is_spdx, is_osi, is_fsf,
#  is_high_usage, is_deprecated, superseded_by, pop_score, word_count,
#  norm_license_id, norm_name)
# xml_template is always None. The column stays in the schema.
LicenseInsertRecord = tuple[
    str,
    str,
    str | None,
    bool,
    bool,
    bool,
    bool,
    bool,
    str | None,
    int,
    int,
    str,
    str,
]
IndexInsertRecord = tuple[str, str]
# (exception_id, name, is_deprecated, superseded_by)
ExceptionInsertRecord = tuple[str, str, bool, str | None]


class Records(NamedTuple):
    """The three record lists of one release, ready to insert."""

    licenses: list[LicenseInsertRecord]
    index_entries: list[IndexInsertRecord]
    exceptions: list[ExceptionInsertRecord]


def build_records(data: SpdxData, popularity_map: dict[str, int]) -> Records:
    """Build the record lists for insertion (no DB access)."""
    licenses, index = _license_records(data, popularity_map)
    return Records(licenses, index, _exception_records(data.exceptions))


def _license_records(
    data: SpdxData, popularity_map: dict[str, int]
) -> tuple[list[LicenseInsertRecord], list[IndexInsertRecord]]:
    """Licence rows and index rows. A licence without a text is dropped, unless
    it is deprecated: that one keeps a metadata row (no index entry), so that
    a lookup of its ID can still be redirected."""
    license_records: list[LicenseInsertRecord] = []
    index_records: list[IndexInsertRecord] = []

    status("\nPreparing license data...", end="")
    # Build the superseded_by mapping at DB build time so runtime lookups
    # are O(1).
    active_ids: set[str] = {
        lic["licenseId"]
        for lic in data.licenses
        if not lic.get("isDeprecatedLicenseId", False)
    }
    active_by_name = _active_ids_by_name(data.licenses)

    for i, lic in enumerate(data.licenses):
        is_deprecated = bool(lic.get("isDeprecatedLicenseId", False))
        superseded_by = (
            _superseded_license(lic, active_ids, active_by_name)
            if is_deprecated
            else None
        )
        res = _prepare_license_record(
            lic, data.texts.get(lic["licenseId"]), popularity_map, superseded_by
        )
        if res:
            license_records.append(res[0])
            index_records.append(res[1])
        elif is_deprecated:
            # Text absent for this deprecated ID (some SPDX releases omit
            # them).  Still store the metadata row so redirect lookups work.
            license_records.append(_metadata_only_record(lic, superseded_by))

        if (i + 1) % 100 == 0 or (i + 1) == len(data.licenses):
            status(".", end="")
    return license_records, index_records


def _active_ids_by_name(
    licenses: tuple[SpdxLicenseEntry, ...],
) -> dict[str, list[str]]:
    """The IDs in use, by case-folded name."""
    by_name: dict[str, list[str]] = {}
    for lic in licenses:
        if not lic.get("isDeprecatedLicenseId", False):
            by_name.setdefault(lic["name"].casefold(), []).append(lic["licenseId"])
    return by_name


def _superseded_license(
    lic: SpdxLicenseEntry,
    active_ids: set[str],
    active_by_name: dict[str, list[str]],
) -> str | None:
    """The successor of a deprecated licence, or ``None``.

    Two cases are certain:

    - the SPDX '+' token: GPL-2.0+ -> GPL-2.0-or-later;
    - a rename: the one ID in use with the same name (StandardML-NJ ->
      SMLNJ). The List does not record a successor, but an unchanged name
      with one holder leaves no other reading.

    Everything else stays NULL: a bare deprecated ID that the List split
    into -only and -or-later (GPL-2.0, whose name equals GPL-2.0-only's)
    cannot be resolved without the granting declaration, and an ID replaced
    by an expression or by a licence of another name is no rename. The split
    is therefore refused by ID, not left to the name check.
    """
    dep_id = lic["licenseId"]
    if dep_id.endswith("+"):
        or_later = dep_id[:-1] + "-or-later"  # strip the '+' operator token
        return or_later if or_later in active_ids else None
    holders = active_by_name.get(lic["name"].casefold(), [])
    if len(holders) != 1 or holders[0] in (f"{dep_id}-only", f"{dep_id}-or-later"):
        return None
    return holders[0]


def _metadata_only_record(
    lic: SpdxLicenseEntry, superseded_by: str | None
) -> LicenseInsertRecord:
    """The row of a deprecated licence that has no text."""
    dep_name = lic.get("name", lic["licenseId"])
    return (
        lic["licenseId"],
        dep_name,
        None,  # xml_template
        True,  # is_spdx
        False,  # is_osi_approved
        False,  # is_fsf_libre
        False,  # is_high_usage
        True,  # is_deprecated
        superseded_by,
        1,  # pop_score
        0,  # word_count
        normalize_text(lic["licenseId"]),
        normalize_text(dep_name),
    )


def _exception_records(
    exceptions_data: tuple[SpdxExceptionEntry, ...],
) -> list[ExceptionInsertRecord]:
    """Exception rows; a deprecated one points to the active exception that
    has the same name (case-folded)."""
    status("\nPreparing exception data...", end="")
    name_to_exception: dict[str, str] = {}
    for exc in exceptions_data:
        if not exc.get("isDeprecatedLicenseId", False):
            name_to_exception[exc["name"].lower()] = exc["licenseExceptionId"]

    exception_records: list[ExceptionInsertRecord] = []
    for exc in exceptions_data:
        is_deprecated = exc.get("isDeprecatedLicenseId", False)
        superseded_by = None
        if is_deprecated:
            superseded_by = name_to_exception.get(exc["name"].lower())
        exception_records.append(
            (exc["licenseExceptionId"], exc["name"], is_deprecated, superseded_by)
        )
    return exception_records


def _prepare_license_record(
    lic: SpdxLicenseEntry,
    text: str | None,
    popularity_map: dict[str, int],
    superseded_by: str | None = None,
) -> tuple[LicenseInsertRecord, IndexInsertRecord] | None:
    """The row and the index entry of one licence, or ``None`` when it has no
    *text* (an empty text is a text)."""
    if text is None:
        return None

    license_id = lic["licenseId"]
    fingerprint = normalize_text(text)
    word_count = len(fingerprint.split())
    is_osi = lic.get("isOsiApproved", False)
    is_fsf = lic.get("isFsfLibre", False)

    baseline = 100 if (is_osi or is_fsf) else 1
    pop_count = popularity_map.get(license_id, 0)
    pop_score = max(baseline, pop_count)

    # High usage: OSI, FSF, or significant popularity
    is_high_usage = is_osi or is_fsf or pop_score > 500

    name = lic.get("name", "")
    license_record: LicenseInsertRecord = (
        license_id,
        name,
        None,  # xml_template
        True,  # is_spdx
        is_osi,
        is_fsf,
        is_high_usage,
        bool(lic.get("isDeprecatedLicenseId", False)),
        superseded_by,
        pop_score,
        word_count,
        normalize_text(license_id),
        normalize_text(name),
    )
    return license_record, (license_id, fingerprint)
