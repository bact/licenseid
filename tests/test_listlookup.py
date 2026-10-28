# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``ListLookup``: the resolver reads a list through the protocol alone."""

import contextlib
from collections.abc import Callable, Generator, Iterator
from typing import cast

import pytest
from matcher_db import Lic, seeded_db
from resolver_helpers import GPL2_PLUS

from licenseid import LicenseDatabase, dbcache, listlookup
from licenseid.listlookup import ListLookup, fold_case
from licenseid.resolver import _lookup
from licenseid.types import (
    DatabaseMetadata,
    ExceptionDetails,
    LicenseDetails,
    LicenseNameId,
)

ROWS = (
    Lic("MIT", "MIT License"),
    Lic("Apache-2.0", "Apache License 2.0"),
    Lic("GPL-2.0-or-later", "GNU General Public License v2.0 or later"),
    GPL2_PLUS,
)


class DictList:
    """A minimal ``ListLookup`` over ``Lic`` rows held in a dict."""

    def __init__(self, rows: tuple[Lic, ...]) -> None:
        self._exceptions: dict[str, ExceptionDetails] = {}
        self._rows = {fold_case(row.license_id): row for row in rows}

    @contextlib.contextmanager
    def _block(self) -> Iterator[None]:
        """One block of queries; nothing to open."""
        yield

    def reading(self) -> contextlib.AbstractContextManager[None]:
        """One block of queries."""
        return self._block()

    def get_license_details(self, license_id: str) -> LicenseDetails | None:
        """The row of an ID, ASCII case folded."""
        row = self._rows.get(fold_case(license_id.strip()))
        if row is None:
            return None
        return cast(
            LicenseDetails,
            {
                "license_id": row.license_id,
                "name": row.name,
                "is_deprecated": row.is_deprecated,
                "superseded_by": row.superseded_by,
            },
        )

    def get_exception_details(self, exception_id: str) -> ExceptionDetails | None:
        """No exceptions in this list."""
        return self._exceptions.get(exception_id)

    def get_names_by_key(
        self, key: Callable[[str], str]
    ) -> dict[str, list[LicenseNameId]]:
        """The rows by key of their IDs."""
        index: dict[str, list[LicenseNameId]] = {}
        for row in self._rows.values():
            record = LicenseNameId(
                license_id=row.license_id,
                name=row.name,
                is_deprecated=row.is_deprecated,
                norm_license_id=row.license_id,
                norm_name=row.name,
                is_spdx=row.is_spdx,
                is_osi_approved=row.is_osi_approved,
                is_fsf_libre=row.is_fsf_libre,
            )
            index.setdefault(key(row.license_id), []).append(record)
        return index

    def get_active_ids_by_name(self) -> dict[str, list[str]]:
        """The IDs in use by case-folded name."""
        found: dict[str, list[str]] = {}
        for row in self._rows.values():
            if not row.is_deprecated:
                found.setdefault(row.name.casefold(), []).append(row.license_id)
        return found

    def get_deprecated_mappings(self) -> dict[str, str]:
        """Each deprecated ID with its successor."""
        return {
            row.license_id: row.superseded_by
            for row in self._rows.values()
            if row.is_deprecated and row.superseded_by
        }

    def get_metadata(self) -> DatabaseMetadata:
        """The list version."""
        return cast(DatabaseMetadata, {"license_list_version": "3.30"})


@pytest.fixture(name="db")
def _db() -> Generator[LicenseDatabase, None, None]:
    """A database with the same rows."""
    for path in seeded_db("test_listlookup", ROWS):
        yield LicenseDatabase(path, create=False)


def _accepts(lookup: ListLookup) -> None:
    """Mypy checks that each argument below satisfies the protocol."""
    with lookup.reading():
        lookup.get_metadata()


def test_the_database_and_the_fake_satisfy_the_protocol(
    db: LicenseDatabase,
) -> None:
    """Mypy checks the calls; the run proves them."""
    _accepts(db)
    _accepts(DictList(ROWS))


@pytest.mark.parametrize(
    "value",
    ["MIT", "Apache2", "GPL-2.0+", "Foo-9", "Apache License 2.0"],
    ids=lambda v: v,
)
def test_a_fake_list_resolves_as_the_database_does(
    db: LicenseDatabase, value: str
) -> None:
    """The fake answers each value as the database does."""
    fake = DictList(ROWS)
    with db.reading():
        expected = _lookup(db, value)
    with fake.reading():
        assert _lookup(fake, value) == expected


def test_fold_case_is_one_function() -> None:
    """The database cache re-exports the one function."""
    assert dbcache.fold_case is listlookup.fold_case
