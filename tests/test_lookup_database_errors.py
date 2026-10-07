# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A database that fails after the matcher is built.

A lookup opens its connection read-only, so it never re-creates a deleted
file, and a SQLite failure surfaces as ``DatabaseNotReadyError``.
"""

# pylint: disable=missing-function-docstring,protected-access

import contextlib
import shutil
import sqlite3
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
from conftest import posix_only
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from db_variants import (
    BREAKERS,
    IS_ROOT,
    corrupt_db,
    make_ready_file_db,
    writer,
)

import licenseid
from licenseid import AggregatedLicenseMatcher, DatabaseNotReadyError, spdx_source
from licenseid.database import LicenseDatabase
from licenseid.dbcheck import lookup_error
from licenseid.dbconnection import Connections
from licenseid.errors import InvalidInputError, LicenseIdError


@pytest.fixture(name="matcher_db")
def _matcher_db(tmp_path: Path) -> tuple[AggregatedLicenseMatcher, Path]:
    path = make_ready_file_db(tmp_path / "b.db")
    matcher = AggregatedLicenseMatcher(db_path=str(path))
    assert matcher.match(license_id="MIT")
    return matcher, path


@pytest.mark.parametrize("break_db", BREAKERS, ids=lambda f: f.__name__)
def test_lookup_after_failure_is_database_not_ready(
    matcher_db: tuple[AggregatedLicenseMatcher, Path],
    break_db: Callable[[Path], None],
) -> None:
    matcher, path = matcher_db
    break_db(path)
    with pytest.raises(DatabaseNotReadyError) as info:
        matcher.match(license_id="MIT")
    message = str(info.value)
    assert message.startswith(f"database: unreadable: {path}: "), message
    # update rebuilds a missing or empty database, not a file that is not one
    repairable = break_db is not corrupt_db
    assert message.endswith("; run 'licenseid update'") is repairable, message
    assert "\n" not in message
    assert isinstance(info.value.__cause__, sqlite3.Error)


LOOKUPS: list[dict[str, Any]] = [
    {"license_id": "MIT"},
    {"text": "MIT"},  # Tier 0: reads every name and ID
    {"text": "Apache License 2.0 text of some length"},
    {"text": "SPDX-License-Identifier: MIT"},
]


@pytest.mark.parametrize("lookup", LOOKUPS, ids=lambda d: str(d)[:40])
def test_lookup_does_not_recreate_a_deleted_database(
    tmp_path: Path, lookup: dict[str, Any]
) -> None:
    path = make_ready_file_db(tmp_path / "d.db")
    matcher = AggregatedLicenseMatcher(db_path=str(path))
    path.unlink()
    with pytest.raises(DatabaseNotReadyError):
        matcher.match(**lookup)
    assert not path.exists()
    with pytest.raises(DatabaseNotReadyError, match="database: not found"):
        AggregatedLicenseMatcher(db_path=str(path))


def _null_norm_columns(path: Path) -> None:
    with writer(path) as conn:
        conn.execute("UPDATE licenses SET norm_license_id = NULL, norm_name = NULL")


def _fingerprint(path: Path) -> tuple[bytes, int]:
    return path.read_bytes(), path.stat().st_mtime_ns


def test_rows_without_norm_columns_are_normalised_not_written(
    tmp_path: Path, connects: list[bool]
) -> None:
    """A lookup never writes: a row that lacks its normalised columns is
    normalised in memory."""
    path = make_ready_file_db(tmp_path / "e.db")
    _null_norm_columns(path)
    before = _fingerprint(path)
    db = LicenseDatabase(str(path), create=False)
    connects.clear()
    names = db.get_all_names_and_ids()
    assert names
    assert all(n["norm_license_id"] and isinstance(n["norm_name"], str) for n in names)
    assert connects == [False] * len(connects), connects
    assert _fingerprint(path) == before, "the lookup wrote to the database"


@posix_only  # chmod only sets a read-only flag on Windows
@pytest.mark.skipif(IS_ROOT, reason="root ignores file permissions")
def test_a_read_only_database_without_norm_columns_still_answers(
    tmp_path: Path,
) -> None:
    path = make_ready_file_db(tmp_path / "ro.db")
    _null_norm_columns(path)
    path.chmod(0o444)
    matcher = AggregatedLicenseMatcher(db_path=str(path))
    assert matcher.match("MIT")[0]["license_id"] == "MIT"


def test_concurrent_lookups_on_rows_without_norm_columns(tmp_path: Path) -> None:
    path = make_ready_file_db(tmp_path / "g.db")
    _null_norm_columns(path)
    before = _fingerprint(path)
    matcher = AggregatedLicenseMatcher(db_path=str(path))
    with ThreadPoolExecutor(4) as pool:
        results = list(pool.map(lambda _: matcher.match("MIT"), range(8)))
    assert all(r and r[0]["license_id"] == "MIT" for r in results)
    assert _fingerprint(path) == before


def test_a_read_failing_during_update_is_an_update_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = make_ready_file_db(tmp_path / "u.db")
    db = LicenseDatabase(str(path))
    real = Connections.connect

    def failing_read(self: Connections, write: bool = False) -> Any:
        if not write:
            raise sqlite3.OperationalError("disk I/O error")
        return real(self, write)

    # No network: the version is known, so the first thing update does is read.
    version_info = mock.create_autospec(
        spdx_source.get_version_info, return_value=("9.99", None, "cache")
    )
    monkeypatch.setattr(spdx_source, "get_version_info", version_info)
    monkeypatch.setattr(Connections, "connect", failing_read)
    with pytest.raises(LicenseIdError) as info:
        db.update_from_remote()
    assert not isinstance(info.value, DatabaseNotReadyError)
    assert (
        str(info.value) == "database: update failed: OperationalError: disk I/O error"
    )
    cause = info.value.__cause__
    assert isinstance(cause, DatabaseNotReadyError)
    assert isinstance(cause.__cause__, sqlite3.OperationalError)


def test_the_open_uri_is_fixed_at_construction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A relative path names the file it named when the database was made, not
    the one a later chdir would make it name."""
    (tmp_path / "one").mkdir()
    (tmp_path / "two").mkdir()
    make_ready_file_db(tmp_path / "one" / "x.db")
    monkeypatch.chdir(tmp_path / "one")
    connections = Connections("x.db", False)
    monkeypatch.chdir(tmp_path / "two")
    with contextlib.closing(connections.connect()) as conn:
        assert conn.execute("SELECT count(*) FROM licenses").fetchone()[0] > 0
    assert not (tmp_path / "two" / "x.db").exists()


@pytest.mark.parametrize(
    "path",
    ["file:%FF.db", "file://localhost/x.db", "file:a.db?vfs=unix", "file:///C:/x.db"],
)
def test_connections_can_be_made_for_an_odd_path(path: str) -> None:
    """The URI is built at construction, so it must not raise for any path
    the readiness check lets through."""
    assert Connections(path, True, label=path).label == path


def test_a_direct_database_read_raises_database_not_ready(tmp_path: Path) -> None:
    path = make_ready_file_db(tmp_path / "i.db")
    db = LicenseDatabase(str(path))
    path.unlink()
    with pytest.raises(DatabaseNotReadyError, match="database: unreadable"):
        db.get_metadata()
    assert not path.exists()


@pytest.mark.parametrize(
    ("message", "action"),
    [
        ("no such table: licenses", True),
        ("unable to open database file", True),
        ("file is not a database", False),
        ("database disk image is malformed", False),
        ("database is locked", False),
        ("attempt to write a readonly database", False),
    ],
)
def test_action_only_for_an_unreadable_file(message: str, action: bool) -> None:
    error = lookup_error("x.db", sqlite3.OperationalError(message))
    assert str(error).endswith("; run 'licenseid update'") is action, str(error)


@pytest.mark.parametrize("method", ["is_spdx", "is_osi", "is_fsf", "is_open"])
def test_predicates_raise_database_not_ready(
    matcher_db: tuple[AggregatedLicenseMatcher, Path], method: str
) -> None:
    matcher, path = matcher_db
    path.unlink()
    with pytest.raises(DatabaseNotReadyError):
        getattr(matcher, method)(license_id="MIT")


def test_diff_pair_raises_database_not_ready(
    matcher_db: tuple[AggregatedLicenseMatcher, Path],
) -> None:
    matcher, path = matcher_db
    path.unlink()
    with pytest.raises(DatabaseNotReadyError):
        matcher.diff_pair("MIT", "MIT")


@pytest.mark.parametrize(
    "error",
    [
        sqlite3.Error,
        sqlite3.DatabaseError,
        sqlite3.OperationalError,
        sqlite3.IntegrityError,
        sqlite3.DataError,
        sqlite3.InternalError,
        sqlite3.NotSupportedError,
        sqlite3.ProgrammingError,
        sqlite3.InterfaceError,
    ],
)
def test_every_sqlite_error_is_wrapped(
    matcher_db: tuple[AggregatedLicenseMatcher, Path], error: type[sqlite3.Error]
) -> None:
    matcher, _ = matcher_db
    with (
        mock.patch.object(
            Connections, "connect", side_effect=error("multi\nline detail")
        ),
        pytest.raises(DatabaseNotReadyError) as info,
    ):
        matcher.match(license_id="MIT")
    assert "\n" not in str(info.value)
    assert isinstance(info.value.__cause__, error)


def test_locked_database_names_no_command(
    matcher_db: tuple[AggregatedLicenseMatcher, Path],
) -> None:
    matcher, _ = matcher_db
    with (
        mock.patch.object(
            Connections,
            "connect",
            side_effect=sqlite3.OperationalError("database is locked"),
        ),
        pytest.raises(DatabaseNotReadyError) as info,
    ):
        matcher.match(license_id="MIT")
    assert "database is locked" in str(info.value)
    assert "licenseid update" not in str(info.value)


def test_invalid_input_stays_invalid_input(
    matcher_db: tuple[AggregatedLicenseMatcher, Path],
) -> None:
    matcher, _ = matcher_db
    with pytest.raises(InvalidInputError):
        matcher.match(license_id="MIT OR Apache-2.0")


@posix_only  # chmod only sets a read-only flag on Windows
@pytest.mark.skipif(IS_ROOT, reason="root ignores file permissions")
def test_a_normal_lookup_still_works_read_only(tmp_path: Path) -> None:
    path = make_ready_file_db(tmp_path / "ok.db")
    path.chmod(0o444)
    matcher = AggregatedLicenseMatcher(db_path=str(path))
    assert matcher.match(license_id="MIT")[0]["license_id"] == "MIT"


def test_copied_database_is_independent(tmp_path: Path) -> None:
    a = make_ready_file_db(tmp_path / "a.db")
    b = tmp_path / "b.db"
    shutil.copy(a, b)
    matcher = AggregatedLicenseMatcher(db_path=str(b))
    b.unlink()
    with pytest.raises(DatabaseNotReadyError):
        matcher.match(license_id="MIT")
    assert not b.exists()


def test_get_default_db_path_is_public() -> None:
    from licenseid import get_default_db_path  # pylint: disable=import-outside-toplevel

    assert "get_default_db_path" in licenseid.__all__
    assert get_default_db_path.__module__ == "licenseid.datadir"
