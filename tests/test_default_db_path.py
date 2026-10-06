# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The default database path is a pure lookup: only building creates it."""

# pylint: disable=redefined-outer-name,missing-function-docstring

from pathlib import Path
from unittest import mock

import pytest
from click.testing import CliRunner

from licenseid.cli import cli
from licenseid.database import LicenseDatabase
from licenseid.datadir import get_default_db_path
from licenseid.errors import DatabaseNotReadyError

NO_HOME = "ERROR: database: not found: no home directory; pass --db\n"


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A home directory with nothing in it, as the only home there is."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))  # Path.home() on Windows
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    return tmp_path


def test_default_path_creates_nothing(home: Path) -> None:
    assert get_default_db_path() == str(
        home / ".local" / "share" / "licenseid" / "licenses.db"
    )
    assert not list(home.iterdir())


@pytest.mark.parametrize("args", [["match", "MIT"], ["is-osi", "MIT"]])
def test_read_command_reports_a_missing_default_database(
    home: Path, args: list[str]
) -> None:
    """A read command on a fresh home exits 2 and leaves the home as it was."""
    result = CliRunner().invoke(cli, args)
    expected = home / ".local" / "share" / "licenseid" / "licenses.db"
    assert result.exit_code == 2
    assert result.stdout == ""
    assert result.stderr == (
        f"ERROR: database: not found: {expected}; run 'licenseid update'\n"
    )
    assert not list(home.iterdir())


@pytest.mark.parametrize("args", [["match", "MIT"], ["is-osi", "MIT"], ["update"]])
def test_no_home_directory_is_an_error_line_not_a_traceback(
    monkeypatch: pytest.MonkeyPatch, args: list[str]
) -> None:
    """A service account or a container user may have none, and exit 1 would
    read as "no"."""

    def no_home() -> Path:
        raise RuntimeError("Could not determine home directory.")

    monkeypatch.setattr(Path, "home", staticmethod(no_home))
    result = CliRunner().invoke(cli, args)
    assert result.exit_code == 2
    assert result.stdout == ""
    assert result.stderr == NO_HOME


@pytest.mark.parametrize("args", [["match", "--help"], ["is-osi", "--help"], []])
def test_help_and_a_bare_run_need_no_home_directory(
    monkeypatch: pytest.MonkeyPatch, args: list[str]
) -> None:
    """The default database is only looked up by a command that opens it."""

    def no_home() -> Path:
        raise RuntimeError("Could not determine home directory.")

    monkeypatch.setattr(Path, "home", staticmethod(no_home))
    result = CliRunner().invoke(cli, args)
    assert "no home directory" not in result.stderr
    assert (result.exit_code, bool(result.stdout or result.stderr)) == (
        (2 if not args else 0),
        True,
    )


def test_clear_cache_without_a_home_directory_is_an_error_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def no_home() -> Path:
        raise RuntimeError("Could not determine home directory.")

    monkeypatch.setattr(Path, "home", staticmethod(no_home))
    result = CliRunner().invoke(cli, ["--clear-cache"])
    assert (result.exit_code, result.stderr) == (2, NO_HOME)


def test_an_empty_home_is_no_home(monkeypatch: pytest.MonkeyPatch) -> None:
    """USERPROFILE or HOME set to nothing: Path.home() is the current
    directory, and the database would be made there."""
    monkeypatch.setattr(Path, "home", staticmethod(Path))
    with pytest.raises(DatabaseNotReadyError, match="no home directory"):
        get_default_db_path()


def test_update_builds_the_default_directory(home: Path) -> None:
    """Building is where the directory is created."""
    with mock.patch.object(
        LicenseDatabase, "update_from_remote", autospec=True, return_value=True
    ):
        result = CliRunner().invoke(cli, ["update"])
    database = home / ".local" / "share" / "licenseid" / "licenses.db"
    assert result.exit_code == 0
    assert result.stdout == f"Database updated at {database}\n"
    assert database.is_file()


def test_update_does_not_build_the_directory_of_an_explicit_path(
    tmp_path: Path,
) -> None:
    """Only the default location is made for the user; a typo in --db is not.

    Current behaviour, not a documented contract: the failure surfaces as the
    generic ``update failed`` line (roadmap item 10 covers rewording it)."""
    missing = tmp_path / "typo" / "licenses.db"
    with mock.patch.object(
        LicenseDatabase, "update_from_remote", autospec=True, return_value=True
    ):
        result = CliRunner().invoke(cli, ["--db", str(missing), "update"])
    assert result.exit_code == 1
    assert not missing.parent.exists()
    assert result.stderr.startswith("ERROR: database: update failed: ")


def test_clear_cache_on_a_fresh_home_works(home: Path) -> None:
    """Nothing to clear: it succeeds and does not make the directory."""
    result = CliRunner().invoke(cli, ["--clear-cache"])
    assert result.exit_code == 0
    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert result.stdout == ""
    assert not (home / ".local" / "share" / "licenseid").exists()


def test_clear_cache_with_a_file_where_the_default_directory_would_be(
    home: Path,
) -> None:
    """A file where the directory should be is no reason for a traceback."""
    blocker = home / ".local" / "share" / "licenseid"
    blocker.parent.mkdir(parents=True)
    blocker.write_text("not a directory")
    result = CliRunner().invoke(cli, ["--clear-cache"])
    assert result.exit_code == 0
    assert result.stdout == ""
    assert blocker.read_text() == "not a directory"
