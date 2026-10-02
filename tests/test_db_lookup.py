# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Lookups by licence ID (roadmap item 37): the same answers as SQLite's
``COLLATE NOCASE`` and a plain ``=``, without a table scan per call."""
# pylint: disable=redefined-outer-name,missing-function-docstring,protected-access

import sqlite3
from collections.abc import Generator
from unittest import mock

import pytest
from matcher_db import Lic, seeded_db

from licenseid.database import LicenseDatabase
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

    def traced(self: Connections) -> sqlite3.Connection:
        conn = real(self)
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


def test_lookups_scan_each_table_once(
    db: LicenseDatabase, statements: list[str]
) -> None:
    ids = ["MIT", "mit", "SK-1.0", "Apache-2.0"]
    for i in range(50):
        for license_id in [*ids, f"LicenseRef-{i}"]:
            db.get_license_details(license_id)
            db.get_search_text(license_id)
    # FTS5 reads its own shadow tables ('main'.'license_index_config').
    selects = [s for s in statements if s.startswith("SELECT") and "'main'" not in s]
    scans = [s for s in selects if "WHERE" not in s]
    by_id = [s for s in selects if "WHERE" in s]
    assert len(scans) == 2  # one per table, at the first lookup
    # Known IDs only: a LicenseRef or an unknown ID costs no query at all.
    # Details for MIT, mit, SK-1.0 and Apache-2.0; text for MIT and SK-1.0.
    assert len(by_id) == 50 * (4 + 2)


def test_a_rebuild_clears_what_was_read(db: LicenseDatabase) -> None:
    assert db.get_license_details("MIT")
    assert db.get_all_names_and_ids()
    db._write_db_records(
        [("Zlib", "zlib License", None, True, True, True, True, False, None, 1, 3,
          "zlib", "zlib license")],
        [("Zlib", "the origin of this software")],
        [],
        "3.30",
        None,
    )  # fmt: skip
    assert db.get_license_details("MIT") is None
    zlib = db.get_license_details("zlib")
    assert zlib and zlib["license_id"] == "Zlib"
    assert db.get_search_text("Zlib") == "the origin of this software"
    assert [r["license_id"] for r in db.get_all_names_and_ids()] == ["Zlib"]


def test_a_rebuild_by_another_process_never_gives_another_text(
    db: LicenseDatabase,
) -> None:
    assert db.get_search_text("SK-1.0") == "made up k"
    with sqlite3.connect(db.db_path, uri=True) as conn:  # rows in another order
        conn.execute("DELETE FROM license_index")
        conn.executemany(
            "INSERT INTO license_index (rowid, license_id, search_text)"
            " VALUES (?, ?, ?)",
            [(1, "SK-1.0", "new k"), (2, "MIT", "new mit")],
        )
    assert db.get_search_text("MIT") == "new mit"
    assert db.get_search_text("SK-1.0") == "new k"
