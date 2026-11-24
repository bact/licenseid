# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A database of build 4 has no ``core_text``, ``core_word_count`` or
``same_text``: it is read as it is (no core, no twin). Opening it writes
nothing, so a read-only file answers and no file changes; ``update`` adds the
columns inside the rebuild."""
# pylint: disable=missing-function-docstring

import hashlib
import os
import stat
from collections.abc import Iterator
from pathlib import Path

import pytest
from click.testing import CliRunner
from conftest import GivenWarnings, posix_only
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from db_variants import writer
from list_entries import lic_entry
from packaged_list import database_of, synthetic_bundle

from licenseid import resolve
from licenseid.cli import cli
from licenseid.database import LicenseDatabase
from licenseid.dbconnection import Connections
from licenseid.dbschema import schema_state
from licenseid.records import BUILD_VERSION

LICENSES = (lic_entry("MIT", "MIT License"),)
RAW = synthetic_bundle(LICENSES, {"MIT": "Text of MIT."})
NEW = ("core_text", "core_word_count", "same_text")
OUTDATED = (
    f"WARNING: database: build v4 outdated: current v{BUILD_VERSION}"
    "; run 'licenseid update'\n"
)


def _columns(path: Path) -> set[str]:
    with writer(path) as conn:
        return {row[1] for row in conn.execute("PRAGMA table_info(licenses)")}


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(name="build_4")
def _build_4(tmp_path: Path) -> Path:
    """A database as build 4 left it: no build-5 columns, stamped 4."""
    path = tmp_path / "licenses.db"
    database_of(RAW, path)
    with writer(path) as conn:
        for column in NEW:
            conn.execute(f"ALTER TABLE licenses DROP COLUMN {column}")
        conn.execute("UPDATE db_metadata SET value = '4' WHERE key = 'build_version'")
    return path


@pytest.fixture(name="mode_444")
def _mode_444() -> Iterator[list[Path]]:
    made: list[Path] = []
    yield made
    for path in made:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def test_a_database_of_build_4_is_current(build_4: Path) -> None:
    location = str(build_4)
    assert schema_state(Connections(location, False, location, False)) == "current"


def test_opening_a_writable_database_of_build_4_writes_nothing(
    build_4: Path, given: GivenWarnings
) -> None:
    before = _digest(build_4)
    result = CliRunner().invoke(cli, ["--db", str(build_4), "detect", "MIT"])
    assert result.exit_code == 0, result.stderr
    assert result.stderr == OUTDATED
    assert resolve("MIT", str(build_4))["expression"] == "MIT"
    assert given.conditions() == {"build v4 outdated"}
    assert _digest(build_4) == before
    assert not set(NEW) & _columns(build_4)


@posix_only
def test_a_read_only_database_of_build_4_answers(
    build_4: Path, mode_444: list[Path]
) -> None:
    build_4.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    mode_444.append(build_4)
    if os.access(build_4, os.W_OK):  # root writes whatever the mode says
        pytest.skip("this user writes to a mode-444 file")
    before = _digest(build_4)
    result = CliRunner().invoke(
        cli, ["--db", str(build_4), "detect", "--text", "MIT License"]
    )
    assert result.exit_code == 0, result.stderr
    assert result.stdout.startswith("EXPRESSION=MIT")
    assert result.stderr == OUTDATED
    assert _digest(build_4) == before


def test_update_adds_the_columns_and_rebuilds(build_4: Path) -> None:
    database = database_of(RAW, build_4)
    assert database.get_metadata()["build_version"] == BUILD_VERSION
    assert set(NEW) <= _columns(build_4)
    assert LicenseDatabase(str(build_4), create=False).get_metadata()
