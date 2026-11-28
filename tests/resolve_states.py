# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The states of the database at the default path that ``resolve()`` meets
when it is given no database, for the option matrix.

Each builder puts one state in place under the test's home directory
(``db_asserts.safe_home`` points ``Path.home`` there) and returns what the
refusal of that state says (``refusal``), or ``None`` for a database that
answers.
"""

import re
from collections.abc import Callable
from pathlib import Path

import pytest
from db_variants import (
    LICENSE_LIST_VERSION,
    create_database,
    make_ready_file_db,
    writer,
)

from licenseid.datadir import get_default_db_path
from licenseid.dbschema import BUILD_VERSION

USABLE = "usable"
MISSING = "missing"
INVALID = "invalid"
EMPTY = "empty"
NO_ROWS = "no_rows"
UNREADABLE = "unreadable"
OUTDATED = "outdated"
NEWER_BUILD = "newer_build"
NO_HOME = "no_home"
STATES = [
    USABLE,
    MISSING,
    INVALID,
    EMPTY,
    NO_ROWS,
    UNREADABLE,
    OUTDATED,
    NEWER_BUILD,
    NO_HOME,
]

#: The version of the List in every database built here.
VERSION = LICENSE_LIST_VERSION
#: What opening a database of a newer build prints, whatever resolve() then
#: reads. One of an older build is not read: it is refused, as an empty one.
NEWER_BUILD_WARNING = f"WARNING: database: build v99 newer: current v{BUILD_VERSION}\n"


def _default_path() -> Path:
    path = Path(get_default_db_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _usable(_: pytest.MonkeyPatch) -> None:
    make_ready_file_db(_default_path())


def _missing(_: pytest.MonkeyPatch) -> None:
    """Nothing at the default path."""


def _invalid(_: pytest.MonkeyPatch) -> None:
    with writer(_default_path()) as conn:
        conn.execute("CREATE TABLE notes (body TEXT)")


def _empty(_: pytest.MonkeyPatch) -> None:
    _default_path().write_bytes(b"")


def _no_rows(_: pytest.MonkeyPatch) -> None:
    """licenseid's tables, and nothing in them."""
    create_database(_default_path())


def _unreadable(_: pytest.MonkeyPatch) -> None:
    """A directory where the database should be: there, but no database."""
    _default_path().mkdir()


def _stamped(build_version: str) -> Callable[[pytest.MonkeyPatch], None]:
    def stamp(_: pytest.MonkeyPatch) -> None:
        path = make_ready_file_db(_default_path())
        with writer(path) as conn:
            conn.execute(
                "UPDATE db_metadata SET value = ? WHERE key = 'build_version'",
                (build_version,),
            )

    return stamp


def _no_home(monkeypatch: pytest.MonkeyPatch) -> None:
    # An empty USERPROFILE or HOME makes Path.home() relative: no home.
    monkeypatch.setattr(Path, "home", staticmethod(Path))


#: Each state's builder.
BUILDERS: dict[str, Callable[[pytest.MonkeyPatch], None]] = {
    USABLE: _usable,
    MISSING: _missing,
    INVALID: _invalid,
    EMPTY: _empty,
    NO_ROWS: _no_rows,
    UNREADABLE: _unreadable,
    OUTDATED: _stamped("1"),
    NEWER_BUILD: _stamped("99"),
    NO_HOME: _no_home,
}


def refusal(state: str) -> tuple[str, str] | None:
    """What reading the database in *state* raises, once built, as a regular
    expression of its head (``database: <condition>: <detail>``) and its
    ACTION (``; ...``, or ``""``); None for a database that answers. The
    head of ``unreadable`` ends in SQLite's own words, which vary."""
    if state == NO_HOME:
        return re.escape("database: not found: no home directory"), "; pass --db"
    path = get_default_db_path()
    action = "; run 'licenseid update'"
    found = {
        MISSING: (f"database: not found: {path}", action),
        INVALID: (f"database: invalid: {path}", ""),
        EMPTY: (f"database: empty: {path}", action),
        NO_ROWS: (f"database: empty: {path}", action),
        OUTDATED: (f"database: build v1 outdated: current v{BUILD_VERSION}", action),
    }.get(state)
    if state == UNREADABLE:
        return re.escape(f"database: unreadable: {path}: ") + "[^;]+", ""
    return None if found is None else (re.escape(found[0]), found[1])


def build(state: str, monkeypatch: pytest.MonkeyPatch) -> tuple[str, str] | None:
    """Put *state* in place; return what reading it raises (see refusal)."""
    BUILDERS[state](monkeypatch)
    return refusal(state)
