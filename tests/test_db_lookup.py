# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Lookups by licence ID (roadmap item 37): the same answers as SQLite's
``COLLATE NOCASE`` and a plain ``=``, without a table scan per call."""
# pylint: disable=redefined-outer-name,missing-function-docstring,protected-access

import contextlib
import sqlite3
from collections.abc import Callable, Generator
from typing import Any
from unittest import mock

import pytest
from db_variants import stamp_rebuild
from matcher_db import Lic, seeded_db

from licenseid.database import LicenseDatabase
from licenseid.dbcache import TableCache
from licenseid.dbconnection import Connections

ROWS = (
    Lic("MIT", "MIT License", True, True, True, search_text="permission is hereby"),
    Lic("Apache-2.0", "Apache License 2.0", True, True, True),  # not indexed
    Lic("SK-1.0", "Made-up K License", search_text="made up k"),
)


@pytest.fixture
def db() -> Generator[LicenseDatabase, None, None]:
    for path in seeded_db("test_db_lookup", ROWS):
        yield LicenseDatabase(path)


@pytest.fixture
def statements() -> Generator[list[str], None, None]:
    """Every SQL statement licenseid runs while the test runs."""
    sql: list[str] = []
    real = Connections.connect

    def traced(self: Connections, write: bool = False) -> sqlite3.Connection:
        conn = real(self, write)
        conn.set_trace_callback(sql.append)
        return conn

    with mock.patch.object(Connections, "connect", autospec=True, side_effect=traced):
        yield sql


@pytest.mark.parametrize(
    ("asked", "found"),
    [
        ("MIT", "MIT"),
        ("mit", "MIT"),
        (" mIt\n", "MIT"),
        ("sk-1.0", "SK-1.0"),
        ("SK-1.0", None),  # KELVIN SIGN: NOCASE folds ASCII only
        ("MİT", None),
        ("MIT+", None),
        ("LicenseRef-x", None),
        ("", None),
    ],
)
def test_license_details_ignore_ascii_case(
    db: LicenseDatabase, asked: str, found: str | None
) -> None:
    details = db.get_license_details(asked)
    assert (details["license_id"] if details else None) == found
    if details:  # the whole row, its flags bool
        assert details["is_osi_approved"] is (found == "MIT")


@pytest.mark.parametrize(
    ("asked", "text"),
    [
        ("MIT", "permission is hereby"),
        ("mit", ""),  # exact case, as before
        ("Apache-2.0", ""),  # a licence with no index row
        ("LicenseRef-x", ""),
        ("MIT AND SK-1.0", ""),
    ],
)
def test_search_text_by_exact_id(db: LicenseDatabase, asked: str, text: str) -> None:
    assert db.get_search_text(asked) == text


def _selects(statements: list[str], table: str) -> list[str]:
    """The SELECTs on *table*; FTS5's reads of its own shadow tables
    ('main'.'license_index_config') are not ours."""
    return [
        s
        for s in statements
        if s.startswith("SELECT") and f"FROM {table}" in s and "'main'" not in s
    ]


@pytest.mark.parametrize("in_block", [True, False], ids=["one-match", "api-calls"])
def test_lookups_scan_each_table_once(
    db: LicenseDatabase, statements: list[str], in_block: bool
) -> None:
    ids = ["MIT", "mit", "SK-1.0", "Apache-2.0"]
    with db.reading() if in_block else contextlib.nullcontext():
        for i in range(50):
            for license_id in [*ids, f"LicenseRef-{i}"]:
                db.get_license_details(license_id)
                db.get_search_text(license_id)
    tables = [*_selects(statements, "licenses"), *_selects(statements, "license_index")]
    assert len([s for s in tables if "WHERE" not in s]) == 2  # once per table
    # Known IDs only: a LicenseRef or an unknown ID costs no query at all.
    # Details for MIT, mit, SK-1.0 and Apache-2.0; text for MIT and SK-1.0.
    assert len([s for s in tables if "WHERE" in s]) == 50 * (4 + 2)
    # The rebuild stamp: once per match, else at every lookup.
    assert len(_selects(statements, "db_metadata")) == (1 if in_block else 500)


def _rebuild(db: LicenseDatabase, stamp: str | None) -> None:
    """Rewrite the index in another order, as another process's update."""
    with sqlite3.connect(db.db_path, uri=True) as conn:
        conn.execute("DELETE FROM license_index")
        conn.executemany(
            "INSERT INTO license_index (rowid, license_id, search_text)"
            " VALUES (?, ?, ?)",
            [(1, "SK-1.0", "new k"), (2, "MIT", "new mit"), (3, "Zlib", "zlib")],
        )
        conn.execute(
            "INSERT INTO licenses (license_id, name) VALUES ('Zlib', 'zlib License')"
        )
        stamp_rebuild(conn, stamp)


def test_a_rebuild_clears_what_was_read(db: LicenseDatabase) -> None:
    assert db.get_license_details("MIT")
    assert db.get_all_names_and_ids()
    db._write_db_records(
        [("Zlib", "zlib License", None, True, True, True, True, False, None, 1, 3,
          "zlib", "zlib license")],
        [("Zlib", "the origin of this software")],
        [],
        None,
    )  # fmt: skip
    assert db.get_license_details("MIT") is None
    zlib = db.get_license_details("zlib")
    assert zlib and zlib["license_id"] == "Zlib"
    assert db.get_search_text("Zlib") == "the origin of this software"
    assert [r["license_id"] for r in db.get_all_names_and_ids()] == ["Zlib"]


@pytest.mark.parametrize("in_block", [True, False], ids=["next-match", "api-call"])
def test_a_rebuild_by_another_process_is_seen(
    db: LicenseDatabase, in_block: bool
) -> None:
    """A long-lived matcher sees what `licenseid update` changed meanwhile."""
    assert db.get_search_text("SK-1.0") == "made up k"
    assert db.get_license_details("Zlib") is None
    _rebuild(db, "2026-10-02T00:00:00")
    with db.reading() if in_block else contextlib.nullcontext():
        assert db.get_search_text("MIT") == "new mit"
        assert db.get_search_text("SK-1.0") == "new k"
        assert db.get_license_details("zlib")
        assert "Zlib" in [r["license_id"] for r in db.get_all_names_and_ids()]


def test_a_rebuild_during_a_match_never_gives_another_text(
    db: LicenseDatabase,
) -> None:
    with db.reading():
        assert db.get_search_text("SK-1.0") == "made up k"
        _rebuild(db, "2026-10-02T00:00:00")  # seen at the next match
        assert db.get_search_text("MIT") == ""  # its old row is SK-1.0's now
    assert db.get_search_text("MIT") == "new mit"


def test_a_row_with_no_id_is_skipped() -> None:
    """A primary key that is not INTEGER may be NULL in SQLite."""
    for path in seeded_db("test_db_lookup_null", ROWS):
        with sqlite3.connect(path, uri=True) as conn:
            conn.execute("INSERT INTO licenses (license_id, name) VALUES (NULL, 'x')")
            conn.execute(
                "INSERT INTO license_index (license_id, search_text) VALUES (NULL, 'x')"
            )
        db = LicenseDatabase(path)
        assert db.get_license_details("mit")
        assert db.get_search_text("MIT") == "permission is hereby"


@pytest.mark.parametrize(
    ("read", "kept"),
    [
        (lambda t: t.license_id("MIT"), "_license_ids"),
        (lambda t: t.index_row("MIT"), "_index_rows"),
        (lambda t: t.names_and_ids(), "_names_and_ids"),
        (lambda t: t.deprecated(), "_deprecated"),
    ],
    ids=["ids", "index", "names", "deprecated"],
)
def test_a_read_made_during_a_clear_is_not_kept(
    db: LicenseDatabase, read: Callable[[TableCache], object], kept: str
) -> None:
    """Another thread saw a rebuild while this one read the old rows."""
    tables = db._tables
    real = Connections.connection

    def connection_then_clear(self: Connections) -> Any:
        tables.clear()
        return real(self)

    with mock.patch.object(
        Connections, "connection", autospec=True, side_effect=connection_then_clear
    ):
        read(tables)
    assert getattr(tables, kept) is None
    read(tables)
    assert getattr(tables, kept) is not None
