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

import contextlib
import os
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from click.testing import CliRunner
from db_asserts import assert_refused, expected_refusal, run_cli
from db_variants import NOT_FOUND, build_ready_wal_with_wal, make_ready_file_db

from licenseid import cli as cli_module
from licenseid.cli import cli
from licenseid.database import LicenseDatabase
from licenseid.dbcheck import (
    _REQUIRED_COLUMNS,
    _open_condition,
    _open_failure,
    _read_only_uri,
    check_database_ready,
    reject_foreign_database,
)
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
    result = run_cli(f"{prefix}nope.db", ["is-osi", "MIT"])
    assert_refused(result, NOT_FOUND, f"{prefix}nope.db")
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


@pytest.mark.parametrize("via", ["path", "symlink", "file_uri"])
def test_a_wal_database_is_never_read_as_immutable(tmp_path: Path, via: str) -> None:
    """Immutable turns locking off. Every database licenseid writes is in WAL
    mode, so reading one that way would race with a running ``update``."""
    path = _idle_wal_database(tmp_path)
    if via == "symlink":
        link = tmp_path / "link.db"
        link.symlink_to(path)
        path = link
    arg = f"file:{path}" if via == "file_uri" else str(path)
    assert "immutable" not in _read_only_uri(arg)
    assert _read_only_uri(arg).endswith("mode=ro")


def test_uri_keeps_an_explicit_immutable(tmp_path: Path) -> None:
    """The user's own URI parameters are theirs to choose."""
    uri = _read_only_uri(f"file:{_idle_wal_database(tmp_path)}?immutable=1")
    assert "immutable=1" in uri
    assert "mode=ro" in uri


def test_uri_with_an_empty_authority_is_ready(tmp_path: Path) -> None:
    """``file:///abs/path`` is the same file as ``file:/abs/path``."""
    path = make_ready_file_db(tmp_path / "auth.db")
    check_database_ready(f"file://{path}")


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
    with pytest.raises(DatabaseNotReadyError, match="database: not found: "):
        check_database_ready("file:/tmp/a\x00b.db")


def test_a_path_that_is_not_utf8_keeps_its_bytes(tmp_path: Path) -> None:
    """A lone surrogate (a file name byte that is not UTF-8) is percent-encoded
    as the raw byte, not refused as an encoding error."""
    assert "bad%FF.db?mode=ro" in _read_only_uri(str(tmp_path / "bad\udcff.db"))
    with pytest.raises(DatabaseNotReadyError, match="database: not found: "):
        check_database_ready(str(tmp_path / "bad\udcff.db"))


def _make_non_utf8_named_db(directory: Path) -> str:
    """A ready database at ``<directory>/lic\\xff.db``, or skip the test where
    the file system refuses the name (Linux allows it, macOS does not)."""
    name = os.fsdecode(os.fsencode(directory) + b"/lic\xff.db")
    try:
        make_ready_file_db(Path(name))
    except (OSError, UnicodeError, sqlite3.OperationalError):
        pytest.skip("this file system refuses a non-UTF-8 file name")
    return name


def test_a_ready_database_with_a_non_utf8_name_is_ready(tmp_path: Path) -> None:
    name = _make_non_utf8_named_db(tmp_path)
    check_database_ready(name)


@pytest.mark.parametrize("suffix", ["", "?mode=ro"])
def test_a_missing_file_uri_is_not_found(tmp_path: Path, suffix: str) -> None:
    """The same condition as a missing plain path, with the same action."""
    uri = f"file:{tmp_path / 'nope.db'}{suffix}"
    with pytest.raises(DatabaseNotReadyError) as info:
        check_database_ready(uri)
    assert f"ERROR: {info.value}\n" == expected_refusal(NOT_FOUND, uri)


def test_a_file_uri_with_a_percent_encoded_non_utf8_name_is_found(
    tmp_path: Path,
) -> None:
    """The name is decoded to bytes, so it is looked up as it is on disk."""
    _make_non_utf8_named_db(tmp_path)
    check_database_ready(f"file:{tmp_path}/lic%FF.db")


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


@pytest.mark.parametrize("args", [["match", "MIT"], ["is-osi", "MIT"]])
def test_second_check_failing_still_exits_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, args: list[str]
) -> None:
    """The file changes between the command's check and the matcher's: the
    refusal is an exit 2 with one line, not a traceback and exit 1."""
    monkeypatch.setattr(cli_module, "check_database_ready", lambda _path: None)
    missing = tmp_path / "gone.db"
    result = run_cli(str(missing), args)
    assert_refused(result, NOT_FOUND, str(missing))


def test_required_columns_exist_in_the_schema_licenseid_writes(
    tmp_path: Path,
) -> None:
    """A column named in the readiness probe but missing from the schema would
    make every database look unreadable."""
    path = tmp_path / "schema.db"
    LicenseDatabase(str(path))
    with sqlite3.connect(str(path)) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(licenses)")}
    assert set(_REQUIRED_COLUMNS) <= columns


@pytest.mark.parametrize("scheme", ["file:", ""])
def test_a_path_with_a_non_utf8_byte_never_raises(tmp_path: Path, scheme: str) -> None:
    """argv gives a surrogate for such a byte; it is refused with a message
    (here 'not found'), not a traceback."""
    with pytest.raises(DatabaseNotReadyError, match="database: not found: "):
        check_database_ready(f"{scheme}{tmp_path}/lic\udcff.db")


def test_a_path_object_is_accepted(tmp_path: Path) -> None:
    """The API took a Path before the check existed."""
    check_database_ready(make_ready_file_db(tmp_path / "p.db"))
    with pytest.raises(DatabaseNotReadyError, match="database: not found: "):
        check_database_ready(tmp_path / "absent.db")


def test_a_uri_with_a_vfs_is_left_to_sqlite() -> None:
    """The name of a database in a non-default VFS need not be a file."""
    with pytest.raises(DatabaseNotReadyError, match="database: (empty|unreadable)"):
        check_database_ready("file:m1?vfs=memdb")


# A path the OS refuses to look at is not the same as one that is not there


def test_an_unreadable_parent_directory_is_not_reported_as_not_found(
    tmp_path: Path,
) -> None:
    """The database may well be there, and 'licenseid update' could not write
    it either, so the "run update" action would mislead."""
    inner = tmp_path / "inner"
    inner.mkdir()
    db_path = make_ready_file_db(inner / "licenses.db")
    inner.chmod(0o000)
    try:
        if os.access(str(db_path), os.R_OK):
            pytest.skip("this user can read through a 000 directory (root?)")
        with pytest.raises(DatabaseNotReadyError) as info:
            check_database_ready(str(db_path))
    finally:
        inner.chmod(0o755)
    assert str(info.value).startswith(f"database: unreadable: {db_path}: ")
    assert "licenseid update" not in str(info.value)


def test_a_symlink_loop_is_not_reported_as_not_found(tmp_path: Path) -> None:
    """os.path.exists() answers False for a loop; the file is not absent."""
    first, second = tmp_path / "a.db", tmp_path / "b.db"
    first.symlink_to(second)
    second.symlink_to(first)
    with pytest.raises(DatabaseNotReadyError) as info:
        check_database_ready(str(first))
    assert str(info.value).startswith(f"database: unreadable: {first}: ")


def test_a_dangling_symlink_is_still_not_found(tmp_path: Path) -> None:
    """Nothing is there, and 'licenseid update' is the way to put it there."""
    link = tmp_path / "link.db"
    link.symlink_to(tmp_path / "gone.db")
    with pytest.raises(DatabaseNotReadyError) as info:
        check_database_ready(str(link))
    assert f"ERROR: {info.value}\n" == expected_refusal(NOT_FOUND, str(link))


def test_a_hot_rollback_journal_is_not_called_unreadable(tmp_path: Path) -> None:
    """A read-only connection cannot roll back a hot journal, so SQLite says
    "database is locked" for a database an ordinary open would repair and
    read. The check gives no verdict rather than refusing a working file."""
    db_path = make_ready_file_db(tmp_path / "licenses.db")
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.close()
    journal = db_path.with_name(db_path.name + "-journal")
    journal.write_bytes(b"\xd9\xd5\x05\xf9\x20\xa1\x63\xd7" + b"\x00" * 504)
    check_database_ready(str(db_path))  # no verdict, so no refusal
    result = run_cli(str(db_path), ["is-osi", "MIT"])
    assert result.exit_code == 0, result.stderr
    assert "unreadable" not in result.stderr


@contextlib.contextmanager
def _exclusive_lock(db_path: Path) -> Iterator[None]:
    """Hold the write lock another process would hold."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA locking_mode=EXCLUSIVE")
    conn.execute("BEGIN EXCLUSIVE")
    conn.execute("UPDATE db_metadata SET value = value")
    try:
        yield
    finally:
        conn.rollback()
        conn.close()


def test_a_locked_database_gives_no_verdict_to_a_reader(tmp_path: Path) -> None:
    """Somebody else holds the write lock. That says nothing about the file,
    so a reader goes on and finds out for itself rather than being refused."""
    db_path = make_ready_file_db(tmp_path / "licenses.db")
    with _exclusive_lock(db_path):
        refusal = _open_condition(str(db_path))
        assert refusal is not None and refusal[0] == "unknown"
        check_database_ready(str(db_path))  # no verdict, so no refusal


def test_a_locked_database_is_never_written_to_or_deleted(tmp_path: Path) -> None:
    """The same "unknown" stops a write: the file could be anybody's, and
    deleting one needs no lock at all."""
    db_path = make_ready_file_db(tmp_path / "licenses.db")
    before = db_path.read_bytes()
    with _exclusive_lock(db_path):
        with pytest.raises(DatabaseNotReadyError, match="database: unreadable: "):
            reject_foreign_database(str(db_path))
        result = run_cli(str(db_path), ["--clear-cache"])
    assert result.exit_code == 2, result.stderr
    assert db_path.exists(), "a locked database was deleted"
    assert db_path.read_bytes() == before


@pytest.mark.parametrize("text", ["database is locked", "database table is locked"])
def test_every_lock_message_is_unknown_not_unreadable(text: str) -> None:
    """Pinned directly: which message SQLite gives for a real lock varies by
    build, and an unpinned string here would silently drop the protection."""
    assert _open_failure(sqlite3.OperationalError(text)) == "unknown"


def test_a_readonly_open_failure_gives_no_verdict_at_all() -> None:
    """A write-ahead log that cannot make its -shm is not in doubt; only this
    way of opening it is, so the command must go on."""
    assert (
        _open_failure(sqlite3.OperationalError("attempt to write a readonly database"))
        is None
    )
    assert (
        _open_failure(sqlite3.DatabaseError("file is not a database")) == "unreadable"
    )


def test_a_named_pipe_is_refused_rather_than_waited_on(tmp_path: Path) -> None:
    """The check opens read-only, and opening a FIFO that way waits for a
    writer that never comes: the command would hang with no exit code."""
    fifo = tmp_path / "p.db"
    try:
        os.mkfifo(fifo)
    except (AttributeError, OSError):
        pytest.skip("this platform has no named pipes")
    with pytest.raises(DatabaseNotReadyError) as info:
        check_database_ready(str(fifo))
    assert str(info.value) == f"database: unreadable: {fifo}: not a regular file"


def test_a_directory_is_still_left_to_sqlite_to_report(tmp_path: Path) -> None:
    """It cannot block, and SQLite's own wording says more than ours."""
    directory = tmp_path / "adir"
    directory.mkdir()
    with pytest.raises(DatabaseNotReadyError, match="database: unreadable: ") as info:
        check_database_ready(str(directory))
    assert "not a regular file" not in str(info.value)


@pytest.mark.parametrize("template", ["file://localhost{p}", "file:{p}?vfs=unix"])
def test_no_uri_spelling_of_a_named_pipe_waits_for_a_writer(
    tmp_path: Path, template: str
) -> None:
    """SQLite resolves these to the same file, so the check must too: it
    opens read-only, and that waits for a writer that never comes."""
    fifo = tmp_path / "p.db"
    try:
        os.mkfifo(fifo)
    except (AttributeError, OSError):
        pytest.skip("this platform has no named pipes")
    db_arg = template.format(p=fifo)
    with pytest.raises(DatabaseNotReadyError) as info:
        check_database_ready(db_arg)
    assert str(info.value) == f"database: unreadable: {db_arg}: not a regular file"


def test_a_uri_with_a_vfs_naming_no_file_is_still_left_to_sqlite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A VFS need not read a file, so a name with nothing at it decides
    nothing: only a file that would block the open does."""
    monkeypatch.chdir(tmp_path)
    with pytest.raises(DatabaseNotReadyError) as info:
        check_database_ready("file:m1?vfs=memdb")
    assert "not found" not in str(info.value)


def test_a_memory_uri_with_a_name_after_it_is_an_ordinary_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SQLite compares the whole name, so "file::memory:notes" opens a file
    called ":memory:notes". Treating it as memory would drop mode=ro and
    create it."""
    monkeypatch.chdir(tmp_path)
    with pytest.raises(DatabaseNotReadyError, match="database: not found: "):
        check_database_ready("file::memory:notes")
    assert not list(tmp_path.iterdir()), "the check created a file"


@pytest.mark.parametrize(
    "db_arg", [":memory:", "file::memory:", "file::memory:?cache=shared"]
)
def test_the_memory_spellings_are_still_memory(db_arg: str) -> None:
    with pytest.raises(DatabaseNotReadyError, match="database: empty: "):
        check_database_ready(db_arg)
