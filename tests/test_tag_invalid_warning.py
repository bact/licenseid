# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A tag value with a non-ASCII letter in an ID is refused whole and said:
``WARNING: input: invalid: <value>`` (roadmap item 33). An idstring holds
ASCII only (SPDX 3.0.1, license expressions annex)."""
# pylint: disable=redefined-outer-name,missing-function-docstring

import time
from collections.abc import Generator
from pathlib import Path

import pytest
from click.testing import CliRunner
from conftest import GivenWarnings
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from spdx_tag_helpers import source_with, tag_db

from licenseid import resolve
from licenseid.cli import cli
from licenseid.detector import LicenseDetector
from licenseid.markers import _cut_by_non_ascii  # pylint: disable=protected-access


@pytest.fixture
def db() -> Generator[str, None, None]:
    yield from tag_db("test_tag_invalid_warning")


INVALID = [
    "LicenseRef-café",
    "MIT-ü",
    "MIT AND LicenseRef-ß",
    "MIT AND (Apache-2.0-ü)",
    "(MIT-ü)",
    "MIT OR LicenseRef-café */",  # a comment closer after it
]

#: No warning: valid, prose after an expression, or no match for another cause.
QUIET = [
    "MIT",
    "MIT AND Apache-2.0",
    "MIT ü",  # a word apart
    "MIT€",
    "MIT-許",
    "LicenseRef-cafe",
    "Unknown-1.0",  # a valid shape, no such licence
    "not an expression at all",
    "MIT AND",
]


@pytest.mark.parametrize("value", INVALID, ids=ascii)
def test_invalid_value_warns_and_answers_nothing(
    db: str, value: str, given: GivenWarnings
) -> None:
    results = LicenseDetector(db).detect(text=source_with(value))
    assert [r for r in results if r["method"] != "text"] == []  # no tag answer
    (warn,) = given.take()
    assert (warn.subject, warn.condition) == ("input", "invalid")
    assert warn.detail == value
    assert warn.action is None


@pytest.mark.parametrize("value", QUIET, ids=ascii)
def test_other_values_do_not_warn(db: str, value: str, given: GivenWarnings) -> None:
    LicenseDetector(db).detect(text=source_with(value))
    assert "invalid" not in given.conditions()


def test_valid_tag_beside_an_invalid_one_still_reads(
    db: str, given: GivenWarnings
) -> None:
    text = "SPDX-License-Identifier: LicenseRef-café SPDX-License-Identifier: MIT\n"
    results = LicenseDetector(db).detect(text=text)
    assert [r["expression"] for r in results[:1]] == ["MIT"]
    (warn,) = given.take()
    assert warn.detail == "LicenseRef-café"


def test_the_same_value_warns_once(db: str, given: GivenWarnings) -> None:
    tag = "SPDX-License-Identifier: MIT-ü\n"
    LicenseDetector(db).detect(text=tag * 3)
    assert len(given.take()) == 1


def test_cli_prints_the_warning_line(db: str, tmp_path: Path) -> None:
    path = tmp_path / "source.c"
    path.write_text(source_with("MIT-ü"), encoding="utf-8")
    result = CliRunner().invoke(cli, ["--db", db, "detect", str(path)])
    assert result.exit_code == 1
    assert "WARNING: input: invalid: MIT-ü\n" in result.stderr


@pytest.mark.parametrize("value", [v for v in INVALID if "*/" not in v], ids=ascii)
def test_resolve_refuses_with_a_reason(db: str, value: str) -> None:
    result = resolve(value, db)
    assert result["expression"] is None
    assert result["reason"]


@pytest.mark.parametrize("size", [2_000, 4_000])
def test_the_check_is_not_quadratic(size: int) -> None:
    started = time.monotonic()
    assert not _cut_by_non_ascii("x" + " " * size)
    assert not _cut_by_non_ascii("ü" + " " * size)
    assert time.monotonic() - started < 2
