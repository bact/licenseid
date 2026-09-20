# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Adversarial tests for the readiness gate.

Written from the contract, not the code: the gate refuses with one grammar
line and exit 2, never a traceback, and never touches the file.
``--clear-cache`` has its own file, ``test_clear_cache.py``.
"""

# pylint: disable=missing-function-docstring,redefined-outer-name

import sqlite3
from pathlib import Path

import pytest
from db_asserts import (  # noqa: F401  # pylint: disable=unused-import
    assert_no_traceback,
    assert_refused,
    safe_home,  # an autouse fixture: imported to apply it here
)
from db_asserts import (
    run_args as run,
)
from db_variants import MIT_TEXT, REFUSED, make_ready_file_db, writer

from licenseid import cli as cli_module
from licenseid.database import LicenseDatabase
from licenseid.dbcheck import check_database_ready, reject_foreign_database
from licenseid.errors import DatabaseNotReadyError

# --------------------------------------------------------------------------
# Readiness: shapes the existing variants do not build
# --------------------------------------------------------------------------


def test_index_rows_but_no_license_rows_is_refused(tmp_path: Path) -> None:
    """The index alone cannot answer: every hit is looked up in licenses."""
    db_path = tmp_path / "licenses.db"
    make_ready_file_db(db_path)
    with writer(db_path) as conn:
        conn.execute("DELETE FROM licenses")
    result = run("--db", str(db_path), "match", "--text", MIT_TEXT)
    assert_refused(result, REFUSED, str(db_path))
    assert result.stderr.startswith(f"ERROR: database: empty: {db_path};")


def test_license_rows_whose_ids_are_not_in_the_index_never_traceback(
    tmp_path: Path,
) -> None:
    """A half-built database: rows on both sides, but they do not line up.
    The gate calls it ready, so the answer must be a clean 'no'."""
    db_path = tmp_path / "licenses.db"
    make_ready_file_db(db_path)
    with writer(db_path) as conn:
        conn.execute("UPDATE license_index SET license_id = 'NOT-A-LICENSE'")
    result = run("--db", str(db_path), "match", "--text", MIT_TEXT)
    assert_no_traceback(result)
    assert result.exit_code in (0, 1), result.stderr
    assert "unreadable" not in result.stderr


@pytest.mark.parametrize("shadow", ["license_index_data", "license_index_content"])
def test_damaged_fts_shadow_table_is_refused_not_a_traceback(
    tmp_path: Path, shadow: str
) -> None:
    """The FTS5 table still exists and SELECT-ability of its shadow tables is
    what actually decides whether a query works."""
    db_path = tmp_path / "licenses.db"
    make_ready_file_db(db_path)
    with writer(db_path) as conn:
        names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master")}
        if shadow not in names:
            pytest.skip(f"{shadow} is not a shadow table in this SQLite build")
        conn.execute(f"DROP TABLE {shadow}")
    result = run("--db", str(db_path), "match", "--text", MIT_TEXT)
    assert_refused(result, REFUSED, str(db_path))


def _foreign_lookalike(db_path: Path) -> None:
    """All three table names, a version and rows -- but license_index is a
    plain table, not the FTS5 index match reads."""
    with writer(db_path) as conn:
        conn.execute(
            "CREATE TABLE licenses (license_id TEXT PRIMARY KEY, name TEXT, "
            "is_spdx BOOLEAN, is_osi_approved BOOLEAN, is_fsf_libre BOOLEAN)"
        )
        conn.execute("INSERT INTO licenses VALUES ('MIT', 'MIT License', 1, 1, 1)")
        conn.execute("CREATE TABLE db_metadata (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO db_metadata VALUES ('license_list_version', '3.30')")
        conn.execute("CREATE TABLE license_index (license_id TEXT, search_text TEXT)")
        conn.execute("INSERT INTO license_index VALUES ('MIT', 'x')")


def test_license_index_as_a_plain_table_is_refused(tmp_path: Path) -> None:
    """A grammar line and exit 2, not a traceback and not exit 1 ("no")."""
    db_path = tmp_path / "licenses.db"
    _foreign_lookalike(db_path)
    result = run("--db", str(db_path), "match", "--text", MIT_TEXT)
    assert_refused(result, REFUSED, str(db_path))


def test_a_foreign_lookalike_file_is_never_written_to(tmp_path: Path) -> None:
    db_path = tmp_path / "licenses.db"
    _foreign_lookalike(db_path)
    before = db_path.read_bytes()
    run("--db", str(db_path), "match", "--text", MIT_TEXT)
    assert db_path.read_bytes() == before, "the foreign file was written to"


def test_a_blob_license_list_version_is_refused(tmp_path: Path) -> None:
    """A BLOB survives the TEXT affinity of the column; it is not a version."""
    db_path = tmp_path / "licenses.db"
    make_ready_file_db(db_path)
    with writer(db_path) as conn:
        conn.execute(
            "UPDATE db_metadata SET value = X'332E3330'"
            " WHERE key = 'license_list_version'"
        )
    result = run("--db", str(db_path), "is-osi", "MIT")
    assert_refused(result, REFUSED, str(db_path))


def test_a_null_license_name_still_answers(tmp_path: Path) -> None:
    """The probe selects `name`; a NULL in it is a value, not a missing
    column, so the database stays ready and is-osi must answer."""
    db_path = tmp_path / "licenses.db"
    make_ready_file_db(db_path)
    with writer(db_path) as conn:
        conn.execute("UPDATE licenses SET name = NULL")
    result = run("--db", str(db_path), "is-osi", "MIT")
    assert_no_traceback(result)
    assert (result.exit_code, result.stdout) == (0, "true\n"), result.stderr


# --------------------------------------------------------------------------
# file: URIs
# --------------------------------------------------------------------------


@pytest.mark.parametrize("uri", ["file:rel.db", "file:./rel.db?mode=ro"])
def test_a_relative_file_uri_is_ready(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, uri: str
) -> None:
    work = tmp_path / "work"
    work.mkdir()
    make_ready_file_db(work / "rel.db")
    monkeypatch.chdir(work)
    result = run("--db", uri, "is-osi", "MIT")
    assert (result.exit_code, result.stdout, result.stderr) == (0, "true\n", "")


@pytest.mark.parametrize(
    "template",
    [
        "file:{path}",
        "file://{path}",
        pytest.param(
            "file://localhost{path}",
            marks=pytest.mark.xfail(
                strict=True,
                reason="BUG: the gate accepts the localhost authority SQLite "
                "documents, then LicenseDatabase's Path() collapses the '//' and "
                "the matcher reports 'unreadable'",
            ),
        ),
        "file:{path}#frag",
        "file:{path}?mode=ro#frag",
    ],
)
def test_absolute_file_uri_spellings_are_ready(tmp_path: Path, template: str) -> None:
    path = make_ready_file_db(tmp_path / "abs.db")
    result = run("--db", template.format(path=path), "is-osi", "MIT")
    assert (result.exit_code, result.stdout, result.stderr) == (0, "true\n", "")


def test_a_percent_encoded_space_in_a_file_uri_is_ready(tmp_path: Path) -> None:
    path = make_ready_file_db(tmp_path / "a licence.db")
    uri = f"file://{tmp_path}/a%20licence.db"
    result = run("--db", uri, "is-osi", "MIT")
    assert (result.exit_code, result.stdout, result.stderr) == (0, "true\n", "")
    assert path.exists()


@pytest.mark.parametrize(
    "suffix", ["?mode=rwc", "?mode=rwc&mode=rwc", "?MODE=rwc", "?mode=rwc#x"]
)
def test_a_writable_file_uri_never_creates_the_database(
    tmp_path: Path, suffix: str
) -> None:
    missing = tmp_path / "nope.db"
    uri = f"file:{missing}{suffix}"
    result = run("--db", uri, "match", "--text", MIT_TEXT)
    assert_refused(result, REFUSED, uri)
    assert not missing.exists(), "mode=rwc created the database"
    with pytest.raises(DatabaseNotReadyError):
        check_database_ready(uri)
    assert not missing.exists()


def test_a_memory_mode_uri_naming_a_real_file_never_touches_it(
    tmp_path: Path,
) -> None:
    """mode=memory wins: SQLite opens an unrelated in-memory database, so the
    real file on disk must be left exactly as it was."""
    path = make_ready_file_db(tmp_path / "real.db")
    before = (path.read_bytes(), path.stat().st_mtime_ns)
    uri = f"file:{path}?mode=memory&cache=shared"
    result = run("--db", uri, "match", "--text", MIT_TEXT)
    assert_refused(result, REFUSED, uri)
    assert (path.read_bytes(), path.stat().st_mtime_ns) == before


def test_a_programming_error_is_not_worded_unreadable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A bug in a query is not a fault in the file."""
    path = make_ready_file_db(tmp_path / "licenses.db")

    def boom(*args: object, **kwargs: object) -> None:
        raise sqlite3.ProgrammingError("Incorrect number of bindings supplied")

    monkeypatch.setattr(cli_module, "AggregatedLicenseMatcher", boom)
    result = run("--db", str(path), "match", "--text", MIT_TEXT)
    assert isinstance(result.exception, sqlite3.ProgrammingError), result.exception
    assert "unreadable" not in result.stderr


def test_an_interface_error_is_not_worded_unreadable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = make_ready_file_db(tmp_path / "licenses.db")

    def boom(*args: object, **kwargs: object) -> None:
        raise sqlite3.InterfaceError("Error binding parameter 0")

    monkeypatch.setattr(cli_module, "AggregatedLicenseMatcher", boom)
    result = run("--db", str(path), "is-osi", "MIT")
    assert isinstance(result.exception, sqlite3.InterfaceError), result.exception
    assert "unreadable" not in result.stderr


def test_the_api_clear_cache_of_a_memory_database_keeps_the_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``Path(":memory:").parent`` is the working directory."""
    (tmp_path / "licenses.json").write_text("keep me\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    LicenseDatabase.clear_cache(":memory:")
    LicenseDatabase.clear_cache("file:x?mode=memory&cache=shared")
    assert (tmp_path / "licenses.json").exists()


def test_a_blob_last_check_datetime_is_not_a_crash(tmp_path: Path) -> None:
    """The staleness check reads it after the gate; a blob is not a date."""
    db_path = make_ready_file_db(tmp_path / "licenses.db")
    with writer(db_path) as conn:
        conn.execute(
            "UPDATE db_metadata SET value = X'32303236'"
            " WHERE key = 'last_check_datetime'"
        )
    result = run("--db", str(db_path), "is-osi", "MIT")
    assert_no_traceback(result)
    assert (result.exit_code, result.stdout) == (0, "true\n"), result.stderr


def test_a_swapped_table_page_never_crashes(tmp_path: Path) -> None:
    """Swap the root page of ``licenses`` with each other page in turn (what a
    damaged disk can do). The command must end with an answer or with exit 2
    and one grammar line, never a traceback. The gate is a structural check,
    not ``PRAGMA quick_check``, so an answer may be wrong (exit 1): roadmap
    item 2 records that. Another table's root page is skipped: swapping two
    whole tables gives ``licenses`` rows from ``db_metadata``, which no cheap
    probe tells apart."""
    source = make_ready_file_db(tmp_path / "source.db")
    with sqlite3.connect(str(source)) as conn:
        roots = dict(
            conn.execute(
                "SELECT name, rootpage FROM sqlite_master WHERE type = 'table'"
            )
        )
        root = roots["licenses"]
        page_size = conn.execute("PRAGMA page_size").fetchone()[0]
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    data = source.read_bytes()
    pages = len(data) // page_size
    for other in range(2, pages + 1):
        if other in roots.values():
            continue
        swapped = bytearray(data)
        a, b = (root - 1) * page_size, (other - 1) * page_size
        swapped[a : a + page_size], swapped[b : b + page_size] = (
            data[b : b + page_size],
            data[a : a + page_size],
        )
        copy = tmp_path / f"swap-{other}.db"
        copy.write_bytes(bytes(swapped))
        result = run("--db", str(copy), "is-osi", "MIT")
        assert_no_traceback(result)
        assert result.exit_code in (0, 1, 2), (other, result.exit_code, result.stderr)
        if result.exit_code == 2:
            assert result.stderr.count("\n") == 1, (other, result.stderr)


def test_a_table_row_that_disagrees_with_its_key_index_is_refused(
    tmp_path: Path,
) -> None:
    """The table row says NULL while the key's index still says 'MIT'. Reading
    only the index (a covering scan) would call the database ready; the
    command then crashes on the NULL id."""
    path = make_ready_file_db(tmp_path / "licenses.db")
    with sqlite3.connect(str(path)) as conn:
        root = conn.execute(
            "SELECT rootpage FROM sqlite_master WHERE name = 'licenses'"
        ).fetchone()[0]
        page_size = conn.execute("PRAGMA page_size").fetchone()[0]
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    data = bytearray(path.read_bytes())
    start = (root - 1) * page_size
    body = data.index(b"MIT", start, start + page_size)
    # The record header's serial type for a 3-byte text (13 + 2 * 3) is 19.
    data[data.rindex(bytes([19]), start, body)] = 0  # NULL
    path.write_bytes(bytes(data))
    with pytest.raises(DatabaseNotReadyError):
        check_database_ready(str(path))
    result = run("--db", str(path), "is-osi", "MIT")
    assert_refused(result, REFUSED, str(path))


def test_a_plain_path_with_mode_memory_in_a_directory_name_is_a_file(
    tmp_path: Path,
) -> None:
    """SQLite reads a name as a URI only when it starts with ``file:``."""
    directory = tmp_path / "mode=memory"
    directory.mkdir()
    database = LicenseDatabase(str(directory / "x.db"))
    assert database.use_uri is False
    assert (directory / "x.db").exists()


# --------------------------------------------------------------------------
# Somebody else's file, under one of licenseid's table names
# --------------------------------------------------------------------------


def _foreign_table(path: Path, ddl: str, insert: str) -> bytes:
    with sqlite3.connect(str(path)) as conn:
        conn.execute(ddl)
        conn.execute(insert)
    return path.read_bytes()


FOREIGN_TABLES = {
    # A licence-seat inventory, an asset register, somebody's own index: each
    # uses a table name licenseid also uses, with a schema that is not ours.
    "licenses": (
        "CREATE TABLE licenses (id INTEGER PRIMARY KEY, name TEXT, seats INT)",
        "INSERT INTO licenses VALUES (1, 'Acme CAD', 50)",
    ),
    "db_metadata": (
        "CREATE TABLE db_metadata (id INTEGER PRIMARY KEY, note TEXT)",
        "INSERT INTO db_metadata VALUES (1, 'notes')",
    ),
    "license_index": (
        "CREATE TABLE license_index (a TEXT)",
        "INSERT INTO license_index VALUES ('x')",
    ),
}


@pytest.mark.parametrize("table", sorted(FOREIGN_TABLES))
def test_a_foreign_table_of_ours_is_invalid_with_no_update_hint(
    tmp_path: Path, table: str
) -> None:
    """The name is one licenseid creates, so without a schema check the file
    would be called "empty" and the user told to run update, which writes
    licenseid's schema into it."""
    db_path = tmp_path / "inventory.db"
    _foreign_table(db_path, *FOREIGN_TABLES[table])
    result = run("--db", str(db_path), "match", "--text", MIT_TEXT)
    assert_no_traceback(result)
    assert result.exit_code == 2
    assert result.stdout == ""
    assert result.stderr == f"ERROR: database: invalid: {db_path}\n"
    assert "licenseid update" not in result.stderr


@pytest.mark.parametrize("table", sorted(FOREIGN_TABLES))
def test_update_never_writes_into_a_foreign_database(
    tmp_path: Path, table: str
) -> None:
    """The refusal is what protects the file; the message alone would not."""
    db_path = tmp_path / "inventory.db"
    before = _foreign_table(db_path, *FOREIGN_TABLES[table])
    result = run("--db", str(db_path), "update")
    assert_no_traceback(result)
    assert result.exit_code == 2, result.stderr
    assert result.stderr == f"ERROR: database: invalid: {db_path}\n"
    assert db_path.read_bytes() == before, "the foreign file was written to"


def test_the_write_guard_allows_what_update_is_for(tmp_path: Path) -> None:
    """It must block only somebody else's file: a missing, empty, damaged or
    ready database is exactly what update and --clear-cache are for. Called
    directly, so no test reaches the network."""
    empty = tmp_path / "empty.db"
    empty.write_bytes(b"")
    damaged = tmp_path / "damaged.db"
    damaged.write_bytes(b"SQLite format 3\x00" + b"\xff" * 4096)
    for db_path in (
        tmp_path / "missing.db",
        empty,
        damaged,
        make_ready_file_db(tmp_path / "ready.db"),
    ):
        reject_foreign_database(str(db_path))  # raises if it refuses
