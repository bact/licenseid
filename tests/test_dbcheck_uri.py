# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Edge cases of how ``check_database_ready`` opens a file read-only.

The contract tests in ``test_db_ready.py`` run every variant through the CLI
and the API. These pin the URI handling underneath: relative paths,
fragments, symlinks, write-ahead logs, and the matcher's own second check.
"""

# pylint: disable=protected-access,missing-function-docstring

import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner
from db_variants import build_ready_wal_with_wal, make_ready_file_db

from licenseid import cli as cli_module
from licenseid.cli import cli
from licenseid.database import LicenseDatabase
from licenseid.dbcheck import _REQUIRED_COLUMNS, _read_only_uri, check_database_ready
from licenseid.errors import DatabaseNotReadyError


@pytest.mark.parametrize("prefix", ["", "./"])
def test_relative_path_is_ready(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, prefix: str
) -> None:
    make_ready_file_db(tmp_path / "rel.db")
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cli, ["--db", f"{prefix}rel.db", "is-osi", "MIT"])
    assert (result.exit_code, result.stdout, result.stderr) == (0, "true\n", "")


@pytest.mark.parametrize("prefix", ["", "./"])
def test_relative_path_not_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, prefix: str
) -> None:
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cli, ["--db", f"{prefix}nope.db", "is-osi", "MIT"])
    assert result.exit_code == 2
    assert result.stderr == (
        f"ERROR: database: not found: {prefix}nope.db; run 'licenseid update'\n"
    )
    assert not list(tmp_path.iterdir())


def test_uri_fragment_does_not_defeat_read_only(tmp_path: Path) -> None:
    """mode=ro placed after a fragment would be dropped, and SQLite would
    create the file."""
    missing = tmp_path / "frag.db"
    for suffix in ("#n", "#f?mode=rwc"):
        with pytest.raises(DatabaseNotReadyError):
            check_database_ready(f"file:{missing}{suffix}")
        assert not missing.exists()


def test_uri_query_is_not_form_encoded() -> None:
    """A space in a value is %20; SQLite does not decode '+'."""
    uri = _read_only_uri("file:/x.db?vfs=unix none")
    assert "+" not in uri
    assert "vfs=unix%20none" in uri


def _idle_wal_database(directory: Path) -> Path:
    """A ready database in WAL mode with no -wal file: every connection is
    closed, so the log was checkpointed and removed."""
    path = make_ready_file_db(directory / "idle-wal.db")
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.close()
    assert not path.with_name(path.name + "-wal").exists()
    return path


def test_idle_wal_database_is_read_as_immutable(tmp_path: Path) -> None:
    path = _idle_wal_database(tmp_path)
    assert _read_only_uri(str(path)).endswith("?mode=ro&immutable=1")
    assert "immutable=1" in _read_only_uri(f"file:{path}")


def test_symlink_to_an_idle_wal_database_is_read_as_immutable(
    tmp_path: Path,
) -> None:
    link = tmp_path / "link.db"
    link.symlink_to(_idle_wal_database(tmp_path))
    assert "immutable=1" in _read_only_uri(str(link))


def test_rollback_journal_database_is_never_read_as_immutable(
    tmp_path: Path,
) -> None:
    """Immutable turns locking off, and an update may be rewriting the file."""
    path = make_ready_file_db(tmp_path / "plain.db")
    assert "immutable" not in _read_only_uri(str(path))
    assert "immutable" not in _read_only_uri(f"file:{path}")


@pytest.mark.parametrize("kind", ["missing", "directory", "short"])
def test_a_file_that_cannot_be_a_wal_database_is_not_immutable(
    tmp_path: Path, kind: str
) -> None:
    path = tmp_path / "x.db"
    if kind == "directory":
        path.mkdir()
    elif kind == "short":
        path.write_bytes(b"SQLite format 3\x00")
    assert "immutable" not in _read_only_uri(str(path))


def test_uri_keeps_an_explicit_immutable(tmp_path: Path) -> None:
    uri = _read_only_uri(f"file:{_idle_wal_database(tmp_path)}?immutable=0")
    assert "immutable=0" in uri
    assert "immutable=1" not in uri


def test_uri_with_an_empty_authority_is_ready(tmp_path: Path) -> None:
    """``file:///abs/path`` is the same file as ``file:/abs/path``."""
    path = make_ready_file_db(tmp_path / "auth.db")
    check_database_ready(f"file://{path}")


def test_uri_naming_a_host_is_not_made_immutable() -> None:
    assert "immutable" not in _read_only_uri("file://host/x.db")


@pytest.mark.parametrize("state", ["missing", "empty", "unreadable"])
def test_a_newline_in_the_path_keeps_the_message_on_one_line(
    tmp_path: Path, state: str
) -> None:
    """One event per line: the newline is written as an escape."""
    path = tmp_path / "a\nb.db"
    if state == "empty":
        path.write_bytes(b"")
    elif state == "unreadable":
        path.write_text("not a database\n" * 20, encoding="utf-8")
    result = CliRunner().invoke(cli, ["--db", str(path), "is-osi", "MIT"])
    assert result.exit_code == 2
    assert result.stdout == ""
    assert result.stderr.count("\n") == 1
    assert "a\\nb.db" in result.stderr
    with pytest.raises(DatabaseNotReadyError) as info:
        check_database_ready(str(path))
    assert "\n" not in str(info.value)


def test_nul_byte_in_a_uri_is_refused_not_raised() -> None:
    with pytest.raises(DatabaseNotReadyError, match="database: unreadable: "):
        check_database_ready("file:/tmp/a\x00b.db")


def test_unencodable_path_is_refused_not_raised(tmp_path: Path) -> None:
    """A lone surrogate cannot be percent-encoded as UTF-8."""
    with pytest.raises(DatabaseNotReadyError):
        check_database_ready(str(tmp_path / "bad\udcff.db"))


def test_symlink_to_a_wal_database_reads_the_wal(tmp_path: Path) -> None:
    """The -wal sits beside the target, not beside the link."""
    variant = build_ready_wal_with_wal("ready_wal_with_wal", tmp_path)
    assert variant.path is not None
    link = tmp_path / "link.db"
    link.symlink_to(variant.path)
    try:
        check_database_ready(str(link))
    finally:
        assert variant.keep_alive is not None
        variant.keep_alive.close()


def test_file_uri_leaves_no_wal_files_behind(tmp_path: Path) -> None:
    path = _idle_wal_database(tmp_path)
    before = sorted(p.name for p in tmp_path.iterdir())
    check_database_ready(f"file:{path}")
    assert sorted(p.name for p in tmp_path.iterdir()) == before


@pytest.mark.parametrize("args", [["match", "MIT"], ["is-osi", "MIT"]])
def test_second_check_failing_still_exits_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, args: list[str]
) -> None:
    """The file changes between the command's check and the matcher's: the
    refusal is an exit 2 with one line, not a traceback and exit 1."""
    monkeypatch.setattr(cli_module, "check_database_ready", lambda _path: None)
    missing = tmp_path / "gone.db"
    result = CliRunner().invoke(cli, ["--db", str(missing), *args])
    assert result.exit_code == 2
    assert result.stdout == ""
    assert result.stderr == (
        f"ERROR: database: not found: {missing}; run 'licenseid update'\n"
    )


def test_required_columns_exist_in_the_schema_licenseid_writes(
    tmp_path: Path,
) -> None:
    """A column named in the readiness probe but missing from the schema would
    make every database look unreadable."""
    path = tmp_path / "schema.db"
    LicenseDatabase(str(path))
    with sqlite3.connect(str(path)) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(licenses)")}
    required = {name.strip() for name in _REQUIRED_COLUMNS.split(",")}
    assert required <= columns
