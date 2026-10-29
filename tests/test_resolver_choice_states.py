# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""What ``match()`` reads, and says, for every state of the database at
the default path, on a first call and on a repeat (characterisation of the
list choice, before it is kept per file stamp)."""
# pylint: disable=missing-function-docstring

import pytest
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from release_fakes import release_bundle, ship
from resolve_states import (
    EMPTY,
    INVALID,
    MISSING,
    NO_HOME,
    NO_ROWS,
    OUTDATED,
    OUTDATED_WARNING,
    UNREADABLE,
    USABLE,
    build,
)

from licenseid import match
from licenseid.datadir import get_default_db_path
from licenseid.errors import DatabaseNotReadyError

# The database is List 3.30; a bundle of 9.99 is newer, one of 3.29 older.
NEWER, OLDER = "9.99", "3.29"
# state, bundle: the source read, and the warning said by the first call
# ({path} is the default path); a repeat says nothing and reads the same.
CASES = [
    (USABLE, NEWER, "packaged", ""),
    (USABLE, OLDER, "database", ""),
    (OUTDATED, NEWER, "packaged", OUTDATED_WARNING),
    (OUTDATED, OLDER, "database", OUTDATED_WARNING),
    (MISSING, NEWER, "packaged", ""),
    (NO_HOME, NEWER, "packaged", ""),
    (INVALID, NEWER, "packaged", "database: invalid: {path}"),
    (EMPTY, NEWER, "packaged", "database: empty: {path}"),
    (NO_ROWS, NEWER, "packaged", "database: empty: {path}"),
]


def _warnings(err: str, path: str) -> str:
    return err.replace(path, "{path}")


@pytest.mark.parametrize("case", CASES, ids=[f"{c[0]}-{c[1]}" for c in CASES])
def test_auto_reads_and_says(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    case: tuple[str, str, str, str],
) -> None:
    state, bundle, source, warning = case
    ship(monkeypatch, release_bundle(bundle))
    build(state, monkeypatch)
    for _ in range(3):
        assert match("MIT")["lists"][0]["source"] == source
    err = capsys.readouterr().err
    if warning.startswith("database:"):
        warning = f"WARNING: {warning}; using packaged data v{bundle}\n"
    if state == NO_HOME:
        assert err == ""
    else:
        assert _warnings(err, str(get_default_db_path())) == warning


def test_auto_reads_a_directory_and_says_once(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    ship(monkeypatch, release_bundle(NEWER))
    build(UNREADABLE, monkeypatch)
    for _ in range(3):
        assert match("MIT")["lists"][0]["source"] == "packaged"
    err = capsys.readouterr().err
    assert err.count("WARNING: database: unreadable: ") == 1
    assert err.endswith(f"; using packaged data v{NEWER}\n")


@pytest.mark.parametrize(
    ("state", "condition"),
    [
        (MISSING, "not found"),
        (INVALID, "invalid"),
        (EMPTY, "empty"),
        (NO_ROWS, "empty"),
        (UNREADABLE, "unreadable"),
        (NO_HOME, "not found"),
    ],
)
def test_source_database_refuses_what_auto_calls_unusable(
    monkeypatch: pytest.MonkeyPatch, state: str, condition: str
) -> None:
    ship(monkeypatch, release_bundle(NEWER))
    build(state, monkeypatch)
    for _ in range(2):
        with pytest.raises(DatabaseNotReadyError) as raised:
            match("MIT", source="database")
        assert raised.value.condition == condition


@pytest.mark.parametrize("state", [USABLE, OUTDATED])
def test_source_database_reads_a_usable_one(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], state: str
) -> None:
    ship(monkeypatch, release_bundle(NEWER))
    build(state, monkeypatch)
    for _ in range(3):
        assert match("MIT", source="database")["lists"][0]["source"] == "database"
    assert capsys.readouterr().err == (OUTDATED_WARNING if state == OUTDATED else "")


@pytest.mark.parametrize("state", [MISSING, INVALID, EMPTY, UNREADABLE, NO_HOME])
def test_auto_without_a_bundle_raises_the_database_error(
    monkeypatch: pytest.MonkeyPatch, state: str
) -> None:
    ship(monkeypatch, None)
    build(state, monkeypatch)
    for _ in range(2):
        with pytest.raises(DatabaseNotReadyError):
            match("MIT")
