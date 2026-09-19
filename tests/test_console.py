# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Tests for the shared diagnostic output helpers."""
# pylint: disable=missing-function-docstring

import pytest
from conftest import DIAGNOSTIC_RE

from licenseid.console import error, status, warn


def test_warn_writes_prefixed_line_to_stderr_only(
    capsys: pytest.CaptureFixture[str],
) -> None:
    warn("popularity.csv: using stale cache")
    captured = capsys.readouterr()
    assert captured.err == "WARNING: popularity.csv: using stale cache\n"
    assert captured.out == ""


def test_status_writes_to_stderr_only_and_honours_end(
    capsys: pytest.CaptureFixture[str],
) -> None:
    status("Working", end="")
    status(".", end="")
    status(" done.")
    captured = capsys.readouterr()
    assert captured.err == "Working. done.\n"
    assert captured.out == ""


def test_error_writes_prefixed_line_to_stderr_only(
    capsys: pytest.CaptureFixture[str],
) -> None:
    error("database: not found: x.db")
    captured = capsys.readouterr()
    assert captured.err == "ERROR: database: not found: x.db\n"
    assert captured.out == ""


@pytest.mark.parametrize(
    "line",
    [
        "WARNING: Something is off.",
        "ERROR: Database not found at x.db",
        "ERROR: database: Not found",
        "WARNING: no subject here",
    ],
)
def test_grammar_rejects_free_prose(line: str) -> None:
    assert not DIAGNOSTIC_RE.fullmatch(line)


@pytest.mark.parametrize(
    "line",
    [
        (
            "WARNING: popularity.csv: 3 rows with missing or non-numeric "
            "num_pushers; counted as 0"
        ),
        (
            "ERROR: spdx-data-v9.99.tar.gz: cache unusable: bad gzip; removed, "
            "run 'licenseid update' again"
        ),
        "ERROR: database: not found: /tmp/x.db; run 'licenseid update'",
    ],
)
def test_grammar_accepts_diagnostics(line: str) -> None:
    assert DIAGNOSTIC_RE.fullmatch(line)
