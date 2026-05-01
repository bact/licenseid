# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""CLI smart argument tests for licenseid."""
# pylint: disable=redefined-outer-name,duplicate-code,missing-function-docstring

import sqlite3
import uuid
from typing import Any, Generator

import pytest
from click.testing import CliRunner

from licenseid.cli import cli
from licenseid.database import LicenseDatabase


@pytest.fixture
def test_db() -> Generator[str, None, None]:
    db_id = str(uuid.uuid4())[:8]
    db_path = f"file:test_cli_{db_id}?mode=memory&cache=shared"

    db_manager = LicenseDatabase(db_path)  # pylint: disable=unused-variable # noqa: F841
    keep_alive = sqlite3.connect(db_path, uri=True)

    with sqlite3.connect(db_path, uri=True) as conn:
        conn.execute(
            "INSERT INTO licenses (license_id, name, is_spdx, is_osi_approved, "
            "is_fsf_libre) VALUES (?, ?, ?, ?, ?)",
            ("MIT", "MIT License", True, True, True),
        )
        conn.execute(
            "INSERT INTO license_index (license_id, search_text) VALUES (?, ?)",
            (
                "MIT",
                "permission is hereby granted free of charge to any person "
                "obtaining a copy",
            ),
        )
        conn.execute(
            "INSERT INTO db_metadata (key, value) VALUES (?, ?)",
            ("last_check_datetime", "2026-01-01T00:00:00"),
        )
    yield db_path
    keep_alive.close()


def test_cli_match_smart_id(test_db: str) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--db", test_db, "match", "MIT"])
    assert result.exit_code == 0
    assert "LICENSE_ID=MIT" in result.output


def test_cli_match_smart_file(test_db: str, tmp_path: Any) -> None:
    runner = CliRunner()
    license_file = tmp_path / "LICENSE"
    license_file.write_text("Permission is hereby granted...")

    result = runner.invoke(cli, ["--db", test_db, "match", str(license_file)])
    assert result.exit_code == 0
    assert "LICENSE_ID=MIT" in result.output


def test_cli_is_osi_smart(test_db: str) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--db", test_db, "is-osi", "MIT"])
    assert result.exit_code == 0
    assert "true" in result.output

    result = runner.invoke(cli, ["--db", test_db, "is-osi", "NonExistent"])
    assert result.exit_code == 1
    assert "false" in result.output


def test_cli_explicit_id(test_db: str, tmp_path: Any) -> None:
    runner = CliRunner()
    file_named_mit = tmp_path / "MIT"
    file_named_mit.write_text("Random junk text")

    result = runner.invoke(cli, ["--db", test_db, "match", "--id", "MIT"])
    assert result.exit_code == 0
    assert "LICENSE_ID=MIT" in result.output
    assert "SIMILARITY=1.0000" in result.output


def test_cli_stdin(test_db: str) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--db", test_db, "is-osi"], input="MIT")
    assert result.exit_code == 0
    assert "true" in result.output
