# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""licenseid reads only a database of its own build (``dbschema``).

A file of older rules (a build or normalisation stamp older than this
licenseid's, missing, or no number) is not ready, ``build vN outdated``, and
one that lacks a table, index or column of this build, whatever its stamp
says, is ``empty``: every lookup refuses it as it refuses an empty file
(exit 2, ``DatabaseNotReadyError``), and writes nothing. ``update`` builds it
again from nothing, ``clear-cache`` deletes it; both still refuse another
program's file. A newer stamp warns, is read, and is never rebuilt."""
# pylint: disable=missing-function-docstring,protected-access

import contextlib
import hashlib
import shutil
import sqlite3
import threading
import warnings
from collections.abc import Callable, Iterator
from pathlib import Path
from unittest import mock

import pytest
import requests
from click.testing import CliRunner
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from db_variants import writer
from list_entries import exc_entry, lic_entry
from packaged_list import database_of, synthetic_bundle
from release_fakes import ship

import licenseid
from licenseid import dbschema, keptdetector
from licenseid.cli import cli
from licenseid.database import LicenseDatabase
from licenseid.datadir import get_default_db_path
from licenseid.dbcheck import reject_foreign_database
from licenseid.dbschema import BUILD_VERSION, NORMALIZATION_VERSION, TABLES
from licenseid.detector import LicenseDetector
from licenseid.errors import DatabaseNotReadyError, LicenseIdError

RAW = synthetic_bundle(
    (
        lic_entry(
            "MIT", "MIT License", see_also=["https://opensource.org/license/mit"]
        ),
        lic_entry("Apache-2.0", "Apache License 2.0"),
    ),
    {"MIT": "Text of the MIT licence.", "Apache-2.0": "Text of Apache-2.0."},
    (exc_entry("LLVM-exception", "LLVM Exception"),),
)
ACTION = "; run 'licenseid update'"
OUTDATED = "database: {} outdated: current v{}" + ACTION
EMPTY = "database: empty: {path}" + ACTION
# Each way a file is not of this build: the change that makes it, and the
# refusal ({path}: the file).
NOT_OF_THIS_BUILD: dict[str, tuple[str, str]] = {
    "stamp-older": (
        "UPDATE db_metadata SET value = '6' WHERE key = 'build_version'",
        OUTDATED.format("build v6", BUILD_VERSION),
    ),
    "stamp-missing": (
        "DELETE FROM db_metadata WHERE key = 'build_version'",
        OUTDATED.format("build v1", BUILD_VERSION),
    ),
    "stamp-no-number": (
        "UPDATE db_metadata SET value = 'seven' WHERE key = 'build_version'",
        OUTDATED.format("build vseven", BUILD_VERSION),
    ),
    "normalization-older": (
        "UPDATE db_metadata SET value = '1' WHERE key = 'normalization_version'",
        OUTDATED.format("normalization v1", NORMALIZATION_VERSION),
    ),
    # A file of build 7: no postings, and its stamp.
    "build-7": (
        (
            "DROP TABLE text_postings; DROP TABLE text_posting_ids;"
            " DELETE FROM db_metadata"
            " WHERE key IN ('text_postings', 'text_postings_update');"
            " UPDATE db_metadata SET value = '7' WHERE key = 'build_version'"
        ),
        OUTDATED.format("build v7", BUILD_VERSION),
    ),
    # A stamp of this build on a file without a table: the stamp lies.
    "no-text_codes": ("DROP TABLE text_codes", EMPTY),
    "no-text_postings": ("DROP TABLE text_postings", EMPTY),
    "no-text_posting_ids": ("DROP TABLE text_posting_ids", EMPTY),
    # A table of this build's name and another shape (roadmap item 66).
    "postings-view": (
        (
            "DROP TABLE text_postings;"
            " CREATE VIEW text_postings AS SELECT 1 AS h, x'00' AS ids"
        ),
        EMPTY,
    ),
    "postings-without-rowid": (
        (
            "DROP TABLE text_postings; CREATE TABLE text_postings"
            " (h INTEGER PRIMARY KEY, ids BLOB) WITHOUT ROWID"
        ),
        EMPTY,
    ),
    "text_codes-with-rowid": (
        (
            "DROP TABLE text_codes; CREATE TABLE text_codes"
            " (kind TEXT, owner_id TEXT, body TEXT, PRIMARY KEY (kind, owner_id))"
        ),
        EMPTY,
    ),
    "posting-ids-no-column": ("ALTER TABLE text_posting_ids DROP COLUMN size", EMPTY),
    "index-a-view": (
        "DROP INDEX idx_licenses_name; CREATE VIEW idx_licenses_name AS SELECT 1",
        EMPTY,
    ),
    "no-license_urls": ("DROP TABLE license_urls", EMPTY),
    "no-index": ("DROP INDEX idx_licenses_name", EMPTY),
    "no-column": ("ALTER TABLE licenses DROP COLUMN same_text", EMPTY),
}
VARIANTS = sorted(NOT_OF_THIS_BUILD)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(name="fresh", scope="module")
def _fresh(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A database of this build, built once: tests copy it."""
    return database_of(RAW, tmp_path_factory.mktemp("fresh") / "licenses.db").db_path


def _variant(fresh: Path, name: str, path: Path) -> tuple[Path, str]:
    """A copy of *fresh* at *path* changed as *name* says, and its refusal."""
    statement, refusal = NOT_OF_THIS_BUILD[name]
    if "DROP COLUMN" in statement and sqlite3.sqlite_version_info < (3, 35):
        pytest.skip("ALTER TABLE DROP COLUMN needs SQLite 3.35")
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(fresh, path)
    with writer(path) as conn:
        conn.executescript(statement)
    return path, refusal.format(path=path)


def _cli(path: Path, *args: str) -> tuple[int, str, str]:
    result = CliRunner().invoke(cli, [f"--db={path}", *args])
    return result.exit_code, result.stdout, result.stderr


def _api(call: Callable[[], object]) -> tuple[int, str, str]:
    """The API's refusal as the CLI words it: exit 2, its line."""
    try:
        call()
    except DatabaseNotReadyError as exc:
        return 2, "", f"ERROR: {exc}\n"
    return 0, "", ""


def _default_detect(path: Path) -> tuple[int, str, str]:
    """``licenseid.detect()``: the file at the default path."""
    default = Path(get_default_db_path())
    default.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, default)
    keptdetector.reset()
    try:
        code, out, err = _api(lambda: licenseid.detect(license_id="MIT"))
    finally:
        default.unlink()
    return code, out, err.replace(str(default), str(path))


ENTRY_POINTS: dict[str, Callable[[Path], tuple[int, str, str]]] = {
    "cli-detect": lambda path: _cli(path, "detect", "--id", "MIT"),
    "cli-resolve": lambda path: _cli(path, "resolve", "MIT"),
    "cli-is-osi": lambda path: _cli(path, "is-osi", "--id", "MIT"),
    "LicenseDetector": lambda path: _api(lambda: LicenseDetector(str(path))),
    "LicenseDatabase": lambda path: _api(
        lambda: LicenseDatabase(str(path), create=False)
    ),
    "detect()": _default_detect,
    "resolve(db=)": lambda path: _api(lambda: licenseid.resolve("MIT", db=path)),
}


@pytest.mark.parametrize("entry", sorted(ENTRY_POINTS))
@pytest.mark.parametrize("name", VARIANTS)
def test_every_lookup_refuses_it_and_writes_nothing(
    fresh: Path, tmp_path: Path, name: str, entry: str, connects: list[bool]
) -> None:
    path, refusal = _variant(fresh, name, tmp_path / "licenses.db")
    before = _digest(path)
    assert ENTRY_POINTS[entry](path) == (2, "", f"ERROR: {refusal}\n")
    assert _digest(path) == before
    assert not any(connects), "a lookup opened a connection to write"


@pytest.mark.parametrize("name", VARIANTS)
def test_resolve_reads_the_bundle_instead_as_for_an_empty_file(
    fresh: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """With no database given, ``resolve()`` reads the bundle after the
    refusal, as it does for ``empty``; with none shipped, it raises it."""
    path, refusal = _variant(fresh, name, Path(get_default_db_path()))
    ship(monkeypatch, RAW)
    with pytest.warns(licenseid.LicenseIdWarning) as given:
        assert licenseid.resolve("MIT")["lists"][0]["source"] == "packaged"
    head = refusal.removesuffix(ACTION)
    assert [str(w.message) for w in given] == [f"{head}; using packaged data v9.99"]
    ship(monkeypatch, None)
    with pytest.raises(DatabaseNotReadyError) as raised:
        licenseid.resolve("MIT")
    assert str(raised.value) == refusal
    assert path.exists()


def _schema_and_rows(path: Path) -> tuple[object, ...]:
    """What a build put in *path*, but the times it was built at."""
    with contextlib.closing(sqlite3.connect(path)) as conn:
        schema = sorted(conn.execute("SELECT type, name, sql FROM sqlite_master"))
        rows = [
            sorted(conn.execute(f"SELECT * FROM {table}"), key=repr)
            for table in TABLES
            if table != "db_metadata"
        ]
        stamps = sorted(
            conn.execute(
                "SELECT key, value FROM db_metadata"
                " WHERE key NOT IN"
                " ('last_check_datetime', 'last_update_datetime',"
                " 'text_postings_update')"
            )
        )
    return schema, rows, stamps


@pytest.mark.parametrize("name", VARIANTS)
def test_update_builds_it_again_as_a_fresh_build(
    fresh: Path, tmp_path: Path, name: str
) -> None:
    """The release it holds already: built again all the same."""
    path, _ = _variant(fresh, name, tmp_path / "licenses.db")
    database_of(RAW, path)  # opens it as a lookup does, after the update
    assert _schema_and_rows(path) == _schema_and_rows(fresh)


@pytest.mark.parametrize("name", VARIANTS)
def test_clear_cache_deletes_it(fresh: Path, tmp_path: Path, name: str) -> None:
    """And the download cache beside a file licenseid built, of older rules
    too; not beside one it cannot tell it built (``empty``)."""
    path, refusal = _variant(fresh, name, tmp_path / "licenses.db")
    cache = tmp_path / "licenses.json"
    cache.write_text("{}", encoding="utf-8")
    assert _cli(path, "clear-cache")[0] == 0
    assert not path.exists()
    assert cache.exists() is refusal.startswith("database: empty: ")


def test_a_failed_rebuild_leaves_the_file_as_it_was(
    fresh: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The old tables are dropped inside the rebuild's transaction."""
    path, refusal = _variant(fresh, "stamp-older", tmp_path / "licenses.db")
    real = dbschema.replace_schema

    def replace_then_fail(conn: sqlite3.Connection) -> None:
        real(conn)
        raise sqlite3.OperationalError("boom")

    monkeypatch.setattr("licenseid.database.replace_schema", replace_then_fail)
    before = _digest(path)
    with pytest.raises(LicenseIdError, match="^database: update failed: boom"):
        _update(path)
    assert _digest(path) == before
    assert _api(lambda: LicenseDetector(str(path))) == (2, "", f"ERROR: {refusal}\n")


def _update(path: Path) -> bool:
    """``update --source packaged`` of RAW, with no network, its warnings
    recorded."""
    with pytest.MonkeyPatch.context() as patch, warnings.catch_warnings():
        warnings.simplefilter("ignore", licenseid.LicenseIdWarning)
        ship(patch, RAW)
        patch.setattr(requests, "get", mock_offline)
        return LicenseDatabase(str(path)).update_from_remote(
            source="packaged", use_cache=False
        )


def mock_offline(*_: object, **__: object) -> None:
    raise requests.ConnectionError("offline: test_older_database")


def _foreign(path: Path) -> Path:
    with writer(path) as conn:
        conn.execute("CREATE TABLE notes (body TEXT)")
        conn.execute("INSERT INTO notes VALUES ('mine')")
    return path


@pytest.mark.parametrize("command", ["update", "clear-cache"])
def test_a_foreign_file_is_still_refused(tmp_path: Path, command: str) -> None:
    path = _foreign(tmp_path / "licenses.db")
    before = _digest(path)
    code, _, err = _cli(path, command)
    assert (code, err) == (2, f"ERROR: database: invalid: {path}\n")
    assert _digest(path) == before


@pytest.mark.terse_cli
def test_a_newer_stamp_warns_answers_and_is_not_rebuilt(
    fresh: Path, tmp_path: Path
) -> None:
    path = tmp_path / "licenses.db"
    shutil.copyfile(fresh, path)
    with writer(path) as conn:
        conn.execute("UPDATE db_metadata SET value = '99' WHERE key = 'build_version'")
    newer = f"WARNING: database: build v99 newer: current v{BUILD_VERSION}\n"
    assert _cli(path, "detect", "--id", "MIT") == (0, "MIT\n", newer)
    before = _digest(path)
    assert _update(path) is False
    assert _digest(path) == before


def test_threads_opening_it_at_once_all_get_the_refusal(
    fresh: Path, tmp_path: Path
) -> None:
    path, refusal = _variant(fresh, "stamp-older", tmp_path / "licenses.db")
    before = _digest(path)
    start = threading.Barrier(8)
    found: list[str] = []

    def open_it() -> None:
        start.wait()
        found.append(_api(lambda: LicenseDetector(str(path)))[2])

    threads = [threading.Thread(target=open_it) for _ in range(8)]
    with _joined(threads):
        for thread in threads:
            thread.start()
    assert found == [f"ERROR: {refusal}\n"] * 8
    assert _digest(path) == before


@contextlib.contextmanager
def _joined(threads: list[threading.Thread]) -> Iterator[None]:
    try:
        yield
    finally:
        for thread in threads:
            thread.join(timeout=60)


def test_a_failed_creation_of_the_tables_leaves_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file with none of licenseid's tables gets them in one transaction."""
    path = tmp_path / "licenses.db"
    path.write_bytes(b"")
    real = dbschema._create_objects

    def create_then_fail(conn: sqlite3.Connection) -> None:
        real(conn)
        raise sqlite3.OperationalError("disk full")

    monkeypatch.setattr(dbschema, "_create_objects", create_then_fail)
    with pytest.raises(sqlite3.OperationalError, match="disk full"):
        LicenseDatabase(str(path))
    with contextlib.closing(sqlite3.connect(path)) as conn:
        assert conn.execute("SELECT name FROM sqlite_master").fetchall() == []


@pytest.mark.parametrize("name", [None, "no-text_codes"])
def test_opening_to_write_judges_only_a_file_not_of_this_build(
    fresh: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str | None
) -> None:
    """A file of this build needs no judging and no write at opening; any
    other is judged as another program's could be, and left to ``update``."""
    path = tmp_path / "licenses.db"
    if name is None:
        shutil.copyfile(fresh, path)
    else:
        _variant(fresh, name, path)
    before = _digest(path)
    judge = mock.create_autospec(reject_foreign_database)
    monkeypatch.setattr("licenseid.database.reject_foreign_database", judge)
    LicenseDatabase(str(path))
    assert judge.call_count == (name is not None)
    assert _digest(path) == before
