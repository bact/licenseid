# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Tests for LicenseDatabase._connection()'s close-on-exit guarantee."""
# pylint: disable=redefined-outer-name,missing-function-docstring,protected-access

import sqlite3
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest

from licenseid.database import LicenseDatabase


@pytest.fixture()
def db(tmp_path: Path) -> Generator[LicenseDatabase, None, None]:
    db_path = str(tmp_path / f"test_{uuid.uuid4().hex[:8]}.db")
    yield LicenseDatabase(db_path)


def _assert_closed(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        conn.execute("SELECT 1")


def test_connection_closes_after_successful_query(db: LicenseDatabase) -> None:
    """A query method must close its connection, not just commit it."""
    opened: list[sqlite3.Connection] = []
    real_connect = db._connect

    def tracking_connect() -> sqlite3.Connection:
        conn = real_connect()
        opened.append(conn)
        return conn

    db._connect = tracking_connect  # type: ignore[method-assign]

    db.get_metadata()

    assert opened
    for conn in opened:
        _assert_closed(conn)


def test_connection_closes_even_when_the_query_raises(db: LicenseDatabase) -> None:
    """The connection must be closed on the exception path too, not leaked."""
    with pytest.raises(RuntimeError, match="boom"), db._connection() as conn:
        raise RuntimeError("boom")

    _assert_closed(conn)


def test_connection_commits_before_closing(db: LicenseDatabase) -> None:
    """Data written inside the context manager must survive past its exit."""
    with db._connection() as conn:
        conn.execute(
            "INSERT INTO db_metadata (key, value) VALUES (?, ?)",
            ("test_key", "test_value"),
        )

    with db._connection() as conn:
        row = conn.execute(
            "SELECT value FROM db_metadata WHERE key = ?", ("test_key",)
        ).fetchone()
    assert row == ("test_value",)
