# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Adversarial tests for the readiness gate and ``--clear-cache``.

Written from the contract, not the code: --clear-cache works from the path
alone and never opens the database; the readiness gate refuses with one
grammar line and exit 2, never a traceback, never touching the file.
"""

# pylint: disable=missing-function-docstring,redefined-outer-name

import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner, Result
from db_asserts import assert_no_traceback, assert_refused
from db_variants import MIT_TEXT, REFUSED, make_ready_file_db, writer

from licenseid import cli as cli_module
from licenseid.cli import cli
from licenseid.database import LicenseDatabase
from licenseid.dbcheck import check_database_ready
from licenseid.errors import DatabaseNotReadyError

CACHE_NAMES = (
    "licenses.json",
    "popularity.csv",
    "spdx-data-v3.30.tar.gz",
    "licenses.json.1234.tmp",
    "popularity.csv.99.tmp",
    "spdx-data-v3.30.tar.gz.7.tmp",
)


@pytest.fixture(autouse=True)
def safe_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Never let anything resolve the developer's real cache."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))


def run(*args: str, stdin: str = "") -> Result:
    return CliRunner().invoke(cli, list(args), input=stdin)


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
    (work / "sub" / "licenses.db").write_bytes(b"not a database at all\n" * 8)
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
    assert last.startswith(f"ERROR: database: unreadable: {db_path}: ")
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
                "documents, then database.py:85 Path() collapses the '//' and "
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
