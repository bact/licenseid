# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The successor a database build records for a deprecated licence ID."""

import pytest

from licenseid.records import build_records
from licenseid.spdxdata import SpdxData
from licenseid.types import SpdxLicenseEntry


def _entry(license_id: str, name: str, deprecated: bool) -> SpdxLicenseEntry:
    return {
        "licenseId": license_id,
        "name": name,
        "isDeprecatedLicenseId": deprecated,
    }


def _successors(*entries: SpdxLicenseEntry) -> dict[str, str | None]:
    """The superseded_by of each deprecated ID (no texts: each keeps a
    metadata row)."""
    data = SpdxData("3.99", None, entries, (), {})
    return {row[0]: row[8] for row in build_records(data, {}).licenses}


@pytest.mark.parametrize(
    ("entries", "expected"),
    [
        # a rename: one holder of the same name
        (
            [_entry("Old", "Some License", True), _entry("New", "Some License", False)],
            {"Old": "New"},
        ),
        (
            [_entry("Old", "Some License", True), _entry("New", "SOME license", False)],
            {"Old": "New"},
        ),
        # the '+' token
        (
            [
                _entry("GPL-2.0+", "GPL v2 or later", True),
                _entry("GPL-2.0-or-later", "GPL v2 or later", False),
            ],
            {"GPL-2.0+": "GPL-2.0-or-later"},
        ),
        # the -only / -or-later split of a bare ID is no rename
        (
            [
                _entry("GPL-2.0", "GPL v2 only", True),
                _entry("GPL-2.0-only", "GPL v2 only", False),
            ],
            {"GPL-2.0": None},
        ),
        (
            [
                _entry("X-1.0", "X v1", True),
                _entry("X-1.0-or-later", "X v1", False),
            ],
            {"X-1.0": None},
        ),
        # two holders of the name: no first choice
        (
            [
                _entry("Old", "Some License", True),
                _entry("A", "Some License", False),
                _entry("B", "Some License", False),
            ],
            {"Old": None},
        ),
        # the successor has another name, or none holds the name
        (
            [_entry("Old", "Some License", True), _entry("New", "Other", False)],
            {"Old": None},
        ),
        ([_entry("Old", "Some License", True)], {"Old": None}),
        # a deprecated ID does not hold a name
        (
            [_entry("Old", "Some License", True), _entry("Old2", "Some License", True)],
            {"Old": None, "Old2": None},
        ),
    ],
    ids=[
        "rename",
        "rename-case",
        "plus",
        "bare-only-split",
        "bare-or-later-split",
        "two-holders",
        "other-name",
        "no-holder",
        "deprecated-holder",
    ],
)
def test_the_successor_recorded_for_a_deprecated_id(
    entries: list[SpdxLicenseEntry], expected: dict[str, str | None]
) -> None:
    assert _successors(*entries) == expected
