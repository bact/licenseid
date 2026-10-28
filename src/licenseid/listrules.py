# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The rules of the SPDX License List itself: which entries are in use,
which are kept, and what a deprecated ID points to.

This is the one place of these rules. The database build
(:mod:`licenseid.records`) and, later, the in-memory index apply them
through these functions, so the two cannot drift apart.

Pure: standard library and :mod:`licenseid.types` only. No console, no
normalisation, no database.
"""

from collections.abc import Iterable

from licenseid.types import SpdxExceptionEntry, SpdxLicenseEntry


def is_deprecated(lic: SpdxLicenseEntry) -> bool:
    """Whether the entry is a deprecated ID (a missing flag means in use)."""
    return bool(lic.get("isDeprecatedLicenseId", False))


def active_ids(licenses: Iterable[SpdxLicenseEntry]) -> set[str]:
    """The IDs in use."""
    return {lic["licenseId"] for lic in licenses if not is_deprecated(lic)}


def active_ids_by_name(
    licenses: Iterable[SpdxLicenseEntry],
) -> dict[str, list[str]]:
    """The IDs in use, by case-folded name."""
    by_name: dict[str, list[str]] = {}
    for lic in licenses:
        if not is_deprecated(lic):
            by_name.setdefault(lic["name"].casefold(), []).append(lic["licenseId"])
    return by_name


def kept(lic: SpdxLicenseEntry, has_text: bool) -> bool:
    """Whether the build keeps the licence.

    One with a text is kept; one without is dropped, unless it is
    deprecated: that one keeps a metadata row, so that a lookup of its ID
    can still be redirected.
    """
    return has_text or is_deprecated(lic)


def superseded_license(
    lic: SpdxLicenseEntry,
    active: set[str],
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
        return or_later if or_later in active else None
    holders = active_by_name.get(lic["name"].casefold(), [])
    if len(holders) != 1 or holders[0] in (f"{dep_id}-only", f"{dep_id}-or-later"):
        return None
    return holders[0]


def active_exceptions_by_name(
    exceptions: Iterable[SpdxExceptionEntry],
) -> dict[str, str]:
    """The exception IDs in use, by lower-cased name (``str.lower``, not
    ``casefold``, as the exception rule has always been)."""
    return {
        exc["name"].lower(): exc["licenseExceptionId"]
        for exc in exceptions
        if not exc.get("isDeprecatedLicenseId", False)
    }


def exception_successor(
    exc: SpdxExceptionEntry, active_by_name: dict[str, str]
) -> str | None:
    """The successor of a deprecated exception: the exception in use with
    the same name; ``None`` for one in use or without such a holder."""
    if not exc.get("isDeprecatedLicenseId", False):
        return None
    return active_by_name.get(exc["name"].lower())
