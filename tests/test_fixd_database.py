# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Fix batch D of the 0.7.0 review: the database handle and its inputs.

``LicenseDatabase(path)`` wrote licenseid's tables into another program's
SQLite file and made a file out of a mistyped name; ``detect()`` took any
object as ``file_path`` (an ``int`` was opened as a descriptor, read and
closed); ``DatabaseNotReadyError.condition`` and ``.detail`` were ``""`` for
nothing, where the API says ``None``; ``clear-cache`` named ``database`` as
the subject of a cache file it could not delete.
"""

# pylint: disable=missing-function-docstring,redefined-outer-name

import os
import sqlite3
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
from conftest import GivenWarnings, make_ready_db_path, posix_only
from db_asserts import (  # noqa: F401  # pylint: disable=unused-import
    refuse_unlink,
    safe_home,  # an autouse fixture: imported to apply it here
)
from db_asserts import run_args as run
from db_variants import make_ready_file_db
from packaged_list import database_of
from release_fakes import VERSION, release_bundle, ship

from licenseid import (
    DatabaseNotReadyError,
    LicenseDatabase,
    LicenseDetector,
    detect,
    resolve,
)
from licenseid.dbcheck import check_database_ready, is_ready

# --- 1. LicenseDatabase(path): another program's file, and a missing one ---


def names_in(path: Path) -> set[str]:
    with sqlite3.connect(path) as conn:
        return {row[0] for row in conn.execute("SELECT name FROM sqlite_master")}


def foreign_wal(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE foo (x)")
        conn.execute("INSERT INTO foo VALUES (1)")
    sqlite3.connect(path).close()  # the last connection removes -wal


def foreign_plain(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE foo (x)")
        conn.execute("INSERT INTO foo VALUES (1)")


def foreign_licenses_table(path: Path) -> None:
    """A table of licenseid's name with another schema: not a half-built
    database, so not one to complete."""
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE licenses (spdx_id TEXT, title TEXT)")
        conn.execute("INSERT INTO licenses VALUES ('MIT', 'MIT License')")


def not_sqlite(path: Path) -> None:
    path.write_text("not a database, " * 8, encoding="utf-8")


FOREIGN: dict[str, Callable[[Path], None]] = {
    "wal": foreign_wal,
    "plain": foreign_plain,
    "licenses-table": foreign_licenses_table,
    "text": not_sqlite,
}


@pytest.mark.parametrize("create", [True, False], ids=["create", "no-create"])
@pytest.mark.parametrize("kind", sorted(FOREIGN))
def test_a_foreign_file_is_refused_and_left_as_it_was(
    tmp_path: Path, kind: str, create: bool
) -> None:
    """P1 (was: ``LicenseDatabase('f.db')`` added licenseid's tables to a
    foreign file, and left a WAL one in WAL mode): the CLI refuses such a
    file on every command, and so does the handle, with or without create."""
    path = tmp_path / "f.db"
    FOREIGN[kind](path)
    before = path.read_bytes()
    names = names_in(path) if kind != "text" else None  # SQLite refuses text
    with pytest.raises(DatabaseNotReadyError, match="^database: (invalid|unreadable)"):
        LicenseDatabase(str(path), create=create)
    assert path.read_bytes() == before
    assert names is None or names_in(path) == names


def test_a_foreign_file_is_refused_when_named_by_uri(tmp_path: Path) -> None:
    path = tmp_path / "f.db"
    foreign_plain(path)
    with pytest.raises(DatabaseNotReadyError, match="^database: invalid: "):
        LicenseDatabase(path.as_uri())
    assert names_in(path) == {"foo"}


def test_a_foreign_file_appearing_before_the_first_write_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A handle on a name with no file waits for its first write; if another
    program has made the file by then, that write must not go into it."""
    path = tmp_path / "late.db"
    handle = LicenseDatabase(str(path))
    foreign_plain(path)
    ship(monkeypatch, release_bundle(VERSION))
    with pytest.raises(DatabaseNotReadyError, match="^database: invalid: "):
        handle.update_from_remote(source="packaged")
    assert names_in(path) == {"foo"}
    with pytest.raises(DatabaseNotReadyError, match="^database: invalid: "):
        handle._write_db_records([], [], [], None)  # pylint: disable=protected-access
    assert names_in(path) == {"foo"}


@pytest.mark.parametrize(
    "make",
    [
        lambda p: p.write_bytes(b""),
        lambda p: sqlite3.connect(p).close(),
        make_ready_file_db,
    ],
    ids=["zero-bytes", "no-tables", "ready"],
)
def test_an_empty_or_licenseid_file_is_still_opened_and_completed(
    tmp_path: Path, make: Callable[[Path], object]
) -> None:
    path = tmp_path / "licenses.db"
    make(path)
    LicenseDatabase(str(path))
    assert {"licenses", "license_index", "db_metadata"} <= names_in(path)


def spellings(path: Path) -> dict[str, object]:
    return {"str": str(path), "path": path, "uri": path.as_uri()}


@pytest.mark.parametrize("spelling", ["str", "path", "uri"])
def test_a_handle_on_a_missing_file_makes_no_file(
    tmp_path: Path, spelling: str
) -> None:
    """P1 (was: opening the handle made ``typo.db``)."""
    path = tmp_path / "typo.db"
    LicenseDatabase(spellings(path)[spelling])  # type: ignore[arg-type]
    assert not path.exists()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["home"]


@pytest.mark.parametrize("spelling", ["str", "path", "uri"])
def test_resolve_on_a_handle_on_a_missing_file_says_not_found_as_a_path_does(
    tmp_path: Path, spelling: str
) -> None:
    """P1 (was: ``database: empty``, after making the file)."""
    path = tmp_path / "typo.db"
    handle = LicenseDatabase(spellings(path)[spelling])  # type: ignore[arg-type]
    with pytest.raises(DatabaseNotReadyError) as by_handle:
        resolve("MIT", handle)
    with pytest.raises(DatabaseNotReadyError) as by_path:
        resolve("MIT", str(path))
    assert by_handle.value.condition == by_path.value.condition == "not found"
    assert str(by_handle.value).startswith("database: not found: ")
    assert str(by_handle.value).endswith("; run 'licenseid update'")
    assert not path.exists()


def test_reads_on_a_handle_on_a_missing_file_make_no_file(tmp_path: Path) -> None:
    path = tmp_path / "typo.db"
    handle = LicenseDatabase(str(path))
    with pytest.raises(DatabaseNotReadyError, match="^database: "):
        handle.get_metadata()
    with pytest.raises(DatabaseNotReadyError, match="^database: "):
        handle.get_license_details("MIT")
    with handle.reading(), pytest.raises(DatabaseNotReadyError):
        handle.search_candidates("permission is hereby granted")
    assert not path.exists()


def test_the_first_write_makes_the_file_and_its_tables(tmp_path: Path) -> None:
    """``update`` still creates the database it is given."""
    path = tmp_path / "licenses.db"
    handle = LicenseDatabase(str(path))
    assert not path.exists()
    handle._write_db_records([], [], [], None)  # pylint: disable=protected-access
    assert {"licenses", "license_index", "db_metadata"} <= names_in(path)
    assert "release_date" in handle.get_metadata()


def test_update_creates_a_missing_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ship(monkeypatch, release_bundle(VERSION))
    path = tmp_path / "licenses.db"
    database = database_of(release_bundle(VERSION), path)
    assert is_ready(str(path))
    assert database.get_metadata()["license_list_version"] == VERSION


def test_a_missing_directory_is_no_file_to_make(tmp_path: Path) -> None:
    path = tmp_path / "nodir" / "x.db"
    handle = LicenseDatabase(str(path))
    with pytest.raises(DatabaseNotReadyError, match="^database: not found: "):
        resolve("MIT", handle)
    assert not path.parent.exists()


def test_a_shared_in_memory_database_still_has_its_tables_at_once() -> None:
    handle = LicenseDatabase("file:fixd_memory?mode=memory&cache=shared")
    assert handle.get_metadata() == {}


# --- 2. file_path and db_path are paths ---

BAD_PATHS = [
    pytest.param(b"x", id="bytes"),
    pytest.param(1.5, id="float"),
    pytest.param(True, id="bool"),
    pytest.param(["x"], id="list"),
    pytest.param(object(), id="object"),
]


class BytesPath:
    """A path-like of bytes: it is no more a ``str`` path than bytes are."""

    def __fspath__(self) -> bytes:
        return b"x"


@pytest.fixture
def ready_db() -> Generator[Callable[[], str], None, None]:
    keep: list[sqlite3.Connection] = []

    def make() -> str:
        db_path, keep_alive = make_ready_db_path("fixd_types")
        keep.append(keep_alive)
        return db_path

    yield make
    for conn in keep:
        conn.close()


@pytest.mark.parametrize(
    "bad", [*BAD_PATHS, pytest.param(BytesPath(), id="bytes-path")]
)
@pytest.mark.parametrize("entry", ["method", "function"])
def test_detect_refuses_a_file_path_that_is_no_path(
    ready_db: Callable[[], str],
    monkeypatch: pytest.MonkeyPatch,
    bad: object,
    entry: str,
) -> None:
    """P2 (was: an ``int`` was opened as a descriptor, read and closed, and
    bytes failed late with a ``FileNotFoundError``)."""
    db_path = ready_db()
    monkeypatch.setattr("licenseid.keptdetector.get_default_db_path", lambda: db_path)
    call = LicenseDetector(db_path).detect if entry == "method" else detect
    with pytest.raises(TypeError, match="^file_path must be str or os.PathLike"):
        call(file_path=bad)  # type: ignore[arg-type]


@pytest.mark.parametrize("entry", ["method", "function"])
def test_an_int_file_path_leaves_the_callers_descriptor_open(
    tmp_path: Path,
    ready_db: Callable[[], str],
    monkeypatch: pytest.MonkeyPatch,
    entry: str,
) -> None:
    db_path = ready_db()
    monkeypatch.setattr("licenseid.keptdetector.get_default_db_path", lambda: db_path)
    path = tmp_path / "LICENSE"
    path.write_text("MIT\n", encoding="utf-8")
    descriptor = os.open(path, os.O_RDONLY)
    try:
        call = LicenseDetector(db_path).detect if entry == "method" else detect
        with pytest.raises(TypeError, match="not int$"):
            call(file_path=descriptor)  # type: ignore[arg-type]
        os.fstat(descriptor)  # still open: the descriptor is the caller's
        assert os.read(descriptor, 3) == b"MIT"
    finally:
        os.close(descriptor)


@pytest.mark.parametrize("form", ["str", "path"])
def test_a_str_or_a_path_is_still_a_file_path(
    tmp_path: Path, ready_db: Callable[[], str], form: str
) -> None:
    path = tmp_path / "LICENSE"
    path.write_text("SPDX-License-Identifier: MIT\n", encoding="utf-8")
    file_path: Any = str(path) if form == "str" else path
    results = LicenseDetector(ready_db()).detect(file_path=file_path)
    assert results[0]["expression"] == "MIT"


@pytest.mark.parametrize(
    "bad",
    [pytest.param(5, id="int"), *BAD_PATHS, pytest.param(BytesPath(), id="bytes-path")],
)
def test_the_detector_refuses_a_db_path_that_is_no_path(bad: object) -> None:
    """P2 (was: ``TypeError: expected str, bytes or os.PathLike object, not
    int``, or ``startswith first arg must be bytes``)."""
    with pytest.raises(TypeError, match="^db_path must be str or os.PathLike"):
        LicenseDetector(bad)  # type: ignore[arg-type]


def test_the_detector_still_takes_a_path_object(tmp_path: Path) -> None:
    path = make_ready_file_db(tmp_path / "licenses.db")
    assert LicenseDetector(path).db.db_path == path  # type: ignore[arg-type]


# --- 3. DatabaseNotReadyError.condition and .detail: None for nothing ---


def test_the_attributes_are_none_when_the_raiser_said_nothing() -> None:
    error = DatabaseNotReadyError("database: unreadable")
    assert (error.condition, error.detail) == (None, None)
    assert str(error) == "database: unreadable"


def test_a_refusal_keeps_its_condition_and_detail(tmp_path: Path) -> None:
    with pytest.raises(DatabaseNotReadyError) as raised:
        resolve("MIT", str(tmp_path / "nope.db"))
    assert raised.value.condition == "not found"
    assert raised.value.detail == str(tmp_path / "nope.db")


def test_a_packaged_list_with_no_detail_has_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ship(monkeypatch, None)
    with pytest.raises(DatabaseNotReadyError) as raised:
        resolve("MIT", source="packaged")
    error = raised.value
    assert str(error) == "spdx-bundle.json.gz: not found"
    assert (error.condition, error.detail) == ("not found", None)


def test_a_refusal_that_kept_no_condition_is_read_from_its_message(
    monkeypatch: pytest.MonkeyPatch, given: GivenWarnings
) -> None:
    """``auto`` falls back to the packaged list and says why: from the
    attributes of the refusal, or its message when it has none."""
    ship(monkeypatch, release_bundle(VERSION))
    refusal = DatabaseNotReadyError("database: unreadable: x.db: boom")
    monkeypatch.setattr(
        "licenseid.listsource.check_database_ready",
        mock.create_autospec(check_database_ready, side_effect=refusal),
    )
    assert resolve("MIT")["lists"][0]["source"] == "packaged"
    (warned,) = given.take()
    assert (warned.condition, warned.detail) == ("unreadable", "x.db: boom")


# --- 4. clear-cache: the subject of a cache file that would not go ---


@pytest.mark.parametrize(
    "name",
    [
        "licenses.json",
        "popularity.csv",
        "latest.json",
        "licenses.json.7.tmp",
        "spdx-data-v3.30.tar.gz",
        "spdx-bundle-v3.30.json.gz",
    ],
)
def test_clear_cache_names_the_cache_file_that_would_not_go(
    tmp_path: Path, name: str
) -> None:
    """P4 (was: ``ERROR: database: delete failed: .../licenses.json: ...``)."""
    db_path = make_ready_file_db(tmp_path / "licenses.db")
    (tmp_path / name).mkdir()
    result = run("--db", str(db_path), "clear-cache")
    assert (result.exit_code, result.stdout) == (1, "")
    last = result.stderr.splitlines()[-1]
    assert last.startswith(f"ERROR: {name}: delete failed: {tmp_path / name}: ")
    assert last.count("\n") == 0 and ";" not in last


def test_clear_cache_still_names_the_database_that_would_not_go(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = make_ready_file_db(tmp_path / "licenses.db")
    refuse_unlink(monkeypatch, db_path)
    result = run("--db", str(db_path), "clear-cache")
    assert (result.exit_code, result.stderr.splitlines()[-1]) == (
        1,
        f"ERROR: database: delete failed: {db_path}: Permission denied",
    )


def test_a_database_named_like_a_cache_file_is_still_the_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The subject follows the file that failed, not its name."""
    db_path = make_ready_file_db(tmp_path / "licenses.json")
    refuse_unlink(monkeypatch, db_path)
    result = run("--db", str(db_path), "clear-cache")
    assert result.stderr.splitlines()[-1].startswith("ERROR: database: delete failed:")


@posix_only
def test_a_cache_file_name_that_is_no_subject_is_called_cache(
    tmp_path: Path,
) -> None:
    db_path = make_ready_file_db(tmp_path / "licenses.db")
    (tmp_path / "spdx-data-v1\nx.tar.gz").mkdir()
    result = run("--db", str(db_path), "clear-cache")
    assert result.exit_code == 1
    last = result.stderr.splitlines()[-1]
    assert last.startswith("ERROR: cache: delete failed: ")
    assert "spdx-data-v1\\nx.tar.gz" in last
