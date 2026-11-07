# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Entries of an SPDX list for tests of the list rules."""

from typing import cast

from licenseid.types import SpdxExceptionEntry, SpdxLicenseEntry


def lic_entry(
    license_id: str,
    name: str = "N",
    deprecated: bool | None = False,
    see_also: object = None,
) -> SpdxLicenseEntry:
    """A licence entry; ``None`` leaves the deprecated flag out, and
    *see_also* (any value, as a damaged List may hold) is ``seeAlso``
    unless it is ``None``."""
    entry: SpdxLicenseEntry = {"licenseId": license_id, "name": name}
    if deprecated is not None:
        entry["isDeprecatedLicenseId"] = deprecated
    if see_also is not None:
        entry["seeAlso"] = cast(list[str], see_also)
    return entry


def exc_entry(
    exc_id: str, name: str, deprecated: bool | None = False, see_also: object = None
) -> SpdxExceptionEntry:
    """An exception entry; ``None`` leaves the deprecated flag out, and
    *see_also* is ``seeAlso`` unless it is ``None``."""
    entry: SpdxExceptionEntry = {"licenseExceptionId": exc_id, "name": name}
    if deprecated is not None:
        entry["isDeprecatedLicenseId"] = deprecated
    if see_also is not None:
        entry["seeAlso"] = cast(list[str], see_also)
    return entry
