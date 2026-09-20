# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""CLI error messages: exact text on stderr, nothing on stdout, exit code."""
# pylint: disable=redefined-outer-name,missing-function-docstring

import sqlite3
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
from click.testing import CliRunner
from conftest import make_memory_db_path, make_ready_db_path

from licenseid.cli import cli
from licenseid.database import LicenseDatabase
from licenseid.matcher import AggregatedLicenseMatcher


@pytest.fixture
def ready_db() -> Generator[str, None, None]:
    """A ready, silent database (one MIT row), so a command reaches the
    input handling and the matching that these tests exercise."""
    db_path, keep_alive = make_ready_db_path("test_cli_errors")
    yield db_path
    keep_alive.close()


@pytest.fixture
def empty_db() -> Generator[str, None, None]:
    """Schema and license list version, but no license rows."""
    db_path, keep_alive = make_memory_db_path("test_cli_errors_empty")
    yield db_path
    keep_alive.close()


@pytest.mark.parametrize("command", ["match", "is-osi"])
def test_missing_database(tmp_path: Path, command: str) -> None:
    db_path = tmp_path / "absent.db"
    result = CliRunner().invoke(cli, ["--db", str(db_path), command, "MIT"])
    assert result.exit_code == 2
    assert result.stdout == ""
    assert result.stderr == (
        f"ERROR: database: not found: {db_path}; run 'licenseid update'\n"
    )


@pytest.mark.parametrize("command", ["match", "is-osi"])
def test_empty_database(empty_db: str, command: str) -> None:
    """A database with no licenses is refused before any input is read: it
    would answer "no license found" (match) or false (is-osi) for everything."""
    result = CliRunner().invoke(cli, ["--db", empty_db, command, "MIT"])
    assert result.exit_code == 2
    assert result.stdout == ""
    assert result.stderr == (
        f"ERROR: database: empty: {empty_db}; run 'licenseid update'\n"
    )


@pytest.mark.parametrize("command", ["match", "is-osi"])
def test_unreadable_database(tmp_path: Path, command: str) -> None:
    db_path = tmp_path / "notes.db"
    db_path.write_text("this is not an SQLite database, " * 8)
    result = CliRunner().invoke(cli, ["--db", str(db_path), command, "MIT"])
    assert result.exit_code == 2
    assert result.stdout == ""
    assert result.stderr.startswith(f"ERROR: database: unreadable: {db_path}: ")
    assert result.stderr.count("\n") == 1


def test_clear_cache_removes_a_file_that_is_not_a_database(tmp_path: Path) -> None:
    """Clearing works on the path alone, so the recovery command is not
    refused by the corruption it exists to recover from."""
    db_path = tmp_path / "notes.db"
    db_path.write_text("this is not an SQLite database, " * 8)
    result = CliRunner().invoke(cli, ["--db", str(db_path), "--clear-cache"])
    assert result.exit_code == 0
    assert result.stdout == ""
    assert not db_path.exists()


@pytest.mark.parametrize(
    ("args", "target", "target_attr"),
    [
        (["match", "--id", "MIT"], AggregatedLicenseMatcher, "match"),
        (["is-osi", "MIT"], LicenseDatabase, "get_license_details"),
    ],
)
def test_sqlite_failure_after_the_check_is_an_unreadable_database(
    ready_db: str, args: list[str], target: Any, target_attr: str
) -> None:
    """The file went bad after the readiness check: still exit 2, one line."""
    failure = sqlite3.DatabaseError("database disk image is malformed")
    with mock.patch.object(target, target_attr, autospec=True, side_effect=failure):
        result = CliRunner().invoke(cli, ["--db", ready_db, *args])
    assert result.exit_code == 2
    assert result.stdout == ""
    assert result.stderr == (
        f"ERROR: database: unreadable: {ready_db}: database disk image is malformed\n"
    )


def test_other_exceptions_are_not_worded_as_a_database_error(ready_db: str) -> None:
    """Only SQLite failures are; a bug elsewhere must still show its traceback."""
    with mock.patch.object(
        AggregatedLicenseMatcher, "match", autospec=True, side_effect=KeyError("x")
    ):
        result = CliRunner().invoke(cli, ["--db", ready_db, "match", "--id", "MIT"])
    assert isinstance(result.exception, KeyError)


@pytest.mark.parametrize(
    "failure", [sqlite3.ProgrammingError("bad"), sqlite3.InterfaceError("bad")]
)
def test_sqlite_programming_errors_are_not_worded_as_a_database_error(
    ready_db: str, failure: sqlite3.Error
) -> None:
    """A bad query is a bug in licenseid, not a fault in the file: the user is
    not told to rebuild a healthy database."""
    with mock.patch.object(
        AggregatedLicenseMatcher, "match", autospec=True, side_effect=failure
    ):
        result = CliRunner().invoke(cli, ["--db", ready_db, "match", "--id", "MIT"])
    assert result.exception is failure
    assert "unreadable" not in result.stderr


@pytest.mark.parametrize("command", ["match", "is-osi"])
def test_missing_input(ready_db: str, command: str) -> None:
    result = CliRunner().invoke(cli, ["--db", ready_db, command], input="")
    assert result.exit_code == 2
    assert result.stdout == ""
    assert result.stderr == (
        "ERROR: input: missing; pass a file, an ID, --text, --id or stdin\n"
    )


@pytest.mark.parametrize("extra", [[], ["--bold"]])
def test_no_match_in_ready_database(ready_db: str, extra: list[str]) -> None:
    result = CliRunner().invoke(
        cli, ["--db", ready_db, "match", "--id", "No-Such-License", *extra]
    )
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == "ERROR: match: no license found\n"


_PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"


@pytest.mark.parametrize("command", ["match", "is-osi"])
def test_binary_input_file(ready_db: str, tmp_path: Path, command: str) -> None:
    path = tmp_path / "logo.png"
    path.write_bytes(_PNG)
    result = CliRunner().invoke(cli, ["--db", ready_db, command, str(path)])
    assert result.exit_code == 2
    assert result.stdout == ""
    assert result.stderr == f"ERROR: input: binary file: {path}\n"


@pytest.mark.parametrize("text", ["MIT\\x00", "\\0"])
def test_binary_text_option(ready_db: str, text: str) -> None:
    """A NUL from a --text escape is rejected as it is from a file or stdin."""
    result = CliRunner().invoke(cli, ["--db", ready_db, "match", "--text", text])
    assert result.exit_code == 2
    assert result.stdout == ""
    assert result.stderr == "ERROR: input: binary file: --text\n"


def test_binary_stdin(ready_db: str) -> None:
    result = CliRunner().invoke(cli, ["--db", ready_db, "match"], input=_PNG)
    assert result.exit_code == 2
    assert result.stdout == ""
    assert result.stderr == "ERROR: input: binary file: stdin\n"


@pytest.mark.parametrize("command", ["match", "is-osi"])
def test_unreadable_input_path(ready_db: str, tmp_path: Path, command: str) -> None:
    directory = tmp_path / "LICENSES"
    directory.mkdir()
    result = CliRunner().invoke(cli, ["--db", ready_db, command, str(directory)])
    assert result.exit_code == 2
    assert result.stdout == ""
    # The reason is the OS's strerror text, which varies by platform/locale.
    assert result.stderr.startswith(f"ERROR: input: unreadable: {directory}: ")
    assert result.stderr.count("\n") == 1


@pytest.mark.parametrize("content", [b"", b"\xef\xbb\xbf", b"  \r\n\t\n"])
@pytest.mark.parametrize("command", ["match", "is-osi"])
def test_empty_input_file(
    ready_db: str, tmp_path: Path, command: str, content: bytes
) -> None:
    """A file was given, so "missing; pass a file..." would be wrong."""
    path = tmp_path / "LICENSE"
    path.write_bytes(content)
    result = CliRunner().invoke(cli, ["--db", ready_db, command, str(path)])
    assert result.exit_code == 2
    assert result.stdout == ""
    assert result.stderr == f"ERROR: input: empty: {path}\n"
