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

from collections.abc import Callable
from pathlib import Path

import pytest
from db_variants import LICENSE_LIST_VERSION, make_ready_file_db, writer

from licenseid.datadir import get_default_db_path

USABLE = "usable"
MISSING = "missing"
INVALID = "invalid"
EMPTY = "empty"
OUTDATED = "outdated"
NO_HOME = "no_home"
STATES = [USABLE, MISSING, INVALID, EMPTY, OUTDATED, NO_HOME]

#: The version of the List in every database built here.
VERSION = LICENSE_LIST_VERSION
#: What opening an outdated database prints, whatever resolve() then reads.
OUTDATED_WARNING = (
    "WARNING: database: build v1 outdated: current v2; run 'licenseid update'\n"
)


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


def _outdated(_: pytest.MonkeyPatch) -> None:
    path = make_ready_file_db(_default_path())
    with writer(path) as conn:
        conn.execute("UPDATE db_metadata SET value = '1' WHERE key = 'build_version'")


def _no_home(monkeypatch: pytest.MonkeyPatch) -> None:
    # An empty USERPROFILE or HOME makes Path.home() relative: no home.
    monkeypatch.setattr(Path, "home", staticmethod(Path))


#: Each state's builder.
BUILDERS: dict[str, Callable[[pytest.MonkeyPatch], None]] = {
    USABLE: _usable,
    MISSING: _missing,
    INVALID: _invalid,
    EMPTY: _empty,
    OUTDATED: _outdated,
    NO_HOME: _no_home,
}


def refusal(state: str) -> str | None:
    """What reading the database in *state* raises, once built; None for a
    database that answers."""
    if state == NO_HOME:
        return "database: not found: no home directory; pass --db"
    path = get_default_db_path()
    return {
        MISSING: f"database: not found: {path}; run 'licenseid update'",
        INVALID: f"database: invalid: {path}",
        EMPTY: f"database: empty: {path}; run 'licenseid update'",
    }.get(state)


def build(state: str, monkeypatch: pytest.MonkeyPatch) -> str | None:
    """Put *state* in place; return what reading it raises (see refusal)."""
    BUILDERS[state](monkeypatch)
    return refusal(state)
