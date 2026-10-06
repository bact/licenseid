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
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
from click.testing import CliRunner
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from db_variants import make_ready_file_db

import licenseid
from licenseid import AggregatedLicenseMatcher, DatabaseNotReadyError
from licenseid.cli import cli
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


def test_lookup_does_not_recreate_a_deleted_database(
    matcher_db: tuple[AggregatedLicenseMatcher, Path],
) -> None:
    matcher, path = matcher_db
    path.unlink()
    with pytest.raises(DatabaseNotReadyError):
        matcher.match(license_id="MIT")
    assert not path.exists()
    with pytest.raises(DatabaseNotReadyError, match="database: not found"):
        AggregatedLicenseMatcher(db_path=str(path))


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
