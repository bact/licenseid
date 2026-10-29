# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``resolve()`` gives one answer with and without a database.

The database is the one ``update --source packaged`` builds from the bundle
the test ships (``conftest.bundle_db``); without one, ``resolve()`` reads the
same bundle in memory (``licenseid.listindex``). Only ``lists[*].source``
may differ, and it says which was read.
"""
# pylint: disable=missing-function-docstring

from pathlib import Path

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from packaged_list import (
    database_of,
    fixture_bundle,
    fixture_data,
    list_values,
    masked,
    synthetic_bundle,
)
from release_fakes import ship
from resolver_corpus import changed_answers, changes_report, corpus_rows

from licenseid import LicenseDatabase, resolve
from licenseid.types import SpdxLicenseEntry
from tools.pypi_licence_sample.answer import unescape_field

FAMILIES = sorted(list_values(fixture_data()))


def _differences(db: LicenseDatabase, values: list[str]) -> list[str]:
    """The values whose answer differs with and without *db*, and why."""
    found = []
    for value in values:
        with_db, without = resolve(value, db), resolve(value, source="packaged")
        assert [entry["source"] for entry in with_db["lists"]] == ["database"]
        assert [entry["source"] for entry in without["lists"]] == ["packaged"]
        if masked(with_db) != masked(without):
            found.append(f"{value!r}: {with_db} != {without}")
    return found


@pytest.mark.parametrize("family", FAMILIES)
def test_a_listed_value_is_read_the_same_without_a_database(
    monkeypatch: pytest.MonkeyPatch, bundle_db: LicenseDatabase, family: str
) -> None:
    ship(monkeypatch, fixture_bundle())
    values = list_values(fixture_data())[family]
    assert values
    differences = _differences(bundle_db, values)
    assert not differences, differences


def test_a_corpus_value_is_read_the_same_without_a_database(
    monkeypatch: pytest.MonkeyPatch, bundle_db: LicenseDatabase
) -> None:
    """Every value of the parity corpus and of the PyPI sample."""
    ship(monkeypatch, fixture_bundle())
    values = list(dict.fromkeys(unescape_field(r["value"]) for r in corpus_rows()))
    assert len(values) > 500
    differences = _differences(bundle_db, values)
    assert not differences, differences


def test_the_guard_gives_the_same_answers_on_the_packaged_list(
    monkeypatch: pytest.MonkeyPatch, corpus_db: LicenseDatabase
) -> None:
    """The guard of the pinned answers reads the packaged list too, and finds
    the changes it finds on the corpus database: none unexpected."""
    ship(monkeypatch, fixture_bundle())
    on_database = changed_answers(corpus_db)
    on_packaged = changed_answers(None, source="packaged")
    assert on_packaged == on_database
    assert not changes_report(on_packaged), changes_report(on_packaged)


# --- the kept rows (review gap G8) ---

# An ID in use with no text is not kept, though it is the successor of the
# deprecated rename that has the same name. 3.29.0 has no such ID.
_RENAMED: tuple[SpdxLicenseEntry, ...] = (
    {"licenseId": "Old-1.0", "name": "Foo License 1.0", "isDeprecatedLicenseId": True},
    {"licenseId": "Foo-1.0", "name": "Foo License 1.0"},
    {"licenseId": "MIT", "name": "MIT License"},
)
_RENAMED_TEXTS = {"Old-1.0": "The old text.", "MIT": "The MIT text."}


@pytest.mark.parametrize(
    "value",
    ["Foo License 1.0", "foo license 1.0", "Old-1.0", "old-1.0", "Old-1.0+", "Foo-1.0"],
)
def test_an_id_with_no_text_is_not_kept_without_a_database(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, value: str
) -> None:
    raw = synthetic_bundle(_RENAMED, _RENAMED_TEXTS)
    db = database_of(raw, tmp_path / "renamed.db")
    ship(monkeypatch, raw)
    differences = _differences(db, [value])
    assert not differences, differences


def test_the_rename_is_followed_but_its_name_is_not_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """What the database answers, pinned: the deprecated ID points to its
    successor, but the name names no licence kept in use."""
    ship(monkeypatch, synthetic_bundle(_RENAMED, _RENAMED_TEXTS))
    renamed = resolve("Old-1.0", source="packaged")
    assert (renamed["expression"], renamed["category"]) == (
        "Foo-1.0",
        "deprecated_equal_successor",
    )
    named = resolve("Foo License 1.0", source="packaged")
    assert (named["expression"], named["category"]) == (None, "unresolved")
