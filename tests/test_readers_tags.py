# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Task ``readers``, second round: a tag answers exact only what it read
whole, and the command line names what it refuses, on the whole 3.29.0
List.

Each test was first a pin of what the branch did (``# BUG:``); it now holds
the new answer.
"""
# pylint: disable=missing-function-docstring

import pytest
from click.testing import CliRunner
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import LicenseDatabase
from licenseid.cli import cli
from licenseid.detector import LicenseDetector


def _tag(corpus_db: LicenseDatabase, value: str) -> tuple[str, bool] | None:
    """The top answer of ``detect()`` for an SPDX tag of *value*."""
    found = LicenseDetector(corpus_db.location).detect(
        f"SPDX-License-Identifier: {value}"
    )
    return (found[0]["expression"], found[0]["exact"]) if found else None


# --- 1: a bare "or later" after an ID -----------------------------------------


@pytest.mark.parametrize(
    ("value", "answer"),
    [
        ("MIT or later", ("MIT OR later", True)),  # BUG: "later" as an ID
        ("MIT OR LATER", ("MIT OR LATER", True)),  # BUG
        ("(MIT) or later", ("MIT OR later", True)),  # BUG
        ("MIT or later version", ("MIT OR later", True)),  # BUG
        ("MIT or-later", ("MIT", True)),  # BUG: the grant dropped
        ("X OR later", None),
    ],
)
def test_a_bare_grant_in_a_tag(
    corpus_db: LicenseDatabase, value: str, answer: tuple[str, bool] | None
) -> None:
    assert _tag(corpus_db, value) == answer


# --- 2: an operand cut at a space ---------------------------------------------


@pytest.mark.parametrize(
    ("value", "answer"),
    [
        ("MIT OR Apache 2.0", ("MIT OR Apache", True)),  # BUG: cut at the space
        ("MIT OR BSD 3-Clause", ("MIT OR BSD", True)),  # BUG
        ("MIT AND Apache License 2.0", ("MIT AND Apache", True)),  # BUG
        ("GPL v2 OR MIT", None),
    ],
)
def test_an_operand_cut_at_a_space_in_a_tag(
    corpus_db: LicenseDatabase, value: str, answer: tuple[str, bool] | None
) -> None:
    assert _tag(corpus_db, value) == answer


# --- 3: an information separator given to detect ------------------------------


@pytest.mark.parametrize(
    ("args", "stderr"),
    [
        (["--text", "\x1f"], "ERROR: input: empty: --text\n"),  # BUG: blank
        (["--id", "\x1f"], "ERROR: option: invalid: --id: ; pass one license ID\n"),
    ],
    ids=["text", "id"],
)
def test_a_unit_separator_given_to_detect(
    corpus_db: LicenseDatabase, args: list[str], stderr: str
) -> None:
    result = CliRunner().invoke(cli, ["--db", corpus_db.location, "detect", *args])
    assert (result.exit_code, result.stderr) == (2, stderr)
