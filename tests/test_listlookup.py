# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``ListLookup``: the resolver reads a list through the protocol alone."""

import contextlib
import sqlite3
from collections.abc import Callable, Generator, Iterator, Mapping, Sequence
from typing import cast

import pytest
from matcher_db import Lic, seeded_db
from resolver_helpers import GPL2_PLUS

from licenseid import LicenseDatabase, shorttext
from licenseid.identifiers import normalize_identifier
from licenseid.listlookup import (
    ListedException,
    ListedLicense,
    ListedMetadata,
    ListedName,
    ListLookup,
    fold_case,
)
from licenseid.resolver import _list_info, _lookup
from licenseid.shorttext import match_version_key
from licenseid.types import ExceptionDetails

ROWS = (
    Lic("MIT", "MIT License"),
    Lic("Apache-2.0", "Apache License 2.0"),
    Lic("GPL-2.0-or-later", "GNU General Public License v2.0 or later"),
    GPL2_PLUS,
)
LIST_VERSION = "3.30"
EXCEPTIONS = (
    cast(
        ExceptionDetails,
        {
            "exception_id": "Nokia-Qt-exception-1.1",
            "name": "Nokia Qt LGPL exception 1.1",
            "is_deprecated": True,
            "superseded_by": "Qt-LGPL-exception-1.1",
        },
    ),
    cast(
        ExceptionDetails,
        {
            "exception_id": "Qt-LGPL-exception-1.1",
            "name": "Qt LGPL exception 1.1",
            "is_deprecated": False,
            "superseded_by": None,
        },
    ),
)


class DictList:
    """A minimal ``ListLookup`` over ``Lic`` rows held in a dict."""

    def __init__(
        self,
        rows: tuple[Lic, ...],
        version: str = LIST_VERSION,
        exceptions: tuple[ExceptionDetails, ...] = EXCEPTIONS,
    ) -> None:
        self._version = version
        self._exceptions = {fold_case(e["exception_id"]): e for e in exceptions}
        self._rows = {fold_case(row.license_id): row for row in rows}

    @contextlib.contextmanager
    def _block(self) -> Iterator[None]:
        """One block of queries; nothing to open."""
        yield

    def reading(self) -> contextlib.AbstractContextManager[None]:
        """One block of queries."""
        return self._block()

    def get_license_details(self, license_id: str) -> ListedLicense | None:
        """The row of an ID, ASCII case folded: the fields the resolver
        reads, no more (an index has no popularity or word count)."""
        row = self._rows.get(fold_case(license_id.strip()))
        if row is None:
            return None
        found = ListedLicense(license_id=row.license_id)
        if row.is_deprecated:
            found["is_deprecated"] = True
        if row.superseded_by:
            found["superseded_by"] = row.superseded_by
        return found

    def get_exception_details(self, exception_id: str) -> ListedException | None:
        """The exceptions of the list, as the resolver reads them."""
        row = self._exceptions.get(fold_case(exception_id.strip()))
        if row is None:
            return None
        found = ListedException(
            exception_id=row["exception_id"], is_deprecated=row["is_deprecated"]
        )
        if row.get("superseded_by"):
            found["superseded_by"] = str(row["superseded_by"])
        return found

    def get_names_by_key(
        self, key: Callable[[str], str]
    ) -> Mapping[str, Sequence[ListedName]]:
        """The rows by key of their IDs."""
        index: dict[str, list[ListedName]] = {}
        for row in self._rows.values():
            record = ListedName(
                license_id=row.license_id, is_deprecated=row.is_deprecated
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
        found = {
            row.license_id: row.superseded_by
            for row in self._rows.values()
            if row.is_deprecated and row.superseded_by
        }
        for exc in self._exceptions.values():
            if exc["is_deprecated"] and exc.get("superseded_by"):
                found[exc["exception_id"]] = str(exc["superseded_by"])
        return found

    def get_metadata(self) -> ListedMetadata:
        """The list version."""
        return ListedMetadata(license_list_version=self._version)


@pytest.fixture(name="db")
def _db() -> Generator[LicenseDatabase, None, None]:
    """A database with the same rows."""
    names = [e["exception_id"] for e in EXCEPTIONS]
    for path in seeded_db("test_listlookup", ROWS, names):
        with sqlite3.connect(path, uri=True) as conn:
            conn.execute(
                "UPDATE exceptions SET is_deprecated = 1, superseded_by = ?"
                " WHERE exception_id = ?",
                ("Qt-LGPL-exception-1.1", "Nokia-Qt-exception-1.1"),
            )
            conn.execute(
                "INSERT OR REPLACE INTO db_metadata (key, value) VALUES (?, ?)",
                ("license_list_version", LIST_VERSION),
            )
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
    [
        "MIT",
        "Apache2",
        "GPL-2.0+",
        "Foo-9",
        "Apache License 2.0",
        "GPL-2.0+ WITH Nokia-Qt-exception-1.1",
        "mit with qt-lgpl-exception-1.1",
        "MIT WITH Nokia-Qt-exception-1.1",
        "MIT WITH Bar-exception",
    ],
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


@pytest.mark.parametrize(
    "value",
    [
        "GPL-2.0+ WITH Nokia-Qt-exception-1.1",
        "gpl-2.0+",
        " nokia-qt-exception-1.1",
        "MIT WITH qt-lgpl-exception-1.1 ",
    ],
    ids=lambda v: v.strip(),
)
def test_normalize_identifier_agrees_on_a_fake_list(
    db: LicenseDatabase, value: str
) -> None:
    """The deprecated-mapping and exception paths read the fake as the base."""
    assert normalize_identifier(value, DictList(ROWS)) == normalize_identifier(
        value, db
    )


def test_the_list_info_agrees_on_a_fake_list(db: LicenseDatabase) -> None:
    """The list version, and the URL made from it."""
    assert _list_info(DictList(ROWS), "database") == _list_info(db, "database")
    assert _list_info(DictList(ROWS), "packaged")["version"] == LIST_VERSION


def test_a_loose_id_hit_keeps_the_flags_of_its_full_row(
    db: LicenseDatabase,
) -> None:
    """``loose_id`` reads the narrow row; Tier 0 takes the flags from the
    database's full one."""
    hit = match_version_key(db, "Apache2")[0]
    assert hit["license_id"] == "Apache-2.0"
    assert hit["is_spdx"] is True
    assert "is_osi_approved" in hit


def test_a_loose_id_row_the_database_lacks_is_no_hit(
    db: LicenseDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Defensive: a narrow row whose ID the full rows do not hold gives no
    match, not a raise."""
    row = ListedName(license_id="Gone-1.0", is_deprecated=False)
    monkeypatch.setattr(shorttext, "loose_id", lambda _db, _text: (row, "Gone-1.0"))
    assert not match_version_key(db, "Apache2")
