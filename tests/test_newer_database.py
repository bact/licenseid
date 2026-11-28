# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A database a newer licenseid built in a shape this one cannot read.

Its stamp (build or normalisation) is newer and a table, index or column of
this build is missing, or it has no text: every lookup refuses it as
``build vN newer`` (exit 2, no action), ``update`` never builds it again
(left as it is at its release, refused at another) but with ``--force``,
and ``clear-cache`` deletes it as licenseid's own. Not ``empty``: two
versions sharing one data directory would build each other's file in turn.
A stamp read from the file is shown on one line (``errors.one_line``)."""
# pylint: disable=missing-function-docstring

import hashlib
import shutil
import sqlite3
from collections.abc import Callable
from pathlib import Path

import pytest
import requests
from db_asserts import (  # noqa: F401  # pylint: disable=unused-import
    run_cli,
    safe_home,  # an autouse fixture: imported to apply it here
)
from db_variants import writer
from list_entries import lic_entry
from packaged_list import database_of, synthetic_bundle
from release_fakes import ship

import licenseid
from licenseid.database import LicenseDatabase
from licenseid.datadir import get_default_db_path
from licenseid.dbschema import BUILD_VERSION, NORMALIZATION_VERSION
from licenseid.detector import LicenseDetector
from licenseid.errors import DatabaseNotReadyError

RAW = synthetic_bundle(
    (lic_entry("MIT", "MIT License"), lic_entry("Apache-2.0", "Apache License 2.0")),
    {"MIT": "Text of the MIT licence.", "Apache-2.0": "Text of Apache-2.0."},
)
ACTION = "; run 'licenseid update'"
# A newer stamp, and the refusal it gives.
STAMPS = {
    "build": (
        "build_version",
        "11",
        f"database: build v11 newer: current v{BUILD_VERSION}",
    ),
    "normalization": (
        "normalization_version",
        "3",
        f"database: normalization v3 newer: current v{NORMALIZATION_VERSION}",
    ),
}
# What a later shape could look like: a file this build cannot read.
SHAPES = {
    "table-renamed": "ALTER TABLE text_code_checks RENAME TO text_code_checks_v11",
    "no-index": "DROP INDEX idx_licenses_name",
    "no-column": "ALTER TABLE licenses DROP COLUMN same_text",
    "no-text": "DELETE FROM license_texts",
}
# A file this build can read, and what ``update`` would judge in it but for
# a newer stamp (``dbverdict.rebuild_refusal``).
READABLE = {
    "readable": "",
    "retired-table": "CREATE VIRTUAL TABLE license_index USING fts5(search_text)",
    "norm-not-text": "UPDATE licenses SET norm_name = NULL WHERE license_id = 'MIT'",
}
ALL_SHAPES = {**SHAPES, **READABLE}
# Each newer stamp on each shape a lookup refuses; with those it reads, for
# update.
CASES = {f"{stamp}/{shape}": (stamp, shape) for stamp in STAMPS for shape in SHAPES}
UPDATE_CASES = {
    f"{stamp}/{shape}": (stamp, shape) for stamp in STAMPS for shape in ALL_SHAPES
}


def _digest(path: Path) -> tuple[str, list[str]]:
    """The file's bytes, and the folder's listing (no journal left)."""
    folder = sorted(p.name for p in path.parent.iterdir())
    return hashlib.sha256(path.read_bytes()).hexdigest(), folder


@pytest.fixture(name="fresh", scope="module")
def _fresh(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return database_of(RAW, tmp_path_factory.mktemp("fresh") / "licenses.db").db_path


def _copy(fresh: Path, path: Path, *statements: str) -> Path:
    old_sqlite = sqlite3.sqlite_version_info < (3, 35)
    if old_sqlite and any("DROP COLUMN" in s for s in statements):
        pytest.skip("ALTER TABLE DROP COLUMN needs SQLite 3.35")
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(fresh, path)
    with writer(path) as conn:
        for statement in statements:
            conn.executescript(statement)
    return path


def _stamped(key: str, value: str) -> str:
    return f"UPDATE db_metadata SET value = '{value}' WHERE key = '{key}'"


def _newer(fresh: Path, path: Path, case: str) -> tuple[Path, str]:
    stamp, shape = UPDATE_CASES[case]
    key, value, refusal = STAMPS[stamp]
    return _copy(fresh, path, _stamped(key, value), ALL_SHAPES[shape]), refusal


def _cli(path: Path, *args: str) -> tuple[int, str, str]:
    result = run_cli(str(path), list(args))
    return result.exit_code, result.stdout, result.stderr


def _api(call: Callable[[], object]) -> tuple[int, str, str]:
    """The API's refusal, as the CLI prints it."""
    with pytest.raises(DatabaseNotReadyError) as raised:
        call()
    return 2, "", f"ERROR: {raised.value}\n"


LOOKUPS = {
    "cli-detect": lambda path: _cli(path, "detect", "--text", "Text of the MIT."),
    "cli-resolve": lambda path: _cli(path, "resolve", "MIT"),
    "cli-is-osi": lambda path: _cli(path, "is-osi", "--id", "MIT"),
    "LicenseDatabase": lambda path: _api(
        lambda: LicenseDatabase(str(path), create=False)
    ),
    "LicenseDetector": lambda path: _api(lambda: LicenseDetector(str(path))),
    "resolve(db=)": lambda path: _api(lambda: licenseid.resolve("MIT", db=path)),
}


@pytest.mark.parametrize("entry", sorted(LOOKUPS))
@pytest.mark.parametrize("case", sorted(CASES))
def test_every_lookup_refuses_it_with_no_action(
    fresh: Path,
    tmp_path: Path,
    case: str,
    entry: str,
    connects: list[bool],
) -> None:
    path, refusal = _newer(fresh, tmp_path / "licenses.db", case)
    before = _digest(path)
    assert LOOKUPS[entry](path) == (2, "", f"ERROR: {refusal}\n")
    assert _digest(path) == before
    assert not any(connects), "a lookup opened a connection to write"


@pytest.mark.parametrize("stamp", sorted(STAMPS))
def test_resolve_reads_the_bundle_instead(
    fresh: Path, monkeypatch: pytest.MonkeyPatch, stamp: str
) -> None:
    """As for an older file: one warning, and the shipped list."""
    path, refusal = _newer(fresh, Path(get_default_db_path()), f"{stamp}/table-renamed")
    ship(monkeypatch, RAW)
    with pytest.warns(licenseid.LicenseIdWarning) as given:
        assert licenseid.resolve("MIT")["lists"][0]["source"] == "packaged"
    assert [str(w.message) for w in given] == [f"{refusal}; using packaged data v9.99"]
    assert path.exists()


def _update(
    monkeypatch: pytest.MonkeyPatch, path: Path, *args: str
) -> tuple[int, str, str]:
    """``update --source packaged --no-cache`` of RAW, with no network."""
    ship(monkeypatch, RAW)
    monkeypatch.setattr(requests, "get", _offline)
    return _cli(path, "update", "--source", "packaged", "--no-cache", *args)


def _offline(*_: object, **__: object) -> None:
    raise requests.ConnectionError("offline: test_newer_database")


@pytest.mark.parametrize("case", sorted(UPDATE_CASES))
def test_update_leaves_it_at_its_release(
    fresh: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
) -> None:
    """``unchanged``, nothing written, whether this build can read it or not."""
    path, _ = _newer(fresh, tmp_path / "licenses.db", case)
    before = _digest(path)
    code, out, err = _update(monkeypatch, path)
    assert (code, out) == (
        0,
        f"LIST=spdx-license-list\tVERSION=9.99\tSTATUS=unchanged\tPATH={path}\n",
    )
    assert "ERROR" not in err
    assert _digest(path) == before


@pytest.mark.parametrize("case", sorted(UPDATE_CASES))
def test_update_refuses_it_at_another_release(
    fresh: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
) -> None:
    """Where it would build again, readable or not: the refusal, exit 1, no
    download."""
    path, refusal = _newer(fresh, tmp_path / "licenses.db", case)
    with writer(path) as conn:
        conn.execute(_stamped("license_list_version", "3.0"))
    before = _digest(path)
    code, out, err = _update(monkeypatch, path)
    assert (code, out) == (1, "")
    assert err.endswith(f"\nERROR: {refusal}\n")
    assert "Updating license database" not in err
    assert _digest(path) == before


@pytest.mark.parametrize("case", sorted(UPDATE_CASES))
def test_update_force_builds_it_as_this_build(
    fresh: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
) -> None:
    path, _ = _newer(fresh, tmp_path / "licenses.db", case)
    code, out, _ = _update(monkeypatch, path, "--force")
    assert (code, "STATUS=updated" in out) == (0, True)
    metadata = LicenseDatabase(str(path), create=False).get_metadata()
    assert metadata["build_version"] == BUILD_VERSION
    assert metadata["normalization_version"] == NORMALIZATION_VERSION


@pytest.mark.parametrize("case", sorted(CASES))
def test_clear_cache_deletes_it_and_the_cache_beside_it(
    fresh: Path, tmp_path: Path, case: str
) -> None:
    path, _ = _newer(fresh, tmp_path / "db" / "licenses.db", case)
    cache = path.parent / "licenses.json"
    cache.write_text("{}", encoding="utf-8")
    code, out, _ = _cli(path, "clear-cache")
    assert (code, out) == (0, f"STATUS=cleared\tPATH={path}\n")
    assert sorted(path.parent.iterdir()) == []


@pytest.mark.terse_cli
@pytest.mark.parametrize("stamp", sorted(STAMPS))
def test_a_newer_file_it_can_read_still_answers(
    fresh: Path, tmp_path: Path, stamp: str
) -> None:
    key, value, refusal = STAMPS[stamp]
    path = _copy(fresh, tmp_path / "licenses.db", _stamped(key, value))
    warned = f"WARNING: {refusal}\n"
    assert _cli(path, "detect", "--id", "MIT") == (0, "MIT\n", warned)


@pytest.mark.parametrize("shape", sorted(READABLE))
def test_an_equal_stamp_is_judged_by_update_as_before(
    fresh: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, shape: str
) -> None:
    """At the release it holds: a retired table or a norm row that is not
    text is built again, a file of this build is left."""
    path = _copy(fresh, tmp_path / "licenses.db", READABLE[shape])
    code, out, _ = _update(monkeypatch, path)
    status = "STATUS=unchanged" if shape == "readable" else "STATUS=updated"
    assert (code, status in out) == (0, True)


# A stamp not newer than this build's on a file this build cannot read.
CONTROLS = {
    "older": ("9", f"database: build v9 outdated: current v{BUILD_VERSION}{ACTION}"),
    "equal": (BUILD_VERSION, "database: empty: {path}" + ACTION),
    "no-number": (
        "eleven",
        f"database: build veleven outdated: current v{BUILD_VERSION}{ACTION}",
    ),
}


@pytest.mark.parametrize("shape", sorted(SHAPES))
@pytest.mark.parametrize("control", sorted(CONTROLS))
def test_a_stamp_not_newer_is_refused_and_built_again_as_before(
    fresh: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    control: str,
    shape: str,
) -> None:
    value, refusal = CONTROLS[control]
    path = _copy(
        fresh, tmp_path / "licenses.db", _stamped("build_version", value), SHAPES[shape]
    )
    refusal = refusal.format(path=path)
    assert _cli(path, "is-osi", "--id", "MIT") == (2, "", f"ERROR: {refusal}\n")
    code, out, _ = _update(monkeypatch, path)
    assert (code, "STATUS=updated" in out) == (0, True)


@pytest.mark.parametrize("command", ["is-osi", "update", "clear-cache"])
def test_a_foreign_file_with_a_newer_stamp_is_still_invalid(
    tmp_path: Path, command: str
) -> None:
    path = tmp_path / "licenses.db"
    with writer(path) as conn:
        conn.executescript(
            "CREATE TABLE licenses (id TEXT); CREATE TABLE notes (body TEXT);"
            " CREATE TABLE db_metadata (key TEXT, value TEXT);"
            " INSERT INTO db_metadata VALUES ('build_version', '11')"
        )
    before = _digest(path)
    args = ["--id", "MIT"] if command == "is-osi" else []
    assert _cli(path, command, *args) == (
        2,
        "",
        f"ERROR: database: invalid: {path}\n",
    )
    assert _digest(path) == before


# A stamp no licenseid wrote, and how it is shown: on one line, cut at 60.
ODD_STAMPS = {
    "line-feed": ("1\nERROR: x", "1 ERROR: x"),
    "tab": ("1\t2", "1 2"),
    "semicolon": ("1; run x", "1, run x"),
    "long": ("1" * 3000, "1" * 60 + "..."),
}


@pytest.mark.parametrize("name", sorted(ODD_STAMPS))
def test_an_odd_stamp_is_shown_on_one_line(
    fresh: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    stored, shown = ODD_STAMPS[name]
    path = _copy(fresh, Path(get_default_db_path()))
    with writer(path) as conn:
        conn.execute(
            "UPDATE db_metadata SET value = ? WHERE key = 'build_version'", (stored,)
        )
    head = f"database: build v{shown} outdated: current v{BUILD_VERSION}"
    assert _cli(path, "is-osi", "--id", "MIT") == (2, "", f"ERROR: {head}{ACTION}\n")
    ship(monkeypatch, RAW)
    with pytest.warns(licenseid.LicenseIdWarning) as given:
        licenseid.resolve("MIT")
    assert [str(w.message) for w in given] == [f"{head}; using packaged data v9.99"]
