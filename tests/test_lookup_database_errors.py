# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A database that fails after the matcher is built.

A lookup opens its connection read-only, so it never re-creates a deleted
file, and a SQLite failure surfaces as ``DatabaseNotReadyError``.
"""

# pylint: disable=missing-function-docstring,protected-access

import shutil
import sqlite3
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
from click.testing import CliRunner
from conftest import posix_only
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from db_variants import make_ready_file_db

import licenseid
from licenseid import AggregatedLicenseMatcher, DatabaseNotReadyError
from licenseid.cli import cli
from licenseid.database import LicenseDatabase
from licenseid.dbcheck import lookup_error
from licenseid.dbconnection import Connections
from licenseid.errors import InvalidInputError


def _delete(path: Path) -> None:
    path.unlink()


def _truncate(path: Path) -> None:
    path.write_bytes(b"")


def _corrupt(path: Path) -> None:
    size = path.stat().st_size
    with path.open("r+b") as handle:
        handle.write(b"\0" * min(4096, size))


BREAKERS: list[Callable[[Path], None]] = [_delete, _truncate, _corrupt]


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
    assert message.startswith(f"database: unreadable: {path}: ")
    assert message.endswith("; run 'licenseid update'")
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


def test_backfill_reads_before_it_writes(tmp_path: Path) -> None:
    """A database that needs no backfill never opens a write connection."""
    path = make_ready_file_db(tmp_path / "e.db")
    LicenseDatabase(str(path)).get_all_names_and_ids()  # the seed needs one
    db = LicenseDatabase(str(path))
    writes: list[bool] = []
    real = Connections.connect

    def record(self: Connections, write: bool = False) -> sqlite3.Connection:
        writes.append(write)
        return real(self, write)

    with mock.patch.object(Connections, "connect", autospec=True, side_effect=record):
        db.get_all_names_and_ids()
    assert writes
    assert not any(writes)


def test_backfill_inside_reading_block_writes_on_its_own_connection(
    tmp_path: Path,
) -> None:
    path = make_ready_file_db(tmp_path / "f.db")
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE licenses SET norm_license_id = NULL")
    db = LicenseDatabase(str(path))
    with db.reading():
        assert db.get_license_details("MIT")  # the shared reader is open
        names = db.get_all_names_and_ids()
    assert names
    with sqlite3.connect(path) as conn:
        left = conn.execute(
            "SELECT count(*) FROM licenses WHERE norm_license_id IS NULL"
        ).fetchone()[0]
    assert left == 0


def test_backfill_on_threads(tmp_path: Path) -> None:
    path = make_ready_file_db(tmp_path / "g.db")
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE licenses SET norm_license_id = NULL")
    matcher = AggregatedLicenseMatcher(db_path=str(path))
    with ThreadPoolExecutor(4) as pool:
        results = list(pool.map(lambda _: matcher.match(license_id="MIT"), range(8)))
    assert all(results)


@pytest.mark.parametrize(
    ("message", "action"),
    [
        ("disk image is malformed", True),
        ("database is locked", False),
        ("attempt to write a readonly database", False),
    ],
)
def test_action_only_for_an_unreadable_file(message: str, action: bool) -> None:
    error = lookup_error("x.db", sqlite3.OperationalError(message))
    assert str(error).endswith("; run 'licenseid update'") is action


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
            matcher, "_match_raw", side_effect=error("multi\nline detail")
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
            matcher,
            "_match_raw",
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


@pytest.mark.parametrize("break_db", BREAKERS, ids=lambda f: f.__name__)
def test_cli_exits_2_for_a_database_gone_bad(
    tmp_path: Path, break_db: Callable[[Path], None]
) -> None:
    path = make_ready_file_db(tmp_path / "c.db")
    real = AggregatedLicenseMatcher._match_raw

    def broken_then_match(self: AggregatedLicenseMatcher, *args: Any, **kw: Any) -> Any:
        break_db(path)
        return real(self, *args, **kw)

    with mock.patch.object(
        AggregatedLicenseMatcher,
        "_match_raw",
        autospec=True,
        side_effect=broken_then_match,
    ):
        result = CliRunner().invoke(cli, ["--db", str(path), "match", "--id", "MIT"])
    assert result.exit_code == 2
    assert result.stderr.startswith("ERROR: database: ")


@posix_only  # chmod only sets a read-only flag on Windows
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
