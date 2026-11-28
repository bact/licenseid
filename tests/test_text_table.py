# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The texts in a plain table (database build 10), and the FTS5 table of
0.9.x known only so far as it must be.

A file of 0.9.x, or of builds 8 and 9, holds its texts in the FTS5 table
``license_index``: licenseid sees that it built the file (``outdated``, not
``invalid``), never reads that table, and ``update`` drops it with its
shadow tables, damaged or not, or refuses with one line. The readiness
verdict is made once per detector, and a row without its norm columns is
found where the names are read."""

# pylint: disable=missing-function-docstring,protected-access

import contextlib
import shutil
import sqlite3
import warnings
from collections.abc import Callable, Iterator
from pathlib import Path
from unittest import mock

import pytest
from click.testing import CliRunner
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from db_variants import writer
from list_entries import lic_entry
from older_shapes import BUILD_7, SHADOWS, TO_FTS, rename_shadow
from packaged_list import database_of, synthetic_bundle
from release_fakes import ship

import licenseid
from licenseid import database, dbcheck, dbschema, dbverdict
from licenseid.cli import cli
from licenseid.database import LicenseDatabase
from licenseid.detector import LicenseDetector
from licenseid.errors import DatabaseNotReadyError, LicenseIdError

RAW = synthetic_bundle(
    (lic_entry("MIT", "MIT License"), lic_entry("ISC", "ISC License")),
    {"MIT": "Text of the MIT licence here.", "ISC": "Text of the ISC licence."},
)
OUTDATED_7 = "ERROR: database: build v7 outdated: current v10; run 'licenseid update'\n"


@pytest.fixture(name="fresh", scope="module")
def _fresh(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A database of this build, built once: tests copy it."""
    return database_of(RAW, tmp_path_factory.mktemp("fresh") / "licenses.db").db_path


def _copy(fresh: Path, path: Path, script: str = "") -> Path:
    shutil.copyfile(fresh, path)
    if script:
        with writer(path) as conn:
            conn.executescript(script)
    return path


def _names(path: Path) -> set[str]:
    with contextlib.closing(sqlite3.connect(path)) as conn:
        return {name for (name,) in conn.execute("SELECT name FROM sqlite_master")}


def _state(path: Path) -> tuple[bytes, int, list[str]]:
    """The bytes and time of *path*, and the files beside it."""
    return (
        path.read_bytes(),
        path.stat().st_mtime_ns,
        sorted(p.name for p in path.parent.iterdir()),
    )


def _cli(*args: str) -> tuple[int, str, str]:
    result = CliRunner().invoke(cli, list(args))
    return result.exit_code, result.stdout, result.stderr


def _update(path: Path) -> None:
    """``update --source packaged`` of RAW, on the file as it is."""
    database_of(RAW, path)


def test_the_texts_table_is_plain_and_keyed_by_its_row(fresh: Path) -> None:
    with contextlib.closing(sqlite3.connect(fresh)) as conn:
        (sql,) = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'license_texts'"
        ).fetchone()
        rows = conn.execute(
            "SELECT rowid, text_id, license_id FROM license_texts"
        ).fetchall()
    assert sql.split("(")[0].split() == ["CREATE", "TABLE", "license_texts"]
    assert rows == [(1, 1, "MIT"), (2, 2, "ISC")]
    assert not {"license_index", "license_index_data"} & _names(fresh)


# --------------------------------------------------------------------------
# A file of 0.9.4: refused, never written, rebuilt, deleted (the versions gate)
# --------------------------------------------------------------------------

LOOKUPS: dict[str, Callable[[Path], tuple[int, str, str]]] = {
    "detect": lambda path: _cli(f"--db={path}", "detect", "--text", "MIT License"),
    "detect --id": lambda path: _cli(f"--db={path}", "detect", "--id", "MIT"),
    "resolve": lambda path: _cli(f"--db={path}", "resolve", "MIT"),
    "is-osi": lambda path: _cli(f"--db={path}", "is-osi", "MIT"),
    "is-fsf": lambda path: _cli(f"--db={path}", "is-fsf", "MIT"),
    "is-spdx": lambda path: _cli(f"--db={path}", "is-spdx", "MIT"),
}


@pytest.mark.parametrize("lookup", sorted(LOOKUPS))
def test_a_file_of_0_9_4_is_refused_and_left_as_it_was(
    fresh: Path, tmp_path: Path, lookup: str
) -> None:
    path = _copy(fresh, tmp_path / "licenses.db", BUILD_7)
    before = _state(path)
    assert LOOKUPS[lookup](path) == (2, "", OUTDATED_7)
    assert _state(path) == before  # no write, no -journal or -wal left


@pytest.mark.terse_cli
def test_update_makes_a_file_of_0_9_4_a_fresh_build(
    fresh: Path, tmp_path: Path
) -> None:
    path = _copy(fresh, tmp_path / "licenses.db", BUILD_7)
    _update(path)
    assert _names(path) == _names(fresh)
    assert _cli(f"--db={path}", "detect", "--id", "MIT")[:2] == (0, "MIT\n")


def test_clear_cache_deletes_a_file_of_0_9_4(fresh: Path, tmp_path: Path) -> None:
    path = _copy(fresh, tmp_path / "licenses.db", BUILD_7)
    assert _cli(f"--db={path}", "clear-cache")[0] == 0
    assert not path.exists()


# --------------------------------------------------------------------------
# The FTS5 table: damaged, left beside this build, a shadow table alone
# --------------------------------------------------------------------------


@pytest.mark.parametrize("shadow", SHADOWS)
def test_a_damaged_fts_table_of_an_older_file_is_never_read(
    fresh: Path, tmp_path: Path, shadow: str
) -> None:
    """Was ``test_damaged_fts_shadow_table_is_refused_not_a_traceback``:
    a lookup refuses the file by its stamp before any read of the table."""
    path = _copy(fresh, tmp_path / "licenses.db", BUILD_7)
    rename_shadow(path, shadow)
    before = _state(path)
    assert LOOKUPS["detect"](path) == (2, "", OUTDATED_7)
    assert _state(path) == before


def _sqlite_drops(path: Path, probe: Path) -> bool:
    """Whether this SQLite drops the FTS5 table of a copy of the file."""
    shutil.copy(path, probe)
    with contextlib.closing(sqlite3.connect(probe)) as conn:
        try:
            conn.execute("DROP TABLE license_index")
        except sqlite3.DatabaseError:
            return False
    return True


@pytest.mark.parametrize("shadow", SHADOWS)
def test_update_rebuilds_a_damaged_fts_table_or_says_why_not(
    fresh: Path, tmp_path: Path, shadow: str
) -> None:
    """``update`` rebuilds the file wherever SQLite can drop the FTS5 table.
    None drops one without its ``config``, and SQLite 3.46.0 none without its
    ``data`` (3.50.4 does): ``update`` then says so in one line and leaves
    the file as it was (``clear-cache`` deletes it)."""
    path = _copy(fresh, tmp_path / "licenses.db", BUILD_7)
    rename_shadow(path, shadow)
    drops = _sqlite_drops(path, tmp_path / "probe.db")
    assert drops == (shadow != "config") or shadow == "data"
    if drops:
        _update(path)
        assert _names(path) == _names(fresh)  # the renamed one gone too
        return
    before = path.read_bytes()
    with pytest.raises(
        LicenseIdError,
        match="^database: update failed: vtable constructor failed: license_index$",
    ):
        _update_quietly(path)
    assert path.read_bytes() == before
    assert _cli(f"--db={path}", "clear-cache")[0] == 0
    assert not path.exists()


def _update_quietly(path: Path) -> None:
    """``update --source packaged`` of RAW, its warnings ignored."""
    with pytest.MonkeyPatch.context() as patch, warnings.catch_warnings():
        warnings.simplefilter("ignore", licenseid.LicenseIdWarning)
        ship(patch, RAW)
        LicenseDatabase(str(path)).update_from_remote(
            source="packaged", use_cache=False
        )


@pytest.mark.terse_cli
def test_an_fts_table_left_beside_this_build_is_ignored_then_dropped(
    fresh: Path, tmp_path: Path
) -> None:
    """Not another program's (licenseid made it), not read: a lookup answers;
    ``update`` drops it with its shadow tables."""
    path = _copy(
        fresh,
        tmp_path / "licenses.db",
        "CREATE VIRTUAL TABLE license_index USING fts5(license_id, search_text);"
        " INSERT INTO license_index VALUES ('MIT', 'x');"
        ' CREATE TABLE license_index_left (x); CREATE TABLE "license_index_a""b" (x)',
    )
    assert _cli(f"--db={path}", "detect", "--id", "MIT")[:2] == (0, "MIT\n")
    _update(path)
    assert _names(path) == _names(fresh)


def test_the_fts_table_alone_is_licenseids_own(tmp_path: Path) -> None:
    """A file with only the FTS5 table (a 0.9.x file half dropped) is
    ``empty``, which ``update`` may complete, not ``invalid``."""
    path = tmp_path / "licenses.db"
    with writer(path) as conn:
        conn.executescript(TO_FTS.split(" INSERT", maxsplit=1)[0])
    assert _cli(f"--db={path}", "is-osi", "MIT")[2].startswith(
        f"ERROR: database: empty: {path};"
    )
    dbcheck.reject_foreign_database(str(path))  # raises if it refuses


# --------------------------------------------------------------------------
# One verdict per detector; no scan of the norm columns at opening
# --------------------------------------------------------------------------


@contextlib.contextmanager
def _verdicts() -> Iterator[mock.Mock]:
    """Every call of ``dbverdict.connection_refusal``, from either module."""
    spy = mock.Mock(wraps=dbverdict.connection_refusal)
    with (
        mock.patch.object(dbcheck, "connection_refusal", spy),
        mock.patch.object(database, "connection_refusal", spy),
    ):
        yield spy


OPENERS: dict[str, Callable[[Path], object]] = {
    "LicenseDetector": lambda path: LicenseDetector(str(path)),
    "cli detect": lambda path: _cli(f"--db={path}", "detect", "--id", "MIT"),
    "cli is-osi": lambda path: _cli(f"--db={path}", "is-osi", "--id", "MIT"),
    "resolve(db=path)": lambda path: licenseid.resolve("MIT", db=path),
}


@pytest.mark.parametrize("opener", sorted(OPENERS))
def test_the_readiness_verdict_is_made_once(
    fresh: Path, tmp_path: Path, opener: str
) -> None:
    path = _copy(fresh, tmp_path / "licenses.db")
    with _verdicts() as spy:
        OPENERS[opener](path)
    assert spy.call_count == 1


def test_a_handle_opened_alone_judges_its_file(fresh: Path, tmp_path: Path) -> None:
    path = _copy(fresh, tmp_path / "licenses.db")
    with _verdicts() as spy:
        LicenseDatabase(str(path), create=False)
    assert spy.call_count == 1


def test_a_detector_opens_one_connection_to_judge_and_read_its_stamps(
    fresh: Path, tmp_path: Path, opened: list[sqlite3.Connection]
) -> None:
    path = _copy(fresh, tmp_path / "licenses.db")
    LicenseDetector(str(path))
    assert len(opened) == 1


def test_a_judged_handle_still_finds_a_file_gone_since(tmp_path: Path) -> None:
    path = tmp_path / "gone.db"
    with pytest.raises(DatabaseNotReadyError) as raised:
        database.judged_database(str(path))
    assert str(raised.value) == f"database: not found: {path}; run 'licenseid update'"


def test_a_judged_handle_warns_a_newer_build(fresh: Path, tmp_path: Path) -> None:
    path = _copy(
        fresh,
        tmp_path / "licenses.db",
        "UPDATE db_metadata SET value = '99' WHERE key = 'build_version'",
    )
    with pytest.warns(licenseid.LicenseIdWarning, match="^database: build v99 newer"):
        database.judged_database(str(path))


def test_opening_scans_no_norm_column(fresh: Path, tmp_path: Path) -> None:
    """``update`` alone judges every row (``dbverdict.rebuild_refusal``); a
    lookup finds a bad one where it reads the names."""
    path = _copy(fresh, tmp_path / "licenses.db")
    with mock.patch.object(
        database, "rebuild_refusal", wraps=dbverdict.rebuild_refusal
    ) as spy:
        LicenseDetector(str(path)).detect(text="MIT License")
        assert spy.call_count == 0
        with pytest.MonkeyPatch.context() as patch:
            ship(patch, RAW)
            handle = LicenseDatabase(str(path))
            assert not handle.update_from_remote(source="packaged", use_cache=False)
        assert spy.call_count == 1


def test_a_shadow_name_is_quoted_when_it_is_dropped() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute('CREATE TABLE "license_index_x""; DROP TABLE t; --" (a)')
    conn.execute("CREATE TABLE t (a)")
    dbschema.replace_schema(conn)
    names = {name for (name,) in conn.execute("SELECT name FROM sqlite_master")}
    assert "t" in names and not any(n.startswith("license_index") for n in names)
