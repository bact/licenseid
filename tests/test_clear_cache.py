# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``--clear-cache`` from the path alone.

Written from the contract, not the code: clearing never opens the database,
so it still removes one SQLite cannot read; it refuses a file licenseid did
not build, because it deletes; and it never creates the default directory.
"""

# pylint: disable=missing-function-docstring,redefined-outer-name

import os
import sqlite3
from pathlib import Path

import pytest
from db_asserts import (  # noqa: F401  # pylint: disable=unused-import
    assert_no_traceback,
    db_in_an_unreadable_directory,
    safe_home,  # an autouse fixture: imported to apply it here
)
from db_asserts import (
    run_args as run,
)
from db_variants import make_ready_file_db

from licenseid.database import LicenseDatabase
from licenseid.errors import DatabaseNotReadyError

CACHE_NAMES = (
    "licenses.json",
    "popularity.csv",
    "spdx-data-v3.30.tar.gz",
    "licenses.json.1234.tmp",
    "popularity.csv.99.tmp",
    "spdx-data-v3.30.tar.gz.7.tmp",
)


# --------------------------------------------------------------------------
# --clear-cache: it works from the path alone
# --------------------------------------------------------------------------


def test_clear_cache_on_a_directory_gives_no_traceback(tmp_path: Path) -> None:
    """--db names a directory: unlink() on it fails, and the user must get a
    grammar line, not an IsADirectoryError traceback."""
    db_dir = tmp_path / "licenses.db"
    db_dir.mkdir()
    (db_dir / "inside.txt").write_text("x\n", encoding="utf-8")
    result = run("--db", str(db_dir), "--clear-cache")
    assert_no_traceback(result)
    assert db_dir.is_dir(), "the directory was removed"


@pytest.mark.parametrize(
    "db_arg",
    [":memory:", "file::memory:", "file:advcache?mode=memory&cache=shared"],
)
def test_clear_cache_with_a_memory_db_keeps_cwd_cache_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, db_arg: str
) -> None:
    """An in-memory database has no directory, so --clear-cache has nothing to
    clear. It must not fall back to the working directory and delete the cache
    files (or a stray tarball) that happen to sit there."""
    work = tmp_path / "work"
    work.mkdir()
    for name in CACHE_NAMES:
        (work / name).write_text("keep me\n", encoding="utf-8")
    monkeypatch.chdir(work)
    result = run("--db", db_arg, "--clear-cache")
    assert_no_traceback(result)
    assert result.exit_code == 0 and result.stderr == "Clearing cache...\n"
    survivors = sorted(p.name for p in work.iterdir())
    assert survivors == sorted(CACHE_NAMES), f"deleted from cwd: {survivors}"


def test_clear_cache_on_a_relative_path_clears_beside_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    work = tmp_path / "work"
    (work / "sub").mkdir(parents=True)
    for name in CACHE_NAMES:
        (work / "sub" / name).write_text("x\n", encoding="utf-8")
    (work / "sub" / "licenses.db").write_bytes(b"SQLite format 3\x00" + b"\xff" * 512)
    (work / "sub" / "keep.txt").write_text("x\n", encoding="utf-8")
    monkeypatch.chdir(work)
    result = run("--db", "sub/licenses.db", "--clear-cache")
    assert_no_traceback(result)
    assert result.exit_code == 0, result.stderr
    assert sorted(p.name for p in (work / "sub").iterdir()) == ["keep.txt"]


def test_clear_cache_removes_a_corrupt_db_and_its_cache_but_no_foreign_file(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "licenses.db"
    db_path.write_bytes(b"SQLite format 3\x00" + b"\xff" * 4096)
    for name in CACHE_NAMES:
        (tmp_path / name).write_text("x\n", encoding="utf-8")
    for name in ("exceptions.json", "spdx-data.tar.gz", "licenses.db.bak"):
        (tmp_path / name).write_text("x\n", encoding="utf-8")
    result = run("--db", str(db_path), "--clear-cache")
    assert_no_traceback(result)
    assert result.exit_code == 0, result.stderr
    assert result.stdout == "", result.stdout
    assert sorted(p.name for p in tmp_path.iterdir() if p.name != "home") == [
        "exceptions.json",
        "licenses.db.bak",
        "spdx-data.tar.gz",
    ]


def test_clear_cache_that_cannot_delete_says_so_in_one_line(tmp_path: Path) -> None:
    """A read-only directory: the OS refuses the delete, and the user gets a
    grammar line and exit 2, not a traceback."""
    directory = tmp_path / "locked"
    directory.mkdir()
    db_path = make_ready_file_db(directory / "licenses.db")
    directory.chmod(0o555)
    try:
        result = run("--db", str(db_path), "--clear-cache")
    finally:
        directory.chmod(0o755)
    assert_no_traceback(result)
    assert result.exit_code == 2, result.stderr
    assert result.stdout == ""
    # Progress lines come first; the failure is the last line, and only one.
    last = result.stderr.splitlines()[-1]
    # Nothing was read: the condition names the delete, not the reading.
    assert last.startswith(f"ERROR: database: delete failed: {db_path}: ")
    assert last.count(str(db_path)) == 1, last
    assert db_path.exists()


def test_clear_cache_twice_is_idempotent(tmp_path: Path) -> None:
    db_path = make_ready_file_db(tmp_path / "licenses.db")
    (tmp_path / "licenses.json").write_text("{}\n", encoding="utf-8")
    first = run("--db", str(db_path), "--clear-cache")
    second = run("--db", str(db_path), "--clear-cache")
    for result in (first, second):
        assert_no_traceback(result)
        assert result.exit_code == 0, result.stderr
        assert result.stdout == "", result.stdout
    assert not db_path.exists()


def test_clear_cache_with_a_nonexistent_parent_succeeds(tmp_path: Path) -> None:
    db_path = tmp_path / "nodir" / "deeper" / "licenses.db"
    result = run("--db", str(db_path), "--clear-cache")
    assert_no_traceback(result)
    assert result.exit_code == 0, result.stderr
    assert not db_path.parent.exists(), "clear-cache created the directory"


def test_clear_cache_with_an_explicit_db_does_not_create_the_default_dir(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "elsewhere" / "licenses.db"
    db_path.parent.mkdir()
    result = run("--db", str(db_path), "--clear-cache")
    assert_no_traceback(result)
    assert not (tmp_path / "home" / ".local").exists(), "default dir was created"


def test_clear_cache_on_a_symlink_does_not_leave_a_live_database(
    tmp_path: Path,
) -> None:
    """The link is what --db names; after clearing, nothing readable may be
    left at that path."""
    target = make_ready_file_db(tmp_path / "real.db")
    link = tmp_path / "licenses.db"
    link.symlink_to(target)
    result = run("--db", str(link), "--clear-cache")
    assert_no_traceback(result)
    assert not link.exists(), "a readable database is still at the --db path"
    assert target.exists(), "the link's target was deleted, not the link"


def test_clear_cache_on_a_dangling_symlink_leaves_nothing_behind(
    tmp_path: Path,
) -> None:
    link = tmp_path / "licenses.db"
    link.symlink_to(tmp_path / "gone.db")
    result = run("--db", str(link), "--clear-cache")
    assert_no_traceback(result)
    assert not link.is_symlink(), "the dangling link survived clear-cache"


# --------------------------------------------------------------------------
# --clear-cache deletes, so it refuses what licenseid did not build
# --------------------------------------------------------------------------


def _foreign_database(path: Path) -> bytes:
    """Another program's SQLite file that happens to hold a `licenses` table."""
    with sqlite3.connect(str(path)) as conn:
        conn.execute("CREATE TABLE licenses (id INTEGER PRIMARY KEY, seats INT)")
        conn.execute("INSERT INTO licenses VALUES (1, 50)")
    return path.read_bytes()


def test_clear_cache_refuses_another_programs_database(tmp_path: Path) -> None:
    """One mistyped --db must not destroy somebody else's database."""
    db_path = tmp_path / "inventory.db"
    before = _foreign_database(db_path)
    for name in CACHE_NAMES:
        (tmp_path / name).write_text("x\n", encoding="utf-8")
    result = run("--db", str(db_path), "--clear-cache")
    assert_no_traceback(result)
    assert result.exit_code == 2
    assert result.stdout == ""
    assert result.stderr == f"ERROR: database: invalid: {db_path}\n"
    assert db_path.read_bytes() == before
    # Nothing beside it either: the refusal stops before the first unlink.
    assert sorted(p.name for p in tmp_path.iterdir() if p.is_file()) == sorted(
        [*CACHE_NAMES, db_path.name]
    )


def test_clear_cache_refuses_a_file_that_is_not_a_database(tmp_path: Path) -> None:
    """No SQLite header: notes, a spreadsheet, anything reached by a typo."""
    notes = tmp_path / "notes.txt"
    notes.write_text("shopping list\n", encoding="utf-8")
    result = run("--db", str(notes), "--clear-cache")
    assert result.exit_code == 2
    assert result.stderr == f"ERROR: database: invalid: {notes}\n"
    assert notes.exists()


def test_clear_cache_still_removes_a_damaged_database(tmp_path: Path) -> None:
    """The header is there, so it is licenseid's own file to clear: the
    recovery command must not be refused by the damage it exists to clear."""
    db_path = tmp_path / "licenses.db"
    db_path.write_bytes(b"SQLite format 3\x00" + b"\xff" * 4096)
    result = run("--db", str(db_path), "--clear-cache")
    assert result.exit_code == 0, result.stderr
    assert not db_path.exists()


def test_clear_cache_through_a_file_uri_clears_the_directory(tmp_path: Path) -> None:
    """A file: URI names a real file, so it has a cache directory too."""
    db_path = make_ready_file_db(tmp_path / "licenses.db")
    for name in CACHE_NAMES:
        (tmp_path / name).write_text("x\n", encoding="utf-8")
    result = run("--db", f"file:{db_path}", "--clear-cache")
    assert result.exit_code == 0, result.stderr
    assert [p.name for p in tmp_path.iterdir() if p.is_file()] == []


def test_clear_cache_removes_the_sqlite_sidecars(tmp_path: Path) -> None:
    """A stale -wal would be replayed into the next database built here."""
    db_path = make_ready_file_db(tmp_path / "licenses.db")
    for suffix in ("-wal", "-shm", "-journal"):
        db_path.with_name(db_path.name + suffix).write_bytes(b"stale")
    result = run("--db", str(db_path), "--clear-cache")
    assert result.exit_code == 0, result.stderr
    assert [p.name for p in tmp_path.iterdir() if p.is_file()] == []


def test_a_sidecar_that_vanishes_between_check_and_unlink_is_not_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Another process (a second --clear-cache, a temp reaper) removes the
    -wal after the check sees it: a race, not a failure to report."""
    db_path = make_ready_file_db(tmp_path / "licenses.db")
    wal = db_path.with_name(db_path.name + "-wal")
    wal.write_bytes(b"stale")
    real_unlink = Path.unlink

    def racing_unlink(self: Path, missing_ok: bool = False) -> None:
        if self == wal:
            real_unlink(self)  # the other process gets there first
        real_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", racing_unlink)
    result = run("--db", str(db_path), "--clear-cache")
    assert_no_traceback(result)
    assert result.exit_code == 0, result.stderr
    assert not wal.exists()


@pytest.mark.parametrize("arg", [".", "/"])
def test_clear_cache_refuses_a_path_that_names_no_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, arg: str
) -> None:
    """--db . would clear the working directory's cache files and then fail
    on a database whose name is empty. Nothing may be removed first."""
    work = tmp_path / "work"
    work.mkdir()
    for name in CACHE_NAMES:
        (work / name).write_text("x\n", encoding="utf-8")
    monkeypatch.chdir(work)
    result = run("--db", arg, "--clear-cache")
    assert_no_traceback(result)
    assert result.exit_code == 2
    assert result.stderr == f"ERROR: database: invalid: {arg}\n"
    assert sorted(p.name for p in work.iterdir()) == sorted(CACHE_NAMES)


def test_clear_cache_refuses_a_file_it_may_not_read(tmp_path: Path) -> None:
    """Deleting needs no read permission, so without this the less readable
    file would be the one destroyed."""
    notes = tmp_path / "notes.txt"
    notes.write_text("private\n", encoding="utf-8")
    notes.chmod(0o000)
    try:
        if os.access(str(notes), os.R_OK):
            pytest.skip("this user can read a 000 file (root?)")
        result = run("--db", str(notes), "--clear-cache")
    finally:
        notes.chmod(0o644)
    assert result.exit_code == 2, result.stderr
    assert result.stderr == f"ERROR: database: invalid: {notes}\n"
    assert notes.exists()


def test_a_file_that_vanishes_before_its_header_is_read_is_not_claimed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """It was a regular file a moment ago and is gone now: licenseid cannot
    say it built it, so it must not delete whatever is there next."""
    db_path = make_ready_file_db(tmp_path / "licenses.db")

    def failing_open(*args: object, **kwargs: object) -> None:
        raise OSError(5, "Input/output error")

    monkeypatch.setattr("licenseid.dbcheck.open", failing_open, raising=False)
    result = run("--db", str(db_path), "--clear-cache")
    assert result.exit_code == 2, result.stderr
    assert result.stderr == f"ERROR: database: invalid: {db_path}\n"
    assert db_path.exists()


def test_clear_cache_refuses_a_path_it_may_not_look_at(tmp_path: Path) -> None:
    """The parent directory cannot be searched, so nothing is known about the
    file: it may be anybody's, and deleting it is not licenseid's call."""
    db_path = db_in_an_unreadable_directory(tmp_path)
    try:
        result = run("--db", str(db_path), "--clear-cache")
    finally:
        db_path.parent.chmod(0o755)
    assert result.exit_code == 2, result.stderr
    assert result.stderr == f"ERROR: database: invalid: {db_path}\n"
    assert db_path.exists()


@pytest.mark.parametrize("spelling", ["{p}", "{p}/", "{p}/.", "{p}/././."])
def test_every_spelling_of_one_path_decides_the_same_way(
    tmp_path: Path, spelling: str
) -> None:
    """Path() drops a trailing separator and a "/.", os.stat does not. Unless
    the name is normalised once, a foreign file is checked under one spelling
    and deleted under another."""
    foreign = tmp_path / "notes.db"
    with sqlite3.connect(str(foreign)) as conn:
        conn.execute("CREATE TABLE notes (a TEXT)")
        conn.execute("INSERT INTO notes VALUES ('precious')")
    before = foreign.read_bytes()
    result = run("--db", spelling.format(p=foreign), "--clear-cache")
    assert_no_traceback(result)
    assert result.exit_code == 2, result.stderr
    assert "database: invalid" in result.stderr
    assert foreign.read_bytes() == before, "a foreign database was deleted"


@pytest.mark.parametrize("spelling", ["{p}", "{p}/", "{p}/.", "{p}/././."])
def test_every_spelling_clears_licenseids_own_database(
    tmp_path: Path, spelling: str
) -> None:
    """The other half: the spellings must not refuse a database either."""
    db_path = make_ready_file_db(tmp_path / "licenses.db")
    result = run("--db", spelling.format(p=db_path), "--clear-cache")
    assert result.exit_code == 0, result.stderr
    assert not db_path.exists()


@pytest.mark.parametrize("db_arg", ["file:{p}?vfs=unix", "file://otherhost{p}"])
def test_clear_cache_refuses_a_uri_whose_file_it_cannot_identify(
    tmp_path: Path, db_arg: str
) -> None:
    """Only SQLite can resolve these: another machine's name, or a VFS that
    need not read a file. Exiting 0 would report a cache cleared that is
    still there; deleting a guess would be worse."""
    db_path = make_ready_file_db(tmp_path / "licenses.db")
    (tmp_path / "licenses.json").write_text("x\n", encoding="utf-8")
    result = run("--db", db_arg.format(p=db_path), "--clear-cache")
    assert_no_traceback(result)
    assert result.exit_code == 2, result.stderr
    assert "database: invalid" in result.stderr
    assert db_path.exists()
    assert (tmp_path / "licenses.json").exists()


def test_the_api_refuses_a_path_it_cannot_even_look_at() -> None:
    """A NUL cannot be a file name. The API must still refuse in its own
    grammar, not raise the ValueError os.stat throws."""
    with pytest.raises(DatabaseNotReadyError, match="database: invalid: "):
        LicenseDatabase.clear_cache("a\x00b.db")


def test_a_sidecar_that_cannot_be_removed_does_not_fail_a_done_delete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The database is gone, so a stale -wal cannot be replayed into
    anything: reporting one would say the delete failed when it succeeded."""
    db_path = make_ready_file_db(tmp_path / "licenses.db")
    wal = db_path.with_name(db_path.name + "-wal")
    wal.write_bytes(b"stale")
    real_unlink = Path.unlink

    def refusing_unlink(self: Path, missing_ok: bool = False) -> None:
        if self == wal:
            raise PermissionError(1, "Operation not permitted", str(self))
        real_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", refusing_unlink)
    result = run("--db", str(db_path), "--clear-cache")
    assert_no_traceback(result)
    assert result.exit_code == 0, result.stderr
    assert not db_path.exists()


@pytest.mark.parametrize("template", ["file:{p}", "file://{p}", "file://localhost{p}"])
def test_clear_cache_through_every_local_uri_spelling(
    tmp_path: Path, template: str
) -> None:
    """An empty authority and "localhost" both name this machine's file, so
    all three name the same database and must clear the same directory."""
    db_path = make_ready_file_db(tmp_path / "licenses.db")
    (tmp_path / "licenses.json").write_text("x\n", encoding="utf-8")
    result = run("--db", template.format(p=db_path), "--clear-cache")
    assert result.exit_code == 0, result.stderr
    assert [p.name for p in tmp_path.iterdir() if p.is_file()] == []
