# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``resolve()`` keeps its choice of list per file stamp (R7): a repeat on an
unchanged file opens no connection to choose, and every change of the file,
the path or the packaged index is seen at the next call."""
# pylint: disable=missing-function-docstring

import os
import sqlite3
import threading
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
from conftest import posix_only
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from db_variants import IS_ROOT, make_ready_file_db, writer
from release_fakes import release_bundle, ship

from licenseid import dbcheck, listindex, listsource, resolve, spdxdata
from licenseid.datadir import get_default_db_path
from licenseid.errors import DatabaseNotReadyError
from licenseid.listlookup import ListLookup
from licenseid.resolvertypes import ListSource, Source

DB_VERSION = "3.30"  # the List of a database made here


def _default_db(version: str = DB_VERSION) -> Path:
    path = Path(get_default_db_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    make_ready_file_db(path)
    _set_version(path, version)
    return path


def _set_version(path: Path, version: str) -> None:
    """Rewrite the List version of the file at *path* and give the file a
    stamp it has not had (a write alone may leave the same nanosecond)."""
    before = path.stat().st_mtime_ns
    with writer(path) as conn:
        conn.execute(
            "UPDATE db_metadata SET value = ? WHERE key = 'license_list_version'",
            (version,),
        )
    os.utime(path, ns=(before + 10**9, before + 10**9))


def _source() -> str:
    return resolve("MIT")["lists"][0]["source"]


def _choose(source: Source = "auto") -> ListLookup:
    return listsource.choose_list(None, source)[0]


# --- the proof: connections ---


@pytest.mark.parametrize("source", ["auto", "database"])
def test_a_repeat_opens_only_the_connection_of_its_reading_block(
    monkeypatch: pytest.MonkeyPatch,
    opened: list[sqlite3.Connection],
    source: Source,
) -> None:
    ship(monkeypatch, release_bundle("3.29"))
    _default_db()
    resolve("MIT", source=source)
    first = len(opened)
    assert first >= 3  # the readiness check, the database, its metadata...
    opened.clear()
    for _ in range(5):
        resolve("MIT", source=source)
    assert len(opened) == 5  # one reading() block each, nothing to choose


@pytest.mark.parametrize("source", ["auto", "database"])
def test_the_choice_is_the_same_object_while_the_file_is_unchanged(
    monkeypatch: pytest.MonkeyPatch,
    opened: list[sqlite3.Connection],
    source: Source,
) -> None:
    ship(monkeypatch, release_bundle("3.29"))
    _default_db()
    first = _choose(source)
    opened.clear()
    assert _choose(source) is first
    assert not opened


def test_a_packaged_choice_costs_no_connection_on_a_repeat(
    monkeypatch: pytest.MonkeyPatch, opened: list[sqlite3.Connection]
) -> None:
    ship(monkeypatch, release_bundle("9.99"))
    _default_db()
    assert _source() == "packaged"
    opened.clear()
    assert [_source() for _ in range(3)] == ["packaged"] * 3
    assert not opened


# --- the file changes ---


def test_an_update_between_two_calls_is_seen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ship(monkeypatch, release_bundle("3.29"))
    path = _default_db("3.30")
    assert _source() == "database"
    _set_version(path, "3.28")  # what an update to an older list leaves
    assert _source() == "packaged"
    _set_version(path, "3.31")
    assert _source() == "database"


def test_a_rewrite_that_keeps_size_and_time_is_not_a_change_but_a_new_inode_is(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ship(monkeypatch, release_bundle("3.29"))
    path = _default_db("3.30")
    first = _choose()
    stat = path.stat()
    copy = path.with_name("copy.db")
    copy.write_bytes(path.read_bytes())
    os.utime(copy, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    os.replace(copy, path)  # same size, same time, another file
    assert _choose() is not first


def test_a_change_of_size_alone_is_seen(monkeypatch: pytest.MonkeyPatch) -> None:
    ship(monkeypatch, release_bundle("3.29"))
    path = _default_db()
    first = _choose()
    stat = path.stat()
    with path.open("ab") as handle:
        handle.write(b"\0")
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))  # same time, same inode
    assert _choose() is not first


def test_a_file_created_after_not_found_is_seen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ship(monkeypatch, release_bundle("3.29"))
    assert _source() == "packaged"
    assert _source() == "packaged"
    _default_db()
    assert _source() == "database"


def test_a_file_deleted_after_a_database_choice_falls_back(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    ship(monkeypatch, release_bundle("3.29"))
    path = _default_db()
    assert _source() == "database"
    path.unlink()
    assert _source() == "packaged"
    assert capsys.readouterr().err == ""  # not found is silent, as it was


def test_a_file_deleted_with_no_bundle_raises_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ship(monkeypatch, None)
    path = _default_db()
    assert _source() == "database"
    path.unlink()
    with pytest.raises(DatabaseNotReadyError, match="^database: not found: "):
        resolve("MIT")
    with pytest.raises(DatabaseNotReadyError, match="^database: not found: "):
        resolve("MIT", source="database")


def test_a_database_that_breaks_is_seen_and_said_once(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    ship(monkeypatch, release_bundle("3.29"))
    path = _default_db()
    assert _source() == "database"
    path.write_bytes(b"")
    assert [_source(), _source()] == ["packaged", "packaged"]
    assert capsys.readouterr().err == (
        f"WARNING: database: empty: {path}; using packaged data v3.29\n"
    )


# --- nothing stale is kept ---


def test_a_choice_that_raised_is_not_kept(monkeypatch: pytest.MonkeyPatch) -> None:
    ship(monkeypatch, None)
    for source in ("auto", "database"):
        with pytest.raises(DatabaseNotReadyError):
            resolve("MIT", source=source)
    assert not listsource._kept  # pylint: disable=protected-access
    _default_db()
    assert _source() == "database"
    assert resolve("MIT", source="database")["lists"][0]["source"] == "database"


def test_another_home_picks_its_own_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    ship(monkeypatch, release_bundle("3.29"))
    _default_db()
    first = _choose()
    assert _source() == "database"
    other = tmp_path / "other-home"
    other.mkdir()
    monkeypatch.setattr(Path, "home", staticmethod(lambda: other))
    assert _source() == "packaged"  # nothing at the new path
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path / "home"))
    assert _source() == "database"
    assert _choose() is not first  # chosen again: kept the last only


@posix_only
def test_another_path_to_the_same_file_is_another_choice(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Same stamp (a hard link), so only the path tells the two homes apart."""
    ship(monkeypatch, release_bundle("3.29"))
    path = _default_db()
    first = _choose()
    other = tmp_path / "other-home"
    target = Path(str(path).replace(str(tmp_path / "home"), str(other)))
    target.parent.mkdir(parents=True)
    os.link(path, target)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: other))
    assert _choose() is not first


def test_another_packaged_index_is_seen(monkeypatch: pytest.MonkeyPatch) -> None:
    """The index is swapped without ``ship``, which forgets the choice too."""

    def swap(raw: bytes | None) -> None:
        monkeypatch.setattr(spdxdata, "packaged_bundle", lambda: raw)
        listindex.reset_packaged_index()

    ship(monkeypatch, release_bundle("3.29"))
    _default_db()
    assert _source() == "database"
    swap(release_bundle("9.99"))
    assert _source() == "packaged"
    swap(None)
    assert _source() == "database"


@pytest.mark.parametrize("error", [PermissionError, NotADirectoryError, OSError])
def test_a_stat_error_chooses_again(
    monkeypatch: pytest.MonkeyPatch, error: type[OSError]
) -> None:
    ship(monkeypatch, release_bundle("3.29"))
    _default_db()
    first = _choose()
    real = listsource._choose  # pylint: disable=protected-access
    with mock.patch.object(
        listsource, "_choose", autospec=True, side_effect=real
    ) as again:
        with mock.patch("os.stat", autospec=True, side_effect=error("no")):
            for _ in range(3):
                _choose()
        assert again.call_count == 3  # never a stale hit
        assert _choose() is first  # the fallback of the errors was not kept
        assert again.call_count == 3


def test_a_reset_forgets_the_choice(monkeypatch: pytest.MonkeyPatch) -> None:
    ship(monkeypatch, release_bundle("3.29"))
    _default_db()
    first = _choose()
    listsource.reset_choice()
    assert _choose() is not first


def test_threads_settle_on_one_choice(monkeypatch: pytest.MonkeyPatch) -> None:
    ship(monkeypatch, release_bundle("3.29"))
    _default_db()
    found: list[ListLookup] = []
    barrier = threading.Barrier(6)

    def work() -> None:
        barrier.wait()
        found.append(_choose())

    threads = [threading.Thread(target=work) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(found) == 6  # the first callers may each choose; none fails
    settled = _choose()
    assert all(_choose() is settled for _ in range(6))


# --- review of T5b: what must not be kept, what must be seen ---


def test_a_lock_held_during_the_first_call_is_not_kept(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``unreadable`` passes by itself: the file's stamp does not change when
    the lock is released, so a fallback made for it must not be kept."""
    ship(monkeypatch, release_bundle("3.29"))
    monkeypatch.setattr(dbcheck, "_BUSY_WAIT", 0.0)  # do not wait for the lock
    path = _default_db()
    locker = sqlite3.connect(path, timeout=0, isolation_level=None)
    try:
        locker.execute("BEGIN EXCLUSIVE")
        real = sqlite3.connect

        def no_wait(*args: Any, **kwargs: Any) -> sqlite3.Connection:
            kwargs["timeout"] = 0  # the default waits 5 s for the lock
            conn: sqlite3.Connection = real(*args, **kwargs)
            return conn

        monkeypatch.setattr(sqlite3, "connect", no_wait)
        locked = _source()
        monkeypatch.setattr(sqlite3, "connect", real)
        locker.execute("ROLLBACK")
    finally:
        locker.close()
    assert locked == "packaged"  # the lock makes the database unreadable
    capsys.readouterr()
    assert _source() == "database"


@posix_only
def test_a_chmod_is_seen_though_the_mtime_is_restored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if IS_ROOT:
        pytest.skip("root reads through chmod 000")
    ship(monkeypatch, release_bundle("3.29"))
    path = _default_db()
    assert _source() == "database"
    stat = path.stat()
    path.chmod(0)
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    try:
        assert _source() == "packaged"
        with pytest.raises(DatabaseNotReadyError):
            resolve("MIT", source="database")
    finally:
        path.chmod(0o644)


@posix_only
def test_a_header_corrupted_in_place_is_seen_though_the_mtime_is_restored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ship(monkeypatch, release_bundle("3.29"))
    path = _default_db()
    assert _source() == "database"
    stat = path.stat()
    with path.open("r+b") as handle:
        handle.write(b"X" * 16)  # the size is the same
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert _source() == "packaged"
    with pytest.raises(DatabaseNotReadyError):
        resolve("MIT", source="database")


def test_the_stamp_is_read_before_the_choice(monkeypatch: pytest.MonkeyPatch) -> None:
    """A file rewritten while the choice is made is chosen again next time."""
    ship(monkeypatch, release_bundle("3.29"))
    path = _default_db("3.30")
    real = listsource._choose  # pylint: disable=protected-access

    def rewrite_then_choose(
        mode: Source, where: str | None
    ) -> tuple[ListLookup, ListSource, bool]:
        _set_version(path, "3.28")
        return real(mode, where)

    with mock.patch.object(
        listsource, "_choose", autospec=True, side_effect=rewrite_then_choose
    ) as spy:
        _source()
        _source()
    assert spy.call_count == 2
