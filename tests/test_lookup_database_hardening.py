# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A database that goes bad or missing: every entry point, the constructor,
the files a lookup leaves, and the paths that block or move.

Companion to ``test_lookup_database_errors.py``.
"""

# pylint: disable=missing-function-docstring,protected-access

import contextlib
import os
import sqlite3
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path, PureWindowsPath
from typing import Any
from unittest import mock

import pytest
from click.testing import CliRunner
from conftest import posix_only
from db_asserts import (  # noqa: F401  # pylint: disable=unused-import
    probe_does_not_hang,
    safe_home,
)
from db_variants import IS_ROOT, make_ready_file_db, writer

from licenseid import AggregatedLicenseMatcher, DatabaseNotReadyError
from licenseid.cli import cli
from licenseid.database import LicenseDatabase
from licenseid.dbcheck import (
    lookup_error,
    open_uri,
    pin_relative_uri,
    reject_blocking_file,
)
from licenseid.dbconnection import Connections
from licenseid.errors import LicenseIdError

TEXT = "Permission is hereby granted, free of charge, to any person obtaining a copy"


def _delete(path: Path) -> None:
    path.unlink()


def _empty(path: Path) -> None:
    path.write_bytes(b"")


def _half(path: Path) -> None:
    path.write_bytes(path.read_bytes()[: path.stat().st_size // 2])


def _one_page(path: Path) -> None:
    path.write_bytes(path.read_bytes()[:4096])


def _garbage(path: Path) -> None:
    path.write_bytes(b"not a database " * 600)


DAMAGE: list[Callable[[Path], None]] = [_delete, _empty, _half, _one_page, _garbage]

ENTRY_POINTS: dict[str, Callable[[AggregatedLicenseMatcher, Path], Any]] = {
    "match-id": lambda m, p: m.match(license_id="MIT"),
    "match-name": lambda m, p: m.match("MIT"),
    "match-text": lambda m, p: m.match(TEXT * 3),
    "match-tag": lambda m, p: m.match("SPDX-License-Identifier: MIT"),
    "match-file": lambda m, p: m.match(file_path=str(p.parent / "in.txt")),
    "is_spdx": lambda m, p: m.is_spdx(license_id="MIT"),
    "is_osi": lambda m, p: m.is_osi("MIT"),
    "resolve_record": lambda m, p: m.resolve_record(TEXT * 3),
    "diff_pair": lambda m, p: m.diff_pair(TEXT, "MIT"),
    "get_metadata": lambda m, p: m.db.get_metadata(),
    "get_all_names_and_ids": lambda m, p: m.db.get_all_names_and_ids(),
    "get_license_details": lambda m, p: m.db.get_license_details("MIT"),
}


@pytest.mark.parametrize("warm", [False, True], ids=["cold", "warm"])
@pytest.mark.parametrize("damage", DAMAGE, ids=lambda f: f.__name__)
@pytest.mark.parametrize("entry", ENTRY_POINTS)
def test_every_entry_point_raises_database_not_ready(
    tmp_path: Path, entry: str, damage: Callable[[Path], None], warm: bool
) -> None:
    path = make_ready_file_db(tmp_path / "m.db")
    (tmp_path / "in.txt").write_text(TEXT * 3, encoding="utf-8")
    matcher = AggregatedLicenseMatcher(db_path=str(path))
    if warm:
        matcher.match("MIT")
    damage(path)
    with pytest.raises(DatabaseNotReadyError):
        ENTRY_POINTS[entry](matcher, path)
    if damage is _delete:
        assert not path.exists(), f"{entry} re-created the deleted database"


@posix_only
@pytest.mark.skipif(IS_ROOT, reason="root ignores file permissions")
def test_a_database_unreadable_after_the_check_is_database_not_ready(
    tmp_path: Path,
) -> None:
    path = make_ready_file_db(tmp_path / "p.db")
    matcher = AggregatedLicenseMatcher(db_path=str(path))
    path.chmod(0)
    with pytest.raises(DatabaseNotReadyError):
        matcher.match(license_id="MIT")


@pytest.mark.parametrize(
    "args",
    [
        ["match", "--id", "MIT"],
        ["match", "--text", "MIT"],
        ["is-osi", "MIT"],
        ["is-fsf", "MIT"],
        ["is-open", "MIT"],
        ["is-free", "MIT"],
        ["is-spdx", "MIT"],
    ],
    ids=" ".join,
)
@pytest.mark.parametrize(
    "damage", [_delete, _empty, _garbage], ids=lambda f: f.__name__
)
def test_cli_exits_2_not_1_for_a_database_gone_bad(
    tmp_path: Path, args: list[str], damage: Callable[[Path], None]
) -> None:
    """Exit 1 means "no": a database that fails after the check must not
    answer it."""
    path = make_ready_file_db(tmp_path / "c.db")
    real = AggregatedLicenseMatcher._match_raw

    def broken_then_match(self: AggregatedLicenseMatcher, *a: Any, **k: Any) -> Any:
        damage(path)
        return real(self, *a, **k)

    with mock.patch.object(
        AggregatedLicenseMatcher,
        "_match_raw",
        autospec=True,
        side_effect=broken_then_match,
    ):
        result = CliRunner().invoke(cli, ["--db", str(path), *args])
    assert result.exit_code == 2, (result.stdout, result.stderr)
    assert result.stdout == ""
    assert result.stderr.startswith("ERROR: database: unreadable: "), result.stderr
    assert result.stderr.count("\n") == 1


def test_update_passes_a_refusal_without_a_cause_on_unchanged(tmp_path: Path) -> None:
    """It is no read of this database that failed, so update rewords nothing."""
    path = make_ready_file_db(tmp_path / "u.db")
    db = LicenseDatabase(str(path))
    with (
        mock.patch.object(
            LicenseDatabase,
            "_update_from_remote",
            autospec=True,
            side_effect=DatabaseNotReadyError("database: unreadable: x"),
        ),
        pytest.raises(DatabaseNotReadyError, match="database: unreadable: x"),
    ):
        db.update_from_remote()


def test_update_wrapper_does_not_reword_other_errors(tmp_path: Path) -> None:
    path = make_ready_file_db(tmp_path / "w.db")
    db = LicenseDatabase(str(path))
    with (
        mock.patch.object(
            LicenseDatabase,
            "_update_from_remote",
            autospec=True,
            side_effect=ValueError("x"),
        ),
        pytest.raises(ValueError, match="x"),
    ):
        db.update_from_remote()
    with (
        mock.patch.object(
            LicenseDatabase,
            "_update_from_remote",
            autospec=True,
            side_effect=LicenseIdError("version: invalid: v"),
        ),
        pytest.raises(LicenseIdError, match="version: invalid: v"),
    ):
        db.update_from_remote()


# ---- the constructor ------------------------------------------------------


def test_a_matcher_never_makes_a_database_of_a_file_that_went_missing(
    tmp_path: Path,
) -> None:
    """The window between the readiness check and the constructor."""
    path = make_ready_file_db(tmp_path / "r.db")
    real = LicenseDatabase.__init__

    def deleted_first(self: LicenseDatabase, *args: Any, **kwargs: Any) -> None:
        path.unlink()
        real(self, *args, **kwargs)

    with (
        mock.patch.object(LicenseDatabase, "__init__", deleted_first),
        pytest.raises(DatabaseNotReadyError),
    ):
        AggregatedLicenseMatcher(db_path=str(path))
    assert not path.exists()


def test_create_false_does_not_create_and_create_true_does(tmp_path: Path) -> None:
    path = tmp_path / "n.db"
    with pytest.raises(DatabaseNotReadyError):
        LicenseDatabase(str(path), create=False)
    assert not path.exists()
    LicenseDatabase(str(path))
    assert path.exists()


@pytest.mark.parametrize("damage", [_empty, _garbage], ids=lambda f: f.__name__)
def test_the_constructor_words_a_bad_file_without_create(
    tmp_path: Path, damage: Callable[[Path], None]
) -> None:
    path = make_ready_file_db(tmp_path / "z.db")
    damage(path)
    with pytest.raises(DatabaseNotReadyError) as info:
        LicenseDatabase(str(path), create=False)
    expected = "database: empty: " if damage is _empty else "database: unreadable: "
    assert str(info.value).startswith(expected), info.value


def test_a_current_database_is_opened_without_a_write(
    tmp_path: Path, connects: list[bool]
) -> None:
    path = make_ready_file_db(tmp_path / "s.db")
    LicenseDatabase(str(path)).get_all_names_and_ids()  # the seed needs a backfill
    connects.clear()
    LicenseDatabase(str(path), create=False)
    assert connects
    assert not any(connects), connects


def test_an_older_schema_is_migrated_in_place_without_create(tmp_path: Path) -> None:
    path = make_ready_file_db(tmp_path / "o.db")
    with writer(path) as conn:
        conn.execute("DROP INDEX idx_licenses_name")
    LicenseDatabase(str(path), create=False)
    with contextlib.closing(sqlite3.connect(path)) as conn:
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master")}
    assert "idx_licenses_name" in names


# ---- files a lookup leaves, and paths that move or block --------------------


def test_leave_wal_converts_a_database_of_an_earlier_version(tmp_path: Path) -> None:
    path = make_ready_file_db(tmp_path / "wal.db")
    with writer(path) as conn:
        conn.execute("PRAGMA journal_mode = WAL")
    LicenseDatabase(str(path))._connections.leave_wal()
    with contextlib.closing(sqlite3.connect(path)) as conn:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
    AggregatedLicenseMatcher(db_path=str(path)).match(license_id="MIT")
    assert sorted(p.name for p in tmp_path.glob("wal.db*")) == ["wal.db"]


def test_leave_wal_does_not_wait_for_a_reader(tmp_path: Path) -> None:
    path = make_ready_file_db(tmp_path / "busy.db")
    with writer(path) as conn:
        conn.execute("PRAGMA journal_mode = WAL")
    db = LicenseDatabase(str(path))
    holder = sqlite3.connect(path, isolation_level=None)
    holder.execute("BEGIN")
    holder.execute("SELECT count(*) FROM licenses").fetchone()
    try:
        db._connections.leave_wal()  # must not raise, whatever the reader holds
        with contextlib.closing(sqlite3.connect(path)) as conn:
            assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    finally:
        holder.close()


@posix_only  # a FIFO
@pytest.mark.parametrize("suffix", ["", "-journal", "-wal"])
def test_a_fifo_in_place_of_the_database_or_a_sidecar_does_not_hang(
    tmp_path: Path, suffix: str
) -> None:
    path = make_ready_file_db(tmp_path / "f.db")
    if not suffix:
        path.unlink()
    os.mkfifo(f"{path}{suffix}")
    assert "DatabaseNotReadyError" in probe_does_not_hang(path)
    with pytest.raises(DatabaseNotReadyError, match="not a regular file"):
        reject_blocking_file(str(path))


def test_reject_blocking_file_leaves_what_it_cannot_describe_to_sqlite() -> None:
    reject_blocking_file("a\0b.db")  # no raise
    reject_blocking_file(":memory:")


def test_a_relative_path_names_one_file_for_reads_and_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "one").mkdir()
    (tmp_path / "two").mkdir()
    make_ready_file_db(tmp_path / "one" / "x.db")
    monkeypatch.chdir(tmp_path / "one")
    db = LicenseDatabase("x.db")
    monkeypatch.chdir(tmp_path / "two")
    with writer(tmp_path / "one" / "x.db") as conn:
        conn.execute("UPDATE licenses SET norm_license_id = NULL")
    db.get_all_names_and_ids()  # reads, then writes the backfill
    assert not list((tmp_path / "two").iterdir())


def test_the_label_of_a_file_uri_is_its_file(tmp_path: Path) -> None:
    path = make_ready_file_db(tmp_path / "u.db")
    posix = path.as_posix()
    uri = f"file://{posix if posix.startswith('/') else '/' + posix}"
    db = LicenseDatabase(uri)
    path.unlink()
    with pytest.raises(DatabaseNotReadyError) as info:
        db.get_metadata()
    assert str(info.value).startswith(f"database: unreadable: {path}: "), info.value


def test_a_path_with_a_semicolon_keeps_one_action(tmp_path: Path) -> None:
    path = tmp_path / "a;b.db"
    with pytest.raises(DatabaseNotReadyError) as info:
        AggregatedLicenseMatcher(db_path=str(path))
    message = str(info.value)
    assert message.count(";") == 1, message
    assert "a,b.db" in message


# ---- queries that blame the file, and queries that blame their text ---------


@pytest.mark.parametrize(
    "text",
    ['" OR ( AND NEAR(', "AND OR NOT", "x" * 40 + " NEAR(a b)", "*", '""'],
    ids=str,
)
def test_a_search_text_never_fails_as_a_query(tmp_path: Path, text: str) -> None:
    db = LicenseDatabase(str(make_ready_file_db(tmp_path / "q.db")))
    assert isinstance(db.search_candidates(text, already_normalized=True), list)


@pytest.mark.parametrize(
    "damage", [_delete, _empty, _half, _garbage], ids=lambda f: f.__name__
)
def test_search_and_fingerprints_raise_for_a_database_gone_bad(
    tmp_path: Path, damage: Callable[[Path], None]
) -> None:
    path = make_ready_file_db(tmp_path / "g.db")
    db = LicenseDatabase(str(path))
    damage(path)
    with pytest.raises(DatabaseNotReadyError):
        db.search_candidates("permission is hereby granted free of charge")
    with pytest.raises(DatabaseNotReadyError):
        db.find_fingerprint_hits("a b c d e f g h")


# ---- the constructor of a matcher's database, and its paths ----------------


def test_a_foreign_file_with_a_licenses_table_is_not_written_to(tmp_path: Path) -> None:
    path = tmp_path / "foreign.db"
    with writer(path) as conn:
        conn.execute("CREATE TABLE licenses (a, b)")
    before = path.read_bytes()
    with pytest.raises(DatabaseNotReadyError, match="database: invalid: "):
        LicenseDatabase(str(path), create=False)
    assert path.read_bytes() == before, "licenseid wrote into another program's file"


def test_a_deleted_file_is_not_found_not_unreadable(tmp_path: Path) -> None:
    path = make_ready_file_db(tmp_path / "gone.db")
    path.unlink()
    with pytest.raises(DatabaseNotReadyError) as info:
        LicenseDatabase(str(path), create=False)
    assert str(info.value) == f"database: not found: {path}; run 'licenseid update'"
    assert info.value.__cause__ is not None


def test_a_user_uri_that_says_read_only_is_never_opened_for_writing(
    tmp_path: Path,
) -> None:
    path = make_ready_file_db(tmp_path / "ro.db")
    with writer(path) as conn:
        conn.execute("DROP INDEX idx_licenses_name")  # an older schema
    before = path.read_bytes()
    posix = path.as_posix()
    uri = f"file://{posix if posix.startswith('/') else '/' + posix}?mode=ro"
    with pytest.raises(DatabaseNotReadyError):
        LicenseDatabase(uri, create=False)
    assert path.read_bytes() == before
    assert open_uri("file:x.db?mode=ro", "rw").endswith("mode=ro")
    assert open_uri("file:x.db?immutable=1", "rw").endswith("mode=ro")
    assert open_uri("file:x.db", "rw").endswith("mode=rw")


@pytest.mark.parametrize("directory", ["a", "a b"])
def test_a_relative_file_uri_names_one_file_after_a_chdir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, directory: str
) -> None:
    for name in (directory, "b"):
        (tmp_path / name).mkdir()
        make_ready_file_db(tmp_path / name / "l.db")
    with writer(tmp_path / "b" / "l.db") as conn:
        conn.execute(
            "INSERT OR REPLACE INTO db_metadata VALUES ('last_update_datetime', 'B')"
        )
    monkeypatch.chdir(tmp_path / directory)
    db = LicenseDatabase("file:l.db?cache=shared", create=False)
    monkeypatch.chdir(tmp_path / "b")
    assert db.get_metadata().get("last_update_datetime") != "B", "it followed the cwd"


def test_a_path_like_object_is_a_path(tmp_path: Path) -> None:
    class Spelled(os.PathLike[str]):
        """A path that is neither a str nor a Path."""

        def __fspath__(self) -> str:
            return str(make_ready_file_db(tmp_path / "pl.db"))

    assert LicenseDatabase(Spelled(), create=False).get_metadata()


def test_the_database_path_is_absolute_so_the_cache_follows_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    make_ready_file_db(tmp_path / "x.db")
    monkeypatch.chdir(tmp_path)
    db = LicenseDatabase("x.db")
    assert db.db_path.is_absolute()
    assert db.db_path == Path(os.path.join(os.getcwd(), "x.db"))


def test_no_working_directory_is_a_database_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "licenseid.dbconnection.absolute_path",
        mock.Mock(side_effect=FileNotFoundError("gone")),
    )
    with pytest.raises(DatabaseNotReadyError, match="database: unreadable: x.db"):
        Connections("x.db", False)


def test_a_nul_in_a_path_is_refused_not_cut_short() -> None:
    with pytest.raises(ValueError, match="null"):
        open_uri("a\0b.db")
    with pytest.raises(ValueError, match="null"):
        open_uri("file:a.db?mode=ro\0x")


@pytest.mark.parametrize(
    ("windows_path", "uri"),
    [
        ("\\\\?\\C:\\x\\a b.db", "file:///C:/x/a%20b.db?mode=ro"),
        ("\\\\?\\UNC\\host\\share\\a.db", "file:////host/share/a.db?mode=ro"),
        ("C:\\x\\a.db", "file:///C:/x/a.db?mode=ro"),
    ],
)
def test_the_uri_of_a_windows_path(windows_path: str, uri: str) -> None:
    from licenseid.dbcheck import _plain_path_uri  # pylint: disable=C0415

    assert _plain_path_uri(PureWindowsPath(windows_path)) == uri


@posix_only  # a FIFO
def test_a_fifo_for_a_journal_does_not_hang(tmp_path: Path) -> None:
    path = make_ready_file_db(tmp_path / "j.db")
    os.mkfifo(f"{path}-journal")
    with pytest.raises(DatabaseNotReadyError, match="not a regular file"):
        reject_blocking_file(str(path))


@posix_only
@pytest.mark.skipif(IS_ROOT, reason="root ignores file permissions")
def test_a_file_that_is_there_but_unreadable_is_not_sent_to_update(
    tmp_path: Path,
) -> None:
    path = make_ready_file_db(tmp_path / "p.db")
    matcher = AggregatedLicenseMatcher(db_path=str(path))
    path.chmod(0)
    with pytest.raises(DatabaseNotReadyError) as info:
        matcher.match(license_id="MIT")
    assert "licenseid update" not in str(info.value), info.value


def test_nothing_in_memory_is_sent_to_update() -> None:
    error = lookup_error(":memory:", sqlite3.OperationalError("no such table: x"))
    assert "licenseid update" not in str(error), error


def test_a_semicolon_in_the_detail_is_a_comma() -> None:
    error = lookup_error("x.db", sqlite3.DatabaseError("a; b"))
    assert str(error) == "database: unreadable: x.db: a, b"


@posix_only  # a symlink
def test_a_dotdot_after_a_symlink_is_not_collapsed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``lnk/..`` is the parent of the link's target, as the OS reads it."""
    (tmp_path / "real" / "deep").mkdir(parents=True)
    make_ready_file_db(tmp_path / "real" / "ready.db")
    (tmp_path / "lnk").symlink_to(tmp_path / "real" / "deep")
    monkeypatch.chdir(tmp_path)
    assert LicenseDatabase("lnk/../ready.db", create=False).get_metadata()
    assert AggregatedLicenseMatcher(db_path="lnk/../ready.db").match("MIT")


@posix_only  # a name that is not UTF-8
def test_a_relative_file_uri_with_a_non_utf8_byte_names_that_byte(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert pin_relative_uri("file:%FF.db").endswith("/%FF.db")
    assert pin_relative_uri("file:a%20b.db?mode=ro").endswith("/a%20b.db?mode=ro")


# ---- round 3: races and limits ----------------------------------------------

_OPEN_OLDER = """
import sys, time
from licenseid.database import LicenseDatabase
while time.time() < float(sys.argv[2]):
    pass
try:
    LicenseDatabase(sys.argv[1], create=False)
    print("ok")
except Exception as exc:
    print(type(exc).__name__, exc)
"""


@pytest.mark.parametrize("column", ["norm_license_id", "norm_name"])
def test_processes_migrating_an_older_database_at_once_all_succeed(
    tmp_path: Path, column: str
) -> None:
    if sqlite3.sqlite_version_info < (3, 35):
        pytest.skip("ALTER TABLE DROP COLUMN needs SQLite 3.35")
    for trial in range(2):
        path = make_ready_file_db(tmp_path / f"m{trial}.db")
        with writer(path) as conn:
            conn.execute(f"ALTER TABLE licenses DROP COLUMN {column}")
        start = time.time() + 1.5
        with contextlib.ExitStack() as stack:
            procs = [
                stack.enter_context(
                    subprocess.Popen(
                        [sys.executable, "-c", _OPEN_OLDER, str(path), str(start)],
                        stdout=subprocess.PIPE,
                        text=True,
                    )
                )
                for _ in range(4)
            ]
            outputs = [p.communicate(timeout=60)[0].strip() for p in procs]
        assert outputs == ["ok"] * 4, outputs


def test_a_huge_input_does_not_exceed_the_sql_variable_limit(
    tmp_path: Path,
) -> None:
    path = make_ready_file_db(tmp_path / "big.db")
    db = LicenseDatabase(str(path), create=False)
    words = " ".join(f"w{i}x" for i in range(40_000))
    assert isinstance(db.find_fingerprint_hits(words), dict)


@posix_only  # chmod
@pytest.mark.skipif(IS_ROOT, reason="root ignores directory modes")
def test_an_unsearchable_parent_directory_is_unreadable_not_a_traceback(
    tmp_path: Path,
) -> None:
    sub = tmp_path / "sub"
    sub.mkdir()
    path = make_ready_file_db(sub / "x.db")
    sub.chmod(0)
    try:
        with pytest.raises(DatabaseNotReadyError):
            LicenseDatabase(str(path), create=False)
    finally:
        sub.chmod(0o700)


def test_connect_closes_the_connection_when_a_pragma_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = make_ready_file_db(tmp_path / "p.db")
    closed: list[bool] = []

    class Fake:
        """A connection whose first statement fails."""

        def execute(self, *_a: object) -> None:
            raise sqlite3.OperationalError("boom")

        def close(self) -> None:
            closed.append(True)

    monkeypatch.setattr(
        "licenseid.dbconnection.sqlite3.connect", lambda *_a, **_k: Fake()
    )
    conns = Connections(str(path), False, create=False)
    with pytest.raises(sqlite3.OperationalError):
        conns.connect()
    assert closed == [True]


_GATE_PROBE = """
import sys
from licenseid.dbcheck import check_database_ready
try:
    check_database_ready(sys.argv[1])
except Exception as exc:
    print(type(exc).__name__, exc)
"""


@posix_only  # a FIFO
@pytest.mark.parametrize("suffix", ["-journal", "-wal"])
def test_the_readiness_gate_does_not_hang_on_a_fifo_sidecar(
    tmp_path: Path, suffix: str
) -> None:
    path = make_ready_file_db(tmp_path / "g.db")
    os.mkfifo(f"{path}{suffix}")
    try:
        done = subprocess.run(
            [sys.executable, "-c", _GATE_PROBE, str(path)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            start_new_session=True,
        )
    except subprocess.TimeoutExpired:
        pytest.fail("the readiness gate hung")
    assert "not a regular file" in done.stdout, done.stdout
