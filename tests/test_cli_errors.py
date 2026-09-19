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


_PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"


@pytest.mark.parametrize("command", ["match", "is-osi"])
def test_binary_input_file(empty_db: str, tmp_path: Path, command: str) -> None:
    path = tmp_path / "logo.png"
    path.write_bytes(_PNG)
    result = CliRunner().invoke(cli, ["--db", empty_db, command, str(path)])
    assert result.exit_code == 2
    assert result.stdout == ""
    assert result.stderr == f"ERROR: input: binary file: {path}\n"


@pytest.mark.parametrize("text", ["MIT\\x00", "\\0"])
def test_binary_text_option(empty_db: str, text: str) -> None:
    """A NUL from a --text escape is rejected as it is from a file or stdin."""
    result = CliRunner().invoke(cli, ["--db", empty_db, "match", "--text", text])
    assert result.exit_code == 2
    assert result.stdout == ""
    assert result.stderr == "ERROR: input: binary file: --text\n"


def test_binary_stdin(empty_db: str) -> None:
    result = CliRunner().invoke(cli, ["--db", empty_db, "match"], input=_PNG)
    assert result.exit_code == 2
    assert result.stdout == ""
    assert result.stderr == "ERROR: input: binary file: stdin\n"


@pytest.mark.parametrize("command", ["match", "is-osi"])
def test_unreadable_input_path(empty_db: str, tmp_path: Path, command: str) -> None:
    directory = tmp_path / "LICENSES"
    directory.mkdir()
    result = CliRunner().invoke(cli, ["--db", empty_db, command, str(directory)])
    assert result.exit_code == 2
    assert result.stdout == ""
    # The reason is the OS's strerror text, which varies by platform/locale.
    assert result.stderr.startswith(f"ERROR: input: unreadable: {directory}: ")
    assert result.stderr.count("\n") == 1


@pytest.mark.parametrize("content", [b"", b"\xef\xbb\xbf", b"  \r\n\t\n"])
@pytest.mark.parametrize("command", ["match", "is-osi"])
def test_empty_input_file(
    empty_db: str, tmp_path: Path, command: str, content: bytes
) -> None:
    """A file was given, so "missing; pass a file..." would be wrong."""
    path = tmp_path / "LICENSE"
    path.write_bytes(content)
    result = CliRunner().invoke(cli, ["--db", empty_db, command, str(path)])
    assert result.exit_code == 2
    assert result.stdout == ""
    assert result.stderr == f"ERROR: input: empty: {path}\n"
