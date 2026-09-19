# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""CLI smart argument tests for licenseid."""
# pylint: disable=redefined-outer-name,duplicate-code,missing-function-docstring

from collections.abc import Generator
from typing import Any
from unittest import mock

import pytest
from click.testing import CliRunner
from conftest import make_mit_db_path

from licenseid.cli import cli
from licenseid.matcher import AggregatedLicenseMatcher


@pytest.fixture
def test_db() -> Generator[str, None, None]:
    # A stale timestamp: these tests also see the staleness warning.
    db_path, keep_alive = make_mit_db_path("test_cli", "2026-01-01T00:00:00")
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


@pytest.mark.parametrize("via", ["file", "stdin"])
def test_cli_match_input_newlines_are_normalised(
    test_db: str, tmp_path: Any, via: str
) -> None:
    """Characterisation: text-mode reading turned CRLF and CR into LF before
    matching; reading bytes must keep doing that."""
    raw = b"Permission is hereby granted\r\nfree of charge\rto any person\n"
    with mock.patch.object(
        AggregatedLicenseMatcher, "match", autospec=True, return_value=[]
    ) as match:
        if via == "file":
            path = tmp_path / "LICENSE"
            path.write_bytes(raw)
            CliRunner().invoke(cli, ["--db", test_db, "match", str(path)])
        else:
            CliRunner().invoke(cli, ["--db", test_db, "match"], input=raw)
    assert match.call_args.kwargs["text"] == (
        "Permission is hereby granted\nfree of charge\nto any person\n"
    )


_LATIN1_MIT = (
    "Permission is hereby granted, free of charge, to any person obtaining a copy"
    " (J\u00e9r\u00f4me)"
).encode("latin-1")


@pytest.mark.parametrize("via", ["file", "stdin"])
def test_cli_match_latin1_input_warns_and_matches(
    test_db: str, tmp_path: Any, via: str
) -> None:
    if via == "file":
        path = tmp_path / "LICENSE"
        path.write_bytes(_LATIN1_MIT)
        result = CliRunner().invoke(cli, ["--db", test_db, "match", str(path)])
        source = str(path)
    else:
        result = CliRunner().invoke(cli, ["--db", test_db, "match"], input=_LATIN1_MIT)
        source = "stdin"
    assert result.exit_code == 0, result.output
    assert "LICENSE_ID=MIT" in result.stdout
    assert f"WARNING: input: not UTF-8, read as Latin-1: {source}" in (
        result.stderr.splitlines()
    )
