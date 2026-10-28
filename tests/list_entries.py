# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Entries of an SPDX list for tests of the list rules."""

from licenseid.types import SpdxExceptionEntry, SpdxLicenseEntry


def lic_entry(
    license_id: str, name: str = "N", deprecated: bool | None = False
) -> SpdxLicenseEntry:
    """A licence entry; ``None`` leaves the deprecated flag out."""
    entry: SpdxLicenseEntry = {"licenseId": license_id, "name": name}
    if deprecated is not None:
        entry["isDeprecatedLicenseId"] = deprecated
    return entry


def exc_entry(
    exc_id: str, name: str, deprecated: bool | None = False
) -> SpdxExceptionEntry:
    """An exception entry; ``None`` leaves the deprecated flag out."""
    entry: SpdxExceptionEntry = {"licenseExceptionId": exc_id, "name": name}
    if deprecated is not None:
        entry["isDeprecatedLicenseId"] = deprecated
    return entry
