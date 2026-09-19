# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""CLI error messages: exact text on stderr, nothing on stdout, exit code."""
# pylint: disable=redefined-outer-name,missing-function-docstring

from collections.abc import Generator
from pathlib import Path

import pytest
from click.testing import CliRunner
from conftest import make_memory_db_path

from licenseid.cli import cli


@pytest.fixture
def empty_db() -> Generator[str, None, None]:
    db_path, keep_alive = make_memory_db_path("test_cli_errors")
    yield db_path
    keep_alive.close()


@pytest.mark.parametrize("command", ["match", "is-osi"])
def test_missing_database(tmp_path: Path, command: str) -> None:
    db_path = tmp_path / "absent.db"
    result = CliRunner().invoke(cli, ["--db", str(db_path), command, "MIT"])
    assert result.exit_code == 2
    assert result.stdout == ""
    assert result.stderr == (
        f"ERROR: database: not found: {db_path}; run 'licenseid update'\n"
    )


@pytest.mark.parametrize("command", ["match", "is-osi"])
def test_missing_input(empty_db: str, command: str) -> None:
    result = CliRunner().invoke(cli, ["--db", empty_db, command], input="")
    assert result.exit_code == 2
    assert result.stdout == ""
    assert result.stderr == (
        "ERROR: input: missing; pass a file, an ID, --text, --id or stdin\n"
    )


@pytest.mark.parametrize("extra", [[], ["--bold"]])
def test_no_match(empty_db: str, extra: list[str]) -> None:
    result = CliRunner().invoke(
        cli, ["--db", empty_db, "match", "--id", "No-Such-License", *extra]
    )
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == "ERROR: match: no license found\n"
