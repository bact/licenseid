# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Which list ``match()`` reads when it has both a database at the
default path and a bundle in the wheel: the newer List wins (Q4); a tie goes
to the database only when this licenseid's rules built its rows (Q10).
``tests/test_option_matrix.py`` holds the axes; this file the edges."""
# pylint: disable=missing-function-docstring

import re
from pathlib import Path
from unittest import mock

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from db_variants import make_ready_file_db, writer
from release_fakes import release_bundle, ship

from licenseid import LicenseDatabase, listsource, match
from licenseid.datadir import get_default_db_path
from licenseid.dbcheck import check_database_ready
from licenseid.errors import DatabaseNotReadyError, InvalidInputError
from licenseid.records import BUILD_VERSION

DB_VERSION = "3.30"


def _default_db(version: str = DB_VERSION, build: str | None = None) -> Path:
    """A usable database at the default path, of List *version*, its rows
    stamped *build* (None: this licenseid's)."""
    path = Path(get_default_db_path())
    path.parent.mkdir(parents=True)
    make_ready_file_db(path)
    with writer(path) as conn:
        conn.execute(
            "UPDATE db_metadata SET value = ? WHERE key = 'license_list_version'",
            (version,),
        )
        if build is not None:
            conn.execute(
                "UPDATE db_metadata SET value = ? WHERE key = 'build_version'",
                (build,),
            )
    return path


def _read(value: str = "MIT") -> tuple[str, str | None]:
    lists = match(value)["lists"]
    assert len(lists) == 1  # only the list read is reported
    return lists[0]["source"], lists[0]["version"]


@pytest.mark.parametrize(
    ("bundle", "expected"),
    [
        ("3.29", ("database", DB_VERSION)),
        ("3.29.9", ("database", DB_VERSION)),
        ("3.31", ("packaged", "3.31")),
        ("3.30.1", ("packaged", "3.30.1")),
        ("4", ("packaged", "4")),
        ("3.30", ("database", DB_VERSION)),  # a tie
        ("3.30.0", ("database", DB_VERSION)),  # a tie in other words
        ("3.30rc1", ("database", DB_VERSION)),  # no number: never older
    ],
)
def test_the_newer_list_wins(
    monkeypatch: pytest.MonkeyPatch, bundle: str, expected: tuple[str, str]
) -> None:
    ship(monkeypatch, release_bundle(bundle))
    _default_db()
    assert _read() == expected


@pytest.mark.parametrize("version", ["next", "3.30-beta"])  # "" is not ready
def test_a_database_version_that_is_no_number_is_a_tie(
    monkeypatch: pytest.MonkeyPatch, version: str
) -> None:
    ship(monkeypatch, release_bundle("3.30"))
    _default_db(version)
    assert _read()[0] == "database"


@pytest.mark.parametrize(
    ("build", "warning"),
    [
        ("1", f"build v1 outdated: current v{BUILD_VERSION}; run 'licenseid update'"),
        ("x", f"build vx outdated: current v{BUILD_VERSION}; run 'licenseid update'"),
        ("99", f"build v99 newer: current v{BUILD_VERSION}"),
    ],
)
def test_a_tie_goes_to_the_bundle_unless_the_build_is_current(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    build: str,
    warning: str,
) -> None:
    """The database still warns as it opens; the answer is the bundle's."""
    ship(monkeypatch, release_bundle(DB_VERSION))
    _default_db(build=build)
    assert _read() == ("packaged", DB_VERSION)
    assert capsys.readouterr().err == f"WARNING: database: {warning}\n"


@pytest.mark.parametrize("build", ["1", "3"])
def test_a_newer_list_wins_whatever_its_build(
    monkeypatch: pytest.MonkeyPatch, build: str
) -> None:
    ship(monkeypatch, release_bundle("3.29"))
    _default_db(build=build)
    assert _read() == ("database", DB_VERSION)


@pytest.mark.parametrize("build", [f"0{BUILD_VERSION}", BUILD_VERSION])
def test_a_current_build_is_read_as_a_number(
    monkeypatch: pytest.MonkeyPatch, build: str
) -> None:
    ship(monkeypatch, release_bundle(DB_VERSION))
    _default_db(build=build)
    assert _read() == ("database", DB_VERSION)


def test_a_directory_at_the_default_path_warns(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """There, but not a database: unusable, so said, then the bundle."""
    ship(monkeypatch, release_bundle("9.99"))
    path = Path(get_default_db_path())
    path.mkdir(parents=True)
    assert _read() == ("packaged", "9.99")
    err = capsys.readouterr().err
    assert err.startswith(f"WARNING: database: unreadable: {path}: ")
    assert err.endswith("; using packaged data v9.99\n")


def test_each_fallback_is_said_once(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A second condition is a second warning; a repeat is none."""
    ship(monkeypatch, release_bundle("9.99"))
    path = Path(get_default_db_path())
    path.parent.mkdir(parents=True)
    path.write_bytes(b"")
    _read()
    _read()
    with writer(path) as conn:
        conn.execute("CREATE TABLE notes (body TEXT)")
    _read()
    _read()
    assert capsys.readouterr().err == (
        f"WARNING: database: empty: {path}; using packaged data v9.99\n"
        f"WARNING: database: invalid: {path}; using packaged data v9.99\n"
    )


def test_an_unusable_bundle_leaves_the_database_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    ship(monkeypatch, b"not gzip")
    with pytest.raises(DatabaseNotReadyError, match="^database: not found: "):
        match("MIT")
    detail = "BadGzipFile: Not a gzipped file (b'no')"
    with pytest.raises(
        DatabaseNotReadyError,
        match=f"^{re.escape(f'spdx-bundle.json.gz: invalid: {detail}')}$",
    ) as raised:
        match("MIT", source="packaged")
    assert (raised.value.condition, raised.value.detail) == ("invalid", detail)
    assert capsys.readouterr().err == (
        f"WARNING: spdx-bundle.json.gz: invalid: {detail}\n"
    )


def test_no_bundle_says_not_found() -> None:
    with pytest.raises(DatabaseNotReadyError) as raised:
        match("MIT", source="packaged")
    assert str(raised.value) == "spdx-bundle.json.gz: not found"
    assert (raised.value.condition, raised.value.detail) == ("not found", "")


@pytest.mark.parametrize("source", ["Auto", "db", "", None, 1])
def test_an_unknown_source_is_refused(source: object) -> None:
    message = f"option: invalid: source: {source!r}; pass auto, database or packaged"
    with pytest.raises(InvalidInputError, match=f"^{re.escape(message)}$"):
        match("MIT", source=source)  # type: ignore[arg-type]


def test_source_is_a_keyword() -> None:
    with pytest.raises(TypeError):
        # pylint: disable-next=too-many-function-args
        match("MIT", None, "packaged")  # type: ignore[call-arg]


def test_a_packaged_answer_reads_no_database(monkeypatch: pytest.MonkeyPatch) -> None:
    """source="packaged" never opens the default database."""
    ship(monkeypatch, release_bundle("9.99"))
    path = Path(get_default_db_path())
    path.parent.mkdir(parents=True)
    path.write_bytes(b"")
    assert _read_source("packaged") == ("packaged", "9.99")
    assert path.read_bytes() == b""


def _read_source(source: str) -> tuple[str, str | None]:
    lists = match("MIT", source=source)  # type: ignore[arg-type]
    return lists["lists"][0]["source"], lists["lists"][0]["version"]


def test_a_database_with_no_rows_is_refused_by_source_database() -> None:
    """P8: what auto calls empty, source="database" refuses, rather than
    answering unresolved for every value as 0.6.0 did."""
    path = Path(get_default_db_path())
    path.parent.mkdir(parents=True)
    LicenseDatabase(str(path))
    message = f"database: empty: {path}; run 'licenseid update'"
    with pytest.raises(DatabaseNotReadyError, match=f"^{re.escape(message)}$"):
        match("MIT", source="database")


def test_a_database_given_is_checked_ready() -> None:
    """P3 of the contract batch: a database the caller opened is checked as
    one ``match()`` opens is (it was read unchecked, so an empty one
    answered ``unresolved`` for MIT)."""
    path = Path(get_default_db_path())
    path.parent.mkdir(parents=True)
    message = f"database: empty: {path}; run 'licenseid update'"
    with pytest.raises(DatabaseNotReadyError, match=f"^{re.escape(message)}$"):
        match("MIT", LicenseDatabase(str(path)), source="database")


@pytest.mark.parametrize("form", ["handle", "str", "path"])
def test_a_database_given_is_checked_once_while_its_file_stays(
    tmp_path: Path, form: str
) -> None:
    """P3: the readiness check costs more than a lookup, so a database given
    is checked once while its file keeps its stamp, and again when it
    changes: an emptied file is refused, not read."""
    path = make_ready_file_db(tmp_path / "given.db")
    db: LicenseDatabase | str | Path = path
    if form == "handle":
        db = LicenseDatabase(str(path), create=False)
    elif form == "str":
        db = str(path)
    checks = mock.create_autospec(
        check_database_ready, side_effect=check_database_ready
    )
    with mock.patch("licenseid.listsource.check_database_ready", checks):
        for _ in range(3):
            assert match("MIT", db)["expression"] == "MIT"
        assert checks.call_count == 1
        with writer(path) as conn:
            conn.execute("DELETE FROM licenses")
        with pytest.raises(DatabaseNotReadyError, match="^database: empty: "):
            match("MIT", db)
        assert checks.call_count == 2


def test_reset_choice_forgets_the_databases_given(tmp_path: Path) -> None:
    path = str(make_ready_file_db(tmp_path / "given.db"))
    checks = mock.create_autospec(
        check_database_ready, side_effect=check_database_ready
    )
    with mock.patch("licenseid.listsource.check_database_ready", checks):
        match("MIT", path)
        listsource.reset_choice()
        match("MIT", path)
    assert checks.call_count == 2
