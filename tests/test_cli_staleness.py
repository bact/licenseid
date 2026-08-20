# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Tests for cli.check_db_staleness()."""
# pylint: disable=redefined-outer-name

import sqlite3
import uuid
from collections.abc import Generator
from datetime import datetime, timedelta, timezone

import pytest

from licenseid.cli import check_db_staleness
from licenseid.database import LicenseDatabase


def _make_db(last_check_datetime: str) -> Generator[LicenseDatabase, None, None]:
    db_id = str(uuid.uuid4())[:8]
    db_path = f"file:test_staleness_{db_id}?mode=memory&cache=shared"
    db_manager = LicenseDatabase(db_path)
    keep_alive = sqlite3.connect(db_path, uri=True)

    with sqlite3.connect(db_path, uri=True) as conn:
        conn.execute(
            "INSERT INTO db_metadata (key, value) VALUES (?, ?)",
            ("last_check_datetime", last_check_datetime),
        )
        conn.commit()

    yield db_manager
    keep_alive.close()


@pytest.fixture
def fresh_db() -> Generator[LicenseDatabase, None, None]:
    """A database whose last_check_datetime is now."""
    now = datetime.now(timezone.utc).isoformat()
    yield from _make_db(now)


@pytest.fixture
def stale_tz_aware_db() -> Generator[LicenseDatabase, None, None]:
    """A database whose last_check_datetime is 200 tz-aware days old."""
    old = (datetime.now(timezone.utc) - timedelta(days=200)).isoformat()
    yield from _make_db(old)


@pytest.fixture
def stale_naive_db() -> Generator[LicenseDatabase, None, None]:
    """Mimics a database written before last_check_datetime became
    tz-aware: a naive local-time ISO string with no UTC offset."""
    old_naive = (datetime.now() - timedelta(days=200)).isoformat()  # noqa: DTZ005
    yield from _make_db(old_naive)


@pytest.fixture
def malformed_db() -> Generator[LicenseDatabase, None, None]:
    """A database whose last_check_datetime is not a valid timestamp."""
    yield from _make_db("not-a-real-timestamp")


def test_fresh_db_no_warning(
    fresh_db: LicenseDatabase, capsys: pytest.CaptureFixture[str]
) -> None:
    """A fresh database doesn't trigger a staleness warning."""
    check_db_staleness(fresh_db)
    assert "WARNING" not in capsys.readouterr().err


def test_stale_tz_aware_db_warns(
    stale_tz_aware_db: LicenseDatabase, capsys: pytest.CaptureFixture[str]
) -> None:
    """A stale tz-aware database triggers a staleness warning."""
    check_db_staleness(stale_tz_aware_db)
    assert "WARNING" in capsys.readouterr().err


def test_stale_naive_db_warns_without_crashing(
    stale_naive_db: LicenseDatabase, capsys: pytest.CaptureFixture[str]
) -> None:
    """Regression test: a pre-existing naive-timestamp database must not
    raise TypeError when compared against a tz-aware datetime.now()."""
    check_db_staleness(stale_naive_db)
    assert "WARNING" in capsys.readouterr().err


def test_malformed_timestamp_ignored(
    malformed_db: LicenseDatabase, capsys: pytest.CaptureFixture[str]
) -> None:
    """A malformed timestamp is ignored rather than raising or warning."""
    check_db_staleness(malformed_db)
    assert capsys.readouterr().err == ""
