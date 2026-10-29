# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The SPDX 3.29.0 List of the fixtures as a bundle, for the tests that read
``resolve()`` with and without a database.

Every licence of ``fixtures/license-list`` gets a short text, so the build
keeps it as the real 3.29.0 does (each ID in use has a text there), and the
database built from this bundle holds the rows of ``resolver_corpus``'s.
Import as ``from packaged_list import ...``.
"""

import copy
from collections.abc import Iterable, Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest
import requests
from release_fakes import ship
from resolver_corpus import EXCEPTION_LIST, LICENSE_LIST, list_meta, list_rows

from licenseid.database import LicenseDatabase
from licenseid.spdxdata import SpdxData, to_bundle
from licenseid.types import SpdxExceptionEntry, SpdxLicenseEntry


def fixture_data() -> SpdxData:
    """The List of the fixtures, each licence with a text."""
    version, release_date = list_meta(LICENSE_LIST)
    licenses: list[SpdxLicenseEntry] = [
        {
            "licenseId": str(row[0]),
            "name": str(row[1]),
            "isDeprecatedLicenseId": bool(row[2]),
        }
        for row in list_rows(LICENSE_LIST, "licenses")
    ]
    exceptions: list[SpdxExceptionEntry] = [
        {
            "licenseExceptionId": str(row[0]),
            "name": str(row[1]),
            "isDeprecatedLicenseId": bool(row[2]),
        }
        for row in list_rows(EXCEPTION_LIST, "exceptions")
    ]
    return SpdxData(
        version=version,
        release_date=release_date,
        licenses=tuple(licenses),
        exceptions=tuple(exceptions),
        texts=MappingProxyType(
            {lic["licenseId"]: f"The text of {lic['name']}." for lic in licenses}
        ),
    )


def fixture_bundle() -> bytes:
    """:func:`fixture_data` as the bundle a wheel ships."""
    return to_bundle(fixture_data())


def synthetic_bundle(
    licenses: Iterable[SpdxLicenseEntry],
    texts: Mapping[str, str],
    exceptions: Iterable[SpdxExceptionEntry] = (),
) -> bytes:
    """A bundle of *licenses* and *exceptions* (SPDX entries), version 9.99,
    with *texts* by licence ID; an ID that is not in *texts* has none."""
    return to_bundle(
        SpdxData(
            version="9.99",
            release_date=None,
            licenses=tuple(licenses),
            exceptions=tuple(exceptions),
            texts=MappingProxyType(dict(texts)),
        )
    )


def database_of(raw: bytes, path: Path) -> LicenseDatabase:
    """The database ``update --source packaged`` builds at *path* from the
    bundle *raw*, opened as ``resolve()`` opens one. No network: the source
    makes no call, and ``requests.get`` fails if one is made."""
    with pytest.MonkeyPatch.context() as patch:
        ship(patch, raw)
        patch.setattr(requests, "get", _no_network)
        LicenseDatabase(str(path)).update_from_remote(
            source="packaged", use_cache=False
        )
    return LicenseDatabase(str(path), create=False)


def _no_network(*_: object, **__: object) -> None:
    raise requests.ConnectionError("offline: packaged_list")


def masked(result: Mapping[str, Any]) -> dict[str, Any]:
    """*result* without ``lists[*].source``, the one key that says where the
    list was read."""
    found = copy.deepcopy(dict(result))
    for entry in found["lists"]:
        entry.pop("source")
    return found


def list_values(data: SpdxData) -> dict[str, list[str]]:
    """The values to resolve with and without a database, by family: every
    ID, in lower case, with ``+``, every name, every deprecated ID, and three
    forms of a ``WITH`` per exception."""
    ids = [lic["licenseId"] for lic in data.licenses]
    exceptions = [exc["licenseExceptionId"] for exc in data.exceptions]
    return {
        "id": ids,
        "lower": [i.lower() for i in ids],
        "plus": [f"{i}+" for i in ids],
        "name": [lic["name"] for lic in data.licenses],
        "deprecated": [
            lic["licenseId"]
            for lic in data.licenses
            if lic.get("isDeprecatedLicenseId", False)
        ],
        "exception": [
            form
            for exc, entry in zip(exceptions, data.exceptions)
            for form in (
                f"MIT WITH {exc}",
                f"GPL-2.0 WITH {exc.lower()}",
                f"GPL-2.0-or-later WITH {entry['name']}",
            )
        ],
    }
